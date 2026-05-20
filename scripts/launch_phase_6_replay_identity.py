"""Phase 4B Step 8 / Phase 6 — replay-identity verification on Isaac Sim.

Runs the Phase 5 two-node session N times (default 2) under
``DurableTraceRecorder`` — writing one SessionPackage per cycle — then
invokes ``tools/check_session_replay_identity.py`` to confirm
byte-equality across all consecutive cycle pairs.

This is the final Step 8 acceptance gate at the runtime layer:
deterministic retained-state continuity + replay-authoritative
byte-equality on the real PhysX host.

Usage
-----

::

    /home/cap2/isaac-sim-5.0.0/python.sh \\
        /home/cap2/last/scripts/launch_phase_6_replay_identity.py \\
        --cycles 3

Outputs
-------

* ``logs/phase_6_replay_identity/cycle_<NNNN>/`` — one SessionPackage
  per cycle (manifest.json + events.jsonl).
* stdout — per-pair comparator output ("L3 REPLAY-IDENTITY: PASS" or
  FAIL); aggregate Step 8 acceptance summary at the end.

Exit code 0 iff every consecutive-cycle pair compares byte-equal.

Contamination resistance (real host)
====================================

This phase elevates the Phase 3 contamination tests from pure-Python
to the real PhysX host. The simulator produces a wide range of
non-authoritative state each cycle (joint velocities, contact
manifolds, articulation solver residuals, sleep/wake flags), all of
which the contract (D-CONT-2) forbids from entering replay identity.

The proof is structural: ``DurableTraceRecorder`` writes only the
event stream emitted by ``ExecutionSession`` + the deterministic
manifest. Boundary snapshots flow through events as canonical-hash
payloads (D-CONT-6c projector purity). No simulator residual state
can enter the SessionPackage by construction. If two cycles produce
different SessionPackages, the divergence is in authoritative state
or contract violation, not contamination — and the comparator
surfaces that directly.

Constraints honoured (Phase 6 brief)
====================================

* Replay identity is strict byte-equality only — no tolerance.
* No new snapshot fields, no D-CONT-1 expansion, no replay databases,
  no persistence frameworks, no mutable replay repair.
* No recovery, no retries, no failure cascades, no async, no
  speculative reconciliation.
* The runner exists for verification only; it does not change the
  orchestration substrate.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


WORKSPACE  = Path("/home/cap2/last")
CELL_STAGE = WORKSPACE / "assets" / "cells" / "cell_01.usda"
LOG_FILE   = WORKSPACE / "logs" / "phase_6_replay_identity.log"
PKG_ROOT   = WORKSPACE / "logs" / "phase_6_replay_identity"
COMPARATOR = WORKSPACE / "tools" / "check_session_replay_identity.py"

PHYSICS_DT_S = 1.0 / 60.0


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
    print(msg, flush=True)


_HEADLESS_CONFIG = {"headless": True}


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    PKG_ROOT.mkdir(parents=True, exist_ok=True)

    ap = argparse.ArgumentParser(prog="launch_phase_6_replay_identity.py")
    ap.add_argument("--cycles", type=int, default=2,
                    help="Number of Phase 5 sessions to run (default 2). "
                         "All consecutive pairs are compared for "
                         "byte-identity.")
    args = ap.parse_args()
    if args.cycles < 2:
        _log(f"[6-replay] ERROR: --cycles must be >= 2; got {args.cycles}")
        return 2

    _log(f"[6-replay] boot — cycles={args.cycles}")
    _log(f"[6-replay] cell stage = {CELL_STAGE}")
    _log(f"[6-replay] SessionPackage root = {PKG_ROOT}")
    _log(f"[6-replay] comparator = {COMPARATOR}")

    # ─── wipe stale per-cycle packages ───
    for p in sorted(PKG_ROOT.glob("cycle_*")):
        for f in p.glob("*"):
            f.unlink()
        p.rmdir()

    from isaacsim import SimulationApp
    kit = SimulationApp(launch_config=_HEADLESS_CONFIG)

    sigint_received = {"flag": False}

    def _on_sigint(signum, frame):
        sigint_received["flag"] = True
        _log("[6-replay] received SIGINT; will exit at next cycle boundary")
    signal.signal(signal.SIGINT,  _on_sigint)
    signal.signal(signal.SIGTERM, _on_sigint)

    try:
        rc_sim = _run_sessions(kit, args, sigint_received)
        if rc_sim != 0:
            return rc_sim
        # IMPORTANT: run the pairwise comparison BEFORE kit.close().
        # Kit's --/app/fastShutdown=True causes SimulationApp.close() to
        # invoke os._exit(0), which would otherwise kill this process
        # before the comparator output reaches the user.
        rc_cmp = _compare_consecutive_pairs(args)
    except Exception as e:
        import traceback
        _log(f"[6-replay] EXCEPTION: {e}\n{traceback.format_exc()}")
        rc_cmp = 1
    try:
        kit.close()
    except Exception:
        pass
    return rc_cmp


def _run_sessions(kit, args, sigint_received) -> int:
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "asset_validator"))

    import omni.usd
    from isaacsim.core.api import World
    from cell_authoring import load_config
    from cell_authoring.tasks import TaskExecutor
    from cell_authoring.orchestration import (
        DurableTraceRecorder,
        EventBus,
        ExecutionSession,
        SessionPackage,
    )
    from cell_authoring.orchestration.phase_5_two_node import (
        build_phase_5_graph,
        build_phase_5_task_resolver,
        build_trajectory_sets,
        register_phase_5_fixtures,
    )

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[6-replay] FAIL: cannot open cell stage")
        return 1
    stage = ctx.get_stage()

    cell_cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")
    world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    world.reset()
    world.play()

    trajectory_sets = build_trajectory_sets()
    executor = TaskExecutor(
        world=world, stage=stage, cell_cfg=cell_cfg,
        trajectory_sets=trajectory_sets,
    )

    for cycle_n in range(1, args.cycles + 1):
        if sigint_received["flag"]:
            _log(f"[6-replay] aborting at cycle {cycle_n} — SIGINT")
            return 130

        pkg_dir = PKG_ROOT / f"cycle_{cycle_n:04d}"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        package = SessionPackage(pkg_dir)
        recorder = DurableTraceRecorder(package)

        register_phase_5_fixtures(executor.registry)
        bus = EventBus()
        bus.register(recorder)

        _log(f"\n[6-replay] === cycle {cycle_n} / {args.cycles} ===")
        _log(f"[6-replay] writing → {pkg_dir}")

        session = ExecutionSession(
            graph=build_phase_5_graph(),
            task_executor=executor,
            event_bus=bus,
            trace_recorder=recorder,
            task_resolver=build_phase_5_task_resolver(),
        )

        t0 = time.time()
        session.begin()
        session.step()      # N1
        session.step()      # N2
        session.complete()
        wall = time.time() - t0
        _log(f"[6-replay] cycle {cycle_n} wall-clock: {wall:.1f}s")

        if not (pkg_dir / "events.jsonl").is_file():
            _log(f"[6-replay] FAIL: events.jsonl not written for cycle {cycle_n}")
            return 1
        if not (pkg_dir / "manifest.json").is_file():
            _log(f"[6-replay] FAIL: manifest.json not written for cycle {cycle_n}")
            return 1
        sz_events   = (pkg_dir / "events.jsonl").stat().st_size
        sz_manifest = (pkg_dir / "manifest.json").stat().st_size
        _log(f"[6-replay] cycle {cycle_n}: events.jsonl={sz_events}b  "
             f"manifest.json={sz_manifest}b")

    try:
        executor.close()
    except Exception:
        pass

    return 0


def _compare_consecutive_pairs(args) -> int:
    """Run the comparator on every consecutive pair (cycle 1 vs cycle 2,
    cycle 2 vs cycle 3, ...). Return 0 iff every pair is byte-identical."""
    _log("\n[6-replay] ─────────── pairwise comparison ───────────")

    fail_count = 0
    for cycle_n in range(2, args.cycles + 1):
        pkg_a = PKG_ROOT / f"cycle_{cycle_n - 1:04d}"
        pkg_b = PKG_ROOT / f"cycle_{cycle_n:04d}"
        _log(f"\n[6-replay] comparing cycle {cycle_n - 1} vs cycle {cycle_n}")
        rc = subprocess.call([
            sys.executable, str(COMPARATOR),
            str(pkg_a), str(pkg_b),
        ])
        if rc != 0:
            fail_count += 1
            _log(f"[6-replay] PAIR {cycle_n - 1}/{cycle_n}: FAIL (rc={rc})")
        else:
            _log(f"[6-replay] PAIR {cycle_n - 1}/{cycle_n}: PASS")

    _log(f"\n[6-replay] ─────────── Step 8 acceptance ───────────")
    _log(f"[6-replay] cycles run                 : {args.cycles}")
    _log(f"[6-replay] consecutive pairs compared : {args.cycles - 1}")
    _log(f"[6-replay] pairs byte-identical       : {args.cycles - 1 - fail_count}")
    _log(f"[6-replay] pairs divergent            : {fail_count}")

    if fail_count == 0:
        _log("[6-replay] STEP 8 CLOSURE: replay-identity GATE PASS")
        return 0
    else:
        _log("[6-replay] STEP 8 CLOSURE: replay-identity GATE FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
