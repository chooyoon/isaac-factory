"""Full-stage Runtime B validator tests against ``assets/cells/cell_01.usda``.

Runs the three Runtime-B-bound validators end-to-end on the actual cell
stage authored by ``cell_authoring``:

  * ``OverlapValidator``               — uses PhysXContactSource
  * ``ColliderValidator``              — uses PhysXColliderInspector
  * ``DeterministicResetValidator``    — uses PhysXResetSimulator

These complement the Runtime-A static checks already exercised by
``scripts/build_cell_01.sh --check``. Sprint gate: validator-clean over
the full composed cell.

Runtime
-------

Kit Python (Runtime B). Skips at module load under Runtime A.
"""

from __future__ import annotations

from pathlib import Path

import pytest


try:
    import isaacsim                                  # noqa: F401
    _ISAAC_AVAILABLE = True
except ImportError:
    _ISAAC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _ISAAC_AVAILABLE,
    reason="Kit Python (Runtime B) required",
)


_WORKSPACE      = Path(__file__).resolve().parents[5]
CELL_STAGE_PATH = _WORKSPACE / "assets" / "cells" / "cell_01.usda"


# =========================================================== fixtures ==


@pytest.fixture(scope="module")
def sim_app():
    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    yield app
    app.close()


@pytest.fixture
def stage(sim_app):
    import omni.usd
    ctx = omni.usd.get_context()
    assert CELL_STAGE_PATH.is_file(), f"cell stage missing: {CELL_STAGE_PATH}"
    r = ctx.open_stage(str(CELL_STAGE_PATH))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    assert ok, f"failed to open {CELL_STAGE_PATH}"
    yield ctx.get_stage()


@pytest.fixture
def world(stage):
    """A live World instance — required by PhysXContactSource and
    PhysXResetSimulator. The adapter constructors look up
    ``World.instance()``; building it here makes that lookup succeed."""
    from isaacsim.core.api import World
    w = World(physics_dt=1.0 / 60.0, rendering_dt=1.0 / 60.0)
    w.reset()
    yield w
    # Teardown — clear the singleton so the next test gets a fresh World.
    w.clear_instance()


# ============================================================ helpers ==


def _build_ctx(stage, *, with_contact=False, with_collider=False, with_reset=False, **reset_kwargs):
    from asset_validator import AcceptanceCriteria, ValidationContext
    from asset_validator.adapters.physx_collider_inspector import PhysXColliderInspector
    from asset_validator.adapters.physx_contact_source     import PhysXContactSource
    from asset_validator.adapters.physx_reset_simulator    import PhysXResetSimulator

    kwargs = {}
    if with_contact:
        kwargs["contact_source"]    = PhysXContactSource(stage=stage)
    if with_collider:
        kwargs["collider_inspector"]= PhysXColliderInspector(stage=stage)
    if with_reset:
        kwargs["reset_simulator"]   = PhysXResetSimulator(stage=stage, **reset_kwargs)
    return ValidationContext(
        asset_uri=str(CELL_STAGE_PATH),
        criteria=AcceptanceCriteria(),
        **kwargs,
    )


# ============================================================ overlap ==


class TestOverlapValidator:
    """At the authored rest state, the cell should have no overlap issues
    above ``OverlapThresholds.pen_depth_max_m`` (1 mm)."""

    def test_no_overlap_issues_on_rest_state(self, stage, world):
        from asset_validator.validators.overlap import OverlapValidator

        ctx = _build_ctx(stage, with_contact=True)
        try:
            issues = OverlapValidator(ctx.criteria).run(ctx)
        finally:
            ctx.contact_source.close()

        # The peg is in contact with the belt at zero penetration by
        # construction (peg bottom flush with belt top). Static fixtures
        # do not penetrate each other — bottoms flush with floor top.
        # Any FAIL is a genuine geometry mistake.
        fails = [i for i in issues if i.severity.name == "FAIL"]
        warns = [i for i in issues if i.severity.name == "WARN"]
        assert fails == [], (
            f"Overlap FAILs: "
            f"{[(i.code, i.prim_paths, i.message[:120]) for i in fails]}"
        )
        # WARNs are recorded but not strictly blocking — surface log them.
        if warns:
            print(f"\n[overlap] WARN issues: {len(warns)}")
            for i in warns:
                print(f"  {i.code} {i.prim_paths}  {i.message[:120]}")


# ============================================================ collider ==


class TestPhysXColliderValidator:
    """Re-run ColliderValidator under Kit (Runtime B inspector).

    The Runtime-A pass (UsdColliderInspector) already gates the build
    script. This test verifies the **PhysX-backed** inspector agrees —
    which catches authored issues that only surface after PhysX cooks
    the mesh (e.g., convex-decomp hull counts on Phase 2B parts).
    """

    def test_zero_fails_on_full_cell(self, stage, world):
        from asset_validator.validators.collider import ColliderValidator
        ctx = _build_ctx(stage, with_collider=True)
        try:
            issues = ColliderValidator(ctx.criteria).run(ctx)
        finally:
            ctx.collider_inspector.close()
        fails = [i for i in issues if i.severity.name == "FAIL"]
        assert fails == [], (
            f"ColliderValidator FAILs (Runtime B inspector): "
            f"{[(i.code, i.prim_paths) for i in fails]}"
        )


# ====================================================== deterministic reset ==


class TestDeterministicResetValidator:
    """3-cycle reset must produce identical end-state poses.

    Uses the Phase 1.B PhysXResetSimulator. Default tolerances are tight
    (translation 1e-5 m, rotation 1e-4 rad) — appropriate because the
    peg's authored translate is the only initial state and reset is a
    pure-USD-snapshot operation under enhanced determinism.
    """

    def test_three_reset_cycles_deterministic(self, stage, world):
        from asset_validator.validators.deterministic_reset import DeterministicResetValidator
        ctx = _build_ctx(stage, with_reset=True, n_cycles=3, steps_per_cycle=30)
        try:
            issues = DeterministicResetValidator(ctx.criteria).run(ctx)
        finally:
            ctx.reset_simulator.close()
        fails = [i for i in issues if i.severity.name == "FAIL"]
        warns = [i for i in issues if i.severity.name == "WARN"]
        assert fails == [], (
            f"DeterministicResetValidator FAILs: "
            f"{[(i.code, i.prim_paths, i.message[:140]) for i in fails]}"
        )
        if warns:
            print(f"\n[reset] WARN issues: {len(warns)}")
            for i in warns:
                print(f"  {i.code} {i.prim_paths}  {i.message[:140]}")
