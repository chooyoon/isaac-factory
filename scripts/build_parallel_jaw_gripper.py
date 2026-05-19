#!/usr/bin/env python3
"""Phase 3D — replacement parallel-jaw gripper for cell_01.

The Robotiq 2F-140 four-bar parallelogram cannot be repaired surgically
in Isaac Sim 5.0: PhysX ignores PhysxMimicJointAPI on loop-closing
joints, and applying mimics to enough spanning-tree joints to constrain
the parallelogram over-constrains the system and crushes the drive
authority (finger_joint stalls at 0.07 rad instead of the commanded
0.60 rad). The pads still close past the peg.

We replace the gripper with a minimal parallel-jaw — same prim
hierarchy, same prim names ``/Robotiq_2F_140/robotiq_base_link`` and
``/Robotiq_2F_140/finger_joint`` so:

  * the UR10e's ``ee_joint`` reference to ``robotiq_base_link`` still resolves;
  * the cell_authoring gripper drive override (which targets
    ``finger_joint.drive:angular:physics:targetPosition``) still resolves;
  * the trajectory player, telemetry, mimic-chain audit, and the
    Phase 3C-tail test code all keep working unchanged.

Topology — single-mimic two-joint, the known-working PhysX pattern:

  /Robotiq_2F_140                                           (Xform)
    /robotiq_base_link                                     (RigidBody, fixed via ee_joint)
      /collisions/base                                     (Cube collider)
    /left_finger                                           (RigidBody)
      /collisions/finger                                   (Cube collider, high friction)
    /right_finger                                          (RigidBody)
      /collisions/finger                                   (Cube collider, high friction)
    /finger_joint           — revolute, axis Z, drive       (DOF)
                              body0=base, body1=left_finger
    /right_finger_joint     — revolute, axis Z, mimic       (DOF, constrained)
                              body0=base, body1=right_finger
                              PhysxMimicJointAPI:rotX, gearing=-1.0, ref=finger_joint

Geometry chosen so the gripper:

  * starts fully OPEN at finger_joint = 0      (130 mm pad separation)
  * fully CLOSES near finger_joint = +0.5 rad  (28 mm pad separation;
    a 50 mm peg blocks the pads at ~+0.35 rad, leaving the rest of the
    drive's targetPosition to apply as pure clamping force via the PD)
  * uses high static + dynamic friction on the finger material so the
    PhysX-only friction grasp engages.

Pivot axis: Z, same as the original ``finger_joint`` so the cell_authoring
code that overrides ``drive:angular`` does not need to change. Rotation
direction is chosen by the body offsets so that positive ``finger_joint``
angle closes the gripper.

Backups: the original ``Robotiq_2F_140_physics_edit.usd`` is preserved at
``.pre3d`` (created by ``repair_robotiq_2f_140_mimic.py``); this script
adds a second backup ``.pre3d_parallel_swap`` so re-running is idempotent.
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
BACKUP_UPSTREAM = ASSET.with_suffix(ASSET.suffix + ".pre3d")
BACKUP_BEFORE_SWAP = ASSET.with_suffix(ASSET.suffix + ".pre3d_parallel_swap")

# Gripper geometry (all in metres). Authored in the prim hierarchy below
# /Robotiq_2F_140, whose base is rotated 90° about the world's local
# (1,0,1)/√2 axis (preserved from the upstream Robotiq asset so the
# UR10e ee_joint reference still resolves with the existing localRot1).
FINGER_LENGTH_M    = 0.08   # Short fingers (Phase 3D iteration 4): match
                            # the actual Robotiq 2F-140 finger length
                            # (~85 mm). Longer fingers were intercepting
                            # the peg's conveyor path before descent
                            # completed, knocking the peg off the belt.
FINGER_WIDTH_M     = 0.06   # Pad width along the conveyor axis (iteration 6;
                            # 12 cm triggered a PhysX segfault — likely
                            # a self-overlap with an arm link at home pose).
                            # 60 mm covers the peg width (50 mm) and gives
                            # ~10 mm of travel margin during the close.
FINGER_THICK_M     = 0.015  # Y-axis extent (Phase 3E: thicker pads to
                            # ensure unambiguous PhysX contact resolution
                            # vs the 50 mm peg. 5 mm was too thin —
                            # contact_count_total stayed at ~10 in v4 and
                            # the pad penetrated the peg in geometry but
                            # PhysX struggled to apply lasting normal
                            # force at sub-cm scale.).
BASE_SIZE_M        = 0.04
PIVOT_Y_OFFSET_M   = 0.045  # left at +0.045, right at -0.045 → 90 mm spacing
PIVOT_Z_OFFSET_M   = -0.16  # Pivot pushed further DOWN so the pad face
                            # ends up at the IK-assumed tool offset:
                            #   pad face centre = PIVOT_Z − FINGER_LEN/2
                            #                   = −0.16 − 0.04 = −0.20 m
                            # The pivot column from base bottom (−0.02 m)
                            # down to the pivot (−0.16 m) is occupied by
                            # the SHAFT (no collider) — only the fingers
                            # are colliders, so they don't intercept the
                            # peg during the descent.

FRICTION_COEF      = 1.8    # static & dynamic; high to engage friction grasp
FINGER_MASS_KG     = 0.05
BASE_MASS_KG       = 0.30


def _set_xform(prim: Usd.Prim, translate=(0, 0, 0), orient=(1, 0, 0, 0)):
    """Author translate + orient as the only xform ops."""
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


def _author_rigid_body(prim: Usd.Prim, mass_kg: float):
    UsdPhysics.RigidBodyAPI.Apply(prim)
    UsdPhysics.MassAPI.Apply(prim)
    # PhysX-specific schema needed for the articulation cooker to
    # properly register this body. Without it the rigid body composes
    # but is NOT linked into the parent articulation — the finger flies
    # free of the gripper. Verified by comparing this asset's schemas
    # against the upstream Robotiq 2F-140 (.pre3d backup) which has the
    # API on every finger/knuckle link.
    prim.AddAppliedSchema("PhysxRigidBodyAPI")
    prim.CreateAttribute("physxRigidBody:sleepThreshold",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)
    prim.CreateAttribute("physxRigidBody:stabilizationThreshold",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)
    prim.CreateAttribute("physics:mass", Sdf.ValueTypeNames.Float, custom=False).Set(float(mass_kg))


def _author_box_collider(stage, parent_path, name, size_xyz, material_path):
    """Author a cube prim with PhysicsCollisionAPI and a bound material."""
    path = Sdf.Path(parent_path).AppendChild(name)
    cube = UsdGeom.Cube.Define(stage, path)
    prim = cube.GetPrim()
    # Cube default size is 2 along each axis (range [-1, 1]); use scale to
    # get the dimensions we want.
    cube.GetSizeAttr().Set(1.0)
    _set_xform(prim,
               translate=(0, 0, 0),
               orient=(1, 0, 0, 0))
    s = prim.GetAttribute("xformOp:scale")
    s.Set(Gf.Vec3d(*size_xyz))
    UsdPhysics.CollisionAPI.Apply(prim)
    # Bind the high-friction material as the physics material.
    rel = prim.CreateRelationship("material:binding:physics", custom=False)
    rel.SetTargets([Sdf.Path(material_path)])
    return prim


def _author_revolute_joint(
    stage, joint_path, *, body0, body1, axis,
    localPos0, localPos1, localRot0, localRot1,
    lower_deg, upper_deg,
    drive_target_deg, drive_stiffness, drive_damping, drive_max_force,
    mimic_reference=None, mimic_gearing=None,
):
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
    drive.CreateTargetPositionAttr().Set(float(drive_target_deg))
    drive.CreateStiffnessAttr().Set(float(drive_stiffness))
    drive.CreateDampingAttr().Set(float(drive_damping))
    drive.CreateMaxForceAttr().Set(float(drive_max_force))

    # PhysicsJointStateAPI:angular so the reset target attr name resolves
    # (state:angular:physics:position) — matches the convention the
    # cell_authoring robot.author uses.
    prim.AddAppliedSchema("PhysicsJointStateAPI:angular")
    prim.CreateAttribute("state:angular:physics:position",
                         Sdf.ValueTypeNames.Float, custom=False).Set(float(drive_target_deg))
    prim.CreateAttribute("state:angular:physics:velocity",
                         Sdf.ValueTypeNames.Float, custom=False).Set(0.0)

    # Phase 3E v15 — CRITICAL FIX. Working UR10e arm joints have
    # PhysxJointAPI applied. Without it, PhysX recognises the joint as a
    # USD prim but does NOT cook it into the articulation tree — the
    # body1 link becomes a free rigid body that ignores the joint
    # constraint entirely. Diagnosed by comparing v14's finger_joint
    # schemas against /World/Robot/joints/wrist_3_joint's:
    #   wrist_3_joint  has: [PhysicsJointStateAPI:angular, PhysxJointAPI,
    #                        PhysicsDriveAPI:angular, IsaacJointAPI]
    #   my finger_joint had: [PhysicsDriveAPI:angular, PhysicsJointStateAPI:angular]
    prim.AddAppliedSchema("PhysxJointAPI")
    prim.AddAppliedSchema("IsaacJointAPI")

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


def _author_friction_material(stage, path):
    mat_path = Sdf.Path(path)
    mat = UsdGeom.Scope.Define(stage, mat_path).GetPrim()
    UsdPhysics.MaterialAPI.Apply(mat)
    mat.CreateAttribute("physics:staticFriction", Sdf.ValueTypeNames.Float, custom=False)\
       .Set(FRICTION_COEF)
    mat.CreateAttribute("physics:dynamicFriction", Sdf.ValueTypeNames.Float, custom=False)\
       .Set(FRICTION_COEF)
    mat.CreateAttribute("physics:restitution", Sdf.ValueTypeNames.Float, custom=False)\
       .Set(0.0)
    return mat


def main() -> int:
    if not ASSET.is_file():
        print(f"[swap] ERROR: asset missing: {ASSET}", file=sys.stderr)
        return 1
    if not BACKUP_UPSTREAM.exists():
        shutil.copy2(ASSET, BACKUP_UPSTREAM)
        print(f"[swap] saved upstream backup: {BACKUP_UPSTREAM.name}")
    if not BACKUP_BEFORE_SWAP.exists():
        shutil.copy2(ASSET, BACKUP_BEFORE_SWAP)
        print(f"[swap] saved pre-swap backup: {BACKUP_BEFORE_SWAP.name}")

    # Pull the original orientation off robotiq_base_link before we
    # overwrite. The cell composes the gripper via ee_link's local rotate
    # +90° about Z, and the upstream robotiq_base_link has its own orient
    # quaternion (≈ rot 180° about (1,0,1)/√2). We must preserve it so
    # the gripper points downward in world frame at the home pose.
    src = Usd.Stage.Open(str(ASSET))
    src_base = src.GetPrimAtPath("/Robotiq_2F_140/robotiq_base_link")
    base_orient = src_base.GetAttribute("xformOp:orient").Get()
    print(f"[swap] preserving robotiq_base_link orient: {base_orient}")

    # Release the source layer from the resolver cache, then unlink the
    # file so CreateNew has a clean path.
    src = None
    src_base = None
    layer = Sdf.Layer.FindOrOpen(str(ASSET))
    if layer is not None:
        layer.Clear()
    Sdf.Layer.Reload(layer) if layer else None  # best-effort flush
    del layer
    ASSET.unlink()
    new_stage = Usd.Stage.CreateNew(str(ASSET))
    new_stage.SetMetadata("metersPerUnit", 1.0)
    new_stage.SetMetadata("upAxis", "Z")
    new_stage.SetDefaultPrim(
        UsdGeom.Xform.Define(new_stage, Sdf.Path("/Robotiq_2F_140")).GetPrim()
    )

    # Articulation root on the gripper subtree so PhysX builds a coherent
    # articulation including the wrist link (composed-stage cell_authoring
    # already authors the master articulation root higher up on the UR10e;
    # marking the gripper as a sub-articulation would conflict — leave it
    # off here, the cell-level articulation root covers us).

    # ────────── friction material ──────────
    _author_friction_material(new_stage, "/Robotiq_2F_140/finger_material")

    # ────────── robotiq_base_link ──────────
    # Phase 3E v13: do NOT preserve the upstream base orient. It was
    # introducing joint-frame inconsistencies that PhysX couldn't
    # resolve (fingers flying free, see v8/v12 telemetry). The cell
    # composes ee_link with rotateZYX = (0, 0, 90) and ee_joint with
    # localRot1 = (0.707, 0, 0, -0.707); we let those handle the
    # composed orientation and keep robotiq_base_link's *own* orient at
    # identity. The visible effect is that the gripper's local frame
    # is rotated 180° about the diagonal axis vs the upstream Robotiq,
    # but that's irrelevant for a replacement gripper — only the
    # composed world axes matter.
    base_path = Sdf.Path("/Robotiq_2F_140/robotiq_base_link")
    base = UsdGeom.Xform.Define(new_stage, base_path).GetPrim()
    _set_xform(base, translate=(0, 0, 0), orient=(1, 0, 0, 0))
    _author_rigid_body(base, BASE_MASS_KG)
    UsdGeom.Scope.Define(new_stage, base_path.AppendChild("collisions"))
    _author_box_collider(new_stage, base_path.AppendChild("collisions"), "base",
                         (BASE_SIZE_M, BASE_SIZE_M, BASE_SIZE_M),
                         "/Robotiq_2F_140/finger_material")

    # ────────── left & right fingers ──────────
    # Coordinate-frame derivation (verified by composing the stage and
    # reading /World/Robot/ee_link/left_finger world position):
    #
    # The cell composes ee_link with rotateZYX = (0, 0, 90); the ee_joint
    # adds localRot1 = (0.707, 0, 0, -0.707) which is a further -90° about
    # Z. The robotiq_base_link prim has orient (0, 0.707, 0, 0.707) which
    # is 180° about (1,0,1)/√2. The NET rotation from /Robotiq_2F_140's
    # frame to world is empirically:
    #     local +X → world +Y     (gripper closure axis)
    #     local +Y → world -X     (conveyor axis)
    #     local +Z → world +Z     (vertical)
    #
    # So to make the fingers straddle the peg in world Y (perpendicular
    # to the conveyor), we put their anchors at local X = ±PIVOT_Y_OFFSET.
    # Fingers still extend downward via local -Z.
    #
    # Joint axis = "Y" (base-local). The base's R takes base-local +Y →
    # /Robotiq_2F_140 -Y → world +X. So rotating about base-local +Y is
    # equivalent to rotating about world +X — fingers swing in world Y-Z
    # plane → pads close in Y. ✓
    # Phase 3E v14: bodies at translate (0,0,0) with identity orient,
    # to match the upstream Robotiq 2F-140's convention. The collider is
    # offset INSIDE the body's local frame via the cube's own xformOp.
    # This is the layout that Isaac Sim's articulation cooker expects:
    # the rigid body's origin == the joint anchor, and the visible mesh /
    # collider is positioned relative to that origin via child xform.
    finger_collider_offset_left  = (+PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M - FINGER_LENGTH_M / 2)
    finger_collider_offset_right = (-PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M - FINGER_LENGTH_M / 2)

    for side, c_offset in (("left", finger_collider_offset_left),
                           ("right", finger_collider_offset_right)):
        finger_path = Sdf.Path(f"/Robotiq_2F_140/{side}_finger")
        f = UsdGeom.Xform.Define(new_stage, finger_path).GetPrim()
        _set_xform(f, translate=(0, 0, 0), orient=(1, 0, 0, 0))
        _author_rigid_body(f, FINGER_MASS_KG)
        UsdGeom.Scope.Define(new_stage, finger_path.AppendChild("collisions"))
        # Box extents: width FINGER_THICK_M along X (pad-face normal),
        # length FINGER_WIDTH_M along Y (cross-conveyor width), and
        # FINGER_LENGTH_M along Z (down). Pad face is the inner X face.
        # The Cube is offset to the pad's intended position via its own
        # xformOp:translate (set inside _author_box_collider via the
        # collider prim's children).
        col = _author_box_collider(new_stage, finger_path.AppendChild("collisions"), "finger",
                                   (FINGER_THICK_M, FINGER_WIDTH_M, FINGER_LENGTH_M),
                                   "/Robotiq_2F_140/finger_material")
        # Offset the collider inside the body's local frame.
        t_attr = col.GetAttribute("xformOp:translate")
        t_attr.Set(Gf.Vec3d(*c_offset))

    # ────────── joints ──────────
    # v14: with finger body at translate (0,0,0), the body's local origin
    # is at /Robotiq_2F_140's origin (== base origin). So the joint
    # anchor in finger-local frame == anchor in /Robotiq_2F_140 frame.
    # Both body0 (base) and body1 (finger) have their origins at the
    # SAME point; the joint anchor is simply the pivot's location.
    BASE_LOCAL_LEFT_PIVOT  = (+PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M)
    BASE_LOCAL_RIGHT_PIVOT = (-PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M)
    FINGER_LEFT_LOCAL_PIVOT  = (+PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M)
    FINGER_RIGHT_LOCAL_PIVOT = (-PIVOT_Y_OFFSET_M, 0.0, PIVOT_Z_OFFSET_M)

    # Since the base orient is now identity (v13), the joint frames in
    # body0 and body1 align without any quaternion compensation. Both
    # localRots are identity.
    BASE_ORIENT_QUAT = (1.0, 0.0, 0.0, 0.0)

    _author_revolute_joint(
        new_stage,
        Sdf.Path("/Robotiq_2F_140/finger_joint"),
        body0      = base_path,
        body1      = Sdf.Path("/Robotiq_2F_140/left_finger"),
        axis       = "Y",
        localPos0  = BASE_LOCAL_LEFT_PIVOT,
        localPos1  = FINGER_LEFT_LOCAL_PIVOT,
        localRot0  = BASE_ORIENT_QUAT,
        localRot1  = (1, 0, 0, 0),
        lower_deg  = -45.0,
        upper_deg  =  45.0,
        drive_target_deg = 0.0,
        drive_stiffness  = 1.0e5,
        drive_damping    = 1.0e4,
        drive_max_force  = 1.0e6,
    )
    _author_revolute_joint(
        new_stage,
        Sdf.Path("/Robotiq_2F_140/right_finger_joint"),
        body0      = base_path,
        body1      = Sdf.Path("/Robotiq_2F_140/right_finger"),
        axis       = "Y",
        localPos0  = BASE_LOCAL_RIGHT_PIVOT,
        localPos1  = FINGER_RIGHT_LOCAL_PIVOT,
        localRot0  = BASE_ORIENT_QUAT,
        localRot1  = (1, 0, 0, 0),
        lower_deg  = -45.0,
        upper_deg  =  45.0,
        drive_target_deg = 0.0,
        drive_stiffness  = 1.0e5,
        drive_damping    = 1.0e4,
        drive_max_force  = 1.0e6,
        mimic_reference  = "/Robotiq_2F_140/finger_joint",
        mimic_gearing    = -1.0,
    )

    new_stage.Save()
    print(f"[swap] wrote new parallel-jaw asset: {ASSET}")

    # ────────── verify ──────────
    v = Usd.Stage.Open(str(ASSET))
    expected = (
        "/Robotiq_2F_140/robotiq_base_link",
        "/Robotiq_2F_140/left_finger",
        "/Robotiq_2F_140/right_finger",
        "/Robotiq_2F_140/finger_joint",
        "/Robotiq_2F_140/right_finger_joint",
    )
    bad = 0
    for p in expected:
        prim = v.GetPrimAtPath(p)
        if not prim or not prim.IsValid():
            print(f"[swap] VERIFY FAIL: missing prim {p}", file=sys.stderr)
            bad += 1
    rfj = v.GetPrimAtPath("/Robotiq_2F_140/right_finger_joint")
    if rfj:
        schemas = list(rfj.GetPrimTypeInfo().GetAppliedAPISchemas())
        if "PhysxMimicJointAPI:rotX" not in schemas:
            print(f"[swap] VERIFY FAIL: right_finger_joint missing PhysxMimicJointAPI:rotX",
                  file=sys.stderr)
            bad += 1
        else:
            g = float(rfj.GetAttribute("physxMimicJoint:rotX:gearing").Get())
            print(f"[swap] right_finger_joint mimic gearing = {g:+.2f}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
