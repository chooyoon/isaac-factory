# Runtime Policy

**Project**: Industrial Digital Twin
**Workspace**: `/home/cap2/last`
**Host**: `ascii-alpha` (RTX 5090, Ubuntu 24.04.3 LTS)
**Status**: Authoritative. Supersedes all ad-hoc setup scripts and any conflicting prior art under `/home/cap2/`.
**Last revised**: 2026-05-18

This document defines the runtimes, paths, and rules every contributor — human or agent — must follow when working in this workspace. Deviations require an explicit, written exception in a Sprint Contract or PR description.

---

## 1. Canonical Stack

| Layer | Canonical Choice | Path | Version |
|---|---|---|---|
| **ROS distribution** | **ROS 2 Jazzy Jalisco** | `/opt/ros/jazzy` | system install |
| **Simulator** | **NVIDIA Isaac Sim 5.0** | `/home/cap2/isaac-sim-5.0.0` | `5.0.0-rc.45+release.23960` |
| **Workspace root** | `/home/cap2/last` — **ONLY production workspace** | — | this repo |
| **Orchestration Python** | conda `env_isaaclab` | `/home/cap2/miniconda3/envs/env_isaaclab` | Python **3.10.12** |
| **In-Sim Python** | Isaac Sim Kit Python | `/home/cap2/isaac-sim-5.0.0/kit/python` | Python **3.11.13** |
| **ROS-side Python** | System Python | `/usr/bin/python3` | Python **3.12.3** |
| **Isaac Lab** | editable, in `env_isaaclab` | `/home/cap2/IsaacLab` | 2.2.0 |
| **CUDA toolkit** | `/usr/local/cuda` → `cuda-12.8` | — | 12.8.0 (matches `torch 2.7.0+cu128`) |
| **NVIDIA driver** | host | — | 590.48.01 (advertises CUDA 13.1 forward-compat) |

> Substitutions (different ROS distro, different sim, different Python) are **not** implementation decisions — they are policy questions. Escalate before changing.

### 1.1 Workspace Layout (canonical, 13 directories)

```
/home/cap2/last/
├── docs/           — specifications and policy (this file lives here)
├── isaac_factory/  — scripts run inside Isaac Sim Kit Python (Runtime B)
├── ros2_ws/        — colcon workspace for ROS 2 Jazzy (Runtime C); src/ under here
├── orchestration/  — Runtime A code: RL, training, analysis, USD authoring via usd-core
├── scripts/        — operator-facing entrypoints and shell launchers
├── assets/         — USD, materials, textures (reference where possible)
├── configs/        — YAML/TOML/JSON configuration; environment-agnostic
├── tests/          — regression, KPI, doctor checks
├── logs/           — runtime logs (rotated, gitignored)
├── datasets/       — input data (gitignored)
├── outputs/        — generated artifacts (gitignored)
├── tools/          — auxiliary utilities and one-shot maintenance scripts
└── cache/          — project-isolated caches (gitignored) — see docs/storage_policy.md §2
                      Subdirs: huggingface/, pip/, conda/pkgs/, torch/, omniverse/,
                      omniverse-data/, omniverse-logs/, nvidia-shader/, warp/,
                      matplotlib/, isaac-kit/
```

Reference-only sibling trees (under `/home/cap2/`, **never copy structure, never import code**): `factory/`, `IsaacLab/`, `IsaacSim-ros_workspaces/`, `auto-assembly-sim/`, `peg_in_hole_2026/`, `unitree_sim_isaaclab/`, `mrs/`, `lee/`, `ros-bridge/`, `ros2_nodes/`. They may be consulted as prior art only.

---

## 2. Runtime Separation Rules

The host runs **three distinct Python ABIs** that are never combined in a single process. Each has one job. The dispatcher script (`scripts/activate_factory_env.sh`) exposes them under three keywords: **`research`**, **`isaac`**, **`ros`**.

| Profile | Keyword | Python | Purpose | Where it runs |
|---|---|---|---|---|
| **A — Research** | `research` | conda `env_isaaclab` (3.10.12) | RL training, IsaacLab tasks, offline USD authoring, data pipelines, analysis | `orchestration/`, `tools/`, `tests/`, `datasets/` |
| **B — Isaac** | `isaac` | Isaac Sim Kit Python (3.11.13) | Anything that imports `omni.*` or the bundled `pxr`; scenes, replicator, physics setup | `isaac_factory/`, launched via `./python.sh` or `./isaac-sim.sh` |
| **C — ROS** | `ros` | System Python (3.12.3) | `ros2 *` CLI, `colcon build`, `rclpy` nodes, launch files | `ros2_ws/`, `scripts/` (ros launchers only) |

### Hard separation rules

1. **One runtime per process.** Never `import` across runtime boundaries.
2. **One runtime profile per shell.** Activate exactly one profile (§4). To switch, **open a new shell** — do not `unset`/re-source. The three runtimes — **ROS 2 Jazzy**, **Isaac Sim Kit Python**, and **conda env_isaaclab (IsaacLab)** — must never be combined in a single shell.
3. **No reuse of site-packages.** Each runtime sees only its own `site-packages`; nothing is symlinked between them.
4. **Cross-runtime communication is through ROS 2 topics/services or external IPC only.** No shared Python imports across runtimes. No shared memory, no `pickle` over `multiprocessing.Manager`, no in-process function calls between ABIs.

### Cross-runtime communication channels

The only permitted transports between runtimes are:

| Channel | Notes |
|---|---|
| **ROS 2 topics / services / actions** | Primary channel for live signals (sensor data, commands, status). Runtime B publishes via the bundled `isaacsim.ros2.bridge/jazzy`; Runtimes A and C subscribe via their native bindings (`rclpy` for C; `rosbags` package for A). |
| **External IPC** | TCP/UDS sockets, named pipes, gRPC. Use when the message shape does not fit ROS 2 message types. |
| **File handoff** | USD in `assets/`, JSON/parquet in `outputs/` or `datasets/`, ROS bag files (`mcap`/`sqlite3`) in `datasets/`. Use for batch / offline flows. |
| **CLI process spawn** | A spawns B via `./python.sh`/`./isaac-sim.sh`; arguments and exit codes are the contract. |

Anything not in this table is forbidden. Specifically: no shared `numpy` arrays via `multiprocessing.shared_memory`, no `pickle` over sockets between ABIs, no in-process `import` of one runtime's modules from another runtime's interpreter.

---

## 3. Python Usage Policy

| If you are writing… | Use profile | Python |
|---|---|---|
| An RL training loop, a Hydra script, a torch model, a `usd-core` USD authoring script | **`research`** | conda env_isaaclab, 3.10 |
| A scene generator, replicator pipeline, asset converter, anything that touches `omni.*` or `pxr` | **`isaac`** | Kit Python, 3.11 |
| A `rclpy` node, a launch file, a `colcon` package | **`ros`** | system, 3.12 |
| A shell launcher, a Makefile target, a doctor check | n/a | shell — does not choose Python at all |

### Rules

- **No `pip install` into Kit Python (Runtime B).** Kit Python is treated as immutable. Third-party Python deps live in Runtime A.
- **No `pip install --user` into system Python (Runtime C).** It bleeds into ROS 2's import path and breaks `colcon`. Use `apt` for ROS packages or Runtime A for general Python.
- **All Runtime A deps are declared** in an `orchestration/requirements.txt` (or `pyproject.toml`) and installed into `env_isaaclab`. No interactive `pip install` without recording.
- **One `numpy` per process.** If a script needs both ROS message types and `torch`, it is mis-architected — split it into two processes.
- **Version-pinned compatibility**: `torch 2.7.0+cu128` ↔ CUDA 12.8 ↔ Python 3.10 in Runtime A is a known-good triple. Do not bump independently.

---

## 4. Activation Order

Pick **exactly one** profile per shell. The order of steps is load-bearing — each step assumes the previous one has run and **none** is run twice.

### Profile A — Research shell (`research`)

```bash
# 1. Clean shell — no inherited ROS or Isaac state
exec bash --noprofile --norc
# 2. Conda
source /home/cap2/miniconda3/etc/profile.d/conda.sh
conda activate env_isaaclab
# 3. Workspace
export WORKSPACE_ROOT=/home/cap2/last
cd "$WORKSPACE_ROOT"
# 4. CUDA toolkit (only in Profile A)
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}
# 5. Override broken pip cache (PIP_CACHE_DIR points to an unwritable shared dir)
export PIP_CACHE_DIR="$HOME/.cache/pip"
# 6. Verify
python -c "import sys, torch; print(sys.version); assert torch.cuda.is_available()"
```

**Forbidden in this profile**: sourcing `/opt/ros/jazzy/setup.bash`; exporting any path under `/home/cap2/isaac-sim-5.0.0`.

### Profile B — Isaac Sim shell (`isaac`)

```bash
# 1. Clean shell
exec bash --noprofile --norc
# 2. Workspace + Isaac path
export WORKSPACE_ROOT=/home/cap2/last
export ISAAC_PATH=/home/cap2/isaac-sim-5.0.0
cd "$WORKSPACE_ROOT"
# 3. ROS 2 bridge libs (ONLY if the launched script uses the bridge)
export LD_LIBRARY_PATH="$ISAAC_PATH/exts/isaacsim.ros2.bridge/jazzy/lib:${LD_LIBRARY_PATH:-}"
# 4. Launch — Kit Python finds pxr/omni from extscache itself
"$ISAAC_PATH/python.sh" isaac_factory/<script>.py [--headless]
# or:
"$ISAAC_PATH/isaac-sim.sh"
```

**Forbidden in this profile**: `conda activate`; `source /opt/ros/jazzy/setup.bash`; adding conda or system `site-packages` to `PYTHONPATH`.

### Profile C — ROS 2 Jazzy shell (`ros`)

```bash
# 1. Clean shell
exec bash --noprofile --norc
# 2. ROS 2 base
source /opt/ros/jazzy/setup.bash
# 3. Workspace + overlay (overlay AFTER base, never before)
export WORKSPACE_ROOT=/home/cap2/last
cd "$WORKSPACE_ROOT"
[ -f ros2_ws/install/setup.bash ] && source ros2_ws/install/setup.bash
# 4. DDS / discovery
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
# 5. Unset stale env var inherited from user shell
unset ISAAC_ROS_WS
# 6. Verify
ros2 doctor --report | head -20
```

**Forbidden in this profile**: `conda activate`; exporting any path under `/home/cap2/isaac-sim-5.0.0` or `/usr/local/cuda`.

### Why the order matters

1. **Start clean.** A fresh shell is the cheapest correct way to guarantee no profile leak.
2. **Conda before workspace** (Profile A) — `conda activate` rewrites `PATH`; doing it after custom exports silently shadows them.
3. **CUDA paths only in Profile A** — Kit and ROS do not need them, and they have caused symbol conflicts.
4. **ROS base before overlay** (Profile C) — colcon's `install/setup.bash` chains onto whatever is already sourced; reversing the order produces undefined behavior.
5. **Bridge libs immediately before launch** (Profile B) — the export is scoped to that one process; doing it earlier leaks to unrelated children.

---

## 5. `PYTHONPATH` Policy

`PYTHONPATH` is the single most common source of cross-runtime contamination on this host. The rules below are absolute.

### General rule

> **Treat `PYTHONPATH` as empty unless a specific scenario below requires otherwise.** Each runtime's interpreter knows how to find its own packages — appending to `PYTHONPATH` is almost always wrong.

### Per-profile policy

| Profile | What may be in `PYTHONPATH` | What must NOT be |
|---|---|---|
| **`research`** | Empty, OR exactly `${WORKSPACE_ROOT}/orchestration` if importing local modules. | Anything from `/opt/ros/jazzy/...`, `/home/cap2/isaac-sim-5.0.0/...`, or another conda env. |
| **`isaac`** | Empty by default. `${ISAAC_PATH}/exts/isaacsim.ros2.bridge/jazzy/lib/python3.11/site-packages` **only** when the script uses the ROS 2 bridge. | Anything from `env_isaaclab`, anything from `/opt/ros/jazzy/lib/python3.12/...`, anything from system `site-packages`. |
| **`ros`** | The default `/opt/ros/jazzy/lib/python3.12/site-packages` (set by `setup.bash`), plus `${WORKSPACE_ROOT}/ros2_ws/install/.../site-packages` (set by overlay). | Anything from `env_isaaclab`, anything from Isaac Sim's bundled libs. |

### Diagnostic

If `python -c "import sys; [print(p) for p in sys.path]"` shows entries from more than one of `{miniconda3, isaac-sim-5.0.0, /opt/ros/jazzy, /usr/lib/python3.12}` at the same time, the shell is contaminated — abandon it and open a new one.

### Inherited contamination — known cases

- The user's login shell sets `PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages`. The `research` profile must `unset PYTHONPATH` (or rely on `conda activate` resetting it, which it does on this conda version) before any work.
- `ISAAC_ROS_WS=/home/cap2/workspaces/isaac_ros-dev/` is inherited and points to a non-existent path. All profiles must `unset` it.

The dispatcher script `scripts/activate_factory_env.sh` performs this scrub automatically before activating any profile.

---

## 6. USD Import Policy

USD is the only library that exists in **three incompatible variants** on this host. Each one has a single legal import site.

| Where you are | USD import | Notes |
|---|---|---|
| Runtime A (`env_isaaclab`, Py 3.10) | `from pxr import Usd` — uses pip's **`usd-core 26.3`** | Standalone, no Kit context. Sufficient for authoring, validation, batch composition. |
| Runtime B (Kit Python, Py 3.11) | `from pxr import Usd` — uses Isaac Sim's bundled `pxr` from `extscache/omni.usd.libs-*/pxr` | The only place schemas like `omni.usd.schema.physx`, `omni.usd.schema.omnigraph`, `omni.usd.schema.semantics` are available. |
| Runtime C (ROS 2, system Py 3.12) | **Forbidden.** Do not import `pxr` here. | No USD build installed for Python 3.12. ROS code that needs USD data should consume serialized USD via files or via a Runtime A/B subprocess. |

### Rules

1. **Never add Isaac Sim's `extscache/.../pxr` directory to `PYTHONPATH`** outside of Runtime B. The bundled `pxr` is built for **cp311**; loading it under cp310 or cp312 segfaults or fails import.
2. **Never `pip install usd-core` into Kit Python.** Kit's bundled `pxr` already shadows it and the duplicate import path corrupts the schema registry.
3. **Schema authoring** that requires `omni.usd.schema.*` (physx, omnigraph, semantics, anim) **must** run in Runtime B. Runtime A's `usd-core` does not ship these.
4. **Round-tripping USD between A and B is allowed** — write the file in A, open it in B, or vice versa. The on-disk USD format is the cross-runtime contract.
5. **Layer composition with custom file format plugins** (e.g., `omni`-prefixed schemes like `omniverse://`) only works in Runtime B. Runtime A's `usd-core` resolves only `file://` paths.

### Determining which `pxr` you imported

```python
import pxr, sys
print(pxr.__file__)
# Runtime A → .../miniconda3/envs/env_isaaclab/lib/python3.10/site-packages/pxr/__init__.py
# Runtime B → .../isaac-sim-5.0.0/extscache/omni.usd.libs-*/pxr/__init__.py
# Anything else → contamination. Abort.
```

---

## 7. Prohibited Mixed Runtime Imports

Each rule below has already broken something on this host. The "failure mode" column is the symptom you will see if you violate it.

| # | Prohibited | Failure mode |
|---|---|---|
| **P1** | `conda activate env_isaaclab` **and** `source /opt/ros/jazzy/setup.bash` in the same shell. | NumPy 1.26 (conda) vs ROS-side packages built against system NumPy → `rclpy` import fails or messages silently mismatch type IDs. |
| **P2** | Importing `pxr` from system Python 3.12 **or** from `env_isaaclab` directly out of `isaac-sim-5.0.0/extscache`. | Bundled `pxr` is cp311; loading under another ABI causes `ImportError` or segfault. Use `usd-core` in Runtime A instead. |
| **P3** | Importing `omni.*` from anywhere outside Isaac Sim Kit Python. | `omni.kit.app` requires the Kit runtime context; standalone imports raise `ModuleNotFoundError` or crash on first `carb` call. |
| **P4** | Mixing ROS Humble and ROS Jazzy paths in `PATH` / `LD_LIBRARY_PATH` / `AMENT_PREFIX_PATH`. | DDS plugin loader resolves the wrong typesupport library; messages serialize but deserialize to garbage. Legacy `~/run_isaac.sh` is non-compliant. |
| **P5** | `PYTHONPATH` containing both conda `site-packages` and Isaac Sim bundled Python paths. | `numpy`, `typing_extensions`, `protobuf` load from the wrong copy → segfault at runtime. |
| **P6** | `pip install` inside Isaac Sim Kit Python. | Installed packages survive only until the next Isaac update; meanwhile they shadow Kit's vendored copies and break extension loading. |
| **P7** | Sourcing `/opt/ros/jazzy/setup.bash` **before** launching `isaac-sim.sh`. | Isaac Sim's bridge loads its own `librcl*`; system ROS libs win the resolver → bridge crashes on symbol mismatch. |
| **P8** | Running `colcon build` from inside `env_isaaclab`. | colcon picks up conda's Python 3.10; generated message Python bindings then fail to load under the system Python 3.12 the rest of Jazzy uses. |
| **P9** | Editing files under `/home/cap2/isaac-sim-5.0.0/` or `/opt/ros/jazzy/`. | Upstream installs; changes are silently overwritten by reinstalls and produce non-reproducible builds. Use extensions or overlay workspaces. |
| **P10** | Trusting `ISAAC_ROS_WS=/home/cap2/workspaces/isaac_ros-dev/` (inherited from the user shell). | Path does not exist. Treat as stale; profiles must `unset` it. |

---

## 8. Verification

Each profile has a one-liner that confirms it activated cleanly. Run after sourcing `scripts/activate_factory_env.sh <profile>`, before any non-trivial session.

```bash
# research
python -c "import sys, torch, isaaclab; \
  print(sys.version.split()[0], torch.__version__, torch.cuda.is_available())"
# Expect: 3.10.12 2.7.0+cu128 True

# isaac
"$ISAAC_PATH/python.sh" -c \
  "import sys; from pxr import Usd; import omni.kit.app; \
   print(sys.version.split()[0], Usd.GetVersion())"
# Expect: 3.11.13 (0, 25, ...) — bundled Kit USD version

# ros
ros2 doctor --report | grep -E 'ROS_DISTRO|RMW'
ros2 pkg list | wc -l
# Expect: ROS_DISTRO=jazzy, RMW=rmw_fastrtps_cpp, ~381 packages
```

If any check fails, **do not proceed**. Open a new shell, re-activate from §4, and try again. If it still fails, the host configuration has drifted from this policy — that is a policy issue, not a debugging issue.

---

## 9. Exceptions

An exception is granted only when **all** of the following are true:

1. The Sprint Contract or PR description names the rule (e.g., "P4 exception") and quotes the failure mode it bypasses.
2. The exception is scoped to a single script or shell session and reverts on exit.
3. A regression test in `tests/` covers the failure mode the rule was protecting against.

Otherwise: **follow the rule.** Each rule exists because something already broke.
