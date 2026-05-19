"""Deterministic ``UsdPhysics.Scene`` authoring.

This is the **only** place in the cell pipeline that decides physics-scene
attributes. Every cell stage routes through ``author_physics_scene`` so the
across-cell physics contract — fixed dt, TGS, enhanced determinism, sorted
iteration — cannot drift.

Runtime A constraint
--------------------

The Phase 1B reset adapter (Runtime B) consumes
``physxScene:enableEnhancedDeterminism`` via
:class:`PhysxSchema.PhysxSceneAPI`. Runtime A does not ship PhysxSchema;
we author the same attribute names as **custom** attributes. Kit picks
them up by name when PhysxSchema applies later. No information loss.

The authoritative dependency on these attribute names is in:
``isaac_factory/extensions/asset_validator/asset_validator/adapters/physx_reset_simulator.py``
— keep names in sync if PhysxSchema renames them.
"""

from __future__ import annotations

from pxr import Gf, Sdf, Usd, UsdPhysics

from .config import RuntimeConfig


_PHYSICS_SCENE_PATH = "/World/PhysicsScene"


def author_physics_scene(stage: Usd.Stage, rt: RuntimeConfig) -> Usd.Prim:
    """Define ``/World/PhysicsScene`` with deterministic settings.

    Idempotent: re-running on the same stage replaces attribute values
    but does not duplicate the prim or its custom attributes.

    Returns the created (or updated) prim so callers can verify.
    """
    scene = UsdPhysics.Scene.Define(stage, Sdf.Path(_PHYSICS_SCENE_PATH))

    # UsdPhysics attributes — schema-recognised, no `custom` keyword.
    direction = Gf.Vec3f(*rt.gravity.direction)
    scene.CreateGravityDirectionAttr(direction, writeSparsely=False)
    scene.CreateGravityMagnitudeAttr(float(rt.gravity.magnitude_m_per_s2), writeSparsely=False)

    prim = scene.GetPrim()

    # PhysxSchema-equivalent attributes authored as `custom` so usd-core
    # accepts them without the schema being registered. Names match
    # PhysxSchema.PhysxSceneAPI exactly so Kit's schema can read them
    # without translation.
    _set_custom_attr(prim, "physxScene:enableEnhancedDeterminism",
                     Sdf.ValueTypeNames.Bool, bool(rt.enable_enhanced_determinism))

    _set_custom_attr(prim, "physxScene:solverType",
                     Sdf.ValueTypeNames.Token, rt.solver_type)

    _set_custom_attr(prim, "physxScene:timeStepsPerSecond",
                     Sdf.ValueTypeNames.UInt, int(round(1.0 / rt.physics_dt)))

    _set_custom_attr(prim, "physxScene:minPositionIterationCount",
                     Sdf.ValueTypeNames.UInt, int(rt.solver_position_iteration_count))
    _set_custom_attr(prim, "physxScene:minVelocityIterationCount",
                     Sdf.ValueTypeNames.UInt, int(rt.solver_velocity_iteration_count))

    # PhysX 5 surface velocity friction-patch behaviour requires the
    # scene's friction type to be 'patch'. Other modes (oneDirectional /
    # twoDirectional) silently drop the surface-velocity drag term and
    # only the rigid-body's own velocity drives friction. Authored
    # empirically from Runtime B diagnostic scripts/diag_belt_transport.py.
    _set_custom_attr(prim, "physxScene:frictionType",
                     Sdf.ValueTypeNames.Token, "patch")

    return prim


# ============================================================== private ==


def _set_custom_attr(
    prim: Usd.Prim,
    name: str,
    type_name: Sdf.ValueTypeName,
    value,
) -> None:
    """Create-or-reuse a `custom` attribute and set its value.

    Re-runs are idempotent: same name + value → same wire bytes.
    """
    attr = prim.GetAttribute(name)
    if not attr:
        attr = prim.CreateAttribute(name, type_name, custom=True)
    attr.Set(value)
