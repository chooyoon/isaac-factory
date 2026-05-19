"""Grounding data model.

The validator consumes a list of pre-computed downward-raycast results. The
real adapter (deferred) runs the raycasts via either PhysX scene queries or
USD geometry intersection; the mock used in tests fabricates results
directly. Either way, the validator works only on the data below.

`GroundingProbe.support_hit_z_m` is the world-space Z of the surface hit
by a downward ray from inside the object. The gap is computed as
``aabb_bottom_z_m - support_hit_z_m`` and interpreted:

  ====================  ==========================================
  gap                   meaning
  ====================  ==========================================
  ~ 0                   resting on support
  > tolerance           floating in air
  < -tolerance          buried (penetrating through the support)
  ====================  ==========================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class GroundingProbe:
    """One grounding query and its raycast result."""

    path:             str
    grounded_intent:  str | None                            # "true" | "false" | "kinematic" | None
    aabb_bottom_z_m:  float                                 # world-space Z of object's AABB bottom

    support_hit_path: str | None       = None               # prim hit by the downward ray, or None
    support_hit_z_m:  float | None     = None               # world-space Z of the hit point
    custom_data:      tuple[tuple[str, Any], ...] = ()

    @property
    def gap_m(self) -> float | None:
        """Signed distance from the object's AABB bottom to the support.

        ``None`` if the raycast missed (no support found within the
        inspector's search distance).
        """
        if self.support_hit_z_m is None:
            return None
        return self.aabb_bottom_z_m - self.support_hit_z_m


class GroundingInspector(Protocol):
    """Anything that can enumerate grounding probes for a stage.

    Real implementation (deferred) emits one probe per "grounded-intent"
    rigid body, running a downward raycast from a point inside the body
    and reporting the result.
    """

    def iter_grounding_probes(self) -> Iterable[GroundingProbe]:
        ...
