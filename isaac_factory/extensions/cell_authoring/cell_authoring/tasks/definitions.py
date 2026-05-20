"""Phase 4A — task definitions, strategies, and result objects.

Composable building blocks for manipulation tasks. Each concrete task
(currently only ``PickPlaceTask``) is a plain dataclass describing:

  pick_source        — where the manipulable object starts (e.g. on a
                       conveyor, in a tray slot, free in space)
  place_target       — where the object should end up
  grasp_strategy     — how to acquire the object (prismatic clamp,
                       suction, two-finger pinch, …)
  transport_strategy — how to move from pick to place (joint-space
                       LERP, Cartesian-linear, RMPflow, …)
  release_strategy   — how to put the object down (open jaw, gentle
                       deceleration, vacuum break, …)

These are *descriptions* only. The executor (``TaskExecutor``) is what
turns a task description into a sequence of TrajectoryPlayer
waypoints + drive commands. Today the executor only knows how to
realise the strategy bundle that matches the validated Phase 3M cycle;
adding a new strategy is a matter of writing a new executor handler.

A ``TaskResult`` carries the full outcome from one execution and is the
unit of validation: temporal-grasp-integrity tests, motion-quality
tests, and robustness statistics all read from this same object.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


# ────────────────────────── source / target ──────────────────────────


@dataclass(frozen=True)
class PickSource:
    """Where the manipulable object starts.

    The base class is intentionally minimal — concrete cell builders
    can subclass for richer source descriptions (conveyor lane index,
    tray-slot id, vision-pose ID), but a plain world-pose source is
    enough for the validated reference task.
    """
    object_id:           str
    world_pose_m:        tuple[float, float, float]
    yaw_rad:             float = 0.0
    source_kind:         str   = "static"   # "static" | "conveyor" | "tray_slot"

    # Optional, source-kind-specific metadata. Free-form to keep the
    # dataclass open for cell-specific extensions (e.g. conveyor speed,
    # tray index) without forcing every callsite to subclass.
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlaceTarget:
    """Where the object should end up after the task."""
    fixture_id:          str
    world_pose_m:        tuple[float, float, float]
    yaw_rad:             float = 0.0
    placement_tolerance_xy_m: float = 0.05   # default 50 mm (Phase 3M gate)
    target_kind:         str   = "fixture_top"
    metadata: dict[str, Any] = field(default_factory=dict)


# ────────────────────────── strategies ──────────────────────────


@dataclass(frozen=True)
class GraspStrategy:
    """Base class. Concrete strategies parametrize HOW the grasp closes.

    The current cell has a parallel prismatic-jaw gripper; future
    extensions might include suction or angular pinch — those would
    be new subclasses with their own executor handlers.
    """
    kind: str  # "prismatic_clamp" | "angular_pinch" | "suction"


@dataclass(frozen=True)
class PrismaticClampGrasp(GraspStrategy):
    """The Phase 3M validated grasp — parallel jaws clamp on peg sides."""
    kind: str  = "prismatic_clamp"
    open_position_m:    float = 0.000
    close_position_m:   float = -0.030
    drive_stiffness:    float = 1.0e5
    drive_damping:      float = 1.0e3


@dataclass(frozen=True)
class TransportStrategy:
    """Base class. How the EE moves from pick to place."""
    kind: str    # "joint_space_lerp" | "cartesian_linear" | "rmpflow"


@dataclass(frozen=True)
class JointSpaceLerpTransport(TransportStrategy):
    """The Phase 3M validated transport — joint-space linear interpolation
    between baked IK waypoints, with 2π unwrap to keep adjacent
    waypoints on a continuous joint manifold."""
    kind: str = "joint_space_lerp"
    waypoint_source: str = "configs/cell_01.yaml"     # YAML path or in-config name
    profile_id:      str = "nominal"                  # see TrajectoryProfile


@dataclass(frozen=True)
class ReleaseStrategy:
    """Base class. How the object is set down."""
    kind: str    # "open_jaw" | "vacuum_break" | "soft_deceleration"


@dataclass(frozen=True)
class OpenJawRelease(ReleaseStrategy):
    """The Phase 3M validated release — gripper opens at the place pose."""
    kind: str = "open_jaw"
    open_dwell_s: float = 0.5    # time held open before retract


# ────────────────────────── task ──────────────────────────


@dataclass(frozen=True)
class TaskDefinition:
    """Abstract base. Concrete tasks subclass.

    A TaskDefinition is *purely descriptive*. The executor reads it,
    plans the realisation (today: lookup-the-baked-IK-waypoint-list),
    and runs the trajectory.
    """
    task_id:    str
    task_kind:  str


@dataclass(frozen=True)
class PickPlaceTask(TaskDefinition):
    """A pick-and-place task description.

    Multi-object: ``additional_objects`` lists other manipulable objects
    in the scene that should be tracked (poses, contacts) but not
    grasped by this task. The validated reference cell has none; the
    field exists so that the architecture is multi-object-ready (Phase
    4A task 4) without requiring a full planner.
    """
    task_kind: str = "pick_place"

    pick_source:        PickSource = None        # type: ignore[assignment]
    place_target:       PlaceTarget = None       # type: ignore[assignment]
    grasp_strategy:     GraspStrategy = None     # type: ignore[assignment]
    transport_strategy: TransportStrategy = None # type: ignore[assignment]
    release_strategy:   ReleaseStrategy = None   # type: ignore[assignment]

    # Multi-object readiness (Phase 4A task 4): the cell may contain
    # objects this task does NOT manipulate. Their poses and contact
    # state are still recorded by the executor for the registry.
    additional_object_ids: tuple[str, ...] = ()

    # Phase 4B Step 8 / Phase 4 — per-TaskDefinition trajectory
    # selection. Declarative; deterministic lookup only; no runtime
    # adaptation, no dynamic planning.
    #
    # Field classification (D-CONT-7a):
    #   * authoritative-evidence — enters the per-task fingerprint
    #     via the executor's trajectory swap. Selecting a different
    #     ``trajectory_id`` produces a categorically different motion
    #     and a different TaskResult.
    #
    # When ``None`` (Phase 4A default), the executor uses
    # ``cell_cfg.robot.trajectory`` unchanged. When set, the executor
    # looks the id up in its ``trajectory_sets`` constructor map and
    # returns EXECUTOR_ERROR on miss (no silent fallback).
    trajectory_id: str | None = None


# ────────────────────────── result ──────────────────────────


class TaskOutcome(enum.Enum):
    PASS                            = "PASS"
    GRASP_NEVER_ACQUIRED            = "GRASP_NEVER_ACQUIRED"
    GRASP_LOST_IN_TRANSPORT         = "GRASP_LOST_IN_TRANSPORT"
    FLOOR_OR_BELT_TRANSPORT_CONTACT = "FLOOR_OR_BELT_TRANSPORT_CONTACT"
    PLACEMENT_MISS                  = "PLACEMENT_MISS"
    WRIST_3_OUT_OF_BOUNDS           = "WRIST_3_OUT_OF_BOUNDS"
    PEG_OUT_OF_BOUNDS               = "PEG_OUT_OF_BOUNDS"
    MOTION_QUALITY_VIOLATION        = "MOTION_QUALITY_VIOLATION"
    EXECUTOR_ERROR                  = "EXECUTOR_ERROR"


@dataclass
class TaskResult:
    """One full execution's outcome. The unit of validation.

    Carries enough data that every Phase 3M/N/O/P validation gate can
    be re-applied without re-running the cycle.

    Field classification per D-CONT-7 / D-CONT-7a:
      * ``peg_xyz_final``, ``peg_xyz_initial`` — replay-authoritative;
        enter the per-task fingerprint (last-tick canonical pose under
        D-CONT-1).
      * ``placement_offset_xy_m``, ``pick_lift_off_step``,
        ``place_landing_step`` — authoritative-evidence (input to the
        session's D-CONT-5 occupancy-commit decision in Phase G).
        NOT motion metrics; their semantics is categorical
        (lift-off detected? landing detected? offset within tol?).
      * every other field — observational/diagnostic. Per-tick
        aggregate metrics (motion peaks, accelerations, EE speeds)
        are bounded to per-node verdicts only (D-CONT-2).
      * ``wall_clock_s`` is diagnostic-only (D-TRACE-4) and is
        excluded from replay-identity comparisons.
    """
    task_id:               str
    profile_id:            str
    outcome:               TaskOutcome
    outcome_detail:        str = ""

    # Endpoint metrics (Phase 3M).
    # ``peg_xyz_initial`` is Phase 4B Step 8 / Phase 2 addition: peg
    # pose at step 0, before any command. Replay-authoritative under
    # D-CONT-1; enters the per-task fingerprint. Used by inter-node
    # continuity verification (post_N1.peg_xyz_final ≈ pre_N2
    # .peg_xyz_initial within Phase 3P tolerance).
    peg_xyz_initial:       tuple[float, float, float] | None = None
    peg_xyz_final:         tuple[float, float, float] | None = None
    peg_max_z_m:           float = 0.0
    peg_min_z_m:           float = 0.0

    # Placement evidence (Phase 4B Step 8 / Phase 2).
    # Authoritative-evidence per D-CONT-5: input to the session's
    # Phase-G occupancy-commit decision. ``placement_offset_xy_m`` is
    # (dx, dy) of peg_xyz_final relative to task.place_target.world_pose_m.
    # When ``None``, no place-target evidence is available
    # (peg_xyz_final missing). NOT a motion metric.
    placement_offset_xy_m: tuple[float, float] | None = None
    # Step at which the peg first cleared its pick-side fixture's top
    # by >= ε (≈ 20 mm). None when there is no pick-side fixture
    # (e.g. from-belt source) or the lift-off was never detected.
    # Authoritative-evidence; not a motion metric.
    pick_lift_off_step:    int | None = None
    # Step at which the peg first re-acquired contact with a fixture
    # AND both pads broke contact for the first time post-release.
    # None when neither condition is observed. Authoritative-evidence;
    # not a motion metric.
    place_landing_step:    int | None = None

    # Temporal-grasp metrics (Phase 3N).
    grasp_acquired_step:   int | None = None
    grasp_lost_in_transport_step: int | None = None
    last_left_pad_contact_step:   int | None = None
    last_right_pad_contact_step:  int | None = None
    floor_or_belt_first_post_close_step: int | None = None
    fixture_first_post_close_step:        int | None = None
    pad_pen_min_during_transport_mm: float = 0.0
    pad_pen_max_during_transport_mm: float = 0.0

    # Motion-quality metrics (Phase 3O).
    wrist_3_max_z_m:       float = 0.0
    wrist_3_min_z_m:       float = 0.0
    wrist_reach_horizontal_peak_m: float = 0.0
    joint_vel_peak_rad_s:  float = 0.0
    joint_vel_peak_per_joint_rad_s: tuple[float, ...] = ()
    joint_accel_peak_rad_s2: float = 0.0
    ee_speed_peak_mps:     float = 0.0
    ee_accel_peak_m_s2:    float = 0.0
    cartesian_path_length_m: float = 0.0

    # Trajectory boundaries (steps).
    grasp_close_step:      int = 0
    lift_end_step:         int = 0
    place_end_step:        int = 0
    release_start_step:    int = 0
    release_end_step:      int = 0
    n_steps:               int = 0

    # Bookkeeping.
    seed:                  int = 0
    wall_clock_s:          float = 0.0
    perturbation:          dict[str, Any] = field(default_factory=dict)
    registry_snapshot:     dict[str, Any] | None = None

    @property
    def passed(self) -> bool:
        return self.outcome == TaskOutcome.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id":            self.task_id,
            "profile_id":         self.profile_id,
            "outcome":            self.outcome.value,
            "outcome_detail":     self.outcome_detail,
            "peg_xyz_initial":    list(self.peg_xyz_initial) if self.peg_xyz_initial else None,
            "peg_xyz_final":      list(self.peg_xyz_final) if self.peg_xyz_final else None,
            "peg_max_z_m":        self.peg_max_z_m,
            "peg_min_z_m":        self.peg_min_z_m,
            "placement_offset_xy_m": (list(self.placement_offset_xy_m)
                                       if self.placement_offset_xy_m is not None
                                       else None),
            "pick_lift_off_step": self.pick_lift_off_step,
            "place_landing_step": self.place_landing_step,
            "grasp_acquired_step":            self.grasp_acquired_step,
            "grasp_lost_in_transport_step":   self.grasp_lost_in_transport_step,
            "last_left_pad_contact_step":     self.last_left_pad_contact_step,
            "last_right_pad_contact_step":    self.last_right_pad_contact_step,
            "floor_or_belt_first_post_close_step": self.floor_or_belt_first_post_close_step,
            "fixture_first_post_close_step":  self.fixture_first_post_close_step,
            "pad_pen_min_during_transport_mm": self.pad_pen_min_during_transport_mm,
            "pad_pen_max_during_transport_mm": self.pad_pen_max_during_transport_mm,
            "wrist_3_max_z_m":    self.wrist_3_max_z_m,
            "wrist_3_min_z_m":    self.wrist_3_min_z_m,
            "wrist_reach_horizontal_peak_m": self.wrist_reach_horizontal_peak_m,
            "joint_vel_peak_rad_s":   self.joint_vel_peak_rad_s,
            "joint_vel_peak_per_joint_rad_s": list(self.joint_vel_peak_per_joint_rad_s),
            "joint_accel_peak_rad_s2": self.joint_accel_peak_rad_s2,
            "ee_speed_peak_mps":   self.ee_speed_peak_mps,
            "ee_accel_peak_m_s2":  self.ee_accel_peak_m_s2,
            "cartesian_path_length_m": self.cartesian_path_length_m,
            "grasp_close_step":   self.grasp_close_step,
            "lift_end_step":      self.lift_end_step,
            "place_end_step":     self.place_end_step,
            "release_start_step": self.release_start_step,
            "release_end_step":   self.release_end_step,
            "n_steps":            self.n_steps,
            "seed":               self.seed,
            "wall_clock_s":       self.wall_clock_s,
            "perturbation":       self.perturbation,
            "registry_snapshot":  self.registry_snapshot,
        }
