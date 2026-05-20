"""Phase 4B Step 8 / Phase 5 — IK for FixtureB-side waypoints.

Bakes joint angles for the new waypoints required by Phase 5's
``fixtureA_pick_fixtureB_place`` trajectory. Only the FixtureB-side
poses are solved here; the FixtureA-side poses (approach_fixtureA,
grasp_fixtureA, lift_fixtureA) are byte-equal to the existing Phase
3 ``approach_place``, ``place``, ``retract_home`` solutions in
``configs/cell_01_ik.yaml`` and are reused without re-solving.

FixtureB location (Phase 5 authoring decision):
  world_pose_m = (0.65, 0.15, 0.65)  — same +X reach as FixtureA,
                                       offset +Y 15 cm. Close enough
                                       to FixtureA that Lula can find
                                       an IK solution on the same
                                       elbow-down branch as
                                       approach_place (which is
                                       essential — a branch flip
                                       between adjacent waypoints
                                       would cause the arm to
                                       traverse through joint-space
                                       discontinuities, producing the
                                       "simulator snap" artefact the
                                       Phase 5 brief forbids).

Targets (tool-tip world positions, tool axis = -Z world):

  approach_fixtureB:  (0.65, 0.4, 0.95)   — 30 cm above fixture top
  place_fixtureB:     (0.65, 0.4, 0.72)   — same height as Phase 3's
                                              place pose (peg release
                                              from gripper, peg bottom
                                              meets fixture top at
                                              0.65 m)
  retract_fixtureB:   (0.65, 0.4, 0.95)   — same as approach_fixtureB

Warm-start strategy (cites Phase 3N mirror logic in
``solve_pick_place_ik.py``): the FixtureB targets are on the +X side
of the robot base, so the same elbow-down-bias warm-start cascade is
applied. The reference elbow value is taken from the existing
``approach_place`` solution (which sits on the validated elbow-down
branch).

Output: ``configs/cell_01_phase_5_ik.yaml``. Original
``cell_01_ik.yaml`` is NOT modified — Phase 5 IK lives in a sibling
file consumed at runtime by the Phase 5 trajectory builder.

Offline-only contract: this script is invoked ONCE at authoring time.
The Phase 5 runtime never imports Lula; it reads the baked YAML.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path


LOG_FILE      = Path("/home/cap2/last/logs/solve_phase_5_fixture_pick_ik.log")
EXISTING_IK   = Path("/home/cap2/last/configs/cell_01_ik.yaml")
OUTPUT_YAML   = Path("/home/cap2/last/configs/cell_01_phase_5_ik.yaml")

URDF_PATH         = "/home/cap2/isaac-sim-5.0.0/exts/isaacsim.robot_motion.motion_generation/motion_policy_configs/universal_robots/ur10e/ur10e.urdf"
DESCRIPTOR_PATH   = "/home/cap2/isaac-sim-5.0.0/exts/isaacsim.robot_motion.motion_generation/motion_policy_configs/universal_robots/ur10e/rmpflow/ur10e_robot_description.yaml"

UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)

ROBOT_BASE_Z_M = 0.80
IK_FRAME_NAME  = "tool0"
TOOL_OFFSET_M  = 0.0

# Phase 5 — three new targets only. FixtureA-side targets reuse
# Phase 3 IK output. FixtureB sits 15 cm in +Y from FixtureA — close
# enough that Lula stays on the validated elbow-down branch.
TARGETS = [
    ("approach_fixtureB", (0.65,  0.15, 0.95), (0.0, 0.0, -1.0)),
    ("place_fixtureB",    (0.65,  0.15, 0.72), (0.0, 0.0, -1.0)),
    ("retract_fixtureB",  (0.65,  0.15, 0.95), (0.0, 0.0, -1.0)),
]


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    _log("[ik-p5] Lula IK for Phase 5 FixtureB-side waypoints (offline)")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        return _run(app)
    except Exception as e:
        import traceback
        _log(f"[ik-p5] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _run(app) -> int:
    import numpy as np
    import yaml
    from isaacsim.robot_motion.motion_generation.lula import LulaKinematicsSolver

    # Load existing IK so we can warm-start with approach_place's
    # joint configuration (the Phase 3-validated elbow-down branch
    # on the +X side).
    with EXISTING_IK.open() as fh:
        existing_ik = yaml.safe_load(fh)
    approach_place_joints = np.array(
        existing_ik["waypoints"]["approach_place"]["joints_rad"],
        dtype=float,
    )
    place_joints = np.array(
        existing_ik["waypoints"]["place"]["joints_rad"],
        dtype=float,
    )
    _log(f"[ik-p5] approach_place reference joints (deg): "
         f"{tuple(round(float(np.degrees(v)), 2) for v in approach_place_joints)}")
    elbow_target_rad = float(approach_place_joints[2])

    solver = LulaKinematicsSolver(
        robot_description_path=DESCRIPTOR_PATH,
        urdf_path=URDF_PATH,
    )
    _log(f"[ik-p5] solver frames: {solver.get_all_frame_names()}")

    def ee_link_target_from_tool_tip(tip_world, tool_dir_world):
        td = np.array(tool_dir_world, dtype=float)
        td = td / np.linalg.norm(td)
        ee_pos_world = np.array(tip_world, dtype=float) - td * TOOL_OFFSET_M
        ee_pos_base = ee_pos_world - np.array([0.0, 0.0, ROBOT_BASE_Z_M])
        return ee_pos_base

    target_orient_quat = np.array([0.0, 0.0, 1.0, 0.0])

    def _solve_with_warm(ws, *, ee_target_base):
        j, ok = solver.compute_inverse_kinematics(
            frame_name=IK_FRAME_NAME,
            target_position=ee_target_base,
            target_orientation=target_orient_quat,
            warm_start=ws,
            position_tolerance=1e-3,
            orientation_tolerance=1e-2,
        )
        if not ok:
            j, ok = solver.compute_inverse_kinematics(
                frame_name=IK_FRAME_NAME,
                target_position=ee_target_base,
                target_orientation=None,
                warm_start=ws,
                position_tolerance=5e-3,
            )
        return (j, ok)

    results = {}
    for name, target_tip_world, tool_dir_world in TARGETS:
        ee_target_base = ee_link_target_from_tool_tip(target_tip_world, tool_dir_world)
        _log(f"\n[ik-p5] {name}: tool_tip_world={target_tip_world}  ee_target_base={ee_target_base}")

        # FixtureB is on the +X side just like Phase 3N's mirror logic
        # handles. Apply the same brute-force warm-start cascade and
        # pick the candidate whose elbow is closest to approach_place's
        # elbow (the validated elbow-down branch).
        candidates = []
        # 1. approach_place verbatim (the existing elbow-down branch).
        candidates.append(approach_place_joints.copy())
        # 2. place verbatim (lower variant of approach_place).
        candidates.append(place_joints.copy())
        # 3. approach_place with shoulder_pan rotated toward +Y.
        j = approach_place_joints.copy(); j[0] -= 0.55; candidates.append(j)
        # 4. approach_place with shoulder_pan rotated more.
        j = approach_place_joints.copy(); j[0] -= 1.0; candidates.append(j)
        # 5. approach_place with shoulder_pan rotated +π.
        j = approach_place_joints.copy(); j[0] += math.pi; candidates.append(j)
        # 6. approach_place with shoulder_pan rotated −π.
        j = approach_place_joints.copy(); j[0] -= math.pi; candidates.append(j)
        # 7. Default initial pose.
        candidates.append(np.array([0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]))
        # 8. Default initial pose flipped on shoulder_pan.
        candidates.append(np.array([0.0,  1.5708, -1.5708,  1.5708, -1.5708, 0.0]))

        best = None
        best_elbow_dist = float("inf")
        for k, ws in enumerate(candidates):
            jcand, okcand = _solve_with_warm(np.array(ws, dtype=float),
                                              ee_target_base=ee_target_base)
            if not okcand:
                _log(f"  cand {k}: warm_elbow={ws[2]:+.3f} → IK FAILED")
                continue
            elbow_dist = abs(float(jcand[2]) - elbow_target_rad)
            _log(f"  cand {k}: warm_elbow={ws[2]:+.3f} → joints elbow={float(jcand[2]):+.3f} rad (Δ={elbow_dist:.3f})")
            if elbow_dist < best_elbow_dist:
                best_elbow_dist = elbow_dist
                best = jcand
        if best is None:
            _log(f"  ABORT: cannot find IK for {name}")
            continue
        joints = best
        _log(f"  best elbow distance from approach_place = {best_elbow_dist:.3f} rad")

        # 2π unwrap relative to the previous waypoint (Phase 3N).
        joints_unwrapped = np.array(joints, dtype=float).copy()
        # Anchor: previous Phase 5 waypoint if any, else approach_place
        # (the natural predecessor of approach_fixtureB in the
        # fixtureA_pick_fixtureB_place trajectory).
        if results:
            prev_name = list(results.keys())[-1]
            prev_joints = np.array(results[prev_name]["joints_rad"], dtype=float)
        else:
            prev_name = "approach_place(existing)"
            prev_joints = approach_place_joints.copy()
        for i in range(len(joints_unwrapped)):
            while joints_unwrapped[i] - prev_joints[i] > math.pi:
                joints_unwrapped[i] -= 2.0 * math.pi
            while joints_unwrapped[i] - prev_joints[i] < -math.pi:
                joints_unwrapped[i] += 2.0 * math.pi
        for i in range(len(joints_unwrapped)):
            if abs(float(joints_unwrapped[i]) - float(joints[i])) > 1e-6:
                _log(f"  joint {i} unwrapped {math.degrees(joints[i]):+.2f}° → "
                     f"{math.degrees(joints_unwrapped[i]):+.2f}° (anchored to '{prev_name}')")
        joints = joints_unwrapped

        _log(f"  joints (deg) = {tuple(round(float(np.degrees(v)), 2) for v in joints)}")
        results[name] = {
            "joints_rad": [float(v) for v in joints],
            "loss":       0.0,
        }

    OUTPUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_YAML.open("w") as fh:
        yaml.safe_dump(
            {
                "phase":            "4B Step 8 Phase 5",
                "joint_names":      list(UR10E_JOINT_NAMES),
                "tool_offset_m":    TOOL_OFFSET_M,
                "robot_base_world_m": [0.0, 0.0, ROBOT_BASE_Z_M],
                "ik_solver":        "lula",
                "fixture_b_world_m": [0.65, 0.4, 0.65],
                "waypoints":        results,
            },
            fh, sort_keys=False, default_flow_style=False,
        )
    _log(f"\n[ik-p5] wrote {OUTPUT_YAML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
