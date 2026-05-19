"""GroundingValidator — raycast-based static grounding check.

Pipeline (per user requirement):
  1. raycast downward          (done by inspector; result fed in as data)
  2. detect support surface    (`GroundingProbe.support_hit_path`)
  3. validate grounding        (gap within floating tolerance)
  4. detect buried / floating  (signed gap classification)

This is a **static geometric** check: it does not run physics. The dynamic
settle-based check described in docs/asset_validator_acceptance.md §5 (1 s
settle + residual-velocity assertion) remains a separate concern and is
out of scope for v1. Both can coexist when the Pipeline gains both phases.

Pure-logic implementation: raycasting is abstracted through
:class:`GroundingInspector`, so this module is importable and testable
without Isaac Sim Kit Python.
"""

from __future__ import annotations

from ..core.context         import ValidationContext
from ..core.grounding       import GroundingProbe
from ..core.issue           import Issue
from ..core.severity        import Severity
from ..core.validator_base  import Validator


# Stable issue codes.
CODE_FLOATING               = "GROUNDING.FLOATING"
CODE_BURIED                 = "GROUNDING.BURIED"
CODE_NO_SUPPORT_FOUND       = "GROUNDING.NO_SUPPORT_FOUND"
CODE_NO_INTENT_TAG          = "GROUNDING.NO_INTENT_TAG"
CODE_NO_GROUNDING_INSPECTOR = "GROUNDING.NO_INSPECTOR"


# Valid values for `GroundingProbe.grounded_intent`.
_INTENT_GROUNDED  = "true"
_INTENT_FLOATING  = "false"
_INTENT_KINEMATIC = "kinematic"
_VALID_INTENTS = {_INTENT_GROUNDED, _INTENT_FLOATING, _INTENT_KINEMATIC}


class GroundingValidator(Validator):
    name  = "grounding"
    phase = "static"

    # ============================================================= run ==

    def run(self, ctx: ValidationContext) -> list[Issue]:
        if ctx.grounding_inspector is None:
            return [self._no_inspector_issue()]

        # Deterministic ordering.
        probes = sorted(
            ctx.grounding_inspector.iter_grounding_probes(),
            key=lambda p: p.path,
        )

        issues: list[Issue] = []
        for probe in probes:
            issues.extend(self._check_probe(probe))

        issues.sort(key=Issue.sort_key)
        return issues

    # =========================================================== probe ==

    def _check_probe(self, probe: GroundingProbe) -> list[Issue]:
        out: list[Issue] = []
        intent = probe.grounded_intent

        # 1. Missing or invalid intent — emit warning, default to grounded.
        effective_intent = intent
        if intent is None:
            out.append(self._no_intent_tag_issue(probe))
            effective_intent = _INTENT_GROUNDED
        elif intent not in _VALID_INTENTS:
            out.append(self._no_intent_tag_issue(probe, observed=intent))
            effective_intent = _INTENT_GROUNDED

        # 2. Skip gap classification for explicitly non-grounded objects.
        if effective_intent == _INTENT_FLOATING:
            return out

        # 3. Detect support surface — raycast result must include a hit.
        if probe.support_hit_path is None:
            out.append(self._no_support_issue(probe))
            return out

        # 4. Kinematic objects are user-positioned; only NO_SUPPORT applies.
        if effective_intent == _INTENT_KINEMATIC:
            return out

        # 5. Gap classification — floating vs buried.
        gap = probe.gap_m
        # Invariant: gap is not None because support_hit_path is set.
        assert gap is not None

        t = self.criteria.grounding
        if gap > t.floating_tolerance_m:
            out.append(self._floating_issue(probe, gap, t.floating_tolerance_m))
        elif gap < -t.buried_tolerance_m:
            out.append(self._buried_issue(probe, gap, t.buried_tolerance_m))
        # else: grounded properly — no issue.

        return out

    # ============================================== Issue factories ==

    def _floating_issue(self, probe: GroundingProbe, gap: float, threshold: float) -> Issue:
        return Issue.create(
            code=CODE_FLOATING,
            severity=Severity.FAIL,
            message=(
                f"Object '{probe.path}' is floating: AABB bottom is "
                f"{gap*1e3:.3f} mm above support '{probe.support_hit_path}' "
                f"(threshold {threshold*1e3:.3f} mm)."
            ),
            prim_paths=(probe.path,),
            metric={"gap_m": gap, "aabb_bottom_z_m": probe.aabb_bottom_z_m,
                    "support_hit_z_m": probe.support_hit_z_m or 0.0},
            threshold={"floating_tolerance_m": threshold},
            validator=self.name,
        )

    def _buried_issue(self, probe: GroundingProbe, gap: float, threshold: float) -> Issue:
        return Issue.create(
            code=CODE_BURIED,
            severity=Severity.FAIL,
            message=(
                f"Object '{probe.path}' is buried: AABB bottom is "
                f"{(-gap)*1e3:.3f} mm BELOW support '{probe.support_hit_path}' "
                f"(threshold {threshold*1e3:.3f} mm)."
            ),
            prim_paths=(probe.path,),
            metric={"gap_m": gap, "aabb_bottom_z_m": probe.aabb_bottom_z_m,
                    "support_hit_z_m": probe.support_hit_z_m or 0.0},
            threshold={"buried_tolerance_m": threshold},
            validator=self.name,
        )

    def _no_support_issue(self, probe: GroundingProbe) -> Issue:
        return Issue.create(
            code=CODE_NO_SUPPORT_FOUND,
            severity=Severity.FAIL,
            message=(
                f"Object '{probe.path}' has no support surface below: "
                f"downward raycast from AABB bottom z={probe.aabb_bottom_z_m:.3f} m "
                f"returned no hit within the inspector's search distance."
            ),
            prim_paths=(probe.path,),
            metric={"aabb_bottom_z_m": probe.aabb_bottom_z_m},
            validator=self.name,
        )

    def _no_intent_tag_issue(self, probe: GroundingProbe, *, observed: str | None = None) -> Issue:
        if observed is None:
            msg = (
                f"Object '{probe.path}' has no `customData['asset_validator']"
                f"['grounded']` tag; defaulting to 'true' for grounding checks."
            )
        else:
            msg = (
                f"Object '{probe.path}' has invalid grounded intent '{observed}'; "
                f"expected one of {sorted(_VALID_INTENTS)}. Defaulting to 'true'."
            )
        return Issue.create(
            code=CODE_NO_INTENT_TAG,
            severity=Severity.WARN,
            message=msg,
            prim_paths=(probe.path,),
            validator=self.name,
        )

    def _no_inspector_issue(self) -> Issue:
        return Issue.create(
            code=CODE_NO_GROUNDING_INSPECTOR,
            severity=Severity.FAIL,
            message=(
                "ValidationContext.grounding_inspector is None — GroundingValidator "
                "requires a GroundingInspector that has performed the downward "
                "raycasts."
            ),
            validator=self.name,
        )
