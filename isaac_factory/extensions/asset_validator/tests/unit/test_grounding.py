"""Unit tests for GroundingValidator.

Pure Python: no pxr, no omni, no isaacsim. The validator depends only on
the GroundingInspector protocol; tests inject a MockGroundingInspector
whose probes carry pre-computed raycast results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pytest

from asset_validator import (
    AcceptanceCriteria,
    GroundingInspector,
    GroundingProbe,
    GroundingThresholds,
    GroundingValidator,
    Issue,
    Severity,
    ValidationContext,
)
from asset_validator.validators.grounding import (
    CODE_BURIED,
    CODE_FLOATING,
    CODE_NO_GROUNDING_INSPECTOR,
    CODE_NO_INTENT_TAG,
    CODE_NO_SUPPORT_FOUND,
)


# ================================================================= mock ==


@dataclass
class MockGroundingInspector:
    probes: list[GroundingProbe] = field(default_factory=list)

    def iter_grounding_probes(self) -> Iterable[GroundingProbe]:
        return list(self.probes)


_: GroundingInspector = MockGroundingInspector()


# ============================================================== helpers ==


def _probe(
    path: str,
    *,
    intent:        str | None = "true",
    aabb_bottom_z: float = 1.0,
    hit_path:      str | None = "/ground",
    hit_z:         float | None = 1.0,           # equal → resting
) -> GroundingProbe:
    return GroundingProbe(
        path=path,
        grounded_intent=intent,
        aabb_bottom_z_m=aabb_bottom_z,
        support_hit_path=hit_path,
        support_hit_z_m=hit_z,
    )


def _run(probes: list[GroundingProbe], *, criteria: AcceptanceCriteria | None = None) -> list[Issue]:
    ins = MockGroundingInspector(probes=probes)
    ctx = ValidationContext(
        asset_uri="test://stage",
        criteria=criteria or AcceptanceCriteria(),
        grounding_inspector=ins,
    )
    return GroundingValidator(ctx.criteria).run(ctx)


# ================================================================= setup ==


class TestSetup:
    def test_missing_inspector_fails(self):
        ctx = ValidationContext(asset_uri="t", criteria=AcceptanceCriteria())
        issues = GroundingValidator(ctx.criteria).run(ctx)
        assert len(issues) == 1
        assert issues[0].code     == CODE_NO_GROUNDING_INSPECTOR
        assert issues[0].severity == Severity.FAIL

    def test_empty_probes_no_issues(self):
        assert _run([]) == []


# ================================================================= grounded ==


class TestGroundedProperly:
    def test_resting_on_support_no_issue(self):
        # gap = 0
        p = _probe("/box", aabb_bottom_z=1.0, hit_z=1.0)
        assert _run([p]) == []

    def test_within_floating_tolerance_no_issue(self):
        # 3mm above support — below default 5mm tolerance
        p = _probe("/box", aabb_bottom_z=1.003, hit_z=1.0)
        assert _run([p]) == []

    def test_within_buried_tolerance_no_issue(self):
        # 3mm below support
        p = _probe("/box", aabb_bottom_z=0.997, hit_z=1.0)
        assert _run([p]) == []

    def test_just_inside_tolerance_no_issue(self):
        # Slightly inside both bounds — strict > / < so passes.
        # (Exact-equality testing avoided due to IEEE 754 representation
        # of decimal literals like 0.995 having tiny error.)
        p_f = _probe("/box_f", aabb_bottom_z=1.004, hit_z=1.0)   # gap +4 mm
        p_b = _probe("/box_b", aabb_bottom_z=0.996, hit_z=1.0)   # gap -4 mm
        assert _run([p_f]) == []
        assert _run([p_b]) == []


# ================================================================= floating ==


class TestFloating:
    def test_gap_above_tolerance_fails(self):
        # 1cm above support — exceeds 5mm
        p = _probe("/floater", aabb_bottom_z=1.01, hit_z=1.0)
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_FLOATING)
        assert i.severity == Severity.FAIL
        assert i.metric_dict()["gap_m"] == pytest.approx(0.01)
        assert i.threshold_dict()["floating_tolerance_m"] == pytest.approx(5.0e-3)

    def test_floating_high_above(self):
        # 5m floating
        p = _probe("/cloud", aabb_bottom_z=6.0, hit_z=1.0)
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_FLOATING)
        assert i.severity == Severity.FAIL
        assert i.message  # not empty

    def test_no_buried_emitted_when_floating(self):
        p = _probe("/floater", aabb_bottom_z=1.01, hit_z=1.0)
        codes = [i.code for i in _run([p])]
        assert CODE_FLOATING in codes
        assert CODE_BURIED  not in codes


# ================================================================= buried ==


class TestBuried:
    def test_gap_below_tolerance_fails_as_buried(self):
        # 1cm into the support
        p = _probe("/sunk", aabb_bottom_z=0.99, hit_z=1.0)
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_BURIED)
        assert i.severity == Severity.FAIL
        assert i.metric_dict()["gap_m"] == pytest.approx(-0.01)

    def test_deep_buried(self):
        p = _probe("/deep", aabb_bottom_z=-5.0, hit_z=0.0)
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_BURIED)
        assert i.severity == Severity.FAIL

    def test_no_floating_emitted_when_buried(self):
        p = _probe("/sunk", aabb_bottom_z=0.99, hit_z=1.0)
        codes = [i.code for i in _run([p])]
        assert CODE_BURIED   in codes
        assert CODE_FLOATING not in codes


# =========================================================== no support ==


class TestNoSupport:
    def test_missing_hit_fails(self):
        # Raycast missed → no support
        p = _probe("/levitating", hit_path=None, hit_z=None)
        issues = _run([p])
        i = next(i for i in issues if i.code == CODE_NO_SUPPORT_FOUND)
        assert i.severity == Severity.FAIL

    def test_no_floating_or_buried_when_no_support(self):
        p = _probe("/levitating", hit_path=None, hit_z=None)
        codes = [i.code for i in _run([p])]
        assert CODE_NO_SUPPORT_FOUND in codes
        assert CODE_FLOATING         not in codes
        assert CODE_BURIED           not in codes


# ============================================================== intent ==


class TestIntent:
    def test_intent_true_runs_checks(self):
        p = _probe("/x", intent="true", aabb_bottom_z=1.5, hit_z=1.0)
        codes = [i.code for i in _run([p])]
        assert CODE_FLOATING in codes

    def test_intent_false_skips_all_checks(self):
        # Object explicitly non-grounded; even floating is OK
        p = _probe("/floater", intent="false", aabb_bottom_z=10.0, hit_z=1.0)
        assert _run([p]) == []

    def test_intent_false_skips_even_no_support(self):
        # Floating object that's explicitly not grounded; no support is fine
        p = _probe("/balloon", intent="false", hit_path=None, hit_z=None)
        assert _run([p]) == []

    def test_intent_kinematic_skips_gap_checks(self):
        # Kinematic object can be anywhere (user-driven)
        p = _probe("/anchor", intent="kinematic", aabb_bottom_z=10.0, hit_z=1.0)
        codes = [i.code for i in _run([p])]
        assert CODE_FLOATING not in codes
        assert CODE_BURIED   not in codes

    def test_intent_kinematic_still_requires_support(self):
        # Even kinematic should hit some surface beneath
        p = _probe("/anchor", intent="kinematic", hit_path=None, hit_z=None)
        codes = [i.code for i in _run([p])]
        assert CODE_NO_SUPPORT_FOUND in codes

    def test_intent_none_warns_and_defaults_to_grounded(self):
        # Floating + missing tag → warn + fail
        p = _probe("/x", intent=None, aabb_bottom_z=1.5, hit_z=1.0)
        codes = sorted(i.code for i in _run([p]))
        assert CODE_NO_INTENT_TAG in codes
        assert CODE_FLOATING      in codes

    def test_intent_invalid_warns_and_defaults_to_grounded(self):
        p = _probe("/x", intent="maybe", aabb_bottom_z=1.5, hit_z=1.0)
        codes = sorted(i.code for i in _run([p]))
        assert CODE_NO_INTENT_TAG in codes
        assert CODE_FLOATING      in codes

    def test_intent_none_on_resting_object_only_warns(self):
        # No tag, but actually grounded → just the warning
        p = _probe("/x", intent=None, aabb_bottom_z=1.0, hit_z=1.0)
        codes = [i.code for i in _run([p])]
        assert codes == [CODE_NO_INTENT_TAG]


# =========================================================== custom criteria ==


class TestCustomCriteria:
    def test_tighter_floating_tolerance_promotes_to_fail(self):
        # 3mm gap is fine at default 5mm; FAIL at 1mm tolerance
        criteria = AcceptanceCriteria(
            grounding=GroundingThresholds(floating_tolerance_m=1.0e-3),
        )
        p = _probe("/x", aabb_bottom_z=1.003, hit_z=1.0)
        codes = [i.code for i in _run([p], criteria=criteria)]
        assert CODE_FLOATING in codes

    def test_looser_buried_tolerance_allows_deeper_penetration(self):
        criteria = AcceptanceCriteria(
            grounding=GroundingThresholds(buried_tolerance_m=0.05),  # 5cm
        )
        p = _probe("/x", aabb_bottom_z=0.97, hit_z=1.0)              # 3cm buried
        codes = [i.code for i in _run([p], criteria=criteria)]
        assert CODE_BURIED not in codes


# ============================================================ determinism ==


class TestDeterminism:
    def _stage(self):
        return [
            _probe("/z_float", aabb_bottom_z=2.0, hit_z=1.0),     # FAIL floating
            _probe("/a_rest"),                                     # OK
            _probe("/m_buried", aabb_bottom_z=0.5, hit_z=1.0),    # FAIL buried
            _probe("/k_no_supp", hit_path=None, hit_z=None),      # FAIL no support
            _probe("/n_no_tag", intent=None),                     # WARN no_intent
        ]

    def test_same_input_same_output(self):
        assert _run(self._stage()) == _run(self._stage())

    def test_input_order_does_not_change_output(self):
        s = self._stage()
        assert _run(s) == _run(list(reversed(s)))

    def test_sorted_severity_desc_then_code(self):
        issues = _run(self._stage())
        sevs = [i.severity for i in issues]
        assert sevs == sorted(sevs, reverse=True)
        for s in (Severity.FAIL, Severity.WARN, Severity.INFO):
            codes = [i.code for i in issues if i.severity == s]
            assert codes == sorted(codes)


# =========================================================== gap property ==


class TestProbeGapProperty:
    def test_gap_computed_correctly(self):
        p = _probe("/x", aabb_bottom_z=1.1, hit_z=1.0)
        assert p.gap_m == pytest.approx(0.1)

    def test_gap_negative_when_buried(self):
        p = _probe("/x", aabb_bottom_z=0.9, hit_z=1.0)
        assert p.gap_m == pytest.approx(-0.1)

    def test_gap_none_when_no_hit(self):
        p = _probe("/x", hit_path=None, hit_z=None)
        assert p.gap_m is None


# ============================================================ validator meta ==


class TestValidatorMetadata:
    def test_name_and_phase(self):
        assert GroundingValidator.name  == "grounding"
        assert GroundingValidator.phase == "static"

    def test_issues_carry_validator_name(self):
        p = _probe("/x", aabb_bottom_z=2.0, hit_z=1.0)
        issues = _run([p])
        assert all(i.validator == "grounding" for i in issues)
