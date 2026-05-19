#!/usr/bin/env python3
"""Phase 3G — lateral-clamping parallel-jaw gripper.

Design contract (from the Phase 3G directive)
---------------------------------------------

1. The pads face INWARD LATERALLY at the open pose. Closure motion
   applies force DIRECTLY into the peg's side faces. No downward-facing
   pad normals (which Phase 3F demonstrated produced only transient
   bump contacts, never a sustained grasp).

2. The articulation schema stack matches the validated Phase 3F set:
     bodies → PhysicsRigidBodyAPI, PhysxRigidBodyAPI, IsaacLinkAPI,
              PhysicsMassAPI
     joints → PhysicsRevoluteJoint (typed), PhysxJointAPI,
              IsaacJointAPI, PhysicsDriveAPI:angular,
              PhysicsJointStateAPI:angular

3. The integration interfaces are preserved:
     - same ee_link attachment (robotiq_base_link is the body referenced
       by the cell's ee_joint);
     - same finger_joint control path (one master drive joint named
       ``finger_joint``);
     - identical prim hierarchy expectations (/Robotiq_2F_140/
       robotiq_base_link, /finger_joint, /right_finger_joint);
     - same trajectory player interface (writes the master joint's
       drive:angular:physics:targetPosition; no per-pad attributes);
     - validator-compatible link tagging (everything under /World/Robot
       inherits the Robot collision group from the cell mount).

Topology
--------

Two long rigid arms, each a sibling of the base under /Robotiq_2F_140.
Pivots at the base's bottom-edge, ±PIVOT_Y_OFFSET on the Y axis. Each
arm extends downward in -Z. The pad face is the INNER X face of the
arm body — the face whose outward normal points toward the OTHER arm.

  /Robotiq_2F_140/
    robotiq_base_link                  (rigid body, mount-stay)
      collisions/base                  (small Cube collider)
    left_finger                        (rigid body, the LEFT arm)
      collisions/finger                (Cube collider, friction-bound)
    right_finger                       (rigid body, the RIGHT arm)
      collisions/finger                (Cube collider, friction-bound)
    finger_joint                       (master revolute, body0=base,
                                        body1=left_finger, drive)
    right_finger_joint                 (revolute, body0=base,
                                        body1=right_finger, mimic gear=-1)

At finger_joint = 0 the arms hang straight down. At finger_joint = -θ
(negative close convention — see geometry note) the arms swing INWARD,
the pad faces move toward each other in the closure direction. The
pad faces' WORLD orientation rotates by θ as the arm rotates; for the
~0.20–0.30 rad closure range we use, the pad face normal stays within
~17° of its initial direction → still a primarily-lateral clamp.

Geometry numbers
----------------

  ARM_LENGTH         = 0.20  m
  ARM_WIDTH          = 0.06  m   (along world X / conveyor direction)
  ARM_THICK          = 0.015 m   (along closure direction)
  PIVOT_Y_OFFSET     = 0.045 m   (each pivot 45 mm off centerline)
  PIVOT_Z_OFFSET     = 0     m   (pivots at base origin Z)
  open pad-face gap  ≈ 75 mm     (50 mm peg + 25 mm clearance)
  closed pad-face gap≈ 26 mm     (at finger_joint = -0.25 rad)
                                   — well under the 45 mm "closed < peg-5mm" gate.

Drive
-----

  drive_stiffness    = 1e5
  drive_damping      = 1e4
  drive_max_force    = 1e6
  drive_type         = "force"
  joint_axis         = "X"   (body0-local; the cell composes ee_link so
                              body0-local X maps to world ±something close to
                              the gripper's lateral closure direction — exact
                              sign empirically tuned via the YAML's
                              close_position_rad sign)

Material
--------

  static + dynamic friction = 1.8 (retained from Phase 3D, sufficient
  for a 100 g peg with even 1 N of normal force).
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
PRE3G    = ASSET.with_suffix(ASSET.suffix + ".pre3g")


# Geometry (all in metres)
ARM_LENGTH_M       = 0.20
ARM_WIDTH_M        = 0.06
                            # gripper settles 20 mm behind IK-target X
                            # under arm load and the descent pushes the
                            # peg back by another 50 mm; net pad-peg X
                            # overlap was only ~5 mm with 60 mm pads.
                            # 150 mm gives a >50 mm safety margin even
                            # with a peg that has drifted -70 mm.
ARM_THICK_M        = 0.015  # along closure direction
BASE_SIZE_M        = 0.020
                            # don't intersect base collider at init.
PIVOT_Y_OFFSET_M   = 0.060  # ±60 mm; base half-width = 10 mm and finger
                            # half-width = 30 mm, so center-to-center
                            # spacing of 60 mm leaves a 20 mm gap between
                            # base and finger colliders → no init overlap.
PIVOT_Z_OFFSET_M   = 0.0    # pivots at base origin Z

ARM_MASS_KG        = 0.20
                            # 0.05 kg arms with stiff 1e5 drives can
                            # be numerically unstable (very small
                            # inertia relative to torque). 200 g per
                            # arm matches the upstream 2F-140 link mass.
BASE_MASS_KG       = 0.30

# Phase 3J drive tuning. The damp=1e5 + stiff=1e6 combination gave the
# first ever 55 mm peg lift (max_z=0.7553). Lower damping made the
# pads bounce on the peg's contact surface; higher damping settles
# them flat.
DRIVE_STIFFNESS    = 1.0e6
DRIVE_DAMPING      = 1.0e5
DRIVE_MAX_FORCE    = 1.0e6

# Pad material
FRICTION_COEF      = 10.0

# Lower / upper limits in degrees per UsdPhysics convention. Permit the
# arms to swing inward enough to clamp + open enough to release.
JOINT_LOWER_DEG    = -30.0   # close direction (≈ -0.52 rad)
JOINT_UPPER_DEG    = +5.0    # tiny over-open buffer


def _set_xform(prim: Usd.Prim, translate=(0, 0, 0), orient=(1, 0, 0, 0)):
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


def _author_link(prim: Usd.Prim, mass_kg: float,
                 inertia_diag=(1.0e-4, 1.0e-4, 1.0e-4)):
    """Apply the full Phase 3F-validated link schema stack with VALID inertia.

    Phase 3H discovery: when MassAPI's centerOfMass / diagonalInertia /
    principalAxes attributes aren't explicitly authored, the composed
    cell shows centerOfMass = (-inf, -inf, -inf) and diagonalInertia =
    (0, 0, 0). PhysX cannot couple such a degenerate body into an
    articulation — it stays attached topologically (the joint shows up
    in dof_names) but the body itself doesn't follow the kinematic
    chain. This was the second half of the Phase 3G "fingers flying
    free" pattern. Set valid values explicitly via the typed MassAPI.
    """
    UsdPhysics.RigidBodyAPI.Apply(prim)
    mass_api = UsdPhysics.MassAPI.Apply(prim)
    mass_api.CreateMassAttr().Set(float(mass_kg))
    mass_api.CreateCenterOfMassAttr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(*inertia_diag))
    mass_api.CreatePrincipalAxesAttr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    prim.AddAppliedSchema("PhysxRigidBodyAPI")
    prim.AddAppliedSchema("IsaacLinkAPI")
    prim.CreateAttribute("physxRigidBody:sleepThreshold",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)
    prim.CreateAttribute("physxRigidBody:stabilizationThreshold",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)


def _author_friction_material(stage, path):
    mat = UsdGeom.Scope.Define(stage, Sdf.Path(path)).GetPrim()
    UsdPhysics.MaterialAPI.Apply(mat)
    mat.CreateAttribute("physics:staticFriction", Sdf.ValueTypeNames.Float, custom=False)\
       .Set(FRICTION_COEF)
    mat.CreateAttribute("physics:dynamicFriction", Sdf.ValueTypeNames.Float, custom=False)\
       .Set(FRICTION_COEF)
    mat.CreateAttribute("physics:restitution", Sdf.ValueTypeNames.Float, custom=False)\
       .Set(0.0)
    return mat


def _author_box_collider(stage, parent_path, name, size_xyz, material_path,
                         local_translate=(0, 0, 0)):
    path = Sdf.Path(parent_path).AppendChild(name)
    cube = UsdGeom.Cube.Define(stage, path)
    prim = cube.GetPrim()
    cube.GetSizeAttr().Set(1.0)
    _set_xform(prim, translate=local_translate, orient=(1, 0, 0, 0))
    s = prim.GetAttribute("xformOp:scale")
    s.Set(Gf.Vec3d(*size_xyz))
    UsdPhysics.CollisionAPI.Apply(prim)
    rel = prim.CreateRelationship("material:binding:physics", custom=False)
    rel.SetTargets([Sdf.Path(material_path)])
    return prim


def _author_revolute_joint(
    stage, joint_path, *,
    body0, body1, axis, localPos0, localPos1,
    localRot0, localRot1,
    lower_deg, upper_deg,
    drive_target, drive_stiffness, drive_damping, drive_max_force,
    mimic_reference=None, mimic_gearing=None,
):
    """Author a revolute joint with the full Phase 3F-validated schema stack."""
    joint = UsdPhysics.RevoluteJoint.Define(stage, joint_path)
    prim = joint.GetPrim()
    joint.GetAxisAttr().Set(axis)
    joint.CreateBody0Rel().SetTargets([Sdf.Path(body0)])
    joint.CreateBody1Rel().SetTargets([Sdf.Path(body1)])
    joint.GetLocalPos0Attr().Set(Gf.Vec3f(*localPos0))
    joint.GetLocalPos1Attr().Set(Gf.Vec3f(*localPos1))
    joint.GetLocalRot0Attr().Set(Gf.Quatf(*localRot0))
    joint.GetLocalRot1Attr().Set(Gf.Quatf(*localRot1))
    joint.GetLowerLimitAttr().Set(float(lower_deg))
    joint.GetUpperLimitAttr().Set(float(upper_deg))

    drive = UsdPhysics.DriveAPI.Apply(prim, "angular")
    drive.CreateTypeAttr().Set("force")
    drive.CreateTargetPositionAttr().Set(float(drive_target))
    drive.CreateStiffnessAttr().Set(float(drive_stiffness))
    drive.CreateDampingAttr().Set(float(drive_damping))
    drive.CreateMaxForceAttr().Set(float(drive_max_force))

    # Phase 3G validated joint schemas — match the working arm joints.
    prim.AddAppliedSchema("PhysxJointAPI")
    prim.AddAppliedSchema("IsaacJointAPI")
    prim.AddAppliedSchema("PhysicsJointStateAPI:angular")
    prim.CreateAttribute("state:angular:physics:position",
                         Sdf.ValueTypeNames.Float, custom=False).Set(float(drive_target))
    prim.CreateAttribute("state:angular:physics:velocity",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)

    if mimic_reference is not None:
        prim.AddAppliedSchema("PhysxMimicJointAPI:rotX")
        prim.CreateAttribute("physxMimicJoint:rotX:gearing",
                             Sdf.ValueTypeNames.Float, custom=False).Set(float(mimic_gearing))
        prim.CreateAttribute("physxMimicJoint:rotX:naturalFrequency",
                             Sdf.ValueTypeNames.Float, custom=False).Set(1000.0)
        prim.CreateAttribute("physxMimicJoint:rotX:dampingRatio",
                             Sdf.ValueTypeNames.Float, custom=False).Set(1.0)
        rel = prim.CreateRelationship("physxMimicJoint:rotX:referenceJoint")
        rel.SetTargets([Sdf.Path(mimic_reference)])

    return prim


def main() -> int:
    if not PRISTINE.is_file():
        print(f"[3g] ERROR: pristine backup missing: {PRISTINE}", file=sys.stderr)
        return 1

    # Phase 3G snapshot of the current state.
    if ASSET.is_file() and not PRE3G.is_file():
        shutil.copy2(ASSET, PRE3G)
        print(f"[3g] saved pre-3g snapshot → {PRE3G.name}")

    # Drop the existing file (release any cached layer first).
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

    # ────── friction material ──────
    _author_friction_material(new_stage, "/Robotiq_2F_140/finger_material")

    # ────── robotiq_base_link ──────
    base_path = Sdf.Path("/Robotiq_2F_140/robotiq_base_link")
    base = UsdGeom.Xform.Define(new_stage, base_path).GetPrim()
    _set_xform(base, translate=(0, 0, 0), orient=(1, 0, 0, 0))
    # cube I = m/12 × (a²+b²); a=b=c=BASE_SIZE_M
    base_I = BASE_MASS_KG / 12.0 * 2 * (BASE_SIZE_M ** 2)
    _author_link(base, BASE_MASS_KG, inertia_diag=(base_I, base_I, base_I))
    UsdGeom.Scope.Define(new_stage, base_path.AppendChild("collisions"))
    _author_box_collider(new_stage, base_path.AppendChild("collisions"), "base",
                         (BASE_SIZE_M, BASE_SIZE_M, BASE_SIZE_M),
                         "/Robotiq_2F_140/finger_material")

    # ────── arms ──────
    # Each arm is a Xform sibling of base, with identity orient. The body
    # origin is at the JOINT ANCHOR (top of arm); the collider Cube child
    # is offset down by ARM_LENGTH/2 so its centre is at the arm's middle.
    # Pad face = inner X face of the collider, perpendicular to the
    # closure direction.
    # v7: bodies at translate (0,0,0) matching the upstream 2F-140
    # convention; collider offsets carry the visual finger position.
    arm_collider_offset_left  = (0.0, +PIVOT_Y_OFFSET_M, PIVOT_Z_OFFSET_M - ARM_LENGTH_M / 2)
    arm_collider_offset_right = (0.0, -PIVOT_Y_OFFSET_M, PIVOT_Z_OFFSET_M - ARM_LENGTH_M / 2)
    arm_body_translate_left   = (0.0, 0.0, 0.0)
    arm_body_translate_right  = (0.0, 0.0, 0.0)

    # Arm inertia tensor for a thin rectangular slab (W=THICK, L=WIDTH, H=LENGTH):
    #   I_xx = m/12 × (W² + L²); I_yy = m/12 × (W² + H²); I_zz = m/12 × (L² + H²)
    # local body frame: X→THICK, Y→WIDTH (across-conveyor), Z→LENGTH (down).
    arm_Ixx = ARM_MASS_KG / 12.0 * (ARM_THICK_M ** 2 + ARM_WIDTH_M ** 2)
    arm_Iyy = ARM_MASS_KG / 12.0 * (ARM_THICK_M ** 2 + ARM_LENGTH_M ** 2)
    arm_Izz = ARM_MASS_KG / 12.0 * (ARM_WIDTH_M ** 2 + ARM_LENGTH_M ** 2)

    for side, body_t, col_t in (
        ("left",  arm_body_translate_left,  arm_collider_offset_left),
        ("right", arm_body_translate_right, arm_collider_offset_right),
    ):
        path = Sdf.Path(f"/Robotiq_2F_140/{side}_finger")
        arm = UsdGeom.Xform.Define(new_stage, path).GetPrim()
        _set_xform(arm, translate=body_t, orient=(1, 0, 0, 0))
        _author_link(arm, ARM_MASS_KG, inertia_diag=(arm_Ixx, arm_Iyy, arm_Izz))
        UsdGeom.Scope.Define(new_stage, path.AppendChild("collisions"))
        # Collider extents: local X = ARM_THICK_M (closure thickness),
        # local Y = ARM_WIDTH_M (cross-conveyor breadth), local Z = ARM_LENGTH_M.
        _author_box_collider(new_stage, path.AppendChild("collisions"), "finger",
                             (ARM_THICK_M, ARM_WIDTH_M, ARM_LENGTH_M),
                             "/Robotiq_2F_140/finger_material",
                             local_translate=col_t)

    # ────── joints ──────
    # Both anchors at (0, ±PIVOT_Y_OFFSET, 0) in /Robotiq_2F_140 frame —
    # body0 (base) has identity orient so anchor in base-local coincides
    # with anchor in /Robotiq_2F_140 frame; body1 (each arm) has identity
    # orient and its body origin is AT the anchor, so localPos1 = (0,0,0).
    # v7: with body translates = 0 on both sides, joint anchors are
    # given by localPos on each side, and they must coincide in
    # /Robotiq_2F_140 frame. We use the same anchor on body0 and body1
    # (the pivot location), so the joint constraint is satisfied at
    # init without any translation gap.
    BASE_LOCAL_LEFT_ANCHOR  = (0.0, +PIVOT_Y_OFFSET_M, PIVOT_Z_OFFSET_M)
    BASE_LOCAL_RIGHT_ANCHOR = (0.0, -PIVOT_Y_OFFSET_M, PIVOT_Z_OFFSET_M)
    LEFT_ARM_LOCAL_ANCHOR   = (0.0, +PIVOT_Y_OFFSET_M, PIVOT_Z_OFFSET_M)
    RIGHT_ARM_LOCAL_ANCHOR  = (0.0, -PIVOT_Y_OFFSET_M, PIVOT_Z_OFFSET_M)

    # Axis "X" — rotation about base-local X. With base orient = identity,
    # this is base-local +X. The arm swings in the body's local Y-Z plane,
    # which after the cell's ee_link / ee_joint composition maps to the
    # WORLD closure direction. Sign of close_position_rad in the YAML is
    # tuned empirically (Phase 3G v1 starts at -0.25 rad ≈ -14°).
    _author_revolute_joint(
        new_stage, Sdf.Path("/Robotiq_2F_140/finger_joint"),
        body0=base_path,
        body1=Sdf.Path("/Robotiq_2F_140/left_finger"),
        axis="Z",
        localPos0=BASE_LOCAL_LEFT_ANCHOR,
        localPos1=LEFT_ARM_LOCAL_ANCHOR,
        localRot0=(1, 0, 0, 0),
        localRot1=(1, 0, 0, 0),
        lower_deg=JOINT_LOWER_DEG, upper_deg=JOINT_UPPER_DEG,
        drive_target=0.0,
        drive_stiffness=DRIVE_STIFFNESS,
        drive_damping=DRIVE_DAMPING,
        drive_max_force=DRIVE_MAX_FORCE,
    )
    _author_revolute_joint(
        new_stage, Sdf.Path("/Robotiq_2F_140/right_finger_joint"),
        body0=base_path,
        body1=Sdf.Path("/Robotiq_2F_140/right_finger"),
        axis="Z",
        localPos0=BASE_LOCAL_RIGHT_ANCHOR,
        localPos1=RIGHT_ARM_LOCAL_ANCHOR,
        localRot0=(1, 0, 0, 0),
        localRot1=(1, 0, 0, 0),
        lower_deg=JOINT_LOWER_DEG, upper_deg=JOINT_UPPER_DEG,
        drive_target=0.0,
        drive_stiffness=DRIVE_STIFFNESS,
        drive_damping=DRIVE_DAMPING,
        drive_max_force=DRIVE_MAX_FORCE,
        mimic_reference="/Robotiq_2F_140/finger_joint",
        mimic_gearing=-1.0,
    )

    new_stage.Save()
    print(f"[3g] saved lateral-clamp gripper → {ASSET}")

    # ────── verify ──────
    verify = Usd.Stage.Open(str(ASSET))
    for path in (
        "/Robotiq_2F_140/robotiq_base_link",
        "/Robotiq_2F_140/left_finger",
        "/Robotiq_2F_140/right_finger",
    ):
        prim = verify.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[3g] VERIFY FAIL: missing prim: {path}", file=sys.stderr)
            return 1
        schemas = set(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        for required in ("PhysicsRigidBodyAPI", "PhysxRigidBodyAPI", "IsaacLinkAPI"):
            if required not in schemas:
                print(f"[3g] VERIFY FAIL: {path} missing schema {required}; "
                      f"have {schemas}", file=sys.stderr)
                return 1
        print(f"[3g] body OK  {path:50s}  schemas={sorted(schemas)}")

    for path in (
        "/Robotiq_2F_140/finger_joint",
        "/Robotiq_2F_140/right_finger_joint",
    ):
        prim = verify.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[3g] VERIFY FAIL: missing joint: {path}", file=sys.stderr)
            return 1
        schemas = set(prim.GetPrimTypeInfo().GetAppliedAPISchemas())
        for required in (
            "PhysxJointAPI", "IsaacJointAPI",
            "PhysicsDriveAPI:angular", "PhysicsJointStateAPI:angular",
        ):
            if required not in schemas:
                print(f"[3g] VERIFY FAIL: {path} missing schema {required}; "
                      f"have {schemas}", file=sys.stderr)
                return 1
        print(f"[3g] joint OK {path:50s}  schemas={sorted(schemas)}")

    rfj = verify.GetPrimAtPath("/Robotiq_2F_140/right_finger_joint")
    g = float(rfj.GetAttribute("physxMimicJoint:rotX:gearing").Get())
    print(f"[3g] mimic gearing on right_finger_joint = {g:+.2f}")
    if abs(g - (-1.0)) > 1e-6:
        print(f"[3g] VERIFY FAIL: mimic gearing must be -1.0", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
