"""Scene-level integration tests for DeterministicResetValidator.

Builds multi-cycle ResetReports for representative scenes (a small
assembly of dynamic bodies) and asserts the validator detects pose
drift, spawn-order jitter, and residual contacts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from asset_validator import (
    AcceptanceCriteria,
    BodyState,
    ContactPair,
    DeterministicResetValidator,
    ResetCycle,
    ResetReport,
    ResetSimulator,
    Severity,
    ValidationContext,
)
from asset_validator.validators.deterministic_reset import (
    CODE_CONTACT_AFTER_RESET,
    CODE_CYCLE_VARIANCE_TRANS,
    CODE_DETERMINISM_FLAG_MISSING,
    CODE_NON_DETERMINISTIC_AUTHORING,
    CODE_POSE_ROTATION_DRIFT,
    CODE_POSE_TRANSLATION_DRIFT,
    CODE_SPAWN_ORDER_MISMATCH,
)


# --------------------------------------------------------------- mock --


@dataclass
class _Sim:
    report: ResetReport

    def get_reset_report(self) -> ResetReport:
        return self.report


_IDENT_Q = (1.0, 0.0, 0.0, 0.0)


def _body(path, t=(0,0,0), q=_IDENT_Q, v=(0,0,0), w=(0,0,0)):
    return BodyState(prim_path=path, translation=tuple(map(float, t)),
                     rotation_quat=tuple(map(float, q)),
                     linear_velocity=tuple(map(float, v)),
                     angular_velocity=tuple(map(float, w)))


def _cycle(idx, *, after_step=(), after_reset=(), spawn_order=(), contacts=()):
    return ResetCycle(cycle_index=idx, after_step_state=tuple(after_step),
                      after_reset_state=tuple(after_reset),
                      spawn_order=tuple(spawn_order),
                      contact_pairs_after_reset=tuple(contacts))


def _report(*, initial=(), spawn_order=(), cycles=(), det=True, seed=True, non_det=()):
    return ResetReport(
        determinism_flag_set=det, seed_set=seed,
        initial_state=tuple(initial), initial_spawn_order=tuple(spawn_order),
        cycles=tuple(cycles), non_deterministic_authoring=tuple(non_det),
    )


def _run(report):
    ctx = ValidationContext(
        asset_uri="test://scene",
        criteria=AcceptanceCriteria(),
        reset_simulator=_Sim(report=report),
    )
    return DeterministicResetValidator(ctx.criteria).run(ctx)


# ============================================================== scenes ==


class TestThreeCycleClean:
    """Two dynamic parts, three perfect reset cycles."""

    def test_clean_run_no_issues(self):
        b_a_init = _body("/Cell/PartA", t=(0.0, 0.0, 1.0))
        b_b_init = _body("/Cell/PartB", t=(0.5, 0.0, 1.0))
        b_a_step = _body("/Cell/PartA", t=(0.0, 0.0, 0.0))   # fell to floor
        b_b_step = _body("/Cell/PartB", t=(0.5, 0.0, 0.0))

        cycles = []
        for i in range(1, 4):
            cycles.append(_cycle(
                i,
                after_step=(b_a_step, b_b_step),
                after_reset=(b_a_init, b_b_init),
                spawn_order=("/Cell/PartA", "/Cell/PartB"),
            ))

        report = _report(
            initial=(b_a_init, b_b_init),
            spawn_order=("/Cell/PartA", "/Cell/PartB"),
            cycles=cycles,
        )
        assert _run(report) == []


class TestPoseDriftAcrossCycles:
    """Cycle 3 fails to reset PartA precisely — 1mm drift."""

    def test_drift_caught_on_specific_cycle(self):
        b_init = _body("/Cell/Part", t=(0.0, 0.0, 1.0))
        b_drifted = _body("/Cell/Part", t=(1.0e-3, 0.0, 1.0))   # 1mm drift

        cycles = [
            _cycle(1, after_reset=(b_init,),    spawn_order=("/Cell/Part",)),
            _cycle(2, after_reset=(b_init,),    spawn_order=("/Cell/Part",)),
            _cycle(3, after_reset=(b_drifted,), spawn_order=("/Cell/Part",)),
        ]
        report = _report(initial=(b_init,), spawn_order=("/Cell/Part",), cycles=cycles)
        issues = _run(report)

        # Exactly one translation-drift issue, on cycle 3, for /Cell/Part
        drifts = [i for i in issues if i.code == CODE_POSE_TRANSLATION_DRIFT]
        assert len(drifts) == 1
        assert drifts[0].metric_dict()["cycle_index"] == 3.0
        assert drifts[0].prim_paths == ("/Cell/Part",)


class TestSpawnOrderJitter:
    """Cycle 2 spawns bodies in a different order than initial."""

    def test_jitter_detected(self):
        a, b = _body("/A"), _body("/B")
        cycles = [
            _cycle(1, after_reset=(a, b), spawn_order=("/A", "/B")),
            _cycle(2, after_reset=(a, b), spawn_order=("/B", "/A")),   # swap!
        ]
        report = _report(initial=(a, b), spawn_order=("/A", "/B"), cycles=cycles)
        issues = _run(report)

        spawn_issues = [i for i in issues if i.code == CODE_SPAWN_ORDER_MISMATCH]
        assert len(spawn_issues) == 1
        assert spawn_issues[0].metric_dict()["cycle_index"] == 2.0


class TestResidualContactAfterReset:
    """A part is left penetrating another at t=0 of the next cycle."""

    def test_contact_caught(self):
        a = _body("/PartA"); b = _body("/PartB")
        pair = ContactPair.create("/PartA", "/PartB", 5.0e-4)    # 0.5mm penetration
        cycles = [_cycle(1, after_reset=(a, b),
                         spawn_order=("/PartA", "/PartB"),
                         contacts=(pair,))]
        report = _report(initial=(a, b),
                         spawn_order=("/PartA", "/PartB"), cycles=cycles)
        issues = _run(report)
        cra = [i for i in issues if i.code == CODE_CONTACT_AFTER_RESET]
        assert len(cra) == 1
        assert set(cra[0].prim_paths) == {"/PartA", "/PartB"}


class TestFullDiagnosticScene:
    """A genuinely bad run: det flag off, non-det authoring, drift + cycle variance."""

    def test_multiple_issue_classes_in_one_report(self):
        init = _body("/Body")
        # Cycle 1: clean
        c1 = _cycle(1,
                    after_step=(_body("/Body", t=(1.0, 0, 0)),),
                    after_reset=(init,),
                    spawn_order=("/Body",))
        # Cycle 2: 1mm drift after reset + after_step differs from c1
        c2 = _cycle(2,
                    after_step=(_body("/Body", t=(1.01, 0, 0)),),
                    after_reset=(_body("/Body", t=(1.0e-3, 0, 0)),),
                    spawn_order=("/Body",))

        report = _report(
            initial=(init,), spawn_order=("/Body",), cycles=(c1, c2),
            det=False, seed=True,
            non_det=("/Body",),
        )
        issues = _run(report)
        codes = [i.code for i in issues]

        # All four expected diagnostics
        assert CODE_DETERMINISM_FLAG_MISSING     in codes
        assert CODE_NON_DETERMINISTIC_AUTHORING  in codes
        assert CODE_POSE_TRANSLATION_DRIFT       in codes
        assert CODE_CYCLE_VARIANCE_TRANS         in codes

        # Severity ordering: FAILs first
        sevs = [i.severity for i in issues]
        assert sevs == sorted(sevs, reverse=True)

        # The WARN is the non-deterministic authoring; one of them
        warns = [i for i in issues if i.severity == Severity.WARN]
        assert any(i.code == CODE_NON_DETERMINISTIC_AUTHORING for i in warns)


class TestRotationDriftAcrossCycles:
    """A rotational anchor drifts by ~1° on cycle 2's reset."""

    def test_rotation_drift_caught(self):
        init = _body("/Joint")
        ang = math.radians(1.0)
        drifted = _body("/Joint",
                        q=(math.cos(ang/2), 0.0, 0.0, math.sin(ang/2)))
        cycles = [
            _cycle(1, after_reset=(init,),    spawn_order=("/Joint",)),
            _cycle(2, after_reset=(drifted,), spawn_order=("/Joint",)),
        ]
        report = _report(initial=(init,), spawn_order=("/Joint",), cycles=cycles)
        issues = _run(report)
        rots = [i for i in issues if i.code == CODE_POSE_ROTATION_DRIFT]
        assert len(rots) == 1
        assert rots[0].metric_dict()["cycle_index"] == 2.0


class TestSimulatorAcceptsProtocol:
    """Sanity: _Sim satisfies the ResetSimulator Protocol structurally."""

    def test_structural_protocol_check(self):
        _: ResetSimulator = _Sim(report=_report())
