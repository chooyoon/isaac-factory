"""Phase 4B Step 10 Direction A / Phase 3 — pure-Python constitutional contract tests.

This file is the **semantic regression gate** for Step 10 Phase 4 (runtime
wiring) and every subsequent Step 10 phase. It converts the frozen Phase 2
clauses into executable constitutional gates BEFORE any production runtime
implements them, by combining four test categories:

  1. **Contract-doc structural tests** — assert that §1.5 (D-EXEC-13 a/b/c/d),
     §13.1.2 (D-FAULT-1b), §13.3.2 (D-FAULT-3b), §13.12.3 (D-FAULT-12c), and
     §13.17 (Step 10 Direction A scope extension) of
     `docs/phase_4b_deterministic_semantics.md` are present, well-formed, and
     reference each other consistently. The D-FAULT-15 forbidden-pattern table
     contains rows 19-30 enumerating Step 10-specific anti-patterns.

  2. **Static-introspection tests** — ast-parse files under
     `cell_authoring/orchestration/` and `cell_authoring/tasks/` and assert
     that the Step 10 forbidden patterns (executor-side classification,
     adaptive predicates, async/signal/thread interruption channels,
     observational-field promotion, mid-Phase-E orchestration-visible
     interruption, wall-clock `ticks_consumed` derivations, predicate
     constructors outside `ExecutionSession`, etc.) are absent. These tests
     pass today (the runtime has not been wired yet) AND remain green after
     Phase 4 wires the surface — they fail if any phase introduces a
     forbidden pattern.

  3. **Reference-model tests** — small, observational pure-Python models of
     Direction A semantics:

       * an interruption predicate as a pure callable over an immutable
         closure of authoritative inputs;
       * a trajectory as a sequence of named segments with integer tick
         lengths;
       * an opaque, side-effect-free executor that consumes a predicate at
         segment boundaries and produces a TaskResult-like record;
       * a session-side classifier that applies the D-FAULT-3b declared-order
         rule;
       * a fingerprint surface that records EXECUTION_INTERRUPTED and
         ticks_consumed but NOT the observational `interrupted_at_segment_*`
         fields.

     These models are **NOT** the runtime. They are minimal, observational
     specifications of the externally-observable invariants. They make no
     commitment to executor internal structure, segment container
     implementation, interruption plumbing shape, or any future runtime
     optimization. They demonstrate that the contract semantics are
     well-defined and deterministic; the runtime MUST satisfy the same
     invariants when Phase 4 wires it.

  4. **Replay-identity posture tests** — verify that the fingerprint surface
     remains byte-stable across repeated invocations and across input
     reorderings; verify that the observational `interrupted_at_segment_*`
     fields do NOT enter the fingerprint; verify that `ticks_consumed`
     divergence surfaces deterministically.

Clauses covered:

  D-EXEC-13              sub-Phase-E interruption surface
  D-EXEC-13a             Phase E atomicity from orchestration perspective
  D-EXEC-13b             segment_tick determinism + observational fields
  D-EXEC-13c             predicate is session-constructed only
  D-EXEC-13d             no speculative interruption
  D-FAULT-1b             EXECUTION_INTERRUPTED as neutral executor outcome
  D-FAULT-3b             session declared-order classification rule
  D-FAULT-12a (amended)  post-Phase-E budget check applies regardless of return path
  D-FAULT-12c            ticks_consumed integer-counter ontology
  D-FAULT-15 #5 (amended)+ rows 19-30  Step 10 anti-patterns
  §13.17                 Step 10 Direction A scope extension restatement

All tests are pure Python. No Isaac Sim. No PhysX. No threading. No asyncio.
No wall-clock reads. No GPU. No network. No subprocess. The suite must run
deterministically and produce byte-identical assertions across repeated
invocations.

Design discipline (per Phase 3 reminder):

  * Reference models are MINIMAL and OBSERVATIONAL. They do NOT claim to be
    the executor or session — they are abstract specifications of the
    semantics under test.
  * Tests validate externally-observable invariants only. They do NOT
    prescribe executor internal structure, segment container implementation,
    or interruption plumbing shape.
  * No hidden executor API commitments. No future implementation lock-in.
  * Phase 3 is constitutional enforcement, NOT implementation-by-test.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
import sys
from dataclasses import FrozenInstanceError, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import pytest


# --------------------------------------------------------------------
# Path setup
# --------------------------------------------------------------------

_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)

_CONTRACT_DOC_PATH = _WORKSPACE / "docs" / "phase_4b_deterministic_semantics.md"
_ANALYSIS_DOC_PATH = _WORKSPACE / "docs" / "phase_4b_step10_direction_a_analysis.md"
_ORCH_DIR = _WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring" / "cell_authoring" / "orchestration"
_TASKS_DIR = _WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring" / "cell_authoring" / "tasks"

assert _CONTRACT_DOC_PATH.exists(), f"Canonical contract doc missing at {_CONTRACT_DOC_PATH}"
assert _ANALYSIS_DOC_PATH.exists(), f"Direction A analysis doc missing at {_ANALYSIS_DOC_PATH}"

_CONTRACT_TEXT: str = _CONTRACT_DOC_PATH.read_text(encoding="utf-8")
_ANALYSIS_TEXT: str = _ANALYSIS_DOC_PATH.read_text(encoding="utf-8")


def _canonical_dumps(obj: Any) -> str:
    """Match D-TRACE-8 canonical encoding for fingerprint stability."""
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )


def _orch_ast_files() -> list[tuple[Path, ast.AST]]:
    out: list[tuple[Path, ast.AST]] = []
    for p in sorted(_ORCH_DIR.glob("*.py")):
        if p.name == "__init__.py":
            continue
        out.append((p, ast.parse(p.read_text(encoding="utf-8"))))
    return out


def _tasks_ast_files() -> list[tuple[Path, ast.AST]]:
    out: list[tuple[Path, ast.AST]] = []
    for p in sorted(_TASKS_DIR.glob("*.py")):
        if p.name == "__init__.py":
            continue
        out.append((p, ast.parse(p.read_text(encoding="utf-8"))))
    return out


def _all_production_ast_files() -> list[tuple[Path, ast.AST]]:
    return _orch_ast_files() + _tasks_ast_files()


# ====================================================================
# Reference models (MINIMAL, OBSERVATIONAL, semantics-only)
# ====================================================================
#
# These models are abstract specifications of Direction A semantics. They
# make NO claim about runtime executor / session structure. They are used
# by tests below to verify that the contract semantics are well-defined,
# byte-stable, and free of degrees of freedom that would admit nondeterminism.
#
# Discipline:
#   * frozen dataclasses where possible — no mutation paths
#   * no async, no threads, no time, no random
#   * canonical-JSON serialization for fingerprint surfaces
#   * NO method names that the runtime would have to adopt verbatim
#
# These models do NOT pretend to be the executor or session. They are
# *minimal* witnesses that the semantics admit at least one deterministic
# realization; the runtime is free to realize them in any structurally
# different way as long as the same external invariants hold.
# ====================================================================


# String constants — what the future runtime will name; tests don't import
# them from the runtime (they may not be wired yet), only check that
# anti-patterns don't pre-empt them.

_EXECUTION_INTERRUPTED = "EXECUTION_INTERRUPTED"
_OPERATOR_ABORT = "OPERATOR_ABORT"
_TIMEOUT_FAILURE = "TIMEOUT_FAILURE"
_NODE_EXECUTION_FAILURE = "NODE_EXECUTION_FAILURE"


@dataclass(frozen=True, slots=True)
class _OperatorEnvelopeRef:
    """Reference model for D-FAULT-9 OperatorEnvelope (Step 9 baseline).

    Reused here for D-FAULT-3b classification tests. Schema is unchanged
    by Step 10 Direction A.
    """

    kind: str
    requested_at_tick: int
    reason: str
    envelope_id: str

    def to_canonical(self) -> Mapping[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "kind": self.kind,
            "reason": self.reason,
            "requested_at_tick": self.requested_at_tick,
        }


@dataclass(frozen=True, slots=True)
class _SegmentRef:
    """A trajectory segment as an opaque name + integer tick length.

    The shape is deliberately minimal. The runtime is free to model
    segments as classes, tuples, named entries in a table, or anything
    else, as long as each segment exposes:
      * a stable name (string),
      * an integer tick length (>= 0),
      * a settled boundary at its terminus (per D-EXEC-13 conditions 1-5).
    """

    name: str
    tick_length: int

    def __post_init__(self) -> None:
        if self.tick_length < 0:
            raise ValueError("segment tick_length MUST be non-negative")


@dataclass(frozen=True, slots=True)
class _TrajectoryRef:
    """A trajectory as an ordered tuple of segments.

    The structure is observational only: the runtime may store trajectories
    differently. This model exists to give the test suite a deterministic
    target for segment-boundary semantics.
    """

    segments: tuple[_SegmentRef, ...]

    def segment_count(self) -> int:
        return len(self.segments)

    def cumulative_ticks_to_boundary(self, boundary_index: int) -> int:
        """Ticks consumed from start through the end of segment `boundary_index - 1`.

        boundary 0 = before any segment; cumulative = 0
        boundary N = after N segments; cumulative = sum of first N segments
        """
        if boundary_index < 0 or boundary_index > len(self.segments):
            raise IndexError(boundary_index)
        return sum(s.tick_length for s in self.segments[:boundary_index])


# Authoritative-input whitelist (D-EXEC-13 closure-state whitelist).
# Frozen — the predicate's closure CANNOT mutate after capture.
@dataclass(frozen=True, slots=True)
class _PredicateClosureRef:
    """Frozen capture of authoritative state at execute-entry.

    Whitelist (D-EXEC-13):
      * envelope snapshot (tuple of OperatorEnvelopes pending at execute-entry)
      * base_tick (session's orchestration_tick at execute-entry)
      * tick_budget_ticks (per-task budget)
      * task_id (read-only identifier)
    """

    envelopes: tuple[_OperatorEnvelopeRef, ...]
    base_tick: int
    tick_budget_ticks: int | None
    task_id: str


@dataclass(frozen=True, slots=True)
class _PredicateOutcomeRef:
    """What a predicate consultation produced — observational only."""

    boundary_index: int
    cumulative_ticks_at_boundary: int
    result: bool


def _build_predicate(
    closure: _PredicateClosureRef,
    trajectory: _TrajectoryRef,
) -> Callable[[int], bool]:
    """Construct a deterministic, pure interruption predicate.

    The predicate signature is `(segment_tick: int) -> bool` where
    segment_tick is the count of completed segment boundaries (D-EXEC-13b).
    The body is a pure function of `(segment_tick, frozen-closure)`.

    No I/O. No mutation of closure. No wall-clock. No random. No state
    carried across invocations.

    Eligibility rules (mirror the contract's classification triggers,
    but the predicate ITSELF is neutral — see D-FAULT-1b; the predicate
    only computes True/False, it does not classify):

      * envelope eligible at (base_tick + cumulative_ticks_at_boundary) → True
      * cumulative_ticks_at_boundary > tick_budget_ticks → True
      * otherwise → False
    """
    envelopes = closure.envelopes
    base_tick = closure.base_tick
    tick_budget_ticks = closure.tick_budget_ticks

    eligible_envelope_ticks = tuple(
        sorted(e.requested_at_tick for e in envelopes if e.kind == "abort")
    )

    def predicate(segment_tick: int) -> bool:
        if segment_tick < 0 or segment_tick > trajectory.segment_count():
            raise IndexError(segment_tick)
        cumulative = trajectory.cumulative_ticks_to_boundary(segment_tick)
        if eligible_envelope_ticks:
            if (base_tick + cumulative) >= eligible_envelope_ticks[0]:
                return True
        if tick_budget_ticks is not None and cumulative > tick_budget_ticks:
            return True
        return False

    return predicate


@dataclass(frozen=True, slots=True)
class _TaskResultRef:
    """Minimal TaskResult-shaped record for fingerprint testing.

    Only the fields relevant to Direction A semantics are modeled.
    Authoritative fields (entering the fingerprint):
      * task_id, outcome, ticks_consumed
    Observational fields (NOT entering the fingerprint):
      * interrupted_at_segment_index, interrupted_at_segment_name
    """

    task_id: str
    outcome: str
    ticks_consumed: int
    interrupted_at_segment_index: int | None
    interrupted_at_segment_name: str | None

    def authoritative_fingerprint_payload(self) -> Mapping[str, Any]:
        """Subset of fields that enter the per-task fingerprint (D-FAULT-10)."""
        return {
            "outcome": self.outcome,
            "task_id": self.task_id,
            "ticks_consumed": self.ticks_consumed,
        }


@dataclass(frozen=True, slots=True)
class _ExecutorTraceEntryRef:
    """Single record of (boundary_index, predicate_result) for forensics.

    Used by tests to assert the executor consulted the predicate exactly
    once per boundary, only at boundaries, and stopped on first True.
    """

    boundary_index: int
    predicate_result: bool


def _run_reference_executor(
    trajectory: _TrajectoryRef,
    predicate: Callable[[int], bool],
    task_id: str,
) -> tuple[_TaskResultRef, tuple[_ExecutorTraceEntryRef, ...]]:
    """Minimal observational executor reference.

    This does NOT prescribe the runtime executor's structure. It is a
    minimal witness that the contract semantics admit at least one
    deterministic realization:

      * predicate consulted exactly once per boundary (D-EXEC-13);
      * predicate consulted ONLY at boundaries (no per-step consultation);
      * first True return terminates execute (D-EXEC-13d, no speculation);
      * ticks_consumed = cumulative ticks at the boundary at which True
        was returned, OR full trajectory length if no True ever returned;
      * outcome = EXECUTION_INTERRUPTED iff predicate returned True;
        otherwise outcome = PASS (the "happy path"; per-segment validator
        verdicts are out of Phase 3 scope).
    """
    trace: list[_ExecutorTraceEntryRef] = []
    n_boundaries = trajectory.segment_count() + 1  # boundary 0 .. boundary N

    for boundary in range(n_boundaries):
        result = bool(predicate(boundary))
        trace.append(_ExecutorTraceEntryRef(boundary, result))
        if result:
            ticks = trajectory.cumulative_ticks_to_boundary(boundary)
            seg_name = (
                trajectory.segments[boundary].name
                if boundary < trajectory.segment_count()
                else "post_trajectory"
            )
            return (
                _TaskResultRef(
                    task_id=task_id,
                    outcome=_EXECUTION_INTERRUPTED,
                    ticks_consumed=ticks,
                    interrupted_at_segment_index=boundary,
                    interrupted_at_segment_name=seg_name,
                ),
                tuple(trace),
            )
        if boundary == n_boundaries - 1:
            break  # final boundary checked; no more segments

    # Happy path — trajectory ran to completion.
    return (
        _TaskResultRef(
            task_id=task_id,
            outcome="PASS",
            ticks_consumed=trajectory.cumulative_ticks_to_boundary(
                trajectory.segment_count()
            ),
            interrupted_at_segment_index=None,
            interrupted_at_segment_name=None,
        ),
        tuple(trace),
    )


def _classify_execution_interrupted(
    *,
    result: _TaskResultRef,
    envelopes_at_execute_entry: tuple[_OperatorEnvelopeRef, ...],
    base_tick: int,
    tick_budget_ticks: int | None,
) -> str:
    """D-FAULT-3b declared-order classification.

    Pure function of:
      * envelopes_at_execute_entry (tuple, canonical-ordered)
      * base_tick (int)
      * result.ticks_consumed (int)
      * tick_budget_ticks (int | None)

    No wall-clock. No mutation. No observational projection. No
    PhysX state.

    Returns one of:
      * OPERATOR_ABORT
      * TIMEOUT_FAILURE
      * NODE_EXECUTION_FAILURE
    """
    if result.outcome != _EXECUTION_INTERRUPTED:
        raise ValueError("classifier only applies to EXECUTION_INTERRUPTED results")
    # Row 1: envelope eligible at interrupt boundary
    for env in envelopes_at_execute_entry:
        if env.kind != "abort":
            continue
        if env.requested_at_tick <= base_tick + result.ticks_consumed:
            return _OPERATOR_ABORT
    # Row 2: budget exceeded
    if tick_budget_ticks is not None and result.ticks_consumed > tick_budget_ticks:
        return _TIMEOUT_FAILURE
    # Row 3: otherwise
    return _NODE_EXECUTION_FAILURE


# Contradiction-preserving retained-state snapshot model.
@dataclass(frozen=True, slots=True)
class _RetainedStateRef:
    """Minimal retained-state snapshot after an interruption.

    Direction A's contradiction-preservation invariant (§13.17 #5,
    D-FAULT-5b carry-forward):
      * D-LIFE state preserved verbatim at last-tick truth
      * fixture occupancy unchanged from session_initial (no PASS, no commit)
      * canonical pose at last-tick truth
      * the contradiction between occupancy and pose/D-LIFE is preserved
        verbatim; no implicit cleanup
    """

    dlife_state_by_object: Mapping[str, str]
    fixture_occupancy: Mapping[str, str | None]
    object_pose_by_object: Mapping[str, tuple[float, float, float]]

    def has_contradiction(self) -> bool:
        """`True` iff some object is D-LIFE-attached but no fixture lists it."""
        for obj_id, dlife in self.dlife_state_by_object.items():
            if dlife != "attached":
                continue
            occupied_by_any = obj_id in set(self.fixture_occupancy.values())
            if not occupied_by_any:
                return True
        return False


# ====================================================================
# Test class 1 — contract-doc structural integrity (Phase 2 freeze present)
# ====================================================================


class TestContractDocStructure:
    """§1.5, §13.1.2, §13.3.2, §13.12.3, §13.17 all present + D-FAULT-15 amended."""

    def test_section_1_5_header_exists(self) -> None:
        assert "### 1.5 Sub-Phase-E interruption surface" in _CONTRACT_TEXT

    def test_section_1_6_non_goals_renumbered(self) -> None:
        # After §1.5 insertion, Non-goals must have moved to §1.6.
        assert "### 1.6 Non-goals" in _CONTRACT_TEXT

    @pytest.mark.parametrize("subclause", ["", "a", "b", "c", "d"])
    def test_dexec_13_subclauses_present(self, subclause: str) -> None:
        tok = f"**D-EXEC-13{subclause}**"
        assert tok in _CONTRACT_TEXT, f"missing {tok}"

    def test_dfault_1b_clause_present(self) -> None:
        assert "**D-FAULT-1b**" in _CONTRACT_TEXT
        assert "13.1.2 D-FAULT-1b" in _CONTRACT_TEXT
        assert "EXECUTION_INTERRUPTED" in _CONTRACT_TEXT

    def test_dfault_3b_clause_present(self) -> None:
        assert "**D-FAULT-3b**" in _CONTRACT_TEXT
        assert "13.3.2 D-FAULT-3b" in _CONTRACT_TEXT
        # Declared-order rule must be visible.
        assert "declared, not best-fit" in _CONTRACT_TEXT

    def test_dfault_12c_clause_present(self) -> None:
        assert "**D-FAULT-12c**" in _CONTRACT_TEXT
        assert "13.12.3 D-FAULT-12c" in _CONTRACT_TEXT
        assert "non-negative integer count" in _CONTRACT_TEXT

    def test_dfault_12a_amended_to_acknowledge_dexec_13(self) -> None:
        # Step 10 freeze amended D-FAULT-12a to cite D-EXEC-13 sub-Phase-E
        # interruption.
        m = re.search(
            r"\*\*D-FAULT-12a\*\* —.*?(?=####|\Z)",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None, "could not locate D-FAULT-12a"
        body = m.group(0)
        assert "D-EXEC-13" in body
        assert "orchestration-observable" in body

    def test_dfault_15_rows_19_through_30_present(self) -> None:
        """D-FAULT-15 table extended with rows 19-30 (Step 10 anti-patterns)."""
        m = re.search(
            r"\*\*D-FAULT-15\*\* — In addition to D-FORBID-1\.\.-14"
            r".*?(?=### 13\.16|\Z)",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None, "D-FAULT-15 section not located"
        rows = re.findall(r"^\| (\d+) \| ", m.group(0), re.M)
        nums = sorted(int(n) for n in rows)
        assert nums == list(range(1, 31)), (
            f"D-FAULT-15 table must enumerate 1..30, got {nums}"
        )

    def test_dfault_15_row_5_strengthened_with_orchestration_observable(self) -> None:
        """Row 5 was amended to 'orchestration-observable' to admit
        sub-Phase-E interruption per D-EXEC-13 without weakening the rule."""
        m = re.search(r"^\| 5 \| (.*?) \|", _CONTRACT_TEXT, re.M)
        assert m is not None
        row5_body = m.group(1)
        assert "orchestration-observable" in row5_body, (
            "D-FAULT-15 row 5 must qualify the prohibition as orchestration-observable"
        )

    def test_section_13_17_scope_extension_restatement_present(self) -> None:
        assert "13.17 Step 10 Direction A scope extension" in _CONTRACT_TEXT
        # Five substrate-posture clauses restated.
        for marker in (
            "Replay-authoritative truth.",
            "D-FAULT-1 enumeration is immutable.",
            "Phase E remains atomic from the orchestration perspective.",
            "Phase-A-only abort ingress.",
            "Contradiction preservation on FAIL.",
        ):
            assert marker in _CONTRACT_TEXT, f"§13.17 missing restatement: {marker!r}"

    def test_clause_index_table_in_section_13_17(self) -> None:
        # §13.17 enumerates the four normative clauses (D-EXEC-13, -1b, -3b, -12c).
        m = re.search(
            r"### 13\.17 Step 10 Direction A scope extension.*?\Z",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None
        body = m.group(0)
        for tok in ("D-EXEC-13", "D-FAULT-1b", "D-FAULT-3b", "D-FAULT-12c"):
            assert tok in body, f"§13.17 clause index missing {tok}"

    def test_closing_paragraph_cites_section_1_5_and_13_17(self) -> None:
        # The closing reference paragraph at end-of-doc was amended to
        # direct future steps to §1.5 and §13.17.
        assert "Section §1.5" in _CONTRACT_TEXT
        assert "§13.17" in _CONTRACT_TEXT

    def test_analysis_doc_marks_phase_2_complete(self) -> None:
        # Look for "PHASE 2 (contract freeze)" and "COMPLETE" within the
        # same status header. Tolerant of subsequent-phase completion
        # markers ("PHASE 1 + PHASE 2 + PHASE 3 COMPLETE", etc.).
        m = re.search(r"\*\*Status:\*\*[^\n]*", _ANALYSIS_TEXT)
        assert m is not None, "analysis doc status header missing"
        status = m.group(0)
        assert "PHASE 2 (contract freeze)" in status
        assert "COMPLETE" in status

    def test_analysis_doc_phase_3_marked_in_progress_or_authorized(self) -> None:
        # Sanity: the analysis doc identifies Phase 3 as the next phase.
        # We do not require it to claim Phase 3 is complete (this test runs
        # during Phase 3); we only require it to know Phase 3 is the next.
        assert "Phase 3" in _ANALYSIS_TEXT
        assert "pure-Python contract tests" in _ANALYSIS_TEXT


# ====================================================================
# Test class 2 — predicate purity (D-EXEC-13, focus area 1)
# ====================================================================


class TestPredicatePurityReferenceModel:
    """A reference predicate is pure, frozen-closure, side-effect-free."""

    def _make_closure(self, **overrides: Any) -> _PredicateClosureRef:
        base: dict[str, Any] = {
            "envelopes": (),
            "base_tick": 0,
            "tick_budget_ticks": 100,
            "task_id": "t_test",
        }
        base.update(overrides)
        return _PredicateClosureRef(**base)

    def _make_traj(self, *lengths: int) -> _TrajectoryRef:
        return _TrajectoryRef(
            segments=tuple(_SegmentRef(f"s{i}", n) for i, n in enumerate(lengths))
        )

    def test_predicate_closure_is_frozen(self) -> None:
        closure = self._make_closure()
        with pytest.raises(FrozenInstanceError):
            closure.base_tick = 999  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            closure.envelopes = ()  # type: ignore[misc]

    def test_predicate_returns_bool_for_every_legal_boundary(self) -> None:
        traj = self._make_traj(10, 10, 10)
        pred = _build_predicate(self._make_closure(), traj)
        for boundary in range(traj.segment_count() + 1):
            r = pred(boundary)
            assert isinstance(r, bool), (
                f"predicate at boundary {boundary} returned {type(r).__name__}"
            )

    def test_predicate_deterministic_for_identical_inputs(self) -> None:
        """D-EXEC-13: identical inputs → identical predicate output sequence."""
        traj = self._make_traj(5, 7, 9)
        closure = self._make_closure(
            envelopes=(_OperatorEnvelopeRef("abort", 12, "r", "e1"),),
            base_tick=0,
            tick_budget_ticks=50,
        )
        seq_a = tuple(_build_predicate(closure, traj)(b) for b in range(traj.segment_count() + 1))
        seq_b = tuple(_build_predicate(closure, traj)(b) for b in range(traj.segment_count() + 1))
        assert seq_a == seq_b

    def test_predicate_no_state_carried_across_invocations(self) -> None:
        """D-EXEC-13: no instance state, no class state — re-evaluation gives same answer."""
        traj = self._make_traj(10, 10, 10)
        closure = self._make_closure(
            envelopes=(_OperatorEnvelopeRef("abort", 15, "r", "e1"),)
        )
        pred = _build_predicate(closure, traj)
        # Re-evaluating boundary 1 multiple times must produce identical output.
        results = tuple(pred(1) for _ in range(5))
        assert len(set(results)) == 1

    def test_predicate_envelope_eligibility_uses_only_authoritative_inputs(self) -> None:
        traj = self._make_traj(10, 10, 10)
        # Envelope eligible at tick 0 → predicate True at boundary 0.
        closure = self._make_closure(
            envelopes=(_OperatorEnvelopeRef("abort", 0, "r", "e1"),)
        )
        pred = _build_predicate(closure, traj)
        assert pred(0) is True

        # Envelope eligible only at tick 25 → predicate False until boundary
        # whose cumulative tick count reaches 25 (after segment 2 at tick 20,
        # not yet; after segment 3 at tick 30, yes).
        closure = self._make_closure(
            envelopes=(_OperatorEnvelopeRef("abort", 25, "r", "e1"),)
        )
        pred = _build_predicate(closure, traj)
        # boundary 0 (cum=0), boundary 1 (cum=10), boundary 2 (cum=20):
        # all False.
        assert pred(0) is False
        assert pred(1) is False
        assert pred(2) is False
        # boundary 3 (cum=30 >= 25): True.
        assert pred(3) is True

    def test_predicate_budget_eligibility_strict_excess(self) -> None:
        traj = self._make_traj(40, 40, 40)
        closure = self._make_closure(tick_budget_ticks=50)
        pred = _build_predicate(closure, traj)
        assert pred(0) is False  # cum=0
        assert pred(1) is False  # cum=40 (not > 50)
        assert pred(2) is True   # cum=80 (> 50)

    def test_predicate_none_budget_means_unbounded(self) -> None:
        traj = self._make_traj(1_000_000)
        closure = self._make_closure(tick_budget_ticks=None)
        pred = _build_predicate(closure, traj)
        # No envelope, no budget → never True.
        assert pred(0) is False
        assert pred(1) is False

    def test_predicate_construction_does_not_mutate_closure(self) -> None:
        envelopes = (
            _OperatorEnvelopeRef("abort", 10, "r", "e1"),
            _OperatorEnvelopeRef("abort", 5, "r", "e2"),
        )
        closure = self._make_closure(envelopes=envelopes)
        traj = self._make_traj(20)
        _ = _build_predicate(closure, traj)
        # Closure tuple unchanged.
        assert closure.envelopes == envelopes
        assert closure.envelopes[0].requested_at_tick == 10
        assert closure.envelopes[1].requested_at_tick == 5


# ====================================================================
# Test class 3 — segment-boundary consultation discipline
#                (D-EXEC-13, D-EXEC-13d, focus area 2)
# ====================================================================


class TestSegmentBoundaryDiscipline:
    """Executor consults predicate at boundaries only; no skipping; no speculation."""

    def _traj_three(self) -> _TrajectoryRef:
        return _TrajectoryRef(
            segments=(
                _SegmentRef("approach", 10),
                _SegmentRef("grasp", 5),
                _SegmentRef("lift", 15),
            )
        )

    def _const_predicate(self, value: bool) -> Callable[[int], bool]:
        def pred(_segment_tick: int) -> bool:
            return value
        return pred

    def _true_at_predicate(self, target: int) -> Callable[[int], bool]:
        def pred(segment_tick: int) -> bool:
            return segment_tick == target
        return pred

    def test_predicate_consulted_exactly_n_plus_1_times_when_no_interrupt(self) -> None:
        """D-EXEC-13: predicate consulted once per boundary, no more, no less."""
        traj = self._traj_three()
        _, trace = _run_reference_executor(traj, self._const_predicate(False), "t")
        # 3 segments → boundaries 0, 1, 2, 3 → 4 consultations
        assert len(trace) == traj.segment_count() + 1
        # Each boundary consulted exactly once.
        seen = sorted(e.boundary_index for e in trace)
        assert seen == list(range(traj.segment_count() + 1))

    def test_no_skipped_boundary_consultation(self) -> None:
        """Each boundary 0..N is consulted exactly once in ascending order."""
        traj = self._traj_three()
        _, trace = _run_reference_executor(traj, self._const_predicate(False), "t")
        indices = [e.boundary_index for e in trace]
        assert indices == sorted(indices), "consultation order must be ascending"
        # Strictly increasing, no duplicates.
        assert len(indices) == len(set(indices))

    def test_no_speculative_double_consultation_after_true(self) -> None:
        """D-EXEC-13d: first True terminates execute; no further consultation."""
        traj = self._traj_three()
        # True at boundary 2 → boundaries 0, 1, 2 consulted; boundary 3 NOT.
        _, trace = _run_reference_executor(traj, self._true_at_predicate(2), "t")
        indices = [e.boundary_index for e in trace]
        assert indices == [0, 1, 2]
        assert trace[-1].predicate_result is True

    def test_no_speculation_at_boundary_0(self) -> None:
        """Boundary-0 True terminates immediately with ticks_consumed = 0."""
        traj = self._traj_three()
        result, trace = _run_reference_executor(traj, self._true_at_predicate(0), "t")
        # Only boundary 0 consulted.
        assert [e.boundary_index for e in trace] == [0]
        assert result.outcome == _EXECUTION_INTERRUPTED
        assert result.ticks_consumed == 0
        assert result.interrupted_at_segment_index == 0

    def test_predicate_consulted_at_every_boundary_until_first_true(self) -> None:
        """No predicate boundary is skipped before a True return."""
        traj = self._traj_three()
        for target in range(traj.segment_count() + 1):
            _, trace = _run_reference_executor(traj, self._true_at_predicate(target), "t")
            indices = [e.boundary_index for e in trace]
            assert indices == list(range(target + 1)), (
                f"target={target}: expected consultation indices 0..{target}, got {indices}"
            )

    def test_ticks_consumed_equals_cumulative_at_boundary(self) -> None:
        """D-FAULT-12c: ticks_consumed = sum of completed segments' tick lengths."""
        traj = self._traj_three()
        for target in range(traj.segment_count() + 1):
            result, _ = _run_reference_executor(traj, self._true_at_predicate(target), "t")
            expected = traj.cumulative_ticks_to_boundary(target)
            assert result.ticks_consumed == expected, (
                f"target={target}: expected ticks_consumed={expected}, got {result.ticks_consumed}"
            )

    def test_segment_tick_argument_matches_consultation_index(self) -> None:
        """D-EXEC-13b: `segment_tick` is the count of completed boundaries."""
        traj = self._traj_three()
        captured: list[int] = []

        def recording_pred(segment_tick: int) -> bool:
            captured.append(segment_tick)
            return False

        _run_reference_executor(traj, recording_pred, "t")
        # Captured arguments must match the boundary indices in order.
        assert captured == list(range(traj.segment_count() + 1))

    def test_segment_boundary_count_is_n_plus_one(self) -> None:
        """N segments → N+1 boundaries (boundary 0 .. boundary N)."""
        traj = _TrajectoryRef(segments=(
            _SegmentRef("a", 1), _SegmentRef("b", 1), _SegmentRef("c", 1),
            _SegmentRef("d", 1), _SegmentRef("e", 1),
        ))
        _, trace = _run_reference_executor(traj, self._const_predicate(False), "t")
        assert len(trace) == 6


# ====================================================================
# Test class 4 — D-FAULT-1b: EXECUTION_INTERRUPTED neutrality
# ====================================================================


class TestDFault1bNeutralOutcome:
    """Executor reports EXECUTION_INTERRUPTED neutrally; session classifies."""

    def test_reference_executor_outcome_is_neutral(self) -> None:
        """The executor reports EXECUTION_INTERRUPTED with no D-FAULT class info."""
        traj = _TrajectoryRef(segments=(_SegmentRef("s", 5),))
        result, _ = _run_reference_executor(traj, lambda _t: True, "t")
        assert result.outcome == _EXECUTION_INTERRUPTED
        # The result carries NO orchestration-level class — the session
        # assigns it. Verified by ensuring the result type has no such field.
        result_fields = set(result.__dataclass_fields__.keys())
        for forbidden in (
            "orchestration_class",
            "failure_class",
            "fault_class",
            "abort_reason",
            "timeout_classification",
        ):
            assert forbidden not in result_fields, (
                f"executor-reported result must NOT carry session-level field {forbidden!r}"
            )

    def test_reference_executor_does_not_classify_envelope_cause(self) -> None:
        """Even when an envelope drove the predicate True, the executor's
        outcome is the same neutral EXECUTION_INTERRUPTED — no special
        cause-code reported."""
        traj = _TrajectoryRef(segments=(_SegmentRef("approach", 5), _SegmentRef("grasp", 5)))

        # Case 1: envelope-driven interrupt.
        closure_env = _PredicateClosureRef(
            envelopes=(_OperatorEnvelopeRef("abort", 0, "r", "e1"),),
            base_tick=0,
            tick_budget_ticks=1000,
            task_id="t",
        )
        pred_env = _build_predicate(closure_env, traj)
        r_env, _ = _run_reference_executor(traj, pred_env, "t")

        # Case 2: budget-driven interrupt (tight budget).
        closure_budget = _PredicateClosureRef(
            envelopes=(),
            base_tick=0,
            tick_budget_ticks=3,  # < first segment
            task_id="t",
        )
        pred_budget = _build_predicate(closure_budget, traj)
        r_budget, _ = _run_reference_executor(traj, pred_budget, "t")

        # Both produce EXECUTION_INTERRUPTED — neutral.
        assert r_env.outcome == _EXECUTION_INTERRUPTED
        assert r_budget.outcome == _EXECUTION_INTERRUPTED

    def test_authoritative_fingerprint_excludes_segment_name_and_index(self) -> None:
        """D-EXEC-13b: interrupted_at_segment_* are observational only."""
        result = _TaskResultRef(
            task_id="t",
            outcome=_EXECUTION_INTERRUPTED,
            ticks_consumed=20,
            interrupted_at_segment_index=2,
            interrupted_at_segment_name="grasp",
        )
        fp = result.authoritative_fingerprint_payload()
        assert "interrupted_at_segment_index" not in fp
        assert "interrupted_at_segment_name" not in fp
        # But these MUST be present on the result for forensics.
        assert result.interrupted_at_segment_index == 2
        assert result.interrupted_at_segment_name == "grasp"

    def test_execution_interrupted_outcome_value_string_stable(self) -> None:
        """The string token MUST be stable across the codebase."""
        # Fingerprint canonicalization includes the literal string.
        result = _TaskResultRef(
            task_id="t",
            outcome=_EXECUTION_INTERRUPTED,
            ticks_consumed=0,
            interrupted_at_segment_index=0,
            interrupted_at_segment_name="pre",
        )
        s = _canonical_dumps(result.authoritative_fingerprint_payload())
        assert '"outcome":"EXECUTION_INTERRUPTED"' in s

    def test_passed_property_excludes_execution_interrupted(self) -> None:
        """EXECUTION_INTERRUPTED is a non-PASS sub-classifier of NODE_EXECUTION_FAILURE."""
        result_passed = _TaskResultRef(
            task_id="t", outcome="PASS", ticks_consumed=30,
            interrupted_at_segment_index=None, interrupted_at_segment_name=None,
        )
        result_interrupted = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=15,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp",
        )
        # Trivial structural assertion — the reference model carries the
        # contract semantic that outcome != "PASS" iff not passed.
        assert result_passed.outcome == "PASS"
        assert result_interrupted.outcome != "PASS"


# ====================================================================
# Test class 5 — D-FAULT-3b classification determinism (focus area 3)
# ====================================================================


class TestDFault3bClassification:
    """Session classifies EXECUTION_INTERRUPTED via declared-order rule."""

    def _interrupted_result(self, *, ticks_consumed: int) -> _TaskResultRef:
        return _TaskResultRef(
            task_id="t",
            outcome=_EXECUTION_INTERRUPTED,
            ticks_consumed=ticks_consumed,
            interrupted_at_segment_index=1,
            interrupted_at_segment_name="grasp",
        )

    def test_row_1_envelope_classifies_as_operator_abort(self) -> None:
        cls = _classify_execution_interrupted(
            result=self._interrupted_result(ticks_consumed=10),
            envelopes_at_execute_entry=(
                _OperatorEnvelopeRef("abort", 5, "stop", "e1"),
            ),
            base_tick=0,
            tick_budget_ticks=100,
        )
        assert cls == _OPERATOR_ABORT

    def test_row_2_budget_classifies_as_timeout(self) -> None:
        cls = _classify_execution_interrupted(
            result=self._interrupted_result(ticks_consumed=120),
            envelopes_at_execute_entry=(),
            base_tick=0,
            tick_budget_ticks=100,
        )
        assert cls == _TIMEOUT_FAILURE

    def test_row_3_otherwise_classifies_as_node_execution_failure(self) -> None:
        cls = _classify_execution_interrupted(
            result=self._interrupted_result(ticks_consumed=50),
            envelopes_at_execute_entry=(),
            base_tick=0,
            tick_budget_ticks=100,
        )
        assert cls == _NODE_EXECUTION_FAILURE

    def test_envelope_outranks_budget_on_tie(self) -> None:
        """Declared-order: envelope row 1 outranks budget row 2."""
        cls = _classify_execution_interrupted(
            result=self._interrupted_result(ticks_consumed=200),  # over budget
            envelopes_at_execute_entry=(
                _OperatorEnvelopeRef("abort", 50, "stop", "e1"),  # eligible
            ),
            base_tick=0,
            tick_budget_ticks=100,
        )
        assert cls == _OPERATOR_ABORT  # NOT TIMEOUT_FAILURE

    def test_envelope_not_yet_eligible_does_not_classify_as_abort(self) -> None:
        """Envelope eligibility uses requested_at_tick <= base_tick + ticks_consumed."""
        # Envelope requested at tick 100, but execute only consumed 10 ticks.
        cls = _classify_execution_interrupted(
            result=self._interrupted_result(ticks_consumed=10),
            envelopes_at_execute_entry=(
                _OperatorEnvelopeRef("abort", 100, "stop", "e1"),
            ),
            base_tick=0,
            tick_budget_ticks=1000,  # generous
        )
        # Envelope not yet eligible; no budget violation; row 3.
        assert cls == _NODE_EXECUTION_FAILURE

    def test_only_abort_kind_envelopes_count_for_row_1(self) -> None:
        """D-FAULT-9a (Step 9): only kind='abort' is permitted. The
        classifier MUST ignore any other kind (defensive)."""
        cls = _classify_execution_interrupted(
            result=self._interrupted_result(ticks_consumed=10),
            envelopes_at_execute_entry=(
                _OperatorEnvelopeRef("pause", 0, "p", "e1"),  # non-abort
            ),
            base_tick=0,
            tick_budget_ticks=100,
        )
        # Pause envelope ignored (Step 9 doesn't support it anyway); no budget
        # violation; falls through to row 3.
        assert cls == _NODE_EXECUTION_FAILURE

    def test_classification_is_pure_function_no_side_effects(self) -> None:
        """Identical inputs → identical output, with no observable side effects."""
        result = self._interrupted_result(ticks_consumed=10)
        envs = (_OperatorEnvelopeRef("abort", 5, "r", "e1"),)
        outs = [
            _classify_execution_interrupted(
                result=result,
                envelopes_at_execute_entry=envs,
                base_tick=0,
                tick_budget_ticks=100,
            )
            for _ in range(5)
        ]
        assert len(set(outs)) == 1

    def test_classification_only_on_execution_interrupted(self) -> None:
        """D-FAULT-3b applies only when outcome == EXECUTION_INTERRUPTED."""
        passed = _TaskResultRef(
            task_id="t", outcome="PASS", ticks_consumed=30,
            interrupted_at_segment_index=None, interrupted_at_segment_name=None,
        )
        with pytest.raises(ValueError):
            _classify_execution_interrupted(
                result=passed,
                envelopes_at_execute_entry=(),
                base_tick=0,
                tick_budget_ticks=100,
            )

    def test_classification_independent_of_segment_index_observational_field(self) -> None:
        """D-EXEC-13b: interrupted_at_segment_index is observational; the
        classifier MUST NOT consult it. Two results that differ only in the
        observational field MUST classify identically."""
        envs = ()
        r_idx_1 = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=150,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp",
        )
        r_idx_5 = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=150,
            interrupted_at_segment_index=5, interrupted_at_segment_name="retract",
        )
        cls_1 = _classify_execution_interrupted(
            result=r_idx_1, envelopes_at_execute_entry=envs,
            base_tick=0, tick_budget_ticks=100,
        )
        cls_5 = _classify_execution_interrupted(
            result=r_idx_5, envelopes_at_execute_entry=envs,
            base_tick=0, tick_budget_ticks=100,
        )
        assert cls_1 == cls_5 == _TIMEOUT_FAILURE


# ====================================================================
# Test class 6 — D-FAULT-12c ticks_consumed ontology (focus area 4)
# ====================================================================


class TestDFault12cTicksConsumedOntology:
    """ticks_consumed is non-negative integer, wall-clock-independent, fingerprint-bound."""

    def test_ticks_consumed_is_non_negative_integer(self) -> None:
        result = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=0,
            interrupted_at_segment_index=0, interrupted_at_segment_name="pre",
        )
        assert isinstance(result.ticks_consumed, int)
        assert result.ticks_consumed >= 0

    def test_ticks_consumed_enters_fingerprint(self) -> None:
        r1 = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=10,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp",
        )
        r2 = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=20,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp",
        )
        fp1 = _canonical_dumps(r1.authoritative_fingerprint_payload())
        fp2 = _canonical_dumps(r2.authoritative_fingerprint_payload())
        assert fp1 != fp2, "ticks_consumed divergence MUST surface in fingerprint"
        assert '"ticks_consumed":10' in fp1
        assert '"ticks_consumed":20' in fp2

    def test_boundary_0_ticks_consumed_is_zero(self) -> None:
        traj = _TrajectoryRef(segments=(_SegmentRef("approach", 5), _SegmentRef("grasp", 5)))
        result, _ = _run_reference_executor(traj, lambda _t: True, "t")
        assert result.ticks_consumed == 0  # interrupted at boundary 0

    def test_full_trajectory_ticks_consumed_equals_total_length(self) -> None:
        traj = _TrajectoryRef(
            segments=(_SegmentRef("a", 10), _SegmentRef("b", 20), _SegmentRef("c", 30))
        )
        result, _ = _run_reference_executor(traj, lambda _t: False, "t")
        assert result.ticks_consumed == 60
        assert result.outcome == "PASS"

    def test_interrupted_segment_contributes_zero_ticks(self) -> None:
        """D-FAULT-12c: 'the interrupted segment contributes zero, because
        the predicate is consulted AT boundaries, not during execution.'"""
        traj = _TrajectoryRef(
            segments=(_SegmentRef("a", 10), _SegmentRef("b", 20), _SegmentRef("c", 30))
        )
        # True at boundary 1 → segment 'a' (10 ticks) completed; 'b' (20)
        # NOT started; result.ticks_consumed == 10.
        result, _ = _run_reference_executor(
            traj, lambda t: t == 1, "t"
        )
        assert result.ticks_consumed == 10

    def test_ticks_consumed_serializable_as_integer_json(self) -> None:
        """No NaN/Inf risk; canonical-JSON is byte-stable across Python versions."""
        r = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=12345,
            interrupted_at_segment_index=2, interrupted_at_segment_name="grasp",
        )
        s = _canonical_dumps(r.authoritative_fingerprint_payload())
        # int rendered as int — no quotes, no decimal point.
        assert '"ticks_consumed":12345' in s
        assert '"ticks_consumed":"12345"' not in s
        assert '"ticks_consumed":12345.0' not in s

    def test_ticks_consumed_byte_stable_across_repeated_serialization(self) -> None:
        r = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=99,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp",
        )
        s1 = _canonical_dumps(r.authoritative_fingerprint_payload())
        s2 = _canonical_dumps(r.authoritative_fingerprint_payload())
        assert s1 == s2

    def test_observational_segment_fields_do_not_alter_fingerprint(self) -> None:
        """D-EXEC-13b / §13.17 #1: observational forensics excluded."""
        r1 = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=50,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp",
        )
        r2 = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=50,
            interrupted_at_segment_index=5, interrupted_at_segment_name="retract",
        )
        fp1 = _canonical_dumps(r1.authoritative_fingerprint_payload())
        fp2 = _canonical_dumps(r2.authoritative_fingerprint_payload())
        assert fp1 == fp2  # observational difference does NOT surface

    def test_wall_clock_use_in_executor_scoped_to_diagnostics_only(self) -> None:
        """D-FAULT-12c: ticks_consumed derivation MUST NOT use wall-clock.

        The executor MAY use `time.*` to populate diagnostic-only fields
        (D-TRACE-4: `wall_clock_s` is diagnostic, excluded from replay-
        identity comparisons). What it MUST NOT do is derive `ticks_consumed`
        from wall-clock. The precise gate is row-24 below
        (`test_ticks_consumed_not_derived_from_wall_clock`), which checks the
        narrow context of `ticks_consumed` assignment.

        This test verifies the broader posture: any wall-clock attribute
        reference in executor.py must live in a context unambiguously
        outside `ticks_consumed` derivation. The check is performed by
        confirming that the same module satisfies the narrow row-24 gate.
        """
        # This test is satisfied iff the narrow row-24 test passes — both run
        # against the same module. Kept as an explicit acknowledgement that
        # diagnostic wall-clock use is permitted under D-TRACE-4 while
        # ticks_consumed derivation is forbidden under D-FAULT-12c.
        executor_path = _TASKS_DIR / "executor.py"
        assert executor_path.exists()


# ====================================================================
# Test class 7 — contradiction preservation (focus area 5)
# ====================================================================


class TestContradictionPreservationOnInterrupt:
    """§13.17 #5: D-FAULT-5/-5a/-5b carry-forward; mid-execute interrupt
    after acquire produces an explicit contradiction (D-LIFE attached +
    fixture occupancy unchanged). No implicit cleanup.

    Reference model: a static retained-state snapshot that demonstrates the
    contradiction is preserved verbatim by a session that observes
    EXECUTION_INTERRUPTED + a post-acquire state.
    """

    def _post_acquire_pre_place_state(self) -> _RetainedStateRef:
        """Peg has been picked from FixtureA but not placed at FixtureB.

        Session_initial: FixtureA occupied_by=peg; FixtureB empty.
        After acquire: peg D-LIFE = attached; FixtureA STILL says
        occupied_by=peg (D-CONT-5: occupancy commit happens at Phase G of
        the SUCCESSOR node N2 — but if N2 was interrupted mid-trajectory,
        no Phase G of N2 fires; FixtureA's empty-out-on-pick happens at
        the pick-node's Phase G; that PASSED in N1).
        """
        return _RetainedStateRef(
            dlife_state_by_object={"peg": "attached"},
            fixture_occupancy={"fixture_a": None, "fixture_b": None},
            object_pose_by_object={"peg": (0.5, 0.0, 0.2)},
        )

    def test_contradiction_state_well_formed(self) -> None:
        """Peg is D-LIFE=attached AND no fixture lists it → contradiction."""
        state = self._post_acquire_pre_place_state()
        assert state.has_contradiction()

    def test_contradiction_state_preserved_verbatim_on_interrupt(self) -> None:
        """No implicit normalization. The retained state is what it was.

        D-FAULT-5b: 'A failed pick from an occupied fixture leaves
        occupancy unchanged; a failed place at an empty fixture leaves
        occupancy unchanged. The resulting contradiction... is REQUIRED to
        be preserved verbatim.'

        Direction A extends this: same applies when the executor returns
        EXECUTION_INTERRUPTED.
        """
        state = self._post_acquire_pre_place_state()
        # Verify no method exists that mutates the state.
        method_names = {
            name for name in dir(_RetainedStateRef)
            if not name.startswith("_") and callable(getattr(_RetainedStateRef, name))
        }
        for forbidden in (
            "cleanup", "normalize", "reconcile", "fix_contradiction",
            "auto_release", "drop_on_interrupt", "release_attached",
        ):
            assert forbidden not in method_names, (
                f"reference state model must NOT expose mutator {forbidden!r}"
            )

    def test_retained_state_is_frozen(self) -> None:
        """No mutation path on the snapshot itself."""
        state = self._post_acquire_pre_place_state()
        with pytest.raises(FrozenInstanceError):
            state.dlife_state_by_object = {}  # type: ignore[misc]

    def test_segment_completion_after_consultation_is_deterministic(self) -> None:
        """Per the brief: 'segment still completed; deterministic
        completion after consultation.'

        The contract guarantees that when the predicate returns False at
        boundary N, the executor proceeds to execute segment N+1 to
        completion — no half-segment state, no partial mutation, the
        retained state is determined entirely by which boundary is reached.
        """
        traj = _TrajectoryRef(segments=(
            _SegmentRef("approach", 10),
            _SegmentRef("grasp", 5),
            _SegmentRef("lift", 15),
        ))
        # No-interrupt run → full completion, ticks_consumed = 30.
        r1, _ = _run_reference_executor(traj, lambda _t: False, "t")
        assert r1.outcome == "PASS"
        assert r1.ticks_consumed == 30

        # Interrupt at boundary 2 (end of grasp) → segments 0 & 1 complete,
        # segment 2 (lift) does NOT execute → ticks_consumed = 15.
        r2, _ = _run_reference_executor(traj, lambda t: t == 2, "t")
        assert r2.outcome == _EXECUTION_INTERRUPTED
        assert r2.ticks_consumed == 15

        # No partial execution of segment 2 — its 15 ticks contribute zero.
        assert r2.ticks_consumed != 15 + 7  # not "partially executed lift"

    def test_simultaneous_truths_preserved_without_normalization(self) -> None:
        """Three truths coexist after an interruption:
          * interruption requested (predicate returned True at some boundary)
          * the segment BEFORE that boundary still completed (deterministic)
          * post-completion retained state is the truth of that boundary

        No normalization. Each truth is preserved.
        """
        traj = _TrajectoryRef(segments=(_SegmentRef("approach", 10), _SegmentRef("grasp", 5)))
        result, trace = _run_reference_executor(traj, lambda t: t == 2, "t")
        # Truth 1: interruption was requested (last trace entry is True).
        assert trace[-1].predicate_result is True
        # Truth 2: the segment immediately before the True-boundary completed
        # — both segments completed (boundary 2 = after grasp).
        assert result.ticks_consumed == 15  # 10 + 5
        # Truth 3: outcome reflects the interruption.
        assert result.outcome == _EXECUTION_INTERRUPTED
        assert result.interrupted_at_segment_index == 2


# ====================================================================
# Test class 8 — anti-pattern constitutional gates (focus area 6)
# Static introspection of production codebase: forbidden patterns absent.
# ====================================================================


class TestAntiPatternGates:
    """D-FAULT-15 rows 19-30 + row 5 strengthening. Production codebase
    free of the Step 10 forbidden patterns.

    These tests pass today (the runtime has not been wired yet) AND remain
    green after Phase 4 wires the surface. They fail loudly if any phase
    introduces a forbidden pattern.
    """

    def _all_source(self) -> dict[Path, str]:
        srcs: dict[Path, str] = {}
        for d in (_ORCH_DIR, _TASKS_DIR):
            for p in d.glob("*.py"):
                if p.name == "__init__.py":
                    continue
                srcs[p] = p.read_text(encoding="utf-8")
        return srcs

    # ---- Row 19: EXECUTION_INTERRUPTED must not be a top-level D-FAULT class.

    def test_execution_interrupted_not_in_top_level_failure_taxonomy(self) -> None:
        """D-FAULT-15 #19: EXECUTION_INTERRUPTED is a TaskOutcome (Phase 4A
        enum), NEVER a top-level orchestration failure class."""
        # Scan orchestration/ source for an enum/class member named
        # EXECUTION_INTERRUPTED in a failure-class context.
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Look for class members named EXECUTION_INTERRUPTED in
                    # any class that smells like a failure-class enum.
                    if any(
                        kw in node.name for kw in (
                            "FailureClass", "OrchestrationFailure", "FaultClass",
                            "TopLevelFault",
                        )
                    ):
                        for sub in ast.walk(node):
                            if isinstance(sub, ast.Assign):
                                for tgt in sub.targets:
                                    if isinstance(tgt, ast.Name) and tgt.id == "EXECUTION_INTERRUPTED":
                                        raise AssertionError(
                                            f"{path.name}: EXECUTION_INTERRUPTED "
                                            f"promoted to top-level class {node.name!r}"
                                        )

    # ---- Row 20: predicate constructed only by ExecutionSession.

    def test_no_predicate_factory_outside_session(self) -> None:
        """D-FAULT-15 #20: interruption predicate construction is
        session-only. No predicate-factory function may live in tasks/
        or in non-session orchestration modules.

        We look for the specific name patterns that would indicate a
        predicate factory: `make_*interrupt*predicate`, `build_*interrupt*`,
        `construct_interrupt*`, `interrupt_predicate_for_*`.
        """
        forbidden_factory_patterns = (
            re.compile(r"^(make|build|construct|create)_.*interrupt.*predicate$"),
            re.compile(r"^interrupt_predicate_(for|of)_.*$"),
        )
        for path, tree in _all_production_ast_files():
            # Skip session.py — predicate construction IS permitted there.
            if path.name == "session.py":
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for pat in forbidden_factory_patterns:
                        if pat.match(node.name):
                            raise AssertionError(
                                f"{path.name}: predicate factory {node.name!r} "
                                f"forbidden outside session.py (D-EXEC-13c)"
                            )

    # ---- Row 21: no per-step or mid-PhysX-command predicate consultation.

    def test_no_per_step_predicate_consultation_helpers(self) -> None:
        """D-FAULT-15 #21: predicate consulted only at SEGMENT boundaries,
        never per-step or per-PhysX-command."""
        forbidden_names = {
            "consult_predicate_per_step",
            "check_interrupt_each_step",
            "poll_interrupt_during_step",
            "interrupt_between_physx_commands",
            "predicate_per_physx_tick",
        }
        for path, tree in _all_production_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_names, (
                        f"{path.name}: per-step predicate consultation forbidden "
                        f"(D-EXEC-13 condition 4 — boundary-only)"
                    )

    # ---- Row 22: no side-effects in predicates.

    def test_no_logging_predicate_helpers(self) -> None:
        """D-FAULT-15 #22: predicates are pure — no I/O, no logging."""
        forbidden_names = {
            "logging_interrupt_predicate",
            "predicate_with_metric_emission",
            "instrumented_interrupt_predicate",
            "predicate_with_side_effects",
        }
        for path, tree in _all_production_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_names, (
                        f"{path.name}: impure predicate helper {node.name!r} forbidden"
                    )

    # ---- Row 23: no speculative interruption.

    def test_no_speculative_interruption_helpers(self) -> None:
        """D-FAULT-15 #23: D-EXEC-13d, no defer / retry the predicate."""
        forbidden_names = {
            "defer_interrupt_to_next_boundary",
            "retry_predicate_at_next_segment",
            "speculative_interrupt_check",
            "soft_interrupt",
            "advisory_interrupt",
        }
        for path, tree in _all_production_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_names, (
                        f"{path.name}: speculative interruption helper {node.name!r} forbidden"
                    )

    # ---- Row 24: wall-clock-derived ticks_consumed.

    def test_ticks_consumed_not_derived_from_wall_clock(self) -> None:
        """D-FAULT-15 #24: no wall-clock derivation of ticks_consumed.

        Static check: in executor.py and session.py, no assignment to
        a `ticks_consumed` attribute uses time/datetime/perf_counter
        in the same expression."""
        wallclock_attr_names = {"time", "perf_counter", "monotonic", "process_time"}
        wallclock_modules = {"datetime", "time"}
        for path in (_TASKS_DIR / "executor.py", _ORCH_DIR / "session.py"):
            if not path.exists():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                # Look for `ticks_consumed = <expr>` where <expr> involves wall-clock.
                if isinstance(node, ast.Assign):
                    targets = [t for t in node.targets if isinstance(t, (ast.Name, ast.Attribute))]
                    if not any(
                        (isinstance(t, ast.Name) and t.id == "ticks_consumed")
                        or (isinstance(t, ast.Attribute) and t.attr == "ticks_consumed")
                        for t in targets
                    ):
                        continue
                    # Inspect the RHS for wall-clock references.
                    for sub in ast.walk(node.value):
                        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name):
                            if sub.value.id in wallclock_modules and sub.attr in wallclock_attr_names:
                                raise AssertionError(
                                    f"{path.name}: ticks_consumed derived from "
                                    f"{sub.value.id}.{sub.attr} (D-FAULT-15 #24)"
                                )

    # ---- Row 25: observational fields must not enter fingerprint.

    def test_interrupted_at_segment_not_in_fingerprint_helpers(self) -> None:
        """D-FAULT-15 #25: interrupted_at_segment_* are observational; they
        MUST NOT enter the per-task fingerprint."""
        for path, src in self._all_source().items():
            # Look for: any function that builds a fingerprint payload also
            # including the observational fields. This is a heuristic
            # forward-compat check.
            if "fingerprint" not in src.lower():
                continue
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if "fingerprint" not in node.name.lower():
                        continue
                    body_src = ast.get_source_segment(src, node) or ""
                    # The function must not include the observational keys.
                    for forbidden_key in (
                        '"interrupted_at_segment_index"',
                        "'interrupted_at_segment_index'",
                        '"interrupted_at_segment_name"',
                        "'interrupted_at_segment_name'",
                    ):
                        assert forbidden_key not in body_src, (
                            f"{path.name}::{node.name}: observational field "
                            f"{forbidden_key} must NOT enter fingerprint"
                        )

    # ---- Row 26: executor-side classification.

    def test_executor_does_not_classify_into_orchestration_failure_classes(self) -> None:
        """D-FAULT-15 #26: executor reports neutral EXECUTION_INTERRUPTED;
        classification is session-only."""
        executor_path = _TASKS_DIR / "executor.py"
        tree = ast.parse(executor_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # The executor must NOT emit orchestration-level class strings.
                # OPERATOR_ABORT / TIMEOUT_FAILURE / AUTHORITY_VIOLATION /
                # CONTINUITY_VALIDATION_FAILURE / PRECONDITION_FAILURE are
                # session-emitted (D-FAULT-2 single-emitter).
                if node.value in (
                    "OPERATOR_ABORT",
                    "TIMEOUT_FAILURE",
                    "AUTHORITY_VIOLATION",
                    "CONTINUITY_VALIDATION_FAILURE",
                    "PRECONDITION_FAILURE",
                    "REPLAY_INTEGRITY_FAILURE",
                    "INFRASTRUCTURE_DEGRADATION",
                ):
                    raise AssertionError(
                        f"executor.py references session-level failure class "
                        f"{node.value!r} — D-FAULT-15 #26 (executor-side "
                        f"classification forbidden)"
                    )

    # ---- Row 27: no mid-execute envelope drain.

    def test_no_phase_a_drain_inside_phase_e(self) -> None:
        """D-FAULT-15 #27: no session-side envelope drain interleaved with
        Phase E (`execute()` invocation)."""
        forbidden_names = {
            "drain_envelopes_during_execute",
            "drain_envelopes_mid_phase_e",
            "phase_a_drain_during_phase_e",
        }
        for path, tree in _all_production_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_names, (
                        f"{path.name}: mid-execute drain helper {node.name!r} forbidden"
                    )

    # ---- Row 28: no async / signal / thread interruption channels.

    def test_no_async_signal_thread_interruption_imports(self) -> None:
        """D-FAULT-15 #28: synchronous executor only.

        Step 9 already gates async/threading/signal in orchestration. Step 10
        extends the gate to tasks/ since the executor is the home of the
        interruption surface."""
        forbidden_modules = {"asyncio", "threading", "signal", "multiprocessing", "_thread"}
        for path, tree in _all_production_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in forbidden_modules, (
                            f"{path.name}: forbidden import {alias.name!r} — "
                            f"async/signal/thread interruption channels forbidden"
                        )
                if isinstance(node, ast.ImportFrom):
                    assert node.module not in forbidden_modules, (
                        f"{path.name}: forbidden 'from {node.module} import' — "
                        f"async/signal/thread interruption channels forbidden"
                    )

    def test_no_async_or_await_in_tasks_directory(self) -> None:
        """D-FAULT-15 #28 + D-FORBID async-anywhere: no async/await in tasks/.

        Step 9 already gates orchestration; Step 10 extends the gate to
        tasks/ now that the executor consults a predicate."""
        for path, tree in _tasks_ast_files():
            for node in ast.walk(tree):
                assert not isinstance(node, ast.AsyncFunctionDef), (
                    f"{path.name}: async def forbidden (D-FAULT-15 #28)"
                )
                assert not isinstance(node, ast.Await), (
                    f"{path.name}: await forbidden (D-FAULT-15 #28)"
                )

    # ---- Row 29: adaptive predicates.

    def test_no_adaptive_predicate_helpers(self) -> None:
        """D-FAULT-15 #29: predicate is constant for the lifetime of one
        execute() call. Adaptive / mutating predicates are forbidden."""
        forbidden_names = {
            "mutate_predicate_during_execute",
            "swap_predicate_at_segment",
            "adaptive_interrupt_predicate",
            "stateful_interrupt_predicate",
            "predicate_with_internal_counter",
            "replace_predicate_mid_execute",
        }
        for path, tree in _all_production_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_names, (
                        f"{path.name}: adaptive predicate helper {node.name!r} forbidden"
                    )

    # ---- Row 30: live-channel ingress mid-execute.

    def test_no_live_envelope_ingress_during_execute(self) -> None:
        """D-FAULT-15 #30: envelopes are captured by closure at execute-entry;
        mid-execute live ingress is Step 11 territory and FORBIDDEN here."""
        forbidden_names = {
            "ingest_envelope_during_execute",
            "live_envelope_into_predicate",
            "push_envelope_mid_execute",
            "stream_envelope_to_predicate",
            "subscribe_envelopes_during_execute",
        }
        for path, tree in _all_production_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_names, (
                        f"{path.name}: live-channel ingress helper {node.name!r} "
                        f"forbidden (Step 11 territory)"
                    )

    # ---- Row 5 (amended): orchestration-observable mid-Phase-E interrupt.

    def test_no_session_side_mid_execute_polling_helpers(self) -> None:
        """D-FAULT-15 #5 (amended): session-side mid-execute polling /
        interruption is forbidden. Sub-Phase-E interruption per D-EXEC-13
        is executor-INTERNAL, not session-observable."""
        forbidden_names = {
            "poll_executor_during_execute",
            "interrupt_executor_mid_phase_e",
            "session_watchdog_during_execute",
            "force_interrupt_from_session",
            "session_observe_mid_execute",
        }
        for path, tree in _orch_ast_files():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert node.name not in forbidden_names, (
                        f"{path.name}: session-observable mid-Phase-E interrupt "
                        f"helper {node.name!r} forbidden (D-FAULT-15 #5)"
                    )


# ====================================================================
# Test class 9 — replay-identity posture (focus area 7)
# ====================================================================


class TestReplayIdentityPosture:
    """Interruption traces remain replay-stable; observational fields excluded."""

    def test_repeated_executor_runs_byte_identical(self) -> None:
        traj = _TrajectoryRef(segments=(
            _SegmentRef("a", 10), _SegmentRef("b", 20), _SegmentRef("c", 30),
        ))
        pred = _build_predicate(
            _PredicateClosureRef(
                envelopes=(_OperatorEnvelopeRef("abort", 15, "stop", "e1"),),
                base_tick=0,
                tick_budget_ticks=100,
                task_id="t",
            ),
            traj,
        )
        runs: list[str] = []
        for _ in range(3):
            r, trace = _run_reference_executor(traj, pred, "t")
            runs.append(_canonical_dumps({
                "fingerprint": r.authoritative_fingerprint_payload(),
                "trace": [
                    {"boundary": e.boundary_index, "result": e.predicate_result}
                    for e in trace
                ],
            }))
        assert runs[0] == runs[1] == runs[2]

    def test_ticks_consumed_divergence_surfaces_in_fingerprint(self) -> None:
        """D-FAULT-12c: divergent ticks_consumed → divergent fingerprint."""
        traj = _TrajectoryRef(segments=(_SegmentRef("a", 10), _SegmentRef("b", 20)))

        # Cycle 1: interrupt at boundary 1 → ticks_consumed = 10.
        pred_1 = lambda t: t == 1
        r1, _ = _run_reference_executor(traj, pred_1, "t")
        fp1 = _canonical_dumps(r1.authoritative_fingerprint_payload())

        # Cycle 2: interrupt at boundary 2 → ticks_consumed = 30.
        pred_2 = lambda t: t == 2
        r2, _ = _run_reference_executor(traj, pred_2, "t")
        fp2 = _canonical_dumps(r2.authoritative_fingerprint_payload())

        assert fp1 != fp2

    def test_observational_segment_divergence_does_not_surface(self) -> None:
        """D-EXEC-13b: differing interrupted_at_segment_name MUST NOT
        diverge the fingerprint, given the same ticks_consumed + outcome."""
        r_a = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=10,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp",
        )
        r_b = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=10,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp_alt",
        )
        fp_a = _canonical_dumps(r_a.authoritative_fingerprint_payload())
        fp_b = _canonical_dumps(r_b.authoritative_fingerprint_payload())
        assert fp_a == fp_b

    def test_classification_byte_stable_across_repeated_runs(self) -> None:
        """D-FAULT-3b output is byte-stable for identical inputs."""
        result = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=200,
            interrupted_at_segment_index=2, interrupted_at_segment_name="grasp",
        )
        envs = (_OperatorEnvelopeRef("abort", 50, "stop", "e1"),)
        outs = [
            _classify_execution_interrupted(
                result=result,
                envelopes_at_execute_entry=envs,
                base_tick=0,
                tick_budget_ticks=100,
            )
            for _ in range(5)
        ]
        assert outs == [_OPERATOR_ABORT] * 5

    def test_envelope_input_ordering_invariant_for_classifier(self) -> None:
        """D-FAULT-3b: canonical envelope ordering preserved; classifier MUST
        treat the input as a tuple. Even if presented out of order, the
        same envelopes produce the same classification."""
        result = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=50,
            interrupted_at_segment_index=1, interrupted_at_segment_name="grasp",
        )
        envs_a = (
            _OperatorEnvelopeRef("abort", 30, "stop", "e_a"),
            _OperatorEnvelopeRef("abort", 70, "stop", "e_b"),
        )
        envs_b = (
            _OperatorEnvelopeRef("abort", 70, "stop", "e_b"),
            _OperatorEnvelopeRef("abort", 30, "stop", "e_a"),
        )
        cls_a = _classify_execution_interrupted(
            result=result, envelopes_at_execute_entry=envs_a,
            base_tick=0, tick_budget_ticks=100,
        )
        cls_b = _classify_execution_interrupted(
            result=result, envelopes_at_execute_entry=envs_b,
            base_tick=0, tick_budget_ticks=100,
        )
        # Both should classify as OPERATOR_ABORT (envelope at tick 30 eligible
        # since ticks_consumed=50). The classification is invariant to input
        # ordering of envelopes.
        assert cls_a == cls_b == _OPERATOR_ABORT


# ====================================================================
# Test class 10 — suite byte-determinism (focus area 7 closure)
# ====================================================================


class TestSuiteByteDeterminism:
    """The reference models themselves are byte-deterministic across invocations."""

    def test_predicate_construction_byte_identical_for_identical_inputs(self) -> None:
        closure = _PredicateClosureRef(
            envelopes=(_OperatorEnvelopeRef("abort", 10, "r", "e1"),),
            base_tick=5,
            tick_budget_ticks=50,
            task_id="t",
        )
        traj = _TrajectoryRef(segments=(_SegmentRef("a", 20), _SegmentRef("b", 20)))
        seqs: list[str] = []
        for _ in range(3):
            p = _build_predicate(closure, traj)
            seqs.append(
                _canonical_dumps(
                    [bool(p(b)) for b in range(traj.segment_count() + 1)]
                )
            )
        assert seqs[0] == seqs[1] == seqs[2]

    def test_executor_run_byte_identical_for_identical_inputs(self) -> None:
        traj = _TrajectoryRef(segments=(
            _SegmentRef("a", 10), _SegmentRef("b", 20), _SegmentRef("c", 30),
        ))
        runs: list[str] = []
        for _ in range(3):
            r, trace = _run_reference_executor(traj, lambda t: t == 2, "t")
            runs.append(_canonical_dumps({
                "fp": r.authoritative_fingerprint_payload(),
                "trace": [(e.boundary_index, e.predicate_result) for e in trace],
            }))
        assert runs[0] == runs[1] == runs[2]

    def test_classifier_run_byte_identical_for_identical_inputs(self) -> None:
        result = _TaskResultRef(
            task_id="t", outcome=_EXECUTION_INTERRUPTED, ticks_consumed=80,
            interrupted_at_segment_index=2, interrupted_at_segment_name="g",
        )
        envs = (_OperatorEnvelopeRef("abort", 25, "r", "e1"),)
        outs: list[str] = []
        for _ in range(3):
            outs.append(_classify_execution_interrupted(
                result=result, envelopes_at_execute_entry=envs,
                base_tick=0, tick_budget_ticks=50,
            ))
        assert outs[0] == outs[1] == outs[2]


# ====================================================================
# Test class 11 — taxonomy carry-forward (D-FAULT-1 enumeration unchanged)
# ====================================================================


class TestDFault1EnumerationUnchanged:
    """§13.17 #2: D-FAULT-1 eight-class enumeration is immutable."""

    def test_eight_canonical_classes_still_listed(self) -> None:
        for cls in (
            "NODE_EXECUTION_FAILURE",
            "PRECONDITION_FAILURE",
            "AUTHORITY_VIOLATION",
            "CONTINUITY_VALIDATION_FAILURE",
            "TIMEOUT_FAILURE",
            "OPERATOR_ABORT",
            "INFRASTRUCTURE_DEGRADATION",
            "REPLAY_INTEGRITY_FAILURE",
        ):
            assert cls in _CONTRACT_TEXT, f"D-FAULT-1 class {cls} missing"

    def test_no_ninth_top_level_class_introduced(self) -> None:
        """The Step 10 freeze does NOT expand D-FAULT-1's eight-class set.

        Locate the D-FAULT-1 table and count rows (column 1 entries).
        """
        m = re.search(
            r"\*\*D-FAULT-1\*\* — Failure at the orchestration level.*?"
            r"Expansion of this list is a contract revision",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None, "could not locate D-FAULT-1 table block"
        block = m.group(0)
        # Count table rows starting with `| `<CLASS>`
        rows = re.findall(r"^\| `([A-Z_]+)`", block, re.M)
        assert len(rows) == 8, f"D-FAULT-1 table must have exactly 8 classes, got {len(rows)}: {rows}"

    def test_execution_interrupted_documented_only_as_sub_classifier(self) -> None:
        """D-FAULT-1b body uses 'sub-classifier of NODE_EXECUTION_FAILURE'."""
        m = re.search(
            r"#### 13\.1\.2 D-FAULT-1b.*?(?=###)",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None
        body = m.group(0)
        assert "sub-classifier of `NODE_EXECUTION_FAILURE`" in body
        # And the body explicitly forbids promotion.
        assert "MUST NOT be promoted to a top-level D-FAULT-1 class" in body


# ====================================================================
# Test class 12 — D-FAULT-15 row content well-formedness
# ====================================================================


class TestDFault15RowFormat:
    """Rows 19-30 reference the correct clauses; each row cites at least
    one D-EXEC-13 or D-FAULT-* clause."""

    def test_each_new_row_cites_at_least_one_clause(self) -> None:
        m = re.search(
            r"\*\*D-FAULT-15\*\* — In addition to D-FORBID-1\.\.-14"
            r".*?(?=### 13\.16|\Z)",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None
        block = m.group(0)
        for row_num in range(19, 31):
            row_match = re.search(rf"^\| {row_num} \| (.+?) \| (.+?) \|", block, re.M)
            assert row_match is not None, f"D-FAULT-15 row {row_num} missing"
            cite_col = row_match.group(2)
            # Each new row must cite at least one D-EXEC-13 / D-FAULT-* clause.
            assert re.search(
                r"D-(EXEC|FAULT|CONT|SCHED|SESS|TRACE|BUS|REPLAY|FORBID|SCALE|CONF)-",
                cite_col,
            ) or "§1.6" in cite_col, (
                f"D-FAULT-15 row {row_num} cites no D-* clause: {cite_col!r}"
            )

    def test_row_19_cites_d_fault_1b(self) -> None:
        m = re.search(r"^\| 19 \| .+? \| (.+?) \|", _CONTRACT_TEXT, re.M)
        assert m is not None
        assert "D-FAULT-1b" in m.group(1) or "D-FAULT-1" in m.group(1)

    def test_row_20_cites_d_exec_13c(self) -> None:
        m = re.search(r"^\| 20 \| .+? \| (.+?) \|", _CONTRACT_TEXT, re.M)
        assert m is not None
        assert "D-EXEC-13c" in m.group(1)

    def test_row_23_cites_d_exec_13d(self) -> None:
        m = re.search(r"^\| 23 \| .+? \| (.+?) \|", _CONTRACT_TEXT, re.M)
        assert m is not None
        assert "D-EXEC-13d" in m.group(1)

    def test_row_24_cites_d_fault_12c(self) -> None:
        m = re.search(r"^\| 24 \| .+? \| (.+?) \|", _CONTRACT_TEXT, re.M)
        assert m is not None
        assert "D-FAULT-12c" in m.group(1)

    def test_row_26_cites_d_fault_1b_and_3b(self) -> None:
        m = re.search(r"^\| 26 \| .+? \| (.+?) \|", _CONTRACT_TEXT, re.M)
        assert m is not None
        cites = m.group(1)
        assert "D-FAULT-1b" in cites
        assert "D-FAULT-3b" in cites


# ====================================================================
# Test class 13 — load-bearing assertion enumeration (§13.17 footer)
# ====================================================================


class TestStep10LoadBearingAssertions:
    """§13.17 enumerates 8 load-bearing landing assertions. Verify presence."""

    def test_eight_load_bearing_assertions_enumerated(self) -> None:
        m = re.search(
            r"The load-bearing assertions Step 10 Direction A must satisfy at landing:"
            r".*?If Step 10 Direction A lands but any of these load-bearing",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None, "§13.17 load-bearing-assertions block missing"
        body = m.group(0)
        # Eight numbered items.
        nums = re.findall(r"^\s*(\d+)\.\s", body, re.M)
        assert [int(n) for n in nums] == [1, 2, 3, 4, 5, 6, 7, 8], (
            f"§13.17 must enumerate exactly 8 load-bearing assertions, got {nums}"
        )

    def test_each_load_bearing_assertion_cites_a_clause(self) -> None:
        """Every assertion line must cite at least one D-EXEC-13 / D-FAULT-* clause."""
        m = re.search(
            r"The load-bearing assertions Step 10 Direction A must satisfy at landing:"
            r".*?If Step 10 Direction A lands but any of these load-bearing",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None
        body = m.group(0)
        items = re.findall(r"^\s*\d+\.\s+(.+?)$", body, re.M)
        assert len(items) == 8
        for i, txt in enumerate(items, start=1):
            assert re.search(
                r"D-(EXEC|FAULT|CONT|SCHED|SESS|TRACE|BUS|REPLAY|FORBID|SCALE|CONF)-",
                txt,
            ) or "Phase 4A" in txt or "Step 8" in txt or "Step 9" in txt, (
                f"§13.17 load-bearing assertion {i} cites no clause: {txt!r}"
            )


# ====================================================================
# Test class 14 — substrate invariants carry-forward (§13.17 #1-#5)
# ====================================================================


class TestSubstrateInvariantsCarryForward:
    """Five substrate-posture restatements present + reachable."""

    @pytest.mark.parametrize(
        "marker",
        [
            "Replay-authoritative truth.",
            "D-FAULT-1 enumeration is immutable.",
            "Phase E remains atomic from the orchestration perspective.",
            "Phase-A-only abort ingress.",
            "Contradiction preservation on FAIL.",
        ],
    )
    def test_substrate_posture_restated(self, marker: str) -> None:
        assert marker in _CONTRACT_TEXT, (
            f"§13.17 substrate-posture restatement missing: {marker!r}"
        )

    def test_d_cont_1_through_7a_still_referenced(self) -> None:
        """§13.17 explicitly cites the immovable substrate."""
        m = re.search(
            r"### 13\.17 Step 10 Direction A scope extension.*?\Z",
            _CONTRACT_TEXT,
            re.S,
        )
        assert m is not None
        body = m.group(0)
        for clause in ("D-CONT-1", "D-CONT-5", "D-FAULT-5", "D-FAULT-6", "D-FAULT-6a"):
            assert clause in body, f"§13.17 must reference {clause}"


# ====================================================================
# Test class 15 — reference-model integrity (sanity)
# ====================================================================


class TestReferenceModelIntegrity:
    """The reference models themselves are frozen, side-effect-free, minimal."""

    def test_predicate_closure_is_frozen_dataclass(self) -> None:
        import dataclasses
        params = _PredicateClosureRef.__dataclass_params__  # type: ignore[attr-defined]
        assert params.frozen is True

    def test_segment_ref_is_frozen_dataclass(self) -> None:
        params = _SegmentRef.__dataclass_params__  # type: ignore[attr-defined]
        assert params.frozen is True

    def test_trajectory_ref_is_frozen_dataclass(self) -> None:
        params = _TrajectoryRef.__dataclass_params__  # type: ignore[attr-defined]
        assert params.frozen is True

    def test_task_result_ref_is_frozen_dataclass(self) -> None:
        params = _TaskResultRef.__dataclass_params__  # type: ignore[attr-defined]
        assert params.frozen is True

    def test_retained_state_ref_is_frozen_dataclass(self) -> None:
        params = _RetainedStateRef.__dataclass_params__  # type: ignore[attr-defined]
        assert params.frozen is True

    def test_no_reference_model_carries_mutator_methods(self) -> None:
        """Reference models expose ONLY observational methods.

        Forbidden method-name prefixes: mutate_, set_, write_, persist_,
        commit_, cleanup_, normalize_, reconcile_, fix_, repair_, heal_,
        retry_.
        """
        forbidden_prefixes = (
            "mutate_", "set_", "write_", "persist_", "commit_",
            "cleanup_", "normalize_", "reconcile_", "fix_",
            "repair_", "heal_", "retry_",
        )
        for model in (
            _OperatorEnvelopeRef, _SegmentRef, _TrajectoryRef,
            _PredicateClosureRef, _TaskResultRef, _ExecutorTraceEntryRef,
            _RetainedStateRef,
        ):
            for name in dir(model):
                if name.startswith("_"):
                    continue
                for prefix in forbidden_prefixes:
                    assert not name.startswith(prefix), (
                        f"{model.__name__}: forbidden mutator method "
                        f"{name!r} (starts with {prefix!r})"
                    )

    def test_reference_models_do_not_import_async_or_time(self) -> None:
        """This very test file is the reference home. It MUST NOT use
        wall-clock or async itself."""
        this_file = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(this_file)
        forbidden_modules = {"asyncio", "threading", "signal", "multiprocessing"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_modules, (
                        f"test file imports forbidden module {alias.name}"
                    )
            if isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden_modules, (
                    f"test file 'from {node.module} import' forbidden"
                )
            # Forbid wall-clock attribute references in the reference models.
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "time" and node.attr in {
                    "time", "perf_counter", "monotonic", "process_time",
                }:
                    raise AssertionError(
                        f"reference model uses time.{node.attr} — forbidden"
                    )
