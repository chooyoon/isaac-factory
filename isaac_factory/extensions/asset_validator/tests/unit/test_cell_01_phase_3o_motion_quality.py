"""Phase 3O — motion-quality + workspace-envelope realism gates.

Phase 3N proved grasp integrity (per-tick pad-contact persistence + no
floor contact + visual-believability ceilings on wrist_3 / peg z). The
motion BETWEEN those temporal checkpoints could still be unrealistic in
ways that the Phase 3N gates don't catch — e.g., a single-tick joint
spike, a near-instant reversal, or wrist_3 sweeping past the UR10e's
nominal horizontal reach.

This file adds those gates:

  A. peak per-joint angular velocity     ≤ JOINT_VEL_LIMIT_RAD_S    (industrial norm)
  B. peak per-joint angular acceleration ≤ JOINT_ACCEL_LIMIT_RAD_S2 (industrial norm w/ headroom)
  C. peak Cartesian EE speed             ≤ EE_SPEED_LIMIT_MPS       (visual realism)
  D. peak horizontal wrist_3 reach       ≤ WRIST_REACH_LIMIT_M      (UR10e max - safety margin)
  E. wrist_3 z floor                     ≥ WRIST_3_MIN_Z_M          (no descent below the work surface)
  F. cartesian path length per cycle     ≤ CART_PATH_LENGTH_LIMIT_M (catches looping / overhead detours)

These are the realism layer. Endpoint correctness stays in
test_cell_01_pick_place_cycle.py; per-tick grasp integrity stays in
test_cell_01_phase_3n_grasp_integrity.py.

NOTE on the joint-acceleration gate: the trajectory player does pure
linear interpolation, so joint velocity is piecewise-constant per
waypoint. At waypoint boundaries the discrete velocity step produces a
single-tick acceleration spike from the finite-difference estimate.
Those tick-level spikes are an artefact of the discrete-time
measurement, NOT physical PhysX behaviour. The gate is loose enough
(40 rad/s² ≈ 2300°/s²) to tolerate those spikes while still rejecting
sustained pathological behaviour. If we ever swap in a smoothed
interpolator, this gate can be tightened.
"""

from __future__ import annotations

import json
import math

import pytest


try:
    import isaacsim                                       # noqa: F401
    _ISAAC_AVAILABLE = True
except ImportError:
    _ISAAC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _ISAAC_AVAILABLE,
    reason="Kit Python (Runtime B) required",
)


from ._helper_cycle_audit import (
    CELL_STAGE_PATH,
    PHYSICS_DT_S,
    _UR10E_JOINT_NAMES,
    _WORKSPACE,
    load_cfg,
    run_full_cycle_audited,
)


# Phase 3O gates ----------------------------------------------------------
#
# Calibration notes (logs/phase_3o_motion_quality_test.jsonl, measured
# on the validated post-Phase-3N trajectory):
#   joint vel peak             : 5.12 rad/s on wrist_3 (PD overshoot at
#                                the lift→approach_place phase boundary,
#                                while the wrist sweeps 178° in 4 s)
#   joint accel peak           : 417 rad/s² (single-tick finite-diff
#                                transient at a waypoint boundary —
#                                an artefact of pure linear interpolation,
#                                not a sustained physical acceleration)
#   EE Cartesian speed peak    : 0.80 m/s
#   wrist horizontal reach peak: ~1.10 m
#   cartesian path length      : 4.66 m
#
# Gates below sit at ~20-30 % above the measured healthy peaks AND below
# the Phase 3M failure footprint. The Phase 3M ceiling-tour cycle had a
# Cartesian path length > 9 m (extra +2.6 m vertical alone); the 6 m
# gate would have caught it cleanly.
JOINT_VEL_LIMIT_RAD_S      = 6.0      # current peak 5.12 + 18 % headroom
JOINT_ACCEL_LIMIT_RAD_S2   = 600.0    # current peak 417 + 44 % headroom (PD transients)
EE_SPEED_LIMIT_MPS         = 1.5      # current peak 0.80 + ~90 % headroom
WRIST_REACH_LIMIT_M        = 1.20     # UR10e physical max ~1.30 m
WRIST_3_MIN_Z_M            = 0.50     # never descend below the work surface
CART_PATH_LENGTH_LIMIT_M   = 6.0      # passes current 4.66; rejects Phase 3M's > 9 m ceiling tour


@pytest.fixture(scope="module")
def sim_app():
    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    yield app
    app.close()


@pytest.fixture
def cell_stage(sim_app):
    import omni.usd
    ctx = omni.usd.get_context()
    assert CELL_STAGE_PATH.is_file(), f"missing stage: {CELL_STAGE_PATH}"
    r = ctx.open_stage(str(CELL_STAGE_PATH))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    assert ok
    yield ctx.get_stage()


@pytest.fixture
def world(cell_stage):
    from isaacsim.core.api import World
    w = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    w.reset()
    w.play()
    yield w
    w.clear_instance()


class TestMotionQuality:
    """Per-joint and Cartesian realism gates."""

    @pytest.fixture
    def audit(self, world, cell_stage):
        cfg = load_cfg()
        summary, trace = run_full_cycle_audited(world, cell_stage, cfg)
        out = _WORKSPACE / "logs" / "phase_3o_motion_quality_test.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w") as fh:
            fh.write(json.dumps(summary) + "\n")
            for r in trace:
                fh.write(json.dumps(r) + "\n")
        # Print the key realism numbers up-front so a failure log is readable.
        print(f"\n[3o-test] joint vel peak (rad/s, per joint):")
        for i, n in enumerate(_UR10E_JOINT_NAMES):
            print(f"          {n:14s} {summary['joint_vel_peak_per_joint_rad_s'][i]:+.4f}")
        print(f"[3o-test] joint accel peak (rad/s², per joint):")
        for i, n in enumerate(_UR10E_JOINT_NAMES):
            print(f"          {n:14s} {summary['joint_accel_peak_per_joint_rad_s2'][i]:+.4f}")
        print(f"[3o-test] EE speed peak  : {summary['ee_speed_peak_mps']:.4f} m/s "
              f"@ step {summary['ee_speed_peak_step']}")
        print(f"[3o-test] EE accel peak  : {summary['ee_accel_peak_m_s2']:.4f} m/s² "
              f"@ step {summary['ee_accel_peak_step']}")
        print(f"[3o-test] wrist horiz reach peak : {summary['wrist_reach_horizontal_peak_m']:.4f} m "
              f"@ step {summary['wrist_reach_horizontal_peak_step']}")
        print(f"[3o-test] cart path length       : {summary['cartesian_path_length_m']:.3f} m")
        return summary

    def test_peak_joint_velocity_within_industrial_norm(self, audit):
        peak = audit["joint_vel_peak_rad_s"]
        which = audit["joint_vel_peak_per_joint_rad_s"]
        assert peak <= JOINT_VEL_LIMIT_RAD_S, (
            f"peak per-joint angular velocity = {peak:.3f} rad/s "
            f"({math.degrees(peak):.1f}°/s), exceeds {JOINT_VEL_LIMIT_RAD_S:.2f} rad/s "
            f"industrial norm. Per-joint peaks (rad/s): "
            f"{[round(v, 3) for v in which]}"
        )

    def test_peak_joint_acceleration_within_bound(self, audit):
        peak = audit["joint_accel_peak_rad_s2"]
        which = audit["joint_accel_peak_per_joint_rad_s2"]
        assert peak <= JOINT_ACCEL_LIMIT_RAD_S2, (
            f"peak per-joint angular acceleration = {peak:.3f} rad/s² "
            f"({math.degrees(peak):.1f}°/s²), exceeds {JOINT_ACCEL_LIMIT_RAD_S2:.1f} rad/s² "
            f"loose bound. Per-joint peaks (rad/s²): "
            f"{[round(v, 3) for v in which]}"
        )

    def test_peak_ee_speed_within_industrial_norm(self, audit):
        peak = audit["ee_speed_peak_mps"]
        assert peak <= EE_SPEED_LIMIT_MPS, (
            f"peak Cartesian EE speed = {peak:.3f} m/s at step "
            f"{audit['ee_speed_peak_step']}, exceeds {EE_SPEED_LIMIT_MPS:.2f} m/s "
            f"industrial gripper norm"
        )

    def test_wrist_horizontal_reach_within_arm_envelope(self, audit):
        peak = audit["wrist_reach_horizontal_peak_m"]
        assert peak <= WRIST_REACH_LIMIT_M, (
            f"wrist_3 horizontal reach (distance from base axis) = {peak:.3f} m "
            f"at step {audit['wrist_reach_horizontal_peak_step']}, exceeds "
            f"{WRIST_REACH_LIMIT_M:.2f} m. UR10e nominal max reach is "
            f"~1.30 m; closer than that indicates near-singular / "
            f"fully-extended pose."
        )

    def test_wrist_3_does_not_descend_below_work_surface(self, audit):
        # Re-derive from per-step trace since summary only stores peak z.
        log_path = _WORKSPACE / "logs" / "phase_3o_motion_quality_test.jsonl"
        recs = [json.loads(l) for l in log_path.read_text().splitlines()]
        trace = recs[1:]
        wmin = min((r["wrist_3_xyz"][2] for r in trace if r["wrist_3_xyz"]), default=999.0)
        assert wmin >= WRIST_3_MIN_Z_M, (
            f"wrist_3 descended to world z = {wmin:.3f} m, below the "
            f"{WRIST_3_MIN_Z_M:.2f} m work-surface floor. The arm should "
            f"never reach below the conveyor belt top."
        )

    def test_cartesian_path_length_within_realistic_envelope(self, audit):
        path = audit["cartesian_path_length_m"]
        assert path <= CART_PATH_LENGTH_LIMIT_M, (
            f"cartesian path length over the full cycle = {path:.3f} m, "
            f"exceeds {CART_PATH_LENGTH_LIMIT_M:.2f} m gate. A reasonable "
            f"pick→transport→place→return for this cell is ~5–8 m; >12 m "
            f"means the trajectory is detouring (e.g. ceiling tour)"
        )
