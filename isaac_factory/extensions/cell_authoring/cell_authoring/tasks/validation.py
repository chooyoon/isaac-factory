"""Phase 4A — UnifiedValidator.

A single entrypoint that runs the four validation layers (endpoint
correctness, temporal grasp integrity, motion-quality realism,
robustness) against a TaskResult or a sequence of TaskResults.

This is an in-process classifier. It does NOT replace the pytest
test suites; it complements them by letting:
  * the harness script,
  * the replay package builder,
  * future ad-hoc scripts
re-apply the same gate logic to a TaskResult without re-running
pytest.

The pytest suites (Phase 3M endpoint, Phase 3N temporal, Phase 3O
motion, Phase 3P robustness) remain the authoritative regression
gate. The UnifiedValidator returns equivalent verdicts on
TaskResult data so a Phase 4A consumer doesn't have to re-implement
those checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .definitions import TaskOutcome, TaskResult
from .profiles import TrajectoryProfile, get_profile_spec


@dataclass
class ValidationReport:
    n_results:     int = 0
    n_pass:        int = 0
    n_fail:        int = 0
    by_outcome:    dict[str, int] = field(default_factory=dict)
    failures:      list[tuple[int, TaskOutcome, str]] = field(default_factory=list)
    pass_rate:     float = 0.0
    deterministic: bool | None = None

    def to_dict(self) -> dict:
        return {
            "n_results":   self.n_results,
            "n_pass":      self.n_pass,
            "n_fail":      self.n_fail,
            "pass_rate":   self.pass_rate,
            "by_outcome":  dict(self.by_outcome),
            "failures":    [(i, o.value, d) for i, o, d in self.failures],
            "deterministic": self.deterministic,
        }


class UnifiedValidator:
    """Apply Phase 3M/N/O/P gates to one TaskResult or a sequence.

    Single-result usage:
        result = executor.execute(task, profile=...)
        passed = UnifiedValidator().check(result).passes

    Sequence usage:
        report = UnifiedValidator().summarise([r0, r1, r2, …])
        report.pass_rate, report.failures, report.deterministic
    """

    def __init__(self,
                 *,
                 placement_tolerance_xy_m: float = 0.060) -> None:
        """``placement_tolerance_xy_m`` is the default for ad-hoc
        re-classification; per-task tolerance comes from the
        PlaceTarget definition during the original execute()."""
        self.placement_tolerance_xy_m = placement_tolerance_xy_m

    def check(self, result: TaskResult) -> TaskResult:
        """Return the result unchanged if PASS, else with outcome+detail
        set to the failing category."""
        from .executor import TaskExecutor
        return TaskExecutor.validate(
            result,
            placement_tolerance_xy_m=self.placement_tolerance_xy_m,
        )

    def summarise(self, results: Iterable[TaskResult]) -> ValidationReport:
        report = ValidationReport()
        finals: list[tuple[float, float, float]] = []
        for i, r in enumerate(results):
            report.n_results += 1
            # Some results may have been validated already; re-running
            # check() is idempotent.
            r = self.check(r)
            cat = r.outcome.value
            report.by_outcome[cat] = report.by_outcome.get(cat, 0) + 1
            if r.outcome == TaskOutcome.PASS:
                report.n_pass += 1
            else:
                report.n_fail += 1
                report.failures.append((i, r.outcome, r.outcome_detail))
            if r.peg_xyz_final is not None:
                finals.append(tuple(r.peg_xyz_final))
        report.pass_rate = report.n_pass / report.n_results if report.n_results else 0.0
        # Determinism is meaningful only if there's no perturbation in any
        # result (we don't have a perturbation-active flag in the result;
        # assume the caller provides homogeneous results).
        report.deterministic = (len(set(finals)) == 1) if len(finals) >= 2 else None
        return report
