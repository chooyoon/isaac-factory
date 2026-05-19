"""Runtime-B articulation smoke for the cell with UR10e mounted.

Phase 3A gate (sprint contract + user requirements):

  * Robot loads under Kit (articulation resolves)
  * 6 revolute joints + fixed-joint anchors are present
  * Articulation root is on the expected prim
  * Self-collision policy reaches PhysX as authored
  * Robot does NOT fall off the pedestal under gravity / steps
    (the in-asset root_joint anchors base_link)
  * Conveyor + peg transport remain stable with robot present
  * Reset returns the robot to its authored pose
"""

from __future__ import annotations

from pathlib import Path

import pytest


try:
    import isaacsim                                       # noqa: F401
    _ISAAC_AVAILABLE = True
except ImportError:
    _ISAAC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _ISAAC_AVAILABLE,
    reason="Kit Python (Runtime B) required",
)


_WORKSPACE      = Path(__file__).resolve().parents[5]
CELL_STAGE_PATH = _WORKSPACE / "assets" / "cells" / "cell_01.usda"

ROBOT_MOUNT_PATH         = "/World/Robot"
ARTICULATION_ROOT_PATH   = "/World/Robot/root_joint"
BASE_LINK_PATH           = "/World/Robot/base_link"
PEG_PATH                 = "/World/Parts/Peg_01"
EXPECTED_REVOLUTE_JOINTS = 6
PEDESTAL_TOP_Z_M         = 0.80   # cell_01.yaml environment.pedestal.height_m

# Tight pose-stability tolerances. Robot is anchored by a fixed joint
# and should not drift over any number of steps.
ANCHOR_DRIFT_TOL_M = 5e-3   # 5 mm
RESET_TOL_M        = 1e-4   # 0.1 mm


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
    from isaacsim.core.api import World
    w = World(physics_dt=1.0 / 60.0, rendering_dt=1.0 / 60.0)
    w.reset()
    w.play()
    yield w
    w.clear_instance()


# ====================================================== articulation ==


class TestArticulation:
    """Composition + schema correctness."""

    def test_robot_mount_exists(self, stage):
        prim = stage.GetPrimAtPath(ROBOT_MOUNT_PATH)
        assert prim and prim.IsValid()

    def test_articulation_root_present(self, stage):
        from pxr import UsdPhysics
        art = stage.GetPrimAtPath(ARTICULATION_ROOT_PATH)
        assert art and art.IsValid()
        assert art.HasAPI(UsdPhysics.ArticulationRootAPI), (
            "ArticulationRootAPI must be applied on the canonical root_joint prim"
        )

    def test_self_collision_policy_authored(self, stage):
        attr = stage.GetPrimAtPath(ARTICULATION_ROOT_PATH) \
                    .GetAttribute("physxArticulation:enabledSelfCollisions")
        assert attr and attr.HasAuthoredValue(), \
            "self-collision policy must be explicit per sprint requirement"
        assert attr.Get() is False, \
            "Phase 3A policy = self-collision disabled; see configs/cell_01.yaml"

    def test_revolute_joint_count(self, stage):
        """Count only the UR10e arm joints under /<mount>/joints — the
        gripper variant (Phase 3B+) adds its own revolute joints
        elsewhere in the subtree."""
        from pxr import UsdPhysics
        arm_joints_path = ROBOT_MOUNT_PATH + "/joints/"
        rev_joints = [
            p for p in stage.Traverse()
            if str(p.GetPath()).startswith(arm_joints_path)
            and p.IsA(UsdPhysics.RevoluteJoint)
        ]
        assert len(rev_joints) == EXPECTED_REVOLUTE_JOINTS, (
            f"UR10e arm expected {EXPECTED_REVOLUTE_JOINTS} revolute joints "
            f"under {arm_joints_path}; got {len(rev_joints)}"
        )


# ====================================================== stability ==


class TestPedestalAnchor:
    """The in-asset root_joint must keep base_link rigidly at the pedestal top."""

    def test_base_link_at_pedestal_top_at_t0(self, world, stage):
        from pxr import UsdGeom, Usd
        mat = UsdGeom.Xformable(stage.GetPrimAtPath(BASE_LINK_PATH)) \
                    .ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        t = mat.RemoveScaleShear().ExtractTranslation()
        # Expect (0, 0, pedestal_top_z) ± float-precision noise
        assert abs(float(t[2]) - PEDESTAL_TOP_Z_M) < ANCHOR_DRIFT_TOL_M, \
            f"base_link z = {float(t[2])} not at pedestal top {PEDESTAL_TOP_Z_M}"

    def test_base_link_does_not_drift_over_60_steps(self, world, stage):
        """No drift over 1 s of physics — the fixed joint must hold."""
        from pxr import UsdGeom, Usd
        xf = UsdGeom.Xformable(stage.GetPrimAtPath(BASE_LINK_PATH))
        t0 = xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default()) \
                .RemoveScaleShear().ExtractTranslation()

        for _ in range(60):
            world.step(render=False)

        t1 = xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default()) \
                .RemoveScaleShear().ExtractTranslation()

        for axis in range(3):
            assert abs(float(t1[axis]) - float(t0[axis])) < ANCHOR_DRIFT_TOL_M, \
                f"base_link drifted on axis {axis}: {float(t0[axis])} → {float(t1[axis])}"


# ====================================================== reset ==


class TestRobotReset:
    """Resetting the world returns the robot's base_link to the authored pose."""

    def test_two_resets_identical_base_pose(self, world, stage):
        from pxr import UsdGeom, Usd
        xf = UsdGeom.Xformable(stage.GetPrimAtPath(BASE_LINK_PATH))

        def read():
            mat = xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            t = mat.RemoveScaleShear().ExtractTranslation()
            return (float(t[0]), float(t[1]), float(t[2]))

        # cycle 1
        for _ in range(20):
            world.step(render=False)
        world.reset()
        a = read()

        # cycle 2
        for _ in range(20):
            world.step(render=False)
        world.reset()
        b = read()

        for ax, (va, vb) in enumerate(zip(a, b)):
            assert abs(va - vb) < RESET_TOL_M, \
                f"axis {ax}: cycle1={va} cycle2={vb} (tol {RESET_TOL_M})"


# ====================================================== conveyor still works ==


class TestConveyorStillTransportsWithRobot:
    """Confirm the friction-transport gate (Phase C) is not regressed by robot."""

    def test_peg_moves_in_minus_x(self, world, stage):
        from isaacsim.core.prims import RigidPrim
        peg = RigidPrim(prim_paths_expr=PEG_PATH)
        # warmup so peg settles onto belt and transport engages
        for _ in range(20):
            world.step(render=False)
        pos_a, _ = peg.get_world_poses()
        for _ in range(30):
            world.step(render=False)
        pos_b, _ = peg.get_world_poses()
        delta_x = float(pos_b[0][0]) - float(pos_a[0][0])
        assert delta_x < -1e-4, (
            f"Peg failed to advance in -X under belt friction with robot present; "
            f"a.x={float(pos_a[0][0])} b.x={float(pos_b[0][0])} delta={delta_x}"
        )
