"""Minimal known-good WebRTC livestream reproduction.

Goal (Step 8 black-frame transport diagnosis):
isolate WebRTC livestream infrastructure from the Phase 5 orchestration
stack. If THIS minimal test ALSO produces black frames at the client,
the issue is in the livestream/render-coupling layer, not in
orchestration. If THIS test shows visible frames but Phase 5 doesn't,
the issue is specific to the orchestration runtime.

Scene
-----

* one cube prim at /World/SpinnyCube
* one camera prim at /World/SmokeCam pointing at the cube
* simple sphere light overhead
* cube rotates 1 rev/s via direct USD attribute write per tick (no
  PhysX, no orchestration, no session, no replay machinery)

Livestream telemetry
--------------------

* QoS status callback registered (``register_qos_status_callback``).
  Every callback prints encode width/height, target+actual streaming
  fps, qos_bitrate, average_rtd_ms — the diagnostic that tells us
  whether frames are actually being encoded and pushed onto the wire.
* /app/livestream/webrtc/logQosStatus = True (the extension's own
  log path; redundant safety net with the explicit callback).

Operator test procedure
-----------------------

::

    /home/cap2/isaac-sim-5.0.0/python.sh \\
        /home/cap2/last/scripts/diag_stream_minimal.py \\
        --public-endpoint 202.30.10.86 \\
        --duration 120

While running:

  1. (highest-priority isolation) connect an Omniverse Streaming Client
     RUNNING ON THE ISAAC HOST ITSELF to ws://localhost:49100. If you
     see the rotating cube → the livestream/render coupling is fine
     and the original Phase 5 black-frame symptom is a remote-transport
     issue (firewall, UDP, NAT, MTU).
  2. From your remote machine, connect to ws://202.30.10.86:49100. If
     remote shows black but localhost shows cube → confirmed remote
     transport issue.
  3. If BOTH localhost and remote show black → Isaac-side media
     pipeline is broken (the QoS callback output in stdout will say
     whether the encoder is even producing frames).

This script does NOT touch the Step-8 orchestration stack in any way.
"""

from __future__ import annotations

import argparse
import ipaddress
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


WORKSPACE = Path("/home/cap2/last")
LOG_FILE  = WORKSPACE / "logs" / "diag_stream_minimal.log"

PHYSICS_DT_S = 1.0 / 60.0


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
    print(msg, flush=True)


def _auto_detect_public_endpoint() -> str | None:
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
    except Exception:
        return None
    loopback = ipaddress.ip_network("127.0.0.0/8")
    docker_default = ipaddress.ip_network("172.17.0.0/16")
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    for tok in out.split():
        try:
            ip = ipaddress.ip_address(tok)
        except ValueError:
            continue
        if not isinstance(ip, ipaddress.IPv4Address):
            continue
        if ip in loopback or ip in docker_default or ip in cgnat:
            continue
        return str(ip)
    return None


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    ap = argparse.ArgumentParser(prog="diag_stream_minimal.py")
    ap.add_argument("--duration", type=float, default=60.0,
                    help="Seconds to run render loop (default 60).")
    ap.add_argument("--public-endpoint", type=str, default=None,
                    help="Public IP to advertise to clients. Default: "
                         "auto-detect non-loopback non-docker non-CGNAT.")
    args = ap.parse_args()
    if args.public_endpoint is None:
        args.public_endpoint = _auto_detect_public_endpoint() or "127.0.0.1"

    _log("[mintest] boot — minimal known-good WebRTC livestream repro")
    _log(f"[mintest] duration         = {args.duration:.0f}s")
    _log(f"[mintest] public_endpoint  = {args.public_endpoint}")
    _log("[mintest] scene = single rotating cube; no PhysX; no orchestration")

    from isaacsim import SimulationApp

    launch_config = {
        "headless":      True,
        "hide_ui":       False,
        "width":         1280,
        "height":        720,
        "window_width":  1920,
        "window_height": 1080,
        "renderer":      "RaytracedLighting",
        "display_options": 3286,
    }
    kit = SimulationApp(launch_config=launch_config)

    # ─── livestream configuration BEFORE extension enable ───
    # In headless mode there's no desktop window swap chain to capture,
    # so the streamer's default "capture the whole app window" mode
    # produces an empty texture — symptom: client connects, no frames
    # arrive. The streamsdk 4.1.0+ ``viewportEnabled`` setting tells
    # the streamer to capture the viewport's render target instead.
    # Set under multiple plausible key names since the exact key isn't
    # documented anywhere in this Isaac Sim install.
    try:
        from isaacsim.core.utils.extensions import enable_extension
        kit.set_setting("/app/window/drawMouse", True)
        kit.set_setting("/app/livestream/publicEndpointAddress",
                        args.public_endpoint)
        kit.set_setting("/app/livestream/webrtc/logQosStatus", True)

        # viewport-capture attempts under several plausible key names.
        # Whichever the streamsdk actually reads wins; the others are
        # silently ignored. Cost = a few extra carb settings entries.
        for key in (
            "/app/livestream/viewportEnabled",
            "/app/livestream/viewport_enabled",
            "/exts/omni.kit.livestream.webrtc/viewportEnabled",
            "/exts/omni.kit.streamsdk.plugins/viewportEnabled",
            "/app/livestream/streamFromViewport",
            "/exts/omni.kit.livestream.core/viewportEnabled",
        ):
            kit.set_setting(key, True)
        _log("[mintest] attempted viewportEnabled=True under 6 candidate keys")

        enabled = enable_extension("omni.kit.livestream.webrtc")
        _log(f"[mintest] enable_extension(omni.kit.livestream.webrtc) → {enabled!r}")
    except Exception as e:
        _log(f"[mintest] WARN: livestream extension setup failed: {e}")

    sigint_received = {"flag": False}
    def _on_sigint(signum, frame):
        sigint_received["flag"] = True
        _log("[mintest] SIGINT received; will exit on next tick boundary")
    signal.signal(signal.SIGINT,  _on_sigint)
    signal.signal(signal.SIGTERM, _on_sigint)

    try:
        return _run(kit, args, sigint_received)
    except Exception as e:
        import traceback
        _log(f"[mintest] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        try:
            kit.close()
        except Exception:
            pass


def _author_minimal_scene() -> tuple[str, str]:
    """Author a tiny scene: ground + sphere light + cube + camera.
    Returns (cube_path, camera_path)."""
    import omni.usd
    from pxr import Usd, UsdGeom, UsdLux, Gf, Sdf

    ctx = omni.usd.get_context()
    ctx.new_stage()
    stage = ctx.get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    # Default prim.
    world = UsdGeom.Xform.Define(stage, "/World").GetPrim()
    stage.SetDefaultPrim(world)

    # Ground plane (large flat cube) so the camera has context.
    ground_path = "/World/Ground"
    ground = UsdGeom.Cube.Define(stage, ground_path)
    UsdGeom.XformCommonAPI(ground.GetPrim()).SetTranslate((0.0, 0.0, -0.05))
    UsdGeom.XformCommonAPI(ground.GetPrim()).SetScale((4.0, 4.0, 0.05))

    # Spinny cube (this is the visual diagnostic).
    cube_path = "/World/SpinnyCube"
    cube = UsdGeom.Cube.Define(stage, cube_path)
    UsdGeom.XformCommonAPI(cube.GetPrim()).SetTranslate((0.0, 0.0, 0.5))
    UsdGeom.XformCommonAPI(cube.GetPrim()).SetScale((0.3, 0.3, 0.3))

    # Sphere light overhead.
    light_path = "/World/KeyLight"
    light = UsdLux.SphereLight.Define(stage, light_path)
    UsdGeom.XformCommonAPI(light.GetPrim()).SetTranslate((1.0, 1.0, 3.0))
    light.CreateRadiusAttr(0.3)
    light.CreateIntensityAttr(50000.0)

    # Camera.
    camera_path = "/World/SmokeCam"
    cam_prim = UsdGeom.Camera.Define(stage, camera_path).GetPrim()
    cam = UsdGeom.Camera(cam_prim)
    cam.CreateFocalLengthAttr().Set(28.0)
    cam.CreateClippingRangeAttr().Set(Gf.Vec2f(0.05, 50.0))
    eye    = Gf.Vec3d(2.0, -2.0, 1.5)
    target = Gf.Vec3d(0.0, 0.0, 0.5)
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
    return cube_path, camera_path


def _qos_callback_factory(state: dict):
    """Returns a QoS-status callback that updates ``state`` with the
    latest encoder/transport telemetry. Also logs every callback."""
    def _cb(qos_status):
        state["last_callback_wall_s"] = time.time()
        state["count"] = state.get("count", 0) + 1
        state["encode_width"]  = int(qos_status.encode_width)
        state["encode_height"] = int(qos_status.encode_height)
        state["target_fps"]    = float(qos_status.target_streaming_fps)
        state["actual_fps"]    = float(qos_status.recommended_mode.actual_streaming_fps)
        state["bitrate"]       = float(qos_status.qos_bitrate)
        state["rtd_ms"]        = float(qos_status.average_rtd_ms)
        _log(
            f"[mintest] QoS#{state['count']:>3}  "
            f"encode={state['encode_width']}x{state['encode_height']}  "
            f"fps target={state['target_fps']:.1f} actual={state['actual_fps']:.1f}  "
            f"bitrate={state['bitrate']:.0f} bps  "
            f"rtd={state['rtd_ms']:.0f}ms"
        )
    return _cb


def _run(kit, args, sigint_received) -> int:
    _log("\n[mintest] ─── boot complete; configuring scene + QoS callback ───")

    # Author the minimal scene.
    cube_path, camera_path = _author_minimal_scene()
    _log(f"[mintest] authored {cube_path} + {camera_path}")

    # Bind viewport to the smoke camera.
    try:
        from omni.kit.viewport.utility import get_active_viewport
        vp = get_active_viewport()
        if vp is not None:
            vp.camera_path = camera_path
            _log(f"[mintest] active viewport bound to {camera_path}  "
                 f"resolution={vp.resolution}")
        else:
            _log("[mintest] WARN: no active viewport in this experience")
    except Exception as e:
        _log(f"[mintest] WARN: viewport bind failed: {e}")

    # Register QoS-status callback.
    qos_state: dict = {}
    try:
        import omni.kit.livestream.bind as ls_bind
        livestream_iface = ls_bind.acquire_livestream_interface()
        qos_cb = _qos_callback_factory(qos_state)
        cb_id = livestream_iface.register_qos_status_callback(qos_cb)
        _log(f"[mintest] registered QoS callback id={cb_id}")
    except Exception as e:
        _log(f"[mintest] WARN: could not register QoS callback: {e}")

    # Dump full livestream settings tree.
    _log("\n[mintest] ─── /app/livestream/* settings dump ───")
    try:
        import carb
        settings = carb.settings.get_settings()
        for k in [
            "/app/livestream/publicEndpointAddress",
            "/app/livestream/publicEndpointPort",
            "/app/livestream/port",
            "/app/livestream/proto",
            "/app/livestream/ipversion",
            "/app/livestream/enabled",
            "/app/livestream/allowResize",
            "/app/livestream/allowDynamicResize",
            "/app/livestream/skipCapture",
            "/app/livestream/disableSdkScaling",
            "/app/livestream/outDirectory",
            "/app/livestream/webrtc/logQosStatus",
            "/app/window/hideUi",
            "/app/window/drawMouse",
            "/app/window/width",
            "/app/window/height",
            "/app/renderer/resolution/width",
            "/app/renderer/resolution/height",
        ]:
            v = settings.get(k)
            _log(f"  {k:55s} = {v!r}")
    except Exception as e:
        _log(f"[mintest] settings dump failed: {e}")

    # Render loop with cube spinning.
    _log(f"\n[mintest] ─── render loop ({args.duration:.0f}s, "
         f"spinning cube at 1 rev/s) ───")
    _log(f"[mintest] CONNECT YOUR STREAMING CLIENT NOW")
    _log(f"[mintest]   localhost:  ws://127.0.0.1:49100")
    _log(f"[mintest]   remote   :  ws://{args.public_endpoint}:49100")
    _log(f"[mintest] If localhost shows the cube → render/encode is fine, "
         f"remote-transport issue.")
    _log(f"[mintest] If localhost is also black → Isaac-side media pipeline "
         f"failure.\n")

    import omni.usd
    from pxr import UsdGeom, Gf
    stage = omni.usd.get_context().get_stage()
    cube_prim = stage.GetPrimAtPath(cube_path)
    cube_xformable = UsdGeom.XformCommonAPI(cube_prim)

    # Real-time pacing: hold ~60 Hz wall so the WebRTC encoder has time
    # to gather frames at a steady rate AND so an operator has the full
    # ``--duration`` to connect a streaming client. Without pacing,
    # kit.update() runs faster than realtime and the duration window
    # closes before any client can connect.
    t_start = time.time()
    last_report_s = t_start
    i = 0
    while True:
        elapsed = time.time() - t_start
        if elapsed >= args.duration or sigint_received["flag"]:
            break
        # Rotate cube 1 rev/s on Z.
        angle_deg = elapsed * 360.0
        cube_xformable.SetRotate((0.0, 0.0, float(angle_deg)))
        kit.update()
        i += 1
        # Pace to ~60 Hz wall.
        target_next = t_start + (i * PHYSICS_DT_S)
        sleep_dur = target_next - time.time()
        if sleep_dur > 0:
            time.sleep(sleep_dur)
        now = time.time()
        if now - last_report_s >= 5.0:
            qcount = qos_state.get("count", 0)
            qfps = qos_state.get("actual_fps", 0.0)
            _log(f"[mintest]  +{(now - t_start):5.1f}s  ticks={i:>5}  "
                 f"qos_callbacks={qcount}  last_actual_fps={qfps:.1f}")
            last_report_s = now
    n_ticks = i

    wall = time.time() - t_start
    _log(f"\n[mintest] ─── render loop done: {n_ticks} ticks in "
         f"{wall:.1f}s ({n_ticks / max(wall, 0.001):.0f} ticks/s) ───")

    _log("\n[mintest] ─── final QoS telemetry ───")
    if qos_state.get("count", 0) == 0:
        _log("[mintest] NO QoS callbacks fired during the run.")
        _log("[mintest]   → either no client connected OR Isaac-side media")
        _log("[mintest]     pipeline is producing no frames.")
        _log("[mintest]   → re-run AFTER connecting a streaming client.")
    else:
        _log(f"[mintest] callbacks fired: {qos_state['count']}")
        _log(f"[mintest] last encode dimensions: "
             f"{qos_state.get('encode_width')}x{qos_state.get('encode_height')}")
        _log(f"[mintest] last actual streaming fps: "
             f"{qos_state.get('actual_fps', 0.0):.1f}")
        _log(f"[mintest] last qos bitrate: "
             f"{qos_state.get('bitrate', 0.0):.0f} bps")
        _log(f"[mintest] last average RTD: "
             f"{qos_state.get('rtd_ms', 0.0):.0f} ms")
    _log("\n[mintest] DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
