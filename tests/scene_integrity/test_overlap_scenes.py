"""Scene-level integration tests for OverlapValidator.

Each test composes a multi-body factory scene, runs the validator, and
asserts scene-level behaviour: correct codes, correct prim paths,
deterministic ordering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from asset_validator import (
    AcceptanceCriteria,
    ContactPair,
    ContactSource,
    OverlapValidator,
    Severity,
    ValidationContext,
)
from asset_validator.validators.overlap import (
    CODE_PEN_DEPTH_EXCEEDED,
    CODE_PEN_DEPTH_EXCEEDED_FIT,
    CODE_SELF_INTERSECTION,
)


# --------------------------------------------------------------- mock --


@dataclass
class _FixedContactSource:
    contacts: list[ContactPair] = field(default_factory=list)

    def setup(self, *, seed: int) -> None: pass
    def step(self) -> None: pass
    def query_contacts(self) -> Sequence[ContactPair]:
        return list(self.contacts)


_: ContactSource = _FixedContactSource()


def _run(
    contacts: list[ContactPair],
    *,
    allowed: set[frozenset[str]] | None = None,
):
    ctx = ValidationContext(
        asset_uri="test://scene",
        criteria=AcceptanceCriteria(),
        contact_source=_FixedContactSource(contacts=contacts),
        allowed_contact_pairs=frozenset(allowed or set()),
    )
    return OverlapValidator(ctx.criteria).run(ctx)


# ============================================================== scenes ==


class TestFactoryFloorClean:
    """Workbench + 3 parts resting at rest. No interpenetration."""

    def test_no_contacts_no_issues(self):
        assert _run([]) == []


class TestPressFitAssembly:
    """Two parts deliberately mated. Sub-fit-tolerance overlap is OK."""

    def test_press_fit_within_tolerance_passes(self):
        contacts = [
            ContactPair.create("/W/Bracket", "/W/Pin", 5.0e-5),    # 0.05 mm — under 0.1 mm fit thresh
        ]
        assert _run(contacts, allowed={frozenset({"/W/Bracket", "/W/Pin"})}) == []

    def test_press_fit_above_tolerance_warns(self):
        contacts = [
            ContactPair.create("/W/Bracket", "/W/Pin", 3.0e-4),    # 0.3 mm — over 0.1 mm
        ]
        issues = _run(contacts, allowed={frozenset({"/W/Bracket", "/W/Pin"})})
        assert len(issues) == 1
        assert issues[0].code     == CODE_PEN_DEPTH_EXCEEDED_FIT
        assert issues[0].severity == Severity.WARN


class TestMisalignedParts:
    """Two parts unexpectedly touching."""

    def test_misalignment_detected(self):
        contacts = [
            ContactPair.create("/W/PartA", "/W/PartB", 2.5e-3),     # 2.5 mm — over 1 mm
        ]
        issues = _run(contacts)
        assert len(issues) == 1
        i = issues[0]
        assert i.code     == CODE_PEN_DEPTH_EXCEEDED
        assert i.severity == Severity.FAIL
        assert set(i.prim_paths) == {"/W/PartA", "/W/PartB"}


class TestClutteredCell:
    """A messy cell with a mix of legitimate contacts and misalignments."""

    def test_mixed_issues_correctly_reported(self):
        contacts = [
            ContactPair.create("/Cell/Fixture", "/Cell/Pin",  6.0e-5),   # fit, within tol → OK
            ContactPair.create("/Cell/PartA",   "/Cell/PartB", 1.5e-3),  # FAIL (non-fit, > 1 mm)
            ContactPair.create("/Cell/Tool",    "/Cell/Tool",  3.0e-4),  # self-intersect FAIL
            ContactPair.create("/Cell/Clamp",   "/Cell/Frame", 3.0e-4),  # fit WARN
        ]
        allowed = {
            frozenset({"/Cell/Fixture", "/Cell/Pin"}),
            frozenset({"/Cell/Clamp",   "/Cell/Frame"}),
        }
        issues = _run(contacts, allowed=allowed)

        codes = [i.code for i in issues]
        # Expect: 1× SELF_INTERSECTION (FAIL) + 1× PEN_DEPTH_EXCEEDED (FAIL) + 1× FIT (WARN)
        assert codes.count(CODE_SELF_INTERSECTION)      == 1
        assert codes.count(CODE_PEN_DEPTH_EXCEEDED)     == 1
        assert codes.count(CODE_PEN_DEPTH_EXCEEDED_FIT) == 1
        assert len(codes) == 3

        # Severity ordering: FAILs before WARN
        sevs = [i.severity for i in issues]
        assert sevs == sorted(sevs, reverse=True)

        # Self-intersection points at the correct single prim
        si = next(i for i in issues if i.code == CODE_SELF_INTERSECTION)
        assert si.prim_paths == ("/Cell/Tool",)


class TestSceneDeterminism:
    """Permuting input order must yield identical reports."""

    def test_input_order_invariance(self):
        contacts = [
            ContactPair.create("/A", "/B", 2.0e-3),
            ContactPair.create("/C", "/D", 1.5e-3),
            ContactPair.create("/E", "/F", 3.0e-3),
        ]
        assert _run(contacts) == _run(list(reversed(contacts)))
