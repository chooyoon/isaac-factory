"""Runtime B bootstrap validator.

Verifies that Isaac Sim Kit Python (Runtime B per docs/runtime_policy.md
§1) is reachable and that the omni.* modules the Phase 1.B PhysX
adapters will need are importable.

Two modes:

  default            — host-level static checks only. Fast. No Kit invoked.
  --probe            — also invokes `$ISAAC_PATH/python.sh` to import
                       omni.physx + pxr.UsdPhysics + isaacsim.core.api
                       and run trivial pxr operations. Slow (10-30s).
  --deep             — reserved; would boot SimulationApp. NOT implemented
                       in this scaffold to avoid GPU/license dependencies
                       during preparation work.

Run as (any Python ≥ 3.10):

    python isaac_factory/extensions/asset_validator/tools/runtime_b_validation.py
    python isaac_factory/extensions/asset_validator/tools/runtime_b_validation.py --probe

Output: human-readable PASS/WARN/FAIL report. Exit code 0 if no FAILs.

Read-only:
  - No env vars exported into the parent shell.
  - No files written.
  - The --probe subprocess spawns `python.sh` with a 60 s timeout.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


WS_ROOT     = "/home/cap2/last"
ISAAC_PATH  = "/home/cap2/isaac-sim-5.0.0"
KIT_PY      = f"{ISAAC_PATH}/kit/python/bin/python3"
KIT_LAUNCH  = f"{ISAAC_PATH}/python.sh"
ISAAC_SH    = f"{ISAAC_PATH}/isaac-sim.sh"
EXTSCACHE   = f"{ISAAC_PATH}/extscache"
PROBE_SCRIPT = (Path(__file__).resolve().parent / "physx_runtime_probe.py")


# ─────────────────────────────────────────────────────────── result helpers ──

_PASS: list[str] = []
_WARN: list[str] = []
_FAIL: list[str] = []


def _is_tty() -> bool:
    return sys.stdout.isatty()


_C_BOLD = "\x1b[1m" if _is_tty() else ""
_C_OFF  = "\x1b[0m" if _is_tty() else ""
_C_PASS = "\x1b[32m" if _is_tty() else ""
_C_WARN = "\x1b[33m" if _is_tty() else ""
_C_FAIL = "\x1b[31m" if _is_tty() else ""
_C_DIM  = "\x1b[2m"  if _is_tty() else ""


def emit_pass(msg: str) -> None:
    print(f"  {_C_PASS}[PASS]{_C_OFF} {msg}")
    _PASS.append(msg)


def emit_warn(msg: str) -> None:
    print(f"  {_C_WARN}[WARN]{_C_OFF} {msg}")
    _WARN.append(msg)


def emit_fail(msg: str) -> None:
    print(f"  {_C_FAIL}[FAIL]{_C_OFF} {msg}")
    _FAIL.append(msg)


def emit_info(msg: str) -> None:
    print(f"  {_C_DIM}{msg}{_C_OFF}")


def section(title: str) -> None:
    print(f"\n{_C_BOLD}── {title} ──{_C_OFF}")


# ────────────────────────────────────────────────────── static check stages ──


def check_isaac_install() -> None:
    section("Isaac Sim install")
    if not Path(ISAAC_PATH).is_dir():
        emit_fail(f"Isaac Sim directory missing: {ISAAC_PATH}")
        return
    emit_pass(f"Isaac Sim directory present: {ISAAC_PATH}")
    for f in (KIT_LAUNCH, ISAAC_SH, KIT_PY):
        if Path(f).is_file() or Path(f).is_symlink():
            emit_pass(f"launcher present: {Path(f).name}")
        else:
            emit_fail(f"launcher missing: {f}")


def check_kit_python_version() -> None:
    section("Kit Python interpreter")
    if not Path(KIT_PY).is_file():
        emit_fail(f"Kit Python binary missing: {KIT_PY}")
        return
    try:
        out = subprocess.check_output([KIT_PY, "--version"],
                                      stderr=subprocess.STDOUT, timeout=10).decode().strip()
    except Exception as e:                              # noqa: BLE001
        emit_fail(f"Kit Python --version failed: {e}")
        return
    emit_pass(f"Kit Python: {out}")
    if "3.11" not in out:
        emit_warn(f"unexpected Kit Python major.minor — policy expects 3.11.x, got {out}")


def check_extscache_for_physx() -> None:
    section("PhysX extensions in extscache")
    if not Path(EXTSCACHE).is_dir():
        emit_fail(f"extscache missing: {EXTSCACHE}")
        return

    expected = {
        "omni.physx":              "omni.physx-",
        "omni.physx.commands":     "omni.physx.commands-",
        "omni.physx.cooking":      "omni.physx.cooking-",
        "omni.usd.libs (pxr host)": "omni.usd.libs-",
        "isaacsim.core.api":       "isaacsim.core.api-",
        "isaacsim.ros2.bridge/jazzy": "isaacsim.ros2.bridge",
    }
    extant = list(Path(EXTSCACHE).iterdir())
    extant_names = [p.name for p in extant]
    for label, prefix in expected.items():
        # Allow either an exts/ dir or an extscache dir starting with the prefix.
        match = any(name.startswith(prefix) for name in extant_names)
        if not match:
            # Some live under $ISAAC_PATH/exts/ instead.
            exts_dir = Path(ISAAC_PATH) / "exts"
            if exts_dir.is_dir():
                if any(p.name.startswith(prefix.rstrip("-")) for p in exts_dir.iterdir()):
                    match = True
        if match:
            emit_pass(f"extension present: {label}")
        else:
            emit_warn(f"extension not found in extscache: {label}")


def check_probe_script() -> None:
    section("Probe script self-check")
    if PROBE_SCRIPT.is_file():
        emit_pass(f"physx_runtime_probe.py present: {PROBE_SCRIPT}")
    else:
        emit_fail(f"physx_runtime_probe.py missing: {PROBE_SCRIPT}")


def check_adapter_scaffolds() -> None:
    section("PhysX adapter scaffolds")
    scaffolds = [
        ("PhysXContactSource",      "physx_contact_source.py"),
        ("PhysXColliderInspector",  "physx_collider_inspector.py"),
        ("PhysXResetSimulator",     "physx_reset_simulator.py"),
    ]
    adapt_dir = Path(WS_ROOT) / "isaac_factory" / "extensions" / "asset_validator" \
                / "asset_validator" / "adapters"
    for klass, fname in scaffolds:
        if (adapt_dir / fname).is_file():
            emit_pass(f"scaffold present: {klass} ({fname})")
        else:
            emit_fail(f"scaffold missing: {klass} ({adapt_dir / fname})")


# ───────────────────────────────────────────────── subprocess probe stages ──


def check_probe_subprocess() -> None:
    section("Kit Python import probe (subprocess)")
    if not Path(KIT_LAUNCH).is_file():
        emit_fail(f"python.sh launcher missing: {KIT_LAUNCH}")
        return
    if not PROBE_SCRIPT.is_file():
        emit_fail(f"probe script missing: {PROBE_SCRIPT}")
        return

    # `python.sh` cd's to ISAAC_PATH internally; pass absolute paths.
    cmd = [KIT_LAUNCH, str(PROBE_SCRIPT)]
    emit_info(f"invoking: {' '.join(cmd)}")
    emit_info("(60s timeout; first invocation may JIT-compile shaders)")

    env = os.environ.copy()
    # Honor the policy P5/P7 — scrub PYTHONPATH so Kit's bundled paths win.
    env.pop("PYTHONPATH", None)
    # Disable Kit telemetry / GPU prompts (best-effort, harmless if ignored).
    env.setdefault("OMNI_KIT_ACCEPT_EULA", "YES")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=60, env=env, check=False,
        )
    except subprocess.TimeoutExpired:
        emit_fail("Kit Python probe timed out (60s)")
        return
    except FileNotFoundError as e:
        emit_fail(f"could not exec {KIT_LAUNCH}: {e}")
        return

    if result.returncode != 0:
        emit_warn(f"probe returned non-zero exit code {result.returncode}")
        if result.stderr:
            emit_info(f"stderr (last 5 lines):\n      "
                      + "\n      ".join(result.stderr.strip().splitlines()[-5:]))
        # Still try to parse JSON if present.

    payload = _extract_json(result.stdout)
    if payload is None:
        emit_fail("probe produced no parsable JSON output")
        if result.stdout:
            emit_info("first 200 chars of stdout:")
            emit_info(result.stdout[:200])
        return

    # Report findings
    if "kit_python_version" in payload:
        emit_pass(f"Kit Python reports: {payload['kit_python_version']}")

    for mod, info in sorted(payload.get("imports", {}).items()):
        if info.get("ok"):
            emit_pass(f"import {mod}")
        else:
            err = (info.get("error") or "").splitlines()[0]
            if mod.startswith(("pxr.", "omni.usd")):
                emit_fail(f"import {mod} failed: {err}")
            else:
                emit_warn(f"import {mod} failed: {err}")

    for cap, info in sorted(payload.get("capabilities", {}).items()):
        if info.get("ok"):
            emit_pass(f"capability {cap}")
        else:
            emit_fail(f"capability {cap} failed")


def _extract_json(text: str) -> dict | None:
    """Find the last balanced JSON object in `text` and return it, or None.

    Kit emits a lot of pre-script noise (banners, warnings); the probe
    script's JSON is the LAST top-level object printed.
    """
    if not text:
        return None
    # Look for the LAST `{` and pair it with the LAST `}` — assume balanced.
    last_open = text.rfind("{")
    last_close = text.rfind("}")
    if last_open == -1 or last_close == -1 or last_open >= last_close:
        return None
    candidate = text[last_open : last_close + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


# ─────────────────────────────────────────────────────────────── summary ──


def print_summary() -> int:
    nP, nW, nF = len(_PASS), len(_WARN), len(_FAIL)
    print(f"\n{_C_BOLD}{'═' * 56}{_C_OFF}")
    print(f"{_C_BOLD} Runtime B validation summary{_C_OFF}")
    print(f"{_C_BOLD}{'═' * 56}{_C_OFF}")
    print(f"pass={nP}  warn={nW}  fail={nF}")
    if nF:
        print(f"\n{_C_FAIL}FAIL{_C_OFF}")
        for m in _FAIL: print(f"  • {m}")
    if nW:
        print(f"\n{_C_WARN}WARN{_C_OFF}")
        for m in _WARN: print(f"  • {m}")
    if nP:
        print(f"\n{_C_PASS}PASS{_C_OFF}  ({nP})")
        for m in _PASS: print(f"  • {m}")

    print()
    if nF:
        print(f"{_C_FAIL}result: FAIL{_C_OFF}")
        return 1
    if nW:
        print(f"{_C_WARN}result: PASS with warnings{_C_OFF}")
        return 0
    print(f"{_C_PASS}result: PASS{_C_OFF}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="runtime_b_validation.py", add_help=True)
    ap.add_argument("--probe", action="store_true",
                    help="invoke $ISAAC_PATH/python.sh to import omni.physx etc.")
    ap.add_argument("--deep", action="store_true",
                    help="(reserved) boot SimulationApp — not implemented in scaffold")
    args = ap.parse_args()

    print(f"{_C_BOLD}Runtime B bootstrap validator{_C_OFF}")
    print(f"workspace : {WS_ROOT}")
    print(f"isaac path: {ISAAC_PATH}")

    check_isaac_install()
    check_kit_python_version()
    check_extscache_for_physx()
    check_probe_script()
    check_adapter_scaffolds()

    if args.deep:
        emit_warn("--deep is reserved; SimulationApp boot is not part of "
                  "this scaffold. Use --probe for import-level verification.")

    if args.probe:
        check_probe_subprocess()
    else:
        emit_info("\n(Skipping subprocess probe; pass --probe to invoke Kit Python.)")

    return print_summary()


if __name__ == "__main__":
    raise SystemExit(main())
