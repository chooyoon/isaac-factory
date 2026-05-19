"""PhysX-backed `ColliderInspector` — real implementation (Phase 1.B).

Replaces the Phase 1.A scaffold. Walks every prim with
:class:`UsdPhysics.CollisionAPI`, classifies the collider approximation,
computes the world-AABB via :class:`UsdGeom.BBoxCache`, resolves the
closest :class:`UsdPhysics.RigidBodyAPI` ancestor, captures any
`omni.physx` cooking-channel log messages, and emits
:class:`ColliderInfo` + :class:`RigidBodyInfo` records the
:class:`~asset_validator.ColliderValidator` consumes.

Runtime: **B** (Isaac Sim Kit Python 3.11). Requires
:class:`isaacsim.SimulationApp` to be running before this adapter is
constructed — the caller owns SimulationApp's lifecycle (per the
"no SimulationApp abstraction layer" constraint).

Cooking-error capture is **best-effort**:
  * The adapter subscribes to `omni.log` at construction.
  * Any message containing the substring ``"cook"`` is buffered.
  * For each collider whose Sdf path appears as a substring in a
    buffered message, that message becomes `cooking_error`.
  * If `omni.log`'s API surface differs from what we know about
    (Kit version churn), subscription silently fails and
    `cooking_error` is `None` for every collider. The validator
    simply doesn't emit `COLLIDER.COOKING_FAILED` in that case.
"""

from __future__ import annotations

from typing import Any, Iterable

# Guarded imports — module loads in Runtime A too (for type checkers).
try:
    from pxr import Gf, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics  # type: ignore
    _HAS_PXR = True
except ImportError:                                            # pragma: no cover
    _HAS_PXR = False

try:
    import omni.physx                                          # noqa: F401
    _HAS_OMNI_PHYSX = True
except ImportError:
    _HAS_OMNI_PHYSX = False

try:
    import omni.log                                            # type: ignore
    _HAS_OMNI_LOG = True
except ImportError:                                            # pragma: no cover
    _HAS_OMNI_LOG = False

from ..core.collider import ColliderInfo, ColliderInspector, RigidBodyInfo


_BOOTSTRAP_HINT = (
    "PhysXColliderInspector requires Isaac Sim Kit Python (Runtime B). "
    "Bootstrap via:\n"
    "    from isaacsim import SimulationApp\n"
    "    app = SimulationApp({'headless': True})\n"
    "before constructing PhysXColliderInspector. See docs/runtime_b_bootstrap.md."
)


# Map primitive-collider USD prim type → canonical approximation string
# expected by ColliderValidator.dynamic_allowed_approximations.
_PRIM_TYPE_TO_APPROX: dict[str, str] = {
    "Cube":     "box",
    "Sphere":   "sphere",
    "Capsule":  "capsule",
    "Cylinder": "cylinder",
}

# AABB cache scopes the validator wants — `default` and `render`.
_DEFAULT_PURPOSES: tuple = ()  # populated lazily in __init__ once pxr is in scope


class PhysXColliderInspector:
    """Real ColliderInspector backed by `omni.physx` + `pxr.UsdPhysics`."""

    name = "physx_collider_inspector"
    runtime = "B"

    def __init__(
        self,
        stage,
        *,
        capture_cooking_logs: bool = True,
    ):
        if not _HAS_OMNI_PHYSX:
            raise RuntimeError(_BOOTSTRAP_HINT)
        if not _HAS_PXR:
            raise RuntimeError(
                "pxr unavailable — Kit Python should have it bundled."
            )
        if not isinstance(stage, Usd.Stage):
            raise TypeError(
                f"PhysXColliderInspector(stage=...) requires a pxr.Usd.Stage; "
                f"got {type(stage).__name__}"
            )

        self._stage = stage
        self._cooking_messages: list[str] = []
        self._log_handle = None

        # Best-effort cooking-log subscription. If the omni.log API
        # surface doesn't match what we expect, we silently fall back
        # to no cooking diagnostics.
        if capture_cooking_logs and _HAS_OMNI_LOG:
            self._setup_log_capture()

    # ===================================================== Protocol ==

    def iter_colliders(self) -> Iterable[ColliderInfo]:
        rb_paths = self._rigid_body_paths()
        bbox_cache = UsdGeom.BBoxCache(
            time=Usd.TimeCode.Default(),
            includedPurposes=[UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
            useExtentsHint=True,
        )

        # Traverse instance proxies — NVIDIA's UR10e (and most referenced
        # articulations) author per-link colliders inside instanceable
        # subtrees for memory efficiency. Standard Traverse skips them
        # and the validator would spuriously emit
        # RIGID_BODY_WITHOUT_COLLIDER for every link.
        prims = [
            p for p in self._traverse_with_instances()
            if p.IsActive() and p.HasAPI(UsdPhysics.CollisionAPI)
        ]
        prims.sort(key=lambda p: str(p.GetPath()))

        for prim in prims:
            yield self._build_collider_info(prim, rb_paths, bbox_cache)

    def iter_rigid_bodies(self) -> Iterable[RigidBodyInfo]:
        # Articulation roots can sit on either a rigid-body link OR a
        # fixed-joint anchor (canonical UR10e pattern places the
        # ArticulationRootAPI on /<robot>/root_joint, a PhysicsFixedJoint).
        # Joint prims aren't rigid bodies — exclude them so the
        # validator's §3.2 check doesn't false-positive.
        prims = [
            p for p in self._traverse_with_instances()
            if p.IsActive()
            and (p.HasAPI(UsdPhysics.RigidBodyAPI)
                 or p.HasAPI(UsdPhysics.ArticulationRootAPI))
            and not p.IsA(UsdPhysics.Joint)
        ]
        prims.sort(key=lambda p: str(p.GetPath()))

        for prim in prims:
            yield self._build_rb_info(prim)

    def _traverse_with_instances(self) -> Iterable["Usd.Prim"]:
        return Usd.PrimRange.Stage(self._stage, Usd.TraverseInstanceProxies())

    # =================================================== lifecycle ==

    def close(self) -> None:
        """Unsubscribe from the omni.log consumer (best-effort)."""
        if self._log_handle is not None:
            try:
                self._log_handle.unsubscribe()
            except Exception:                                   # pragma: no cover
                pass
            self._log_handle = None

    def __enter__(self) -> "PhysXColliderInspector":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):                                          # pragma: no cover
        try:
            self.close()
        except Exception:
            pass

    # ===================================================== internal ==

    def _setup_log_capture(self) -> None:
        """Subscribe to omni.log. Different Kit versions expose different
        method names, so we try a couple in order."""
        try:
            log = omni.log.get_log()
        except Exception:                                       # pragma: no cover
            return

        for method in ("add_log_message_consumer", "add_message_consumer"):
            fn = getattr(log, method, None)
            if fn is None:
                continue
            try:
                self._log_handle = fn(self._on_log_message)
                return
            except Exception:                                   # pragma: no cover
                continue
        # All known method names failed → silently degrade.

    def _on_log_message(self, *args, **kwargs) -> None:
        """Capture cooking-related messages. Args vary by Kit version; we
        scan all string-valued args for the heuristic."""
        for a in args:
            if isinstance(a, str) and "cook" in a.lower():
                self._cooking_messages.append(a)
                return
            if isinstance(a, str) and "physx" in a.lower() and (
                "error" in a.lower() or "fail" in a.lower()
            ):
                self._cooking_messages.append(a)
                return

    def _rigid_body_paths(self) -> set[str]:
        """Set of paths of every UsdPhysics.RigidBodyAPI prim — used for
        ancestor lookup when building collider records."""
        return {
            str(p.GetPath()) for p in self._traverse_with_instances()
            if p.IsActive() and p.HasAPI(UsdPhysics.RigidBodyAPI)
        }

    def _build_collider_info(
        self,
        prim: "Usd.Prim",
        rb_paths: set[str],
        bbox_cache: "UsdGeom.BBoxCache",
    ) -> ColliderInfo:
        path = str(prim.GetPath())
        rigid_body_path  = self._find_rb_path(prim, rb_paths)
        approximation    = self._classify_approximation(prim)
        aabb_min, aabb_max = self._world_aabb(prim, bbox_cache)
        collision_group  = self._read_filter_group(prim)
        cooking_error    = self._cooking_error_for(path)
        custom_data      = self._freeze_custom_data(prim)
        # Convex-decomposition runtime hull count requires post-cook
        # PhysX query; left None in v1 (so the validator does not emit
        # CONVEX_DECOMP_HULL_LIMIT). Documented in
        # docs/physx_collider_inspector.md §5.
        hull_count: int | None = None

        return ColliderInfo(
            path=path,
            approximation=approximation,
            rigid_body_path=rigid_body_path,
            collider_aabb_min=aabb_min,
            collider_aabb_max=aabb_max,
            # Visual = collider AABB for the implementations we ship —
            # accurate for primitives, conservative for meshes. Refining
            # this for cooked-mesh hulls is a follow-up.
            visual_aabb_min=aabb_min,
            visual_aabb_max=aabb_max,
            convex_decomposition_hull_count=hull_count,
            cooking_error=cooking_error,
            collision_group=collision_group,
            custom_data=custom_data,
        )

    def _build_rb_info(self, prim: "Usd.Prim") -> RigidBodyInfo:
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
            path=path,
            is_kinematic=kinematic,
            is_articulation_root=art_root,
            mass=mass,
            density=density,
            volume_m3=volume,
            custom_data=custom_data,
        )

    @staticmethod
    def _find_rb_path(prim: "Usd.Prim", rb_paths: set[str]) -> str | None:
        """Closest RigidBody ancestor (or the prim itself)."""
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
    def _classify_approximation(prim: "Usd.Prim") -> str:
        """Return the canonical approximation string.

        - Primitive Gprim types map directly (Cube → 'box', etc.).
        - Meshes with PhysxConvexHullCollisionAPI → 'convexHull'.
        - Meshes with PhysxConvexDecompositionCollisionAPI → 'convexDecomposition'.
        - Meshes with UsdPhysics.MeshCollisionAPI take the value of its
          'approximation' attribute (defaults to 'none' if unauthored).
        - Otherwise 'unknown'.
        """
        prim_type = prim.GetTypeName()
        if prim_type in _PRIM_TYPE_TO_APPROX:
            return _PRIM_TYPE_TO_APPROX[prim_type]
        if prim.HasAPI(PhysxSchema.PhysxConvexHullCollisionAPI):
            return "convexHull"
        if prim.HasAPI(PhysxSchema.PhysxConvexDecompositionCollisionAPI):
            return "convexDecomposition"
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
    def _world_aabb(prim: "Usd.Prim", bbox_cache: "UsdGeom.BBoxCache"):
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
    def _read_filter_group(prim: "Usd.Prim") -> str | None:
        for attr_name in (
            "physxCollision:filterGroup",
            "physxCollisionFilterGroup",
        ):
            attr = prim.GetAttribute(attr_name)
            if attr and attr.HasAuthoredValue():
                v = attr.Get()
                if v:
                    return str(v)
        return None

    @staticmethod
    def _read_mass_density_volume(
        prim: "Usd.Prim",
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

        # Closed-form volume for the cheap primitives. Anything more
        # complex (mesh, capsule, cylinder) we leave as None — the
        # validator's MASS_DENSITY_CONFLICT check needs all three of
        # mass / density / volume, and skips gracefully on None.
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

    def _cooking_error_for(self, path: str) -> str | None:
        """First captured message whose text mentions ``path``, truncated
        to 200 chars."""
        for msg in self._cooking_messages:
            if path in msg:
                return msg.strip()[:200]
        return None

    @staticmethod
    def _freeze_custom_data(prim: "Usd.Prim") -> tuple[tuple[str, Any], ...]:
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


def _safe_attr_float(prim: "Usd.Prim", attr_name: str) -> float | None:
    attr = prim.GetAttribute(attr_name)
    if attr and attr.HasAuthoredValue():
        try:
            return float(attr.Get())
        except Exception:                                       # pragma: no cover
            return None
    return None
