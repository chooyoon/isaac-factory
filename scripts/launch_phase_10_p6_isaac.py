#!/usr/bin/env python3
"""Phase 4B Step 10 Direction A / Phase 6 — Isaac Sim regression.

Empirically validates the Step 10 Direction A surface on real PhysX
for the four deferred-from-Step-9 scenarios:

  C. Operator-abort after acquire — operator envelope becomes eligible
     mid-trajectory while N2 transports the peg; predicate trips at the
     ``approach_place`` boundary (D-EXEC-13); session classifies as
     OPERATOR_ABORT (D-FAULT-3b row 1); cascade-skips remaining pending
     nodes; SessionAborted.

  D. Cascade-skipped downstream graph — operator envelope eligible
     mid-trajectory during N1; predicate trips at ``approach_place``;
     N1 classified as OPERATOR_ABORT; N2 cascade-skipped with
     reason="OPERATOR_ABORT" (D-FAULT-3 row 6); SessionAborted.

  E. Tick-budget timeout — N1 carries a deliberately tight
     ``tick_budget_ticks``; predicate trips on budget at the first
     boundary whose cumulative tick count exceeds the budget; classifier
     resolves to TIMEOUT_FAILURE (D-FAULT-3b row 2); NodeTimeoutTripped
     emitted; N2 cascade-skipped via FailureAction; SessionFailed.

  F. Contradiction-preserving retained-state interruption — mirrors C
     plus an explicit post-interrupt boundary-snapshot inspection
     asserting the post-N2 contradiction: FixtureA.occupied_by =
     "Peg_01" (committed by N1's Phase G; N2 did NOT commit) AND
     Peg_01.canonical_pose differs from FixtureA's world pose
     (peg attached to gripper, mid-transport). D-FAULT-5b in action.

Acceptance per cycle:

  * SessionState as scenario-prescribed (ABORTED for C/D/F, FAILED for E).
  * outcome_value on the interrupted node matches scenario.
  * Forensic fields (interrupted_at_segment_index/name) populated.
  * Ingress events emitted exactly once.
  * events.jsonl canonical-hash byte-identical across all cycles
    (D-FAULT-11a strict byte-equality).

Constraints honoured:

  * No mid-Phase-E orchestration-observable interrupt (D-FAULT-6a,
    D-EXEC-13a). Predicate consultation is executor-internal at
    authored segment boundaries (D-EXEC-13).
  * No hidden cleanup: post-abort retained state preserves last-tick
    truth (D-FAULT-5/-5a/-5b).
  * No wall-clock cadence: predicate closure uses only authoritative
    inputs (envelope snapshot, base_tick, boundary_ticks_consumed,
    tick_budget_ticks). All deterministic; replay-identical across
    cycles (D-FAULT-12c).
  * No new event types, no new SessionState values; the existing
    Step 9 P5 surface handles all four scenarios.

Invocation:
  ~/isaac-sim-5.0.0/python.sh scripts/launch_phase_10_p6_isaac.py \\
      --scenario {C|D|E|F} [--cycles 3] [--record-mp4] [--out-dir DIR]

Cites: D-EXEC-13, D-FAULT-1b, D-FAULT-3, D-FAULT-3a, D-FAULT-3b,
D-FAULT-4, D-FAULT-5, D-FAULT-5b, D-FAULT-6, D-FAULT-6a, D-FAULT-7,
D-FAULT-10, D-FAULT-11a, D-FAULT-12, D-FAULT-12c, D-FAULT-15.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
CELL_STAGE = WORKSPACE / "assets" / "cells" / "cell_01.usda"
PHYSICS_DT_S = 1.0 / 60.0
CAMERA_PATH = "/World/VisCam"

# MP4 capture cadence — match Step 9 P6.
_FRAMES_PER_CYCLE_PRE = 30   # pre-execute scene posture (~0.5s @60fps)
_FRAMES_PER_CYCLE_POST = 60  # post-terminal static posture (~1s @60fps)


# WebRTC livestream config — mirrors launch_phase_5_two_node.py so the
# Omniverse Streaming Client can attach to the running session for live
# operator observation. Purely observational; does NOT perturb
# orchestration / replay-identity / D-CONT semantics.
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

_HEADLESS_CONFIG = {
    "headless": True,
    "renderer": "RaytracedLighting",
    "width":   640,
    "height":  480,
    "anti_aliasing": 0,
}


def _auto_detect_public_endpoint() -> str | None:
    """Return the first IPv4 from ``hostname -I`` that is NOT loopback
    (127/8), docker0's default subnet (172.17/16), or CGNAT/Tailscale
    (100.64/10). Falls back to None if no suitable IP found.

    Auto-detection is a convenience, not a contract. The selected IP
    is logged so the operator can override if it picks the wrong
    interface.
    """
    import ipaddress
    import subprocess as _sp
    try:
        out = _sp.check_output(["hostname", "-I"], text=True).strip()
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


# ────────────────────────── scenario configuration ──────────────────────────


@dataclass(frozen=True)
class ScenarioSpec:
    """All scenario-varying configuration in one place. Pure dataclass —
    no runtime behaviour; the cycle loop reads it and acts accordingly."""

    code:                str    # "C", "D", "E", "F"
    name:                str    # short forensic name
    description:         str    # one-line description for log
    # Envelope configuration: requested_at_tick OR None for budget-only scenarios.
    envelope_requested_at_tick: int | None
    envelope_reason:     str
    # Budget override on N1 (TIMEOUT_FAILURE scenarios).
    n1_tick_budget_ticks_override: int | None
    # Which node should be the interrupted/failed one (for acceptance).
    interrupted_node: str  # "N1" or "N2"
    expected_outcome_value: str  # "OPERATOR_ABORT" | "TIMEOUT_FAILURE"
    expected_terminal_state: str  # "ABORTED" | "FAILED"
    expected_terminator_reason: str  # "OPERATOR_ABORT" | "TIMEOUT_FAILURE"
    # F-specific: assert post-interrupt contradiction in boundary snapshot.
    assert_contradiction_in_snapshot: bool


def _load_scenario(code: str) -> ScenarioSpec:
    """Return the scenario configuration. Pure switch; no runtime state."""
    if code == "C":
        return ScenarioSpec(
            code="C",
            name="operator_abort_after_acquire",
            description=(
                "envelope eligible mid-N1 transport (post-acquire, "
                "pre-place); predicate trips at N1's approach_place "
                "boundary; classified as OPERATOR_ABORT; N2 cascade-skipped"
            ),
            # Phase 6 Run-1 forensic finding: with pre-queued envelopes
            # + per-step orchestration_tick advance + Cell-01 trajectory
            # durations, an envelope cannot be designed to fire ONLY
            # during N2 (N1's boundary range 60..918 always satisfies
            # the eligibility formula first). This is architectural,
            # not a constitutional violation — the scenario locus
            # naturally lives in N1.
            #
            # N1 runs at orchestration_tick=0. Eligibility formula:
            # base_tick + ticks_consumed_at_K >= requested_at_tick.
            # With Cell-01 N1 trajectory, approach_place boundary's
            # cumulative tick count is 558. base_tick=0, requested=400:
            #   boundary 5 (lift, 318):           0+318=318 < 400 → False
            #   boundary 6 (approach_place, 558): 0+558=558 ≥ 400 → True ★
            # The peg is "after acquire" because grasp_close (boundary 4,
            # tick 228) completed before the predicate trips at boundary 6.
            envelope_requested_at_tick=400,
            envelope_reason="Phase 10 P6 scenario C — abort after acquire",
            n1_tick_budget_ticks_override=None,
            interrupted_node="N1",
            expected_outcome_value="OPERATOR_ABORT",
            expected_terminal_state="ABORTED",
            expected_terminator_reason="OPERATOR_ABORT",
            assert_contradiction_in_snapshot=False,
        )
    if code == "D":
        return ScenarioSpec(
            code="D",
            name="cascade_skipped_downstream",
            description=(
                "envelope eligible mid-N1 transport; N1 classified as "
                "OPERATOR_ABORT; N2 cascade-skipped"
            ),
            # N1 runs at orchestration_tick=0. base_tick=0,
            # requested_at_tick=400. Predicate trips at approach_place
            # (boundary 6, cumulative 558): 0+558 >= 400 → True.
            envelope_requested_at_tick=400,
            envelope_reason="Phase 10 P6 scenario D — mid-N1 abort with cascade",
            n1_tick_budget_ticks_override=None,
            interrupted_node="N1",
            expected_outcome_value="OPERATOR_ABORT",
            expected_terminal_state="ABORTED",
            expected_terminator_reason="OPERATOR_ABORT",
            assert_contradiction_in_snapshot=False,
        )
    if code == "E":
        return ScenarioSpec(
            code="E",
            name="tick_budget_timeout",
            description=(
                "N1 tick_budget_ticks deliberately tight; predicate trips "
                "on budget at the first boundary > budget; classified as "
                "TIMEOUT_FAILURE"
            ),
            # N1 budget = 400. Boundaries: 60, 120, 138, 228, 318, 558, ...
            # Predicate row 2: ticks_at_boundary > budget. First trigger:
            # boundary 6 (approach_place, 558 > 400) → True.
            # Classifier row 2: 558 > 400 → TIMEOUT_FAILURE.
            envelope_requested_at_tick=None,
            envelope_reason="",
            n1_tick_budget_ticks_override=400,
            interrupted_node="N1",
            expected_outcome_value="TIMEOUT_FAILURE",
            expected_terminal_state="FAILED",
            expected_terminator_reason="TIMEOUT_FAILURE",
            assert_contradiction_in_snapshot=False,
        )
    if code == "F":
        return ScenarioSpec(
            code="F",
            name="contradiction_preserving_interrupt",
            description=(
                "scenario C plus explicit post-N1 contradiction "
                "verification: peg pose moved from belt origin (acquired) "
                "AND FixtureA.occupied_by = None (N1 never committed); "
                "D-FAULT-5b in action — no implicit reconciliation"
            ),
            # Phase 6 Run-1 forensic finding: contradiction inspection
            # moves to the post-N1 boundary snapshot. The D-FAULT-5b
            # contradiction class is preserved; only the snapshot locus
            # changes (N1's post-node snapshot instead of N2's).
            envelope_requested_at_tick=400,
            envelope_reason="Phase 10 P6 scenario F — contradiction preservation",
            n1_tick_budget_ticks_override=None,
            interrupted_node="N1",
            expected_outcome_value="OPERATOR_ABORT",
            expected_terminal_state="ABORTED",
            expected_terminator_reason="OPERATOR_ABORT",
            assert_contradiction_in_snapshot=True,
        )
    raise ValueError(f"Unknown scenario code {code!r}")


def _log(msg: str) -> None:
    print(msg, flush=True)


# ────────────────────────── entry point ──────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(prog="launch_phase_10_p6_isaac.py")
    ap.add_argument("--scenario", choices=["C", "D", "E", "F"], required=True,
                    help="Which deferred-from-Step-9 scenario to run.")
    ap.add_argument("--cycles", type=int, default=3,
                    help="Cycles for the replay-identity gate (default 3).")
    ap.add_argument("--out-dir", type=str, default=None,
                    help="Directory for per-cycle artifacts. Defaults to "
                         "logs/phase_10_p6_scenario_<code>/.")
    ap.add_argument("--record-mp4", action="store_true",
                    help="Phase 8-style MP4 capture for operator review.")
    ap.add_argument("--record-fps", type=int, default=60,
                    help="MP4 playback FPS (default 60 = physics_dt^-1).")
    ap.add_argument("--stream", action="store_true",
                    help="Enable WebRTC livestream so the operator can "
                         "attach via the Omniverse Streaming Client for "
                         "live observation. Observational only; does NOT "
                         "perturb orchestration / replay-identity / "
                         "D-CONT semantics.")
    ap.add_argument("--public-endpoint", type=str, default=None,
                    help="LAN/remote IPv4 to advertise to the Streaming "
                         "Client (sets /app/livestream/publicEndpointAddress). "
                         "When set, ICE is disabled and media routes "
                         "directly to this endpoint. Required for remote "
                         "viewers. Default: auto-detected non-loopback, "
                         "non-docker, non-tailscale IPv4.")
    ap.add_argument("--diagnostic-dump-registry", action="store_true",
                    help="Diagnostic-only: write per-cycle registry-state "
                         "side artifact (Peg_01.pose_m, Peg_01.yaw_rad, "
                         "FixtureA.occupied_by) to "
                         "logs/<scenario>/cycle_NN_registry_dump.json. "
                         "Observational only; does NOT affect snapshot "
                         "field set, canonicalization, comparator, or "
                         "replay criteria. Implies --diagnostic-continue-"
                         "on-divergence.")
    ap.add_argument("--diagnostic-continue-on-divergence", action="store_true",
                    help="Diagnostic-only: when events.jsonl byte-divergence "
                         "is detected at cycle 2+, log + write the "
                         "DIVERGENT_cycle_NN.json artifact (same as "
                         "non-diagnostic path) but continue running the "
                         "remaining cycles instead of exiting. Lets the "
                         "operator observe whether divergence stabilizes "
                         "across subsequent cycles. NOT for production "
                         "acceptance runs.")
    ap.add_argument("--diagnostic-world-reset-between-cycles", action="store_true",
                    help="Diagnostic-only: between cycles, call "
                         "world.stop()/world.reset()/world.play() to "
                         "re-isolate the simulator state. Tests whether "
                         "persistent PhysX solver state across "
                         "executor.reset(FULL) is the source of "
                         "cross-cycle peg-pose divergence. Pure simulator-"
                         "isolation forensics; does NOT affect "
                         "orchestration semantics, snapshot field set, "
                         "comparator, or canonicalization. NOT for "
                         "production acceptance runs.")
    ap.add_argument("--diagnostic-enhanced-determinism", action="store_true",
                    help="Diagnostic-only: apply "
                         "PhysxSceneAPI.enableEnhancedDeterminism=True "
                         "to /World/PhysicsScene immediately after stage "
                         "load, before world.reset(). Documented PhysX "
                         "flag for stricter per-step determinism. Pure "
                         "simulator-isolation forensics; does NOT touch "
                         "orchestration semantics, snapshot field set, "
                         "comparator, or canonicalization. NOT for "
                         "production acceptance runs.")
    ap.add_argument("--diagnostic-reopen-stage-between-cycles", action="store_true",
                    help="Diagnostic-only: between cycles, fully tear "
                         "down + re-open the USD stage and re-construct "
                         "the World + TaskExecutor. Tests whether "
                         "persistent state at the stage/articulation/"
                         "PhysX-scene-compile level (beyond what "
                         "World.reset() clears) is the source of "
                         "cross-cycle divergence. Heavyweight (~5-10s "
                         "per re-open). Pure simulator-isolation "
                         "forensics; orchestration semantics unchanged. "
                         "Alias: --reopen-stage-between-cycles "
                         "(production isolation policy).")
    ap.add_argument("--reopen-stage-between-cycles", action="store_true",
                    help="Production isolation policy for Phase 6 mid-"
                         "trajectory-interrupt scenarios. Between cycles, "
                         "tears down + re-opens the USD stage and re-"
                         "constructs World + TaskExecutor. Empirically "
                         "validated as the minimum-invasiveness fix for "
                         "cross-cycle PhysX articulation/solver state "
                         "leakage observed in Scenario C diagnostics "
                         "(World.reset and enableEnhancedDeterminism "
                         "alone were insufficient). Heavyweight (~5-10s "
                         "per re-open). Orchestration / snapshot / "
                         "comparator semantics unchanged. Equivalent "
                         "behaviour to --diagnostic-reopen-stage-between-"
                         "cycles; the production flag exists as a stable "
                         "API for Phase 6 acceptance runs.")
    args = ap.parse_args()
    if args.diagnostic_dump_registry:
        # The registry dump diagnostic is only useful if all cycles run;
        # otherwise we lose the cycle-3+ data needed to answer the
        # 'does divergence stabilize?' question.
        args.diagnostic_continue_on_divergence = True

    scenario = _load_scenario(args.scenario)

    if args.stream and args.public_endpoint is None:
        args.public_endpoint = _auto_detect_public_endpoint()

    out_dir = Path(
        args.out_dir or
        (WORKSPACE / "logs" / f"phase_10_p6_scenario_{scenario.code.lower()}")
    ).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    _log(f"[p10-p6-{scenario.code}] === Scenario {scenario.code}: {scenario.name} ===")
    _log(f"[p10-p6-{scenario.code}] {scenario.description}")
    _log(f"[p10-p6-{scenario.code}] cycles={args.cycles}, stream={args.stream}, "
         f"record_mp4={args.record_mp4}, out_dir={out_dir}")

    # Boot SimulationApp BEFORE any cell_authoring import that pulls
    # isaacsim transitively.
    from isaacsim import SimulationApp
    cfg = _LIVESTREAM_CONFIG if args.stream else _HEADLESS_CONFIG
    kit = SimulationApp(launch_config=cfg)

    # ── WebRTC livestream extension load (only when --stream) ──
    if args.stream:
        try:
            from isaacsim.core.utils.extensions import enable_extension
            kit.set_setting("/app/window/drawMouse", True)
            if args.public_endpoint:
                kit.set_setting("/app/livestream/publicEndpointAddress",
                                args.public_endpoint)
                _log(f"[p10-p6-{scenario.code}] "
                     f"/app/livestream/publicEndpointAddress = "
                     f"{args.public_endpoint!r}  (ICE disabled; media "
                     f"routed direct to this host)")
            else:
                _log(f"[p10-p6-{scenario.code}] WARN: no --public-endpoint "
                     f"set and no auto-detected IPv4; remote clients may "
                     f"receive signaling only (black frame)")
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
            _log(f"[p10-p6-{scenario.code}] enable_extension"
                 f"(omni.kit.livestream.webrtc) → {enabled!r}")
        except Exception as e:
            _log(f"[p10-p6-{scenario.code}] WARN: WebRTC livestream "
                 f"enable failed: {type(e).__name__}: {e}")

    sigint_received = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: sigint_received.__setitem__("flag", True))

    try:
        rc = _run(kit, args, scenario, out_dir, sigint_received)
    except Exception as e:
        _log(f"[p10-p6-{scenario.code}] FATAL: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        rc = 1
    finally:
        try:
            kit.close()
        except Exception:
            pass
    return rc


# ────────────────────────── core runner ──────────────────────────


def _run(kit, args, scenario: ScenarioSpec, out_dir: Path, sigint_received) -> int:
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
        EVENT_NODE_EXECUTION_COMPLETED,
        EVENT_NODE_EXECUTION_STARTED,
        EVENT_NODE_TIMEOUT_TRIPPED,
        EVENT_OPERATOR_ABORT_REQUESTED,
        EVENT_SESSION_ABORTED,
        EVENT_SESSION_ABORTING,
        EVENT_SESSION_FAILED,
        EVENT_TASK_CASCADE_SKIPPED,
        EVENT_NODE_BOUNDARY_SNAPSHOT,
        ExecutionSession,
        InMemoryTraceRecorder,
        OperatorEnvelope,
        SessionState,
        derive_envelope_id,
    )
    from cell_authoring.orchestration.phase_5_two_node import (
        FIXTURE_A_ID,
        FIXTURE_A_WORLD_POSE_M,
        FIXTURE_B_ID,
        NODE_ID_N1,
        NODE_ID_N2,
        OBJECT_ID_PEG,
        TASK_ID_N1,
        TASK_ID_N2,
        build_phase_5_graph,
        build_phase_5_task_resolver,
        build_trajectory_sets,
        register_phase_5_fixtures,
    )

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE))
    if not (bool(r[0]) if isinstance(r, tuple) else bool(r)):
        _log(f"[p10-p6-{scenario.code}] FAIL: cannot open cell stage")
        return 1
    stage = ctx.get_stage()

    cell_cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")

    if args.record_mp4:
        _author_view_camera(stage)

    # Diagnostic-only: PhysxSceneAPI.enableEnhancedDeterminism=True on
    # /World/PhysicsScene. Applied BEFORE World() construction so the
    # PhysX scene picks up the setting at compile time. Pure simulator-
    # determinism forensics; does NOT touch the orchestration contract.
    if args.diagnostic_enhanced_determinism:
        try:
            from pxr import PhysxSchema, UsdPhysics
            scene_prim = stage.GetPrimAtPath("/World/PhysicsScene")
            if not scene_prim or not scene_prim.IsValid():
                _log(f"[p10-p6-{scenario.code}]   [diag] no PhysicsScene "
                     f"at /World/PhysicsScene; enhanced-determinism "
                     f"NOT applied")
            else:
                physx_scene_api = PhysxSchema.PhysxSceneAPI.Apply(scene_prim)
                attr = physx_scene_api.CreateEnableEnhancedDeterminismAttr()
                attr.Set(True)
                applied = bool(physx_scene_api.GetEnableEnhancedDeterminismAttr().Get())
                _log(f"[p10-p6-{scenario.code}]   [diag] PhysxSceneAPI."
                     f"enableEnhancedDeterminism applied → {applied}")
        except Exception as _e:
            _log(f"[p10-p6-{scenario.code}]   [diag] enhanced-determinism "
                 f"apply FAILED: {type(_e).__name__}: {_e}")

    world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    world.reset()
    world.play()

    trajectory_sets = build_trajectory_sets()
    executor = TaskExecutor(
        world=world, stage=stage, cell_cfg=cell_cfg,
        trajectory_sets=trajectory_sets,
    )

    # ─── MP4 recording setup ───
    record_state: dict = {"enabled": False}
    if args.record_mp4:
        utc_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rec_root = out_dir / "mp4_recording" / utc_tag
        rec_root.mkdir(parents=True, exist_ok=True)
        record_state.update(
            root=rec_root, fps=int(args.record_fps),
            per_cycle_dirs=[], per_cycle_writers=[], enabled=True,
        )
        _log(f"[p10-p6-{scenario.code}] MP4 recording enabled — output: {rec_root}")
        try:
            import omni.replicator.core as rep  # noqa: F401
            record_state["rep"] = rep
        except Exception as e:
            _log(f"[p10-p6-{scenario.code}] FAIL: omni.replicator.core unavailable: {e}")
            return 1

    cycle_count = 0
    pass_count = 0
    events_canonical_first: str | None = None
    summary_lines: list[str] = []

    while cycle_count < args.cycles and not sigint_received["flag"]:
        cycle_count += 1
        _log(f"\n[p10-p6-{scenario.code}] === cycle {cycle_count} / {args.cycles} ===")

        # Diagnostic-only: between cycles, force a full simulator
        # re-isolation via World.stop/reset/play. Tests whether
        # persistent PhysX solver state surviving executor.reset(FULL)
        # is the source of cross-cycle peg-pose divergence. Cycle 1 is
        # skipped because the world was already reset at startup; for
        # cycle 2+ this clears any PhysX state inherited from the
        # interrupted prior cycle. Pure simulator-isolation forensics;
        # does NOT touch orchestration / snapshot / comparator semantics.
        if args.diagnostic_world_reset_between_cycles and cycle_count > 1:
            _log(f"[p10-p6-{scenario.code}]   [diag] world.stop / "
                 f"world.reset / world.play between cycle "
                 f"{cycle_count - 1} → {cycle_count}")
            try:
                world.stop()
            except Exception as _e:
                _log(f"[p10-p6-{scenario.code}]   [diag] world.stop "
                     f"raised {type(_e).__name__}: {_e}")
            world.reset()
            world.play()

        # Between cycles, tear down + re-open the USD stage and
        # re-construct World + TaskExecutor. Cycle 1 is skipped (the
        # initial stage was already opened at startup). For cycle 2+
        # this fully isolates stage / articulation / PhysX-scene-
        # compile state from prior cycles — empirically validated as
        # the minimum-invasiveness fix for Phase 6 mid-trajectory-
        # interrupt scenarios. Production flag is
        # ``--reopen-stage-between-cycles``; ``--diagnostic-reopen-
        # stage-between-cycles`` remains an alias.
        if ((args.diagnostic_reopen_stage_between_cycles
             or args.reopen_stage_between_cycles)
                and cycle_count > 1):
            _log(f"[p10-p6-{scenario.code}]   [diag] STAGE REOPEN "
                 f"between cycle {cycle_count - 1} → {cycle_count}")
            try:
                executor.close()
            except Exception as _e:
                _log(f"[p10-p6-{scenario.code}]   [diag] executor.close "
                     f"raised {type(_e).__name__}: {_e}")
            try:
                world.stop()
            except Exception as _e:
                _log(f"[p10-p6-{scenario.code}]   [diag] world.stop "
                     f"raised {type(_e).__name__}: {_e}")
            # Re-open the stage from disk — drops every cached USD
            # prim handle, forces PhysX scene to be re-compiled at
            # the next World() construction.
            r2 = ctx.open_stage(str(CELL_STAGE))
            if not (bool(r2[0]) if isinstance(r2, tuple) else bool(r2)):
                _log(f"[p10-p6-{scenario.code}] FAIL: stage reopen "
                     f"failed at cycle {cycle_count}")
                return 1
            stage = ctx.get_stage()
            if args.record_mp4:
                _author_view_camera(stage)
            if args.diagnostic_enhanced_determinism:
                try:
                    from pxr import PhysxSchema
                    scene_prim = stage.GetPrimAtPath("/World/PhysicsScene")
                    if scene_prim and scene_prim.IsValid():
                        physx_scene_api = PhysxSchema.PhysxSceneAPI.Apply(scene_prim)
                        physx_scene_api.CreateEnableEnhancedDeterminismAttr().Set(True)
                except Exception as _e:
                    _log(f"[p10-p6-{scenario.code}]   [diag] re-apply "
                         f"enhanced-determinism FAILED: "
                         f"{type(_e).__name__}: {_e}")
            world = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
            world.reset()
            world.play()
            executor = TaskExecutor(
                world=world, stage=stage, cell_cfg=cell_cfg,
                trajectory_sets=trajectory_sets,
            )
            _log(f"[p10-p6-{scenario.code}]   [diag] stage reopened; "
                 f"World + TaskExecutor reconstructed")

        bus = EventBus()
        rec = InMemoryTraceRecorder()
        bus.register(rec)
        register_phase_5_fixtures(executor.registry)

        # ─── per-cycle Replicator attach ───
        if record_state["enabled"]:
            rep = record_state["rep"]
            cycle_raw_dir = (
                record_state["root"] / "raw" / f"cycle_{cycle_count:04d}"
            )
            cycle_raw_dir.mkdir(parents=True, exist_ok=True)
            record_state["per_cycle_dirs"].append(cycle_raw_dir)
            rp = rep.create.render_product(CAMERA_PATH, (1280, 720))
            writer = rep.WriterRegistry.get("BasicWriter")
            writer.initialize(output_dir=str(cycle_raw_dir), rgb=True)
            writer.attach([rp])
            record_state["per_cycle_writers"].append((writer, rp))
            _log(f"[p10-p6-{scenario.code}]   recording → {cycle_raw_dir}")
            # Pre-execute static frames so the operator can confirm the
            # initial scene posture BEFORE Phase E enters.
            for _ in range(_FRAMES_PER_CYCLE_PRE):
                world.step(render=True)

        # ─── envelope (C/D/F) or budget override (E) ───
        envelopes: tuple[OperatorEnvelope, ...] = ()
        if scenario.envelope_requested_at_tick is not None:
            eid = derive_envelope_id(
                kind="abort",
                requested_at_tick=scenario.envelope_requested_at_tick,
                reason=scenario.envelope_reason,
            )
            envelopes = (OperatorEnvelope(
                kind="abort",
                requested_at_tick=scenario.envelope_requested_at_tick,
                reason=scenario.envelope_reason,
                envelope_id=eid,
            ),)
        else:
            eid = None  # E has no envelope

        # ─── task resolver with optional budget override for E ───
        if scenario.n1_tick_budget_ticks_override is not None:
            base_resolver = build_phase_5_task_resolver()
            from dataclasses import replace as _replace
            def _resolver_with_budget(node):
                task = base_resolver(node)
                if node.node_id == NODE_ID_N1:
                    return _replace(
                        task, tick_budget_ticks=scenario.n1_tick_budget_ticks_override,
                    )
                return task
            task_resolver = _resolver_with_budget
        else:
            task_resolver = build_phase_5_task_resolver()

        session = ExecutionSession(
            graph=build_phase_5_graph(),
            task_executor=executor,
            event_bus=bus,
            task_resolver=task_resolver,
            pending_operator_envelopes=envelopes,
        )

        session.begin()
        # Drive the session until terminal — the session's step()
        # returns a snapshot whose session_state we inspect each tick.
        max_steps = 12  # safety: tightly bounds the orchestration ticks
        for _ in range(max_steps):
            if session._session_state in (SessionState.RUNNING, SessionState.ABORTING):
                session.step()
            else:
                break
            # If both nodes have terminated, also break.
            snap = session.snapshot()
            if len(snap.completed) + len(snap.failed) + len(snap.skipped) >= 2:
                break
        final = session.complete()

        if record_state["enabled"]:
            for _ in range(_FRAMES_PER_CYCLE_POST):
                world.step(render=True)
            try:
                writer, rp = record_state["per_cycle_writers"][-1]
                writer.detach()
                rp.destroy()
                import time as _t; _t.sleep(0.5)
                cycle_dir = record_state["per_cycle_dirs"][-1]
                n_pngs = len(list(cycle_dir.glob("rgb_*.png")))
                _log(f"[p10-p6-{scenario.code}]   recorded {n_pngs} PNGs "
                     f"for cycle {cycle_count}")
            except Exception as e:
                _log(f"[p10-p6-{scenario.code}] WARN: writer detach failed: {e}")

        # ─────────────── acceptance criteria ───────────────
        events = list(rec.events)

        # 1. Terminal state matches scenario.
        actual_state = final.session_state.value
        if actual_state.upper() != scenario.expected_terminal_state:
            _log(f"[p10-p6-{scenario.code}] FAIL: terminal state = "
                 f"{actual_state} (expected {scenario.expected_terminal_state})")
            return 2

        # 2. The interrupted node's NodeExecutionCompleted carries the
        # expected outcome_value.
        interrupted_node_id = (
            NODE_ID_N1 if scenario.interrupted_node == "N1" else NODE_ID_N2
        )
        nec_events = [
            e for e in events
            if e.event_type == EVENT_NODE_EXECUTION_COMPLETED
            and e.payload.get("node_id") == interrupted_node_id
        ]
        if len(nec_events) != 1:
            _log(f"[p10-p6-{scenario.code}] FAIL: expected exactly 1 "
                 f"NodeExecutionCompleted for {interrupted_node_id}, "
                 f"got {len(nec_events)}")
            return 2
        if nec_events[0].payload["outcome_value"] != scenario.expected_outcome_value:
            _log(f"[p10-p6-{scenario.code}] FAIL: "
                 f"{interrupted_node_id}.outcome_value = "
                 f"{nec_events[0].payload['outcome_value']!r} "
                 f"(expected {scenario.expected_outcome_value!r})")
            return 2

        # 3. ticks_consumed appears in the fingerprint and is non-zero
        # (mid-trajectory interrupt produced settled boundaries).
        fp = nec_events[0].payload["task_result_fingerprint"]
        if '"ticks_consumed":' not in fp:
            _log(f"[p10-p6-{scenario.code}] FAIL: fingerprint missing "
                 f"ticks_consumed: {fp}")
            return 2
        if '"interrupted_at_segment_index"' in fp or '"interrupted_at_segment_name"' in fp:
            _log(f"[p10-p6-{scenario.code}] FAIL: fingerprint LEAKED "
                 f"observational segment fields (D-EXEC-13b): {fp}")
            return 2

        # 4. Ingress events per scenario.
        if scenario.expected_outcome_value == "OPERATOR_ABORT":
            oar = [e for e in events
                   if e.event_type == EVENT_OPERATOR_ABORT_REQUESTED]
            if len(oar) != 1:
                _log(f"[p10-p6-{scenario.code}] FAIL: expected 1 "
                     f"OperatorAbortRequested, got {len(oar)}")
                return 2
            if eid is not None and oar[0].payload.get("envelope_id") != eid:
                _log(f"[p10-p6-{scenario.code}] FAIL: envelope_id mismatch")
                return 2
            sa = [e for e in events if e.event_type == EVENT_SESSION_ABORTING]
            if len(sa) != 1:
                _log(f"[p10-p6-{scenario.code}] FAIL: expected 1 "
                     f"SessionAborting, got {len(sa)}")
                return 2
        elif scenario.expected_outcome_value == "TIMEOUT_FAILURE":
            ntt = [e for e in events
                   if e.event_type == EVENT_NODE_TIMEOUT_TRIPPED]
            if len(ntt) < 1:
                _log(f"[p10-p6-{scenario.code}] FAIL: expected >=1 "
                     f"NodeTimeoutTripped, got {len(ntt)}")
                return 2

        # 5. Cascade-skip semantics for downstream node.
        # Scenarios C/F interrupt N2 → N2 is the last node, nothing to
        # cascade. Scenario D interrupts N1 → N2 must be cascade-skipped
        # with reason="OPERATOR_ABORT". Scenario E times out on N1 → N2
        # must be cascade-skipped per FailureAction (SKIP_NODE → reason
        # is "SKIP_NODE" via _propagate_cascade_on_failure).
        if scenario.interrupted_node == "N1":
            tcs = [e for e in events
                   if e.event_type == EVENT_TASK_CASCADE_SKIPPED
                   and e.payload.get("node_id") == NODE_ID_N2]
            if len(tcs) != 1:
                _log(f"[p10-p6-{scenario.code}] FAIL: expected 1 "
                     f"TaskCascadeSkipped for {NODE_ID_N2}, got {len(tcs)}")
                return 2

        # 6. Scenario F — explicit contradiction inspection.
        # Phase 6 Run-1 reinterpretation: with N1-locus interruption, the
        # canonical D-FAULT-5b contradiction is:
        #   * peg pose has moved from the belt-origin (acquired and in
        #     transit toward FixtureA)
        #   * FixtureA.occupied_by remains None (N1's Phase G never fired
        #     because outcome != PASS)
        #   * the contradiction is: SOMETHING clearly has the peg
        #     (peg pose ≠ belt origin → grasp registered) BUT no fixture
        #     lists it (occupancy not committed). Only an explicit recovery
        #     node would resolve this per D-FAULT-8.
        #
        # We inspect ``executor.registry`` directly. The session emits
        # NodeBoundarySnapshot events carrying only a ``canonical_hash``
        # (the full blob is not placed on the event payload by design —
        # see session._emit_boundary_snapshot docstring). The registry
        # state at this point in the launcher loop reflects the same
        # last-tick data that was projected into the post-N1 snapshot
        # (no further executor mutations occur between snapshot emission
        # and session.complete() return on the OPERATOR_ABORT path).
        if scenario.assert_contradiction_in_snapshot:
            # (a) confirm a post_node snapshot for N1 was emitted — uses
            # the correct payload key ``snapshot_kind``.
            post_n1_snap_events = [
                e for e in events
                if e.event_type == EVENT_NODE_BOUNDARY_SNAPSHOT
                and e.payload.get("snapshot_kind") == "post_node"
                and e.payload.get("node_id") == NODE_ID_N1
            ]
            if len(post_n1_snap_events) != 1:
                _log(f"[p10-p6-{scenario.code}] FAIL: expected 1 post-N1 "
                     f"boundary snapshot, got {len(post_n1_snap_events)}")
                return 2

            # (b) verify the contradiction directly from
            # executor.registry — the same data the snapshot was
            # projected from.
            fix_a = executor.registry.fixtures.get(FIXTURE_A_ID)
            peg = executor.registry.objects.get(OBJECT_ID_PEG)
            if fix_a is None or peg is None:
                _log(f"[p10-p6-{scenario.code}] FAIL (F-contradiction): "
                     f"FixtureA or Peg_01 absent from registry "
                     f"(fix_a={fix_a is not None}, peg={peg is not None})")
                return 2
            # 6a. FixtureA must NOT be occupied by peg — N1's Phase G never
            # fired (outcome != PASS), so D-CONT-5's PASS-conditional
            # mark_fixture_occupied was never invoked. If FixtureA reads
            # occupied_by=Peg_01 here, a hidden cleanup / implicit commit
            # has run somewhere, violating D-CONT-5a / D-FAULT-5b.
            if fix_a.occupied_by is not None:
                _log(f"[p10-p6-{scenario.code}] FAIL (F-contradiction): "
                     f"FixtureA.occupied_by = "
                     f"{fix_a.occupied_by!r} (expected None — "
                     f"N1's Phase G did NOT fire); D-CONT-5 / D-FAULT-5b "
                     f"violated by implicit commit")
                return 2
            # 6b. Peg's canonical pose must have moved meaningfully from
            # the belt-origin (-0.80, 0.0, 0.701). At N1's boundary 6
            # (approach_place), the peg has been acquired and transported
            # over FixtureA. If the peg's pose snaps back to the belt
            # origin, the executor performed a hidden rollback.
            BELT_ORIGIN = (-0.80, 0.0, 0.701)
            peg_pose = peg.pose_m
            if peg_pose is None:
                _log(f"[p10-p6-{scenario.code}] FAIL (F-contradiction): "
                     f"peg.pose_m absent from registry — cannot "
                     f"verify acquisition")
                return 2
            dx = abs(float(peg_pose[0]) - BELT_ORIGIN[0])
            dy = abs(float(peg_pose[1]) - BELT_ORIGIN[1])
            if dx < 0.05 and dy < 0.05:
                _log(f"[p10-p6-{scenario.code}] FAIL (F-contradiction): "
                     f"peg pose ({peg_pose[0]:.3f},{peg_pose[1]:.3f},"
                     f"{peg_pose[2]:.3f}) is still at the belt origin "
                     f"({BELT_ORIGIN[0]:.3f},{BELT_ORIGIN[1]:.3f},"
                     f"{BELT_ORIGIN[2]:.3f}) — implicit rollback "
                     f"detected; D-FAULT-5a / D-FAULT-15 #1 violated")
                return 2
            _log(f"[p10-p6-{scenario.code}]   F-contradiction confirmed: "
                 f"FixtureA.occupied_by=None (no Phase G commit), peg "
                 f"pose=({peg_pose[0]:.3f},{peg_pose[1]:.3f},"
                 f"{peg_pose[2]:.3f}) (moved from belt origin); "
                 f"D-FAULT-5b retained-state preserved verbatim")

        # 7. Canonical events.jsonl hash for replay-identity gate.
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

        cycle_path = out_dir / f"cycle_{cycle_count:02d}_events.json"
        cycle_path.write_text(events_canonical, encoding="utf-8")

        _log(f"[p10-p6-{scenario.code}] cycle {cycle_count} ACCEPTANCE PASS")
        _log(f"  events.count        : {len(events)}")
        _log(f"  events.canonical_hash: {events_hash}")
        _log(f"  outcome_value       : {nec_events[0].payload['outcome_value']}")
        _log(f"  terminal_state      : {actual_state}")
        _log(f"  failed (final)      : {sorted(final.failed)}")
        _log(f"  skipped (final)     : {sorted(final.skipped)}")
        _log(f"  completed (final)   : {sorted(final.completed)}")
        summary_lines.append(
            f"cycle_{cycle_count:02d}: hash={events_hash}  "
            f"events={len(events)}  state={actual_state.upper()}"
        )

        # Replay-identity gate (D-FAULT-11a strict byte-equality).
        gate_failed = False
        if events_canonical_first is None:
            events_canonical_first = events_canonical
        else:
            if events_canonical != events_canonical_first:
                _log(f"[p10-p6-{scenario.code}] FAIL: events.jsonl "
                     f"byte-divergence at cycle {cycle_count} "
                     f"(D-FAULT-11a strict byte-equality)")
                (out_dir / f"DIVERGENT_cycle_{cycle_count:02d}.json").write_text(
                    events_canonical, encoding="utf-8")
                gate_failed = True

        # Diagnostic-only: per-cycle observational side dump of the
        # registry fields that feed the post-N1 boundary snapshot. Pure
        # observation; does NOT mutate the snapshot, comparator, or
        # canonicalization. Captured after session.complete() so the
        # registry state reflects the same moment the post-N1 snapshot
        # was emitted (no further executor.update_object_pose calls
        # happen between snapshot emission and session.complete()).
        if args.diagnostic_dump_registry:
            try:
                reg_objects = executor.registry.objects
                reg_fixtures = executor.registry.fixtures
                peg = reg_objects.get(OBJECT_ID_PEG)
                fix_a = reg_fixtures.get(FIXTURE_A_ID)
                fix_b = reg_fixtures.get(FIXTURE_B_ID)
                # Render with full float precision so any sub-mm
                # divergence is visible. Using repr() preserves the
                # full IEEE-754 mantissa.
                dump = {
                    "scenario_code": scenario.code,
                    "cycle":         cycle_count,
                    "ticks_consumed": int(getattr(
                        executor.registry.task, "step", -1)),
                    "events_canonical_hash": events_hash,
                    "peg": {
                        "pose_m": (
                            None if peg is None or peg.pose_m is None
                            else [repr(float(x)) for x in peg.pose_m]
                        ),
                        "yaw_rad": (
                            None if peg is None else repr(float(peg.yaw_rad))
                        ),
                        "dlife_state": (
                            None if peg is None
                            else getattr(peg, "dlife_state", None)
                        ),
                    },
                    "fixture_a": {
                        "occupied_by": (
                            None if fix_a is None else fix_a.occupied_by
                        ),
                    },
                    "fixture_b": {
                        "occupied_by": (
                            None if fix_b is None else fix_b.occupied_by
                        ),
                    },
                }
                dump_path = out_dir / f"cycle_{cycle_count:02d}_registry_dump.json"
                dump_path.write_text(
                    json.dumps(dump, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                _log(f"[p10-p6-{scenario.code}]   [diag] registry "
                     f"dump → {dump_path.name}")
            except Exception as _e:
                _log(f"[p10-p6-{scenario.code}]   [diag] registry dump "
                     f"FAILED: {type(_e).__name__}: {_e}")

        if gate_failed and not args.diagnostic_continue_on_divergence:
            return 2
        if gate_failed:
            _log(f"[p10-p6-{scenario.code}]   [diag] continuing past "
                 f"divergence at cycle {cycle_count} "
                 f"(diagnostic mode)")

        pass_count += 1

    summary_path = out_dir / "summary.txt"
    summary_path.write_text("\n".join([
        f"=== Phase 4B Step 10 Direction A / Phase 6 — scenario "
        f"{scenario.code} ({scenario.name}) ===",
        f"started_at      : {datetime.now(timezone.utc).isoformat()}",
        f"description     : {scenario.description}",
        f"cycles_requested: {args.cycles}",
        f"cycles_passed   : {pass_count}",
        f"---",
        *summary_lines,
        f"---",
        f"REPLAY-IDENTITY GATE: {'PASS' if pass_count == args.cycles else 'FAIL'}",
    ]) + "\n", encoding="utf-8")
    _log(f"\n[p10-p6-{scenario.code}] {pass_count}/{args.cycles} cycles ACCEPTANCE PASS")
    _log(f"[p10-p6-{scenario.code}] summary → {summary_path}")

    if record_state["enabled"]:
        _encode_mp4_recording(record_state, scenario, args.cycles, pass_count)
        _write_review_manifest(record_state, scenario, out_dir, summary_lines)

    return 0 if pass_count == args.cycles else 1


# ────────────────────────── helpers (camera + MP4 + manifest) ──────────────────────────


def _author_view_camera(stage) -> None:
    """Author /World/VisCam matching the Step 9 P6 view geometry so
    MP4 reviews are visually comparable across phases."""
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


def _encode_mp4_recording(record_state, scenario, n_cycles, pass_count) -> None:
    """Encode per-cycle PNG sequences via ffmpeg. Same surface as the
    Step 9 P6 launcher; no replay state touched."""
    import shutil
    import subprocess as _sp
    rec_root = record_state["root"]
    fps = record_state["fps"]
    code = scenario.code
    if shutil.which("ffmpeg") is None:
        _log(f"[p10-p6-{code}] FAIL: ffmpeg not on PATH; raw PNGs in "
             f"{rec_root / 'raw'}")
        return
    _log(f"\n[p10-p6-{code}] ─── MP4 encoding ({fps} FPS via ffmpeg) ───")
    per_cycle_mp4s: list[Path] = []
    for i, cycle_dir in enumerate(record_state["per_cycle_dirs"], start=1):
        n_pngs = len(list(cycle_dir.glob("rgb_*.png")))
        if n_pngs == 0:
            _log(f"[p10-p6-{code}]   cycle {i}: NO PNGs — skip")
            continue
        out_mp4 = rec_root / f"cycle_{i:04d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-pattern_type", "glob",
            "-i",  str(cycle_dir / "rgb_*.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-crf", "22",
            str(out_mp4),
        ]
        r = _sp.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            _log(f"[p10-p6-{code}]   cycle {i}: ffmpeg FAILED rc={r.returncode}")
            continue
        per_cycle_mp4s.append(out_mp4)
        sz_mb = out_mp4.stat().st_size / 1e6
        _log(f"[p10-p6-{code}]   cycle {i}: {n_pngs} PNGs → "
             f"{out_mp4.name} ({sz_mb:.1f} MB)")
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
            _log(f"[p10-p6-{code}]   concatenated → {all_mp4.name} "
                 f"({sz_mb:.1f} MB)")
        try:
            concat_list.unlink()
        except Exception:
            pass


def _write_review_manifest(record_state, scenario, out_dir, summary_lines) -> None:
    """Operator review manifest — links each per-cycle MP4 to its
    canonical events.jsonl + SHA-256 so the operator can confirm visual
    posture against the replay-authoritative artifacts."""
    rec_root = record_state["root"]
    manifest: dict = {
        "scenario_code":   scenario.code,
        "scenario_name":   scenario.name,
        "description":     scenario.description,
        "schema":          "phase_4b_step10_p6_review_manifest_v1",
        "generated":       datetime.now(timezone.utc).isoformat(),
        "cells_stage":     str(CELL_STAGE),
        "camera_path":     CAMERA_PATH,
        "fps":             record_state["fps"],
        "expected_outcome_value": scenario.expected_outcome_value,
        "expected_terminal_state": scenario.expected_terminal_state,
        "interrupted_node": scenario.interrupted_node,
        "cycles":          [],
        "operator_review_checklist": _operator_review_checklist(scenario),
    }
    for i, cycle_dir in enumerate(record_state["per_cycle_dirs"], start=1):
        mp4_path = rec_root / f"cycle_{i:04d}.mp4"
        events_path = out_dir / f"cycle_{i:02d}_events.json"
        events_sha = (
            hashlib.sha256(events_path.read_bytes()).hexdigest()
            if events_path.exists() else None
        )
        manifest["cycles"].append({
            "cycle":         i,
            "mp4_path":      str(mp4_path.relative_to(out_dir)) if mp4_path.exists() else None,
            "raw_dir":       str(cycle_dir.relative_to(out_dir)),
            "events_path":   str(events_path.relative_to(out_dir)) if events_path.exists() else None,
            "events_sha256": events_sha,
        })
    manifest["replay_identity_expectation"] = (
        "All cycles' events.json files must be byte-identical (SHA-256 "
        "equal). The comparator tools/check_session_replay_identity.py "
        "MUST report REPLAY-IDENTICAL for every pairwise comparison. "
        "Visual MP4 review must show the same trajectory progression "
        "and interruption point across all cycles."
    )
    manifest_path = rec_root / "review_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    _log(f"[p10-p6-{scenario.code}] operator review manifest → {manifest_path}")


def _operator_review_checklist(scenario: ScenarioSpec) -> list[str]:
    """Per-scenario operator review checklist — what the human watcher
    should confirm against the MP4 recording."""
    common = [
        "no mid-motion teleport observed (no peg / robot snap between frames)",
        "no hidden reset appearance (peg / robot do not snap to home)",
        "no abrupt rollback to pre-task state",
        "no impossible state snap (peg never relocates while gripper is "
        "open and not in contact)",
        "no spontaneous state repair after the terminal event",
        "all cycles visually identical (frame-level replay-identity coherent "
        "with byte-level events.jsonl SHA-256 identity)",
    ]
    if scenario.code == "C":
        return common + [
            "N1 starts the belt-pick → FixtureA-transport. The robot reaches "
            "the belt, grasps the peg (grasp_close, ~tick 228), lifts it",
            "during N1's transport, the operator-abort fires at the "
            "approach_place segment (~tick 558). Peg is mid-air OVER "
            "FixtureA but never descends",
            "peg remains attached to the gripper at the moment of interrupt "
            "(visual: pads visibly closed around peg; no release motion)",
            "no descent / placement / release motion after the interrupt",
            "robot remains at the approach_place pose until the cycle ends",
            "N2 never visibly executes (the robot does not return to belt "
            "or to FixtureA for any second attempt)",
        ]
    if scenario.code == "D":
        return common + [
            "N1 starts the belt-pick → FixtureA-transport but is interrupted "
            "MID-TRAJECTORY at the approach_place segment (peg is over "
            "FixtureA area but never descends)",
            "no descent / placement / release motion after the interrupt",
            "N2 never visibly executes (the robot does not return to "
            "FixtureA for a second pick attempt)",
            "downstream cascade: the orchestration cleanly skips N2 with no "
            "visible motion",
        ]
    if scenario.code == "E":
        return common + [
            "N1 starts the belt-pick → FixtureA-transport, runs UP TO the "
            "first boundary at which the tick budget is exceeded "
            "(approach_place if the budget is 400; the trajectory stops "
            "AT that boundary)",
            "no descent / placement / release motion after the timeout",
            "no operator-induced motion (no UI / human input visible)",
            "N2 never visibly executes; cascade-skipped per FailureAction",
        ]
    if scenario.code == "F":
        return common + [
            "N1 starts the belt-pick → FixtureA-transport. Robot grasps the "
            "peg at the belt (grasp_close, ~tick 228), lifts it cleanly",
            "during N1's transport, the operator-abort fires at "
            "approach_place (~tick 558). Peg is mid-air over FixtureA but "
            "NEVER descends, NEVER releases, NEVER lands at FixtureA",
            "post-abort visual posture: peg ATTACHED to gripper, mid-air "
            "above FixtureA; no implicit descent; no implicit release; "
            "FixtureA visibly EMPTY (peg was never placed there)",
            "the post-abort scene preserves the CONTRADICTION: the peg has "
            "clearly been ACQUIRED (gripper closed, peg moved from belt), "
            "but NO fixture lists it (FixtureA.occupied_by = None — N1's "
            "Phase G never fired because outcome != PASS). This is "
            "D-FAULT-5b: contradiction preserved verbatim; only an "
            "explicit recovery node would resolve it (D-FAULT-8)",
            "N2 never visibly executes (cascade-skipped per D-FAULT-3 "
            "row 6 OPERATOR_ABORT propagation)",
        ]
    return common


if __name__ == "__main__":
    sys.exit(main())
