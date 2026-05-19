"""Deterministic joint-space trajectory playback for the cell robot.

Authoring contract (Phase 3B)
-----------------------------

The cell config declares a list of ``TrajectoryWaypoint`` entries:

* Each waypoint names every revolute joint and its target angle in
  radians.
* ``duration_s`` on waypoint ``i > 0`` is the time to travel **from**
  waypoint ``i-1`` **to** waypoint ``i``.
* The gripper state at each waypoint is ``"open"`` or ``"close"``.
* The first waypoint must have ``duration_s = 0.0`` (it is the
  start pose).

Playback is **strict joint-space linear interpolation**. No motion
planning, no spline smoothing, no IK, no reactive control. Samples
align to ``physics_dt`` so identical command streams produce
identical motion under PhysX (sprint §3 determinism contract).

Runtime API
-----------

* :class:`TrajectoryPlayer` — stateful playback over an open Kit stage.
  Constructed once with the cell config; ``advance(dt)`` is called
  once per physics step and writes the next per-joint drive target
  via ``drive:angular:physics:targetPosition``.

* :func:`load_trajectory_paths` — locates every joint's drive target
  attribute up-front so the per-step writes do not re-walk the stage.

This module is **Runtime A safe** (only imports ``pxr``) so the
playback class can be constructed and validated under conda
``env_isaaclab`` for unit tests; the Runtime B test uses the same
class to drive a live Kit ``World``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from pxr import Sdf, Usd

from .config import RobotConfig, TrajectoryWaypoint


# Phase 3I: UsdPhysics revolute-joint drive targets are interpreted in
# DEGREES per the spec. Cell-config waypoints carry joint angles in
# RADIANS; we convert at write time so PhysX sees the right numbers.
_DEG_PER_RAD = 180.0 / math.pi


# ============================================================ utilities ==


def _joint_target_attr_path(robot_mount_path: str, joint_name: str) -> str:
    """Stable USD path for one revolute joint's drive-target attribute."""
    return f"{robot_mount_path}/joints/{joint_name}_joint.drive:angular:physics:targetPosition"


# ============================================================ data ==


@dataclass(frozen=True)
class _Phase:
    """One interpolation phase between two waypoints."""
    start_t_s:        float
    end_t_s:          float                              # = start_t_s + duration_s
    from_positions:   tuple[tuple[str, float], ...]
    to_positions:     tuple[tuple[str, float], ...]
    gripper:          str                                # state ENTERING this phase ("open" | "close")


def _build_phases(waypoints: Sequence[TrajectoryWaypoint]) -> tuple[_Phase, ...]:
    """Compute cumulative time spans for each waypoint transition.

    Waypoint 0 is the start pose (``duration_s=0``); we still emit a
    zero-duration "phase 0" so the first physics tick can set the
    joints to the start positions deterministically and announce the
    initial gripper command.
    """
    phases: list[_Phase] = []
    t = 0.0
    prev_positions = waypoints[0].joint_positions_rad
    # Phase 0: zero-duration "set initial pose" tick.
    phases.append(_Phase(
        start_t_s     = 0.0,
        end_t_s       = 0.0,
        from_positions= prev_positions,
        to_positions  = prev_positions,
        gripper       = waypoints[0].gripper,
    ))
    for wp in waypoints[1:]:
        phases.append(_Phase(
            start_t_s     = t,
            end_t_s       = t + wp.duration_s,
            from_positions= prev_positions,
            to_positions  = wp.joint_positions_rad,
            gripper       = wp.gripper,
        ))
        t += wp.duration_s
        prev_positions = wp.joint_positions_rad
    return tuple(phases)


def _lerp_positions(
    p_from: Sequence[tuple[str, float]],
    p_to:   Sequence[tuple[str, float]],
    alpha:  float,
) -> dict[str, float]:
    """Linear interpolation in joint space.

    Both sequences must have identical ordering of joints (config parser
    guarantees this).
    """
    out: dict[str, float] = {}
    for (name, a), (_, b) in zip(p_from, p_to):
        out[name] = a + (b - a) * alpha
    return out


# ============================================================ player ==


class TrajectoryPlayer:
    """Stateful, deterministic open-loop joint-trajectory player.

    Construct once per simulation run:

    >>> player = TrajectoryPlayer(stage, robot_cfg)
    >>> player.reset()
    >>> for _ in range(n_steps):
    ...     world.step(render=False)
    ...     player.advance(physics_dt)

    Public state:

    * ``current_time_s`` — accumulated wall-time since ``reset()``.
    * ``current_waypoint_index`` — index of the most-recently-passed
      waypoint (0 → start; ``len(trajectory)-1`` → final).
    * ``is_done`` — True once the final waypoint's end time is reached.
    * ``gripper_command`` — "open" or "close" — the state authored by
      the most-recently-entered phase.

    All state derives from ``current_time_s`` so a reset+replay produces
    identical commands at identical step indices.
    """

    def __init__(self, stage: Usd.Stage, robot_cfg: RobotConfig) -> None:
        self._stage = stage
        self._cfg = robot_cfg
        self._phases = _build_phases(robot_cfg.trajectory)
        self._total_duration_s = self._phases[-1].end_t_s

        # Resolve joint target attribute Sdf paths once.
        self._joint_attr_paths: dict[str, Sdf.Path] = {}
        for joint_name, _ in robot_cfg.home_pose_rad:
            attr_path = Sdf.Path(_joint_target_attr_path(
                robot_cfg.mount_prim_path, joint_name,
            ))
            self._joint_attr_paths[joint_name] = attr_path

        # Gripper attribute discovered lazily — the joint lives at a
        # variable depth under the mount depending on which gripper
        # variant composed.
        self._gripper_attr_path: Sdf.Path | None = None
        # Phase 3K: gripper drive type — angular (revolute, deg target)
        # or linear (prismatic, metre target). Resolved lazily in
        # _get_gripper_attr by inspecting the composed gripper joint.
        self._gripper_drive_is_angular: bool = True

        self.current_time_s: float = 0.0
        self.current_waypoint_index: int = 0
        self.gripper_command: str = robot_cfg.trajectory[0].gripper
        self.is_done: bool = False

    # ============================================================ control ==

    def reset(self) -> None:
        """Return to time = 0; the next ``advance`` re-emits the start pose."""
        self.current_time_s = 0.0
        self.current_waypoint_index = 0
        self.gripper_command = self._cfg.trajectory[0].gripper
        self.is_done = False
        # Write the home pose targets immediately so the joints are
        # commanded toward home at the very first physics step after reset.
        self._write_targets(dict(self._cfg.home_pose_rad))
        self._write_gripper_command(self.gripper_command)

    def advance(self, dt_s: float) -> None:
        """Advance simulation time and emit the joint / gripper targets."""
        if self.is_done:
            return
        self.current_time_s = min(self.current_time_s + dt_s, self._total_duration_s)
        phase, idx = self._select_phase(self.current_time_s)
        self.current_waypoint_index = idx
        if phase.end_t_s == phase.start_t_s:
            alpha = 1.0
        else:
            alpha = (self.current_time_s - phase.start_t_s) / (phase.end_t_s - phase.start_t_s)
        alpha = max(0.0, min(1.0, alpha))
        joint_targets = _lerp_positions(phase.from_positions, phase.to_positions, alpha)
        self._write_targets(joint_targets)

        if phase.gripper != self.gripper_command:
            self.gripper_command = phase.gripper
            self._write_gripper_command(self.gripper_command)

        if self.current_time_s >= self._total_duration_s:
            self.is_done = True

    # ============================================================ private ==

    def _select_phase(self, t_s: float) -> tuple[_Phase, int]:
        """Find the phase whose [start_t_s, end_t_s] contains t_s.

        We deliberately iterate (deterministic) rather than binary-search;
        the trajectory has at most ~10 phases.
        """
        for i, phase in enumerate(self._phases):
            if t_s <= phase.end_t_s:
                return phase, i
        return self._phases[-1], len(self._phases) - 1

    def _write_targets(self, positions: Mapping[str, float]) -> None:
        for joint_name, value in positions.items():
            attr_path = self._joint_attr_paths[joint_name]
            attr = self._stage.GetAttributeAtPath(attr_path)
            if attr and attr.IsValid():
                attr.Set(float(value) * _DEG_PER_RAD)

    def _write_gripper_command(self, command: str) -> None:
        target_value = (
            self._cfg.gripper.open_position_rad
            if command == "open"
            else self._cfg.gripper.close_position_rad
        )
        attr = self._get_gripper_attr()
        if attr is not None:
            # Phase 3K: scale only for ANGULAR (revolute) drives. For
            # LINEAR (prismatic) drives the YAML's close_position_rad
            # is interpreted as metres of pad stroke (the YAML field
            # name is kept for backwards compat; ``close_position_rad``
            # is the joint-native unit per Phase 3K's prismatic
            # convention).
            scale = _DEG_PER_RAD if self._gripper_drive_is_angular else 1.0
            attr.Set(float(target_value) * scale)

    def _get_gripper_attr(self) -> Usd.Attribute | None:
        if self._gripper_attr_path is not None:
            return self._stage.GetAttributeAtPath(self._gripper_attr_path)
        # Find the gripper drive joint by name and decide whether it's
        # revolute (writes drive:angular) or prismatic (writes drive:linear).
        from pxr import UsdPhysics
        mount_prefix = self._cfg.mount_prim_path.rstrip("/") + "/"
        for prim in self._stage.Traverse():
            ps = str(prim.GetPath())
            if not ps.startswith(mount_prefix):
                continue
            if ps.rsplit("/", 1)[-1] != self._cfg.gripper.drive_joint_name:
                continue
            if prim.IsA(UsdPhysics.PrismaticJoint):
                self._gripper_drive_is_angular = False
                attr_path = Sdf.Path(ps + ".drive:linear:physics:targetPosition")
                self._gripper_attr_path = attr_path
                return self._stage.GetAttributeAtPath(attr_path)
            if prim.IsA(UsdPhysics.Joint):
                self._gripper_drive_is_angular = True
                attr_path = Sdf.Path(ps + ".drive:angular:physics:targetPosition")
                self._gripper_attr_path = attr_path
                return self._stage.GetAttributeAtPath(attr_path)
        return None
