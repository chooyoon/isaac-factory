"""USD-only implementation of :class:`StageInspector`.

Walks every active :class:`UsdGeom.Xformable` prim, extracts its xformOps
into :class:`TransformOp` records, resolves the prim's `xformOpOrder`
against the actually-present ops (to flag corruption), and packages the
result into :class:`XformablePrim` records that the validator consumes.

The pxr dependency is `usd-core 26.3` (Runtime A's conda env). The
adapter detects physics schemas if `pxr.UsdPhysics` is importable, but
gracefully degrades if not — `is_likely_dynamic` and `has_collision_api`
default to ``False`` rather than failing the import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pxr import Gf, Sdf, Usd, UsdGeom

# UsdPhysics is part of OpenUSD but not used in every workflow. Optional.
try:
    from pxr import UsdPhysics  # noqa: F401
    _HAS_USDPHYSICS = True
except ImportError:                      # pragma: no cover
    _HAS_USDPHYSICS = False

from ..core.stage import StageInspector, TransformOp, XformablePrim


# Identity-default values per canonical op_type. Used when an xformOp is
# present in `xformOpOrder` but has no authored value — USD's behaviour
# is to fall back to identity; the validator mirrors that. Industrial
# assets like NVIDIA's UR10e author this pattern intentionally
# (e.g. ee_link has xformOp:rotateZYX in order with no value).
_DEFAULT_BY_OP_TYPE: dict[str, tuple[float, ...]] = {
    "translate":        (0.0, 0.0, 0.0),
    "scale":            (1.0, 1.0, 1.0),
    "rotate_axis":      (0.0,),
    "rotate_euler":     (0.0, 0.0, 0.0),
    "rotate_quat":      (1.0, 0.0, 0.0, 0.0),
    "transform_matrix": (1.0, 0.0, 0.0, 0.0,
                         0.0, 1.0, 0.0, 0.0,
                         0.0, 0.0, 1.0, 0.0,
                         0.0, 0.0, 0.0, 1.0),
}


# UsdGeom.XformOp.Type → our canonical op_type string.
_OP_TYPE_MAP = {
    UsdGeom.XformOp.TypeTranslate: "translate",
    UsdGeom.XformOp.TypeScale:     "scale",
    UsdGeom.XformOp.TypeRotateX:   "rotate_axis",
    UsdGeom.XformOp.TypeRotateY:   "rotate_axis",
    UsdGeom.XformOp.TypeRotateZ:   "rotate_axis",
    UsdGeom.XformOp.TypeRotateXYZ: "rotate_euler",
    UsdGeom.XformOp.TypeRotateXZY: "rotate_euler",
    UsdGeom.XformOp.TypeRotateYXZ: "rotate_euler",
    UsdGeom.XformOp.TypeRotateYZX: "rotate_euler",
    UsdGeom.XformOp.TypeRotateZXY: "rotate_euler",
    UsdGeom.XformOp.TypeRotateZYX: "rotate_euler",
    UsdGeom.XformOp.TypeOrient:    "rotate_quat",
    UsdGeom.XformOp.TypeTransform: "transform_matrix",
}


@dataclass
class UsdStageInspector:
    """:class:`StageInspector` backed by raw USD geometry.

    Parameters
    ----------
    stage
        The opened :class:`Usd.Stage` to inspect.
    time_code
        TimeCode at which to sample xformOp values. Default is
        ``Usd.TimeCode.Default()`` — the "no-animation" sample.
    """

    stage: Usd.Stage
    time_code: Usd.TimeCode = Usd.TimeCode.Default()

    def iter_xformable_prims(self) -> Iterable[XformablePrim]:
        prims = [
            p for p in self.stage.Traverse()
            if p.IsActive() and p.IsA(UsdGeom.Xformable)
        ]
        prims.sort(key=lambda p: str(p.GetPath()))

        for prim in prims:
            yield self._build_record(prim)

    # ============================================================ helpers ==

    def _build_record(self, prim: Usd.Prim) -> XformablePrim:
        xformable = UsdGeom.Xformable(prim)
        ops_in_order = xformable.GetOrderedXformOps()
        resolved_names = {op.GetOpName() for op in ops_in_order}

        # Detect unresolved xformOpOrder entries (hierarchy corruption).
        order_attr = xformable.GetXformOpOrderAttr()
        unresolved: tuple[str, ...] = ()
        if order_attr and order_attr.HasAuthoredValue():
            raw_order = order_attr.Get() or []
            unresolved = tuple(n for n in raw_order if n not in resolved_names)

        op_records = tuple(self._build_op(op) for op in ops_in_order)

        parent = prim.GetParent()
        parent_path = str(parent.GetPath()) if parent and parent.GetPath() != Sdf.Path("/") else None

        # Custom data (we only need `mirror` and `asset_validator.is_dynamic`).
        custom = prim.GetCustomData() or {}
        is_mirror = bool(custom.get("mirror", False))
        av_dict = custom.get("asset_validator") or {}
        explicit_dynamic = bool(av_dict.get("is_dynamic", False))

        # Physics-derived signals.
        has_collision = self._has_collision_api(prim)
        physics_dynamic = self._has_dynamic_physics_api(prim)
        is_dynamic = explicit_dynamic or physics_dynamic

        return XformablePrim(
            path=str(prim.GetPath()),
            parent_path=parent_path,
            is_active=prim.IsActive(),
            has_collision_api=has_collision,
            is_likely_dynamic=is_dynamic,
            ops=op_records,
            xform_op_order_unresolved=unresolved,
            custom_data=self._freeze_relevant_custom_data(is_mirror, av_dict),
        )

    def _build_op(self, op: UsdGeom.XformOp) -> TransformOp:
        op_name = op.GetOpName()
        op_type = _OP_TYPE_MAP.get(op.GetOpType(), "transform_matrix")
        raw = op.Get(self.time_code)
        values = self._flatten_value(raw, op_type)
        ts_count = op.GetAttr().GetNumTimeSamples()
        return TransformOp(
            op_name=op_name,
            op_type=op_type,
            values=values,
            time_sample_count=int(ts_count),
        )

    # --------------------------------------------------------------- value --

    @staticmethod
    def _flatten_value(raw: Any, op_type: str) -> tuple[float, ...]:
        """Flatten Gf type into a tuple of floats matching the validator's contract.

        - translate / scale / rotate_euler : Vec3d → (x, y, z)
        - rotate_axis                       : scalar → (angle,)
        - rotate_quat                       : Quatd → (w, x, y, z)
        - transform_matrix                  : Matrix4d → 16 floats row-major
        """
        if raw is None:
            # Op listed in xformOpOrder without an authored value — USD
            # treats this as identity-default; we synthesise the
            # correct-arity tuple so the validator's numeric checks see
            # well-formed data instead of (spuriously) flagging
            # OP_VALUE_COUNT_MISMATCH.
            return _DEFAULT_BY_OP_TYPE.get(op_type, ())

        if op_type in {"translate", "scale", "rotate_euler"}:
            return (float(raw[0]), float(raw[1]), float(raw[2]))

        if op_type == "rotate_axis":
            return (float(raw),)

        if op_type == "rotate_quat":
            return (
                float(raw.GetReal()),
                float(raw.GetImaginary()[0]),
                float(raw.GetImaginary()[1]),
                float(raw.GetImaginary()[2]),
            )

        if op_type == "transform_matrix":
            # GfMatrix4d is row-major; access via m[i][j].
            return tuple(float(raw[i][j]) for i in range(4) for j in range(4))

        # Unknown op type — defensive fallback
        return tuple(float(v) for v in raw) if hasattr(raw, "__iter__") else (float(raw),)

    # ------------------------------------------------------------- physics --

    @staticmethod
    def _has_collision_api(prim: Usd.Prim) -> bool:
        if not _HAS_USDPHYSICS:
            return False
        from pxr import UsdPhysics
        return prim.HasAPI(UsdPhysics.CollisionAPI)

    @staticmethod
    def _has_dynamic_physics_api(prim: Usd.Prim) -> bool:
        if not _HAS_USDPHYSICS:
            return False
        from pxr import UsdPhysics
        return (
            prim.HasAPI(UsdPhysics.RigidBodyAPI)
            or prim.HasAPI(UsdPhysics.ArticulationRootAPI)
        )

    @staticmethod
    def _freeze_relevant_custom_data(
        is_mirror: bool, av_dict: dict,
    ) -> tuple[tuple[str, Any], ...]:
        """Snapshot the small slice of customData the validator looks at."""
        out: list[tuple[str, Any]] = []
        if is_mirror:
            out.append(("mirror", True))
        # av_dict already validated as dict. Keep only flat scalar entries
        # the validator might consume.
        for k, v in sorted(av_dict.items()):
            if isinstance(v, (str, bool, int, float)):
                out.append((f"asset_validator.{k}", v))
        return tuple(out)


# Structural Protocol assertion (caught at import time).
_: StageInspector = UsdStageInspector(stage=Usd.Stage.CreateInMemory())
