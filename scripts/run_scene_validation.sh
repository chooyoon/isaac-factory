#!/usr/bin/env bash
# scripts/run_scene_validation.sh
#
# Run all asset validators and write a PASS/WARN/FAIL report.
#
# Read-only:
#   - Does not modify env vars in the parent shell.
#   - Does not delete or rewrite any source file.
#   - The only filesystem writes are inside the run-specific output
#     directory, which lives under `$WORKSPACE_ROOT/outputs/asset_validation/`
#     per docs/storage_policy.md §3.
#
# Implementation note:
#   The asset_validator's CLI entry point
#   (`asset_validator.cli.validate`, see docs/asset_validator_design.md §4.6)
#   is not yet implemented. Until it is, this script invokes the validators
#   via the existing pytest suites — they exercise every validator
#   end-to-end with mock inspectors. When the CLI exists, this script will
#   pivot to:
#
#     python.sh -m asset_validator.cli.validate \
#       --asset <path> \
#       --validators overlap,transform,collider,grounding,deterministic_reset \
#       --reporter text,json,junit \
#       --out-dir "$OUT"
#
#   The PASS/WARN/FAIL section format and the output-dir layout will not
#   change at that point.
#
# Usage:
#   bash scripts/run_scene_validation.sh
#   bash scripts/run_scene_validation.sh --out-dir /custom/path
#   bash scripts/run_scene_validation.sh --help
#
# Exit codes:
#   0  All validator tests passed
#   1  At least one test failed
#   2  Bad argument or environment problem

set -u

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
WS_ROOT="/home/cap2/last"
EXT_TESTS="$WS_ROOT/isaac_factory/extensions/asset_validator/tests/unit"
SCENE_TESTS="$WS_ROOT/tests/scene_integrity"
POLICY_DOC="$WS_ROOT/docs/runtime_policy.md"

# Validator → suite-file mapping (used for grouping pytest output)
VALIDATORS=(overlap transform collider grounding deterministic_reset)

# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers (TTY only)
# ─────────────────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  C_BOLD=$'\e[1m'; C_OFF=$'\e[0m'
  C_PASS=$'\e[32m'; C_WARN=$'\e[33m'; C_FAIL=$'\e[31m'; C_DIM=$'\e[2m'
else
  C_BOLD=''; C_OFF=''; C_PASS=''; C_WARN=''; C_FAIL=''; C_DIM=''
fi

log()  { printf '[run_scene_validation] %s\n' "$*"; }
err()  { printf '[run_scene_validation] ERROR: %s\n' "$*" >&2; }

# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────
OUT_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --out-dir)
      OUT_DIR="${2:-}"
      [ -z "$OUT_DIR" ] && { err "--out-dir requires a value"; exit 2; }
      shift 2
      ;;
    -h|--help)
      sed -n '2,40p' "$0"
      exit 0
      ;;
    *)
      err "unknown argument: $1"
      exit 2
      ;;
  esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Environment checks
# ─────────────────────────────────────────────────────────────────────────────
log "checking environment..."

if [ ! -d "$WS_ROOT" ]; then
  err "workspace missing: $WS_ROOT"
  exit 2
fi

if [ ! -d "$EXT_TESTS" ] || [ ! -d "$SCENE_TESTS" ]; then
  err "test suites missing — expected $EXT_TESTS and $SCENE_TESTS"
  exit 2
fi

# The validators are pure Python; any Python 3.10+ with pytest will do.
# Prefer the conda env_isaaclab interpreter (research profile) since that
# is the canonical orchestration runtime per docs/runtime_policy.md §1.
PY=""
if [ -n "${CONDA_DEFAULT_ENV:-}" ] && [ "${CONDA_DEFAULT_ENV}" = "env_isaaclab" ]; then
  PY="$(command -v python)"
elif [ -x "/home/cap2/miniconda3/envs/env_isaaclab/bin/python" ]; then
  PY="/home/cap2/miniconda3/envs/env_isaaclab/bin/python"
  log "research profile not active; using conda env's python directly: $PY"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
  log "neither research profile active nor conda env's python available; falling back to: $PY"
else
  err "no usable python found"
  exit 2
fi

# Confirm pytest is importable
if ! "$PY" -c "import pytest" >/dev/null 2>&1; then
  err "pytest is not importable by $PY — activate the research profile first:"
  err "  source scripts/activate_factory_env.sh research"
  err "(see $POLICY_DOC §4 for activation rules)"
  exit 2
fi

PY_VERSION=$("$PY" --version 2>&1)
log "python: $PY ($PY_VERSION)"

# ─────────────────────────────────────────────────────────────────────────────
# Resolve output directory
# Default: $WORKSPACE_ROOT/outputs/asset_validation/run-<UTC-timestamp>
# ─────────────────────────────────────────────────────────────────────────────
RUN_ID="run-$(date -u +%Y%m%dT%H%M%SZ)"
if [ -z "$OUT_DIR" ]; then
  OUT_DIR="$WS_ROOT/outputs/asset_validation/$RUN_ID"
fi

if ! mkdir -p "$OUT_DIR" 2>/dev/null; then
  err "cannot create output directory: $OUT_DIR"
  exit 2
fi
log "output directory: $OUT_DIR"

STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_SEC=$(date +%s)

# ─────────────────────────────────────────────────────────────────────────────
# Run the two pytest suites — capture JUnit XML + stdout/stderr
# ─────────────────────────────────────────────────────────────────────────────
run_suite() {
  local suite_name="$1"
  local suite_path="$2"
  local junit="$OUT_DIR/${suite_name}.junit.xml"
  local log_file="$OUT_DIR/${suite_name}.log"

  log "running $suite_name suite at $suite_path"
  "$PY" -m pytest "$suite_path" \
        --junit-xml="$junit" \
        -v --tb=short \
        --color=no \
        > "$log_file" 2>&1
  return $?
}

run_suite "unit"           "$EXT_TESTS"
UNIT_RC=$?

run_suite "scene_integrity" "$SCENE_TESTS"
SCENE_RC=$?

DURATION=$(( $(date +%s) - START_SEC ))

# ─────────────────────────────────────────────────────────────────────────────
# Analysis — group test outcomes by validator
# ─────────────────────────────────────────────────────────────────────────────
log "analyzing results..."

# Heredoc-injected Python analyzer reads both JUnit files, groups by validator,
# and writes summary.txt + report.json into OUT_DIR. It also prints the same
# summary to stdout. The analyzer is read-only: it reads JUnit files we just
# wrote and writes two output files in OUT_DIR.
"$PY" - "$OUT_DIR" "$WS_ROOT" "$RUN_ID" "$STARTED_AT" "$DURATION" \
       "$UNIT_RC" "$SCENE_RC" \
       "${VALIDATORS[@]}" <<'PY'
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

(out_dir, ws_root, run_id, started_at, duration,
 unit_rc, scene_rc, *validators) = sys.argv[1:]
out_dir  = Path(out_dir)
duration = int(duration)
unit_rc  = int(unit_rc)
scene_rc = int(scene_rc)


def parse_junit(path: Path) -> list[dict]:
    """Return a list of {classname, name, outcome, reason} dicts."""
    if not path.is_file():
        return []
    cases = []
    root = ET.parse(path).getroot()
    # JUnit can have <testsuites><testsuite>...</testsuite></testsuites>
    # OR a single <testsuite> root.
    suites = root.findall(".//testsuite") or [root]
    for suite in suites:
        for tc in suite.findall("testcase"):
            classname = tc.get("classname", "")
            name      = tc.get("name", "")
            outcome   = "passed"
            reason    = ""
            if tc.find("failure") is not None:
                outcome = "failed"
                reason  = (tc.find("failure").get("message") or "").splitlines()[0][:200]
            elif tc.find("error") is not None:
                outcome = "error"
                reason  = (tc.find("error").get("message") or "").splitlines()[0][:200]
            elif tc.find("skipped") is not None:
                outcome = "skipped"
                reason  = (tc.find("skipped").get("message") or "")[:200]
            cases.append({"classname": classname, "name": name,
                          "outcome": outcome, "reason": reason})
    return cases


def validator_for_case(classname: str) -> str:
    """Best-effort: pull the validator slug out of the classname/file path."""
    cl = classname.lower()
    for v in validators:
        if v in cl:
            return v
    return "unknown"


unit_cases  = parse_junit(out_dir / "unit.junit.xml")
scene_cases = parse_junit(out_dir / "scene_integrity.junit.xml")
all_cases   = [*unit_cases, *scene_cases]

# Group by validator
by_validator: dict[str, list[dict]] = defaultdict(list)
for c in all_cases:
    by_validator[validator_for_case(c["classname"])].append(c)

# Per-validator classification
per_validator = {}
for v in validators:
    cs = by_validator.get(v, [])
    n      = len(cs)
    fails  = sum(1 for c in cs if c["outcome"] in ("failed", "error"))
    skips  = sum(1 for c in cs if c["outcome"] == "skipped")
    passes = n - fails - skips
    if n == 0:
        status = "FAIL"   # no tests covered this validator at all
        note   = "no tests found"
    elif fails > 0:
        status = "FAIL"
        note   = f"{fails} of {n} tests failed"
    elif skips > 0:
        status = "WARN"
        note   = f"{skips} of {n} tests skipped"
    else:
        status = "PASS"
        note   = f"{passes}/{n} passed"
    per_validator[v] = {"status": status, "passes": passes, "fails": fails,
                        "skips": skips, "total": n, "note": note}

# Overall status
fails_total = sum(c["outcome"] in ("failed", "error") for c in all_cases)
skips_total = sum(c["outcome"] == "skipped" for c in all_cases)
passes_total = len(all_cases) - fails_total - skips_total
if fails_total or unit_rc not in (0, 5) or scene_rc not in (0, 5):
    overall = "FAIL"
elif skips_total:
    overall = "WARN"
else:
    overall = "PASS"
# (rc==5 from pytest means "no tests collected", which we surface via
# per_validator note rather than auto-failing the whole suite.)

# ─── Build summary.txt ─────────────────────────────────────────────────────
hr = "═" * 64

# Per-validator block
pv_lines = []
for v in validators:
    pv = per_validator[v]
    bullet = {"PASS": "✓", "WARN": "○", "FAIL": "✗"}[pv["status"]]
    pv_lines.append(
        f"  [{pv['status']:<4}] {bullet}  {v:<24} {pv['note']}"
    )

# FAIL section: list failing tests
fail_lines = []
for c in all_cases:
    if c["outcome"] in ("failed", "error"):
        fail_lines.append(
            f"  {c['outcome'].upper():<7}  {c['classname']}::{c['name']}"
        )
        if c["reason"]:
            fail_lines.append(f"           reason: {c['reason']}")

# WARN section
warn_lines = []
for c in all_cases:
    if c["outcome"] == "skipped":
        warn_lines.append(f"  SKIP    {c['classname']}::{c['name']}")
        if c["reason"]:
            warn_lines.append(f"           reason: {c['reason']}")

# PASS section: compact, just counts per validator
pass_lines = []
for v in validators:
    pv = per_validator[v]
    if pv["status"] == "PASS":
        pass_lines.append(f"  {v:<24} ({pv['passes']} tests)")

summary_lines = []
summary_lines.append(hr)
summary_lines.append(" Asset Validator Run Summary")
summary_lines.append(hr)
summary_lines.append(f"Run ID       : {run_id}")
summary_lines.append(f"Workspace    : {ws_root}")
summary_lines.append(f"Output dir   : {out_dir}")
summary_lines.append(f"Started      : {started_at}")
summary_lines.append(f"Duration     : {duration} s")
summary_lines.append(f"Tests        : {len(all_cases)} "
                     f"(pass {passes_total}, warn/skip {skips_total}, "
                     f"fail/error {fails_total})")
summary_lines.append("")
summary_lines.append("Validators tested:")
summary_lines.extend(pv_lines)
summary_lines.append("")
summary_lines.append("──── FAIL ────")
summary_lines.extend(fail_lines or ["  (none)"])
summary_lines.append("")
summary_lines.append("──── WARN ────")
summary_lines.extend(warn_lines or ["  (none)"])
summary_lines.append("")
summary_lines.append("──── PASS ────")
summary_lines.extend(pass_lines or ["  (none)"])
summary_lines.append("")
summary_lines.append(hr)
summary_lines.append(f"Overall      : {overall}")
summary_lines.append(hr)

(out_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n",
                                     encoding="utf-8")

# Print to stdout (no colour — bash wrapper handles colour for the final line)
print("\n".join(summary_lines))

# ─── report.json — machine-readable mirror ─────────────────────────────────
report = {
    "schema_version":  "1.0.0",
    "run_id":          run_id,
    "workspace":       ws_root,
    "started_at":      started_at,
    "duration_seconds": duration,
    "overall_status":  overall,
    "totals": {
        "tests":  len(all_cases),
        "passed": passes_total,
        "failed": fails_total,
        "skipped": skips_total,
    },
    "per_validator":   per_validator,
    "failures": [
        {"classname": c["classname"], "name": c["name"],
         "outcome": c["outcome"], "reason": c["reason"]}
        for c in all_cases if c["outcome"] in ("failed", "error")
    ],
    "warnings": [
        {"classname": c["classname"], "name": c["name"],
         "outcome": c["outcome"], "reason": c["reason"]}
        for c in all_cases if c["outcome"] == "skipped"
    ],
    "pytest_exit_codes": {"unit": unit_rc, "scene_integrity": scene_rc},
    "logs": {
        "unit":             "unit.log",
        "scene_integrity":  "scene_integrity.log",
        "junit_unit":       "unit.junit.xml",
        "junit_scene":      "scene_integrity.junit.xml",
    },
}
(out_dir / "report.json").write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

# Exit code mirrors overall status for the wrapper bash to consume.
sys.exit(0 if overall == "PASS" else (1 if overall == "FAIL" else 0))
PY
ANALYZE_RC=$?

# ─────────────────────────────────────────────────────────────────────────────
# Final status line + exit
# ─────────────────────────────────────────────────────────────────────────────
echo ""

if [ "$ANALYZE_RC" -eq 0 ]; then
  # Either PASS or WARN. Distinguish by reading the summary tail.
  if grep -q "Overall      : PASS" "$OUT_DIR/summary.txt" 2>/dev/null; then
    printf '%sresult: PASS%s — logs in %s\n' "$C_PASS" "$C_OFF" "$OUT_DIR"
    exit 0
  elif grep -q "Overall      : WARN" "$OUT_DIR/summary.txt" 2>/dev/null; then
    printf '%sresult: PASS with warnings%s — logs in %s\n' "$C_WARN" "$C_OFF" "$OUT_DIR"
    exit 0
  fi
fi

printf '%sresult: FAIL%s — see %s/summary.txt\n' "$C_FAIL" "$C_OFF" "$OUT_DIR"
exit 1
