"""Phase 3M visualization — replay the validated pick-and-place cycle with
rendering enabled and capture viewport frames for an MP4 deliverable.

Constraints honored
-------------------

* Trajectory, physics_dt, belt timing, gripper drives, IK pose — NONE
  are modified here. The script imports the same trajectory player and
  drives the same articulation API write pattern used by the validated
  cycle test (test_cell_01_pick_place_cycle.py).
* Rendering enabled (so frames can be captured) does NOT change
  determinism — PhysX runs the same way regardless of render mode.
* Physics-debug visualization (collision meshes, joint axes, mass
  properties) is toggled via carb settings — viewport flags only, no
  physics-side parameter changes.

Output
------

  /home/cap2/last/outputs/phase_3m_visual/
    frames/                 — every captured PNG (one per 6 physics steps)
    landmarks/              — labelled screenshots at cycle landmarks
    cycle.mp4               — stitched video (30 FPS, frames at 10 Hz of sim time)
    notes.md                — motion-quality observations

This script is for review only. It is NOT part of the validation suite.
"""

from __future__ import annotations

import os
import sys
import math
from pathlib import Path


WORKSPACE      = Path("/home/cap2/last")
CELL_STAGE     = WORKSPACE / "assets" / "cells" / "cell_01.usda"
OUT_ROOT       = WORKSPACE / "outputs" / "phase_3m_visual"
FRAMES_DIR     = OUT_ROOT / "frames"
LANDMARKS_DIR  = OUT_ROOT / "landmarks"
LOG_FILE       = WORKSPACE / "logs" / "phase_3m_visualize.log"

PHYSICS_DT_S   = 1.0 / 60.0
CAPTURE_EVERY_N_STEPS = 6              # 60 Hz / 6 = 10 captures per simulated second

ROBOT_MOUNT_PATH = "/World/Robot"
EE_LINK_PATH     = "/World/Robot/ee_link"
PEG_PATH         = "/World/Parts/Peg_01"
BELT_PATH        = "/World/Machinery/Conveyor_InFeed/Belt"

CAMERA_PATH      = "/World/VisCam"
RENDER_W, RENDER_H = 1280, 720

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
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    LANDMARKS_DIR.mkdir(parents=True, exist_ok=True)
    # Clean any stale frames from a prior run so the MP4 is a clean replay.
    for p in FRAMES_DIR.glob("*.png"):
        p.unlink()
    for p in LANDMARKS_DIR.glob("*.png"):
        p.unlink()

    _log(f"[3m-viz] starting; stage={CELL_STAGE}; output={OUT_ROOT}")

    from isaacsim import SimulationApp
    # headless=True keeps Kit from trying to grab a desktop window, but
    # the RTX renderer still runs and produces frames we can capture.
    app = SimulationApp({
        "headless":  True,
        "renderer":  "RayTracedLighting",
        "width":     RENDER_W,
        "height":    RENDER_H,
    })
    try:
        return _run(app)
    except Exception as e:
        import traceback
        _log(f"[3m-viz] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


# ============================================================ helpers ==


def _world_translate(stage, path: str):
    from pxr import UsdGeom, Usd
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return None
    mat = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    t = mat.ExtractTranslation()
    return (float(t[0]), float(t[1]), float(t[2]))


def _author_view_camera(stage):
    """Add a single perspective camera looking at the work cell."""
    from pxr import UsdGeom, Sdf, Gf

    cam_prim = UsdGeom.Camera.Define(stage, Sdf.Path(CAMERA_PATH)).GetPrim()
    cam = UsdGeom.Camera(cam_prim)
    cam.CreateFocalLengthAttr().Set(28.0)        # mm
    cam.CreateClippingRangeAttr().Set(Gf.Vec2f(0.05, 50.0))

    # Position: 2.0 m off in +X, 2.0 m off in -Y, 1.8 m up. Looking
    # roughly at the work fixture / centre of the cell.
    eye    = Gf.Vec3d(2.0, -2.0, 1.8)
    target = Gf.Vec3d(0.0, 0.0, 0.85)
    up     = Gf.Vec3d(0.0, 0.0, 1.0)

    # Compute a look-at orientation manually (USD doesn't ship a helper).
    fwd = (target - eye)
    fwd = fwd / fwd.GetLength()
    right = Gf.Cross(fwd, up)
    right = right / right.GetLength()
    actual_up = Gf.Cross(right, fwd)

    # Camera in USD looks down its local -Z. Build a 3x3 with columns
    # (right, actual_up, -fwd) and convert to a quaternion.
    m = Gf.Matrix3d(
        right[0],     right[1],     right[2],
        actual_up[0], actual_up[1], actual_up[2],
        -fwd[0],      -fwd[1],      -fwd[2],
    )
    quat = m.ExtractRotation().GetQuat()

    xf = UsdGeom.Xformable(cam_prim)
    xf.ClearXformOpOrder()
    t_op = xf.AddTranslateOp()
    t_op.Set(eye)
    r_op = xf.AddOrientOp()
    r_op.Set(Gf.Quatf(
        float(quat.GetReal()),
        float(quat.GetImaginary()[0]),
        float(quat.GetImaginary()[1]),
        float(quat.GetImaginary()[2]),
    ))
    return CAMERA_PATH


def _enable_physics_debug_viz():
    """Best-effort toggle of physics-debug overlays.

    Many of these settings are version-sensitive; we apply a generous
    superset and silently skip the ones the running Kit doesn't expose.
    """
    import carb
    try:
        s = carb.settings.get_settings()
    except Exception:
        return
    debug_toggles = {
        # Generic physics-debug viz (covers older + newer keys).
        "/persistent/physics/visualizationDisplayJoints":            True,
        "/persistent/physics/visualizationDisplayMasses":            False,
        "/persistent/physics/visualizationDisplayMassProperties":    False,
        "/persistent/physics/visualizationSimulationOutput":         True,
        "/physics/visualizationDisplayJoints":                       True,
        "/physics/visualizationCollisionShapes":                     True,
        "/physics/visualizationCollisionMesh":                       True,
        # Contact normals + impulses (omni.physx.debug_visualization).
        "/physics/visualizationDisplayContacts":                     True,
        "/physics/contactNormalLength":                              0.05,
        # Joint frames (axes).
        "/physics/visualizationDisplayJointFrames":                  True,
    }
    for key, val in debug_toggles.items():
        try:
            if isinstance(val, bool):
                s.set_bool(key, val)
            elif isinstance(val, float):
                s.set_float(key, val)
            else:
                s.set(key, val)
        except Exception:
            pass


def _capture(viewport_api, out_path: Path) -> bool:
    """Schedule an async viewport capture; returns True on submit success."""
    from omni.kit.viewport.utility import capture_viewport_to_file
    try:
        capture_viewport_to_file(viewport_api, str(out_path))
        return True
    except Exception as e:
        _log(f"[3m-viz] capture failed for {out_path.name}: {e}")
        return False


# ============================================================ cycle ==


def _run(app) -> int:
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))

    import math as _math
    import numpy as np
    import omni.usd
    from isaacsim.core.api import World
    from isaacsim.core.prims import Articulation, RigidPrim
    from cell_authoring import load_config
    from cell_authoring.trajectory import TrajectoryPlayer
    from omni.kit.viewport.utility import get_active_viewport

    # Open the cell stage.
    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    if isinstance(r, tuple):
        ok = bool(r[0])
    else:
        ok = bool(r)
    if not ok:
        _log("[3m-viz] FAIL: cannot open stage"); return 1
    stage = ctx.get_stage()

    cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")

    # Author + select the view camera on the active viewport.
    cam_path = _author_view_camera(stage)
    viewport_api = get_active_viewport()
    try:
        viewport_api.camera_path = cam_path
    except Exception as e:
        _log(f"[3m-viz] note: could not bind view camera: {e}")

    _enable_physics_debug_viz()

    # World init.
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

    # ----- initial conditions (same as Phase 3M validated cycle) ------
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

    # Settle.
    for _ in range(10):
        world.step(render=True)
    peg.set_world_poses(
        positions=np.array([[authored_xyz[0], authored_xyz[1], authored_xyz[2]]], dtype=np.float32),
        orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
    )
    peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
    peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))

    # ----- belt halt control (mirrors the cycle test exactly) ---------
    from pxr import Gf
    belt_attr = stage.GetAttributeAtPath(BELT_PATH + ".physxSurfaceVelocity:surfaceVelocity")
    original_belt_v = belt_attr.Get() if (belt_attr and belt_attr.IsValid()) else None

    def _set_belt_vel(v):
        if belt_attr and belt_attr.IsValid():
            belt_attr.Set(Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])))
    if original_belt_v is not None:
        _set_belt_vel(original_belt_v)

    # ----- timing landmarks -------------------------------------------
    waypoints  = list(cfg.robot.trajectory)
    cumulative = []; t_c = 0.0
    for wp in waypoints:
        t_c += wp.duration_s
        cumulative.append(t_c)
    name_to_end_t = {wp.name: cumulative[i] for i, wp in enumerate(waypoints)}

    grasp_end_s        = name_to_end_t.get("grasp",        2.0)
    grasp_drop_end_s   = name_to_end_t.get("grasp_drop",   grasp_end_s)
    grasp_close_end_s  = name_to_end_t.get("grasp_close",  grasp_drop_end_s + 1.5)
    lift_end_s         = name_to_end_t.get("lift",         grasp_close_end_s + 1.5)
    place_end_s        = name_to_end_t.get("place",        lift_end_s + 3.5)
    release_end_s      = name_to_end_t.get("release",      place_end_s + 0.5)
    total_s            = cumulative[-1]

    belt_halt_step = int(round(grasp_end_s    / PHYSICS_DT_S))
    belt_resume_step = int(round(lift_end_s   / PHYSICS_DT_S))
    n_steps        = int(round(total_s        / PHYSICS_DT_S)) + 60

    LANDMARKS = {
        "00_t0_home_belt_running":            0,
        "01_descent_to_clearance":            int(round(0.5 / PHYSICS_DT_S)),
        "02_holding_clearance_belt_running":  int(round(1.5 / PHYSICS_DT_S)),
        "03_belt_halt_grasp_pose_held":       belt_halt_step,
        "04_final_drop_grasp_pose":           int(round(grasp_drop_end_s / PHYSICS_DT_S)),
        "05_jaw_close_complete":              int(round(grasp_close_end_s / PHYSICS_DT_S)),
        "06_lift_complete":                   int(round(lift_end_s / PHYSICS_DT_S)),
        "07_approach_place":                  int(round((lift_end_s + (place_end_s - lift_end_s) * 0.7) / PHYSICS_DT_S)),
        "08_at_place_pose":                   int(round(place_end_s / PHYSICS_DT_S)),
        "09_post_release":                    int(round(release_end_s / PHYSICS_DT_S)),
        "10_retract_above_place":             int(round((release_end_s + 1.0) / PHYSICS_DT_S)),
        "11_returning_home_belt_resumed":     int(round((release_end_s + 2.0) / PHYSICS_DT_S)),
    }
    landmark_by_step = {v: k for k, v in LANDMARKS.items()}
    _log(f"[3m-viz] n_steps={n_steps}, landmarks={LANDMARKS}")

    # ----- DOF index resolution + player ------------------------------
    player = TrajectoryPlayer(stage=stage, robot_cfg=cfg.robot)
    player.reset()

    _DEG2RAD = _math.pi / 180.0

    # ----- main loop (mirrors test_cell_01_pick_place_cycle.py) -------
    n_frames_written = 0
    for step_i in range(n_steps):
        # Write joint targets from USD drive attrs (same as cycle test).
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

        # Belt halt + resume — verbatim from cycle test.
        if step_i == belt_halt_step:
            _set_belt_vel((0.0, 0.0, 0.0))
        elif step_i == belt_resume_step and original_belt_v is not None:
            _set_belt_vel(original_belt_v)

        world.step(render=True)
        player.advance(PHYSICS_DT_S)

        # Capture: continuous + landmark.
        if step_i % CAPTURE_EVERY_N_STEPS == 0:
            out = FRAMES_DIR / f"frame_{n_frames_written:05d}.png"
            _capture(viewport_api, out)
            n_frames_written += 1
        if step_i in landmark_by_step:
            tag = landmark_by_step[step_i]
            out = LANDMARKS_DIR / f"{tag}.png"
            _capture(viewport_api, out)
            _log(f"[3m-viz] landmark {tag} @ step={step_i} t={step_i*PHYSICS_DT_S:.3f}s")

    # Drain a few extra app updates so any in-flight async captures
    # actually land on disk before SimulationApp.close().
    for _ in range(20):
        app.update()

    _log(f"[3m-viz] cycle done. continuous frames written: {n_frames_written}")
    _log(f"[3m-viz] continuous frames dir: {FRAMES_DIR}")
    _log(f"[3m-viz] landmark frames dir:   {LANDMARKS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
