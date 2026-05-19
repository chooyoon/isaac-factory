"""Check whether set_joint_position_targets actually moves the robot."""

from __future__ import annotations

import os
import sys
from pathlib import Path

LOG = Path("/home/cap2/last/logs/diag_robot_motion.log")


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
    import omni.usd
    from pxr import UsdGeom, Usd
    from isaacsim.core.api import World
    from isaacsim.core.prims import Articulation

    ctx = omni.usd.get_context()
    ctx.open_stage("/home/cap2/last/assets/cells/cell_01.usda")
    stage = ctx.get_stage()

    world = World(physics_dt=1.0/60.0, rendering_dt=1.0/60.0)
    world.reset()
    world.play()

    art = Articulation(prim_paths_expr="/World/Robot/root_joint")
    art.initialize()
    _log(f"DOFs: {list(art.dof_names)}")

    JOINT_NAMES = ("shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3")
    arm_idx = [list(art.dof_names).index(f"{n}_joint") for n in JOINT_NAMES]

    # Home pose (approach_pick angles)
    home = [0.294662, -2.264833, -1.890586, -3.699, -1.569941, 1.865738]
    # Lift pose
    lift = [0.294415, -2.126223, -1.879776, -3.84829, -1.571156, 1.865025]

    def read_w3():
        m = UsdGeom.Xformable(stage.GetPrimAtPath("/World/Robot/wrist_3_link")) \
            .ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        t = m.RemoveScaleShear().ExtractTranslation()
        return float(t[0]), float(t[1]), float(t[2])

    # Set targets to LIFT pose. Run 60 steps. Should converge.
    full = art.get_joint_positions()
    _log(f"initial DOF positions: {full[0].tolist()}")
    _log(f"initial wrist_3: {read_w3()}")
    for i, idx in enumerate(arm_idx):
        full[0][idx] = float(lift[i])
    art.set_joint_position_targets(full)

    for step_i in range(120):
        world.step(render=False)
        if step_i in (0, 30, 60, 119):
            jp = art.get_joint_positions()
            _log(f"step {step_i}: shoulder_lift = {jp[0][arm_idx[1]]:.4f}  wrist_3 = {read_w3()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
