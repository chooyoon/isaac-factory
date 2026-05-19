"""Unit tests for ColliderValidator.

Pure Python: no pxr, no omni, no isaacsim. Uses a MockColliderInspector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pytest

from asset_validator import (
    AcceptanceCriteria,
    ColliderInfo,
    ColliderInspector,
    ColliderThresholds,
    ColliderValidator,
    Issue,
    RigidBodyInfo,
    Severity,
    ValidationContext,
)
from asset_validator.validators.collider import (
    CODE_AABB_MISMATCH,
    CODE_CONVEX_DECOMP_HULL_LIM,
    CODE_COOKING_FAILED,
    CODE_DEGENERATE_AABB,
    CODE_EXTREME_ASPECT_RATIO,
    CODE_MASS_DENSITY_CONFLICT,
    CODE_MASS_OUT_OF_RANGE,
    CODE_MESH_ON_DYNAMIC,
    CODE_MISSING_COLLISION_GROUP,
    CODE_NO_COLLIDER_INSPECTOR,
    CODE_NO_RIGID_BODY_ANCESTOR,
    CODE_RIGID_BODY_WITHOUT_COLL,
)


# ============================================================= mock ==


@dataclass
class MockColliderInspector:
    colliders:    list[ColliderInfo]    = field(default_factory=list)
    rigid_bodies: list[RigidBodyInfo]   = field(default_factory=list)

    def iter_colliders(self) -> Iterable[ColliderInfo]:
        return list(self.colliders)

    def iter_rigid_bodies(self) -> Iterable[RigidBodyInfo]:
        return list(self.rigid_bodies)


_: ColliderInspector = MockColliderInspector()


# ============================================================ helpers ==


def _coll(
    path: str,
    approximation: str = "box",
    *,
    rigid_body_path: str | None = None,
    collider_aabb: tuple[tuple[float, float, float], tuple[float, float, float]] | None = ((0, 0, 0), (1, 1, 1)),
    visual_aabb:   tuple[tuple[float, float, float], tuple[float, float, float]] | None = ((0, 0, 0), (1, 1, 1)),
    hull_count:    int | None = None,
    cooking_error: str | None = None,
    collision_group: str | None = "default_group",
    custom_data:   tuple[tuple[str, object], ...] = (),
) -> ColliderInfo:
    cmin = collider_aabb[0] if collider_aabb else None
    cmax = collider_aabb[1] if collider_aabb else None
    vmin = visual_aabb[0]   if visual_aabb   else None
    vmax = visual_aabb[1]   if visual_aabb   else None
    return ColliderInfo(
        path=path,
        approximation=approximation,
        rigid_body_path=rigid_body_path,
        collider_aabb_min=cmin, collider_aabb_max=cmax,
        visual_aabb_min=vmin,   visual_aabb_max=vmax,
        convex_decomposition_hull_count=hull_count,
        cooking_error=cooking_error,
        collision_group=collision_group,
        custom_data=custom_data,
    )


def _rb(
    path: str,
    *,
    is_kinematic: bool = False,
    mass: float | None = 1.0,
    density: float | None = None,
    volume_m3: float | None = None,
) -> RigidBodyInfo:
    return RigidBodyInfo(
        path=path, is_kinematic=is_kinematic,
        mass=mass, density=density, volume_m3=volume_m3,
    )


def _run(
    colliders: list[ColliderInfo],
    rigid_bodies: list[RigidBodyInfo],
    *,
    criteria: AcceptanceCriteria | None = None,
) -> list[Issue]:
    ins = MockColliderInspector(colliders=colliders, rigid_bodies=rigid_bodies)
    ctx = ValidationContext(
        asset_uri="test://stage",
        criteria=criteria or AcceptanceCriteria(),
        collider_inspector=ins,
    )
    return ColliderValidator(ctx.criteria).run(ctx)


# ============================================================== setup ==


class TestSetup:
    def test_missing_inspector_fails(self):
        ctx = ValidationContext(asset_uri="t", criteria=AcceptanceCriteria())
        issues = ColliderValidator(ctx.criteria).run(ctx)
        assert len(issues) == 1
        assert issues[0].code     == CODE_NO_COLLIDER_INSPECTOR
        assert issues[0].severity == Severity.FAIL

    def test_empty_stage_no_issues(self):
        assert _run([], []) == []

    def test_well_formed_dynamic_rb_with_box_collider_no_issues(self):
        rb = _rb("/A")
        c  = _coll("/A/coll", "box", rigid_body_path="/A")
        assert _run([c], [rb]) == []


# ============================================================== §3.1 ==


class TestOrphanCollider:
    def test_orphan_collider_fails(self):
        c = _coll("/orphan", "box", rigid_body_path=None)
        codes = [i.code for i in _run([c], [])]
        assert CODE_NO_RIGID_BODY_ANCESTOR in codes
        i = next(i for i in _run([c], []) if i.code == CODE_NO_RIGID_BODY_ANCESTOR)
        assert i.severity == Severity.FAIL

    def test_orphan_with_static_collider_flag_allowed(self):
        c = _coll("/static", "box", rigid_body_path=None,
                  custom_data=(("static_collider", True),))
        codes = [i.code for i in _run([c], [])]
        assert CODE_NO_RIGID_BODY_ANCESTOR not in codes


# ============================================================== §3.2 ==


class TestRigidBodyWithoutCollider:
    def test_rigid_body_with_no_colliders_fails(self):
        rb = _rb("/A")
        codes = [i.code for i in _run([], [rb])]
        assert CODE_RIGID_BODY_WITHOUT_COLL in codes

    def test_rigid_body_with_collider_ok(self):
        rb = _rb("/A")
        c  = _coll("/A/c", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_RIGID_BODY_WITHOUT_COLL not in codes

    def test_collider_pointing_at_unknown_rb_does_not_satisfy(self):
        rb = _rb("/A")
        # collider declares rigid_body_path that doesn't match any RB
        c  = _coll("/A/c", rigid_body_path="/B")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_RIGID_BODY_WITHOUT_COLL in codes


# ============================================================== §3.3 ==


class TestMeshOnDynamic:
    def test_none_approximation_on_dynamic_fails(self):
        rb = _rb("/A", is_kinematic=False)
        c  = _coll("/A/c", "none", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MESH_ON_DYNAMIC in codes

    def test_mesh_simplification_on_dynamic_fails(self):
        rb = _rb("/A", is_kinematic=False)
        c  = _coll("/A/c", "meshSimplification", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MESH_ON_DYNAMIC in codes

    def test_convex_hull_on_dynamic_ok(self):
        rb = _rb("/A", is_kinematic=False)
        c  = _coll("/A/c", "convexHull", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MESH_ON_DYNAMIC not in codes

    def test_none_approximation_on_kinematic_ok(self):
        rb = _rb("/A", is_kinematic=True)
        c  = _coll("/A/c", "none", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MESH_ON_DYNAMIC not in codes

    def test_none_approximation_on_static_collider_ok(self):
        # static collider (no RB ancestor, flagged) — mesh approximation is OK
        c = _coll("/static", "none", rigid_body_path=None,
                  custom_data=(("static_collider", True),))
        codes = [i.code for i in _run([c], [])]
        assert CODE_MESH_ON_DYNAMIC not in codes


# ============================================================== §3.4 ==


class TestConvexDecomposition:
    def test_low_hull_count_ok(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "convexDecomposition", rigid_body_path="/A", hull_count=20)
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_CONVEX_DECOMP_HULL_LIM not in codes

    def test_hull_count_above_warn_warns(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "convexDecomposition", rigid_body_path="/A", hull_count=40)
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_CONVEX_DECOMP_HULL_LIM)
        assert i.severity == Severity.WARN
        assert i.metric_dict()["hull_count"] == 40.0

    def test_hull_count_above_fail_fails(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "convexDecomposition", rigid_body_path="/A", hull_count=100)
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_CONVEX_DECOMP_HULL_LIM)
        assert i.severity == Severity.FAIL

    def test_hull_count_check_skipped_for_other_approximations(self):
        rb = _rb("/A")
        # box collider with bogus hull_count — should not trigger the check
        c  = _coll("/A/c", "box", rigid_body_path="/A", hull_count=999)
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_CONVEX_DECOMP_HULL_LIM not in codes


# ============================================================== §3.5 ==


class TestAABBMismatch:
    def test_collider_matching_visual_ok(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (1,1,1)), visual_aabb=((0,0,0), (1,1,1)))
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_AABB_MISMATCH not in codes

    def test_collider_within_tolerance_ok(self):
        rb = _rb("/A")
        # 1.08x on X axis — within default 1.10
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (1.08,1,1)), visual_aabb=((0,0,0), (1,1,1)))
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_AABB_MISMATCH not in codes

    def test_collider_exceeding_tolerance_warns(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (1.2,1,1)), visual_aabb=((0,0,0), (1,1,1)))
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_AABB_MISMATCH)
        assert i.severity == Severity.WARN

    def test_missing_aabb_data_skips_check(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=None, visual_aabb=None)
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_AABB_MISMATCH not in codes


# ============================================================== §3.6 ==


class TestCollisionGroup:
    def test_explicit_group_ok(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "box", rigid_body_path="/A", collision_group="parts")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MISSING_COLLISION_GROUP not in codes

    def test_missing_group_warns(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "box", rigid_body_path="/A", collision_group=None)
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_MISSING_COLLISION_GROUP)
        assert i.severity == Severity.WARN


# ============================================================== §3.7 ==


class TestCookingFailed:
    def test_cooking_error_fails(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "convexHull", rigid_body_path="/A",
                   cooking_error="degenerate input")
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_COOKING_FAILED)
        assert i.severity == Severity.FAIL


# ============================================================== §3.9 ==


class TestMassRange:
    def test_mass_within_range_ok(self):
        rb = _rb("/A", mass=10.0)
        c  = _coll("/A/c", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MASS_OUT_OF_RANGE not in codes

    def test_mass_below_range_warns(self):
        rb = _rb("/A", mass=1.0e-4)
        c  = _coll("/A/c", rigid_body_path="/A")
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_MASS_OUT_OF_RANGE)
        assert i.severity == Severity.WARN

    def test_mass_above_range_warns(self):
        rb = _rb("/A", mass=1.0e7)
        c  = _coll("/A/c", rigid_body_path="/A")
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_MASS_OUT_OF_RANGE)
        assert i.severity == Severity.WARN

    def test_mass_none_skipped(self):
        rb = _rb("/A", mass=None)
        c  = _coll("/A/c", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MASS_OUT_OF_RANGE not in codes


# ============================================================== §3.10 ==


class TestMassDensityConflict:
    def test_consistent_mass_density_no_issue(self):
        # mass = density * volume → no conflict
        rb = _rb("/A", mass=10.0, density=1000.0, volume_m3=0.01)
        c  = _coll("/A/c", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MASS_DENSITY_CONFLICT not in codes

    def test_inconsistent_mass_density_warns(self):
        # mass = 10kg, density*volume = 2kg → 80% off
        rb = _rb("/A", mass=10.0, density=200.0, volume_m3=0.01)
        c  = _coll("/A/c", rigid_body_path="/A")
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_MASS_DENSITY_CONFLICT)
        assert i.severity == Severity.WARN

    def test_within_tolerance_no_issue(self):
        # mass=10, density*volume=10.5 → 5% off, within default 10%
        rb = _rb("/A", mass=10.0, density=1050.0, volume_m3=0.01)
        c  = _coll("/A/c", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MASS_DENSITY_CONFLICT not in codes

    def test_missing_volume_skips_check(self):
        rb = _rb("/A", mass=10.0, density=1000.0, volume_m3=None)
        c  = _coll("/A/c", rigid_body_path="/A")
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_MASS_DENSITY_CONFLICT not in codes


# =========================================== unstable geometry heuristics ==


class TestDegenerateAABB:
    def test_zero_thickness_axis_warns(self):
        rb = _rb("/A")
        # Z-axis extent = 0 (paper-thin) — below default 0.1mm minimum
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (1,1,0.0)),
                   visual_aabb=((0,0,0), (1,1,0.0)))
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_DEGENERATE_AABB)
        assert i.severity == Severity.WARN

    def test_thin_axis_below_threshold_warns(self):
        rb = _rb("/A")
        # 50 micrometers — below 0.1mm
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (1,1,5.0e-5)),
                   visual_aabb=((0,0,0), (1,1,5.0e-5)))
        issues = _run([c], [rb])
        i = next(i for i in issues if i.code == CODE_DEGENERATE_AABB)
        assert i.severity == Severity.WARN


class TestExtremeAspectRatio:
    def test_extreme_aspect_ratio_warns(self):
        rb = _rb("/A")
        # Ratio = 2000:1 — exceeds default 1000
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (2.0, 0.001, 0.001)),
                   visual_aabb=((0,0,0), (2.0, 0.001, 0.001)))
        issues = _run([c], [rb])
        # Don't get degenerate (min extent = 1mm > 0.1mm); should get aspect ratio
        i = next(i for i in issues if i.code == CODE_EXTREME_ASPECT_RATIO)
        assert i.severity == Severity.WARN

    def test_normal_aspect_ratio_ok(self):
        rb = _rb("/A")
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (2,1,1)),
                   visual_aabb=((0,0,0), (2,1,1)))
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_EXTREME_ASPECT_RATIO not in codes

    def test_degenerate_aabb_supersedes_aspect_ratio(self):
        # When AABB is degenerate (zero or near-zero axis), only DEGENERATE_AABB
        # fires; aspect ratio isn't reported on top.
        rb = _rb("/A")
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (1.0, 1.0, 0.0)),
                   visual_aabb=((0,0,0), (1.0, 1.0, 0.0)))
        codes = [i.code for i in _run([c], [rb])]
        assert CODE_DEGENERATE_AABB      in codes
        assert CODE_EXTREME_ASPECT_RATIO not in codes


# ============================================================ determinism ==


class TestDeterminism:
    def _stage(self):
        rbs = [
            _rb("/Z", mass=1.0e7),                              # mass out-of-range WARN
            _rb("/A"),                                           # has collider; no issues from this
            _rb("/lonely", mass=None),                          # no collider → FAIL
        ]
        colls = [
            _coll("/A/c1", "box", rigid_body_path="/A"),
            _coll("/orphan", "box", rigid_body_path=None),      # FAIL
            _coll("/A/c2", "none", rigid_body_path="/A"),       # mesh on dynamic FAIL
        ]
        return colls, rbs

    def test_same_input_same_output(self):
        c, r = self._stage()
        assert _run(c, r) == _run(c, r)

    def test_input_order_does_not_change_output(self):
        c, r = self._stage()
        assert _run(c, r) == _run(list(reversed(c)), list(reversed(r)))

    def test_sorted_severity_desc_then_code(self):
        c, r = self._stage()
        issues = _run(c, r)
        sevs   = [i.severity for i in issues]
        assert sevs == sorted(sevs, reverse=True)
        # Within each severity bucket, codes lexicographically sorted.
        for s in (Severity.FAIL, Severity.WARN, Severity.INFO):
            codes = [i.code for i in issues if i.severity == s]
            assert codes == sorted(codes)


# ====================================================== custom criteria ==


class TestCustomCriteria:
    def test_tighter_aabb_ratio_promotes_to_warn(self):
        criteria = AcceptanceCriteria(
            collider=ColliderThresholds(aabb_ratio_max=1.05),
        )
        rb = _rb("/A")
        c  = _coll("/A/c", "box", rigid_body_path="/A",
                   collider_aabb=((0,0,0), (1.08,1,1)),
                   visual_aabb=((0,0,0), (1,1,1)))
        codes = [i.code for i in _run([c], [rb], criteria=criteria)]
        assert CODE_AABB_MISMATCH in codes

    def test_looser_hull_thresholds_allows_high_count(self):
        criteria = AcceptanceCriteria(
            collider=ColliderThresholds(convex_decomp_hull_warn=200,
                                        convex_decomp_hull_fail=400),
        )
        rb = _rb("/A")
        c  = _coll("/A/c", "convexDecomposition", rigid_body_path="/A", hull_count=100)
        codes = [i.code for i in _run([c], [rb], criteria=criteria)]
        assert CODE_CONVEX_DECOMP_HULL_LIM not in codes


# ====================================================== validator metadata ==


class TestValidatorMetadata:
    def test_name_and_phase(self):
        assert ColliderValidator.name  == "collider"
        assert ColliderValidator.phase == "static"

    def test_issues_carry_validator_name(self):
        c = _coll("/orphan", "box", rigid_body_path=None)
        issues = _run([c], [])
        assert all(i.validator == "collider" for i in issues)
