"""TransformValidator — static checks on USD Xformable prims.

Covers the threshold rows in docs/asset_validator_acceptance.md §2 plus
three transform-related concerns the user asked for that don't fit
elsewhere as static checks:

  * "floating objects"     → static heuristic on local translate.z
                             (full grounding is the dynamic GroundingValidator)
  * "hierarchy corruption" → unresolved xformOpOrder entries, mixed-style ops,
                             and a cascade marker on descendants of failing prims
  * "transform drift"      → static interpretation: time-sampled values on prims
                             not flagged dynamic (full drift is the dynamic
                             DeterministicResetValidator)

Pure-logic implementation: USD access is abstracted through StageInspector,
so this module is importable and testable without Isaac Sim Kit Python.
"""

from __future__ import annotations

import math
from typing import Mapping

from ..core.context         import ValidationContext
from ..core.issue           import Issue
from ..core.severity        import Severity
from ..core.stage           import StageInspector, TransformOp, XformablePrim
from ..core.validator_base  import Validator
from ..utils.transform_math import (
    matrix_rotation_orthogonality_error,
    quaternion_magnitude,
    vec3_magnitude,
)


# Stable issue codes — referenced by Sprint Contracts and CI gates.
CODE_NAN_VALUE                 = "TRANSFORM.NAN_VALUE"                  # §2.1
CODE_INF_VALUE                 = "TRANSFORM.INF_VALUE"                  # §2.2
CODE_ZERO_SCALE                = "TRANSFORM.ZERO_SCALE"                 # §2.3
CODE_SCALE_OUT_OF_RANGE        = "TRANSFORM.SCALE_OUT_OF_RANGE"         # §2.4
CODE_NON_POSITIVE_SCALE        = "TRANSFORM.NON_POSITIVE_SCALE"         # §2.5
CODE_QUATERNION_DENORMAL       = "TRANSFORM.QUATERNION_DENORMAL"        # §2.6
CODE_ROTATION_NON_ORTHOGONAL   = "TRANSFORM.ROTATION_NON_ORTHOGONAL"    # §2.7
CODE_TRANSLATION_OUT_OF_RANGE  = "TRANSFORM.TRANSLATION_OUT_OF_RANGE"   # §2.8
CODE_TIME_SAMPLED_ON_STATIC    = "TRANSFORM.TIME_SAMPLED_ON_STATIC"     # §2.9
CODE_MIXED_OP_ORDER            = "TRANSFORM.MIXED_OP_ORDER"             # §2.10
CODE_XFORMOP_ORDER_INVALID     = "TRANSFORM.XFORMOP_ORDER_INVALID"      # hierarchy corruption
CODE_CASCADE_INVALID_WORLD     = "TRANSFORM.CASCADE_INVALID_WORLD"      # cascade marker
CODE_FLOATING_HEURISTIC        = "TRANSFORM.FLOATING_HEURISTIC"         # static floating heuristic
CODE_OP_VALUE_COUNT_MISMATCH   = "TRANSFORM.OP_VALUE_COUNT_MISMATCH"    # malformed op
CODE_NO_STAGE_INSPECTOR        = "TRANSFORM.NO_STAGE_INSPECTOR"         # missing dependency

# Expected number of values per canonical op_type.
_EXPECTED_VALUES: Mapping[str, int] = {
    "translate":        3,
    "scale":            3,
    "rotate_quat":      4,
    "rotate_euler":     3,
    "rotate_axis":      1,
    "transform_matrix": 16,
}

# Op-style classification for mixed-order detection (§2.10).
_SEPARATE_STYLE = {"translate", "scale", "rotate_quat", "rotate_euler", "rotate_axis"}
_MATRIX_STYLE   = {"transform_matrix"}


class TransformValidator(Validator):
    name  = "transform"
    phase = "static"

    # =========================================================== run ==

    def run(self, ctx: ValidationContext) -> list[Issue]:
        if ctx.stage_inspector is None:
            return [self._no_inspector_issue()]

        prims = sorted(
            ctx.stage_inspector.iter_xformable_prims(),
            key=lambda p: p.path,
        )
        prim_by_path = {p.path: p for p in prims}

        issues: list[Issue] = []
        failing_prim_paths: set[str] = set()

        # Pass 1 — per-prim local checks
        for prim in prims:
            prim_issues = self._check_prim(prim)
            issues.extend(prim_issues)
            if any(i.severity == Severity.FAIL for i in prim_issues):
                failing_prim_paths.add(prim.path)

        # Pass 2 — cascade: mark descendants of failing prims
        for prim in prims:
            if prim.path in failing_prim_paths:
                continue
            ancestor = self._failing_ancestor(prim, prim_by_path, failing_prim_paths)
            if ancestor is not None:
                issues.append(self._cascade_issue(prim, ancestor))

        # Pass 3 — floating heuristic (cross-prim, opt-in via threshold)
        thr = self.criteria.transform.floating_heuristic_z_m
        if thr is not None and thr > 0:
            for prim in prims:
                z = self._local_translate_z(prim)
                if z is not None and z > thr:
                    issues.append(self._floating_issue(prim, z, thr))

        issues.sort(key=Issue.sort_key)
        return issues

    # ============================================== per-prim checks ==

    def _check_prim(self, prim: XformablePrim) -> list[Issue]:
        out: list[Issue] = []

        # Hierarchy corruption — unresolved xformOpOrder entries
        if prim.xform_op_order_unresolved:
            out.append(Issue.create(
                code=CODE_XFORMOP_ORDER_INVALID,
                severity=Severity.FAIL,
                message=(
                    f"Prim '{prim.path}' xformOpOrder references missing ops: "
                    f"{', '.join(prim.xform_op_order_unresolved)}"
                ),
                prim_paths=(prim.path,),
                validator=self.name,
            ))

        # Mixed op style (§2.10)
        if self._has_mixed_op_styles(prim):
            out.append(Issue.create(
                code=CODE_MIXED_OP_ORDER,
                severity=Severity.WARN,
                message=(
                    f"Prim '{prim.path}' mixes xformOp:transform with separate "
                    f"translate/rotate/scale ops in xformOpOrder."
                ),
                prim_paths=(prim.path,),
                validator=self.name,
            ))

        for op in prim.ops:
            out.extend(self._check_op(op, prim))

        return out

    def _check_op(self, op: TransformOp, prim: XformablePrim) -> list[Issue]:
        out: list[Issue] = []

        # Value-count check first — if malformed, skip downstream numeric checks.
        expected = _EXPECTED_VALUES.get(op.op_type)
        if expected is not None and len(op.values) != expected:
            out.append(Issue.create(
                code=CODE_OP_VALUE_COUNT_MISMATCH,
                severity=Severity.FAIL,
                message=(
                    f"Op '{op.op_name}' on '{prim.path}' has {len(op.values)} values; "
                    f"type '{op.op_type}' expects {expected}."
                ),
                prim_paths=(prim.path,),
                metric={"value_count": float(len(op.values)),
                        "expected_count": float(expected)},
                validator=self.name,
            ))
            return out

        # NaN / Inf
        nan_idx = [i for i, v in enumerate(op.values) if math.isnan(v)]
        inf_idx = [i for i, v in enumerate(op.values) if math.isinf(v)]
        if nan_idx:
            out.append(Issue.create(
                code=CODE_NAN_VALUE,
                severity=Severity.FAIL,
                message=f"Op '{op.op_name}' on '{prim.path}' contains NaN at indices {nan_idx}.",
                prim_paths=(prim.path,),
                metric={"nan_count": float(len(nan_idx))},
                validator=self.name,
            ))
        if inf_idx:
            out.append(Issue.create(
                code=CODE_INF_VALUE,
                severity=Severity.FAIL,
                message=f"Op '{op.op_name}' on '{prim.path}' contains Inf at indices {inf_idx}.",
                prim_paths=(prim.path,),
                metric={"inf_count": float(len(inf_idx))},
                validator=self.name,
            ))

        # Skip downstream numeric checks if non-finite values were found —
        # they'd produce noisy secondary issues. Still report time-sampling.
        if nan_idx or inf_idx:
            if op.is_time_sampled and not prim.is_likely_dynamic:
                out.append(self._time_sampled_issue(op, prim))
            return out

        # Type-specific checks
        if   op.op_type == "scale":            out.extend(self._check_scale(op, prim))
        elif op.op_type == "rotate_quat":      out.extend(self._check_quaternion(op, prim))
        elif op.op_type == "transform_matrix": out.extend(self._check_matrix(op, prim))
        elif op.op_type == "translate":        out.extend(self._check_translation(op, prim))

        # Drift (static-only sense): time-sampled values on a non-dynamic prim
        if op.is_time_sampled and not prim.is_likely_dynamic:
            out.append(self._time_sampled_issue(op, prim))

        return out

    # ----- scale (§2.3, 2.4, 2.5) -----

    def _check_scale(self, op: TransformOp, prim: XformablePrim) -> list[Issue]:
        out: list[Issue] = []
        c = self.criteria.transform
        for axis_idx, v in enumerate(op.values):
            axis = "xyz"[axis_idx]
            mag = abs(v)

            if mag < c.min_scale_magnitude:
                out.append(Issue.create(
                    code=CODE_ZERO_SCALE,
                    severity=Severity.FAIL,
                    message=(
                        f"Op '{op.op_name}' on '{prim.path}': {axis}-scale={v} "
                        f"below minimum magnitude {c.min_scale_magnitude}."
                    ),
                    prim_paths=(prim.path,),
                    metric={f"scale_{axis}": v},
                    threshold={"min_scale_magnitude": c.min_scale_magnitude},
                    validator=self.name,
                ))
                continue  # zero is the dominant issue for this axis

            if mag > c.max_scale_magnitude:
                out.append(Issue.create(
                    code=CODE_SCALE_OUT_OF_RANGE,
                    severity=Severity.FAIL,
                    message=(
                        f"Op '{op.op_name}' on '{prim.path}': |{axis}-scale|={mag} "
                        f"exceeds {c.max_scale_magnitude}."
                    ),
                    prim_paths=(prim.path,),
                    metric={f"scale_{axis}": v},
                    threshold={"max_scale_magnitude": c.max_scale_magnitude},
                    validator=self.name,
                ))
                continue

            if v < 0.0 and not prim.is_mirror():
                severity = Severity.FAIL if prim.has_collision_api else Severity.WARN
                out.append(Issue.create(
                    code=CODE_NON_POSITIVE_SCALE,
                    severity=severity,
                    message=(
                        f"Op '{op.op_name}' on '{prim.path}': {axis}-scale={v} "
                        f"is negative without `customData['mirror']`."
                    ),
                    prim_paths=(prim.path,),
                    metric={f"scale_{axis}": v},
                    validator=self.name,
                ))
        return out

    # ----- rotate_quat (§2.6) -----

    def _check_quaternion(self, op: TransformOp, prim: XformablePrim) -> list[Issue]:
        c = self.criteria.transform
        mag = quaternion_magnitude(op.values)
        if not (c.quaternion_magnitude_min <= mag <= c.quaternion_magnitude_max):
            return [Issue.create(
                code=CODE_QUATERNION_DENORMAL,
                severity=Severity.FAIL,
                message=(
                    f"Op '{op.op_name}' on '{prim.path}': quaternion magnitude "
                    f"{mag:.6f} not in [{c.quaternion_magnitude_min}, "
                    f"{c.quaternion_magnitude_max}]."
                ),
                prim_paths=(prim.path,),
                metric={"quaternion_magnitude": mag},
                threshold={"quaternion_magnitude_min": c.quaternion_magnitude_min,
                           "quaternion_magnitude_max": c.quaternion_magnitude_max},
                validator=self.name,
            )]
        return []

    # ----- transform_matrix (§2.7) -----

    def _check_matrix(self, op: TransformOp, prim: XformablePrim) -> list[Issue]:
        c   = self.criteria.transform
        err = matrix_rotation_orthogonality_error(op.values)
        if err > c.rotation_orthogonality_eps:
            return [Issue.create(
                code=CODE_ROTATION_NON_ORTHOGONAL,
                severity=Severity.FAIL,
                message=(
                    f"Op '{op.op_name}' on '{prim.path}': rotation submatrix "
                    f"orthogonality error {err:.6f} exceeds {c.rotation_orthogonality_eps}."
                ),
                prim_paths=(prim.path,),
                metric={"orthogonality_error": err},
                threshold={"rotation_orthogonality_eps": c.rotation_orthogonality_eps},
                validator=self.name,
            )]
        return []

    # ----- translate (§2.8) -----

    def _check_translation(self, op: TransformOp, prim: XformablePrim) -> list[Issue]:
        c   = self.criteria.transform
        mag = vec3_magnitude(op.values)
        if mag > c.max_translation_magnitude_m:
            return [Issue.create(
                code=CODE_TRANSLATION_OUT_OF_RANGE,
                severity=Severity.WARN,
                message=(
                    f"Op '{op.op_name}' on '{prim.path}': translation magnitude "
                    f"{mag:.3f} m exceeds {c.max_translation_magnitude_m} m."
                ),
                prim_paths=(prim.path,),
                metric={"translation_magnitude_m": mag},
                threshold={"max_translation_magnitude_m": c.max_translation_magnitude_m},
                validator=self.name,
            )]
        return []

    # ============================================ structural checks ==

    def _has_mixed_op_styles(self, prim: XformablePrim) -> bool:
        types = {op.op_type for op in prim.ops}
        return bool(types & _MATRIX_STYLE) and bool(types & _SEPARATE_STYLE)

    def _failing_ancestor(
        self,
        prim: XformablePrim,
        prim_by_path: Mapping[str, XformablePrim],
        failing: set[str],
    ) -> str | None:
        cur = prim.parent_path
        while cur:
            if cur in failing:
                return cur
            parent = prim_by_path.get(cur)
            if parent is None:
                return None
            cur = parent.parent_path
        return None

    def _local_translate_z(self, prim: XformablePrim) -> float | None:
        translates = [op for op in prim.ops
                      if op.op_type == "translate" and len(op.values) == 3]
        if len(translates) != 1:
            return None
        v = translates[0].values
        if not all(math.isfinite(x) for x in v):
            return None
        return v[2]

    # ================================================ Issue factories ==

    def _time_sampled_issue(self, op: TransformOp, prim: XformablePrim) -> Issue:
        return Issue.create(
            code=CODE_TIME_SAMPLED_ON_STATIC,
            severity=Severity.WARN,
            message=(
                f"Op '{op.op_name}' on '{prim.path}' has {op.time_sample_count} "
                f"time samples but the prim is not flagged dynamic."
            ),
            prim_paths=(prim.path,),
            metric={"time_sample_count": float(op.time_sample_count)},
            validator=self.name,
        )

    def _cascade_issue(self, prim: XformablePrim, ancestor_path: str) -> Issue:
        return Issue.create(
            code=CODE_CASCADE_INVALID_WORLD,
            severity=Severity.INFO,
            message=(
                f"Prim '{prim.path}' inherits an invalid world transform from "
                f"ancestor '{ancestor_path}'; downstream metrics may be unreliable."
            ),
            prim_paths=(prim.path,),
            validator=self.name,
        )

    def _floating_issue(
        self, prim: XformablePrim, z: float, threshold_m: float,
    ) -> Issue:
        return Issue.create(
            code=CODE_FLOATING_HEURISTIC,
            severity=Severity.WARN,
            message=(
                f"Prim '{prim.path}' has local translate.z={z:.3f} m exceeding "
                f"the floating-heuristic threshold {threshold_m} m. Static check "
                f"only; authoritative grounding is the GroundingValidator (dynamic)."
            ),
            prim_paths=(prim.path,),
            metric={"translate_z_m": z},
            threshold={"floating_heuristic_z_m": threshold_m},
            validator=self.name,
        )

    def _no_inspector_issue(self) -> Issue:
        return Issue.create(
            code=CODE_NO_STAGE_INSPECTOR,
            severity=Severity.FAIL,
            message=(
                "ValidationContext.stage_inspector is None — TransformValidator "
                "requires a StageInspector to enumerate xformable prims."
            ),
            validator=self.name,
        )
