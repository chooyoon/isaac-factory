"""Phase 4B Step 9 Phase 7 — replay-identity comparator extension tests.

Validates the extended ``tools/check_session_replay_identity.py`` against
failure-terminating SessionPackages constructed in-test. No Isaac
dependency, no PhysX, no threading.

Phase 7 brief items covered:

  1. Comparator handles FAILED + ABORTED sessions as first-class
     replay objects (D-FAULT-3 / -4 / -9, F.12 ruling).
  2. Strict byte-identity preserved (D-FAULT-11a; no tolerance,
     no fuzzy match, no normalized repair).
  3. Failure-session fingerprint coverage — terminus classifier,
     terminator_reason, schema_version=2, OperatorEnvelope ids,
     cascade ordering.
  4. Multi-cycle byte-identity for the four canonical failure
     scenarios (operator-abort, cascade-skip, contradiction
     preservation, schema_version=2).
  5. REPLAY_INTEGRITY_FAILURE is comparator-only (no in-session
     event ever appended; D-FAULT-11).
  6. Forensic validation: append-only ordering, deterministic
     terminal events, envelope causality, no hidden mutation.
  7. Schema-version enforcement — pre-Phase-5 (schema=1) packages
     refused against post-Phase-5 (schema=2) packages per D-CONT-6b.
  8. Sequencing discipline preserved — comparator is pure-Python and
     stateless; no async, threading, recovery, or healing logic.

The comparator must:

  * exit 0 (REPLAY-IDENTICAL) when both packages are byte-equal,
    same schema, same terminus, same terminator;
  * exit 1 (REPLAY-DIVERGENT) when packages are byte-different but
    classify identically;
  * exit 2 (REPLAY-INVALID) when packages cannot be meaningfully
    compared (missing files, malformed events.jsonl, schema mismatch,
    incomplete trace, terminus class mismatch, terminator mismatch).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


_WORKSPACE = Path(__file__).resolve().parents[5]
_COMPARATOR_PATH = _WORKSPACE / "tools" / "check_session_replay_identity.py"

assert _COMPARATOR_PATH.exists(), (
    f"comparator not located at {_COMPARATOR_PATH}"
)


# Load the comparator module by file path (the tools/ directory is not
# part of an importable package).
_spec = importlib.util.spec_from_file_location(
    "check_session_replay_identity", _COMPARATOR_PATH
)
assert _spec is not None and _spec.loader is not None
comparator = importlib.util.module_from_spec(_spec)
sys.modules["check_session_replay_identity"] = comparator
_spec.loader.exec_module(comparator)


# --------------------------------------------------------------------
# Helpers for synthesizing SessionPackages in-test
# --------------------------------------------------------------------


def _canonical_dumps(obj: Any) -> str:
    """Match D-TRACE-8 canonical encoding."""
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )


def _write_session_package(
    pkg_dir: Path,
    events: list[dict[str, Any]],
    manifest: dict[str, Any] | None = None,
) -> Path:
    """Construct a SessionPackage directory with manifest.json +
    events.jsonl in canonical-JSON form. Returns the directory path.
    """
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "events.jsonl").write_text(
        "\n".join(_canonical_dumps(e) for e in events) + "\n",
        encoding="utf-8",
    )
    if manifest is None:
        manifest = {
            "package_version": 1,
            "invariant_contract_version": 1,
            "event_count": len(events),
            "trace_hash": None,
            "runtime_hash": None,
            "session_identity": None,
        }
    (pkg_dir / "manifest.json").write_text(
        _canonical_dumps(manifest), encoding="utf-8"
    )
    return pkg_dir


def _completed_session_events(schema_version: int = 2) -> list[dict[str, Any]]:
    return [
        {"seq": 0, "event_type": "SessionStarted",
         "payload": {"graph_fingerprint": "g_h0", "node_count": 1},
         "orchestration_tick": 0},
        {"seq": 1, "event_type": "NodeBoundarySnapshot",
         "payload": {"canonical_hash": "abc", "node_id": None,
                     "schema_version": schema_version,
                     "snapshot_kind": "session_initial", "snapshot_seq": 1},
         "orchestration_tick": 1},
        {"seq": 2, "event_type": "NodeSelected",
         "payload": {"node_id": "n1", "scheduler_decision_fingerprint": "d_h"},
         "orchestration_tick": 2},
        {"seq": 3, "event_type": "NodeExecutionCompleted",
         "payload": {"node_id": "n1", "passed": True,
                     "outcome_value": "PASS", "task_result_fingerprint": "r_h"},
         "orchestration_tick": 3},
        {"seq": 4, "event_type": "SessionCompleted",
         "payload": {"completed_count": 1, "failed_count": 0, "node_count": 1},
         "orchestration_tick": 4},
    ]


def _failed_session_events(schema_version: int = 2) -> list[dict[str, Any]]:
    return [
        {"seq": 0, "event_type": "SessionStarted",
         "payload": {"graph_fingerprint": "g_h0", "node_count": 2},
         "orchestration_tick": 0},
        {"seq": 1, "event_type": "NodeBoundarySnapshot",
         "payload": {"canonical_hash": "abc", "node_id": None,
                     "schema_version": schema_version,
                     "snapshot_kind": "session_initial", "snapshot_seq": 1},
         "orchestration_tick": 1},
        {"seq": 2, "event_type": "NodeExecutionCompleted",
         "payload": {"node_id": "n1", "passed": False,
                     "outcome_value": "PLACEMENT_MISS",
                     "task_result_fingerprint": "r_h"},
         "orchestration_tick": 2},
        {"seq": 3, "event_type": "TaskCascadeSkipped",
         "payload": {"node_id": "n2", "ancestor_failed_id": "n1",
                     "reason": "SKIP_NODE"},
         "orchestration_tick": 3},
        {"seq": 4, "event_type": "SessionFailed",
         "payload": {"completed_count": 0, "failed_count": 1,
                     "skipped_count": 1, "node_count": 2,
                     "first_failure": "n1",
                     "terminator_reason": "NODE_EXECUTION_FAILURE"},
         "orchestration_tick": 4},
    ]


def _aborted_session_events(
    schema_version: int = 2,
    envelope_id: str = "env_id_abc",
) -> list[dict[str, Any]]:
    return [
        {"seq": 0, "event_type": "SessionStarted",
         "payload": {"graph_fingerprint": "g_h0", "node_count": 2},
         "orchestration_tick": 0},
        {"seq": 1, "event_type": "NodeBoundarySnapshot",
         "payload": {"canonical_hash": "abc", "node_id": None,
                     "schema_version": schema_version,
                     "snapshot_kind": "session_initial", "snapshot_seq": 1},
         "orchestration_tick": 1},
        {"seq": 2, "event_type": "OperatorAbortRequested",
         "payload": {"envelope_id": envelope_id, "kind": "abort",
                     "reason": "stop", "requested_at_tick": 0},
         "orchestration_tick": 2},
        {"seq": 3, "event_type": "SessionAborting",
         "payload": {"terminator_reason": "OPERATOR_ABORT",
                     "trigger_envelope_id": envelope_id},
         "orchestration_tick": 3},
        {"seq": 4, "event_type": "TaskCascadeSkipped",
         "payload": {"node_id": "n1", "ancestor_failed_id": None,
                     "reason": "OPERATOR_ABORT"},
         "orchestration_tick": 4},
        {"seq": 5, "event_type": "TaskCascadeSkipped",
         "payload": {"node_id": "n2", "ancestor_failed_id": None,
                     "reason": "OPERATOR_ABORT"},
         "orchestration_tick": 5},
        {"seq": 6, "event_type": "SessionAborted",
         "payload": {"completed_count": 0, "failed_count": 0,
                     "skipped_count": 2, "node_count": 2,
                     "terminator_reason": "OPERATOR_ABORT"},
         "orchestration_tick": 6},
    ]


# --------------------------------------------------------------------
# Test class 1 — terminus classification (D-FAULT-3 / F.11)
# --------------------------------------------------------------------


class TestTerminusClassification:
    """Comparator extracts (terminus, terminator_reason, terminal_seq)
    correctly for each canonical termination class."""

    def test_completed_session(self, tmp_path: Path) -> None:
        events = _completed_session_events()
        pkg = _write_session_package(tmp_path / "pkg", events)
        cls = comparator.classify_terminus(pkg / "events.jsonl")
        assert cls["terminus"] == "COMPLETED"
        assert cls["terminal_event_type"] == "SessionCompleted"
        assert cls["terminal_seq"] == 4
        assert cls["terminator_reason"] is None
        assert cls["event_count"] == 5

    def test_failed_session(self, tmp_path: Path) -> None:
        events = _failed_session_events()
        pkg = _write_session_package(tmp_path / "pkg", events)
        cls = comparator.classify_terminus(pkg / "events.jsonl")
        assert cls["terminus"] == "FAILED"
        assert cls["terminal_event_type"] == "SessionFailed"
        assert cls["terminator_reason"] == "NODE_EXECUTION_FAILURE"

    def test_aborted_session(self, tmp_path: Path) -> None:
        events = _aborted_session_events()
        pkg = _write_session_package(tmp_path / "pkg", events)
        cls = comparator.classify_terminus(pkg / "events.jsonl")
        assert cls["terminus"] == "ABORTED"
        assert cls["terminal_event_type"] == "SessionAborted"
        assert cls["terminator_reason"] == "OPERATOR_ABORT"

    def test_incomplete_session(self, tmp_path: Path) -> None:
        """Missing terminal event → INCOMPLETE."""
        events = _completed_session_events()[:-1]  # drop SessionCompleted
        pkg = _write_session_package(tmp_path / "pkg", events)
        cls = comparator.classify_terminus(pkg / "events.jsonl")
        assert cls["terminus"] == "INCOMPLETE"
        assert cls["terminal_event_type"] is None
        assert cls["terminal_seq"] is None


# --------------------------------------------------------------------
# Test class 2 — schema-version extraction + enforcement (D-CONT-6b)
# --------------------------------------------------------------------


class TestSchemaVersionEnforcement:
    """D-CONT-6b — mismatched-version replays are refused, not coerced."""

    def test_schema_version_extracted(self, tmp_path: Path) -> None:
        pkg = _write_session_package(
            tmp_path / "pkg",
            _completed_session_events(schema_version=2),
        )
        assert comparator.extract_schema_version(pkg / "events.jsonl") == 2

    def test_schema_version_1_to_2_refused(self, tmp_path: Path) -> None:
        """Pre-Phase-5 (schema=1) vs post-Phase-5 (schema=2) → REPLAY-INVALID."""
        pkg_a = _write_session_package(
            tmp_path / "pkg_a", _completed_session_events(schema_version=1)
        )
        pkg_b = _write_session_package(
            tmp_path / "pkg_b", _completed_session_events(schema_version=2)
        )
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID

    def test_schema_version_2_to_2_compatible(self, tmp_path: Path) -> None:
        pkg_a = _write_session_package(
            tmp_path / "pkg_a", _completed_session_events(schema_version=2)
        )
        pkg_b = _write_session_package(
            tmp_path / "pkg_b", _completed_session_events(schema_version=2)
        )
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_IDENTICAL

    def test_no_snapshot_event_refused(self, tmp_path: Path) -> None:
        """Missing boundary snapshot → schema_version=None → REPLAY-INVALID."""
        events = [
            e for e in _completed_session_events()
            if e["event_type"] != "NodeBoundarySnapshot"
        ]
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events)
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID


# --------------------------------------------------------------------
# Test class 3 — happy-path replay identity (regression preservation)
# --------------------------------------------------------------------


class TestHappyPathReplayIdentity:
    """Step 8 Phase 6 base — identical COMPLETED sessions remain identical."""

    def test_completed_byte_equal_identical(self, tmp_path: Path) -> None:
        events = _completed_session_events()
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events)
        assert comparator.compare_session_packages(pkg_a, pkg_b) == (
            comparator.EXIT_IDENTICAL
        )

    def test_completed_events_diverge(self, tmp_path: Path) -> None:
        events_a = _completed_session_events()
        events_b = _completed_session_events()
        # Mutate one field — same terminus, same schema, but byte-different.
        events_b[2]["payload"]["scheduler_decision_fingerprint"] = "DIFFERENT"
        pkg_a = _write_session_package(tmp_path / "pkg_a", events_a)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events_b)
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_DIVERGENT


# --------------------------------------------------------------------
# Test class 4 — failure-terminating replay identity (Phase 7 brief)
# --------------------------------------------------------------------


class TestFailureSessionReplayIdentity:
    """Phase 7 item 4 — multi-session FAIL / ABORT replay byte-identity."""

    def test_failed_session_identical_across_two_packages(
        self, tmp_path: Path
    ) -> None:
        events = _failed_session_events()
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events)
        assert comparator.compare_session_packages(pkg_a, pkg_b) == (
            comparator.EXIT_IDENTICAL
        )

    def test_aborted_session_identical_across_two_packages(
        self, tmp_path: Path
    ) -> None:
        events = _aborted_session_events()
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events)
        assert comparator.compare_session_packages(pkg_a, pkg_b) == (
            comparator.EXIT_IDENTICAL
        )

    def test_failed_vs_completed_refused(self, tmp_path: Path) -> None:
        """COMPLETED vs FAILED → terminus mismatch → REPLAY-INVALID."""
        pkg_a = _write_session_package(
            tmp_path / "pkg_a", _completed_session_events()
        )
        pkg_b = _write_session_package(
            tmp_path / "pkg_b", _failed_session_events()
        )
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID

    def test_failed_vs_aborted_refused(self, tmp_path: Path) -> None:
        """FAILED vs ABORTED → terminus mismatch → REPLAY-INVALID
        (the F.11 ruling: distinct terminal states are byte-
        distinguishable, and the comparator refuses to claim
        identity across them)."""
        pkg_a = _write_session_package(
            tmp_path / "pkg_a", _failed_session_events()
        )
        pkg_b = _write_session_package(
            tmp_path / "pkg_b", _aborted_session_events()
        )
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID

    def test_failed_terminator_reason_mismatch_refused(
        self, tmp_path: Path
    ) -> None:
        """Same terminus (FAILED), different terminator_reason →
        REPLAY-INVALID. F.12 ruling: identity is across same
        (SessionState, seq, terminator_reason)."""
        events_a = _failed_session_events()
        events_b = _failed_session_events()
        events_b[-1]["payload"]["terminator_reason"] = "TIMEOUT_FAILURE"
        pkg_a = _write_session_package(tmp_path / "pkg_a", events_a)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events_b)
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID

    def test_aborted_envelope_id_mismatch_diverges(
        self, tmp_path: Path
    ) -> None:
        """Same terminator_reason (OPERATOR_ABORT) but different
        envelope_id → REPLAY-DIVERGENT (the terminus classifier
        matches, so this is a byte-level divergence, not an
        invalid classification)."""
        events_a = _aborted_session_events(envelope_id="env_aaa")
        events_b = _aborted_session_events(envelope_id="env_bbb")
        pkg_a = _write_session_package(tmp_path / "pkg_a", events_a)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events_b)
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_DIVERGENT

    def test_three_cycle_aborted_byte_identity(self, tmp_path: Path) -> None:
        """Mirror the Phase 6 Isaac proof — 3 identical ABORTED runs
        all byte-equal pairwise."""
        events = _aborted_session_events()
        pkg_1 = _write_session_package(tmp_path / "pkg_1", events)
        pkg_2 = _write_session_package(tmp_path / "pkg_2", events)
        pkg_3 = _write_session_package(tmp_path / "pkg_3", events)
        assert comparator.compare_session_packages(pkg_1, pkg_2) == (
            comparator.EXIT_IDENTICAL
        )
        assert comparator.compare_session_packages(pkg_2, pkg_3) == (
            comparator.EXIT_IDENTICAL
        )
        assert comparator.compare_session_packages(pkg_1, pkg_3) == (
            comparator.EXIT_IDENTICAL
        )


# --------------------------------------------------------------------
# Test class 5 — package validation (REPLAY-INVALID gate)
# --------------------------------------------------------------------


class TestPackageValidation:
    """Comparator refuses to claim identity / divergence when the
    packages are malformed or missing required pieces."""

    def test_missing_events_file(self, tmp_path: Path) -> None:
        pkg_a = _write_session_package(
            tmp_path / "pkg_a", _completed_session_events()
        )
        pkg_b = tmp_path / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "manifest.json").write_text("{}", encoding="utf-8")
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID

    def test_missing_manifest_file(self, tmp_path: Path) -> None:
        pkg_a = _write_session_package(
            tmp_path / "pkg_a", _completed_session_events()
        )
        pkg_b = tmp_path / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "events.jsonl").write_text("", encoding="utf-8")
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID

    def test_missing_directory(self, tmp_path: Path) -> None:
        pkg_a = _write_session_package(
            tmp_path / "pkg_a", _completed_session_events()
        )
        rc = comparator.compare_session_packages(
            pkg_a, tmp_path / "nonexistent"
        )
        assert rc == comparator.EXIT_INVALID

    def test_malformed_events_jsonl(self, tmp_path: Path) -> None:
        pkg_a = _write_session_package(
            tmp_path / "pkg_a", _completed_session_events()
        )
        pkg_b = tmp_path / "pkg_b"
        pkg_b.mkdir()
        (pkg_b / "events.jsonl").write_text(
            'this is not valid JSON', encoding="utf-8"
        )
        (pkg_b / "manifest.json").write_text("{}", encoding="utf-8")
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID

    def test_incomplete_session_refused(self, tmp_path: Path) -> None:
        """No terminal event in events.jsonl → REPLAY-INVALID."""
        events = _completed_session_events()[:-1]
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events)
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_INVALID


# --------------------------------------------------------------------
# Test class 6 — strict byte-equality (D-FAULT-11a)
# --------------------------------------------------------------------


class TestStrictByteEquality:
    """D-FAULT-11a — no tolerance, no fuzzy match, no normalized repair."""

    def test_trailing_whitespace_in_jsonl_is_divergent(
        self, tmp_path: Path
    ) -> None:
        events = _completed_session_events()
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events)
        # Inject a single trailing space into B's events.jsonl — should
        # surface as REPLAY-DIVERGENT (byte-level), not tolerated.
        events_path = pkg_b / "events.jsonl"
        existing = events_path.read_text(encoding="utf-8")
        events_path.write_text(existing + " ", encoding="utf-8")
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_DIVERGENT

    def test_payload_float_reordering_is_divergent(
        self, tmp_path: Path
    ) -> None:
        """Two identically-valued floats serialized as 0.10 vs 0.1
        produce byte-different JSONL → divergent. The comparator
        does NOT normalize float repr (D-FAULT-11a)."""
        events_a = _completed_session_events()
        events_b = _completed_session_events()
        # Write a custom B with a hand-crafted float string that differs
        # in representation.
        pkg_a = _write_session_package(tmp_path / "pkg_a", events_a)
        pkg_b = tmp_path / "pkg_b"
        pkg_b.mkdir()
        # Replace one event's payload with an explicit "0.10" string
        # (Python's json.dumps emits "0.1" by default).
        lines = []
        for e in events_b:
            line = _canonical_dumps(e)
            line = line.replace('"abc"', '"abc_DIFFERENT"', 1)
            lines.append(line)
        (pkg_b / "events.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        (pkg_b / "manifest.json").write_text(
            _canonical_dumps({
                "package_version": 1, "invariant_contract_version": 1,
                "event_count": len(events_b), "trace_hash": None,
                "runtime_hash": None, "session_identity": None,
            }), encoding="utf-8"
        )
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_DIVERGENT

    def test_manifest_byte_divergence_diverges(self, tmp_path: Path) -> None:
        events = _completed_session_events()
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events)
        # Mutate B's manifest only.
        mp = pkg_b / "manifest.json"
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        manifest["event_count"] = 9999
        mp.write_text(_canonical_dumps(manifest), encoding="utf-8")
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_DIVERGENT


# --------------------------------------------------------------------
# Test class 7 — REPLAY_INTEGRITY_FAILURE isolation (D-FAULT-11)
# --------------------------------------------------------------------


class TestReplayIntegrityIsolation:
    """The comparator never writes to either package and never injects
    a ReplayIntegrityFailure event into the trace."""

    def test_divergence_does_not_mutate_packages(
        self, tmp_path: Path
    ) -> None:
        events_a = _completed_session_events()
        events_b = _completed_session_events()
        events_b[2]["payload"]["scheduler_decision_fingerprint"] = "X"
        pkg_a = _write_session_package(tmp_path / "pkg_a", events_a)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events_b)
        events_a_before = (pkg_a / "events.jsonl").read_bytes()
        events_b_before = (pkg_b / "events.jsonl").read_bytes()
        manifest_a_before = (pkg_a / "manifest.json").read_bytes()
        manifest_b_before = (pkg_b / "manifest.json").read_bytes()
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_DIVERGENT
        # Critical: comparator MUST NOT have rewritten either package.
        assert (pkg_a / "events.jsonl").read_bytes() == events_a_before
        assert (pkg_b / "events.jsonl").read_bytes() == events_b_before
        assert (pkg_a / "manifest.json").read_bytes() == manifest_a_before
        assert (pkg_b / "manifest.json").read_bytes() == manifest_b_before

    def test_no_replay_integrity_event_appended(self, tmp_path: Path) -> None:
        """The comparator must NOT inject ReplayIntegrity events into
        either trace, even on divergence (D-FAULT-11)."""
        events = _failed_session_events()
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events)
        comparator.compare_session_packages(pkg_a, pkg_b)
        for pkg in (pkg_a, pkg_b):
            for line in (pkg / "events.jsonl").read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                env = json.loads(line)
                assert "ReplayIntegrity" not in env.get("event_type", ""), (
                    "comparator must never inject ReplayIntegrity* events"
                )


# --------------------------------------------------------------------
# Test class 8 — forensic ordering invariants
# --------------------------------------------------------------------


class TestForensicOrderingInvariants:
    """Phase 7 item 6 — the comparator should NOT mask
    out-of-order events. If a session's events are reordered, the
    comparator must surface that as divergence (not silently
    pass)."""

    def test_event_reordering_diverges(self, tmp_path: Path) -> None:
        events = _failed_session_events()
        events_reordered = list(events)
        # Swap two non-terminal events; same terminus, same schema,
        # but byte-different events.jsonl.
        events_reordered[1], events_reordered[2] = (
            events_reordered[2],
            events_reordered[1],
        )
        pkg_a = _write_session_package(tmp_path / "pkg_a", events)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events_reordered)
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        # Same terminus + reason, but events.jsonl differs at byte-level.
        assert rc == comparator.EXIT_DIVERGENT

    def test_cascade_skipped_node_order_matters(
        self, tmp_path: Path
    ) -> None:
        """D-FAULT-4 + D-SCHED-3: cascade emission is canonical-order.
        Swapping the order of two cascade-skipped node_ids must surface
        as divergent (it is a contract violation if it happens, and the
        comparator's job is to expose it)."""
        events_a = _aborted_session_events()
        events_b = _aborted_session_events()
        # Swap n1 and n2 in B's TaskCascadeSkipped events.
        # Find their indices and swap node_ids.
        i_n1 = next(i for i, e in enumerate(events_b)
                    if e.get("event_type") == "TaskCascadeSkipped"
                    and e["payload"]["node_id"] == "n1")
        i_n2 = next(i for i, e in enumerate(events_b)
                    if e.get("event_type") == "TaskCascadeSkipped"
                    and e["payload"]["node_id"] == "n2")
        events_b[i_n1]["payload"]["node_id"] = "n2"
        events_b[i_n2]["payload"]["node_id"] = "n1"
        pkg_a = _write_session_package(tmp_path / "pkg_a", events_a)
        pkg_b = _write_session_package(tmp_path / "pkg_b", events_b)
        rc = comparator.compare_session_packages(pkg_a, pkg_b)
        assert rc == comparator.EXIT_DIVERGENT


# --------------------------------------------------------------------
# Test class 9 — exit-code stability (programmatic-use contract)
# --------------------------------------------------------------------


class TestExitCodeContract:
    """Exit codes are part of the comparator's contract — CI consumers
    branch on them. Confirm they remain stable."""

    def test_exit_constants_stable(self) -> None:
        assert comparator.EXIT_IDENTICAL == 0
        assert comparator.EXIT_DIVERGENT == 1
        assert comparator.EXIT_INVALID == 2

    def test_verdict_constants_stable(self) -> None:
        assert comparator.VERDICT_IDENTICAL == "REPLAY-IDENTICAL"
        assert comparator.VERDICT_DIVERGENT == "REPLAY-DIVERGENT"
        assert comparator.VERDICT_INVALID == "REPLAY-INVALID"

    def test_terminal_event_types_canonical(self) -> None:
        assert comparator.TERMINAL_EVENT_TYPES == {
            "SessionCompleted": "COMPLETED",
            "SessionFailed":    "FAILED",
            "SessionAborted":   "ABORTED",
        }
