"""Scene-level integration tests for ColliderValidator.

Builds rigid-body + collider scenes that resemble real factory cells
(static floor, kinematic workbench, dynamic parts) and asserts the
validator picks out the right issues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from asset_validator import (
    AcceptanceCriteria,
    ColliderInfo,
    ColliderInspector,
    ColliderValidator,
    RigidBodyInfo,
    Severity,
    ValidationContext,
)
from asset_validator.validators.collider import (
    CODE_AABB_MISMATCH,
    CODE_MESH_ON_DYNAMIC,
    CODE_MISSING_COLLISION_GROUP,
    CODE_NO_RIGID_BODY_ANCESTOR,
    CODE_RIGID_BODY_WITHOUT_COLL,
)


# --------------------------------------------------------------- mock --


@dataclass
class _Phys:
    colliders:    list[ColliderInfo]  = field(default_factory=list)
    rigid_bodies: list[RigidBodyInfo] = field(default_factory=list)

    def iter_colliders(self) -> Iterable[ColliderInfo]:
        return list(self.colliders)

    def iter_rigid_bodies(self) -> Iterable[RigidBodyInfo]:
        return list(self.rigid_bodies)


_: ColliderInspector = _Phys()


def _coll(path, approx="box", *, rb=None, group="parts",
          aabb=((0,0,0), (1,1,1)), visual=((0,0,0), (1,1,1)),
          custom=()):
    return ColliderInfo(
        path=path, approximation=approx, rigid_body_path=rb,
        collider_aabb_min=aabb[0], collider_aabb_max=aabb[1],
        visual_aabb_min=visual[0], visual_aabb_max=visual[1],
        collision_group=group, custom_data=custom,
    )


def _rb(path, *, kin=False, mass=1.0):
    return RigidBodyInfo(path=path, is_kinematic=kin, mass=mass)


def _run(colliders, rigid_bodies):
    ctx = ValidationContext(
        asset_uri="test://scene",
        criteria=AcceptanceCriteria(),
        collider_inspector=_Phys(colliders=list(colliders),
                                 rigid_bodies=list(rigid_bodies)),
    )
    return ColliderValidator(ctx.criteria).run(ctx)


# ============================================================== scenes ==


class TestCleanAssembly:
    """A floor (static collider), a workbench (kinematic RB + mesh),
    two dynamic parts (RB + convex hull). All clean."""

    def test_clean_assembly_passes(self):
        rbs = [
            _rb("/Cell/Workbench", kin=True, mass=50.0),
            _rb("/Cell/PartA"),
            _rb("/Cell/PartB"),
        ]
        cols = [
            _coll("/Cell/Floor", approx="none",
                  custom=(("static_collider", True),)),         # static; OK
            _coll("/Cell/Workbench/Coll", approx="meshSimplification",
                  rb="/Cell/Workbench"),                         # kinematic; mesh OK
            _coll("/Cell/PartA/Coll", approx="convexHull",   rb="/Cell/PartA"),
            _coll("/Cell/PartB/Coll", approx="convexDecomposition", rb="/Cell/PartB"),
        ]
        assert _run(cols, rbs) == []


class TestOrphanCollider:
    """A loose collider with no RB ancestor and no static_collider flag."""

    def test_orphan_caught(self):
        cols = [_coll("/Loose", approx="box", rb=None)]
        codes = [i.code for i in _run(cols, [])]
        assert codes == [CODE_NO_RIGID_BODY_ANCESTOR]


class TestRigidBodyWithoutCollider:
    """RB that lost its collider (delete-by-accident scenario)."""

    def test_rb_alone_fails(self):
        rbs = [_rb("/RB_NoColl")]
        codes = [i.code for i in _run([], rbs)]
        assert codes == [CODE_RIGID_BODY_WITHOUT_COLL]


class TestDynamicWithMeshApproximation:
    """A dynamic RB with raw triangle mesh — common authoring mistake."""

    def test_triangle_mesh_caught(self):
        rbs  = [_rb("/Dyn")]
        cols = [_coll("/Dyn/Coll", approx="none", rb="/Dyn")]
        issues = _run(cols, rbs)
        codes = [i.code for i in issues]
        assert CODE_MESH_ON_DYNAMIC in codes
        msg = next(i for i in issues if i.code == CODE_MESH_ON_DYNAMIC).message
        assert "Dyn" in msg and "none" in msg


class TestMultiIssueCell:
    """A bad cell mixing several distinct failures plus a clean part."""

    def test_multiple_codes_each_isolated(self):
        rbs = [
            _rb("/Cell/CleanRB"),                              # has collider; OK
            _rb("/Cell/EmptyRB"),                              # RB w/o coll FAIL
            _rb("/Cell/DynRB"),                                # dynamic but has mesh FAIL
        ]
        cols = [
            _coll("/Cell/CleanRB/Coll", "box", rb="/Cell/CleanRB"),
            _coll("/Cell/DynRB/Coll",   "none", rb="/Cell/DynRB"),
            _coll("/Cell/Orphan",       "box", rb=None),       # orphan FAIL
            _coll("/Cell/NoGroup/Coll", "box", rb="/Cell/CleanRB", group=None),  # WARN
            _coll("/Cell/BadAABB/Coll", "box", rb="/Cell/CleanRB",
                  aabb=((0,0,0), (1.5, 1, 1)),
                  visual=((0,0,0), (1, 1, 1))),                # AABB mismatch WARN
        ]
        issues = _run(cols, rbs)
        codes  = [i.code for i in issues]

        # Each expected code appears at least once
        for c in (CODE_NO_RIGID_BODY_ANCESTOR,
                  CODE_RIGID_BODY_WITHOUT_COLL,
                  CODE_MESH_ON_DYNAMIC,
                  CODE_MISSING_COLLISION_GROUP,
                  CODE_AABB_MISMATCH):
            assert c in codes, f"missing expected code: {c}"

        # FAIL severities sort before WARN severities
        sevs = [i.severity for i in issues]
        assert sevs == sorted(sevs, reverse=True)
        fails = [i for i in issues if i.severity == Severity.FAIL]
        warns = [i for i in issues if i.severity == Severity.WARN]
        assert len(fails) == 3        # orphan, empty RB, mesh-on-dyn
        assert len(warns) == 2        # no group, AABB mismatch


class TestStaticColliderWaiver:
    """`customData['static_collider']=True` suppresses §3.1 FAIL."""

    def test_flagged_static_no_orphan_warning(self):
        cols = [
            _coll("/Cell/Floor",    "none", rb=None,
                  custom=(("static_collider", True),)),
            _coll("/Cell/Walls",    "box",  rb=None,
                  custom=(("static_collider", True),)),
        ]
        issues = _run(cols, [])
        assert all(i.code != CODE_NO_RIGID_BODY_ANCESTOR for i in issues)


class TestSceneDeterminism:
    def test_collider_and_rb_order_does_not_change_output(self):
        rbs  = [_rb("/A"), _rb("/B")]
        cols = [
            _coll("/A/c", "box", rb="/A"),
            _coll("/B/c", "none", rb="/B"),
            _coll("/orphan", "box", rb=None),
        ]
        a = _run(cols, rbs)
        b = _run(list(reversed(cols)), list(reversed(rbs)))
        assert a == b
