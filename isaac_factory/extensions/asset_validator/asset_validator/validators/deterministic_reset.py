"""DeterministicResetValidator — validates that World.reset() returns the
scene to a bit-identical state across multiple step-and-reset cycles.

User-listed checks:
  * identical reset transforms       → §6.1, §6.2 (translation/rotation drift)
  * identical spawn order            → new: SPAWN_ORDER_MISMATCH (cross-cycle)
  * no overlap after reset           → new: CONTACT_AFTER_RESET (penetration > 0)
  * stable physics after reset       → §6.3, §6.4 (linear/angular velocity ~ 0)

Pure-logic implementation: simulation is abstracted through
:class:`ResetSimulator`, so this module is importable and testable without
Isaac Sim Kit Python. The real adapter (deferred) executes the cycles
under PhysX with a fixed seed and fills in the report.
"""

from __future__ import annotations

from typing import Mapping

from ..core.context         import ValidationContext
from ..core.contact         import ContactPair
from ..core.issue           import Issue
from ..core.reset           import BodyState, ResetCycle, ResetReport
from ..core.severity        import Severity
from ..core.validator_base  import Validator
from ..utils.transform_math import (
    quaternion_angle_delta,
    vec3_distance,
    vec3_magnitude,
)


# Stable issue codes.
CODE_POSE_TRANSLATION_DRIFT  = "RESET.POSE_TRANSLATION_DRIFT"        # §6.1
CODE_POSE_ROTATION_DRIFT     = "RESET.POSE_ROTATION_DRIFT"           # §6.2
CODE_LINEAR_VELOCITY_DRIFT   = "RESET.LINEAR_VELOCITY_DRIFT"         # §6.3
CODE_ANGULAR_VELOCITY_DRIFT  = "RESET.ANGULAR_VELOCITY_DRIFT"        # §6.4
CODE_DETERMINISM_FLAG_MISSING = "RESET.DETERMINISM_FLAG_MISSING"     # §6.5
CODE_SEED_NOT_FIXED          = "RESET.SEED_NOT_FIXED"                # §6.6
CODE_CYCLE_VARIANCE_TRANS    = "RESET.CYCLE_VARIANCE_TRANSLATION"    # §6.7
CODE_CYCLE_VARIANCE_ROT      = "RESET.CYCLE_VARIANCE_ROTATION"       # §6.7
CODE_NON_DETERMINISTIC_AUTHORING = "RESET.NON_DETERMINISTIC_AUTHORING"  # §6.8
CODE_SPAWN_ORDER_MISMATCH    = "RESET.SPAWN_ORDER_MISMATCH"          # user
CODE_CONTACT_AFTER_RESET     = "RESET.CONTACT_AFTER_RESET"           # user
CODE_BODY_SET_MISMATCH       = "RESET.BODY_SET_MISMATCH"             # new — guard
CODE_NO_RESET_SIMULATOR      = "RESET.NO_SIMULATOR"


class DeterministicResetValidator(Validator):
    name  = "deterministic_reset"
    phase = "dynamic"

    # ============================================================= run ==

    def run(self, ctx: ValidationContext) -> list[Issue]:
        if ctx.reset_simulator is None:
            return [self._no_simulator_issue()]

        report = ctx.reset_simulator.get_reset_report()
        issues: list[Issue] = []

        # 6.5 / 6.6 — determinism prerequisites
        issues.extend(self._check_prerequisites(report))

        # 6.8 — non-deterministic authoring (WARN)
        for path in sorted(set(report.non_deterministic_authoring)):
            issues.append(self._non_deterministic_authoring_issue(path))

        # Build lookup maps for cross-cycle comparisons
        initial_map: Mapping[str, BodyState] = {
            b.prim_path: b for b in report.initial_state
        }
        initial_paths        = set(initial_map.keys())
        initial_spawn_order  = tuple(report.initial_spawn_order)

        # Cycle 1 after_step is the variance reference for §6.7
        cycle_1_after_step: Mapping[str, BodyState] | None = None
        sorted_cycles = sorted(report.cycles, key=lambda c: c.cycle_index)
        if sorted_cycles:
            cycle_1_after_step = {
                b.prim_path: b for b in sorted_cycles[0].after_step_state
            }

        for cycle in sorted_cycles:
            issues.extend(self._check_cycle(
                cycle, initial_map, initial_paths, initial_spawn_order,
                cycle_1_after_step,
            ))

        issues.sort(key=Issue.sort_key)
        return issues

    # =================================================== prerequisites ==

    def _check_prerequisites(self, report: ResetReport) -> list[Issue]:
        out: list[Issue] = []
        t = self.criteria.deterministic_reset

        if t.require_determinism_flag and not report.determinism_flag_set:
            out.append(Issue.create(
                code=CODE_DETERMINISM_FLAG_MISSING,
                severity=Severity.FAIL,
                message=(
                    "PhysX `useDeterministicSimulation` is not set on the "
                    "scene; reset reproducibility cannot be guaranteed."
                ),
                validator=self.name,
            ))
        if t.require_seed and not report.seed_set:
            out.append(Issue.create(
                code=CODE_SEED_NOT_FIXED,
                severity=Severity.FAIL,
                message=(
                    "Seeds for NumPy / random / PhysX solver / Warp were not "
                    "fixed before the cycle started."
                ),
                validator=self.name,
            ))
        return out

    # =================================================== per-cycle ==

    def _check_cycle(
        self,
        cycle: ResetCycle,
        initial_map: Mapping[str, BodyState],
        initial_paths: set[str],
        initial_spawn_order: tuple[str, ...],
        cycle_1_after_step: Mapping[str, BodyState] | None,
    ) -> list[Issue]:
        out: list[Issue] = []
        t = self.criteria.deterministic_reset

        after_reset_map = {b.prim_path: b for b in cycle.after_reset_state}

        # Body set mismatch — a body present at t=0 should still be present
        # after reset; conversely, no new bodies should appear.
        missing = initial_paths - set(after_reset_map.keys())
        extra   = set(after_reset_map.keys()) - initial_paths
        if missing or extra:
            out.append(Issue.create(
                code=CODE_BODY_SET_MISMATCH,
                severity=Severity.FAIL,
                message=(
                    f"Cycle {cycle.cycle_index}: body set after reset differs "
                    f"from initial. Missing: {sorted(missing) or '∅'}. "
                    f"Extra: {sorted(extra) or '∅'}."
                ),
                metric={"missing_count": float(len(missing)),
                        "extra_count":   float(len(extra))},
                validator=self.name,
            ))

        # Per-body drift checks on the intersection
        for path in sorted(initial_paths & set(after_reset_map.keys())):
            init  = initial_map[path]
            after = after_reset_map[path]

            # §6.1 — translation drift
            t_delta = vec3_distance(init.translation, after.translation)
            if t_delta > t.translation_tolerance_m:
                out.append(self._translation_drift_issue(
                    cycle.cycle_index, path, t_delta,
                    t.translation_tolerance_m,
                ))

            # §6.2 — rotation drift
            r_delta = quaternion_angle_delta(init.rotation_quat, after.rotation_quat)
            if r_delta > t.rotation_tolerance_rad:
                out.append(self._rotation_drift_issue(
                    cycle.cycle_index, path, r_delta, t.rotation_tolerance_rad,
                ))

            # §6.3 — linear velocity at reset must be ~ 0
            v_mag = vec3_magnitude(after.linear_velocity)
            if v_mag > t.velocity_tolerance_m_per_s:
                out.append(self._linear_velocity_drift_issue(
                    cycle.cycle_index, path, v_mag,
                    t.velocity_tolerance_m_per_s,
                ))

            # §6.4 — angular velocity at reset must be ~ 0
            w_mag = vec3_magnitude(after.angular_velocity)
            if w_mag > t.angular_velocity_tolerance_rad_per_s:
                out.append(self._angular_velocity_drift_issue(
                    cycle.cycle_index, path, w_mag,
                    t.angular_velocity_tolerance_rad_per_s,
                ))

        # Spawn order check
        if tuple(cycle.spawn_order) != initial_spawn_order:
            out.append(self._spawn_order_mismatch_issue(
                cycle.cycle_index, initial_spawn_order, tuple(cycle.spawn_order),
            ))

        # No-overlap-after-reset — any residual contact above threshold
        for pair in sorted(
            cycle.contact_pairs_after_reset,
            key=lambda p: (p.prim_a, p.prim_b),
        ):
            if pair.penetration_depth > t.max_penetration_after_reset_m:
                out.append(self._contact_after_reset_issue(
                    cycle.cycle_index, pair, t.max_penetration_after_reset_m,
                ))

        # §6.7 — cycle variance vs cycle 1
        if cycle_1_after_step is not None and cycle.cycle_index > 1:
            after_step_map = {b.prim_path: b for b in cycle.after_step_state}
            common = set(after_step_map.keys()) & set(cycle_1_after_step.keys())
            for path in sorted(common):
                c1 = cycle_1_after_step[path]
                ci = after_step_map[path]

                t_delta = vec3_distance(c1.translation, ci.translation)
                if t_delta > t.cycle_variance_translation_m:
                    out.append(self._cycle_variance_trans_issue(
                        cycle.cycle_index, path, t_delta,
                        t.cycle_variance_translation_m,
                    ))

                r_delta = quaternion_angle_delta(c1.rotation_quat, ci.rotation_quat)
                if r_delta > t.cycle_variance_rotation_rad:
                    out.append(self._cycle_variance_rot_issue(
                        cycle.cycle_index, path, r_delta,
                        t.cycle_variance_rotation_rad,
                    ))

        return out

    # ============================================ Issue factories ==

    def _translation_drift_issue(self, cycle_idx, path, delta, threshold):
        return Issue.create(
            code=CODE_POSE_TRANSLATION_DRIFT,
            severity=Severity.FAIL,
            message=(
                f"Cycle {cycle_idx}: body '{path}' translation drifted "
                f"{delta:.3e} m after reset (tolerance {threshold:.0e} m)."
            ),
            prim_paths=(path,),
            metric={"translation_delta_m": delta, "cycle_index": float(cycle_idx)},
            threshold={"translation_tolerance_m": threshold},
            validator=self.name,
        )

    def _rotation_drift_issue(self, cycle_idx, path, delta, threshold):
        return Issue.create(
            code=CODE_POSE_ROTATION_DRIFT,
            severity=Severity.FAIL,
            message=(
                f"Cycle {cycle_idx}: body '{path}' rotation drifted "
                f"{delta:.3e} rad after reset (tolerance {threshold:.0e} rad)."
            ),
            prim_paths=(path,),
            metric={"rotation_delta_rad": delta, "cycle_index": float(cycle_idx)},
            threshold={"rotation_tolerance_rad": threshold},
            validator=self.name,
        )

    def _linear_velocity_drift_issue(self, cycle_idx, path, mag, threshold):
        return Issue.create(
            code=CODE_LINEAR_VELOCITY_DRIFT,
            severity=Severity.FAIL,
            message=(
                f"Cycle {cycle_idx}: body '{path}' linear velocity {mag:.3e} m/s "
                f"after reset exceeds zero tolerance {threshold:.0e} m/s."
            ),
            prim_paths=(path,),
            metric={"linear_velocity_m_per_s": mag, "cycle_index": float(cycle_idx)},
            threshold={"velocity_tolerance_m_per_s": threshold},
            validator=self.name,
        )

    def _angular_velocity_drift_issue(self, cycle_idx, path, mag, threshold):
        return Issue.create(
            code=CODE_ANGULAR_VELOCITY_DRIFT,
            severity=Severity.FAIL,
            message=(
                f"Cycle {cycle_idx}: body '{path}' angular velocity "
                f"{mag:.3e} rad/s after reset exceeds zero tolerance "
                f"{threshold:.0e} rad/s."
            ),
            prim_paths=(path,),
            metric={"angular_velocity_rad_per_s": mag, "cycle_index": float(cycle_idx)},
            threshold={"angular_velocity_tolerance_rad_per_s": threshold},
            validator=self.name,
        )

    def _spawn_order_mismatch_issue(
        self, cycle_idx, initial_order, observed_order,
    ):
        return Issue.create(
            code=CODE_SPAWN_ORDER_MISMATCH,
            severity=Severity.FAIL,
            message=(
                f"Cycle {cycle_idx}: spawn order differs from initial. "
                f"Initial: {list(initial_order)}. Observed: {list(observed_order)}."
            ),
            metric={"cycle_index": float(cycle_idx)},
            validator=self.name,
        )

    def _contact_after_reset_issue(
        self, cycle_idx: int, pair: ContactPair, threshold: float,
    ):
        return Issue.create(
            code=CODE_CONTACT_AFTER_RESET,
            severity=Severity.FAIL,
            message=(
                f"Cycle {cycle_idx}: residual contact between "
                f"'{pair.prim_a}' and '{pair.prim_b}' after reset "
                f"(penetration {pair.penetration_depth*1e3:.3f} mm; "
                f"max allowed {threshold*1e3:.6f} mm)."
            ),
            prim_paths=(pair.prim_a, pair.prim_b),
            metric={"penetration_depth_m": pair.penetration_depth,
                    "cycle_index":          float(cycle_idx)},
            threshold={"max_penetration_after_reset_m": threshold},
            validator=self.name,
        )

    def _cycle_variance_trans_issue(self, cycle_idx, path, delta, threshold):
        return Issue.create(
            code=CODE_CYCLE_VARIANCE_TRANS,
            severity=Severity.FAIL,
            message=(
                f"Cycle {cycle_idx}: body '{path}' after_step translation differs "
                f"from cycle 1 by {delta:.3e} m (tolerance {threshold:.0e} m)."
            ),
            prim_paths=(path,),
            metric={"translation_delta_m": delta, "cycle_index": float(cycle_idx)},
            threshold={"cycle_variance_translation_m": threshold},
            validator=self.name,
        )

    def _cycle_variance_rot_issue(self, cycle_idx, path, delta, threshold):
        return Issue.create(
            code=CODE_CYCLE_VARIANCE_ROT,
            severity=Severity.FAIL,
            message=(
                f"Cycle {cycle_idx}: body '{path}' after_step rotation differs "
                f"from cycle 1 by {delta:.3e} rad (tolerance {threshold:.0e} rad)."
            ),
            prim_paths=(path,),
            metric={"rotation_delta_rad": delta, "cycle_index": float(cycle_idx)},
            threshold={"cycle_variance_rotation_rad": threshold},
            validator=self.name,
        )

    def _non_deterministic_authoring_issue(self, path: str) -> Issue:
        return Issue.create(
            code=CODE_NON_DETERMINISTIC_AUTHORING,
            severity=Severity.WARN,
            message=(
                f"Prim '{path}' uses a non-deterministic physics API "
                f"(e.g., `physxRigidBody:randomizedSeed`)."
            ),
            prim_paths=(path,),
            validator=self.name,
        )

    def _no_simulator_issue(self) -> Issue:
        return Issue.create(
            code=CODE_NO_RESET_SIMULATOR,
            severity=Severity.FAIL,
            message=(
                "ValidationContext.reset_simulator is None — "
                "DeterministicResetValidator requires a ResetSimulator that "
                "has executed the reset cycles."
            ),
            validator=self.name,
        )
