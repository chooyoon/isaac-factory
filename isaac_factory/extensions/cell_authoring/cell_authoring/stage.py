"""Top-level cell-stage assembler.

Builds a single ``.usda`` from a :class:`CellConfig`. Composition order:

  1. root metadata + ``/World``
  2. in-stage class prim tags (``_StaticProp`` / ``_DynamicPart`` / …)
  3. ``/World/PhysicsScene``
  4. ``/World/Lights/DomeLight``
  5. ``/World/Materials/Physics/{BeltSurface,Consumable,StaticFixture}``
  6. ``/World/Collisions/{Environment,Machinery,Consumable,Robot}``
  7. ``/World/Environment/*``    (floor, cage, pedestal, work fixture)
  8. ``/World/Machinery/*``      (conveyor belt + rails)
  9. ``/World/Parts/*``          (consumables)
 10. final wiring pass: every collider receives its
     ``physxCollision:filterGroup``-matched ``PhysicsMaterial`` binding
     **and** is added to the matching ``CollisionGroup``.

Wiring rationale
----------------

The per-collider material + collision-group decisions live in
:func:`_wire_colliders` rather than in the template factories. Two
reasons:

* keeps :mod:`cell_authoring.templates` independent of the
  material / collision-group modules (no import cycle, and templates
  remain reusable for cells that pick different materials);
* one single pass at the end means the order of authoring (templates →
  materials → groups) is independent of when the colliders are
  authored.

Determinism
-----------

Sorted iteration over Stage.Traverse() — same input → same wire bytes.
"""

from __future__ import annotations

from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdLux, UsdPhysics

from .collision_groups import (
    CONSUMABLE_GROUP_PATH,
    ENVIRONMENT_GROUP_PATH,
    MACHINERY_GROUP_PATH,
    ROBOT_GROUP_PATH,
    add_member,
    author_collision_groups,
)
from .config       import CellConfig
from .conveyor     import author_machinery
from .environment  import author_environment
from .materials    import (
    BELT_MATERIAL_PATH,
    CONSUMABLE_MAT_PATH,
    GRIPPER_PAD_MAT_PATH,
    STATIC_MAT_PATH,
    author_materials,
    bind_material,
)
from .parts        import author_parts
from .physics      import author_physics_scene
from .robot        import author_robot
from .templates    import ensure_class_prims


_PHYSX_SURFACE_VELOCITY_SCHEMA = "PhysxSurfaceVelocityAPI"


# ============================================================ public API ==


def build_cell(config: CellConfig, workspace_root: Path) -> Path:
    """Build the cell stage from ``config`` and write it to disk."""
    out_path = (workspace_root / config.cell_stage_rel).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stage = Usd.Stage.CreateInMemory()
    _author_stage_metadata(stage)
    ensure_class_prims       (stage)
    author_physics_scene     (stage, config.runtime)
    _author_lights           (stage, config)
    author_materials         (stage)
    author_collision_groups  (stage)
    author_environment       (stage, config)
    author_machinery         (stage, config)
    author_parts             (stage, config)
    if config.robot is not None:
        author_robot(stage, config.robot, workspace_root=workspace_root)
        _wire_robot_collisions(stage, config.robot)
    _wire_colliders          (stage, config)

    stage.GetRootLayer().Export(
        str(out_path),
        comment=f"cell_authoring: built from configs schema_version={config.schema_version}",
    )
    return out_path


# ============================================================ scaffolders ==


def _author_stage_metadata(stage: Usd.Stage) -> None:
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))


def _author_lights(stage: Usd.Stage, cfg: CellConfig) -> None:
    UsdGeom.Xform.Define(stage, Sdf.Path("/World/Lights"))

    dome_path = Sdf.Path("/World/Lights/DomeLight")
    dome = UsdLux.DomeLight.Define(stage, dome_path)
    dome.CreateIntensityAttr(float(cfg.lighting.dome_intensity), writeSparsely=False)
    _set_empty_xform_op_order(dome.GetPrim())


# =================================================== wiring pass ==


def _wire_robot_collisions(stage: Usd.Stage, robot_cfg) -> None:
    """Add the robot mount to the Robot collision group + bind gripper material.

    Two pieces:

    * The mount prim joins the Robot CollisionGroup via collection
      include — every descendant CollisionAPI prim is automatically a
      member, no enumeration needed.
    * The high-friction ``GripperPad`` material binds at the gripper's
      root container under ``/<mount>/ee_link/Robotiq_2F_140``. UsdShade
      MaterialBindingAPI inheritance propagates the binding to every
      descendant collider (Robotiq finger pads, knuckles, fingertips)
      automatically — no per-collider walk needed. The override is
      authored at the known asset path, so it composes correctly even
      though the asset reference doesn't resolve during in-memory build.
    """
    add_member(stage, ROBOT_GROUP_PATH, Sdf.Path(robot_cfg.mount_prim_path))

    # Bind gripper-pad material at the Robotiq subtree root.
    # Robotiq_2F_140 is canonical for the chosen variant; older 2F_85
    # uses the same naming convention. We use OverridePrim so the
    # binding is authored even if the asset reference is unresolved
    # at this point (in-memory composition limitation).
    gripper_root_path = Sdf.Path(robot_cfg.mount_prim_path) \
        .AppendChild("ee_link") \
        .AppendChild(_gripper_root_name(robot_cfg.gripper_variant))
    gripper_root = stage.OverridePrim(gripper_root_path)
    bind_material(gripper_root, GRIPPER_PAD_MAT_PATH)


def _gripper_root_name(gripper_variant: str) -> str:
    """Map the variant token to the canonical subtree root name.

    Empirically verified by inspecting the composed cell stage with
    each variant selected (see scripts/diag_robot_compose.py).
    """
    if gripper_variant == "Robotiq_2f_85":
        return "Robotiq_2F_85"
    if gripper_variant == "Robotiq_2f_140":
        return "Robotiq_2F_140"
    return ""  # "None" variant has no gripper subtree


def _wire_colliders(stage: Usd.Stage, config: CellConfig) -> None:
    """Per-collider material binding + collision-group membership.

    Classification:

      * ``filterGroup == "machinery"`` AND PhysxSurfaceVelocityAPI applied
        → belt material, Machinery collision group.
      * ``filterGroup == "machinery"``
        → static-fixture material, Machinery collision group.
      * ``filterGroup == "environment"``
        → static-fixture material, Environment collision group.
      * ``filterGroup == "consumable"``
        → consumable material, Consumable collision group.
      * ``filterGroup == "robot"``
        → static-fixture material, Robot collision group.  (Phase 3 fills.)
    """
    # Robot colliders are handled in bulk by _wire_robot_collisions (the
    # mount path is added to the Robot collision group as a single
    # collection include). Material binding for robot links is deferred
    # to Phase 3B if grasp tuning needs it — the asset's authored
    # materials are sufficient for joint motion.
    robot_mount: str | None = None
    if config.robot is not None:
        robot_mount = config.robot.mount_prim_path.rstrip("/") + "/"

    colliders = sorted(
        (p for p in stage.Traverse() if p.IsActive() and p.HasAPI(UsdPhysics.CollisionAPI)),
        key=lambda p: str(p.GetPath()),
    )
    for prim in colliders:
        path_str = str(prim.GetPath())
        if robot_mount is not None and (path_str == robot_mount.rstrip("/") or path_str.startswith(robot_mount)):
            continue  # handled by _wire_robot_collisions

        filter_group = _filter_group(prim)
        has_surface_velocity = _PHYSX_SURFACE_VELOCITY_SCHEMA in _applied_schema_names(prim)

        if filter_group == "machinery" and has_surface_velocity:
            material_path = BELT_MATERIAL_PATH
            group_path    = MACHINERY_GROUP_PATH
        elif filter_group == "machinery":
            material_path = STATIC_MAT_PATH
            group_path    = MACHINERY_GROUP_PATH
        elif filter_group == "environment":
            material_path = STATIC_MAT_PATH
            group_path    = ENVIRONMENT_GROUP_PATH
        elif filter_group == "consumable":
            material_path = CONSUMABLE_MAT_PATH
            group_path    = CONSUMABLE_GROUP_PATH
        elif filter_group == "robot":
            # Robot collider that's outside the bulk-included mount —
            # shouldn't happen in Phase 3A, but if it does, route to the
            # Robot group without external material binding.
            add_member(stage, ROBOT_GROUP_PATH, prim.GetPath())
            continue
        else:
            raise RuntimeError(
                f"Collider {prim.GetPath()} has unknown filter_group "
                f"{filter_group!r}; expected one of "
                f"environment / machinery / consumable / robot."
            )

        bind_material(prim, material_path)
        add_member(stage, group_path, prim.GetPath())


# ============================================================== helpers ==


def _filter_group(prim: Usd.Prim) -> str | None:
    attr = prim.GetAttribute("physxCollision:filterGroup")
    if attr and attr.HasAuthoredValue():
        v = attr.Get()
        return str(v) if v else None
    return None


def _applied_schema_names(prim: Usd.Prim) -> list[str]:
    """All schema names in the prim's ``apiSchemas`` metadata, registered or not.

    ``GetAppliedSchemas()`` filters to *registered* schemas, which means
    PhysxSchema entries don't appear in Runtime A. We read the raw
    metadata so the test ``"PhysxSurfaceVelocityAPI" in …`` works in
    both runtimes.
    """
    out: list[str] = []
    md = prim.GetMetadata("apiSchemas")
    if md is None:
        return out
    out.extend(md.explicitItems  or [])
    out.extend(md.prependedItems or [])
    out.extend(md.appendedItems  or [])
    out.extend(md.addedItems     or [])
    return out


def _set_empty_xform_op_order(prim: Usd.Prim) -> None:
    attr = prim.CreateAttribute(
        "xformOpOrder",
        Sdf.ValueTypeNames.TokenArray,
        custom=False,
        variability=Sdf.VariabilityUniform,
    )
    attr.Set([])
