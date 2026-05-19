"""Phase 3M live WebRTC streaming session.

Boots Isaac Sim 5.0 in headless WebRTC livestream mode (the canonical
``omni.services.livestream.nvcf`` path documented in
``/home/cap2/isaac-sim-5.0.0/standalone_examples/api/isaacsim.simulation_app/livestream.py``),
loads the validated Phase 3M cell, and loops the deterministic
pick-and-place cycle forever so an external client (Omniverse Streaming
Client) can connect and watch in real time.

Strict constraints honoured
---------------------------

  * Same ``TrajectoryPlayer`` + articulation-API write pattern as
    ``test_cell_01_pick_place_cycle.py`` — NO change to trajectory
    timings, physics_dt, belt-halt/resume, IK pose, or gripper drives.
  * Rendering is enabled (``world.step(render=True)``) so the frame
    encoder has content to stream; PhysX state is identical to the
    headless-validation determinism test.
  * No physics-debug overlay flags are forced from the script — leaving
    those for the connected viewer to toggle via the Kit UI.
  * Session stays alive on Ctrl-C / SIGTERM only; the cycle loops
    indefinitely otherwise.
"""

from __future__ import annotations

import os
import sys
import math
import signal
from pathlib import Path


WORKSPACE  = Path("/home/cap2/last")
CELL_STAGE = WORKSPACE / "assets" / "cells" / "cell_01.usda"
LOG_FILE   = WORKSPACE / "logs" / "phase_3m_stream.log"

PHYSICS_DT_S = 1.0 / 60.0

ROBOT_MOUNT_PATH = "/World/Robot"
PEG_PATH         = "/World/Parts/Peg_01"
BELT_PATH        = "/World/Machinery/Conveyor_InFeed/Belt"

CAMERA_PATH = "/World/VisCam"

_UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
    print(msg, flush=True)


# ───────────────────────── livestream-enabled SimulationApp ────────────

_LIVESTREAM_CONFIG = {
    "width":         1280,
    "height":        720,
    "window_width":  1920,
    "window_height": 1080,
    "headless":      True,                   # no on-screen window
    "hide_ui":       False,                  # show the Kit UI in the stream
    "renderer":      "RaytracedLighting",
    "display_options": 3286,                 # default grid + lights
}


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    _log("[3m-stream] boot — Isaac Sim WebRTC streaming session for Phase 3M")
    _log(f"[3m-stream] stage = {CELL_STAGE}")

    from isaacsim import SimulationApp
    kit = SimulationApp(launch_config=_LIVESTREAM_CONFIG)

    # Enable the NVCF WebRTC livestream service.
    try:
        from isaacsim.core.utils.extensions import enable_extension
        kit.set_setting("/app/window/drawMouse", True)
        enable_extension("omni.services.livestream.nvcf")
        _log("[3m-stream] enabled omni.services.livestream.nvcf")
    except Exception as e:
        _log(f"[3m-stream] WARN: could not enable livestream ext: {e}")

    sigint_received = {"flag": False}

    def _on_sigint(signum, frame):
        sigint_received["flag"] = True
        _log("[3m-stream] received SIGINT; will exit at next loop boundary")

    signal.signal(signal.SIGINT,  _on_sigint)
    signal.signal(signal.SIGTERM, _on_sigint)

    try:
        return _run(kit, sigint_received)
    except Exception as e:
        import traceback
        _log(f"[3m-stream] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        try:
            kit.close()
        except Exception:
            pass


# ───────────────────────── camera + scene setup ────────────────────────


def _author_view_camera(stage):
    from pxr import UsdGeom, Sdf, Gf

    cam_prim = UsdGeom.Camera.Define(stage, Sdf.Path(CAMERA_PATH)).GetPrim()
    cam = UsdGeom.Camera(cam_prim)
    cam.CreateFocalLengthAttr().Set(28.0)
    cam.CreateClippingRangeAttr().Set(Gf.Vec2f(0.05, 50.0))

    eye    = Gf.Vec3d(1.6, -1.6, 1.5)
    target = Gf.Vec3d(0.0, 0.0, 0.85)
    up     = Gf.Vec3d(0.0, 0.0, 1.0)

    fwd = (target - eye); fwd = fwd / fwd.GetLength()
    right = Gf.Cross(fwd, up); right = right / right.GetLength()
    actual_up = Gf.Cross(right, fwd)

    m = Gf.Matrix3d(
        right[0],     right[1],     right[2],
        actual_up[0], actual_up[1], actual_up[2],
        -fwd[0],      -fwd[1],      -fwd[2],
    )
    quat = m.ExtractRotation().GetQuat()

    xf = UsdGeom.Xformable(cam_prim)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(eye)
    xf.AddOrientOp().Set(Gf.Quatf(
        float(quat.GetReal()),
        float(quat.GetImaginary()[0]),
        float(quat.GetImaginary()[1]),
        float(quat.GetImaginary()[2]),
    ))
    return CAMERA_PATH


# ───────────────────────── cycle loop (mirrors validated test) ─────────


def _run(kit, sigint_received) -> int:
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))

    import math as _math
    import numpy as np
    import omni.usd
    from isaacsim.core.api import World
    from isaacsim.core.prims import Articulation, RigidPrim
    from cell_authoring import load_config
    from cell_authoring.trajectory import TrajectoryPlayer

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[3m-stream] FAIL: cannot open cell stage"); return 1
    stage = ctx.get_stage()
    _log(f"[3m-stream] stage opened")

    cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")

    _author_view_camera(stage)
    try:
        from omni.kit.viewport.utility import get_active_viewport
        vp = get_active_viewport()
        if vp is not None:
            vp.camera_path = CAMERA_PATH
            _log(f"[3m-stream] active viewport camera set to {CAMERA_PATH}")
    except Exception as e:
        _log(f"[3m-stream] WARN: could not bind viewport camera: {e}")

    world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    world.reset()
    world.play()
    _log("[3m-stream] World ready, physics playing")

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
    _log("[3m-stream] articulation + peg handles initialized")

    # Belt velocity attr (for indexed halt).
    from pxr import Gf
    belt_attr = stage.GetAttributeAtPath(BELT_PATH + ".physxSurfaceVelocity:surfaceVelocity")
    original_belt_v = belt_attr.Get() if (belt_attr and belt_attr.IsValid()) else None

    def _set_belt_vel(v):
        if belt_attr and belt_attr.IsValid():
            belt_attr.Set(Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])))

    # Cycle timing landmarks.
    waypoints  = list(cfg.robot.trajectory)
    cumulative = []; t_c = 0.0
    for wp in waypoints:
        t_c += wp.duration_s
        cumulative.append(t_c)
    name_to_end_t = {wp.name: cumulative[i] for i, wp in enumerate(waypoints)}
    grasp_end_s   = name_to_end_t.get("grasp", 2.0)
    lift_end_s    = name_to_end_t.get("lift", 5.3)
    total_s       = cumulative[-1]
    n_steps       = int(round(total_s / PHYSICS_DT_S)) + 60
    belt_halt_step   = int(round(grasp_end_s / PHYSICS_DT_S))
    belt_resume_step = int(round(lift_end_s   / PHYSICS_DT_S))
    _log(f"[3m-stream] one cycle = {total_s:.2f}s = {n_steps} steps "
         f"(belt halt @ {belt_halt_step}, resume @ {belt_resume_step})")

    home_pose = dict(cfg.robot.home_pose_rad)
    authored_xyz = cfg.parts[0].translate_world_m

    player = TrajectoryPlayer(stage=stage, robot_cfg=cfg.robot)

    _DEG2RAD = _math.pi / 180.0
    cycle_n = 0

    _log("[3m-stream] entering livestream loop — cycles will repeat until SIGINT")

    while not sigint_received["flag"]:
        cycle_n += 1
        # Reset per-cycle initial conditions (mirrors the cycle test).
        world.reset()
        world.play()
        try:
            art.initialize()
        except Exception:
            pass
        player.reset()

        full = art.get_joint_positions()
        for i, name in enumerate(_UR10E_JOINT_NAMES):
            full[0][joint_indices[i]] = float(home_pose[name])
        art.set_joint_positions(full)
        art.set_joint_position_targets(full)

        peg.set_world_poses(
            positions=np.array([[authored_xyz[0], authored_xyz[1], authored_xyz[2]]], dtype=np.float32),
            orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
        )
        peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
        peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))

        for _ in range(10):
            world.step(render=True)
            if sigint_received["flag"]:
                break
        peg.set_world_poses(
            positions=np.array([[authored_xyz[0], authored_xyz[1], authored_xyz[2]]], dtype=np.float32),
            orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
        )
        peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
        peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))
        if original_belt_v is not None:
            _set_belt_vel(original_belt_v)

        _log(f"[3m-stream] cycle {cycle_n} start")

        for step_i in range(n_steps):
            if sigint_received["flag"]:
                break

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

            world.step(render=True)
            player.advance(PHYSICS_DT_S)

            # Pump the Kit app loop so the streamer encoder + signaling
            # service can do their work between physics steps.
            kit.update()

        _log(f"[3m-stream] cycle {cycle_n} done")

    _log("[3m-stream] livestream loop exiting; shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
