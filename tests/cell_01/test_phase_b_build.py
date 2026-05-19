"""Phase B integration tests: templates, environment, conveyor, peg.

These exercise the Phase B exit gates (sprint §5 Phase 1B/1C/2A/2B and
the Phase-B-specific user requests):

* class-prim templates are present and inherited by every prop
* static environment authored (floor, cage, pedestal, work fixture)
* one conveyor with belt + rails, kinematic, with surface velocity
* one dynamic peg with authored mass, resting on the belt
* ColliderValidator clean (Runtime A inspector)
* deterministic export stable through the larger composed stage
"""

from __future__ import annotations

from pathlib import Path

import pytest

pxr = pytest.importorskip("pxr")
from pxr import Usd, UsdGeom, UsdPhysics                              # noqa: E402

from asset_validator import (                                         # noqa: E402
    AcceptanceCriteria,
    ColliderValidator,
    GroundingValidator,
    TransformValidator,
    ValidationContext,
)
from asset_validator.adapters.usd_collider_inspector import (        # noqa: E402
    UsdColliderInspector,
)
from asset_validator.adapters.usd_grounding_inspector import (       # noqa: E402
    UsdGroundingInspector,
)
from asset_validator.adapters.usd_stage_inspector import (           # noqa: E402
    UsdStageInspector,
)
from cell_authoring import build_cell, load_config                   # noqa: E402


_WORKSPACE = Path(__file__).resolve().parents[2]
_CONFIG    = _WORKSPACE / "configs" / "cell_01.yaml"


@pytest.fixture(scope="module")
def cfg():
    return load_config(_CONFIG)


@pytest.fixture
def stage(tmp_path: Path, cfg) -> Usd.Stage:
    out = build_cell(cfg, workspace_root=tmp_path)
    s = Usd.Stage.Open(str(out))
    assert s is not None
    return s


# ============================================================ templates ==


class TestClassPrims:
    """The four class-prim tags must exist as `class` prims in every stage."""

    @pytest.mark.parametrize("class_path,kind", [
        ("/_StaticProp",   "static_prop"),
        ("/_DynamicPart",  "dynamic_part"),
        ("/_BeltSurface",  "belt_surface"),
        ("/_RobotLink",    "robot_link"),
    ])
    def test_class_prim_exists_and_tagged(self, stage, class_path, kind):
        prim = stage.GetPrimAtPath(class_path)
        assert prim and prim.IsValid(), f"missing class prim {class_path}"
        # `class` specifier is what makes it abstract.
        assert prim.GetSpecifier() == pxr.Sdf.SpecifierClass
        assert prim.GetCustomDataByKey("template_kind") == kind


class TestInherits:
    """Every authored instance inherits the matching class prim."""

    @pytest.mark.parametrize("inst_path,class_path", [
        # static props
        ("/World/Environment/Floor",         "/_StaticProp"),
        ("/World/Environment/Cage_East",     "/_StaticProp"),
        ("/World/Environment/Cage_North",    "/_StaticProp"),
        ("/World/Environment/RobotPedestal", "/_StaticProp"),
        ("/World/Environment/WorkFixture",   "/_StaticProp"),
        ("/World/Machinery/Conveyor_InFeed/Frame_East",  "/_StaticProp"),
        ("/World/Machinery/Conveyor_InFeed/Frame_West",  "/_StaticProp"),
        # belt
        ("/World/Machinery/Conveyor_InFeed/Belt",        "/_BeltSurface"),
        # dynamic part
        ("/World/Parts/Peg_01",                          "/_DynamicPart"),
    ])
    def test_instance_inherits_class(self, stage, inst_path, class_path):
        prim = stage.GetPrimAtPath(inst_path)
        assert prim and prim.IsValid(), f"missing instance {inst_path}"
        inherits = [str(p) for p in prim.GetInherits().GetAllDirectInherits()]
        assert class_path in inherits, (
            f"{inst_path} does not inherit {class_path}; inherits={inherits}"
        )


# ============================================================ env ==


class TestEnvironment:
    """The static environment matches the cell config."""

    def test_floor_top_at_z_zero(self, stage, cfg):
        floor = stage.GetPrimAtPath("/World/Environment/Floor")
        t = floor.GetAttribute("xformOp:translate").Get()
        assert float(t[2]) == pytest.approx(-cfg.environment.floor.thickness_m / 2.0)

    def test_four_cage_walls_present(self, stage):
        for name in ("Cage_East", "Cage_North", "Cage_South", "Cage_West"):
            prim = stage.GetPrimAtPath(f"/World/Environment/{name}")
            assert prim and prim.IsValid(), f"missing {name}"

    def test_pedestal_top_at_authored_height(self, stage, cfg):
        prim = stage.GetPrimAtPath("/World/Environment/RobotPedestal")
        t = prim.GetAttribute("xformOp:translate").Get()
        # Centre at h/2 → top at h.
        assert float(t[2]) == pytest.approx(cfg.environment.pedestal.height_m / 2.0)


# ============================================================ conveyor ==


class TestConveyor:
    """Belt + rails are authored per cell config; belt is kinematic with
    PhysxSurfaceVelocityAPI-named custom attributes."""

    def test_belt_is_kinematic_rigid_body(self, stage):
        belt = stage.GetPrimAtPath("/World/Machinery/Conveyor_InFeed/Belt")
        assert belt.HasAPI(UsdPhysics.RigidBodyAPI)
        rb = UsdPhysics.RigidBodyAPI(belt)
        attr = rb.GetKinematicEnabledAttr()
        assert attr and attr.IsValid() and attr.Get() is True

    def test_belt_surface_velocity_authored(self, stage, cfg):
        col = stage.GetPrimAtPath("/World/Machinery/Conveyor_InFeed/Belt")
        enabled = col.GetAttribute("physxSurfaceVelocity:surfaceVelocityEnabled")
        assert enabled and enabled.Get() is True
        vel = col.GetAttribute("physxSurfaceVelocity:surfaceVelocity").Get()
        expected = cfg.conveyors[0].belt_velocity_world_m_per_s
        assert tuple(float(v) for v in vel) == pytest.approx(expected)

    def test_belt_filter_group_is_machinery(self, stage):
        col = stage.GetPrimAtPath("/World/Machinery/Conveyor_InFeed/Belt")
        attr = col.GetAttribute("physxCollision:filterGroup")
        assert attr and attr.Get() == "machinery"

    def test_belt_collider_static_marker_present(self, stage):
        col = stage.GetPrimAtPath("/World/Machinery/Conveyor_InFeed/Belt")
        assert col.GetCustomDataByKey("static_collider") is True

    def test_belt_collider_uses_box_approximation(self, stage):
        col = stage.GetPrimAtPath("/World/Machinery/Conveyor_InFeed/Belt")
        assert col.HasAPI(UsdPhysics.MeshCollisionAPI)
        approx = UsdPhysics.MeshCollisionAPI(col).GetApproximationAttr().Get()
        assert approx == UsdPhysics.Tokens.boundingCube

    def test_rails_are_static_props(self, stage):
        for name in ("Frame_East", "Frame_West"):
            rail = stage.GetPrimAtPath(f"/World/Machinery/Conveyor_InFeed/{name}")
            # No RigidBodyAPI on rails — they are static.
            assert not rail.HasAPI(UsdPhysics.RigidBodyAPI)
            col = stage.GetPrimAtPath(f"/World/Machinery/Conveyor_InFeed/{name}/collider")
            assert col.GetCustomDataByKey("static_collider") is True
            assert col.GetAttribute("physxCollision:filterGroup").Get() == "machinery"


# ============================================================ peg ==


class TestConsumablePeg:
    """The peg is dynamic, has authored mass, rests on the belt top."""

    def test_peg_is_dynamic_rigid_body(self, stage):
        peg = stage.GetPrimAtPath("/World/Parts/Peg_01")
        assert peg.HasAPI(UsdPhysics.RigidBodyAPI)
        # No kinematic flag → dynamic by default.
        rb = UsdPhysics.RigidBodyAPI(peg)
        attr = rb.GetKinematicEnabledAttr()
        assert (attr is None) or (not attr.IsAuthored()) or (attr.Get() is False)

    def test_peg_has_authored_mass(self, stage, cfg):
        peg = stage.GetPrimAtPath("/World/Parts/Peg_01")
        assert peg.HasAPI(UsdPhysics.MassAPI)
        mass = UsdPhysics.MassAPI(peg).GetMassAttr().Get()
        assert float(mass) == pytest.approx(cfg.parts[0].mass_kg)

    def test_peg_grounded_intent_authored(self, stage):
        peg = stage.GetPrimAtPath("/World/Parts/Peg_01")
        av = peg.GetCustomDataByKey("asset_validator") or {}
        assert av.get("grounded") == "true"

    def test_peg_collider_filter_group_consumable(self, stage):
        col = stage.GetPrimAtPath("/World/Parts/Peg_01/collider")
        assert col.GetAttribute("physxCollision:filterGroup").Get() == "consumable"

    def test_peg_bottom_1mm_above_belt_top(self, stage, cfg):
        """Peg bottom sits 1 mm above belt top — small clearance so reset
        does not detect resting-contact penetration. Peg settles within
        <1 physics step under gravity."""
        peg     = stage.GetPrimAtPath("/World/Parts/Peg_01")
        visual  = stage.GetPrimAtPath("/World/Parts/Peg_01/visual")
        peg_t   = peg.GetAttribute("xformOp:translate").Get()
        peg_s   = visual.GetAttribute("xformOp:scale").Get()
        peg_bottom_z = float(peg_t[2]) - float(peg_s[2]) / 2.0
        belt_top_z   = cfg.conveyors[0].belt_top_z_m
        clearance_m  = peg_bottom_z - belt_top_z
        assert 0.0 < clearance_m <= 0.002, (
            f"Peg should sit 1 mm above belt; clearance = {clearance_m*1000:.3f} mm"
        )


# ============================================================ validators ==


class TestRuntimeAValidatorsClean:
    """Three Runtime-A validators clean on the full Phase B stage."""

    def _ctx(self, stage):
        return ValidationContext(
            asset_uri="cell_01.usda",
            criteria=AcceptanceCriteria(),
            stage_inspector     = UsdStageInspector    (stage=stage),
            grounding_inspector = UsdGroundingInspector(stage=stage),
            collider_inspector  = UsdColliderInspector (stage=stage),
        )

    def test_transform_clean(self, stage):
        ctx = self._ctx(stage)
        issues = TransformValidator(ctx.criteria).run(ctx)
        assert issues == [], [(i.severity.name, i.code, i.prim_paths) for i in issues]

    def test_grounding_clean(self, stage):
        ctx = self._ctx(stage)
        issues = GroundingValidator(ctx.criteria).run(ctx)
        assert issues == [], [(i.severity.name, i.code, i.prim_paths) for i in issues]

    def test_collider_clean(self, stage):
        ctx = self._ctx(stage)
        issues = ColliderValidator(ctx.criteria).run(ctx)
        assert issues == [], [(i.severity.name, i.code, i.prim_paths) for i in issues]


# ============================================================ determinism ==


class TestDeterministicLargeStage:
    """Same config → byte-identical .usda even with templates + machinery + parts."""

    def test_two_consecutive_builds_byte_identical(self, tmp_path: Path, cfg):
        ws_a = tmp_path / "a"
        ws_b = tmp_path / "b"
        a = build_cell(cfg, workspace_root=ws_a).read_bytes()
        b = build_cell(cfg, workspace_root=ws_b).read_bytes()
        assert a == b, "Phase B build is non-deterministic"

    def test_size_invariant_under_third_build(self, tmp_path: Path, cfg):
        """Third build also matches — guards against build-twice short-circuits."""
        ws_a = tmp_path / "a"
        ws_b = tmp_path / "b"
        ws_c = tmp_path / "c"
        a = build_cell(cfg, workspace_root=ws_a).read_bytes()
        b = build_cell(cfg, workspace_root=ws_b).read_bytes()
        c = build_cell(cfg, workspace_root=ws_c).read_bytes()
        assert a == b == c
