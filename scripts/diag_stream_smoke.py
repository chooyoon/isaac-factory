"""Minimal WebRTC livestream smoke test.

Goal: isolate WHICH layer of the WebRTC stack is broken when the
Phase 5 `--stream` runner produces no visible viewport.

The smoke test:
  1. Boots Isaac Sim using ``isaacsim.exp.full.streaming.kit`` (the
     dedicated streaming experience — declares omni.services.livestream
     .nvcf at startup, includes full renderer + viewport).
  2. Opens the cell USD stage.
  3. Authors and binds /World/VisCam to the active viewport.
  4. Renders for N seconds at 60 Hz with explicit ``world.step(render
     =True)`` calls so frames are produced.
  5. Logs every diagnostic surface we can reach: extension load status,
     viewport extension presence, livestream extension state, viewport
     camera path, world play state.

After the run, inspect ``logs/diag_stream_smoke.log`` to see exactly
which layer is healthy and which is broken.

Usage::

    /home/cap2/isaac-sim-5.0.0/python.sh \\
        /home/cap2/last/scripts/diag_stream_smoke.py [--duration 20]

While the smoke test is running, connect an Omniverse Streaming Client
(or a WebRTC-capable viewer) to the local stream endpoint. The default
local endpoint is typically ``ws://localhost:8211`` or via the
streaming-client's "Connect to Server" dialog using ``localhost``.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


WORKSPACE      = Path("/home/cap2/last")
ISAAC_PATH     = Path("/home/cap2/isaac-sim-5.0.0")
STREAMING_KIT  = ISAAC_PATH / "apps" / "isaacsim.exp.full.streaming.kit"
CELL_STAGE     = WORKSPACE / "assets" / "cells" / "cell_01.usda"
LOG_FILE       = WORKSPACE / "logs" / "diag_stream_smoke.log"

PHYSICS_DT_S = 1.0 / 60.0
CAMERA_PATH = "/World/VisCam"


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
    print(msg, flush=True)


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    ap = argparse.ArgumentParser(prog="diag_stream_smoke.py")
    ap.add_argument("--duration", type=float, default=20.0,
                    help="Seconds to run the render loop (default 20).")
    args = ap.parse_args()

    _log("[smoke] boot — minimal WebRTC livestream smoke test")
    _log(f"[smoke] streaming kit  = {STREAMING_KIT}")
    _log(f"[smoke] cell stage     = {CELL_STAGE}")
    _log(f"[smoke] duration       = {args.duration:.1f}s")

    if not STREAMING_KIT.is_file():
        _log(f"[smoke] FAIL: streaming kit not found at {STREAMING_KIT}")
        return 1

    from isaacsim import SimulationApp

    # NOTE: switching to isaacsim.exp.full.streaming.kit segfaults
    # SimulationApp at boot on this host (libomni.usd → libomni.graph
    # .image.core stack, 2026-05-20). Falling back to the validated
    # base.python.kit and enabling the WebRTC livestream extension
    # post-boot — the same pattern Phase 4A's stream launcher used,
    # but switching to ``omni.kit.livestream.webrtc`` (local-stream
    # capable) instead of ``omni.services.livestream.nvcf`` (NGC Cloud
    # Functions deployment only — not a local viewer endpoint).
    launch_config = {
        "headless":      True,    # no local desktop window, frames go to stream
        "hide_ui":       False,
        "width":         1280,
        "height":        720,
        "window_width":  1920,
        "window_height": 1080,
        "renderer":      "RaytracedLighting",
        "display_options": 3286,
    }
    _log(f"[smoke] SimulationApp(launch_config={launch_config}) "
         f"(default base.python.kit experience)")

    kit = SimulationApp(launch_config=launch_config)

    # Post-boot: enable the LOCAL WebRTC livestream extension.
    try:
        from isaacsim.core.utils.extensions import enable_extension
        kit.set_setting("/app/window/drawMouse", True)
        enabled = enable_extension("omni.kit.livestream.webrtc")
        _log(f"[smoke] enable_extension(omni.kit.livestream.webrtc) → {enabled!r}")
    except Exception as e:
        _log(f"[smoke] WARN: could not enable webrtc livestream ext: {e}")
    try:
        return _run(kit, args)
    except Exception as e:
        import traceback
        _log(f"[smoke] EXCEPTION: {e}\n{traceback.format_exc()}")
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


def _diagnose_extension_state(kit) -> None:
    """Log everything we can learn about extension load state."""
    _log("\n[smoke] ─── extension diagnosis ───")
    try:
        import omni.kit.app
        app = omni.kit.app.get_app()
        ext_mgr = app.get_extension_manager()
        all_exts = ext_mgr.get_extensions()
        livestream_exts = [
            (e["name"], e.get("enabled", False), e.get("version", "?"))
            for e in all_exts
            if "livestream" in e["name"].lower()
               or "webrtc" in e["name"].lower()
        ]
        _log(f"[smoke] livestream-related extensions visible to the manager:")
        for name, enabled, ver in sorted(livestream_exts):
            mark = "  ENABLED" if enabled else "  loaded "
            _log(f"  {mark}  {name:50s}  v{ver}")
        if not livestream_exts:
            _log("  (NO livestream extensions found — streaming kit didn't load)")
    except Exception as e:
        _log(f"[smoke] extension-manager probe failed: {e}")


def _diagnose_settings(kit) -> None:
    """Read livestream-related Carb settings."""
    _log("\n[smoke] ─── Carb settings diagnosis ───")
    try:
        import carb
        settings = carb.settings.get_settings()
        keys_of_interest = [
            "/app/livestream/enabled",
            "/app/livestream/allowResize",
            "/app/window/hideUi",
            "/app/window/drawMouse",
            "/app/renderer/resolution/width",
            "/app/renderer/resolution/height",
            "/exts/omni.kit.livestream.webrtc/server_address",
            "/exts/omni.kit.livestream.webrtc/server_port",
            "/exts/omni.services.livestream.nvcf/streamer/server_port",
            "/persistent/app/viewport/displayOptions",
        ]
        for k in keys_of_interest:
            v = settings.get(k)
            _log(f"  {k:60s} = {v!r}")
    except Exception as e:
        _log(f"[smoke] settings probe failed: {e}")


def _diagnose_viewport(stage) -> None:
    _log("\n[smoke] ─── viewport diagnosis ───")
    try:
        from omni.kit.viewport.utility import get_active_viewport, get_viewport_from_window_name
        vp = get_active_viewport()
        if vp is None:
            _log("[smoke] get_active_viewport() returned None — no active viewport!")
            return
        _log(f"[smoke] active viewport: type={type(vp).__name__}")
        _log(f"[smoke] active viewport camera_path: {vp.camera_path}")
        _log(f"[smoke] active viewport resolution:  "
             f"{vp.resolution}")
    except Exception as e:
        _log(f"[smoke] viewport probe failed: {e}")


def _run(kit, args) -> int:
    _log("\n[smoke] ─── Kit boot complete; probing extensions + settings ───")
    _diagnose_extension_state(kit)
    _diagnose_settings(kit)

    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))

    import omni.usd
    from isaacsim.core.api import World

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[smoke] FAIL: cannot open cell stage")
        return 1
    stage = ctx.get_stage()
    _log(f"[smoke] stage opened: {CELL_STAGE}")

    _author_view_camera(stage)
    _log(f"[smoke] /World/VisCam authored")

    try:
        from omni.kit.viewport.utility import get_active_viewport
        vp = get_active_viewport()
        if vp is not None:
            vp.camera_path = CAMERA_PATH
            _log(f"[smoke] viewport camera bound: {CAMERA_PATH}")
        else:
            _log(f"[smoke] WARN: no active viewport — cannot bind camera")
    except Exception as e:
        _log(f"[smoke] WARN: viewport bind failed: {e}")

    _diagnose_viewport(stage)

    world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    world.reset()
    world.play()
    _log(f"[smoke] World playing")

    _log(f"\n[smoke] ─── render loop ({args.duration:.1f}s, render=True per tick) ───")
    n_ticks = int(args.duration / PHYSICS_DT_S)
    t0 = time.time()
    last_report_s = t0
    for i in range(n_ticks):
        world.step(render=True)
        # Light progress reporting every 5 seconds.
        now = time.time()
        if now - last_report_s >= 5.0:
            _log(f"  [smoke] {i+1}/{n_ticks} ticks, wall={now - t0:.1f}s")
            last_report_s = now

    wall = time.time() - t0
    _log(f"\n[smoke] render loop completed: {n_ticks} ticks in {wall:.1f}s "
         f"({n_ticks / wall:.1f} ticks/s)")

    # ─── post-run final diagnostic ───
    _diagnose_extension_state(kit)
    _diagnose_settings(kit)
    _log("\n[smoke] DONE — inspect log + verify whether your Omniverse Streaming "
         "Client showed frames during the render loop window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
