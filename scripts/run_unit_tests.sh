#!/usr/bin/env bash
# scripts/run_unit_tests.sh
#
# Run every Runtime-A unit test suite under a sanitized environment.
#
# Why this script exists
# ----------------------
# The `env_isaaclab` conda env ships two ROS-shipped pytest plugins —
# `launch_testing` 1.0.4 and `launch_testing_ros` 0.19.4 — that break
# pytest 9.0.2 collection (they call `import_path()` with an outdated
# signature). Running pytest directly therefore crashes BEFORE collecting
# any tests, with INTERNALERROR / PluginValidationError.
#
# This script:
#   * sets `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` so only explicit plugins load
#   * scrubs ROS-injected env vars that bleed via the user's shell
#     (PYTHONPATH, ROS_DISTRO, AMENT_PREFIX_PATH, CMAKE_PREFIX_PATH,
#      GZ_CONFIG_PATH) per docs/runtime_policy.md §5 / §7
#   * adds the two cell-pipeline extensions to PYTHONPATH explicitly
#
# Usage
# -----
#   bash scripts/run_unit_tests.sh                  # all suites
#   bash scripts/run_unit_tests.sh tests/cell_01    # specific path
#   bash scripts/run_unit_tests.sh -v -k convey     # passthrough args
#
# Exit codes
# ----------
#   0   all tests passed
#   1   at least one test failed
#   2   bad argument or environment problem

set -eu

# --------------------------------------------------------------------- paths
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)
WORKSPACE=$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)

EXT_AUTHORING="$WORKSPACE/isaac_factory/extensions/cell_authoring"
EXT_VALIDATOR="$WORKSPACE/isaac_factory/extensions/asset_validator"

DEFAULT_TARGETS=(
  "$WORKSPACE/tests/cell_01"
  "$WORKSPACE/tests/scene_integrity"
  "$WORKSPACE/isaac_factory/extensions/asset_validator/tests"
)

# --------------------------------------------------------------------- python
if [[ -n "${FACTORY_PY:-}" ]]; then
  PY="$FACTORY_PY"
elif [[ -x "$HOME/miniconda3/envs/env_isaaclab/bin/python3" ]]; then
  PY="$HOME/miniconda3/envs/env_isaaclab/bin/python3"
else
  printf '[run_unit_tests] ERROR: no Runtime-A python found.\n' >&2
  printf '[run_unit_tests]   set FACTORY_PY or install env_isaaclab.\n' >&2
  exit 2
fi

# Verify imports without contaminating env: -E ignores PYTHON* env vars,
# -I also isolates from user site. We re-add what we need below.
if ! "$PY" -E -I -c "import pxr, yaml" 2>/dev/null; then
  printf '[run_unit_tests] ERROR: %s missing pxr or pyyaml.\n' "$PY" >&2
  exit 2
fi

# ------------------------------------------------------------- env scrubbing
# ROS / ament env-vars must NOT propagate into Runtime A pytest. The
# subset we unset matches the contamination guards in
# isaac_factory/extensions/asset_validator/tools/runtime_b_pytest_runner.py
# so the two test-running pipelines behave identically.
declare -a ROS_VARS_TO_UNSET=(
  PYTHONPATH
  ROS_DISTRO
  ROS_VERSION
  ROS_PYTHON_VERSION
  AMENT_PREFIX_PATH
  CMAKE_PREFIX_PATH
  GZ_CONFIG_PATH
  COLCON_PREFIX_PATH
)
for v in "${ROS_VARS_TO_UNSET[@]}"; do
  if [[ -n "${!v:-}" ]]; then
    printf '[run_unit_tests] unsetting %s (was: %s)\n' "$v" "${!v}" >&2
    unset "$v"
  fi
done

# ------------------------------------------------------------- pytest config
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTHONPATH="$EXT_AUTHORING:$EXT_VALIDATOR"

# ------------------------------------------------------------- targets / args
TARGETS=()
PYTEST_ARGS=()
if [[ $# -eq 0 ]]; then
  TARGETS=("${DEFAULT_TARGETS[@]}")
else
  # Args may include paths (existing dirs/files) and pytest options.
  for arg in "$@"; do
    if [[ -e "$arg" || "$arg" =~ ^/ || "$arg" == tests/* || "$arg" == isaac_factory/* ]]; then
      TARGETS+=("$arg")
    else
      PYTEST_ARGS+=("$arg")
    fi
  done
  if [[ ${#TARGETS[@]} -eq 0 ]]; then
    TARGETS=("${DEFAULT_TARGETS[@]}")
  fi
fi

# --------------------------------------------------------------- run
printf '[run_unit_tests] python    = %s\n' "$PY"
printf '[run_unit_tests] PYTHONPATH= %s\n' "$PYTHONPATH"
printf '[run_unit_tests] targets   = %s\n' "${TARGETS[*]}"

exec "$PY" -m pytest "${PYTEST_ARGS[@]}" "${TARGETS[@]}"
