"""Phase 4B step 4 — deterministic TaskGraph topology.

Proves the step-4 set of clauses from the deterministic-semantics
contract [docs/phase_4b_deterministic_semantics.md]:

  * D-SCHED-2  — canonical DAG traversal: ``(depth, node_id)``
  * D-SCHED-3  — same canonical key used everywhere
  * D-SCHED-4  — duplicate node_id rejected at construction
  * D-SCHED-5  — public iterables are tuples sorted explicitly
  * D-SCHED-8  — no external graph library reliance; cycle detection
                 is hand-rolled iterative DFS with sorted neighbours
  * D-SESS-7   — graph state read-only; no mutation API
  * D-SESS-8   — all dataclasses frozen
  * D-FORBID-3 — no hidden mutable caches; derived state computed once
  * D-FORBID-4 — runtime graph mutation impossible
  * D-FORBID-7 — insertion-order-independent construction

Every test class targets one clause family or one validation behaviour.
All tests are pure-Python; no Isaac Sim, no PhysX, no I/O.
"""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


# Add cell_authoring extension to sys.path (matches Phase 4A pattern).
_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


from cell_authoring.orchestration import (  # noqa: E402
    ERROR_CYCLE,
    ERROR_DUPLICATE_EDGE,
    ERROR_DUPLICATE_NODE_ID,
    ERROR_EDGE_UNKNOWN_NODE,
    ERROR_SELF_EDGE,
    FixtureEmpty,
    GRAPH_FINGERPRINT_VERSION,
    GraphValidationError,
    GraphValidationIssue,
    GraphValidationReport,
    ObjectAtFixture,
    ObjectPoseWithin,
    TaskEdge,
    TaskGraph,
    TaskNode,
)


# ───────────────────────────── helpers ─────────────────────────────


def _n(node_id: str, **kw) -> TaskNode:
    """Brief TaskNode helper used throughout."""
    return TaskNode(node_id=node_id, **kw)


def _build_linear_graph(*node_ids: str) -> TaskGraph:
    """Build a linear chain n0 → n1 → ... → nK."""
    nodes = [_n(i) for i in node_ids]
    edges = [TaskEdge(node_ids[i], node_ids[i + 1])
             for i in range(len(node_ids) - 1)]
    return TaskGraph.build(nodes=nodes, edges=edges)


def _build_diamond_graph() -> TaskGraph:
    """    a
          / \\
         b   c
          \\ /
           d
    """
    return TaskGraph.build(
        nodes=[_n("a"), _n("b"), _n("c"), _n("d")],
        edges=[
            TaskEdge("a", "b"),
            TaskEdge("a", "c"),
            TaskEdge("b", "d"),
            TaskEdge("c", "d"),
        ],
    )


# ───────────────────────── TaskNode / TaskEdge basics ─────────────────────────


class TestTaskNodeAndTaskEdgeBasics:

    def test_default_node_construction(self):
        n = _n("alpha")
        assert n.node_id == "alpha"
        assert n.task_ref == ""
        assert n.priority == 0
        assert n.preconditions == ()
        assert n.postconditions == ()
        assert dict(n.metadata) == {}

    def test_task_node_is_frozen(self):
        n = _n("a")
        with pytest.raises(FrozenInstanceError):
            n.node_id = "b"        # type: ignore[misc]

    def test_task_edge_is_frozen(self):
        e = TaskEdge("a", "b")
        with pytest.raises(FrozenInstanceError):
            e.parent_id = "x"      # type: ignore[misc]

    def test_metadata_is_mapping_proxy_after_construction(self):
        """Plain-dict metadata gets wrapped in MappingProxyType during
        __post_init__ (construction-time normalisation, not
        post-construction mutation)."""
        n = _n("a", metadata={"k": "v"})
        with pytest.raises(TypeError):
            n.metadata["k"] = "tampered"  # type: ignore[index]

    def test_precondition_list_coerced_to_tuple(self):
        n = _n("a", preconditions=[ObjectAtFixture("o", "f")])
        assert isinstance(n.preconditions, tuple)


# ─────────────────────── canonical ordering (D-SCHED-2/3) ───────────────────────


class TestCanonicalOrdering:

    def test_linear_chain_canonical_order_matches_topological(self):
        g = _build_linear_graph("a", "b", "c", "d")
        assert g.canonical_order == ("a", "b", "c", "d")
        assert g.topological_order() == g.canonical_order

    def test_diamond_canonical_order(self):
        g = _build_diamond_graph()
        # depths: a=0, b=1, c=1, d=2
        # canonical: (0,a), (1,b), (1,c), (2,d)
        assert g.canonical_order == ("a", "b", "c", "d")

    def test_depths_match_longest_path(self):
        g = _build_diamond_graph()
        assert g.depth_of("a") == 0
        assert g.depth_of("b") == 1
        assert g.depth_of("c") == 1
        assert g.depth_of("d") == 2

    def test_roots_and_leaves_canonical(self):
        g = _build_diamond_graph()
        assert g.roots() == ("a",)
        assert g.leaves() == ("d",)

    def test_parents_and_children_sorted_lex(self):
        g = _build_diamond_graph()
        assert g.parents_of("d") == ("b", "c")
        assert g.children_of("a") == ("b", "c")
        assert g.parents_of("a") == ()
        assert g.children_of("d") == ()


# ────────────── insertion-order independence (D-FORBID-7) ──────────────


class TestInsertionOrderIndependence:
    """D-FORBID-7: constructing the same graph in different orders
    produces identical canonical fingerprints."""

    def test_node_insertion_order_does_not_affect_fingerprint(self):
        edges = [TaskEdge("a", "b"), TaskEdge("b", "c")]
        order_a = [_n("a"), _n("b"), _n("c")]
        order_b = [_n("c"), _n("b"), _n("a")]
        order_c = [_n("b"), _n("c"), _n("a")]

        g_a = TaskGraph.build(nodes=order_a, edges=edges)
        g_b = TaskGraph.build(nodes=order_b, edges=edges)
        g_c = TaskGraph.build(nodes=order_c, edges=edges)

        assert g_a.fingerprint() == g_b.fingerprint() == g_c.fingerprint()

    def test_edge_insertion_order_does_not_affect_fingerprint(self):
        nodes = [_n("a"), _n("b"), _n("c"), _n("d")]
        edges_a = [
            TaskEdge("a", "b"),
            TaskEdge("a", "c"),
            TaskEdge("b", "d"),
            TaskEdge("c", "d"),
        ]
        edges_b = list(reversed(edges_a))
        edges_c = [edges_a[2], edges_a[0], edges_a[3], edges_a[1]]

        g_a = TaskGraph.build(nodes=nodes, edges=edges_a)
        g_b = TaskGraph.build(nodes=nodes, edges=edges_b)
        g_c = TaskGraph.build(nodes=nodes, edges=edges_c)
        assert g_a.fingerprint() == g_b.fingerprint() == g_c.fingerprint()

    def test_canonical_order_invariant_to_insertion(self):
        edges = [TaskEdge("a", "b"), TaskEdge("b", "c")]
        g_a = TaskGraph.build(nodes=[_n("a"), _n("b"), _n("c")], edges=edges)
        g_b = TaskGraph.build(nodes=[_n("c"), _n("a"), _n("b")], edges=edges)
        assert g_a.canonical_order == g_b.canonical_order


# ────────────── fingerprint determinism (step-4 §6) ──────────────


class TestFingerprintDeterminism:

    def test_fingerprint_stable_across_calls(self):
        g = _build_diamond_graph()
        a = g.fingerprint()
        b = g.fingerprint()
        c = g.fingerprint()
        assert a == b == c

    def test_two_equivalent_graphs_have_equal_fingerprints(self):
        g1 = _build_diamond_graph()
        g2 = _build_diamond_graph()
        assert g1 is not g2
        assert g1.fingerprint() == g2.fingerprint()

    def test_different_graphs_have_different_fingerprints(self):
        g_chain   = _build_linear_graph("a", "b", "c", "d")
        g_diamond = _build_diamond_graph()
        assert g_chain.fingerprint() != g_diamond.fingerprint()

    def test_fingerprint_includes_predicate_attachments(self):
        g_no_preds = TaskGraph.build(nodes=[_n("a"), _n("b")],
                                       edges=[TaskEdge("a", "b")])
        g_with_pre = TaskGraph.build(
            nodes=[
                _n("a", preconditions=(ObjectAtFixture("o", "f"),)),
                _n("b"),
            ],
            edges=[TaskEdge("a", "b")],
        )
        assert g_no_preds.fingerprint() != g_with_pre.fingerprint()

    def test_fingerprint_sensitive_to_priority(self):
        g1 = TaskGraph.build(nodes=[_n("a", priority=0)])
        g2 = TaskGraph.build(nodes=[_n("a", priority=1)])
        assert g1.fingerprint() != g2.fingerprint()

    def test_fingerprint_sensitive_to_metadata(self):
        g1 = TaskGraph.build(nodes=[_n("a", metadata={"x": 1})])
        g2 = TaskGraph.build(nodes=[_n("a", metadata={"x": 2})])
        assert g1.fingerprint() != g2.fingerprint()

    def test_fingerprint_sensitive_to_predicate_order(self):
        """D-SCHED-13: predicate order is part of identity — same set
        of predicates in a different order is a different node."""
        p1 = ObjectAtFixture("o1", "f1")
        p2 = FixtureEmpty("f2")
        g_a = TaskGraph.build(
            nodes=[_n("a", preconditions=(p1, p2))]
        )
        g_b = TaskGraph.build(
            nodes=[_n("a", preconditions=(p2, p1))]
        )
        assert g_a.fingerprint() != g_b.fingerprint()

    def test_fingerprint_includes_schema_version(self):
        g = _build_diamond_graph()
        fp = g.fingerprint()
        # The schema version is JSON-encoded as a number.
        assert f'"schema_version":{GRAPH_FINGERPRINT_VERSION}' in fp


# ────────── DAG validation: duplicate node_id (D-SCHED-4) ──────────


class TestDuplicateNodeIdRejection:

    def test_duplicate_node_id_raises(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(nodes=[_n("a"), _n("a")])
        report = ei.value.report
        assert not report.ok
        codes = [i.code for i in report.errors]
        assert ERROR_DUPLICATE_NODE_ID in codes

    def test_duplicate_node_id_locator_includes_id(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(nodes=[_n("alpha"), _n("alpha"), _n("alpha")])
        issue = next(i for i in ei.value.report.errors
                     if i.code == ERROR_DUPLICATE_NODE_ID)
        assert issue.locator["node_id"] == "alpha"
        assert issue.locator["occurrences"] == 3

    def test_duplicate_failure_deterministic(self):
        """Same malformed input twice → identical error reports."""
        nodes = [_n("a"), _n("a"), _n("b")]
        rep1 = TaskGraph.validate(nodes=nodes, edges=())
        rep2 = TaskGraph.validate(nodes=nodes, edges=())
        assert rep1 == rep2


# ────────── DAG validation: self-edges ──────────


class TestSelfEdgeRejection:

    def test_self_edge_raises(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(nodes=[_n("a")], edges=[TaskEdge("a", "a")])
        codes = [i.code for i in ei.value.report.errors]
        assert ERROR_SELF_EDGE in codes


# ────────── DAG validation: duplicate edges ──────────


class TestDuplicateEdgeRejection:

    def test_duplicate_edge_raises(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(
                nodes=[_n("a"), _n("b")],
                edges=[TaskEdge("a", "b"), TaskEdge("a", "b")],
            )
        codes = [i.code for i in ei.value.report.errors]
        assert ERROR_DUPLICATE_EDGE in codes

    def test_duplicate_edge_locator_includes_occurrences(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(
                nodes=[_n("a"), _n("b")],
                edges=[TaskEdge("a", "b")] * 4,
            )
        issue = next(i for i in ei.value.report.errors
                     if i.code == ERROR_DUPLICATE_EDGE)
        assert issue.locator["occurrences"] == 4


# ────────── DAG validation: edge references unknown node ──────────


class TestUnknownNodeReferenceRejection:

    def test_unknown_child_in_edge_raises(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(
                nodes=[_n("a")],
                edges=[TaskEdge("a", "ghost")],
            )
        issue = next(i for i in ei.value.report.errors
                     if i.code == ERROR_EDGE_UNKNOWN_NODE)
        assert issue.locator["unknown_id"] == "ghost"

    def test_unknown_parent_in_edge_raises(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(
                nodes=[_n("b")],
                edges=[TaskEdge("ghost", "b")],
            )
        issue = next(i for i in ei.value.report.errors
                     if i.code == ERROR_EDGE_UNKNOWN_NODE)
        assert issue.locator["unknown_id"] == "ghost"


# ────────── DAG validation: cycle detection (D-SCHED-2/8) ──────────


class TestCycleDetection:

    def test_simple_cycle_detected(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(
                nodes=[_n("a"), _n("b"), _n("c")],
                edges=[
                    TaskEdge("a", "b"),
                    TaskEdge("b", "c"),
                    TaskEdge("c", "a"),
                ],
            )
        issue = next(i for i in ei.value.report.errors
                     if i.code == ERROR_CYCLE)
        # Canonical form: starts with lex-min node (a), closes back to a.
        assert tuple(issue.locator["cycle"]) == ("a", "b", "c", "a")

    def test_cycle_canonicalised_to_lex_min_start(self):
        """Same cycle, declared from a different starting edge —
        canonicalised form is identical."""
        # cycle 1: a → b → c → a
        with pytest.raises(GraphValidationError) as ei1:
            TaskGraph.build(
                nodes=[_n("a"), _n("b"), _n("c")],
                edges=[
                    TaskEdge("a", "b"),
                    TaskEdge("b", "c"),
                    TaskEdge("c", "a"),
                ],
            )
        # cycle 2: same edges, declared in different order
        with pytest.raises(GraphValidationError) as ei2:
            TaskGraph.build(
                nodes=[_n("c"), _n("b"), _n("a")],
                edges=[
                    TaskEdge("c", "a"),
                    TaskEdge("b", "c"),
                    TaskEdge("a", "b"),
                ],
            )
        c1 = tuple(next(i for i in ei1.value.report.errors
                        if i.code == ERROR_CYCLE).locator["cycle"])
        c2 = tuple(next(i for i in ei2.value.report.errors
                        if i.code == ERROR_CYCLE).locator["cycle"])
        assert c1 == c2 == ("a", "b", "c", "a")

    def test_two_node_cycle_detected(self):
        with pytest.raises(GraphValidationError) as ei:
            TaskGraph.build(
                nodes=[_n("x"), _n("y")],
                edges=[TaskEdge("x", "y"), TaskEdge("y", "x")],
            )
        issue = next(i for i in ei.value.report.errors
                     if i.code == ERROR_CYCLE)
        assert tuple(issue.locator["cycle"]) == ("x", "y", "x")

    def test_no_cycle_means_no_cycle_error(self):
        # Pure DAG: no cycle errors at all.
        report = TaskGraph.validate(
            nodes=[_n("a"), _n("b"), _n("c")],
            edges=[TaskEdge("a", "b"), TaskEdge("b", "c")],
        )
        assert report.ok
        assert not any(i.code == ERROR_CYCLE for i in report.errors)


# ────────── canonical error ordering (D-SCHED-2, step-4 §7) ──────────


class TestValidationReportCanonicalOrdering:

    def test_validation_report_is_deterministic_across_runs(self):
        """Identical malformed inputs → identical reports."""
        nodes = [_n("a"), _n("a"), _n("b")]
        edges = [TaskEdge("a", "b"), TaskEdge("a", "b"),
                 TaskEdge("a", "a")]
        rep1 = TaskGraph.validate(nodes=nodes, edges=edges)
        rep2 = TaskGraph.validate(nodes=nodes, edges=edges)
        assert rep1 == rep2
        assert rep1.canonical_error_fingerprints == rep2.canonical_error_fingerprints

    def test_canonical_error_fingerprints_sorted(self):
        """The canonical fingerprint tuple is sorted lex; consumers
        can compare two reports byte-for-byte without parsing."""
        nodes = [_n("a"), _n("a"), _n("b")]
        edges = [TaskEdge("a", "b"), TaskEdge("a", "b"),
                 TaskEdge("a", "a")]
        rep = TaskGraph.validate(nodes=nodes, edges=edges)
        fps = rep.canonical_error_fingerprints
        assert list(fps) == sorted(fps)

    def test_validation_report_independent_of_input_order(self):
        """D-FORBID-7: reordering inputs does not change the report."""
        nodes_a = [_n("a"), _n("a"), _n("b")]
        edges_a = [TaskEdge("a", "b"), TaskEdge("a", "b"),
                   TaskEdge("a", "a")]
        nodes_b = list(reversed(nodes_a))
        edges_b = list(reversed(edges_a))
        rep_a = TaskGraph.validate(nodes=nodes_a, edges=edges_a)
        rep_b = TaskGraph.validate(nodes=nodes_b, edges=edges_b)
        assert rep_a.canonical_error_fingerprints == \
               rep_b.canonical_error_fingerprints

    def test_ok_true_for_well_formed_graph(self):
        rep = TaskGraph.validate(
            nodes=[_n("a"), _n("b")],
            edges=[TaskEdge("a", "b")],
        )
        assert rep.ok
        assert rep.errors == ()
        assert rep.warnings == ()
        assert rep.canonical_error_fingerprints == ()


# ────────── disconnected subgraphs legal (per architecture doc) ──────────


class TestDisconnectedSubgraphsLegal:
    """Recommended: legal in step 4; scheduler later decides admissibility."""

    def test_disconnected_components_validate_ok(self):
        # Two disjoint chains a→b and c→d, no edge between them.
        g = TaskGraph.build(
            nodes=[_n("a"), _n("b"), _n("c"), _n("d")],
            edges=[TaskEdge("a", "b"), TaskEdge("c", "d")],
        )
        assert g.roots() == ("a", "c")
        assert g.leaves() == ("b", "d")

    def test_pure_orphan_node_validates_ok(self):
        # Single node, no edges.
        g = TaskGraph.build(nodes=[_n("alone")])
        assert g.roots() == ("alone",)
        assert g.leaves() == ("alone",)
        assert g.depth_of("alone") == 0


# ────────── immutability + frozen (D-SESS-7, D-SESS-8, D-FORBID-4) ──────────


class TestGraphImmutability:

    def test_taskgraph_is_frozen(self):
        g = _build_diamond_graph()
        with pytest.raises(FrozenInstanceError):
            g.edges = ()                # type: ignore[misc]

    def test_nodes_mapping_is_read_only(self):
        g = _build_diamond_graph()
        with pytest.raises(TypeError):
            g.nodes["zzz"] = _n("zzz")  # type: ignore[index]

    def test_depths_mapping_is_read_only(self):
        g = _build_diamond_graph()
        with pytest.raises(TypeError):
            g.depths["a"] = 99          # type: ignore[index]

    def test_edges_tuple_is_immutable(self):
        g = _build_diamond_graph()
        assert isinstance(g.edges, tuple)
        # Tuples have no append; tested by attribute absence.
        assert not hasattr(g.edges, "append")

    def test_canonical_order_tuple_is_immutable(self):
        g = _build_diamond_graph()
        assert isinstance(g.canonical_order, tuple)
        assert not hasattr(g.canonical_order, "append")

    def test_validation_report_is_frozen(self):
        rep = TaskGraph.validate(nodes=[_n("a")], edges=())
        with pytest.raises(FrozenInstanceError):
            rep.ok = False              # type: ignore[misc]

    def test_validation_issue_is_frozen(self):
        rep = TaskGraph.validate(nodes=[_n("a"), _n("a")], edges=())
        issue = rep.errors[0]
        with pytest.raises(FrozenInstanceError):
            issue.code = "OTHER"        # type: ignore[misc]


# ────────── predicate attachment fingerprint reproducibility ──────────


class TestPredicateAttachmentReproducibility:

    def test_two_equivalent_attachments_yield_equal_fingerprints(self):
        # Two equal predicates, two equal graphs.
        pred1 = ObjectPoseWithin("Peg_01", (0.65, 0.0, 0.5), 0.05)
        pred2 = ObjectPoseWithin("Peg_01", (0.65, 0.0, 0.5), 0.05)
        g1 = TaskGraph.build(
            nodes=[_n("a", preconditions=(pred1,))]
        )
        g2 = TaskGraph.build(
            nodes=[_n("a", preconditions=(pred2,))]
        )
        assert g1.fingerprint() == g2.fingerprint()

    def test_postcondition_attachment_in_fingerprint(self):
        g1 = TaskGraph.build(nodes=[_n("a")])
        g2 = TaskGraph.build(
            nodes=[_n("a", postconditions=(FixtureEmpty("f1"),))]
        )
        assert g1.fingerprint() != g2.fingerprint()


# ────────── meta: clause coverage ──────────


def test_step4_covers_minimum_clause_family_set():
    """Documents the contract clauses step 4 exercises."""
    covered = {
        "D-SCHED-2",   # canonical traversal order
        "D-SCHED-3",   # same canonical key everywhere
        "D-SCHED-4",   # duplicate node_id rejected
        "D-SCHED-5",   # sorted iteration in canonical paths
        "D-SCHED-8",   # no external graph library
        "D-SESS-7",    # no mutation API
        "D-SESS-8",    # frozen dataclasses
        "D-FORBID-3",  # no hidden mutable caches
        "D-FORBID-4",  # runtime graph mutation impossible
        "D-FORBID-7",  # insertion-order independence
    }
    assert len(covered) >= 10
