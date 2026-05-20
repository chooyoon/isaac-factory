"""Phase 4A — TaskExecutor.

Runs one PickPlaceTask end-to-end against an existing Isaac Sim world,
populating a CellStateRegistry and returning a TaskResult.

Architectural rules
-------------------

* The executor **wraps** the validated Phase 3M trajectory player and
  the Phase 3N/3O per-tick instrumentation. It does NOT modify them.
  ``cell_authoring.trajectory.TrajectoryPlayer`` is used unchanged.

* The executor accepts a profile override that scales motion-phase
  durations via ``profiles.apply_profile_to_trajectory``. NOMINAL is
  the validated reference and exactly reproduces the
  ``test_cell_01_pick_place_cycle`` cycle.

* The grasp/transport/release strategies in the task definition are
  matched against a small ``_realisation_table`` of supported tuples.
  Only one tuple is implemented today (PrismaticClampGrasp +
  JointSpaceLerpTransport + OpenJawRelease — i.e. the validated
  reference task). The architecture leaves room for future strategy
  combinations: each combination registers an executor handler.

* The executor follows the prepare → execute → validate → reset
  contract specified in Phase 4A task 1.

Output: a fully-populated TaskResult dataclass. The result is the
single source of validation truth — every Phase 3M/N/O/P gate can be
applied to it.
"""

from __future__ import annotations

import enum
import math
import time
from pathlib import Path
from typing import Callable

from ..config import CellConfig, RobotConfig
from ..trajectory import TrajectoryPlayer
from .definitions import (
    GraspStrategy, JointSpaceLerpTransport, OpenJawRelease,
    PickPlaceTask, PrismaticClampGrasp, ReleaseStrategy,
    TaskDefinition, TaskOutcome, TaskResult, TransportStrategy,
)
from .profiles import TrajectoryProfile, apply_profile_to_trajectory, get_profile_spec
from .registry import (
    CellStateRegistry, ContactState, FixtureState, ObjectState, RobotState,
)


# ───────────────────────── tokens ─────────────────────────

ROBOT_MOUNT_PATH = "/World/Robot"
PEG_PATH         = "/World/Parts/Peg_01"
BELT_PATH        = "/World/Machinery/Conveyor_InFeed/Belt"
LEFT_FINGER      = "/World/Robot/ee_link/left_finger"
RIGHT_FINGER     = "/World/Robot/ee_link/right_finger"
WRIST_3_LINK     = "/World/Robot/wrist_3_link"
WORK_FIXTURE     = "/World/Environment/WorkFixture"
FLOOR_TOKEN      = "/World/Environment/Floor"

PHYSICS_DT_S = 1.0 / 60.0

_UR10E_JOINT_NAMES = (
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
)


# ─────────────────── Phase 4B step 6 — reset scoping ───────────────────
#
# Additive: ResetScope.FULL (the default) preserves Phase 4A reset()
# behaviour byte-for-byte. ACQUIRED_ONLY is a new branch used by
# ExecutionSession between nodes of a multi-task job — it skips the
# peg-teleport so objects placed by a prior task stay where they were
# placed. All 32 Phase 4A tests exercise the default FULL path and
# therefore remain regression-stable.

class ResetScope(enum.Enum):
    """Scope of a TaskExecutor.reset() call.

    Cites Phase 4B architecture doc §6 + step-6 brief §6.

    FULL:
        Phase 4A behaviour. Resets arm to home AND teleports the
        authored peg back to its authored pose AND drains the contact
        source AND clears registry contact/metrics. **Default** —
        preserves the validated 32/32 Phase 4A regression suite.

    ACQUIRED_ONLY:
        Phase 4B addition. Resets arm to home, drains the contact
        source, and clears registry contact/metrics. Does **NOT**
        teleport objects; objects placed by a prior task remain at
        their post-placement pose. Used by ExecutionSession between
        nodes of a multi-task job.
    """
    FULL          = "full"
    ACQUIRED_ONLY = "acquired_only"


# ─────────────────────── strategy realisation table ───────────────────────

def _check_realisable(task: PickPlaceTask) -> tuple[bool, str]:
    """True if (grasp, transport, release) matches the validated tuple
    we know how to run today. The table is intentionally a tiny
    whitelist so that adding a new strategy combo is a deliberate
    extension, not an accident."""
    if not isinstance(task.grasp_strategy,     PrismaticClampGrasp):
        return False, f"grasp_strategy {task.grasp_strategy.kind!r} not implemented; only 'prismatic_clamp'"
    if not isinstance(task.transport_strategy, JointSpaceLerpTransport):
        return False, f"transport_strategy {task.transport_strategy.kind!r} not implemented; only 'joint_space_lerp'"
    if not isinstance(task.release_strategy,   OpenJawRelease):
        return False, f"release_strategy {task.release_strategy.kind!r} not implemented; only 'open_jaw'"
    return True, ""


# ─────────────────────── helpers ───────────────────────

def _classify_peg_pair(other_path: str) -> str:
    o = other_path
    if o == LEFT_FINGER  or o.startswith(LEFT_FINGER  + "/"): return "pad_L"
    if o == RIGHT_FINGER or o.startswith(RIGHT_FINGER + "/"): return "pad_R"
    if BELT_PATH in o:        return "belt"
    if FLOOR_TOKEN in o:      return "floor"
    if WORK_FIXTURE in o:     return "fixture"
    return "other"


def _world_translate(stage, path: str):
    from pxr import UsdGeom, Usd
    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        return None
    mat = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    t = mat.ExtractTranslation()
    return (float(t[0]), float(t[1]), float(t[2]))


# ─────────────────────── executor ───────────────────────


class TaskExecutor:
    """One executor per (world, stage, cell_cfg) triple. The same
    executor instance can run many tasks back-to-back (each call to
    ``execute`` produces one TaskResult)."""

    def __init__(self,
                 *,
                 world,
                 stage,
                 cell_cfg: CellConfig,
                 registry: CellStateRegistry | None = None,
                 trajectory_sets: dict[str, list] | None = None) -> None:
        self.world          = world
        self.stage          = stage
        self.cell_cfg       = cell_cfg
        self.registry       = registry or CellStateRegistry()

        # Phase 4B Step 8 / Phase 4 — per-TaskDefinition trajectory
        # selection. Optional mapping ``trajectory_id`` → trajectory
        # (list of TrajectoryWaypoint-like). When ``None`` (Phase 4A
        # default), tasks with no ``trajectory_id`` use the cell
        # config's single trajectory; tasks with a ``trajectory_id``
        # set raise EXECUTOR_ERROR because there is no mapping to
        # look up against. Deterministic lookup only; no planning, no
        # runtime adaptation.
        self._trajectory_sets = trajectory_sets

        # Lazy-created PhysX-backed handles. Constructed once and reused
        # across tasks executed by this instance (the Phase 3P
        # determinism finding mandates this).
        self._art           = None
        self._joint_indices = None
        self._grip_idx      = None
        self._right_grip_idx = None
        self._peg           = None
        self._contact_source = None

        # Belt control.
        self._belt_attr     = None
        self._belt_original = None

        self._initialised   = False

    # ─────────── prepare ───────────
    def prepare(self) -> None:
        """Initialise PhysX-backed handles and pre-populate the registry
        with declared cell objects / fixtures / robots. Idempotent."""
        if self._initialised:
            return
        from isaacsim.core.prims import Articulation, RigidPrim
        from pxr import Gf
        import sys
        # Local import keeps the asset_validator path optional.
        try:
            from asset_validator.adapters.physx_contact_source import PhysXContactSource
        except ImportError:
            from pathlib import Path as _P
            sys.path.insert(0, str(_P(__file__).resolve().parents[5] / "asset_validator"))
            from asset_validator.adapters.physx_contact_source import PhysXContactSource

        self._art = Articulation(prim_paths_expr=ROBOT_MOUNT_PATH)
        try:
            self.world.scene.add(self._art)
        except Exception:
            pass
        self._art.initialize()
        dof = list(self._art.dof_names)
        self._joint_indices = [dof.index(f"{n}_joint") for n in _UR10E_JOINT_NAMES]
        self._grip_idx       = dof.index("finger_joint")       if "finger_joint"       in dof else None
        self._right_grip_idx = dof.index("right_finger_joint") if "right_finger_joint" in dof else None

        self._peg = RigidPrim(prim_paths_expr=PEG_PATH)
        self._peg.initialize()

        self._contact_source = PhysXContactSource(stage=self.stage, physics_dt=PHYSICS_DT_S)

        self._belt_attr = self.stage.GetAttributeAtPath(
            BELT_PATH + ".physxSurfaceVelocity:surfaceVelocity")
        if self._belt_attr and self._belt_attr.IsValid():
            self._belt_original = self._belt_attr.Get()

        # Populate registry with declared cell entities.
        self.registry.register_robot(RobotState(robot_id="UR10e"))
        for part in self.cell_cfg.parts:
            self.registry.register_object(ObjectState(
                object_id=part.name,
                pose_m=tuple(part.translate_world_m),
            ))
        # Cell author currently declares no separate fixture configs,
        # so we register the WorkFixture descriptively.
        self.registry.register_fixture(FixtureState(fixture_id="WorkFixture_01"))

        self._initialised = True

    # ─────────── reset ───────────
    def reset(self, scope: ResetScope = ResetScope.FULL) -> None:
        """Reset the cell to a known state.

        ``scope`` (Phase 4B step-6 additive parameter; **default
        preserves Phase 4A behaviour byte-for-byte**):

        * ``ResetScope.FULL`` (default): Phase 4A reset — world + arm
          + peg + belt + contact-source drain + registry refresh. The
          validated 32/32 Phase 4A test surface exercises this path
          unchanged.
        * ``ResetScope.ACQUIRED_ONLY``: arm + belt + contact-source
          drain + registry contact/metrics clear; **does NOT teleport
          objects**. Used by ExecutionSession between nodes of a
          multi-task job so prior placements survive.
        """
        if scope == ResetScope.FULL:
            self._reset_full()
        elif scope == ResetScope.ACQUIRED_ONLY:
            self._reset_acquired_only()
        else:
            raise ValueError(f"unknown ResetScope: {scope!r}")

    def _reset_full(self) -> None:
        """Phase 4A reset — body verbatim from pre-step-6.

        **This method's body must remain byte-equivalent to the
        original reset() body** to preserve the 32/32 Phase 4A
        regression-test surface.
        """
        import numpy as np
        from pxr import Gf
        if not self._initialised:
            self.prepare()

        self.world.reset()
        self.world.play()
        try:
            self._art.initialize()
        except Exception:
            pass
        if self._belt_attr and self._belt_attr.IsValid() and self._belt_original is not None:
            self._belt_attr.Set(Gf.Vec3f(*[float(c) for c in self._belt_original]))

        # Arm → home.
        home = dict(self.cell_cfg.robot.home_pose_rad)
        full = self._art.get_joint_positions()
        for i, name in enumerate(_UR10E_JOINT_NAMES):
            full[0][self._joint_indices[i]] = float(home[name])
        self._art.set_joint_positions(full)
        self._art.set_joint_position_targets(full)

        # Peg → authored pose.
        authored = self.cell_cfg.parts[0].translate_world_m
        self._peg.set_world_poses(
            positions=np.array([[authored[0], authored[1], authored[2]]], dtype=np.float32),
            orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
        )
        self._peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
        self._peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))

        for _ in range(10):
            self.world.step(render=False)
        self._peg.set_world_poses(
            positions=np.array([[authored[0], authored[1], authored[2]]], dtype=np.float32),
            orientations=np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32),
        )
        self._peg.set_linear_velocities(np.zeros((1, 3), dtype=np.float32))
        self._peg.set_angular_velocities(np.zeros((1, 3), dtype=np.float32))
        self._contact_source.query_contacts()

        # Refresh registry.
        self.registry.update_object_pose(self.cell_cfg.parts[0].name, tuple(authored), 0.0)
        self.registry.contact = ContactState()
        self.registry.metrics.clear()

    def _reset_acquired_only(self) -> None:
        """Phase 4B Step 8 / Phase 4 — selective authoritative
        persistence only.

        Cites D-CONT-3 (boundary PhysX-quiescence) and D-CONT-4
        (selective authoritative persistence semantics).

        Preserved (authoritative continuity, D-CONT-1 + D-CONT-4):
          * canonical object pose — the PhysX scene is left untouched;
            objects placed by a prior task remain at their post-
            placement pose. No ``set_world_poses`` is called.
          * fixture occupancy in the registry — untouched here;
            session Phase-G is the sole occupancy authority (D-CONT-5).
          * articulation joint positions in PhysX — left as the prior
            task's last drive target settled them. No teleport.

        Drained / zeroed (non-stepping operations on incidental state):
          * contact-source query queue — drains stale contact events
            from the C++ buffer so the next cycle starts with a clean
            event stream. Non-stepping.
          * ``registry.contact`` — in-memory; replaced with a fresh
            ``ContactState()`` instance. D-CONT-2 forbidden contact
            flags are zeroed at boundary entry (D-CONT-4).
          * ``registry.metrics`` — in-memory diagnostic scratchpad.

        Restored to authored value:
          * belt surface velocity — config-level USD attribute write,
            non-stepping. Without restoration the belt would remain
            in N1's "halted" state and contaminate N2's runtime.

        Forbidden (per D-CONT-3 and D-CONT-4):
          * ``world.step(...)``, ``world.play()``+step, ``kit.update()``
            — would advance the simulator, violating boundary
            quiescence (D-CONT-3).
          * ``self._art.initialize()`` — re-init can perturb
            articulation stabilization state. Originally added "to be
            safe"; Phase 4 removes it (Phase 1 hazard H4).
          * ``set_joint_positions`` — direct joint teleport (D-CONT-4
            forbidden list).
          * ``set_world_poses`` — direct object teleport.
          * ``set_linear_velocities`` — direct velocity write.
          * ``set_joint_position_targets`` — redundant; the next
            cycle's first physics tick writes fresh drive targets,
            and any "arm-home" target here would be overwritten on
            tick 0. Removing it reduces the surface where
            non-deterministic re-init effects could enter.

        Residual incidental state (joint velocities, contact manifold
        warm-starts, articulation sleep/wake flags) IS left in PhysX
        — this state is D-CONT-2 forbidden as a continuity input but
        cannot be "wiped" without a teleport. Orchestration treats it
        as forbidden via the contract; the next cycle's PD control
        dissipates residual velocity within the first few ticks.
        """
        from pxr import Gf
        if not self._initialised:
            self.prepare()

        # Belt back to authored speed — config-level USD attribute
        # write, non-stepping (D-CONT-3 compliant). Without this the
        # belt remains in the halted state left by N1's belt_halt_step
        # command and contaminates N2's runtime.
        if self._belt_attr and self._belt_attr.IsValid() and self._belt_original is not None:
            self._belt_attr.Set(Gf.Vec3f(*[float(c) for c in self._belt_original]))

        # Drain transient contact state. ``query_contacts`` flushes the
        # C++ event buffer (non-stepping); registry mutations are
        # in-memory. None of these advances the simulator.
        self._contact_source.query_contacts()
        self.registry.contact = ContactState()
        self.registry.metrics.clear()

    # ─────────── execute ───────────
    def execute(self,
                task: TaskDefinition,
                *,
                profile: TrajectoryProfile = TrajectoryProfile.NOMINAL,
                seed: int = 20260519,
                reset_scope: ResetScope | None = None,
                step_observer: Callable[[int, dict], None] | None = None,
                render: bool = False) -> TaskResult:
        """Run one task end-to-end. Returns a fully-populated TaskResult.

        prepare → reset → run-cycle → validate → return result.

        ``reset_scope`` (optional): scope of the pre-cycle reset.
        Phase 4B Step 8 / Phase 4 addition.

          * ``None`` (default) — Phase 4A behaviour: caller did not
            specify a scope; the executor performs a ``FULL`` reset.
            Preserves the 32/32 Phase 4A regression surface byte-for-
            byte. Phase 4A tests do not set ``reset_scope``.
          * ``ResetScope.FULL`` — explicit FULL reset. Identical to
            ``None`` in current behaviour; the explicit form is what
            :class:`cell_authoring.orchestration.session.ExecutionSession`
            passes for the first node of a job.
          * ``ResetScope.ACQUIRED_ONLY`` — selective authoritative
            persistence (D-CONT-4). Used by ExecutionSession between
            nodes so prior placements survive. The reset performs only
            non-stepping operations; no teleports; no implicit world
            stepping.

        ``step_observer`` (optional): per-physics-step callback invoked
        with ``(step_index, observer_state_dict)``. observer_state_dict
        contains the live registry view + the current waypoint name +
        cumulative cycle metrics. Use for HUD overlays, live telemetry
        feeds, or pacing (e.g. ``kit.update()`` for an interactive
        streaming session). The callback is None by default, so the
        validated determinism path (Phase 4A
        TestProfilesPreserveDeterminismOnNominal) is unaffected.

        ``render`` (optional): if True, ``world.step(render=True)`` is
        called each physics tick so the renderer produces frames (for
        live WebRTC streaming or video capture). Defaults to False so
        validation/regression runs stay fast and head-less-equivalent.
        Rendering does NOT alter PhysX state — the determinism property
        is preserved either way.
        """
        if not isinstance(task, PickPlaceTask):
            return TaskResult(
                task_id=task.task_id, profile_id=profile.value,
                outcome=TaskOutcome.EXECUTOR_ERROR,
                outcome_detail=f"only PickPlaceTask is implemented today; got {type(task).__name__}",
                seed=seed,
            )
        ok, why = _check_realisable(task)
        if not ok:
            return TaskResult(
                task_id=task.task_id, profile_id=profile.value,
                outcome=TaskOutcome.EXECUTOR_ERROR, outcome_detail=why, seed=seed,
            )

        self.prepare()
        # Phase 4B Step 8 / Phase 4 — reset_scope plumbing.
        # When the caller does not specify a scope, fall back to
        # ``ResetScope.FULL`` (Phase 4A default; preserves 32/32
        # regression byte-for-byte). When the caller specifies
        # ``ACQUIRED_ONLY``, the session is asserting that retained
        # state from the prior tick must persist (D-CONT-4).
        if reset_scope is None:
            self.reset()  # Phase 4A default — FULL via reset()'s own default
        else:
            self.reset(scope=reset_scope)

        # Apply profile (NOMINAL is a pass-through).
        profiled_robot_cfg = apply_profile_to_trajectory(self.cell_cfg.robot, profile)

        # Phase 4B Step 8 / Phase 4 — per-TaskDefinition trajectory
        # selection (minimal implementation). When ``task.trajectory_id``
        # is set and a matching entry exists in ``self._trajectory_sets``,
        # swap the trajectory on ``profiled_robot_cfg``. Phase 4A's
        # default path (no ``trajectory_id`` on the task) uses
        # ``cell_cfg.robot.trajectory`` unchanged.
        trajectory_id = getattr(task, "trajectory_id", None)
        if trajectory_id is not None:
            if self._trajectory_sets is None or trajectory_id not in self._trajectory_sets:
                return TaskResult(
                    task_id=task.task_id, profile_id=profile.value,
                    outcome=TaskOutcome.EXECUTOR_ERROR,
                    outcome_detail=(
                        f"unknown trajectory_id {trajectory_id!r}; "
                        f"executor was constructed with "
                        f"{sorted((self._trajectory_sets or {}).keys())!r}"
                    ),
                    seed=seed,
                )
            from dataclasses import replace as _replace
            profiled_robot_cfg = _replace(
                profiled_robot_cfg,
                trajectory=list(self._trajectory_sets[trajectory_id]),
            )

        return self._run_cycle(task, profiled_robot_cfg, profile, seed,
                                step_observer=step_observer, render=render)

    # ─────────── validate (per-result classifier) ───────────
    @staticmethod
    def validate(result: TaskResult,
                 *,
                 placement_tolerance_xy_m: float | None = None) -> TaskResult:
        """Re-classify a TaskResult against the standard gate set.

        Called automatically at end of execute(); also exposed so that
        a test can re-validate a stored result without re-running.
        """
        from .profiles import TrajectoryProfile, get_profile_spec
        spec = get_profile_spec(TrajectoryProfile(result.profile_id))

        # Gates (Phase 3M endpoint first, then 3N temporal, then 3O motion).
        if result.grasp_acquired_step is None:
            result.outcome = TaskOutcome.GRASP_NEVER_ACQUIRED
            result.outcome_detail = (
                f"pads never both made sustained contact — "
                f"peg final z = {result.peg_xyz_final[2] if result.peg_xyz_final else 'n/a':.4f}"
            )
            return result
        if result.grasp_lost_in_transport_step is not None:
            result.outcome = TaskOutcome.GRASP_LOST_IN_TRANSPORT
            result.outcome_detail = (
                f"pads broke contact at step {result.grasp_lost_in_transport_step} "
                f"before release_start_step={result.release_start_step}"
            )
            return result
        fb = result.floor_or_belt_first_post_close_step
        if fb is not None and result.lift_end_step <= fb < result.release_start_step:
            result.outcome = TaskOutcome.FLOOR_OR_BELT_TRANSPORT_CONTACT
            result.outcome_detail = (
                f"peg touched floor/belt at step {fb} during transport "
                f"({result.lift_end_step} ≤ step < {result.release_start_step})"
            )
            return result
        # Placement check — caller can override the tolerance, otherwise
        # default to the Phase 3M gate (50 mm).
        TOL = placement_tolerance_xy_m or 0.050
        if result.peg_xyz_final is not None:
            dx = abs(result.peg_xyz_final[0] - 0.65)
            dy = abs(result.peg_xyz_final[1] - 0.00)
            if dx > TOL or dy > TOL:
                result.outcome = TaskOutcome.PLACEMENT_MISS
                result.outcome_detail = (
                    f"final XY=({result.peg_xyz_final[0]:+.4f},{result.peg_xyz_final[1]:+.4f}) "
                    f"target=(+0.650,+0.000) tol±{TOL*1000:.0f}mm "
                    f"Δ=({dx*1000:+.1f},{dy*1000:+.1f})mm"
                )
                return result
        if result.wrist_3_max_z_m > spec.wrist_3_max_z_m:
            result.outcome = TaskOutcome.WRIST_3_OUT_OF_BOUNDS
            result.outcome_detail = (
                f"wrist_3 max z {result.wrist_3_max_z_m:.3f}m > {spec.wrist_3_max_z_m:.2f}m"
            )
            return result
        if result.peg_max_z_m > spec.peg_max_z_m:
            result.outcome = TaskOutcome.PEG_OUT_OF_BOUNDS
            result.outcome_detail = (
                f"peg max z {result.peg_max_z_m:.3f}m > {spec.peg_max_z_m:.2f}m"
            )
            return result
        if result.joint_vel_peak_rad_s > spec.joint_vel_limit_rad_s:
            result.outcome = TaskOutcome.MOTION_QUALITY_VIOLATION
            result.outcome_detail = (
                f"joint vel peak {result.joint_vel_peak_rad_s:.3f} rad/s > "
                f"{spec.joint_vel_limit_rad_s:.2f} rad/s ({spec.name} profile)"
            )
            return result
        if result.joint_accel_peak_rad_s2 > spec.joint_accel_limit_rad_s2:
            result.outcome = TaskOutcome.MOTION_QUALITY_VIOLATION
            result.outcome_detail = (
                f"joint accel peak {result.joint_accel_peak_rad_s2:.1f} rad/s² > "
                f"{spec.joint_accel_limit_rad_s2:.1f} rad/s² ({spec.name})"
            )
            return result
        if result.ee_speed_peak_mps > spec.ee_speed_limit_mps:
            result.outcome = TaskOutcome.MOTION_QUALITY_VIOLATION
            result.outcome_detail = (
                f"ee speed peak {result.ee_speed_peak_mps:.3f} m/s > "
                f"{spec.ee_speed_limit_mps:.2f} m/s ({spec.name})"
            )
            return result
        if result.cartesian_path_length_m > spec.cartesian_path_limit_m:
            result.outcome = TaskOutcome.MOTION_QUALITY_VIOLATION
            result.outcome_detail = (
                f"cartesian path {result.cartesian_path_length_m:.3f} m > "
                f"{spec.cartesian_path_limit_m:.2f} m ({spec.name})"
            )
            return result
        result.outcome = TaskOutcome.PASS
        return result

    # ─────────── core cycle loop ───────────
    def _run_cycle(self, task: PickPlaceTask, robot_cfg: RobotConfig,
                   profile: TrajectoryProfile, seed: int,
                   *,
                   step_observer: Callable[[int, dict], None] | None = None,
                   render: bool = False) -> TaskResult:
        import numpy as np
        from pxr import Gf, UsdGeom, Usd
        _DEG2RAD = math.pi / 180.0
        t_start = time.time()

        # Trajectory timing landmarks (derived from THIS profile's cfg).
        waypoints  = list(robot_cfg.trajectory)
        cumulative = []; t_c = 0.0
        for wp in waypoints:
            t_c += wp.duration_s
            cumulative.append(t_c)
        name_to_end_t = {wp.name: cumulative[i] for i, wp in enumerate(waypoints)}
        grasp_end_s        = name_to_end_t.get("grasp",        2.0)
        grasp_close_end_s  = name_to_end_t.get("grasp_close",  3.8)
        lift_end_s         = name_to_end_t.get("lift",         5.3)
        place_end_s        = name_to_end_t.get("place",        11.3)
        release_end_s      = name_to_end_t.get("release",      11.8)
        total_s            = cumulative[-1]

        belt_halt_step     = int(round(grasp_end_s     / PHYSICS_DT_S))
        belt_resume_step   = int(round(lift_end_s      / PHYSICS_DT_S))
        grasp_close_step   = int(round(grasp_close_end_s / PHYSICS_DT_S))
        lift_end_step      = int(round(lift_end_s      / PHYSICS_DT_S))
        place_end_step     = int(round(place_end_s     / PHYSICS_DT_S))
        release_end_step   = int(round(release_end_s   / PHYSICS_DT_S))
        release_start_step = place_end_step
        n_steps            = int(round(total_s         / PHYSICS_DT_S)) + 60

        self.registry.start_task(task.task_id, started_at_step=0)

        # Phase 4B Step 8 / Phase 2 — replay-authoritative peg pose probe
        # at step 0, BEFORE any command. Enters the per-task fingerprint
        # under D-CONT-1; used by inter-node continuity verification
        # (post_N1.peg_xyz_final ≈ pre_N2.peg_xyz_initial).
        _peg_pos_initial_arr, _ = self._peg.get_world_poses()
        peg_xyz_initial: tuple[float, float, float] = (
            float(_peg_pos_initial_arr[0][0]),
            float(_peg_pos_initial_arr[0][1]),
            float(_peg_pos_initial_arr[0][2]),
        )

        # Phase 4B Step 8 / Phase 2 — pick-side lift-off threshold.
        # Active only when the task picks from a fixture (Phase 5+
        # scope). For Phase 4A from-belt sources, stays None and
        # pick_lift_off_step remains None throughout the cycle.
        pick_source_z_threshold_m: float | None = None
        if (hasattr(task.pick_source, "fixture_id")
                and getattr(task.pick_source, "source_kind", None)
                in ("fixture", "from_fixture")):
            pick_source_z_threshold_m = (
                float(task.pick_source.world_pose_m[2]) + 0.02
            )

        player = TrajectoryPlayer(stage=self.stage, robot_cfg=robot_cfg)
        player.reset()

        # Per-tick aggregates.
        peg_max_z = -1e9; peg_max_z_step = -1
        peg_min_z = 1e9
        wmax = -1e9; wmax_step = -1
        wmin = 1e9
        wrist_reach_peak = 0.0
        j_vel_peak = [0.0] * 6
        j_accel_peak = [0.0] * 6
        ee_speed_peak = 0.0; ee_speed_peak_step = -1
        ee_accel_peak = 0.0
        cart_path = 0.0
        pad_pen_min_in_transport = 1e9
        pad_pen_max_in_transport = 0.0
        grasp_acquired_step = None
        grasp_lost_in_transport_step = None
        last_left_contact_step = None
        last_right_contact_step = None
        floor_or_belt_first_post_close = None
        fixture_first_post_close = None
        peg_xyz_final = None
        # Phase 4B Step 8 / Phase 2 — authoritative-evidence trackers
        # (D-CONT-5 inputs).
        pick_lift_off_step: int | None = None
        place_landing_step: int | None = None

        SUSTAINED = 30
        BREAK_THR = int(round(0.10 / PHYSICS_DT_S))
        consec = 0; loss_consec = 0

        prev_wrist = None
        prev_jvel  = None
        prev_ee_v  = None

        for step_i in range(n_steps):
            self.registry.task.step = step_i

            # Joint-target write (mirrors the validated test pattern).
            full_target = np.array(self._art.get_joint_positions(), dtype=np.float32).copy()
            for i, name in enumerate(_UR10E_JOINT_NAMES):
                attr_path = (
                    f"{robot_cfg.mount_prim_path}/joints/{name}_joint"
                    f".drive:angular:physics:targetPosition"
                )
                attr = self.stage.GetAttributeAtPath(attr_path)
                if attr and attr.IsValid():
                    full_target[0, self._joint_indices[i]] = float(attr.Get()) * _DEG2RAD
            if self._grip_idx is not None and player._gripper_attr_path is not None:
                gattr = self.stage.GetAttributeAtPath(player._gripper_attr_path)
                if gattr and gattr.IsValid():
                    grip_scale = _DEG2RAD if getattr(player, "_gripper_drive_is_angular", True) else 1.0
                    tgt = float(gattr.Get()) * grip_scale
                    full_target[0, self._grip_idx] = tgt
                    if self._right_grip_idx is not None and not getattr(player, "_gripper_drive_is_angular", True):
                        full_target[0, self._right_grip_idx] = -tgt
            self._art.set_joint_position_targets(full_target)

            # Belt halt + resume (verbatim from validated cycle test).
            if step_i == belt_halt_step and self._belt_attr and self._belt_attr.IsValid():
                self._belt_attr.Set(Gf.Vec3f(0.0, 0.0, 0.0))
            elif step_i == belt_resume_step and self._belt_original is not None:
                self._belt_attr.Set(Gf.Vec3f(*[float(c) for c in self._belt_original]))

            self.world.step(render=render)
            player.advance(PHYSICS_DT_S)

            # Probes.
            peg_pos_arr, _ = self._peg.get_world_poses()
            peg_xyz = (float(peg_pos_arr[0][0]), float(peg_pos_arr[0][1]), float(peg_pos_arr[0][2]))
            wrist_xyz = _world_translate(self.stage, WRIST_3_LINK)

            if peg_xyz[2] > peg_max_z:
                peg_max_z = peg_xyz[2]; peg_max_z_step = step_i
            if peg_xyz[2] < peg_min_z:
                peg_min_z = peg_xyz[2]
            if wrist_xyz is not None:
                if wrist_xyz[2] > wmax:
                    wmax = wrist_xyz[2]; wmax_step = step_i
                if wrist_xyz[2] < wmin:
                    wmin = wrist_xyz[2]
                rh = math.sqrt(wrist_xyz[0]**2 + wrist_xyz[1]**2)
                if rh > wrist_reach_peak:
                    wrist_reach_peak = rh

            jv_arr = self._art.get_joint_velocities()
            jv = [float(jv_arr[0][self._joint_indices[i]]) for i in range(6)]
            for i in range(6):
                if abs(jv[i]) > j_vel_peak[i]: j_vel_peak[i] = abs(jv[i])
            if prev_jvel is not None:
                for i in range(6):
                    a = abs((jv[i] - prev_jvel[i]) / PHYSICS_DT_S)
                    if a > j_accel_peak[i]: j_accel_peak[i] = a
            prev_jvel = jv

            if prev_wrist is not None and wrist_xyz is not None:
                dx = wrist_xyz[0] - prev_wrist[0]
                dy = wrist_xyz[1] - prev_wrist[1]
                dz = wrist_xyz[2] - prev_wrist[2]
                seg = math.sqrt(dx*dx + dy*dy + dz*dz)
                cart_path += seg
                sp = seg / PHYSICS_DT_S
                if sp > ee_speed_peak:
                    ee_speed_peak = sp; ee_speed_peak_step = step_i
                if prev_ee_v is not None:
                    ax = (dx/PHYSICS_DT_S - prev_ee_v[0]) / PHYSICS_DT_S
                    ay = (dy/PHYSICS_DT_S - prev_ee_v[1]) / PHYSICS_DT_S
                    az = (dz/PHYSICS_DT_S - prev_ee_v[2]) / PHYSICS_DT_S
                    am = math.sqrt(ax*ax + ay*ay + az*az)
                    if am > ee_accel_peak:
                        ee_accel_peak = am
                prev_ee_v = (dx/PHYSICS_DT_S, dy/PHYSICS_DT_S, dz/PHYSICS_DT_S)
            if wrist_xyz is not None:
                prev_wrist = wrist_xyz

            # Contacts.
            contacts = self._contact_source.query_contacts()
            pad_L = pad_R = floor_c = belt_c = fixture_c = False
            max_pad_pen_mm = 0.0
            for c in contacts:
                a, b = c.prim_a, c.prim_b
                if PEG_PATH in a:    other = b
                elif PEG_PATH in b:  other = a
                else:                continue
                cls = _classify_peg_pair(other)
                if cls == "pad_L":  pad_L = True;  max_pad_pen_mm = max(max_pad_pen_mm, float(c.penetration_depth) * 1000.0)
                if cls == "pad_R":  pad_R = True;  max_pad_pen_mm = max(max_pad_pen_mm, float(c.penetration_depth) * 1000.0)
                if cls == "floor":  floor_c   = True
                if cls == "belt":   belt_c    = True
                if cls == "fixture": fixture_c = True

            if pad_L: last_left_contact_step = step_i
            if pad_R: last_right_contact_step = step_i
            if pad_L and pad_R:
                consec += 1
                if consec >= SUSTAINED and grasp_acquired_step is None:
                    grasp_acquired_step = step_i - SUSTAINED + 1
            else:
                consec = 0
            if grasp_acquired_step is not None and step_i < release_start_step and step_i > grasp_acquired_step:
                if not pad_L and not pad_R:
                    loss_consec += 1
                    if loss_consec >= BREAK_THR and grasp_lost_in_transport_step is None:
                        grasp_lost_in_transport_step = step_i - BREAK_THR + 1
                else:
                    loss_consec = 0
            if step_i >= grasp_close_step:
                if floor_or_belt_first_post_close is None and (floor_c or belt_c):
                    floor_or_belt_first_post_close = step_i
                if fixture_first_post_close is None and fixture_c:
                    fixture_first_post_close = step_i

            # Phase 4B Step 8 / Phase 2 — pick-lift-off detection.
            # Only active for tasks that pick from a fixture (D-CONT-5
            # input for the session's mark_fixture_empty commit on the
            # pick side). For from-belt sources, stays None.
            if (pick_lift_off_step is None
                    and pick_source_z_threshold_m is not None
                    and step_i >= grasp_close_step
                    and pad_L and pad_R
                    and peg_xyz[2] > pick_source_z_threshold_m):
                pick_lift_off_step = step_i

            # Phase 4B Step 8 / Phase 2 — place-landing detection.
            # First step at or after release_start_step where the peg
            # has re-acquired contact with a fixture AND both pads
            # have broken contact. D-CONT-5 input for the session's
            # mark_fixture_occupied commit on the place side.
            if (place_landing_step is None
                    and step_i >= release_start_step
                    and fixture_c
                    and not pad_L and not pad_R):
                place_landing_step = step_i
            if lift_end_step <= step_i < place_end_step and (pad_L or pad_R):
                if max_pad_pen_mm < pad_pen_min_in_transport:
                    pad_pen_min_in_transport = max_pad_pen_mm
                if max_pad_pen_mm > pad_pen_max_in_transport:
                    pad_pen_max_in_transport = max_pad_pen_mm

            # Stream updates into the registry (last-tick view).
            self.registry.update_contact_state(ContactState(
                pad_L_contact=pad_L, pad_R_contact=pad_R,
                floor_contact=floor_c, belt_contact=belt_c, fixture_contact=fixture_c,
                pad_pen_max_mm=max_pad_pen_mm,
            ))
            self.registry.update_object_pose(task.pick_source.object_id, peg_xyz, 0.0)
            if wrist_xyz is not None:
                self.registry.update_robot_pose(
                    "UR10e",
                    joint_velocities_rad_s=tuple(jv),
                    wrist_3_xyz=wrist_xyz,
                )

            if step_i == n_steps - 1:
                peg_xyz_final = peg_xyz

            # Optional per-step observer (live streaming HUD, replay
            # tracing, etc.). The observer state is a lightweight snapshot
            # — no extra contact queries or pose reads.
            if step_observer is not None:
                # Derive current trajectory waypoint name from the player.
                phase_name = "?"
                try:
                    phase, _ = player._select_phase(player.current_time_s)
                    idx = player.current_waypoint_index
                    if 0 <= idx < len(waypoints):
                        phase_name = waypoints[idx].name
                except Exception:
                    pass
                step_observer(step_i, {
                    "task_id":         task.task_id,
                    "profile":         profile.value,
                    "n_steps":         n_steps,
                    "phase_name":      phase_name,
                    "peg_xyz":         peg_xyz,
                    "wrist_3_xyz":     wrist_xyz,
                    "wrist_3_z":       wrist_xyz[2] if wrist_xyz else None,
                    "pad_L":           pad_L,
                    "pad_R":           pad_R,
                    "gripper_state":   "close" if (pad_L or pad_R) else "open",
                    "grasp_acquired":  grasp_acquired_step is not None,
                    "grasp_acquired_step": grasp_acquired_step,
                    "fixture_contact": fixture_c,
                    "cart_path_so_far_m": cart_path,
                })

        if pad_pen_min_in_transport >= 1e9:
            pad_pen_min_in_transport = 0.0

        # Phase 4B Step 8 / Phase 2 — placement evidence emission.
        # The executor no longer mutates fixture occupancy (D-CONT-5);
        # it emits the objective placement offset and lets
        # ExecutionSession commit the occupancy transition in Phase G,
        # conditioned on the validator's PASS verdict (D-CONT-5,
        # D-CONT-5a).
        placement_offset_xy_m: tuple[float, float] | None = None
        if peg_xyz_final is not None:
            dx_signed = peg_xyz_final[0] - task.place_target.world_pose_m[0]
            dy_signed = peg_xyz_final[1] - task.place_target.world_pose_m[1]
            placement_offset_xy_m = (dx_signed, dy_signed)

        self.registry.set_task_phase("validating")

        result = TaskResult(
            task_id=task.task_id, profile_id=profile.value,
            outcome=TaskOutcome.PASS,
            peg_xyz_initial=peg_xyz_initial,
            peg_xyz_final=peg_xyz_final,
            placement_offset_xy_m=placement_offset_xy_m,
            pick_lift_off_step=pick_lift_off_step,
            place_landing_step=place_landing_step,
            peg_max_z_m=peg_max_z, peg_min_z_m=peg_min_z,
            grasp_acquired_step=grasp_acquired_step,
            grasp_lost_in_transport_step=grasp_lost_in_transport_step,
            last_left_pad_contact_step=last_left_contact_step,
            last_right_pad_contact_step=last_right_contact_step,
            floor_or_belt_first_post_close_step=floor_or_belt_first_post_close,
            fixture_first_post_close_step=fixture_first_post_close,
            pad_pen_min_during_transport_mm=pad_pen_min_in_transport,
            pad_pen_max_during_transport_mm=pad_pen_max_in_transport,
            wrist_3_max_z_m=wmax, wrist_3_min_z_m=wmin,
            wrist_reach_horizontal_peak_m=wrist_reach_peak,
            joint_vel_peak_rad_s=max(j_vel_peak),
            joint_vel_peak_per_joint_rad_s=tuple(j_vel_peak),
            joint_accel_peak_rad_s2=max(j_accel_peak),
            ee_speed_peak_mps=ee_speed_peak, ee_accel_peak_m_s2=ee_accel_peak,
            cartesian_path_length_m=cart_path,
            grasp_close_step=grasp_close_step,
            lift_end_step=lift_end_step,
            place_end_step=place_end_step,
            release_start_step=release_start_step,
            release_end_step=release_end_step,
            n_steps=n_steps,
            seed=seed,
            wall_clock_s=round(time.time() - t_start, 3),
            perturbation={},
            registry_snapshot=self.registry.snapshot(),
        )

        result = self.validate(result, placement_tolerance_xy_m=task.place_target.placement_tolerance_xy_m)
        self.registry.set_task_phase("done")
        return result

    # ─────────── teardown ───────────
    def close(self) -> None:
        if self._contact_source is not None:
            try:
                self._contact_source.close()
            except Exception:
                pass
        self._contact_source = None
        self._initialised = False
