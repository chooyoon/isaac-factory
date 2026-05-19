"""Unit tests for DeterministicResetValidator.

Pure Python: no pxr, no omni, no isaacsim. The validator depends only on
the ResetSimulator protocol; tests inject a MockResetSimulator with
hand-crafted ResetReport data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pytest

from asset_validator import (
    AcceptanceCriteria,
    BodyState,
    ContactPair,
    DeterministicResetThresholds,
    DeterministicResetValidator,
    Issue,
    ResetCycle,
    ResetReport,
    ResetSimulator,
    Severity,
    ValidationContext,
)
from asset_validator.validators.deterministic_reset import (
    CODE_ANGULAR_VELOCITY_DRIFT,
    CODE_BODY_SET_MISMATCH,
    CODE_CONTACT_AFTER_RESET,
    CODE_CYCLE_VARIANCE_ROT,
    CODE_CYCLE_VARIANCE_TRANS,
    CODE_DETERMINISM_FLAG_MISSING,
    CODE_LINEAR_VELOCITY_DRIFT,
    CODE_NO_RESET_SIMULATOR,
    CODE_NON_DETERMINISTIC_AUTHORING,
    CODE_POSE_ROTATION_DRIFT,
    CODE_POSE_TRANSLATION_DRIFT,
    CODE_SEED_NOT_FIXED,
    CODE_SPAWN_ORDER_MISMATCH,
)


# ============================================================== mock ==


@dataclass
class MockResetSimulator:
    report: ResetReport

    def get_reset_report(self) -> ResetReport:
        return self.report


_IDENTITY_Q = (1.0, 0.0, 0.0, 0.0)


# ============================================================ helpers ==


def _body(path: str, t=(0.0, 0.0, 0.0), q=_IDENTITY_Q, v=(0.0, 0.0, 0.0), w=(0.0, 0.0, 0.0)) -> BodyState:
    return BodyState(prim_path=path, translation=t, rotation_quat=q,
                     linear_velocity=v, angular_velocity=w)


def _cycle(
    idx: int,
    *,
    after_step: tuple[BodyState, ...] = (),
    after_reset: tuple[BodyState, ...] = (),
    spawn_order: tuple[str, ...] = (),
    contacts: tuple[ContactPair, ...] = (),
) -> ResetCycle:
    return ResetCycle(
        cycle_index=idx,
        after_step_state=after_step,
        after_reset_state=after_reset,
        spawn_order=spawn_order,
        contact_pairs_after_reset=contacts,
    )


def _report(
    *,
    initial: tuple[BodyState, ...] = (),
    spawn_order: tuple[str, ...]   = (),
    cycles:  tuple[ResetCycle, ...] = (),
    det_flag: bool = True,
    seed_set: bool = True,
    non_det:  tuple[str, ...] = (),
) -> ResetReport:
    return ResetReport(
        determinism_flag_set=det_flag,
        seed_set=seed_set,
        initial_state=initial,
        initial_spawn_order=spawn_order,
        cycles=cycles,
        non_deterministic_authoring=non_det,
    )


def _run(report: ResetReport, *, criteria: AcceptanceCriteria | None = None) -> list[Issue]:
    sim = MockResetSimulator(report=report)
    ctx = ValidationContext(
        asset_uri="test://stage",
        criteria=criteria or AcceptanceCriteria(),
        reset_simulator=sim,
    )
    return DeterministicResetValidator(ctx.criteria).run(ctx)


# Structural check
_: ResetSimulator = MockResetSimulator(report=_report())


# ============================================================== setup ==


class TestSetup:
    def test_missing_simulator_fails(self):
        ctx = ValidationContext(asset_uri="t", criteria=AcceptanceCriteria())
        issues = DeterministicResetValidator(ctx.criteria).run(ctx)
        assert len(issues) == 1
        assert issues[0].code     == CODE_NO_RESET_SIMULATOR
        assert issues[0].severity == Severity.FAIL

    def test_empty_report_no_issues(self):
        assert _run(_report()) == []

    def test_perfect_cycle_no_issues(self):
        b = _body("/A", t=(1.0, 0.0, 0.0))
        c = _cycle(1, after_step=(b,), after_reset=(b,), spawn_order=("/A",))
        r = _report(initial=(b,), spawn_order=("/A",), cycles=(c,))
        assert _run(r) == []


# ============================================================ §6.5 / §6.6 ==


class TestPrerequisites:
    def test_determinism_flag_off_fails(self):
        r = _report(det_flag=False)
        codes = [i.code for i in _run(r)]
        assert CODE_DETERMINISM_FLAG_MISSING in codes

    def test_seed_not_set_fails(self):
        r = _report(seed_set=False)
        codes = [i.code for i in _run(r)]
        assert CODE_SEED_NOT_FIXED in codes

    def test_relaxed_criteria_skips_check(self):
        criteria = AcceptanceCriteria(
            deterministic_reset=DeterministicResetThresholds(
                require_determinism_flag=False, require_seed=False,
            ),
        )
        r = _report(det_flag=False, seed_set=False)
        codes = [i.code for i in _run(r, criteria=criteria)]
        assert CODE_DETERMINISM_FLAG_MISSING not in codes
        assert CODE_SEED_NOT_FIXED            not in codes


# =================================================== §6.8 non-det authoring ==


class TestNonDeterministicAuthoring:
    def test_warning_emitted(self):
        r = _report(non_det=("/World/RandomBody",))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_NON_DETERMINISTIC_AUTHORING)
        assert i.severity == Severity.WARN
        assert i.prim_paths == ("/World/RandomBody",)


# ======================================================== §6.1 translation ==


class TestTranslationDrift:
    def test_drift_above_tolerance_fails(self):
        init = _body("/A", t=(0.0, 0.0, 0.0))
        # 1mm drift — well above 1e-5 default
        after = _body("/A", t=(1.0e-3, 0.0, 0.0))
        c = _cycle(1, after_step=(init,), after_reset=(after,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c,))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_POSE_TRANSLATION_DRIFT)
        assert i.severity == Severity.FAIL
        assert i.metric_dict()["translation_delta_m"] == pytest.approx(1.0e-3)

    def test_drift_within_tolerance_ok(self):
        init  = _body("/A", t=(0.0, 0.0, 0.0))
        after = _body("/A", t=(5.0e-6, 0.0, 0.0))  # 5e-6 < 1e-5
        c = _cycle(1, after_reset=(after,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c,))
        codes = [i.code for i in _run(r)]
        assert CODE_POSE_TRANSLATION_DRIFT not in codes


# =========================================================== §6.2 rotation ==


class TestRotationDrift:
    def test_rotation_drift_above_tolerance_fails(self):
        init = _body("/A")
        # Rotation by ~1 deg = 0.0175 rad — well above 1e-4 default
        ang = math.radians(1.0)
        after = _body("/A", q=(math.cos(ang/2), 0.0, 0.0, math.sin(ang/2)))
        c = _cycle(1, after_reset=(after,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c,))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_POSE_ROTATION_DRIFT)
        assert i.severity == Severity.FAIL
        assert i.metric_dict()["rotation_delta_rad"] == pytest.approx(ang, abs=1e-7)

    def test_q_and_minus_q_treated_as_same(self):
        init  = _body("/A", q=(1.0, 0.0, 0.0, 0.0))
        after = _body("/A", q=(-1.0, 0.0, 0.0, 0.0))   # double-cover
        c = _cycle(1, after_reset=(after,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c,))
        codes = [i.code for i in _run(r)]
        assert CODE_POSE_ROTATION_DRIFT not in codes


# =========================================================== §6.3 / §6.4 ==


class TestVelocityDrift:
    def test_linear_velocity_drift_fails(self):
        init  = _body("/A")
        # 1 mm/s — above 1e-6 default
        after = _body("/A", v=(1.0e-3, 0.0, 0.0))
        c = _cycle(1, after_reset=(after,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c,))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_LINEAR_VELOCITY_DRIFT)
        assert i.severity == Severity.FAIL

    def test_angular_velocity_drift_fails(self):
        init  = _body("/A")
        after = _body("/A", w=(0.0, 0.0, 0.01))   # 10 mrad/s
        c = _cycle(1, after_reset=(after,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c,))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_ANGULAR_VELOCITY_DRIFT)
        assert i.severity == Severity.FAIL

    def test_zero_velocity_no_issue(self):
        init  = _body("/A")
        after = _body("/A")
        c = _cycle(1, after_reset=(after,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c,))
        codes = [i.code for i in _run(r)]
        assert CODE_LINEAR_VELOCITY_DRIFT  not in codes
        assert CODE_ANGULAR_VELOCITY_DRIFT not in codes


# =========================================================== spawn order ==


class TestSpawnOrder:
    def test_spawn_order_mismatch_fails(self):
        b1 = _body("/A"); b2 = _body("/B")
        c = _cycle(1, after_reset=(b1, b2), spawn_order=("/B", "/A"))   # reversed!
        r = _report(initial=(b1, b2), spawn_order=("/A", "/B"), cycles=(c,))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_SPAWN_ORDER_MISMATCH)
        assert i.severity == Severity.FAIL

    def test_matching_spawn_order_ok(self):
        b1 = _body("/A"); b2 = _body("/B")
        c = _cycle(1, after_reset=(b1, b2), spawn_order=("/A", "/B"))
        r = _report(initial=(b1, b2), spawn_order=("/A", "/B"), cycles=(c,))
        codes = [i.code for i in _run(r)]
        assert CODE_SPAWN_ORDER_MISMATCH not in codes


# ========================================================= contact after reset ==


class TestContactAfterReset:
    def test_residual_contact_above_threshold_fails(self):
        b = _body("/A")
        pair = ContactPair.create("/A", "/B", 1.0e-3)   # 1mm penetration
        c = _cycle(1, after_reset=(b,), spawn_order=("/A",), contacts=(pair,))
        r = _report(initial=(b,), spawn_order=("/A",), cycles=(c,))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_CONTACT_AFTER_RESET)
        assert i.severity == Severity.FAIL
        assert i.prim_paths == ("/A", "/B")

    def test_contact_below_threshold_ok(self):
        # max_penetration_after_reset_m default = 1e-6
        b = _body("/A")
        pair = ContactPair.create("/A", "/B", 5.0e-7)
        c = _cycle(1, after_reset=(b,), spawn_order=("/A",), contacts=(pair,))
        r = _report(initial=(b,), spawn_order=("/A",), cycles=(c,))
        codes = [i.code for i in _run(r)]
        assert CODE_CONTACT_AFTER_RESET not in codes

    def test_no_contacts_ok(self):
        b = _body("/A")
        c = _cycle(1, after_reset=(b,), spawn_order=("/A",), contacts=())
        r = _report(initial=(b,), spawn_order=("/A",), cycles=(c,))
        codes = [i.code for i in _run(r)]
        assert CODE_CONTACT_AFTER_RESET not in codes


# =========================================================== §6.7 variance ==


class TestCycleVariance:
    def test_translation_variance_above_tolerance_fails(self):
        init = _body("/A", t=(0.0, 0.0, 0.0))
        # Cycle 1 ends at x=1.0; cycle 2 ends at x=1.0 + 1mm
        c1_after = _body("/A", t=(1.0, 0.0, 0.0))
        c2_after = _body("/A", t=(1.001, 0.0, 0.0))
        c1 = _cycle(1, after_step=(c1_after,), after_reset=(init,), spawn_order=("/A",))
        c2 = _cycle(2, after_step=(c2_after,), after_reset=(init,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c1, c2))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_CYCLE_VARIANCE_TRANS)
        assert i.severity == Severity.FAIL
        assert i.metric_dict()["cycle_index"] == 2.0

    def test_rotation_variance_above_tolerance_fails(self):
        init = _body("/A")
        ang = math.radians(1.0)
        c1_after = _body("/A")                                                       # identity
        c2_after = _body("/A", q=(math.cos(ang/2), 0.0, 0.0, math.sin(ang/2)))       # ~1 deg
        c1 = _cycle(1, after_step=(c1_after,), after_reset=(init,), spawn_order=("/A",))
        c2 = _cycle(2, after_step=(c2_after,), after_reset=(init,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c1, c2))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_CYCLE_VARIANCE_ROT)
        assert i.severity == Severity.FAIL

    def test_no_variance_check_on_cycle_1(self):
        init = _body("/A")
        a = _body("/A", t=(1.0, 0.0, 0.0))
        c1 = _cycle(1, after_step=(a,), after_reset=(init,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c1,))
        codes = [i.code for i in _run(r)]
        assert CODE_CYCLE_VARIANCE_TRANS not in codes
        assert CODE_CYCLE_VARIANCE_ROT   not in codes

    def test_consistent_cycles_no_variance(self):
        init = _body("/A")
        same = _body("/A", t=(1.0, 0.0, 0.0))
        c1 = _cycle(1, after_step=(same,), after_reset=(init,), spawn_order=("/A",))
        c2 = _cycle(2, after_step=(same,), after_reset=(init,), spawn_order=("/A",))
        c3 = _cycle(3, after_step=(same,), after_reset=(init,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c1, c2, c3))
        codes = [i.code for i in _run(r)]
        assert CODE_CYCLE_VARIANCE_TRANS not in codes
        assert CODE_CYCLE_VARIANCE_ROT   not in codes


# =========================================================== body set ==


class TestBodySet:
    def test_missing_body_after_reset_fails(self):
        b1 = _body("/A"); b2 = _body("/B")
        # Only /A is present after reset
        c = _cycle(1, after_reset=(b1,), spawn_order=("/A", "/B"))
        r = _report(initial=(b1, b2), spawn_order=("/A", "/B"), cycles=(c,))
        issues = _run(r)
        i = next(i for i in issues if i.code == CODE_BODY_SET_MISMATCH)
        assert i.severity == Severity.FAIL

    def test_extra_body_after_reset_fails(self):
        b1 = _body("/A")
        b_extra = _body("/Phantom")
        c = _cycle(1, after_reset=(b1, b_extra), spawn_order=("/A",))
        r = _report(initial=(b1,), spawn_order=("/A",), cycles=(c,))
        codes = [i.code for i in _run(r)]
        assert CODE_BODY_SET_MISMATCH in codes


# =========================================================== custom criteria ==


class TestCustomCriteria:
    def test_tighter_translation_tolerance_promotes(self):
        criteria = AcceptanceCriteria(
            deterministic_reset=DeterministicResetThresholds(translation_tolerance_m=1.0e-8),
        )
        init  = _body("/A", t=(0.0, 0.0, 0.0))
        after = _body("/A", t=(1.0e-6, 0.0, 0.0))
        c = _cycle(1, after_reset=(after,), spawn_order=("/A",))
        r = _report(initial=(init,), spawn_order=("/A",), cycles=(c,))
        codes = [i.code for i in _run(r, criteria=criteria)]
        assert CODE_POSE_TRANSLATION_DRIFT in codes

    def test_looser_contact_threshold_allows_small_pen(self):
        criteria = AcceptanceCriteria(
            deterministic_reset=DeterministicResetThresholds(max_penetration_after_reset_m=1.0e-2),
        )
        b = _body("/A")
        pair = ContactPair.create("/A", "/B", 1.0e-3)
        c = _cycle(1, after_reset=(b,), spawn_order=("/A",), contacts=(pair,))
        r = _report(initial=(b,), spawn_order=("/A",), cycles=(c,))
        codes = [i.code for i in _run(r, criteria=criteria)]
        assert CODE_CONTACT_AFTER_RESET not in codes


# ============================================================ determinism ==


class TestDeterminism:
    def _report(self):
        init   = _body("/A")
        bad    = _body("/A", t=(1.0e-3, 0.0, 0.0))
        c1     = _cycle(1, after_step=(_body("/A", t=(1.0, 0, 0)),), after_reset=(bad,), spawn_order=("/A",))
        c2     = _cycle(2, after_step=(_body("/A", t=(1.005, 0, 0)),), after_reset=(bad,), spawn_order=("/A",))
        return _report(
            initial=(init,), spawn_order=("/A",), cycles=(c1, c2),
            non_det=("/A",),
        )

    def test_same_input_same_output(self):
        r = self._report()
        assert _run(r) == _run(r)

    def test_issues_sorted_severity_desc_then_code(self):
        r = self._report()
        issues = _run(r)
        sevs = [i.severity for i in issues]
        assert sevs == sorted(sevs, reverse=True)
        for s in (Severity.FAIL, Severity.WARN, Severity.INFO):
            codes = [i.code for i in issues if i.severity == s]
            assert codes == sorted(codes)


# ============================================================ validator meta ==


class TestValidatorMetadata:
    def test_name_and_phase(self):
        assert DeterministicResetValidator.name  == "deterministic_reset"
        assert DeterministicResetValidator.phase == "dynamic"

    def test_issues_carry_validator_name(self):
        r = _report(det_flag=False)
        issues = _run(r)
        assert all(i.validator == "deterministic_reset" for i in issues)
