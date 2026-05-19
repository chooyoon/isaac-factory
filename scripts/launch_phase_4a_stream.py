"""Phase 4A live WebRTC streaming — human-observer motion review.

Loops the validated PickPlaceTask through the Phase 4A
``cell_authoring.tasks.TaskExecutor`` under alternating SAFE and
NOMINAL profiles, so a remote operator can connect with Omniverse
Streaming Client and watch motion quality side-by-side. A small
``omni.ui`` HUD window shows the current task phase, profile, outcome,
grasp state, wrist_3 z, and cycle counter.

Per cycle:
    * the executor produces a TaskResult (validated against Phase
      3M/N/O/P gates via the UnifiedValidator)
    * a ReplayPackage is written to
      logs/phase_4a_stream/<cycle_index>__<profile>/
    * a one-line summary appears in stdout

Constraints honored
-------------------

* The executor is used as-is. No bypass of the task abstraction. The
  only addition is the ``step_observer`` callback the executor
  already supports (Phase 4A small additive change, regression-clean).
* No physics / trajectory / gripper / profile-spec parameter is
  modified at runtime.
* The HUD writes only via omni.ui labels. If omni.ui is unavailable
  in this Kit build, the script silently falls back to stdout-only
  reporting.
"""

from __future__ import annotations

import math
import os
import signal
import sys
import time
from pathlib import Path


WORKSPACE  = Path("/home/cap2/last")
CELL_STAGE = WORKSPACE / "assets" / "cells" / "cell_01.usda"
LOG_FILE   = WORKSPACE / "logs" / "phase_4a_stream.log"
PKG_ROOT   = WORKSPACE / "logs" / "phase_4a_stream"

PHYSICS_DT_S = 1.0 / 60.0

CAMERA_PATH = "/World/VisCam"
RENDER_W, RENDER_H = 1280, 720


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
    print(msg, flush=True)


_LIVESTREAM_CONFIG = {
    "width":         1280,
    "height":        720,
    "window_width":  1920,
    "window_height": 1080,
    "headless":      True,
    "hide_ui":       False,
    "renderer":      "RaytracedLighting",
    "display_options": 3286,
}


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    PKG_ROOT.mkdir(parents=True, exist_ok=True)
    _log("[4a-stream] boot — WebRTC streaming + Phase 4A executor + SAFE/NOMINAL loop")
    _log(f"[4a-stream] cell stage = {CELL_STAGE}")
    _log(f"[4a-stream] replay packages → {PKG_ROOT}")

    from isaacsim import SimulationApp
    kit = SimulationApp(launch_config=_LIVESTREAM_CONFIG)

    # Enable the NVCF WebRTC livestream service.
    try:
        from isaacsim.core.utils.extensions import enable_extension
        kit.set_setting("/app/window/drawMouse", True)
        enable_extension("omni.services.livestream.nvcf")
        _log("[4a-stream] enabled omni.services.livestream.nvcf")
    except Exception as e:
        _log(f"[4a-stream] WARN: could not enable livestream ext: {e}")

    sigint_received = {"flag": False}

    def _on_sigint(signum, frame):
        sigint_received["flag"] = True
        _log("[4a-stream] received SIGINT; will exit at next cycle boundary")
    signal.signal(signal.SIGINT,  _on_sigint)
    signal.signal(signal.SIGTERM, _on_sigint)

    try:
        return _run(kit, sigint_received)
    except Exception as e:
        import traceback
        _log(f"[4a-stream] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        try:
            kit.close()
        except Exception:
            pass


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


class _Overlay:
    """Tiny ``omni.ui`` HUD. Silently degrades to a no-op if omni.ui
    can't open a Window in this Kit build."""

    def __init__(self) -> None:
        self.window = None
        self.labels = {}
        try:
            import omni.ui as ui
            self.window = ui.Window(
                "Phase 4A — Operator HUD",
                width=380, height=300,
                position_x=20, position_y=20,
                dockPreference=ui.DockPreference.LEFT_BOTTOM,
            )
            with self.window.frame:
                with ui.VStack(spacing=4):
                    for key, prefix in (
                        ("task_id",        "task        : "),
                        ("profile",        "profile     : "),
                        ("cycle_n",        "cycle       : "),
                        ("phase_name",     "phase       : "),
                        ("step",           "step        : "),
                        ("wrist_z",        "wrist_3 z   : "),
                        ("grasp_state",    "gripper     : "),
                        ("last_outcome",   "last_outcome: "),
                        ("pass_count",     "pass / total: "),
                    ):
                        lbl = ui.Label(prefix + "—", style={"font_size": 14, "color": 0xFFD0D0D0})
                        self.labels[key] = (prefix, lbl)
            _log("[4a-stream] omni.ui HUD created")
        except Exception as e:
            _log(f"[4a-stream] omni.ui HUD unavailable: {e} — falling back to stdout HUD")

    def set(self, key: str, value: str) -> None:
        if self.window is None:
            return
        entry = self.labels.get(key)
        if entry is None:
            return
        prefix, lbl = entry
        try:
            lbl.text = prefix + value
        except Exception:
            pass


def _run(kit, sigint_received) -> int:
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))

    import omni.usd
    from isaacsim.core.api import World
    from cell_authoring import load_config
    from cell_authoring.tasks import (
        TaskExecutor, TrajectoryProfile,
        PickPlaceTask, PickSource, PlaceTarget,
        PrismaticClampGrasp, JointSpaceLerpTransport, OpenJawRelease,
        UnifiedValidator, ReplayPackage,
    )

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[4a-stream] FAIL: cannot open cell stage"); return 1
    stage = ctx.get_stage()

    cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")
    _author_view_camera(stage)
    try:
        from omni.kit.viewport.utility import get_active_viewport
        vp = get_active_viewport()
        if vp is not None:
            vp.camera_path = CAMERA_PATH
            _log(f"[4a-stream] viewport camera = {CAMERA_PATH}")
    except Exception as e:
        _log(f"[4a-stream] WARN: could not bind view camera: {e}")

    overlay = _Overlay()

    world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    world.reset()
    world.play()

    # Build the validated task once. The executor reuses persistent
    # PhysX handles across cycles — same pattern as the Phase 3P
    # harness, same determinism guarantee.
    task = PickPlaceTask(
        task_id="cell_01_validated_pick_place",
        pick_source=PickSource(
            object_id="Peg_01",
            world_pose_m=(-0.80, 0.0, 0.701),
            source_kind="conveyor",
            metadata={"conveyor_id": "Conveyor_InFeed"},
        ),
        place_target=PlaceTarget(
            fixture_id="WorkFixture_01",
            world_pose_m=(0.65, 0.0, 0.65),
            target_kind="fixture_top",
            placement_tolerance_xy_m=0.05,
        ),
        grasp_strategy=PrismaticClampGrasp(),
        transport_strategy=JointSpaceLerpTransport(profile_id="nominal"),
        release_strategy=OpenJawRelease(),
    )

    executor  = TaskExecutor(world=world, stage=stage, cell_cfg=cfg)
    validator = UnifiedValidator()

    profile_loop = [TrajectoryProfile.NOMINAL, TrajectoryProfile.SAFE]
    cycle_n   = 0
    pass_n    = 0
    last_outcome = "(none)"

    overlay.set("task_id", task.task_id)
    overlay.set("pass_count", f"{pass_n} / {cycle_n}")

    def _make_step_observer(profile_value: str, cycle_idx: int):
        # HUD labels are updated every K steps (not every tick) so that
        # omni.ui doesn't perturb the streamer's encoder budget. The
        # streamer is driven by world.step(render=True) at 60 Hz already.
        K = 6
        def _observer(step_i: int, state: dict) -> None:
            if step_i % K != 0:
                return
            overlay.set("profile",     state["profile"])
            overlay.set("cycle_n",     str(cycle_idx))
            overlay.set("phase_name",  state["phase_name"])
            overlay.set("step",        f"{step_i:>4} / {state['n_steps']}")
            wz = state.get("wrist_3_z")
            overlay.set("wrist_z",     f"{wz:+.3f} m" if wz is not None else "—")
            overlay.set("grasp_state", state.get("gripper_state", "—"))
            overlay.set("last_outcome", last_outcome)
            overlay.set("pass_count",  f"{pass_n} / {cycle_n}")
        return _observer

    _log("[4a-stream] entering loop — Ctrl-C to exit; cycles alternate NOMINAL → SAFE → ...")

    while not sigint_received["flag"]:
        cycle_n += 1
        profile = profile_loop[(cycle_n - 1) % len(profile_loop)]
        overlay.set("profile", profile.value)
        overlay.set("cycle_n", str(cycle_n))
        overlay.set("phase_name", "preparing")
        kit.update()

        t0 = time.time()
        result = executor.execute(
            task,
            profile=profile,
            seed=20260520,
            step_observer=_make_step_observer(profile.value, cycle_n),
            render=True,    # WebRTC livestream needs rendered frames
        )
        wall = time.time() - t0

        last_outcome = result.outcome.value
        if result.passed:
            pass_n += 1

        _log(f"[4a-stream] cycle {cycle_n:>3} profile={profile.value:10s}  "
             f"outcome={result.outcome.value:32s}  "
             f"peg_final=({result.peg_xyz_final[0]:+.4f},{result.peg_xyz_final[1]:+.4f},{result.peg_xyz_final[2]:+.4f})  "
             f"w3_max_z={result.wrist_3_max_z_m:.3f}  cart={result.cartesian_path_length_m:.3f}m  "
             f"wall={wall:.1f}s")

        # Persist a replay package per cycle.
        try:
            pkg_dir = PKG_ROOT / f"cycle_{cycle_n:04d}__{profile.value}"
            report  = validator.summarise([result])
            ReplayPackage(
                task=task, result=result, cell_cfg=cfg,
                profile=profile, seed=20260520, validation_report=report,
            ).write_dir(pkg_dir)
        except Exception as e:
            _log(f"[4a-stream] WARN: replay package write failed: {e}")

        overlay.set("last_outcome", last_outcome)
        overlay.set("pass_count", f"{pass_n} / {cycle_n}")

    _log(f"[4a-stream] loop exiting; total cycles = {cycle_n}, pass = {pass_n}")
    try:
        executor.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
