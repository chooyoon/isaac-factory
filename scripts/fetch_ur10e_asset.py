"""Mirror the UR10e USD asset tree from the public S3 bucket into the workspace.

Why this exists
---------------

The Isaac Sim 5.0 UR10e ships as a multi-layered USD asset on
https://omniverse-content-production.s3-us-west-2.amazonaws.com . The
top-level ``ur10e.usd`` (10 KB) is a variant wrapper that payloads
into ``configuration/ur10e_{robot,physics,sensor}.usd``, which in turn
reference per-link meshes elsewhere in the same bucket.

For deterministic, network-independent cell builds we need every layer
resolved at authoring time, mirrored under
``assets/cells/cell_01/robot/`` (workspace storage policy §3 — no
global user caches).

Strategy
--------

  1. Boot SimulationApp (only because the USD asset resolver requires
     it to handle ``omniverse://`` / ``https://`` resolution).
  2. ``Usd.Stage.Open`` the remote URL with all payloads loaded.
  3. Walk ``stage.GetUsedLayers()`` and ``stage.GetLayerStack()``.
  4. For every layer whose identifier resolves to the remote URL prefix,
     download it into the local mirror at the same relative path.

The local mirror's root-layer path remains stable so the cell stage
can reference ``assets/cells/cell_01/robot/ur10e.usd`` independently
of where this script downloaded from.
"""

from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Walk every layer used by the UR10e (including selected gripper variant)
# and mirror it under the local robot/ directory, preserving the
# NVIDIA Isaac/Robots/ subtree layout so internal relative references
# inside the assets (e.g. `../../Robotiq/2F-85/...` from inside
# `UniversalRobots/ur10e/`) resolve natively.
REMOTE_PREFIX = (
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com"
    "/Assets/Isaac/5.0/Isaac/Robots/"
)
REMOTE_TOP    = REMOTE_PREFIX + "UniversalRobots/ur10e/ur10e.usd"
LOCAL_ROOT    = Path("/home/cap2/last/assets/cells/cell_01/robot/")
# Variants we want fully resolved + mirrored. Robotiq_2f_85 is the
# Phase 3B-selected gripper.
# Robotiq_2f_85 ships without colliders in Isaac Sim 5.0.0-rc.45 — unfit
# for friction-based grasp. Robotiq_2f_140 ships with 7-collider geometry
# matched to its 7 rigid bodies. The 140 mm stroke also has room for the
# cell's 50 mm peg.
GRIPPER_VARIANT = "Robotiq_2f_140"

LOG = Path("/home/cap2/last/logs/fetch_ur10e.log")


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        _log(f"  skip  (exists)  {dest.name}")
        return
    _log(f"  fetch          {url} -> {dest}")
    urllib.request.urlretrieve(url, str(dest))


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    _log(f"[fetch] REMOTE_PREFIX = {REMOTE_PREFIX}")
    _log(f"[fetch] REMOTE_TOP    = {REMOTE_TOP}")
    _log(f"[fetch] LOCAL_ROOT    = {LOCAL_ROOT}")
    _log(f"[fetch] gripper var   = {GRIPPER_VARIANT}")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        return _run(app)
    except Exception as e:
        import traceback
        _log(f"[fetch] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _run(app) -> int:
    from pxr import Sdf, Usd

    _log(f"\n[fetch] opening remote top layer: {REMOTE_TOP}")
    stage = Usd.Stage.Open(REMOTE_TOP, Usd.Stage.LoadAll)
    if not stage:
        _log("[fetch] FAILED to open remote stage")
        return 1

    # Select the Robotiq_2f_85 gripper variant so its layers join
    # GetUsedLayers().
    prim = stage.GetDefaultPrim()
    gripper_vs = prim.GetVariantSet("Gripper")
    if GRIPPER_VARIANT in gripper_vs.GetVariantNames():
        gripper_vs.SetVariantSelection(GRIPPER_VARIANT)
        _log(f"[fetch] selected Gripper={GRIPPER_VARIANT}")
        # Trigger payload resolution after variant switch
        stage.Load()

    used_layers = stage.GetUsedLayers(includeClipLayers=True)
    _log(f"\n[fetch] used layers ({len(used_layers)}):")
    for layer in used_layers:
        _log(f"  - {layer.identifier}  (anonymous={layer.anonymous})")

    # Filter to layers under REMOTE_PREFIX; mirror into LOCAL_ROOT
    # preserving the path structure beyond REMOTE_PREFIX (so e.g.
    # remote ".../Isaac/Robots/UniversalRobots/ur10e/ur10e.usd" maps to
    # local "<LOCAL_ROOT>/UniversalRobots/ur10e/ur10e.usd").
    downloaded = 0
    for layer in used_layers:
        if layer.anonymous:
            continue
        ident = layer.identifier
        if not ident.startswith(REMOTE_PREFIX):
            _log(f"  external layer (not mirrored): {ident}")
            continue
        rel = ident[len(REMOTE_PREFIX):].split("?", 1)[0]
        local_path = LOCAL_ROOT / rel
        _fetch(ident, local_path)
        downloaded += 1

    _log(f"\n[fetch] downloaded {downloaded} layer(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
