"""ColliderValidator — static checks on USD physics collision schemas.

Covers acceptance §3 rules 3.1–3.7, 3.9, 3.10 (rule 3.8 is collapsed into
3.1 — same condition, different severity). Adds two "unstable collider
geometry" heuristics for the user's open-ended item.

Pure-logic implementation: USD / PhysX access is abstracted through
:class:`ColliderInspector`, so this module is importable and testable
without Isaac Sim Kit Python.
"""

from __future__ import annotations

from typing import Mapping

from ..core.collider        import ColliderInfo, RigidBodyInfo
from ..core.context         import ValidationContext
from ..core.issue           import Issue
from ..core.severity        import Severity
from ..core.validator_base  import Validator


# Stable issue codes — referenced by Sprint Contracts and CI gates.
CODE_NO_RIGID_BODY_ANCESTOR  = "COLLIDER.NO_RIGID_BODY_ANCESTOR"   # §3.1
CODE_RIGID_BODY_WITHOUT_COLL = "COLLIDER.RIGID_BODY_WITHOUT_COLLIDER"  # §3.2
CODE_MESH_ON_DYNAMIC         = "COLLIDER.MESH_ON_DYNAMIC"           # §3.3
CODE_CONVEX_DECOMP_HULL_LIM  = "COLLIDER.CONVEX_DECOMP_HULL_LIMIT"  # §3.4
CODE_AABB_MISMATCH           = "COLLIDER.AABB_MISMATCH"             # §3.5
CODE_MISSING_COLLISION_GROUP = "COLLIDER.MISSING_COLLISION_GROUP"   # §3.6
CODE_COOKING_FAILED          = "COLLIDER.COOKING_FAILED"            # §3.7
CODE_MASS_OUT_OF_RANGE       = "COLLIDER.MASS_OUT_OF_RANGE"         # §3.9
CODE_MASS_DENSITY_CONFLICT   = "COLLIDER.MASS_DENSITY_CONFLICT"     # §3.10
CODE_DEGENERATE_AABB         = "COLLIDER.DEGENERATE_AABB"           # stability
CODE_EXTREME_ASPECT_RATIO    = "COLLIDER.EXTREME_ASPECT_RATIO"      # stability
CODE_NO_COLLIDER_INSPECTOR   = "COLLIDER.NO_COLLIDER_INSPECTOR"     # missing dep


class ColliderValidator(Validator):
    name  = "collider"
    phase = "static"

    # ============================================================= run ==

    def run(self, ctx: ValidationContext) -> list[Issue]:
        ins = ctx.collider_inspector
        if ins is None:
            return [self._no_inspector_issue()]

        # Deterministic ordering.
        rigid_bodies = sorted(ins.iter_rigid_bodies(), key=lambda r: r.path)
        colliders    = sorted(ins.iter_colliders(),    key=lambda c: c.path)
        rb_by_path: Mapping[str, RigidBodyInfo] = {rb.path: rb for rb in rigid_bodies}

        # Pre-bucket: which colliders belong to which rigid body.
        rb_collider_counts: dict[str, int] = {rb.path: 0 for rb in rigid_bodies}
        for c in colliders:
            if c.rigid_body_path is not None and c.rigid_body_path in rb_collider_counts:
                rb_collider_counts[c.rigid_body_path] += 1

        issues: list[Issue] = []

        # §3.2 — rigid bodies without colliders
        for rb in rigid_bodies:
            if rb_collider_counts.get(rb.path, 0) == 0:
                issues.append(self._rb_without_collider_issue(rb))

        # Per-collider checks
        for c in colliders:
            issues.extend(self._check_collider(c, rb_by_path))

        # Per-rigid-body mass checks
        for rb in rigid_bodies:
            issues.extend(self._check_rigid_body(rb))

        issues.sort(key=Issue.sort_key)
        return issues

    # ================================================ per-collider ==

    def _check_collider(
        self,
        c: ColliderInfo,
        rb_by_path: Mapping[str, RigidBodyInfo],
    ) -> list[Issue]:
        out: list[Issue] = []
        t = self.criteria.collider

        rb = rb_by_path.get(c.rigid_body_path) if c.rigid_body_path else None

        # §3.1 — orphan collider
        if rb is None and not c.is_static_collider_flagged():
            out.append(Issue.create(
                code=CODE_NO_RIGID_BODY_ANCESTOR,
                severity=Severity.FAIL,
                message=(
                    f"Collider '{c.path}' has no rigid-body ancestor and is not "
                    f"flagged `customData['static_collider']=True`."
                ),
                prim_paths=(c.path,),
                validator=self.name,
            ))

        # §3.3 — mesh approximation on dynamic body
        if rb is not None and not rb.is_kinematic:
            if c.approximation not in t.dynamic_allowed_approximations:
                out.append(Issue.create(
                    code=CODE_MESH_ON_DYNAMIC,
                    severity=Severity.FAIL,
                    message=(
                        f"Collider '{c.path}' uses approximation "
                        f"'{c.approximation}' on dynamic rigid body '{rb.path}'. "
                        f"Allowed for dynamic bodies: "
                        f"{', '.join(t.dynamic_allowed_approximations)}."
                    ),
                    prim_paths=(c.path, rb.path),
                    validator=self.name,
                ))

        # §3.4 — convex decomposition hull limit
        if (c.approximation == "convexDecomposition"
                and c.convex_decomposition_hull_count is not None):
            hulls = c.convex_decomposition_hull_count
            if hulls > t.convex_decomp_hull_fail:
                out.append(self._hull_count_issue(c, hulls, Severity.FAIL, t.convex_decomp_hull_fail))
            elif hulls > t.convex_decomp_hull_warn:
                out.append(self._hull_count_issue(c, hulls, Severity.WARN, t.convex_decomp_hull_warn))

        # §3.5 — AABB mismatch (collider vs visual)
        ratios = self._aabb_axis_ratios(c)
        if ratios is not None:
            max_ratio = max(ratios)
            if max_ratio > t.aabb_ratio_max:
                out.append(Issue.create(
                    code=CODE_AABB_MISMATCH,
                    severity=Severity.WARN,
                    message=(
                        f"Collider '{c.path}' AABB extends "
                        f"{max_ratio:.3f}× the visual AABB (max allowed "
                        f"{t.aabb_ratio_max:.2f}× per axis)."
                    ),
                    prim_paths=(c.path,),
                    metric={"ratio_x": ratios[0], "ratio_y": ratios[1], "ratio_z": ratios[2]},
                    threshold={"aabb_ratio_max": t.aabb_ratio_max},
                    validator=self.name,
                ))

        # §3.6 — missing collision group
        if c.collision_group is None:
            out.append(Issue.create(
                code=CODE_MISSING_COLLISION_GROUP,
                severity=Severity.WARN,
                message=(
                    f"Collider '{c.path}' has no explicit collision group; "
                    f"set `physxCollision:filterGroup` to avoid default-group "
                    f"interactions."
                ),
                prim_paths=(c.path,),
                validator=self.name,
            ))

        # §3.7 — cooking failed
        if c.cooking_error is not None:
            out.append(Issue.create(
                code=CODE_COOKING_FAILED,
                severity=Severity.FAIL,
                message=(
                    f"Collider '{c.path}' failed PhysX cooking: {c.cooking_error}"
                ),
                prim_paths=(c.path,),
                validator=self.name,
            ))

        # Stability heuristics — degenerate AABB / aspect ratio
        extents = self._collider_extents(c)
        if extents is not None:
            min_e = min(extents)
            max_e = max(extents)

            if min_e < t.min_aabb_extent_m:
                out.append(Issue.create(
                    code=CODE_DEGENERATE_AABB,
                    severity=Severity.WARN,
                    message=(
                        f"Collider '{c.path}' has an AABB axis of {min_e:.6f} m "
                        f"(below stability minimum {t.min_aabb_extent_m} m). "
                        f"Thin colliders generate unstable contacts."
                    ),
                    prim_paths=(c.path,),
                    metric={"min_extent_m": min_e},
                    threshold={"min_aabb_extent_m": t.min_aabb_extent_m},
                    validator=self.name,
                ))
            elif min_e > 0:
                ratio = max_e / min_e
                if ratio > t.max_aabb_aspect_ratio:
                    out.append(Issue.create(
                        code=CODE_EXTREME_ASPECT_RATIO,
                        severity=Severity.WARN,
                        message=(
                            f"Collider '{c.path}' has aspect ratio {ratio:.1f} "
                            f"(max_extent/min_extent), exceeding stability "
                            f"limit {t.max_aabb_aspect_ratio}."
                        ),
                        prim_paths=(c.path,),
                        metric={"aspect_ratio": ratio},
                        threshold={"max_aabb_aspect_ratio": t.max_aabb_aspect_ratio},
                        validator=self.name,
                    ))

        return out

    # ============================================ per-rigid-body ==

    def _check_rigid_body(self, rb: RigidBodyInfo) -> list[Issue]:
        out: list[Issue] = []
        t = self.criteria.collider

        # §3.9 — mass out of range
        if rb.mass is not None and (rb.mass < t.mass_min_kg or rb.mass > t.mass_max_kg):
            out.append(Issue.create(
                code=CODE_MASS_OUT_OF_RANGE,
                severity=Severity.WARN,
                message=(
                    f"Rigid body '{rb.path}' has mass {rb.mass} kg, outside "
                    f"sanity range [{t.mass_min_kg}, {t.mass_max_kg}] kg."
                ),
                prim_paths=(rb.path,),
                metric={"mass_kg": rb.mass},
                threshold={"mass_min_kg": t.mass_min_kg, "mass_max_kg": t.mass_max_kg},
                validator=self.name,
            ))

        # §3.10 — mass-density conflict (only checked when both authored + volume known)
        if (rb.mass is not None
                and rb.density is not None
                and rb.volume_m3 is not None
                and rb.volume_m3 > 0
                and rb.mass > 0):
            expected = rb.density * rb.volume_m3
            rel_err  = abs(rb.mass - expected) / rb.mass
            if rel_err > t.mass_density_tolerance:
                out.append(Issue.create(
                    code=CODE_MASS_DENSITY_CONFLICT,
                    severity=Severity.WARN,
                    message=(
                        f"Rigid body '{rb.path}' mass {rb.mass} kg vs density × "
                        f"volume = {expected:.6f} kg differ by {rel_err*100:.1f}% "
                        f"(tolerance {t.mass_density_tolerance*100:.0f}%)."
                    ),
                    prim_paths=(rb.path,),
                    metric={"mass_kg": rb.mass, "expected_mass_kg": expected,
                            "relative_error": rel_err},
                    threshold={"mass_density_tolerance": t.mass_density_tolerance},
                    validator=self.name,
                ))

        return out

    # ============================================ Issue factories ==

    def _rb_without_collider_issue(self, rb: RigidBodyInfo) -> Issue:
        return Issue.create(
            code=CODE_RIGID_BODY_WITHOUT_COLL,
            severity=Severity.FAIL,
            message=(
                f"Rigid body '{rb.path}' has no descendant with PhysicsCollisionAPI; "
                f"physics interactions would be undefined."
            ),
            prim_paths=(rb.path,),
            validator=self.name,
        )

    def _hull_count_issue(
        self, c: ColliderInfo, hulls: int, severity: Severity, threshold: int,
    ) -> Issue:
        return Issue.create(
            code=CODE_CONVEX_DECOMP_HULL_LIM,
            severity=severity,
            message=(
                f"Collider '{c.path}' convex-decomposition produces {hulls} hulls "
                f"(threshold {threshold}). High hull counts hurt cook time and "
                f"contact-resolution stability."
            ),
            prim_paths=(c.path,),
            metric={"hull_count": float(hulls)},
            threshold={"hull_threshold": float(threshold)},
            validator=self.name,
        )

    def _no_inspector_issue(self) -> Issue:
        return Issue.create(
            code=CODE_NO_COLLIDER_INSPECTOR,
            severity=Severity.FAIL,
            message=(
                "ValidationContext.collider_inspector is None — ColliderValidator "
                "requires a ColliderInspector to enumerate colliders and rigid bodies."
            ),
            validator=self.name,
        )

    # ============================================ geometry helpers ==

    @staticmethod
    def _collider_extents(c: ColliderInfo) -> tuple[float, float, float] | None:
        if c.collider_aabb_min is None or c.collider_aabb_max is None:
            return None
        return tuple(
            c.collider_aabb_max[i] - c.collider_aabb_min[i] for i in range(3)
        )  # type: ignore[return-value]

    @staticmethod
    def _visual_extents(c: ColliderInfo) -> tuple[float, float, float] | None:
        if c.visual_aabb_min is None or c.visual_aabb_max is None:
            return None
        return tuple(
            c.visual_aabb_max[i] - c.visual_aabb_min[i] for i in range(3)
        )  # type: ignore[return-value]

    @classmethod
    def _aabb_axis_ratios(cls, c: ColliderInfo) -> tuple[float, float, float] | None:
        coll = cls._collider_extents(c)
        vis  = cls._visual_extents(c)
        if coll is None or vis is None:
            return None
        ratios = []
        for i in range(3):
            if vis[i] <= 0:
                # Visual mesh degenerate on this axis; skip ratio for this axis
                ratios.append(0.0)
            else:
                ratios.append(coll[i] / vis[i])
        return (ratios[0], ratios[1], ratios[2])
