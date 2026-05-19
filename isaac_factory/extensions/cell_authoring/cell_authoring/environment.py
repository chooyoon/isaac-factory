"""Static cell environment authoring.

Phase B scope: floor (re-authored through ``_StaticProp``), safety cage
(4 perimeter walls), robot pedestal, work fixture. Conveyor structural
frames live in :mod:`cell_authoring.conveyor` because they belong to
the conveyor unit.

All translates are interpreted as **prim centres** in world space.
Sizes are extents (axis-aligned full lengths). The factory functions
keep their bottom faces flush with the top face of their support —
this is what the GroundingValidator expects for static-grounding clean.
"""

from __future__ import annotations

from pxr import Sdf, Usd

from .config import CellConfig
from .templates import (
    StaticPropSpec,
    author_static_prop,
)


# Coordinate convention (locked for cell_01):
#   +X = robot's "front" (work-fixture direction)
#   +Y = cell-left
#   +Z = up
#   world origin: centre of floor, with floor top at z=0


def author_environment(stage: Usd.Stage, cfg: CellConfig) -> None:
    """Author every static environment prop into a single ``/World/Environment`` Xform."""
    env_path = Sdf.Path("/World/Environment")
    from pxr import UsdGeom
    UsdGeom.Xform.Define(stage, env_path)

    _author_floor(stage, env_path, cfg)
    _author_safety_cage(stage, env_path, cfg)
    _author_robot_pedestal(stage, env_path, cfg)
    _author_work_fixture(stage, env_path, cfg)


# ============================================================ pieces ==


def _author_floor(stage: Usd.Stage, parent: Sdf.Path, cfg: CellConfig) -> None:
    """Floor: top flush with z = 0."""
    size_x, size_y = cfg.floor.size_xy_m
    thickness = cfg.floor.thickness_m

    author_static_prop(stage, StaticPropSpec(
        parent_path = parent,
        name        = "Floor",
        translate   = (0.0, 0.0, -thickness / 2.0),
        size_xyz_m  = (size_x, size_y, thickness),
        filter_group= "environment",
    ))


def _author_safety_cage(stage: Usd.Stage, parent: Sdf.Path, cfg: CellConfig) -> None:
    """Four perimeter walls forming an open-top safety cage.

    Wall geometry (size_x is along world X, size_y along world Y):
      * North / South walls span (cage_inner_x - 2 * wall_thickness) along X.
      * East / West walls span the full Y dimension to close the corners.

    Walls are centred at z = cage_height / 2 so their bottom face sits
    flush with the floor top (z=0). The mass of each wall is irrelevant
    because they're static colliders — no rigid-body API applied.
    """
    floor_x, floor_y = cfg.floor.size_xy_m
    wall_thickness   = cfg.environment.safety_cage.wall_thickness_m
    cage_height      = cfg.environment.safety_cage.height_m
    # Walls sit on the floor's perimeter (centres are inset by half thickness).
    half_x = floor_x / 2.0 - wall_thickness / 2.0
    half_y = floor_y / 2.0 - wall_thickness / 2.0
    inner_x_span = floor_x - 2.0 * wall_thickness   # north/south wall length

    # Sorted alphabetic order — diff-friendly.
    walls = (
        ("Cage_East",  (+half_x, 0.0, cage_height / 2.0),
                       (wall_thickness, floor_y, cage_height)),
        ("Cage_North", (0.0, +half_y, cage_height / 2.0),
                       (inner_x_span, wall_thickness, cage_height)),
        ("Cage_South", (0.0, -half_y, cage_height / 2.0),
                       (inner_x_span, wall_thickness, cage_height)),
        ("Cage_West",  (-half_x, 0.0, cage_height / 2.0),
                       (wall_thickness, floor_y, cage_height)),
    )
    for name, translate, size in walls:
        author_static_prop(stage, StaticPropSpec(
            parent_path = parent,
            name        = name,
            translate   = translate,
            size_xyz_m  = size,
            filter_group= "environment",
        ))


def _author_robot_pedestal(stage: Usd.Stage, parent: Sdf.Path, cfg: CellConfig) -> None:
    """Robot pedestal at the cell origin. Top face at ``pedestal.top_z``."""
    p = cfg.environment.pedestal
    sx, sy = p.size_xy_m
    h = p.height_m
    author_static_prop(stage, StaticPropSpec(
        parent_path = parent,
        name        = "RobotPedestal",
        translate   = (0.0, 0.0, h / 2.0),    # bottom flush with floor top
        size_xyz_m  = (sx, sy, h),
        filter_group= "environment",
    ))


def _author_work_fixture(stage: Usd.Stage, parent: Sdf.Path, cfg: CellConfig) -> None:
    """Work fixture in front of the pedestal (+X direction).

    Position is set so the fixture's centre is at ``(offset_x, 0, h/2)``,
    with bottom flush against the floor.
    """
    f = cfg.environment.work_fixture
    sx, sy = f.size_xy_m
    h = f.height_m
    author_static_prop(stage, StaticPropSpec(
        parent_path = parent,
        name        = "WorkFixture",
        translate   = (f.offset_x_m, 0.0, h / 2.0),
        size_xyz_m  = (sx, sy, h),
        filter_group= "environment",
    ))
