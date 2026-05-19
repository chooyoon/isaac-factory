"""Conveyor authoring — kinematic belt + static side rails.

Design
------

A conveyor is a Xform group ``/World/Machinery/<name>/`` containing:

  * ``Frame_East``  — static side rail (``_StaticProp``)
  * ``Frame_West``  — static side rail
  * ``Belt``        — kinematic belt surface (``_BeltSurface``) with
                      PhysxSurfaceVelocityAPI for friction transport

Transport mechanism
-------------------

The belt does NOT move via animated transforms (sprint §3 prohibition).
Items on the belt are transported by:

  1. The belt's collider has ``PhysxSurfaceVelocityAPI`` authored.
  2. PhysX resolves the contact between part collider and belt collider.
  3. Friction at the contact pushes the part in the direction of
     ``surfaceVelocity`` — i.e., genuine physics, not teleport.

Reset behaviour
---------------

When the cell resets, the belt's authored translate (kinematic, no
physics updates) is restored to the USD-authored value. The
``surfaceVelocity`` attributes are authored constants → they don't
change across steps → reset is exactly the authored state.
"""

from __future__ import annotations

from dataclasses import dataclass

from pxr import Sdf, Usd, UsdGeom

from .config import CellConfig, ConveyorConfig
from .templates import (
    BeltSurfaceSpec,
    StaticPropSpec,
    author_belt_surface,
    author_static_prop,
)


def author_conveyor(
    stage: Usd.Stage,
    parent: Sdf.Path,
    name: str,
    conveyor: ConveyorConfig,
) -> Sdf.Path:
    """Author one conveyor under ``parent / name``. Returns the conveyor group path."""
    group_path = parent.AppendChild(name)
    UsdGeom.Xform.Define(stage, group_path)

    _author_rails(stage, group_path, conveyor)
    _author_belt (stage, group_path, conveyor)
    return group_path


def author_machinery(stage: Usd.Stage, cfg: CellConfig) -> None:
    """Author every conveyor declared in the cell config."""
    machinery_path = Sdf.Path("/World/Machinery")
    UsdGeom.Xform.Define(stage, machinery_path)

    for cv in sorted(cfg.conveyors, key=lambda c: c.name):
        author_conveyor(stage, machinery_path, cv.name, cv)


# ============================================================== pieces ==


def _author_rails(stage: Usd.Stage, parent: Sdf.Path, cv: ConveyorConfig) -> None:
    """Two side rails along +X. Bottom face flush with floor top (z=0)."""
    # Rails span the full belt length along X, plus a small lip on each
    # end so they remain visible past the belt edges. Match the belt
    # length exactly for now — overshoot can be added later without
    # changing the contract.
    rail_y_offset = cv.belt_width_m / 2.0 + cv.rail_thickness_m / 2.0
    rail_height = cv.rail_height_m
    rail_size = (cv.belt_length_m, cv.rail_thickness_m, rail_height)

    author_static_prop(stage, StaticPropSpec(
        parent_path = parent,
        name        = "Frame_East",
        translate   = (cv.translate_world_m[0],
                       cv.translate_world_m[1] - rail_y_offset,
                       rail_height / 2.0),
        size_xyz_m  = rail_size,
        filter_group= "machinery",
    ))
    author_static_prop(stage, StaticPropSpec(
        parent_path = parent,
        name        = "Frame_West",
        translate   = (cv.translate_world_m[0],
                       cv.translate_world_m[1] + rail_y_offset,
                       rail_height / 2.0),
        size_xyz_m  = rail_size,
        filter_group= "machinery",
    ))


def _author_belt(stage: Usd.Stage, parent: Sdf.Path, cv: ConveyorConfig) -> None:
    """Belt: kinematic body with surface velocity along world ±X.

    The belt sits at z = belt_top_z - thickness/2 (centre), so its top
    face is at the authored ``belt_top_z`` — that is the world z a
    consumable's bottom face must touch for friction transport.
    """
    belt_centre_z = cv.belt_top_z_m - cv.belt_thickness_m / 2.0
    author_belt_surface(stage, BeltSurfaceSpec(
        parent_path = parent,
        name        = "Belt",
        translate   = (cv.translate_world_m[0],
                       cv.translate_world_m[1],
                       belt_centre_z),
        size_xyz_m  = (cv.belt_length_m, cv.belt_width_m, cv.belt_thickness_m),
        surface_velocity_m_per_s = (cv.belt_velocity_world_m_per_s[0],
                                    cv.belt_velocity_world_m_per_s[1],
                                    cv.belt_velocity_world_m_per_s[2]),
        filter_group= "machinery",
    ))
