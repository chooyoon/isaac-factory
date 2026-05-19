# scripts/activate_factory_env.sh
#
# Deterministic activator for the industrial digital twin runtimes.
# This script must be SOURCED, not executed. Sourcing it activates exactly one
# of the three runtime profiles defined in docs/runtime_policy.md §4:
#
#   research  Profile A — conda env_isaaclab (Python 3.10) + CUDA 12.8 + IsaacLab
#   isaac     Profile B — Isaac Sim 5.0 Kit Python (3.11); optional ROS 2 bridge
#   ros       Profile C — ROS 2 Jazzy (system Python 3.12) + overlay
#
# RULE: one runtime profile per shell. The three runtimes —
#   ROS 2 Jazzy, Isaac Sim Kit Python, conda env_isaaclab (IsaacLab) —
# must NEVER be combined in the same shell. Cross-runtime communication is
# via ROS 2 topics/services or external IPC (files, sockets, ROS bag), never
# via shared Python imports.
#
# Usage:
#   source scripts/activate_factory_env.sh <research|isaac|ros>
#
# Optional env vars:
#   FACTORY_WITH_BRIDGE=1   (isaac profile only) — load isaacsim.ros2.bridge/jazzy lib
#
# Policy: docs/runtime_policy.md is authoritative. This script implements §4 and
# enforces §5 (PYTHONPATH), §6 (USD), and §7 (prohibited mixing). It refuses to
# proceed if required paths are missing, and prints an active-runtime summary
# on success.

# ---------------------------------------------------------------------------
# Guard: must be sourced, not executed
# ---------------------------------------------------------------------------
(return 0 2>/dev/null) || {
  printf '[activate_factory_env] ERROR: script must be sourced, not executed.\n' >&2
  printf '[activate_factory_env]   use: source scripts/activate_factory_env.sh <research|isaac|ros>\n' >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Helpers (namespaced; cleaned up at end)
# ---------------------------------------------------------------------------
_fae_log()  { printf '[activate_factory_env] %s\n' "$*"; }
_fae_err()  { printf '[activate_factory_env] ERROR: %s\n' "$*" >&2; }

_fae_usage() {
  cat >&2 <<'EOF'
usage: source scripts/activate_factory_env.sh <profile>

profiles:
  research  Profile A — conda env_isaaclab (Python 3.10) + CUDA + IsaacLab
  isaac     Profile B — Isaac Sim 5.0 Kit Python (3.11)
            set FACTORY_WITH_BRIDGE=1 to also load the bundled ROS 2 bridge libs
  ros       Profile C — ROS 2 Jazzy (system Python 3.12) + ros2_ws overlay if built

Rule: one profile per shell. To switch, open a new shell and re-source.
Cross-runtime communication: ROS 2 topics/services or external IPC only —
never shared Python imports.

See docs/runtime_policy.md §4 for the full activation order and §7 for the
prohibited-mixing rules this script enforces.
EOF
}

# ---------------------------------------------------------------------------
# Canonical constants (mirror docs/runtime_policy.md §1)
# ---------------------------------------------------------------------------
_FAE_WORKSPACE_ROOT="/home/cap2/last"
_FAE_ISAAC_PATH="/home/cap2/isaac-sim-5.0.0"
_FAE_CONDA_ROOT="/home/cap2/miniconda3"
_FAE_CONDA_ENV="env_isaaclab"
_FAE_ROS_SETUP="/opt/ros/jazzy/setup.bash"
_FAE_CUDA_ROOT="/usr/local/cuda"
_FAE_POLICY_DOC="$_FAE_WORKSPACE_ROOT/docs/runtime_policy.md"

# ---------------------------------------------------------------------------
# Step 1: validate the argument BEFORE touching the environment
# ---------------------------------------------------------------------------
if [ $# -eq 0 ]; then _fae_usage; return 2 2>/dev/null || return; fi

_FAE_PROFILE="$1"
case "$_FAE_PROFILE" in
  research|isaac|ros) ;;
  -h|--help)          _fae_usage; return 0 ;;
  *)
    _fae_err "unknown profile: $_FAE_PROFILE"
    _fae_usage
    return 2
    ;;
esac

# ---------------------------------------------------------------------------
# Step 2: validate required paths for the requested profile
# (still no env mutation — bail clean if anything is missing)
# ---------------------------------------------------------------------------
_FAE_REQUIRED=()
case "$_FAE_PROFILE" in
  research)
    _FAE_REQUIRED=(
      "$_FAE_WORKSPACE_ROOT"
      "$_FAE_CONDA_ROOT/etc/profile.d/conda.sh"
      "$_FAE_CONDA_ROOT/envs/$_FAE_CONDA_ENV"
      "$_FAE_CUDA_ROOT"
    )
    ;;
  isaac)
    _FAE_REQUIRED=(
      "$_FAE_WORKSPACE_ROOT"
      "$_FAE_ISAAC_PATH"
      "$_FAE_ISAAC_PATH/python.sh"
      "$_FAE_ISAAC_PATH/isaac-sim.sh"
      "$_FAE_ISAAC_PATH/kit/python/bin/python3"
    )
    ;;
  ros)
    _FAE_REQUIRED=(
      "$_FAE_WORKSPACE_ROOT"
      "$_FAE_ROS_SETUP"
    )
    ;;
esac

_FAE_MISS=0
for _p in "${_FAE_REQUIRED[@]}"; do
  if [ ! -e "$_p" ]; then
    _fae_err "missing required path: $_p"
    _FAE_MISS=1
  fi
done
if [ "$_FAE_MISS" -eq 1 ]; then
  _fae_err "validation failed — refusing to activate '$_FAE_PROFILE'"
  unset _FAE_WORKSPACE_ROOT _FAE_ISAAC_PATH _FAE_CONDA_ROOT _FAE_CONDA_ENV \
        _FAE_ROS_SETUP _FAE_CUDA_ROOT _FAE_POLICY_DOC \
        _FAE_PROFILE _FAE_REQUIRED _FAE_MISS _p
  unset -f _fae_log _fae_err _fae_usage
  return 1
fi

# ---------------------------------------------------------------------------
# Step 3: contamination check + scrub (runtime isolation)
# Open-shell policy: docs/runtime_policy.md says SWITCH profiles by opening a
# new shell. We still scrub so a freshly opened shell (which inherits ROS env
# from the user's login) starts clean.
# ---------------------------------------------------------------------------
if [ -n "${CONDA_DEFAULT_ENV:-}" ] && [ "${CONDA_DEFAULT_ENV}" != "base" ]; then
  _fae_log "warn: conda env already active ($CONDA_DEFAULT_ENV) — open a new shell to switch cleanly"
fi
if [ -n "${AMENT_PREFIX_PATH:-}" ] && [ "$_FAE_PROFILE" != "ros" ]; then
  _fae_log "warn: ROS already sourced (AMENT_PREFIX_PATH set) — open a new shell to switch cleanly"
fi

# scrub inherited contamination
unset PYTHONPATH
unset ISAAC_ROS_WS                 # P10: stale env var, points to nonexistent path
unset LD_LIBRARY_PATH              # each profile rebuilds this from scratch

# fully deactivate any conda stack (only if conda is reachable)
if command -v conda >/dev/null 2>&1; then
  while [ "${CONDA_SHLVL:-0}" -gt 0 ]; do
    conda deactivate >/dev/null 2>&1 || break
  done
fi

# ---------------------------------------------------------------------------
# Step 4: activate the requested profile
# ---------------------------------------------------------------------------
_FAE_BRIDGE_STATUS=""
_FAE_OVERLAY_STATUS=""

case "$_FAE_PROFILE" in
  # -----------------------------------------------------------------------
  # Profile A — Research (conda env_isaaclab + CUDA + IsaacLab)
  # -----------------------------------------------------------------------
  research)
    # shellcheck source=/dev/null
    source "$_FAE_CONDA_ROOT/etc/profile.d/conda.sh"
    conda activate "$_FAE_CONDA_ENV" || { _fae_err "conda activate failed"; return 1; }

    export WORKSPACE_ROOT="$_FAE_WORKSPACE_ROOT"
    cd "$WORKSPACE_ROOT" || { _fae_err "cannot cd $WORKSPACE_ROOT"; return 1; }

    # CUDA only in Profile A (policy §1 + §4)
    export PATH="$_FAE_CUDA_ROOT/bin:$PATH"
    export LD_LIBRARY_PATH="$_FAE_CUDA_ROOT/lib64"

    # Storage policy §5.1 — project-isolated caches under last/cache/.
    # Every workspace-internal cache target must contain the segment
    # `last/cache/`; this is what makes the workspace self-contained.
    export HF_HOME="$WORKSPACE_ROOT/cache/huggingface"
    export PIP_CACHE_DIR="$WORKSPACE_ROOT/cache/pip"
    export TORCH_HOME="$WORKSPACE_ROOT/cache/torch"
    export WARP_CACHE_PATH="$WORKSPACE_ROOT/cache/warp"
    export MPLCONFIGDIR="$WORKSPACE_ROOT/cache/matplotlib"
    export __GL_SHADER_DISK_CACHE_PATH="$WORKSPACE_ROOT/cache/nvidia-shader"
    export CUDA_CACHE_PATH="$WORKSPACE_ROOT/cache/nvidia-shader"
    if [ -f "$WORKSPACE_ROOT/configs/condarc.yaml" ]; then
      export CONDARC="$WORKSPACE_ROOT/configs/condarc.yaml"
    fi

    # PYTHONPATH policy §5: empty or workspace's orchestration only
    # (orchestration/ may be empty during Phase 0 — Python tolerates this).
    export PYTHONPATH="$WORKSPACE_ROOT/orchestration"

    _FAE_PYTHON_BIN="$(command -v python)"
    _FAE_PY_VER="$("$_FAE_PYTHON_BIN" --version 2>&1)"
    _FAE_RT_LABEL="A — research (conda env_isaaclab + IsaacLab)"
    ;;

  # -----------------------------------------------------------------------
  # Profile B — Isaac Sim
  # -----------------------------------------------------------------------
  isaac)
    export WORKSPACE_ROOT="$_FAE_WORKSPACE_ROOT"
    export ISAAC_PATH="$_FAE_ISAAC_PATH"
    cd "$WORKSPACE_ROOT" || { _fae_err "cannot cd $WORKSPACE_ROOT"; return 1; }

    # Storage policy §5.2 — NVIDIA shader caches into the workspace.
    # Omniverse caches (~/.cache/ov, ~/.local/share/ov/data, ~/.nvidia-omniverse/logs)
    # and isaac-sim-5.0.0/kit/cache are redirected via SYMLINK (§6 of storage_policy);
    # one-time migration of those is deferred.
    export __GL_SHADER_DISK_CACHE_PATH="$WORKSPACE_ROOT/cache/nvidia-shader"
    export CUDA_CACHE_PATH="$WORKSPACE_ROOT/cache/nvidia-shader"

    # PYTHONPATH policy §5/§6: Kit Python resolves its own pxr/omni from
    # extscache — do NOT prepend anything here. Leave PYTHONPATH unset.

    # ROS 2 bridge libs are opt-in. The bundled bridge is the ONLY allowed
    # way to combine Isaac Sim and ROS 2 in one process (see §2 transports
    # B → C and §7 P7).
    if [ "${FACTORY_WITH_BRIDGE:-0}" = "1" ]; then
      _FAE_BRIDGE="$ISAAC_PATH/exts/isaacsim.ros2.bridge/jazzy/lib"
      if [ -d "$_FAE_BRIDGE" ]; then
        export LD_LIBRARY_PATH="$_FAE_BRIDGE"
        _FAE_BRIDGE_STATUS="loaded ($_FAE_BRIDGE)"
      else
        _fae_log "warn: bridge dir not found, continuing without it: $_FAE_BRIDGE"
        _FAE_BRIDGE_STATUS="missing"
      fi
      unset _FAE_BRIDGE
    else
      _FAE_BRIDGE_STATUS="not loaded (set FACTORY_WITH_BRIDGE=1 to enable)"
    fi

    _FAE_PYTHON_BIN="$_FAE_ISAAC_PATH/kit/python/bin/python3"
    _FAE_PY_VER="$("$_FAE_PYTHON_BIN" --version 2>&1)"
    _FAE_RT_LABEL="B — Isaac Sim 5.0 Kit Python"
    ;;

  # -----------------------------------------------------------------------
  # Profile C — ROS 2 Jazzy
  # -----------------------------------------------------------------------
  ros)
    # shellcheck source=/dev/null
    source "$_FAE_ROS_SETUP"

    export WORKSPACE_ROOT="$_FAE_WORKSPACE_ROOT"
    cd "$WORKSPACE_ROOT" || { _fae_err "cannot cd $WORKSPACE_ROOT"; return 1; }

    # Overlay AFTER base setup (policy §4)
    if [ -f "$WORKSPACE_ROOT/ros2_ws/install/setup.bash" ]; then
      # shellcheck source=/dev/null
      source "$WORKSPACE_ROOT/ros2_ws/install/setup.bash"
      _FAE_OVERLAY_STATUS="loaded"
    else
      _FAE_OVERLAY_STATUS="not built (ros2_ws/install/ absent)"
    fi

    export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
    export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET

    # Storage policy §5.3 — pip cache for ROS-side Python tools only
    # (no HF / torch / CUDA caches; ROS code does not need them).
    export PIP_CACHE_DIR="$WORKSPACE_ROOT/cache/pip"

    _FAE_PYTHON_BIN="$(command -v python3)"
    _FAE_PY_VER="$("$_FAE_PYTHON_BIN" --version 2>&1)"
    _FAE_RT_LABEL="C — ROS 2 Jazzy (system Python)"
    ;;
esac

# ---------------------------------------------------------------------------
# Step 5: active runtime summary
# ---------------------------------------------------------------------------
printf '\n=========== Factory Runtime Summary ===========\n'
printf 'Active runtime : %s\n' "$_FAE_RT_LABEL"
printf 'Profile        : %s\n' "$_FAE_PROFILE"
printf 'Python         : %s  (%s)\n' "$_FAE_PY_VER" "$_FAE_PYTHON_BIN"
printf 'Workspace      : %s\n' "$WORKSPACE_ROOT"

case "$_FAE_PROFILE" in
  research)
    printf 'Conda env      : %s\n' "${CONDA_DEFAULT_ENV:-?}"
    printf 'CUDA           : %s\n' "$_FAE_CUDA_ROOT"
    printf 'PYTHONPATH     : %s\n' "${PYTHONPATH:-(empty)}"
    printf 'PIP_CACHE_DIR  : %s\n' "${PIP_CACHE_DIR:-(default)}"
    ;;
  isaac)
    printf 'ISAAC_PATH     : %s\n' "$ISAAC_PATH"
    printf 'Launchers      : $ISAAC_PATH/python.sh | $ISAAC_PATH/isaac-sim.sh\n'
    printf 'ROS 2 bridge   : %s\n' "$_FAE_BRIDGE_STATUS"
    printf 'PYTHONPATH     : %s\n' "${PYTHONPATH:-(empty)}"
    ;;
  ros)
    printf 'ROS_DISTRO     : %s\n' "${ROS_DISTRO:-?}"
    printf 'RMW            : %s\n' "${RMW_IMPLEMENTATION:-?}"
    printf 'Discovery      : %s\n' "${ROS_AUTOMATIC_DISCOVERY_RANGE:-?}"
    printf 'Overlay        : %s\n' "$_FAE_OVERLAY_STATUS"
    printf 'PYTHONPATH     : %s\n' "${PYTHONPATH:-(empty)}"
    ;;
esac

printf '===============================================\n'
printf 'Policy reference: %s\n' "$_FAE_POLICY_DOC"
printf 'To switch profile: open a new shell and re-source this script.\n\n'

# ---------------------------------------------------------------------------
# Step 6: clean up script-local symbols (do not leak into the user shell)
# ---------------------------------------------------------------------------
unset _FAE_WORKSPACE_ROOT _FAE_ISAAC_PATH _FAE_CONDA_ROOT _FAE_CONDA_ENV \
      _FAE_ROS_SETUP _FAE_CUDA_ROOT _FAE_POLICY_DOC \
      _FAE_PROFILE _FAE_REQUIRED _FAE_MISS \
      _FAE_PYTHON_BIN _FAE_PY_VER _FAE_RT_LABEL \
      _FAE_BRIDGE_STATUS _FAE_OVERLAY_STATUS _p
unset -f _fae_log _fae_err _fae_usage

return 0
