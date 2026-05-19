#!/usr/bin/env bash
# scripts/build_cell_01.sh
#
# Build the deterministic cell_01 USD stage and (optionally) run the
# Phase 1A exit-gate validators against it.
#
# Runtime: research profile (Runtime A) — conda env_isaaclab. The script
# does NOT activate the profile itself; it expects either:
#   (a) you have already sourced `scripts/activate_factory_env.sh research`,
#   (b) FACTORY_PY env var is set to the absolute path of the right python,
#   (c) the env_isaaclab python exists at its canonical location and we
#       use it directly.
#
# Usage:
#   bash scripts/build_cell_01.sh           # build only
#   bash scripts/build_cell_01.sh --check   # build + Phase 1A gate (validators clean)
#   bash scripts/build_cell_01.sh --help
#
# Read-only beyond producing assets/cells/cell_01.usda. Validator output
# (in --check mode) is printed only — no JSON report is written here;
# the future `scripts/run_scene_validation.sh` pivot handles persisted
# reports per docs/storage_policy.md §3.
#
# Exit codes:
#   0  Build (and optional check) succeeded.
#   1  Build failed.
#   2  Bad argument.
#   3  Validator check failed (only meaningful with --check).

set -eu

# ─────────────────────────────────────────────────────────────────────────────
# Args
# ─────────────────────────────────────────────────────────────────────────────
CHECK=0
case "${1:-}" in
  "")            ;;
  --check)       CHECK=1 ;;
  -h|--help)
    sed -n '1,30p' "$0" | sed 's/^# //; s/^#//'
    exit 0
    ;;
  *)
    printf '[build_cell_01] ERROR: unknown argument %q\n' "$1" >&2
    exit 2
    ;;
esac

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)
WORKSPACE=$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)

CONFIG="$WORKSPACE/configs/cell_01.yaml"
STAGE="$WORKSPACE/assets/cells/cell_01.usda"

EXT_AUTHORING="$WORKSPACE/isaac_factory/extensions/cell_authoring"
EXT_VALIDATOR="$WORKSPACE/isaac_factory/extensions/asset_validator"

# ─────────────────────────────────────────────────────────────────────────────
# Python selector
# ─────────────────────────────────────────────────────────────────────────────
# Prefer (in order): FACTORY_PY → conda env_isaaclab (canonical) → first
# python3 on PATH that has pxr+yaml. System python3 only used as a last
# resort because the canonical research profile is env_isaaclab per
# docs/runtime_policy.md §4.
if [[ -n "${FACTORY_PY:-}" ]]; then
  PY="$FACTORY_PY"
elif [[ -x "$HOME/miniconda3/envs/env_isaaclab/bin/python3" ]]; then
  PY="$HOME/miniconda3/envs/env_isaaclab/bin/python3"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import pxr, yaml" 2>/dev/null; then
  PY=$(command -v python3)
else
  printf '[build_cell_01] ERROR: cannot locate a Runtime-A python with pxr + pyyaml.\n' >&2
  printf '[build_cell_01]   set FACTORY_PY to an absolute path, or\n' >&2
  printf '[build_cell_01]   source scripts/activate_factory_env.sh research first.\n' >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────
printf '[build_cell_01] python      = %s\n' "$PY"
printf '[build_cell_01] config      = %s\n' "$CONFIG"
printf '[build_cell_01] stage out   = %s\n' "$STAGE"

PYTHONPATH="$EXT_AUTHORING" \
  "$PY" -m cell_authoring.cli build \
      --config    "$CONFIG" \
      --workspace "$WORKSPACE" \
  || { printf '[build_cell_01] build FAILED\n' >&2; exit 1; }

# ─────────────────────────────────────────────────────────────────────────────
# Optional Phase 1A validator gate
# ─────────────────────────────────────────────────────────────────────────────
if [[ $CHECK -eq 1 ]]; then
  printf '[build_cell_01] running Runtime-A gate (Transform + Grounding + Collider)…\n'
  PYTHONPATH="$EXT_VALIDATOR" \
    "$PY" - <<PYEOF
import sys
from pxr import Usd
from asset_validator import (
    AcceptanceCriteria, ColliderValidator, GroundingValidator,
    TransformValidator, ValidationContext,
)
from asset_validator.adapters.usd_collider_inspector  import UsdColliderInspector
from asset_validator.adapters.usd_grounding_inspector import UsdGroundingInspector
from asset_validator.adapters.usd_stage_inspector     import UsdStageInspector

stage = Usd.Stage.Open("$STAGE")
assert stage, "stage open failed: $STAGE"

ctx = ValidationContext(
    asset_uri="$STAGE",
    criteria=AcceptanceCriteria(),
    stage_inspector     = UsdStageInspector    (stage=stage),
    grounding_inspector = UsdGroundingInspector(stage=stage),
    collider_inspector  = UsdColliderInspector (stage=stage),
)

results = {
    "TransformValidator": TransformValidator(ctx.criteria).run(ctx),
    "GroundingValidator": GroundingValidator(ctx.criteria).run(ctx),
    "ColliderValidator":  ColliderValidator (ctx.criteria).run(ctx),
}

fail = 0
for name, issues in results.items():
    print(f"  {name}: {len(issues)} issue(s)")
    for i in issues:
        paths = ",".join(i.prim_paths) if i.prim_paths else ""
        print(f"    {i.severity.name:<5} {i.code:<42} {paths}")
    if issues:
        fail = 1
sys.exit(fail)
PYEOF
  rc=$?
  if [[ $rc -ne 0 ]]; then
    printf '[build_cell_01] Runtime-A gate FAILED\n' >&2
    exit 3
  fi
  printf '[build_cell_01] Runtime-A gate PASS\n'
fi

printf '[build_cell_01] OK\n'
