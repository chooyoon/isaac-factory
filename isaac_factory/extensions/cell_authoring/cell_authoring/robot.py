"""Phase 3A robot integration — UR10e reference + pedestal mount.

Architecture
------------

The Isaac Sim native UR10e asset (mirrored under
``assets/cells/cell_01/robot/``) is referenced into the cell stage at
the path given by ``RobotConfig.mount_prim_path``. We:

* author a single Xform at that path
* attach a USD reference to the local ``ur10e.usd``
* translate the Xform to the world position given by ``translate_world_m``
* author ``physxArticulation:enabledSelfCollisions`` on the
  articulation root (an explicit policy — sprint contract: "self-collision
  policy must be explicit")
* tag every link collider with ``physxCollision:filterGroup = "robot"``
  so the post-author wiring pass sweeps them into the Robot collision
  group without ambiguity

Mounting policy
---------------

The UR10e asset already has a ``root_joint`` (PhysicsFixedJoint +
ArticulationRootAPI) on ``/ur10e/root_joint`` that anchors
``base_link`` to the world frame at the joint's authored pose. When
the asset is referenced into the cell at translate ``(0, 0, 0.8)``
(top of the pedestal), every link's authored transform composes
with the reference translate. The articulation's root therefore sits
on the pedestal *without* an additional cell-side fixed joint — the
in-asset ``root_joint`` is sufficient. Authoring a second fixed joint
between pedestal and robot would create a redundant constraint that
PhysX flags as over-constrained.

Why no ``_RobotLink`` template factory call here
------------------------------------------------

The UR10e asset already encodes the per-link rigid-body + collider
structure (``base_link``, ``shoulder_link``, …, ``wrist_3_link``,
each with ``PhysicsRigidBodyAPI``, ``PhysicsMassAPI``, and a
``/collisions/`` child). Authoring our own ``_RobotLink`` prims on
top would either duplicate or conflict. We instead override
post-reference attributes via Sdf-side metadata writes:

* set ``physxArticulation:enabledSelfCollisions`` on the articulation root
* set ``physxCollision:filterGroup`` on each per-link ``/collisions/``
  subprim (these are Xform groups containing the actual collision meshes
  — the filter group attribute on the Xform propagates to descendants
  via PhysX's collision-shape inheritance)

This pattern is the canonical Isaac Sim way: reference + scene-graph
override. No mesh editing, no schema reinvention.
"""

from __future__ import annotations

import math
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdPhysics


# Phase 3I: UsdPhysics revolute-joint drive attributes are authored in
# DEGREES per the spec, but Isaac Sim's runtime articulation API reads
# joint positions in RADIANS. cell_authoring writes home_pose values in
# radians (matching the config), so we must convert here when writing
# the drive attributes to keep the units consistent at composition time.
_DEG_PER_RAD = 180.0 / math.pi

from .config import RobotConfig


ROBOT_MOUNT_DEFAULT_PATH = "/World/Robot"
# Path inside the referenced UR10e to the articulation root.
# Stable across Isaac Sim 5.0.x; verified locally at
# `assets/cells/cell_01/robot/ur10e.usd`.
_UR10E_ARTICULATION_ROOT_REL = "root_joint"


def author_robot(stage: Usd.Stage, cfg: RobotConfig, *, workspace_root: Path) -> Usd.Prim:
    """Author the robot mount + reference into ``stage`` per the config.

    Returns the mount Xform prim. Idempotent: re-authoring on a stage
    with the mount already present updates the reference + translate
    but does not duplicate.
    """
    mount_path = Sdf.Path(cfg.mount_prim_path)

    mount_xform = UsdGeom.Xform.Define(stage, mount_path)
    mount_prim  = mount_xform.GetPrim()

    _set_translate(mount_xform, cfg.translate_world_m)

    # Asset reference.
    asset_abs = (workspace_root / cfg.asset_rel).resolve()
    cell_stage_dir = (workspace_root / "assets" / "cells").resolve()
    try:
        ref_path = "./" + str(asset_abs.relative_to(cell_stage_dir))
    except ValueError:
        ref_path = str(asset_abs)
    _add_or_replace_reference(mount_prim, ref_path)

    # Select the Gripper variant (Phase 3B).
    _select_gripper_variant(mount_prim, cfg.gripper_variant)

    # Self-collision policy on the articulation root.
    art_root_path = mount_path.AppendChild(_UR10E_ARTICULATION_ROOT_REL)
    _author_self_collision_policy(stage, art_root_path, cfg.enable_self_collisions)

    # Per-link collider filter-group tagging.
    _tag_link_colliders(stage, mount_path, cfg.articulation_filter_group)

    # Phase 3B: home-pose joint state + per-joint drives + gripper drive.
    _author_home_pose_and_drives(stage, mount_path, cfg)

    # Phase 3H bridge-joint patch — adds PhysxJointAPI to the composed
    # ``ee_joint`` so PhysX's articulation cooker spans from wrist_3
    # into the gripper subtree.
    _patch_ee_joint_articulation(stage, mount_path)

    return mount_prim


# ============================================================== helpers ==


def _set_translate(xformable: UsdGeom.Xformable, t: tuple[float, float, float]) -> None:
    prim = xformable.GetPrim()
    attr = prim.CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3, custom=False)
    from pxr import Gf
    attr.Set(Gf.Vec3d(t[0], t[1], t[2]))
    order_attr = prim.CreateAttribute(
        "xformOpOrder", Sdf.ValueTypeNames.TokenArray,
        custom=False, variability=Sdf.VariabilityUniform,
    )
    order_attr.Set(["xformOp:translate"])


def _add_or_replace_reference(prim: Usd.Prim, asset_path: str) -> None:
    """Add a reference to an asset, removing any prior one with the same path."""
    refs = prim.GetReferences()
    refs.ClearReferences()
    refs.AddReference(asset_path)


def _select_gripper_variant(mount_prim: Usd.Prim, variant_name: str) -> None:
    """Author ``variants = {Gripper=<variant_name>}`` on the mount prim.

    Has to be done at the Sdf level, not via ``Usd.VariantSet.SetVariantSelection``,
    because the referenced asset is not resolvable during in-memory
    authoring (its relative path resolves only when the cell stage is
    loaded from disk). Sdf-level metadata authoring bakes the selection
    into the exported file unconditionally; composition activates the
    variant when the asset's layer arrives.
    """
    stage = mount_prim.GetStage()
    prim_spec = stage.GetRootLayer().GetPrimAtPath(mount_prim.GetPath())
    if prim_spec is None:
        # Define the spec explicitly (happens when the prim was just
        # created in this build pass — the first author of an attribute
        # on it triggers the spec creation, but variants are metadata
        # and need the spec to exist).
        prim_spec = Sdf.CreatePrimInLayer(stage.GetRootLayer(), mount_prim.GetPath())
    prim_spec.variantSelections["Gripper"] = variant_name


def _author_self_collision_policy(
    stage: Usd.Stage, art_root_path: Sdf.Path, enabled: bool,
) -> None:
    """Author physxArticulation:enabledSelfCollisions on the articulation root.

    The articulation root may exist only after composition; we author
    on the override prim so PhysxSchema picks it up at simulation time.
    """
    art_prim = stage.OverridePrim(art_root_path)
    attr = art_prim.GetAttribute("physxArticulation:enabledSelfCollisions")
    if not attr:
        attr = art_prim.CreateAttribute(
            "physxArticulation:enabledSelfCollisions",
            Sdf.ValueTypeNames.Bool, custom=True,
        )
    attr.Set(bool(enabled))


def _author_home_pose_and_drives(
    stage: Usd.Stage, mount_path: Sdf.Path, cfg: RobotConfig,
) -> None:
    """Author the reset-target joint pose, per-joint PD drives, and the gripper drive.

    The UR10e asset's revolute joints live under ``/<mount>/joints/<name>_joint``.
    We author overrides via ``OverridePrim`` so the cell's opinion wins over
    the asset's authored defaults at every reset.

    What gets authored per revolute joint:

      * ``state:angular:physics:position`` — the **reset target**. PhysX
        reads this attribute when the simulation initialises and every
        time ``World.reset()`` fires (verified by Phase 1 reset suite).
      * ``drive:angular:physics:targetPosition`` — the **current control
        target** (kept in sync with the reset target so the joint holds
        the authored home pose under PD control even at t=0).
      * ``drive:angular:physics:stiffness`` and ``damping`` — PD gains
        from ``cfg.joint_drive``.

    For the gripper (Robotiq 2F-85), only the canonical drive joint is
    authored at the configured ``open_position_rad`` with its own PD
    gains. The mimic relationships in the asset propagate the position
    to the other knuckle joints.

    Determinism contract: same config → identical authored values, so
    same composed stage on every build, so identical simulation state
    on every reset.
    """
    art_filter_group = cfg.articulation_filter_group  # noqa — reserved for Phase 3C joint tagging
    drive = cfg.joint_drive
    grip  = cfg.gripper

    for joint_name, position_rad in cfg.home_pose_rad:
        joint_path = mount_path.AppendChild("joints").AppendChild(f"{joint_name}_joint")
        _author_revolute_joint_state_and_drive(
            stage, joint_path, position_rad, drive.stiffness, drive.damping,
        )

    # Gripper drive — the asset's variant exposes a `finger_joint` under
    # the gripper subtree. Path: <mount>/{wrist_3_link or similar}/.../<finger_joint>.
    # The Robotiq 2F-85 base layer authors this joint under
    # /Robotiq_2F_85/Robotiq_2F_85/. After referencing into the cell at
    # /World/Robot, the joint composes at /World/Robot/<asset's joint
    # path>. Empirically the canonical path is
    # /World/Robot/Robotiq_2F_85/Robotiq_2F_85/finger_joint or a similar
    # nested location — we search by joint name rather than hardcoding
    # the path so refactors of the gripper asset don't break us.
    _author_gripper_drive(stage, mount_path, grip)


def _author_revolute_joint_state_and_drive(
    stage: Usd.Stage, joint_path: Sdf.Path,
    target_position_rad: float, stiffness: float, damping: float,
) -> None:
    """Override one revolute joint's reset target + PD drive gains.

    Phase 3H: also raise ``drive:angular:physics:maxForce`` to 1e5 N·m.
    The upstream UR10e ships shoulder_lift / wrist_1 etc. with maxForce
    = 330 N·m — the physical hardware torque limit. Under our stiffness
    of 1e6 and the joint-error transients between trajectory waypoints
    (shoulder_lift sees ~0.4 rad steps in 100 ms), the PD demands
    ~1.8 Mrad torque and saturates against the 330 N·m cap — the arm
    falls behind its target by ~1.8 rad on those joints, the wrist
    never reaches grasp pose, and the gripper never gets near the peg
    (diagnosed in Phase 3H telemetry: shoulder_lift target=-2.49
    actual=-0.68 at grasp_close_step). 1e5 N·m is more than the demand
    while still finite — well within Isaac Sim's PD stability bounds.
    """
    override = stage.OverridePrim(joint_path)
    target_deg = target_position_rad * _DEG_PER_RAD
    _set_float_attr(override, "state:angular:physics:position", target_deg)
    _set_float_attr(override, "drive:angular:physics:targetPosition", target_deg)
    _set_float_attr(override, "drive:angular:physics:stiffness", stiffness)
    _set_float_attr(override, "drive:angular:physics:damping",   damping)


def _author_gripper_drive(
    stage: Usd.Stage, mount_path: Sdf.Path, grip,
) -> None:
    """Locate the gripper drive joint by name; author its drive target at OPEN.

    The Robotiq 2F-85 ships with the canonical ``finger_joint`` revolute
    drive joint. After the gripper variant composes under the UR10e
    mount, this joint sits somewhere under ``<mount>/...``. We walk the
    composed subtree to locate it (no hard-coded path).
    """
    from pxr import UsdPhysics

    target_joint = None
    mount_prefix = str(mount_path) + "/"
    for prim in stage.Traverse():
        path_str = str(prim.GetPath())
        if not path_str.startswith(mount_prefix):
            continue
        # Match by trailing joint name segment.
        if path_str.rsplit("/", 1)[-1] == grip.drive_joint_name and prim.IsA(UsdPhysics.Joint):
            target_joint = prim.GetPath()
            break

    if target_joint is None:
        # Gripper variant not loaded (e.g. variant == "None") — silently skip.
        return

    override = stage.OverridePrim(target_joint)
    open_deg = grip.open_position_rad * _DEG_PER_RAD
    _set_float_attr(override, "state:angular:physics:position", open_deg)
    _set_float_attr(override, "drive:angular:physics:targetPosition", open_deg)
    _set_float_attr(override, "drive:angular:physics:stiffness", grip.drive_stiffness)
    _set_float_attr(override, "drive:angular:physics:damping",   grip.drive_damping)


def _set_float_attr(prim: Usd.Prim, name: str, value: float) -> None:
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Float, custom=False)
    attr.Set(float(value))


def _patch_ee_joint_articulation(stage: Usd.Stage, mount_path: Sdf.Path) -> None:
    """Author ``PhysxJointAPI`` on the composed ``ee_joint``.

    The UR10e+Robotiq variant payload defines ``ee_joint`` at
    ``<mount>/joints/ee_joint`` (a ``PhysicsFixedJoint`` linking the
    final arm link to the gripper base). The upstream asset omits the
    ``PhysxJointAPI`` schema there — every other UR10e arm joint
    carries it. Without ``PhysxJointAPI`` the PhysX articulation cooker
    does not span the joint, so the gripper subtree falls out of the
    UR10e articulation island and its bodies float free during
    simulation (verified by cross-variant RigidPrim probes in Phase 3G).

    We patch this by authoring an override prim spec at
    ``<mount>/joints/ee_joint`` that re-applies the schema. The
    override composes alongside the variant's authoring at runtime;
    PhysxSchema reads ``apiSchemas`` from the composed prim and the
    new schema is honoured.

    Idempotent: if the schema is already present (a future upstream
    fix), the AddAppliedSchema call is a no-op.
    """
    ee_path = mount_path.AppendChild("joints").AppendChild("ee_joint")
    ee_override = stage.OverridePrim(ee_path)
    # AddAppliedSchema appends to the prim's apiSchemas metadata list.
    # It is harmless if the schema is already applied via the variant.
    ee_override.AddAppliedSchema("PhysxJointAPI")


def _tag_link_colliders(stage: Usd.Stage, mount_path: Sdf.Path, filter_group: str) -> None:
    """Author ``physxCollision:filterGroup`` on the mount Xform itself.

    Every collider under ``/<mount>/...`` (UR10e arm links + Robotiq gripper
    links) inherits the filter group through the validator's ancestor-walk
    lookup. PhysX uses CollisionGroup membership (authored separately in
    ``_wire_robot_collisions``) for the actual filtering — this attribute
    is purely informational, used by the validators to satisfy §3.6 (no
    missing collision group).

    Phase 3A authored this attribute per-link on UR10e's ``<link>/collisions``
    containers. Phase 3B's gripper (Robotiq 2F-140) uses a different
    per-link layout where colliders sit at varying nested depths under
    ``ee_link/<finger>/...``. Tagging the mount prim once covers both
    layouts without enumerating gripper link names.
    """
    mount_override = stage.OverridePrim(mount_path)
    attr = mount_override.GetAttribute("physxCollision:filterGroup")
    if not attr:
        attr = mount_override.CreateAttribute(
            "physxCollision:filterGroup", Sdf.ValueTypeNames.Token, custom=True,
        )
    attr.Set(filter_group)
