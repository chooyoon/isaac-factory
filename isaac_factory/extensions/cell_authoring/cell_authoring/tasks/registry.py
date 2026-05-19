"""Phase 4A — CellStateRegistry.

Single in-memory store of "what's in the cell, what's happening right
now". Eliminates the implicit state-sharing previously distributed
across the helper, the test fixtures, the harness, and the trajectory
player.

The registry is a passive data holder — it does NOT drive simulation
state. The executor reads and writes it during cycle execution; tests
read it for assertions; the replay package serialises it for portable
review.

Multi-object readiness: ``objects`` is a dict keyed by object_id, NOT
a single-peg reference. Fixtures are likewise keyed. Adding a second
peg to a future task is a matter of registering it; no code change.

Determinism: snapshots are pure data. No callbacks. No side effects.
Two equal-state cells produce equal snapshots.


Write-site classification (D-CONT-7)
====================================

Every write method in this module is explicitly classified per D-CONT-7
(`docs/phase_4b_deterministic_semantics.md` §12.8). "Authoritative"
writes mirror the D-CONT-1 retained-continuity set and participate in
replay-identity hashes via the boundary-snapshot projector.
"Observational" writes mirror live physics into the registry for
diagnostics and per-tick consumers; they do NOT enter replay identity.

+--------------------------------------+-------------------------------+
| method                               | classification                |
+======================================+===============================+
| ``register_object``                  | session-bootstrap (D-CONT-1)  |
| ``update_object_pose``               | observational projection;     |
|                                      | only the last-tick value is   |
|                                      | promoted to authoritative by  |
|                                      | the boundary snapshot         |
|                                      | (D-CONT-1, D-CONT-7)          |
| ``register_fixture``                 | session-bootstrap (D-CONT-1)  |
| ``mark_fixture_occupied``            | authoritative; session-only   |
|                                      | (D-CONT-5)                    |
| ``mark_fixture_empty``               | authoritative; session-only   |
|                                      | (D-CONT-5)                    |
| ``register_robot``                   | session-bootstrap (diagnostic)|
| ``update_robot_pose``                | observational projection;     |
|                                      | NOT authoritative (D-CONT-7)  |
| ``start_task`` / ``set_task_phase``  | diagnostic (D-CONT-2)         |
| ``update_contact_state``             | observational projection;     |
|                                      | NOT authoritative (D-CONT-2)  |
| ``set_metric`` / ``get_metric``      | diagnostic scratchpad         |
+--------------------------------------+-------------------------------+

Future contributors adding a new write method MUST classify it in this
table (D-CONT-7a). Membership in this registry confers NO replay
authority on its own.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


# ─────────────────────── exceptions ───────────────────────


class RegistryStateError(RuntimeError):
    """Raised on illegal authoritative-state transitions.

    Cites D-LIFE-6, D-LIFE-7, D-CONT-5. Examples:

      * ``mark_fixture_occupied(F, A)`` when F is already
        ``occupied(B)`` with B != A (D-LIFE-7 binary-occupancy
        violation: a fixture cannot transition between two distinct
        ``occupied(...)`` states without passing through ``empty``);
      * ``mark_fixture_empty(F, A)`` when F is ``occupied(B)`` with
        B != A (caller asserts release of an object that is not the
        recorded occupant — diagnostic of a contract or wiring bug).
    """


@dataclass
class ObjectState:
    """One manipulable object's runtime state."""
    object_id:   str
    pose_m:      tuple[float, float, float] | None = None
    yaw_rad:     float = 0.0
    contact_with: tuple[str, ...] = ()          # last-tick contact list
    metadata:    dict[str, Any] = field(default_factory=dict)


@dataclass
class FixtureState:
    """One fixture's runtime occupancy state.

    Binary occupancy per D-LIFE-6: a fixture is either ``empty``
    (``occupied_by is None``) or ``occupied(object_id)`` (``occupied_by
    == object_id``). Multi-occupancy is forbidden and rejected at
    :py:meth:`CellStateRegistry.mark_fixture_occupied`.

    Authoritative under D-CONT-1. Mutated only via session-committed
    :py:meth:`CellStateRegistry.mark_fixture_occupied` /
    :py:meth:`mark_fixture_empty` (D-CONT-5).
    """
    fixture_id:  str
    occupied_by: str | None = None               # the object_id occupying this fixture, or None
    metadata:    dict[str, Any] = field(default_factory=dict)


@dataclass
class RobotState:
    """The robot's runtime joint + EE state."""
    robot_id:    str
    joint_positions_rad: tuple[float, ...] = ()
    joint_velocities_rad_s: tuple[float, ...] = ()
    wrist_3_xyz: tuple[float, float, float] | None = None
    gripper_state: str = "open"                  # "open" | "close"
    gripper_drive_target: float = 0.0            # current drive target (rad or m)


@dataclass
class TaskState:
    """The currently-executing task's runtime state."""
    task_id:      str
    phase:        str = "idle"                   # "idle"|"preparing"|"executing"|"validating"|"done"
    step:         int = 0
    started_at_step: int = -1


@dataclass
class ContactState:
    """Last-tick PhysX contact classifications, peg-centric.

    The classifier currently uses fixed pair-token strings (LEFT_FINGER,
    RIGHT_FINGER, BELT, FLOOR, WORK_FIXTURE). The registry stores the
    bits per-tick so the executor + tests can read them without
    re-running the contact source.
    """
    pad_L_contact:    bool = False
    pad_R_contact:    bool = False
    floor_contact:    bool = False
    belt_contact:     bool = False
    fixture_contact:  bool = False
    pad_pen_max_mm:   float = 0.0


class CellStateRegistry:
    """The cell's authoritative runtime state, all in one place.

    Usage:
        reg = CellStateRegistry()
        reg.register_object(ObjectState(object_id="Peg_01", ...))
        reg.register_fixture(FixtureState(fixture_id="WorkFixture_01"))
        reg.register_robot(RobotState(robot_id="UR10e"))
        # During execution:
        reg.update_object_pose("Peg_01", (x, y, z), yaw)
        reg.update_contact_state(ContactState(...))
        # Snapshot for replay or test assertions:
        snap = reg.snapshot()
    """

    def __init__(self) -> None:
        self.objects:   dict[str, ObjectState] = {}
        self.fixtures:  dict[str, FixtureState] = {}
        self.robots:    dict[str, RobotState]   = {}
        self.task:      TaskState | None = None
        self.contact:   ContactState = ContactState()
        # Per-tick scalar metrics readable by validators.
        self.metrics:   dict[str, Any] = {}

    # ─────────── object lifecycle ───────────
    def register_object(self, obj: ObjectState) -> None:
        """Bootstrap registration (D-CONT-1 read-set member).

        Idempotent: re-registering an existing ``object_id`` replaces
        the entry. Bootstrap-time use only; per-tick mutation goes
        through :py:meth:`update_object_pose`.
        """
        self.objects[obj.object_id] = obj

    def update_object_pose(self, object_id: str,
                           pose_m: tuple[float, float, float],
                           yaw_rad: float = 0.0) -> None:
        """Observational projection (D-CONT-7).

        Per-tick mirror of live PhysX object pose into the registry.
        Intermediate per-tick values are observational only. Only the
        **last-tick** value is promoted to authoritative (D-CONT-1)
        via the boundary-snapshot projector at node-boundary commit.
        """
        o = self.objects.get(object_id)
        if o is None:
            o = ObjectState(object_id=object_id)
            self.objects[object_id] = o
        o.pose_m = pose_m
        o.yaw_rad = yaw_rad

    # ─────────── fixture lifecycle ───────────
    def register_fixture(self, fix: FixtureState) -> None:
        """Bootstrap registration (D-CONT-1 read-set member).

        Idempotent: re-registering an existing ``fixture_id`` replaces
        the entry. Bootstrap-time use only; per-cycle occupancy
        mutations go through session-committed
        :py:meth:`mark_fixture_occupied` / :py:meth:`mark_fixture_empty`
        (D-CONT-5).
        """
        self.fixtures[fix.fixture_id] = fix

    def mark_fixture_occupied(self, fixture_id: str, object_id: str) -> None:
        """Authoritative occupancy transition (D-CONT-1, D-LIFE-6).

        **Session-only mutation per D-CONT-5.** Direct invocation from
        ``TaskExecutor._run_cycle`` or any subordinate executor path
        is a contract violation (D-CONT-5a). The call site that
        commits this transition must be ``ExecutionSession.step()``
        Phase G, conditioned on ``TaskResult.outcome == PASS`` and on
        the task definition declaring ``place_target.fixture_id``.

        Binary occupancy (D-LIFE-7):

          * fixture currently ``empty`` → becomes ``occupied(object_id)``
          * fixture currently ``occupied(object_id)`` → no-op (idempotent)
          * fixture currently ``occupied(other_id)`` with other_id !=
            object_id → :class:`RegistryStateError` (D-LIFE-7 violation:
            two distinct occupants without an intervening empty)

        Auto-registers the fixture if not previously registered, to
        preserve Phase 4A's forgiving behavior at the registration
        boundary.
        """
        f = self.fixtures.get(fixture_id)
        if f is None:
            f = FixtureState(fixture_id=fixture_id)
            self.fixtures[fixture_id] = f
        if f.occupied_by is None:
            f.occupied_by = object_id
            return
        if f.occupied_by == object_id:
            return  # idempotent
        raise RegistryStateError(
            f"mark_fixture_occupied({fixture_id!r}, {object_id!r}): "
            f"fixture is already occupied by {f.occupied_by!r}; "
            f"D-LIFE-7 requires an intervening mark_fixture_empty"
        )

    def mark_fixture_empty(self, fixture_id: str, object_id: str) -> None:
        """Authoritative occupancy transition (D-CONT-1, D-LIFE-6).

        **Session-only mutation per D-CONT-5.** Same authority
        discipline as :py:meth:`mark_fixture_occupied`.

        The ``object_id`` parameter is a defensive caller-asserts-this
        check: the session declares which object it believes is being
        released from this fixture. Mismatch with the recorded
        occupant raises :class:`RegistryStateError`, surfacing the
        contract or wiring bug at the mutation point rather than
        silently corrupting registry state.

          * fixture currently ``occupied(object_id)`` → becomes ``empty``
          * fixture currently ``empty`` → no-op (idempotent)
          * fixture currently ``occupied(other_id)`` with other_id !=
            object_id → :class:`RegistryStateError`

        Auto-registers the fixture if not previously registered
        (idempotent no-op then), mirroring :py:meth:`mark_fixture_occupied`.
        """
        f = self.fixtures.get(fixture_id)
        if f is None:
            f = FixtureState(fixture_id=fixture_id)
            self.fixtures[fixture_id] = f
            return  # was-empty → still empty; idempotent
        if f.occupied_by is None:
            return  # idempotent
        if f.occupied_by == object_id:
            f.occupied_by = None
            return
        raise RegistryStateError(
            f"mark_fixture_empty({fixture_id!r}, {object_id!r}): "
            f"fixture is occupied by {f.occupied_by!r}, not by "
            f"{object_id!r}; caller asserts release of an object that "
            f"is not the recorded occupant"
        )

    # ─────────── robot lifecycle ───────────
    def register_robot(self, robot: RobotState) -> None:
        self.robots[robot.robot_id] = robot

    def update_robot_pose(self, robot_id: str, *,
                          joint_positions_rad: tuple[float, ...] | None = None,
                          joint_velocities_rad_s: tuple[float, ...] | None = None,
                          wrist_3_xyz: tuple[float, float, float] | None = None) -> None:
        r = self.robots.get(robot_id)
        if r is None:
            r = RobotState(robot_id=robot_id)
            self.robots[robot_id] = r
        if joint_positions_rad is not None:    r.joint_positions_rad = joint_positions_rad
        if joint_velocities_rad_s is not None: r.joint_velocities_rad_s = joint_velocities_rad_s
        if wrist_3_xyz is not None:            r.wrist_3_xyz = wrist_3_xyz

    # ─────────── task + contact ───────────
    def start_task(self, task_id: str, started_at_step: int) -> None:
        self.task = TaskState(task_id=task_id, phase="executing",
                              started_at_step=started_at_step)

    def set_task_phase(self, phase: str) -> None:
        if self.task is None: return
        self.task.phase = phase

    def update_contact_state(self, c: ContactState) -> None:
        self.contact = c

    # ─────────── metrics scratchpad ───────────
    def set_metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value

    def get_metric(self, key: str, default: Any = None) -> Any:
        return self.metrics.get(key, default)

    # ─────────── snapshot ───────────
    def snapshot(self) -> dict[str, Any]:
        """Deep-copy serialisable view of the entire registry. Suitable
        for the replay package or test assertions."""
        return {
            "objects":  {oid: {"pose_m": o.pose_m, "yaw_rad": o.yaw_rad,
                                "contact_with": list(o.contact_with),
                                "metadata": dict(o.metadata)}
                          for oid, o in self.objects.items()},
            "fixtures": {fid: {"occupied_by": ([f.occupied_by]
                                                if f.occupied_by is not None
                                                else []),
                                "metadata": dict(f.metadata)}
                          for fid, f in self.fixtures.items()},
            "robots":   {rid: {"joint_positions_rad": list(r.joint_positions_rad),
                                "joint_velocities_rad_s": list(r.joint_velocities_rad_s),
                                "wrist_3_xyz": r.wrist_3_xyz,
                                "gripper_state": r.gripper_state,
                                "gripper_drive_target": r.gripper_drive_target}
                          for rid, r in self.robots.items()},
            "task":     None if self.task is None else {
                "task_id": self.task.task_id, "phase": self.task.phase,
                "step": self.task.step, "started_at_step": self.task.started_at_step,
            },
            "contact":  {
                "pad_L_contact":   self.contact.pad_L_contact,
                "pad_R_contact":   self.contact.pad_R_contact,
                "floor_contact":   self.contact.floor_contact,
                "belt_contact":    self.contact.belt_contact,
                "fixture_contact": self.contact.fixture_contact,
                "pad_pen_max_mm":  self.contact.pad_pen_max_mm,
            },
            "metrics":  copy.deepcopy(self.metrics),
        }
