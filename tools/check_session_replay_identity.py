#!/usr/bin/env python3
"""Phase 4B replay-identity comparator (Step 8 Phase 6 base + Step 9 Phase 7
failure-trace extension).

Compares two SessionPackage directories for L3 replay identity
(D-REPLAY-1 layer L3 in ``docs/phase_4b_deterministic_semantics.md``
section 4.1). Strict byte-equality only — D-FAULT-11a forbids
tolerance, fuzzy matching, semantic equivalence, or normalized repair.

Phase 7 (Step 9) extensions
===========================

* **Terminus classification.** The comparator scans each
  ``events.jsonl`` for the canonical terminal event and reports the
  terminus (``COMPLETED`` / ``FAILED`` / ``ABORTED`` / ``INCOMPLETE``)
  plus the terminator_reason. Per the §F.12 Phase-2 ruling, failure
  termination must be replay-identical (not merely replay-tolerant),
  so the comparator treats FAILED / ABORTED packages as first-class
  replay objects.
* **Schema-version enforcement (D-CONT-6b).** Reads the
  ``schema_version`` from the first ``NodeBoundarySnapshot`` event of
  each package. Mismatched schema versions are refused (REPLAY-INVALID
  exit), not silently divergent. Pre-Phase-5 SessionPackages
  (schema_version=1) cannot be compared against post-Phase-5 packages
  (schema_version=2); the refusal is explicit and terminal.
* **REPLAY_INTEGRITY_FAILURE classification (D-FAULT-11).** The
  comparator is the sole detector. When the comparator reports
  divergence, that is the operational REPLAY_INTEGRITY_FAILURE event
  — by construction it is NOT appended to either session's
  ``events.jsonl`` (D-FAULT-11 forbids).
* **Failure-trace forensic report.** When comparing failure-terminal
  sessions, the comparator surfaces the terminator_reason and the
  terminal seq for both packages.

Usage
-----

::

    python tools/check_session_replay_identity.py SESSION_A SESSION_B
    echo $?

Each SESSION_A / SESSION_B is a path to a SessionPackage directory
written by ``DurableTraceRecorder``. Expected layout::

    SESSION_A/
      manifest.json
      events.jsonl

What the tool compares
======================

* ``events.jsonl`` — byte-for-byte. Strict byte-equality (D-FAULT-11a).
* ``manifest.json`` — byte-for-byte. The manifest schema is
  deterministic by construction.
* ``schema_version`` — extracted from the first
  ``NodeBoundarySnapshot`` event of each package. Mismatch → refuse
  comparison (D-CONT-6b).

What the tool reports
=====================

For each package:

* **Terminus**: COMPLETED / FAILED / ABORTED / INCOMPLETE.
* **Terminator reason** (from terminal-event payload when present).
* **Terminal seq** (orchestration tick of the terminal event).
* **Schema version** (from boundary snapshot payloads).

Exit codes
==========

  0 — REPLAY-IDENTICAL (events.jsonl + manifest.json byte-equal; same
                        schema; same terminus; same terminator).
  1 — REPLAY-DIVERGENT (byte-different, same schema, same terminus
                        classifier; differs in event content).
  2 — REPLAY-INVALID    (missing file, malformed package, schema-version
                        mismatch, no terminal event, divergent terminus
                        classification; refused comparison per D-CONT-6b
                        / D-FAULT-13).

Cites D-REPLAY-1 / D-REPLAY-2 / D-CONT-6 / D-CONT-6a / D-CONT-6b /
D-FAULT-3 (terminus classification) / D-FAULT-4 / D-FAULT-9 / D-FAULT-10
/ D-FAULT-11 / D-FAULT-11a / D-FAULT-13.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


MANIFEST_FILENAME = "manifest.json"
EVENTS_FILENAME   = "events.jsonl"


# ─────────────────── canonical terminal event types ───────────────────


TERMINAL_EVENT_TYPES: dict[str, str] = {
    "SessionCompleted": "COMPLETED",
    "SessionFailed":    "FAILED",
    "SessionAborted":   "ABORTED",
}


# ───────────────────────── verdict constants ─────────────────────────


VERDICT_IDENTICAL: str = "REPLAY-IDENTICAL"
VERDICT_DIVERGENT: str = "REPLAY-DIVERGENT"
VERDICT_INVALID:   str = "REPLAY-INVALID"


EXIT_IDENTICAL: int = 0
EXIT_DIVERGENT: int = 1
EXIT_INVALID:   int = 2


# ─────────────────────────── helpers ───────────────────────────


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bytewise_compare(path_a: Path, path_b: Path) -> tuple[bool, str]:
    """Return (equal, diagnostic). The diagnostic is empty on equal,
    or a short human-readable description of the first divergence."""
    data_a = path_a.read_bytes()
    data_b = path_b.read_bytes()
    if data_a == data_b:
        return True, ""
    n = min(len(data_a), len(data_b))
    first_diff = next((i for i in range(n) if data_a[i] != data_b[i]), n)
    return False, (
        f"sizes={len(data_a)} vs {len(data_b)} bytes; "
        f"first diverging byte at offset {first_diff}"
    )


def _line_level_diff(path_a: Path, path_b: Path, max_lines: int = 8) -> list[str]:
    """For events.jsonl divergence: first N differing lines as A/B pairs."""
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


def _iter_events(events_path: Path):
    """Yield each parsed event dict in order. Skips blank lines.

    Raises ``ValueError`` if any line is not valid canonical JSON.
    """
    text = events_path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"events.jsonl line {i+1} is not valid JSON: {exc}"
            ) from exc


def classify_terminus(events_path: Path) -> dict[str, Any]:
    """Scan ``events.jsonl`` for the canonical terminal event.

    Returns
    -------
    dict with keys:

      * ``terminus``           — one of COMPLETED / FAILED / ABORTED /
                                  INCOMPLETE.
      * ``terminal_event_type`` — the matching event_type string (or
                                  None if INCOMPLETE).
      * ``terminal_seq``       — seq of the terminal event (or None).
      * ``terminator_reason``  — from the terminal event's payload
                                  (None if absent — COMPLETED never
                                  carries one).
      * ``event_count``        — total non-blank lines.

    Idempotent / pure: no caching, no side effects.
    """
    terminus = "INCOMPLETE"
    terminal_event_type: str | None = None
    terminal_seq: int | None = None
    terminator_reason: Any = None
    event_count = 0
    for env in _iter_events(events_path):
        event_count += 1
        etype = env.get("event_type")
        if etype in TERMINAL_EVENT_TYPES:
            # A well-formed package has exactly one terminal event;
            # if multiples appear, the LAST one wins (defensive).
            terminus = TERMINAL_EVENT_TYPES[etype]
            terminal_event_type = etype
            terminal_seq = env.get("seq")
            payload = env.get("payload") or {}
            terminator_reason = payload.get("terminator_reason")
    return {
        "terminus":            terminus,
        "terminal_event_type": terminal_event_type,
        "terminal_seq":        terminal_seq,
        "terminator_reason":   terminator_reason,
        "event_count":         event_count,
    }


def extract_schema_version(events_path: Path) -> int | None:
    """Extract the boundary-snapshot schema_version from the first
    ``NodeBoundarySnapshot`` event in ``events.jsonl``.

    Returns the int schema_version, or None if no snapshot event is
    present (D-CONT-6b: a session without boundary snapshots cannot be
    schema-version-classified, which is itself a contract violation —
    callers SHOULD treat None as REPLAY-INVALID).
    """
    for env in _iter_events(events_path):
        if env.get("event_type") == "NodeBoundarySnapshot":
            payload = env.get("payload") or {}
            sv = payload.get("schema_version")
            if isinstance(sv, int):
                return sv
    return None


# ─────────────────────────── package validation ───────────────────────────


def _validate_package(path: Path, label: str) -> tuple[bool, str]:
    """Check that ``path`` is a SessionPackage directory with the
    required files. Returns (valid, diagnostic).
    """
    if not path.is_dir():
        return False, f"SESSION {label} not a directory: {path}"
    for fn in (MANIFEST_FILENAME, EVENTS_FILENAME):
        if not (path / fn).is_file():
            return False, f"SESSION {label} missing {fn}: {path / fn}"
    return True, ""


# ─────────────────────────── main comparison ───────────────────────────


def compare_session_packages(path_a: Path, path_b: Path) -> int:
    """Compare two SessionPackage directories.

    Returns
    -------
    int
        :data:`EXIT_IDENTICAL` (0)  — events + manifest byte-equal;
                                       same schema_version; same terminus;
                                       same terminator_reason.
        :data:`EXIT_DIVERGENT` (1)  — byte-different; same schema and
                                       terminus classifiers.
        :data:`EXIT_INVALID`   (2)  — missing file / malformed package /
                                       schema-version mismatch / no terminal
                                       event / divergent terminus
                                       classification (D-CONT-6b /
                                       D-FAULT-13).

    Side effect: prints a human-readable forensic report to stdout.
    """
    # ─── 1. file presence ───
    for label, p in (("A", path_a), ("B", path_b)):
        ok, diag = _validate_package(p, label)
        if not ok:
            print(f"[identity] ERROR: {diag}", file=sys.stderr)
            print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_INVALID}")
            return EXIT_INVALID

    print(f"[identity] comparing SESSION A: {path_a}")
    print(f"[identity] comparing SESSION B: {path_b}")
    print()

    # ─── 2. terminus + schema_version classification ───
    try:
        cls_a = classify_terminus(path_a / EVENTS_FILENAME)
        cls_b = classify_terminus(path_b / EVENTS_FILENAME)
        sv_a = extract_schema_version(path_a / EVENTS_FILENAME)
        sv_b = extract_schema_version(path_b / EVENTS_FILENAME)
    except ValueError as exc:
        print(f"[identity] ERROR: malformed events.jsonl: {exc}",
              file=sys.stderr)
        print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_INVALID}")
        return EXIT_INVALID

    print(f"[identity] SESSION A terminus       : {cls_a['terminus']}"
          + (f"  (reason={cls_a['terminator_reason']!r})"
             if cls_a['terminator_reason'] is not None else ""))
    print(f"[identity] SESSION A terminal_seq   : {cls_a['terminal_seq']}")
    print(f"[identity] SESSION A event_count    : {cls_a['event_count']}")
    print(f"[identity] SESSION A schema_version : {sv_a}")
    print(f"[identity] SESSION B terminus       : {cls_b['terminus']}"
          + (f"  (reason={cls_b['terminator_reason']!r})"
             if cls_b['terminator_reason'] is not None else ""))
    print(f"[identity] SESSION B terminal_seq   : {cls_b['terminal_seq']}")
    print(f"[identity] SESSION B event_count    : {cls_b['event_count']}")
    print(f"[identity] SESSION B schema_version : {sv_b}")
    print()

    # ─── 3. INCOMPLETE rejection (no terminal event) ───
    if cls_a["terminus"] == "INCOMPLETE" or cls_b["terminus"] == "INCOMPLETE":
        print(f"[identity] REFUSE: at least one package lacks a terminal "
              f"event (SessionCompleted / SessionFailed / SessionAborted). "
              f"D-FAULT-14: every transition is one append; an incomplete "
              f"trace is a contract violation and cannot be replay-compared.")
        print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_INVALID}")
        return EXIT_INVALID

    # ─── 4. schema_version enforcement (D-CONT-6b) ───
    if sv_a is None or sv_b is None:
        print(f"[identity] REFUSE: at least one package lacks any "
              f"NodeBoundarySnapshot event → schema_version cannot be "
              f"determined. D-CONT-6b: replay refuses to coerce unknown "
              f"versions.")
        print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_INVALID}")
        return EXIT_INVALID
    if sv_a != sv_b:
        print(f"[identity] REFUSE: schema_version mismatch "
              f"(A={sv_a}, B={sv_b}). D-CONT-6b: mismatched-version "
              f"replays are refused, not coerced. Pre-Phase-5 packages "
              f"(schema_version=1) cannot be compared against post-Phase-5 "
              f"packages (schema_version=2).")
        print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_INVALID}")
        return EXIT_INVALID

    # ─── 5. terminus classifier mismatch (a strict gate) ───
    # Two packages terminating in different classes (e.g. one COMPLETED
    # and one FAILED) cannot be "replay-identical" by any reasonable
    # definition. Surface this as INVALID — the operator's pre-condition
    # for invoking the comparator (both runs of the same canonical
    # input) was violated.
    if cls_a["terminus"] != cls_b["terminus"]:
        print(f"[identity] REFUSE: terminus mismatch — "
              f"A={cls_a['terminus']}, B={cls_b['terminus']}. The two "
              f"packages did not terminate in the same SessionState; "
              f"replay-identity is undefined across distinct termini.")
        print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_INVALID}")
        return EXIT_INVALID
    if cls_a["terminator_reason"] != cls_b["terminator_reason"]:
        print(f"[identity] REFUSE: terminator_reason mismatch — "
              f"A={cls_a['terminator_reason']!r}, "
              f"B={cls_b['terminator_reason']!r}. Both packages "
              f"terminated in the same class but for different reasons; "
              f"replay-identity is undefined across distinct terminator "
              f"reasons (F.12 Phase-2 ruling).")
        print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_INVALID}")
        return EXIT_INVALID

    rc = EXIT_IDENTICAL

    # ─── 6. manifest.json byte-equality ───
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
        rc = EXIT_DIVERGENT

    # ─── 7. events.jsonl byte-equality ───
    events_a = path_a / EVENTS_FILENAME
    events_b = path_b / EVENTS_FILENAME
    eq_e, diag_e = _bytewise_compare(events_a, events_b)
    if eq_e:
        n_lines = sum(
            1 for line in events_a.read_text(encoding="utf-8").splitlines() if line
        )
        print(f"[identity] events.jsonl  byte-equal:   YES "
              f"({events_a.stat().st_size} bytes, {n_lines} events)")
        print(f"[identity] events.jsonl  sha256:       "
              f"{_sha256_of_file(events_a)}")
    else:
        print(f"[identity] events.jsonl  byte-equal:   NO  ({diag_e})")
        for line in _line_level_diff(events_a, events_b):
            print(line)
        rc = EXIT_DIVERGENT

    print()
    if rc == EXIT_IDENTICAL:
        print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_IDENTICAL} "
              f"({cls_a['terminus']}, schema_version={sv_a})")
    else:
        print(f"[identity] L3 REPLAY-IDENTITY: {VERDICT_DIVERGENT} "
              f"(both terminated {cls_a['terminus']}, schema_version={sv_a})")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="check_session_replay_identity.py",
        description="L3 replay-identity comparator for two SessionPackages "
                    "(events.jsonl + manifest.json byte-equality; "
                    "terminus + schema-version aware per Step 9 Phase 7).",
    )
    ap.add_argument("session_a", type=Path,
                    help="Path to first SessionPackage directory.")
    ap.add_argument("session_b", type=Path,
                    help="Path to second SessionPackage directory.")
    args = ap.parse_args()
    return compare_session_packages(
        args.session_a.resolve(), args.session_b.resolve()
    )


if __name__ == "__main__":
    sys.exit(main())
