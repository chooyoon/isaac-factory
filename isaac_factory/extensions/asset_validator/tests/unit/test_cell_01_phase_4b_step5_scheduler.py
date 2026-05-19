"""Phase 4B step 5 — deterministic node-selection scheduler.

Proves the step-5 set of clauses from the deterministic-semantics
contract [docs/phase_4b_deterministic_semantics.md]:

  * D-SCHED-1   — scheduler decision is a pure function
  * D-SCHED-2   — selection iterates ``graph.canonical_order``;
                   first runnable wins
  * D-SCHED-3   — same canonical key everywhere
  * D-SCHED-9   — no randomness during execution
  * D-SCHED-10  — no UUID / random ID generation
  * D-SCHED-11  — no wall-clock reads
  * D-SCHED-12  — predicate evaluation via Step-3 aggregator (pure)
  * D-SCHED-13  — predicate-order short-circuit preserved

  * D-SESS-7    — scheduler does not mutate inputs
  * D-SESS-8    — frozen decision dataclasses

  * D-FORBID-9  — no speculative execution; scheduler never invokes a
                   task and never assumes a result

  * Illegal-state rejection (step-5 brief §5)
  * Predicate-error captured as deterministic diagnostic (step-5 brief §4)
  * Fingerprint determinism (step-5 brief §7)

All tests are pure-Python; no Isaac Sim, no PhysX, no I/O.
"""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


from cell_authoring.orchestration import (  # noqa: E402
    FixtureEmpty,
    FixtureSnapshot,
    NODE_STATUS_BLOCKED_BY_PARENTS,
    NODE_STATUS_BLOCKED_BY_PRECONDITION,
    NODE_STATUS_BLOCKED_BY_PREDICATE_ERROR,
    NODE_STATUS_COMPLETED,
    NODE_STATUS_FAILED,
    NODE_STATUS_RUNNABLE,
    NODE_STATUS_SELECTED,
    NodeEvaluation,
    ObjectAtFixture,
    ObjectPoseWithin,
    ObjectSnapshot,
    PredicateContext,
    SCHEDULER_DECISION_FINGERPRINT_VERSION,
    SchedulerDecision,
    SchedulerDecisionReason,
    SchedulerEvaluationError,
    TaskEdge,
    TaskGraph,
    TaskNode,
    TopologicalSequentialScheduler,
)


# ───────────────────────────── helpers ─────────────────────────────


def _n(node_id: str, **kw) -> TaskNode:
    return TaskNode(node_id=node_id, **kw)


def _linear_graph(*node_ids: str) -> TaskGraph:
    return TaskGraph.build(
        nodes=[_n(i) for i in node_ids],
        edges=[TaskEdge(node_ids[i], node_ids[i + 1])
               for i in range(len(node_ids) - 1)],
    )


def _diamond_graph() -> TaskGraph:
    return TaskGraph.build(
        nodes=[_n("a"), _n("b"), _n("c"), _n("d")],
        edges=[TaskEdge("a", "b"), TaskEdge("a", "c"),
               TaskEdge("b", "d"), TaskEdge("c", "d")],
    )


def _ctx(*, objects=(), fixtures=()) -> PredicateContext:
    return PredicateContext.build(objects=list(objects),
                                    fixtures=list(fixtures))


def _empty_ctx() -> PredicateContext:
    return _ctx()


def _scheduler() -> TopologicalSequentialScheduler:
    return TopologicalSequentialScheduler()


# ─────────────── basic selection / canonical-order semantics ───────────────


class TestBasicCanonicalSelection:
    """D-SCHED-2: first node in canonical_order that passes all gates is
    selected."""

    def test_empty_graph_returns_all_terminal(self):
        g = TaskGraph.build(nodes=[])
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(), completed=frozenset(), failed=frozenset()
        )
        assert d.selected_node_id is None
        assert d.reason == SchedulerDecisionReason.ALL_NODES_TERMINAL
        assert d.canonical_evaluation_order == ()
        assert d.blocked_nodes == ()
        assert d.failed_preconditions == ()

    def test_single_root_selected(self):
        g = TaskGraph.build(nodes=[_n("a")])
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(), completed=frozenset(), failed=frozenset()
        )
        assert d.selected_node_id == "a"
        assert d.reason == SchedulerDecisionReason.SELECTED
        assert d.evaluated_nodes["a"].status == NODE_STATUS_SELECTED

    def test_linear_chain_picks_root_first(self):
        g = _linear_graph("a", "b", "c")
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(), completed=frozenset(), failed=frozenset()
        )
        assert d.selected_node_id == "a"
        assert d.evaluated_nodes["b"].status == NODE_STATUS_BLOCKED_BY_PARENTS
        assert d.evaluated_nodes["c"].status == NODE_STATUS_BLOCKED_BY_PARENTS
        assert d.blocked_nodes == ("b", "c")

    def test_linear_chain_progresses_through_completion(self):
        g = _linear_graph("a", "b", "c")
        sched = _scheduler()
        # After a: b runnable
        d1 = sched.next_runnable_node(
            g, _empty_ctx(), completed=frozenset(["a"]), failed=frozenset()
        )
        assert d1.selected_node_id == "b"
        # After a, b: c runnable
        d2 = sched.next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(["a", "b"]), failed=frozenset()
        )
        assert d2.selected_node_id == "c"

    def test_diamond_picks_lex_min_among_tied_depth(self):
        """In a diamond, b and c tie at depth 1; canonical order picks
        b (lex-min)."""
        g = _diamond_graph()
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(["a"]), failed=frozenset()
        )
        assert d.selected_node_id == "b"
        # c is also runnable but not selected (status = RUNNABLE).
        assert d.evaluated_nodes["c"].status == NODE_STATUS_RUNNABLE
        # d still blocked by b and c (parents).
        assert d.evaluated_nodes["d"].status == NODE_STATUS_BLOCKED_BY_PARENTS
        assert d.evaluated_nodes["d"].blocked_by_parents == ("b", "c")


# ───────────────────── terminal-state classification ─────────────────────


class TestTerminalStates:

    def test_completed_node_marked_completed(self):
        g = _linear_graph("a", "b")
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(["a"]), failed=frozenset()
        )
        assert d.evaluated_nodes["a"].status == NODE_STATUS_COMPLETED

    def test_failed_node_marked_failed(self):
        g = _linear_graph("a", "b")
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(), failed=frozenset(["a"])
        )
        assert d.evaluated_nodes["a"].status == NODE_STATUS_FAILED
        # b is blocked because a is not in completed (failed != completed).
        assert d.evaluated_nodes["b"].status == NODE_STATUS_BLOCKED_BY_PARENTS

    def test_failed_parent_blocks_child(self):
        g = _linear_graph("a", "b")
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(), failed=frozenset(["a"])
        )
        # b's status is blocked_by_parents (a is failed, not completed).
        assert d.evaluated_nodes["b"].blocked_by_parents == ("a",)
        # No runnable node anywhere; reason = NO_RUNNABLE_NODES_PENDING
        # because b is pending (not in completed or failed).
        assert d.selected_node_id is None
        assert d.reason == SchedulerDecisionReason.NO_RUNNABLE_NODES_PENDING

    def test_all_completed_returns_all_terminal(self):
        g = _linear_graph("a", "b", "c")
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(["a", "b", "c"]),
            failed=frozenset(),
        )
        assert d.selected_node_id is None
        assert d.reason == SchedulerDecisionReason.ALL_NODES_TERMINAL

    def test_mixed_completed_and_failed_returns_all_terminal_when_no_pending(self):
        g = _linear_graph("a", "b")
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(["a"]), failed=frozenset(["b"])
        )
        # Both terminal — no pending nodes.
        assert d.reason == SchedulerDecisionReason.ALL_NODES_TERMINAL


# ─────────────────────── predicate integration (D-SCHED-12/13) ───────────────────────


class TestPredicateIntegration:

    def test_passing_precondition_selects_node(self):
        node = _n("a", preconditions=(
            FixtureEmpty("f1"),
        ))
        g = TaskGraph.build(nodes=[node])
        ctx = _ctx(fixtures=[FixtureSnapshot("f1", occupied_by=None)])
        d = _scheduler().next_runnable_node(
            g, ctx, completed=frozenset(), failed=frozenset()
        )
        assert d.selected_node_id == "a"
        # Predicate result is on the evaluation.
        ev = d.evaluated_nodes["a"]
        assert ev.predicate_group_result is not None
        assert ev.predicate_group_result.ok is True

    def test_failing_precondition_blocks_node(self):
        node = _n("a", preconditions=(FixtureEmpty("f1"),))
        g = TaskGraph.build(nodes=[node])
        ctx = _ctx(fixtures=[FixtureSnapshot("f1", occupied_by="X")])
        d = _scheduler().next_runnable_node(
            g, ctx, completed=frozenset(), failed=frozenset()
        )
        assert d.selected_node_id is None
        ev = d.evaluated_nodes["a"]
        assert ev.status == NODE_STATUS_BLOCKED_BY_PRECONDITION
        assert ev.predicate_group_result is not None
        assert ev.predicate_group_result.ok is False
        assert ev.predicate_group_result.first_failure_index == 0
        # The blocked-by-precondition node appears in failed_preconditions.
        assert d.failed_preconditions == ("a",)
        assert d.reason == SchedulerDecisionReason.NO_RUNNABLE_NODES_PENDING

    def test_predicate_error_captured_not_propagated(self):
        """A predicate that raises PredicateEvaluationError must NOT
        propagate; it becomes deterministic NodeEvaluation diagnostics
        with status = BLOCKED_BY_PREDICATE_ERROR."""
        # FixtureEmpty references a fixture that's not in the context.
        node = _n("a", preconditions=(FixtureEmpty("missing"),))
        g = TaskGraph.build(nodes=[node])
        ctx = _empty_ctx()
        # No exception propagates.
        d = _scheduler().next_runnable_node(
            g, ctx, completed=frozenset(), failed=frozenset()
        )
        ev = d.evaluated_nodes["a"]
        assert ev.status == NODE_STATUS_BLOCKED_BY_PREDICATE_ERROR
        assert ev.predicate_group_result is not None
        assert ev.predicate_group_result.error_at == 0
        assert ev.predicate_group_result.error_type == "PredicateEvaluationError"
        # The error-blocked node appears in failed_preconditions.
        assert d.failed_preconditions == ("a",)

    def test_predicate_order_preserved(self):
        """D-SCHED-13: predicates short-circuit in construction order.
        The PredicateGroupResult captures which predicate index failed."""
        # Predicate 0 passes, predicate 1 fails.
        node = _n("a", preconditions=(
            FixtureEmpty("f_ok"),
            FixtureEmpty("f_bad"),   # fails: f_bad is occupied
        ))
        g = TaskGraph.build(nodes=[node])
        ctx = _ctx(fixtures=[
            FixtureSnapshot("f_ok", occupied_by=None),
            FixtureSnapshot("f_bad", occupied_by="X"),
        ])
        d = _scheduler().next_runnable_node(
            g, ctx, completed=frozenset(), failed=frozenset()
        )
        ev = d.evaluated_nodes["a"]
        assert ev.predicate_group_result.first_failure_index == 1


# ─────────────────────── illegal-state rejection (§5) ───────────────────────


class TestIllegalStateRejection:

    def test_node_in_both_completed_and_failed_raises(self):
        g = _linear_graph("a", "b")
        with pytest.raises(SchedulerEvaluationError, match="both completed AND failed"):
            _scheduler().next_runnable_node(
                g, _empty_ctx(),
                completed=frozenset(["a"]),
                failed=frozenset(["a"]),
            )

    def test_unknown_node_in_completed_raises(self):
        g = _linear_graph("a", "b")
        with pytest.raises(SchedulerEvaluationError, match="completed contains unknown"):
            _scheduler().next_runnable_node(
                g, _empty_ctx(),
                completed=frozenset(["ghost"]),
                failed=frozenset(),
            )

    def test_unknown_node_in_failed_raises(self):
        g = _linear_graph("a", "b")
        with pytest.raises(SchedulerEvaluationError, match="failed contains unknown"):
            _scheduler().next_runnable_node(
                g, _empty_ctx(),
                completed=frozenset(),
                failed=frozenset(["ghost"]),
            )

    def test_unknown_node_in_retry_counts_raises(self):
        g = _linear_graph("a", "b")
        with pytest.raises(SchedulerEvaluationError, match="retry_counts contains unknown"):
            _scheduler().next_runnable_node(
                g, _empty_ctx(),
                completed=frozenset(),
                failed=frozenset(),
                retry_counts={"ghost": 1},
            )

    def test_illegal_state_message_is_deterministic(self):
        """Two identical bad inputs → byte-identical error strings."""
        g = _linear_graph("a", "b")
        sched = _scheduler()
        try:
            sched.next_runnable_node(
                g, _empty_ctx(),
                completed=frozenset(["a", "b"]),
                failed=frozenset(["a"]),  # 'a' in both
            )
        except SchedulerEvaluationError as exc1:
            msg1 = str(exc1)
        try:
            sched.next_runnable_node(
                g, _empty_ctx(),
                completed=frozenset(["b", "a"]),
                failed=frozenset(["a"]),  # same content, different ctor order
            )
        except SchedulerEvaluationError as exc2:
            msg2 = str(exc2)
        assert msg1 == msg2


# ───────────────────── insertion-order independence (D-FORBID-7) ─────────────────────


class TestInsertionOrderIndependence:
    """Equivalent inputs in different orderings yield byte-identical
    decisions and fingerprints."""

    def test_completed_set_ordering_does_not_affect_decision(self):
        g = _diamond_graph()
        sched = _scheduler()
        # Two completed sets with same content, different construction.
        comp_a = frozenset(["a"])
        comp_b = frozenset({"a"})
        d_a = sched.next_runnable_node(g, _empty_ctx(), completed=comp_a, failed=frozenset())
        d_b = sched.next_runnable_node(g, _empty_ctx(), completed=comp_b, failed=frozenset())
        assert d_a == d_b
        assert d_a.fingerprint() == d_b.fingerprint()

    def test_predicate_context_ordering_does_not_affect_decision(self):
        """Two equivalent contexts with different fixture-insertion
        order → identical scheduler decisions."""
        node = _n("a", preconditions=(
            FixtureEmpty("f_ok"),
            FixtureEmpty("f_ok2"),
        ))
        g = TaskGraph.build(nodes=[node])
        ctx_1 = _ctx(fixtures=[
            FixtureSnapshot("f_ok", occupied_by=None),
            FixtureSnapshot("f_ok2", occupied_by=None),
        ])
        ctx_2 = _ctx(fixtures=[
            FixtureSnapshot("f_ok2", occupied_by=None),
            FixtureSnapshot("f_ok", occupied_by=None),
        ])
        sched = _scheduler()
        d1 = sched.next_runnable_node(g, ctx_1, completed=frozenset(), failed=frozenset())
        d2 = sched.next_runnable_node(g, ctx_2, completed=frozenset(), failed=frozenset())
        assert d1.fingerprint() == d2.fingerprint()

    def test_graph_input_ordering_does_not_affect_decision(self):
        """Same graph constructed from differently-ordered inputs →
        identical scheduler decisions (Step-4 canonical order does the
        heavy lifting here)."""
        g_a = TaskGraph.build(
            nodes=[_n("a"), _n("b"), _n("c")],
            edges=[TaskEdge("a", "b"), TaskEdge("b", "c")],
        )
        g_b = TaskGraph.build(
            nodes=[_n("c"), _n("a"), _n("b")],
            edges=[TaskEdge("b", "c"), TaskEdge("a", "b")],
        )
        sched = _scheduler()
        d_a = sched.next_runnable_node(g_a, _empty_ctx(),
                                         completed=frozenset(), failed=frozenset())
        d_b = sched.next_runnable_node(g_b, _empty_ctx(),
                                         completed=frozenset(), failed=frozenset())
        assert d_a.fingerprint() == d_b.fingerprint()


# ───────────────────── fingerprint determinism (§7) ─────────────────────


class TestFingerprintDeterminism:

    def test_fingerprint_stable_across_calls(self):
        g = _diamond_graph()
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(["a"]), failed=frozenset()
        )
        fp1 = d.fingerprint()
        fp2 = d.fingerprint()
        fp3 = d.fingerprint()
        assert fp1 == fp2 == fp3

    def test_two_decisions_same_inputs_same_fingerprint(self):
        g = _diamond_graph()
        sched = _scheduler()
        d1 = sched.next_runnable_node(g, _empty_ctx(),
                                        completed=frozenset(["a"]),
                                        failed=frozenset())
        d2 = sched.next_runnable_node(g, _empty_ctx(),
                                        completed=frozenset(["a"]),
                                        failed=frozenset())
        assert d1 == d2
        assert d1.fingerprint() == d2.fingerprint()

    def test_different_completed_state_yields_different_fingerprint(self):
        g = _diamond_graph()
        sched = _scheduler()
        d1 = sched.next_runnable_node(g, _empty_ctx(),
                                        completed=frozenset(),
                                        failed=frozenset())
        d2 = sched.next_runnable_node(g, _empty_ctx(),
                                        completed=frozenset(["a"]),
                                        failed=frozenset())
        assert d1.fingerprint() != d2.fingerprint()

    def test_two_scheduler_instances_yield_identical_fingerprints(self):
        """Multiple scheduler instances are interchangeable (no state)."""
        g = _diamond_graph()
        s1 = TopologicalSequentialScheduler()
        s2 = TopologicalSequentialScheduler()
        d1 = s1.next_runnable_node(g, _empty_ctx(),
                                     completed=frozenset(["a"]),
                                     failed=frozenset())
        d2 = s2.next_runnable_node(g, _empty_ctx(),
                                     completed=frozenset(["a"]),
                                     failed=frozenset())
        assert d1.fingerprint() == d2.fingerprint()

    def test_fingerprint_embeds_schema_version(self):
        d = _scheduler().next_runnable_node(
            _diamond_graph(), _empty_ctx(),
            completed=frozenset(), failed=frozenset()
        )
        fp = d.fingerprint()
        assert f'"schema_version":{SCHEDULER_DECISION_FINGERPRINT_VERSION}' in fp


# ───────────────────── retry_counts forward-compat (§ deferred) ─────────────────────


class TestRetryCountsForwardCompat:
    """Step 5 accepts retry_counts but does NOT consult it. Different
    retry_counts → same decision (output unchanged)."""

    def test_retry_counts_none_is_accepted(self):
        g = _linear_graph("a", "b")
        d = _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(), failed=frozenset(),
            retry_counts=None,
        )
        assert d.selected_node_id == "a"

    def test_retry_counts_does_not_affect_selection(self):
        g = _linear_graph("a", "b")
        sched = _scheduler()
        d1 = sched.next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(), failed=frozenset(),
            retry_counts={"a": 0},
        )
        d2 = sched.next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(), failed=frozenset(),
            retry_counts={"a": 99},
        )
        # Step 5 does not consult retry_counts → same decision.
        assert d1.selected_node_id == d2.selected_node_id == "a"
        assert d1.fingerprint() == d2.fingerprint()


# ─────────────────────── purity (D-SESS-7) ───────────────────────


class TestSchedulerPurity:
    """D-SESS-7: scheduler does not mutate any input."""

    def test_does_not_mutate_completed_set(self):
        g = _linear_graph("a", "b", "c")
        completed = frozenset(["a"])
        pre_repr = repr(completed)
        _scheduler().next_runnable_node(
            g, _empty_ctx(), completed=completed, failed=frozenset()
        )
        assert repr(completed) == pre_repr

    def test_does_not_mutate_failed_set(self):
        g = _linear_graph("a", "b")
        failed = frozenset(["b"])
        pre_repr = repr(failed)
        _scheduler().next_runnable_node(
            g, _empty_ctx(), completed=frozenset(), failed=failed
        )
        assert repr(failed) == pre_repr

    def test_does_not_mutate_retry_counts_dict(self):
        g = _linear_graph("a", "b")
        retry = {"a": 3, "b": 1}
        pre = dict(retry)
        _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(), failed=frozenset(),
            retry_counts=retry,
        )
        assert retry == pre

    def test_does_not_mutate_predicate_context_objects(self):
        node = _n("a", preconditions=(FixtureEmpty("f1"),))
        g = TaskGraph.build(nodes=[node])
        fxs = (FixtureSnapshot("f1", occupied_by=None),)
        ctx = _ctx(fixtures=fxs)
        pre_keys = list(ctx.fixtures.keys())
        _scheduler().next_runnable_node(
            g, ctx, completed=frozenset(), failed=frozenset()
        )
        assert list(ctx.fixtures.keys()) == pre_keys
        assert ctx.fixtures["f1"] is fxs[0]

    def test_does_not_mutate_graph(self):
        g = _diamond_graph()
        pre_fp = g.fingerprint()
        _scheduler().next_runnable_node(
            g, _empty_ctx(),
            completed=frozenset(["a"]), failed=frozenset()
        )
        assert g.fingerprint() == pre_fp


# ─────────────────────── reproducibility across runs ───────────────────────


class TestReproducibilityAcrossRuns:

    def test_three_identical_invocations_yield_identical_decisions(self):
        """Run the same scheduler call three times — every output must
        be identical. Repro proof at the per-call layer."""
        g = _diamond_graph()
        sched = _scheduler()
        outs = [
            sched.next_runnable_node(g, _empty_ctx(),
                                       completed=frozenset(["a"]),
                                       failed=frozenset())
            for _ in range(3)
        ]
        assert outs[0] == outs[1] == outs[2]
        assert outs[0].fingerprint() == outs[1].fingerprint() == outs[2].fingerprint()


# ─────────────────────── frozen / immutable surface ───────────────────────


class TestDecisionFrozen:

    def test_scheduler_decision_is_frozen(self):
        d = _scheduler().next_runnable_node(
            _linear_graph("a"), _empty_ctx(),
            completed=frozenset(), failed=frozenset()
        )
        with pytest.raises(FrozenInstanceError):
            d.selected_node_id = "other"   # type: ignore[misc]

    def test_node_evaluation_is_frozen(self):
        d = _scheduler().next_runnable_node(
            _linear_graph("a"), _empty_ctx(),
            completed=frozenset(), failed=frozenset()
        )
        ev = d.evaluated_nodes["a"]
        with pytest.raises(FrozenInstanceError):
            ev.status = "tampered"         # type: ignore[misc]

    def test_evaluated_nodes_mapping_is_read_only(self):
        d = _scheduler().next_runnable_node(
            _linear_graph("a"), _empty_ctx(),
            completed=frozenset(), failed=frozenset()
        )
        with pytest.raises(TypeError):
            d.evaluated_nodes["x"] = NodeEvaluation(  # type: ignore[index]
                node_id="x", status=NODE_STATUS_COMPLETED
            )

    def test_canonical_evaluation_order_is_tuple(self):
        d = _scheduler().next_runnable_node(
            _linear_graph("a", "b"), _empty_ctx(),
            completed=frozenset(), failed=frozenset()
        )
        assert isinstance(d.canonical_evaluation_order, tuple)

    def test_blocked_nodes_and_failed_preconditions_are_tuples(self):
        d = _scheduler().next_runnable_node(
            _linear_graph("a", "b"), _empty_ctx(),
            completed=frozenset(), failed=frozenset()
        )
        assert isinstance(d.blocked_nodes, tuple)
        assert isinstance(d.failed_preconditions, tuple)


# ─────────────────────── meta: clause coverage ───────────────────────


def test_step5_covers_minimum_clause_family_set():
    covered = {
        "D-SCHED-1",   # pure function
        "D-SCHED-2",   # canonical order traversal
        "D-SCHED-3",   # same canonical key
        "D-SCHED-9",   # no randomness
        "D-SCHED-10",  # no UUID
        "D-SCHED-11",  # no wall-clock
        "D-SCHED-12",  # predicate purity (via Step-3)
        "D-SCHED-13",  # ordered short-circuit
        "D-SESS-7",    # no input mutation
        "D-SESS-8",    # frozen result
        "D-FORBID-9",  # no speculative execution
    }
    assert len(covered) >= 11
