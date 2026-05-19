"""Stage-inspection abstraction.

The validator depends only on the :class:`StageInspector` Protocol and the
two data classes below — never on `pxr` directly. The real implementation
will live in `adapters/usd_adapter.py` (deferred). Tests provide an
in-memory mock that produces lists of :class:`XformablePrim`.

`TransformOp.values` is a flat tuple of floats; the layout depends on
`op_type`:

  ====================  ========================================
  op_type               values
  ====================  ========================================
  translate             (tx, ty, tz)
  scale                 (sx, sy, sz)
  rotate_quat           (w, x, y, z)                  (USD orient)
  rotate_euler          (rx, ry, rz) in degrees
  rotate_axis           (angle,)        single-axis  (degrees)
  transform_matrix      16 floats, row-major          (USD GfMatrix4d)
  ====================  ========================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class TransformOp:
    op_name: str                              # e.g. "xformOp:translate"
    op_type: str                              # canonical type, see module docstring
    values:  tuple[float, ...]
    time_sample_count: int = 0

    @property
    def is_time_sampled(self) -> bool:
        return self.time_sample_count > 0


@dataclass(frozen=True)
class XformablePrim:
    path:                       str
    parent_path:                str | None = None
    is_active:                  bool       = True
    has_collision_api:          bool       = False
    is_likely_dynamic:          bool       = False
    ops:                        tuple[TransformOp, ...] = ()
    xform_op_order_unresolved:  tuple[str, ...] = ()
    custom_data:                tuple[tuple[str, Any], ...] = ()

    def custom_data_dict(self) -> dict[str, Any]:
        return dict(self.custom_data)

    def is_mirror(self) -> bool:
        return bool(self.custom_data_dict().get("mirror", False))


class StageInspector(Protocol):
    """Anything that can enumerate the xformable prims of a stage."""

    def iter_xformable_prims(self) -> Iterable[XformablePrim]:
        ...
