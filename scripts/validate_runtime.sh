#!/usr/bin/env bash
# scripts/validate_runtime.sh
#
# Read-only doctor for the industrial digital twin runtime.
#
# Usage:
#   bash scripts/validate_runtime.sh            # standard checks
#   bash scripts/validate_runtime.sh --deep     # also run Kit Python pxr/omni import (slow, ~30s)
#
# Detects the active runtime profile (research|isaac|ros|none|contaminated),
# runs the relevant checks, and prints a human-readable report ending in
# PASS / WARN / FAIL sections.
#
# Read-only: no environment variable is exported, no file is written,
# no daemon is started. Subprocesses are used only to probe interpreter
# health and never inherit a mutated env.
#
# Exit codes:
#   0 — no FAILs (WARNs allowed)
#   1 — at least one FAIL
#   2 — bad argument

set -u   # no env mutation; this affects only this script's own subshell

# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────
DEEP=0
for arg in "$@"; do
  case "$arg" in
    --deep)        DEEP=1 ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *) printf 'unknown arg: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Canonical constants (mirror docs/runtime_policy.md §1)
# ─────────────────────────────────────────────────────────────────────────────
WS_ROOT="/home/cap2/last"
ISAAC_DIR="/home/cap2/isaac-sim-5.0.0"
CONDA_ROOT="/home/cap2/miniconda3"
CONDA_ENV_NAME="env_isaaclab"
CONDA_ENV_DIR="$CONDA_ROOT/envs/$CONDA_ENV_NAME"
CONDA_ENV_PY="$CONDA_ENV_DIR/bin/python"
ROS_SETUP="/opt/ros/jazzy/setup.bash"
ROS_DISTRO_EXPECTED="jazzy"
CUDA_ROOT="/usr/local/cuda"
KIT_PY="$ISAAC_DIR/kit/python/bin/python3"
KIT_LAUNCHER="$ISAAC_DIR/python.sh"
USD_LIBS_GLOB="$ISAAC_DIR/extscache/omni.usd.libs-*"

# ─────────────────────────────────────────────────────────────────────────────
# Result accumulators + emitters
# ─────────────────────────────────────────────────────────────────────────────
PASS_LIST=()
WARN_LIST=()
FAIL_LIST=()

# Bold / colour if stdout is a TTY
if [ -t 1 ]; then
  C_BOLD=$'\e[1m'; C_OFF=$'\e[0m'
  C_PASS=$'\e[32m'; C_WARN=$'\e[33m'; C_FAIL=$'\e[31m'; C_DIM=$'\e[2m'
else
  C_BOLD=''; C_OFF=''; C_PASS=''; C_WARN=''; C_FAIL=''; C_DIM=''
fi

emit_pass() { printf '  %s[PASS]%s %s\n' "$C_PASS" "$C_OFF" "$1"; PASS_LIST+=("$1"); }
emit_warn() { printf '  %s[WARN]%s %s\n' "$C_WARN" "$C_OFF" "$1"; WARN_LIST+=("$1"); }
emit_fail() { printf '  %s[FAIL]%s %s\n' "$C_FAIL" "$C_OFF" "$1"; FAIL_LIST+=("$1"); }
emit_info() { printf '  %s%s%s\n' "$C_DIM" "$1" "$C_OFF"; }

section() { printf '\n%s── %s ──%s\n' "$C_BOLD" "$1" "$C_OFF"; }

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
printf '%sFactory Runtime Validation%s\n' "$C_BOLD" "$C_OFF"
printf 'host: %s\n' "$(hostname)"
printf 'time: %s\n' "$(date -Iseconds)"
printf 'mode: %s\n' "$( [ "$DEEP" -eq 1 ] && echo 'deep (includes Kit Python pxr import)' || echo 'standard' )"
printf 'policy ref: %s/docs/runtime_policy.md\n' "$WS_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Profile detection
# ─────────────────────────────────────────────────────────────────────────────
section "Profile detection"

HAS_CONDA=0; HAS_ROS=0; HAS_ISAAC_VAR=0
[ "${CONDA_DEFAULT_ENV:-}" = "$CONDA_ENV_NAME" ] && HAS_CONDA=1
[ -n "${ROS_DISTRO:-}" ] && HAS_ROS=1
[ -n "${ISAAC_PATH:-}" ] && HAS_ISAAC_VAR=1

ACTIVE_COUNT=$(( HAS_CONDA + HAS_ROS + HAS_ISAAC_VAR ))

if [ "$ACTIVE_COUNT" -gt 1 ]; then
  PROFILE="contaminated"
  emit_fail "multiple runtime indicators active simultaneously (conda=$HAS_CONDA ros=$HAS_ROS isaac_var=$HAS_ISAAC_VAR) — violates policy §2 hard separation"
elif [ "$HAS_CONDA" = 1 ]; then
  PROFILE="research"
  emit_pass "active profile: research (conda $CONDA_ENV_NAME)"
elif [ "$HAS_ROS" = 1 ]; then
  PROFILE="ros"
  emit_pass "active profile: ros (ROS_DISTRO=${ROS_DISTRO:-?})"
elif [ "$HAS_ISAAC_VAR" = 1 ]; then
  PROFILE="isaac"
  emit_pass "active profile: isaac (ISAAC_PATH set)"
else
  PROFILE="none"
  emit_warn "no profile active — host-level checks will still run; per-profile checks will be skipped"
fi

emit_info "use scripts/activate_factory_env.sh <research|isaac|ros> to activate one"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Workspace
# ─────────────────────────────────────────────────────────────────────────────
section "Workspace"

if [ -d "$WS_ROOT" ]; then
  emit_pass "canonical workspace exists: $WS_ROOT"
else
  emit_fail "canonical workspace MISSING: $WS_ROOT"
fi

if [ "${WORKSPACE_ROOT:-}" = "$WS_ROOT" ]; then
  emit_pass "WORKSPACE_ROOT env var matches canonical path"
elif [ -z "${WORKSPACE_ROOT:-}" ]; then
  emit_warn "WORKSPACE_ROOT is unset (set by activate_factory_env.sh)"
else
  emit_fail "WORKSPACE_ROOT=${WORKSPACE_ROOT} does not match canonical $WS_ROOT"
fi

REQUIRED_DIRS=(docs isaac_factory ros2_ws orchestration scripts assets configs tests logs datasets outputs tools cache)
MISSING=()
for d in "${REQUIRED_DIRS[@]}"; do
  [ -d "$WS_ROOT/$d" ] || MISSING+=("$d")
done
if [ "${#MISSING[@]}" -eq 0 ]; then
  emit_pass "all 13 canonical directories present"
else
  emit_warn "missing canonical dirs: ${MISSING[*]}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3. GPU & NVIDIA driver
# ─────────────────────────────────────────────────────────────────────────────
section "GPU & NVIDIA driver"

if command -v nvidia-smi >/dev/null 2>&1; then
  if NVSMI_OUT=$(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>&1); then
    GPU_NAME=$(printf '%s\n' "$NVSMI_OUT" | head -1 | awk -F',' '{print $1}' | xargs)
    DRV_VER=$(printf '%s\n'  "$NVSMI_OUT" | head -1 | awk -F',' '{print $2}' | xargs)
    VRAM=$(printf '%s\n'     "$NVSMI_OUT" | head -1 | awk -F',' '{print $3}' | xargs)
    emit_pass "GPU detected: $GPU_NAME ($VRAM)"
    if printf '%s' "$GPU_NAME" | grep -qiE 'RTX|GeForce'; then
      emit_pass "RTX-class GPU confirmed"
    else
      emit_warn "GPU is not RTX-class: $GPU_NAME (Isaac Sim 5 expects RTX)"
    fi
    emit_pass "NVIDIA driver version: $DRV_VER"
  else
    emit_fail "nvidia-smi failed: $NVSMI_OUT"
  fi
else
  emit_fail "nvidia-smi not on PATH — driver not installed?"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 4. CUDA visibility
# ─────────────────────────────────────────────────────────────────────────────
section "CUDA"

if [ -d "$CUDA_ROOT" ]; then
  CUDA_REAL=$(readlink -f "$CUDA_ROOT")
  if [ -f "$CUDA_ROOT/version.json" ]; then
    CUDA_VER=$(grep -m1 '"version"' "$CUDA_ROOT/version.json" | awk -F'"' '{print $4}')
    emit_pass "CUDA toolkit $CUDA_VER at $CUDA_REAL"
  else
    emit_pass "CUDA toolkit at $CUDA_REAL (version.json missing)"
  fi
else
  emit_fail "CUDA toolkit missing: $CUDA_ROOT"
fi

if command -v nvcc >/dev/null 2>&1; then
  emit_pass "nvcc on PATH: $(command -v nvcc)"
else
  if [ "$PROFILE" = "research" ]; then
    emit_warn "nvcc not on PATH (research profile should export $CUDA_ROOT/bin)"
  else
    emit_info "nvcc not on PATH (expected outside research profile)"
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5. Isaac Sim install
# ─────────────────────────────────────────────────────────────────────────────
section "Isaac Sim 5.0 install"

if [ -d "$ISAAC_DIR" ]; then
  emit_pass "Isaac Sim directory present: $ISAAC_DIR"
  if [ -f "$ISAAC_DIR/VERSION" ]; then
    ISAAC_VER=$(head -1 "$ISAAC_DIR/VERSION")
    emit_pass "Isaac Sim version: $ISAAC_VER"
  else
    emit_warn "Isaac Sim VERSION file missing"
  fi
  for f in "$KIT_LAUNCHER" "$ISAAC_DIR/isaac-sim.sh" "$KIT_PY"; do
    if [ -e "$f" ]; then
      emit_pass "launcher present: ${f#$ISAAC_DIR/}"
    else
      emit_fail "launcher missing: $f"
    fi
  done
else
  emit_fail "Isaac Sim directory missing: $ISAAC_DIR"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 6. Extension paths
# ─────────────────────────────────────────────────────────────────────────────
section "Extension path validity"

for sub in exts extscache extsPhysics; do
  if [ -d "$ISAAC_DIR/$sub" ]; then
    COUNT=$(find "$ISAAC_DIR/$sub" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
      emit_pass "$sub/ has $COUNT extensions"
    else
      emit_warn "$sub/ exists but is empty"
    fi
  else
    emit_fail "$sub/ missing under $ISAAC_DIR"
  fi
done

# Specific sentinel extensions
for ext_check in \
    "isaacsim.core.api:$ISAAC_DIR/exts/isaacsim.core.api" \
    "omni.usd.libs (pxr host):$ISAAC_DIR/extscache" \
    "isaacsim.ros2.bridge/jazzy:$ISAAC_DIR/exts/isaacsim.ros2.bridge/jazzy" ; do
  name="${ext_check%%:*}"
  path="${ext_check#*:}"
  if compgen -G "$path"* >/dev/null 2>&1 || [ -e "$path" ]; then
    emit_pass "sentinel extension found: $name"
  else
    emit_warn "sentinel extension not found: $name (at $path)"
  fi
done

# pxr files inside the bundled USD libs extension (static check; no import)
BUNDLED_PXR=$(compgen -G "$USD_LIBS_GLOB/pxr/__init__.py" 2>/dev/null | head -1 || true)
if [ -n "$BUNDLED_PXR" ]; then
  emit_pass "bundled pxr package found: $BUNDLED_PXR"
else
  emit_fail "bundled pxr not found under $USD_LIBS_GLOB/pxr/"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 7. Python runtime (active interpreter)
# ─────────────────────────────────────────────────────────────────────────────
section "Active Python runtime"

case "$PROFILE" in
  research)
    if [ -x "$CONDA_ENV_PY" ]; then
      PY_BIN=$(command -v python || true)
      PY_VER=$("${PY_BIN:-/bin/false}" --version 2>&1 || echo "?")
      if [ "$PY_BIN" = "$CONDA_ENV_PY" ]; then
        emit_pass "python on PATH is $CONDA_ENV_NAME's: $PY_BIN ($PY_VER)"
      else
        emit_warn "python on PATH is $PY_BIN — expected $CONDA_ENV_PY"
      fi
      if [[ "$PY_VER" == *"3.10"* ]]; then
        emit_pass "Python version matches policy (3.10.x)"
      else
        emit_fail "Python version $PY_VER does not match policy 3.10.x"
      fi
    else
      emit_fail "conda env python missing: $CONDA_ENV_PY"
    fi
    ;;
  isaac)
    if [ -x "$KIT_PY" ]; then
      KIT_PY_VER=$("$KIT_PY" --version 2>&1 || echo "?")
      emit_pass "Kit Python: $KIT_PY ($KIT_PY_VER)"
      if [[ "$KIT_PY_VER" == *"3.11"* ]]; then
        emit_pass "Kit Python version matches policy (3.11.x)"
      else
        emit_fail "Kit Python $KIT_PY_VER does not match policy 3.11.x"
      fi
    else
      emit_fail "Kit Python missing: $KIT_PY"
    fi
    ;;
  ros)
    PY_BIN=$(command -v python3 || true)
    PY_VER=$("${PY_BIN:-/bin/false}" --version 2>&1 || echo "?")
    if [ "$PY_BIN" = "/usr/bin/python3" ]; then
      emit_pass "system python3: $PY_BIN ($PY_VER)"
    else
      emit_warn "python3 on PATH is $PY_BIN (expected /usr/bin/python3)"
    fi
    if [[ "$PY_VER" == *"3.12"* ]]; then
      emit_pass "Python version matches policy (3.12.x)"
    else
      emit_fail "Python version $PY_VER does not match policy 3.12.x"
    fi
    ;;
  *)
    emit_info "no profile active — skipping per-profile Python check"
    ;;
esac

# ─────────────────────────────────────────────────────────────────────────────
# 8. USD importability (usd-core in conda env — fast subprocess, never mutates env)
# ─────────────────────────────────────────────────────────────────────────────
section "USD importability (usd-core / Runtime A)"

if [ -x "$CONDA_ENV_PY" ]; then
  USD_OUT=$("$CONDA_ENV_PY" - <<'PY' 2>&1
try:
    from pxr import Usd
    print("OK", Usd.GetVersion())
    import pxr, sys
    print("PATH", pxr.__file__)
except Exception as e:
    print("ERR", type(e).__name__, e)
PY
  )
  if printf '%s' "$USD_OUT" | head -1 | grep -q '^OK'; then
    USD_VER=$(printf '%s\n' "$USD_OUT" | head -1 | cut -d' ' -f2-)
    USD_PATH=$(printf '%s\n' "$USD_OUT" | sed -n '2p' | cut -d' ' -f2-)
    emit_pass "usd-core imports cleanly in conda env: pxr version $USD_VER"
    case "$USD_PATH" in
      "$CONDA_ENV_DIR/"*) emit_pass "pxr loaded from expected conda location" ;;
      *)                  emit_warn "pxr loaded from unexpected path: $USD_PATH" ;;
    esac
  else
    emit_fail "usd-core import failed in conda env: $(printf '%s' "$USD_OUT" | head -1)"
  fi
else
  emit_fail "cannot test usd-core: conda env python missing"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 9. pxr importability (bundled, via Kit Python)
# Standard mode: static file check (already done in §6).
# Deep mode: actually launch python.sh and import pxr/omni. Slow.
# ─────────────────────────────────────────────────────────────────────────────
section "pxr importability (bundled / Runtime B)"

if [ "$DEEP" -eq 1 ]; then
  if [ -x "$KIT_LAUNCHER" ]; then
    emit_info "running $KIT_LAUNCHER (deep mode, may take ~30s) ..."
    if KIT_OUT=$(timeout 90 "$KIT_LAUNCHER" -c "from pxr import Usd; import omni.kit.app; print('OK', Usd.GetVersion())" 2>&1 < /dev/null); then
      if printf '%s' "$KIT_OUT" | grep -q '^OK '; then
        KIT_VER=$(printf '%s' "$KIT_OUT" | grep '^OK ' | head -1 | cut -d' ' -f2-)
        emit_pass "Kit Python: pxr + omni.kit.app import OK; pxr version $KIT_VER"
      else
        emit_fail "Kit Python ran but imports did not report OK (last 3 lines):"
        printf '%s\n' "$KIT_OUT" | tail -3 | sed 's/^/      /'
        FAIL_LIST+=("Kit Python pxr/omni import did not return OK")
      fi
    else
      emit_fail "Kit Python launcher timed out or errored (90s budget)"
    fi
  else
    emit_fail "cannot test bundled pxr: $KIT_LAUNCHER not executable"
  fi
else
  emit_info "skipped — pass --deep to launch Kit Python and import pxr/omni"
  if [ -n "$BUNDLED_PXR" ]; then
    emit_pass "static check: bundled pxr/__init__.py exists (see §6)"
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# 10. ROS 2 distro
# ─────────────────────────────────────────────────────────────────────────────
section "ROS 2 distro"

if [ -d "/opt/ros/$ROS_DISTRO_EXPECTED" ]; then
  emit_pass "ROS 2 $ROS_DISTRO_EXPECTED installed at /opt/ros/$ROS_DISTRO_EXPECTED"
else
  emit_fail "ROS 2 $ROS_DISTRO_EXPECTED missing at /opt/ros/$ROS_DISTRO_EXPECTED"
fi

OTHER_DISTROS=()
for d in /opt/ros/*/; do
  name=$(basename "$d")
  [ "$name" = "$ROS_DISTRO_EXPECTED" ] && continue
  OTHER_DISTROS+=("$name")
done
if [ "${#OTHER_DISTROS[@]}" -gt 0 ]; then
  emit_warn "additional ROS distros installed: ${OTHER_DISTROS[*]} (only $ROS_DISTRO_EXPECTED is canonical)"
fi

if [ "$PROFILE" = "ros" ]; then
  if [ "${ROS_DISTRO:-}" = "$ROS_DISTRO_EXPECTED" ]; then
    emit_pass "ROS_DISTRO=$ROS_DISTRO (matches canonical)"
  else
    emit_fail "ROS_DISTRO=${ROS_DISTRO:-?} (expected $ROS_DISTRO_EXPECTED)"
  fi
  if command -v ros2 >/dev/null 2>&1; then
    if PKG_COUNT=$(ros2 pkg list 2>/dev/null | wc -l); then
      emit_pass "ros2 CLI reachable; $PKG_COUNT packages indexed"
    else
      emit_fail "ros2 CLI present but pkg list failed"
    fi
  else
    emit_fail "ros2 CLI not on PATH"
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# 11. PYTHONPATH contamination
# ─────────────────────────────────────────────────────────────────────────────
section "PYTHONPATH contamination"

PP="${PYTHONPATH:-}"
if [ -z "$PP" ]; then
  emit_pass "PYTHONPATH is empty"
else
  emit_info "PYTHONPATH = $PP"
  has_conda=0; has_isaac=0; has_ros=0; has_user=0
  IFS=':' read -ra _PP_ENTRIES <<< "$PP"
  for e in "${_PP_ENTRIES[@]}"; do
    case "$e" in
      "$CONDA_ROOT/"*)   has_conda=1 ;;
      "$ISAAC_DIR/"*)    has_isaac=1 ;;
      "/opt/ros/"*)      has_ros=1 ;;
      "$WS_ROOT/"*)      has_user=1 ;;
    esac
  done
  mix=$(( has_conda + has_isaac + has_ros ))
  if [ "$mix" -gt 1 ]; then
    emit_fail "PYTHONPATH mixes runtimes (conda=$has_conda isaac=$has_isaac ros=$has_ros) — violates §5/§7 P5"
  fi
  # Profile-specific rules
  case "$PROFILE" in
    research)
      [ "$has_ros"   = 1 ] && emit_fail "PYTHONPATH contains ROS path in research profile (§5)"
      [ "$has_isaac" = 1 ] && emit_fail "PYTHONPATH contains Isaac path in research profile (§5)"
      [ "$mix" -le 1 ] && [ "$has_user$has_conda" != "00" ] && emit_pass "PYTHONPATH entries valid for research profile"
      ;;
    isaac)
      [ "$has_conda" = 1 ] && emit_fail "PYTHONPATH contains conda path in isaac profile (§5/§7 P5)"
      [ "$has_ros"   = 1 ] && emit_fail "PYTHONPATH contains system ROS path in isaac profile (use bundled bridge only, §5)"
      ;;
    ros)
      [ "$has_conda" = 1 ] && emit_fail "PYTHONPATH contains conda path in ros profile (§5/§7 P1)"
      [ "$has_isaac" = 1 ] && emit_fail "PYTHONPATH contains Isaac path in ros profile (§5)"
      [ "$has_ros"   = 1 ] && emit_pass "PYTHONPATH contains expected ROS site-packages"
      ;;
    none)
      [ "$has_ros"   = 1 ] && emit_warn "PYTHONPATH inherits ROS path from login shell — scrub before activating research/isaac"
      ;;
  esac
fi

# ─────────────────────────────────────────────────────────────────────────────
# 12. LD_LIBRARY_PATH contamination
# ─────────────────────────────────────────────────────────────────────────────
section "LD_LIBRARY_PATH contamination"

LL="${LD_LIBRARY_PATH:-}"
if [ -z "$LL" ]; then
  emit_pass "LD_LIBRARY_PATH is empty"
else
  emit_info "LD_LIBRARY_PATH (first 200 chars) = ${LL:0:200}$([ ${#LL} -gt 200 ] && echo '...')"
  ll_isaac=0; ll_isaac_bridge=0; ll_ros=0; ll_cuda=0
  IFS=':' read -ra _LL_ENTRIES <<< "$LL"
  for e in "${_LL_ENTRIES[@]}"; do
    case "$e" in
      "$ISAAC_DIR/exts/isaacsim.ros2.bridge/"*) ll_isaac_bridge=1 ;;
      "$ISAAC_DIR/"*)                            ll_isaac=1 ;;
      "/opt/ros/"*)                              ll_ros=1 ;;
      "$CUDA_ROOT/"*|/usr/local/cuda-*/lib*)     ll_cuda=1 ;;
    esac
  done
  # In isaac profile WITH bridge, having both isaac_bridge and (no ros) is the only legal combo
  if [ "$ll_ros" = 1 ] && [ "$ll_isaac" = 1 ] && [ "$ll_isaac_bridge" = 0 ]; then
    emit_fail "LD_LIBRARY_PATH mixes Isaac install libs with /opt/ros/ libs (violates §7 P7)"
  fi
  case "$PROFILE" in
    research)
      [ "$ll_cuda"  = 1 ] && emit_pass "LD_LIBRARY_PATH contains CUDA libs (expected in research)"
      [ "$ll_ros"   = 1 ] && emit_fail "LD_LIBRARY_PATH contains ROS libs in research profile"
      [ "$ll_isaac" = 1 ] && emit_fail "LD_LIBRARY_PATH contains Isaac libs in research profile"
      ;;
    isaac)
      [ "$ll_ros"          = 1 ] && emit_fail "LD_LIBRARY_PATH contains /opt/ros libs in isaac profile (use bundled bridge only — §7 P7)"
      [ "$ll_isaac_bridge" = 1 ] && emit_pass "LD_LIBRARY_PATH contains bundled ROS 2 bridge libs (opt-in OK)"
      ;;
    ros)
      [ "$ll_isaac" = 1 ] && emit_fail "LD_LIBRARY_PATH contains Isaac libs in ros profile"
      [ "$ll_ros"   = 1 ] && emit_pass "LD_LIBRARY_PATH contains ROS libs (expected in ros)"
      ;;
    none)
      [ "$ll_ros" = 1 ] && emit_warn "LD_LIBRARY_PATH inherits ROS libs from login shell"
      ;;
  esac
fi

# ─────────────────────────────────────────────────────────────────────────────
# 13. Duplicate ROS sourcing
# ─────────────────────────────────────────────────────────────────────────────
section "Duplicate ROS sourcing"

APP="${AMENT_PREFIX_PATH:-}"
if [ -z "$APP" ]; then
  if [ "$PROFILE" = "ros" ]; then
    emit_fail "AMENT_PREFIX_PATH is empty but ros profile is active"
  else
    emit_pass "AMENT_PREFIX_PATH not set (no ROS sourcing leaked)"
  fi
else
  # count occurrences of each ROS install prefix
  jazzy_count=0; humble_count=0
  IFS=':' read -ra _APP_ENTRIES <<< "$APP"
  for e in "${_APP_ENTRIES[@]}"; do
    case "$e" in
      "/opt/ros/jazzy"*)  jazzy_count=$((jazzy_count + 1)) ;;
      "/opt/ros/humble"*) humble_count=$((humble_count + 1)) ;;
    esac
  done
  if [ "$humble_count" -gt 0 ]; then
    emit_fail "AMENT_PREFIX_PATH contains Humble entries — multi-distro contamination (§7 P4)"
  fi
  if [ "$jazzy_count" -gt 1 ]; then
    emit_warn "AMENT_PREFIX_PATH contains /opt/ros/jazzy* $jazzy_count times — ROS setup was sourced more than once"
  elif [ "$jazzy_count" -eq 1 ]; then
    emit_pass "AMENT_PREFIX_PATH contains /opt/ros/jazzy exactly once"
  fi
fi

# stale env var (P10)
if [ -n "${ISAAC_ROS_WS:-}" ]; then
  if [ -d "${ISAAC_ROS_WS}" ]; then
    emit_pass "ISAAC_ROS_WS=$ISAAC_ROS_WS (exists)"
  else
    emit_warn "ISAAC_ROS_WS=$ISAAC_ROS_WS is set but the directory does not exist (P10 — stale)"
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# 14. Runtime profile correctness (cross-checks)
# ─────────────────────────────────────────────────────────────────────────────
section "Runtime profile correctness"

# Detect specific prohibited mixes (§7)
if [ "$HAS_CONDA" = 1 ] && [ "$HAS_ROS" = 1 ]; then
  emit_fail "P1 violation: conda env_isaaclab active AND /opt/ros sourced in the same shell"
fi
if [ "$HAS_ROS" = 1 ] && [ "$HAS_ISAAC_VAR" = 1 ]; then
  emit_fail "P7 violation: ROS sourced AND ISAAC_PATH set in the same shell"
fi
if [ "$HAS_CONDA" = 1 ] && [ "$HAS_ISAAC_VAR" = 1 ]; then
  emit_fail "Policy violation: conda env AND ISAAC_PATH set in the same shell"
fi

# CUDA on PATH outside research
if [ "$PROFILE" != "research" ] && [ "$PROFILE" != "none" ]; then
  if printf '%s' "${PATH:-}" | grep -q "$CUDA_ROOT/bin"; then
    emit_warn "CUDA bin on PATH outside research profile (§4 says CUDA only in research)"
  fi
fi

if [ "$ACTIVE_COUNT" -le 1 ] && [ "$PROFILE" != "contaminated" ]; then
  emit_pass "profile self-consistency check: no prohibited mixes detected"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Final summary
# ─────────────────────────────────────────────────────────────────────────────
n_pass=${#PASS_LIST[@]}
n_warn=${#WARN_LIST[@]}
n_fail=${#FAIL_LIST[@]}

printf '\n%s════════════════════════════════════════════════════════%s\n' "$C_BOLD" "$C_OFF"
printf '%sSummary%s — profile=%s  pass=%d  warn=%d  fail=%d\n' \
  "$C_BOLD" "$C_OFF" "$PROFILE" "$n_pass" "$n_warn" "$n_fail"
printf '%s════════════════════════════════════════════════════════%s\n' "$C_BOLD" "$C_OFF"

if [ "$n_fail" -gt 0 ]; then
  printf '\n%sFAIL%s (%d)\n' "$C_FAIL" "$C_OFF" "$n_fail"
  for m in "${FAIL_LIST[@]}"; do printf '  • %s\n' "$m"; done
fi
if [ "$n_warn" -gt 0 ]; then
  printf '\n%sWARN%s (%d)\n' "$C_WARN" "$C_OFF" "$n_warn"
  for m in "${WARN_LIST[@]}"; do printf '  • %s\n' "$m"; done
fi
if [ "$n_pass" -gt 0 ]; then
  printf '\n%sPASS%s (%d)\n' "$C_PASS" "$C_OFF" "$n_pass"
  for m in "${PASS_LIST[@]}"; do printf '  • %s\n' "$m"; done
fi

printf '\n'
if [ "$n_fail" -gt 0 ]; then
  printf '%sresult: FAIL%s — see docs/runtime_policy.md to remediate.\n' "$C_FAIL" "$C_OFF"
  exit 1
else
  if [ "$n_warn" -gt 0 ]; then
    printf '%sresult: PASS with warnings%s\n' "$C_WARN" "$C_OFF"
  else
    printf '%sresult: PASS%s\n' "$C_PASS" "$C_OFF"
  fi
  exit 0
fi
