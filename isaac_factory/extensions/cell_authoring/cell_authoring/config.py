"""Strict, frozen-dataclass mirror of ``configs/cell_01.yaml``.

The loader rejects unknown top-level keys, unknown schema versions, and
out-of-range numeric values. Defaults live ONLY in the YAML file —
this module does not silently fill in missing entries, because that is
how cell-to-cell drift starts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"0.4.0"})

_TOP_LEVEL_KEYS = frozenset({
    "schema_version", "cell", "runtime", "environment", "lighting",
    "machinery", "parts", "robot", "paths",
})


# ============================================================== nested ==


@dataclass(frozen=True)
class GravityConfig:
    direction:           tuple[float, float, float]
    magnitude_m_per_s2:  float


@dataclass(frozen=True)
class RuntimeConfig:
    seed:                              int
    physics_dt:                        float
    rendering_dt:                      float
    enable_enhanced_determinism:       bool
    solver_type:                       str   # "PGS" | "TGS"
    solver_position_iteration_count:   int
    solver_velocity_iteration_count:   int
    gravity:                           GravityConfig


@dataclass(frozen=True)
class FloorConfig:
    size_xy_m:    tuple[float, float]
    thickness_m:  float


@dataclass(frozen=True)
class SafetyCageConfig:
    wall_thickness_m:  float
    height_m:          float


@dataclass(frozen=True)
class PedestalConfig:
    size_xy_m:  tuple[float, float]
    height_m:   float


@dataclass(frozen=True)
class WorkFixtureConfig:
    size_xy_m:    tuple[float, float]
    height_m:     float
    offset_x_m:   float


@dataclass(frozen=True)
class EnvironmentConfig:
    floor:         FloorConfig
    safety_cage:   SafetyCageConfig
    pedestal:      PedestalConfig
    work_fixture:  WorkFixtureConfig


@dataclass(frozen=True)
class LightingConfig:
    dome_intensity: float


@dataclass(frozen=True)
class ConveyorConfig:
    name:                          str
    translate_world_m:             tuple[float, float, float]  # belt centre xy + z
    belt_length_m:                 float
    belt_width_m:                  float
    belt_thickness_m:              float
    belt_top_z_m:                  float
    rail_thickness_m:              float
    rail_height_m:                 float
    belt_velocity_world_m_per_s:   tuple[float, float, float]


@dataclass(frozen=True)
class PartConfig:
    name:                  str
    translate_world_m:     tuple[float, float, float]
    size_xyz_m:            tuple[float, float, float]
    mass_kg:               float
    approximation:         str


_UR10E_REVOLUTE_JOINT_NAMES: tuple[str, ...] = (
    "shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3",
)


@dataclass(frozen=True)
class JointDriveConfig:
    """PD gains applied to every revolute joint via UsdPhysics.DriveAPI."""
    stiffness:  float
    damping:    float


@dataclass(frozen=True)
class GripperDriveConfig:
    """Drive parameters for the Robotiq 2F-85 main knuckle joint."""
    drive_joint_name:    str
    open_position_rad:   float
    close_position_rad:  float
    drive_stiffness:     float
    drive_damping:       float


@dataclass(frozen=True)
class TrajectoryWaypoint:
    """One target pose in the open-loop joint-space trajectory.

    ``duration_s`` is the time to travel **to this waypoint** from the
    previous one (linear interpolation in joint space, sampled at
    physics_dt). The first waypoint must have duration 0.0.
    """
    name:                 str
    duration_s:           float
    joint_positions_rad:  tuple[tuple[str, float], ...]   # ordered, hashable
    gripper:              str                              # "open" | "close"


@dataclass(frozen=True)
class RobotConfig:
    """Phase 3A + 3B robot integration parameters.

    See cell_01.yaml's `robot:` section for field-by-field documentation.
    """
    asset_rel:                str
    mount_prim_path:          str
    translate_world_m:        tuple[float, float, float]
    enable_self_collisions:   bool
    articulation_filter_group: str
    gripper_variant:          str                                 # "None" | "Robotiq_2f_85" | …
    home_pose_rad:            tuple[tuple[str, float], ...]       # ordered, hashable
    joint_drive:              JointDriveConfig
    trajectory:               tuple[TrajectoryWaypoint, ...]
    gripper:                  GripperDriveConfig


@dataclass(frozen=True)
class CellConfig:
    schema_version:   str
    cell_id:          str
    display_name:     str
    description:      str
    runtime:          RuntimeConfig
    environment:      EnvironmentConfig
    lighting:         LightingConfig
    conveyors:        tuple[ConveyorConfig, ...]
    parts:            tuple[PartConfig, ...]
    robot:            RobotConfig | None
    cell_stage_rel:   str
    output_root_rel:  str

    # Backwards-compatible alias retained for Phase A callers that read
    # `.floor` directly off CellConfig — re-routes to environment.floor.
    @property
    def floor(self) -> FloorConfig:
        return self.environment.floor


# =============================================================== loader ==


def load_config(path: str | Path) -> CellConfig:
    """Load and validate a cell config from a YAML file.

    Raises :class:`ValueError` on schema problems and :class:`FileNotFoundError`
    if the file does not exist.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"cell config not found: {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"top-level YAML must be a mapping; got {type(raw).__name__}")
    return _parse(raw)


# ============================================================== private ==


def _parse(raw: Mapping[str, Any]) -> CellConfig:
    # Check schema_version BEFORE the rest of the keys: an unknown
    # schema_version is the right error to surface even when the file
    # is otherwise structurally incomplete.
    if "schema_version" in raw:
        sv = str(raw["schema_version"])
        if sv not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported schema_version {sv!r}; supported: "
                f"{sorted(SUPPORTED_SCHEMA_VERSIONS)}"
            )
    _require_keys(raw, _TOP_LEVEL_KEYS, "<root>")
    sv = str(raw["schema_version"])

    cell = _as_map(raw["cell"], "cell")
    _require_keys(cell, {"id", "display_name", "description"}, "cell")

    runtime     = _parse_runtime    (_as_map(raw["runtime"],     "runtime"))
    environment = _parse_environment(_as_map(raw["environment"], "environment"))
    lighting    = _parse_lights     (_as_map(raw["lighting"],    "lighting"))
    conveyors   = _parse_conveyors  (_as_seq(raw["machinery"],   "machinery"))
    parts       = _parse_parts      (_as_seq(raw["parts"],       "parts"))
    robot       = _parse_robot      (raw.get("robot"))

    paths = _as_map(raw["paths"], "paths")
    _require_keys(paths, {"cell_stage", "output_root"}, "paths")

    return CellConfig(
        schema_version  = sv,
        cell_id         = str(cell["id"]),
        display_name    = str(cell["display_name"]),
        description     = str(cell["description"]).strip(),
        runtime         = runtime,
        environment     = environment,
        lighting        = lighting,
        conveyors       = conveyors,
        parts           = parts,
        robot           = robot,
        cell_stage_rel  = str(paths["cell_stage"]),
        output_root_rel = str(paths["output_root"]),
    )


def _parse_robot(d: Any) -> RobotConfig | None:
    """Robot is optional (None when YAML omits the section)."""
    if d is None:
        return None
    if not isinstance(d, Mapping):
        raise ValueError(f"robot must be a mapping; got {type(d).__name__}")
    _require_keys(d, {
        "asset_rel", "mount_prim_path", "translate_world_m",
        "enable_self_collisions", "articulation_filter_group",
        "gripper_variant", "home_pose_rad", "joint_drive",
        "trajectory", "gripper",
    }, "robot")

    home = _parse_joint_dict(d["home_pose_rad"], "robot.home_pose_rad")
    drive = _parse_joint_drive(_as_map(d["joint_drive"], "robot.joint_drive"))
    traj = _parse_trajectory(_as_seq(d["trajectory"], "robot.trajectory"))
    grip = _parse_gripper_drive(_as_map(d["gripper"], "robot.gripper"))

    return RobotConfig(
        asset_rel                = str(d["asset_rel"]),
        mount_prim_path          = str(d["mount_prim_path"]),
        translate_world_m        = _as_vec3(d["translate_world_m"], "robot.translate_world_m"),
        enable_self_collisions   = bool(d["enable_self_collisions"]),
        articulation_filter_group= str(d["articulation_filter_group"]),
        gripper_variant          = str(d["gripper_variant"]),
        home_pose_rad            = home,
        joint_drive              = drive,
        trajectory               = traj,
        gripper                  = grip,
    )


def _parse_joint_dict(
    d: Any, where: str,
) -> tuple[tuple[str, float], ...]:
    """Parse a mapping of joint-name → radians into a deterministic tuple."""
    if not isinstance(d, Mapping):
        raise ValueError(f"{where} must be a mapping; got {type(d).__name__}")
    missing = sorted(set(_UR10E_REVOLUTE_JOINT_NAMES) - set(d.keys()))
    if missing:
        raise ValueError(f"{where} missing joints: {missing}")
    extra = sorted(set(d.keys()) - set(_UR10E_REVOLUTE_JOINT_NAMES))
    if extra:
        raise ValueError(f"{where} has unknown joints: {extra}")
    return tuple((name, float(d[name])) for name in _UR10E_REVOLUTE_JOINT_NAMES)


def _parse_joint_drive(d: Mapping[str, Any]) -> JointDriveConfig:
    _require_keys(d, {"stiffness", "damping"}, "robot.joint_drive")
    s = float(d["stiffness"])
    da = float(d["damping"])
    if s <= 0 or da < 0:
        raise ValueError(f"robot.joint_drive values must be positive; got stiffness={s} damping={da}")
    return JointDriveConfig(stiffness=s, damping=da)


def _parse_gripper_drive(d: Mapping[str, Any]) -> GripperDriveConfig:
    _require_keys(d, {
        "drive_joint_name", "open_position_rad", "close_position_rad",
        "drive_stiffness", "drive_damping",
    }, "robot.gripper")
    return GripperDriveConfig(
        drive_joint_name   = str(d["drive_joint_name"]),
        open_position_rad  = float(d["open_position_rad"]),
        close_position_rad = float(d["close_position_rad"]),
        drive_stiffness    = float(d["drive_stiffness"]),
        drive_damping      = float(d["drive_damping"]),
    )


def _parse_trajectory(seq: Sequence[Any]) -> tuple[TrajectoryWaypoint, ...]:
    if len(seq) < 2:
        raise ValueError(f"robot.trajectory must have at least 2 waypoints")
    out: list[TrajectoryWaypoint] = []
    seen_names: set[str] = set()
    for i, raw in enumerate(seq):
        d = _as_map(raw, f"robot.trajectory[{i}]")
        _require_keys(d, {"name", "duration_s", "joint_positions_rad", "gripper"},
                      f"robot.trajectory[{i}]")
        name = str(d["name"])
        if name in seen_names:
            raise ValueError(f"robot.trajectory waypoint names must be unique; '{name}' repeated")
        seen_names.add(name)
        dur = float(d["duration_s"])
        if i == 0 and dur != 0.0:
            raise ValueError("robot.trajectory[0].duration_s must be 0.0 (start waypoint)")
        if i > 0 and dur < 0.0:
            raise ValueError(f"robot.trajectory[{i}].duration_s must be non-negative; got {dur}")
        joints = _parse_joint_dict(d["joint_positions_rad"],
                                   f"robot.trajectory[{i}].joint_positions_rad")
        grip = str(d["gripper"])
        if grip not in {"open", "close"}:
            raise ValueError(
                f"robot.trajectory[{i}].gripper must be 'open' or 'close'; got {grip!r}"
            )
        out.append(TrajectoryWaypoint(
            name=name, duration_s=dur, joint_positions_rad=joints, gripper=grip,
        ))
    return tuple(out)


def _parse_runtime(d: Mapping[str, Any]) -> RuntimeConfig:
    _require_keys(d, {
        "seed", "physics_dt", "rendering_dt", "enable_enhanced_determinism",
        "solver_type", "solver_position_iteration_count",
        "solver_velocity_iteration_count", "gravity",
    }, "runtime")

    solver = str(d["solver_type"]).upper()
    if solver not in {"PGS", "TGS"}:
        raise ValueError(f"runtime.solver_type must be PGS or TGS; got {d['solver_type']!r}")

    physics_dt = float(d["physics_dt"])
    if not (0.0 < physics_dt <= 1.0):
        raise ValueError(f"runtime.physics_dt out of (0, 1]: {physics_dt}")

    g = _as_map(d["gravity"], "runtime.gravity")
    _require_keys(g, {"direction", "magnitude_m_per_s2"}, "runtime.gravity")

    return RuntimeConfig(
        seed                              = int(d["seed"]),
        physics_dt                        = physics_dt,
        rendering_dt                      = float(d["rendering_dt"]),
        enable_enhanced_determinism       = bool(d["enable_enhanced_determinism"]),
        solver_type                       = solver,
        solver_position_iteration_count   = int(d["solver_position_iteration_count"]),
        solver_velocity_iteration_count   = int(d["solver_velocity_iteration_count"]),
        gravity = GravityConfig(
            direction          = _as_vec3(g["direction"], "runtime.gravity.direction"),
            magnitude_m_per_s2 = float(g["magnitude_m_per_s2"]),
        ),
    )


def _parse_environment(d: Mapping[str, Any]) -> EnvironmentConfig:
    _require_keys(d, {"floor", "safety_cage", "pedestal", "work_fixture"}, "environment")

    floor = _parse_floor(_as_map(d["floor"], "environment.floor"))
    cage = _parse_cage  (_as_map(d["safety_cage"], "environment.safety_cage"))
    ped  = _parse_pedestal(_as_map(d["pedestal"], "environment.pedestal"))
    wf   = _parse_fixture(_as_map(d["work_fixture"], "environment.work_fixture"))

    return EnvironmentConfig(floor=floor, safety_cage=cage, pedestal=ped, work_fixture=wf)


def _parse_floor(d: Mapping[str, Any]) -> FloorConfig:
    _require_keys(d, {"size_xy_m", "thickness_m"}, "environment.floor")
    sx, sy = _as_vec2(d["size_xy_m"], "environment.floor.size_xy_m")
    if sx <= 0 or sy <= 0:
        raise ValueError(f"environment.floor.size_xy_m must be positive; got ({sx}, {sy})")
    thickness = float(d["thickness_m"])
    if thickness <= 0:
        raise ValueError(f"environment.floor.thickness_m must be positive; got {thickness}")
    return FloorConfig(size_xy_m=(sx, sy), thickness_m=thickness)


def _parse_cage(d: Mapping[str, Any]) -> SafetyCageConfig:
    _require_keys(d, {"wall_thickness_m", "height_m"}, "environment.safety_cage")
    wt = float(d["wall_thickness_m"])
    h  = float(d["height_m"])
    if wt <= 0 or h <= 0:
        raise ValueError(f"environment.safety_cage dimensions must be positive")
    return SafetyCageConfig(wall_thickness_m=wt, height_m=h)


def _parse_pedestal(d: Mapping[str, Any]) -> PedestalConfig:
    _require_keys(d, {"size_xy_m", "height_m"}, "environment.pedestal")
    sx, sy = _as_vec2(d["size_xy_m"], "environment.pedestal.size_xy_m")
    h = float(d["height_m"])
    if sx <= 0 or sy <= 0 or h <= 0:
        raise ValueError(f"environment.pedestal dimensions must be positive")
    return PedestalConfig(size_xy_m=(sx, sy), height_m=h)


def _parse_fixture(d: Mapping[str, Any]) -> WorkFixtureConfig:
    _require_keys(d, {"size_xy_m", "height_m", "offset_x_m"}, "environment.work_fixture")
    sx, sy = _as_vec2(d["size_xy_m"], "environment.work_fixture.size_xy_m")
    h = float(d["height_m"])
    if sx <= 0 or sy <= 0 or h <= 0:
        raise ValueError(f"environment.work_fixture dimensions must be positive")
    return WorkFixtureConfig(size_xy_m=(sx, sy), height_m=h, offset_x_m=float(d["offset_x_m"]))


def _parse_lights(d: Mapping[str, Any]) -> LightingConfig:
    _require_keys(d, {"dome_intensity"}, "lighting")
    intensity = float(d["dome_intensity"])
    if intensity < 0:
        raise ValueError(f"lighting.dome_intensity must be non-negative; got {intensity}")
    return LightingConfig(dome_intensity=intensity)


def _parse_conveyors(seq: Sequence[Any]) -> tuple[ConveyorConfig, ...]:
    out: list[ConveyorConfig] = []
    for i, raw in enumerate(seq):
        d = _as_map(raw, f"machinery[{i}]")
        _require_keys(d, {
            "name", "translate_world_m", "belt_length_m", "belt_width_m",
            "belt_thickness_m", "belt_top_z_m", "rail_thickness_m",
            "rail_height_m", "belt_velocity_world_m_per_s",
        }, f"machinery[{i}]")
        out.append(ConveyorConfig(
            name                         = str(d["name"]),
            translate_world_m            = _as_vec3(d["translate_world_m"], f"machinery[{i}].translate_world_m"),
            belt_length_m                = float(d["belt_length_m"]),
            belt_width_m                 = float(d["belt_width_m"]),
            belt_thickness_m             = float(d["belt_thickness_m"]),
            belt_top_z_m                 = float(d["belt_top_z_m"]),
            rail_thickness_m             = float(d["rail_thickness_m"]),
            rail_height_m                = float(d["rail_height_m"]),
            belt_velocity_world_m_per_s  = _as_vec3(
                d["belt_velocity_world_m_per_s"],
                f"machinery[{i}].belt_velocity_world_m_per_s",
            ),
        ))
    names = [c.name for c in out]
    if len(names) != len(set(names)):
        raise ValueError(f"machinery names must be unique; got {names}")
    return tuple(out)


def _parse_parts(seq: Sequence[Any]) -> tuple[PartConfig, ...]:
    out: list[PartConfig] = []
    for i, raw in enumerate(seq):
        d = _as_map(raw, f"parts[{i}]")
        _require_keys(d, {
            "name", "translate_world_m", "size_xyz_m", "mass_kg", "approximation",
        }, f"parts[{i}]")
        mass = float(d["mass_kg"])
        if mass <= 0:
            raise ValueError(f"parts[{i}].mass_kg must be positive; got {mass}")
        out.append(PartConfig(
            name               = str(d["name"]),
            translate_world_m  = _as_vec3(d["translate_world_m"], f"parts[{i}].translate_world_m"),
            size_xyz_m         = _as_vec3(d["size_xyz_m"],         f"parts[{i}].size_xyz_m"),
            mass_kg            = mass,
            approximation      = str(d["approximation"]),
        ))
    names = [p.name for p in out]
    if len(names) != len(set(names)):
        raise ValueError(f"parts names must be unique; got {names}")
    return tuple(out)


def _as_map(v: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(v, Mapping):
        raise ValueError(f"{where} must be a mapping; got {type(v).__name__}")
    return v


def _as_seq(v: Any, where: str) -> Sequence[Any]:
    if not isinstance(v, (list, tuple)):
        raise ValueError(f"{where} must be a list; got {type(v).__name__}")
    return v


def _as_vec2(v: Any, where: str) -> tuple[float, float]:
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        raise ValueError(f"{where} must be a 2-element list")
    return float(v[0]), float(v[1])


def _as_vec3(v: Any, where: str) -> tuple[float, float, float]:
    if not (isinstance(v, (list, tuple)) and len(v) == 3):
        raise ValueError(f"{where} must be a 3-element list")
    return float(v[0]), float(v[1]), float(v[2])


def _require_keys(d: Mapping[str, Any], required: frozenset[str] | set[str], where: str) -> None:
    missing = sorted(set(required) - set(d.keys()))
    if missing:
        raise ValueError(f"{where} missing required keys: {missing}")
    extra = sorted(set(d.keys()) - set(required)) if where == "<root>" else []
    if extra:
        raise ValueError(f"{where} has unknown keys: {extra}")
