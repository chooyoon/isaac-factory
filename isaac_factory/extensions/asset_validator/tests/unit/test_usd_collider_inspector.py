"""Integration tests for ``UsdColliderInspector`` (Runtime A).

Pattern mirrors ``test_usd_grounding_inspector.py`` — author a tiny USD
stage in memory, build the inspector, run :class:`ColliderValidator`,
assert the expected issue codes.

Runtime: ``research`` profile (conda env_isaaclab, Python 3.10,
``usd-core 26.3``). No Kit, no PhysX.
"""

from __future__ import annotations

import pytest

pxr = pytest.importorskip("pxr")
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics                    # noqa: E402

from asset_validator import (                                         # noqa: E402
    AcceptanceCriteria,
    ColliderValidator,
    Severity,
    ValidationContext,
)
from asset_validator.adapters.usd_collider_inspector import (        # noqa: E402
    UsdColliderInspector,
)
from asset_validator.validators.collider import (                    # noqa: E402
    CODE_MESH_ON_DYNAMIC,
    CODE_MISSING_COLLISION_GROUP,
    CODE_NO_RIGID_BODY_ANCESTOR,
    CODE_RIGID_BODY_WITHOUT_COLL,
)


# ============================================================ helpers ==


def _build_stage_with_static_collider(
    *,
    static_flag: bool,
    filter_group: str | None = "environment",
) -> Usd.Stage:
    """Stage with one collider that has no rigid-body ancestor.

    Parameters control whether the static_collider customData is set and
    whether the filter group attribute is authored. Used by the §3.1
    and §3.6 tests.
    """
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))

    cube = UsdGeom.Cube.Define(stage, Sdf.Path("/World/Box"))
    cube.CreateSizeAttr(1.0, writeSparsely=False)
    prim = cube.GetPrim()

    UsdPhysics.CollisionAPI.Apply(prim)
    UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr(
        UsdPhysics.Tokens.boundingCube, writeSparsely=False
    )

    if static_flag:
        prim.SetCustomDataByKey("static_collider", True)
    if filter_group is not None:
        attr = prim.CreateAttribute(
            "physxCollision:filterGroup", Sdf.ValueTypeNames.Token, custom=True
        )
        attr.Set(filter_group)
    return stage


def _build_stage_with_dynamic_part(*, approximation: str) -> Usd.Stage:
    """Stage with a RigidBodyAPI prim and a child collider using ``approximation``."""
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))

    part = UsdGeom.Xform.Define(stage, Sdf.Path("/World/Part"))
    UsdPhysics.RigidBodyAPI.Apply(part.GetPrim())
    UsdPhysics.MassAPI.Apply(part.GetPrim()).CreateMassAttr(0.1, writeSparsely=False)

    mesh = UsdGeom.Mesh.Define(stage, Sdf.Path("/World/Part/collider"))
    UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
    mca = UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())
    mca.CreateApproximationAttr(approximation, writeSparsely=False)
    fg = mesh.GetPrim().CreateAttribute(
        "physxCollision:filterGroup", Sdf.ValueTypeNames.Token, custom=True
    )
    fg.Set("consumable")
    return stage


def _validate(stage: Usd.Stage):
    inspector = UsdColliderInspector(stage=stage)
    ctx = ValidationContext(
        asset_uri="test",
        criteria=AcceptanceCriteria(),
        collider_inspector=inspector,
    )
    return ColliderValidator(ctx.criteria).run(ctx)


# ============================================================ tests ==


class TestStaticCollider:
    def test_orphan_collider_flagged_as_static_passes(self):
        stage = _build_stage_with_static_collider(static_flag=True)
        issues = _validate(stage)
        codes = {i.code for i in issues}
        assert CODE_NO_RIGID_BODY_ANCESTOR not in codes
        assert CODE_MISSING_COLLISION_GROUP not in codes

    def test_orphan_collider_without_flag_fails(self):
        stage = _build_stage_with_static_collider(static_flag=False)
        issues = _validate(stage)
        codes = {i.code for i in issues}
        assert CODE_NO_RIGID_BODY_ANCESTOR in codes
        i = next(i for i in issues if i.code == CODE_NO_RIGID_BODY_ANCESTOR)
        assert i.severity == Severity.FAIL

    def test_missing_filter_group_warns(self):
        stage = _build_stage_with_static_collider(static_flag=True, filter_group=None)
        issues = _validate(stage)
        codes = {i.code for i in issues}
        assert CODE_MISSING_COLLISION_GROUP in codes


class TestDynamicCollider:
    def test_convex_hull_approximation_clean(self):
        # convexHull is in ColliderThresholds.dynamic_allowed_approximations.
        stage = _build_stage_with_dynamic_part(approximation=UsdPhysics.Tokens.convexHull)
        issues = _validate(stage)
        codes = {i.code for i in issues}
        assert CODE_MESH_ON_DYNAMIC not in codes

    def test_triangle_mesh_on_dynamic_fails(self):
        # 'none' approximation = raw triangle mesh — explicitly disallowed.
        stage = _build_stage_with_dynamic_part(approximation="none")
        issues = _validate(stage)
        codes = {i.code for i in issues}
        assert CODE_MESH_ON_DYNAMIC in codes

    def test_rigid_body_without_collider_warns(self):
        # Stage with only RigidBodyAPI prim — no children with CollisionAPI.
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))
        part = UsdGeom.Xform.Define(stage, Sdf.Path("/World/EmptyPart"))
        UsdPhysics.RigidBodyAPI.Apply(part.GetPrim())

        issues = _validate(stage)
        codes = {i.code for i in issues}
        assert CODE_RIGID_BODY_WITHOUT_COLL in codes
