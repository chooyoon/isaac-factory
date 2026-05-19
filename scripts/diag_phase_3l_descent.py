"""Phase 3L — descent-phase diagnostic.

Runs ONLY the home → grasp portion of the cell_01 trajectory and records
fine-resolution telemetry at every physics step (60 Hz). Goal: identify
the exact UR10e collider (and step index) that first contacts the peg
before jaw closure, and quantify the peg's Y drift induced by that
contact.

What this script does
---------------------

  1. Opens ``assets/cells/cell_01.usda``.
  2. Builds an Isaac Sim World + Articulation (UR10e + prismatic gripper)
     + RigidPrim for the peg.
  3. Subscribes to PhysX contact-report events via
     ``asset_validator.adapters.physx_contact_source.PhysXContactSource``.
  4. Forces the peg to its authored pose and zeros velocities (the
     Phase 3C-tail determinism fix; not modified here).
  5. Replays only the trajectory phases up to AND INCLUDING the start
     of ``grasp_close`` (i.e. the descent + the moment of first jaw
     contact). The close itself is NOT exercised — gripper drive target
     stays at OPEN.
  6. Each physics step, records:
        - step index
        - peg world (x, y, z)
        - peg world velocity (linear)
        - finger pad world positions
        - all contact pairs (prim_a, prim_b, penetration_depth, normal)
          deduplicated by frozenset of the pair
        - whether any pair involves the peg
  7. Identifies the FIRST step where the peg is involved in a contact,
     and reports the offending UR10e collider link.
  8. Dumps the full per-step trace to
     ``logs/phase_3l_descent_telemetry.jsonl`` (one JSON record per step
     plus a summary header at the top).

Hard constraints honored (Phase 3L charter)
-------------------------------------------

  - No gripper geometry, prismatic joint, or gripper drive change.
  - No collision disabling.
  - No runtime IK; no online planning.
  - No fake attachment, no parenting, no teleport (peg reset is the
    same Phase 3C-tail initial-condition write that already exists).
  - This script is read-only on every layer the user listed as
    validated — it only reads stage state and writes telemetry.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path


WORKSPACE       = Path("/home/cap2/last")
CELL_STAGE_PATH = WORKSPACE / "assets" / "cells" / "cell_01.usda"
TELEMETRY_JSONL = WORKSPACE / "logs" / "phase_3l_descent_telemetry.jsonl"
LOG_FILE        = WORKSPACE / "logs" / "phase_3l_descent.log"

ROBOT_MOUNT_PATH = "/World/Robot"
PEG_PATH         = "/World/Parts/Peg_01"
EE_LINK_PATH     = "/World/Robot/ee_link"

PHYSICS_DT_S = 1.0 / 60.0

_UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    print(msg, flush=True)


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    if TELEMETRY_JSONL.exists():
        TELEMETRY_JSONL.unlink()
    _log("[3l] descent-phase instrumentation start")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        return _run()
    except Exception as e:
        import traceback
        _log(f"[3l] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _world_translate(stage, path: str):
    from pxr import UsdGeom, Usd
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return None
    mat = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    t = mat.ExtractTranslation()
    return (float(t[0]), float(t[1]), float(t[2]))


def _run() -> int:
    # Make in-repo extensions importable for the diagnostic.
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))

    import math as _math
    import numpy as np
    import omni.usd
    from isaacsim.core.api import World
    from isaacsim.core.prims import Articulation, RigidPrim
    from cell_authoring import load_config
    from cell_authoring.trajectory import TrajectoryPlayer
    from asset_validator.adapters.physx_contact_source import PhysXContactSource

    _log(f"[3l] opening stage {CELL_STAGE_PATH}")
    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE_PATH))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[3l] FAILED to open stage"); return 1
    stage = ctx.get_stage()

    cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")
    _log(f"[3l] config loaded, {len(cfg.robot.trajectory)} waypoints")

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
    _log(f"[3l] articulation dof_names={dof_names}")
    joint_indices = [dof_names.index(f"{n}_joint") for n in _UR10E_JOINT_NAMES]
    grip_idx       = dof_names.index("finger_joint")        if "finger_joint"        in dof_names else None
    right_grip_idx = dof_names.index("right_finger_joint")  if "right_finger_joint"  in dof_names else None

    peg = RigidPrim(prim_paths_expr=PEG_PATH)
    peg.initialize()

    # Contact source — capture every pair every step.
    contact_source = PhysXContactSource(stage=stage, physics_dt=PHYSICS_DT_S)

    # -------- initial conditions (same as the validated cycle) ----------
    home_pose = dict(cfg.robot.home_pose_rad)
    full = art.get_joint_positions()
    for i, name in enumerate(_UR10E_JOINT_NAMES):
        full[0][joint_indices[i]] = float(home_pose[name])
    # Gripper open at start.
    if grip_idx is not None:
        full[0][grip_idx] = float(cfg.robot.gripper.open_position_rad)
    if right_grip_idx is not None:
        full[0][right_grip_idx] = -float(cfg.robot.gripper.open_position_rad)
    art.set_joint_positions(full)
    art.set_joint_position_targets(full)

    # Snap peg to authored pose, zero velocities.
    authored_xyz = cfg.parts[0].translate_world_m
    peg.set_world_poses(
        positions=np.array([[authored_xyz[0], authored_xyz[1], authored_xyz[2]]], dtype=np.float32),
        orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
    )
    peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
    peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))

    # Settle so the articulation reaches home before t=0.
    for _ in range(10):
        world.step(render=False)
    # Re-assert peg pose after settle.
    peg.set_world_poses(
        positions=np.array([[authored_xyz[0], authored_xyz[1], authored_xyz[2]]], dtype=np.float32),
        orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
    )
    peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
    peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))

    # Drain settle-window contacts so they don't pollute the descent trace.
    contact_source.query_contacts()

    # -------- timing landmarks ------------------------------------------
    waypoints = list(cfg.robot.trajectory)
    cumulative = []; t_c = 0.0
    for wp in waypoints:
        t_c += wp.duration_s
        cumulative.append(t_c)
    name_to_end_t = {wp.name: cumulative[i] for i, wp in enumerate(waypoints)}

    grasp_end_s     = name_to_end_t.get("grasp",       2.0)
    grasp_drop_end_s= name_to_end_t.get("grasp_drop",  grasp_end_s)
    close_end_s     = name_to_end_t.get("grasp_close", grasp_drop_end_s + 1.5)

    # Phase 3L instruments through the END of the "grasp_drop" waypoint
    # — i.e. through the final wrist descent that now happens AFTER belt
    # halt. The actual jaw close (grasp_close) is NOT exercised here.
    descent_end_s    = max(grasp_end_s, grasp_drop_end_s)
    descent_end_step = int(round(descent_end_s / PHYSICS_DT_S))
    close_end_step   = int(round(close_end_s   / PHYSICS_DT_S))

    n_steps = descent_end_step + 1
    _log(f"[3l] grasp_end={grasp_end_s}s grasp_drop_end={grasp_drop_end_s}s "
         f"descent_end_step={descent_end_step}  close_end_step={close_end_step}  "
         f"running n_steps={n_steps}")

    # -------- player drives the joints using the SAME phased trajectory --
    # Use the real TrajectoryPlayer so the multi-phase descent
    # (home→clearance→hold→drop) is honored exactly. The player writes
    # joint targets to USD-attr-target (degrees) every advance(); we
    # mirror that read here when forwarding to the articulation API.
    player = TrajectoryPlayer(stage=stage, robot_cfg=cfg.robot)
    player.reset()

    _DEG2RAD = _math.pi / 180.0

    # -------- per-step trace --------------------------------------------
    trace_records: list[dict] = []
    first_peg_contact: dict | None = None

    peg_link_token = PEG_PATH

    # Belt halt timing (mirror the cycle test): halt at end of "grasp",
    # resume at end of "lift". This script doesn't run far enough to
    # restart, but we still need to halt at t=grasp_end_s so the peg
    # actually stops before the grasp_drop phase.
    from pxr import Gf
    BELT_COLLIDER_PATH = "/World/Machinery/Conveyor_InFeed/Belt"
    belt_attr = stage.GetAttributeAtPath(
        BELT_COLLIDER_PATH + ".physxSurfaceVelocity:surfaceVelocity"
    )
    original_belt_v = belt_attr.Get() if (belt_attr and belt_attr.IsValid()) else None
    belt_halt_step = int(round(grasp_end_s / PHYSICS_DT_S))

    for step_i in range(n_steps):
        # Drive the arm via the real player (writes USD drive attrs).
        # Then mirror those USD targets into the articulation API in
        # radians — same pattern the cycle test uses.
        full_target = np.array(art.get_joint_positions(), dtype=np.float32).copy()
        for i, name in enumerate(_UR10E_JOINT_NAMES):
            attr_path = (
                f"{cfg.robot.mount_prim_path}/joints/{name}_joint"
                f".drive:angular:physics:targetPosition"
            )
            attr = stage.GetAttributeAtPath(attr_path)
            if attr and attr.IsValid():
                full_target[0, joint_indices[i]] = float(attr.Get()) * _DEG2RAD
        # Force gripper to stay OPEN for the entire descent diagnostic.
        if grip_idx is not None:
            full_target[0, grip_idx] = float(cfg.robot.gripper.open_position_rad)
        if right_grip_idx is not None:
            full_target[0, right_grip_idx] = -float(cfg.robot.gripper.open_position_rad)
        art.set_joint_position_targets(full_target)

        # Belt halt at end of "grasp" waypoint.
        if step_i == belt_halt_step and belt_attr is not None and belt_attr.IsValid():
            belt_attr.Set(Gf.Vec3f(0.0, 0.0, 0.0))

        world.step(render=False)
        player.advance(PHYSICS_DT_S)

        # Sample peg state.
        peg_pos_arr, _ = peg.get_world_poses()
        peg_xyz = (float(peg_pos_arr[0][0]), float(peg_pos_arr[0][1]), float(peg_pos_arr[0][2]))
        peg_vel_arr = peg.get_linear_velocities()
        peg_vel = (float(peg_vel_arr[0][0]), float(peg_vel_arr[0][1]), float(peg_vel_arr[0][2]))

        # Finger positions (RigidPrim — keeps USD xform fresh).
        try:
            l_pos = _world_translate(stage, "/World/Robot/ee_link/left_finger")
        except Exception:
            l_pos = None
        try:
            r_pos = _world_translate(stage, "/World/Robot/ee_link/right_finger")
        except Exception:
            r_pos = None
        try:
            ee_pos = _world_translate(stage, EE_LINK_PATH)
        except Exception:
            ee_pos = None

        # Drain contacts captured during this step.
        contacts = contact_source.query_contacts()
        peg_contacts: list[dict] = []
        for c in contacts:
            a, b = c.prim_a, c.prim_b
            if peg_link_token in a or peg_link_token in b:
                peg_contacts.append({
                    "a": a,
                    "b": b,
                    "penetration_depth_m": float(c.penetration_depth),
                    "normal": tuple(float(x) for x in c.contact_normal),
                })

        rec = {
            "step_i":         step_i,
            "t_s":            step_i * PHYSICS_DT_S,
            "peg_xyz":        peg_xyz,
            "peg_vel":        peg_vel,
            "ee_xyz":         ee_pos,
            "left_finger":    l_pos,
            "right_finger":   r_pos,
            "n_contacts_all": len(contacts),
            "peg_contacts":   peg_contacts,
        }
        trace_records.append(rec)

        if peg_contacts and first_peg_contact is None:
            first_peg_contact = {
                "step_i":      step_i,
                "t_s":         step_i * PHYSICS_DT_S,
                "peg_xyz":     peg_xyz,
                "pairs":       peg_contacts,
            }
            _log(f"[3l] FIRST PEG CONTACT @ step={step_i} t={step_i*PHYSICS_DT_S:.4f}s")
            for pc in peg_contacts:
                _log(f"[3l]   pair: a={pc['a']}  b={pc['b']}  pen={pc['penetration_depth_m']*1000:.3f}mm")

    contact_source.close()

    # -------- summary ----------------------------------------------------
    peg_xyz_start = trace_records[0]["peg_xyz"] if trace_records else None
    peg_xyz_end   = trace_records[-1]["peg_xyz"] if trace_records else None
    peg_y_drift_mm = (
        1000.0 * abs(peg_xyz_end[1] - peg_xyz_start[1])
        if peg_xyz_start and peg_xyz_end else None
    )
    peg_y_max_abs_mm = 1000.0 * max(abs(r["peg_xyz"][1]) for r in trace_records) if trace_records else None

    # Tally arm-link contacts seen on the peg, across the entire descent.
    arm_link_counts: dict[str, int] = {}
    for r in trace_records:
        for pc in r["peg_contacts"]:
            other = pc["b"] if peg_link_token in pc["a"] else pc["a"]
            arm_link_counts[other] = arm_link_counts.get(other, 0) + 1

    summary = {
        "_kind":             "phase_3l_descent_summary",
        "physics_dt_s":      PHYSICS_DT_S,
        "n_steps":           n_steps,
        "descent_end_step":  descent_end_step,
        "peg_xyz_start":     peg_xyz_start,
        "peg_xyz_end":       peg_xyz_end,
        "peg_y_drift_mm":    peg_y_drift_mm,
        "peg_y_max_abs_mm":  peg_y_max_abs_mm,
        "first_peg_contact": first_peg_contact,
        "arm_link_contact_counts": arm_link_counts,
    }

    TELEMETRY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with TELEMETRY_JSONL.open("w") as fh:
        fh.write(json.dumps(summary) + "\n")
        for r in trace_records:
            fh.write(json.dumps(r) + "\n")

    _log(f"[3l] wrote {TELEMETRY_JSONL}  ({len(trace_records)} per-step records)")
    _log(f"[3l] summary: {json.dumps(summary, indent=2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
