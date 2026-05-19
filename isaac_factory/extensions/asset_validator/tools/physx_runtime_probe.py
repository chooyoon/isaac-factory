"""PhysX runtime probe — meant to be run **inside Isaac Sim Kit Python**.

Run as:
    $ISAAC_PATH/python.sh \
        isaac_factory/extensions/asset_validator/tools/physx_runtime_probe.py

Imports the omni.* and pxr.* modules the Phase 1.B adapters will need,
verifies that each is reachable from Kit Python, and emits a single
JSON object to stdout reporting which capabilities are available.

The output JSON is consumed by `tools/runtime_b_validation.py`. Format:

    {
      "kit_python_version": "3.11.13",
      "imports": {
        "pxr.Usd":                 {"ok": true,  "error": null},
        "pxr.UsdGeom":             {"ok": true,  "error": null},
        "pxr.UsdPhysics":          {"ok": true,  "error": null},
        "omni.usd":                {"ok": true,  "error": null},
        "omni.physx":              {"ok": true,  "error": null},
        "omni.physx.scripts":      {"ok": true,  "error": null},
        "isaacsim.core.api":       {"ok": true,  "error": null}
      },
      "capabilities": {
        "stage_create":            {"ok": true,  "error": null},
        "stage_traverse":          {"ok": true,  "error": null},
        "prim_define":             {"ok": true,  "error": null}
      },
      "errors": []
    }

This script does NOT boot SimulationApp; it only verifies module
importability and trivial pxr-only operations. Booting Kit is a
separate `--deep` step in `runtime_b_validation.py`.
"""

from __future__ import annotations

import json
import sys
import traceback


def _try_import(modname: str) -> dict:
    try:
        __import__(modname)
        return {"ok": True, "error": None}
    except Exception as e:                                  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _try_capability(name: str, fn) -> dict:
    try:
        fn()
        return {"ok": True, "error": None}
    except Exception:                                       # noqa: BLE001
        return {"ok": False, "error": traceback.format_exc(limit=2)}


def main() -> int:
    report: dict = {
        "kit_python_version": sys.version.split()[0],
        "imports": {},
        "capabilities": {},
        "errors": [],
    }

    modules = [
        "pxr.Usd",
        "pxr.UsdGeom",
        "pxr.UsdPhysics",
        "omni.usd",
        "omni.physx",
        "omni.physx.scripts",
        "isaacsim.core.api",
    ]
    for m in modules:
        report["imports"][m] = _try_import(m)

    # Capabilities — only attempted if pxr.Usd imported cleanly.
    if report["imports"]["pxr.Usd"]["ok"]:
        from pxr import Usd, UsdGeom  # type: ignore

        def _create_stage():
            stage = Usd.Stage.CreateInMemory()
            assert stage is not None

        def _traverse_stage():
            stage = Usd.Stage.CreateInMemory()
            stage.DefinePrim("/A")
            stage.DefinePrim("/A/B")
            stage.DefinePrim("/A/B/C")
            n = sum(1 for _ in stage.Traverse())
            assert n >= 3

        def _define_prim():
            stage = Usd.Stage.CreateInMemory()
            cube = UsdGeom.Cube.Define(stage, "/Box")
            cube.GetSizeAttr().Set(1.0)
            assert cube.GetPrim().IsValid()

        report["capabilities"]["stage_create"]   = _try_capability("stage_create",   _create_stage)
        report["capabilities"]["stage_traverse"] = _try_capability("stage_traverse", _traverse_stage)
        report["capabilities"]["prim_define"]    = _try_capability("prim_define",    _define_prim)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
