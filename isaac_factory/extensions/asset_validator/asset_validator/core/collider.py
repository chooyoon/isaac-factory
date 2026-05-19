"""Collider / rigid-body data model.

Separate from :mod:`stage` because ColliderValidator has its own concerns and
should not force TransformValidator to depend on collider data, or vice versa.
The two protocols are independent; an adapter (real implementation, deferred)
may implement both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class ColliderInfo:
    """One prim with `PhysicsCollisionAPI` applied.

    `rigid_body_path` is the prim path of the closest ancestor with
    `PhysicsRigidBodyAPI` (or the same prim if both APIs are on it).
    ``None`` means the collider is an orphan — no rigid-body owner.

    AABBs are stored as ``(min_x, min_y, min_z) / (max_x, max_y, max_z)`` in
    the collider's local space. `visual_aabb_*` is the AABB of the underlying
    visual mesh; the collider AABB is the AABB the physics engine actually
    cooked. The two should agree within 10 % per axis (acceptance §3.5).
    """

    path:                              str
    approximation:                     str
    rigid_body_path:                   str | None                       = None
    collider_aabb_min:                 tuple[float, float, float] | None = None
    collider_aabb_max:                 tuple[float, float, float] | None = None
    visual_aabb_min:                   tuple[float, float, float] | None = None
    visual_aabb_max:                   tuple[float, float, float] | None = None
    convex_decomposition_hull_count:   int | None                       = None
    cooking_error:                     str | None                       = None
    collision_group:                   str | None                       = None
    custom_data:                       tuple[tuple[str, Any], ...]      = ()

    def custom_data_dict(self) -> dict[str, Any]:
        return dict(self.custom_data)

    def is_static_collider_flagged(self) -> bool:
        return bool(self.custom_data_dict().get("static_collider", False))


@dataclass(frozen=True)
class RigidBodyInfo:
    """One prim with `PhysicsRigidBodyAPI` applied."""

    path:                  str
    is_kinematic:          bool                      = False
    is_articulation_root:  bool                      = False
    mass:                  float | None              = None      # kg; None = compute from density
    density:               float | None              = None      # kg/m³
    volume_m3:             float | None              = None      # for §3.10 cross-check
    custom_data:           tuple[tuple[str, Any], ...] = ()


class ColliderInspector(Protocol):
    """Anything that can enumerate physics colliders and rigid bodies for a stage.

    Real implementation (deferred) walks the USD stage via `pxr.UsdPhysics` and
    queries `omni.physx` for cooked AABBs and hull counts.
    """

    def iter_colliders(self)   -> Iterable[ColliderInfo]:   ...
    def iter_rigid_bodies(self) -> Iterable[RigidBodyInfo]: ...
