"""Minimal reproducible case for PhysxSurfaceVelocityAPI placement.

Tests three placements of the surface-velocity API on a kinematic belt,
each with a dynamic peg sitting on top. We measure the peg's pos.x and
lin.x after 60 physics steps.

Variants
--------

A.  RB+CollisionAPI+SurfaceVelocityAPI all on the SAME prim (single Cube).
    Mirrors NVIDIA SurfaceVelocityDemo / PhysxSurfaceVelocityAPI test.

B.  RigidBodyAPI on parent Xform, CollisionAPI + SurfaceVelocityAPI on
    a child Cube (CURRENT cell_01 architecture — surface velocity on the
    child collider, not the body).

C.  Legacy: kinematic body's `physics:velocity` attribute *is* the
    surface velocity. No PhysxSurfaceVelocityAPI at all. Mirrors
    NVIDIA ConveyorBeltDemo.

Each variant runs in a fresh Usd.Stage; we open three stages in a single
SimulationApp lifetime.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

LOG = Path("/home/cap2/last/logs/runtime_b_tests/diag_repro_surface_velocity.log")


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    _log("[repro] boot SimulationApp")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        return _run(app)
    except Exception as e:
        import traceback
        _log(f"[repro] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _run(app) -> int:
    """Build three test stages in succession and measure peg.x after 60 steps."""
    from isaacsim.core.api import World
    from isaacsim.core.prims import RigidPrim
    from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics
    import omni.usd

    ctx = omni.usd.get_context()

    def _baseline_stage():
        """Open a fresh stage and author the common ground (floor + scene)."""
        ctx.new_stage()
        stage = ctx.get_stage()
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
        stage.SetDefaultPrim(stage.DefinePrim("/World", "Xform"))
        # Floor at z<=0 so peg won't fall to -infinity if it slips
        floor = UsdGeom.Cube.Define(stage, "/World/Floor")
        floor.CreateSizeAttr(1.0)
        floor.AddScaleOp().Set(Gf.Vec3f(20.0, 20.0, 0.1))
        floor.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, -0.05))
        UsdPhysics.CollisionAPI.Apply(floor.GetPrim())
        return stage

    def _peg(stage):
        """Dynamic peg sitting on belt at z=0.625 (bottom at 0.6, top at 0.65)."""
        peg = UsdGeom.Cube.Define(stage, "/World/Peg")
        peg.CreateSizeAttr(1.0)
        peg.AddScaleOp().Set(Gf.Vec3f(0.05, 0.05, 0.05))
        peg.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, 0.625))
        UsdPhysics.CollisionAPI.Apply(peg.GetPrim())
        UsdPhysics.RigidBodyAPI.Apply(peg.GetPrim())
        UsdPhysics.MassAPI.Apply(peg.GetPrim()).CreateMassAttr(0.10)
        # Disable sleep so tiny velocities don't put peg to sleep
        peg.GetPrim().AddAppliedSchema("PhysxRigidBodyAPI")
        st = peg.GetPrim().CreateAttribute("physxRigidBody:sleepThreshold",
                                           Sdf.ValueTypeNames.Float, custom=True)
        st.Set(0.0)
        return peg

    def _simulate(stage, label):
        w = World(physics_dt=1.0/60.0, rendering_dt=1.0/60.0)
        w.reset()
        w.play()
        peg_rigid = RigidPrim(prim_paths_expr="/World/Peg")
        for _ in range(60):
            w.step(render=False)
        pos, _ = peg_rigid.get_world_poses()
        lin = peg_rigid.get_linear_velocities()
        _log(f"[{label}]  after 60 steps:  pos.x = {float(pos[0][0]):+.6f}   "
             f"lin.x = {float(lin[0][0]):+.6f}")
        w.clear_instance()

    # ============ Variant A — SurfaceVelocityAPI on a SELF-COLLIDING kinematic Cube ============
    _log("\n[repro] Variant A: RigidBodyAPI + CollisionAPI + PhysxSurfaceVelocityAPI on SAME prim (a Cube)")
    stage = _baseline_stage()
    belt = UsdGeom.Cube.Define(stage, "/World/Belt")
    belt.CreateSizeAttr(1.0)
    belt.AddScaleOp().Set(Gf.Vec3f(2.0, 0.4, 0.05))
    belt.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, 0.575))   # top at 0.6
    UsdPhysics.CollisionAPI.Apply(belt.GetPrim())
    rb = UsdPhysics.RigidBodyAPI.Apply(belt.GetPrim())
    rb.CreateKinematicEnabledAttr().Set(True)
    sv = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(belt.GetPrim())
    sv.GetSurfaceVelocityAttr().Set(Gf.Vec3f(-0.10, 0.0, 0.0))
    sv.CreateSurfaceVelocityLocalSpaceAttr(False)
    _peg(stage)
    _simulate(stage, "A")

    # ============ Variant B — current cell_01 architecture (CHILD collider) ============
    _log("\n[repro] Variant B: RigidBodyAPI on PARENT, SurfaceVelocityAPI on CHILD collider")
    stage = _baseline_stage()
    belt_xform = UsdGeom.Xform.Define(stage, "/World/Belt")
    belt_xform.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, 0.575))
    rb = UsdPhysics.RigidBodyAPI.Apply(belt_xform.GetPrim())
    rb.CreateKinematicEnabledAttr().Set(True)
    coll = UsdGeom.Cube.Define(stage, "/World/Belt/collider")
    coll.CreateSizeAttr(1.0)
    coll.AddScaleOp().Set(Gf.Vec3f(2.0, 0.4, 0.05))
    UsdPhysics.CollisionAPI.Apply(coll.GetPrim())
    sv = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(coll.GetPrim())
    sv.GetSurfaceVelocityAttr().Set(Gf.Vec3f(-0.10, 0.0, 0.0))
    sv.CreateSurfaceVelocityLocalSpaceAttr(False)
    _peg(stage)
    _simulate(stage, "B")

    # ============ Variant C — legacy: physics:velocity on kinematic body ============
    _log("\n[repro] Variant C: kinematic body's physics:velocity (no SurfaceVelocityAPI)")
    stage = _baseline_stage()
    belt = UsdGeom.Cube.Define(stage, "/World/Belt")
    belt.CreateSizeAttr(1.0)
    belt.AddScaleOp().Set(Gf.Vec3f(2.0, 0.4, 0.05))
    belt.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, 0.575))
    UsdPhysics.CollisionAPI.Apply(belt.GetPrim())
    rb = UsdPhysics.RigidBodyAPI.Apply(belt.GetPrim())
    rb.CreateKinematicEnabledAttr().Set(True)
    rb.GetVelocityAttr().Set(Gf.Vec3f(-0.10, 0.0, 0.0))
    _peg(stage)
    _simulate(stage, "C")

    # ============ Variant D — fix: move SurfaceVelocityAPI to PARENT (same prim as RB) ============
    _log("\n[repro] Variant D: RigidBodyAPI + SurfaceVelocityAPI on PARENT Xform, collider as child")
    stage = _baseline_stage()
    belt_xform = UsdGeom.Xform.Define(stage, "/World/Belt")
    belt_xform.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, 0.575))
    rb = UsdPhysics.RigidBodyAPI.Apply(belt_xform.GetPrim())
    rb.CreateKinematicEnabledAttr().Set(True)
    sv = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(belt_xform.GetPrim())
    sv.GetSurfaceVelocityAttr().Set(Gf.Vec3f(-0.10, 0.0, 0.0))
    sv.CreateSurfaceVelocityLocalSpaceAttr(False)
    coll = UsdGeom.Cube.Define(stage, "/World/Belt/collider")
    coll.CreateSizeAttr(1.0)
    coll.AddScaleOp().Set(Gf.Vec3f(2.0, 0.4, 0.05))
    UsdPhysics.CollisionAPI.Apply(coll.GetPrim())
    _peg(stage)
    _simulate(stage, "D")

    _log("\n[repro] === expected: only variants A, C, D engage transport (peg moves to -X) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
