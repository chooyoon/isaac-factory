"""Real class-prim template factories for cell composition.

Phase B implementation replacing the Phase A ``NotImplementedError`` stubs.

What each factory authors
-------------------------

Every factory produces the canonical ``/visual`` + ``/collider`` sibling
structure (sprint §7), plus the customData / APIs / filter-group rules
declared in :file:`assets/templates/cell_templates.usda`. Instances also
``inherits`` the matching class prim so the kinship survives composition
review.

Determinism contract
--------------------

Every factory authors prims with explicit ``xformOpOrder`` token arrays,
explicit ``size`` attributes (no schema defaults), and ``CreateAttribute``
on every value we set (never relying on USD's lazy attribute creation).
Same args → same wire bytes.

Validator-clean contract
------------------------

Static props, dynamic parts, and belt surfaces emitted by these factories
satisfy the Runtime-A ColliderValidator out of the box. The two acceptance
rules every prop must satisfy:

  * ``§3.1`` orphan collider — either rigid-body ancestor or
    ``customData.static_collider = true`` (top-level, per sprint §7).
  * ``§3.6`` missing collision group — every collider carries
    ``physxCollision:filterGroup``.

Filter groups assigned by family:

  * ``_StaticProp``   → ``"environment"``
  * ``_DynamicPart``  → ``"consumable"``
  * ``_BeltSurface``  → ``"machinery"``
  * ``_RobotLink``    → ``"robot"``  (Phase 3)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

# Forward declarations: real types from materials / collision_groups.
# Imported lazily where used to avoid an authoring-side dependency cycle.


# ============================================================== paths ==

STATIC_PROP_CLASS_PATH   = Sdf.Path("/_StaticProp")
DYNAMIC_PART_CLASS_PATH  = Sdf.Path("/_DynamicPart")
BELT_SURFACE_CLASS_PATH  = Sdf.Path("/_BeltSurface")
ROBOT_LINK_CLASS_PATH    = Sdf.Path("/_RobotLink")

# Class metadata authored on the in-stage class prim so the inherits
# kinship is human-readable in the composed USD. Each factory ensures
# its class prim exists before creating instances.
_CLASS_KINDS: dict[Sdf.Path, str] = {
    STATIC_PROP_CLASS_PATH:   "static_prop",
    DYNAMIC_PART_CLASS_PATH:  "dynamic_part",
    BELT_SURFACE_CLASS_PATH:  "belt_surface",
    ROBOT_LINK_CLASS_PATH:    "robot_link",
}


def ensure_class_prims(stage: Usd.Stage) -> None:
    """Define every cell-template ``class`` prim on ``stage`` (idempotent).

    Called once per stage by the assembler before any instance is authored.
    Each class prim is empty save for ``customData.template_kind`` — the
    factory functions below own the structural content of every instance.
    Keeping the class prims tag-only avoids USD inherit-composition
    surprises and keeps the wire diff small.
    """
    for class_path, kind in sorted(_CLASS_KINDS.items(), key=lambda kv: str(kv[0])):
        prim = stage.GetPrimAtPath(class_path)
        if not prim or not prim.IsValid():
            prim = stage.CreateClassPrim(class_path)
        prim.SetCustomDataByKey("template_kind", kind)


# ============================================================ specs ==


@dataclass(frozen=True)
class StaticPropSpec:
    """Inputs for :func:`author_static_prop`."""
    parent_path:        Sdf.Path
    name:               str
    translate:          tuple[float, float, float]
    size_xyz_m:         tuple[float, float, float]    # visual + collider scale
    filter_group:       str = "environment"


@dataclass(frozen=True)
class DynamicPartSpec:
    """Inputs for :func:`author_dynamic_part`.

    ``mass_kg`` is mandatory (no defaults; sprint §3 — every consumable
    has authored mass/inertia/friction). ``approximation`` must come
    from ``ColliderThresholds.dynamic_allowed_approximations``.
    """
    parent_path:        Sdf.Path
    name:               str
    translate:          tuple[float, float, float]
    size_xyz_m:         tuple[float, float, float]
    mass_kg:            float
    approximation:      str = "box"
    grounded:           str = "true"               # "true" | "false" | "kinematic"
    filter_group:       str = "consumable"


@dataclass(frozen=True)
class BeltSurfaceSpec:
    """Inputs for :func:`author_belt_surface`.

    ``surface_velocity_m_per_s`` is the linear velocity of the belt
    surface in WORLD frame. Sign follows USD convention (+X moves
    parts in the +X direction).
    """
    parent_path:             Sdf.Path
    name:                    str
    translate:               tuple[float, float, float]
    size_xyz_m:              tuple[float, float, float]
    surface_velocity_m_per_s: tuple[float, float, float]
    filter_group:            str = "machinery"


# ============================================================ factories ==


def author_static_prop(stage: Usd.Stage, spec: StaticPropSpec) -> Usd.Prim:
    """Author a ``_StaticProp`` instance and return its root Xform prim."""
    prop_path = spec.parent_path.AppendChild(spec.name)
    xform = UsdGeom.Xform.Define(stage, prop_path)
    _add_inherits(xform.GetPrim(), STATIC_PROP_CLASS_PATH)
    _set_translate_only(xform, spec.translate)

    _author_visual_cube(stage, prop_path, spec.size_xyz_m)
    col = _author_collider_cube(
        stage,
        prop_path,
        spec.size_xyz_m,
        approximation=UsdPhysics.Tokens.boundingCube,
        filter_group=spec.filter_group,
    )
    # Top-level static_collider tag per sprint §7.
    col.GetPrim().SetCustomDataByKey("static_collider", True)
    return xform.GetPrim()


def author_dynamic_part(stage: Usd.Stage, spec: DynamicPartSpec) -> Usd.Prim:
    """Author a ``_DynamicPart`` instance and return its root Xform prim.

    RigidBodyAPI + MassAPI go on the **root** Xform of the part, not on
    the collider child. This matches the Phase 1 fixture convention
    (Cube with apiSchemas = ["PhysicsCollisionAPI", "PhysicsRigidBodyAPI"])
    after lifting the rigid-body responsibilities up to a wrapper, which
    is the only structurally honest way to keep visual + collider as
    siblings while still owning physics state.
    """
    if spec.mass_kg <= 0:
        raise ValueError(f"DynamicPartSpec.mass_kg must be positive; got {spec.mass_kg}")

    part_path = spec.parent_path.AppendChild(spec.name)
    xform = UsdGeom.Xform.Define(stage, part_path)
    _add_inherits(xform.GetPrim(), DYNAMIC_PART_CLASS_PATH)
    _set_translate_only(xform, spec.translate)

    part_prim = xform.GetPrim()
    UsdPhysics.RigidBodyAPI.Apply(part_prim)
    mass_api = UsdPhysics.MassAPI.Apply(part_prim)
    mass_api.CreateMassAttr(float(spec.mass_kg), writeSparsely=False)

    # Disable sleep on consumables. PhysX's default sleep threshold
    # (~5e-5 m^2/s^2) puts the peg to sleep the instant friction transport
    # produces sub-threshold velocity; surface velocity then cannot wake
    # it. Setting both thresholds to 0 keeps the body always-awake.
    # Authored as `custom` PhysxRigidBodyAPI attribute names so Kit's
    # PhysxSchema picks them up at composition.
    part_prim.AddAppliedSchema("PhysxRigidBodyAPI")
    _set_custom_float(part_prim, "physxRigidBody:sleepThreshold",         0.0)
    _set_custom_float(part_prim, "physxRigidBody:stabilizationThreshold", 0.0)

    # Grounding-intent customData tag (sprint §7).
    av = part_prim.GetCustomDataByKey("asset_validator") or {}
    av["grounded"] = spec.grounded
    part_prim.SetCustomDataByKey("asset_validator", dict(av))

    _author_visual_cube(stage, part_path, spec.size_xyz_m)
    _author_collider_cube(
        stage,
        part_path,
        spec.size_xyz_m,
        approximation=_approximation_token(spec.approximation),
        filter_group=spec.filter_group,
    )
    return part_prim


def author_belt_surface(stage: Usd.Stage, spec: BeltSurfaceSpec) -> Usd.Prim:
    """Author a ``_BeltSurface`` instance as a single co-located Cube prim.

    Why one prim, not a sibling ``visual + collider`` pair like ``_StaticProp``:

    PhysX 5.x in Kit 5.0 has a hard constraint for **kinematic surface
    velocity transport**: the prim carrying ``PhysxSurfaceVelocityAPI``
    (or the kinematic body's ``physics:velocity`` legacy fallback) must
    also carry ``UsdPhysics.CollisionAPI``. Splitting the rigid body
    onto a parent Xform and the collider onto a child silently disables
    friction transport (peg's tangential velocity → ~0 instead of belt
    speed). Verified empirically in
    ``scripts/diag_repro_surface_velocity.py`` against four variants and
    against NVIDIA's own ``SurfaceVelocityDemo`` /
    ``ConveyorBeltDemo`` / ``isaacsim.asset.gen.conveyor`` reference
    code — every working configuration co-locates RB+Coll on one prim.

    The cell convention (sprint §7) "/visual sibling of /collider" is
    therefore amended for kinematic belts: the belt prim IS both visual
    and collider. For static props and dynamic parts (which don't
    depend on kinematic surface velocity), the sibling structure stays.
    """
    belt_path = spec.parent_path.AppendChild(spec.name)
    belt_cube = UsdGeom.Cube.Define(stage, belt_path)
    _add_inherits(belt_cube.GetPrim(), BELT_SURFACE_CLASS_PATH)

    belt_prim = belt_cube.GetPrim()
    _set_translate_only(belt_cube, spec.translate)
    # Scale takes a second xformOp; re-author the op order to keep both.
    _set_translate_and_scale(belt_cube, spec.translate, spec.size_xyz_m)
    belt_cube.CreateSizeAttr(1.0, writeSparsely=False)

    # Rigid body — kinematic, with placeholder mass to silence PhysX's
    # "kinematic body without mass" warning. Mass on a kinematic body
    # has no dynamic effect, so the value is conventional.
    rb_api = UsdPhysics.RigidBodyAPI.Apply(belt_prim)
    rb_api.CreateKinematicEnabledAttr(True, writeSparsely=False)
    mass_api = UsdPhysics.MassAPI.Apply(belt_prim)
    mass_api.CreateMassAttr(1.0, writeSparsely=False)

    # Collision API on the SAME prim (co-located with RB).
    UsdPhysics.CollisionAPI.Apply(belt_prim)
    mca = UsdPhysics.MeshCollisionAPI.Apply(belt_prim)
    mca.CreateApproximationAttr(UsdPhysics.Tokens.boundingCube, writeSparsely=False)

    # Filter group + static-collider customData. The belt is a friction
    # source — flag it so the validator's §3.1 check accepts it as a
    # static-style collider in spite of the kinematic rigid body.
    _set_custom_token(belt_prim, "physxCollision:filterGroup", spec.filter_group)
    belt_prim.SetCustomDataByKey("static_collider", True)

    # Surface velocity — applied on the SAME prim as RB+Coll.
    _apply_surface_velocity(belt_prim, spec.surface_velocity_m_per_s)
    return belt_prim


def author_robot_link(stage: Usd.Stage, parent_path: Sdf.Path, name: str) -> Usd.Prim:
    """Phase 3A: real robot-link factory. Phase B placeholder."""
    raise NotImplementedError("_RobotLink factory lands in Phase 3A")


# ========================================================== authoring ==


def _author_visual_cube(
    stage: Usd.Stage,
    parent_path: Sdf.Path,
    size_xyz_m: tuple[float, float, float],
) -> UsdGeom.Cube:
    visual = UsdGeom.Cube.Define(stage, parent_path.AppendChild("visual"))
    visual.CreateSizeAttr(1.0, writeSparsely=False)
    _set_scale_only(visual, size_xyz_m)
    return visual


def _author_collider_cube(
    stage: Usd.Stage,
    parent_path: Sdf.Path,
    size_xyz_m: tuple[float, float, float],
    *,
    approximation: str,
    filter_group: str,
) -> UsdGeom.Cube:
    """Collider Cube under ``parent/collider`` with explicit policy attrs.

    Authors:
      * UsdPhysics.CollisionAPI + MeshCollisionAPI
      * physics:approximation (schema-typed)
      * physxCollision:filterGroup (custom token — Kit picks up by name)
      * purpose = guide (keeps collider out of render bbox cache by default)
    """
    collider = UsdGeom.Cube.Define(stage, parent_path.AppendChild("collider"))
    collider.CreateSizeAttr(1.0, writeSparsely=False)
    _set_scale_only(collider, size_xyz_m)
    # purpose=default (not guide) — Kit's PhysX implementation in 5.0 does
    # NOT resolve material:binding:physics on prims with purpose=guide.
    # Runtime-B diagnostics (scripts/diag_belt_transport.py) confirmed
    # this empirically: with purpose=guide, the bound BeltSurface material
    # (μ=1.2) is ignored and PhysX combines peg's material with its
    # internal default (μ≈0), yielding effective friction ~0.2 instead of
    # the authored 0.8. With purpose=default, the binding is honoured.
    collider.CreatePurposeAttr(UsdGeom.Tokens.default_, writeSparsely=False)

    prim = collider.GetPrim()
    UsdPhysics.CollisionAPI.Apply(prim)
    mca = UsdPhysics.MeshCollisionAPI.Apply(prim)
    mca.CreateApproximationAttr(approximation, writeSparsely=False)

    _set_custom_token(prim, "physxCollision:filterGroup", filter_group)
    return collider


def _apply_surface_velocity(
    collider_prim: Usd.Prim,
    velocity_world: tuple[float, float, float],
) -> None:
    """Author PhysxSurfaceVelocityAPI on the prim, including schema activation.

    Two parts:

    1. ``AddAppliedSchema("PhysxSurfaceVelocityAPI")`` — appends the schema
       name to the prim's ``apiSchemas`` token list. This is the activation
       step PhysX requires to actually consume the surface velocity at
       contact resolution. Without it, the attributes are inert custom
       data and friction transport does NOT engage (Runtime B smoke test
       proved this empirically).

    2. Author the schema's attributes by their canonical names as
       ``custom`` typed-value attributes. PhysxSchema is not importable
       in Runtime A; ``AddAppliedSchema`` adds the *name* without requiring
       the schema *class*, and when Kit loads PhysxSchema the named
       attributes get picked up as schema attributes by name.
    """
    collider_prim.AddAppliedSchema("PhysxSurfaceVelocityAPI")

    _set_custom_bool   (collider_prim, "physxSurfaceVelocity:surfaceVelocityEnabled", True)
    _set_custom_vector3(collider_prim, "physxSurfaceVelocity:surfaceVelocity",
                        Gf.Vec3f(*velocity_world))
    # Angular surface velocity is zero — belts only translate. Authored
    # explicitly so a future modification does not pick up an implicit
    # default.
    _set_custom_vector3(collider_prim, "physxSurfaceVelocity:surfaceAngularVelocity",
                        Gf.Vec3f(0.0, 0.0, 0.0))


# ============================================================== helpers ==


def _add_inherits(prim: Usd.Prim, class_path: Sdf.Path) -> None:
    inherits = prim.GetInherits()
    if class_path not in inherits.GetAllDirectInherits():
        inherits.AddInherit(class_path)


def _set_translate_only(xformable: UsdGeom.Xformable, t: tuple[float, float, float]) -> None:
    prim = xformable.GetPrim()
    attr = prim.CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3, custom=False)
    attr.Set(Gf.Vec3d(t[0], t[1], t[2]))
    _set_xform_op_order(prim, ("xformOp:translate",))


def _set_scale_only(xformable: UsdGeom.Xformable, s: tuple[float, float, float]) -> None:
    prim = xformable.GetPrim()
    attr = prim.CreateAttribute("xformOp:scale", Sdf.ValueTypeNames.Double3, custom=False)
    attr.Set(Gf.Vec3d(s[0], s[1], s[2]))
    _set_xform_op_order(prim, ("xformOp:scale",))


def _set_translate_and_scale(
    xformable: UsdGeom.Xformable,
    t: tuple[float, float, float],
    s: tuple[float, float, float],
) -> None:
    """Author both translate and scale ops; lock op order to translate→scale."""
    prim = xformable.GetPrim()
    t_attr = prim.CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3, custom=False)
    t_attr.Set(Gf.Vec3d(t[0], t[1], t[2]))
    s_attr = prim.CreateAttribute("xformOp:scale", Sdf.ValueTypeNames.Double3, custom=False)
    s_attr.Set(Gf.Vec3d(s[0], s[1], s[2]))
    _set_xform_op_order(prim, ("xformOp:translate", "xformOp:scale"))


def _set_xform_op_order(prim: Usd.Prim, names: Sequence[str]) -> None:
    attr = prim.CreateAttribute(
        "xformOpOrder",
        Sdf.ValueTypeNames.TokenArray,
        custom=False,
        variability=Sdf.VariabilityUniform,
    )
    attr.Set(list(names))


def _set_custom_token(prim: Usd.Prim, name: str, value: str) -> None:
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Token, custom=True)
    attr.Set(value)


def _set_custom_bool(prim: Usd.Prim, name: str, value: bool) -> None:
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Bool, custom=True)
    attr.Set(bool(value))


def _set_custom_float(prim: Usd.Prim, name: str, value: float) -> None:
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Float, custom=True)
    attr.Set(float(value))


def _set_custom_vector3(prim: Usd.Prim, name: str, value: Gf.Vec3f) -> None:
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Float3, custom=True)
    attr.Set(value)


def _approximation_token(name: str) -> str:
    """Map our string approximation names to UsdPhysics.Tokens where they
    exist; pass through otherwise. Centralises the mapping so spec callers
    use simple strings."""
    mapping = {
        "box":                  UsdPhysics.Tokens.boundingCube,
        "sphere":               UsdPhysics.Tokens.boundingSphere,
        "convexHull":           UsdPhysics.Tokens.convexHull,
        "convexDecomposition":  UsdPhysics.Tokens.convexDecomposition,
        # capsule / cylinder do not have UsdPhysics.Tokens entries pre-25;
        # passed through as raw string.
    }
    return mapping.get(name, name)
