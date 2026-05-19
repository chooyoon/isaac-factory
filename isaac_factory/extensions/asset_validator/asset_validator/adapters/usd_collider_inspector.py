"""USD-only implementation of :class:`ColliderInspector`.

Mirrors :class:`asset_validator.adapters.physx_collider_inspector.PhysXColliderInspector`
for the **static** USD-resident facts that ColliderValidator consumes —
approximation class, rigid-body ancestor, world AABB, filter group, mass,
and custom-data flags.

What this adapter intentionally does NOT do
--------------------------------------------

* **No cooking-error capture.** Cooking happens in PhysX (Runtime B). The
  adapter always reports ``cooking_error=None``; the validator simply
  cannot emit :data:`CODE_COOKING_FAILED` under Runtime A.
* **No convex-decomposition hull count.** Cooked hull counts only exist
  after PhysX cooks the mesh. Always ``None`` → §3.4 is not checked
  under Runtime A.
* **No ``PhysxSchema`` import.** Convex-hull / decomposition classification
  is done by walking the prim's ``apiSchemas`` token list rather than
  ``HasAPI(PhysxSchema.…)`` — the latter requires the PhysxSchema plugin
  which is only present in Kit Python.

Runtime: **A** (conda env_isaaclab, Python 3.10, ``usd-core 26.3``).

Validator coverage under Runtime A
-----------------------------------

Out of the codes ``CODE_*`` in :mod:`asset_validator.validators.collider`,
Runtime A still emits:

* ``NO_RIGID_BODY_ANCESTOR``       (§3.1)
* ``RIGID_BODY_WITHOUT_COLLIDER``  (§3.2)
* ``MESH_ON_DYNAMIC``              (§3.3)
* ``AABB_MISMATCH``                (§3.5)
* ``MISSING_COLLISION_GROUP``      (§3.6)
* ``MASS_OUT_OF_RANGE``            (§3.9)
* ``MASS_DENSITY_CONFLICT``        (§3.10)
* ``DEGENERATE_AABB``              (stability)
* ``EXTREME_ASPECT_RATIO``         (stability)

``CODE_COOKING_FAILED`` (§3.7) and ``CODE_CONVEX_DECOMP_HULL_LIMIT`` (§3.4)
require Runtime B.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

from ..core.collider import ColliderInfo, ColliderInspector, RigidBodyInfo


# Map USD-primitive type → canonical approximation string used by
# ColliderValidator.dynamic_allowed_approximations.
_PRIM_TYPE_TO_APPROX: dict[str, str] = {
    "Cube":     "box",
    "Sphere":   "sphere",
    "Capsule":  "capsule",
    "Cylinder": "cylinder",
}

# Schema tokens we recognise on the prim's `apiSchemas` list. PhysxSchema
# is not importable in Runtime A; we match by token string instead. The
# tokens come from the PhysxSchema USD plugin manifest and are stable
# across Isaac Sim 4.x and 5.x.
_PHYSX_CONVEX_HULL_SCHEMA          = "PhysxConvexHullCollisionAPI"
_PHYSX_CONVEX_DECOMPOSITION_SCHEMA = "PhysxConvexDecompositionCollisionAPI"


@dataclass
class UsdColliderInspector:
    """:class:`ColliderInspector` backed by raw USD geometry.

    Parameters
    ----------
    stage
        The opened :class:`Usd.Stage` to inspect.
    bbox_purposes
        Which `purpose` tokens the BBox cache should consider. Default
        is ``("default", "render")``.
    include_guide_purpose
        When True, also include ``UsdGeom.Tokens.guide`` in the bbox cache.
        Required when collider geometry is hidden behind ``purpose=guide``
        (the cell_authoring convention to keep collider cubes out of
        render views). Default ``True`` because the cell pipeline relies
        on it; set ``False`` for fixtures that share visual + collider.
    """

    stage: Usd.Stage
    bbox_purposes: tuple = (UsdGeom.Tokens.default_, UsdGeom.Tokens.render)
    include_guide_purpose: bool = True

    # ===================================================== Protocol ==

    def iter_colliders(self) -> Iterable[ColliderInfo]:
        rb_paths = self._rigid_body_paths()
        bbox_cache = self._make_bbox_cache()

        # Traverse instance proxies so that colliders inside *instanceable*
        # subtrees (the canonical layout for NVIDIA's UR10e and other
        # referenced articulations — each per-link mesh is an instance
        # of a prototype) are visible. Without ``TraverseInstanceProxies``
        # the standard Traverse skips them and the validator reports
        # spurious RIGID_BODY_WITHOUT_COLLIDER on every robot link.
        prims = [
            p for p in self._traverse_with_instances()
            if p.IsActive() and p.HasAPI(UsdPhysics.CollisionAPI)
        ]
        prims.sort(key=lambda p: str(p.GetPath()))

        for prim in prims:
            yield self._build_collider_info(prim, rb_paths, bbox_cache)

    def iter_rigid_bodies(self) -> Iterable[RigidBodyInfo]:
        # Articulation roots can be hosted on either a rigid-body link OR
        # a fixed-joint anchor (the canonical UR10e pattern places the
        # ArticulationRootAPI on /<robot>/root_joint, a PhysicsFixedJoint
        # whose only role is to anchor base_link to world frame).
        # Joints aren't rigid bodies — they have no inertial state, no
        # colliders, no mass. Excluding them prevents a false
        # RIGID_BODY_WITHOUT_COLLIDER on every articulation root that
        # happens to live on a joint.
        prims = [
            p for p in self._traverse_with_instances()
            if p.IsActive()
            and (p.HasAPI(UsdPhysics.RigidBodyAPI)
                 or p.HasAPI(UsdPhysics.ArticulationRootAPI))
            and not _is_physics_joint(p)
        ]
        prims.sort(key=lambda p: str(p.GetPath()))

        for prim in prims:
            yield self._build_rb_info(prim)

    def _traverse_with_instances(self) -> Iterable[Usd.Prim]:
        """Yield every prim in the stage including descendants of instanceable prims."""
        return Usd.PrimRange.Stage(self.stage, Usd.TraverseInstanceProxies())

    # ===================================================== internal ==

    def _make_bbox_cache(self) -> UsdGeom.BBoxCache:
        purposes = list(self.bbox_purposes)
        if self.include_guide_purpose and UsdGeom.Tokens.guide not in purposes:
            purposes.append(UsdGeom.Tokens.guide)
        return UsdGeom.BBoxCache(
            time=Usd.TimeCode.Default(),
            includedPurposes=purposes,
            useExtentsHint=True,
        )

    def _rigid_body_paths(self) -> set[str]:
        return {
            str(p.GetPath()) for p in self._traverse_with_instances()
            if p.IsActive() and p.HasAPI(UsdPhysics.RigidBodyAPI)
        }

    def _build_collider_info(
        self,
        prim: Usd.Prim,
        rb_paths: set[str],
        bbox_cache: UsdGeom.BBoxCache,
    ) -> ColliderInfo:
        path             = str(prim.GetPath())
        rigid_body_path  = self._find_rb_path(prim, rb_paths)
        approximation    = self._classify_approximation(prim)
        aabb_min, aabb_max = self._world_aabb(prim, bbox_cache)
        collision_group  = self._read_filter_group(prim)
        custom_data      = self._freeze_custom_data(prim)

        return ColliderInfo(
            path                              = path,
            approximation                     = approximation,
            rigid_body_path                   = rigid_body_path,
            collider_aabb_min                 = aabb_min,
            collider_aabb_max                 = aabb_max,
            visual_aabb_min                   = aabb_min,
            visual_aabb_max                   = aabb_max,
            convex_decomposition_hull_count   = None,
            cooking_error                     = None,
            collision_group                   = collision_group,
            custom_data                       = custom_data,
        )

    def _build_rb_info(self, prim: Usd.Prim) -> RigidBodyInfo:
        path = str(prim.GetPath())
        kinematic = False
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            rb_api = UsdPhysics.RigidBodyAPI(prim)
            attr = rb_api.GetKinematicEnabledAttr()
            if attr and attr.HasAuthoredValue():
                kinematic = bool(attr.Get())
        art_root = prim.HasAPI(UsdPhysics.ArticulationRootAPI)
        mass, density, volume = self._read_mass_density_volume(prim)
        custom_data = self._freeze_custom_data(prim)
        return RigidBodyInfo(
            path                  = path,
            is_kinematic          = kinematic,
            is_articulation_root  = art_root,
            mass                  = mass,
            density               = density,
            volume_m3             = volume,
            custom_data           = custom_data,
        )

    @staticmethod
    def _find_rb_path(prim: Usd.Prim, rb_paths: set[str]) -> str | None:
        path = str(prim.GetPath())
        if path in rb_paths:
            return path
        cur = prim.GetParent()
        while cur and not cur.IsPseudoRoot():
            cp = str(cur.GetPath())
            if cp in rb_paths:
                return cp
            cur = cur.GetParent()
        return None

    @staticmethod
    def _classify_approximation(prim: Usd.Prim) -> str:
        # Primitive Gprim types.
        prim_type = prim.GetTypeName()
        if prim_type in _PRIM_TYPE_TO_APPROX:
            return _PRIM_TYPE_TO_APPROX[prim_type]

        # Physx convex schema by apiSchemas token (no PhysxSchema import).
        applied = set(prim.GetAppliedSchemas())
        if _PHYSX_CONVEX_HULL_SCHEMA in applied:
            return "convexHull"
        if _PHYSX_CONVEX_DECOMPOSITION_SCHEMA in applied:
            return "convexDecomposition"

        # UsdPhysics.MeshCollisionAPI approximation attribute.
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            mca = UsdPhysics.MeshCollisionAPI(prim)
            attr = mca.GetApproximationAttr()
            if attr and attr.HasAuthoredValue():
                v = attr.Get()
                if v:
                    return str(v)
            return "none"

        if prim_type == "Mesh":
            return "none"
        return "unknown"

    @staticmethod
    def _world_aabb(prim: Usd.Prim, bbox_cache: UsdGeom.BBoxCache):
        try:
            bbox = bbox_cache.ComputeWorldBound(prim)
            rng = bbox.ComputeAlignedRange()
            if rng.IsEmpty():
                return None, None
            mn = rng.GetMin()
            mx = rng.GetMax()
            return (
                (float(mn[0]), float(mn[1]), float(mn[2])),
                (float(mx[0]), float(mx[1]), float(mx[2])),
            )
        except Exception:                                       # pragma: no cover
            return None, None

    @staticmethod
    def _read_filter_group(prim: Usd.Prim) -> str | None:
        """Find ``physxCollision:filterGroup`` on the prim or nearest ancestor.

        Ancestor inheritance matters for referenced articulations (e.g.
        UR10e), where the cell tags ``<robot>/<link>/collisions`` at the
        container Xform and the per-shape collider prims sit one or two
        levels below. PhysX itself inherits the filter via collision-
        group membership; this lookup mirrors that for the validator.
        """
        cur: Usd.Prim | None = prim
        while cur and not cur.IsPseudoRoot():
            for attr_name in (
                "physxCollision:filterGroup",
                "physxCollisionFilterGroup",
            ):
                attr = cur.GetAttribute(attr_name)
                if attr and attr.HasAuthoredValue():
                    v = attr.Get()
                    if v:
                        return str(v)
            cur = cur.GetParent()
        return None

    @staticmethod
    def _read_mass_density_volume(
        prim: Usd.Prim,
    ) -> tuple[float | None, float | None, float | None]:
        mass: float | None = None
        density: float | None = None
        volume: float | None = None

        if prim.HasAPI(UsdPhysics.MassAPI):
            mass_api = UsdPhysics.MassAPI(prim)
            ma = mass_api.GetMassAttr()
            if ma and ma.HasAuthoredValue():
                mass = float(ma.Get())
            da = mass_api.GetDensityAttr()
            if da and da.HasAuthoredValue():
                density = float(da.Get())

        prim_type = prim.GetTypeName()
        if prim_type == "Cube":
            size = _safe_attr_float(prim, "size")
            if size is not None:
                volume = size ** 3
        elif prim_type == "Sphere":
            r = _safe_attr_float(prim, "radius")
            if r is not None:
                volume = (4.0 / 3.0) * 3.141592653589793 * r ** 3

        return mass, density, volume

    @staticmethod
    def _freeze_custom_data(prim: Usd.Prim) -> tuple[tuple[str, Any], ...]:
        cd = prim.GetCustomData() or {}
        out: list[tuple[str, Any]] = []
        if "static_collider" in cd:
            out.append(("static_collider", bool(cd["static_collider"])))
        av = cd.get("asset_validator", {})
        if isinstance(av, dict):
            for k in sorted(av):
                v = av[k]
                if isinstance(v, (str, bool, int, float)):
                    out.append((f"asset_validator.{k}", v))
        return tuple(out)


def _safe_attr_float(prim: Usd.Prim, attr_name: str) -> float | None:
    attr = prim.GetAttribute(attr_name)
    if attr and attr.HasAuthoredValue():
        try:
            return float(attr.Get())
        except Exception:                                       # pragma: no cover
            return None
    return None


def _is_physics_joint(prim: Usd.Prim) -> bool:
    """True if the prim's type is a UsdPhysics.Joint subclass.

    Used to filter joint prims out of rigid-body enumeration —
    articulation roots that sit on a fixed joint (the canonical
    UR10e pattern) shouldn't be counted as rigid bodies.
    """
    return prim.IsA(UsdPhysics.Joint)
