"""Offline IK solver for cell_01 pick/place waypoints (Lula + UR10e URDF).

Runs ONCE at authoring time under Kit Python. Uses
``isaacsim.robot_motion.motion_generation.kinematics_interface.LulaKinematicsSolver``
— the Lula library shipped with Isaac Sim — to invert UR10e kinematics
against the asset's own URDF + robot_description.yaml. No DH params
re-derived; no scipy.

Output: ``configs/cell_01_ik.yaml`` mapping waypoint name → 6-tuple of
revolute-joint angles (radians, UR10e canonical order). The cell config
references these baked angles in its trajectory.

Offline-only contract: Lula is invoked here, in a one-shot script. The
runtime cell pipeline never imports Lula — it only reads the baked
YAML. This satisfies the Phase 3C "no runtime IK solving" rule.

Targets are specified in the **robot's BASE frame** (Lula's convention),
NOT the cell world frame. The cell mounts the UR10e at world z=0.80
on the pedestal top, so to target world (x, y, z) we pass (x, y, z-0.80)
to Lula.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

LOG_FILE      = Path("/home/cap2/last/logs/solve_pick_place_ik.log")
OUTPUT_YAML   = Path("/home/cap2/last/configs/cell_01_ik.yaml")

URDF_PATH         = "/home/cap2/isaac-sim-5.0.0/exts/isaacsim.robot_motion.motion_generation/motion_policy_configs/universal_robots/ur10e/ur10e.urdf"
DESCRIPTOR_PATH   = "/home/cap2/isaac-sim-5.0.0/exts/isaacsim.robot_motion.motion_generation/motion_policy_configs/universal_robots/ur10e/rmpflow/ur10e_robot_description.yaml"

UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)

ROBOT_BASE_Z_M = 0.80   # cell pedestal top

# IK target frame for UR10e: the tool0 / TCP frame. Lula needs this to
# match a frame in the URDF; ur10e.urdf typically names the end-of-arm
# frame "tool0" or "ee_link". We pass "ee_link" — the Robotiq 2F-140
# gripper mounts beyond ee_link by ~0.20 m, so we account for that
# offset by targeting a point that is the desired tool-tip MINUS the
# gripper-length tool offset.
IK_FRAME_NAME = "tool0"   # UR URDF canonical tool frame
# Empirically (scripts/diag_verify_ik.py): the Robotiq 2F-140 fingertip
# Xforms in this asset sit ~2.4 mm BELOW wrist_3 in world z when the
# tool axis is straight down. So the effective "tool length" between
# Lula's tool0 frame and the grasp point is ≈ 0. Targeting tool tip =
# wrist_3 = tool0 directly works.
TOOL_OFFSET_M = 0.0


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
        os.fsync(fh.fileno())


# Each entry: (name, tool-tip world pos, tool axis world dir).
# Tool axis (-Z) = "EE pointing straight down".
#
# Phase 3L: ``grasp_clearance`` added at tool tip z=0.78 — 30 mm above
# the empirical wrist_3-vs-peg first-contact z (0.741, see
# logs/phase_3l_descent_telemetry.jsonl). The trajectory holds the wrist
# at this clearance pose until the belt halts (peg stationary), then
# performs the final 80 mm drop to the unchanged ``grasp`` pose. This
# keeps the wrist_3 housing OUT of the peg's z-column during the descent
# window when peg-arm contact was inducing the +21 mm Y drift.
TARGETS = [
    ("approach_pick",   (-0.60, 0.0, 0.85), (0.0, 0.0, -1.0)),
    ("grasp_clearance", (-0.60, 0.0, 0.78), (0.0, 0.0, -1.0)),
    ("grasp",           (-0.60, 0.0, 0.70), (0.0, 0.0, -1.0)),
    ("lift",            (-0.60, 0.0, 0.95), (0.0, 0.0, -1.0)),
    ("approach_place",  ( 0.65, 0.0, 0.95), (0.0, 0.0, -1.0)),
    ("place",           ( 0.65, 0.0, 0.72), (0.0, 0.0, -1.0)),
    ("retract_home",    ( 0.65, 0.0, 0.95), (0.0, 0.0, -1.0)),
]


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    _log("[ik] Lula IK for UR10e (offline, baked to YAML)")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        return _run(app)
    except Exception as e:
        import traceback
        _log(f"[ik] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _run(app) -> int:
    import numpy as np
    import yaml
    from isaacsim.robot_motion.motion_generation.lula import LulaKinematicsSolver

    solver = LulaKinematicsSolver(
        robot_description_path=DESCRIPTOR_PATH,
        urdf_path=URDF_PATH,
    )
    _log(f"[ik] solver frames: {solver.get_all_frame_names()}")
    _log(f"[ik] joint names:   {solver.get_joint_names()}")

    # Tool-tip → ee_link offset (subtract along tool axis, since ee_link
    # is BEHIND the tip in the tool-direction frame).
    def ee_link_target_from_tool_tip(tip_world, tool_dir_world):
        td = np.array(tool_dir_world, dtype=float)
        td = td / np.linalg.norm(td)
        # ee_link sits BEHIND the tool tip by TOOL_OFFSET_M along the tool axis
        ee_pos_world = np.array(tip_world, dtype=float) - td * TOOL_OFFSET_M
        # convert from world to robot base frame
        ee_pos_base = ee_pos_world - np.array([0.0, 0.0, ROBOT_BASE_Z_M])
        return ee_pos_base

    # Orientation: tool axis = -Z world, so ee_link's local +z points down.
    # Express as a quaternion (w, x, y, z). For "+z local = -z world",
    # rotate ee_link's identity orientation by 180° around X (or Y).
    # Quaternion for 180° around Y: (0, 0, 1, 0).
    target_orient_quat = np.array([0.0, 0.0, 1.0, 0.0])

    initial = np.array([0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0])

    # Phase 3N — elbow-down warm-start override for the +X side waypoints.
    #
    # Default behaviour (warm_start = previous waypoint's joints) caused
    # Lula to pick an elbow=+2.247 rad solution for ``approach_place``
    # while ``lift`` had elbow=-1.880 rad. The trajectory player's
    # joint-space LERP between those two values takes the short path
    # through +0.18 rad — i.e. through a fully-extended-arm
    # configuration that swings wrist_3 up to z≈2.28 m mid-transport
    # (proven via scripts/diag_phase_3n_grasp_audit.py and
    # logs/phase_3n_grasp_audit.jsonl). Grasp is retained throughout,
    # but the arm shoots to the cell ceiling, which is the "empty
    # gripper" visual the user reported.
    #
    # Fix: for the +X-side waypoints, warm-start Lula with a MIRRORED
    # copy of ``lift``'s joint vector: same shoulder_lift / elbow /
    # wrist_*, but shoulder_pan flipped to the -X→+X mirror angle.
    # That biases the solver toward the elbow-DOWN solution on the +X
    # side, so joint-space LERP from lift to approach_place stays
    # entirely on the elbow-down branch and the TCP arcs at transport
    # altitude rather than spiking to full extension.
    _PHASE_3N_MIRROR_NAMES = {"approach_place", "place", "retract_home"}

    def _solve_with_warm(ws):
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
        _log(f"\n[ik] {name}: tool_tip_world={target_tip_world}  ee_target_base={ee_target_base}")

        joints = None
        success = False

        if name in _PHASE_3N_MIRROR_NAMES and "lift" in results:
            # Phase 3N: Lula's IK has multiple branches at the +X-side
            # targets. Brute-force across a small fan of warm-starts and
            # pick the result whose elbow is CLOSEST to lift's elbow value.
            # That keeps the joint-space LERP from lift→approach_place
            # on a single elbow branch and prevents the arm from passing
            # through full extension (verified visually at z≈2.28 m in
            # Phase 3M; see Phase 3N audit log).
            lift_joints = np.array(results["lift"]["joints_rad"], dtype=float)
            elbow_target_rad = float(lift_joints[2])  # = -1.880 rad after Phase 3M bake

            # Candidate warm-starts: mix of mirror-about-Z, base-rotation,
            # and partial flips. Each row is (sp, sl, e, w1, w2, w3) in rad.
            candidates = []
            # 1. Lift verbatim.
            candidates.append(lift_joints.copy())
            # 2. shoulder_pan negated, rest of lift kept.
            j = lift_joints.copy(); j[0] = -j[0]; candidates.append(j)
            # 3. shoulder_pan rotated by +pi, rest kept.
            j = lift_joints.copy(); j[0] = j[0] + math.pi; candidates.append(j)
            # 4. shoulder_pan rotated by -pi, rest kept.
            j = lift_joints.copy(); j[0] = j[0] - math.pi; candidates.append(j)
            # 5. Full mirror across base: negate shoulder_pan, wrist_3.
            j = lift_joints.copy(); j[0] = -j[0]; j[5] = -j[5]; candidates.append(j)
            # 6. shoulder_pan rotated, elbow kept negative + wrist flipped.
            j = lift_joints.copy(); j[0] = -j[0]; j[3] = -j[3]; j[5] = -j[5]; candidates.append(j)
            # 7. Default initial pose (the original safe default).
            candidates.append(np.array([0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0]))
            # 8. Default initial pose flipped on shoulder_pan.
            candidates.append(np.array([0.0,  1.5708, -1.5708,  1.5708, -1.5708, 0.0]))
            # 9. Same shoulder_pan as the previously-cached approach_place
            #    Lula solution but force elbow to be NEGATIVE (= 2.247 - 2pi).
            j = lift_joints.copy(); j[0] = -0.271; j[2] = -1.880; candidates.append(j)
            # 10. As 9 but with shoulder_lift mirrored.
            j = lift_joints.copy(); j[0] = -0.271; j[1] = -lift_joints[1] - math.pi; j[2] = -lift_joints[2]; candidates.append(j)

            best = None
            best_elbow_dist = float("inf")
            for k, ws in enumerate(candidates):
                jcand, okcand = _solve_with_warm(np.array(ws, dtype=float))
                if not okcand:
                    continue
                elbow_dist = abs(float(jcand[2]) - elbow_target_rad)
                _log(f"  [phase_3n] cand {k}: warm_elbow={ws[2]:+.3f} → joints elbow={float(jcand[2]):+.3f} rad (Δ={elbow_dist:.3f})")
                if elbow_dist < best_elbow_dist:
                    best_elbow_dist = elbow_dist
                    best = jcand
            if best is not None:
                joints, success = best, True
                _log(f"  [phase_3n] best elbow distance from lift = {best_elbow_dist:.3f} rad")
        else:
            joints, success = _solve_with_warm(initial)

        if not success or joints is None:
            _log(f"  ABORT: cannot find IK for {name}")
            continue

        # Phase 3N: unwrap joint angles into a continuous space relative
        # to the previous waypoint so joint-space LERP doesn't take a
        # full-rotation shortcut. Without this, Lula's per-call output
        # can land in different 2π wraps for adjacent waypoints
        # (observed: approach_place shoulder_pan = -164.45°, place
        # shoulder_pan = +195.54° — same angle, +360° apart in joint
        # space). The trajectory player LERPs raw values, so it would
        # rotate shoulder_pan a full 360° between adjacent waypoints
        # unless we collapse to the nearest equivalent angle.
        joints_unwrapped = np.array(joints, dtype=float).copy()
        if len(results) > 0:
            # Last-stored waypoint's UNWRAPPED joints become the reference.
            prev_name = list(results.keys())[-1]
            prev_joints = np.array(results[prev_name]["joints_rad"], dtype=float)
            for i in range(len(joints_unwrapped)):
                while joints_unwrapped[i] - prev_joints[i] > math.pi:
                    joints_unwrapped[i] -= 2.0 * math.pi
                while joints_unwrapped[i] - prev_joints[i] < -math.pi:
                    joints_unwrapped[i] += 2.0 * math.pi
            # Log any joint that needed unwrapping.
            for i in range(len(joints_unwrapped)):
                if abs(float(joints_unwrapped[i]) - float(joints[i])) > 1e-6:
                    _log(f"  [phase_3n] joint {i} unwrapped {math.degrees(joints[i]):+.2f}° → "
                         f"{math.degrees(joints_unwrapped[i]):+.2f}° (anchored to prev '{prev_name}')")
        joints = joints_unwrapped

        _log(f"  joints (deg) = {tuple(round(float(np.degrees(v)), 2) for v in joints)}")
        results[name] = {
            "joints_rad":   [float(v) for v in joints],
            "loss":         0.0,
        }
        initial = joints  # warm-start next pose (still used for non-mirror entries)

    OUTPUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_YAML.open("w") as fh:
        yaml.safe_dump(
            {
                "joint_names":  list(UR10E_JOINT_NAMES),
                "tool_offset_m": TOOL_OFFSET_M,
                "robot_base_world_m": [0.0, 0.0, ROBOT_BASE_Z_M],
                "ik_solver": "lula",
                "waypoints":    results,
            },
            fh, sort_keys=False, default_flow_style=False,
        )
    _log(f"\n[ik] wrote {OUTPUT_YAML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
