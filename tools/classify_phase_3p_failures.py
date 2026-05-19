#!/usr/bin/env python3
"""Phase 3P — failure taxonomy classifier.

Reads a Phase 3P robustness run's ``cycles.jsonl`` and classifies each
cycle into PASS or one of a fixed failure category, then prints
aggregate robustness statistics.

Pure Python. Reads the per-cycle summary records emitted by
``scripts/phase_3p_robustness_harness.py``. Decoupled from Kit / PhysX
so it can be invoked from any environment, CI, or test harness.

Categories (most-specific-first, first match wins):

  GRASP_NEVER_ACQUIRED
      ``grasp_acquired_step`` is None — pads never made sustained contact.
      Almost always means the peg arrived outside the jaws.

  GRASP_LOST_IN_TRANSPORT
      ``grasp_lost_in_transport_step`` is non-None — the pads released
      the peg before the deliberate release waypoint began.

  FLOOR_OR_BELT_TRANSPORT_CONTACT
      The peg touched the floor or belt during the strict transport
      window (= lift_end_step ≤ step < release_start_step). This is the
      "peg fell during transport" failure mode. We deliberately exclude
      contact at the grasp_close boundary itself, since the peg is
      legitimately still sitting on the belt at the moment the close
      finishes (the lift hasn't started yet).

  PLACEMENT_MISS
      ``peg_xyz_final`` farther than tolerance from the place target
      (default tol 50 mm XY).

  WRIST_3_OUT_OF_BOUNDS
      ``wrist_3_max_z_m`` > 1.10 m (= Phase 3O visual-believability
      ceiling).

  PEG_OUT_OF_BOUNDS
      ``peg_max_z_m`` > 1.10 m (= Phase 3O ceiling).

  MOTION_QUALITY_VIOLATION
      ``joint_vel_peak_rad_s`` > 6.0 OR ``ee_speed_peak_mps`` > 1.5 OR
      ``cartesian_path_length_m`` > 6.0 — the Phase 3O motion-quality
      gates expressed at single-cycle granularity.

  PASS — none of the above.

Usage:

  python tools/classify_phase_3p_failures.py \
      logs/phase_3p_robustness/endurance_100/cycles.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


PLACE_TARGET_XY_M  = (0.65, 0.00)
PLACE_TOL_XY_M     = 0.050
WRIST_3_CEILING_M  = 1.10
PEG_CEILING_M      = 1.10
JOINT_VEL_LIMIT    = 6.0      # rad/s
EE_SPEED_LIMIT     = 1.5      # m/s
CART_PATH_LIMIT    = 6.0      # m


def classify_cycle(rec: dict, *, lift_end_step: int | None = None) -> tuple[str, str]:
    """Return (category, detail). Category is "PASS" or a failure tag."""
    lift_end_step = lift_end_step or rec.get("lift_end_step")

    # 1. grasp never acquired
    if rec.get("grasp_acquired_step") is None:
        return ("GRASP_NEVER_ACQUIRED",
                "pads never both made sustained contact — peg arrived outside jaws "
                f"(peg final z = {rec['peg_xyz_final'][2]:.4f})")

    # 2. grasp lost mid-transport
    if rec.get("grasp_lost_in_transport_step") is not None:
        return ("GRASP_LOST_IN_TRANSPORT",
                f"pads broke contact at step {rec['grasp_lost_in_transport_step']} "
                f"before release_start_step={rec.get('release_start_step')}")

    # 3. transport-window surface contact (exclude step at grasp_close boundary)
    fb = rec.get("floor_or_belt_first_post_close")
    if fb is not None and lift_end_step is not None and fb >= lift_end_step:
        if fb < rec.get("release_start_step", 10**9):
            return ("FLOOR_OR_BELT_TRANSPORT_CONTACT",
                    f"peg touched floor/belt at step {fb} during transport "
                    f"({lift_end_step} ≤ step < {rec.get('release_start_step')})")

    # 4. placement miss
    peg_f = rec.get("peg_xyz_final")
    if peg_f is None:
        return ("UNKNOWN_NO_FINAL_POSE", "peg_xyz_final missing from record")
    dx = abs(peg_f[0] - PLACE_TARGET_XY_M[0])
    dy = abs(peg_f[1] - PLACE_TARGET_XY_M[1])
    if dx > PLACE_TOL_XY_M or dy > PLACE_TOL_XY_M:
        return ("PLACEMENT_MISS",
                f"peg final XY = ({peg_f[0]:+.4f}, {peg_f[1]:+.4f}), "
                f"target ({PLACE_TARGET_XY_M[0]:+.3f}, {PLACE_TARGET_XY_M[1]:+.3f}), "
                f"tol ±{PLACE_TOL_XY_M*1000:.0f}mm; Δxy = ({dx*1000:+.1f}, {dy*1000:+.1f}) mm")

    # 5. wrist_3 out of bounds
    w3 = rec.get("wrist_3_max_z_m", 0.0)
    if w3 > WRIST_3_CEILING_M:
        return ("WRIST_3_OUT_OF_BOUNDS",
                f"wrist_3 max z = {w3:.3f} m > {WRIST_3_CEILING_M:.2f} m ceiling")

    # 6. peg out of bounds
    pz = rec.get("peg_max_z_m", 0.0)
    if pz > PEG_CEILING_M:
        return ("PEG_OUT_OF_BOUNDS",
                f"peg max z = {pz:.3f} m > {PEG_CEILING_M:.2f} m ceiling")

    # 7. motion-quality violation
    jv = rec.get("joint_vel_peak_rad_s", 0.0)
    if jv > JOINT_VEL_LIMIT:
        return ("MOTION_QUALITY_VIOLATION",
                f"joint vel peak {jv:.3f} rad/s > {JOINT_VEL_LIMIT:.2f}")
    ee = rec.get("ee_speed_peak_mps", 0.0)
    if ee > EE_SPEED_LIMIT:
        return ("MOTION_QUALITY_VIOLATION",
                f"EE speed peak {ee:.3f} m/s > {EE_SPEED_LIMIT:.2f}")
    cp = rec.get("cartesian_path_length_m", 0.0)
    if cp > CART_PATH_LIMIT:
        return ("MOTION_QUALITY_VIOLATION",
                f"cartesian path length {cp:.3f} m > {CART_PATH_LIMIT:.2f}")

    return ("PASS", "")


def _aggregate(records: list[dict]) -> dict:
    """Compute mean / stddev / min / max for numeric per-cycle metrics."""
    keys = ["peg_max_z_m", "wrist_3_max_z_m", "wrist_3_min_z_m",
            "wrist_reach_horizontal_peak_m",
            "joint_vel_peak_rad_s", "joint_accel_peak_rad_s2",
            "ee_speed_peak_mps", "ee_accel_peak_m_s2",
            "cartesian_path_length_m",
            "pad_pen_min_during_transport_mm", "pad_pen_max_during_transport_mm",
            "grasp_acquired_step", "wall_clock_s"]
    out = {}
    for k in keys:
        vals = [r[k] for r in records if r.get(k) is not None]
        if not vals:
            continue
        out[k] = {
            "mean":  statistics.fmean(vals),
            "stdev": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "min":   min(vals),
            "max":   max(vals),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl_path", type=Path)
    parser.add_argument("--strict-success-rate", type=float, default=None,
                        help="exit non-zero if PASS rate < this fraction (e.g. 0.99)")
    args = parser.parse_args()

    if not args.jsonl_path.is_file():
        print(f"error: log not found: {args.jsonl_path}", file=sys.stderr)
        return 2
    lines = args.jsonl_path.read_text().strip().splitlines()
    if not lines:
        print("error: empty log", file=sys.stderr); return 2

    header = json.loads(lines[0])
    cycle_records = [json.loads(l) for l in lines[1:] if json.loads(l).get("_kind") == "cycle_summary"]
    n_cycles_expected = header.get("n_cycles", "?")
    print(f"\nPhase 3P failure-taxonomy report")
    print(f"  run_tag       : {header.get('run_tag')}")
    print(f"  expected_cycles: {n_cycles_expected}")
    print(f"  cycle_records : {len(cycle_records)}")
    print(f"  seed          : {header.get('seed')}")
    print(f"  no_perturb    : {header.get('no_perturb')}")
    print()

    classifications: list[tuple[int, str, str]] = []
    cat_counts: Counter = Counter()
    for rec in cycle_records:
        cat, detail = classify_cycle(rec)
        classifications.append((rec["cycle"], cat, detail))
        cat_counts[cat] += 1

    total = len(cycle_records)
    pass_n = cat_counts.get("PASS", 0)
    pass_rate = pass_n / total if total else 0.0

    print(f"OUTCOMES ({total} cycles):")
    for cat, n in cat_counts.most_common():
        print(f"  {cat:38s} {n:>4}  ({100*n/total:5.1f}%)")
    print(f"  ────────────────────────────────────  ────")
    print(f"  PASS RATE                             {100*pass_rate:6.2f}%")
    print()

    failures = [(c, cat, det) for c, cat, det in classifications if cat != "PASS"]
    if failures:
        print(f"PER-FAILURE DETAILS:")
        for c, cat, det in failures:
            # Pull perturbation for context.
            perturbation = next((r.get("perturbation") for r in cycle_records if r["cycle"] == c), None)
            print(f"  cycle {c:>3}  {cat:35s}")
            if perturbation:
                px = perturbation.get("peg_x_off", 0.0); py = perturbation.get("peg_y_off", 0.0)
                pyw = perturbation.get("peg_yaw_off", 0.0); pf = perturbation.get("pad_friction_scale", 1.0)
                print(f"            perturbation: peg_x_off={px*1000:+.1f}mm, peg_y_off={py*1000:+.1f}mm, "
                      f"peg_yaw_off={math.degrees(pyw):+.2f}°, friction_scale={pf:.3f}")
            print(f"            {det}")
        print()

    print("AGGREGATE STATS (mean / stdev / min / max over cycle records):")
    agg = _aggregate(cycle_records)
    width = max(len(k) for k in agg.keys()) if agg else 0
    for k, v in agg.items():
        print(f"  {k:<{width}s}  μ={v['mean']:+.4f}  σ={v['stdev']:.4f}  "
              f"min={v['min']:+.4f}  max={v['max']:+.4f}")
    print()

    # Determinism check — for runs with no_perturb, all peg final XY must be identical.
    if header.get("no_perturb"):
        finals = [tuple(r["peg_xyz_final"]) for r in cycle_records if r.get("peg_xyz_final")]
        if len(set(finals)) == 1:
            print(f"DETERMINISM (--no-perturb): all {len(finals)} cycles produced peg_xyz_final = {finals[0]}")
        else:
            print(f"DETERMINISM (--no-perturb): VIOLATED — {len(set(finals))} distinct peg_xyz_final values across {len(finals)} cycles")
            return 1

    if args.strict_success_rate is not None and pass_rate < args.strict_success_rate:
        print(f"STRICT GATE: pass rate {100*pass_rate:.2f}% < required {100*args.strict_success_rate:.2f}% — FAIL")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
