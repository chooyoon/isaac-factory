# Storage Policy

**Workspace**: `/home/cap2/last`
**Host**: `ascii-alpha` (shared research server)
**Status**: Authoritative. Supersedes the relocation recommendations in [docs/storage_audit.md](storage_audit.md) §4.2.
**Last revised**: 2026-05-18

This policy defines **where the industrial digital twin project's data, models, caches, logs, and outputs live** on disk. The motivating constraint is host shared use: `/home2/` and `/home/shared/` are co-tenant resources, and this project must not depend on or pollute them.

---

## 1. Hard constraints

All five hold simultaneously. None is negotiable without a written exception per [docs/runtime_policy.md](runtime_policy.md) §9.

1. **All project-related data lives under `/home/cap2/`.**
   No directory the project creates, writes to, or relies on may be located outside `/home/cap2/`.
2. **The workspace is self-contained.**
   Everything the project owns is reachable from `/home/cap2/last/` — either directly as a child path or via a symlink the project itself created.
3. **Caches are project-isolated.**
   The project does not write to caches that are shared with other users, other projects, or other Claude/agent identities on this host. Each cache the project uses has a path that contains the segment `last/cache/`.
4. **Paths are deterministic.**
   Every cache, model, dataset, log, and output directory has a single, documented absolute path. No "wherever the tool defaults to" — defaults are explicitly overridden per §5.
5. **No dependence on `/home2/`.**
   `/home2/` is a co-tenant filesystem. The project must run end-to-end with `/home2/` unmounted. Scripts, configs, env vars, and docs must not reference `/home2/` paths.

### What this rules out

- Writing to `~/.cache/huggingface`, `~/.cache/pip`, `~/.cache/ov`, `~/.cache/torch`, `~/.cache/warp`, `~/.cache/matplotlib` (these are global-user caches shared with every tool the `cap2` account runs).
- Writing to `/home/shared/.cache/huggingface` or `/home/shared/.cache/pip` (these are group-shared with other users).
- Writing to `$HOME/omni.replicator_out` (Isaac Sim Replicator default).
- Writing to `~/miniconda3/pkgs` for project-driven installs (shared with every conda env on the host).
- Writing to `~/IsaacLab/logs` (default location chosen by the IsaacLab repo, not by this project).
- Any path under `/home2/`.

The fact that the policy *contradicts* these tools' defaults is the point. Defaults are overridden per §5.

---

## 2. Canonical cache root (accepted 2026-05-18)

```
/home/cap2/last/
├── cache/                       ← 13th canonical directory (accepted)
│   ├── huggingface/             ← HF_HOME target
│   │   └── hub/, datasets/, lerobot/, ...
│   ├── pip/                     ← PIP_CACHE_DIR target
│   ├── conda/
│   │   └── pkgs/                ← conda pkgs_dirs target
│   ├── torch/                   ← TORCH_HOME target
│   ├── omniverse/               ← ~/.cache/ov target (symlink source, one-time migration deferred)
│   ├── omniverse-data/          ← ~/.local/share/ov/data target (symlink source, deferred)
│   ├── omniverse-logs/          ← ~/.nvidia-omniverse/logs target (symlink source, deferred)
│   ├── nvidia-shader/           ← __GL_SHADER_DISK_CACHE_PATH + CUDA_CACHE_PATH target
│   ├── warp/                    ← WARP_CACHE_PATH target
│   ├── matplotlib/              ← MPLCONFIGDIR target
│   └── isaac-kit/               ← /home/cap2/isaac-sim-5.0.0/kit/cache target (symlink source, deferred)
│
├── docs/, isaac_factory/, ros2_ws/, orchestration/, scripts/, assets/,
│   configs/, tests/, logs/, datasets/, outputs/, tools/   ← existing 12 dirs
```

`last/cache/` is the **13th canonical workspace directory** (accepted 2026-05-18). [docs/runtime_policy.md](runtime_policy.md) §1.1 has been updated to list it. The env-var contract that targets these subdirs (§5) is now wired into [scripts/activate_factory_env.sh](../scripts/activate_factory_env.sh).

### Why one root and not per-component

A single `cache/` root means:

- A single line of `.gitignore` excludes all caches (`cache/`).
- A single `du -sh last/cache/` answers "how much disk are project caches using?".
- A single `rm -rf last/cache/` is the nuclear reset — and is safe because everything in it is regenerable.
- Backups can exclude one path instead of enumerating eight.

---

## 3. Data class → location map

Every kind of project data has exactly one home. No exceptions for "just this once".

| Data class | Canonical path under `last/` | Notes |
|---|---|---|
| Source code (Python, ROS pkgs, Kit extensions) | `isaac_factory/`, `ros2_ws/src/`, `orchestration/`, `tools/`, `scripts/` | code only |
| Shell launchers, doctor scripts | `scripts/` | per [docs/runtime_validation.md](runtime_validation.md) |
| Configuration (YAML/TOML/JSON, hydra configs) | `configs/` | env-agnostic |
| Static input data (USDs, materials, textures) | `assets/` | versioned; may include large binaries |
| Input datasets (HDF5, parquet, CSVs, lerobot datasets) | `datasets/` | gitignored |
| Generated artifacts (renders, USDs from runs, JSON metrics) | `outputs/` | gitignored; per-run subdirs |
| Runtime logs (rclpy, training, Isaac Sim sessions) | `logs/` | gitignored; rotated externally |
| Regression / KPI / doctor results | `tests/` (code), `outputs/test-runs/` (artifacts) | |
| Tests fixtures, mock data | `tests/fixtures/` | |
| Model weights downloaded from HF Hub | `cache/huggingface/hub/...` | via `HF_HOME` |
| Pre-trained model checkpoints **the project produces** | `outputs/checkpoints/` | distinguish from cached HF weights |
| RL training logs, tensorboard events | `logs/<algo>/<run-id>/` | redirect from IsaacLab defaults |
| Replicator outputs | `outputs/replicator/<run-id>/` | redirect from `$HOME/omni.replicator_out` |
| Pip wheels | `cache/pip/` | via `PIP_CACHE_DIR` |
| Conda package cache | `cache/conda/pkgs/` | via `~/.condarc` `pkgs_dirs` (project-scoped condarc) |
| Torch hub, torchvision weights | `cache/torch/` | via `TORCH_HOME` |
| Omniverse texture / shader / client / generic cache | `cache/omniverse/` | symlinked from `~/.cache/ov` |
| Omniverse Kit user data | `cache/omniverse-data/` | symlinked from `~/.local/share/ov/data` |
| Omniverse Kit logs | `cache/omniverse-logs/` | symlinked from `~/.nvidia-omniverse/logs` |
| Isaac Sim 5.0 launcher cache | `cache/isaac-kit/` | symlinked from `isaac-sim-5.0.0/kit/cache` |
| NVIDIA driver shader cache (OpenGL/Vulkan/CUDA) | `cache/nvidia-shader/` | via `__GL_SHADER_DISK_CACHE_PATH`, `CUDA_CACHE_PATH` |
| NVIDIA Warp kernel cache | `cache/warp/` | via `WARP_CACHE_PATH` (Warp ≥1.2) |
| Matplotlib font/cache | `cache/matplotlib/` | via `MPLCONFIGDIR` |

---

## 4. Forbidden write targets

The project must never write to any path matching:

- `/home2/**`
- `/home/shared/**`
- `/home/cap2/.cache/**`           ← global per-user cache (shared with every tool `cap2` runs)
- `/home/cap2/.local/share/ov/**`  ← global Omniverse user data
- `/home/cap2/.nv/**`              ← global NVIDIA driver caches
- `/home/cap2/.nvidia-omniverse/**` ← global Omniverse logs
- `$HOME/omni.replicator_out/**`   ← Isaac Sim Replicator default output
- `/home/cap2/miniconda3/**`       ← shared with every conda env (read-only for project)
- `/home/cap2/IsaacLab/logs/**`    ← shared with IsaacLab repo's own use
- `/home/cap2/factory/**`          ← reference-only sibling project
- `/home/cap2/IsaacSim-ros_workspaces/**` ← reference
- `/home/cap2/auto-assembly-sim/**`, `peg_in_hole_2026/**`, `unitree_sim_isaaclab/**`, `mrs/**`, `lee/**` ← reference

If a tool insists on writing to one of these locations, the resolution is one of:

1. **Override its config** to write under `last/cache/` instead (preferred).
2. **Symlink** the global location → `last/cache/<component>/` so the bytes physically live in the workspace.
3. If neither is possible, the tool is not policy-compatible and cannot be used.

---

## 5. Per-profile environment variable contract

Each runtime profile (per [docs/runtime_policy.md](runtime_policy.md) §4) exports these vars during activation. This is the mechanism by which §3 and §4 are enforced.

### 5.1 `research` profile

```bash
# §3 redirections
export HF_HOME="${WORKSPACE_ROOT}/cache/huggingface"
export PIP_CACHE_DIR="${WORKSPACE_ROOT}/cache/pip"
export TORCH_HOME="${WORKSPACE_ROOT}/cache/torch"
export WARP_CACHE_PATH="${WORKSPACE_ROOT}/cache/warp"
export MPLCONFIGDIR="${WORKSPACE_ROOT}/cache/matplotlib"
export __GL_SHADER_DISK_CACHE_PATH="${WORKSPACE_ROOT}/cache/nvidia-shader"
export CUDA_CACHE_PATH="${WORKSPACE_ROOT}/cache/nvidia-shader"
# Conda pkgs_dirs is set via a project-scoped condarc (§7), not env var.
```

### 5.2 `isaac` profile

```bash
# §3 redirections
export __GL_SHADER_DISK_CACHE_PATH="${WORKSPACE_ROOT}/cache/nvidia-shader"
export CUDA_CACHE_PATH="${WORKSPACE_ROOT}/cache/nvidia-shader"
# Omniverse cache (~/.cache/ov), user data (~/.local/share/ov/data), and
# Kit logs (~/.nvidia-omniverse/logs) are redirected via symlink (§7), not env var,
# because no documented Kit setting cleanly overrides them per-launch.
# Replicator output paths are set explicitly in each script's writer config.
```

### 5.3 `ros` profile

```bash
# §3 redirections
export PIP_CACHE_DIR="${WORKSPACE_ROOT}/cache/pip"   # if installing Python deps for ROS-side tools
# No HF/torch/CUDA cache vars here — ROS-side code does not download models or compile CUDA.
```

The dispatcher [scripts/activate_factory_env.sh](../scripts/activate_factory_env.sh) **exports these vars per profile as of 2026-05-18** (audit remediation pass). Symlink-style redirections for caches that cannot be env-overridden (§6) remain deferred.

---

## 6. Symlink contract

For caches that cannot be redirected via env var (Omniverse `~/.cache/ov`, `~/.local/share/ov/data`, `~/.nvidia-omniverse/logs`, and the Isaac Sim install's own `kit/cache`), the workspace owns the bytes and the global location is a **symlink into the workspace**:

| Global path (symlink, becomes) | Target (real bytes) |
|---|---|
| `~/.cache/ov` → | `/home/cap2/last/cache/omniverse` |
| `~/.local/share/ov/data` → | `/home/cap2/last/cache/omniverse-data` |
| `~/.nvidia-omniverse/logs` → | `/home/cap2/last/cache/omniverse-logs` |
| `/home/cap2/isaac-sim-5.0.0/kit/cache` → | `/home/cap2/last/cache/isaac-kit` |

This satisfies §1 constraint #2 (self-contained workspace) because every byte the project causes to be written reaches disk inside `last/`, even when the tool insists on writing to its own conventional path.

**Symlink direction matters**: the *global* path is the symlink, the *workspace* path is the real directory. Reversing this (workspace path = symlink → global path) would violate self-containment.

---

## 7. Conda pkgs_dirs

`/home/cap2/miniconda3/pkgs/` is shared across every conda env on the host. To redirect project-driven installs to the workspace:

1. Create `${WORKSPACE_ROOT}/configs/condarc.yaml`:
   ```yaml
   pkgs_dirs:
     - /home/cap2/last/cache/conda/pkgs
     - /home/cap2/miniconda3/pkgs   # read-only fallback for already-cached packages
   ```
2. Export `CONDARC=${WORKSPACE_ROOT}/configs/condarc.yaml` in the `research` profile **before** `conda activate`.

The fallback is intentional: existing packages already cached in `miniconda3/pkgs/` remain readable. New downloads driven by this project's `pip install` / `conda install` go to the workspace.

---

## 8. Implementation plan (deferred — no files moved yet)

This policy describes the **target state**. Reaching it is a separate, user-approved change. The mechanical steps would be, in order:

1. `mkdir -p last/cache/{huggingface,pip,conda/pkgs,torch,omniverse,omniverse-data,omniverse-logs,nvidia-shader,warp,matplotlib,isaac-kit}` (creates only; ~50 ms).
2. Add `cache/` to `.gitignore`.
3. Update [docs/runtime_policy.md](runtime_policy.md) §1.1 to list `cache/` as the 13th canonical directory.
4. Update [scripts/activate_factory_env.sh](../scripts/activate_factory_env.sh) to export the env vars from §5 per profile.
5. (Optional, one-time data migration — requires user confirmation per item):
   - For `~/.cache/ov` (16 G): `mv` to `last/cache/omniverse/`, then `ln -s last/cache/omniverse ~/.cache/ov`.
   - For `~/.local/share/ov/data` (1.1 G): same pattern.
   - For `~/.nvidia-omniverse/logs` (214 M): same pattern.
   - For `isaac-sim-5.0.0/kit/cache` (2.3 G): `mv` + symlink, then run `validate_runtime.sh --deep` to confirm Kit still boots.
6. Update [scripts/validate_runtime.sh](../scripts/validate_runtime.sh) to assert each cache target exists and that no project process is writing outside `last/`.

**None of this is done in this turn.** The policy is the contract; the implementation is the next conversation.

---

## 9. Trade-offs (acknowledged, accepted)

This policy intentionally accepts costs that the previous [docs/storage_audit.md](storage_audit.md) recommendation would have avoided.

| Trade-off | Cost | Why accepted |
|---|---|---|
| All project data on `/` (88 % full) | Less headroom; faster path to disk-full | `/home2/` is co-tenant resource; project portability and tenant isolation outweigh free-space relief |
| HF model weights re-downloaded into `last/cache/huggingface` | Bytes duplicated vs `/home/shared/.cache/huggingface` (101 G); first-use download latency for each model | Project gets a known set of model versions, isolated from other users' churn |
| Omniverse cache moved out of `~/.cache/ov` | First-run textures recompile until cache repopulates | Symlink preserves cache after first session; one-time hit |
| Conda pkgs split across two dirs | Slightly more disk; conda must check two paths | Fallback to `miniconda3/pkgs` makes the transition zero-cost for already-cached pkgs |
| Larger `cache/` makes `last/` larger overall | A clone or backup of `last/` includes caches unless excluded | One `.gitignore` line, one rsync `--exclude=cache/` |

**Disk-pressure mitigation** is now done *within* `/home/cap2/`:

- Delete duplicate `cuda-repo-…amd64.deb.1` (reclaims 3.9 G).
- `conda clean -a` on `miniconda3/pkgs/` (reclaims up to 5.9 G).
- Delete empty `isaacsim_old/` shell.
- Audit and prune `IsaacLab/logs/rl_games/` (88 G, untouched since 2026-03-26) — owned by the IsaacLab repo, not this project, so the decision is the user's; this project will not write there going forward.
- Audit and prune `factory/out/` (1.2 G generated, not a project dep).
- Each of these is a separate user-approved action, not done in this audit.

---

## 10. Relation to other documents

| Document | Role | Relationship to this policy |
|---|---|---|
| [docs/runtime_policy.md](runtime_policy.md) | Authoritative runtime stack and activation rules | This policy adds the storage-side env-var contract (§5) and proposes a 13th canonical dir for §1.1 |
| [docs/runtime_validation.md](runtime_validation.md) | Doctor script doc | Validator will be extended (deferred) to assert §4 forbidden-write avoidance and §6 symlink directions |
| [docs/storage_audit.md](storage_audit.md) | One-shot inventory snapshot | The audit's findings remain valid; the audit's **recommendations** (relocate to `/home2`) are **superseded** by this policy |
| [scripts/activate_factory_env.sh](../scripts/activate_factory_env.sh) | Profile dispatcher | Will be updated (deferred) to export §5 vars per profile |
| [scripts/validate_runtime.sh](../scripts/validate_runtime.sh) | Read-only doctor | Will be extended (deferred) to validate this policy |

---

## 11. Open questions (for the next conversation)

- **Accept `cache/` as the 13th canonical workspace dir?** Or use a different name (e.g., `var/`, `state/`)?
- **`IsaacLab/logs/rl_games` (88 G, stale 2 months):** owned by the IsaacLab tree, not this project. Delete, archive, or leave alone? Either way, this project will redirect its own future training logs into `last/logs/` instead.
- **HF Hub model migration policy:** when this project needs a model that already exists in `/home/shared/.cache/huggingface/`, do we (a) re-download into `last/cache/huggingface`, accepting bytes duplication, (b) copy from shared, (c) hardlink? §1 says no dependence on shared — (a) is the safest answer.
- **`HF_HOME` is currently set in the user's login shell.** Does the user want it removed from `~/.bashrc` (which would affect every shell on this account), or just shadowed in the `research` profile (which leaves other tools using the old path)?
- **Backup strategy:** with caches inside the workspace, backup tools need a clear exclude. Add `cache/` to `.gitignore` and to any rsync/backup wrapper as a single exclusion?
- **Disk-pressure remediation order:** which of §9's reclaim items does the user want done first?

These are policy questions for the user, not implementation work. None is decided here.
