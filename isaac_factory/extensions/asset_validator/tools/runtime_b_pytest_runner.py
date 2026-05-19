#!/usr/bin/env python3
"""Dedicated Runtime B pytest runner — option (2) of the diagnostic
remediation path from docs/full_system_audit.md §11.

What this solves
----------------

Pytest run under Isaac Sim Kit Python suffers from
``--/app/fastShutdown=True``: when SimulationApp.close() fires (typically
in fixture teardown after the last test), Kit calls ``os._exit(0)``
**before** pytest's terminal summary, FAILURES section, or JUnit XML
get written.

This runner side-steps the problem by:

  1. Spawning ``$ISAAC_PATH/python.sh -m pytest`` as a **child** process
     — Kit's fast-shutdown kills the child, but the parent survives.
  2. Installing a pytest plugin
     (``runtime_b_pertest_plugin``, sibling file in this directory) that
     captures each test's outcome the moment it finishes (`call` phase)
     and writes it to a JSONL file. The data survives ``os._exit()``
     because it's already on disk and fsync'd.
  3. Reading the JSONL after the child exits, computing the real
     summary, and synthesising a JUnit XML that downstream CI consumers
     expect at the same path pytest would have written one.

Constraints honoured
--------------------

  - No validator logic changes.
  - No adapter logic changes.
  - No fixture semantic changes (the existing `sim_app` module-scoped
    fixture still owns SimulationApp's lifecycle; this runner does not
    pre-create or override it).
  - Diagnostics infrastructure only.

Usage
-----

::

    python isaac_factory/extensions/asset_validator/tools/runtime_b_pytest_runner.py \\
        isaac_factory/extensions/asset_validator/tests/unit/test_overlap_adapter.py

Default output directory is ``logs/runtime_b_tests/``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


# Workspace and runtime constants
WS_ROOT     = Path("/home/cap2/last")
ISAAC_PATH  = Path("/home/cap2/isaac-sim-5.0.0")
PYTHON_SH   = ISAAC_PATH / "python.sh"
DEFAULT_OUT = WS_ROOT / "logs" / "runtime_b_tests"
TOOLS_DIR   = Path(__file__).resolve().parent
PLUGIN_NAME = "runtime_b_pertest_plugin"

# Env vars the user mandated be stripped before invoking Kit Python.
# (Matches docs/runtime_policy.md §7 P5/P7 prohibitions.)
SANITIZE_VARS = (
    "PYTHONPATH",
    "ROS_DISTRO",
    "AMENT_PREFIX_PATH",
    "CMAKE_PREFIX_PATH",
    "GZ_CONFIG_PATH",
    "LD_LIBRARY_PATH",
)


def _sanitize_env(extra_pythonpath: Iterable[Path] = ()) -> tuple[dict, dict]:
    """Return (cleaned_env, stripped_summary). Re-inject only what we need."""
    env = os.environ.copy()
    stripped: dict[str, str] = {}
    for var in SANITIZE_VARS:
        if var in env:
            stripped[var] = env.pop(var)

    # Re-inject a fresh PYTHONPATH containing only the directories we
    # explicitly need for plugin loading.
    paths = [str(p) for p in extra_pythonpath if p]
    if paths:
        env["PYTHONPATH"] = ":".join(paths)
    env["PYTHONUNBUFFERED"] = "1"
    # Kit telemetry / EULA bypass (no UI, no network).
    env.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")
    return env, stripped


def _build_pytest_cmd(test_target: Path, *, junit_path: Path) -> list[str]:
    return [
        str(PYTHON_SH), "-m", "pytest",
        str(test_target),
        "-v",
        "--tb=long",
        "-ra",
        "-p", "no:cacheprovider",
        "-p", PLUGIN_NAME,
        f"--junit-xml={junit_path}",
        "--color=no",
    ]


def _read_jsonl(path: Path) -> list[dict]:
    """Parse JSONL; return list of records (skipping malformed lines)."""
    out: list[dict] = []
    if not path.is_file():
        return out
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _classify(records: list[dict]) -> dict:
    """Aggregate per-test records into per-outcome counts.

    A test that fails in setup/teardown gets its own record under that
    `when` phase; we collapse to one outcome per node (failure wins).
    """
    by_node: dict[str, str] = {}
    failure_node: set[str] = set()
    for r in records:
        node = r["nodeid"]
        outcome = r["outcome"]
        if outcome == "failed":
            failure_node.add(node)
        by_node.setdefault(node, outcome)
        if node in failure_node:
            by_node[node] = "failed"
    counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    for outcome in by_node.values():
        counts[outcome] = counts.get(outcome, 0) + 1
    return {"by_node": by_node, "counts": counts, "total": len(by_node)}


def _write_junit_xml(
    records: list[dict],
    summary: dict,
    junit_path: Path,
    test_target: Path,
    duration_s: float,
) -> None:
    """Synthesise a JUnit XML from per-test records.

    Honest emulation of pytest's own format. Used only if pytest's own
    JUnit writer didn't run (Kit fast-shutdown intercepts it).
    """
    by_node = summary["by_node"]
    longreprs: dict[str, str] = {}
    durations: dict[str, float] = {}
    for r in records:
        node = r["nodeid"]
        if r["outcome"] == "failed" and r.get("longrepr"):
            longreprs[node] = r["longrepr"]
        durations[node] = max(durations.get(node, 0.0), float(r.get("duration", 0.0)))

    root = ET.Element("testsuites")
    suite = ET.SubElement(
        root, "testsuite",
        name=f"runtime_b::{test_target.stem}",
        tests=str(summary["total"]),
        failures=str(summary["counts"]["failed"]),
        errors=str(summary["counts"]["error"]),
        skipped=str(summary["counts"]["skipped"]),
        time=f"{duration_s:.3f}",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    for node, outcome in sorted(by_node.items()):
        # nodeid format: path/to/test_file.py::ClassName::test_method
        parts = node.split("::")
        if len(parts) >= 3:
            classname = "::".join(parts[:-1])
            name = parts[-1]
        else:
            classname = parts[0] if parts else node
            name = parts[-1] if parts else "unknown"
        tc = ET.SubElement(
            suite, "testcase",
            classname=classname,
            name=name,
            time=f"{durations.get(node, 0.0):.3f}",
        )
        if outcome == "failed":
            failure = ET.SubElement(tc, "failure", type="AssertionError",
                                    message="(synthesised by runtime_b_pytest_runner)")
            failure.text = longreprs.get(node, "")
        elif outcome == "skipped":
            ET.SubElement(tc, "skipped")
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(junit_path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    ap = argparse.ArgumentParser(prog="runtime_b_pytest_runner.py")
    ap.add_argument("test_target", help="Path to test file or directory")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    test_target = Path(args.test_target).resolve()
    if not test_target.exists():
        print(f"[runner] ERROR: test target not found: {test_target}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stdout_log = out_dir / "stdout.log"
    stderr_log = out_dir / "stderr.log"
    pertest    = out_dir / "per_test.jsonl"
    junit_path = out_dir / "junit.xml"
    summary_path = out_dir / "summary.txt"

    # Wipe stale per-test data so this run is self-contained
    for p in (stdout_log, stderr_log, pertest, junit_path, summary_path,
              pertest.with_suffix(".manifest.json")):
        if p.exists():
            p.unlink()

    # Sanitize env; plugin needs TOOLS_DIR on PYTHONPATH so `-p plugin` resolves
    env, stripped = _sanitize_env(extra_pythonpath=[TOOLS_DIR])
    env["RUNTIME_B_PERTEST_JSONL"] = str(pertest)

    started_at = datetime.now(timezone.utc)

    print(f"[runner] === runtime_b_pytest_runner.py ===")
    print(f"[runner] start time : {started_at.isoformat()}")
    print(f"[runner] workspace  : {WS_ROOT}")
    print(f"[runner] isaac path : {ISAAC_PATH}")
    print(f"[runner] test target: {test_target}")
    print(f"[runner] out dir    : {out_dir}")
    print(f"[runner] timeout    : {args.timeout}s")

    print(f"\n[runner] sanitized env vars (stripped from parent shell):")
    if stripped:
        for k in sorted(stripped):
            v = stripped[k]
            v_disp = v if len(v) <= 80 else v[:77] + "..."
            print(f"  - {k:<22} = {v_disp}")
    else:
        print(f"  (parent shell already clean — nothing stripped)")
    print(f"[runner] PYTHONPATH replanted to: {env['PYTHONPATH']}")
    print(f"[runner] PYTHONUNBUFFERED=1, OMNI_KIT_ACCEPT_EULA=YES")

    cmd = _build_pytest_cmd(test_target, junit_path=junit_path)
    print(f"\n[runner] invoking subprocess:")
    print(f"  {' '.join(cmd)}")
    print(f"  stdout → {stdout_log}")
    print(f"  stderr → {stderr_log}")
    print(f"  per-test JSONL → {pertest}")
    print(f"  (Kit log flooding lands in stdout.log — that's the underlying behaviour)")
    print()

    t0 = datetime.now(timezone.utc).timestamp()
    try:
        with stdout_log.open("wb") as out, stderr_log.open("wb") as err:
            proc = subprocess.run(
                cmd, stdout=out, stderr=err, env=env,
                timeout=args.timeout, check=False,
            )
        child_rc = proc.returncode
    except subprocess.TimeoutExpired:
        print(f"\n[runner] ERROR: subprocess exceeded {args.timeout}s timeout",
              file=sys.stderr)
        child_rc = 124
    duration_s = datetime.now(timezone.utc).timestamp() - t0

    # Parse per-test results
    records = _read_jsonl(pertest)
    summary = _classify(records)

    # Synthesise JUnit XML if pytest didn't write one (Kit fast-shutdown)
    junit_was_pytests = junit_path.is_file() and junit_path.stat().st_size > 0
    if not junit_was_pytests:
        _write_junit_xml(records, summary, junit_path, test_target, duration_s)

    counts = summary["counts"]
    # Real exit code: derived from per-test outcomes, not the child's
    # exit (which is Kit's, not pytest's).
    if counts["failed"] or counts["error"]:
        real_rc = 1
    elif summary["total"] == 0:
        real_rc = 2
    else:
        real_rc = 0

    # Build summary text
    lines = []
    lines.append("=" * 64)
    lines.append("runtime_b_pytest_runner — REAL summary")
    lines.append("=" * 64)
    lines.append(f"test_target          : {test_target}")
    lines.append(f"started_at           : {started_at.isoformat()}")
    lines.append(f"duration_seconds     : {duration_s:.2f}")
    lines.append(f"child exit code      : {child_rc}   (Kit fast-shutdown's exit, not pytest's)")
    lines.append(f"real exit code       : {real_rc}   (derived from per-test outcomes)")
    lines.append(f"junit xml            : {junit_path}  "
                 f"({'pytest-written' if junit_was_pytests else 'synthesised by runner'})")
    lines.append("")
    lines.append(f"total tests          : {summary['total']}")
    lines.append(f"  passed             : {counts['passed']}")
    lines.append(f"  failed             : {counts['failed']}")
    lines.append(f"  skipped            : {counts['skipped']}")
    lines.append(f"  errored            : {counts['error']}")
    lines.append("")

    # Per-test outcomes table
    lines.append("Per-test outcomes (deterministic order: nodeid lexicographic):")
    for node, outcome in sorted(summary["by_node"].items()):
        mark = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP",
                "error":  "ERR "}.get(outcome, "??? ")
        lines.append(f"  [{mark}]  {node}")

    # FAILURES tracebacks
    failed_nodes = [n for n, o in summary["by_node"].items() if o == "failed"]
    if failed_nodes:
        lines.append("")
        lines.append("=" * 64)
        lines.append("FAILURES")
        lines.append("=" * 64)
        longreprs = {r["nodeid"]: r.get("longrepr") for r in records
                     if r["outcome"] == "failed"}
        for node in sorted(failed_nodes):
            lines.append("")
            lines.append("_" * (len(node) + 6))
            lines.append(f"   {node}   ")
            lines.append("_" * (len(node) + 6))
            tb = longreprs.get(node) or "(no traceback captured)"
            lines.extend(tb.splitlines())

    output = "\n".join(lines) + "\n"
    summary_path.write_text(output, encoding="utf-8")
    print(output)
    print(f"\n[runner] artefacts:")
    print(f"  stdout (raw)         : {stdout_log}")
    print(f"  stderr (raw)         : {stderr_log}")
    print(f"  per-test JSONL       : {pertest}")
    print(f"  collection manifest  : {pertest.with_suffix('.manifest.json')}")
    print(f"  junit XML            : {junit_path}")
    print(f"  summary              : {summary_path}")
    return real_rc


if __name__ == "__main__":
    sys.exit(main())
