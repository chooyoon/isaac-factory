"""Pytest plugin: write per-test results to a JSONL file as each test
finishes.

Purpose
-------
Kit's ``--/app/fastShutdown=True`` (set by ``SimulationApp``) calls
``os._exit(0)`` during fixture teardown, **before** pytest's
``pytest_sessionfinish`` hook fires. That hook is where pytest's
terminal summary, FAILURES section, and JUnit XML are normally written
— so under Kit Python they're lost.

This plugin sidesteps the problem by capturing each test's outcome
**at the moment the test finishes** (`pytest_runtest_logreport` with
``when == "call"``). The captured data lands in a JSONL file whose
path is taken from ``$RUNTIME_B_PERTEST_JSONL``. The runner script
parses this file after the subprocess exits to manufacture the real
summary + a synthesised JUnit XML.

This is **diagnostics infrastructure only** — it does not alter any
test, fixture, validator, or adapter code.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


_OUT_ENV = "RUNTIME_B_PERTEST_JSONL"


def _output_path() -> Path | None:
    path = os.environ.get(_OUT_ENV)
    return Path(path) if path else None


def pytest_sessionstart(session):
    """Truncate the JSONL at the start of a session so a re-run replaces
    rather than appends.
    """
    out = _output_path()
    if out is None:
        print(f"[runtime_b_pertest_plugin] WARN: ${_OUT_ENV} not set; "
              f"no per-test data will be written", file=sys.stderr)
        return
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("")
    except Exception:
        traceback.print_exc(file=sys.stderr)


def pytest_runtest_logreport(report):
    """After each test's `call` phase, append a structured record.

    Records are produced for every outcome (passed / failed / skipped /
    error) so the runner can manufacture a complete summary. The
    `longrepr` field carries the failure traceback as a string when
    present; it's enough to reconstruct a meaningful FAILURES section.
    """
    if report.when != "call":
        # Skip setup/teardown phases — `call` is the test body proper.
        # (`setup` and `teardown` failures show up under their own
        # `when` value with `report.failed = True`; we capture those too
        # because they also carry tracebacks.)
        if not (report.failed and report.when in ("setup", "teardown")):
            return

    out = _output_path()
    if out is None:
        return

    longrepr = None
    if report.failed and report.longrepr is not None:
        try:
            longrepr = str(report.longrepr)
        except Exception:                            # pragma: no cover
            longrepr = "<unrepresentable longrepr>"

    record = {
        "nodeid":   report.nodeid,
        "when":     report.when,
        "outcome":  report.outcome,
        "duration": float(getattr(report, "duration", 0.0)),
        "longrepr": longrepr,
    }
    try:
        with out.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
            fh.flush()
            os.fsync(fh.fileno())  # survive Kit's os._exit() reliably
    except Exception:
        traceback.print_exc(file=sys.stderr)


def pytest_collection_finish(session):
    """Record the collection set so the runner can detect "tests never
    ran" (e.g. all failed at setup before any `call` phase).
    """
    out = _output_path()
    if out is None:
        return
    try:
        manifest_path = out.with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps({
            "collected": [item.nodeid for item in session.items],
        }, indent=2))
    except Exception:                                # pragma: no cover
        traceback.print_exc(file=sys.stderr)
