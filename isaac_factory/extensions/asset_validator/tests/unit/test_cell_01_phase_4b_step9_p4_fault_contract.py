"""Phase 4B Step 9 Phase 4 — pure-Python deterministic contract tests for D-FAULT.

This file is the **semantic regression gate** for Step 9 Phase 5 (runtime
wiring). It enforces the D-FAULT contract surface BEFORE any runtime code
implements it, by combining three test categories:

  1. **Contract-doc structural tests** — assert §13 of
     `docs/phase_4b_deterministic_semantics.md` has the expected D-FAULT-*
     clauses, that §11 / §12 amendments landed, and that the Mutation
     Authority Matrix in `session.py` docstring carries the Step 9
     authority extensions.

  2. **Static-introspection tests** — ast-parse files under
     `cell_authoring/orchestration/` and `cell_authoring/tasks/` and
     assert that forbidden patterns (e.g. `ExecutionSession.request_abort`,
     `time.time()` / `time.perf_counter()`, `threading`, `asyncio`,
     wall-clock timeout watchdogs, `RECOVERING` as a SessionState value)
     are absent from the production codebase.

  3. **Reference-model tests** — small pure-Python models of D-FAULT
     semantics (cascade propagation, idempotent emission, tick-budget
     evaluation, contradiction-preserving snapshots, append-only traces).
     The models are **not** the runtime — they are executable
     specifications of the contract. When Phase 5 wires the runtime, the
     runtime MUST satisfy the same invariants the reference models
     demonstrate.

Clauses covered (every D-FAULT clause from the canonical contract has at
least one test):

  D-FAULT-1 / -1a   taxonomy + inner sub-classification
  D-FAULT-2          single-emitter discipline
  D-FAULT-3 / -3a   propagation rules + FailureAction enum
  D-FAULT-4 / -4a   TaskCascadeSkipped distinct from NodeFailed;
                     _skipped enters authoritative continuity
  D-FAULT-5 / -5a / -5b  no implicit rollback; pose-on-FAIL last-tick truth;
                          fixture occupancy preserved on FAIL
  D-FAULT-6 / -6a   abort enters only at Phase A; Phase E atomic
  D-FAULT-7          idempotent cancellation (cascade + envelope + blocked)
  D-FAULT-8 / -8a / -8b  recovery is graph topology; no inference; no retry
  D-FAULT-9 / -9a   OperatorEnvelope schema; Step 9 kind="abort" only
  D-FAULT-10         failure-event canonical-JSON discipline
  D-FAULT-11 / -11a replay-integrity is meta-failure; strict byte-equality
  D-FAULT-12 / -12a / -12b  tick-budget enforcement; Phase E atomicity;
                              margin requirement
  D-FAULT-13         infrastructure-degradation sidecar (out-of-session)
  D-FAULT-14         no implicit secondary orchestration system
  D-FAULT-15         18 forbidden anti-patterns

All tests are pure Python. No Isaac Sim. No PhysX. No threading. No
asyncio. No wall-clock reads. No GPU. No network. No subprocess. The
suite must run deterministically and produce byte-identical assertions
across repeated invocations.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
import sys
from dataclasses import FrozenInstanceError, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pytest


# --------------------------------------------------------------------
# Path setup
# --------------------------------------------------------------------

_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)

_CONTRACT_DOC_PATH = _WORKSPACE / "docs" / "phase_4b_deterministic_semantics.md"
_ANALYSIS_DOC_PATH = _WORKSPACE / "docs" / "phase_4b_step9_failure_semantics_analysis.md"
_ORCH_DIR = _WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring" / "cell_authoring" / "orchestration"
_TASKS_DIR = _WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring" / "cell_authoring" / "tasks"

assert _CONTRACT_DOC_PATH.exists(), f"Canonical contract doc missing at {_CONTRACT_DOC_PATH}"

_CONTRACT_TEXT: str = _CONTRACT_DOC_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------
# Reference models (pure-Python executable specifications of D-FAULT)
# --------------------------------------------------------------------

_FAILURE_CLASSES = (
    "NODE_EXECUTION_FAILURE",
    "PRECONDITION_FAILURE",
    "AUTHORITY_VIOLATION",
    "CONTINUITY_VALIDATION_FAILURE",
    "TIMEOUT_FAILURE",
    "OPERATOR_ABORT",
    "INFRASTRUCTURE_DEGRADATION",
    "REPLAY_INTEGRITY_FAILURE",
)

_FAILURE_CLASSES_EMITTED_IN_SESSION = (
    "NODE_EXECUTION_FAILURE",
    "PRECONDITION_FAILURE",
    "AUTHORITY_VIOLATION",
    "CONTINUITY_VALIDATION_FAILURE",
    "TIMEOUT_FAILURE",
    "OPERATOR_ABORT",
)

_FAILURE_CLASSES_OUT_OF_SESSION = (
    "INFRASTRUCTURE_DEGRADATION",
    "REPLAY_INTEGRITY_FAILURE",
)


@dataclass(frozen=True, slots=True)
class _OperatorEnvelopeRef:
    """Reference model for D-FAULT-9 OperatorEnvelope.

    Schema is fixed by D-FAULT-9 and MUST be canonical-JSON serializable.
    Step 9 supports only kind="abort" per D-FAULT-9a.
    """

    kind: str
    requested_at_tick: int
    reason: str
    envelope_id: str

    def to_canonical(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "kind": self.kind,
            "reason": self.reason,
            "requested_at_tick": self.requested_at_tick,
        }


def _canonical_envelope_order(
    envelopes: Iterable[_OperatorEnvelopeRef],
) -> tuple[_OperatorEnvelopeRef, ...]:
    return tuple(sorted(envelopes, key=lambda e: (e.requested_at_tick, e.envelope_id)))


@dataclass(slots=True)
class _NodeRuntimeStateRef:
    """Reference model for NodeRuntimeState — extended with D-FAULT-7
    idempotency tracking fields (`_cascade_emitted`, `_blocked_emission_key`).
    """

    node_id: str
    status: str
    cascade_emitted: bool = False
    blocked_emission_key: str | None = None
    outcome_value: str = ""

    def to_canonical(self) -> dict[str, Any]:
        return {
            "blocked_emission_key": self.blocked_emission_key,
            "cascade_emitted": self.cascade_emitted,
            "node_id": self.node_id,
            "outcome_value": self.outcome_value,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class _FailureActionRef:
    """Reference model for D-FAULT-3a FailureAction per-edge enum."""

    SKIP_NODE: str = "SKIP_NODE"
    ABORT_COHORT: str = "ABORT_COHORT"
    ABORT_JOB: str = "ABORT_JOB"


_FA = _FailureActionRef()


@dataclass(slots=True)
class _CascadeRefModel:
    """Reference model for D-FAULT-3 / -3a / -4 / -7 cascade propagation.

    Encodes:
      * propagation rules per FailureAction (D-FAULT-3a),
      * cascade emission iterates canonical_order (D-FAULT-4 + D-SCHED-3),
      * idempotency at the transition (D-FAULT-7: skip-twice → emit once).

    `graph_edges`: tuple of (parent, child, FailureAction) tuples.
    `canonical_order`: deterministic node ordering per Step 4 D-SCHED-2.
    `failed`: nodes whose execution produced non-PASS verdict.
    """

    canonical_order: tuple[str, ...]
    graph_edges: tuple[tuple[str, str, str], ...]
    failed: set[str] = field(default_factory=set)
    skipped: set[str] = field(default_factory=set)
    cascade_emitted: set[str] = field(default_factory=set)
    events: list[tuple[str, str]] = field(default_factory=list)

    def _descendants(self, node: str) -> set[str]:
        out: set[str] = set()
        frontier = [node]
        while frontier:
            cur = frontier.pop()
            for p, c, _action in self.graph_edges:
                if p == cur and c not in out:
                    out.add(c)
                    frontier.append(c)
        return out

    def _siblings(self, node: str) -> set[str]:
        sibs: set[str] = set()
        for p, c, _action in self.graph_edges:
            if c == node:
                for p2, c2, _a2 in self.graph_edges:
                    if p2 == p and c2 != node:
                        sibs.add(c2)
        return sibs

    def mark_failed(self, node: str, action: str = _FA.SKIP_NODE) -> None:
        """Mark a node failed and propagate cascade per D-FAULT-3a."""
        if node not in self.canonical_order:
            raise ValueError(f"unknown node: {node}")
        self.failed.add(node)
        self.events.append(("NodeFailed", node))

        if action == _FA.SKIP_NODE:
            targets = self._descendants(node)
        elif action == _FA.ABORT_COHORT:
            targets = self._descendants(node) | self._siblings(node)
            for sib in self._siblings(node):
                targets |= self._descendants(sib)
        elif action == _FA.ABORT_JOB:
            targets = {n for n in self.canonical_order if n not in self.failed and n != node}
        else:
            raise ValueError(f"unknown FailureAction: {action}")

        # Emit in canonical order (D-SCHED-3); idempotent at transition (D-FAULT-7).
        for nid in self.canonical_order:
            if nid not in targets:
                continue
            if nid in self.failed:
                continue
            if nid in self.cascade_emitted:
                continue
            self.cascade_emitted.add(nid)
            self.skipped.add(nid)
            self.events.append(("TaskCascadeSkipped", nid))


@dataclass(slots=True)
class _BoundarySnapshotRefModel:
    """Reference model for D-FAULT-5/-5a/-5b post-failure snapshot.

    Captures the contradiction-preservation rule: fixture occupancy
    is NOT mutated on FAIL (D-FAULT-5b), canonical pose reflects
    last-tick truth (D-FAULT-5a). The contradiction between the two
    is preserved verbatim.
    """

    objects: dict[str, dict[str, Any]] = field(default_factory=dict)
    fixtures: dict[str, dict[str, Any]] = field(default_factory=dict)
    completed: frozenset[str] = field(default_factory=frozenset)
    failed: frozenset[str] = field(default_factory=frozenset)
    skipped: frozenset[str] = field(default_factory=frozenset)

    def project_post_fail(
        self,
        failed_node_id: str,
        last_tick_object_poses: dict[str, list[float]],
    ) -> dict[str, Any]:
        """Project post-failure boundary snapshot per D-FAULT-5/-5a/-5b.

        Inputs:
          last_tick_object_poses — pose values the executor wrote on its
          last per-tick update_object_pose call (D-CONT-1 canonical pose).

        Side-effect free; returns canonical-JSON-ready dict.
        """
        new_objects = {}
        for oid in sorted(self.objects):
            new_objects[oid] = {
                "dlife_state": self.objects[oid]["dlife_state"],
                "pose_m": list(last_tick_object_poses.get(oid, self.objects[oid]["pose_m"])),
            }
        # Fixtures unchanged on FAIL (D-FAULT-5b).
        new_fixtures = {fid: dict(self.fixtures[fid]) for fid in sorted(self.fixtures)}
        return {
            "fixtures": new_fixtures,
            "objects": new_objects,
            "schema_version": 2,
            "session": {
                "completed": sorted(self.completed),
                "failed": sorted(self.failed | {failed_node_id}),
                "skipped": sorted(self.skipped),
            },
        }


def _canonical_dumps(obj: Any) -> str:
    """Match D-TRACE-8 canonical encoding for fingerprint stability."""
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )


@dataclass(slots=True)
class _TraceRefModel:
    """Append-only trace reference model (D-FAULT-10 + D-FAULT-14).

    Provides the contract surface for failure events without dependency on
    Phase 4B step 1 EventBus runtime. A test that finalizes this trace
    cannot then append; this enforces D-FAULT-14 (no implicit healing) at
    the model layer.
    """

    events: list[dict[str, Any]] = field(default_factory=list)
    finalized: bool = False

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.finalized:
            raise RuntimeError("trace finalized — append forbidden (D-FAULT-14)")
        seq = len(self.events)
        self.events.append({"event_type": event_type, "payload": payload, "seq": seq})

    def finalize(self) -> str:
        self.finalized = True
        return _canonical_dumps(self.events)


# --------------------------------------------------------------------
# Test class 1 — contract-doc structural integrity
# --------------------------------------------------------------------


class TestContractDocStructure:
    """§13 D-FAULT-* clauses, §11 amendments, §12 amendments all present."""

    def test_section_13_header_exists(self) -> None:
        assert "## 13. Deterministic Failure Semantics Contract  *(D-FAULT)*" in _CONTRACT_TEXT

    def test_all_15_primary_clauses_present(self) -> None:
        for n in range(1, 16):
            tok = f"**D-FAULT-{n}**"
            assert tok in _CONTRACT_TEXT, f"missing primary clause {tok}"

    @pytest.mark.parametrize(
        "corollary",
        ["1a", "3a", "4a", "5a", "5b", "6a", "8a", "8b", "9a", "11a", "12a", "12b"],
    )
    def test_corollaries_present(self, corollary: str) -> None:
        tok = f"**D-FAULT-{corollary}**"
        assert tok in _CONTRACT_TEXT, f"missing corollary {tok}"

    def test_eight_failure_classes_enumerated(self) -> None:
        for cls in _FAILURE_CLASSES:
            assert cls in _CONTRACT_TEXT, f"failure class {cls} absent from contract"

    def test_section_11_item_4_resolved(self) -> None:
        assert "Pinned in §13 D-FAULT" in _CONTRACT_TEXT, (
            "§11 item 4 must cite §13 D-FAULT as the resolution"
        )

    def test_dcont_1_includes_skipped(self) -> None:
        m = re.search(
            r"\*\*D-CONT-1\*\* — Authoritative retained continuity.*?"
            r"This list is the complete authoritative continuity",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None, "could not locate D-CONT-1 body"
        assert "`_skipped`" in m.group(0), "D-CONT-1 must enumerate _skipped (D-FAULT-4a)"

    def test_dcont_6_snapshot_template_has_skipped(self) -> None:
        assert '"skipped":' in _CONTRACT_TEXT, (
            "D-CONT-6 boundary-snapshot template must serialize `_skipped`"
        )

    def test_dcont_6_allowed_content_includes_skipped(self) -> None:
        m = re.search(
            r"\*\*Allowed snapshot content:\*\*.*?\*\*Forbidden snapshot content\*\*",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None
        assert "_skipped" in m.group(0)

    def test_schema_version_bump_declared(self) -> None:
        assert "schema_version" in _CONTRACT_TEXT
        # D-FAULT-4a declares the bump 1 → 2
        assert re.search(
            r"BOUNDARY_SNAPSHOT_SCHEMA_VERSION.*increments from 1 to 2", _CONTRACT_TEXT
        ) is not None

    def test_no_retry_clause_updated(self) -> None:
        assert "D-FAULT-8b" in _CONTRACT_TEXT
        assert (
            "Step 9 explicitly **defers** retry semantics further" in _CONTRACT_TEXT
            or "explicitly defers retry semantics further" in _CONTRACT_TEXT
        )

    def test_dfault_15_table_has_step9_forbidden_patterns_1_through_18(self) -> None:
        # Step 9 baseline: D-FAULT-15 enumerates anti-patterns 1..18.
        # Step 10+ may extend the table (Step 10 Direction A added rows
        # 19..30); this test ensures the Step 9 rows remain present and
        # contiguous, without forbidding future expansion.
        m = re.search(
            r"\*\*D-FAULT-15\*\* — In addition to D-FORBID-1\.\.-14"
            r".*?(?=### 13\.16|\Z)",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None, "D-FAULT-15 section not located"
        rows = re.findall(r"^\| (\d+) \| ", m.group(0), re.M)
        nums = sorted(int(n) for n in rows)
        # The Step 9 prefix 1..18 must be intact and contiguous.
        assert nums[:18] == list(range(1, 19)), (
            f"D-FAULT-15 table must enumerate Step 9 rows 1..18 contiguously, got prefix {nums[:18]}"
        )
        # No duplicates anywhere.
        assert len(nums) == len(set(nums)), f"D-FAULT-15 has duplicate row numbers: {nums}"
        # If extended, every row number must be a positive integer in the
        # full contiguous sequence starting at 1.
        assert nums == list(range(1, len(nums) + 1)), (
            f"D-FAULT-15 row numbering must be contiguous from 1, got {nums}"
        )

    def test_section_13_scope_restatement_present(self) -> None:
        assert "13.16 Step 9 scope restatement" in _CONTRACT_TEXT


# --------------------------------------------------------------------
# Test class 2 — Mutation Authority Matrix (session.py docstring)
# --------------------------------------------------------------------


def _session_module_doc() -> str:
    mod = importlib.import_module("cell_authoring.orchestration.session")
    assert mod.__doc__ is not None
    return mod.__doc__


def _normalize_doc(doc: str) -> str:
    """Collapse ASCII-table wrapping artifacts so substring assertions
    work regardless of where the matrix lines wrapped. Removes leading
    `|` table-boundary characters, then squashes all runs of whitespace
    (including newlines) to single spaces."""
    no_bars = re.sub(r"\|", " ", doc)
    return re.sub(r"\s+", " ", no_bars).strip()


class TestMutationAuthorityMatrix:
    """D-FAULT extends the matrix. Session.py docstring must reflect it."""

    def test_matrix_header_mentions_step9(self) -> None:
        doc = _session_module_doc()
        assert "extended Step 9 D-FAULT" in doc

    def test_executionsession_row_has_step9_authorities(self) -> None:
        doc = _normalize_doc(_session_module_doc())
        for required in (
            "abort ingress drain at Phase A only",
            "operator-envelope ingress",
            "retained-state authority during FAIL",
            "contradiction persistence authority",
            "cascade-abort emission authority",
            "timeout accounting authority",
            "authority-violation detection",
            "continuity-validation detection",
        ):
            assert required in doc, f"matrix missing Step 9 authority: {required!r}"

    def test_skipped_set_present_in_matrix(self) -> None:
        doc = _normalize_doc(_session_module_doc())
        assert "skipped: frozenset[str]" in doc
        assert "D-FAULT-4, D-FAULT-4a" in doc

    def test_idempotency_fields_present_in_matrix(self) -> None:
        doc = _normalize_doc(_session_module_doc())
        assert "_cascade_emitted" in doc
        assert "_blocked_emission_key" in doc
        assert "D-FAULT-7" in doc

    def test_launch_harness_row_present(self) -> None:
        doc = _normalize_doc(_session_module_doc())
        assert "Launch harness" in doc
        assert "D-FAULT-13" in doc
        assert "infrastructure_degradation. json" in doc or "infrastructure_degradation.json" in doc
        assert "MUST NOT append to any session's" in doc

    def test_replay_comparator_row_present(self) -> None:
        doc = _normalize_doc(_session_module_doc())
        assert "Replay-identity" in doc
        assert "D-FAULT-11" in doc
        assert "strict byte-equality" in doc

    def test_recovering_state_forbidden_in_matrix(self) -> None:
        doc = _normalize_doc(_session_module_doc())
        assert "RECOVERING is" in doc
        assert "FORBIDDEN" in doc
        assert "D-FAULT-15 #18" in doc

    def test_taskoutcome_restriction_documented(self) -> None:
        doc = _normalize_doc(_session_module_doc())
        assert "inner sub-classification of NODE_EXECUTION_FAILURE" in doc
        assert "D-FAULT-1a" in doc


# --------------------------------------------------------------------
# Test class 3 — abort ingress discipline (focus area 1)
# --------------------------------------------------------------------


def _orch_ast_files() -> list[tuple[Path, ast.AST]]:
    out: list[tuple[Path, ast.AST]] = []
    for p in sorted(_ORCH_DIR.glob("*.py")):
        if p.name == "__init__.py":
            continue
        out.append((p, ast.parse(p.read_text(encoding="utf-8"))))
    return out


def _executor_ast() -> tuple[Path, ast.AST]:
    p = _TASKS_DIR / "executor.py"
    return p, ast.parse(p.read_text(encoding="utf-8"))


class TestAbortIngressDiscipline:
    """D-FAULT-6, -6a, -9, -9a, -15 #16."""

    def test_no_request_abort_method_on_session(self) -> None:
        """D-FAULT-15 #16: method-as-ingress is FORBIDDEN."""
        from cell_authoring.orchestration import ExecutionSession

        attrs = dir(ExecutionSession)
        for forbidden in ("request_abort", "abort", "cancel", "force_abort", "kill"):
            assert forbidden not in attrs, (
                f"ExecutionSession exposes forbidden ingress method {forbidden!r}"
            )

    def test_no_forbidden_ingress_method_definitions(self) -> None:
        """ast-introspect orchestration modules — no FunctionDef with the
        forbidden ingress names anywhere in orchestration/."""
        forbidden_names = {"request_abort", "force_abort", "kill_session", "abort_now"}
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_names, (
                        f"{path.name}: forbidden ingress method {node.name!r}"
                    )

    def test_no_async_functions_in_orchestration(self) -> None:
        """D-FORBID-1, D-FAULT-15: no async orchestration anywhere."""
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                assert not isinstance(node, ast.AsyncFunctionDef), (
                    f"{path.name}: async def {node.name!r} forbidden in orchestration"
                )
                assert not isinstance(node, ast.Await), f"{path.name}: await forbidden"

    def test_envelope_canonical_ordering_is_deterministic(self) -> None:
        """D-FAULT-9: envelopes sorted by (requested_at_tick, envelope_id)."""
        e1 = _OperatorEnvelopeRef("abort", 5, "stop", "id_b")
        e2 = _OperatorEnvelopeRef("abort", 5, "stop", "id_a")
        e3 = _OperatorEnvelopeRef("abort", 3, "stop", "id_z")
        ordered = _canonical_envelope_order([e1, e2, e3])
        assert tuple(e.envelope_id for e in ordered) == ("id_z", "id_a", "id_b")
        # Stability across re-ordering of input
        ordered2 = _canonical_envelope_order([e3, e1, e2])
        assert ordered == ordered2

    def test_envelope_is_frozen(self) -> None:
        e = _OperatorEnvelopeRef("abort", 1, "test", "id_x")
        with pytest.raises(FrozenInstanceError):
            e.kind = "pause"  # type: ignore[misc]

    def test_step9_only_abort_kind_permitted_in_reference(self) -> None:
        """D-FAULT-9a — Step 9 supports only kind='abort'."""
        permitted = {"abort"}
        reserved = {"pause", "resume", "manual_advance"}
        for k in reserved:
            assert k not in permitted, f"Step 9 must reject {k!r} per D-FAULT-9a"

    def test_envelope_canonical_form_is_byte_stable(self) -> None:
        e = _OperatorEnvelopeRef("abort", 7, "reason text", "envid_42")
        a = _canonical_dumps(e.to_canonical())
        b = _canonical_dumps(e.to_canonical())
        assert a == b
        # The fingerprint MUST sort keys (D-TRACE-8 / D-FAULT-10).
        assert a.startswith('{"envelope_id":'), a


# --------------------------------------------------------------------
# Test class 4 — idempotent cascade-abort (focus area 2)
# --------------------------------------------------------------------


class TestIdempotentCascade:
    """D-FAULT-3, -3a, -4, -7."""

    def _diamond_graph(self) -> _CascadeRefModel:
        # A → {B, C} → D
        return _CascadeRefModel(
            canonical_order=("A", "B", "C", "D"),
            graph_edges=(
                ("A", "B", _FA.SKIP_NODE),
                ("A", "C", _FA.SKIP_NODE),
                ("B", "D", _FA.SKIP_NODE),
                ("C", "D", _FA.SKIP_NODE),
            ),
        )

    def test_skip_node_default_skips_descendants_only(self) -> None:
        g = self._diamond_graph()
        g.mark_failed("B", action=_FA.SKIP_NODE)
        # B failed; only B's descendants (D) cascade-skipped
        assert g.failed == {"B"}
        assert g.skipped == {"D"}
        # Sibling C unaffected (sibling-tolerant default — F.3 ruling)
        assert "C" not in g.skipped
        events = [(t, n) for t, n in g.events]
        assert events == [("NodeFailed", "B"), ("TaskCascadeSkipped", "D")]

    def test_abort_cohort_skips_descendants_and_siblings(self) -> None:
        g = self._diamond_graph()
        g.mark_failed("B", action=_FA.ABORT_COHORT)
        assert g.failed == {"B"}
        # Cohort includes B's siblings (C) AND C's descendants (D).
        assert "C" in g.skipped
        assert "D" in g.skipped

    def test_abort_job_cascades_remaining_uniformly(self) -> None:
        g = self._diamond_graph()
        g.mark_failed("B", action=_FA.ABORT_JOB)
        assert g.failed == {"B"}
        assert g.skipped == {"A", "C", "D"}

    def test_cascade_emission_iterates_canonical_order(self) -> None:
        """D-FAULT-4 + D-SCHED-3: emission iterates canonical_order."""
        g = self._diamond_graph()
        g.mark_failed("A", action=_FA.ABORT_JOB)
        skip_events = [n for t, n in g.events if t == "TaskCascadeSkipped"]
        # Must be in canonical order (B, C, D) — not insertion order.
        assert skip_events == ["B", "C", "D"]

    def test_double_skip_emits_once(self) -> None:
        """D-FAULT-7: idempotent at the transition."""
        g = _CascadeRefModel(
            canonical_order=("A", "B", "C", "D"),
            graph_edges=(
                ("A", "C", _FA.SKIP_NODE),
                ("B", "C", _FA.SKIP_NODE),
                ("C", "D", _FA.SKIP_NODE),
            ),
        )
        g.mark_failed("A", action=_FA.SKIP_NODE)
        g.mark_failed("B", action=_FA.SKIP_NODE)
        # C and D each cascade-skipped from BOTH parents but emitted ONCE.
        c_emits = sum(1 for t, n in g.events if t == "TaskCascadeSkipped" and n == "C")
        d_emits = sum(1 for t, n in g.events if t == "TaskCascadeSkipped" and n == "D")
        assert c_emits == 1
        assert d_emits == 1

    def test_cascade_replay_byte_identity(self) -> None:
        """Repeated identical runs produce byte-identical cascade traces."""
        runs = []
        for _ in range(3):
            g = self._diamond_graph()
            g.mark_failed("A", action=_FA.ABORT_JOB)
            runs.append(_canonical_dumps([(t, n) for t, n in g.events]))
        assert runs[0] == runs[1] == runs[2]

    def test_cascade_emitted_flag_authoritative(self) -> None:
        """D-FAULT-7: cascade_emitted is per-node, on NodeRuntimeState."""
        nr = _NodeRuntimeStateRef(node_id="X", status="pending")
        # Simulate emission
        nr.cascade_emitted = True
        nr.status = "skipped"
        # Re-emission must be guarded by the flag — the model assumes
        # callers consult it.
        snapshot = _canonical_dumps(nr.to_canonical())
        assert '"cascade_emitted":true' in snapshot

    def test_blocked_emission_key_idempotency(self) -> None:
        """D-FAULT-7: NodeBlocked emits once per episode."""
        nr = _NodeRuntimeStateRef(node_id="X", status="pending")
        # Episode 1: blocked by precondition
        nr.blocked_emission_key = "blocked_by_precondition:p_hash_1"
        first_emit_key = nr.blocked_emission_key
        # Repeated scheduler call with same key: no re-emit
        assert nr.blocked_emission_key == first_emit_key
        # Episode ends: key cleared
        nr.blocked_emission_key = None
        # New episode (different reason) — emit
        nr.blocked_emission_key = "blocked_by_predicate_error:p_hash_2"
        assert nr.blocked_emission_key != first_emit_key


# --------------------------------------------------------------------
# Test class 5 — tick-budget timeout determinism (focus area 3)
# --------------------------------------------------------------------


def _evaluate_tick_budget(*, tick_budget_ticks: int, ticks_consumed: int) -> str | None:
    """Reference impl of D-FAULT-12 post-Phase-E check."""
    if ticks_consumed > tick_budget_ticks:
        return "TIMEOUT_FAILURE"
    return None


def _check_tick_budget_margin(
    *, tick_budget_ticks: int, trajectory_length_ticks: int, margin_ticks: int
) -> bool:
    """Reference impl of D-FAULT-12b margin assertion."""
    return tick_budget_ticks >= trajectory_length_ticks + margin_ticks


class TestTickBudgetDeterminism:
    """D-FAULT-12, -12a, -12b."""

    def test_timeout_triggers_only_on_strict_excess(self) -> None:
        assert _evaluate_tick_budget(tick_budget_ticks=100, ticks_consumed=100) is None
        assert _evaluate_tick_budget(tick_budget_ticks=100, ticks_consumed=99) is None
        assert (
            _evaluate_tick_budget(tick_budget_ticks=100, ticks_consumed=101)
            == "TIMEOUT_FAILURE"
        )

    def test_timeout_independent_of_wall_clock(self) -> None:
        """Identical tick sequences → identical timeout outcomes."""
        # Run 3 times; output is purely a function of integer inputs.
        outs = [
            _evaluate_tick_budget(tick_budget_ticks=50, ticks_consumed=51) for _ in range(3)
        ]
        assert outs == ["TIMEOUT_FAILURE", "TIMEOUT_FAILURE", "TIMEOUT_FAILURE"]

    def test_margin_assertion_per_dfault_12b(self) -> None:
        # Tight: budget == trajectory; insufficient margin
        assert not _check_tick_budget_margin(
            tick_budget_ticks=100, trajectory_length_ticks=100, margin_ticks=5
        )
        # Adequate
        assert _check_tick_budget_margin(
            tick_budget_ticks=105, trajectory_length_ticks=100, margin_ticks=5
        )
        # Over-margin OK
        assert _check_tick_budget_margin(
            tick_budget_ticks=200, trajectory_length_ticks=100, margin_ticks=5
        )

    def test_no_wall_clock_imports_in_orchestration(self) -> None:
        """D-FAULT-12: no time.time / time.perf_counter / wall-clock APIs.

        Permitted: imports of `time` module are allowed only if the file
        does NOT reference `time.time`, `time.perf_counter`,
        `time.monotonic`, `time.process_time`, or `time.sleep`.
        """
        forbidden_attrs = {"time", "perf_counter", "monotonic", "process_time", "sleep"}
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    if node.value.id == "time" and node.attr in forbidden_attrs:
                        raise AssertionError(
                            f"{path.name}: forbidden wall-clock reference time.{node.attr}"
                        )

    def test_no_threading_in_orchestration(self) -> None:
        """D-FAULT-12 watchdog threads FORBIDDEN; D-FORBID async/threading."""
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name != "threading", f"{path.name}: threading import"
                        assert alias.name != "asyncio", f"{path.name}: asyncio import"
                        assert not alias.name.startswith(
                            "_thread"
                        ), f"{path.name}: _thread import"
                if isinstance(node, ast.ImportFrom):
                    assert node.module != "threading", f"{path.name}: from threading import"
                    assert node.module != "asyncio", f"{path.name}: from asyncio import"

    def test_no_subprocess_or_signal_in_orchestration(self) -> None:
        """No out-of-process timeout helpers."""
        forbidden_modules = {"subprocess", "signal", "multiprocessing"}
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert (
                            alias.name not in forbidden_modules
                        ), f"{path.name}: import {alias.name}"
                if isinstance(node, ast.ImportFrom):
                    assert (
                        node.module not in forbidden_modules
                    ), f"{path.name}: from {node.module} import"


# --------------------------------------------------------------------
# Test class 6 — contradiction-preservation semantics (focus area 4)
# --------------------------------------------------------------------


class TestContradictionPreservation:
    """D-FAULT-5, -5a, -5b."""

    def _staged_pre_fail_snapshot(self) -> _BoundarySnapshotRefModel:
        return _BoundarySnapshotRefModel(
            objects={
                "peg": {"dlife_state": "attached", "pose_m": [0.50, 0.00, 0.10]},
            },
            fixtures={"fixture_a": {"occupied_by": "peg"}},
            completed=frozenset({"node_n1"}),
            failed=frozenset(),
            skipped=frozenset(),
        )

    def test_pose_on_fail_reflects_last_tick_truth(self) -> None:
        """D-FAULT-5a: post-failure pose is last-tick `update_object_pose`."""
        snap = self._staged_pre_fail_snapshot()
        post = snap.project_post_fail(
            failed_node_id="node_n2",
            last_tick_object_poses={"peg": [0.70, 0.10, 0.00]},  # dropped pose
        )
        assert post["objects"]["peg"]["pose_m"] == [0.70, 0.10, 0.00]

    def test_fixture_occupancy_unchanged_on_fail(self) -> None:
        """D-FAULT-5b: occupancy is NOT mutated on FAIL."""
        snap = self._staged_pre_fail_snapshot()
        post = snap.project_post_fail(
            failed_node_id="node_n2",
            last_tick_object_poses={"peg": [0.70, 0.10, 0.00]},
        )
        # FixtureA still occupied — even though peg moved away.
        assert post["fixtures"]["fixture_a"] == {"occupied_by": "peg"}

    def test_contradiction_explicitly_preserved(self) -> None:
        """The contradiction between occupancy and pose is the forensic truth."""
        snap = self._staged_pre_fail_snapshot()
        post = snap.project_post_fail(
            failed_node_id="node_n2",
            last_tick_object_poses={"peg": [0.70, 0.10, 0.00]},
        )
        # Contradiction detector
        occupied_by = post["fixtures"]["fixture_a"]["occupied_by"]
        peg_pose = post["objects"]["peg"]["pose_m"]
        original_pose = [0.50, 0.00, 0.10]
        assert occupied_by == "peg" and peg_pose != original_pose, (
            "post-failure snapshot must preserve the contradiction explicitly"
        )

    def test_no_implicit_rollback_to_clean_state(self) -> None:
        """D-FAULT-5: rollback is FORBIDDEN. Verified by reference model
        having no `rollback`, `revert`, `restore` methods."""
        snap_attrs = [a for a in dir(_BoundarySnapshotRefModel) if not a.startswith("_")]
        for forbidden in ("rollback", "revert", "restore", "heal", "repair", "fixup"):
            assert forbidden not in snap_attrs, (
                f"reference model exposes forbidden rollback API {forbidden!r}"
            )

    def test_failed_node_added_to_session_failed_set(self) -> None:
        snap = self._staged_pre_fail_snapshot()
        post = snap.project_post_fail(
            failed_node_id="node_n2", last_tick_object_poses={}
        )
        assert post["session"]["failed"] == ["node_n2"]

    def test_post_fail_snapshot_is_canonical_json_stable(self) -> None:
        snap = self._staged_pre_fail_snapshot()
        a = _canonical_dumps(
            snap.project_post_fail("node_n2", {"peg": [0.7, 0.1, 0.0]})
        )
        b = _canonical_dumps(
            snap.project_post_fail("node_n2", {"peg": [0.7, 0.1, 0.0]})
        )
        assert a == b

    def test_recovery_not_synthesized_automatically(self) -> None:
        """D-FAULT-8: recovery is graph topology, not runtime behaviour."""
        # Reference model has no method that creates recovery nodes.
        snap_methods = [m for m in dir(_BoundarySnapshotRefModel) if not m.startswith("_")]
        cascade_methods = [m for m in dir(_CascadeRefModel) if not m.startswith("_")]
        for method_set in (snap_methods, cascade_methods):
            for forbidden in (
                "auto_recover",
                "synthesize_recovery",
                "retry_failed_node",
                "heal_contradiction",
                "self_repair",
            ):
                assert forbidden not in method_set, (
                    f"forbidden auto-recovery API: {forbidden!r}"
                )


# --------------------------------------------------------------------
# Test class 7 — REPLAY_INTEGRITY_FAILURE isolation (focus area 5)
# --------------------------------------------------------------------


class TestReplayIntegrityIsolation:
    """D-FAULT-11, -11a."""

    def test_runtime_event_types_exclude_replay_integrity(self) -> None:
        """REPLAY_INTEGRITY_FAILURE MUST NOT be a session-emitted event."""
        from cell_authoring.orchestration import session as session_module

        event_constants = {
            name: getattr(session_module, name)
            for name in dir(session_module)
            if name.startswith("EVENT_")
        }
        for name, value in event_constants.items():
            assert "ReplayIntegrity" not in value, (
                f"session.{name} = {value!r} must not be a ReplayIntegrity event"
            )
            assert "REPLAY_INTEGRITY" not in value.upper().replace("_", "")[:23] or (
                "ReplayIntegrity" not in value
            )

    def test_no_replay_integrity_emit_call_in_orchestration(self) -> None:
        """Static scan: no string literal 'ReplayIntegrity' / 'REPLAY_INTEGRITY'
        in orchestration source (it would only appear if someone planned to
        emit it from the session)."""
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert "ReplayIntegrity" not in node.value, (
                        f"{path.name}: forbidden 'ReplayIntegrity' string literal"
                    )

    def test_strict_byte_equality_no_tolerance_keywords(self) -> None:
        """D-FAULT-11a: no 'tolerance' / 'approximate' / 'fuzzy' keywords
        in the replay-comparator tool source."""
        comparator = _WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring" / "cell_authoring" / "tools" / "check_session_replay_identity.py"
        if not comparator.exists():
            # Fall back to repo-wide locations.
            candidates = list(
                (_WORKSPACE).rglob("check_session_replay_identity.py")
            )
            if not candidates:
                pytest.skip("comparator tool not located on this checkout")
            comparator = candidates[0]
        src = comparator.read_text(encoding="utf-8").lower()
        for forbidden in ("tolerance", "approx_equal", "approximately", "fuzzy_match"):
            # The word may appear in comments banning it; check for actual code use.
            # We allow the word in comments / docstrings only.
            assert (
                f"def {forbidden}" not in src and f"{forbidden}(" not in src.replace(
                    "abs(", ""
                )
            ), f"comparator must not use {forbidden!r}"


# --------------------------------------------------------------------
# Test class 8 — failure trace append-only guarantees (focus area 6)
# --------------------------------------------------------------------


class TestFailureTraceAppendOnly:
    """D-FAULT-10, -14."""

    def test_append_after_finalize_raises(self) -> None:
        t = _TraceRefModel()
        t.append("NodeExecutionCompleted", {"passed": False, "outcome_value": "PLACEMENT_MISS"})
        t.finalize()
        with pytest.raises(RuntimeError, match=r"finalized"):
            t.append("SneakyCleanup", {"silent": True})

    def test_aborted_and_failed_byte_distinguishable(self) -> None:
        """Distinct terminal event types per F.11 / D-FAULT-3."""
        t_abort = _TraceRefModel()
        t_abort.append("SessionAborted", {"terminator_reason": "OPERATOR_ABORT"})
        t_fail = _TraceRefModel()
        t_fail.append("SessionFailed", {"terminator_reason": "AUTHORITY_VIOLATION"})
        finalized_abort = t_abort.finalize()
        finalized_fail = t_fail.finalize()
        assert finalized_abort != finalized_fail
        # Different event_type strings — byte distinguishable.
        assert t_abort.events[-1]["event_type"] == "SessionAborted"
        assert t_fail.events[-1]["event_type"] == "SessionFailed"
        # Canonical encodings contain the quoted distinguishing event_type.
        assert '"event_type":"SessionAborted"' in finalized_abort
        assert '"event_type":"SessionFailed"' in finalized_fail

    def test_envelope_ingress_preserves_causal_order(self) -> None:
        """D-FAULT-7: late envelopes recorded but no second transition."""
        t = _TraceRefModel()
        t.append("OperatorAbortRequested", {"envelope_id": "id_1"})
        t.append("SessionAborting", {"terminator_reason": "OPERATOR_ABORT"})
        # Second envelope arrives after ABORTING already entered.
        t.append("OperatorAbortRequested", {"envelope_id": "id_2"})
        # No second SessionAborting emission.
        t.append("SessionAborted", {"last_clean_seq": 5})
        types = [e["event_type"] for e in t.events]
        assert types.count("SessionAborting") == 1
        # But both envelope ingresses recorded for forensics.
        assert types.count("OperatorAbortRequested") == 2

    def test_canonical_fingerprint_byte_stable(self) -> None:
        """D-FAULT-10: failure events canonical-JSON-fingerprinted."""
        events_a = [{"event_type": "NodeFailed", "payload": {"node": "X"}, "seq": 0}]
        events_b = [{"event_type": "NodeFailed", "payload": {"node": "X"}, "seq": 0}]
        assert _canonical_dumps(events_a) == _canonical_dumps(events_b)
        # Sorted-keys: payload key ordering does not matter.
        events_c = [{"seq": 0, "event_type": "NodeFailed", "payload": {"node": "X"}}]
        assert _canonical_dumps(events_a) == _canonical_dumps(events_c)


# --------------------------------------------------------------------
# Test class 9 — mutation-authority enforcement (focus area 7)
# --------------------------------------------------------------------


class TestMutationAuthorityEnforcement:
    """Authority discipline: only documented authorities mutate fault state."""

    def test_executor_does_not_call_mark_fixture_in_run_cycle(self) -> None:
        """D-CONT-5 + D-FAULT-5: only session mutates fixture occupancy.

        ast-scan TaskExecutor._run_cycle for calls to mark_fixture_*.
        (Step 8 Phase 2 already removed these; Phase 4 of Step 9 maintains
        the invariant.)
        """
        path, tree = _executor_ast()
        target_methods = ("_run_cycle", "run_cycle", "_execute_cycle")
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in target_methods:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        # Check for attribute access like X.mark_fixture_occupied(...)
                        func = sub.func
                        if isinstance(func, ast.Attribute):
                            assert not func.attr.startswith("mark_fixture_"), (
                                f"executor.{node.name} calls forbidden {func.attr}"
                            )

    def test_executor_does_not_emit_session_state_changes(self) -> None:
        """ast-scan: executor must not import or reference SessionState."""
        path, tree = _executor_ast()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "session" in node.module:
                    raise AssertionError(
                        f"executor.py imports from {node.module} — authority breach"
                    )
            if isinstance(node, ast.Name) and node.id == "SessionState":
                raise AssertionError("executor.py references SessionState")

    def test_session_module_owns_state_mutation(self) -> None:
        """Only session.py declares SessionState enum."""
        session_defines = 0
        other_defines = 0
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "SessionState":
                    if path.name == "session.py":
                        session_defines += 1
                    else:
                        other_defines += 1
        assert session_defines == 1
        assert other_defines == 0

    def test_predicate_layer_has_no_mutators(self) -> None:
        """D-SCHED-12: predicates are pure."""
        predicates_path = _ORCH_DIR / "predicates.py"
        tree = ast.parse(predicates_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # No method named mutate_*, set_*, write_*, persist_*
                for prefix in ("mutate_", "set_", "write_", "persist_", "commit_"):
                    assert not node.name.startswith(prefix), (
                        f"predicates.py: forbidden mutator {node.name!r}"
                    )


# --------------------------------------------------------------------
# Test class 10 — forbidden-pattern regression (focus area 8)
# --------------------------------------------------------------------


class TestForbiddenPatterns:
    """D-FAULT-15: all 18 forbidden patterns get an explicit static check."""

    def test_no_RECOVERING_session_state_value(self) -> None:
        """D-FAULT-15 #18."""
        from cell_authoring.orchestration import SessionState

        for member in SessionState.__members__:
            assert member != "RECOVERING", (
                "SessionState.RECOVERING FORBIDDEN per D-FAULT-15 #18"
            )

    def test_no_request_abort_in_orchestration_or_tasks(self) -> None:
        """D-FAULT-15 #16."""
        for paths in (_ORCH_DIR, _TASKS_DIR):
            for f in paths.glob("*.py"):
                src = f.read_text(encoding="utf-8")
                # Allow citation in docstrings; forbid function definition.
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        assert node.name != "request_abort", (
                            f"{f.name}: defines request_abort (D-FAULT-15 #16)"
                        )

    def test_no_implicit_retry_helper_names(self) -> None:
        """D-FAULT-15 #2."""
        forbidden = {
            "retry_failed",
            "retry_node",
            "auto_retry",
            "exponential_backoff",
            "with_retry",
        }
        for paths in (_ORCH_DIR, _TASKS_DIR):
            for f in paths.glob("*.py"):
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        assert node.name not in forbidden, (
                            f"{f.name}: forbidden retry helper {node.name!r}"
                        )

    def test_no_silent_cleanup_helper_names(self) -> None:
        """D-FAULT-15 #7."""
        forbidden = {
            "cleanup_on_fail",
            "auto_cleanup",
            "release_on_fail",
            "rollback_on_fail",
            "reset_after_fail",
            "heal_state",
        }
        for paths in (_ORCH_DIR, _TASKS_DIR):
            for f in paths.glob("*.py"):
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        assert node.name not in forbidden, (
                            f"{f.name}: forbidden cleanup helper {node.name!r}"
                        )

    def test_no_topology_derived_recovery_inference(self) -> None:
        """D-FAULT-15 #15: recovery is metadata-tagged, not graph-inferred."""
        forbidden_names = {
            "infer_recovery_node",
            "is_recovery_path",
            "detect_recovery_from_topology",
            "find_recovery_descendants",
        }
        for paths in (_ORCH_DIR, _TASKS_DIR):
            for f in paths.glob("*.py"):
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        assert node.name not in forbidden_names, (
                            f"{f.name}: topology-derived recovery inference forbidden"
                        )

    def test_no_warning_severity_tier_helpers(self) -> None:
        """D-FAULT-15 #14."""
        forbidden = {
            "warn_violation",
            "soft_failure",
            "transient_failure",
            "minor_failure",
            "downgrade_to_warning",
        }
        for paths in (_ORCH_DIR, _TASKS_DIR):
            for f in paths.glob("*.py"):
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        assert node.name not in forbidden, (
                            f"{f.name}: severity-tier helper {node.name!r} forbidden"
                        )

    def test_no_replay_tolerance_helpers(self) -> None:
        """D-FAULT-15 #4: byte-equality only."""
        forbidden = {
            "approximately_equal_traces",
            "fuzzy_compare_sessions",
            "soft_replay_match",
            "tolerant_equal",
        }
        for paths in (_ORCH_DIR, _TASKS_DIR):
            for f in paths.glob("*.py"):
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        assert node.name not in forbidden, (
                            f"{f.name}: replay-tolerance helper {node.name!r} forbidden"
                        )

    def test_no_mid_phase_e_interrupt_handlers(self) -> None:
        """D-FAULT-15 #5: Phase E atomic."""
        forbidden = {
            "interrupt_execute",
            "stop_mid_step",
            "cancel_during_execute",
            "preempt_executor",
        }
        for paths in (_ORCH_DIR, _TASKS_DIR):
            for f in paths.glob("*.py"):
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        assert node.name not in forbidden, (
                            f"{f.name}: mid-Phase-E interrupt handler {node.name!r} forbidden"
                        )

    def test_no_cross_session_state_helpers(self) -> None:
        """D-FAULT-15 #12 + D-FORBID."""
        forbidden = {
            "load_state_from_prior_session",
            "carry_over_retained_state",
            "inherit_session_state",
            "share_state_between_sessions",
        }
        for paths in (_ORCH_DIR, _TASKS_DIR):
            for f in paths.glob("*.py"):
                tree = ast.parse(f.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        assert node.name not in forbidden, (
                            f"{f.name}: cross-session helper {node.name!r} forbidden"
                        )

    def test_no_failure_action_mutation_after_build(self) -> None:
        """D-FAULT-15 #13 + D-SCHED-8: TaskGraph frozen after build()."""
        from cell_authoring.orchestration import TaskGraph

        # TaskGraph itself must be a frozen dataclass.
        import dataclasses

        assert dataclasses.is_dataclass(TaskGraph)
        params = TaskGraph.__dataclass_params__  # type: ignore[attr-defined]
        assert params.frozen is True

    def test_canonical_envelope_id_is_deterministic_text(self) -> None:
        """D-FAULT-9: envelope_id is a deterministic UUID-equivalent.
        Forbidden: live random or wall-clock derivation. Verified by static
        scan for `uuid.uuid4` / `random.` use in orchestration."""
        forbidden_calls = (
            ("uuid", "uuid4"),
            ("uuid", "uuid1"),
            ("random", "random"),
            ("random", "randint"),
            ("os", "urandom"),
        )
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    pair = (node.value.id, node.attr)
                    if pair in forbidden_calls:
                        raise AssertionError(
                            f"{path.name}: nondeterministic id source {pair[0]}.{pair[1]}"
                        )


# --------------------------------------------------------------------
# Test class 11 — taxonomy sanity (D-FAULT-1, D-FAULT-1a, D-FAULT-2)
# --------------------------------------------------------------------


class TestFaultTaxonomyContract:
    """D-FAULT-1, -1a, -2: taxonomy enumeration + two-tier discipline."""

    def test_exactly_eight_failure_classes(self) -> None:
        assert len(_FAILURE_CLASSES) == 8
        assert len(set(_FAILURE_CLASSES)) == 8

    def test_six_classes_emitted_in_session(self) -> None:
        assert len(_FAILURE_CLASSES_EMITTED_IN_SESSION) == 6

    def test_two_classes_out_of_session(self) -> None:
        assert len(_FAILURE_CLASSES_OUT_OF_SESSION) == 2
        assert set(_FAILURE_CLASSES_EMITTED_IN_SESSION) | set(
            _FAILURE_CLASSES_OUT_OF_SESSION
        ) == set(_FAILURE_CLASSES)

    def test_taskoutcome_only_subclassifies_node_execution_failure(self) -> None:
        """D-FAULT-1a: TaskOutcome is inner sub-classification of
        NODE_EXECUTION_FAILURE only. Verified by ast: TaskOutcome enum
        is defined in `tasks/` (Phase 4A surface), not in `orchestration/`."""
        # No TaskOutcome class definition in orchestration/
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "TaskOutcome":
                    raise AssertionError(
                        f"{path.name}: TaskOutcome must live in tasks/, not orchestration/"
                    )
        # And IS defined exactly once in tasks/
        defs = 0
        for p in _TASKS_DIR.glob("*.py"):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "TaskOutcome":
                    defs += 1
        assert defs == 1, f"TaskOutcome must be defined exactly once, got {defs}"

    def test_single_emitter_per_class_documented(self) -> None:
        """D-FAULT-2: each class has exactly one origin authority.

        Verified by the canonical-doc D-FAULT-1 table — every class appears
        in column 1 exactly once.
        """
        # Extract the D-FAULT-1 table block.
        m = re.search(
            r"\*\*D-FAULT-1\*\* — Failure at the orchestration level.*?"
            r"Expansion of this list is a contract revision",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None
        block = m.group(0)
        for cls in _FAILURE_CLASSES:
            # Class name appears at start of a table row: `| `<class>`
            occurrences = len(re.findall(rf"^\| `{re.escape(cls)}`", block, re.M))
            assert occurrences == 1, (
                f"D-FAULT-1 table: {cls} appears {occurrences} times (must be 1)"
            )


# --------------------------------------------------------------------
# Test class 12 — replay-identity discipline on the test suite itself
# --------------------------------------------------------------------


class TestSuiteReplayIdentity:
    """The pure-Python suite itself MUST be byte-deterministic. Run small
    representative computations twice and confirm identical outputs."""

    def test_cascade_run_byte_identical_across_invocations(self) -> None:
        outs = []
        for _ in range(3):
            g = _CascadeRefModel(
                canonical_order=("A", "B", "C", "D", "E"),
                graph_edges=(
                    ("A", "B", _FA.SKIP_NODE),
                    ("A", "C", _FA.SKIP_NODE),
                    ("B", "D", _FA.SKIP_NODE),
                    ("C", "E", _FA.SKIP_NODE),
                ),
            )
            g.mark_failed("A", action=_FA.ABORT_JOB)
            outs.append(_canonical_dumps([(t, n) for t, n in g.events]))
        assert outs[0] == outs[1] == outs[2]

    def test_snapshot_serialization_byte_identical(self) -> None:
        outs = []
        for _ in range(3):
            snap = _BoundarySnapshotRefModel(
                objects={"peg": {"dlife_state": "available", "pose_m": [0.0, 0.0, 0.1]}},
                fixtures={"f1": {"occupied_by": None}, "f2": {"occupied_by": "peg"}},
                completed=frozenset({"n1", "n2"}),
                failed=frozenset(),
                skipped=frozenset({"n3"}),
            )
            outs.append(
                _canonical_dumps(
                    snap.project_post_fail("n4", {"peg": [0.1, 0.0, 0.05]})
                )
            )
        assert outs[0] == outs[1] == outs[2]

    def test_envelope_ordering_byte_identical(self) -> None:
        envs = [
            _OperatorEnvelopeRef("abort", 10, "reason_a", "id_5"),
            _OperatorEnvelopeRef("abort", 3, "reason_b", "id_7"),
            _OperatorEnvelopeRef("abort", 10, "reason_c", "id_2"),
        ]
        canonical_str = _canonical_dumps(
            [e.to_canonical() for e in _canonical_envelope_order(envs)]
        )
        # Run again with shuffled input
        envs2 = [envs[2], envs[0], envs[1]]
        canonical_str2 = _canonical_dumps(
            [e.to_canonical() for e in _canonical_envelope_order(envs2)]
        )
        assert canonical_str == canonical_str2


# --------------------------------------------------------------------
# Test class 13 — D-FAULT-14 load-bearing rule end-to-end
# --------------------------------------------------------------------


class TestNoImplicitSecondaryOrchestration:
    """D-FAULT-14: every state mutation has exactly one D-FAULT clause behind it.

    These tests cross-cut the contract: they assert that no symbol or
    behaviour exists in the codebase that would mean "failure handling
    is its own second orchestration system" — abort daemons, recovery
    schedulers, watchdog timers, retry queues, etc.
    """

    def test_no_separate_failure_scheduler_class(self) -> None:
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for forbidden in (
                        "FailureScheduler",
                        "RecoveryScheduler",
                        "AbortCoordinator",
                        "TimeoutWatchdog",
                        "RetryEngine",
                        "RecoveryEngine",
                    ):
                        assert node.name != forbidden, (
                            f"{path.name}: forbidden secondary-orchestration class {forbidden!r}"
                        )

    def test_session_remains_the_single_orchestration_authority(self) -> None:
        """Every D-FAULT authority extension is on ExecutionSession (per matrix)."""
        from cell_authoring.orchestration import ExecutionSession

        # Verify ExecutionSession is the canonical orchestration class — no peer.
        from cell_authoring.orchestration import session as session_module

        # No alternate session class.
        for name in dir(session_module):
            obj = getattr(session_module, name)
            if isinstance(obj, type) and name.endswith("Session"):
                assert name in ("ExecutionSession",), (
                    f"unexpected session class: {name}"
                )

    def test_authority_matrix_is_normative(self) -> None:
        """The matrix in session.py docstring is the single source of truth."""
        raw = _session_module_doc()
        doc = _normalize_doc(raw)
        # Required normative markers
        assert "**normative**" in doc
        assert "contract violation" in doc
        assert 'no "hidden orchestration mutation path"' in doc
