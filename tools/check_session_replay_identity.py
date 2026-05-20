#!/usr/bin/env python3
"""Phase 4B Step 8 / Phase 6 — replay-identity comparator.

Compares two SessionPackage directories for L3 replay identity
(D-REPLAY-1 layer L3 in docs/phase_4b_deterministic_semantics.md
section 4.1).

Usage
-----

::

    python tools/check_session_replay_identity.py SESSION_A SESSION_B
    echo $?    # 0 == identical, 1 == divergent

Each SESSION_A / SESSION_B is a path to a SessionPackage directory
(written by DurableTraceRecorder). The expected layout:

    SESSION_A/
      manifest.json
      events.jsonl

What the tool compares
======================

* ``events.jsonl`` — byte-for-byte. By contract (D-SCHED-11, D-EXEC-7),
  no event envelope carries a wall-clock-derived field, so byte-
  equality is the definition of L3 trace identity. There is no
  filtering, no tolerance — a single byte difference is a divergence.

* ``manifest.json`` — byte-for-byte. The manifest schema
  (D-TRACE-8, ``orchestration.package.Manifest``) is deterministic by
  construction: ``package_version`` and ``invariant_contract_version``
  are constants; ``event_count`` is a deterministic function of
  the session's input; ``trace_hash`` / ``runtime_hash`` /
  ``session_identity`` are placeholder ``None`` in Step-8 packages.
  Any divergence here means a contract violation.

What the tool does NOT compare
==============================

This is intentional (D-CONT-7 forbidden list, D-TRACE-4 diagnostic
classification):

* Wall-clock fields. The contract forbids them in replay-authoritative
  artifacts; the tool would reject any sidecar wall-clock log as
  out-of-scope.
* Per-tick aggregate metrics (motion peaks, accelerations, EE speeds).
  These are diagnostic and live outside the SessionPackage.
* Observational projection of registry state beyond what the boundary
  snapshot captures (D-CONT-1 allowlist).
* Tolerance-based comparison. Replay identity is strict byte-equality
  only. Numerical drift, even at the last decimal place, is a
  divergence.

Exit codes
==========

  0 — L3 replay-identical (events.jsonl byte-equal AND manifest.json
      byte-equal)
  1 — divergent (one or both files differ)
  2 — usage error or missing input file

Cites D-REPLAY-1 / D-REPLAY-2 / D-CONT-6 / D-CONT-6a.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


MANIFEST_FILENAME = "manifest.json"
EVENTS_FILENAME   = "events.jsonl"


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bytewise_compare(path_a: Path, path_b: Path) -> tuple[bool, str]:
    """Return (equal, diagnostic). The diagnostic is empty on equal,
    or a short human-readable description of the first divergence."""
    data_a = path_a.read_bytes()
    data_b = path_b.read_bytes()
    if data_a == data_b:
        return True, ""
    # Find the first divergent byte.
    n = min(len(data_a), len(data_b))
    first_diff = next((i for i in range(n) if data_a[i] != data_b[i]), n)
    return False, (
        f"sizes={len(data_a)} vs {len(data_b)} bytes; "
        f"first diverging byte at offset {first_diff}"
    )


def _line_level_diff(path_a: Path, path_b: Path, max_lines: int = 8) -> list[str]:
    """For events.jsonl divergence: return the first N differing lines
    as ``[A] / [B]`` pairs. Helps the operator pinpoint which event(s)
    diverged without diffing kilobyte files manually."""
    lines_a = path_a.read_text(encoding="utf-8").splitlines()
    lines_b = path_b.read_text(encoding="utf-8").splitlines()
    diffs: list[str] = []
    n = min(len(lines_a), len(lines_b))
    for i in range(n):
        if lines_a[i] != lines_b[i]:
            diffs.append(f"  line {i+1} A: {lines_a[i][:200]}")
            diffs.append(f"  line {i+1} B: {lines_b[i][:200]}")
            if len(diffs) // 2 >= max_lines:
                break
    if len(lines_a) != len(lines_b):
        diffs.append(
            f"  line count: A={len(lines_a)}  B={len(lines_b)}  "
            f"(first {min(len(lines_a), len(lines_b))} lines compared)"
        )
    return diffs


def compare_session_packages(path_a: Path, path_b: Path) -> int:
    """Compare two SessionPackage directories. Return 0 if identical,
    1 if divergent, 2 if a required file is missing.

    Side effect: prints a human-readable report to stdout.
    """
    for label, p in (("A", path_a), ("B", path_b)):
        if not p.is_dir():
            print(f"[identity] ERROR: SESSION {label} not a directory: {p}",
                  file=sys.stderr)
            return 2
        for fn in (MANIFEST_FILENAME, EVENTS_FILENAME):
            if not (p / fn).is_file():
                print(f"[identity] ERROR: SESSION {label} missing {fn}: {p / fn}",
                      file=sys.stderr)
                return 2

    print(f"[identity] comparing SESSION A: {path_a}")
    print(f"[identity] comparing SESSION B: {path_b}")
    print()

    rc = 0

    # ─── manifest.json ───
    manifest_a = path_a / MANIFEST_FILENAME
    manifest_b = path_b / MANIFEST_FILENAME
    eq_m, diag_m = _bytewise_compare(manifest_a, manifest_b)
    if eq_m:
        print(f"[identity] manifest.json byte-equal:   YES "
              f"({manifest_a.stat().st_size} bytes)")
    else:
        print(f"[identity] manifest.json byte-equal:   NO  ({diag_m})")
        print(f"  A: {manifest_a.read_text(encoding='utf-8').strip()[:400]}")
        print(f"  B: {manifest_b.read_text(encoding='utf-8').strip()[:400]}")
        rc = 1

    # ─── events.jsonl ───
    events_a = path_a / EVENTS_FILENAME
    events_b = path_b / EVENTS_FILENAME
    eq_e, diag_e = _bytewise_compare(events_a, events_b)
    if eq_e:
        n_lines = sum(1 for line in events_a.read_text(encoding="utf-8").splitlines() if line)
        print(f"[identity] events.jsonl  byte-equal:   YES "
              f"({events_a.stat().st_size} bytes, {n_lines} events)")
        print(f"[identity] events.jsonl  sha256:       "
              f"{_sha256_of_file(events_a)}")
    else:
        print(f"[identity] events.jsonl  byte-equal:   NO  ({diag_e})")
        for line in _line_level_diff(events_a, events_b):
            print(line)
        rc = 1

    print()
    if rc == 0:
        print("[identity] L3 REPLAY-IDENTITY: PASS")
    else:
        print("[identity] L3 REPLAY-IDENTITY: FAIL")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="check_session_replay_identity.py",
        description="L3 replay-identity comparator for two SessionPackages "
                    "(events.jsonl + manifest.json byte-equality).",
    )
    ap.add_argument("session_a", type=Path,
                    help="Path to first SessionPackage directory.")
    ap.add_argument("session_b", type=Path,
                    help="Path to second SessionPackage directory.")
    args = ap.parse_args()
    return compare_session_packages(args.session_a.resolve(),
                                     args.session_b.resolve())


if __name__ == "__main__":
    sys.exit(main())
