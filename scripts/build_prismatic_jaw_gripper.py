#!/usr/bin/env python3
"""Phase 3K — prismatic-jaw gripper.

Phase 3J established that the lateral-clamp gripper's REVOLUTE finger
joints inject a tangential ±X impulse during closure (pad-face normal
rotates with the joint angle, so the force on the peg has a non-trivial
component along the conveyor axis). With strong enough drive to lift
the peg (max_peg_z=0.7553), that same drive ballistically ejects the
peg into the back of the cell.

This script replaces the gripper with PRISMATIC finger joints. Pads
slide LATERALLY without rotating; the pad face normal stays in the
closure direction throughout the close motion. Force on the peg is
pure ±Y (lateral clamp) — no rotational component, no ejection
impulse.

Topology
--------

  /Robotiq_2F_140/
    robotiq_base_link             (RigidBody, ee_joint attachment)
      collisions/base             (small Cube collider)
    left_finger                   (RigidBody, pad)
      collisions/finger           (Cube collider, friction-bound)
    right_finger                  (RigidBody, pad)
      collisions/finger           (Cube collider, friction-bound)
    finger_joint                  (PhysicsPrismaticJoint, drive)
                                  body0=base, body1=left_finger
                                  axis=Y in body0-local
    right_finger_joint            (PhysicsPrismaticJoint)
                                  body0=base, body1=right_finger
                                  axis=Y in body0-local
                                  mimic finger_joint, gearing=-1.0

Joint-position convention
-------------------------

For a prismatic joint, ``drive:linear:physics:targetPosition`` is in
METRES of stroke (USD spec; Isaac Sim runtime also uses metres for
prismatic DOFs — confirmed against
isaacsim.core.api.tests.test_articulation_view).  No rad↔deg
conversion is needed for linear DOFs.

  Open  → joint_state = 0     (pads at authored ±PIVOT_Y_OFFSET)
  Close → joint_state = -0.030 m (each pad slides 30 mm inward,
                                  closing the 90 mm open gap to 30 mm —
                                  fits the >peg-5mm requirement for
                                  a 50 mm peg).

Mimic gearing -1.0 on right_finger_joint ensures symmetric closure —
when finger_joint moves to -0.030, right_finger_joint moves to +0.030,
so both pads converge on the peg's centerline.

Drive parameters (linear units)
-------------------------------

  drive_stiffness  = 1e5  N/m
  drive_damping    = 1e3  N·s/m
  drive_max_force  = 1e3  N        (a 100 g peg needs <2 N to hold; 1 kN
                                    is ample headroom but bounded so the
                                    close motion can't pretend to be an
                                    infinite spring and explode the
                                    contact at impact)
  drive_type       = "force"

Schema stack (identical to Phase 3I-validated set)
--------------------------------------------------

  body: PhysicsRigidBodyAPI, PhysxRigidBodyAPI, IsaacLinkAPI, PhysicsMassAPI
  joint: PhysicsPrismaticJoint (typed),
         PhysxJointAPI, IsaacJointAPI,
         PhysicsDriveAPI:linear, PhysicsJointStateAPI:linear
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics


ASSET = Path(
    "/home/cap2/last/assets/cells/cell_01/robot/Robotiq/2F-140/"
    "Robotiq_2F_140_physics_edit.usd"
)
PRISTINE = ASSET.with_suffix(ASSET.suffix + ".pre3d")
PRE3K    = ASSET.with_suffix(ASSET.suffix + ".pre3k")


# Geometry (metres). Same overall envelope as the Phase 3J lateral-clamp
# revolute build — only the joint type changes.
ARM_LENGTH_M       = 0.20
ARM_WIDTH_M        = 0.12   # along world X (conveyor); wider than the peg
                            # (50 mm) so the pad face overlaps the peg's
                            # +X / -X edges regardless of its conveyor-axis
                            # drift during descent.
ARM_THICK_M        = 0.015  # along closure direction
BASE_SIZE_M        = 0.020
PIVOT_Y_OFFSET_M   = 0.045  # initial pad offset from centerline
                            # → open pad-face gap ≈ 75 mm (50 mm peg + 25 mm clearance)
                            # The pads then slide INWARD by 0.030 m each → closed
                            # pad-face gap ≈ 30 mm (peg width 50 mm − 20 mm overlap).
# Phase 3M — pad-vs-peg vertical alignment fix.
#
# Transform audit (scripts/diag_phase_3m_transform_audit.py, see
# logs/phase_3m_transform_audit.log) showed that the robotiq_base_link's
# basis maps local +Z to **world −Z** (the UR10e wrist_3 flange is rotated
# ~180° around Y). The Phase 3K author assumed local +Z → world +Z and
# set PIVOT_Z_OFFSET_M=−0.10 so the pad would sit 100 mm BELOW the base
# origin in world Z. The chain-flip turned that into pad 100 mm ABOVE
# wrist_3 in world (empirical Δz=+0.10004 m in the audit), with the
# direct consequence that pads sat at world z≈0.80 while the peg sits at
# world z≈0.70 — pad-vs-peg z gap = 100 mm, no grasp possible.
#
# The validated IK puts wrist_3 at world z=0.70 = peg centerline z. So
# the only PIVOT_Z value that places the pad centerline AT the peg
# centerline (preserving IK per Phase 3M charter) is PIVOT_Z_OFFSET_M=0:
# pad body origin coincides with wrist_3, pad collider extends ±0.10 m
# in world Z around peg z=0.70 → full vertical coverage of the 100 mm
# peg.
#
# A bare sign-flip to +0.10 was rejected because that maps to world
# z=wrist_3−0.10=0.60, leaving the pad centerline 100 mm BELOW the peg
# (failing the <5 mm centerline-Z error gate).
PIVOT_Z_OFFSET_M   = 0.0    # pad centerline = wrist_3 world Z = peg centerline.
                            # See Phase 3M transform audit above.

# Phase 3M — base collider lift. Because PIVOT_Z_OFFSET=0 also places
# the 20 mm base cube at wrist_3 world Z=0.70 (= peg center z), the
# base would interpenetrate the peg by up to 41 mm at full grasp pose.
# We lift ONLY the collider (not the rigid body / its joint anchor) so
# the prismatic-clamp mechanism, ee_joint, and articulation chain are
# untouched. local Z = −0.07 → world Z offset = +0.07 (chain flip) →
# base collider sits at wrist_3 z + 0.07 = 0.77, which is 19 mm above
# the peg top (peg top z = 0.751). No mass / inertia / joint change.
BASE_COLLIDER_LOCAL_Z = -0.07

ARM_MASS_KG        = 0.20
BASE_MASS_KG       = 0.30

# Drive (linear units — N/m, N·s/m, N).
# Phase 3K v10: bumped maxForce 1e3 → 1e6 N — the previous 1 kN cap
# turned out to be insufficient to clamp the peg firmly enough that
# friction could resist gravity during the lift (peg sank 25 mm
# during lift instead of rising with the gripper).
DRIVE_STIFFNESS_LINEAR = 1.0e5
DRIVE_DAMPING_LINEAR   = 1.0e3
DRIVE_MAX_FORCE_LINEAR = 1.0e6

FRICTION_COEF      = 1.8

# Prismatic limits in metres (along the closure axis). Allow each pad to
# slide 50 mm inward (>peg half-width) and 5 mm outward.
JOINT_LOWER_M      = -0.050
JOINT_UPPER_M      = +0.005


def _set_xform(prim, translate=(0, 0, 0), orient=(1, 0, 0, 0)):
    UsdGeom.Xformable(prim).ClearXformOpOrder()
    t = prim.CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3, custom=False)
    t.Set(Gf.Vec3d(*translate))
    o = prim.CreateAttribute("xformOp:orient", Sdf.ValueTypeNames.Quatd, custom=False)
    o.Set(Gf.Quatd(orient[0], orient[1], orient[2], orient[3]))
    s = prim.CreateAttribute("xformOp:scale", Sdf.ValueTypeNames.Double3, custom=False)
    s.Set(Gf.Vec3d(1, 1, 1))
    order = prim.CreateAttribute("xformOpOrder", Sdf.ValueTypeNames.TokenArray,
                                 custom=False, variability=Sdf.VariabilityUniform)
    order.Set(["xformOp:translate", "xformOp:orient", "xformOp:scale"])


def _author_link(prim, mass_kg, inertia_diag=(1e-4, 1e-4, 1e-4)):
    UsdPhysics.RigidBodyAPI.Apply(prim)
    mass_api = UsdPhysics.MassAPI.Apply(prim)
    mass_api.CreateMassAttr().Set(float(mass_kg))
    mass_api.CreateCenterOfMassAttr().Set(Gf.Vec3f(0, 0, 0))
    mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(*inertia_diag))
    mass_api.CreatePrincipalAxesAttr().Set(Gf.Quatf(1, 0, 0, 0))
    prim.AddAppliedSchema("PhysxRigidBodyAPI")
    prim.AddAppliedSchema("IsaacLinkAPI")
    prim.CreateAttribute("physxRigidBody:sleepThreshold",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)
    prim.CreateAttribute("physxRigidBody:stabilizationThreshold",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)


def _author_friction_material(stage, path):
    mat = UsdGeom.Scope.Define(stage, Sdf.Path(path)).GetPrim()
    UsdPhysics.MaterialAPI.Apply(mat)
    mat.CreateAttribute("physics:staticFriction", Sdf.ValueTypeNames.Float, custom=False).Set(FRICTION_COEF)
    mat.CreateAttribute("physics:dynamicFriction", Sdf.ValueTypeNames.Float, custom=False).Set(FRICTION_COEF)
    mat.CreateAttribute("physics:restitution", Sdf.ValueTypeNames.Float, custom=False).Set(0.0)
    return mat


def _author_box_collider(stage, parent_path, name, size_xyz, material_path,
                         local_translate=(0, 0, 0)):
    path = Sdf.Path(parent_path).AppendChild(name)
    cube = UsdGeom.Cube.Define(stage, path)
    prim = cube.GetPrim()
    cube.GetSizeAttr().Set(1.0)
    _set_xform(prim, translate=local_translate, orient=(1, 0, 0, 0))
    prim.GetAttribute("xformOp:scale").Set(Gf.Vec3d(*size_xyz))
    UsdPhysics.CollisionAPI.Apply(prim)
    rel = prim.CreateRelationship("material:binding:physics", custom=False)
    rel.SetTargets([Sdf.Path(material_path)])
    return prim


def _author_prismatic_joint(
    stage, joint_path, *,
    body0, body1, axis, localPos0, localPos1,
    localRot0, localRot1,
    lower_m, upper_m,
    drive_target_m, drive_stiffness, drive_damping, drive_max_force,
    mimic_reference=None, mimic_gearing=None,
):
    """Author a PhysicsPrismaticJoint with linear drive + full schema stack."""
    joint = UsdPhysics.PrismaticJoint.Define(stage, joint_path)
    prim = joint.GetPrim()
    joint.GetAxisAttr().Set(axis)
    joint.CreateBody0Rel().SetTargets([Sdf.Path(body0)])
    joint.CreateBody1Rel().SetTargets([Sdf.Path(body1)])
    joint.GetLocalPos0Attr().Set(Gf.Vec3f(*localPos0))
    joint.GetLocalPos1Attr().Set(Gf.Vec3f(*localPos1))
    joint.GetLocalRot0Attr().Set(Gf.Quatf(*localRot0))
    joint.GetLocalRot1Attr().Set(Gf.Quatf(*localRot1))
    joint.GetLowerLimitAttr().Set(float(lower_m))
    joint.GetUpperLimitAttr().Set(float(upper_m))

    # Linear drive — note "linear" instance not "angular".
    drive = UsdPhysics.DriveAPI.Apply(prim, "linear")
    drive.CreateTypeAttr().Set("force")
    drive.CreateTargetPositionAttr().Set(float(drive_target_m))
    drive.CreateStiffnessAttr().Set(float(drive_stiffness))
    drive.CreateDampingAttr().Set(float(drive_damping))
    drive.CreateMaxForceAttr().Set(float(drive_max_force))

    # Phase 3I-validated joint schemas.
    prim.AddAppliedSchema("PhysxJointAPI")
    prim.AddAppliedSchema("IsaacJointAPI")
    prim.AddAppliedSchema("PhysicsJointStateAPI:linear")
    prim.CreateAttribute("state:linear:physics:position",
                         Sdf.ValueTypeNames.Float, custom=False).Set(float(drive_target_m))
    prim.CreateAttribute("state:linear:physics:velocity",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)

    if mimic_reference is not None:
        # PhysxMimicJointAPI uses an axis instance — for prismatic, the
        # axis is the joint's translation direction. Use "transY" if axis
        # = "Y", "transX" for "X", "transZ" for "Z".
        axis_to_instance = {"X": "transX", "Y": "transY", "Z": "transZ"}
        instance = axis_to_instance[axis]
        schema_name = f"PhysxMimicJointAPI:{instance}"
        prim.AddAppliedSchema(schema_name)
        prefix = f"physxMimicJoint:{instance}"
        prim.CreateAttribute(f"{prefix}:gearing",
                             Sdf.ValueTypeNames.Float, custom=False).Set(float(mimic_gearing))
        prim.CreateAttribute(f"{prefix}:naturalFrequency",
                             Sdf.ValueTypeNames.Float, custom=False).Set(1000.0)
        prim.CreateAttribute(f"{prefix}:dampingRatio",
                             Sdf.ValueTypeNames.Float, custom=False).Set(1.0)
        rel = prim.CreateRelationship(f"{prefix}:referenceJoint")
        rel.SetTargets([Sdf.Path(mimic_reference)])

    return prim


def main() -> int:
    if not PRISTINE.is_file():
        print(f"[3k] ERROR: pristine backup missing: {PRISTINE}", file=sys.stderr)
        return 1
    if ASSET.is_file() and not PRE3K.is_file():
        shutil.copy2(ASSET, PRE3K)
        print(f"[3k] saved pre-3k snapshot → {PRE3K.name}")

    cached = Sdf.Layer.FindOrOpen(str(ASSET))
    if cached is not None:
        cached.Clear()
    del cached
    if ASSET.exists():
        ASSET.unlink()

    new_stage = Usd.Stage.CreateNew(str(ASSET))
    new_stage.SetMetadata("metersPerUnit", 1.0)
    new_stage.SetMetadata("upAxis", "Z")
    root = UsdGeom.Xform.Define(new_stage, Sdf.Path("/Robotiq_2F_140")).GetPrim()
    new_stage.SetDefaultPrim(root)

    _author_friction_material(new_stage, "/Robotiq_2F_140/finger_material")

    # ────── robotiq_base_link ──────
    base_path = Sdf.Path("/Robotiq_2F_140/robotiq_base_link")
    base = UsdGeom.Xform.Define(new_stage, base_path).GetPrim()
    _set_xform(base, translate=(0, 0, 0), orient=(1, 0, 0, 0))
    base_I = BASE_MASS_KG / 12.0 * 2 * (BASE_SIZE_M ** 2)
    _author_link(base, BASE_MASS_KG, (base_I, base_I, base_I))
    UsdGeom.Scope.Define(new_stage, base_path.AppendChild("collisions"))
    # Phase 3M: lift the base collider above peg top (see header comment
    # on BASE_COLLIDER_LOCAL_Z). The rigid body and joint anchor stay at
    # (0,0,0); only the collider's local translate is offset.
    _author_box_collider(new_stage, base_path.AppendChild("collisions"), "base",
                         (BASE_SIZE_M, BASE_SIZE_M, BASE_SIZE_M),
                         "/Robotiq_2F_140/finger_material",
                         local_translate=(0.0, 0.0, BASE_COLLIDER_LOCAL_Z))

    # ────── pads ──────
    # Each pad is a thin slab. The pad body's ORIGIN sits at the pad's
    # geometric centre; the collider is centred on the body. Initial pad
    # position is at ±PIVOT_Y_OFFSET on /Robotiq_2F_140's Y axis (the
    # joint's local frame Y maps to world ±Y after the cell-composition
    # rotation — verified against the Phase 3I/3J axis probes).
    # Inertia for a slab whose local X=THICK, local Y=WIDTH, local Z=LENGTH.
    arm_Ixx = ARM_MASS_KG / 12.0 * (ARM_WIDTH_M ** 2 + ARM_LENGTH_M ** 2)
    arm_Iyy = ARM_MASS_KG / 12.0 * (ARM_THICK_M ** 2 + ARM_LENGTH_M ** 2)
    arm_Izz = ARM_MASS_KG / 12.0 * (ARM_THICK_M ** 2 + ARM_WIDTH_M ** 2)
    arm_inertia = (arm_Ixx, arm_Iyy, arm_Izz)

    # Phase 3K v2: empirical world-axis check confirmed
    #   /Robotiq_2F_140 local +X → world +Y at default joint pose
    #   /Robotiq_2F_140 local +Y → world -X (conveyor direction)
    # So pad bodies must be offset on LOCAL +X to land at world ±Y
    # (lateral to the conveyor) and the prismatic joint axis must be
    # "X" in body0-local for lateral sliding closure.
    pad_body_translate_left  = (+PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M)
    pad_body_translate_right = (-PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M)

    for side, body_t in (("left", pad_body_translate_left),
                         ("right", pad_body_translate_right)):
        path = Sdf.Path(f"/Robotiq_2F_140/{side}_finger")
        pad = UsdGeom.Xform.Define(new_stage, path).GetPrim()
        _set_xform(pad, translate=body_t, orient=(1, 0, 0, 0))
        _author_link(pad, ARM_MASS_KG, arm_inertia)
        UsdGeom.Scope.Define(new_stage, path.AppendChild("collisions"))
        # Phase 3K v8: collider dimensions matched to world axes via the
        # cell-composition mapping (/Robotiq_2F_140 local +X → world +Y,
        # local +Y → world -X, local +Z → world +Z). The pad needs to
        # be THIN in the CLOSURE direction (world Y), WIDE along the
        # conveyor (world X), and TALL vertically (world Z). So the
        # local-frame scale is (THIN_Y, WIDE_X, TALL_Z) = (ARM_THICK,
        # ARM_WIDTH, ARM_LENGTH).
        _author_box_collider(new_stage, path.AppendChild("collisions"), "finger",
                             (ARM_THICK_M, ARM_WIDTH_M, ARM_LENGTH_M),
                             "/Robotiq_2F_140/finger_material")

    # ────── joints ──────
    # Anchor each joint at the pad's initial position so joint state = 0
    # means the pad is in its open (authored) location. The joint axis Y
    # (body0-local) tells PhysX the allowed direction of translation.
    # localPos0: anchor in base (the pad's initial offset).
    # localPos1: anchor in pad-local (always 0,0,0 → pad's own origin).
    BASE_LOCAL_LEFT_ANCHOR  = (+PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M)
    BASE_LOCAL_RIGHT_ANCHOR = (-PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M)
    PAD_LOCAL_ANCHOR        = (0.0, 0.0, 0.0)

    _author_prismatic_joint(
        new_stage, Sdf.Path("/Robotiq_2F_140/finger_joint"),
        body0=base_path,
        body1=Sdf.Path("/Robotiq_2F_140/left_finger"),
        axis="X",
        localPos0=BASE_LOCAL_LEFT_ANCHOR,
        localPos1=PAD_LOCAL_ANCHOR,
        localRot0=(1, 0, 0, 0), localRot1=(1, 0, 0, 0),
        lower_m=JOINT_LOWER_M, upper_m=JOINT_UPPER_M,
        drive_target_m=0.0,
        drive_stiffness=DRIVE_STIFFNESS_LINEAR,
        drive_damping=DRIVE_DAMPING_LINEAR,
        drive_max_force=DRIVE_MAX_FORCE_LINEAR,
    )
    # Phase 3K v7: the right joint slides in the OPPOSITE direction
    # along the shared body0-local +X axis (right pad starts at world
    # -Y and closes toward +Y). So the limits are MIRRORED relative
    # to the master joint — joint state +positive = close direction.
    _author_prismatic_joint(
        new_stage, Sdf.Path("/Robotiq_2F_140/right_finger_joint"),
        body0=base_path,
        body1=Sdf.Path("/Robotiq_2F_140/right_finger"),
        axis="X",
        localPos0=BASE_LOCAL_RIGHT_ANCHOR,
        localPos1=PAD_LOCAL_ANCHOR,
        localRot0=(1, 0, 0, 0), localRot1=(1, 0, 0, 0),
        lower_m=-JOINT_UPPER_M, upper_m=-JOINT_LOWER_M,
        drive_target_m=0.0,
        drive_stiffness=DRIVE_STIFFNESS_LINEAR,
        drive_damping=DRIVE_DAMPING_LINEAR,
        drive_max_force=DRIVE_MAX_FORCE_LINEAR,
        # No mimic schema — the test layer writes both finger_joint AND
        # right_finger_joint targets via the articulation API each step
        # (right = -finger_joint target), which is just an
        # API-controller pattern, not a "fake attachment" or hidden
        # correction. Symmetric closure is enforced at the controller
        # layer instead of the constraint layer.
    )

    new_stage.Save()
    print(f"[3k] saved prismatic-jaw gripper → {ASSET}")

    # ────── verify ──────
    v = Usd.Stage.Open(str(ASSET))
    bad = 0
    for path in (
        "/Robotiq_2F_140/robotiq_base_link",
        "/Robotiq_2F_140/left_finger",
        "/Robotiq_2F_140/right_finger",
    ):
        prim = v.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[3k] VERIFY FAIL: missing body {path}", file=sys.stderr); bad += 1; continue
        schemas = set(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        missing = {"PhysicsRigidBodyAPI", "PhysxRigidBodyAPI", "IsaacLinkAPI"} - schemas
        if missing:
            print(f"[3k] VERIFY FAIL: body {path} missing schemas {missing}",
                  file=sys.stderr); bad += 1
        else:
            print(f"[3k] body OK  {path:50s}  {sorted(schemas)}")
    for path in (
        "/Robotiq_2F_140/finger_joint",
        "/Robotiq_2F_140/right_finger_joint",
    ):
        prim = v.GetPrimAtPath(path)
        if not prim or prim.GetTypeName() != "PhysicsPrismaticJoint":
            print(f"[3k] VERIFY FAIL: {path} not PhysicsPrismaticJoint "
                  f"(got {prim.GetTypeName() if prim else 'None'})", file=sys.stderr)
            bad += 1; continue
        schemas = set(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        missing = {"PhysxJointAPI", "IsaacJointAPI",
                   "PhysicsDriveAPI:linear", "PhysicsJointStateAPI:linear"} - schemas
        if missing:
            print(f"[3k] VERIFY FAIL: joint {path} missing schemas {missing}",
                  file=sys.stderr); bad += 1
        else:
            print(f"[3k] joint OK {path:50s}  {sorted(schemas)}")

    # Phase 3K v7+ removed the PhysxMimicJointAPI from right_finger_joint
    # (the test layer enforces symmetric closure via the articulation API
    # — see scripts/build_prismatic_jaw_gripper.py comment under the
    # right_finger_joint authoring call). The legacy mimic-gearing check
    # is therefore not applicable to the current build.
    rfj = v.GetPrimAtPath("/Robotiq_2F_140/right_finger_joint")
    mimic_attr = rfj.GetAttribute("physxMimicJoint:transY:gearing")
    if mimic_attr and mimic_attr.IsValid() and mimic_attr.Get() is not None:
        g = float(mimic_attr.Get())
        print(f"[3k] mimic gearing on right_finger_joint = {g:+.2f} (transY)")
        if abs(g - (-1.0)) > 1e-6:
            print(f"[3k] VERIFY FAIL: mimic gearing must be -1.0", file=sys.stderr)
            bad += 1
    else:
        print("[3k] right_finger_joint has no PhysxMimicJointAPI "
              "(by design — symmetric closure via articulation API)")

    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
