"""Scene-level integration tests for GroundingValidator.

Builds probe scenes that resemble a real factory cell: floor + parts at
rest, a floating drone, a ceiling-mounted lamp (intent=false), a
conveyor (intent=kinematic).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from asset_validator import (
    AcceptanceCriteria,
    GroundingInspector,
    GroundingProbe,
    GroundingValidator,
    Severity,
    ValidationContext,
)
from asset_validator.validators.grounding import (
    CODE_BURIED,
    CODE_FLOATING,
    CODE_NO_INTENT_TAG,
    CODE_NO_SUPPORT_FOUND,
)


# --------------------------------------------------------------- mock --


@dataclass
class _Probes:
    probes: list[GroundingProbe] = field(default_factory=list)

    def iter_grounding_probes(self) -> Iterable[GroundingProbe]:
        return list(self.probes)


_: GroundingInspector = _Probes()


def _probe(path, *, intent="true", aabb_bottom_z, hit_path="/Cell/Floor", hit_z=0.0):
    return GroundingProbe(
        path=path, grounded_intent=intent,
        aabb_bottom_z_m=aabb_bottom_z,
        support_hit_path=hit_path, support_hit_z_m=hit_z,
    )


def _run(probes):
    ctx = ValidationContext(
        asset_uri="test://scene",
        criteria=AcceptanceCriteria(),
        grounding_inspector=_Probes(probes=list(probes)),
    )
    return GroundingValidator(ctx.criteria).run(ctx)


# ============================================================== scenes ==


class TestAssemblyLineAllGrounded:
    """Four parts sitting flush on the floor (z=0)."""

    def test_all_resting_passes(self):
        probes = [
            _probe("/Cell/PartA", aabb_bottom_z=0.0,    hit_z=0.0),
            _probe("/Cell/PartB", aabb_bottom_z=0.001,  hit_z=0.0),  # 1mm — within tol
            _probe("/Cell/PartC", aabb_bottom_z=-0.001, hit_z=0.0),  # -1mm — within tol
            _probe("/Cell/PartD", aabb_bottom_z=0.0,    hit_z=0.0),
        ]
        assert _run(probes) == []


class TestFloatingObject:
    """One part levitating above the floor."""

    def test_floating_caught_specifically(self):
        probes = [
            _probe("/Cell/PartA", aabb_bottom_z=0.0,  hit_z=0.0),
            _probe("/Cell/PartB", aabb_bottom_z=0.5,  hit_z=0.0),    # 50 cm above
        ]
        issues = _run(probes)
        codes = [i.code for i in issues]
        assert codes == [CODE_FLOATING]
        assert issues[0].prim_paths == ("/Cell/PartB",)


class TestBuriedObject:
    """A bracket sunk into the floor."""

    def test_buried_caught_specifically(self):
        probes = [
            _probe("/Cell/Bracket", aabb_bottom_z=-0.05, hit_z=0.0),  # 5 cm under
        ]
        issues = _run(probes)
        codes = [i.code for i in issues]
        assert codes == [CODE_BURIED]


class TestMixedIntentCell:
    """A cell with a floor part, a ceiling lamp (intent=false),
    a conveyor section (intent=kinematic), and an untagged object."""

    def test_intent_is_correctly_differentiated(self):
        probes = [
            # Grounded — OK
            _probe("/Cell/Floor/PartA", intent="true",  aabb_bottom_z=0.0, hit_z=0.0),
            # Ceiling lamp — intent=false: floating is intentional, no issue
            _probe("/Cell/Ceiling/Lamp", intent="false",
                   aabb_bottom_z=2.0, hit_path=None, hit_z=None),
            # Conveyor — intent=kinematic: position is user-set, but support must exist
            _probe("/Cell/Conveyor", intent="kinematic",
                   aabb_bottom_z=0.5, hit_z=0.0),                         # OK
            # Untagged part that's floating — should WARN + FAIL
            _probe("/Cell/Unknown", intent=None, aabb_bottom_z=1.0, hit_z=0.0),
        ]
        issues = _run(probes)
        per_path = {i.prim_paths[0]: [] for i in issues}
        for i in issues:
            per_path[i.prim_paths[0]].append(i.code)

        # Floor part — no issues
        assert "/Cell/Floor/PartA" not in per_path

        # Ceiling lamp — no issues
        assert "/Cell/Ceiling/Lamp" not in per_path

        # Conveyor — no issues
        assert "/Cell/Conveyor" not in per_path

        # Unknown — both NO_INTENT_TAG (WARN) and FLOATING (FAIL)
        assert sorted(per_path["/Cell/Unknown"]) == sorted([CODE_FLOATING, CODE_NO_INTENT_TAG])


class TestNoSupportForCentral:
    """A pallet that was supposed to be on the floor but the floor wasn't loaded."""

    def test_no_support_caught(self):
        probes = [
            _probe("/Cell/Pallet", aabb_bottom_z=0.5,
                   hit_path=None, hit_z=None),
        ]
        issues = _run(probes)
        assert [i.code for i in issues] == [CODE_NO_SUPPORT_FOUND]


class TestSceneDeterminism:
    def test_probe_order_does_not_change_output(self):
        probes = [
            _probe("/Cell/PartA", aabb_bottom_z=0.5, hit_z=0.0),       # FAIL
            _probe("/Cell/PartB", aabb_bottom_z=-0.05, hit_z=0.0),     # FAIL buried
            _probe("/Cell/PartC", aabb_bottom_z=0.0, hit_path=None, hit_z=None),  # no support
        ]
        assert _run(probes) == _run(list(reversed(probes)))
