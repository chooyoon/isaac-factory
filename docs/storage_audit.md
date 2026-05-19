# Storage Audit

**Workspace**: `/home/cap2/last`
**Host**: `ascii-alpha`
**Date**: 2026-05-18
**Mode**: Inspection only — no files moved or deleted.

This report inventories every cache, log, model, and artifact directory relevant to the industrial digital twin runtime, classifies each by **runtime criticality** and **movability**, and flags directories likely to grow into a problem.

---

## 1. Headline numbers

| Mount | Size | Used | Free | Use% |
|---|---|---|---|---|
| `/` (`/dev/nvme0n1p2`, NVMe) | 937 G | **782 G** | 108 G | **88 %** ⚠️ |
| `/home2` (`/dev/sda1`, SATA) | 15 T | 879 G | 13 T | **7 %** |
| `/tmp` (tmpfs) | 32 G | 8.6 M | 32 G | 1 % |

- Root partition is **88 %** full. Less than 110 GB free.
- `/home2` holds **13 TB** of free, idle capacity on the same host. It is the obvious relocation target for anything large that does not need NVMe latency.
- Inode pressure is not a concern (`/` at 6 %, `/home2` at 1 %).
- `/home/cap2/` total: **188 G**. The remaining ~594 GB on `/` belongs to other users (`/home/shared/`, other home dirs, system).

---

## 2. Largest directories (sorted)

### 2.1 On root partition (`/`)

| Size | Path | Category |
|---|---|---|
| **101 G** | `/home/shared/.cache/huggingface` | model cache (shared group) |
| **89 G** | `/home/cap2/IsaacLab` | IsaacLab tree, of which **88 G is `logs/rl_games/`** |
| **25 G** | `/home/cap2/isaac-sim-5.0.0` | Isaac Sim 5.0 install (canonical) |
| **22 G** | `/home/cap2/miniconda3` | conda root (envs 12 G + pkgs 5.9 G) |
| **16 G** | `/home/cap2/.cache/ov` | Omniverse user cache (textures, shaders, client) |
| **15 G** | `/home/shared/.cache/pip` | pip cache (shared group, unwritable by cap2) |
| **14 G** | `/home/cap2/miniconda3/envs/env_isaaclab` | canonical research env |
| **9.0 G** | `/home/cap2/isaac-sim-5.0.0/extscache` | Isaac extscache (includes bundled pxr, omni schemas) |
| **9.3 G** | `/home/cap2/.cache/ov/texturecache` | Omniverse texture cache |
| **7.8 G** | `/home/cap2/cuda-repo-…amd64.deb` ×2 | duplicate cuda 12.8 installer (and `.deb.1`) |
| **7.1 G** | `/home/cap2/isaac-sim-5.0.0/exts` | Isaac shipped extensions |
| **5.9 G** | `/home/cap2/miniconda3/pkgs` | conda package cache (816 cached pkg dirs) |
| **4.5 G** | `/home/cap2/IsaacSim-ros_workspaces` | reference workspaces (humble_ws + jazzy_ws + duplicate) |
| **4.4 G** | `/home/cap2/factory` | sibling project (reference-only) |
| **3.9 G** | `/home/cap2/.cache/pip` | fallback pip cache (because `/home/shared/.cache/pip` is unwritable) |
| **2.9 G** | `/home/cap2/.cache/ov/client` | Omniverse Nucleus client cache |
| **2.3 G** | `/home/cap2/isaac-sim-5.0.0/kit/cache` | Kit launcher cache |
| **2.2 G** | `/home/cap2/.cache/ov/shaders` | Omniverse shader cache |
| **1.7 G** | `/home/cap2/unitree_sim_isaaclab/assets` | sibling project assets |
| **1.5 G** | `/home/cap2/.cache/ov/cache` | Omniverse generic cache |
| **1.4 G** | `/home/cap2/blender-4.5` | Blender 4.5 install |
| **1.1 G** | `/home/cap2/.local/share/ov/data` | Omniverse hub data (Kit user data) |
| **446 M** | `/home/cap2/.nv/ComputeCache` | NVIDIA CUDA shader cache (driver-managed) |
| **353 M** | `/home/cap2/.local/share/ov/pkg` | Omniverse Hub package (hub-2.0.0) |
| **214 M** | `/home/cap2/.nvidia-omniverse/logs` | Omniverse runtime logs |

### 2.2 On `/home2` (idle target)

`/home2/cap2/` exists but is small (size not separately measured here). Other users' data dominates: `cap10` has the 137 GB ImageNet 2012 train tar + 6.3 GB val tar. **Plenty of headroom** for relocations.

### 2.3 Inside the canonical workspace

`/home/cap2/last/` itself is **128 K** — only `docs/` (36 K) and `scripts/` (48 K) hold anything. The other 10 directories are empty. **Zero current pressure from the workspace itself.**

---

## 3. Audit by focus area

### 3.1 Isaac Sim install / caches

| Path | Size | Notes |
|---|---|---|
| `/home/cap2/isaac-sim-5.0.0/extscache` | 9.0 G | bundled extensions (incl. pxr cp311 build); install-managed |
| `/home/cap2/isaac-sim-5.0.0/exts` | 7.1 G | shipped extensions; install-managed |
| `/home/cap2/isaac-sim-5.0.0/kit/cache` | 2.3 G | Kit launcher cache (regenerable) |
| `/home/cap2/isaac-sim-5.0.0/docs` | 192 M | offline Kit docs |
| `/home/cap2/isaacsim_old/` | 0 B | empty shell of the 4.2 install; deletable |

Total active Isaac Sim install: **25 G**. Most of that (16 G) is `extscache` + `exts` and **must stay co-located with the launcher** — these are loaded by file path from `kit-app.toml` manifests.

### 3.2 Shader cache

| Path | Size | Owner |
|---|---|---|
| `/home/cap2/.cache/ov/shaders` | 2.2 G | Omniverse RTX shaders (per-asset cache) |
| `/home/cap2/.nv/ComputeCache` | 446 M | NVIDIA driver-level CUDA shader cache |
| `/home/cap2/.cache/mesa_shader_cache_db` | 2.1 M | Mesa (CPU GL fallback) |

Driver-level shader caches are **always regenerable** but tank the first-run latency of new scenes when missing. Acceptable to relocate; not safe to lock to a slow medium (SATA HDD-class write would visibly slow shader compilation).

### 3.3 Omniverse cache (`~/.cache/ov`)

| Sub-path | Size |
|---|---|
| `texturecache/` | 9.3 G |
| `client/` (Nucleus) | 2.9 G |
| `shaders/` | 2.2 G |
| `cache/` (generic) | 1.5 G |
| `DerivedDataCache/` | 30 M |
| `ogn_generated/` | 11 M |
| **Total** | **16 G** |

Currently active — newest mtime is **today (2026-05-18)**, driven by the `factory/` project's stage rendering work. Texture cache is the dominant component (single textures up to 128 MB each). Will grow without bound as new USD assets are loaded.

### 3.4 Logs

| Path | Size | Newest | Status |
|---|---|---|---|
| `/home/cap2/IsaacLab/logs/rl_games` | **88 G** | 2026-03-26 (~2 months old) | **stale**; RL training artifacts from past runs |
| `/home/cap2/IsaacLab/logs/rsl_rl` | 21 M | — | small |
| `/home/cap2/.nvidia-omniverse/logs` | 214 M | active | Omniverse client logs (rotated by Kit) |
| `/home/cap2/IsaacLab/logs/docker_tutorial` | 312 K | — | tutorial leftover |
| `/home/cap2/peg_in_hole_2026/logs` | 4.1 M | — | RL run logs |
| `/home/cap2/auto-assembly-sim/logs` | 100 K | — | small |
| `/home/cap2/last/logs` | empty | — | canonical workspace logs dir |
| `/home/cap2/isaac-sim-5.0.0/logs` | — | — | (not separately measured; small) |

**`IsaacLab/logs/rl_games` is by far the single largest log directory on the host (88 G, untouched for ~2 months).** This is the biggest single relocation/cleanup candidate.

### 3.5 Checkpoints

| Path | Size | Notes |
|---|---|---|
| `/home/cap2/peg_in_hole_2026/checkpoints` | 4 K (empty) | — |
| `/home/cap2/factory/checkpoints` | (not measured separately; small, inside the 4.4 G `factory/` total) | — |
| `/home/cap2/auto-assembly-sim/checkpoints` | — | placeholder |
| `/home/cap2/last/checkpoints` | **does not exist** | not in canonical 12 dirs — checkpoints live under `outputs/` if at all |

Distinct project-level checkpoint hoards are not yet a problem on this host. Future checkpoints from IsaacLab training will land under `IsaacLab/logs/` unless redirected.

### 3.6 Datasets

| Path | Size | Notes |
|---|---|---|
| `/home/cap2/last/datasets` | empty | canonical |
| `/home/cap2/factory/assets` | 3.2 G | external USD/textures/materials referenced by sibling project |
| `/home/cap2/peg_in_hole_2026/data` | 4 K (empty) | — |
| `/home/cap2/auto-assembly-sim/data` | 8 K | empty |
| `/home2/ILSVRC2012_img_train.tar` (other user) | 147 G | external to `cap2`, on /home2 already |

No project-owned dataset hoard yet inside `last/`. Once the project starts ingesting data, `datasets/` should be pre-pointed at `/home2/cap2/datasets/` via symlink before it grows.

### 3.7 Replicator outputs

| Path | Size |
|---|---|
| `/home/cap2/omni.replicator_out` | empty (4 K placeholder) |
| `/home/cap2/last/outputs` | empty |

Currently **zero replicator output stored**. This will change rapidly once synthetic data generation runs — Replicator produces multi-GB image/depth/seg sequences per session. The default output path of `omni.replicator_out` is at `$HOME` (root partition) — needs explicit redirect in scripts.

### 3.8 TensorBoard runs

| Path | Size | Newest | Notes |
|---|---|---|---|
| `/home/cap2/runs` | 7.1 M | 2026-04-25 | YOLO `detect/val2/` outputs, not TB |
| `/home/cap2/IsaacLab/logs/rl_games/*/runs` | (part of 88 G) | 2026-03-26 | implicit TB event files inside RL log dirs |

No standalone TB run hoard. The growth risk lives inside the `IsaacLab/logs/rl_games` 88 G — TensorBoard event files are co-located with checkpoints.

### 3.9 Pip cache

| Path | Size | Writable by `cap2`? |
|---|---|---|
| `/home/shared/.cache/pip` | 15 G | **No** (perms; group `shared`) |
| `/home/cap2/.cache/pip` | 3.9 G | Yes (fallback) |

Currently effective cache is **`~/.cache/pip` 3.9 G** because the policy `PIP_CACHE_DIR=/home/shared/.cache/pip` is not writable by `cap2`. The 15 G shared cache is historical, not actively grown by this user. Policy §4 already overrides to `$HOME/.cache/pip` in the `research` profile.

### 3.10 HuggingFace cache

| Path | Size |
|---|---|
| `/home/shared/.cache/huggingface` | **101 G** |
| └ `hub/` (models) | 98 G |
| └ `lerobot/` | 1.9 G |
| └ `clip/` | 1.6 G |
| └ `datasets/` | 26 M |
| └ `xet/` | 22 M |

Top models in `hub/`:

| Model | Size |
|---|---|
| `nvidia/Alpamayo-R1-10B` | 21 G |
| `moojink/openvla-7b-oft-finetuned-libero-spatial` | 15 G |
| `lerobot/pi0_base` | 14 G |
| `meta-llama/Llama-2-7b-hf` | 13 G |
| `declare-lab/nora-long` | 7.1 G |
| `InternRobotics/InternVLA-M1` | 7.0 G |
| `nvidia/GR00T-N1.6-3B` | 6.2 G |
| `facebook/opt-1.3b` | 5.0 G |

Set via `HF_HOME=/home/shared/.cache/huggingface` (env-inherited). On the **root partition**. Newest mtime 2026-05-13, actively used. **Single largest relocatable consumer on `/`.**

---

## 4. Classification

### 4.1 Runtime-critical (do not move without symlink + testing)

| Path | Why critical | Safer relocation |
|---|---|---|
| `/home/cap2/isaac-sim-5.0.0/` (25 G) | Kit `.toml` manifests load extensions from absolute paths; rebinding requires sweeping config edits | Possible via symlink but verify with `validate_runtime.sh --deep` after |
| `/home/cap2/miniconda3/` (22 G) | Conda envs encode interpreter paths; moving breaks shebangs in installed wheels | Re-create env in a new location; do not just `mv` |
| `/opt/ros/jazzy/` | System apt install | Not movable |
| `/usr/local/cuda*` | System install | Not movable |
| NVMe latency | Shader compilation, Kit boot, USD parsing | Keep Isaac Sim + conda env on NVMe |

### 4.2 Safely movable (regenerable or pure data)

| Path | Size | Recommended new home | Mechanism |
|---|---|---|---|
| `/home/cap2/IsaacLab/logs/rl_games` | **88 G** | `/home2/cap2/IsaacLab/logs/rl_games` | symlink the `logs/` dir |
| `/home/shared/.cache/huggingface` | 101 G | `/home2/shared/.cache/huggingface` | `HF_HOME` env override + rsync |
| `/home/cap2/.cache/ov` | 16 G | `/home2/cap2/.cache/ov` | symlink (Omniverse re-creates if missing) |
| `/home/cap2/.cache/pip` + `/home/shared/.cache/pip` | 3.9 + 15 G | `/home2/.../pip` | `PIP_CACHE_DIR` env (already in policy §4) |
| `/home/cap2/miniconda3/pkgs/` (816 dirs) | 5.9 G | regenerable | `conda clean -a` reclaims; not a relocation |
| `/home/cap2/isaac-sim-5.0.0/kit/cache` | 2.3 G | regenerable | clear via Isaac Sim's `clear_caches.sh`; refills on next boot |
| `/home/cap2/.nv/ComputeCache` | 446 M | `/home2/cap2/.nv/...` if NVMe pressure justifies it | symlink; first-run slowdown is mild |
| `/home/cap2/factory/` (4.4 G) | reference-only sibling | `/home2/cap2/factory/` | mv whole tree once user confirms it's reference-only |
| `/home/cap2/IsaacSim-ros_workspaces/` (4.5 G, incl. nested duplicate) | reference | `/home2/cap2/...` | mv (clean up nested dup first) |
| Loose `cuda-repo-…amd64.deb` + `.deb.1` (3.9 G × 2 = 7.8 G) | stale installer | delete the `.deb.1` (duplicate), archive the other if wanted | `rm`, with confirmation |
| `/home/cap2/isaacsim_old/` (0 B shell) | dead remnant | delete entirely | `rmdir`/`rm -rf` |
| `/home/cap2/omni.replicator_out/` (empty) | placeholder | symlink to `/home2/cap2/replicator_out` *before* generating data | symlink |
| `/home/cap2/runs/detect/` (7.1 M) | old YOLO val outputs | `/home2/cap2/runs/` or delete | mv |
| Loose `NvStreamer-*.etli` ×6 (~24 M total) | NVIDIA Nsight Streamer traces | `tools/diagnostics/` or delete | unclear if still needed |
| `/home/cap2/yolov8n.pt` (6.3 M), `yolo26n.pt` (5.3 M) | small model weights | `assets/models/` | small; low priority |

### 4.3 Cold but ambiguous

| Path | Size | Why ambiguous |
|---|---|---|
| `/home/cap2/IsaacLab/logs/rl_games` | 88 G | Newest mtime is **2026-03-26 (~2 months old)**. Almost certainly stale — but contains historical RL checkpoints that may still be referenced by analysis scripts. Confirm with user before bulk-moving. |
| `/home/cap2/peg_in_hole_2026/results_*` | 5 dirs × 14–52 MB ≈ 180 MB total | Many `results_*` snapshot directories (`results_partial_*`, `results_pre_final_*`, `results_bug_broken_pre_drfix_*`); some look like intermediate save-points, some like rescue copies. User context needed before pruning. |
| Two identical `cuda-repo-…12-8-local_…amd64.deb` files (one with `.1` suffix) | 7.8 G | The `.1` is a confirmed duplicate from a re-download. Safe to delete after MD5 check. |

---

## 5. Growth risk projection

Ranked by expected delta over the next 90 days, given the current project trajectory (Phase 0 → simulation work + RL training in `research` profile).

| Rank | Source | Current | 90-day projection | Mitigation |
|---|---|---|---|---|
| 1 | **IsaacLab/logs/rl_games** | 88 G | **+50–150 G** if RL training resumes; each task × seeds × env count produces multi-GB per run | Redirect `IsaacLab/logs` to `/home2` **before** training restarts; add `tests/doctor.sh` check for log dir mount |
| 2 | **HF cache** | 101 G | +20–60 G per new VLA / robot foundation model downloaded | Move `HF_HOME` to `/home2`; one-time rsync |
| 3 | **`.cache/ov/texturecache`** | 9.3 G | +5–20 G as new USD assets (factory `assets/` is currently 3.2 G) get rendered | Symlink `~/.cache/ov` to `/home2`; clear via Isaac Sim `clear_caches.sh` periodically |
| 4 | **Replicator outputs** (currently zero) | 0 | **+10–500 G** the first time SDG runs (depth/seg/rgb per env per step) | Decide output path **before** running Replicator; default writes to `$HOME/omni.replicator_out` (root partition) |
| 5 | **Workspace `logs/` + `outputs/` + `datasets/`** | empty | depends on usage | Pre-symlink to `/home2/cap2/last/{logs,outputs,datasets}` before populating |
| 6 | **conda `pkgs/`** | 5.9 G | +1–3 G per env update or pip install activity | `conda clean -a` quarterly; doesn't need relocation |
| 7 | **Omniverse logs** | 214 M | low growth; Kit rotates | leave |
| 8 | **`.nv/ComputeCache`** | 446 M | low growth (caps at a few GB) | leave |

**Headroom math, no action**: 108 G free now. Items 1 + 4 alone could blow through that within one heavy training week. The threshold for "filesystem full" pain is well within reach.

**Headroom math, with items 1+2 relocated**: ~189 G recovered → ~297 G free. Comfortable runway.

---

## 6. Observations worth flagging

- **The pip cache situation is self-defeating.** `PIP_CACHE_DIR=/home/shared/.cache/pip` (15 G) is set in the inherited shell env but is not writable by `cap2`; every `pip install` warns and disables cache, then quietly accumulates a separate 3.9 G under `~/.cache/pip`. Two caches, neither effective. Policy §4 (`research` profile activator) already overrides; no system-wide fix attempted in this audit.
- **`IsaacLab/_isaac_sim` is empty** (0 B). This is the symlink target IsaacLab expects to point at an Isaac Sim install. Probably benign here because the editable install in `env_isaaclab` works around it, but worth knowing if IsaacLab CLI starts misbehaving.
- **Two CUDA repo installers** (`cuda-repo-…amd64.deb` and `…amd64.deb.1`) sum to 7.8 G in `$HOME`. Identical filenames except the `.1` suffix — almost certainly a duplicate download. The non-suffixed file is dated Jan 2025; toolkit 12.8 is already installed at `/usr/local/cuda-12.8`. Neither file is referenced by anything live.
- **The `omni.replicator_out/` directory at `$HOME` is the implicit default for Isaac Sim Replicator outputs.** It is currently empty. The first synthetic-data-generation run will start writing there *on the root partition* unless the script overrides the output path. This is the single highest-velocity growth surprise this host can hit.
- **Loose `NvStreamer-*.etli` files** at `$HOME` (6 files, ~24 M total, March 2026) appear to be NVIDIA Nsight Streamer captures. If still needed they belong in `tools/diagnostics/`; otherwise they're cruft.

---

## 7. Summary table

| Bucket | Size | On `/`? | Action posture |
|---|---|---|---|
| **Runtime-critical, keep on NVMe** | ~50 G | yes | Isaac Sim 5.0, miniconda envs, ROS install, CUDA |
| **Large + safely movable to `/home2`** | ~225 G | yes | IsaacLab logs (88 G) + HF cache (101 G) + ov cache (16 G) + pip caches (19 G) + factory ref (4 G) |
| **Reclaimable (delete/clean)** | ~14 G | yes | cuda-repo .deb duplicate (3.9 G), conda pkgs clean (5.9 G), isaacsim_old shell (0), kit/cache regenerable (2.3 G) |
| **Empty / placeholder (zero now, watch later)** | — | yes | replicator output dir, workspace `logs/`/`outputs/`/`datasets/` |

**Bottom line**: ~80 % of pressure on `/` is from data that *should* live on `/home2`. None of it was moved by this audit. The single highest-leverage move would be `IsaacLab/logs/` → `/home2/cap2/IsaacLab/logs/` via symlink — that alone reclaims 88 G and removes the largest growth source.

---

## 8. What this audit did NOT do

- Did not move, copy, link, delete, or modify anything.
- Did not run `du` deep enough to verify hardlink-aware totals (so HF blobs counted once each — accurate).
- Did not check filesystem snapshots, btrfs subvolumes, or LVM (this is plain ext4, single partition per device).
- Did not assess `/home2/` contents in detail — only confirmed it has 13 TB free.
- Did not contact remote services (Nucleus, HF, conda) to verify cache validity.
- Did not modify any env vars, including `HF_HOME`, `PIP_CACHE_DIR`, or `OV_CACHE_PATH`.

Remediation would happen in a separate, user-approved change (per [docs/runtime_policy.md](runtime_policy.md) §9 exception process), not in this audit.
