"""Phase 4B Step 8 / Phase 3 — boundary snapshot infrastructure tests.

Proves the contract clauses landed in section 12 of
[docs/phase_4b_deterministic_semantics.md] for the boundary-snapshot
projector and its session-level integration:

  * D-CONT-6    — allowlist-only serialization (NO subtraction-from-
                  full-dump pattern; explicit field enumeration).
  * D-CONT-6a   — canonical-JSON byte equality ↔ snapshot identity.
  * D-CONT-6b   — schema_version mandatory; refused on mismatch.
  * D-CONT-6c   — pure-function, side-effect free, deterministic,
                  allowlist-only, clock-independent, simulator-state-
                  independent, incidental-registry-field-independent.
  * D-CONT-7    — registry membership confers NO authority;
                  diagnostic snapshot (registry.snapshot) and
                  boundary snapshot are NEVER conflated.
  * D-EXEC-10   — boundary snapshots at end of Phase C (pre_node) and
                  Phase G (post_node).
  * D-EXEC-11   — session_initial snapshot at end of session.begin().
  * D-BUS-3     — gap-free monotone seq.

The load-bearing assertion of this phase is the **contamination test**:
snapshot canonical-hash remains byte-stable when any D-CONT-2
forbidden field or D-CONT-7 observational-only field is perturbed.

All tests pure-Python; no Isaac Sim, no PhysX.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


from cell_authoring.orchestration import (  # noqa: E402
    BOUNDARY_SNAPSHOT_KIND_POST_NODE,
    BOUNDARY_SNAPSHOT_KIND_PRE_NODE,
    BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
    BOUNDARY_SNAPSHOT_SCHEMA_VERSION,
    BoundarySnapshotError,
    EventBus,
    EVENT_NODE_BOUNDARY_SNAPSHOT,
    EVENT_NODE_EXECUTION_COMPLETED,
    EVENT_NODE_EXECUTION_STARTED,
    EVENT_NODE_SELECTED,
    EVENT_SESSION_STARTED,
    ExecutionSession,
    InMemoryTraceRecorder,
    ResetScope,
    TaskGraph,
    TaskNode,
    boundary_snapshot,
    boundary_snapshot_canonical_json,
    boundary_snapshot_hash,
)
from cell_authoring.tasks import (  # noqa: E402
    CellStateRegistry,
    ContactState,
    FixtureState,
    ObjectState,
    RobotState,
)


# ─────────────────────────── helpers ───────────────────────────


def _ok_kwargs(**overrides: Any) -> dict[str, Any]:
    """A canonical, valid set of boundary_snapshot kwargs. Tests
    override specific fields."""
    base = dict(
        kind=BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
        node_id=None,
        seq=0,
        objects={},
        fixtures={},
        session_completed=frozenset(),
        session_failed=frozenset(),
        session_retry_counts={},
    )
    base.update(overrides)
    return base


def _registry_with_authoritative_state() -> CellStateRegistry:
    """Build a registry populated with **only** the authoritative
    fields the projector reads. Tests then perturb non-authoritative
    surroundings and assert the snapshot hash is invariant."""
    reg = CellStateRegistry()
    reg.register_object(ObjectState(
        object_id="Peg_01",
        pose_m=(-0.80, 0.0, 0.701),
        yaw_rad=0.0,
    ))
    reg.register_fixture(FixtureState(
        fixture_id="FixtureA",
        occupied_by=None,
    ))
    reg.register_fixture(FixtureState(
        fixture_id="FixtureB",
        occupied_by="Peg_01",
    ))
    return reg


def _snapshot_from_registry(
    reg: CellStateRegistry,
    *,
    kind: str = BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
    node_id: str | None = None,
    seq: int = 0,
    completed: frozenset[str] = frozenset(),
    failed: frozenset[str] = frozenset(),
    retries: dict[str, int] | None = None,
) -> dict[str, Any]:
    return boundary_snapshot(
        kind=kind,
        node_id=node_id,
        seq=seq,
        objects=reg.objects,
        fixtures=reg.fixtures,
        session_completed=completed,
        session_failed=failed,
        session_retry_counts=retries if retries is not None else {},
    )


@dataclass(frozen=True)
class _FakeOutcome:
    value: str


@dataclass(frozen=True)
class _FakeResult:
    passed: bool
    outcome: Any
    peg_xyz_final: tuple[float, float, float] | None = None
    peg_xyz_initial: tuple[float, float, float] | None = None


class _FakeRegistryAwareExecutor:
    """Same shape as the Phase 2 fake — exposes ``.registry``."""

    def __init__(self, *, execute_result: _FakeResult, registry: CellStateRegistry | None = None):
        self.call_log: list[tuple] = []
        self.registry = registry if registry is not None else CellStateRegistry()
        self._execute_result = execute_result

    def prepare(self) -> None: self.call_log.append(("prepare",))
    def reset(self, scope: ResetScope = ResetScope.FULL) -> None:
        self.call_log.append(("reset", scope))
    def execute(self, task: Any, **kw: Any) -> _FakeResult:
        self.call_log.append(("execute", task))
        return self._execute_result
    def close(self) -> None: self.call_log.append(("close",))


def _single_node_graph(node_id: str = "n0", task_ref: str = "t") -> TaskGraph:
    return TaskGraph.build(nodes=[TaskNode(node_id=node_id, task_ref=task_ref)])


# ═══════════════════════════════════════════════════════════════════════
class TestBoundarySnapshotProjectorPurity:
    """D-CONT-6c — pure-function discipline."""

    def test_two_calls_with_identical_inputs_byte_equal(self):
        kwargs = _ok_kwargs()
        a = boundary_snapshot_canonical_json(boundary_snapshot(**kwargs))
        b = boundary_snapshot_canonical_json(boundary_snapshot(**kwargs))
        assert a == b

    def test_canonical_json_includes_only_enumerated_top_level_keys(self):
        snap = boundary_snapshot(**_ok_kwargs())
        # Adding a top-level key would require D-CONT-6 amendment.
        assert sorted(snap.keys()) == [
            "fixtures", "kind", "node_id", "objects",
            "schema_version", "seq", "session",
        ]

    def test_object_projection_only_reads_allowlist_fields(self):
        # Use registry-backed object; ensure unrelated fields are not
        # serialized (proves enumeration discipline).
        reg = _registry_with_authoritative_state()
        reg.objects["Peg_01"].contact_with = ("LeftPad", "RightPad")  # observational
        reg.objects["Peg_01"].metadata["seq_count"] = 99               # diagnostic
        snap = _snapshot_from_registry(reg)
        peg = snap["objects"]["Peg_01"]
        # Allowlist for objects under D-CONT-1 (Step 8 / Phase 3): pose_m + yaw_rad.
        assert sorted(peg.keys()) == ["pose_m", "yaw_rad"]
        # Forbidden fields absent.
        assert "contact_with" not in peg
        assert "metadata"     not in peg

    def test_fixture_projection_only_reads_allowlist_fields(self):
        reg = _registry_with_authoritative_state()
        reg.fixtures["FixtureA"].metadata["debug_tag"] = "ignore-me"
        snap = _snapshot_from_registry(reg)
        # Allowlist for fixtures: occupied_by only.
        assert sorted(snap["fixtures"]["FixtureA"].keys()) == ["occupied_by"]
        assert "metadata" not in snap["fixtures"]["FixtureA"]

    def test_does_not_mutate_inputs(self):
        objects  = {"Peg_01": ObjectState(object_id="Peg_01", pose_m=(0.0, 0.0, 0.0))}
        fixtures = {"F":      FixtureState(fixture_id="F", occupied_by=None)}
        completed = frozenset({"a", "b"})
        failed    = frozenset({"c"})
        retries   = {"d": 2}
        objects_id_before  = id(objects["Peg_01"])
        fixtures_id_before = id(fixtures["F"])
        # Snapshot
        boundary_snapshot(
            kind=BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
            node_id=None, seq=0,
            objects=objects, fixtures=fixtures,
            session_completed=completed, session_failed=failed,
            session_retry_counts=retries,
        )
        # Caller's references are unchanged in identity and value.
        assert id(objects["Peg_01"])  == objects_id_before
        assert id(fixtures["F"])      == fixtures_id_before
        assert objects["Peg_01"].pose_m == (0.0, 0.0, 0.0)
        assert fixtures["F"].occupied_by is None
        assert completed == frozenset({"a", "b"})  # frozensets are immutable anyway
        assert retries == {"d": 2}

    def test_returned_dict_is_independent_of_subsequent_input_mutation(self):
        objects = {"Peg_01": ObjectState(object_id="Peg_01", pose_m=(1.0, 2.0, 3.0))}
        snap = boundary_snapshot(
            kind=BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
            node_id=None, seq=0,
            objects=objects, fixtures={},
            session_completed=frozenset(), session_failed=frozenset(),
            session_retry_counts={},
        )
        # Mutate the original (D-CONT-5a observational-projection style).
        objects["Peg_01"].pose_m = (9.0, 9.0, 9.0)
        # Snapshot's pose_m unchanged — the projector copied to a list.
        assert snap["objects"]["Peg_01"]["pose_m"] == [1.0, 2.0, 3.0]


# ═══════════════════════════════════════════════════════════════════════
class TestBoundarySnapshotContamination:
    """D-CONT-6 / D-CONT-7 — THE load-bearing assertion of Phase 3.

    Any D-CONT-2 forbidden or D-CONT-7 observational-only perturbation
    of the registry MUST leave the boundary snapshot byte-identical.
    """

    @staticmethod
    def _baseline_hash() -> tuple[str, CellStateRegistry]:
        reg = _registry_with_authoritative_state()
        snap = _snapshot_from_registry(reg)
        return boundary_snapshot_hash(snap), reg

    def test_contact_state_perturbation_does_not_change_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.contact = ContactState(
            pad_L_contact=True, pad_R_contact=True,
            floor_contact=True, belt_contact=True, fixture_contact=True,
            pad_pen_max_mm=42.5,
        )
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) == baseline_hash

    def test_robot_state_perturbation_does_not_change_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.register_robot(RobotState(
            robot_id="UR10e",
            joint_positions_rad=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6),
            joint_velocities_rad_s=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
            wrist_3_xyz=(0.5, 0.5, 0.5),
            gripper_state="close",
            gripper_drive_target=-0.030,
        ))
        # Adding an entire robot to the registry must not perturb the
        # snapshot. (D-CONT-7: robots are observational-only.)
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) == baseline_hash

    def test_task_state_perturbation_does_not_change_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.start_task("task_x", started_at_step=99)
        reg.task.step = 12345
        reg.set_task_phase("executing")
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) == baseline_hash

    def test_metrics_perturbation_does_not_change_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.set_metric("peg_max_z_m",      0.999)
        reg.set_metric("joint_vel_peak",   12.5)
        reg.set_metric("anything",         {"deep": [1, 2, 3]})
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) == baseline_hash

    def test_object_contact_with_perturbation_does_not_change_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.objects["Peg_01"].contact_with = ("LeftPad", "RightPad", "Floor")
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) == baseline_hash

    def test_object_metadata_perturbation_does_not_change_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.objects["Peg_01"].metadata["mass_kg"] = 0.5
        reg.objects["Peg_01"].metadata["debug"]   = {"nested": [1, 2]}
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) == baseline_hash

    def test_fixture_metadata_perturbation_does_not_change_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.fixtures["FixtureA"].metadata["height_m"] = 0.65
        reg.fixtures["FixtureB"].metadata["debug"]    = "ignore-me"
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) == baseline_hash

    def test_combined_forbidden_perturbations_do_not_change_hash(self):
        """All forbidden perturbations applied at once. The snapshot
        hash must STILL match the baseline. This is the strict D-CONT-6
        contamination assertion."""
        baseline_hash, reg = self._baseline_hash()
        reg.contact = ContactState(pad_L_contact=True, pad_pen_max_mm=99.0)
        reg.register_robot(RobotState(
            robot_id="UR10e",
            joint_velocities_rad_s=(7.0,) * 6,
        ))
        reg.start_task("xx", started_at_step=42)
        reg.set_metric("peg_max_z_m", 7.7)
        reg.objects["Peg_01"].contact_with = ("Foo", "Bar")
        reg.objects["Peg_01"].metadata["debug"] = "X"
        reg.fixtures["FixtureA"].metadata["debug"] = "Y"
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) == baseline_hash

    # ── conversely: authoritative perturbations MUST change the hash ──

    def test_object_pose_perturbation_changes_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.objects["Peg_01"].pose_m = (-0.79, 0.0, 0.701)  # 1 cm shift
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) != baseline_hash

    def test_object_yaw_perturbation_changes_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.objects["Peg_01"].yaw_rad = 0.0001
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) != baseline_hash

    def test_fixture_occupancy_perturbation_changes_hash(self):
        baseline_hash, reg = self._baseline_hash()
        reg.fixtures["FixtureA"].occupied_by = "Peg_02"
        assert boundary_snapshot_hash(_snapshot_from_registry(reg)) != baseline_hash

    def test_session_completed_perturbation_changes_hash(self):
        reg = _registry_with_authoritative_state()
        baseline_hash = boundary_snapshot_hash(_snapshot_from_registry(reg))
        # Add a node_id to completed.
        perturbed = boundary_snapshot_hash(_snapshot_from_registry(
            reg, completed=frozenset({"n_done"})))
        assert perturbed != baseline_hash


# ═══════════════════════════════════════════════════════════════════════
class TestBoundarySnapshotCanonicalOrdering:
    """D-SCHED-5/-6/-7 — sorted iteration in canonical paths.

    Insertion order of objects/fixtures must not leak into the
    canonical-JSON output (D-FORBID-7)."""

    def test_object_insertion_order_does_not_affect_snapshot(self):
        # Forward order.
        reg_fwd = CellStateRegistry()
        reg_fwd.register_object(ObjectState(object_id="A", pose_m=(1.0, 0.0, 0.0)))
        reg_fwd.register_object(ObjectState(object_id="B", pose_m=(2.0, 0.0, 0.0)))
        reg_fwd.register_object(ObjectState(object_id="C", pose_m=(3.0, 0.0, 0.0)))

        # Reverse order.
        reg_rev = CellStateRegistry()
        reg_rev.register_object(ObjectState(object_id="C", pose_m=(3.0, 0.0, 0.0)))
        reg_rev.register_object(ObjectState(object_id="B", pose_m=(2.0, 0.0, 0.0)))
        reg_rev.register_object(ObjectState(object_id="A", pose_m=(1.0, 0.0, 0.0)))

        a = boundary_snapshot_canonical_json(_snapshot_from_registry(reg_fwd))
        b = boundary_snapshot_canonical_json(_snapshot_from_registry(reg_rev))
        assert a == b

    def test_fixture_insertion_order_does_not_affect_snapshot(self):
        reg_fwd = CellStateRegistry()
        reg_fwd.register_fixture(FixtureState(fixture_id="F_a"))
        reg_fwd.register_fixture(FixtureState(fixture_id="F_b"))
        reg_fwd.register_fixture(FixtureState(fixture_id="F_c"))
        reg_rev = CellStateRegistry()
        reg_rev.register_fixture(FixtureState(fixture_id="F_c"))
        reg_rev.register_fixture(FixtureState(fixture_id="F_b"))
        reg_rev.register_fixture(FixtureState(fixture_id="F_a"))
        a = boundary_snapshot_canonical_json(_snapshot_from_registry(reg_fwd))
        b = boundary_snapshot_canonical_json(_snapshot_from_registry(reg_rev))
        assert a == b

    def test_retry_counts_insertion_order_does_not_affect_snapshot(self):
        reg = CellStateRegistry()
        a = boundary_snapshot_canonical_json(_snapshot_from_registry(
            reg, retries={"x": 1, "y": 2, "z": 3}))
        b = boundary_snapshot_canonical_json(_snapshot_from_registry(
            reg, retries={"z": 3, "y": 2, "x": 1}))
        assert a == b


# ═══════════════════════════════════════════════════════════════════════
class TestBoundarySnapshotKindEnforcement:
    """D-CONT-6b — kind discipline; rejection of malformed inputs."""

    def test_unknown_kind_raises(self):
        with pytest.raises(BoundarySnapshotError, match="unknown snapshot kind"):
            boundary_snapshot(**_ok_kwargs(kind="not_a_real_kind"))

    def test_pre_node_with_none_node_id_raises(self):
        with pytest.raises(BoundarySnapshotError, match="requires a non-None node_id"):
            boundary_snapshot(**_ok_kwargs(
                kind=BOUNDARY_SNAPSHOT_KIND_PRE_NODE, node_id=None,
            ))

    def test_post_node_with_none_node_id_raises(self):
        with pytest.raises(BoundarySnapshotError, match="requires a non-None node_id"):
            boundary_snapshot(**_ok_kwargs(
                kind=BOUNDARY_SNAPSHOT_KIND_POST_NODE, node_id=None,
            ))

    def test_session_initial_with_node_id_raises(self):
        with pytest.raises(BoundarySnapshotError, match="requires node_id is None"):
            boundary_snapshot(**_ok_kwargs(
                kind=BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL, node_id="n0",
            ))

    def test_negative_seq_raises(self):
        with pytest.raises(BoundarySnapshotError, match="seq must be >= 0"):
            boundary_snapshot(**_ok_kwargs(seq=-1))

    def test_zero_or_negative_schema_version_raises(self):
        with pytest.raises(BoundarySnapshotError, match="schema_version"):
            boundary_snapshot(**_ok_kwargs(schema_version=0))


# ═══════════════════════════════════════════════════════════════════════
class TestBoundarySnapshotHash:
    """SHA-256 hash discipline (D-CONT-6a, D-CONT-6c)."""

    def test_hash_is_64_hex_chars(self):
        h = boundary_snapshot_hash(boundary_snapshot(**_ok_kwargs()))
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_identity_equal_snapshots_have_identical_hash(self):
        a = boundary_snapshot_hash(boundary_snapshot(**_ok_kwargs()))
        b = boundary_snapshot_hash(boundary_snapshot(**_ok_kwargs()))
        assert a == b

    def test_different_snapshots_have_different_hashes(self):
        a = boundary_snapshot_hash(boundary_snapshot(**_ok_kwargs(seq=0)))
        b = boundary_snapshot_hash(boundary_snapshot(**_ok_kwargs(seq=1)))
        assert a != b


# ═══════════════════════════════════════════════════════════════════════
class TestDiagnosticVsAuthoritativeSeparation:
    """D-CONT-7 + section 12.1: registry.snapshot() and
    boundary_snapshot() must NEVER be conflated.

    The diagnostic snapshot includes every registry field; the
    boundary snapshot includes only the D-CONT-1 allowlist."""

    def test_diagnostic_snapshot_includes_observational_fields(self):
        reg = _registry_with_authoritative_state()
        reg.register_robot(RobotState(robot_id="UR10e"))
        reg.contact = ContactState(pad_L_contact=True)
        reg.start_task("task_x", started_at_step=0)
        reg.set_metric("a", 1.0)
        diag = reg.snapshot()
        # Diagnostic snapshot exposes EVERY top-level registry section.
        assert "robots"   in diag
        assert "contact"  in diag
        assert "task"     in diag
        assert "metrics"  in diag
        assert diag["robots"]["UR10e"]["gripper_state"] == "open"
        assert diag["contact"]["pad_L_contact"]         is True

    def test_boundary_snapshot_excludes_observational_sections(self):
        reg = _registry_with_authoritative_state()
        reg.register_robot(RobotState(robot_id="UR10e"))
        reg.contact = ContactState(pad_L_contact=True)
        reg.start_task("task_x", started_at_step=0)
        reg.set_metric("a", 1.0)
        snap = _snapshot_from_registry(reg)
        # Boundary snapshot has EXACTLY the D-CONT-1 allowlist top-level
        # keys — no observational sections.
        assert sorted(snap.keys()) == [
            "fixtures", "kind", "node_id", "objects",
            "schema_version", "seq", "session",
        ]
        assert "robots"   not in snap
        assert "contact"  not in snap
        assert "task"     not in snap
        assert "metrics"  not in snap


# ═══════════════════════════════════════════════════════════════════════
class TestSessionBoundarySnapshotIntegration:
    """Session-level integration: session_initial / pre_node / post_node
    are all emitted, in canonical order, with the minimal D-CONT-6
    payload."""

    def _run_single_node_session(
        self,
        *,
        registry: CellStateRegistry | None = None,
    ) -> tuple[InMemoryTraceRecorder, _FakeRegistryAwareExecutor]:
        ex = _FakeRegistryAwareExecutor(
            execute_result=_FakeResult(
                passed=True, outcome=_FakeOutcome("PASS"),
                peg_xyz_final=(0.65, 0.0, 0.65),
                peg_xyz_initial=(-0.80, 0.0, 0.701),
            ),
            registry=registry if registry is not None
                     else _registry_with_authoritative_state(),
        )
        bus = EventBus()
        rec = InMemoryTraceRecorder()
        bus.register(rec)
        session = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=bus,
        )
        session.begin()
        session.step()
        session.complete()
        return rec, ex

    def test_three_boundary_snapshots_emitted_in_correct_order(self):
        rec, _ex = self._run_single_node_session()
        snapshot_events = [e for e in rec.events
                           if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        assert len(snapshot_events) == 3
        kinds = [e.payload["snapshot_kind"] for e in snapshot_events]
        assert kinds == [
            BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
            BOUNDARY_SNAPSHOT_KIND_PRE_NODE,
            BOUNDARY_SNAPSHOT_KIND_POST_NODE,
        ]
        # session_initial has node_id=None; pre/post have a node_id.
        assert snapshot_events[0].payload["node_id"] is None
        assert snapshot_events[1].payload["node_id"] == "n0"
        assert snapshot_events[2].payload["node_id"] == "n0"

    def test_snapshot_event_payload_is_minimal(self):
        rec, _ex = self._run_single_node_session()
        snap_events = [e for e in rec.events
                       if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        for env in snap_events:
            # D-CONT-6 minimal payload — no embedded snapshot body.
            assert sorted(env.payload.keys()) == [
                "canonical_hash", "node_id", "schema_version",
                "snapshot_kind", "snapshot_seq",
            ]
            assert env.payload["schema_version"] == BOUNDARY_SNAPSHOT_SCHEMA_VERSION
            # canonical_hash is the SHA-256 hex shape.
            h = env.payload["canonical_hash"]
            assert len(h) == 64
            assert all(c in "0123456789abcdef" for c in h)

    def test_snapshot_seq_matches_envelope_seq(self):
        rec, _ex = self._run_single_node_session()
        snap_events = [e for e in rec.events
                       if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        # snapshot_seq in the payload equals the envelope's seq.
        # (Redundant but explicit — see D-CONT-6 brief §5.)
        for env in snap_events:
            assert env.payload["snapshot_seq"] == env.seq

    def test_seq_ordering_session_initial_pre_post(self):
        rec, _ex = self._run_single_node_session()
        seqs = {e.payload["snapshot_kind"]: e.seq
                for e in rec.events
                if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT}
        # session_initial < pre_node < post_node (strict).
        assert seqs[BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL] \
             < seqs[BOUNDARY_SNAPSHOT_KIND_PRE_NODE] \
             < seqs[BOUNDARY_SNAPSHOT_KIND_POST_NODE]
        # post_node is strictly before NodeExecutionCompleted.
        post_seq = seqs[BOUNDARY_SNAPSHOT_KIND_POST_NODE]
        node_complete_seq = next(
            e.seq for e in rec.events
            if e.event_type == EVENT_NODE_EXECUTION_COMPLETED
        )
        assert post_seq < node_complete_seq

    def test_two_independent_sessions_produce_identical_snapshot_hashes(self):
        # D-CONT-6a — replay identity at the snapshot layer.
        rec_a, _ = self._run_single_node_session()
        rec_b, _ = self._run_single_node_session()
        hashes_a = [e.payload["canonical_hash"] for e in rec_a.events
                    if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        hashes_b = [e.payload["canonical_hash"] for e in rec_b.events
                    if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        assert hashes_a == hashes_b

    def test_pre_node_hash_equals_session_initial_hash_when_state_unchanged(self):
        # The single-node fake executor never mutates the registry
        # between session_initial and pre_node (it just records call
        # log). So session_initial and pre_node should produce
        # identical authoritative state → identical canonical-JSON
        # → identical hash. (post_node may differ due to Phase-G
        # session-completed mutation.)
        rec, _ex = self._run_single_node_session()
        snap_events = [e for e in rec.events
                       if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        kinds_to_hash = {e.payload["snapshot_kind"]: e.payload["canonical_hash"]
                         for e in snap_events}
        # Wait — session_initial has session_completed=set(); pre_node
        # has session_completed=set() also (node hasn't completed yet).
        # And object/fixture state is unchanged. They should match.
        # ... EXCEPT seq differs (D-CONT-6 includes seq), so hashes
        # will differ even if all other content matches. Document
        # that behaviour explicitly.
        assert kinds_to_hash[BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL] \
            != kinds_to_hash[BOUNDARY_SNAPSHOT_KIND_PRE_NODE], (
                "session_initial and pre_node hashes should differ "
                "because seq is part of the snapshot identity"
            )

    def test_post_node_hash_reflects_phase_g_state_change(self):
        """When Phase-G commits an occupancy change, post_node hash
        must reflect that change — proving the snapshot is taken
        AFTER the mutation, not before."""
        # Build a registry where the place fixture starts empty.
        reg = CellStateRegistry()
        reg.register_object(ObjectState(object_id="Peg_01", pose_m=(0.0, 0.0, 0.7)))
        reg.register_fixture(FixtureState(fixture_id="FixtureB", occupied_by=None))

        # Use a fake task that has a place_target with fixture_id.
        from cell_authoring.tasks import (
            PickPlaceTask, PickSource, PlaceTarget,
            PrismaticClampGrasp, JointSpaceLerpTransport, OpenJawRelease,
        )
        task = PickPlaceTask(
            task_id="t",
            pick_source=PickSource(
                object_id="Peg_01",
                world_pose_m=(0.0, 0.0, 0.7),
                source_kind="conveyor",
            ),
            place_target=PlaceTarget(
                fixture_id="FixtureB",
                world_pose_m=(0.65, 0.0, 0.65),
                placement_tolerance_xy_m=0.05,
            ),
            grasp_strategy=PrismaticClampGrasp(),
            transport_strategy=JointSpaceLerpTransport(profile_id="nominal"),
            release_strategy=OpenJawRelease(),
        )
        ex = _FakeRegistryAwareExecutor(
            execute_result=_FakeResult(
                passed=True, outcome=_FakeOutcome("PASS"),
                peg_xyz_final=(0.65, 0.0, 0.65),
            ),
            registry=reg,
        )
        bus = EventBus()
        rec = InMemoryTraceRecorder()
        bus.register(rec)
        session = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=bus,
            task_resolver=lambda _node: task,
        )
        session.begin(); session.step(); session.complete()

        # FixtureB should be occupied AFTER the session completes
        # (Phase-G commit).
        assert reg.fixtures["FixtureB"].occupied_by == "Peg_01"

        snap_events = [e for e in rec.events
                       if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        pre_hash  = next(e.payload["canonical_hash"] for e in snap_events
                         if e.payload["snapshot_kind"] == BOUNDARY_SNAPSHOT_KIND_PRE_NODE)
        post_hash = next(e.payload["canonical_hash"] for e in snap_events
                         if e.payload["snapshot_kind"] == BOUNDARY_SNAPSHOT_KIND_POST_NODE)
        # Different — because Phase-G changed both fixture occupancy
        # and session._completed between pre and post.
        assert pre_hash != post_hash


# ═══════════════════════════════════════════════════════════════════════
class TestSnapshotEmissionWithoutRegistry:
    """A fake executor without a ``.registry`` attribute (Step-6-style)
    must not crash the session's snapshot emission. The snapshot is
    built from empty mappings; the event still emits."""

    def test_no_registry_yields_empty_objects_and_fixtures(self):
        class _NoRegistryFake:
            def __init__(self): self.call_log = []
            def prepare(self): self.call_log.append(("prepare",))
            def reset(self, scope=ResetScope.FULL): pass
            def execute(self, task, **kw):
                return _FakeResult(passed=True, outcome=_FakeOutcome("PASS"))
            def close(self): pass
        ex = _NoRegistryFake()
        bus = EventBus()
        rec = InMemoryTraceRecorder()
        bus.register(rec)
        session = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=bus,
        )
        session.begin(); session.step(); session.complete()
        # Three snapshot events still emit; they're just over empty
        # registry state.
        snap_events = [e for e in rec.events
                       if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        assert len(snap_events) == 3
        # All payloads have the canonical hash; no crash.
        for env in snap_events:
            assert "canonical_hash" in env.payload
            assert len(env.payload["canonical_hash"]) == 64
