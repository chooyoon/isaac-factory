"""Phase 4B Step 8 / Phase 5 — two-node runtime composition.

Defines the first true two-node TaskGraph that exercises inter-node
retained-state continuity end-to-end on Isaac Sim.

Topology
========

   ┌───────────────────────────────┐         ┌──────────────────────────────────┐
   │ N1: belt_pick_fixtureA_place   │  ───►  │ N2: fixtureA_pick_fixtureB_place │
   │  pick_source: Conveyor_InFeed  │         │  pick_source: FixtureA           │
   │  place_target: FixtureA        │         │  place_target: FixtureB          │
   │  trajectory_id: "belt_..._A"   │         │  trajectory_id: "fixA..._B"      │
   └───────────────────────────────┘         └──────────────────────────────────┘

   ResetScope between nodes: ACQUIRED_ONLY  (D-CONT-4 selective
                                              authoritative persistence).

Reset semantics summary
=======================

  * N1 starts via session.begin() → ResetScope.FULL (Phase 4A path).
  * Between N1 and N2: session.step() Phase G commits FixtureA
    occupancy (D-CONT-5), then ExecutionSession.step()'s next-node
    invocation uses ACQUIRED_ONLY (the hardened reset: belt restore +
    contact drain + registry contact/metrics zero, NO teleport, NO
    world.step() — Phase 4 hardening, D-CONT-3 / D-CONT-4).
  * N2's Phase G commits FixtureA → empty (pick-side, peg lifted off)
    and FixtureB → occupied (place-side).

FixtureA / FixtureB world poses
================================

Phase 5 ships FixtureA and FixtureB co-located at the cell's existing
WorkFixture world pose (0.65, 0.0, 0.65). Rationale: the cell's USD
scene defines a single physical work fixture; adding a second
physical fixture would require additive modification of the cell
scene (out of Phase 5 scope per the brief's "no scene modification"
constraint).

The two fixtures are distinguished by:
  * fixture_id in the registry — FixtureA vs FixtureB
  * D-CONT-5 occupancy transitions — N2's pick empties FixtureA,
    N2's place fills FixtureB.

Visual believability is preserved: the peg sits on the physical
WorkFixture surface throughout both nodes; nothing falls through
mid-air. The "two fixtures" abstraction is registry-level, exactly
as D-CONT-1 intends ("fixture occupancy" is registry state, not USD
geometry).

A future Phase 5B (out of this session's scope) can introduce a
second physical fixture geometry at the baked Phase 5 IK location
(0.65, 0.15, 0.65) — the baked angles live in
``configs/cell_01_phase_5_ik.yaml`` waiting for the scene additive
that would make them physically meaningful.

Trajectory composition
======================

* ``belt_pick_fixtureA_place`` — the validated Phase 3 trajectory,
  unchanged. The full waypoint sequence as authored in
  ``configs/cell_01.yaml``. Phase 5 reuses it verbatim.

* ``fixtureA_pick_fixtureB_place`` — new for Phase 5. Starts where N1
  ended (at ``approach_place`` joints, gripper OPEN), descends to
  the FixtureA grasp pose, closes the gripper, lifts, descends back
  to the same pose (FixtureB is co-located), releases, retracts.
  All joint angles reuse existing baked IK from
  ``configs/cell_01_ik.yaml`` (approach_place / place /
  retract_above_place). No new IK is consumed at runtime.

Authority discipline preserved
==============================

This module:
  * does not mutate the registry directly (occupancy commits are
    session Phase-G, D-CONT-5);
  * does not introduce new replay-authoritative fields (the boundary
    snapshot allowlist is unchanged; the Phase 5 trajectory IDs flow
    only through the executor's `trajectory_sets` map, which is
    constructor-injected, never registered);
  * does not introduce continuity predicates (Phase 5 brief defers
    these; Phase 5 task definitions ship with empty preconditions).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..tasks.definitions import (
    JointSpaceLerpTransport,
    OpenJawRelease,
    PickPlaceTask,
    PickSource,
    PlaceTarget,
    PrismaticClampGrasp,
)
from ..tasks.executor import TaskExecutor
from ..tasks.registry import CellStateRegistry, FixtureState
from .graph import TaskEdge, TaskGraph, TaskNode


# ─────────────────────────── public identifiers ───────────────────────────


NODE_ID_N1: str = "N1_belt_pick_fixtureA_place"
NODE_ID_N2: str = "N2_fixtureA_pick_fixtureB_place"

TASK_ID_N1: str = "phase_5_n1_belt_to_fixtureA"
TASK_ID_N2: str = "phase_5_n2_fixtureA_to_fixtureB"

TRAJECTORY_ID_N1: str = "belt_pick_fixtureA_place"
TRAJECTORY_ID_N2: str = "fixtureA_pick_fixtureB_place"

FIXTURE_A_ID: str = "FixtureA"
FIXTURE_B_ID: str = "FixtureB"

# Co-located per the module docstring rationale (no physical scene
# modification in Phase 5).
FIXTURE_A_WORLD_POSE_M: tuple[float, float, float] = (0.65, 0.0, 0.65)
FIXTURE_B_WORLD_POSE_M: tuple[float, float, float] = (0.65, 0.0, 0.65)

OBJECT_ID_PEG: str = "Peg_01"

PLACEMENT_TOLERANCE_XY_M: float = 0.05


# ─────────────────────────── joint-angle constants ───────────────────────────
#
# Baked from configs/cell_01_ik.yaml (Phase 3 Lula IK output). Reused
# verbatim by both N1's trajectory (which is the validated Phase 3
# cycle) and N2's trajectory (which approaches/places at the same
# physical location FixtureA = FixtureB). Joint angles in radians.


def _jp(**joints: float) -> tuple[tuple[str, float], ...]:
    """Compact constructor for joint_positions_rad tuples."""
    canonical_order = ("shoulder_pan", "shoulder_lift", "elbow",
                       "wrist_1", "wrist_2", "wrist_3")
    return tuple((name, joints[name]) for name in canonical_order)


# Phase 3 home pose (= approach_pick).
_HOME = _jp(
    shoulder_pan= 0.294662, shoulder_lift=-2.264833, elbow=-1.890586,
    wrist_1=-3.699000, wrist_2=-1.569941, wrist_3= 1.865738,
)
# Phase 3 grasp_clearance / grasp (peg's belt-grasp pose).
_GRASP_CLEARANCE = _jp(
    shoulder_pan= 0.294616, shoulder_lift=-2.369633, elbow=-1.880357,
    wrist_1=-3.603954, wrist_2=-1.570172, wrist_3= 1.865833,
)
_GRASP_DROP = _jp(
    shoulder_pan= 0.294589, shoulder_lift=-2.494560, elbow=-1.850756,
    wrist_1=-3.508462, wrist_2=-1.570293, wrist_3= 1.865840,
)
_LIFT = _jp(
    shoulder_pan= 0.294415, shoulder_lift=-2.126223, elbow=-1.879776,
    wrist_1=-3.848290, wrist_2=-1.571156, wrist_3= 1.865025,
)
_APPROACH_PLACE = _jp(
    shoulder_pan= 3.412998, shoulder_lift=-2.184815, elbow=-1.769258,
    wrist_1=-3.899986, wrist_2=-1.569894, wrist_3= 4.983946,
)
_PLACE = _jp(
    shoulder_pan= 3.412758, shoulder_lift=-2.499025, elbow=-1.749861,
    wrist_1=-3.604545, wrist_2=-1.571176, wrist_3= 4.982636,
)


# ─────────────────────────── trajectory_sets ───────────────────────────


def build_trajectory_sets():
    """Return ``{trajectory_id: tuple[TrajectoryWaypoint, ...]}``.

    The TrajectoryWaypoint type lives in ``cell_authoring.config``;
    we import lazily to keep this module importable without the
    full cell-authoring stack (the orchestration tests use fake
    executors and don't need TrajectoryWaypoint).
    """
    from ..config import TrajectoryWaypoint

    n1 = (
        TrajectoryWaypoint("home",              0.0, _HOME,           "open"),
        TrajectoryWaypoint("grasp_clearance",   1.0, _GRASP_CLEARANCE, "open"),
        TrajectoryWaypoint("grasp",             1.0, _GRASP_CLEARANCE, "open"),
        TrajectoryWaypoint("grasp_drop",        0.3, _GRASP_DROP,      "open"),
        TrajectoryWaypoint("grasp_close",       1.5, _GRASP_DROP,      "close"),
        TrajectoryWaypoint("lift",              1.5, _LIFT,            "close"),
        TrajectoryWaypoint("approach_place",    4.0, _APPROACH_PLACE,  "close"),
        TrajectoryWaypoint("place",             2.0, _PLACE,           "close"),
        TrajectoryWaypoint("release",           0.5, _PLACE,           "open"),
        TrajectoryWaypoint("retract_above_place", 1.0, _APPROACH_PLACE, "open"),
        TrajectoryWaypoint("return_home",       2.5, _HOME,            "open"),
    )

    # N2: arm starts at HOME (where N1's last waypoint "return_home"
    # left it under ACQUIRED_ONLY — no teleport). Slow transit to
    # approach_place (the FixtureA-above pose), descends to grasp the
    # peg at FixtureA, lifts, descends back (FixtureB co-located),
    # releases, retracts, slow transit back to home. Uses ONLY existing
    # baked IK angles — no new IK consumed.
    #
    # Waypoint timing notes:
    #   * "home → approach_place" is 4.0s to match N1's transport
    #     segment timing — the joint-space distance is the same
    #     (≈ 178° on shoulder_pan and wrist_3). Shorter durations
    #     trigger MOTION_QUALITY_VIOLATION on the NOMINAL profile's
    #     joint-velocity gate.
    #   * "grasp" / "grasp_close" / "lift" / "place" / "release" are
    #     dispatch-keyed by ``TaskExecutor._run_cycle`` to derive
    #     belt_halt_step, grasp_close_step, lift_end_step,
    #     place_end_step, release_end_step.
    n2 = (
        # Wp 0: start at HOME (arm is here after N1's return_home).
        TrajectoryWaypoint("home",              0.0, _HOME,           "open"),
        # Wp 1: slow transit from HOME to approach_place
        # (= approach_fixtureA). 4.0s to keep joint velocities under
        # the NOMINAL gate.
        TrajectoryWaypoint("approach_pickA",    4.0, _APPROACH_PLACE, "open"),
        # Wp 2: descend toward grasp pose. "grasp" is the executor's
        # belt-halt step key — it fires here but the belt is empty
        # during N2, so the halt is a benign no-op.
        TrajectoryWaypoint("grasp_clearance",   1.0, _APPROACH_PLACE, "open"),
        TrajectoryWaypoint("grasp",             1.5, _PLACE,          "open"),
        # Wp 4: close gripper at grasp pose.
        TrajectoryWaypoint("grasp_close",       1.5, _PLACE,          "close"),
        # Wp 5: lift back to approach_place. "lift" is the belt-resume
        # step key.
        TrajectoryWaypoint("lift",              1.5, _APPROACH_PLACE, "close"),
        # Wp 6: descend again to place pose (FixtureB co-located with
        # FixtureA's location for Phase 5).
        TrajectoryWaypoint("place",             2.0, _PLACE,          "close"),
        # Wp 7: release the peg.
        TrajectoryWaypoint("release",           0.5, _PLACE,          "open"),
        # Wp 8: retract to approach_place with gripper open.
        TrajectoryWaypoint("retract_above_place", 1.0, _APPROACH_PLACE, "open"),
        # Wp 9: slow transit back to HOME (mirror of Wp 1).
        TrajectoryWaypoint("return_home",       4.0, _HOME,            "open"),
    )

    return {
        TRAJECTORY_ID_N1: n1,
        TRAJECTORY_ID_N2: n2,
    }


# ─────────────────────────── task / graph builders ───────────────────────────


def build_phase_5_n1_task() -> PickPlaceTask:
    """N1: pick from belt, place at FixtureA."""
    return PickPlaceTask(
        task_id=TASK_ID_N1,
        pick_source=PickSource(
            object_id=OBJECT_ID_PEG,
            world_pose_m=(-0.80, 0.0, 0.701),    # belt-side peg start
            source_kind="conveyor",
            metadata={"conveyor_id": "Conveyor_InFeed"},
        ),
        place_target=PlaceTarget(
            fixture_id=FIXTURE_A_ID,
            world_pose_m=FIXTURE_A_WORLD_POSE_M,
            placement_tolerance_xy_m=PLACEMENT_TOLERANCE_XY_M,
        ),
        grasp_strategy=PrismaticClampGrasp(),
        transport_strategy=JointSpaceLerpTransport(profile_id="nominal"),
        release_strategy=OpenJawRelease(),
        trajectory_id=TRAJECTORY_ID_N1,
    )


def build_phase_5_n2_task() -> PickPlaceTask:
    """N2: pick from FixtureA, place at FixtureB.

    PickSource doesn't natively carry a ``fixture_id`` field; we
    monkey-attach it via ``object.__setattr__`` after constructing the
    frozen dataclass so the session's Phase-G commit logic can find
    the pick-side fixture id for ``mark_fixture_empty``. The
    forward-compatible alternative (a from-fixture PickSource subclass)
    is Phase 5B scope.
    """
    pick_source = PickSource(
        object_id=OBJECT_ID_PEG,
        world_pose_m=FIXTURE_A_WORLD_POSE_M,    # peg's location after N1
        source_kind="fixture",
    )
    object.__setattr__(pick_source, "fixture_id", FIXTURE_A_ID)
    return PickPlaceTask(
        task_id=TASK_ID_N2,
        pick_source=pick_source,
        place_target=PlaceTarget(
            fixture_id=FIXTURE_B_ID,
            world_pose_m=FIXTURE_B_WORLD_POSE_M,
            placement_tolerance_xy_m=PLACEMENT_TOLERANCE_XY_M,
        ),
        grasp_strategy=PrismaticClampGrasp(),
        transport_strategy=JointSpaceLerpTransport(profile_id="nominal"),
        release_strategy=OpenJawRelease(),
        trajectory_id=TRAJECTORY_ID_N2,
    )


def build_phase_5_graph() -> TaskGraph:
    """The 2-node TaskGraph — N1 → N2, strict serial dependency."""
    return TaskGraph.build(
        nodes=[
            TaskNode(node_id=NODE_ID_N1, task_ref=TASK_ID_N1),
            TaskNode(node_id=NODE_ID_N2, task_ref=TASK_ID_N2),
        ],
        edges=[
            TaskEdge(parent_id=NODE_ID_N1, child_id=NODE_ID_N2),
        ],
    )


# ─────────────────────────── session-builder helpers ───────────────────────────


def register_phase_5_fixtures(registry: CellStateRegistry) -> None:
    """Register FixtureA and FixtureB in the registry.

    Idempotent. Authoritative-bootstrap write (D-CONT-1 read-set
    member). Called by the Phase 5 Isaac Sim runner after
    ``TaskExecutor.prepare()`` has run (which registers the cell's
    default WorkFixture). The Phase 5 fixtures are additional
    registrations and do not displace WorkFixture.
    """
    registry.register_fixture(FixtureState(fixture_id=FIXTURE_A_ID))
    registry.register_fixture(FixtureState(fixture_id=FIXTURE_B_ID))


def build_phase_5_task_resolver():
    """Return a ``task_resolver`` callable for the Phase 5 graph.

    Resolves ``TaskNode → PickPlaceTask`` by node_id. Used by the
    session to convert the symbolic graph node into the concrete
    task descriptor the executor consumes.
    """
    n1 = build_phase_5_n1_task()
    n2 = build_phase_5_n2_task()
    by_id = {NODE_ID_N1: n1, NODE_ID_N2: n2}

    def _resolve(node: TaskNode) -> PickPlaceTask:
        if node.node_id not in by_id:
            raise ValueError(
                f"phase_5_two_node task_resolver: unknown node_id "
                f"{node.node_id!r} (expected one of {sorted(by_id.keys())!r})"
            )
        return by_id[node.node_id]

    return _resolve
