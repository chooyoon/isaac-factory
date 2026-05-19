"""Deterministic node-selection scheduler (Phase 4B step 5).

A **pure-function** topological-sequential scheduler. Given a frozen
TaskGraph, an immutable PredicateContext, and frozen completion / failure
state, the scheduler computes which node (if any) is next runnable,
plus a full per-node evaluation report. There is NO execution here:
no callbacks, no task invocation, no PhysX, no async, no retries.

Step 5 is a **deterministic node-selection oracle**. The selected
node_id and the full SchedulerDecision are pure functions of the
explicit inputs.

Contract clauses honoured
-------------------------
D-SCHED-1  — Decision is a pure function of (graph, registry, completed,
             failed, retry_counts). No other inputs are consulted.
D-SCHED-2  — Selection iterates ``graph.canonical_order`` only;
             first runnable wins (D-SCHED-3 same canonical key).
D-SCHED-3  — Same canonical key (``(depth, node_id)``) used everywhere
             — inherited from Step 4 via ``graph.canonical_order``.
D-SCHED-5  — Public iterable outputs are tuples; all enumeration uses
             ``graph.canonical_order`` (already canonical) or
             explicit ``sorted(...)``.
D-SCHED-6  — No dict iteration in canonical paths.
D-SCHED-7  — No set iteration in canonical paths.
D-SCHED-9  — No randomness during execution.
D-SCHED-10 — No UUID / random ID generation.
D-SCHED-11 — No wall-clock reads. SchedulerDecision carries no
             timestamps and no runtime-duration metrics.
D-SCHED-12 — Predicate evaluation goes through Step 3's pure aggregator.
D-SCHED-13 — Predicates evaluated in construction order, short-circuit.

D-SESS-7   — Scheduler does not mutate ``graph``, ``registry``,
             ``completed``, ``failed``, or ``retry_counts``. Inputs are
             read; outputs are fresh frozen objects.
D-SESS-8   — All result dataclasses are
             ``@dataclass(frozen=True, slots=True)``.

D-FORBID-3 — No hidden mutable caches; the scheduler is stateless and
             allocates fresh result objects per call.
D-FORBID-7 — Result is insertion-order independent — depends only on
             ``graph.canonical_order`` (which is itself insertion-order
             independent per Step 4) and the membership of the
             completed/failed sets.
D-FORBID-9 — No speculative execution: the scheduler never invokes a
             task and never assumes a result.

Out of scope (deferred to later phases — documented to prevent creep)
---------------------------------------------------------------------
* retry budgets / retry_count consumption — Step 5 accepts
  ``retry_counts`` for API stability but does NOT consult it. A future
  step's retry-eligibility filter will use it (per architecture doc §3,
  step 5 of "ordering rules" list).
* backoff / exponential timing
* priority arbitration (priority is descriptive only in Step 4)
* resource scheduling / locking
* parallel scheduling (D-SCALE-1 forbids concurrent PhysX, so
  parallelism is forever out of scope for orchestration)
* fairness / starvation prevention
* temporal scheduling ("run X at simulation_tick == N")
* distributed / multi-cell scheduling
* speculative scheduling (D-FORBID-9)
* checkpoint-aware scheduling / recovery scheduling
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from types import MappingProxyType
from typing import AbstractSet, Any, Mapping

from .graph import TaskGraph
from .package import canonical_dumps
from .predicates import (
    PredicateContext,
    PredicateGroupResult,
    PredicateResult,
    evaluate_predicates,
)


# ───────────────────────── version / constants ─────────────────────────


SCHEDULER_DECISION_FINGERPRINT_VERSION: int = 1
"""Canonical scheduler-decision fingerprint schema version. Bumped on
any fingerprint format change."""


# Per-node status — stable string identifiers used in fingerprints.
# Each status is a leaf-state of the per-node evaluation. Bumping the
# fingerprint schema is required to rename or remove a status.
NODE_STATUS_COMPLETED:                  str = "completed"
NODE_STATUS_FAILED:                     str = "failed"
NODE_STATUS_BLOCKED_BY_PARENTS:         str = "blocked_by_parents"
NODE_STATUS_BLOCKED_BY_PRECONDITION:    str = "blocked_by_precondition"
NODE_STATUS_BLOCKED_BY_PREDICATE_ERROR: str = "blocked_by_predicate_error"
NODE_STATUS_RUNNABLE:                   str = "runnable"
NODE_STATUS_SELECTED:                   str = "selected"


# ───────────────────────────── errors ─────────────────────────────


class SchedulerEvaluationError(RuntimeError):
    """Raised on **illegal scheduler input state**.

    Examples (cites step-5 brief §5, D-SCHED-1):

      * a node appears in both ``completed`` AND ``failed``,
      * ``completed`` contains a node_id not in ``graph``,
      * ``failed`` contains a node_id not in ``graph``,
      * ``retry_counts`` contains a node_id not in ``graph``.

    Step 5 does NOT raise on predicate evaluation errors — those become
    deterministic per-node diagnostics
    (:py:data:`NODE_STATUS_BLOCKED_BY_PREDICATE_ERROR`), captured into
    the :class:`NodeEvaluation`'s ``predicate_group_result``.
    """


# ───────────────────────── enums ─────────────────────────


class SchedulerDecisionReason(enum.Enum):
    """Why the scheduler returned the decision it did.

    Stable string values used in fingerprints; renames require a
    :data:`SCHEDULER_DECISION_FINGERPRINT_VERSION` bump.
    """
    SELECTED                  = "SELECTED"
    NO_RUNNABLE_NODES_PENDING = "NO_RUNNABLE_NODES_PENDING"
    ALL_NODES_TERMINAL        = "ALL_NODES_TERMINAL"


# ───────────────────────── helper serialisation ─────────────────────────


def _group_to_canonical_dict(g: PredicateGroupResult) -> dict[str, Any]:
    """Convert a :class:`PredicateGroupResult` into a JSON-friendly dict
    suitable for embedding in a NodeEvaluation / SchedulerDecision
    fingerprint. Cites D-SCHED-13 (preserves predicate-order results)."""
    return {
        "ok":                  g.ok,
        "first_failure_index": g.first_failure_index,
        "error_at":            g.error_at,
        "error_type":          g.error_type,
        "error_str":           g.error_str,
        "results": [
            {
                "predicate_fingerprint": r.predicate_fingerprint,
                "ok":                    r.ok,
                "detail":                r.detail,
            }
            for r in g.results
        ],
    }


def _evaluation_to_canonical_dict(ev: "NodeEvaluation") -> dict[str, Any]:
    """Convert a :class:`NodeEvaluation` to its fingerprint dict.

    Used by both :py:meth:`NodeEvaluation.fingerprint` and
    :py:meth:`SchedulerDecision.fingerprint` so the same canonical form
    is produced from both call paths.
    """
    return {
        "node_id":            ev.node_id,
        "status":             ev.status,
        "blocked_by_parents": list(ev.blocked_by_parents),
        "predicate_group_result": (
            _group_to_canonical_dict(ev.predicate_group_result)
            if ev.predicate_group_result is not None else None
        ),
    }


# ───────────────────────────── NodeEvaluation ─────────────────────────────


@dataclass(frozen=True, slots=True)
class NodeEvaluation:
    """Per-node outcome of one scheduler invocation. Frozen (D-SESS-8).

    Exactly one ``status`` per node per call.

    Fields
    ------
    node_id:
        The node this evaluation describes.
    status:
        One of the :data:`NODE_STATUS_*` constants. See module docstring.
    blocked_by_parents:
        Sorted-lex tuple of parent ``node_id``s that are not in
        ``completed``. Empty for non-``blocked_by_parents`` statuses.
    predicate_group_result:
        The :class:`PredicateGroupResult` from evaluating this node's
        preconditions, if preconditions were evaluated at all
        (i.e. status is one of ``blocked_by_precondition``,
        ``blocked_by_predicate_error``, ``runnable``, ``selected``).
        ``None`` otherwise.
    """
    node_id: str
    status:  str
    blocked_by_parents:     tuple[str, ...] = ()
    predicate_group_result: PredicateGroupResult | None = None

    def fingerprint(self) -> str:
        """Canonical-JSON identity of this per-node evaluation
        (D-SCHED-3, D-SCHED-13)."""
        return canonical_dumps(_evaluation_to_canonical_dict(self))


# ───────────────────────────── SchedulerDecision ─────────────────────────────


@dataclass(frozen=True, slots=True)
class SchedulerDecision:
    """The full outcome of one scheduler invocation. Frozen (D-SESS-8).

    Pure function of the scheduler's inputs (D-SCHED-1): identical
    inputs produce ``SchedulerDecision``s with byte-identical
    fingerprints.

    Fields
    ------
    selected_node_id:
        The chosen ``node_id``, or ``None`` if nothing was runnable.
    reason:
        Why the scheduler returned this decision (see
        :class:`SchedulerDecisionReason`).
    canonical_evaluation_order:
        Tuple of ``node_id``s, equal to ``graph.canonical_order``.
        Every node in the graph appears here; the order is canonical
        (Step 4 ``(depth, node_id)``).
    evaluated_nodes:
        ``MappingProxyType[str, NodeEvaluation]`` — read-only, one
        entry per node in the graph.
    blocked_nodes:
        Tuple of ``node_id``s whose status is
        ``blocked_by_parents``, in canonical order.
    failed_preconditions:
        Tuple of ``node_id``s whose status is either
        ``blocked_by_precondition`` or
        ``blocked_by_predicate_error``, in canonical order.
    """
    selected_node_id:           str | None
    reason:                     SchedulerDecisionReason
    canonical_evaluation_order: tuple[str, ...]
    evaluated_nodes:            Mapping[str, NodeEvaluation]
    blocked_nodes:              tuple[str, ...]
    failed_preconditions:       tuple[str, ...]

    def fingerprint(self) -> str:
        """Canonical-JSON identity of this scheduler decision.

        Cites D-SCHED-2 (canonical order) and step-5 brief §7. Includes
        the embedded :data:`SCHEDULER_DECISION_FINGERPRINT_VERSION` so
        a forward-incompatible bump is detectable.

        Identical decisions produce byte-identical fingerprints.
        """
        return canonical_dumps({
            "schema_version":             SCHEDULER_DECISION_FINGERPRINT_VERSION,
            "selected_node_id":           self.selected_node_id,
            "reason":                     self.reason.value,
            "canonical_evaluation_order": list(self.canonical_evaluation_order),
            "evaluations": [
                _evaluation_to_canonical_dict(self.evaluated_nodes[nid])
                for nid in self.canonical_evaluation_order
            ],
            "blocked_nodes":              list(self.blocked_nodes),
            "failed_preconditions":       list(self.failed_preconditions),
        })


# ───────────────────────── TopologicalSequentialScheduler ─────────────────────────


class TopologicalSequentialScheduler:
    """Pure-function topological-sequential scheduler.

    The class is stateless: instances hold no fields and behave
    identically. Two instances yield byte-identical decisions for the
    same inputs (proved by tests).

    Provided as a class (rather than a free function) so that future
    alternative schedulers (priority / budgeted / etc.) can be drop-in
    replacements with the same call surface.

    All four scheduler kinds — current and hypothetical future — must
    obey the contract clauses listed at the module docstring. Adding a
    scheduler kind is a deliberate Phase 4C+ extension.
    """

    # ──────────── main API ────────────

    def next_runnable_node(
        self,
        graph: TaskGraph,
        registry: PredicateContext,
        *,
        completed:    AbstractSet[str],
        failed:       AbstractSet[str],
        retry_counts: Mapping[str, int] | None = None,
    ) -> SchedulerDecision:
        """Compute the next runnable node and the full per-node
        evaluation report. Cites D-SCHED-1, D-SCHED-2, D-SCHED-3.

        Parameters
        ----------
        graph:
            The frozen orchestration topology (Step 4).
        registry:
            An immutable :class:`PredicateContext` (Step 3). The
            architecture doc names this ``registry`` for forward
            compatibility with the CellStateRegistry → PredicateContext
            converter that will land with ExecutionSession.
        completed:
            Set of node_ids whose execution has terminally PASSed.
        failed:
            Set of node_ids whose execution has terminally FAILed.
        retry_counts:
            Mapping[node_id, int]. **Step 5 does NOT consult this** —
            accepted for API stability with later steps that will
            implement retry-eligibility filtering. ``None`` is accepted
            and treated as empty.

        Returns
        -------
        SchedulerDecision
            Fresh frozen decision object. Pure function of the inputs.

        Raises
        ------
        SchedulerEvaluationError
            If the input state is illegal (overlapping
            completed/failed, unknown node_ids in any of the three
            input sets/maps). Cites step-5 brief §5.
        """
        # ── 1. Normalise inputs (no mutation of caller state) ──
        # D-SESS-7: we copy into frozensets / a plain dict; the caller's
        # references are never touched.
        completed_fs: frozenset[str] = frozenset(completed)
        failed_fs:    frozenset[str] = frozenset(failed)
        retry_map = dict(retry_counts) if retry_counts is not None else {}

        # ── 2. Illegal-state checks ──
        # Determinism note: every error message lists the offending
        # node_ids sorted lex, so two identical bad inputs yield
        # byte-identical error strings (replayable diagnostics).
        all_ids = set(graph.nodes.keys())

        overlap = sorted(completed_fs & failed_fs)
        if overlap:
            raise SchedulerEvaluationError(
                f"nodes appear in both completed AND failed: {overlap} "
                f"(D-SCHED-1 — scheduler state must be unambiguous)"
            )

        unknown_completed = sorted(completed_fs - all_ids)
        if unknown_completed:
            raise SchedulerEvaluationError(
                f"completed contains unknown node_ids "
                f"(not in graph): {unknown_completed}"
            )

        unknown_failed = sorted(failed_fs - all_ids)
        if unknown_failed:
            raise SchedulerEvaluationError(
                f"failed contains unknown node_ids "
                f"(not in graph): {unknown_failed}"
            )

        unknown_retry = sorted(set(retry_map.keys()) - all_ids)
        if unknown_retry:
            raise SchedulerEvaluationError(
                f"retry_counts contains unknown node_ids "
                f"(not in graph): {unknown_retry}"
            )

        # ── 3. Per-node evaluation in canonical order (D-SCHED-2) ──
        canonical_order: tuple[str, ...] = graph.canonical_order
        evaluations: dict[str, NodeEvaluation] = {}
        selected_node_id: str | None = None

        for node_id in canonical_order:
            # 3a. Terminal states first.
            if node_id in completed_fs:
                evaluations[node_id] = NodeEvaluation(
                    node_id=node_id,
                    status=NODE_STATUS_COMPLETED,
                )
                continue
            if node_id in failed_fs:
                evaluations[node_id] = NodeEvaluation(
                    node_id=node_id,
                    status=NODE_STATUS_FAILED,
                )
                continue

            # 3b. Parent gate. Parents already sorted lex by Step-4
            # graph.parents_of (D-SCHED-5).
            parents = graph.parents_of(node_id)
            incomplete_parents: tuple[str, ...] = tuple(
                p for p in parents if p not in completed_fs
            )
            if incomplete_parents:
                evaluations[node_id] = NodeEvaluation(
                    node_id=node_id,
                    status=NODE_STATUS_BLOCKED_BY_PARENTS,
                    blocked_by_parents=incomplete_parents,
                )
                continue

            # 3c. Preconditions, via Step-3 aggregator (D-SCHED-13).
            node = graph.nodes[node_id]
            group = evaluate_predicates(node.preconditions, registry)

            if not group.ok:
                # Two failure flavours: predicate returned False, vs
                # predicate raised. Both are deterministic and reported
                # as scheduler diagnostics — NOT as raised exceptions.
                if group.error_at is not None:
                    status = NODE_STATUS_BLOCKED_BY_PREDICATE_ERROR
                else:
                    status = NODE_STATUS_BLOCKED_BY_PRECONDITION
                evaluations[node_id] = NodeEvaluation(
                    node_id=node_id,
                    status=status,
                    predicate_group_result=group,
                )
                continue

            # 3d. All checks pass → runnable. First-wins (D-SCHED-2).
            if selected_node_id is None:
                evaluations[node_id] = NodeEvaluation(
                    node_id=node_id,
                    status=NODE_STATUS_SELECTED,
                    predicate_group_result=group,
                )
                selected_node_id = node_id
            else:
                evaluations[node_id] = NodeEvaluation(
                    node_id=node_id,
                    status=NODE_STATUS_RUNNABLE,
                    predicate_group_result=group,
                )

        # ── 4. Determine top-level reason ──
        if selected_node_id is not None:
            reason = SchedulerDecisionReason.SELECTED
        else:
            # ``pending`` = nodes neither completed nor failed.
            pending_count = sum(
                1 for nid in canonical_order
                if nid not in completed_fs and nid not in failed_fs
            )
            if pending_count == 0:
                reason = SchedulerDecisionReason.ALL_NODES_TERMINAL
            else:
                reason = SchedulerDecisionReason.NO_RUNNABLE_NODES_PENDING

        # ── 5. Aggregate diagnostic tuples in canonical order ──
        blocked_nodes: tuple[str, ...] = tuple(
            nid for nid in canonical_order
            if evaluations[nid].status == NODE_STATUS_BLOCKED_BY_PARENTS
        )
        failed_preconditions: tuple[str, ...] = tuple(
            nid for nid in canonical_order
            if evaluations[nid].status in (
                NODE_STATUS_BLOCKED_BY_PRECONDITION,
                NODE_STATUS_BLOCKED_BY_PREDICATE_ERROR,
            )
        )

        return SchedulerDecision(
            selected_node_id=selected_node_id,
            reason=reason,
            canonical_evaluation_order=canonical_order,
            evaluated_nodes=MappingProxyType(evaluations),
            blocked_nodes=blocked_nodes,
            failed_preconditions=failed_preconditions,
        )
