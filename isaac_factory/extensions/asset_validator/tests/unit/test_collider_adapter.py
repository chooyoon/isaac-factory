"""Runtime B integration tests for `PhysXColliderInspector`.

Mirrors the pattern in test_overlap_adapter.py — module-level skip if
`isaacsim` isn't importable, module-scoped sim_app fixture, opened_stage
fixture with the Isaac Sim 5 / older return-shape compatibility shim.

Run via:

    python isaac_factory/extensions/asset_validator/tools/runtime_b_pytest_runner.py \\
        isaac_factory/extensions/asset_validator/tests/unit/test_collider_adapter.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Skip the whole module if not running under Kit Python.
try:
    import isaacsim  # noqa: F401
    _ISAAC_AVAILABLE = True
except ImportError:
    _ISAAC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _ISAAC_AVAILABLE,
    reason="Kit Python (Runtime B) required — isaacsim package not importable",
)


_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "collider"


# ============================================================ sim_app ==


@pytest.fixture(scope="module")
def sim_app():
    """Boot SimulationApp once for all tests in this module."""
    try:
        from isaacsim import SimulationApp
        app = SimulationApp({"headless": True})
    except Exception as e:                                       # pragma: no cover
        pytest.skip(f"SimulationApp boot failed: {e}")
    yield app
    try:
        app.close()
    except Exception:                                            # pragma: no cover
        pass


@pytest.fixture()
def opened_stage(sim_app, request):
    """Open a fixture .usda via omni.usd; yield a callable that returns the stage."""
    import omni.usd
    ctx = omni.usd.get_context()

    def _open(name: str):
        path = _FIXTURE_DIR / f"{name}.usda"
        assert path.is_file(), f"missing fixture: {path}"
        # Isaac Sim 5.0: open_stage returns bool; older: (bool, error).
        rv = ctx.open_stage(str(path))
        if isinstance(rv, tuple):
            result, error = rv
            assert result, f"open_stage failed: {error}"
        else:
            assert rv, f"open_stage failed for: {path}"
        return ctx.get_stage()

    yield _open

    ctx.new_stage()


def _build_inspector_and_validate(stage):
    """Helper: build inspector + run ColliderValidator; return (issues, inspector)."""
    from asset_validator import (
        AcceptanceCriteria, ColliderValidator, ValidationContext,
    )
    from asset_validator.adapters.physx_collider_inspector import (
        PhysXColliderInspector,
    )

    inspector = PhysXColliderInspector(stage=stage)
    ctx = ValidationContext(
        asset_uri="test://collider",
        criteria=AcceptanceCriteria(),
        collider_inspector=inspector,
    )
    issues = ColliderValidator(ctx.criteria).run(ctx)
    return issues, inspector


def _codes(issues):
    return [i.code for i in issues]


# ====================================================== clean assembly ==


class TestCleanAssembly:
    """Floor with static_collider flag + cube with RB+CollisionAPI.
    Only the MISSING_COLLISION_GROUP warnings should fire (filter groups
    are not authored on these fixtures by design)."""

    def test_no_structural_failures(self, opened_stage):
        from asset_validator.validators.collider import (
            CODE_DEGENERATE_AABB,
            CODE_EXTREME_ASPECT_RATIO,
            CODE_MESH_ON_DYNAMIC,
            CODE_NO_RIGID_BODY_ANCESTOR,
            CODE_RIGID_BODY_WITHOUT_COLL,
        )

        stage = opened_stage("clean_collider_assembly")
        issues, inspector = _build_inspector_and_validate(stage)
        codes = _codes(issues)
        try:
            assert CODE_NO_RIGID_BODY_ANCESTOR  not in codes
            assert CODE_RIGID_BODY_WITHOUT_COLL not in codes
            assert CODE_MESH_ON_DYNAMIC         not in codes
            assert CODE_DEGENERATE_AABB         not in codes
            assert CODE_EXTREME_ASPECT_RATIO    not in codes
        finally:
            inspector.close()

    def test_inspector_emits_two_colliders_and_one_rb(self, opened_stage):
        from asset_validator.adapters.physx_collider_inspector import (
            PhysXColliderInspector,
        )
        stage = opened_stage("clean_collider_assembly")
        ins = PhysXColliderInspector(stage=stage)
        try:
            cols = list(ins.iter_colliders())
            rbs  = list(ins.iter_rigid_bodies())
            # /World/Floor + /World/DynBox
            assert sorted(c.path for c in cols) == ["/World/DynBox", "/World/Floor"]
            # /World/DynBox carries RB
            assert sorted(r.path for r in rbs) == ["/World/DynBox"]

            floor = next(c for c in cols if c.path.endswith("Floor"))
            dynbox = next(c for c in cols if c.path.endswith("DynBox"))
            assert floor.approximation == "box"
            assert dynbox.approximation == "box"
            assert dynbox.rigid_body_path == "/World/DynBox"
            # Floor's static_collider customData propagated
            cd = dict(floor.custom_data)
            assert cd.get("static_collider") is True
        finally:
            ins.close()


# =========================================================== orphan ==


class TestOrphanCollider:
    def test_no_rigid_body_ancestor_fires(self, opened_stage):
        from asset_validator.validators.collider import CODE_NO_RIGID_BODY_ANCESTOR

        stage = opened_stage("orphan_collider")
        issues, inspector = _build_inspector_and_validate(stage)
        try:
            assert CODE_NO_RIGID_BODY_ANCESTOR in _codes(issues)
            i = next(i for i in issues if i.code == CODE_NO_RIGID_BODY_ANCESTOR)
            assert i.prim_paths == ("/World/Loose",)
        finally:
            inspector.close()


# ============================================== RB without collider ==


class TestRigidBodyWithoutCollider:
    def test_fires_when_rb_has_no_collider_descendant(self, opened_stage):
        from asset_validator.validators.collider import CODE_RIGID_BODY_WITHOUT_COLL

        stage = opened_stage("rb_without_collider")
        issues, inspector = _build_inspector_and_validate(stage)
        try:
            assert CODE_RIGID_BODY_WITHOUT_COLL in _codes(issues)
            i = next(i for i in issues if i.code == CODE_RIGID_BODY_WITHOUT_COLL)
            assert i.prim_paths == ("/World/EmptyRB",)
        finally:
            inspector.close()


# ============================================== mesh on dynamic ==


class TestMeshOnDynamic:
    def test_triangle_mesh_on_dynamic_body_caught(self, opened_stage):
        from asset_validator.validators.collider import CODE_MESH_ON_DYNAMIC

        stage = opened_stage("mesh_on_dynamic")
        issues, inspector = _build_inspector_and_validate(stage)
        try:
            codes = _codes(issues)
            assert CODE_MESH_ON_DYNAMIC in codes
            i = next(i for i in issues if i.code == CODE_MESH_ON_DYNAMIC)
            # Mesh path participates + closest RB path
            assert "/World/TriMesh" in i.prim_paths
        finally:
            inspector.close()

    def test_inspector_reports_approximation_none(self, opened_stage):
        from asset_validator.adapters.physx_collider_inspector import (
            PhysXColliderInspector,
        )
        stage = opened_stage("mesh_on_dynamic")
        ins = PhysXColliderInspector(stage=stage)
        try:
            cols = list(ins.iter_colliders())
            assert len(cols) == 1
            assert cols[0].approximation == "none"
            assert cols[0].rigid_body_path == "/World/TriMesh"
        finally:
            ins.close()


# ============================================== degenerate AABB ==


class TestDegenerateAABB:
    def test_thin_collider_caught(self, opened_stage):
        from asset_validator.validators.collider import CODE_DEGENERATE_AABB

        stage = opened_stage("degenerate_aabb")
        issues, inspector = _build_inspector_and_validate(stage)
        try:
            assert CODE_DEGENERATE_AABB in _codes(issues)
            i = next(i for i in issues if i.code == CODE_DEGENERATE_AABB)
            assert i.prim_paths == ("/World/Paper",)
            # Reported min extent should be below threshold
            min_ext = i.metric_dict().get("min_extent_m")
            assert min_ext is not None
            assert min_ext < 1.0e-4
        finally:
            inspector.close()


# ============================================== determinism ==


class TestDeterminism:
    def test_same_stage_same_collider_set(self, opened_stage):
        from asset_validator.adapters.physx_collider_inspector import (
            PhysXColliderInspector,
        )
        stage = opened_stage("clean_collider_assembly")
        ins_a = PhysXColliderInspector(stage=stage)
        try:
            cols_a = list(ins_a.iter_colliders())
            cols_b = list(ins_a.iter_colliders())
            # Re-iterating should yield identical paths + approximations
            assert [c.path for c in cols_a] == [c.path for c in cols_b]
            assert [c.approximation for c in cols_a] == [c.approximation for c in cols_b]
        finally:
            ins_a.close()


# ============================================== lifecycle ==


class TestLifecycle:
    def test_context_manager_releases_log_handle(self, opened_stage):
        from asset_validator.adapters.physx_collider_inspector import (
            PhysXColliderInspector,
        )
        stage = opened_stage("clean_collider_assembly")
        with PhysXColliderInspector(stage=stage) as ins:
            pre = ins._log_handle  # may be None if omni.log subscription failed
            _ = list(ins.iter_colliders())
        # After context exit, the handle must be None
        assert ins._log_handle is None  # noqa: SLF001
