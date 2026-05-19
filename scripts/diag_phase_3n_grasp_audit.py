"""Phase 3N — sustained-grasp truthfulness audit.

Runs the full validated Phase 3M cycle exactly as
test_cell_01_pick_place_cycle.py runs it, then on every physics tick
records:

  per_step:
    peg world (x, y, z)
    peg world velocity (vx, vy, vz)
    wrist_3 world pose
    left_finger / right_finger world pose
    peg expressed in EE-local frame  (slip detector)
    contact pairs filtered to peg, classified into:
        peg ↔ left_finger      → left pad contact bool
        peg ↔ right_finger     → right pad contact bool
        peg ↔ floor / belt     → "fell to a surface" bool
        peg ↔ work_fixture     → "on fixture" bool
        peg ↔ any robot link   → arm contact bool
    max penetration depth of any pad↔peg pair (overlap metric)

  summary:
    grasp_acquired_step:    first step left+right pad contact ≥ 0.05 s
    grasp_lost_step:        last step left+right pad contact, before sustained loss
    left_pad_contact_loss_step  / right_pad_contact_loss_step
    floor_or_belt_first_contact_step (post-grasp)
    peg_in_ee_drift_at_grasp_close / lift_end / each phase boundary
    peg_max_z (with timestamp)
    pad_separation_min_during_transport

The point is to prove with frame-accurate timing whether the peg is
RETAINED through transport or ejected.

Strict constraints honoured
---------------------------
  * Same TrajectoryPlayer + articulation-API write pattern as the
    validated cycle test. No trajectory / physics_dt / gripper drive
    / belt timing change.
  * Pure read-only instrumentation otherwise.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path


WORKSPACE       = Path("/home/cap2/last")
CELL_STAGE      = WORKSPACE / "assets" / "cells" / "cell_01.usda"
TELEMETRY_JSONL = WORKSPACE / "logs" / "phase_3n_grasp_audit.jsonl"
LOG_FILE        = WORKSPACE / "logs" / "phase_3n_grasp_audit.log"

PHYSICS_DT_S    = 1.0 / 60.0

ROBOT_MOUNT_PATH = "/World/Robot"
EE_LINK_PATH     = "/World/Robot/ee_link"
PEG_PATH         = "/World/Parts/Peg_01"
BELT_PATH        = "/World/Machinery/Conveyor_InFeed/Belt"
LEFT_FINGER      = "/World/Robot/ee_link/left_finger"
RIGHT_FINGER     = "/World/Robot/ee_link/right_finger"
WRIST_3_LINK     = "/World/Robot/wrist_3_link"
WORK_FIXTURE     = "/World/Environment/WorkFixture"
FLOOR_TOKEN      = "/World/Environment/Floor"

_UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
    print(msg, flush=True)


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    if TELEMETRY_JSONL.exists():
        TELEMETRY_JSONL.unlink()
    _log("[3n] grasp-retention audit start")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        return _run()
    except Exception as e:
        import traceback
        _log(f"[3n] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _world_transform(stage, path: str):
    """Returns ((tx,ty,tz), 3x3 rot tuple)."""
    from pxr import UsdGeom, Usd, Gf
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return None, None
    mat = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    mat = mat.RemoveScaleShear()
    t = mat.ExtractTranslation()
    rot33 = Gf.Matrix3d(mat.ExtractRotationMatrix())
    rot = tuple(tuple(float(rot33[i][j]) for j in range(3)) for i in range(3))
    return (float(t[0]), float(t[1]), float(t[2])), rot


def _in_local(parent_t, parent_rot33, child_t):
    """child position expressed in parent frame = rot^T * (child - parent)."""
    dx = child_t[0] - parent_t[0]
    dy = child_t[1] - parent_t[1]
    dz = child_t[2] - parent_t[2]
    rx = parent_rot33[0][0]*dx + parent_rot33[1][0]*dy + parent_rot33[2][0]*dz
    ry = parent_rot33[0][1]*dx + parent_rot33[1][1]*dy + parent_rot33[2][1]*dz
    rz = parent_rot33[0][2]*dx + parent_rot33[1][2]*dy + parent_rot33[2][2]*dz
    return (rx, ry, rz)


def _classify_peg_pair(other_path: str) -> str:
    o = other_path
    if o == LEFT_FINGER:                 return "pad_L"
    if o == RIGHT_FINGER:                return "pad_R"
    if "Fingertip" in o or o.startswith(LEFT_FINGER + "/"):  return "pad_L"
    if o.startswith(RIGHT_FINGER + "/"): return "pad_R"
    if BELT_PATH in o:                   return "belt"
    if FLOOR_TOKEN in o:                 return "floor"
    if WORK_FIXTURE in o:                return "fixture"
    if o.startswith(ROBOT_MOUNT_PATH):   return "robot_other"
    return "other"


def _run() -> int:
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))

    import numpy as np
    import omni.usd
    from isaacsim.core.api import World
    from isaacsim.core.prims import Articulation, RigidPrim
    from cell_authoring import load_config
    from cell_authoring.trajectory import TrajectoryPlayer
    from asset_validator.adapters.physx_contact_source import PhysXContactSource
    from pxr import Gf

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[3n] cannot open stage"); return 1
    stage = ctx.get_stage()

    cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")

    world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    world.reset()
    world.play()

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

    # ---- initial conditions (validated Phase 3M reset) ---------------
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

    # ---- belt halt control (same as cycle test) ----------------------
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
    grasp_end_s        = name_to_end_t.get("grasp", 2.0)
    grasp_close_end_s  = name_to_end_t.get("grasp_close", 3.8)
    lift_end_s         = name_to_end_t.get("lift", 5.3)
    approach_place_end_s = name_to_end_t.get("approach_place", lift_end_s + 4.0)
    place_end_s        = name_to_end_t.get("place", approach_place_end_s + 2.0)
    release_end_s      = name_to_end_t.get("release", place_end_s + 0.5)
    total_s            = cumulative[-1]

    belt_halt_step     = int(round(grasp_end_s    / PHYSICS_DT_S))
    belt_resume_step   = int(round(lift_end_s     / PHYSICS_DT_S))
    grasp_close_step   = int(round(grasp_close_end_s / PHYSICS_DT_S))
    lift_end_step      = int(round(lift_end_s     / PHYSICS_DT_S))
    approach_place_end_step = int(round(approach_place_end_s / PHYSICS_DT_S))
    place_end_step     = int(round(place_end_s    / PHYSICS_DT_S))
    release_end_step   = int(round(release_end_s  / PHYSICS_DT_S))
    n_steps            = int(round(total_s        / PHYSICS_DT_S)) + 60
    _log(f"[3n] n_steps={n_steps}  grasp_close_step={grasp_close_step}  "
         f"lift_end_step={lift_end_step}  approach_place_end_step={approach_place_end_step}  "
         f"place_end_step={place_end_step}  release_end_step={release_end_step}")

    player = TrajectoryPlayer(stage=stage, robot_cfg=cfg.robot)
    player.reset()

    _DEG2RAD = math.pi / 180.0

    # ---- main loop ---------------------------------------------------
    records = []
    last_peg = None
    left_contact_ever  = False
    right_contact_ever = False
    last_left_contact_step  = None
    last_right_contact_step = None
    floor_first_post_close  = None
    fixture_first_post_close = None
    peg_in_ee_at_close = None
    max_pen_pad_peg = 0.0
    peg_max_z = (-1e9, -1)

    for step_i in range(n_steps):
        # --- write joint + gripper targets (verbatim from cycle test) ---
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

        # --- per-step probes ------------------------------------------
        peg_pos_arr, _ = peg.get_world_poses()
        peg_xyz = (float(peg_pos_arr[0][0]), float(peg_pos_arr[0][1]), float(peg_pos_arr[0][2]))
        peg_vel_arr = peg.get_linear_velocities()
        peg_vel = (float(peg_vel_arr[0][0]), float(peg_vel_arr[0][1]), float(peg_vel_arr[0][2]))

        ee_t, ee_rot = _world_transform(stage, EE_LINK_PATH)
        wrist_t, _   = _world_transform(stage, WRIST_3_LINK)
        l_t, _       = _world_transform(stage, LEFT_FINGER)
        r_t, _       = _world_transform(stage, RIGHT_FINGER)

        peg_in_ee = _in_local(ee_t, ee_rot, peg_xyz) if (ee_t and ee_rot) else None

        # --- contacts -------------------------------------------------
        contacts = contact_source.query_contacts()
        pad_L_contact = False
        pad_R_contact = False
        belt_contact  = False
        floor_contact = False
        fixture_contact = False
        robot_other_contact = False
        peg_contact_classes = {}
        for c in contacts:
            a, b = c.prim_a, c.prim_b
            if PEG_PATH in a:
                other = b
            elif PEG_PATH in b:
                other = a
            else:
                continue
            cls = _classify_peg_pair(other)
            peg_contact_classes.setdefault(cls, []).append((other, float(c.penetration_depth)))
            if cls == "pad_L":  pad_L_contact = True
            if cls == "pad_R":  pad_R_contact = True
            if cls == "belt":   belt_contact = True
            if cls == "floor":  floor_contact = True
            if cls == "fixture": fixture_contact = True
            if cls == "robot_other": robot_other_contact = True

        # Max pad-peg penetration depth (proxy for clamp depth).
        for cls in ("pad_L", "pad_R"):
            for _, depth in peg_contact_classes.get(cls, []):
                if depth > max_pen_pad_peg:
                    max_pen_pad_peg = depth

        # Persistence tracking.
        if pad_L_contact:
            left_contact_ever  = True
            last_left_contact_step  = step_i
        if pad_R_contact:
            right_contact_ever = True
            last_right_contact_step = step_i

        # First post-close floor/fixture/belt contact tracking.
        if step_i >= grasp_close_step:
            if floor_first_post_close is None and (floor_contact or belt_contact):
                floor_first_post_close = step_i
            if fixture_first_post_close is None and fixture_contact:
                fixture_first_post_close = step_i

        # Track max-z.
        if peg_xyz[2] > peg_max_z[0]:
            peg_max_z = (peg_xyz[2], step_i)

        # Cache peg-in-ee at grasp_close end.
        if step_i == grasp_close_step and peg_in_ee is not None:
            peg_in_ee_at_close = peg_in_ee

        rec = {
            "step":             step_i,
            "t_s":              step_i * PHYSICS_DT_S,
            "peg_xyz":          peg_xyz,
            "peg_vel":          peg_vel,
            "ee_xyz":           ee_t,
            "wrist_3_xyz":      wrist_t,
            "left_finger_xyz":  l_t,
            "right_finger_xyz": r_t,
            "peg_in_ee_local":  peg_in_ee,
            "pad_L_contact":    pad_L_contact,
            "pad_R_contact":    pad_R_contact,
            "belt_contact":     belt_contact,
            "floor_contact":    floor_contact,
            "fixture_contact":  fixture_contact,
            "robot_other_contact": robot_other_contact,
            "contact_classes":  {k: len(v) for k, v in peg_contact_classes.items()},
            "max_pad_pen_mm":   max((d for cls in ("pad_L","pad_R")
                                    for _, d in peg_contact_classes.get(cls, [])), default=0.0) * 1000.0,
        }
        records.append(rec)
        last_peg = peg_xyz

    contact_source.close()

    # ---- summarise --------------------------------------------------
    # First "sustained" pad acquisition: 30 consecutive steps of both
    # left+right pad contact (= 0.5 s).
    SUSTAINED = 30
    consec = 0
    grasp_acquired_step = None
    for r in records:
        if r["pad_L_contact"] and r["pad_R_contact"]:
            consec += 1
            if consec >= SUSTAINED and grasp_acquired_step is None:
                grasp_acquired_step = r["step"] - SUSTAINED + 1
        else:
            consec = 0
    # First step AFTER grasp_acquired_step where BOTH pads break and
    # the break lasts ≥ 6 steps (0.1 s) = sustained grasp loss.
    grasp_lost_step = None
    if grasp_acquired_step is not None:
        loss_consec = 0
        for r in records:
            if r["step"] < grasp_acquired_step + SUSTAINED:
                continue
            if not r["pad_L_contact"] and not r["pad_R_contact"]:
                loss_consec += 1
                if loss_consec >= 6:
                    grasp_lost_step = r["step"] - 6 + 1
                    break
            else:
                loss_consec = 0

    # Peg-in-EE drift over time.
    drift_records = []
    if peg_in_ee_at_close is not None:
        for r in records:
            p = r["peg_in_ee_local"]
            if p is None:
                continue
            d = math.sqrt(sum((a-b)**2 for a, b in zip(p, peg_in_ee_at_close))) * 1000.0
            drift_records.append((r["step"], d))
    drift_max = max((d for _, d in drift_records), default=0.0)
    drift_at_lift_end = next((d for s, d in drift_records if s == lift_end_step), None)
    drift_at_place_end = next((d for s, d in drift_records if s == place_end_step), None)

    summary = {
        "_kind":                          "phase_3n_grasp_audit",
        "n_steps":                        n_steps,
        "grasp_close_step":               grasp_close_step,
        "lift_end_step":                  lift_end_step,
        "approach_place_end_step":        approach_place_end_step,
        "place_end_step":                 place_end_step,
        "release_end_step":               release_end_step,
        "grasp_acquired_step":            grasp_acquired_step,
        "grasp_lost_step":                grasp_lost_step,
        "last_left_pad_contact_step":     last_left_contact_step,
        "last_right_pad_contact_step":    last_right_contact_step,
        "floor_or_belt_first_post_close": floor_first_post_close,
        "fixture_first_post_close":       fixture_first_post_close,
        "peg_max_z":                      peg_max_z[0],
        "peg_max_z_step":                 peg_max_z[1],
        "peg_in_ee_at_close":             peg_in_ee_at_close,
        "peg_in_ee_drift_max_mm":         drift_max,
        "peg_in_ee_drift_at_lift_end_mm": drift_at_lift_end,
        "peg_in_ee_drift_at_place_end_mm": drift_at_place_end,
        "max_pad_peg_penetration_mm":     max_pen_pad_peg * 1000.0,
    }

    # Write JSONL.
    TELEMETRY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with TELEMETRY_JSONL.open("w") as fh:
        fh.write(json.dumps(summary) + "\n")
        for r in records:
            fh.write(json.dumps(r) + "\n")

    _log(f"[3n] wrote {TELEMETRY_JSONL} ({len(records)} per-step records)")
    _log(f"[3n] SUMMARY: {json.dumps(summary, indent=2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
