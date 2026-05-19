"""Consumable rigid-body parts (peg, housing, tray).

Phase B scope ships only the peg as a first consumable so we can prove
the conveyor-transport pipeline end-to-end. Housing and tray follow in
Phase 2B with the same factory pattern.

Deterministic initial state
---------------------------

Every consumable has an authored ``translate`` (the only xformOp).
Reset returns the rigid body to this translate exactly. No randomisation,
no jitter, no perturbed initial velocity — the dynamic flow is fully
determined by authored mass, friction, and belt surface velocity.

Mass / inertia / friction
-------------------------

* **mass** authored via UsdPhysics.MassAPI; range checked against
  ``ColliderThresholds`` (1e-3 to 1e+5 kg).
* **inertia** — left implicit (PhysX computes from collider geometry +
  mass). Authoring an explicit inertia tensor is a Phase 2B concern;
  for a uniform box the computed inertia is exact.
* **friction** — authored as a PhysicsMaterial binding (custom token
  attribute) per Phase 2B. For Phase B the default material is used;
  the cell's default friction coefficient is high enough to transport
  a peg of the authored mass.
"""

from __future__ import annotations

from pxr import Sdf, Usd, UsdGeom

from .config import CellConfig, PartConfig
from .templates import (
    DynamicPartSpec,
    author_dynamic_part,
)


def author_parts(stage: Usd.Stage, cfg: CellConfig) -> None:
    """Author every consumable declared in the cell config under ``/World/Parts``."""
    parts_path = Sdf.Path("/World/Parts")
    UsdGeom.Xform.Define(stage, parts_path)

    for part in sorted(cfg.parts, key=lambda p: p.name):
        _author_part(stage, parts_path, part)


def _author_part(stage: Usd.Stage, parent: Sdf.Path, part: PartConfig) -> None:
    """Author one dynamic consumable. ``translate`` is the prim centre."""
    author_dynamic_part(stage, DynamicPartSpec(
        parent_path  = parent,
        name         = part.name,
        translate    = part.translate_world_m,
        size_xyz_m   = part.size_xyz_m,
        mass_kg      = part.mass_kg,
        approximation= part.approximation,
        grounded     = "true",
        filter_group = "consumable",
    ))
