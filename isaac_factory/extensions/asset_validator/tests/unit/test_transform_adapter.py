"""Integration tests for `UsdStageInspector` against synthetic `.usda` fixtures.

Pattern mirrors `test_usd_grounding_inspector.py` — open fixture, build
adapter, run the validator, assert the expected Issue codes are emitted.

Runtime: `research` profile (conda env_isaaclab, Python 3.10.12 +
usd-core 26.3 + pyyaml 6.0.3). No Kit, no PhysX.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pxr = pytest.importorskip("pxr")
from pxr import Usd                                              # noqa: E402

from asset_validator import (                                     # noqa: E402
    AcceptanceCriteria,
    Severity,
    TransformValidator,
    ValidationContext,
)
from asset_validator.adapters.usd_stage_inspector import (       # noqa: E402
    UsdStageInspector,
)
from asset_validator.validators.transform import (               # noqa: E402
    CODE_CASCADE_INVALID_WORLD,
    CODE_FLOATING_HEURISTIC,
    CODE_INF_VALUE,
    CODE_NAN_VALUE,
    CODE_NON_POSITIVE_SCALE,
    CODE_QUATERNION_DENORMAL,
    CODE_ROTATION_NON_ORTHOGONAL,
    CODE_TIME_SAMPLED_ON_STATIC,
    CODE_XFORMOP_ORDER_INVALID,
    CODE_ZERO_SCALE,
)


_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "transform"


def _open(name: str) -> Usd.Stage:
    path = _FIXTURE_DIR / name
    assert path.is_file(), f"missing fixture: {path}"
    stage = Usd.Stage.Open(str(path))
    assert stage, f"failed to open {path}"
    return stage


def _validate(stage: Usd.Stage):
    inspector = UsdStageInspector(stage=stage)
    ctx = ValidationContext(
        asset_uri=str(stage.GetRootLayer().identifier),
        criteria=AcceptanceCriteria(),
        stage_inspector=inspector,
    )
    return TransformValidator(ctx.criteria).run(ctx)


# ============================================================ clean ==


class TestClean:
    def test_clean_assembly_passes(self):
        issues = _validate(_open("clean_transforms.usda"))
        assert issues == [], f"expected clean; got: {[i.code for i in issues]}"


# ========================================================== non-finite ==


class TestNonFinite:
    def test_nan_translation_fails(self):
        issues = _validate(_open("nan_translation.usda"))
        nans = [i for i in issues if i.code == CODE_NAN_VALUE]
        assert len(nans) == 1
        assert nans[0].severity == Severity.FAIL
        assert nans[0].prim_paths == ("/World/Box",)

    def test_inf_scale_fails(self):
        issues = _validate(_open("inf_scale.usda"))
        infs = [i for i in issues if i.code == CODE_INF_VALUE]
        assert len(infs) == 1
        assert infs[0].severity == Severity.FAIL


# =============================================================== scale ==


class TestScale:
    def test_zero_scale_fails(self):
        issues = _validate(_open("zero_scale.usda"))
        codes = [i.code for i in issues]
        assert CODE_ZERO_SCALE in codes

    def test_negative_scale_warns(self):
        issues = _validate(_open("negative_scale.usda"))
        ns = [i for i in issues if i.code == CODE_NON_POSITIVE_SCALE]
        assert len(ns) == 1
        assert ns[0].severity == Severity.WARN

    def test_mirror_metadata_suppresses_negative_scale_warning(self):
        issues = _validate(_open("mirror_allowed.usda"))
        assert all(i.code != CODE_NON_POSITIVE_SCALE for i in issues)
        # Whole asset is clean — no other issues either.
        assert issues == []


# ============================================================= rotation ==


class TestRotation:
    def test_denormal_quaternion_fails(self):
        issues = _validate(_open("denormal_quat.usda"))
        codes = [i.code for i in issues]
        assert CODE_QUATERNION_DENORMAL in codes

    def test_non_orthogonal_matrix_fails(self):
        issues = _validate(_open("non_orthogonal_matrix.usda"))
        codes = [i.code for i in issues]
        assert CODE_ROTATION_NON_ORTHOGONAL in codes


# ================================================= floating heuristic ==


class TestFloatingHeuristic:
    def test_high_translate_z_warns(self):
        issues = _validate(_open("floating_high.usda"))
        fhs = [i for i in issues if i.code == CODE_FLOATING_HEURISTIC]
        assert len(fhs) == 1
        assert fhs[0].severity == Severity.WARN
        assert fhs[0].metric_dict()["translate_z_m"] == pytest.approx(200.0)


# ============================================================= cascade ==


class TestCascade:
    def test_descendant_of_failing_parent_gets_info(self):
        issues = _validate(_open("cascade_invalid.usda"))
        codes = [i.code for i in issues]
        assert CODE_NAN_VALUE in codes
        assert CODE_CASCADE_INVALID_WORLD in codes
        # The cascade INFO points at the child, not the parent.
        cascade = next(i for i in issues if i.code == CODE_CASCADE_INVALID_WORLD)
        assert cascade.prim_paths == ("/World/Root/Child",)


# ===================================================== time-sampled drift ==


class TestTimeSamples:
    def test_time_sampled_on_static_warns(self):
        issues = _validate(_open("time_sampled_static.usda"))
        ts = [i for i in issues if i.code == CODE_TIME_SAMPLED_ON_STATIC]
        assert len(ts) == 1
        assert ts[0].severity == Severity.WARN
        assert ts[0].metric_dict()["time_sample_count"] >= 1.0


# ======================================================= xformOpOrder ==


class TestXformOpOrder:
    def test_unresolved_op_in_order_fails(self):
        issues = _validate(_open("xformop_order_corrupt.usda"))
        codes = [i.code for i in issues]
        assert CODE_XFORMOP_ORDER_INVALID in codes


# ============================================================ inspector ==


class TestInspectorBasics:
    def test_iter_in_path_sorted_order(self):
        stage = _open("clean_transforms.usda")
        prims = list(UsdStageInspector(stage=stage).iter_xformable_prims())
        paths = [p.path for p in prims]
        assert paths == sorted(paths)

    def test_parent_path_resolves_correctly(self):
        stage = _open("cascade_invalid.usda")
        prims = {p.path: p for p in UsdStageInspector(stage=stage).iter_xformable_prims()}
        assert prims["/World/Root"].parent_path == "/World"
        assert prims["/World/Root/Child"].parent_path == "/World/Root"
        # /World's parent is the pseudo-root → None
        assert prims["/World"].parent_path is None

    def test_op_value_count_matches_op_type(self):
        stage = _open("clean_transforms.usda")
        prims = list(UsdStageInspector(stage=stage).iter_xformable_prims())
        for p in prims:
            for op in p.ops:
                if op.op_type in ("translate", "scale", "rotate_euler"):
                    assert len(op.values) == 3, (p.path, op.op_name, op.values)
                elif op.op_type == "rotate_quat":
                    assert len(op.values) == 4
                elif op.op_type == "transform_matrix":
                    assert len(op.values) == 16
                elif op.op_type == "rotate_axis":
                    assert len(op.values) == 1

    def test_mirror_metadata_propagated(self):
        stage = _open("mirror_allowed.usda")
        prims = {p.path: p for p in UsdStageInspector(stage=stage).iter_xformable_prims()}
        mp = prims["/World/MirroredPart"]
        assert mp.is_mirror() is True


# ============================================================ determinism ==


class TestDeterminism:
    def test_same_stage_same_prims(self):
        stage = _open("clean_transforms.usda")
        p1 = list(UsdStageInspector(stage=stage).iter_xformable_prims())
        p2 = list(UsdStageInspector(stage=stage).iter_xformable_prims())
        assert p1 == p2

    def test_validator_output_stable_across_runs(self):
        stage = _open("non_orthogonal_matrix.usda")
        a = _validate(stage)
        b = _validate(stage)
        assert a == b
