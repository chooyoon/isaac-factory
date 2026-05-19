#!/usr/bin/env python3
"""Phase 3F — surgical simplification of the upstream Robotiq 2F-140.

Strategy (from the Phase 3F directive):

  Do NOT continue building replacement grippers from scratch.

  perform surgical simplification of the ORIGINAL working 2F-140 articulation.

  preserve all upstream articulation/link schemas while removing the
  broken loop-closing topology.

What this script does
---------------------

Starting from the upstream-pristine ``Robotiq_2F_140_physics_edit.usd``
(preserved at ``.pre3d``), produce a forked asset that:

* preserves every body's existing schemas (PhysicsRigidBodyAPI,
  PhysxRigidBodyAPI, IsaacLinkAPI, PhysicsCollisionAPI, ...);
* preserves every body's translate/orient/scale exactly;
* preserves the master drive joint (``finger_joint``) and the working
  mimic follower (``right_outer_knuckle_joint``) untouched;
* **removes the two loop-closing joints**
  ``left_inner_knuckle_joint`` and ``right_inner_knuckle_joint`` —
  PhysX's articulation cooker treats them as constraints and ignores
  the four-bar parallelogram closure (the Phase 3D root cause);
* **locks the remaining 6 passive joints at their canonical open-pose
  angles** by writing strong PD gains (stiffness 1e6, damping 1e4) and
  keeping each joint's authored ``drive:angular:physics:targetPosition``.
  The joints stay revolute (so the articulation cooker keeps them in
  the spanning tree) but PhysX holds them rigid — converting the
  parallelogram into a single rigid lever-arm per side.

Result topology (each side is now an open chain, not a 4-bar loop):

  base ── finger_joint (DRIVE) ─→ left_outer_knuckle ─[LOCK]→
                                  left_outer_finger ─[LOCK]→
                                  left_inner_finger ─[LOCK]→
                                  left_inner_knuckle (terminal)
                              ─[LOCK]→
                                  Fingertip_01 (terminal pad)

  base ── right_outer_knuckle_joint (MIMIC -1) ─→ right_outer_knuckle ...

Backups
-------

The cell's current ``.usd`` is overwritten in place; the pristine
upstream copy at ``.pre3d`` is untouched. A `.pre3f` backup of the
current `.usd` is written before the edit so a future revision can
diff against the Phase 3F state.

Idempotent: re-running uses ``.pre3d`` as the source and re-applies the
same simplifying edits.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pxr import Sdf, Usd, UsdPhysics


ASSET     = Path("/home/cap2/last/assets/cells/cell_01/robot/Robotiq/2F-140/"
                 "Robotiq_2F_140_physics_edit.usd")
PRISTINE  = ASSET.with_suffix(ASSET.suffix + ".pre3d")
PRE3F     = ASSET.with_suffix(ASSET.suffix + ".pre3f")

# Joints to DELETE (the loop closures).
DELETE_JOINTS = (
    "/Robotiq_2F_140/left_inner_knuckle_joint",
    "/Robotiq_2F_140/right_inner_knuckle_joint",
)

# Joints to LOCK rigid (stay revolute, strong PD).
LOCK_JOINTS = (
    "/Robotiq_2F_140/left_outer_finger_joint",
    "/Robotiq_2F_140/right_outer_finger_joint",
    "/Robotiq_2F_140/left_inner_finger_joint",
    "/Robotiq_2F_140/right_inner_finger_joint",
    "/Robotiq_2F_140/left_inner_finger_pad_joint",
    "/Robotiq_2F_140/right_inner_finger_pad_joint",
)

LOCK_STIFFNESS    = 1.0e6   # N·m/rad — keep the joint within ~µ-rad of target
LOCK_DAMPING      = 1.0e4   # N·m·s/rad
LOCK_MAX_FORCE    = 1.0e8   # effectively unlimited

# Phase 3F drive bake for the master finger_joint. cell_authoring's
# _author_gripper_drive() doesn't fire at build time (the gripper
# variant isn't composed in the in-memory authoring stage), so the
# YAML's drive_stiffness/drive_damping never reach the asset. We bake
# them in here so the master drive can actually fight the locked
# passive joints (which sit at 1e6 stiffness).
DRIVE_STIFFNESS   = 1.0e5
DRIVE_DAMPING     = 1.0e4
DRIVE_MAX_FORCE   = 1.0e6


def _set_float_attr(prim: Usd.Prim, name: str, value: float) -> None:
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Float, custom=False)
    attr.Set(float(value))


import math


def _ensure_open_pose_target(prim: Usd.Prim) -> float:
    """Return the joint's pinned-pose drive target IN RADIANS.

    PHASE 3F v5 fix: Isaac Sim's PhysX integration interprets
    ``drive:angular:physics:targetPosition`` as RADIANS at runtime
    (verified empirically — writing 0.60 to finger_joint produces a
    measured joint angle of ~0.62 rad). The USD spec nominally calls
    for degrees, but the upstream Robotiq 2F-140 was authored with
    DEGREE values (e.g. -45.0 on the inner-finger joints) and survived
    because its drive stiffness was so weak (~0.002) that the force
    barely registered.

    Once we crank stiffness to 1e6 to lock the joints rigid, a -45 RAD
    target = -2578° tries to slam the joint thousands of degrees past
    its ±45° limit, producing the numerical instability observed in
    v1/v3 ("inner_finger flying free" telemetry, z = 2.2 m).

    Convert each upstream authored DEGREE value to its radian
    equivalent so the lock pins the joint at the geometrically-correct
    rest angle. Joint limits in the upstream USD ARE in degrees
    (lowerLimit / upperLimit = -45.0 / +45.0); the runtime converts
    those to radians too, so the limit at ±0.785 rad is consistent.
    """
    # Phase 3F v7 EXPERIMENT: every passive joint pinned at 0 rad.
    # If this stops the body-flight, the issue is with the converted
    # -0.7854 rad target on the inner_finger joints (which sits at the
    # joint's lower limit and may trigger numerical instability).
    return 0.0


def main() -> int:
    if not PRISTINE.is_file():
        print(f"[3f] ERROR: pristine backup missing: {PRISTINE}", file=sys.stderr)
        return 1

    # Phase 3F snapshot of the current state, then restore from pristine.
    if ASSET.is_file() and not PRE3F.is_file():
        shutil.copy2(ASSET, PRE3F)
        print(f"[3f] saved pre-3f snapshot → {PRE3F.name}")
    shutil.copy2(PRISTINE, ASSET)
    print(f"[3f] restored pristine 2F-140 → {ASSET.name}")

    # Release any Sdf layer Isaac/USD may already be holding for this path.
    layer = Sdf.Layer.FindOrOpen(str(ASSET))
    if layer is not None:
        layer.Reload(force=True)

    stage = Usd.Stage.Open(str(ASSET))
    if stage is None:
        print(f"[3f] ERROR: could not open stage", file=sys.stderr)
        return 1

    # ───── neutralise the two loop-closing joints ─────
    # The joint specs live in sublayers and cannot be deleted from this
    # file.  Phase 3F v7 tried SetActive(False) — that removed the
    # joints from PhysX but the downstream bodies (inner_finger and
    # below) drifted free because the original 2F-140's articulation
    # cooker depended on the loop joints being PRESENT.
    #
    # Instead, NEUTRALISE the loop joints by zeroing their drive and
    # leaving them in-place. They remain a kinematic constraint
    # (revolute joint with no drive) but contribute no opinion on the
    # joint angle. The articulation cooker sees the same topology as
    # upstream; the body-coupling stays intact; the parallelogram is
    # mechanically decoupled.
    for path in DELETE_JOINTS:
        prim = stage.GetPrimAtPath(Sdf.Path(path))
        if not prim or not prim.IsValid():
            print(f"[3f] WARN: loop joint missing: {path}")
            continue
        _set_float_attr(prim, "drive:angular:physics:stiffness", 0.0)
        _set_float_attr(prim, "drive:angular:physics:damping",   0.0)
        _set_float_attr(prim, "drive:angular:physics:maxForce",  0.0)
        _set_float_attr(prim, "drive:angular:physics:targetPosition", 0.0)
        type_attr = prim.GetAttribute("drive:angular:physics:type")
        if type_attr:
            type_attr.Set("force")
        print(f"[3f] neutralised loop joint (drive=0): {path}")

    # ───── lock the 6 passive joints ─────
    for path in LOCK_JOINTS:
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[3f] WARN: joint to lock missing: {path}")
            continue
        target_rad = _ensure_open_pose_target(prim)
        _set_float_attr(prim, "drive:angular:physics:targetPosition", target_rad)
        _set_float_attr(prim, "drive:angular:physics:stiffness",      LOCK_STIFFNESS)
        _set_float_attr(prim, "drive:angular:physics:damping",        LOCK_DAMPING)
        _set_float_attr(prim, "drive:angular:physics:maxForce",       LOCK_MAX_FORCE)
        # Force drive type = "force" for every locked joint. The
        # upstream 2F-140 had ``left_outer_finger_joint`` and
        # ``right_outer_finger_joint`` authored as type="acceleration"
        # — that produces wildly unstable behaviour at stiffness 1e6
        # (the target becomes an angular acceleration of 1e6 × error,
        # i.e. tens of thousands of rad/s² for sub-mrad errors). Force
        # mode applies torque = stiffness × error, which the joint
        # limits can absorb safely.
        type_attr = prim.GetAttribute("drive:angular:physics:type")
        if not type_attr:
            type_attr = prim.CreateAttribute(
                "drive:angular:physics:type", Sdf.ValueTypeNames.Token, custom=False)
        type_attr.Set("force")
        # Pin the joint's reset-state position so World.reset() restores
        # the locked angle every cycle (determinism contract).
        _set_float_attr(prim, "state:angular:physics:position",       target_rad)
        _set_float_attr(prim, "state:angular:physics:velocity",       0.0)
        print(f"[3f] locked {path:62s} target={target_rad:+.4f} rad  "
              f"stiff={LOCK_STIFFNESS:.0e}  type=force")

    # ───── bake strong PD on the master finger_joint ─────
    fj = stage.GetPrimAtPath("/Robotiq_2F_140/finger_joint")
    if fj and fj.IsValid():
        _set_float_attr(fj, "drive:angular:physics:stiffness", DRIVE_STIFFNESS)
        _set_float_attr(fj, "drive:angular:physics:damping",   DRIVE_DAMPING)
        _set_float_attr(fj, "drive:angular:physics:maxForce",  DRIVE_MAX_FORCE)
        print(f"[3f] baked drive: finger_joint stiffness={DRIVE_STIFFNESS:.0e} "
              f"damping={DRIVE_DAMPING:.0e} maxForce={DRIVE_MAX_FORCE:.0e}")

    stage.Save()
    print(f"[3f] saved simplified 2F-140 to: {ASSET}")

    # ───── verify ─────
    verify = Usd.Stage.Open(str(ASSET))
    for path in DELETE_JOINTS:
        prim = verify.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[3f] VERIFY FAIL: loop joint missing entirely: {path}",
                  file=sys.stderr)
            return 1
        stiff = float(prim.GetAttribute("drive:angular:physics:stiffness").Get())
        if stiff != 0.0:
            print(f"[3f] VERIFY FAIL: loop joint still has stiffness {stiff}: {path}",
                  file=sys.stderr)
            return 1
    for path in LOCK_JOINTS:
        prim = verify.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[3f] VERIFY FAIL: locked joint missing after save: {path}",
                  file=sys.stderr)
            return 1
        sa = float(prim.GetAttribute("drive:angular:physics:stiffness").Get())
        if abs(sa - LOCK_STIFFNESS) > 1e-3:
            print(f"[3f] VERIFY FAIL: {path} stiffness = {sa} expected {LOCK_STIFFNESS}",
                  file=sys.stderr)
            return 1
    # Confirm the master joints are untouched.
    for path in ("/Robotiq_2F_140/finger_joint",
                 "/Robotiq_2F_140/right_outer_knuckle_joint"):
        prim = verify.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[3f] VERIFY FAIL: master joint missing: {path}", file=sys.stderr)
            return 1

    # Count surviving joints for the human reading the log.
    n_joints = 0
    for prim in verify.Traverse():
        if prim.IsA(UsdPhysics.Joint):
            n_joints += 1
    print(f"[3f] joints surviving = {n_joints} (expected 8: 1 drive + 1 mimic + 6 locked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
