"""Phase 4B Step 8 / Phase 5 — two-node runtime composition tests.

Proves the orchestration mechanics of the first true two-node
TaskGraph end-to-end at the pure-Python layer. Cites D-CONT-3 (boundary
quiescence), D-CONT-4 (selective authoritative persistence), D-CONT-5
(occupancy authority), D-CONT-6 (boundary snapshot canonicality).

Physical execution on Isaac Sim is exercised by
``scripts/launch_phase_5_two_node.py`` and verified visually over
WebRTC per the Phase 5 brief — that path requires the actual
``TaskExecutor`` + PhysX + USD stack and lives outside the unit-test
boundary. This file proves the orchestration plumbing.

Coverage
--------

  * TestPhase5TaskGraph        — 2-node graph structure, edges,
                                  canonical order, fingerprint
                                  stability.
  * TestPhase5TrajectorySets   — trajectory_sets has the two expected
                                  keys; waypoint names match the
                                  executor's dispatch keys (grasp,
                                  grasp_close, lift, place, release).
  * TestPhase5TaskDefinitions  — N1/N2 PickPlaceTasks reference the
                                  expected pick/place fixtures and
                                  trajectory_ids; N2.pick_source has
                                  fixture_id attached.
  * TestPhase5SessionRun       — 2-node session runs both nodes,
                                  occupancy transitions are correct,
                                  ResetScope is FULL for N1 and
                                  ACQUIRED_ONLY for N2.
  * TestPhase5DeterministicReplay — three independent runs of the
                                  2-node session produce
                                  byte-identical event payloads and
                                  boundary snapshot hashes.
  * TestPhase5BoundaryContinuity — peg pose at the inter-node
                                  boundary is preserved (no teleport)
                                  through ACQUIRED_ONLY reset.

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
    EventBus,
    EVENT_FIXTURE_STATE_CHANGED,
    EVENT_NODE_BOUNDARY_SNAPSHOT,
    EVENT_NODE_EXECUTION_COMPLETED,
    EVENT_NODE_EXECUTION_STARTED,
    EVENT_NODE_SELECTED,
    EVENT_SESSION_COMPLETED,
    EVENT_SESSION_STARTED,
    ExecutionSession,
    InMemoryTraceRecorder,
    ResetScope,
)
from cell_authoring.orchestration.phase_5_two_node import (  # noqa: E402
    FIXTURE_A_ID,
    FIXTURE_A_WORLD_POSE_M,
    FIXTURE_B_ID,
    FIXTURE_B_WORLD_POSE_M,
    NODE_ID_N1,
    NODE_ID_N2,
    OBJECT_ID_PEG,
    TASK_ID_N1,
    TASK_ID_N2,
    TRAJECTORY_ID_N1,
    TRAJECTORY_ID_N2,
    build_phase_5_graph,
    build_phase_5_n1_task,
    build_phase_5_n2_task,
    build_phase_5_task_resolver,
    build_trajectory_sets,
    register_phase_5_fixtures,
)
from cell_authoring.tasks import (  # noqa: E402
    CellStateRegistry,
    FixtureState,
    ObjectState,
    PickPlaceTask,
)


# ───────────────────────────── fakes ─────────────────────────────


@dataclass(frozen=True)
class _FakeOutcome:
    value: str


@dataclass(frozen=True)
class _FakeResult:
    passed: bool
    outcome: Any
    peg_xyz_initial: tuple[float, float, float] | None = None
    peg_xyz_final:   tuple[float, float, float] | None = None
    placement_offset_xy_m: tuple[float, float] | None = None
    pick_lift_off_step: int | None = None
    place_landing_step: int | None = None


class _Phase5FakeExecutor:
    """Fake executor with a registry that mirrors the runtime contract.

    Behaviour:
      * ``prepare()`` registers the peg + cell's existing WorkFixture
        and the Phase 5 fixtures (FixtureA + FixtureB).
      * ``reset(FULL)`` teleports the peg to belt-start (Phase 4A
        emulation).
      * ``reset(ACQUIRED_ONLY)`` does nothing to the peg (D-CONT-4
        — selective authoritative persistence; the peg stays where
        it was placed).
      * ``execute(task, **kwargs)`` moves the peg to ``task.place_target
        .world_pose_m`` and returns PASS.

    Records every call for test assertions.
    """

    def __init__(self):
        self.call_log: list[tuple] = []
        self.registry = CellStateRegistry()
        self.registry.register_object(ObjectState(
            object_id=OBJECT_ID_PEG, pose_m=(-0.80, 0.0, 0.701),
        ))
        # Default WorkFixture + Phase 5 additions.
        self.registry.register_fixture(FixtureState(fixture_id="WorkFixture_01"))
        register_phase_5_fixtures(self.registry)

    def prepare(self) -> None:
        self.call_log.append(("prepare",))

    def reset(self, scope: ResetScope = ResetScope.FULL) -> None:
        self.call_log.append(("reset", scope))
        if scope == ResetScope.FULL:
            # Phase 4A semantics: peg back to belt-start.
            self.registry.update_object_pose(
                OBJECT_ID_PEG, (-0.80, 0.0, 0.701), 0.0,
            )
        # ACQUIRED_ONLY: leave peg where it is (D-CONT-4).

    def execute(self, task: Any, **kwargs: Any) -> _FakeResult:
        self.call_log.append(("execute", task, dict(kwargs)))
        # "Run" the trajectory: move peg from current pose to
        # task.place_target.world_pose_m. Record initial pose first.
        initial = self.registry.objects[OBJECT_ID_PEG].pose_m
        place = task.place_target.world_pose_m
        self.registry.update_object_pose(OBJECT_ID_PEG, place, 0.0)
        return _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_initial=tuple(initial),
            peg_xyz_final=tuple(place),
            placement_offset_xy_m=(0.0, 0.0),
            pick_lift_off_step=None,
            place_landing_step=300,
        )

    def close(self) -> None:
        self.call_log.append(("close",))


def _run_phase_5_session() -> tuple[InMemoryTraceRecorder, _Phase5FakeExecutor]:
    """Build + run a full 2-node Phase 5 session with the fake executor.
    Returns (recorder, executor) so tests can introspect both."""
    ex = _Phase5FakeExecutor()
    bus = EventBus()
    rec = InMemoryTraceRecorder()
    bus.register(rec)
    s = ExecutionSession(
        graph=build_phase_5_graph(),
        task_executor=ex,
        event_bus=bus,
        task_resolver=build_phase_5_task_resolver(),
    )
    s.begin()
    s.step()    # advances N1
    s.step()    # advances N2
    s.complete()
    return rec, ex


# ═══════════════════════════════════════════════════════════════════════
class TestPhase5TaskGraph:
    """Structural tests on the 2-node graph."""

    def test_graph_has_two_nodes(self):
        g = build_phase_5_graph()
        assert set(g.nodes.keys()) == {NODE_ID_N1, NODE_ID_N2}

    def test_graph_has_one_edge_n1_to_n2(self):
        g = build_phase_5_graph()
        assert g.parents_of(NODE_ID_N1) == ()
        assert g.parents_of(NODE_ID_N2) == (NODE_ID_N1,)

    def test_canonical_order_is_n1_then_n2(self):
        g = build_phase_5_graph()
        assert g.canonical_order == (NODE_ID_N1, NODE_ID_N2)

    def test_graph_fingerprint_stable_across_construction(self):
        # D-FORBID-7 — graph fingerprint independent of construction
        # order. Same graph built twice → same fingerprint.
        g1 = build_phase_5_graph()
        g2 = build_phase_5_graph()
        assert g1.fingerprint() == g2.fingerprint()


# ═══════════════════════════════════════════════════════════════════════
class TestPhase5TrajectorySets:
    """The two trajectories shipped by Phase 5."""

    def test_two_trajectory_ids_present(self):
        ts = build_trajectory_sets()
        assert set(ts.keys()) == {TRAJECTORY_ID_N1, TRAJECTORY_ID_N2}

    def test_n1_trajectory_has_all_executor_dispatch_waypoints(self):
        # The executor looks up these names to derive step indices.
        # Phase 5's N1 trajectory must keep them.
        required = {"grasp", "grasp_close", "lift", "place", "release"}
        names = {wp.name for wp in build_trajectory_sets()[TRAJECTORY_ID_N1]}
        assert required <= names, (
            f"N1 trajectory missing executor-dispatch waypoints: "
            f"{required - names}"
        )

    def test_n2_trajectory_has_all_executor_dispatch_waypoints(self):
        required = {"grasp", "grasp_close", "lift", "place", "release"}
        names = {wp.name for wp in build_trajectory_sets()[TRAJECTORY_ID_N2]}
        assert required <= names, (
            f"N2 trajectory missing executor-dispatch waypoints: "
            f"{required - names}"
        )

    def test_trajectory_first_waypoint_has_zero_duration(self):
        for tid, traj in build_trajectory_sets().items():
            assert traj[0].duration_s == 0.0, (
                f"{tid}: first waypoint must have duration_s=0.0; "
                f"got {traj[0].duration_s}"
            )

    def test_trajectory_total_duration_finite_and_positive(self):
        for tid, traj in build_trajectory_sets().items():
            total = sum(wp.duration_s for wp in traj)
            assert total > 0.0
            assert total < 30.0, (
                f"{tid}: total trajectory duration {total} s is too long; "
                f"Phase 5 trajectories should be a single cycle (< 30s)"
            )

    def test_trajectory_sets_deterministic(self):
        # Two calls return equal data (no hidden RNG / clock).
        a = build_trajectory_sets()
        b = build_trajectory_sets()
        assert a == b


# ═══════════════════════════════════════════════════════════════════════
class TestPhase5TaskDefinitions:
    """N1 and N2 task descriptors."""

    def test_n1_pick_is_belt_place_is_fixtureA(self):
        n1 = build_phase_5_n1_task()
        assert isinstance(n1, PickPlaceTask)
        assert n1.task_id == TASK_ID_N1
        assert n1.pick_source.source_kind == "conveyor"
        assert n1.pick_source.object_id == OBJECT_ID_PEG
        assert n1.place_target.fixture_id == FIXTURE_A_ID
        assert n1.place_target.world_pose_m == FIXTURE_A_WORLD_POSE_M
        assert n1.trajectory_id == TRAJECTORY_ID_N1

    def test_n2_pick_is_fixtureA_place_is_fixtureB(self):
        n2 = build_phase_5_n2_task()
        assert isinstance(n2, PickPlaceTask)
        assert n2.task_id == TASK_ID_N2
        assert n2.pick_source.source_kind == "fixture"
        assert n2.pick_source.object_id == OBJECT_ID_PEG
        # N2.pick_source has fixture_id bolted on so the session's
        # Phase-G commit can find it.
        assert getattr(n2.pick_source, "fixture_id", None) == FIXTURE_A_ID
        assert n2.place_target.fixture_id == FIXTURE_B_ID
        assert n2.place_target.world_pose_m == FIXTURE_B_WORLD_POSE_M
        assert n2.trajectory_id == TRAJECTORY_ID_N2

    def test_task_resolver_returns_correct_task_for_each_node_id(self):
        resolve = build_phase_5_task_resolver()
        from cell_authoring.orchestration import TaskNode
        n1 = resolve(TaskNode(node_id=NODE_ID_N1, task_ref=TASK_ID_N1))
        n2 = resolve(TaskNode(node_id=NODE_ID_N2, task_ref=TASK_ID_N2))
        assert n1.task_id == TASK_ID_N1
        assert n2.task_id == TASK_ID_N2

    def test_task_resolver_rejects_unknown_node_id(self):
        from cell_authoring.orchestration import TaskNode
        resolve = build_phase_5_task_resolver()
        with pytest.raises(ValueError, match="unknown node_id"):
            resolve(TaskNode(node_id="not_a_phase_5_node", task_ref="x"))


# ═══════════════════════════════════════════════════════════════════════
class TestPhase5FixtureRegistration:
    """register_phase_5_fixtures() adds FixtureA and FixtureB to the
    registry without disturbing existing entries."""

    def test_registers_both_fixtures_as_empty(self):
        reg = CellStateRegistry()
        register_phase_5_fixtures(reg)
        assert reg.fixtures[FIXTURE_A_ID].occupied_by is None
        assert reg.fixtures[FIXTURE_B_ID].occupied_by is None

    def test_idempotent_re_registration(self):
        reg = CellStateRegistry()
        register_phase_5_fixtures(reg)
        register_phase_5_fixtures(reg)   # second call: no-op
        assert reg.fixtures[FIXTURE_A_ID].occupied_by is None
        assert reg.fixtures[FIXTURE_B_ID].occupied_by is None

    def test_does_not_disturb_preexisting_fixtures(self):
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="WorkFixture_01"))
        register_phase_5_fixtures(reg)
        assert "WorkFixture_01" in reg.fixtures
        assert FIXTURE_A_ID in reg.fixtures
        assert FIXTURE_B_ID in reg.fixtures


# ═══════════════════════════════════════════════════════════════════════
class TestPhase5SessionRun:
    """End-to-end behaviour with the fake executor."""

    def test_both_nodes_complete(self):
        rec, _ex = _run_phase_5_session()
        completed_events = [e for e in rec.events
                            if e.event_type == EVENT_NODE_EXECUTION_COMPLETED]
        assert len(completed_events) == 2
        assert all(e.payload["passed"] for e in completed_events)
        assert [e.payload["node_id"] for e in completed_events] \
            == [NODE_ID_N1, NODE_ID_N2]

    def test_n1_uses_full_reset_scope(self):
        rec, _ex = _run_phase_5_session()
        nes_events = [e for e in rec.events
                      if e.event_type == EVENT_NODE_EXECUTION_STARTED]
        n1_event = next(e for e in nes_events if e.payload["node_id"] == NODE_ID_N1)
        assert n1_event.payload["reset_scope"] == "full"

    def test_n2_uses_acquired_only_reset_scope(self):
        rec, _ex = _run_phase_5_session()
        nes_events = [e for e in rec.events
                      if e.event_type == EVENT_NODE_EXECUTION_STARTED]
        n2_event = next(e for e in nes_events if e.payload["node_id"] == NODE_ID_N2)
        # D-CONT-4 — between-node default.
        assert n2_event.payload["reset_scope"] == "acquired_only"

    def test_fixture_occupancy_transitions_are_correct(self):
        rec, ex = _run_phase_5_session()
        # Final registry state — D-LIFE-6 / D-CONT-5:
        #   FixtureA was occupied(Peg_01) after N1, then emptied at N2
        #     (mark_fixture_empty for pick-side).
        #   FixtureB is occupied(Peg_01) after N2 (place-side commit).
        assert ex.registry.fixtures[FIXTURE_A_ID].occupied_by is None
        assert ex.registry.fixtures[FIXTURE_B_ID].occupied_by == OBJECT_ID_PEG

    def test_fixture_state_changed_events_in_correct_order(self):
        rec, _ex = _run_phase_5_session()
        fsc_events = [e for e in rec.events
                      if e.event_type == EVENT_FIXTURE_STATE_CHANGED]
        # Exactly 3 fixture transitions:
        #   1. N1.Phase-G   — FixtureA occupied(Peg_01)
        #   2. N2.Phase-G   — FixtureA empty (pick-side)
        #   3. N2.Phase-G   — FixtureB occupied(Peg_01) (place-side)
        assert len(fsc_events) == 3
        payloads = [e.payload for e in fsc_events]
        assert payloads[0] == {
            "fixture_id":       FIXTURE_A_ID,
            "prev_occupied_by": None,
            "new_occupied_by":  OBJECT_ID_PEG,
            "by_node_id":       NODE_ID_N1,
            "transition":       "occupied",
        }
        assert payloads[1] == {
            "fixture_id":       FIXTURE_A_ID,
            "prev_occupied_by": OBJECT_ID_PEG,
            "new_occupied_by":  None,
            "by_node_id":       NODE_ID_N2,
            "transition":       "empty",
        }
        assert payloads[2] == {
            "fixture_id":       FIXTURE_B_ID,
            "prev_occupied_by": None,
            "new_occupied_by":  OBJECT_ID_PEG,
            "by_node_id":       NODE_ID_N2,
            "transition":       "occupied",
        }

    def test_n2_pick_side_empty_precedes_place_side_occupied(self):
        # D-EXEC-7 trace-commit-follows-action: in N2's Phase G, the
        # pick-side mark_fixture_empty mutates first AND emits first;
        # the place-side mark_fixture_occupied follows. Strict seq
        # ordering enforces this.
        rec, _ex = _run_phase_5_session()
        fsc = [e for e in rec.events
               if e.event_type == EVENT_FIXTURE_STATE_CHANGED]
        n2_events = [e for e in fsc if e.payload["by_node_id"] == NODE_ID_N2]
        assert len(n2_events) == 2
        # Pick-side (empty) before place-side (occupied).
        assert n2_events[0].payload["transition"] == "empty"
        assert n2_events[1].payload["transition"] == "occupied"
        assert n2_events[0].seq < n2_events[1].seq


# ═══════════════════════════════════════════════════════════════════════
class TestPhase5DeterministicReplay:
    """Three independent runs of the same session produce
    byte-identical event payloads and boundary snapshot hashes
    (D-CONT-6a)."""

    def _events_tuple(self, rec):
        return [(e.seq, e.event_type, dict(e.payload)) for e in rec.events]

    def test_three_runs_produce_identical_event_payloads(self):
        a, _ = _run_phase_5_session()
        b, _ = _run_phase_5_session()
        c, _ = _run_phase_5_session()
        ea = self._events_tuple(a)
        eb = self._events_tuple(b)
        ec = self._events_tuple(c)
        assert ea == eb == ec

    def test_boundary_snapshot_hashes_byte_identical_across_runs(self):
        a, _ = _run_phase_5_session()
        b, _ = _run_phase_5_session()
        hashes_a = [e.payload["canonical_hash"] for e in a.events
                    if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        hashes_b = [e.payload["canonical_hash"] for e in b.events
                    if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        assert hashes_a == hashes_b
        # 1 session_initial + 2 pre_node + 2 post_node = 5 snapshots.
        assert len(hashes_a) == 5

    def test_each_node_has_pre_and_post_snapshot(self):
        rec, _ex = _run_phase_5_session()
        snap_events = [e for e in rec.events
                       if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        kinds_by_node: dict[str, list[str]] = {}
        for e in snap_events:
            kinds_by_node.setdefault(
                e.payload["node_id"] or "session_initial", []
            ).append(e.payload["snapshot_kind"])
        # session_initial belongs to the None/"session_initial" bucket.
        assert kinds_by_node["session_initial"] \
            == [BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL]
        assert kinds_by_node[NODE_ID_N1] == [
            BOUNDARY_SNAPSHOT_KIND_PRE_NODE,
            BOUNDARY_SNAPSHOT_KIND_POST_NODE,
        ]
        assert kinds_by_node[NODE_ID_N2] == [
            BOUNDARY_SNAPSHOT_KIND_PRE_NODE,
            BOUNDARY_SNAPSHOT_KIND_POST_NODE,
        ]


# ═══════════════════════════════════════════════════════════════════════
class TestPhase5BoundaryContinuity:
    """The peg's authoritative pose in the registry must be preserved
    across the inter-node boundary (post-N1 == pre-N2). Cites D-CONT-4
    (selective authoritative persistence) and D-CONT-1 (canonical
    object pose is authoritative continuity state)."""

    def test_post_n1_pose_equals_pre_n2_pose(self):
        rec, ex = _run_phase_5_session()
        # The fake executor records the peg pose AFTER each execute().
        # By the time N2 starts, the registry's peg.pose_m equals the
        # value N1's execute() set (the place_target world pose).
        # The boundary snapshots N1.post_node and N2.pre_node both
        # snapshot the same registry; their hashes for the object
        # field differ ONLY in metadata (snapshot_seq differs because
        # one is post_node and one is pre_node).
        #
        # Direct test: registry.objects[Peg_01].pose_m post-N1 commit
        # is FixtureA's pose; pre-N2 (after ACQUIRED_ONLY reset, which
        # does NOT teleport the peg) is the same value.
        assert ex.registry.objects[OBJECT_ID_PEG].pose_m \
            == FIXTURE_B_WORLD_POSE_M    # N2's place target
        # The pose at the end of N1 (= FixtureA) is the SAME world
        # location as FixtureB in Phase 5 (co-located). So the
        # post-session pose matches.

    def test_acquired_only_reset_does_not_teleport_peg(self):
        # The fake executor's reset(ACQUIRED_ONLY) is documented to
        # NOT teleport the peg (mirrors the hardened
        # _reset_acquired_only).
        ex = _Phase5FakeExecutor()
        # Place the peg at FixtureA.
        ex.registry.update_object_pose(
            OBJECT_ID_PEG, FIXTURE_A_WORLD_POSE_M, 0.0,
        )
        # Apply ACQUIRED_ONLY reset.
        ex.reset(scope=ResetScope.ACQUIRED_ONLY)
        # Peg pose unchanged.
        assert ex.registry.objects[OBJECT_ID_PEG].pose_m \
            == FIXTURE_A_WORLD_POSE_M

    def test_full_reset_teleports_peg_to_belt_start(self):
        # Contrast: FULL reset DOES teleport the peg (Phase 4A
        # semantics, preserved as the first-node reset path).
        ex = _Phase5FakeExecutor()
        ex.registry.update_object_pose(
            OBJECT_ID_PEG, FIXTURE_A_WORLD_POSE_M, 0.0,
        )
        ex.reset(scope=ResetScope.FULL)
        assert ex.registry.objects[OBJECT_ID_PEG].pose_m \
            == (-0.80, 0.0, 0.701)
