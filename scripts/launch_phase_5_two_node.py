"""Phase 4B Step 8 / Phase 5 — two-node runtime launcher.

Composes the validated two-node TaskGraph
(``cell_authoring.orchestration.phase_5_two_node``) and runs it
end-to-end on Isaac Sim. Two run modes:

  * Default (--cycles 1, no streaming): single 2-node run; print
    telemetric acceptance summary; exit.
  * --stream:                            enable WebRTC livestream + HUD
                                          for human-visible boundary
                                          continuity verification.

Telemetric acceptance criteria checked after each cycle (per the
Phase 5 brief):

  * Both nodes PASS.
  * Event sequence in canonical order (D-EXEC).
  * Exactly five NodeBoundarySnapshot events (1 session_initial +
    2 pre_node + 2 post_node).
  * Three FixtureStateChanged events: N1→FixtureA-occupied;
    N2→FixtureA-empty; N2→FixtureB-occupied.
  * Reset scope per node: N1=FULL, N2=ACQUIRED_ONLY.
  * Boundary snapshot canonical hashes byte-stable across cycles.

Human-visible verification (--stream mode only — operator inspects
WebRTC stream):

  * Peg picked from belt by N1, placed at FixtureA.
  * Between N1 and N2: peg sits on fixture; no teleport; no
    simulator "snap"; arm continues smoothly from N1's retract pose
    into N2's first descent.
  * N2 returns to FixtureA, grasps the peg, lifts, descends, releases
    (FixtureB co-located per phase_5_two_node module docstring).
  * No discontinuities visible at the inter-node boundary.

Constraints honoured (Phase 5 brief):

* No multi-node beyond the 2-node graph.
* No retries / recovery / branching / dynamic scheduling.
* No async / parallel / speculative orchestration.
* The executor stack is unchanged from Phase 4; the only Phase 5
  additions are the trajectory_sets + 2-node graph + Phase-5 fixture
  registrations on top of the validated runtime.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path


WORKSPACE  = Path("/home/cap2/last")
CELL_STAGE = WORKSPACE / "assets" / "cells" / "cell_01.usda"
LOG_FILE   = WORKSPACE / "logs" / "phase_5_two_node.log"
PKG_ROOT   = WORKSPACE / "logs" / "phase_5_two_node"

PHYSICS_DT_S = 1.0 / 60.0

CAMERA_PATH = "/World/VisCam"


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

_HEADLESS_CONFIG = {"headless": True}


def _auto_detect_public_endpoint() -> str | None:
    """Return the first IPv4 from ``hostname -I`` that is NOT loopback
    (127/8), docker0's default subnet (172.17/16), or CGNAT/Tailscale
    (100.64/10). Falls back to None if no suitable IP found — operator
    must pass ``--public-endpoint`` explicitly in that case.

    Auto-detection is a convenience, not a contract. The selected IP
    is logged so the operator can override if it picks the wrong
    interface.
    """
    import ipaddress
    import subprocess
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
    except Exception:
        return None
    loopback = ipaddress.ip_network("127.0.0.0/8")
    docker_default = ipaddress.ip_network("172.17.0.0/16")
    cgnat = ipaddress.ip_network("100.64.0.0/10")  # Tailscale et al.
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
    PKG_ROOT.mkdir(parents=True, exist_ok=True)

    ap = argparse.ArgumentParser(prog="launch_phase_5_two_node.py")
    ap.add_argument("--cycles", type=int, default=1,
                    help="Number of 2-node sessions to run (default 1).")
    ap.add_argument("--stream", action="store_true",
                    help="Enable WebRTC livestream + HUD for visual "
                         "boundary continuity verification. When set, "
                         "also enables rendered physics ticks.")
    ap.add_argument("--public-endpoint", type=str, default=None,
                    help="LAN/remote IP to advertise to the Omniverse "
                         "Streaming Client (sets "
                         "/app/livestream/publicEndpointAddress). When "
                         "set, the livestream extension DISABLES ICE "
                         "and routes media directly to this endpoint "
                         "(streamsdk 7.3.2+ behaviour). Required when "
                         "the WebRTC client lives on a different host "
                         "than the simulator. Default: auto-detected "
                         "non-loopback, non-docker, non-tailscale IPv4.")
    ap.add_argument("--record-mp4", action="store_true",
                    help="Record an MP4 video of the full session via "
                         "offscreen PNG sequence + ffmpeg encode. Capture "
                         "is observational (uses the same step_observer + "
                         "render=True path as --stream); orchestration / "
                         "replay-identity / D-CONT semantics are not "
                         "perturbed. Output: "
                         "logs/phase_5_recording/<utc>/all_cycles.mp4 + "
                         "per-cycle MP4s + per-cycle PNG sequences.")
    ap.add_argument("--record-fps", type=int, default=60,
                    help="MP4 playback framerate. Each physics tick "
                         "(1/60s) emits one PNG; ffmpeg encodes at this "
                         "playback rate. Default 60 → real-time playback. "
                         "30 → 2x speed. Lower for compact files; higher "
                         "for slow-motion.")
    args = ap.parse_args()

    # Auto-detect public endpoint if --stream is set and the operator
    # didn't pass an explicit address. Picks the first IPv4 from
    # ``hostname -I`` that is NOT loopback, NOT docker0, NOT tailscale.
    if args.stream and args.public_endpoint is None:
        args.public_endpoint = _auto_detect_public_endpoint()

    _log(f"[5-2node] boot — cycles={args.cycles}, stream={args.stream}")
    _log(f"[5-2node] cell stage = {CELL_STAGE}")

    from isaacsim import SimulationApp
    cfg = _LIVESTREAM_CONFIG if args.stream else _HEADLESS_CONFIG
    kit = SimulationApp(launch_config=cfg)

    if args.stream:
        # CORRECTED 2026-05-20 (Step 8 visibility diagnosis):
        # The original ``omni.services.livestream.nvcf`` is the NGC
        # Cloud Functions streamer — designed for NGC deployments,
        # NOT for local Omniverse Streaming Client connections. The
        # local-streamable extension is ``omni.kit.livestream.webrtc``.
        #
        # PUBLIC ENDPOINT (2nd correction, 2026-05-20): without
        # ``/app/livestream/publicEndpointAddress`` the server gathers
        # ICE candidates from local interfaces with no guarantee of
        # advertising a remote-reachable IP — symptom: client connects
        # (signaling works) but media frames never arrive (black frame).
        # Setting publicEndpointAddress DISABLES ICE entirely and
        # routes media directly to the named host (streamsdk 7.3.2+,
        # see omni.kit.streamsdk.plugins/docs/CHANGELOG.md). MUST be
        # set BEFORE enable_extension(omni.kit.livestream.webrtc).
        try:
            from isaacsim.core.utils.extensions import enable_extension
            kit.set_setting("/app/window/drawMouse", True)
            if args.public_endpoint:
                kit.set_setting("/app/livestream/publicEndpointAddress",
                                args.public_endpoint)
                _log(f"[5-2node] /app/livestream/publicEndpointAddress = "
                     f"{args.public_endpoint!r}  (ICE disabled; media "
                     f"routed direct to this host)")
            else:
                _log("[5-2node] WARN: no --public-endpoint set and no "
                     "auto-detected IPv4 — remote clients may receive "
                     "signaling only (black frame). Pass "
                     "--public-endpoint <ip> for remote viewers.")
            # viewportEnabled attempts — see diag_stream_minimal.py for
            # rationale (capture viewport texture instead of full app
            # window, which is empty in headless mode).
            for key in (
                "/app/livestream/viewportEnabled",
                "/app/livestream/viewport_enabled",
                "/exts/omni.kit.livestream.webrtc/viewportEnabled",
                "/exts/omni.kit.streamsdk.plugins/viewportEnabled",
                "/app/livestream/streamFromViewport",
                "/exts/omni.kit.livestream.core/viewportEnabled",
            ):
                kit.set_setting(key, True)
            kit.set_setting("/app/livestream/webrtc/logQosStatus", True)
            enabled = enable_extension("omni.kit.livestream.webrtc")
            _log(f"[5-2node] enable_extension(omni.kit.livestream.webrtc) → {enabled!r}")

            # ─── transport diag: register QoS callback ───
            try:
                import omni.kit.livestream.bind as _ls_bind
                _ls_iface = _ls_bind.acquire_livestream_interface()
                _qos_state = {"count": 0}
                def _qos_cb(qos_status):
                    _qos_state["count"] += 1
                    _log(
                        f"[5-2node] QoS#{_qos_state['count']:>3}  "
                        f"encode={int(qos_status.encode_width)}x"
                        f"{int(qos_status.encode_height)}  "
                        f"fps target={float(qos_status.target_streaming_fps):.1f} "
                        f"actual={float(qos_status.recommended_mode.actual_streaming_fps):.1f}  "
                        f"bitrate={float(qos_status.qos_bitrate):.0f} bps  "
                        f"rtd={float(qos_status.average_rtd_ms):.0f}ms"
                    )
                _cb_id = _ls_iface.register_qos_status_callback(_qos_cb)
                _log(f"[5-2node] registered QoS callback id={_cb_id}")
            except Exception as e:
                _log(f"[5-2node] WARN: QoS callback registration failed: {e}")
            # ─── operator pre-cycle verification dump ───
            import carb
            settings = carb.settings.get_settings()
            actual_endpoint = settings.get("/app/livestream/publicEndpointAddress")
            actual_port     = settings.get("/app/livestream/port")
            actual_proto    = settings.get("/app/livestream/proto")
            actual_enabled  = settings.get("/app/livestream/enabled")
            actual_w        = settings.get("/app/renderer/resolution/width")
            actual_h        = settings.get("/app/renderer/resolution/height")
            ws_url = (f"ws://{actual_endpoint}:{actual_port}"
                      if actual_endpoint and actual_port else "<unset>")
            _log("[5-2node] ─── stream pre-cycle verification ───")
            _log(f"[5-2node]   /app/livestream/publicEndpointAddress = "
                 f"{actual_endpoint!r}")
            _log(f"[5-2node]   /app/livestream/port                  = "
                 f"{actual_port!r}")
            _log(f"[5-2node]   /app/livestream/proto                 = "
                 f"{actual_proto!r}")
            _log(f"[5-2node]   /app/livestream/enabled               = "
                 f"{actual_enabled!r}")
            _log(f"[5-2node]   websocket endpoint                    = "
                 f"{ws_url}")
            _log(f"[5-2node]   render resolution                     = "
                 f"{actual_w}x{actual_h}")
            _log(f"[5-2node]   renderer                              = "
                 f"{_LIVESTREAM_CONFIG['renderer']}")
            # Extension state.
            try:
                import omni.kit.app as _kit_app
                _ext_mgr = _kit_app.get_app().get_extension_manager()
                _ls_exts = [
                    (e["name"], bool(e.get("enabled", False)),
                     e.get("version", "?"))
                    for e in _ext_mgr.get_extensions()
                    if "livestream" in e["name"].lower()
                ]
                for name, ext_enabled, ver in sorted(_ls_exts):
                    state = "ENABLED" if ext_enabled else "loaded "
                    _log(f"[5-2node]   extension  {state}  {name:42s} v{ver}")
            except Exception as e:
                _log(f"[5-2node]   extension probe failed: {e}")
            _log("[5-2node] ─── pre-cycle verification end ───")
        except Exception as e:
            _log(f"[5-2node] WARN: could not enable webrtc livestream ext: {e}")

    sigint_received = {"flag": False}

    def _on_sigint(signum, frame):
        sigint_received["flag"] = True
        _log("[5-2node] received SIGINT; will exit at next session boundary")
    signal.signal(signal.SIGINT,  _on_sigint)
    signal.signal(signal.SIGTERM, _on_sigint)

    try:
        return _run(kit, args, sigint_received)
    except Exception as e:
        import traceback
        _log(f"[5-2node] EXCEPTION: {e}\n{traceback.format_exc()}")
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


def _run(kit, args, sigint_received) -> int:
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))

    import omni.usd
    from isaacsim.core.api import World
    from cell_authoring import load_config
    from cell_authoring.tasks import (
        TaskExecutor, TaskOutcome,
    )
    from cell_authoring.orchestration import (
        BOUNDARY_SNAPSHOT_KIND_POST_NODE,
        BOUNDARY_SNAPSHOT_KIND_PRE_NODE,
        BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
        EventBus,
        EVENT_FIXTURE_STATE_CHANGED,
        EVENT_NODE_BOUNDARY_SNAPSHOT,
        EVENT_NODE_EXECUTION_COMPLETED,
        EVENT_NODE_EXECUTION_STARTED,
        ExecutionSession,
        InMemoryTraceRecorder,
        ResetScope,
    )
    from cell_authoring.orchestration.phase_5_two_node import (
        FIXTURE_A_ID,
        FIXTURE_B_ID,
        NODE_ID_N1,
        NODE_ID_N2,
        OBJECT_ID_PEG,
        build_phase_5_graph,
        build_phase_5_task_resolver,
        build_trajectory_sets,
        register_phase_5_fixtures,
    )

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[5-2node] FAIL: cannot open cell stage")
        return 1
    stage = ctx.get_stage()

    cell_cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")
    _author_view_camera(stage)
    if args.stream:
        try:
            from omni.kit.viewport.utility import get_active_viewport
            vp = get_active_viewport()
            if vp is not None:
                vp.camera_path = CAMERA_PATH
                _log(f"[5-2node] viewport camera = {CAMERA_PATH}")
        except Exception as e:
            _log(f"[5-2node] WARN: could not bind view camera: {e}")

    world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    world.reset()
    world.play()

    # Construct the Phase 5 trajectory_sets and the TaskExecutor that
    # honours them.
    trajectory_sets = build_trajectory_sets()
    _log(f"[5-2node] trajectory_sets keys: {sorted(trajectory_sets.keys())}")
    for tid, traj in sorted(trajectory_sets.items()):
        total = sum(wp.duration_s for wp in traj)
        _log(f"  - {tid}: {len(traj)} waypoints, {total:.1f}s total")

    executor = TaskExecutor(
        world=world, stage=stage, cell_cfg=cell_cfg,
        trajectory_sets=trajectory_sets,
    )

    # ─────────── MP4 recording setup (observational, optional) ───────────
    record_state: dict = {"enabled": False}
    if args.record_mp4:
        # Output layout:
        #   logs/phase_5_recording/<UTC ISO>/raw/cycle_NNNN/rgb_*.png
        #   logs/phase_5_recording/<UTC ISO>/cycle_NNNN.mp4
        #   logs/phase_5_recording/<UTC ISO>/all_cycles.mp4
        from datetime import datetime, timezone
        utc_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rec_root = WORKSPACE / "logs" / "phase_5_recording" / utc_tag
        rec_root.mkdir(parents=True, exist_ok=True)
        record_state["root"]     = rec_root
        record_state["fps"]      = int(args.record_fps)
        record_state["per_cycle_writers"] = []
        record_state["per_cycle_dirs"]    = []
        record_state["enabled"]  = True
        _log(f"[5-2node] MP4 recording enabled — output root: {rec_root}")
        _log(f"[5-2node]   playback fps: {args.record_fps}  "
             f"(physics tick rate is 60 Hz; encode at this rate)")

        # Import Replicator and verify it loads in this kit experience.
        try:
            import omni.replicator.core as rep
            record_state["rep"] = rep
            _log(f"[5-2node]   omni.replicator.core imported OK")
        except Exception as e:
            _log(f"[5-2node] FAIL: omni.replicator.core unavailable: {e}")
            return 1

    # ─────────────── per-cycle session loop ───────────────

    cycle_count   = 0
    pass_count    = 0
    boundary_hashes_first: list[str] = []

    while cycle_count < args.cycles and not sigint_received["flag"]:
        cycle_count += 1
        _log(f"\n[5-2node] === cycle {cycle_count} / {args.cycles} ===")

        # Fresh EventBus + recorder per cycle; the executor instance
        # (and its registry) is reused — Phase 3P determinism guarantee.
        bus = EventBus()
        rec = InMemoryTraceRecorder()
        bus.register(rec)

        # Phase-5 fixtures registered on the executor's registry. This
        # is bootstrap (D-CONT-1) — registry has the slots ready; the
        # session's Phase-G commits will fill/empty them.
        register_phase_5_fixtures(executor.registry)

        # ─── per-cycle MP4 recording: attach Replicator BasicWriter ───
        if record_state["enabled"]:
            rep = record_state["rep"]
            cycle_raw_dir = record_state["root"] / "raw" / f"cycle_{cycle_count:04d}"
            cycle_raw_dir.mkdir(parents=True, exist_ok=True)
            record_state["per_cycle_dirs"].append(cycle_raw_dir)
            # Create a render product targeting /World/VisCam at 1280x720.
            rp = rep.create.render_product("/World/VisCam", (1280, 720))
            writer = rep.WriterRegistry.get("BasicWriter")
            writer.initialize(output_dir=str(cycle_raw_dir), rgb=True)
            writer.attach([rp])
            record_state["per_cycle_writers"].append((writer, rp))
            _log(f"[5-2node]   recording → {cycle_raw_dir}")

        # CORRECTED 2026-05-20: ``render=True`` is REQUIRED for
        # WebRTC livestreaming AND for MP4 recording (without it
        # ``world.step(render=False)`` runs every physics tick and
        # produces no rendered frames for either path).
        need_render = args.stream or args.record_mp4
        execute_kwargs = {"render": True} if need_render else {}
        session = ExecutionSession(
            graph=build_phase_5_graph(),
            task_executor=executor,
            event_bus=bus,
            task_resolver=build_phase_5_task_resolver(),
            execute_kwargs=execute_kwargs,
        )

        t0 = time.time()
        session.begin()
        session.step()        # N1
        session.step()        # N2
        session.complete()
        wall = time.time() - t0
        _log(f"[5-2node] cycle {cycle_count} wall-clock: {wall:.1f}s")

        # ─────────────── telemetric acceptance checks ───────────────

        events = list(rec.events)
        kinds  = [e.event_type for e in events]

        # 1. Both nodes completed and passed.
        nec_events = [e for e in events
                      if e.event_type == EVENT_NODE_EXECUTION_COMPLETED]
        if len(nec_events) != 2:
            _log(f"[5-2node] FAIL acceptance: expected 2 NodeExecutionCompleted, got {len(nec_events)}")
            return 2
        n1_done = next((e for e in nec_events
                        if e.payload["node_id"] == NODE_ID_N1), None)
        n2_done = next((e for e in nec_events
                        if e.payload["node_id"] == NODE_ID_N2), None)
        if not (n1_done and n2_done):
            _log("[5-2node] FAIL acceptance: missing N1 or N2 completion")
            return 2
        if not (n1_done.payload["passed"] and n2_done.payload["passed"]):
            _log(f"[5-2node] FAIL acceptance: a node did not PASS "
                 f"(N1.passed={n1_done.payload['passed']}, "
                 f"N2.passed={n2_done.payload['passed']})")
            _log(f"[5-2node]   N1 outcome: {n1_done.payload['outcome_value']}")
            _log(f"[5-2node]   N2 outcome: {n2_done.payload['outcome_value']}")
            return 2

        # 2. Reset scopes: N1=FULL, N2=ACQUIRED_ONLY (D-CONT-4).
        nes_events = [e for e in events
                      if e.event_type == EVENT_NODE_EXECUTION_STARTED]
        n1_started = next(e for e in nes_events if e.payload["node_id"] == NODE_ID_N1)
        n2_started = next(e for e in nes_events if e.payload["node_id"] == NODE_ID_N2)
        if n1_started.payload["reset_scope"] != "full":
            _log(f"[5-2node] FAIL acceptance: N1 reset_scope expected 'full', got {n1_started.payload['reset_scope']}")
            return 2
        if n2_started.payload["reset_scope"] != "acquired_only":
            _log(f"[5-2node] FAIL acceptance: N2 reset_scope expected 'acquired_only', got {n2_started.payload['reset_scope']}")
            return 2

        # 3. Exactly 5 NodeBoundarySnapshot events.
        snap_events = [e for e in events
                       if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT]
        if len(snap_events) != 5:
            _log(f"[5-2node] FAIL acceptance: expected 5 boundary snapshots, got {len(snap_events)}")
            return 2

        # 4. Three FixtureStateChanged events with correct transitions.
        fsc_events = [e for e in events
                      if e.event_type == EVENT_FIXTURE_STATE_CHANGED]
        if len(fsc_events) != 3:
            _log(f"[5-2node] FAIL acceptance: expected 3 fixture transitions, got {len(fsc_events)}")
            for e in fsc_events:
                _log(f"    {e.payload}")
            return 2
        expected_transitions = [
            (FIXTURE_A_ID, None, OBJECT_ID_PEG, NODE_ID_N1, "occupied"),
            (FIXTURE_A_ID, OBJECT_ID_PEG, None, NODE_ID_N2, "empty"),
            (FIXTURE_B_ID, None, OBJECT_ID_PEG, NODE_ID_N2, "occupied"),
        ]
        actual_transitions = [
            (e.payload["fixture_id"], e.payload["prev_occupied_by"],
             e.payload["new_occupied_by"], e.payload["by_node_id"],
             e.payload["transition"])
            for e in fsc_events
        ]
        if actual_transitions != expected_transitions:
            _log(f"[5-2node] FAIL acceptance: fixture-transition mismatch")
            _log(f"  expected: {expected_transitions}")
            _log(f"  actual  : {actual_transitions}")
            return 2

        # 5. Boundary snapshot hash determinism across cycles.
        cycle_hashes = [e.payload["canonical_hash"] for e in snap_events]
        if cycle_count == 1:
            boundary_hashes_first = cycle_hashes
        else:
            if cycle_hashes != boundary_hashes_first:
                _log(f"[5-2node] FAIL acceptance: boundary hashes diverged across cycles")
                for i, (a, b) in enumerate(zip(boundary_hashes_first, cycle_hashes)):
                    if a != b:
                        _log(f"  snap {i} ({snap_events[i].payload['snapshot_kind']}): {a[:16]} vs {b[:16]}")
                return 2

        # All acceptance checks pass.
        pass_count += 1
        _log(f"[5-2node] cycle {cycle_count} ACCEPTANCE PASS — all telemetric criteria met")
        _log(f"[5-2node]   N1 outcome: {n1_done.payload['outcome_value']}")
        _log(f"[5-2node]   N2 outcome: {n2_done.payload['outcome_value']}")
        _log(f"[5-2node]   boundary snapshot hashes (first 16 chars):")
        for snap_event in snap_events:
            _log(f"    {snap_event.payload['snapshot_kind']:18s}  "
                 f"node={snap_event.payload['node_id'] or '(initial)':40s}  "
                 f"hash={snap_event.payload['canonical_hash'][:16]}")

        # 6. Final registry occupancy assertion.
        fa_occ = executor.registry.fixtures[FIXTURE_A_ID].occupied_by
        fb_occ = executor.registry.fixtures[FIXTURE_B_ID].occupied_by
        if fa_occ is not None:
            _log(f"[5-2node] FAIL acceptance: FixtureA expected empty, got occupied_by={fa_occ!r}")
            return 2
        if fb_occ != OBJECT_ID_PEG:
            _log(f"[5-2node] FAIL acceptance: FixtureB expected occupied({OBJECT_ID_PEG!r}), got {fb_occ!r}")
            return 2

        # 7. End-of-cycle recording detach (flush PNGs to disk).
        if record_state["enabled"]:
            try:
                writer, rp = record_state["per_cycle_writers"][-1]
                writer.detach()
                rp.destroy()
                # Give the file system a moment for outstanding async writes.
                time.sleep(0.5)
                cycle_dir = record_state["per_cycle_dirs"][-1]
                n_pngs = len(list(cycle_dir.glob("rgb_*.png")))
                _log(f"[5-2node]   recorded {n_pngs} PNGs for cycle {cycle_count}")
            except Exception as e:
                _log(f"[5-2node] WARN: writer detach failed for cycle "
                     f"{cycle_count}: {e}")

    _log(f"\n[5-2node] ALL CYCLES PASSED ({pass_count}/{cycle_count})")

    # ─── post-run MP4 encoding ───
    if record_state["enabled"]:
        _encode_mp4_recording(record_state, args.cycles, pass_count)

    try:
        executor.close()
    except Exception:
        pass
    return 0 if pass_count == cycle_count else 1


def _encode_mp4_recording(record_state, n_cycles, pass_count) -> None:
    """Encode the per-cycle PNG sequences into per-cycle MP4 files and
    a concatenated ``all_cycles.mp4``. Print operator-review guidance.

    This is observational-only post-processing — no orchestration / replay
    / D-CONT state is touched."""
    import shutil
    import subprocess as _sp
    rec_root = record_state["root"]
    fps = record_state["fps"]
    if shutil.which("ffmpeg") is None:
        _log("[5-2node] FAIL: ffmpeg not on PATH; cannot encode MP4. "
             "Raw PNGs remain in " + str(rec_root / "raw"))
        return
    _log(f"\n[5-2node] ─── MP4 encoding ({fps} FPS via ffmpeg) ───")

    per_cycle_mp4s: list[Path] = []
    per_cycle_seconds: list[float] = []
    for i, cycle_dir in enumerate(record_state["per_cycle_dirs"], start=1):
        n_pngs = len(list(cycle_dir.glob("rgb_*.png")))
        if n_pngs == 0:
            _log(f"[5-2node]   cycle {i:>2}: NO PNGs in {cycle_dir} — skip")
            continue
        out_mp4 = rec_root / f"cycle_{i:04d}.mp4"
        # ``rgb_*.png`` from Replicator's BasicWriter has a zero-padded
        # frame index. Use ffmpeg's glob input rather than printf so we
        # don't have to know the exact pad width.
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-pattern_type", "glob",
            "-i",  str(cycle_dir / "rgb_*.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "22",
            str(out_mp4),
        ]
        r = _sp.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            _log(f"[5-2node]   cycle {i:>2}: ffmpeg FAILED rc={r.returncode}")
            _log(f"[5-2node]      stderr tail: {r.stderr.strip().splitlines()[-1] if r.stderr else '(empty)'}")
            continue
        cycle_sec = n_pngs / fps
        per_cycle_mp4s.append(out_mp4)
        per_cycle_seconds.append(cycle_sec)
        sz_mb = out_mp4.stat().st_size / 1e6
        _log(f"[5-2node]   cycle {i:>2}: {n_pngs:>5} PNGs → {out_mp4.name} "
             f"({sz_mb:.1f} MB, {cycle_sec:.1f}s @ {fps}fps)")

    # Concatenated all-cycles MP4.
    all_mp4 = rec_root / "all_cycles.mp4"
    if per_cycle_mp4s:
        concat_list = rec_root / "_concat.txt"
        with concat_list.open("w") as fh:
            for p in per_cycle_mp4s:
                fh.write(f"file '{p.name}'\n")
        r = _sp.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_list), "-c", "copy", str(all_mp4)],
            capture_output=True, text=True, cwd=str(rec_root),
        )
        if r.returncode == 0:
            sz_mb = all_mp4.stat().st_size / 1e6
            total_sec = sum(per_cycle_seconds)
            _log(f"[5-2node]   concatenated → {all_mp4.name} "
                 f"({sz_mb:.1f} MB, {total_sec:.1f}s total)")
        else:
            _log(f"[5-2node]   FAIL: concat ffmpeg rc={r.returncode}")
        try:
            concat_list.unlink()
        except Exception:
            pass

    # ─── operator-review guidance ───
    # Phase 4A's ``_run_cycle`` derives step indices from waypoint
    # timings. For the Phase 5 trajectories:
    #   N1 (belt_pick_fixtureA_place):
    #     home(0.0) + grasp_clearance(1.0) + grasp(1.0) + grasp_drop(0.3)
    #     + grasp_close(1.5) + lift(1.5) + approach_place(4.0) + place(2.0)
    #     + release(0.5) + retract_above_place(1.0) + return_home(2.5)
    #     = 15.3s of authored waypoints + ~1s padding
    #     ⇒ release_step ≈ (1+1+0.3+1.5+1.5+4+2)/PHYSICS_DT = 681 step;
    #       n_steps_N1 = round(15.3/0.0167)+60 ≈ 978
    #   N2 (fixtureA_pick_fixtureB_place):
    #     home(0.0)+approach_pickA(4.0)+grasp_clearance(1.0)+grasp(1.5)
    #     +grasp_close(1.5)+lift(1.5)+place(2.0)+release(0.5)
    #     +retract_above_place(1.0)+return_home(4.0) = 17.0s
    #     ⇒ grasp_close_end_step ≈ (4+1+1.5+1.5)/PHYSICS_DT = 480;
    #       place_step ≈ (4+1+1.5+1.5+1.5+2)/PHYSICS_DT = 690;
    #       n_steps_N2 = round(17.0/0.0167)+60 ≈ 1080
    PHYSICS_DT = 1.0 / 60.0
    N1_RELEASE_S = (1.0 + 1.0 + 0.3 + 1.5 + 1.5 + 4.0 + 2.0)  # ≈ 11.3s
    N1_DURATION_S = (978 * PHYSICS_DT)                        # ≈ 16.3s
    N2_PICKUP_S   = (4.0 + 1.0 + 1.5 + 1.5)                   # ≈ 8.0s (grasp_close end)
    N2_PLACE_S    = (4.0 + 1.0 + 1.5 + 1.5 + 1.5 + 2.0)       # ≈ 11.5s
    N2_DURATION_S = (1080 * PHYSICS_DT)                       # ≈ 18.0s

    _log("\n[5-2node] ─── operator review guidance ───")
    _log(f"[5-2node] output root: {rec_root}")
    _log(f"[5-2node] full recording: {all_mp4}")
    _log(f"[5-2node] format: H.264 (libx264) YUV420p @ {fps} FPS, CRF 22")
    if per_cycle_seconds:
        _log(f"[5-2node] total duration: {sum(per_cycle_seconds):.1f}s "
             f"({len(per_cycle_seconds)} cycles × ~{N1_DURATION_S + N2_DURATION_S:.1f}s)")
    _log("[5-2node] suggested review timestamps (concatenated all_cycles.mp4):")
    _log(f"[5-2node]   (relative offsets within each cycle are simulated-time; "
         f"per-cycle MP4 lengths are below)")
    cumulative_s = 0.0
    for i, sec in enumerate(per_cycle_seconds, start=1):
        cs = cumulative_s
        # Within-cycle offsets are from the AUTHORED waypoint timing — they
        # may exceed the actual per-cycle MP4 length if Replicator
        # dropped frames or the cycle finished early; the per-cycle MP4
        # length is the upper bound for valid offsets.
        n1_release_t   = min(cs + N1_RELEASE_S, cs + sec)
        n1_boundary_t  = min(cs + N1_DURATION_S, cs + sec)
        n2_pickup_t    = min(cs + N1_DURATION_S + N2_PICKUP_S, cs + sec)
        n2_release_t   = min(cs + N1_DURATION_S + N2_PLACE_S, cs + sec)
        _log(f"[5-2node]   cycle {i:>2}  (mp4 spans {cs:6.1f}s – {cs + sec:6.1f}s):")
        _log(f"[5-2node]     N1 release on FixtureA       at {n1_release_t:6.1f}s")
        _log(f"[5-2node]     N1.post_node / boundary      at {n1_boundary_t:6.1f}s")
        _log(f"[5-2node]     N2.pre_node / boundary       at {n1_boundary_t:6.1f}s  (same instant; ACQUIRED_ONLY is non-stepping)")
        _log(f"[5-2node]     N2 grasp from FixtureA       at {n2_pickup_t:6.1f}s")
        _log(f"[5-2node]     N2 release on FixtureB       at {n2_release_t:6.1f}s")
        cumulative_s += sec


if __name__ == "__main__":
    sys.exit(main())
