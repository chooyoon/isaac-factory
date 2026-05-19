"""Shared cycle-audit helper for the Phase 3N grasp-integrity and the
Phase 3O motion-quality test files.

Owning one copy of the cycle runner keeps the two test suites in sync
and avoids drift between their per-tick instrumentation. The validated
Phase 3M cycle is run unchanged — same TrajectoryPlayer, articulation
write pattern, indexed-belt halt, deterministic peg reset.

What this helper records per physics tick (= per world.step):

  grasp + pose
    peg_xyz, peg_vel             (peg world position + linear velocity)
    wrist_3_xyz                  (UR10e tool-flange world position)
    left_finger_xyz, right_finger_xyz

  contact classification
    pad_L_contact, pad_R_contact (peg ↔ pad contact bits)
    belt_contact, floor_contact, fixture_contact
    pad_pen_mm                   (max pad↔peg penetration)

  motion quality (Phase 3O)
    joint_pos                    (6 UR10e joint positions, rad)
    joint_vel                    (6 UR10e joint velocities, rad/s, from articulation)
    joint_accel                  (finite-diff of joint_vel over physics_dt)
    joint_jerk                   (finite-diff of joint_accel)
    ee_lin_vel                   (finite-diff of wrist_3_xyz)
    ee_speed_mps                 (|ee_lin_vel|)

Filename starts with an underscore so pytest does NOT collect it as a
test module.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


_WORKSPACE      = Path(__file__).resolve().parents[5]
CELL_STAGE_PATH = _WORKSPACE / "assets" / "cells" / "cell_01.usda"

ROBOT_MOUNT_PATH = "/World/Robot"
EE_LINK_PATH     = "/World/Robot/ee_link"
PEG_PATH         = "/World/Parts/Peg_01"
BELT_PATH        = "/World/Machinery/Conveyor_InFeed/Belt"
LEFT_FINGER      = "/World/Robot/ee_link/left_finger"
RIGHT_FINGER     = "/World/Robot/ee_link/right_finger"
WRIST_3_LINK     = "/World/Robot/wrist_3_link"
WORK_FIXTURE     = "/World/Environment/WorkFixture"
FLOOR_TOKEN      = "/World/Environment/Floor"

PHYSICS_DT_S = 1.0 / 60.0

_UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)

# Phase 3N gates (preserved here for the grasp-integrity tests).
WRIST_3_MAX_Z_GATE_M       = 1.10
PEG_MAX_Z_GATE_M           = 1.10
SUSTAINED_CONTACT_STEPS    = 30
MAX_PRE_RELEASE_BREAK_S    = 0.10
MIN_PAD_PEG_PENETRATION_MM = 1.0
RELEASE_FIXTURE_TOLERANCE_STEPS = 30


def _world_translate(stage, path: str):
    from pxr import UsdGeom, Usd
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return None
    mat = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    t = mat.ExtractTranslation()
    return (float(t[0]), float(t[1]), float(t[2]))


def _classify_peg_pair(other_path: str) -> str:
    o = other_path
    if o == LEFT_FINGER or o.startswith(LEFT_FINGER + "/"):    return "pad_L"
    if o == RIGHT_FINGER or o.startswith(RIGHT_FINGER + "/"):  return "pad_R"
    if BELT_PATH in o:                                          return "belt"
    if FLOOR_TOKEN in o:                                        return "floor"
    if WORK_FIXTURE in o:                                       return "fixture"
    if o.startswith(ROBOT_MOUNT_PATH):                          return "robot_other"
    return "other"


def load_cfg():
    import sys
    sys.path.insert(0, str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    from cell_authoring import load_config
    return load_config(_WORKSPACE / "configs" / "cell_01.yaml")


def run_full_cycle_audited(world, stage, cfg) -> tuple[dict, list[dict]]:
    """Run one validated Phase 3M cycle with full grasp + motion-quality
    telemetry. Returns (summary, per_step_trace)."""
    import numpy as np
    import sys
    from isaacsim.core.prims import Articulation, RigidPrim
    from cell_authoring.trajectory import TrajectoryPlayer
    sys.path.insert(0, str(_WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))
    from asset_validator.adapters.physx_contact_source import PhysXContactSource
    from pxr import Gf

    art = Articulation(prim_paths_expr=ROBOT_MOUNT_PATH)
    try:
        world.scene.add(art)
    except Exception:
        pass
    art.initialize()
    dof_names = list(art.dof_names)
    joint_indices = [dof_names.index(f"{n}_joint") for n in _UR10E_JOINT_NAMES]
    grip_idx       = dof_names.index("finger_joint")        if "finger_joint"        in dof_names else None
    right_grip_idx = dof_names.index("right_finger_joint")  if "right_finger_joint"  in dof_names else None

    peg = RigidPrim(prim_paths_expr=PEG_PATH)
    peg.initialize()

    contact_source = PhysXContactSource(stage=stage, physics_dt=PHYSICS_DT_S)

    home_pose = dict(cfg.robot.home_pose_rad)
    full = art.get_joint_positions()
    for i, name in enumerate(_UR10E_JOINT_NAMES):
        full[0][joint_indices[i]] = float(home_pose[name])
    art.set_joint_positions(full)
    art.set_joint_position_targets(full)

    authored_xyz = cfg.parts[0].translate_world_m
    peg.set_world_poses(
        positions=np.array([[authored_xyz[0], authored_xyz[1], authored_xyz[2]]], dtype=np.float32),
        orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
    )
    peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
    peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))
    for _ in range(10):
        world.step(render=False)
    peg.set_world_poses(
        positions=np.array([[authored_xyz[0], authored_xyz[1], authored_xyz[2]]], dtype=np.float32),
        orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
    )
    peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
    peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))
    contact_source.query_contacts()

    belt_attr = stage.GetAttributeAtPath(BELT_PATH + ".physxSurfaceVelocity:surfaceVelocity")
    original_belt_v = belt_attr.Get() if (belt_attr and belt_attr.IsValid()) else None

    def _set_belt_vel(v):
        if belt_attr and belt_attr.IsValid():
            belt_attr.Set(Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])))
    if original_belt_v is not None:
        _set_belt_vel(original_belt_v)

    waypoints  = list(cfg.robot.trajectory)
    cumulative = []; t_c = 0.0
    for wp in waypoints:
        t_c += wp.duration_s
        cumulative.append(t_c)
    name_to_end_t = {wp.name: cumulative[i] for i, wp in enumerate(waypoints)}
    grasp_end_s        = name_to_end_t.get("grasp",        2.0)
    grasp_close_end_s  = name_to_end_t.get("grasp_close",  3.8)
    lift_end_s         = name_to_end_t.get("lift",         5.3)
    place_end_s        = name_to_end_t.get("place",        11.3)
    release_end_s      = name_to_end_t.get("release",      11.8)
    total_s            = cumulative[-1]

    belt_halt_step       = int(round(grasp_end_s     / PHYSICS_DT_S))
    belt_resume_step     = int(round(lift_end_s      / PHYSICS_DT_S))
    grasp_close_step     = int(round(grasp_close_end_s / PHYSICS_DT_S))
    lift_end_step        = int(round(lift_end_s      / PHYSICS_DT_S))
    place_end_step       = int(round(place_end_s     / PHYSICS_DT_S))
    release_end_step     = int(round(release_end_s   / PHYSICS_DT_S))
    release_start_step   = place_end_step
    n_steps              = int(round(total_s         / PHYSICS_DT_S)) + 60

    player = TrajectoryPlayer(stage=stage, robot_cfg=cfg.robot)
    player.reset()
    _DEG2RAD = math.pi / 180.0

    trace: list[dict[str, Any]] = []
    prev_wrist  = None
    prev_jvel   = None
    prev_jaccel = None
    prev_ee_v   = None

    try:
        for step_i in range(n_steps):
            full_target = np.array(art.get_joint_positions(), dtype=np.float32).copy()
            for i, name in enumerate(_UR10E_JOINT_NAMES):
                attr_path = (
                    f"{cfg.robot.mount_prim_path}/joints/{name}_joint"
                    f".drive:angular:physics:targetPosition"
                )
                attr = stage.GetAttributeAtPath(attr_path)
                if attr and attr.IsValid():
                    full_target[0, joint_indices[i]] = float(attr.Get()) * _DEG2RAD
            if grip_idx is not None and player._gripper_attr_path is not None:
                gattr = stage.GetAttributeAtPath(player._gripper_attr_path)
                if gattr and gattr.IsValid():
                    grip_scale = _DEG2RAD if getattr(player, "_gripper_drive_is_angular", True) else 1.0
                    target_v = float(gattr.Get()) * grip_scale
                    full_target[0, grip_idx] = target_v
                    if right_grip_idx is not None and not getattr(player, "_gripper_drive_is_angular", True):
                        full_target[0, right_grip_idx] = -target_v
            art.set_joint_position_targets(full_target)

            if step_i == belt_halt_step:
                _set_belt_vel((0.0, 0.0, 0.0))
            elif step_i == belt_resume_step and original_belt_v is not None:
                _set_belt_vel(original_belt_v)

            world.step(render=False)
            player.advance(PHYSICS_DT_S)

            # Pose probes.
            peg_pos_arr, _ = peg.get_world_poses()
            peg_xyz = (float(peg_pos_arr[0][0]), float(peg_pos_arr[0][1]), float(peg_pos_arr[0][2]))
            peg_vel_arr = peg.get_linear_velocities()
            peg_vel = (float(peg_vel_arr[0][0]), float(peg_vel_arr[0][1]), float(peg_vel_arr[0][2]))
            wrist_t = _world_translate(stage, WRIST_3_LINK)
            l_t = _world_translate(stage, LEFT_FINGER)
            r_t = _world_translate(stage, RIGHT_FINGER)

            # Joint pos / vel from articulation.
            jp_arr = art.get_joint_positions()
            jv_arr = art.get_joint_velocities()
            joint_pos = tuple(float(jp_arr[0][joint_indices[i]]) for i in range(6))
            joint_vel = tuple(float(jv_arr[0][joint_indices[i]]) for i in range(6))

            # Finite-diff joint accel and jerk.
            if prev_jvel is not None:
                joint_accel = tuple((joint_vel[i] - prev_jvel[i]) / PHYSICS_DT_S for i in range(6))
            else:
                joint_accel = tuple(0.0 for _ in range(6))
            if prev_jaccel is not None:
                joint_jerk = tuple((joint_accel[i] - prev_jaccel[i]) / PHYSICS_DT_S for i in range(6))
            else:
                joint_jerk = tuple(0.0 for _ in range(6))

            # EE linear velocity from wrist_3 finite diff.
            if prev_wrist is not None and wrist_t is not None:
                ee_lin_vel = ((wrist_t[0] - prev_wrist[0]) / PHYSICS_DT_S,
                              (wrist_t[1] - prev_wrist[1]) / PHYSICS_DT_S,
                              (wrist_t[2] - prev_wrist[2]) / PHYSICS_DT_S)
            else:
                ee_lin_vel = (0.0, 0.0, 0.0)
            ee_speed = math.sqrt(ee_lin_vel[0]**2 + ee_lin_vel[1]**2 + ee_lin_vel[2]**2)

            # EE acceleration (Cartesian) from finite diff of ee_lin_vel.
            if prev_ee_v is not None:
                ee_accel = ((ee_lin_vel[0] - prev_ee_v[0]) / PHYSICS_DT_S,
                            (ee_lin_vel[1] - prev_ee_v[1]) / PHYSICS_DT_S,
                            (ee_lin_vel[2] - prev_ee_v[2]) / PHYSICS_DT_S)
            else:
                ee_accel = (0.0, 0.0, 0.0)
            ee_accel_mag = math.sqrt(ee_accel[0]**2 + ee_accel[1]**2 + ee_accel[2]**2)

            # Contacts.
            contacts = contact_source.query_contacts()
            pad_L = pad_R = floor_c = belt_c = fixture_c = False
            max_pad_pen_mm = 0.0
            for c in contacts:
                a, b = c.prim_a, c.prim_b
                if PEG_PATH in a:    other = b
                elif PEG_PATH in b:  other = a
                else:                continue
                cls = _classify_peg_pair(other)
                if cls == "pad_L":   pad_L = True;   max_pad_pen_mm = max(max_pad_pen_mm, float(c.penetration_depth) * 1000.0)
                if cls == "pad_R":   pad_R = True;   max_pad_pen_mm = max(max_pad_pen_mm, float(c.penetration_depth) * 1000.0)
                if cls == "floor":   floor_c = True
                if cls == "belt":    belt_c = True
                if cls == "fixture": fixture_c = True

            trace.append({
                "step":          step_i,
                "peg_xyz":       peg_xyz,
                "peg_vel":       peg_vel,
                "wrist_3_xyz":   wrist_t,
                "left_finger_xyz":  l_t,
                "right_finger_xyz": r_t,
                "pad_L_contact": pad_L,
                "pad_R_contact": pad_R,
                "floor_contact": floor_c,
                "belt_contact":  belt_c,
                "fixture_contact": fixture_c,
                "pad_pen_mm":    max_pad_pen_mm,
                # Motion-quality fields (Phase 3O).
                "joint_pos":     joint_pos,
                "joint_vel":     joint_vel,
                "joint_accel":   joint_accel,
                "joint_jerk":    joint_jerk,
                "ee_lin_vel":    ee_lin_vel,
                "ee_speed_mps":  ee_speed,
                "ee_accel":      ee_accel,
                "ee_accel_mag":  ee_accel_mag,
            })

            prev_wrist  = wrist_t
            prev_jvel   = joint_vel
            prev_jaccel = joint_accel
            prev_ee_v   = ee_lin_vel
    finally:
        contact_source.close()

    # Build summary.
    summary: dict[str, Any] = {
        "grasp_close_step":     grasp_close_step,
        "lift_end_step":        lift_end_step,
        "place_end_step":       place_end_step,
        "release_start_step":   release_start_step,
        "release_end_step":     release_end_step,
        "n_steps":              n_steps,
    }

    # Sustained-contact detection.
    consec = 0; acquired = None
    for r in trace:
        if r["pad_L_contact"] and r["pad_R_contact"]:
            consec += 1
            if consec >= SUSTAINED_CONTACT_STEPS and acquired is None:
                acquired = r["step"] - SUSTAINED_CONTACT_STEPS + 1
        else:
            consec = 0
    summary["grasp_acquired_step"] = acquired
    lost = None
    if acquired is not None:
        loss_consec = 0
        steps_threshold = int(round(MAX_PRE_RELEASE_BREAK_S / PHYSICS_DT_S))
        for r in trace:
            if r["step"] <= acquired:                       continue
            if r["step"] >= release_start_step:             break
            if not r["pad_L_contact"] and not r["pad_R_contact"]:
                loss_consec += 1
                if loss_consec >= steps_threshold:
                    lost = r["step"] - steps_threshold + 1
                    break
            else:
                loss_consec = 0
    summary["grasp_lost_in_transport_step"] = lost

    floor_or_belt_first = None; fixture_first = None
    for r in trace:
        if r["step"] < grasp_close_step:                    continue
        if floor_or_belt_first is None and (r["floor_contact"] or r["belt_contact"]):
            floor_or_belt_first = r["step"]
        if fixture_first is None and r["fixture_contact"]:
            fixture_first = r["step"]
    summary["floor_or_belt_first_post_close_step"] = floor_or_belt_first
    summary["fixture_first_post_close_step"]      = fixture_first

    wmax = max((r["wrist_3_xyz"][2] for r in trace if r["wrist_3_xyz"]), default=0.0)
    wmax_step = max(((r["wrist_3_xyz"][2], r["step"]) for r in trace if r["wrist_3_xyz"]))[1]
    pmax = max(r["peg_xyz"][2] for r in trace)
    pmax_step = max(((r["peg_xyz"][2], r["step"]) for r in trace))[1]
    summary["wrist_3_max_z_m"] = wmax
    summary["wrist_3_max_z_step"] = wmax_step
    summary["peg_max_z_m"] = pmax
    summary["peg_max_z_step"] = pmax_step

    transport = [r for r in trace if lift_end_step <= r["step"] < place_end_step
                                  and (r["pad_L_contact"] or r["pad_R_contact"])]
    summary["pad_pen_min_during_transport_mm"] = min((r["pad_pen_mm"] for r in transport),
                                                     default=0.0)
    summary["pad_pen_max_during_transport_mm"] = max((r["pad_pen_mm"] for r in transport),
                                                     default=0.0)

    # Phase 3O motion-quality summary.
    j_vel_peak_per = [0.0] * 6
    j_accel_peak_per = [0.0] * 6
    j_jerk_peak_per = [0.0] * 6
    ee_speed_peak = 0.0
    ee_speed_peak_step = -1
    ee_accel_peak = 0.0
    ee_accel_peak_step = -1
    wrist_reach_peak = 0.0     # horizontal distance from base (shoulder x=0, y=0)
    wrist_reach_peak_step = -1
    cart_path_len = 0.0
    prev_w = None
    for r in trace:
        for i in range(6):
            if abs(r["joint_vel"][i])   > j_vel_peak_per[i]:   j_vel_peak_per[i]   = abs(r["joint_vel"][i])
            if abs(r["joint_accel"][i]) > j_accel_peak_per[i]: j_accel_peak_per[i] = abs(r["joint_accel"][i])
            if abs(r["joint_jerk"][i])  > j_jerk_peak_per[i]:  j_jerk_peak_per[i]  = abs(r["joint_jerk"][i])
        if r["ee_speed_mps"] > ee_speed_peak:
            ee_speed_peak = r["ee_speed_mps"]; ee_speed_peak_step = r["step"]
        if r["ee_accel_mag"] > ee_accel_peak:
            ee_accel_peak = r["ee_accel_mag"]; ee_accel_peak_step = r["step"]
        w = r["wrist_3_xyz"]
        if w is not None:
            # Reach distance from the UR10e base axis (world x=0, y=0; arm
            # mounted at z=0.80, so the relevant reach is horizontal).
            r_h = math.sqrt(w[0]**2 + w[1]**2)
            if r_h > wrist_reach_peak:
                wrist_reach_peak = r_h; wrist_reach_peak_step = r["step"]
            if prev_w is not None:
                dx = w[0] - prev_w[0]; dy = w[1] - prev_w[1]; dz = w[2] - prev_w[2]
                cart_path_len += math.sqrt(dx*dx + dy*dy + dz*dz)
            prev_w = w

    summary["joint_vel_peak_per_joint_rad_s"]   = j_vel_peak_per
    summary["joint_accel_peak_per_joint_rad_s2"] = j_accel_peak_per
    summary["joint_jerk_peak_per_joint_rad_s3"]  = j_jerk_peak_per
    summary["joint_vel_peak_rad_s"]   = max(j_vel_peak_per)
    summary["joint_accel_peak_rad_s2"] = max(j_accel_peak_per)
    summary["joint_jerk_peak_rad_s3"]  = max(j_jerk_peak_per)
    summary["ee_speed_peak_mps"]      = ee_speed_peak
    summary["ee_speed_peak_step"]     = ee_speed_peak_step
    summary["ee_accel_peak_m_s2"]     = ee_accel_peak
    summary["ee_accel_peak_step"]     = ee_accel_peak_step
    summary["wrist_reach_horizontal_peak_m"] = wrist_reach_peak
    summary["wrist_reach_horizontal_peak_step"] = wrist_reach_peak_step
    summary["cartesian_path_length_m"] = cart_path_len

    return summary, trace
