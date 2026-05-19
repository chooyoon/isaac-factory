"""Unit tests for TransformValidator.

Pure Python: no pxr, no omni, no isaacsim. The validator depends only on
the StageInspector protocol; tests inject a MockStageInspector.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import pytest

from asset_validator import (
    AcceptanceCriteria,
    Issue,
    Severity,
    StageInspector,
    TransformOp,
    TransformThresholds,
    TransformValidator,
    ValidationContext,
    XformablePrim,
)
from asset_validator.validators.transform import (
    CODE_CASCADE_INVALID_WORLD,
    CODE_FLOATING_HEURISTIC,
    CODE_INF_VALUE,
    CODE_MIXED_OP_ORDER,
    CODE_NAN_VALUE,
    CODE_NO_STAGE_INSPECTOR,
    CODE_NON_POSITIVE_SCALE,
    CODE_OP_VALUE_COUNT_MISMATCH,
    CODE_QUATERNION_DENORMAL,
    CODE_ROTATION_NON_ORTHOGONAL,
    CODE_SCALE_OUT_OF_RANGE,
    CODE_TIME_SAMPLED_ON_STATIC,
    CODE_TRANSLATION_OUT_OF_RANGE,
    CODE_XFORMOP_ORDER_INVALID,
    CODE_ZERO_SCALE,
)


# ===================================================================== mock ==


@dataclass
class MockStageInspector:
    prims: list[XformablePrim] = field(default_factory=list)

    def iter_xformable_prims(self) -> Iterable[XformablePrim]:
        return list(self.prims)


# Structural check that MockStageInspector satisfies the Protocol.
_: StageInspector = MockStageInspector()


# ================================================================== helpers ==


def _translate(values=(0.0, 0.0, 0.0), *, ts: int = 0) -> TransformOp:
    return TransformOp(op_name="xformOp:translate", op_type="translate",
                       values=tuple(float(v) for v in values), time_sample_count=ts)


def _scale(values=(1.0, 1.0, 1.0)) -> TransformOp:
    return TransformOp(op_name="xformOp:scale", op_type="scale",
                       values=tuple(float(v) for v in values))


def _quat(w=1.0, x=0.0, y=0.0, z=0.0) -> TransformOp:
    return TransformOp(op_name="xformOp:orient", op_type="rotate_quat",
                       values=(float(w), float(x), float(y), float(z)))


def _matrix(rotation_3x3=None) -> TransformOp:
    # Identity by default; otherwise embed the provided 3x3 in the upper-left.
    if rotation_3x3 is None:
        m = (
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        )
    else:
        r = rotation_3x3
        m = (
            r[0][0], r[0][1], r[0][2], 0.0,
            r[1][0], r[1][1], r[1][2], 0.0,
            r[2][0], r[2][1], r[2][2], 0.0,
            0.0,     0.0,     0.0,     1.0,
        )
    return TransformOp(op_name="xformOp:transform", op_type="transform_matrix",
                       values=tuple(float(x) for x in m))


def _prim(path: str, ops: tuple[TransformOp, ...] = (), **kw) -> XformablePrim:
    return XformablePrim(path=path, ops=ops, **kw)


def _run(prims: list[XformablePrim], *, criteria: AcceptanceCriteria | None = None) -> list[Issue]:
    inspector = MockStageInspector(prims=prims)
    ctx = ValidationContext(
        asset_uri="test://stage",
        criteria=criteria or AcceptanceCriteria(),
        stage_inspector=inspector,
    )
    return TransformValidator(ctx.criteria).run(ctx)


# ============================================================ smoke / setup ==


class TestSetup:
    def test_missing_inspector_emits_no_inspector_fail(self):
        ctx = ValidationContext(asset_uri="t", criteria=AcceptanceCriteria())
        issues = TransformValidator(ctx.criteria).run(ctx)
        assert len(issues) == 1
        assert issues[0].code     == CODE_NO_STAGE_INSPECTOR
        assert issues[0].severity == Severity.FAIL

    def test_empty_stage_no_issues(self):
        assert _run([]) == []

    def test_well_formed_prim_no_issues(self):
        p = _prim("/A", ops=(_translate(), _quat(), _scale()))
        assert _run([p]) == []


# ======================================================== NaN / Inf handling ==


class TestNonFinite:
    def test_nan_in_translation_fails(self):
        p = _prim("/A", ops=(_translate((float("nan"), 0, 0)),))
        codes = [i.code for i in _run([p])]
        assert CODE_NAN_VALUE in codes
        for i in _run([p]):
            if i.code == CODE_NAN_VALUE:
                assert i.severity == Severity.FAIL

    def test_inf_in_scale_fails(self):
        p = _prim("/A", ops=(_scale((float("inf"), 1, 1)),))
        codes = [i.code for i in _run([p])]
        assert CODE_INF_VALUE in codes

    def test_nan_suppresses_secondary_checks_on_same_op(self):
        # Scale of NaN should produce NAN but NOT zero/oor/negative — those
        # are bogus secondary issues on a non-finite value.
        p = _prim("/A", ops=(_scale((float("nan"), 1.0, 1.0)),))
        codes = sorted(i.code for i in _run([p]))
        assert CODE_NAN_VALUE in codes
        assert CODE_ZERO_SCALE         not in codes
        assert CODE_SCALE_OUT_OF_RANGE not in codes
        assert CODE_NON_POSITIVE_SCALE not in codes


# ============================================================ scale (§2.3-5) ==


class TestScale:
    def test_zero_scale_axis_fails(self):
        p = _prim("/A", ops=(_scale((0.0, 1.0, 1.0)),))
        codes = [i.code for i in _run([p])]
        assert CODE_ZERO_SCALE in codes
        zero = next(i for i in _run([p]) if i.code == CODE_ZERO_SCALE)
        assert zero.severity == Severity.FAIL
        assert zero.metric_dict()["scale_x"] == 0.0

    def test_scale_above_range_fails(self):
        p = _prim("/A", ops=(_scale((1.0, 1.0e4, 1.0)),))
        codes = [i.code for i in _run([p])]
        assert CODE_SCALE_OUT_OF_RANGE in codes

    def test_scale_below_range_is_zero_scale(self):
        # 1e-4 is below the 1e-3 default min; reported as ZERO_SCALE
        p = _prim("/A", ops=(_scale((1.0e-4, 1.0, 1.0)),))
        codes = [i.code for i in _run([p])]
        assert CODE_ZERO_SCALE in codes
        assert CODE_SCALE_OUT_OF_RANGE not in codes

    def test_negative_scale_warns_without_mirror(self):
        p = _prim("/A", ops=(_scale((-1.0, 1.0, 1.0)),))
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_NON_POSITIVE_SCALE)
        assert i.severity == Severity.WARN

    def test_negative_scale_with_collider_escalates_to_fail(self):
        p = _prim("/A", ops=(_scale((-1.0, 1.0, 1.0)),), has_collision_api=True)
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_NON_POSITIVE_SCALE)
        assert i.severity == Severity.FAIL

    def test_negative_scale_with_mirror_metadata_allowed(self):
        p = _prim(
            "/A",
            ops=(_scale((-1.0, 1.0, 1.0)),),
            custom_data=(("mirror", True),),
        )
        codes = [i.code for i in _run([p])]
        assert CODE_NON_POSITIVE_SCALE not in codes


# =========================================================== quaternion §2.6 ==


class TestQuaternion:
    def test_unit_quaternion_ok(self):
        p = _prim("/A", ops=(_quat(1, 0, 0, 0),))
        codes = [i.code for i in _run([p])]
        assert CODE_QUATERNION_DENORMAL not in codes

    def test_half_magnitude_quaternion_fails(self):
        p = _prim("/A", ops=(_quat(0.5, 0.0, 0.0, 0.0),))
        codes = [i.code for i in _run([p])]
        assert CODE_QUATERNION_DENORMAL in codes

    def test_just_outside_tolerance_fails(self):
        # 1.01 magnitude — outside default [0.999, 1.001]
        p = _prim("/A", ops=(_quat(1.01, 0.0, 0.0, 0.0),))
        codes = [i.code for i in _run([p])]
        assert CODE_QUATERNION_DENORMAL in codes


# =========================================================== matrix §2.7 ==


class TestMatrixOrthogonality:
    def test_identity_passes(self):
        p = _prim("/A", ops=(_matrix(),))
        codes = [i.code for i in _run([p])]
        assert CODE_ROTATION_NON_ORTHOGONAL not in codes

    def test_pure_rotation_passes(self):
        c, s = math.cos(0.5), math.sin(0.5)
        # Rotate-Z by 0.5 rad
        r = ((c, -s, 0), (s, c, 0), (0, 0, 1))
        p = _prim("/A", ops=(_matrix(r),))
        codes = [i.code for i in _run([p])]
        assert CODE_ROTATION_NON_ORTHOGONAL not in codes

    def test_skew_matrix_fails(self):
        # Skew (non-orthogonal): R^T R ≠ I
        r = ((1.0, 0.5, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        p = _prim("/A", ops=(_matrix(r),))
        codes = [i.code for i in _run([p])]
        assert CODE_ROTATION_NON_ORTHOGONAL in codes


# ============================================================ translation §2.8 ==


class TestTranslation:
    def test_within_range_ok(self):
        p = _prim("/A", ops=(_translate((100.0, 0, 0)),))
        codes = [i.code for i in _run([p])]
        assert CODE_TRANSLATION_OUT_OF_RANGE not in codes

    def test_above_range_warns(self):
        p = _prim("/A", ops=(_translate((2.0e6, 0, 0)),))
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_TRANSLATION_OUT_OF_RANGE)
        assert i.severity == Severity.WARN


# ====================================================== time-sampled drift §2.9 ==


class TestTimeSampledDrift:
    def test_time_sampled_on_static_warns(self):
        p = _prim("/A", ops=(_translate(ts=42),), is_likely_dynamic=False)
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_TIME_SAMPLED_ON_STATIC)
        assert i.severity == Severity.WARN
        assert i.metric_dict()["time_sample_count"] == 42

    def test_time_sampled_on_dynamic_ignored(self):
        p = _prim("/A", ops=(_translate(ts=42),), is_likely_dynamic=True)
        codes = [i.code for i in _run([p])]
        assert CODE_TIME_SAMPLED_ON_STATIC not in codes


# ============================================ mixed op style + hierarchy corruption ==


class TestStructural:
    def test_mixed_op_style_warns(self):
        # transform_matrix and translate together → mixed
        p = _prim("/A", ops=(_matrix(), _translate((1, 2, 3))))
        codes = [i.code for i in _run([p])]
        assert CODE_MIXED_OP_ORDER in codes

    def test_xform_op_order_unresolved_fails(self):
        p = _prim(
            "/A",
            ops=(_translate(),),
            xform_op_order_unresolved=("xformOp:rotateXYZ",),
        )
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_XFORMOP_ORDER_INVALID)
        assert i.severity == Severity.FAIL


# =========================================================== cascade ==


class TestCascade:
    def test_descendant_of_failing_prim_gets_info(self):
        parent = _prim("/A", ops=(_scale((0.0, 1.0, 1.0)),))   # ZERO_SCALE FAIL
        child  = _prim("/A/B", parent_path="/A", ops=(_translate(),))
        codes = [i.code for i in _run([parent, child])]
        assert CODE_ZERO_SCALE             in codes   # on /A
        assert CODE_CASCADE_INVALID_WORLD  in codes   # on /A/B

    def test_no_cascade_on_clean_tree(self):
        parent = _prim("/A", ops=(_scale(),))
        child  = _prim("/A/B", parent_path="/A", ops=(_translate(),))
        codes = [i.code for i in _run([parent, child])]
        assert CODE_CASCADE_INVALID_WORLD not in codes

    def test_cascade_does_not_repeat_on_failing_descendants(self):
        # If both parent and grandchild fail, grandchild emits its own FAIL,
        # not a cascade INFO referring to parent.
        p1 = _prim("/A",     ops=(_scale((0.0, 1.0, 1.0)),))
        p2 = _prim("/A/B",   parent_path="/A",   ops=(_translate(),))
        p3 = _prim("/A/B/C", parent_path="/A/B", ops=(_scale((0.0, 1.0, 1.0)),))
        codes = [i.code for i in _run([p1, p2, p3])]
        # /A/B should have CASCADE_INVALID_WORLD; /A/B/C should NOT
        cascade_paths = [
            i.prim_paths[0] for i in _run([p1, p2, p3])
            if i.code == CODE_CASCADE_INVALID_WORLD
        ]
        assert "/A/B" in cascade_paths
        assert "/A/B/C" not in cascade_paths


# ====================================================== floating heuristic ==


class TestFloatingHeuristic:
    def test_high_z_warns_with_default_threshold(self):
        # default threshold = 100m
        p = _prim("/A", ops=(_translate((0, 0, 250.0)),))
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_FLOATING_HEURISTIC)
        assert i.severity == Severity.WARN
        assert i.metric_dict()["translate_z_m"] == pytest.approx(250.0)

    def test_low_z_no_warn(self):
        p = _prim("/A", ops=(_translate((0, 0, 0.5)),))
        codes = [i.code for i in _run([p])]
        assert CODE_FLOATING_HEURISTIC not in codes

    def test_disabled_threshold_skips_check(self):
        criteria = AcceptanceCriteria(
            transform=TransformThresholds(floating_heuristic_z_m=None)
        )
        p = _prim("/A", ops=(_translate((0, 0, 1.0e6)),))   # would trip OOR too
        codes = [i.code for i in _run([p], criteria=criteria)]
        assert CODE_FLOATING_HEURISTIC not in codes

    def test_zero_threshold_disables_check(self):
        criteria = AcceptanceCriteria(
            transform=TransformThresholds(floating_heuristic_z_m=0.0)
        )
        p = _prim("/A", ops=(_translate((0, 0, 200.0)),))
        codes = [i.code for i in _run([p], criteria=criteria)]
        assert CODE_FLOATING_HEURISTIC not in codes

    def test_skipped_when_multiple_translate_ops(self):
        # Composed translates → ambiguous; the heuristic skips rather than
        # heuristically summing them.
        p = _prim("/A", ops=(_translate((0, 0, 200)), _translate((0, 0, 200))))
        codes = [i.code for i in _run([p])]
        assert CODE_FLOATING_HEURISTIC not in codes


# ============================================================ value count ==


class TestValueCount:
    def test_translate_with_wrong_count_fails(self):
        op = TransformOp("xformOp:translate", "translate", (1.0, 2.0))  # only 2 values
        p = _prim("/A", ops=(op,))
        codes = [i.code for i in _run([p])]
        assert CODE_OP_VALUE_COUNT_MISMATCH in codes

    def test_malformed_op_skips_other_checks(self):
        # Even if values look bad, count-mismatch should be the only issue.
        op = TransformOp("xformOp:scale", "scale", (0.0, 1.0))   # too few
        p = _prim("/A", ops=(op,))
        codes = sorted(i.code for i in _run([p]))
        assert codes == [CODE_OP_VALUE_COUNT_MISMATCH]


# ============================================================ determinism ==


class TestDeterminism:
    def _stage(self):
        return [
            _prim("/Z", ops=(_scale((0.0, 1, 1)),)),
            _prim("/A", ops=(_quat(0.5, 0, 0, 0),)),
            _prim("/M", ops=(_translate((0, 0, 2.0e6)),)),
        ]

    def test_same_inputs_same_outputs(self):
        a = _run(self._stage())
        b = _run(self._stage())
        assert a == b

    def test_input_prim_order_does_not_change_output(self):
        s = self._stage()
        a = _run(s)
        b = _run(list(reversed(s)))
        assert a == b

    def test_issues_sorted_severity_desc_then_code(self):
        issues = _run(self._stage())
        sevs   = [i.severity for i in issues]
        assert sevs == sorted(sevs, reverse=True)
        # Within each severity bucket, codes are sorted lexicographically.
        for s in (Severity.FAIL, Severity.WARN, Severity.INFO):
            codes = [i.code for i in issues if i.severity == s]
            assert codes == sorted(codes)


# ============================================================ custom criteria ==


class TestCustomCriteria:
    def test_tighter_quaternion_tolerance_promotes_to_fail(self):
        # Default tolerance accepts |q| in [0.999, 1.001]; tighten to [0.9999, 1.0001]
        criteria = AcceptanceCriteria(
            transform=TransformThresholds(
                quaternion_magnitude_min=0.9999,
                quaternion_magnitude_max=1.0001,
            )
        )
        p = _prim("/A", ops=(_quat(0.999, 0, 0, 0),))   # passes default, fails tight
        codes = [i.code for i in _run([p], criteria=criteria)]
        assert CODE_QUATERNION_DENORMAL in codes

    def test_looser_scale_range_allows_previously_failing(self):
        criteria = AcceptanceCriteria(
            transform=TransformThresholds(max_scale_magnitude=1.0e+6),
        )
        p = _prim("/A", ops=(_scale((1.0e4, 1.0, 1.0)),))
        codes = [i.code for i in _run([p], criteria=criteria)]
        assert CODE_SCALE_OUT_OF_RANGE not in codes


# ============================================================ validator meta ==


class TestValidatorMetadata:
    def test_name_and_phase(self):
        assert TransformValidator.name  == "transform"
        assert TransformValidator.phase == "static"

    def test_issues_carry_validator_name(self):
        p = _prim("/A", ops=(_scale((0.0, 1.0, 1.0)),))
        issues = _run([p])
        assert all(i.validator == "transform" for i in issues)
