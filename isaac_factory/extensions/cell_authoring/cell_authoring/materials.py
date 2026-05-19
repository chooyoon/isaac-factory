"""PhysicsMaterial authoring + per-collider binding.

Phase B-tail addition (after the Runtime B smoke surfaced "no material →
zero friction → no transport"). All materials live under
``/World/Materials/Physics``; bindings are authored on the **collider**
prim (not the wrapper Xform) so PhysX resolves the contact-side material
without ambiguity.

Stability-first tuning
----------------------

Sprint guidance: *"Tune for stable conveyor transport, minimal jitter,
stable resting contacts, deterministic settling. Do not optimise for
speed yet."*

The three materials below pick friction values that:

  * keep the peg stuck to the belt under PhysxSurfaceVelocityAPI
    (transport works);
  * stop the peg from sliding on the work-fixture / floor at rest
    (no creep);
  * absorb any vertical contact bounce (zero restitution everywhere).
"""

from __future__ import annotations

from dataclasses import dataclass

from pxr import Sdf, Usd, UsdPhysics, UsdShade


MATERIALS_ROOT       = Sdf.Path("/World/Materials/Physics")
BELT_MATERIAL_PATH   = MATERIALS_ROOT.AppendChild("BeltSurface")
CONSUMABLE_MAT_PATH  = MATERIALS_ROOT.AppendChild("Consumable")
STATIC_MAT_PATH      = MATERIALS_ROOT.AppendChild("StaticFixture")
GRIPPER_PAD_MAT_PATH = MATERIALS_ROOT.AppendChild("GripperPad")


@dataclass(frozen=True)
class MaterialSpec:
    """Parameters for a single ``UsdPhysics.MaterialAPI`` material."""
    path:               Sdf.Path
    dynamic_friction:   float
    static_friction:    float
    restitution:        float
    density_kg_m3:      float    # required by UsdPhysics.MaterialAPI


# Stability-first defaults. Higher static than dynamic across the board
# prevents incipient-motion slips; restitution = 0 kills bounce.
BELT_SURFACE_SPEC = MaterialSpec(
    path             = BELT_MATERIAL_PATH,
    dynamic_friction = 1.20,
    static_friction  = 1.50,
    restitution      = 0.00,
    density_kg_m3    = 1500.0,   # ~rubber belt; ignored on kinematic body but UsdPhysics requires it
)

CONSUMABLE_SPEC = MaterialSpec(
    path             = CONSUMABLE_MAT_PATH,
    dynamic_friction = 0.40,
    static_friction  = 0.50,
    restitution      = 0.00,
    density_kg_m3    = 1000.0,   # ABS-typical; not authoritative — MassAPI overrides
)

STATIC_FIXTURE_SPEC = MaterialSpec(
    path             = STATIC_MAT_PATH,
    dynamic_friction = 0.60,
    static_friction  = 0.80,
    restitution      = 0.00,
    density_kg_m3    = 7800.0,   # steel
)

# Phase 3C: high-friction gripper-pad material. Industrial-rubber-pad-
# typical numbers (Robotiq's own datasheet quotes μ ≈ 1.5–2.0 for
# friction-style pads). Combined with the Consumable material's
# static 0.5 the contact-pair effective friction will be in the
# 1.0–1.2 range under the cell's PhysxMaterial frictionCombineMode = max,
# enough to hold a 0.10 kg peg without slip during transport.
GRIPPER_PAD_SPEC = MaterialSpec(
    path             = GRIPPER_PAD_MAT_PATH,
    dynamic_friction = 1.80,
    static_friction  = 2.00,
    restitution      = 0.00,
    density_kg_m3    = 1100.0,   # NBR rubber
)


# ============================================================ authoring ==


def author_materials(stage: Usd.Stage) -> None:
    """Define ``/World/Materials/Physics`` and the three Phase-B materials.

    Idempotent — re-running on an already-authored stage rewrites the
    same attribute values.
    """
    from pxr import UsdGeom
    UsdGeom.Scope.Define(stage, MATERIALS_ROOT.GetParentPath())
    UsdGeom.Scope.Define(stage, MATERIALS_ROOT)

    for spec in (BELT_SURFACE_SPEC, CONSUMABLE_SPEC, STATIC_FIXTURE_SPEC, GRIPPER_PAD_SPEC):
        _author_one_material(stage, spec)


def bind_material(prim: Usd.Prim, material_path: Sdf.Path) -> None:
    """Bind a PhysicsMaterial to a collider prim by path.

    Uses ``UsdShade.MaterialBindingAPI`` with the ``physics`` purpose so
    the binding does not collide with a render-purpose Material binding
    the cell may grow later.
    """
    binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
    material = UsdShade.Material.Get(prim.GetStage(), material_path)
    if not material:
        raise RuntimeError(f"PhysicsMaterial not found: {material_path}")
    binding_api.Bind(material, UsdShade.Tokens.weakerThanDescendants, "physics")


# ============================================================== private ==


def _author_one_material(stage: Usd.Stage, spec: MaterialSpec) -> None:
    material = UsdShade.Material.Define(stage, spec.path)
    prim = material.GetPrim()

    mat_api = UsdPhysics.MaterialAPI.Apply(prim)
    mat_api.CreateDynamicFrictionAttr(float(spec.dynamic_friction), writeSparsely=False)
    mat_api.CreateStaticFrictionAttr (float(spec.static_friction),  writeSparsely=False)
    mat_api.CreateRestitutionAttr    (float(spec.restitution),      writeSparsely=False)
    mat_api.CreateDensityAttr        (float(spec.density_kg_m3),    writeSparsely=False)

    # PhysxSchema.PhysxMaterialAPI authored as a `prepend apiSchemas`
    # token + custom-named attributes. PhysxSchema is not importable in
    # Runtime A, but Kit's PhysxSchema picks up these attributes when
    # the schema name is in apiSchemas. Empirically required by
    # Kit 5.0 for the bound material to flow through to PhysX's
    # contact-resolution stage — without it, PhysX uses internal
    # defaults regardless of UsdPhysics.MaterialAPI values.
    prim.AddAppliedSchema("PhysxMaterialAPI")
    _set_custom_token(prim, "physxMaterial:frictionCombineMode",  "max")
    _set_custom_token(prim, "physxMaterial:restitutionCombineMode", "average")
    _set_custom_token(prim, "physxMaterial:dampingCombineMode",    "average")


def _set_custom_token(prim, name: str, value: str) -> None:
    from pxr import Sdf
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Token, custom=True)
    attr.Set(value)
