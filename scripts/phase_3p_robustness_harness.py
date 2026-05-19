"""Phase 3P — robustness, repeatability, and operational-envelope harness.

Runs N pick-and-place cycles inside a single SimulationApp lifetime,
records per-cycle telemetry summary, and optionally perturbs each
cycle's initial peg pose / friction with a seeded RNG to map the
operational envelope.

Same trajectory player, articulation write pattern, indexed-belt halt,
and deterministic peg reset as the Phase 3M validated cycle. No
physics / gripper / trajectory modification.

Output: ``logs/phase_3p_robustness/<run_tag>/cycles.jsonl`` — one JSON
record per cycle plus a header summary. Each record carries the full
motion-quality summary that ``_helper_cycle_audit.run_full_cycle_audited``
already produces.

Usage examples (run under Kit Python):

  # 10-cycle deterministic-replay endurance (no perturbation)
  python.sh scripts/phase_3p_robustness_harness.py \
      --n-cycles 10 --run-tag endurance_10 --no-perturb

  # 30-cycle seeded XY-offset sweep (peg ± 5 mm randomised)
  python.sh scripts/phase_3p_robustness_harness.py \
      --n-cycles 30 --run-tag perturb_xy_5mm --seed 20260519 \
      --peg-xy-jitter-m 0.005

  # Tolerance scan — fixed offset per cycle, linearly stepped
  python.sh scripts/phase_3p_robustness_harness.py \
      --n-cycles 11 --run-tag tolerance_xscan \
      --peg-x-sweep -0.020 0.020

Hard constraints
----------------

* SimulationApp boots once. The world is reset between cycles (no app
  restart) — this is the realistic scenario for a long-running cell
  controller.
* Perturbation sweeps must be seed-deterministic. The RNG is seeded
  with ``--seed`` (default 0) and drawn once per cycle before that
  cycle's setup; no system-clock or external entropy.
* No new gripper, joint, or trajectory parameters are touched. Friction
  perturbations are read-only on the gripper USD — they only change
  PhysicsMaterial scalar attributes at runtime, not topology.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path


WORKSPACE  = Path("/home/cap2/last")
LOG_ROOT   = WORKSPACE / "logs" / "phase_3p_robustness"

ROBOT_MOUNT_PATH = "/World/Robot"
PEG_PATH         = "/World/Parts/Peg_01"
BELT_PATH        = "/World/Machinery/Conveyor_InFeed/Belt"
LEFT_FINGER      = "/World/Robot/ee_link/left_finger"
RIGHT_FINGER     = "/World/Robot/ee_link/right_finger"
WRIST_3_LINK     = "/World/Robot/wrist_3_link"
WORK_FIXTURE     = "/World/Environment/WorkFixture"
FLOOR_TOKEN      = "/World/Environment/Floor"
FINGER_MATERIAL_TOKENS = (
    "/Robotiq_2F_140/finger_material",  # local path inside the gripper USD
)

PHYSICS_DT_S = 1.0 / 60.0

_UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n-cycles",        type=int,   default=10)
    parser.add_argument("--run-tag",         type=str,   default="endurance",
                        help="output sub-directory under logs/phase_3p_robustness/")
    parser.add_argument("--seed",            type=int,   default=20260519)
    parser.add_argument("--no-perturb",      action="store_true",
                        help="deterministic replay — no jitter applied per cycle")
    parser.add_argument("--peg-xy-jitter-m", type=float, default=0.0,
                        help="random uniform peg-XY translation jitter, half-range in metres")
    parser.add_argument("--peg-yaw-jitter-rad", type=float, default=0.0,
                        help="random uniform peg-yaw jitter, half-range in radians")
    parser.add_argument("--peg-x-sweep",     nargs=2, type=float, metavar=("X_MIN", "X_MAX"),
                        help="linearly step peg X offset (m) across the cycle index")
    parser.add_argument("--peg-y-sweep",     nargs=2, type=float, metavar=("Y_MIN", "Y_MAX"),
                        help="linearly step peg Y offset (m) across the cycle index")
    parser.add_argument("--peg-yaw-sweep",   nargs=2, type=float, metavar=("YAW_MIN", "YAW_MAX"),
                        help="linearly step peg yaw (rad) across the cycle index")
    parser.add_argument("--friction-jitter-frac", type=float, default=0.0,
                        help="multiplicative random uniform jitter on gripper-pad friction "
                             "(half-range = friction × frac)")
    args = parser.parse_args()

    out_dir = LOG_ROOT / args.run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "cycles.jsonl"
    if log_path.exists():
        log_path.unlink()

    print(f"[3p] run_tag={args.run_tag}  n_cycles={args.n_cycles}  seed={args.seed}")
    print(f"[3p] output: {log_path}")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        rc = _run(app, args, log_path)
        return rc
    except Exception as e:
        import traceback
        with log_path.open("a") as fh:
            fh.write(json.dumps({"_kind": "fatal", "error": str(e),
                                 "trace": traceback.format_exc()}) + "\n")
        print(f"[3p] EXCEPTION: {e}\n{traceback.format_exc()}", file=sys.stderr)
        return 1
    finally:
        app.close()


def _sample_perturbation(args, rng, cycle_i: int, n: int) -> dict:
    """Return {peg_x_off, peg_y_off, peg_yaw_off, pad_friction_scale}
    for cycle ``cycle_i``."""
    out = {"peg_x_off": 0.0, "peg_y_off": 0.0, "peg_yaw_off": 0.0,
           "pad_friction_scale": 1.0}
    if args.no_perturb:
        return out
    # Linear sweeps win if specified (cycle index → endpoint).
    def _lin(span, i, n):
        if n <= 1:
            return 0.5 * (span[0] + span[1])
        return span[0] + (span[1] - span[0]) * (i / (n - 1))
    if args.peg_x_sweep:    out["peg_x_off"]   = _lin(args.peg_x_sweep, cycle_i, n)
    if args.peg_y_sweep:    out["peg_y_off"]   = _lin(args.peg_y_sweep, cycle_i, n)
    if args.peg_yaw_sweep:  out["peg_yaw_off"] = _lin(args.peg_yaw_sweep, cycle_i, n)
    # Jitter sweeps (independent random per cycle).
    if args.peg_xy_jitter_m > 0:
        out["peg_x_off"] += float(rng.uniform(-args.peg_xy_jitter_m, +args.peg_xy_jitter_m))
        out["peg_y_off"] += float(rng.uniform(-args.peg_xy_jitter_m, +args.peg_xy_jitter_m))
    if args.peg_yaw_jitter_rad > 0:
        out["peg_yaw_off"] += float(rng.uniform(-args.peg_yaw_jitter_rad, +args.peg_yaw_jitter_rad))
    if args.friction_jitter_frac > 0:
        lo = 1.0 - args.friction_jitter_frac
        hi = 1.0 + args.friction_jitter_frac
        out["pad_friction_scale"] = float(rng.uniform(lo, hi))
    return out


def _run(app, args, log_path: Path) -> int:
    # Path setup so we can import the existing per-tick helper.
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator" / "tests" / "unit"))

    import numpy as np
    import omni.usd
    from isaacsim.core.api import World
    from isaacsim.core.prims import Articulation, RigidPrim
    from cell_authoring import load_config
    from cell_authoring.trajectory import TrajectoryPlayer
    from asset_validator.adapters.physx_contact_source import PhysXContactSource
    from pxr import Gf, UsdPhysics

    # Open stage once.
    ctx = omni.usd.get_context()
    cell_stage_path = WORKSPACE / "assets" / "cells" / "cell_01.usda"
    r = ctx.open_stage(str(cell_stage_path))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        print("[3p] FAIL: cannot open cell stage"); return 1
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
    authored_xyz = cfg.parts[0].translate_world_m

    # Belt control.
    belt_attr = stage.GetAttributeAtPath(BELT_PATH + ".physxSurfaceVelocity:surfaceVelocity")
    original_belt_v = belt_attr.Get() if (belt_attr and belt_attr.IsValid()) else None
    def _set_belt_vel(v):
        if belt_attr and belt_attr.IsValid():
            belt_attr.Set(Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])))

    # Pad-material friction control. The friction material lives inside
    # the gripper USD; after composition its prim path is under
    # /World/Robot/ee_link/.../finger_material. Search the stage for the
    # actual composed path so a runtime friction override only touches
    # the PhysicsMaterial attribute (not gripper topology).
    pad_friction_prims = []
    for prim in stage.Traverse():
        ps = str(prim.GetPath())
        if "/finger_material" in ps:
            pad_friction_prims.append(prim)
    pad_friction_base = None
    if pad_friction_prims:
        base_attr = pad_friction_prims[0].GetAttribute("physics:staticFriction")
        if base_attr and base_attr.IsValid() and base_attr.Get() is not None:
            pad_friction_base = float(base_attr.Get())

    # Phase timings.
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
    belt_halt_step     = int(round(grasp_end_s     / PHYSICS_DT_S))
    belt_resume_step   = int(round(lift_end_s      / PHYSICS_DT_S))
    grasp_close_step   = int(round(grasp_close_end_s / PHYSICS_DT_S))
    lift_end_step      = int(round(lift_end_s      / PHYSICS_DT_S))
    place_end_step     = int(round(place_end_s     / PHYSICS_DT_S))
    release_end_step   = int(round(release_end_s   / PHYSICS_DT_S))
    release_start_step = place_end_step
    n_steps            = int(round(total_s         / PHYSICS_DT_S)) + 60

    home_pose = dict(cfg.robot.home_pose_rad)

    rng = np.random.default_rng(int(args.seed))

    # Header summary.
    with log_path.open("w") as fh:
        fh.write(json.dumps({
            "_kind":              "phase_3p_run_header",
            "run_tag":            args.run_tag,
            "n_cycles":           args.n_cycles,
            "seed":               args.seed,
            "no_perturb":         args.no_perturb,
            "peg_xy_jitter_m":    args.peg_xy_jitter_m,
            "peg_yaw_jitter_rad": args.peg_yaw_jitter_rad,
            "peg_x_sweep":        args.peg_x_sweep,
            "peg_y_sweep":        args.peg_y_sweep,
            "peg_yaw_sweep":      args.peg_yaw_sweep,
            "friction_jitter_frac": args.friction_jitter_frac,
            "pad_friction_base":  pad_friction_base,
            "authored_peg_xyz":   list(authored_xyz),
            "physics_dt_s":       PHYSICS_DT_S,
            "n_steps_per_cycle":  n_steps,
            "trajectory_total_s": total_s,
        }) + "\n")

    contact_source = PhysXContactSource(stage=stage, physics_dt=PHYSICS_DT_S)

    DEG2RAD = math.pi / 180.0

    def _apply_friction(scale: float):
        if not pad_friction_prims or pad_friction_base is None:
            return
        new_f = float(pad_friction_base * scale)
        for prim in pad_friction_prims:
            for attr_name in ("physics:staticFriction", "physics:dynamicFriction"):
                a = prim.GetAttribute(attr_name)
                if a and a.IsValid():
                    a.Set(new_f)

    # Initial belt + friction reset.
    if original_belt_v is not None:
        _set_belt_vel(original_belt_v)

    t_run_start = time.time()
    for cycle_i in range(args.n_cycles):
        t_cyc_start = time.time()

        pert = _sample_perturbation(args, rng, cycle_i, args.n_cycles)
        _apply_friction(pert["pad_friction_scale"])

        # ---------- per-cycle reset (mirrors validated cycle test) -------
        world.reset()
        world.play()
        try:
            art.initialize()
        except Exception:
            pass

        # Restore belt to original speed (it may have been halted at end
        # of previous cycle's "grasp" waypoint).
        if original_belt_v is not None:
            _set_belt_vel(original_belt_v)

        # Set arm to home pose.
        full = art.get_joint_positions()
        for i, name in enumerate(_UR10E_JOINT_NAMES):
            full[0][joint_indices[i]] = float(home_pose[name])
        art.set_joint_positions(full)
        art.set_joint_position_targets(full)

        # Reset peg with perturbation applied.
        px = float(authored_xyz[0]) + pert["peg_x_off"]
        py = float(authored_xyz[1]) + pert["peg_y_off"]
        pz = float(authored_xyz[2])
        # Convert yaw (about Z) to quaternion (w, x, y, z).
        yaw = float(pert["peg_yaw_off"])
        cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
        quat = (cy, 0.0, 0.0, sy)
        peg.set_world_poses(
            positions=np.array([[px, py, pz]], dtype=np.float32),
            orientations=np.array([[quat[0], quat[1], quat[2], quat[3]]], dtype=np.float32),
        )
        peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
        peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))

        for _ in range(10):
            world.step(render=False)
        peg.set_world_poses(
            positions=np.array([[px, py, pz]], dtype=np.float32),
            orientations=np.array([[quat[0], quat[1], quat[2], quat[3]]], dtype=np.float32),
        )
        peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
        peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))
        contact_source.query_contacts()

        # ---------- run the cycle, track per-tick salient metrics ---------
        player = TrajectoryPlayer(stage=stage, robot_cfg=cfg.robot)
        player.reset()

        # Aggregates rather than full trace (one record per cycle is enough).
        grasp_acquired_step  = None
        grasp_lost_in_transport_step = None
        floor_or_belt_first_post_close = None
        fixture_first_post_close = None
        last_left_contact_step  = None
        last_right_contact_step = None
        peg_max_z = -1e9; peg_max_z_step = -1
        wrist_3_max_z = -1e9; wrist_3_max_z_step = -1
        wrist_3_min_z = 1e9
        wrist_reach_peak = 0.0
        j_vel_peak_per   = [0.0] * 6
        j_accel_peak_per = [0.0] * 6
        ee_speed_peak    = 0.0
        ee_accel_peak    = 0.0
        cart_path_len    = 0.0
        pad_pen_min_in_transport = 1e9
        pad_pen_max_in_transport = 0.0
        peg_xyz_final = None

        SUSTAINED_STEPS  = 30
        BREAK_STEPS_THR  = int(round(0.10 / PHYSICS_DT_S))
        consec = 0; loss_consec = 0

        prev_wrist = None
        prev_jvel  = None
        prev_ee_v  = None
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
                        full_target[0, joint_indices[i]] = float(attr.Get()) * DEG2RAD
                if grip_idx is not None and player._gripper_attr_path is not None:
                    gattr = stage.GetAttributeAtPath(player._gripper_attr_path)
                    if gattr and gattr.IsValid():
                        grip_scale = DEG2RAD if getattr(player, "_gripper_drive_is_angular", True) else 1.0
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

                peg_pos_arr, _ = peg.get_world_poses()
                peg_xyz = (float(peg_pos_arr[0][0]), float(peg_pos_arr[0][1]), float(peg_pos_arr[0][2]))
                from pxr import UsdGeom, Usd
                w_prim = stage.GetPrimAtPath(WRIST_3_LINK)
                if w_prim and w_prim.IsValid():
                    wmat = UsdGeom.Xformable(w_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                    wt = wmat.ExtractTranslation()
                    wrist_xyz = (float(wt[0]), float(wt[1]), float(wt[2]))
                else:
                    wrist_xyz = None

                if peg_xyz[2] > peg_max_z:
                    peg_max_z, peg_max_z_step = peg_xyz[2], step_i
                if wrist_xyz is not None:
                    if wrist_xyz[2] > wrist_3_max_z:
                        wrist_3_max_z, wrist_3_max_z_step = wrist_xyz[2], step_i
                    if wrist_xyz[2] < wrist_3_min_z:
                        wrist_3_min_z = wrist_xyz[2]
                    rh = math.sqrt(wrist_xyz[0]**2 + wrist_xyz[1]**2)
                    if rh > wrist_reach_peak:
                        wrist_reach_peak = rh

                jp_arr = art.get_joint_positions()
                jv_arr = art.get_joint_velocities()
                jv = [float(jv_arr[0][joint_indices[i]]) for i in range(6)]
                for i in range(6):
                    if abs(jv[i]) > j_vel_peak_per[i]: j_vel_peak_per[i] = abs(jv[i])
                if prev_jvel is not None:
                    for i in range(6):
                        a_i = abs((jv[i] - prev_jvel[i]) / PHYSICS_DT_S)
                        if a_i > j_accel_peak_per[i]: j_accel_peak_per[i] = a_i
                prev_jvel = jv

                if prev_wrist is not None and wrist_xyz is not None:
                    dx = wrist_xyz[0] - prev_wrist[0]
                    dy = wrist_xyz[1] - prev_wrist[1]
                    dz = wrist_xyz[2] - prev_wrist[2]
                    seg = math.sqrt(dx*dx + dy*dy + dz*dz)
                    cart_path_len += seg
                    sp = seg / PHYSICS_DT_S
                    if sp > ee_speed_peak: ee_speed_peak = sp
                    if prev_ee_v is not None:
                        ax = (dx/PHYSICS_DT_S - prev_ee_v[0]) / PHYSICS_DT_S
                        ay = (dy/PHYSICS_DT_S - prev_ee_v[1]) / PHYSICS_DT_S
                        az = (dz/PHYSICS_DT_S - prev_ee_v[2]) / PHYSICS_DT_S
                        am = math.sqrt(ax*ax + ay*ay + az*az)
                        if am > ee_accel_peak: ee_accel_peak = am
                    prev_ee_v = (dx/PHYSICS_DT_S, dy/PHYSICS_DT_S, dz/PHYSICS_DT_S)
                if wrist_xyz is not None:
                    prev_wrist = wrist_xyz

                # Contacts.
                contacts = contact_source.query_contacts()
                pad_L = pad_R = floor_c = belt_c = fixture_c = False
                max_pad_pen_mm = 0.0
                for c in contacts:
                    a, b = c.prim_a, c.prim_b
                    if PEG_PATH in a:    other = b
                    elif PEG_PATH in b:  other = a
                    else:                continue
                    if other == LEFT_FINGER  or other.startswith(LEFT_FINGER  + "/"):
                        pad_L = True; max_pad_pen_mm = max(max_pad_pen_mm, float(c.penetration_depth)*1000.0)
                    if other == RIGHT_FINGER or other.startswith(RIGHT_FINGER + "/"):
                        pad_R = True; max_pad_pen_mm = max(max_pad_pen_mm, float(c.penetration_depth)*1000.0)
                    if BELT_PATH    in other: belt_c    = True
                    if FLOOR_TOKEN  in other: floor_c   = True
                    if WORK_FIXTURE in other: fixture_c = True

                if pad_L: last_left_contact_step = step_i
                if pad_R: last_right_contact_step = step_i
                if pad_L and pad_R:
                    consec += 1
                    if consec >= SUSTAINED_STEPS and grasp_acquired_step is None:
                        grasp_acquired_step = step_i - SUSTAINED_STEPS + 1
                else:
                    consec = 0
                if grasp_acquired_step is not None and step_i < release_start_step and step_i > grasp_acquired_step:
                    if not pad_L and not pad_R:
                        loss_consec += 1
                        if loss_consec >= BREAK_STEPS_THR and grasp_lost_in_transport_step is None:
                            grasp_lost_in_transport_step = step_i - BREAK_STEPS_THR + 1
                    else:
                        loss_consec = 0

                if step_i >= grasp_close_step:
                    if floor_or_belt_first_post_close is None and (floor_c or belt_c):
                        floor_or_belt_first_post_close = step_i
                    if fixture_first_post_close is None and fixture_c:
                        fixture_first_post_close = step_i

                if lift_end_step <= step_i < place_end_step and (pad_L or pad_R):
                    if max_pad_pen_mm < pad_pen_min_in_transport:
                        pad_pen_min_in_transport = max_pad_pen_mm
                    if max_pad_pen_mm > pad_pen_max_in_transport:
                        pad_pen_max_in_transport = max_pad_pen_mm

                if step_i == n_steps - 1:
                    peg_xyz_final = peg_xyz

        except Exception as e:
            import traceback
            print(f"[3p] cycle {cycle_i} CRASH: {e}\n{traceback.format_exc()}", file=sys.stderr)
            with log_path.open("a") as fh:
                fh.write(json.dumps({
                    "_kind":   "cycle_crash",
                    "cycle":   cycle_i,
                    "error":   str(e),
                }) + "\n")
            continue

        if pad_pen_min_in_transport >= 1e9:
            pad_pen_min_in_transport = 0.0

        rec = {
            "_kind":              "cycle_summary",
            "cycle":              cycle_i,
            "wall_clock_s":       round(time.time() - t_cyc_start, 3),
            "perturbation":       pert,
            "peg_xyz_final":      peg_xyz_final,
            "peg_max_z_m":        peg_max_z,
            "peg_max_z_step":     peg_max_z_step,
            "wrist_3_max_z_m":    wrist_3_max_z,
            "wrist_3_max_z_step": wrist_3_max_z_step,
            "wrist_3_min_z_m":    wrist_3_min_z,
            "wrist_reach_horizontal_peak_m": wrist_reach_peak,
            "joint_vel_peak_per_joint_rad_s":   j_vel_peak_per,
            "joint_vel_peak_rad_s":             max(j_vel_peak_per),
            "joint_accel_peak_per_joint_rad_s2": j_accel_peak_per,
            "joint_accel_peak_rad_s2":          max(j_accel_peak_per),
            "ee_speed_peak_mps":      ee_speed_peak,
            "ee_accel_peak_m_s2":     ee_accel_peak,
            "cartesian_path_length_m": cart_path_len,
            "pad_pen_min_during_transport_mm": pad_pen_min_in_transport,
            "pad_pen_max_during_transport_mm": pad_pen_max_in_transport,
            "grasp_acquired_step":              grasp_acquired_step,
            "grasp_lost_in_transport_step":     grasp_lost_in_transport_step,
            "last_left_pad_contact_step":       last_left_contact_step,
            "last_right_pad_contact_step":      last_right_contact_step,
            "floor_or_belt_first_post_close":   floor_or_belt_first_post_close,
            "fixture_first_post_close":         fixture_first_post_close,
            "release_start_step":               release_start_step,
            "release_end_step":                 release_end_step,
            "lift_end_step":                    lift_end_step,
            "n_steps":                          n_steps,
        }
        with log_path.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")

        print(f"[3p] cycle {cycle_i:>3}/{args.n_cycles} done  "
              f"final=({peg_xyz_final[0]:+.4f},{peg_xyz_final[1]:+.4f},{peg_xyz_final[2]:+.4f}) "
              f"w3z_max={wrist_3_max_z:.3f}  cart={cart_path_len:.3f}m  "
              f"grasp_acq={grasp_acquired_step}  lost_in_transit={grasp_lost_in_transport_step}  "
              f"wall={rec['wall_clock_s']:.1f}s")

    contact_source.close()
    print(f"[3p] run complete; total wall = {time.time() - t_run_start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
