#!/usr/bin/env python3
"""Phase 4B Step 9 Phase 6 — operator-abort on Isaac Sim.

Exercises the D-FAULT runtime wiring landed in Step 9 Phase 5 on the
real PhysX host:

  * Envelope-as-event abort ingress (D-FAULT-9, D-FAULT-15 #16) — a
    pre-queued ``OperatorEnvelope(kind="abort", requested_at_tick=0)``
    drains at Phase A of the first step() invocation, BEFORE any
    scheduler decision can select N1.
  * Phase-A drain only, no mid-Phase-E interrupt (D-FAULT-6, -6a).
  * Cascade-skip iterates ``graph.canonical_order`` for both pending
    nodes (D-FAULT-3, -4, D-SCHED-3); emission idempotent per
    D-FAULT-7.
  * ``SessionState.ABORTED`` is the terminal — byte-distinguishable
    from ``FAILED`` via the ``SessionAborted`` event_type (F.11
    Phase-2 ruling).
  * 3-cycle byte-identity of ``events.jsonl`` is the replay-identity
    gate (D-FAULT-12, mirrors Step 8 Phase 6's gate but for abort
    traces).

Reuses the Phase 5 two-node graph + trajectory sets verbatim — no
trajectories actually execute because abort drains before scheduler
selection. The Isaac host is loaded only to prove the schema-version=2
boundary snapshot serialization remains stable end-to-end on real PhysX.

Acceptance criteria (all three cycles):

  1. ``SessionState`` ends as ``ABORTED``.
  2. Exactly one ``OperatorAbortRequested`` envelope ingress event.
  3. Exactly one ``SessionAborting`` transition event.
  4. Exactly two ``TaskCascadeSkipped`` events (N1 + N2 in canonical
     order).
  5. Exactly zero ``NodeExecutionStarted`` events (Phase E never entered).
  6. Exactly one ``SessionAborted`` terminal event with
     ``terminator_reason == "OPERATOR_ABORT"``.
  7. Events.jsonl canonical-hash byte-identical across all 3 cycles.

Cites: D-FAULT-3, D-FAULT-4, D-FAULT-6, D-FAULT-6a, D-FAULT-7,
D-FAULT-9, D-FAULT-9a, D-FAULT-10, D-FAULT-11a, D-FAULT-15 #16.
"""

from __future__ import annotations

import hashlib
import json
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

WORKSPACE = Path(__file__).resolve().parent.parent
CELL_STAGE = WORKSPACE / "assets" / "cells" / "cell_01.usda"
PHYSICS_DT_S = 1.0 / 60.0
CAMERA_PATH = "/World/VisCam"

# Number of static frames to capture per cycle when --record-mp4 is set.
# The abort scenario produces NO PhysX motion (Phase E never enters), so
# the MP4 is a static scene throughout. This is the load-bearing visual
# proof: the operator confirms the absence of any hidden motion / reset
# / teleport / rollback artefact.
_PHASE_8_STATIC_FRAMES_PER_CYCLE = 90  # ~1.5s at 60fps


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="launch_phase_9p6_step9_abort.py")
    ap.add_argument("--cycles", type=int, default=3,
                    help="Number of cycles to run for replay-identity gate.")
    ap.add_argument("--out-dir", type=str,
                    default=str(WORKSPACE / "logs" / "phase_9p6_step9_abort"),
                    help="Directory for per-cycle artifacts (events.jsonl, "
                         "summary.txt).")
    ap.add_argument("--record-mp4", action="store_true",
                    help="Phase 4B Step 9 Phase 8: record MP4 per cycle for "
                         "operator review. Captures a short static scene "
                         "(no PhysX motion expected — abort drains at Phase A "
                         "before any world.step()).")
    ap.add_argument("--record-fps", type=int, default=60,
                    help="MP4 playback FPS (matches physics dt = 1/60s).")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Boot SimulationApp BEFORE any cell_authoring import that pulls
    # isaacsim transitively.
    from isaacsim import SimulationApp
    kit = SimulationApp({
        "headless": True,
        "renderer": "RaytracedLighting",
        "width":   640,
        "height":  480,
        "anti_aliasing": 0,
    })
    sigint_received = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: sigint_received.__setitem__("flag", True))

    try:
        rc = _run(kit, args, out_dir, sigint_received)
    except Exception as e:
        _log(f"[9p6-abort] FATAL: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        rc = 1
    finally:
        try:
            kit.close()
        except Exception:
            pass
    return rc


def _run(kit, args, out_dir, sigint_received) -> int:
    sys.path.insert(
        0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    sys.path.insert(
        0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))

    import omni.usd
    from isaacsim.core.api import World

    from cell_authoring import load_config
    from cell_authoring.tasks import TaskExecutor
    from cell_authoring.orchestration import (
        EventBus,
        EVENT_OPERATOR_ABORT_REQUESTED,
        EVENT_SESSION_ABORTED,
        EVENT_SESSION_ABORTING,
        EVENT_NODE_EXECUTION_STARTED,
        EVENT_TASK_CASCADE_SKIPPED,
        ExecutionSession,
        InMemoryTraceRecorder,
        OperatorEnvelope,
        SessionState,
        derive_envelope_id,
    )
    from cell_authoring.orchestration.phase_5_two_node import (
        NODE_ID_N1,
        NODE_ID_N2,
        build_phase_5_graph,
        build_phase_5_task_resolver,
        build_trajectory_sets,
        register_phase_5_fixtures,
    )

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    if not (bool(r[0]) if isinstance(r, tuple) else bool(r)):
        _log("[9p6-abort] FAIL: cannot open cell stage")
        return 1
    stage = ctx.get_stage()

    cell_cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")

    # ─── Phase 8 — author view camera for MP4 recording ───
    if args.record_mp4:
        _author_view_camera(stage)

    world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    world.reset()
    world.play()

    trajectory_sets = build_trajectory_sets()
    executor = TaskExecutor(
        world=world, stage=stage, cell_cfg=cell_cfg,
        trajectory_sets=trajectory_sets,
    )

    # ─── Phase 8 — MP4 recording setup ───
    record_state: dict = {"enabled": False}
    if args.record_mp4:
        utc_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rec_root = out_dir / "mp4_recording" / utc_tag
        rec_root.mkdir(parents=True, exist_ok=True)
        record_state["root"] = rec_root
        record_state["fps"] = int(args.record_fps)
        record_state["per_cycle_dirs"] = []
        record_state["per_cycle_writers"] = []
        record_state["enabled"] = True
        _log(f"[9p6-abort] MP4 recording enabled — output: {rec_root}")
        try:
            import omni.replicator.core as rep  # noqa: F401
            record_state["rep"] = rep
        except Exception as e:
            _log(f"[9p6-abort] FAIL: omni.replicator.core unavailable: {e}")
            return 1

    cycle_count = 0
    pass_count = 0
    events_canonical_first: str | None = None
    summary_lines: list[str] = []

    while cycle_count < args.cycles and not sigint_received["flag"]:
        cycle_count += 1
        _log(f"\n[9p6-abort] === cycle {cycle_count} / {args.cycles} ===")

        bus = EventBus()
        rec = InMemoryTraceRecorder()
        bus.register(rec)
        register_phase_5_fixtures(executor.registry)

        # ─── per-cycle Replicator attach (Phase 8 MP4) ───
        if record_state["enabled"]:
            rep = record_state["rep"]
            cycle_raw_dir = (record_state["root"] / "raw"
                             / f"cycle_{cycle_count:04d}")
            cycle_raw_dir.mkdir(parents=True, exist_ok=True)
            record_state["per_cycle_dirs"].append(cycle_raw_dir)
            rp = rep.create.render_product(CAMERA_PATH, (1280, 720))
            writer = rep.WriterRegistry.get("BasicWriter")
            writer.initialize(output_dir=str(cycle_raw_dir), rgb=True)
            writer.attach([rp])
            record_state["per_cycle_writers"].append((writer, rp))
            _log(f"[9p6-abort]   recording → {cycle_raw_dir}")
            # Capture a few pre-abort static frames so the operator can
            # confirm the initial scene posture (peg on belt, robot at
            # home) BEFORE the abort drain.
            for _ in range(_PHASE_8_STATIC_FRAMES_PER_CYCLE // 2):
                world.step(render=True)

        # Pre-queued operator-abort envelope (D-FAULT-9). The deterministic
        # envelope_id is a blake2b digest of the content tuple — same
        # content across cycles → same id → replay-stable trace.
        eid = derive_envelope_id(
            kind="abort", requested_at_tick=0,
            reason="Phase 9 Phase 6 abort validation",
        )
        env = OperatorEnvelope(
            kind="abort",
            requested_at_tick=0,
            reason="Phase 9 Phase 6 abort validation",
            envelope_id=eid,
        )

        session = ExecutionSession(
            graph=build_phase_5_graph(),
            task_executor=executor,
            event_bus=bus,
            task_resolver=build_phase_5_task_resolver(),
            pending_operator_envelopes=(env,),
        )

        session.begin()
        # First step() drains the envelope at Phase A → ABORTING →
        # cascade-skips remaining pending nodes.
        session.step()
        final = session.complete()

        # ─── Phase 8 — post-abort static frames + writer detach ───
        if record_state["enabled"]:
            # Capture post-abort frames to prove the absence of any
            # hidden cleanup motion AFTER the SessionAborted terminal.
            # If anything were teleporting, releasing the gripper, or
            # otherwise "fixing" state, it would appear here.
            for _ in range(_PHASE_8_STATIC_FRAMES_PER_CYCLE // 2):
                world.step(render=True)
            try:
                writer, rp = record_state["per_cycle_writers"][-1]
                writer.detach()
                rp.destroy()
                import time as _t; _t.sleep(0.5)  # async flush
                cycle_dir = record_state["per_cycle_dirs"][-1]
                n_pngs = len(list(cycle_dir.glob("rgb_*.png")))
                _log(f"[9p6-abort]   recorded {n_pngs} PNGs for cycle "
                     f"{cycle_count}")
            except Exception as e:
                _log(f"[9p6-abort] WARN: writer detach failed for cycle "
                     f"{cycle_count}: {e}")

        # ─────────────── acceptance criteria ───────────────
        events = list(rec.events)
        types = [e.event_type for e in events]

        # 1. Terminal state.
        if final.session_state != SessionState.ABORTED:
            _log(f"[9p6-abort] FAIL: terminal state = "
                 f"{final.session_state.value} (expected ABORTED)")
            return 2

        # 2. Envelope ingress event exactly once.
        ingress = [e for e in events
                   if e.event_type == EVENT_OPERATOR_ABORT_REQUESTED]
        if len(ingress) != 1:
            _log(f"[9p6-abort] FAIL: expected 1 OperatorAbortRequested, "
                 f"got {len(ingress)}")
            return 2
        if ingress[0].payload["envelope_id"] != eid:
            _log(f"[9p6-abort] FAIL: envelope_id mismatch — payload="
                 f"{ingress[0].payload['envelope_id']!r}, expected={eid!r}")
            return 2

        # 3. SessionAborting exactly once.
        aborting = [e for e in events if e.event_type == EVENT_SESSION_ABORTING]
        if len(aborting) != 1:
            _log(f"[9p6-abort] FAIL: expected 1 SessionAborting, "
                 f"got {len(aborting)}")
            return 2

        # 4. Exactly 2 TaskCascadeSkipped (N1, N2) in canonical order.
        cascades = [e for e in events
                    if e.event_type == EVENT_TASK_CASCADE_SKIPPED]
        if len(cascades) != 2:
            _log(f"[9p6-abort] FAIL: expected 2 TaskCascadeSkipped, "
                 f"got {len(cascades)}")
            return 2
        cascade_ids = [e.payload["node_id"] for e in cascades]
        if cascade_ids != [NODE_ID_N1, NODE_ID_N2]:
            _log(f"[9p6-abort] FAIL: cascade order = {cascade_ids}, "
                 f"expected [{NODE_ID_N1}, {NODE_ID_N2}]")
            return 2
        for e in cascades:
            if e.payload.get("reason") != "OPERATOR_ABORT":
                _log(f"[9p6-abort] FAIL: cascade reason = "
                     f"{e.payload.get('reason')!r} (expected OPERATOR_ABORT)")
                return 2

        # 5. Zero NodeExecutionStarted (Phase E never entered).
        nes = [e for e in events if e.event_type == EVENT_NODE_EXECUTION_STARTED]
        if len(nes) != 0:
            _log(f"[9p6-abort] FAIL: expected 0 NodeExecutionStarted, "
                 f"got {len(nes)} — abort failed to short-circuit Phase E")
            return 2

        # 6. SessionAborted exactly once with terminator_reason.
        aborted = [e for e in events if e.event_type == EVENT_SESSION_ABORTED]
        if len(aborted) != 1:
            _log(f"[9p6-abort] FAIL: expected 1 SessionAborted, "
                 f"got {len(aborted)}")
            return 2
        if aborted[0].payload.get("terminator_reason") != "OPERATOR_ABORT":
            _log(f"[9p6-abort] FAIL: SessionAborted.terminator_reason = "
                 f"{aborted[0].payload.get('terminator_reason')!r}")
            return 2

        # 7. Canonical-JSON encoding of the trace; replay-identity gate.
        # Per-event canonical encoding: each event becomes {seq, type, payload}
        # with sorted keys recursively. Two cycles produce byte-equal
        # canonical strings IFF the abort path is fully deterministic.
        events_canonical = json.dumps(
            [
                {
                    "seq":        e.seq,
                    "event_type": e.event_type,
                    "payload":    dict(e.payload),
                }
                for e in events
            ],
            sort_keys=True, ensure_ascii=True, allow_nan=False,
            separators=(",", ":"),
        )
        events_hash = hashlib.sha256(events_canonical.encode("utf-8")).hexdigest()

        # Persist per-cycle artifact.
        cycle_path = out_dir / f"cycle_{cycle_count:02d}_events.json"
        cycle_path.write_text(events_canonical, encoding="utf-8")

        _log(f"[9p6-abort] cycle {cycle_count} ACCEPTANCE PASS")
        _log(f"  events.count        : {len(events)}")
        _log(f"  events.canonical_hash: {events_hash}")
        _log(f"  skipped (final)     : {sorted(final.skipped)}")
        _log(f"  failed  (final)     : {sorted(final.failed)}")
        _log(f"  completed (final)   : {sorted(final.completed)}")
        summary_lines.append(
            f"cycle_{cycle_count:02d}: hash={events_hash}  "
            f"events={len(events)}  state=ABORTED"
        )

        if events_canonical_first is None:
            events_canonical_first = events_canonical
        else:
            if events_canonical != events_canonical_first:
                _log(f"[9p6-abort] FAIL: events.jsonl byte-divergence at "
                     f"cycle {cycle_count} (D-FAULT-11a strict byte-equality)")
                # Save the divergent cycle for forensic inspection.
                (out_dir / f"DIVERGENT_cycle_{cycle_count:02d}.json").write_text(
                    events_canonical, encoding="utf-8")
                return 2

        pass_count += 1

    summary_path = out_dir / "summary.txt"
    summary_path.write_text("\n".join([
        f"=== Phase 9 Phase 6 — operator-abort Isaac Sim regression ===",
        f"started_at      : {datetime.now(timezone.utc).isoformat()}",
        f"cycles_requested: {args.cycles}",
        f"cycles_passed   : {pass_count}",
        f"---",
        *summary_lines,
        f"---",
        f"REPLAY-IDENTITY GATE: {'PASS' if pass_count == args.cycles else 'FAIL'}",
    ]) + "\n", encoding="utf-8")
    _log(f"\n[9p6-abort] {pass_count}/{args.cycles} cycles ACCEPTANCE PASS")
    _log(f"[9p6-abort] summary → {summary_path}")

    # ─── Phase 8 — encode MP4s + write operator-review manifest ───
    if record_state["enabled"]:
        _encode_mp4_recording(record_state, args.cycles, pass_count)
        _write_phase_8_manifest(record_state, out_dir, summary_lines)

    return 0 if pass_count == args.cycles else 1


def _author_view_camera(stage):
    """Author the /World/VisCam camera used by Replicator render product.

    Same view geometry as the Phase 5 launcher so operator MP4 reviews
    are visually comparable across happy-path and abort scenarios.
    """
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


def _encode_mp4_recording(record_state, n_cycles, pass_count) -> None:
    """Encode per-cycle PNG sequences into per-cycle MP4 files +
    a concatenated all_cycles.mp4. Pure post-processing — no
    orchestration / replay state touched."""
    import shutil
    import subprocess as _sp
    rec_root = record_state["root"]
    fps = record_state["fps"]
    if shutil.which("ffmpeg") is None:
        _log("[9p6-abort] FAIL: ffmpeg not on PATH; cannot encode MP4. "
             "Raw PNGs remain in " + str(rec_root / "raw"))
        return
    _log(f"\n[9p6-abort] ─── MP4 encoding ({fps} FPS via ffmpeg) ───")
    per_cycle_mp4s: list[Path] = []
    for i, cycle_dir in enumerate(record_state["per_cycle_dirs"], start=1):
        n_pngs = len(list(cycle_dir.glob("rgb_*.png")))
        if n_pngs == 0:
            _log(f"[9p6-abort]   cycle {i}: NO PNGs — skip")
            continue
        out_mp4 = rec_root / f"cycle_{i:04d}.mp4"
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
            _log(f"[9p6-abort]   cycle {i}: ffmpeg FAILED rc={r.returncode}")
            continue
        per_cycle_mp4s.append(out_mp4)
        sz_mb = out_mp4.stat().st_size / 1e6
        _log(f"[9p6-abort]   cycle {i}: {n_pngs} PNGs → {out_mp4.name} "
             f"({sz_mb:.1f} MB)")
    # Concatenated MP4 for single-file operator review.
    if per_cycle_mp4s:
        all_mp4 = rec_root / "all_cycles.mp4"
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
            _log(f"[9p6-abort]   concatenated → {all_mp4.name} ({sz_mb:.1f} MB)")
        try:
            concat_list.unlink()
        except Exception:
            pass


def _write_phase_8_manifest(record_state, out_dir, summary_lines) -> None:
    """Phase 4B Step 9 Phase 8 — operator review manifest.

    Single JSON file linking each per-cycle MP4 to its
    replay-authoritative artifacts (events.json + SHA-256). The
    operator reads this manifest, watches the MP4, and confirms the
    visual posture against the canonical event sequence.
    """
    rec_root = record_state["root"]
    manifest: dict = {
        "scenario":   "operator_abort",
        "schema":     "phase_4b_step9_phase8_review_manifest_v1",
        "generated":  datetime.now(timezone.utc).isoformat(),
        "cells_stage": str(CELL_STAGE),
        "camera_path": CAMERA_PATH,
        "fps":         record_state["fps"],
        "cycles":     [],
        "operator_review_checklist": [
            "no mid-motion teleport observed",
            "no hidden reset appearance (peg / robot do not snap to home)",
            "no abrupt rollback to pre-task state",
            "no impossible state snap (peg never relocates while gripper is "
            "open and not in contact)",
            "abort timing operationally understandable (no motion expected "
            "in this scenario — abort drains at Phase A BEFORE Phase E "
            "enters; scene is static throughout)",
            "Phase E never visibly enters (no trajectory execution observed)",
            "no spontaneous state repair after SessionAborted (post-abort "
            "frames identical to pre-abort frames)",
            "all 3 cycles visually identical (replay-identity coherent at "
            "frame level, mirroring byte-level events.jsonl SHA-256 "
            "identity)",
        ],
        "replay_authoritative_artifacts": [],
    }
    # Per-cycle linkage: MP4 path + events.json path + events SHA-256.
    for i, cycle_dir in enumerate(record_state["per_cycle_dirs"], start=1):
        mp4_path = rec_root / f"cycle_{i:04d}.mp4"
        events_path = out_dir / f"cycle_{i:02d}_events.json"
        if events_path.exists():
            events_sha = hashlib.sha256(
                events_path.read_bytes()
            ).hexdigest()
        else:
            events_sha = None
        manifest["cycles"].append({
            "cycle":       i,
            "mp4_path":    str(mp4_path.relative_to(out_dir)) if mp4_path.exists() else None,
            "raw_dir":     str(cycle_dir.relative_to(out_dir)),
            "events_path": str(events_path.relative_to(out_dir)) if events_path.exists() else None,
            "events_sha256": events_sha,
        })
    # Pairwise comparator verdicts are computed post-hoc by the
    # operator (or CI) via tools/check_session_replay_identity.py;
    # this manifest records the expectation.
    manifest["replay_identity_expectation"] = (
        "All cycles' events.json files must be byte-identical "
        "(SHA-256 equal). The comparator (tools/check_session_replay_"
        "identity.py) MUST report REPLAY-IDENTICAL for every pairwise "
        "comparison. Visual MP4 review must show the same static scene "
        "posture across all cycles."
    )
    manifest_path = rec_root / "review_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    _log(f"[9p6-abort] operator review manifest → {manifest_path}")


if __name__ == "__main__":
    sys.exit(main())
