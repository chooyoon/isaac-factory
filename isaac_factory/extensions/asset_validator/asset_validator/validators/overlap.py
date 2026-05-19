"""OverlapValidator — see docs/asset_validator_design.md §5 and
docs/asset_validator_acceptance.md §1.

Detects unwanted interpenetration between rigid bodies in an asset stage.
Pure-logic implementation: physics access is abstracted through
:class:`ContactSource`, so this module is importable and testable without
Isaac Sim Kit Python.
"""

from __future__ import annotations

from ..core.contact         import ContactPair
from ..core.context         import ValidationContext
from ..core.issue           import Issue
from ..core.severity        import Severity
from ..core.validator_base  import Validator


# Issue codes — stable. Sprint Contracts and CI gates reference these.
CODE_PEN_DEPTH_EXCEEDED      = "OVERLAP.PEN_DEPTH_EXCEEDED"        # rule 1.1
CODE_PEN_DEPTH_EXCEEDED_FIT  = "OVERLAP.PEN_DEPTH_EXCEEDED_FIT"    # rule 1.2
CODE_SELF_INTERSECTION       = "OVERLAP.SELF_INTERSECTION"         # rule 1.5


class OverlapValidator(Validator):
    """Reports interpenetration issues.

    Notes on the acceptance rules:
    - 1.1 and 1.3 are consolidated: a non-fit contact whose penetration
      exceeds ``pen_depth_max_m`` produces ``OVERLAP.PEN_DEPTH_EXCEEDED``.
      The "any contact at all" interpretation of 1.3 would require a
      separate near-zero threshold; deferred until needed.
    - 1.4 (convergence within N steps) requires multi-step measurement
      and is out of scope for this single-step validator; the threshold
      is wired through `AcceptanceCriteria` so a future revision can
      enforce it without an API change.
    """

    name  = "overlap"
    phase = "dynamic"

    # ---------------------------------------------------------------- run --

    def run(self, ctx: ValidationContext) -> list[Issue]:
        cs = ctx.contact_source

        cs.setup(seed=int(ctx.seed))
        for _ in range(self.criteria.overlap.physics_settle_pre_steps):
            cs.step()
        cs.step()   # measurement step

        # Canonicalize pair orientation and sort for deterministic output.
        pairs = sorted(
            (ContactPair.create(p.prim_a, p.prim_b, p.penetration_depth)
             for p in cs.query_contacts()),
            key=lambda p: (p.prim_a, p.prim_b, p.penetration_depth),
        )

        issues: list[Issue] = []
        for pair in pairs:
            issue = self._classify(pair, ctx)
            if issue is not None:
                issues.append(issue)

        issues.sort(key=Issue.sort_key)
        return issues

    # ----------------------------------------------------------- internal --

    def _classify(self, pair: ContactPair, ctx: ValidationContext) -> Issue | None:
        if pair.is_self_contact:
            return self._self_intersection_issue(pair)

        pair_set = frozenset({pair.prim_a, pair.prim_b})
        is_fit   = pair_set in ctx.allowed_contact_pairs
        ov       = self.criteria.overlap

        if is_fit:
            if pair.penetration_depth > ov.pen_depth_max_fit_m:
                return self._fit_exceeded_issue(pair, ov.pen_depth_max_fit_m)
            return None

        if pair.penetration_depth > ov.pen_depth_max_m:
            return self._unexpected_exceeded_issue(pair, ov.pen_depth_max_m)
        return None

    def _self_intersection_issue(self, pair: ContactPair) -> Issue:
        return Issue.create(
            code=CODE_SELF_INTERSECTION,
            severity=Severity.FAIL,
            message=(
                f"Self-intersection on '{pair.prim_a}' "
                f"(penetration {pair.penetration_depth*1e3:.3f} mm). "
                f"Likely a cooking artifact on the collider."
            ),
            prim_paths=(pair.prim_a,),
            metric={"penetration_depth_m": pair.penetration_depth},
            validator=self.name,
        )

    def _fit_exceeded_issue(self, pair: ContactPair, threshold_m: float) -> Issue:
        return Issue.create(
            code=CODE_PEN_DEPTH_EXCEEDED_FIT,
            severity=Severity.WARN,
            message=(
                f"Expected-contact pair '{pair.prim_a}' <-> '{pair.prim_b}' "
                f"penetrates {pair.penetration_depth*1e3:.3f} mm "
                f"(fit threshold {threshold_m*1e3:.3f} mm)."
            ),
            prim_paths=(pair.prim_a, pair.prim_b),
            metric={"penetration_depth_m": pair.penetration_depth},
            threshold={"pen_depth_max_fit_m": threshold_m},
            validator=self.name,
        )

    def _unexpected_exceeded_issue(self, pair: ContactPair, threshold_m: float) -> Issue:
        return Issue.create(
            code=CODE_PEN_DEPTH_EXCEEDED,
            severity=Severity.FAIL,
            message=(
                f"Unexpected contact between '{pair.prim_a}' and '{pair.prim_b}' "
                f"penetrates {pair.penetration_depth*1e3:.3f} mm "
                f"(threshold {threshold_m*1e3:.3f} mm)."
            ),
            prim_paths=(pair.prim_a, pair.prim_b),
            metric={"penetration_depth_m": pair.penetration_depth},
            threshold={"pen_depth_max_m": threshold_m},
            validator=self.name,
        )
