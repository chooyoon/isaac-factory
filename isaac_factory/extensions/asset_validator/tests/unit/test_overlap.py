"""Unit tests for OverlapValidator.

No Isaac Sim, no PhysX, no Kit — tests use an in-memory MockContactSource.
Run from the extension root:

    python -m pytest tests/unit/test_overlap.py -v

or from anywhere with the conftest.py-injected sys.path:

    python -m pytest /home/cap2/last/isaac_factory/extensions/asset_validator/tests
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import pytest

from asset_validator import (
    AcceptanceCriteria,
    ContactPair,
    ContactSource,
    Issue,
    OverlapThresholds,
    OverlapValidator,
    Severity,
    ValidationContext,
)
from asset_validator.validators.overlap import (
    CODE_PEN_DEPTH_EXCEEDED,
    CODE_PEN_DEPTH_EXCEEDED_FIT,
    CODE_SELF_INTERSECTION,
)


# ---------------------------------------------------------------- mock --


@dataclass
class MockContactSource:
    """Records all interactions; returns canned contacts."""

    contacts:      list[ContactPair] = field(default_factory=list)
    setup_calls:   int               = 0
    last_seed:     int | None        = None
    step_count:    int               = 0
    query_calls:   int               = 0

    def setup(self, *, seed: int) -> None:
        self.setup_calls += 1
        self.last_seed = seed

    def step(self) -> None:
        self.step_count += 1

    def query_contacts(self) -> Sequence[ContactPair]:
        self.query_calls += 1
        return list(self.contacts)


# Make sure the mock satisfies the Protocol structurally.
_: ContactSource = MockContactSource()


# ----------------------------------------------------------- helpers --


def _ctx(
    contacts: list[ContactPair],
    *,
    allowed_pairs: set[frozenset[str]] | None = None,
    criteria:      AcceptanceCriteria | None = None,
    seed:          int = 0,
) -> ValidationContext:
    return ValidationContext(
        asset_uri="test://stage",
        criteria=criteria or AcceptanceCriteria(),
        contact_source=MockContactSource(contacts=contacts),
        allowed_contact_pairs=frozenset(allowed_pairs or set()),
        seed=seed,
    )


def _run(
    contacts:      list[ContactPair],
    *,
    allowed_pairs: set[frozenset[str]] | None = None,
    criteria:      AcceptanceCriteria | None = None,
) -> list[Issue]:
    ctx = _ctx(contacts, allowed_pairs=allowed_pairs, criteria=criteria)
    return OverlapValidator(ctx.criteria).run(ctx)


# ============================================================== tests ==


class TestNoContacts:
    def test_empty_contacts_produces_no_issues(self):
        assert _run([]) == []


class TestUnexpectedContacts:
    def test_penetration_above_threshold_fails(self):
        # default threshold = 1.0 mm; 2.0 mm should fail
        issues = _run([ContactPair.create("/A", "/B", 2.0e-3)])
        assert len(issues) == 1
        i = issues[0]
        assert i.code     == CODE_PEN_DEPTH_EXCEEDED
        assert i.severity == Severity.FAIL
        assert i.prim_paths == ("/A", "/B")
        assert i.metric_dict()["penetration_depth_m"] == pytest.approx(2.0e-3)
        assert i.threshold_dict()["pen_depth_max_m"]  == pytest.approx(1.0e-3)

    def test_penetration_at_threshold_does_not_fail(self):
        # Boundary: == threshold is NOT a failure (strict >).
        assert _run([ContactPair.create("/A", "/B", 1.0e-3)]) == []

    def test_penetration_just_above_threshold_fails(self):
        issues = _run([ContactPair.create("/A", "/B", 1.0001e-3)])
        assert len(issues) == 1
        assert issues[0].severity == Severity.FAIL

    def test_penetration_below_threshold_no_issue(self):
        assert _run([ContactPair.create("/A", "/B", 5.0e-4)]) == []


class TestAllowedContactPairs:
    def test_fit_pair_below_fit_threshold_no_issue(self):
        # Fit threshold = 0.1mm; 0.05mm is fine even though > non-fit would also be fine.
        issues = _run(
            [ContactPair.create("/A", "/B", 5.0e-5)],
            allowed_pairs={frozenset({"/A", "/B"})},
        )
        assert issues == []

    def test_fit_pair_above_fit_threshold_warns(self):
        # 0.5mm exceeds 0.1mm fit threshold but is below non-fit FAIL threshold (1mm)
        issues = _run(
            [ContactPair.create("/A", "/B", 5.0e-4)],
            allowed_pairs={frozenset({"/A", "/B"})},
        )
        assert len(issues) == 1
        i = issues[0]
        assert i.code     == CODE_PEN_DEPTH_EXCEEDED_FIT
        assert i.severity == Severity.WARN
        assert i.threshold_dict()["pen_depth_max_fit_m"] == pytest.approx(1.0e-4)

    def test_fit_pair_allowed_in_either_order(self):
        # frozenset is order-invariant; ContactPair.create canonicalizes.
        issues_a = _run(
            [ContactPair.create("/A", "/B", 5.0e-5)],
            allowed_pairs={frozenset({"/B", "/A"})},
        )
        issues_b = _run(
            [ContactPair.create("/B", "/A", 5.0e-5)],
            allowed_pairs={frozenset({"/A", "/B"})},
        )
        assert issues_a == issues_b == []

    def test_unrelated_unexpected_pair_still_flagged(self):
        # Allowed list is for /A,/B only; /C,/D should still FAIL.
        issues = _run(
            [
                ContactPair.create("/A", "/B", 2.0e-4),    # fit, above fit threshold → WARN
                ContactPair.create("/C", "/D", 2.0e-3),    # non-fit, > 1mm → FAIL
            ],
            allowed_pairs={frozenset({"/A", "/B"})},
        )
        codes = sorted(i.code for i in issues)
        assert codes == sorted([CODE_PEN_DEPTH_EXCEEDED, CODE_PEN_DEPTH_EXCEEDED_FIT])


class TestSelfIntersection:
    def test_self_contact_always_fails(self):
        issues = _run([ContactPair.create("/X", "/X", 5.0e-5)])
        assert len(issues) == 1
        i = issues[0]
        assert i.code     == CODE_SELF_INTERSECTION
        assert i.severity == Severity.FAIL
        assert i.prim_paths == ("/X",)

    def test_self_contact_ignores_allowed_pairs(self):
        # Even if user puts {"/X","/X"} in allowed, self-contact still FAILs.
        # (frozenset({"/X","/X"}) is just {"/X"}, but spirit of the test is:
        # a self-contact code does not get downgraded by allowance.)
        issues = _run(
            [ContactPair.create("/X", "/X", 5.0e-5)],
            allowed_pairs={frozenset({"/X"})},
        )
        assert len(issues) == 1
        assert issues[0].code == CODE_SELF_INTERSECTION


class TestDeterminism:
    def test_same_input_same_output(self):
        contacts = [
            ContactPair.create("/A", "/B", 2.0e-3),
            ContactPair.create("/C", "/D", 1.5e-3),
            ContactPair.create("/E", "/F", 3.0e-3),
        ]
        assert _run(contacts) == _run(contacts) == _run(contacts)

    def test_input_order_does_not_change_output(self):
        c1 = [
            ContactPair.create("/A", "/B", 2.0e-3),
            ContactPair.create("/C", "/D", 1.5e-3),
        ]
        c2 = list(reversed(c1))
        assert _run(c1) == _run(c2)

    def test_pair_orientation_does_not_change_output(self):
        # B,A and A,B should canonicalize identically.
        out_a = _run([ContactPair.create("/A", "/B", 2.0e-3)])
        out_b = _run([ContactPair.create("/B", "/A", 2.0e-3)])
        assert out_a == out_b

    def test_issues_sorted_severity_desc_then_code(self):
        issues = _run(
            [
                ContactPair.create("/A", "/B", 5.0e-4),       # fit WARN
                ContactPair.create("/C", "/D", 2.0e-3),       # non-fit FAIL
                ContactPair.create("/X", "/X", 1.0e-4),       # self FAIL
            ],
            allowed_pairs={frozenset({"/A", "/B"})},
        )
        severities = [i.severity for i in issues]
        # FAILs come before WARNs because of -int(severity) sort key.
        assert severities == sorted(severities, reverse=True)
        # Within FAILs, sorted by code lexicographically.
        fails = [i for i in issues if i.severity == Severity.FAIL]
        assert [i.code for i in fails] == sorted(i.code for i in fails)


class TestContactSourceLifecycle:
    def test_setup_called_once_with_seed(self):
        cs = MockContactSource(contacts=[])
        ctx = ValidationContext(
            asset_uri="t", criteria=AcceptanceCriteria(),
            contact_source=cs, seed=42,
        )
        OverlapValidator(ctx.criteria).run(ctx)
        assert cs.setup_calls == 1
        assert cs.last_seed   == 42

    def test_step_count_equals_settle_plus_one(self):
        criteria = AcceptanceCriteria(overlap=OverlapThresholds(physics_settle_pre_steps=7))
        cs = MockContactSource(contacts=[])
        ctx = ValidationContext(
            asset_uri="t", criteria=criteria, contact_source=cs,
        )
        OverlapValidator(ctx.criteria).run(ctx)
        assert cs.step_count == 7 + 1     # settle_pre + 1 measurement step

    def test_query_called_once(self):
        cs = MockContactSource(contacts=[])
        ctx = ValidationContext(asset_uri="t", criteria=AcceptanceCriteria(), contact_source=cs)
        OverlapValidator(ctx.criteria).run(ctx)
        assert cs.query_calls == 1


class TestCustomThresholds:
    def test_tighter_threshold_promotes_to_fail(self):
        # Default threshold passes 0.5mm; tighter (0.2mm) should FAIL it.
        tight = AcceptanceCriteria(overlap=OverlapThresholds(pen_depth_max_m=2.0e-4))
        issues = _run([ContactPair.create("/A", "/B", 5.0e-4)], criteria=tight)
        assert len(issues) == 1
        assert issues[0].severity == Severity.FAIL

    def test_looser_threshold_allows_previously_failing_contact(self):
        # Default threshold fails 2mm; loosened (5mm) should allow it.
        loose = AcceptanceCriteria(overlap=OverlapThresholds(pen_depth_max_m=5.0e-3))
        assert _run([ContactPair.create("/A", "/B", 2.0e-3)], criteria=loose) == []


class TestIssueSerialization:
    def test_to_dict_round_trips_metric_and_threshold(self):
        issues = _run([ContactPair.create("/A", "/B", 2.0e-3)])
        d = issues[0].to_dict()
        assert d["code"]      == CODE_PEN_DEPTH_EXCEEDED
        assert d["severity"]  == "FAIL"
        assert d["validator"] == "overlap"
        assert d["prim_paths"] == ["/A", "/B"]
        assert d["metric"]["penetration_depth_m"]   == pytest.approx(2.0e-3)
        assert d["threshold"]["pen_depth_max_m"]    == pytest.approx(1.0e-3)


class TestValidatorMetadata:
    def test_phase_is_dynamic(self):
        assert OverlapValidator.phase == "dynamic"

    def test_name_matches_issue_field(self):
        issues = _run([ContactPair.create("/A", "/B", 2.0e-3)])
        assert issues[0].validator == OverlapValidator.name == "overlap"
