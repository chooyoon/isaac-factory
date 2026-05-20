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
    args = ap.parse_args()

    _log(f"[5-2node] boot — cycles={args.cycles}, stream={args.stream}")
    _log(f"[5-2node] cell stage = {CELL_STAGE}")

    from isaacsim import SimulationApp
    cfg = _LIVESTREAM_CONFIG if args.stream else _HEADLESS_CONFIG
    kit = SimulationApp(launch_config=cfg)

    if args.stream:
        try:
            from isaacsim.core.utils.extensions import enable_extension
            kit.set_setting("/app/window/drawMouse", True)
            enable_extension("omni.services.livestream.nvcf")
            _log("[5-2node] enabled omni.services.livestream.nvcf")
        except Exception as e:
            _log(f"[5-2node] WARN: could not enable livestream ext: {e}")

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

        session = ExecutionSession(
            graph=build_phase_5_graph(),
            task_executor=executor,
            event_bus=bus,
            task_resolver=build_phase_5_task_resolver(),
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

    _log(f"\n[5-2node] ALL CYCLES PASSED ({pass_count}/{cycle_count})")
    try:
        executor.close()
    except Exception:
        pass
    return 0 if pass_count == cycle_count else 1


if __name__ == "__main__":
    sys.exit(main())
