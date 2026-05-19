# Runtime B Testing — Operations Manual

**Scope**: How to run pytest under Isaac Sim Kit Python (Runtime B) and recover real outcomes / tracebacks / JUnit XML despite Kit's `--/app/fastShutdown=True` behaviour.
**Companion docs**: [runtime_b.md](runtime_b.md), [runtime_b_bootstrap.md](runtime_b_bootstrap.md), [physx_runtime_constraints.md](physx_runtime_constraints.md), [full_system_audit.md §11](full_system_audit.md)
**Last revised**: 2026-05-18

---

## 1. The problem

Tests that need `omni.physx`, `isaacsim.core.api.World`, or any other Kit-loaded extension must run under Isaac Sim Kit Python (Runtime B). The standard invocation looks like:

```bash
$ISAAC_PATH/python.sh -m pytest path/to/test_file.py -v --tb=long --junit-xml=out.xml
```

Two infrastructure problems make this fragile in practice:

1. **Inherited PYTHONPATH contamination.** The user's login shell exports `PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages` (per `runtime_policy.md §7 P5`). Kit Python 3.11 picks that up, tries to load ROS 2's `launch_testing` pytest plugin, and fails with `ModuleNotFoundError: lark` before any test runs.
2. **Kit fast-shutdown kills pytest's session finalisation.** `SimulationApp.close()` (typically called in a module-scoped or session-scoped fixture's teardown) calls `os._exit(0)` via Kit's `--/app/fastShutdown=True`. That `os._exit` fires **before** pytest's `pytest_terminal_summary` and `pytest_sessionfinish` hooks — so the FAILURES section, summary counts, and JUnit XML are never written. Worse, the process exits with code 0 regardless of test outcomes.

The result: even when 7 of 7 tests fail, the standard run looks like a success.

---

## 2. The runner

`tools/runtime_b_pytest_runner.py` solves both problems:

### 2.1 Environment sanitization

Before spawning `python.sh`, the runner strips:

```
PYTHONPATH
ROS_DISTRO
AMENT_PREFIX_PATH
CMAKE_PREFIX_PATH
GZ_CONFIG_PATH
LD_LIBRARY_PATH
```

from the inherited environment, then **re-injects** a minimal `PYTHONPATH` containing only `tools/` (so the per-test plugin module resolves). It also sets `PYTHONUNBUFFERED=1` and `OMNI_KIT_ACCEPT_EULA=YES`.

The runner prints exactly which variables it stripped, including the start of their inherited values, so the contamination is visible:

```
[runner] sanitized env vars (stripped from parent shell):
  - PYTHONPATH            = /opt/ros/jazzy/lib/python3.12/site-packages
  - ROS_DISTRO            = jazzy
  - AMENT_PREFIX_PATH     = /opt/ros/jazzy
  ...
[runner] PYTHONPATH replanted to: .../tools
[runner] PYTHONUNBUFFERED=1, OMNI_KIT_ACCEPT_EULA=YES
```

### 2.2 Per-test JSONL plugin

`tools/runtime_b_pertest_plugin.py` registers a `pytest_runtest_logreport` hook that writes each test's outcome — node id, when phase, outcome, duration, and `str(longrepr)` if failed — to a JSONL file the moment the test's `call` phase finishes. After every write the plugin calls `fsync()` so the data is on disk **before** Kit fast-shutdown can intercept.

The runner passes `-p runtime_b_pertest_plugin` to pytest, after setting `RUNTIME_B_PERTEST_JSONL` to a known path. The plugin reads that env var and uses it as the output path.

### 2.3 Subprocess isolation

The runner invokes pytest in a **child process** via `subprocess.run`. If Kit fast-shuts down the child, the parent runner survives. After the child exits (regardless of how — clean exit, `os._exit`, timeout), the parent:

1. Reads the JSONL on disk.
2. Aggregates outcomes (collapses setup/teardown failures into per-node fails).
3. Synthesises a real pytest-style summary.
4. Synthesises a JUnit XML if pytest didn't manage to write one.
5. Computes the **real** exit code (1 if any failed, 0 otherwise) — distinct from the child's exit code (which is Kit's `os._exit`).

### 2.4 What it does NOT change

The runner is diagnostics infrastructure. It does **not**:

- Modify any test fixture's semantics.
- Modify any validator or adapter code.
- Pre-create or override `SimulationApp` — the test's existing fixture still owns SimulationApp's lifecycle.
- Modify Kit's `fast_shutdown` setting.

---

## 3. Usage

```bash
python isaac_factory/extensions/asset_validator/tools/runtime_b_pytest_runner.py \
    isaac_factory/extensions/asset_validator/tests/unit/test_overlap_adapter.py
```

Optional flags:

| Flag | Default | Meaning |
|---|---|---|
| `--out-dir DIR`  | `logs/runtime_b_tests/` | where per-test JSONL, JUnit XML, summary, and raw stdout/stderr go |
| `--timeout S`    | `180`                   | subprocess wall-clock limit |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | All collected tests passed |
| `1` | At least one test failed or errored |
| `2` | No tests collected (and the runner couldn't tell because the JSONL was empty) |
| `124` | Subprocess timed out |

---

## 4. Output artefacts

All under `--out-dir`:

| File | Purpose |
|---|---|
| `stdout.log` | Raw subprocess stdout — includes Kit's `[Info]` flood and pytest's per-test `PASSED/FAILED` markers. Big, noisy, complete. |
| `stderr.log` | Raw subprocess stderr — typically small (Kit logs to stdout, not stderr). |
| `per_test.jsonl` | One JSON record per test outcome. Order = collection order. Persistent across Kit fast-shutdown. |
| `per_test.manifest.json` | The set of test node-ids pytest collected, written at `pytest_collection_finish`. Lets the runner detect "test was collected but never ran". |
| `junit.xml` | Pytest-style JUnit XML. Either written by pytest (rare under Kit) or synthesised by the runner from the JSONL. The runner's summary line says which. |
| `summary.txt` | Human-readable real summary: per-test outcomes, FAILURES tracebacks, real exit code. Same content the runner prints to stdout. |

### 4.1 `per_test.jsonl` record shape

```json
{"nodeid":   "tests/.../test_file.py::TestClass::test_method",
 "when":     "call",
 "outcome":  "failed",
 "duration": 0.0123,
 "longrepr": "Traceback (most recent call last):\n  File ...\n  AssertionError: ..."}
```

`when` can also be `setup` or `teardown` for fixtures that fail before the test body — those records are included too, so the runner can distinguish "test failed" from "fixture failed before test ran".

---

## 5. Limitations

| Limitation | Explanation |
|---|---|
| **Kit log floods stdout** | Kit's `print()` calls go to stdout, and pytest's `-v` output goes there too. `stdout.log` is the raw interleave. The clean view is in `summary.txt` / `per_test.jsonl`. |
| **Runner's JUnit XML is synthesised, not pytest's** | Format matches pytest's enough for CI consumers to parse, but `system-out` / `properties` blocks aren't included. |
| **Cannot recover test results that crash the interpreter** | If a test segfaults Kit (rare, but possible with PhysX), no `pytest_runtest_logreport` fires — that test's row is missing from the JSONL. The collection manifest catches this case: `collected ≠ records` ⇒ a test was lost. |
| **One test target per invocation** | Multiple targets would need explicit JSONL aggregation; not worth complicating the runner for a single-file diagnostic. |

---

## 6. When to use this vs. plain pytest

| Scenario | Tool |
|---|---|
| Runtime A (`research` profile, conda env_isaaclab) — pure-python tests | Plain `python -m pytest …` |
| Runtime B (Kit Python) — needs `omni.physx` / `isaacsim.core.api` | **`runtime_b_pytest_runner.py`** |
| CI under Kit | This runner. Plain pytest under Kit will silently report success even on failure. |

---

## 7. Relationship to the deferred Pipeline + CLI

The pipeline / reporter / CLI work described in `asset_validator_design.md §4.6` will eventually call validators end-to-end and use `JsonReporter` for output. That path is **not** affected by Kit fast-shutdown because it doesn't run pytest — it's a normal Python script invoking validators directly.

This runner exists specifically for the **test infrastructure** path, not the production path.
