"""Phase 3M — gripper-frame transform audit.

Walks the rigid-body / joint chain from the UR10e ``wrist_3_link`` down
to the prismatic-jaw pad colliders and prints, for every node along the
chain:

  * the node's authored local Xform ops (translate, orient, scale)
  * the joint anchors (localPos0/1, localRot0/1) when the node is a joint
  * the prim's computed world transform (under the cell's home pose)
  * the local-axis → world-axis map (i.e. where local +X / +Y / +Z point
    in world coordinates)

Goal: identify exactly which joint or Xform in the chain flips the
local-Z direction. The Phase 3K build script authors the pads at
``PIVOT_Z_OFFSET_M = -0.10`` (i.e. 100 mm BELOW the gripper base in
local +Z space). Empirically the pads end up 100 mm ABOVE wrist_3 in
world Z. Somewhere between the gripper-root Xform and the pad collider,
local +Z gets mapped to world -Z. This audit produces the evidence.

Strict instrumentation only — does NOT modify any USD layer, does NOT
load PhysX, does NOT subscribe to anything. Just reads transforms.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


WORKSPACE       = Path("/home/cap2/last")
CELL_STAGE_PATH = WORKSPACE / "assets" / "cells" / "cell_01.usda"
LOG_FILE        = WORKSPACE / "logs" / "phase_3m_transform_audit.log"


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(msg + "\n")
    print(msg, flush=True)


def main() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
    _log(f"[3m] Phase 3M transform audit; stage={CELL_STAGE_PATH}")

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        return _run()
    except Exception as e:
        import traceback
        _log(f"[3m] EXCEPTION: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _fmt_xyz(v):
    return f"({v[0]:+.5f}, {v[1]:+.5f}, {v[2]:+.5f})"


def _fmt_quat(q):
    # q = (w, x, y, z)
    return f"(w={q[0]:+.5f}, x={q[1]:+.5f}, y={q[2]:+.5f}, z={q[3]:+.5f})"


def _quat_to_basis(q):
    """Return (e_x, e_y, e_z) — world directions of local +X, +Y, +Z."""
    w, x, y, z = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    e_x = (1 - 2*(y*y + z*z), 2*(x*y + w*z),       2*(x*z - w*y))
    e_y = (2*(x*y - w*z),     1 - 2*(x*x + z*z),   2*(y*z + w*x))
    e_z = (2*(x*z + w*y),     2*(y*z - w*x),       1 - 2*(x*x + y*y))
    return e_x, e_y, e_z


def _local_xform_ops(prim):
    """Return a list of (op_name, value, op_type) authored on this prim."""
    from pxr import UsdGeom
    if not prim or not prim.IsValid():
        return []
    xf = UsdGeom.Xformable(prim)
    if not xf:
        return []
    ops = []
    for op in xf.GetOrderedXformOps():
        try:
            v = op.GetOpTransform(0.0)
        except Exception:
            v = None
        ops.append((op.GetOpName(), op.Get(0.0), op.GetOpType()))
    return ops


def _world_xform(stage, path):
    """Returns (translate, world-orient-quat (w,x,y,z), 3x3 rot tuple)."""
    from pxr import UsdGeom, Usd, Gf
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return None, None, None
    mat = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    mat = mat.RemoveScaleShear()
    t = mat.ExtractTranslation()
    q = mat.ExtractRotation().GetQuat()
    quat_wxyz = (float(q.GetReal()),
                 float(q.GetImaginary()[0]),
                 float(q.GetImaginary()[1]),
                 float(q.GetImaginary()[2]))
    rot33 = Gf.Matrix3d(mat.ExtractRotationMatrix())
    rot = tuple(tuple(float(rot33[i][j]) for j in range(3)) for i in range(3))
    return (float(t[0]), float(t[1]), float(t[2])), quat_wxyz, rot


def _report_xform(stage, label, path, indent="  "):
    from pxr import UsdGeom, UsdPhysics
    _log(f"\n{indent}── {label}  ({path})")
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        _log(f"{indent}   MISSING")
        return None
    # Authored local ops.
    ops = _local_xform_ops(prim)
    if ops:
        for op_name, value, op_type in ops:
            _log(f"{indent}   local op {op_name}: {value}")
    else:
        _log(f"{indent}   (no authored xformOps)")
    # Computed world pose.
    t, q, _ = _world_xform(stage, path)
    if t is not None:
        e_x, e_y, e_z = _quat_to_basis(q)
        _log(f"{indent}   world translate: {_fmt_xyz(t)}")
        _log(f"{indent}   world orient   : {_fmt_quat(q)}")
        _log(f"{indent}   local +X → world {_fmt_xyz(e_x)}")
        _log(f"{indent}   local +Y → world {_fmt_xyz(e_y)}")
        _log(f"{indent}   local +Z → world {_fmt_xyz(e_z)}")
    return prim


def _report_joint(stage, label, path, indent="  "):
    from pxr import UsdPhysics, Gf
    _log(f"\n{indent}── JOINT {label}  ({path})")
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        _log(f"{indent}   MISSING")
        return None
    joint = UsdPhysics.Joint(prim)
    if not joint:
        _log(f"{indent}   not a UsdPhysics.Joint")
        return None
    b0 = joint.GetBody0Rel().GetTargets()
    b1 = joint.GetBody1Rel().GetTargets()
    lp0 = joint.GetLocalPos0Attr().Get()
    lp1 = joint.GetLocalPos1Attr().Get()
    lr0 = joint.GetLocalRot0Attr().Get()
    lr1 = joint.GetLocalRot1Attr().Get()
    _log(f"{indent}   body0 = {[str(p) for p in b0]}")
    _log(f"{indent}   body1 = {[str(p) for p in b1]}")
    if lp0 is not None:
        _log(f"{indent}   localPos0 = ({lp0[0]:+.5f}, {lp0[1]:+.5f}, {lp0[2]:+.5f})")
    if lp1 is not None:
        _log(f"{indent}   localPos1 = ({lp1[0]:+.5f}, {lp1[1]:+.5f}, {lp1[2]:+.5f})")
    if lr0 is not None:
        q = (lr0.GetReal(), lr0.GetImaginary()[0], lr0.GetImaginary()[1], lr0.GetImaginary()[2])
        ex, ey, ez = _quat_to_basis(q)
        _log(f"{indent}   localRot0 = {_fmt_quat(q)}")
        _log(f"{indent}     body0-local +Z (joint axis direction in body0) → {_fmt_xyz(ez)}")
    if lr1 is not None:
        q = (lr1.GetReal(), lr1.GetImaginary()[0], lr1.GetImaginary()[1], lr1.GetImaginary()[2])
        ex, ey, ez = _quat_to_basis(q)
        _log(f"{indent}   localRot1 = {_fmt_quat(q)}")
        _log(f"{indent}     body1-local +Z (joint axis direction in body1) → {_fmt_xyz(ez)}")
    if prim.IsA(UsdPhysics.PrismaticJoint):
        pj = UsdPhysics.PrismaticJoint(prim)
        axis = pj.GetAxisAttr().Get()
        _log(f"{indent}   prismatic axis (body0-local) = {axis}")
    return prim


def _run() -> int:
    sys.path.insert(0, str(WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring"))

    import omni.usd
    from isaacsim.core.api import World
    from isaacsim.core.prims import Articulation
    from cell_authoring import load_config

    ctx = omni.usd.get_context()
    r = ctx.open_stage(str(CELL_STAGE_PATH))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    if not ok:
        _log("[3m] cannot open stage"); return 1
    stage = ctx.get_stage()
    cfg = load_config(WORKSPACE / "configs" / "cell_01.yaml")

    # Bring the robot into its home pose so the wrist_3 / ee_link chain
    # is at the same configuration the cycle test sees at t=0.
    world = World()
    world.reset()
    world.play()
    art = Articulation(prim_paths_expr="/World/Robot")
    try:
        world.scene.add(art)
    except Exception:
        pass
    art.initialize()

    import numpy as np
    dof_names = list(art.dof_names)
    UR10E = ("shoulder_pan", "shoulder_lift", "elbow",
             "wrist_1", "wrist_2", "wrist_3")
    joint_indices = [dof_names.index(f"{n}_joint") for n in UR10E]

    home_pose = dict(cfg.robot.home_pose_rad)
    full = art.get_joint_positions()
    for i, name in enumerate(UR10E):
        full[0][joint_indices[i]] = float(home_pose[name])
    art.set_joint_positions(full)
    art.set_joint_position_targets(full)
    for _ in range(15):
        world.step(render=False)

    # ─── BOTTOM LINE: where SHOULD the pad land vs where it actually does? ───
    _log("\n" + "="*72)
    _log("CHAIN AUDIT @ home pose (= approach_pick IK = tool tip world z=0.85)")
    _log("="*72)

    # Walk the chain.
    chain = [
        ("wrist_3_link",                  "/World/Robot/wrist_3_link"),
        ("joints/ee_joint",               "/World/Robot/joints/ee_joint"),
        ("ee_link",                       "/World/Robot/ee_link"),
        ("ee_link/robotiq_base_link",     "/World/Robot/ee_link/robotiq_base_link"),
        ("ee_link/robotiq_base/collisions/base",
                                          "/World/Robot/ee_link/robotiq_base_link/collisions/base"),
        ("ee_link/left_finger",           "/World/Robot/ee_link/left_finger"),
        ("ee_link/left_finger/collisions/finger",
                                          "/World/Robot/ee_link/left_finger/collisions/finger"),
        ("ee_link/right_finger",          "/World/Robot/ee_link/right_finger"),
        ("ee_link/right_finger/collisions/finger",
                                          "/World/Robot/ee_link/right_finger/collisions/finger"),
    ]

    for label, path in chain:
        _report_xform(stage, label, path)

    # Joints in the chain.
    for label, path in [
        ("joints/ee_joint (fixed joint)",  "/World/Robot/joints/ee_joint"),
        ("ee_link/finger_joint",           "/World/Robot/ee_link/finger_joint"),
        ("ee_link/right_finger_joint",     "/World/Robot/ee_link/right_finger_joint"),
    ]:
        _report_joint(stage, label, path)

    # Compute the world-Z deltas now that the home pose has settled.
    _log("\n" + "="*72)
    _log("PAD-vs-WRIST_3 WORLD-Z DELTAS (home pose)")
    _log("="*72)
    targets = {
        "wrist_3_link":           "/World/Robot/wrist_3_link",
        "ee_link":                "/World/Robot/ee_link",
        "robotiq_base_link":      "/World/Robot/ee_link/robotiq_base_link",
        "left_finger":            "/World/Robot/ee_link/left_finger",
        "right_finger":           "/World/Robot/ee_link/right_finger",
    }
    poses = {}
    for k, p in targets.items():
        t, q, _ = _world_xform(stage, p)
        poses[k] = (t, q)
        _log(f"  {k:24s} world_t = {_fmt_xyz(t)}")
    wz = poses["wrist_3_link"][0][2]
    for k in ("ee_link", "robotiq_base_link", "left_finger", "right_finger"):
        dz = poses[k][0][2] - wz
        _log(f"  Δz({k} − wrist_3) = {dz*1000:+.2f} mm")

    # The Phase 3K build script sets pad body origin at
    # local Z = PIVOT_Z_OFFSET_M = -0.10. Expected pad world-Z relative
    # to wrist_3 is therefore −0.10 m IF local Z → world +Z. If pads
    # end up at +0.10 m, local Z → world -Z somewhere in the chain.
    _log("\nExpected pad Δz (per Phase 3K build): −0.10000 m (100 mm BELOW wrist_3 in local +Z).")
    lfz = poses["left_finger"][0][2] - wz
    rfz = poses["right_finger"][0][2] - wz
    _log(f"Observed left_finger  Δz = {lfz:+.5f} m")
    _log(f"Observed right_finger Δz = {rfz:+.5f} m")
    _log(f"Sign-flip evidence: expected/observed ratio ≈ {(-0.10/lfz) if abs(lfz)>1e-6 else 'n/a':}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
