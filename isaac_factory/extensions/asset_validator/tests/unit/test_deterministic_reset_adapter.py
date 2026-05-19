"""Runtime B integration tests for `PhysXResetSimulator`.

Mirrors `test_overlap_adapter.py` and `test_collider_adapter.py`:
module-level skip if not under Kit Python, module-scoped SimulationApp
fixture, opened_stage helper with the Isaac Sim 5 / older return-shape
compatibility shim.

Run via:

    python isaac_factory/extensions/asset_validator/tools/runtime_b_pytest_runner.py \\
        isaac_factory/extensions/asset_validator/tests/unit/test_reset_adapter.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import isaacsim  # noqa: F401
    _ISAAC_AVAILABLE = True
except ImportError:
    _ISAAC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _ISAAC_AVAILABLE,
    reason="Kit Python (Runtime B) required — isaacsim package not importable",
)


_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "reset"


# ============================================================ sim_app ==


@pytest.fixture(scope="module")
def sim_app():
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
    """Open fixture .usda + clear any pre-existing World instance."""
    import omni.usd
    from isaacsim.core.api import World

    # Ensure no World leak between tests.
    try:
        World.clear_instance()
    except Exception:                                            # pragma: no cover
        pass

    ctx = omni.usd.get_context()

    def _open(name: str):
        path = _FIXTURE_DIR / f"{name}.usda"
        assert path.is_file(), f"missing fixture: {path}"
        rv = ctx.open_stage(str(path))
        if isinstance(rv, tuple):
            result, error = rv
            assert result, f"open_stage failed: {error}"
        else:
            assert rv, f"open_stage failed for: {path}"
        return ctx.get_stage()

    yield _open

    # Teardown: drop the World and stage.
    try:
        World.clear_instance()
    except Exception:                                            # pragma: no cover
        pass
    ctx.new_stage()


def _build_and_run(stage, *, n_cycles=2, steps_per_cycle=5):
    """Helper: build simulator + World, run get_reset_report()."""
    from isaacsim.core.api import World
    from asset_validator.adapters.physx_reset_simulator import (
        PhysXResetSimulator,
    )

    # Simulator construction BEFORE World so contact subscription is in
    # place when PhysX cooks during World init.
    sim = PhysXResetSimulator(
        stage=stage,
        n_cycles=n_cycles,
        steps_per_cycle=steps_per_cycle,
    )
    world = World()
    report = sim.get_reset_report()
    return report, sim, world


# ====================================================== clean reset ==


class TestCleanReset:
    """Single isolated dynamic body — reset is trivial."""

    def test_no_validator_issues(self, opened_stage):
        from asset_validator import (
            AcceptanceCriteria, DeterministicResetValidator, ValidationContext,
        )
        stage = opened_stage("clean_reset")
        report, sim, world = _build_and_run(stage)
        try:
            ctx = ValidationContext(
                asset_uri="test://clean_reset",
                criteria=AcceptanceCriteria(),
                reset_simulator=_FrozenSim(report),
            )
            issues = DeterministicResetValidator(ctx.criteria).run(ctx)
            assert issues == [], f"expected clean; got: {[i.code for i in issues]}"
        finally:
            sim.close()

    def test_determinism_flag_set(self, opened_stage):
        stage = opened_stage("clean_reset")
        report, sim, world = _build_and_run(stage)
        try:
            assert report.determinism_flag_set is True
            assert report.seed_set is True
        finally:
            sim.close()

    def test_initial_and_after_reset_match(self, opened_stage):
        stage = opened_stage("clean_reset")
        report, sim, world = _build_and_run(stage, n_cycles=2)
        try:
            init = {b.prim_path: b for b in report.initial_state}
            for cycle in report.cycles:
                after = {b.prim_path: b for b in cycle.after_reset_state}
                # Same set of bodies
                assert set(init) == set(after)
                # Each body's translation matches initial within tolerance
                for path in init:
                    dt = max(
                        abs(init[path].translation[i] - after[path].translation[i])
                        for i in range(3)
                    )
                    assert dt < 1.0e-3, (path, init[path].translation, after[path].translation)
        finally:
            sim.close()

    def test_no_residual_contacts(self, opened_stage):
        # Single body, no other geometry → no contacts ever.
        stage = opened_stage("clean_reset")
        report, sim, world = _build_and_run(stage, n_cycles=2)
        try:
            for cycle in report.cycles:
                assert cycle.contact_pairs_after_reset == ()
        finally:
            sim.close()


# ============================================== spawn order determinism ==


class TestSpawnOrderDeterminism:
    def test_spawn_order_stable_across_cycles(self, opened_stage):
        stage = opened_stage("two_body_assembly")
        report, sim, world = _build_and_run(stage, n_cycles=3)
        try:
            # Initial spawn order is lex-sorted by path
            assert report.initial_spawn_order == ("/World/Alpha", "/World/Beta")
            # Every cycle's spawn order must match the initial
            for cycle in report.cycles:
                assert cycle.spawn_order == report.initial_spawn_order
        finally:
            sim.close()

    def test_no_spawn_order_mismatch_issue(self, opened_stage):
        from asset_validator import (
            AcceptanceCriteria, DeterministicResetValidator, ValidationContext,
        )
        from asset_validator.validators.deterministic_reset import (
            CODE_SPAWN_ORDER_MISMATCH,
        )
        stage = opened_stage("two_body_assembly")
        report, sim, world = _build_and_run(stage, n_cycles=2)
        try:
            ctx = ValidationContext(
                asset_uri="test://two_body",
                criteria=AcceptanceCriteria(),
                reset_simulator=_FrozenSim(report),
            )
            issues = DeterministicResetValidator(ctx.criteria).run(ctx)
            codes = [i.code for i in issues]
            assert CODE_SPAWN_ORDER_MISMATCH not in codes
        finally:
            sim.close()


# ============================================== non-deterministic authoring ==


class TestNonDeterministicAuthoring:
    def test_random_seed_authoring_detected(self, opened_stage):
        from asset_validator import (
            AcceptanceCriteria, DeterministicResetValidator, ValidationContext,
        )
        from asset_validator.validators.deterministic_reset import (
            CODE_NON_DETERMINISTIC_AUTHORING,
        )
        stage = opened_stage("nondet_authoring")
        report, sim, world = _build_and_run(stage, n_cycles=2)
        try:
            # Adapter must flag the prim
            assert "/World/Random" in report.non_deterministic_authoring
            # Validator emits the WARN
            ctx = ValidationContext(
                asset_uri="test://nondet",
                criteria=AcceptanceCriteria(),
                reset_simulator=_FrozenSim(report),
            )
            issues = DeterministicResetValidator(ctx.criteria).run(ctx)
            codes = [i.code for i in issues]
            assert CODE_NON_DETERMINISTIC_AUTHORING in codes
        finally:
            sim.close()


# ============================================== regression / state hash ==


class TestResetStateRegression:
    """`ResetReport` is a frozen dataclass tree of tuples — two runs over
    the same fixture should yield equal reports (modulo float wobble in
    after_step states; we compare initial + after_reset state)."""

    def test_two_runs_produce_same_post_reset_states(self, opened_stage):
        stage = opened_stage("two_body_assembly")
        # Run 1
        report_a, sim_a, world_a = _build_and_run(stage, n_cycles=2)
        sim_a.close()
        try:
            world_a.clear_instance()
        except Exception:                                       # pragma: no cover
            pass

        # Run 2 — re-open the stage (teardown happens via fixture but we're
        # still inside the test; force a fresh World by clearing instance).
        from isaacsim.core.api import World
        try:
            World.clear_instance()
        except Exception:                                       # pragma: no cover
            pass
        stage_b = opened_stage("two_body_assembly")
        report_b, sim_b, world_b = _build_and_run(stage_b, n_cycles=2)
        try:
            assert len(report_a.cycles) == len(report_b.cycles)
            # After-reset states must match across runs (poses snap back
            # to authored values).
            for ca, cb in zip(report_a.cycles, report_b.cycles):
                assert ca.spawn_order == cb.spawn_order
                assert ca.after_reset_state == cb.after_reset_state
        finally:
            sim_b.close()


# ================================================ snapshot shape ==


class TestSnapshotShape:
    def test_body_state_fields_populated(self, opened_stage):
        """Verify the snapshot mechanism reads body state correctly.

        Tolerance is 5 cm — PhysX's reset re-settles bodies with a few mm
        of cooking jitter that's outside this adapter's control. The
        validator's own §6.1 cycle-to-cycle drift check uses a much
        tighter 1e-5 m, but that's a different invariant (cycle-to-cycle
        consistency, not absolute-pose fidelity to authored values).
        """
        stage = opened_stage("clean_reset")
        report, sim, world = _build_and_run(stage, n_cycles=1)
        try:
            assert len(report.initial_state) == 1
            b = report.initial_state[0]
            assert b.prim_path == "/World/Body"
            # Authored translate is (0, 0, 1); PhysX may shift by a few mm.
            assert b.translation == pytest.approx((0.0, 0.0, 1.0), abs=0.05)
            # Unit quaternion (identity) — these stay tight since rotation
            # has no equivalent of "settling".
            assert b.rotation_quat[0] == pytest.approx(1.0, abs=1e-4)
            for v in b.rotation_quat[1:]:
                assert v == pytest.approx(0.0, abs=1e-4)
            # Velocities zero by construction (adapter always reports 0).
            assert b.linear_velocity == (0.0, 0.0, 0.0)
            assert b.angular_velocity == (0.0, 0.0, 0.0)
        finally:
            sim.close()


# ============================================== lifecycle ==


class TestLifecycle:
    def test_context_manager_unsubscribes(self, opened_stage):
        from isaacsim.core.api import World
        from asset_validator.adapters.physx_reset_simulator import (
            PhysXResetSimulator,
        )
        stage = opened_stage("clean_reset")
        with PhysXResetSimulator(stage=stage, n_cycles=1, steps_per_cycle=1) as sim:
            world = World()
            _ = sim.get_reset_report()
        assert sim._sub is None  # noqa: SLF001


# ============================================ helpers ==


class _FrozenSim:
    """Wrap a ResetReport so it can be passed as a `reset_simulator` to
    the validator without re-running the simulation."""

    def __init__(self, report):
        self._report = report

    def get_reset_report(self):
        return self._report
