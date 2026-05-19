"""Verify the offline IK solution against actual Kit articulation FK.

Sets each waypoint's joint angles, plays the simulation until joints
converge (or N steps), and reads the actual world position of the
gripper tip — to compare against the IK script's predicted achieved
position.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

LOG = Path("/home/cap2/last/logs/diag_verify_ik.log")


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as fh:
        fh.write(msg + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        return _run(app)
    except Exception as e:
        import traceback
        _log(f"ERR: {e}\n{traceback.format_exc()}")
        return 1
    finally:
        app.close()


def _run(app) -> int:
    import numpy as np
    import yaml
    import omni.usd
    from pxr import UsdGeom, Usd, UsdPhysics
    from isaacsim.core.api import World
    from isaacsim.core.prims import Articulation

    cell = Path("/home/cap2/last/assets/cells/cell_01.usda")
    ctx = omni.usd.get_context()
    ctx.open_stage(str(cell))
    stage = ctx.get_stage()

    world = World(physics_dt=1.0/60.0, rendering_dt=1.0/60.0)
    world.reset()
    world.play()

    art = Articulation(prim_paths_expr="/World/Robot/root_joint")
    art.initialize()
    _log(f"DOFs: {list(art.dof_names) if hasattr(art, 'dof_names') else 'N/A'}")
    _log(f"num_dof: {art.num_dof}")

    UR10E_JOINT_NAMES = ("shoulder_pan", "shoulder_lift", "elbow",
                         "wrist_1", "wrist_2", "wrist_3")
    dof_names = list(art.dof_names)
    arm_idx = [dof_names.index(f"{n}_joint") for n in UR10E_JOINT_NAMES]
    _log(f"arm_idx = {arm_idx}")

    with open("/home/cap2/last/configs/cell_01_ik.yaml") as f:
        ik = yaml.safe_load(f)

    def read_link_pose(path):
        prim = stage.GetPrimAtPath(path)
        mat = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        m = mat.RemoveScaleShear()
        t = m.ExtractTranslation()
        return (float(t[0]), float(t[1]), float(t[2]))

    # For each waypoint, set the targets, run 300 physics steps, then
    # measure the EE link and wrist_3 link world positions.
    for name, wp in ik["waypoints"].items():
        angles = wp["joints_rad"]
        full_pos = art.get_joint_positions()  # current DOF positions
        # set arm + zero gripper (don't disturb gripper for this probe)
        for i, idx in enumerate(arm_idx):
            full_pos[0][idx] = float(angles[i])
        art.set_joint_positions(full_pos)

        # also set the action target so PD doesn't fight the kinematic teleport
        full_target = art.get_joint_positions()
        for i, idx in enumerate(arm_idx):
            full_target[0][idx] = float(angles[i])
        art.set_joint_position_targets(full_target)

        # Settle for 300 steps so PD converges
        for _ in range(300):
            world.step(render=False)

        ee   = read_link_pose("/World/Robot/ee_link")
        w3   = read_link_pose("/World/Robot/wrist_3_link")
        # Also probe the gripper finger-pad inner-finger world pose so
        # we can see where the gripper actually CLOSES around objects.
        left_finger  = read_link_pose("/World/Robot/ee_link/left_inner_finger/Fingertip_01")
        right_finger = read_link_pose("/World/Robot/ee_link/right_inner_finger/Fingertip_01")
        _log(f"[{name}]")
        _log(f"          wrist_3 world      = {tuple(round(v,4) for v in w3)}")
        _log(f"          left_inner_finger  = {tuple(round(v,4) for v in left_finger)}")
        _log(f"          right_inner_finger = {tuple(round(v,4) for v in right_finger)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
