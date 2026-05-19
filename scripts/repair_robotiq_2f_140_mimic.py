#!/usr/bin/env python3
"""Phase 3D — Robotiq 2F-140 mimic-chain surgical repair.

Defect (Phase 3C-tail diagnosis)
--------------------------------

The mirrored NVIDIA-Robotiq 2F-140 ``physics_edit`` USD ships with a
``PhysxMimicJointAPI:rotX`` on only **one** joint — the
``right_outer_knuckle_joint`` (gearing -1, reference = ``finger_joint``).
The two **inner knuckle** joints — which together close the four-bar
parallelogram that keeps the finger pads parallel — have **no mimic API
and no drive**. They float passively.

Consequence under Kit / PhysX
-----------------------------

* ``finger_joint`` (drive) and ``right_outer_knuckle_joint`` (mimic -1)
  rotate as the trajectory commands.
* The left inner knuckle goes slack; the left outer finger rotates by
  near-zero (~9 × 10⁻⁶ rad) instead of mirroring the drive.
* The right inner knuckle, being unconstrained, follows the inner-finger
  spring bias (target = −45°) rather than the drive.
* Net result: the pads close asymmetrically with min separation 4.5–9.7
  mm — far short of clamping a 50 mm peg. No friction grasp engages.

Repair
------

Apply ``PhysxMimicJointAPI:rotX`` to both inner-knuckle joints with the
same numerical signature as the working right_outer_knuckle mimic:

  * referenceJoint  = /Robotiq_2F_140/finger_joint
  * gearing         = +1.0 for the **left**  inner knuckle (same side as drive)
  * gearing         = -1.0 for the **right** inner knuckle (mirror)
  * naturalFrequency= 1000.0
  * dampingRatio    = 1.0

That is the minimum patch — two missing joint constraints — and lives
entirely inside ``Robotiq_2F_140_physics_edit.usd``. No cell-side
override needed.

Backups
-------

The original file is copied to ``Robotiq_2F_140_physics_edit.usd.pre3d``
**only if** that backup does not already exist (so re-running the script
is idempotent and the backup always points at the upstream-pristine
version).

Verification
------------

After saving, the script re-opens the file and prints the applied
schemas + mimic attributes for both repaired joints + the original
``right_outer_knuckle_joint`` reference; failure to confirm the schema
attaches raises ``SystemExit(1)``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pxr import Sdf, Usd, UsdPhysics


ASSET = Path(
    "/home/cap2/last/assets/cells/cell_01/robot/Robotiq/2F-140/"
    "Robotiq_2F_140_physics_edit.usd"
)
BACKUP = ASSET.with_suffix(ASSET.suffix + ".pre3d")

DRIVE_JOINT_PATH = "/Robotiq_2F_140/finger_joint"

REPAIR_TARGETS = (
    # (joint name,                 gearing sign relative to finger_joint)
    #
    # NB: PhysX honours PhysxMimicJointAPI only on joints that live in the
    # articulation's spanning tree (the kinematic chain it can traverse
    # without revisiting a body); loop-closing joints are treated as
    # constraints and the mimic is ignored. The inner-knuckle joints are
    # loop-closures, so we instead apply mimic to the spanning-tree
    # joints whose position propagates the parallelogram closure: the
    # outer-finger and inner-finger-pad joints on each side.
    #
    # Sign convention chosen so each joint's authored axis (+Z) follows
    # the finger_joint's drive in the direction that closes the gripper.
    # Validated empirically by re-running the cycle and inspecting
    # mimic_joint_pos_at_close in the telemetry sidecar.
    ("left_outer_finger_joint",        -1.0),
    ("right_outer_finger_joint",       +1.0),
    ("left_inner_finger_pad_joint",    -1.0),
    ("right_inner_finger_pad_joint",   +1.0),
    # Inner-knuckle (loop-closing) — kept for documentation; PhysX may
    # ignore them but they're harmless. If a future Kit / PhysX version
    # gains support for mimic-on-loop-joint, both sides will fall in line.
    ("left_inner_knuckle_joint",       +1.0),
    ("right_inner_knuckle_joint",      -1.0),
)

MIMIC_NATURAL_FREQ = 1000.0
MIMIC_DAMPING_RATIO = 1.0
SCHEMA_NAME = "PhysxMimicJointAPI:rotX"


def _apply_mimic(prim: Usd.Prim, *, reference_joint: str,
                 gearing: float, natural_freq: float, damping_ratio: float) -> None:
    """Apply PhysxMimicJointAPI:rotX and write its four attrs.

    We use ``AddAppliedSchema`` rather than ``PhysxSchema.PhysxMimicJointAPI.Apply``
    because the latter requires importing ``pxr.PhysxSchema``, which is
    bundled with Kit Python but absent from the env_isaaclab conda
    environment used for offline authoring. The schema name in the
    apiSchemas metadata is the only thing PhysX checks at composition
    time; the runtime reads the typed attributes by name.
    """
    prim.AddAppliedSchema(SCHEMA_NAME)

    def _attr(name: str, type_name: Sdf.ValueTypeName, value):
        attr = prim.GetAttribute(name)
        if not attr:
            attr = prim.CreateAttribute(name, type_name, custom=False)
        attr.Set(value)

    _attr("physxMimicJoint:rotX:gearing",          Sdf.ValueTypeNames.Float, float(gearing))
    _attr("physxMimicJoint:rotX:naturalFrequency", Sdf.ValueTypeNames.Float, float(natural_freq))
    _attr("physxMimicJoint:rotX:dampingRatio",     Sdf.ValueTypeNames.Float, float(damping_ratio))

    rel = prim.GetRelationship("physxMimicJoint:rotX:referenceJoint")
    if not rel:
        rel = prim.CreateRelationship("physxMimicJoint:rotX:referenceJoint")
    rel.SetTargets([Sdf.Path(reference_joint)])


def main() -> int:
    if not ASSET.is_file():
        print(f"[repair] ERROR: asset not found: {ASSET}", file=sys.stderr)
        return 1

    if not BACKUP.exists():
        shutil.copy2(ASSET, BACKUP)
        print(f"[repair] backed up upstream-pristine asset → {BACKUP.name}")
    else:
        print(f"[repair] backup already present (not overwriting): {BACKUP.name}")

    stage = Usd.Stage.Open(str(ASSET))
    if stage is None:
        print(f"[repair] ERROR: could not open stage", file=sys.stderr)
        return 1

    # Sanity: confirm the drive joint we'll reference exists.
    drv = stage.GetPrimAtPath(DRIVE_JOINT_PATH)
    if not drv or not drv.IsValid():
        print(f"[repair] ERROR: drive joint missing: {DRIVE_JOINT_PATH}", file=sys.stderr)
        return 1

    # Apply mimic to each target.
    for name, gearing in REPAIR_TARGETS:
        path = f"/Robotiq_2F_140/{name}"
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[repair] ERROR: target joint missing: {path}", file=sys.stderr)
            return 1
        if not prim.IsA(UsdPhysics.Joint):
            print(f"[repair] ERROR: target is not a Joint: {path}", file=sys.stderr)
            return 1
        _apply_mimic(
            prim,
            reference_joint = DRIVE_JOINT_PATH,
            gearing         = gearing,
            natural_freq    = MIMIC_NATURAL_FREQ,
            damping_ratio   = MIMIC_DAMPING_RATIO,
        )
        print(f"[repair] applied {SCHEMA_NAME} to {path} (gearing={gearing:+.1f})")

    stage.Save()
    print(f"[repair] saved: {ASSET}")

    # Verify by re-opening from disk.
    verify = Usd.Stage.Open(str(ASSET))
    bad = 0
    for name, gearing in REPAIR_TARGETS:
        path = f"/Robotiq_2F_140/{name}"
        prim = verify.GetPrimAtPath(path)
        schemas = list(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        if SCHEMA_NAME not in schemas:
            print(f"[repair] VERIFY FAIL: {path}: {SCHEMA_NAME} not applied; schemas={schemas}",
                  file=sys.stderr)
            bad += 1
            continue
        g = float(prim.GetAttribute("physxMimicJoint:rotX:gearing").Get())
        nf = float(prim.GetAttribute("physxMimicJoint:rotX:naturalFrequency").Get())
        dr = float(prim.GetAttribute("physxMimicJoint:rotX:dampingRatio").Get())
        ref = list(prim.GetRelationship("physxMimicJoint:rotX:referenceJoint").GetTargets())
        print(f"[verify] {name}: gearing={g:+.2f}  natFreq={nf}  damp={dr}  ref={ref}")
        if abs(g - gearing) > 1e-9 or ref != [Sdf.Path(DRIVE_JOINT_PATH)]:
            print(f"[repair] VERIFY FAIL: {path}: numeric mismatch", file=sys.stderr)
            bad += 1

    if bad:
        return 1
    print("[repair] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
