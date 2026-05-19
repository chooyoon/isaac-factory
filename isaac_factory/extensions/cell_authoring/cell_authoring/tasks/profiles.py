"""Phase 4A — trajectory profiles.

Profiles are duration-and-limits overlays on top of a base trajectory
description (the cell config's waypoint list). They preserve the
geometric path (waypoint joint targets) but scale time and tighten or
loosen the realism gates. This is the lightest possible profile system
that still satisfies the Phase 4A asks without modifying the validated
TrajectoryPlayer.

Profile rules
-------------

* ``SAFE``        — 1.5× duration on every motion phase. Lowest joint
                    velocities, lowest PD overshoot, strictest gates.
                    Cycle takes ~50% longer.
* ``NOMINAL``     — 1.0× duration. Exactly what Phase 3M/N/O/P were
                    validated against. The reference.
* ``AGGRESSIVE``  — 0.75× duration on every motion phase. Faster but
                    higher joint-velocity peaks; gates relax to absorb
                    the resulting PD transients.

Phases that are "hold" or zero-duration (the dwell waypoints in the
cell config — e.g. ``grasp_close``, ``release``) are NOT scaled. Only
motion phases (where the arm actually moves) are stretched/compressed.
A waypoint is considered a "motion phase" if its joint vector differs
from the previous waypoint.

The profile does NOT modify the trajectory player or the cell config
file. It produces a NEW config dataclass via ``dataclasses.replace``
that the executor passes to ``TrajectoryPlayer(...)``.
"""

from __future__ import annotations

import dataclasses
import enum
import math
from dataclasses import dataclass

from ..config import RobotConfig, TrajectoryWaypoint


class TrajectoryProfile(enum.Enum):
    SAFE       = "safe"
    NOMINAL    = "nominal"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class ProfileSpec:
    """Per-profile gate values and time-scaling factors.

    The gate values are not enforced here — they're surfaced for the
    UnifiedValidator and tests to read so that per-profile asserts can
    be expressed declaratively.
    """
    name:                       str
    motion_duration_scale:      float    # multiply each motion phase's duration_s
    # Phase 3O motion-quality gates, per profile.
    joint_vel_limit_rad_s:      float
    joint_accel_limit_rad_s2:   float
    ee_speed_limit_mps:         float
    cartesian_path_limit_m:     float
    # Visual-believability ceilings (Phase 3N).
    wrist_3_max_z_m:            float = 1.10
    peg_max_z_m:                float = 1.10


_PROFILE_SPECS: dict[TrajectoryProfile, ProfileSpec] = {
    TrajectoryProfile.SAFE: ProfileSpec(
        name                     = "safe",
        motion_duration_scale    = 1.5,
        joint_vel_limit_rad_s    = 4.0,    # tighter than nominal
        joint_accel_limit_rad_s2 = 400.0,
        ee_speed_limit_mps       = 1.0,
        cartesian_path_limit_m   = 6.5,
    ),
    TrajectoryProfile.NOMINAL: ProfileSpec(
        name                     = "nominal",
        motion_duration_scale    = 1.0,
        joint_vel_limit_rad_s    = 6.0,    # = Phase 3O gate
        joint_accel_limit_rad_s2 = 600.0,
        ee_speed_limit_mps       = 1.5,
        cartesian_path_limit_m   = 6.0,
    ),
    TrajectoryProfile.AGGRESSIVE: ProfileSpec(
        name                     = "aggressive",
        motion_duration_scale    = 0.75,
        joint_vel_limit_rad_s    = 9.0,    # higher PD overshoot expected
        joint_accel_limit_rad_s2 = 900.0,
        ee_speed_limit_mps       = 2.0,
        cartesian_path_limit_m   = 6.0,
    ),
}


def get_profile_spec(profile: TrajectoryProfile) -> ProfileSpec:
    return _PROFILE_SPECS[profile]


def _is_motion_phase(prev_wp: TrajectoryWaypoint, cur_wp: TrajectoryWaypoint) -> bool:
    """True if cur_wp's joint vector differs from prev_wp's by any joint
    delta (= the arm moves during this phase). A waypoint that holds
    the previous pose with zero duration, or duplicates the previous
    joint vector for gripper-only state changes, is NOT a motion phase
    and is not scaled.
    """
    if cur_wp.duration_s <= 1e-9:
        return False
    prev_d = dict(prev_wp.joint_positions_rad)
    cur_d  = dict(cur_wp.joint_positions_rad)
    for k, v in cur_d.items():
        if abs(v - prev_d.get(k, v)) > 1e-9:
            return True
    return False


# Phase 4A — waypoints that must NOT be time-scaled because the cell's
# indexed-belt halt timing is calibrated against their cumulative
# duration. The cell_01 belt halts at the end of the waypoint named
# "grasp" (see scripts/launch_phase_3m_stream.py + the cycle test);
# any waypoint at or before that point participates in the
# peg-arrival-on-belt synchronisation contract and so cannot be
# stretched/compressed by a motion profile without de-syncing the peg.
#
# Profile time-scaling therefore applies ONLY to post-belt-halt
# motion phases (grasp_drop / lift / approach_place / place / retract
# / return_home in the cell_01 trajectory). The pre-belt-halt phases
# stay at their authored durations regardless of profile.
_BELT_SYNCHRONIZED_WAYPOINT_NAMES = frozenset({
    "home",
    "grasp_clearance",
    "grasp",
})


def apply_profile_to_trajectory(robot_cfg: RobotConfig,
                                profile: TrajectoryProfile) -> RobotConfig:
    """Return a new RobotConfig with the trajectory's per-waypoint
    durations scaled per the profile. Joint angles are NOT touched.

    NOMINAL is a fast path — returns the original cfg unchanged. SAFE
    and AGGRESSIVE create a new cfg via ``dataclasses.replace`` so the
    caller can pass it to ``TrajectoryPlayer`` without mutating the
    cell config in-place.
    """
    spec = get_profile_spec(profile)
    if abs(spec.motion_duration_scale - 1.0) < 1e-9:
        return robot_cfg
    s = spec.motion_duration_scale
    waypoints = list(robot_cfg.trajectory)
    new_waypoints: list[TrajectoryWaypoint] = []
    for i, wp in enumerate(waypoints):
        if i == 0:
            # First waypoint is always the start pose with duration 0.
            new_waypoints.append(wp)
            continue
        if wp.name in _BELT_SYNCHRONIZED_WAYPOINT_NAMES:
            # Belt-synced phase — preserve authored duration regardless
            # of profile, so the peg-on-belt arrival timing stays in
            # sync with the indexed-belt halt.
            new_waypoints.append(wp)
            continue
        if _is_motion_phase(waypoints[i-1], wp):
            new_wp = dataclasses.replace(wp, duration_s=wp.duration_s * s)
        else:
            new_wp = wp
        new_waypoints.append(new_wp)
    new_cfg = dataclasses.replace(robot_cfg, trajectory=tuple(new_waypoints))
    return new_cfg
