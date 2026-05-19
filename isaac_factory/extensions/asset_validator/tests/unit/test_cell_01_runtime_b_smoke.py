"""Runtime-B smoke test for the cell_01 assembled stage.

This is the Phase B "before Phase C" Runtime-B gate (sprint contract +
user requirements):

  1. PhysxScene smoke — opening the cell stage under Kit composes the
     `physxScene:*` custom attributes into ``PhysxSchema.PhysxSceneAPI``
     and the values match what Runtime A authored.
  2. Belt surface velocity smoke — the `physxSurfaceVelocity:*` custom
     attributes round-trip into ``PhysxSchema.PhysxSurfaceVelocityAPI``
     and PhysX applies the kinematic surface motion at simulation step.
  3. Conveyor determinism — peg is transported in -X by friction; reset
     restores the authored initial pose; three reset cycles match each
     other in final pose to ``DeterministicReset`` tolerances.

Runs ONLY under Kit Python — `isaacsim` is the gating sentinel. Under
Runtime A this file is skipped at collection time.

The cell stage path is resolved relative to the workspace root
(``CELL_STAGE_PATH`` constant). Tests that depend on a clean build of
the stage assume ``scripts/build_cell_01.sh`` has been run beforehand —
the Runtime-B suite does NOT call back into the Runtime-A build, both
because the runtimes are isolated and because the build is part of
``scripts/run_scene_validation.sh``'s contract, not this test's.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest


# `isaacsim` only resolves in Kit Python. Use pytestmark rather than
# pytest.importorskip — the latter raises Skipped at module load, and
# under pytest 9.0.2 that exception can bleed into the collection of
# sibling test modules.
try:
    import isaacsim                                  # noqa: F401
    _ISAAC_AVAILABLE = True
except ImportError:
    _ISAAC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _ISAAC_AVAILABLE,
    reason="Kit Python (Runtime B) required — isaacsim package not importable",
)


# Resolved at module load — five parents up:
#   parents[0] = unit
#   parents[1] = tests
#   parents[2] = asset_validator
#   parents[3] = extensions
#   parents[4] = isaac_factory
#   parents[5] = workspace root  ← /home/cap2/last
_WORKSPACE = Path(__file__).resolve().parents[5]
CELL_STAGE_PATH = _WORKSPACE / "assets" / "cells" / "cell_01.usda"


# Sprint-pinned tolerances for the Phase-B Runtime-B gate. Tighter than
# DeterministicResetThresholds because we are testing a static-pose
# reset, not a multi-cycle post-step measurement.
TRANSLATE_RESET_TOL_M = 1e-4   # 0.1 mm
TRANSPORT_DIR_TOL     = 0.20   # |peg.x(t1) - peg.x(t0)| / belt_speed * dt >= this fraction

PEG_PATH         = "/World/Parts/Peg_01"
# Co-located with the kinematic belt prim — see templates.author_belt_surface
# for the rationale and the minimal repro that proves PhysX requires this.
BELT_COLLIDER    = "/World/Machinery/Conveyor_InFeed/Belt"
PHYSICS_SCENE    = "/World/PhysicsScene"

EXPECTED_DETERMINISM   = True
EXPECTED_SOLVER_TYPE   = "TGS"
EXPECTED_BELT_VELOCITY = (-0.10, 0.0, 0.0)


# ============================================================== sim_app ==


@pytest.fixture(scope="module")
def sim_app():
    """Boot SimulationApp once for all tests in this module."""
    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    yield app
    app.close()


@pytest.fixture
def stage(sim_app):
    """Open the canonical cell stage into the shared omni.usd context."""
    import omni.usd
    ctx = omni.usd.get_context()

    assert CELL_STAGE_PATH.is_file(), (
        f"cell stage missing — run scripts/build_cell_01.sh first.\n"
        f"  expected: {CELL_STAGE_PATH}"
    )

    result = ctx.open_stage(str(CELL_STAGE_PATH))
    # Isaac Sim 5 returns a single bool; older returns (bool, error). Support both.
    success = bool(result[0]) if isinstance(result, tuple) else bool(result)
    assert success, f"failed to open {CELL_STAGE_PATH}"

    yield ctx.get_stage()


# ============================================================ PhysxScene ==


class TestPhysxScene:
    """Custom attributes authored by Runtime A round-trip into PhysxSchema."""

    def test_enhanced_determinism_round_trips(self, stage):
        from pxr import PhysxSchema
        prim = stage.GetPrimAtPath(PHYSICS_SCENE)
        assert prim and prim.IsValid()
        scene_api = PhysxSchema.PhysxSceneAPI.Apply(prim)
        attr = scene_api.GetEnableEnhancedDeterminismAttr()
        assert attr and attr.HasAuthoredValue(), (
            "physxScene:enableEnhancedDeterminism not visible to PhysxSchema"
        )
        assert bool(attr.Get()) is EXPECTED_DETERMINISM

    def test_solver_type_round_trips(self, stage):
        from pxr import PhysxSchema
        prim = stage.GetPrimAtPath(PHYSICS_SCENE)
        scene_api = PhysxSchema.PhysxSceneAPI.Apply(prim)
        attr = scene_api.GetSolverTypeAttr()
        assert attr and attr.HasAuthoredValue()
        assert str(attr.Get()) == EXPECTED_SOLVER_TYPE


# ====================================================== SurfaceVelocity ==


class TestBeltSurfaceVelocity:
    """Belt's `physxSurfaceVelocity:*` custom attrs become PhysxSurfaceVelocityAPI."""

    def test_surface_velocity_round_trips(self, stage):
        from pxr import PhysxSchema
        prim = stage.GetPrimAtPath(BELT_COLLIDER)
        assert prim and prim.IsValid()
        sv = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(prim)
        enabled_attr = sv.GetSurfaceVelocityEnabledAttr()
        assert enabled_attr and enabled_attr.HasAuthoredValue()
        assert bool(enabled_attr.Get()) is True

        vel_attr = sv.GetSurfaceVelocityAttr()
        assert vel_attr and vel_attr.HasAuthoredValue()
        v = vel_attr.Get()
        assert (float(v[0]), float(v[1]), float(v[2])) == pytest.approx(EXPECTED_BELT_VELOCITY)


# ====================================================== transport+reset ==


def _peg_world_translate(stage):
    """Read the peg's world-space translation from USD (post-step or post-reset)."""
    from pxr import UsdGeom, Usd
    prim = stage.GetPrimAtPath(PEG_PATH)
    xformable = UsdGeom.Xformable(prim)
    mat = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    t = mat.ExtractTranslation()
    return (float(t[0]), float(t[1]), float(t[2]))


def _peg_authored_translate(stage):
    """Peg's authored xformOp:translate (pre-simulation)."""
    prim = stage.GetPrimAtPath(PEG_PATH)
    t = prim.GetAttribute("xformOp:translate").Get()
    return (float(t[0]), float(t[1]), float(t[2]))


def _step_world(world, n: int) -> None:
    for _ in range(n):
        world.step(render=False)


@pytest.fixture
def world(stage):
    """Build a World on top of the opened stage and start playing.

    ``World.reset()`` initialises sim state but does not run PhysX —
    ``play()`` is required for ``step(render=False)`` to advance physics.
    """
    from isaacsim.core.api import World
    from pxr import PhysxSchema

    # Idempotent re-Apply: pin the schema activation even though it's
    # already in apiSchemas from Runtime-A authoring.
    belt = stage.GetPrimAtPath(BELT_COLLIDER)
    PhysxSchema.PhysxSurfaceVelocityAPI.Apply(belt)

    w = World(physics_dt=1.0 / 60.0, rendering_dt=1.0 / 60.0)
    w.reset()
    w.play()
    return w


class TestConveyorTransport:
    """Peg friction transport under PhysxSurfaceVelocityAPI.

    Resolved by co-locating RigidBodyAPI + CollisionAPI + PhysxSurfaceVelocityAPI
    on the same belt prim (templates.author_belt_surface). The minimal repro
    at scripts/diag_repro_surface_velocity.py and NVIDIA's own
    SurfaceVelocityDemo / ConveyorBeltDemo / isaacsim.asset.gen.conveyor
    extension all confirm this is the only working configuration in Kit 5.0.
    """

    def test_peg_moves_in_minus_x_under_friction(self, world, stage):
        authored_t = _peg_authored_translate(stage)

        # A short warmup so PhysX picks up the surface velocity contact.
        _step_world(world, n=10)
        t_after_warmup = _peg_world_translate(stage)

        # Step further; the peg's x should be MORE negative now.
        _step_world(world, n=30)
        t_after_run = _peg_world_translate(stage)

        delta_x = t_after_run[0] - t_after_warmup[0]
        assert delta_x < -1e-4, (
            f"Peg did not move in -X under friction transport. "
            f"authored={authored_t} after_warmup={t_after_warmup} "
            f"after_run={t_after_run} delta_x={delta_x:.6f}"
        )
        # And it should not have fallen off the belt sideways or vertically.
        assert abs(t_after_run[1] - authored_t[1]) < 5e-3, "peg drifted in Y"
        assert abs(t_after_run[2] - authored_t[2]) < 5e-3, "peg lost / fell off belt in Z"


class TestConveyorDeterministicReset:
    """Three reset cycles must all return the peg to the authored initial pose."""

    def test_three_resets_match_authored_pose(self, world, stage):
        authored = _peg_authored_translate(stage)
        seen: list[tuple[float, float, float]] = []
        for _ in range(3):
            _step_world(world, n=20)
            world.reset()
            seen.append(_peg_world_translate(stage))

        for i, t in enumerate(seen):
            for axis, expected, actual in zip("xyz", authored, t):
                assert abs(actual - expected) < TRANSLATE_RESET_TOL_M, (
                    f"cycle {i} {axis}-axis differs from authored: "
                    f"expected={expected:.6f} got={actual:.6f} "
                    f"tol={TRANSLATE_RESET_TOL_M}"
                )
        # Inter-cycle equality — same reset, same answer.
        for i in range(1, len(seen)):
            for axis, a, b in zip("xyz", seen[0], seen[i]):
                assert math.isclose(a, b, abs_tol=TRANSLATE_RESET_TOL_M), (
                    f"cycles 0 and {i} disagree on {axis}: {a} vs {b}"
                )
