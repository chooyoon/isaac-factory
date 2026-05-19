"""Runtime B diagnostic: probe whether PhysxSurfaceVelocityAPI engages.

Steps:
  1. Boot SimulationApp (headless)
  2. Open cell_01.usda
  3. Build a World, play it
  4. Step physics; after each step, print peg linear velocity + position
     and any PhysX warnings

Usage:
    /home/cap2/isaac-sim-5.0.0/python.sh scripts/diag_belt_transport.py
"""

from __future__ import annotations

import sys
from pathlib import Path


DIAG_LOG = Path("/home/cap2/last/logs/runtime_b_tests/diag_belt_transport.log")


def _log(msg: str) -> None:
    DIAG_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DIAG_LOG.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
        import os
        os.fsync(fh.fileno())


def main() -> int:
    if DIAG_LOG.exists():
        DIAG_LOG.unlink()
    _log("[diag] boot SimulationApp")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})

    try:
        return _run(app)
    except Exception as e:
        import traceback
        _log(f"[diag] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _run(app) -> int:
    import omni.usd
    from pxr import PhysxSchema, Usd, UsdGeom, UsdPhysics

    workspace = Path(__file__).resolve().parents[1]
    cell_stage = workspace / "assets" / "cells" / "cell_01.usda"
    _log(f"[diag] stage = {cell_stage}")

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(cell_stage))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[diag] failed to open stage")
        return 1
    stage = ctx.get_stage()
    _log("[diag] stage opened")

    belt_path = "/World/Machinery/Conveyor_InFeed/Belt"
    belt_collider_path = belt_path + "/collider"
    peg_path = "/World/Parts/Peg_01"
    peg_collider_path = peg_path + "/collider"

    belt = stage.GetPrimAtPath(belt_collider_path)
    peg  = stage.GetPrimAtPath(peg_path)

    _log(f"[diag] belt apiSchemas (raw metadata):")
    md = belt.GetMetadata("apiSchemas")
    _log(f"           prepended={list(md.prependedItems)}")
    _log(f"           explicit={list(md.explicitItems)}")

    # Inspect bound PhysicsMaterial values from USD's perspective.
    from pxr import UsdShade
    binding = UsdShade.MaterialBindingAPI(belt).GetDirectBinding("physics")
    belt_mat = binding.GetMaterial()
    if belt_mat:
        mat_api_belt = UsdPhysics.MaterialAPI(belt_mat.GetPrim())
        _log(f"[diag] belt material attrs:")
        _log(f"    staticFriction  = {mat_api_belt.GetStaticFrictionAttr().Get()}")
        _log(f"    dynamicFriction = {mat_api_belt.GetDynamicFrictionAttr().Get()}")
        _log(f"    restitution     = {mat_api_belt.GetRestitutionAttr().Get()}")
        _log(f"    density         = {mat_api_belt.GetDensityAttr().Get()}")
    else:
        _log("[diag] belt material binding NOT resolvable as UsdShade.Material!")

    peg_col = stage.GetPrimAtPath(peg_collider_path)
    binding2 = UsdShade.MaterialBindingAPI(peg_col).GetDirectBinding("physics")
    peg_mat = binding2.GetMaterial()
    if peg_mat:
        mat_api_peg = UsdPhysics.MaterialAPI(peg_mat.GetPrim())
        _log(f"[diag] peg material attrs:")
        _log(f"    staticFriction  = {mat_api_peg.GetStaticFrictionAttr().Get()}")
        _log(f"    dynamicFriction = {mat_api_peg.GetDynamicFrictionAttr().Get()}")

    # Also: check belt rigid-body parent (where MaterialAPI might also need binding)
    rb_prim = belt.GetParent()
    rb_binding = UsdShade.MaterialBindingAPI(rb_prim).GetDirectBinding("physics")
    _log(f"[diag] belt RIGID-BODY (parent Xform) physics material binding: "
         f"{rb_binding.GetMaterialPath() if rb_binding.GetMaterial() else 'NONE'}")

    sv = PhysxSchema.PhysxSurfaceVelocityAPI.Apply(belt)
    _log(f"[diag] surfaceVelocityEnabled = {sv.GetSurfaceVelocityEnabledAttr().Get()}")
    _log(f"[diag] surfaceVelocity        = {tuple(sv.GetSurfaceVelocityAttr().Get())}")

    rb = UsdPhysics.RigidBodyAPI(belt.GetParent())  # the Belt Xform
    _log(f"[diag] belt kinematicEnabled  = {rb.GetKinematicEnabledAttr().Get()}")

    # Bind material check
    binding_rel = belt.GetRelationship("material:binding:physics")
    _log(f"[diag] belt material binding  = {[str(t) for t in binding_rel.GetTargets()] if binding_rel else 'NONE'}")
    binding_rel = peg.GetPrimAtPath(peg_collider_path).GetRelationship("material:binding:physics")
    _log(f"[diag] peg  material binding  = {[str(t) for t in binding_rel.GetTargets()] if binding_rel else 'NONE'}")

    from isaacsim.core.api import World
    from isaacsim.core.prims import RigidPrim

    w = World(physics_dt=1.0 / 60.0, rendering_dt=1.0 / 60.0)
    w.reset()
    w.play()

    # Wrap peg as a RigidPrim so we can read velocities
    peg_rigid = RigidPrim(prim_paths_expr=peg_path)

    _log(f"\n[diag] is_playing={w.is_playing()}  is_stopped={w.is_stopped()}")
    _log(f"[diag] physics_context.physics_dt={w.get_physics_dt()}")

    # Try simulation_app.update() instead of world.step() to confirm
    # whether World.step is actually advancing physics.
    # Dump every attribute on the surface-velocity API
    _log(f"[diag] === PhysxSurfaceVelocityAPI attributes on belt ===")
    sv_inst = PhysxSchema.PhysxSurfaceVelocityAPI(belt)
    _log(f"  GetSurfaceVelocityAttr().Get():       {sv_inst.GetSurfaceVelocityAttr().Get()}")
    _log(f"  GetSurfaceVelocityEnabledAttr().Get():{sv_inst.GetSurfaceVelocityEnabledAttr().Get()}")
    _log(f"  GetSurfaceAngularVelocityAttr().Get():{sv_inst.GetSurfaceAngularVelocityAttr().Get()}")
    # Iterate all PhysxSurfaceVelocity:* attributes on the prim
    for attr in belt.GetAttributes():
        if "physxSurfaceVelocity" in attr.GetName():
            _log(f"  {attr.GetName()}: value={attr.Get()}  type={attr.GetTypeName()}")
    _log(f"[diag] === PhysxSurfaceVelocityAPI class methods ===")
    methods = [m for m in dir(PhysxSchema.PhysxSurfaceVelocityAPI) if 'Get' in m or 'Local' in m]
    _log(f"  {methods}")

    # ---- experiment: set physxScene:frictionType=patch ----
    from pxr import Sdf
    scene = stage.GetPrimAtPath("/World/PhysicsScene")
    sv_scene = PhysxSchema.PhysxSceneAPI.Apply(scene)
    ft_attr = scene.GetAttribute("physxScene:frictionType")
    _log(f"[diag] frictionType current = {ft_attr.Get() if ft_attr and ft_attr.IsValid() else 'NONE'}")
    sv_scene.CreateFrictionTypeAttr("patch", False)
    _log(f"[diag] frictionType after set = {scene.GetAttribute('physxScene:frictionType').Get()}")

    # ---- experiment: try PhysxMaterialAPI with friction combine mode ----
    if belt_mat:
        # Apply PhysxMaterialAPI on top of UsdPhysics.MaterialAPI
        belt_phys_mat = PhysxSchema.PhysxMaterialAPI.Apply(belt_mat.GetPrim())
        belt_phys_mat.CreateFrictionCombineModeAttr("max", False)
        _log("[diag] Applied PhysxSchema.PhysxMaterialAPI(frictionCombineMode=max) to belt material")
        # Print the PhysxMaterialAPI attrs to confirm
        for a in belt_mat.GetPrim().GetAttributes():
            if "physx" in a.GetName().lower() or "physics" in a.GetName().lower():
                _log(f"  belt mat attr: {a.GetName()} = {a.Get()}")
    if peg_mat:
        peg_phys_mat = PhysxSchema.PhysxMaterialAPI.Apply(peg_mat.GetPrim())
        peg_phys_mat.CreateFrictionCombineModeAttr("max", False)
        _log("[diag] Applied PhysxSchema.PhysxMaterialAPI to peg material")

    # ---- TEST 1: set initial linear velocity directly; does peg move? ----
    import numpy as np
    initial_vel = np.array([[-0.5, 0.0, 0.0]], dtype=np.float32)
    peg_rigid.set_linear_velocities(initial_vel)
    _log(f"[diag] === Set peg initial velocity to {initial_vel.tolist()} ===")

    _log("[diag] === Phase 1: world.step() x 60 with high-precision position ===")
    for i in range(60):
        w.step(render=False)
        if i in (0, 1, 2, 5, 10, 30, 59):
            pos, _ = peg_rigid.get_world_poses()
            lin = peg_rigid.get_linear_velocities()
            _log(f"  step {i:4}: pos.x={float(pos[0][0]):.9f}  lin.x={float(lin[0][0]):.9f}")

    # Query omni.physx directly for actor velocity
    try:
        from omni.physx import get_physx_interface
        physx_iface = get_physx_interface()
        _log(f"[diag] omni.physx interface: {physx_iface}")
    except Exception as e:
        _log(f"[diag] omni.physx query failed: {e}")
    return 0


    # Read USD-side translate too (in case RigidPrim reads from cache)
    from pxr import UsdGeom
    peg_xformable = UsdGeom.Xformable(stage.GetPrimAtPath(peg_path))

    def _read_usd_world_xy():
        mat = peg_xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        t = mat.ExtractTranslation()
        return float(t[0]), float(t[1]), float(t[2])

    _log(f"[diag] stepping 600 ticks at dt=1/60s (10 sec of sim)...")
    for i in range(600):
        w.step(render=False)
        if i in (0, 1, 2, 5, 10, 30, 60, 120, 300, 599):
            pos, _ = peg_rigid.get_world_poses()
            lin = peg_rigid.get_linear_velocities()
            usd_x, usd_y, usd_z = _read_usd_world_xy()
            _log(f"  step {i:4}: RP.x={float(pos[0][0]): .6f} USD.x={usd_x: .6f} "
                 f"USD.y={usd_y: .6f} USD.z={usd_z: .6f}  "
                 f"lin.x={float(lin[0][0]): .6f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
