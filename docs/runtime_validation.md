# Runtime Validation

**Script**: `scripts/validate_runtime.sh`
**Purpose**: Read-only doctor for the industrial digital twin runtime — confirms the canonical stack (per [docs/runtime_policy.md](runtime_policy.md)) is installed, reachable, and free of cross-runtime contamination.
**Status**: Authoritative for runtime health diagnosis.
**Last revised**: 2026-05-18

---

## 1. What it is

A bash script that inspects the current shell and the host, runs subprocess probes against the installed Python interpreters, and emits a human-readable report ending in three sections — **PASS**, **WARN**, **FAIL**.

It is **strictly read-only**:

- No environment variables are exported.
- No files are created, deleted, or modified.
- No daemons are started.
- Subprocesses (`python`, `nvidia-smi`, `ros2`, etc.) are spawned only to probe state, never with a mutated environment.

Run it any time you suspect a runtime is misconfigured, before starting a long simulation, or as the first step in a CI gate.

---

## 2. Usage

```bash
bash scripts/validate_runtime.sh            # standard checks (fast, ≈1–2 s)
bash scripts/validate_runtime.sh --deep     # also launches Kit Python to import pxr/omni (≈30–90 s)
bash scripts/validate_runtime.sh --help
```

You can run the script:

- From **any shell** — activated or not. It detects which profile (if any) is active.
- From any working directory — paths are resolved from canonical constants, not from `pwd`.
- With or without an internet connection — every check is local.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | No FAIL items. WARN items may be present. |
| `1` | At least one FAIL — see the `FAIL` section of the report for details. |
| `2` | Bad argument (unknown flag). |

---

## 3. Output format

Each section is printed in order with one of three tags per check:

| Tag | Meaning |
|---|---|
| `[PASS]` | The check matches the policy expectation. |
| `[WARN]` | A condition worth noting that does not by itself break the active profile (e.g., an inherited env var, an extra ROS distro installed, a missing optional path). |
| `[FAIL]` | The check directly violates policy or indicates a broken runtime. The script's overall result is FAIL if any FAIL items are present. |

The final block repeats the FAIL / WARN / PASS items grouped under headed sections so they can be skimmed independently of the narrative output.

Colour is enabled when stdout is a TTY; piping to a file gives plain text.

---

## 4. Profile detection

The script begins by inferring which runtime profile is active from environment variables:

| Indicator | Implies |
|---|---|
| `CONDA_DEFAULT_ENV=env_isaaclab` | `research` profile |
| `ROS_DISTRO=jazzy` (any `ROS_DISTRO` value) | `ros` profile |
| `ISAAC_PATH` set, no conda, no ROS | `isaac` profile |
| None of the above | `none` — host-level checks still run |
| Two or more of the above | `contaminated` — emits a FAIL and continues with diagnostics |

The detected profile gates which downstream checks run as PASS/FAIL versus informational.

---

## 5. Check catalog

The script runs the checks below, in this order.

### §2 Workspace
- Canonical workspace `/home/cap2/last` exists.
- `WORKSPACE_ROOT` env var matches canonical path.
- All 13 canonical subdirectories present (`docs`, `isaac_factory`, `ros2_ws`, `orchestration`, `scripts`, `assets`, `configs`, `tests`, `logs`, `datasets`, `outputs`, `tools`, `cache`).

### §3 GPU & NVIDIA driver
- `nvidia-smi` is on PATH and returns successfully.
- A GPU is detected; its name contains `RTX` or `GeForce` (PASS) or doesn't (WARN — Isaac Sim 5 requires RTX).
- The driver version is reported.

### §4 CUDA
- `/usr/local/cuda` directory exists; version is read from `version.json`.
- `nvcc` is on PATH (expected only in `research` profile per policy §4).

### §5 Isaac Sim install
- `/home/cap2/isaac-sim-5.0.0/` exists.
- `VERSION` file is readable.
- Launchers present: `python.sh`, `isaac-sim.sh`, `kit/python/bin/python3`.

### §6 Extension path validity
- `exts/`, `extscache/`, `extsPhysics/` each contain at least one extension.
- Sentinel extensions present: `isaacsim.core.api`, `omni.usd.libs`, `isaacsim.ros2.bridge/jazzy`.
- The bundled `pxr/__init__.py` is found under `extscache/omni.usd.libs-*/pxr/` (static check; no import).

### §7 Active Python runtime
Profile-dependent:

| Profile | Expectation |
|---|---|
| `research` | `python` on PATH resolves to `env_isaaclab/bin/python` and reports 3.10.x |
| `isaac`    | `kit/python/bin/python3` exists and reports 3.11.x |
| `ros`      | `python3` on PATH is `/usr/bin/python3` and reports 3.12.x |
| `none`     | skipped |

### §8 USD importability (Runtime A)
Spawns the conda env's Python in a subprocess (does **not** activate conda) and runs `from pxr import Usd`. Reports:
- PASS with `Usd.GetVersion()` if it succeeded.
- PASS that `pxr.__file__` resolves under the conda env directory.
- FAIL with the exception message otherwise.

### §9 pxr importability (Runtime B — bundled)
- **Standard mode**: skipped; relies on the static file check from §6.
- **Deep mode (`--deep`)**: launches `$ISAAC_PATH/python.sh` with a 90-second timeout and runs `from pxr import Usd; import omni.kit.app`. Reports PASS/FAIL based on the launcher's exit code and stdout sentinel.

### §10 ROS 2 distro
- `/opt/ros/jazzy/` exists.
- Any other `/opt/ros/*/` distros installed are flagged as WARN (only Jazzy is canonical).
- In `ros` profile: `ROS_DISTRO=jazzy`, `ros2 pkg list` returns successfully, package count is reported.

### §11 PYTHONPATH contamination
Splits `PYTHONPATH` on `:` and classifies each entry as `conda`, `isaac`, `ros`, or `user`. The check fails if entries from two or more runtime classes are present at once (policy §5/§7 P5). Profile-specific rules also apply — e.g., `research` profile forbids any ROS or Isaac entries.

### §12 LD_LIBRARY_PATH contamination
Same approach: classifies entries as `isaac-install`, `isaac-bridge`, `ros`, or `cuda`. Specifically catches:
- Isaac install libs **and** `/opt/ros/` libs together without the bundled-bridge path → P7 violation.
- ROS libs in `research` or `isaac` profile.
- Isaac libs in `ros` profile.

### §13 Duplicate ROS sourcing
- `AMENT_PREFIX_PATH` contains Humble entries → P4 violation.
- `/opt/ros/jazzy*` appears more than once in `AMENT_PREFIX_PATH` → WARN (`setup.bash` was sourced multiple times).
- `ISAAC_ROS_WS` is set but points to a nonexistent path → WARN (P10).

### §14 Runtime profile correctness
Cross-checks for the three forbidden mixes (policy §7):

| Combination present | Rule | Severity |
|---|---|---|
| conda env_isaaclab + `/opt/ros/jazzy` sourced | P1 | FAIL |
| `/opt/ros/jazzy` sourced + `ISAAC_PATH` set | P7 | FAIL |
| conda env_isaaclab + `ISAAC_PATH` set | — | FAIL |
| CUDA bin on PATH outside `research` | §4 | WARN |

If no mix is detected and the script reached this point, a single PASS line confirms profile self-consistency.

---

## 6. Interpreting results

### All PASS
The active runtime matches policy. Proceed with work.

### PASS with WARN
The runtime is usable, but a non-critical condition exists. Common WARN cases:

| Warning | Meaning | Action |
|---|---|---|
| Stale `ISAAC_ROS_WS` | Inherited env var from login shell points nowhere | `unset ISAAC_ROS_WS`, ideally remove the export from `~/.bashrc` |
| Other ROS distros installed | Humble or other under `/opt/ros/` | Don't source them; remove if unused |
| Missing canonical dirs | One of the 12 workspace dirs is absent | `mkdir -p` the missing one |
| AMENT_PREFIX_PATH duplicates | `setup.bash` sourced multiple times | Open a fresh shell |
| `nvcc` not on PATH | `research` profile not active or CUDA bin not exported | `source scripts/activate_factory_env.sh research` |

### FAIL
The runtime violates policy. **Do not proceed with work**.

- Open the FAIL section to see which check failed.
- Cross-reference [docs/runtime_policy.md](runtime_policy.md) §7 (prohibited mixing) — each FAIL message names the rule (P1, P4, P5, P7, P10) it represents.
- The safest remedy for env-contamination FAILs is almost always **open a new shell and re-source `scripts/activate_factory_env.sh <profile>`**. Half-measures (`unset`, `conda deactivate` followed by `conda activate`) rarely produce a clean state.
- For install-missing FAILs (Isaac Sim, CUDA, conda env, ROS), file an environment-setup task — these are not script-fixable.

---

## 7. When to run

| Situation | Mode |
|---|---|
| Start of a working session | standard |
| Before a long-running Isaac Sim run | standard, then `--deep` if any doubt |
| After installing a package, sourcing a workspace, or editing shell rc files | standard |
| In CI, as the first step | standard (deep optional) |
| After upgrading Isaac Sim, CUDA, ROS, or conda | `--deep` |
| Triaging an "it worked yesterday" bug | `--deep` |

The `--deep` mode launches the full Kit Python interpreter, which is the only way to verify the bundled `pxr` and `omni.*` actually import end-to-end. Reserve it for upgrades and triage because each invocation takes 30–90 seconds.

---

## 8. Read-only guarantee

The script is verified read-only by inspection:

- `set -u` is local to the script and does not propagate to the parent shell.
- The script contains **no** `export`, `unset`, `cd`, `source`, `>` (write redirect), `mkdir`, `rm`, `mv`, `cp`, `chmod`, `chown`, `ln`, `touch`, `git`, `pip install`, `apt`, `conda activate`, `conda install`, `colcon build`, or daemon start commands at the top level.
- Subprocesses are invoked with the **inherited** environment plus the script's own constants — they do not source profiles, activate envs, or write outside their own stdout/stderr.
- The `--deep` Kit Python probe runs `python.sh -c` in a subprocess with `< /dev/null`; it does not start the Kit GUI.

If a future change adds any of the above primitives, the script's read-only guarantee is broken — flag it in code review.

---

## 9. Relation to other runtime tooling

| Tool | Purpose |
|---|---|
| [docs/runtime_policy.md](runtime_policy.md) | Authoritative policy — the source of truth this validator checks against. |
| [scripts/activate_factory_env.sh](../scripts/activate_factory_env.sh) | Dispatcher that puts the shell into one of `research|isaac|ros`. Run this **before** validating if you want a profile-active check. |
| `scripts/validate_runtime.sh` | This script. Validates current state; does not change it. |

A typical first-touch sequence:

```bash
# 1. New shell
exec bash --noprofile --norc

# 2. Validate the host (no profile yet — host-level checks)
bash scripts/validate_runtime.sh

# 3. Activate the profile you need
source scripts/activate_factory_env.sh research

# 4. Validate again (now per-profile checks run)
bash scripts/validate_runtime.sh

# 5. (Periodically) deep validation after upgrades or before long sims
bash scripts/validate_runtime.sh --deep
```

---

## 10. Limitations

- Does not validate **GPU compute** end-to-end (e.g., a CUDA kernel launch). Add that as a separate test in `tests/` if needed — it would require torch in the research profile and a non-trivial subprocess.
- Does not check **network DDS reachability** between hosts (only local `ros2 doctor` and pkg count).
- Does not verify **disk space**, **inode counts**, or **filesystem permissions** — those belong to a separate host-health check.
- Does not modify or repair anything by design. A separate `scripts/repair_runtime.sh` (not yet written) is the right home for any auto-remediation.
