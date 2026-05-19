#!/usr/bin/env python3
"""Phase 3O — offline trajectory-continuity validator.

Reads the cell config (configs/cell_01.yaml) and audits every adjacent
waypoint pair on the robot's trajectory for the failure mode that
caused the Phase 3M "empty gripper" artefact:

  * **raw joint deltas exceeding π** (= 180°). After Phase 3N's IK 2π
    unwrap pass these should not occur; if they do, the IK bake is
    leaving wrap-explosions that the linear interpolator will rotate
    through 360° (or worse).

  * **per-joint angular velocity exceeding an industrial-norm limit**.
    UR10e datasheet caps each joint at ~3.14 rad/s (= 180°/s). We default
    the gate to 2.5 rad/s to keep some margin and reject any single-joint
    sweep that's faster than a believable industrial transport.

  * **per-joint acceleration estimate from waypoint-to-waypoint
    duration changes**. If a joint's angular speed varies sharply across
    adjacent phases (e.g., 0.1 rad/s → 1.5 rad/s in a single step), the
    LERP boundary will impose a high jerk on PhysX.

Runtime: pure Python 3.10+. No pxr, no Kit, no Isaac Sim. Run from any
environment that can read a YAML file.

Usage:
  python tools/validate_trajectory_continuity.py
  python tools/validate_trajectory_continuity.py --config configs/cell_01.yaml
  python tools/validate_trajectory_continuity.py --joint-vel-limit-rad-s 2.5
  python tools/validate_trajectory_continuity.py --strict          # exit non-zero on any flag

Exit codes:
  0 — all gates pass
  1 — at least one gate violated (only when --strict)
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "cell_01.yaml"

# Industrial norms — UR10e datasheet joint speed caps are ~3.14 rad/s
# per joint. We pick 2.5 rad/s as the default Phase 3O gate to keep
# headroom against ramp dynamics and to reject obviously-wrong sweeps.
DEFAULT_JOINT_VEL_LIMIT_RAD_S      = 2.5
# Max raw |Δ| (= linear-interpolation delta on a single joint between
# adjacent waypoints). Anything above π means the IK 2π unwrap pass
# failed and the player would LERP through a wrap.
DEFAULT_RAW_DELTA_LIMIT_RAD        = math.pi
# Joint angular-acceleration estimate gate (rad/s²). UR10e datasheet is
# ~15 rad/s²; we set 8 rad/s² as a believability gate.
DEFAULT_JOINT_ACCEL_LIMIT_RAD_S2   = 8.0

_UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)


@dataclass
class Flag:
    pair: str
    joint: str
    metric: str
    value: float
    limit: float
    detail: str

    def format(self) -> str:
        return (f"  [{self.pair:35s}] {self.joint:14s} "
                f"{self.metric:18s} = {self.value:+.4f}  "
                f"(limit {self.limit:.4f})  — {self.detail}")


def _load_yaml(path: Path) -> dict:
    """Minimal YAML loader — uses pyyaml if available, else a hand parser
    sufficient for the cell_01 schema shape."""
    try:
        import yaml
        return yaml.safe_load(path.read_text())
    except ImportError:
        sys.stderr.write("warning: PyYAML missing; using stub loader\n")
        return _stub_yaml_load(path.read_text())


def _stub_yaml_load(text: str) -> dict:
    """Bare-bones loader for the cell_01.yaml format only (key: value with
    list and nested mappings). Not a general YAML loader."""
    raise RuntimeError(
        "PyYAML is required to read configs/cell_01.yaml. "
        "Install it in this Python env: pip install pyyaml"
    )


def _parse_trajectory(cfg) -> list[dict]:
    """Pull out the (name, duration_s, joint_positions_rad) tuples."""
    out = []
    for wp in cfg["robot"]["trajectory"]:
        joints = {n: float(wp["joint_positions_rad"][n]) for n in _UR10E_JOINT_NAMES}
        out.append({
            "name":       str(wp["name"]),
            "duration_s": float(wp["duration_s"]),
            "joints":     joints,
            "gripper":    str(wp.get("gripper", "")),
        })
    return out


def _audit(waypoints: list[dict], *,
           raw_delta_limit: float,
           joint_vel_limit: float,
           joint_accel_limit: float) -> tuple[list[Flag], list[dict]]:
    """Audit every adjacent pair, return (flags, per_pair_metrics)."""
    flags: list[Flag] = []
    per_pair_metrics: list[dict] = []

    # Per-joint angular velocities per pair (for accel estimate).
    pair_velocities: list[dict[str, float]] = []

    for i in range(1, len(waypoints)):
        prev = waypoints[i-1]
        cur  = waypoints[i]
        label = f"{prev['name']} → {cur['name']}"
        dt = cur["duration_s"]
        pair_metrics = {
            "pair":         label,
            "duration_s":   dt,
            "per_joint":    {},
        }
        velocities = {}
        for jn in _UR10E_JOINT_NAMES:
            a = prev["joints"][jn]
            b = cur["joints"][jn]
            raw_delta = b - a

            # Wrap-explosion check: raw delta > π means LERP would
            # rotate the joint through more than a half-revolution
            # despite a shorter equivalent angle (b ± 2π) existing.
            if abs(raw_delta) > raw_delta_limit + 1e-9:
                flags.append(Flag(
                    pair=label, joint=jn, metric="raw_|Δ|",
                    value=raw_delta, limit=raw_delta_limit,
                    detail=(f"LERP would rotate joint by {math.degrees(raw_delta):+.1f}° "
                            f"(equivalent wrap exists at "
                            f"{math.degrees(raw_delta - math.copysign(2*math.pi, raw_delta)):+.1f}°)"),
                ))

            # Velocity check (skip waypoints with dt=0 — they're
            # "set initial pose" zero-duration markers, not real moves).
            if dt > 1e-6:
                ang_vel = raw_delta / dt
                velocities[jn] = ang_vel
                if abs(ang_vel) > joint_vel_limit + 1e-9:
                    flags.append(Flag(
                        pair=label, joint=jn, metric="ω (rad/s)",
                        value=ang_vel, limit=joint_vel_limit,
                        detail=f"joint sweeps {math.degrees(ang_vel):+.1f}°/s — exceeds industrial-norm gate",
                    ))
                pair_metrics["per_joint"][jn] = {
                    "raw_delta_rad":  raw_delta,
                    "duration_s":     dt,
                    "ang_vel_rad_s":  ang_vel,
                }
            else:
                pair_metrics["per_joint"][jn] = {
                    "raw_delta_rad":  raw_delta,
                    "duration_s":     dt,
                    "ang_vel_rad_s":  None,
                }

        pair_velocities.append(velocities)
        per_pair_metrics.append(pair_metrics)

    # Acceleration estimate: velocity-change between adjacent NON-ZERO
    # phases, over the time spanning their midpoints.
    for i in range(1, len(pair_velocities)):
        v_prev = pair_velocities[i-1]
        v_cur  = pair_velocities[i]
        dt_prev = waypoints[i].get("duration_s", 0.0)
        dt_cur  = waypoints[i+1].get("duration_s", 0.0)
        if dt_prev <= 1e-6 or dt_cur <= 1e-6:
            continue
        accel_window = 0.5 * (dt_prev + dt_cur)
        if accel_window <= 1e-6:
            continue
        label = f"{waypoints[i-1]['name']} → {waypoints[i]['name']} → {waypoints[i+1]['name']}"
        for jn in _UR10E_JOINT_NAMES:
            if jn not in v_prev or jn not in v_cur:
                continue
            dv = v_cur[jn] - v_prev[jn]
            accel = dv / accel_window
            per_pair_metrics[i].setdefault("accel_estimate_rad_s2", {})[jn] = accel
            if abs(accel) > joint_accel_limit + 1e-9:
                flags.append(Flag(
                    pair=label, joint=jn, metric="α (rad/s²)",
                    value=accel, limit=joint_accel_limit,
                    detail=(f"velocity jumps from {math.degrees(v_prev[jn]):+.1f}°/s "
                            f"to {math.degrees(v_cur[jn]):+.1f}°/s across phase boundary"),
                ))

    return flags, per_pair_metrics


def _print_report(waypoints, per_pair_metrics, flags,
                  raw_delta_limit, joint_vel_limit, joint_accel_limit):
    print(f"\nTrajectory-continuity audit  ({len(waypoints)} waypoints, {len(waypoints)-1} pairs)")
    print(f"  Gates: raw |Δ| ≤ {math.degrees(raw_delta_limit):.1f}° "
          f"| ω ≤ {math.degrees(joint_vel_limit):.1f}°/s "
          f"| α ≤ {math.degrees(joint_accel_limit):.1f}°/s²")
    print()

    # Compact per-pair summary table.
    print("PER-PAIR PEAK VALUES (degrees / second):")
    hdr = f"  {'pair':<38s} {'dur':>6s}  " + "  ".join(f"{n:>8s}" for n in _UR10E_JOINT_NAMES)
    print(hdr)
    for m in per_pair_metrics:
        cells = []
        for jn in _UR10E_JOINT_NAMES:
            v = m["per_joint"][jn].get("ang_vel_rad_s")
            if v is None:
                cells.append("    —   ")
            else:
                cells.append(f"{math.degrees(v):>+8.1f}")
        print(f"  {m['pair']:<38s} {m['duration_s']:>6.2f}  " + "  ".join(cells))

    print()
    if flags:
        print(f"FLAGS ({len(flags)}):")
        for f in flags:
            print(f.format())
    else:
        print("FLAGS: none.  All adjacent waypoint pairs are continuity-clean.")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config",
                        type=Path, default=_DEFAULT_CONFIG,
                        help="cell config YAML (default: configs/cell_01.yaml)")
    parser.add_argument("--raw-delta-limit-rad",
                        type=float, default=DEFAULT_RAW_DELTA_LIMIT_RAD,
                        help=f"max |Δ_joint| between adjacent waypoints (default {DEFAULT_RAW_DELTA_LIMIT_RAD:.4f} = π)")
    parser.add_argument("--joint-vel-limit-rad-s",
                        type=float, default=DEFAULT_JOINT_VEL_LIMIT_RAD_S,
                        help=f"max per-joint angular velocity (rad/s) (default {DEFAULT_JOINT_VEL_LIMIT_RAD_S})")
    parser.add_argument("--joint-accel-limit-rad-s2",
                        type=float, default=DEFAULT_JOINT_ACCEL_LIMIT_RAD_S2,
                        help=f"max per-joint angular acceleration estimate (rad/s²) (default {DEFAULT_JOINT_ACCEL_LIMIT_RAD_S2})")
    parser.add_argument("--strict",
                        action="store_true",
                        help="exit non-zero on any flag (CI mode)")
    args = parser.parse_args()

    if not args.config.is_file():
        print(f"error: config not found: {args.config}", file=sys.stderr)
        return 2
    cfg = _load_yaml(args.config)
    waypoints = _parse_trajectory(cfg)
    flags, per_pair_metrics = _audit(
        waypoints,
        raw_delta_limit=args.raw_delta_limit_rad,
        joint_vel_limit=args.joint_vel_limit_rad_s,
        joint_accel_limit=args.joint_accel_limit_rad_s2,
    )
    _print_report(waypoints, per_pair_metrics, flags,
                  args.raw_delta_limit_rad,
                  args.joint_vel_limit_rad_s,
                  args.joint_accel_limit_rad_s2)

    if args.strict and flags:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
