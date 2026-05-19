"""USD-only implementation of :class:`GroundingInspector`.

Produces a :class:`GroundingProbe` for every prim that carries
``customData["asset_validator"]["grounded"]`` by performing a downward
**AABB-vs-vertical-ray** intersection against every other geometric prim
on the stage.

This is a *static geometric* check — it does not require PhysX or Kit,
and is the runtime backing of the static-grounding pipeline described in
[docs/scene_validation_workflow.md §3 step 4](../../docs/scene_validation_workflow.md).
The pxr dependency is `usd-core 26.3` (Runtime A's conda env), so unit
tests can run in the `research` profile.

Algorithm
---------

For each candidate prim C:
  1. Compute C's world-space AABB via :class:`UsdGeom.BBoxCache`.
  2. Take the ray origin from the AABB's **top-centre** (x, y, max_z).
     Casting from the top ensures buried candidates can still find the
     support whose surface intersects their volume.
  3. For every other geometric prim S that is not C and not a descendant
     of C:
       a. Compute S's world AABB.
       b. Project the ray onto S: skip if (cx, cy) is outside the AABB's
          XY projection.
       c. If S's AABB max_z ≤ origin_z, S is a hit candidate; record
          (S.path, top_z).
  4. Pick the hit with the **largest top_z** (closest below the origin).
  5. If no hit is within ``search_distance_m`` below the origin, emit a
     probe with ``support_hit_path=None`` — the validator will report
     ``GROUNDING.NO_SUPPORT_FOUND``.

The signed gap returned by :attr:`GroundingProbe.gap_m` is then
``aabb_bottom_z - support_hit_z``; positive → floating, negative →
buried, near-zero → resting. Reporting the bottom (not the ray origin)
is intentional: the bottom is what physically touches the support, so
the signed gap is meaningful regardless of where the ray started.

Determinism
-----------

Candidates are sorted by prim path before emission. Tied hits are broken
by prim path (lexicographic). Same input stage → same probe sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pxr import Gf, Sdf, Usd, UsdGeom

from ..core.grounding import GroundingInspector, GroundingProbe


_VALID_INTENTS = {"true", "false", "kinematic"}
_DEFAULT_SEARCH_DISTANCE_M = 10.0
# `purpose` tokens included when computing world AABBs. Default + render
# match what would actually be visible/collidable in a sim.
_DEFAULT_PURPOSES = (UsdGeom.Tokens.default_, UsdGeom.Tokens.render)


@dataclass
class UsdGroundingInspector:
    """:class:`GroundingInspector` backed by raw USD geometry.

    Parameters
    ----------
    stage
        The opened :class:`Usd.Stage` to inspect.
    search_distance_m
        Maximum vertical distance below the candidate to search for a
        support. Beyond this, the probe reports no support.
    bbox_purposes
        Which `purpose` tokens the BBox cache should consider. Default
        is ``("default", "render")``.
    """

    stage: Usd.Stage
    search_distance_m: float = _DEFAULT_SEARCH_DISTANCE_M
    bbox_purposes: tuple = _DEFAULT_PURPOSES

    # ------------------------------------------------------- public API --

    def iter_grounding_probes(self) -> Iterable[GroundingProbe]:
        bbox_cache = UsdGeom.BBoxCache(
            time=Usd.TimeCode.Default(),
            includedPurposes=list(self.bbox_purposes),
            useExtentsHint=True,
        )

        # 1. Enumerate candidates + support pool in one pass.
        # Candidates: any imageable prim with grounding intent (typically a
        #     Cube/Mesh, but a tagged Xform container is allowed too).
        # Support pool: only concrete `Gprim` geometry (Cube, Sphere, Mesh,
        #     etc.). Generic Xform containers are excluded — they
        #     aggregate child AABBs and would otherwise be selected as
        #     spurious "supports".
        candidates: list[Usd.Prim] = []
        all_geo: list[Usd.Prim] = []
        for prim in self.stage.Traverse():
            if not prim.IsActive():
                continue
            if not prim.IsA(UsdGeom.Imageable):
                continue
            if prim.IsA(UsdGeom.Gprim):
                all_geo.append(prim)
            if self._grounding_intent(prim) is not None:
                candidates.append(prim)

        # Deterministic candidate order.
        candidates.sort(key=lambda p: str(p.GetPath()))

        # 2. Pre-compute world AABBs once (cache amortises traversal).
        aabbs: dict[Sdf.Path, Gf.Range3d | None] = {}
        for prim in all_geo:
            aabbs[prim.GetPath()] = self._world_aabb(prim, bbox_cache)
        # Candidates may be Xform wrappers whose AABB aggregates the
        # children — BBoxCache.ComputeWorldBound walks descendants, so a
        # single call gives the correct world bound for an Xform with a
        # /visual + /collider sibling pair.
        for cand in candidates:
            if cand.GetPath() not in aabbs:
                aabbs[cand.GetPath()] = self._world_aabb(cand, bbox_cache)

        # 3. Per candidate, raycast and emit one probe.
        for cand in candidates:
            yield self._build_probe(cand, all_geo, aabbs)

    # ----------------------------------------------------- per candidate --

    def _build_probe(
        self,
        cand: Usd.Prim,
        all_geo: list[Usd.Prim],
        aabbs: dict[Sdf.Path, Gf.Range3d | None],
    ) -> GroundingProbe:
        cand_path = str(cand.GetPath())
        intent = self._grounding_intent(cand)
        cand_aabb = aabbs.get(cand.GetPath())
        if cand_aabb is None or cand_aabb.IsEmpty():
            # Degenerate candidate — emit with NaN-ish positioning so the
            # validator reports NO_SUPPORT_FOUND.
            return GroundingProbe(
                path=cand_path,
                grounded_intent=intent,
                aabb_bottom_z_m=float("nan"),
                support_hit_path=None,
                support_hit_z_m=None,
            )

        min_pt = cand_aabb.GetMin()
        max_pt = cand_aabb.GetMax()
        cx = (min_pt[0] + max_pt[0]) * 0.5
        cy = (min_pt[1] + max_pt[1]) * 0.5
        cand_bottom_z = min_pt[2]
        cand_top_z    = max_pt[2]

        # Ray origin is the AABB top-centre. Casting from the top ensures
        # that a support intersecting the candidate from below (buried
        # case) is still found, because its top_z lies between the
        # candidate's bottom and top.
        ray_origin_z = cand_top_z
        min_search_z = ray_origin_z - self.search_distance_m
        cand_descendants = self._descendants_paths(cand)

        best_top_z: float | None = None
        best_path: str | None = None

        for sprim in all_geo:
            spath = sprim.GetPath()
            spath_str = str(spath)
            if spath == cand.GetPath():
                continue
            if spath_str in cand_descendants:
                continue

            saabb = aabbs.get(spath)
            if saabb is None or saabb.IsEmpty():
                continue

            smin = saabb.GetMin()
            smax = saabb.GetMax()
            # XY projection test
            if not (smin[0] <= cx <= smax[0]):
                continue
            if not (smin[1] <= cy <= smax[1]):
                continue
            # Must be at or below ray origin
            top_z = smax[2]
            if top_z > ray_origin_z:
                continue
            if top_z < min_search_z:
                continue

            # Closest hit going downward = largest top_z.
            if best_top_z is None or top_z > best_top_z or (
                top_z == best_top_z and (best_path is None or spath_str < best_path)
            ):
                best_top_z = top_z
                best_path = spath_str

        return GroundingProbe(
            path=cand_path,
            grounded_intent=intent,
            aabb_bottom_z_m=float(cand_bottom_z),
            support_hit_path=best_path,
            support_hit_z_m=(float(best_top_z) if best_top_z is not None else None),
        )

    # ----------------------------------------------------------- helpers --

    @staticmethod
    def _world_aabb(prim: Usd.Prim, bbox_cache: UsdGeom.BBoxCache) -> Gf.Range3d | None:
        try:
            bbox = bbox_cache.ComputeWorldBound(prim)
        except Exception:
            return None
        rng = bbox.ComputeAlignedRange()
        if rng.IsEmpty():
            return None
        return rng

    @staticmethod
    def _grounding_intent(prim: Usd.Prim) -> str | None:
        """Return the prim's grounded-intent string, or None if untagged.

        Lookups inspect ``customData["asset_validator"]["grounded"]``.
        Accepted values: ``"true"``, ``"false"``, ``"kinematic"``.
        Anything else (or an invalid value) returns the raw string so
        :class:`GroundingValidator` can emit ``NO_INTENT_TAG``.
        """
        custom = prim.GetCustomData()
        if not custom:
            return None
        av = custom.get("asset_validator")
        if not isinstance(av, dict):
            return None
        v = av.get("grounded")
        if v is None:
            return None
        # USD stores tokens / strings / bools — normalise to lowercase string.
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v).lower()

    @staticmethod
    def _descendants_paths(prim: Usd.Prim) -> set[str]:
        """All strict-descendant paths of ``prim`` (excludes self)."""
        return {str(d.GetPath()) for d in _iter_descendants(prim)}


def _iter_descendants(prim: Usd.Prim) -> Iterable[Usd.Prim]:
    """Yield every strict descendant of ``prim`` (depth-first)."""
    stack = list(prim.GetChildren())
    while stack:
        cur = stack.pop()
        yield cur
        stack.extend(cur.GetChildren())


# Structural Protocol assertion (caught at import time on mismatch).
_: GroundingInspector = UsdGroundingInspector(stage=Usd.Stage.CreateInMemory())
