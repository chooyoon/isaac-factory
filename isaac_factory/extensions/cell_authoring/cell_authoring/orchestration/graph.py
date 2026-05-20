"""Deterministic TaskGraph topology (Phase 4B step 4).

Pure-declarative orchestration topology. Step 4 establishes the
structural-replay-identity contract: identical inputs (modulo iteration
order) produce byte-identical canonical forms + byte-identical
fingerprints. There is NO execution here — no scheduler, no traversal-
at-runtime, no PhysX, no event bus integration. The graph is a
replay-authoritative topology contract.

Contract clauses honoured
-------------------------
D-SCHED-1   — TaskGraph methods are pure functions of their inputs.
D-SCHED-2   — DAG traversal order is canonical: ``(depth, node_id)``.
D-SCHED-3   — Same canonical key used everywhere ordering matters.
D-SCHED-4   — Duplicate ``node_id`` rejected at construction.
D-SCHED-5   — Every public iterable is a ``tuple`` constructed via
              explicit ``sorted(...)``; no ``dict.keys()`` /
              ``set`` iteration is observable to callers.
D-SCHED-6   — No dict iteration in canonical paths.
D-SCHED-7   — No set iteration in canonical paths.
D-SCHED-8   — No external graph-library reliance; cycle detection
              is hand-rolled iterative DFS with sorted neighbour
              enumeration.

D-SESS-7    — Graph state is read-only externally; no mutation API.
D-SESS-8    — All structural dataclasses are
              ``@dataclass(frozen=True, slots=True)``.

D-FORBID-3  — No hidden mutable caches: depths / canonical_order are
              computed once at build() and stored as immutable fields.
D-FORBID-4  — Runtime graph mutation is impossible (frozen).
D-FORBID-7  — Construction-order independence proved by tests.
D-FORBID-8  — Graph behaviour depends only on (nodes, edges) inputs.

Explicitly deferred (documented to prevent implicit creep later)
----------------------------------------------------------------
* Scheduler runtime (step 5).
* Retries / failure_action / retry_budget on TaskNode (not in scope
  for step-4 topology — they are scheduler-runtime metadata).
* Conditional branching / loops / temporal dependencies / dynamic
  graph mutation.
* Distributed graphs / multi-cell orchestration.
* Priority arbitration (step-4 ``priority`` is descriptive; no
  selection logic).
* Resource locking.
* Graph persistence on disk (the fingerprint string is the canonical
  replay identifier; a serialisation policy comes later).
* All-cycles enumeration (Johnson's algorithm). Step 4 reports ONE
  deterministically-chosen cycle; the scheduler does not need more.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .package import canonical_dumps
from .predicates import Predicate


class FailureAction(enum.Enum):
    """Per-edge cascade policy on parent-node failure.

    Cites D-FAULT-3a — per-edge enumeration on :class:`TaskGraph`, immutable
    after :py:meth:`TaskGraph.build`. Live mutation of ``FailureAction``
    after build is FORBIDDEN (D-FAULT-15 #13, D-SCHED-8 frozen-graph
    invariant).

    Members
    -------
    SKIP_NODE:
        (default) Descendants of the failed node cascade-skipped; siblings
        unaffected. Sibling-tolerant default per the §F.3 Phase-2 ruling.
    ABORT_COHORT:
        Descendants AND all fan-out siblings of the failure point
        cascade-skipped.
    ABORT_JOB:
        Session → ``FAILED``; all remaining pending nodes
        cascade-skipped uniformly.
    """
    SKIP_NODE    = "SKIP_NODE"
    ABORT_COHORT = "ABORT_COHORT"
    ABORT_JOB    = "ABORT_JOB"


# ───────────────────────── version / constants ─────────────────────────


GRAPH_FINGERPRINT_VERSION: int = 2
"""Canonical fingerprint schema version (D-SCHED-2). Bumped on any
fingerprint format change. Bump policy is intentionally undocumented
until the first compatibility break."""


# ───────────────────────────── errors ─────────────────────────────


class GraphValidationError(RuntimeError):
    """Raised by :py:meth:`TaskGraph.build` when validation fails.

    The exception's ``args[0]`` is a human-readable summary; the full
    canonical-ordered issue list is available as ``.report`` (a
    :class:`GraphValidationReport`). Cites D-SCHED-4 (duplicate rejection)
    and D-SCHED-2 (canonical error ordering).
    """

    def __init__(self, message: str, report: "GraphValidationReport") -> None:
        super().__init__(message)
        self.report: "GraphValidationReport" = report


# ───────────────────────────── validation report ─────────────────────────────


# Error / warning codes — stable identifiers, used in fingerprints and
# canonical sort keys. Adding a code is additive; renaming is a break.
ERROR_DUPLICATE_NODE_ID:     str = "DUPLICATE_NODE_ID"
ERROR_DUPLICATE_EDGE:        str = "DUPLICATE_EDGE"
ERROR_SELF_EDGE:             str = "SELF_EDGE"
ERROR_EDGE_UNKNOWN_NODE:     str = "EDGE_UNKNOWN_NODE"
ERROR_CYCLE:                 str = "CYCLE"


@dataclass(frozen=True, slots=True)
class GraphValidationIssue:
    """One structural problem with a TaskGraph proposal.

    Frozen (D-SESS-8). Fields are JSON-serialisable so the fingerprint
    can be canonical-encoded.

    Fields
    ------
    severity: ``"error"`` or ``"warning"``.
    code:     stable identifier (see ``ERROR_*`` constants above).
    locator:  JSON-serialisable dict pin-pointing the offending bit
              (e.g. ``{"node_id": "n1"}`` for DUPLICATE_NODE_ID,
              ``{"cycle": ["a", "b", "a"]}`` for CYCLE).
    message:  short human-readable explanation.
    """
    severity: str
    code:     str
    locator:  Mapping[str, Any]
    message:  str

    def __post_init__(self) -> None:
        # Wrap locator in MappingProxyType for deep immutability.
        # Construction-time normalization, not post-construction mutation,
        # so this is within the spirit of D-FORBID-14.
        if not isinstance(self.locator, MappingProxyType):
            object.__setattr__(self, "locator",
                                MappingProxyType(dict(self.locator)))

    def fingerprint(self) -> str:
        """Canonical-JSON identity of this issue. Two equal issues
        (same severity / code / locator) produce byte-identical
        fingerprints. Used as the canonical sort key."""
        return canonical_dumps({
            "severity": self.severity,
            "code":     self.code,
            "locator":  dict(self.locator),
        })


@dataclass(frozen=True, slots=True)
class GraphValidationReport:
    """Outcome of :py:meth:`TaskGraph.validate`. Frozen (D-SESS-8).

    ``ok`` is True iff ``errors == ()``. Warnings do not affect ``ok``.
    All tuples are in canonical order (sorted by issue fingerprint),
    so two equivalent malformed graphs produce identical reports.
    """
    ok:                            bool
    errors:                        tuple[GraphValidationIssue, ...]
    warnings:                      tuple[GraphValidationIssue, ...]
    canonical_error_fingerprints:  tuple[str, ...]


# ───────────────────────────── node / edge ─────────────────────────────


@dataclass(frozen=True, slots=True)
class TaskNode:
    """Declarative description of one orchestration node.

    Frozen (D-SESS-8); slots-backed to forbid attribute injection.

    Fields
    ------
    node_id:
        Stable string identifier, unique within a graph (D-SCHED-4).
    task_ref:
        Pointer to the task this node executes. Step 4 holds this as
        an opaque string; a typed binding to Phase 4A's
        ``TaskDefinition`` is a deliberate later-step concern.
    priority:
        Integer priority. Lower = earlier in scheduler selection.
        Step 4 is purely descriptive — no selection logic uses this.
    preconditions / postconditions:
        Tuples of step-3 :class:`Predicate`s in CONSTRUCTION ORDER
        (preserved per D-SCHED-13). The aggregator
        :py:func:`evaluate_predicates` short-circuits in this order
        at scheduler time (later step).
    metadata:
        Free-form, JSON-serialisable, ``MappingProxyType``-wrapped.
        Wraps in __post_init__ if a plain dict is passed.
    """
    node_id:        str
    task_ref:       str = ""
    priority:       int = 0
    preconditions:  tuple[Predicate, ...] = ()
    postconditions: tuple[Predicate, ...] = ()
    metadata:       Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        # Normalize collections (construction-time, not post-mutation —
        # within the spirit of D-FORBID-14). Tuples for predicate
        # sequences (preserves D-SCHED-13 ordering); MappingProxyType
        # for metadata (prevents external-reference mutation).
        if not isinstance(self.preconditions, tuple):
            object.__setattr__(self, "preconditions", tuple(self.preconditions))
        if not isinstance(self.postconditions, tuple):
            object.__setattr__(self, "postconditions", tuple(self.postconditions))
        if not isinstance(self.metadata, MappingProxyType):
            object.__setattr__(self, "metadata",
                                MappingProxyType(dict(self.metadata)))

    def fingerprint(self) -> str:
        """Canonical-JSON identity of this node + its attachments.

        Predicates contribute via their own ``fingerprint()`` strings,
        treated as opaque content tags (not re-parsed). Predicate
        ORDER is preserved (D-SCHED-13).
        """
        return canonical_dumps({
            "node_id":         self.node_id,
            "task_ref":        self.task_ref,
            "priority":        self.priority,
            "preconditions":   [p.fingerprint() for p in self.preconditions],
            "postconditions":  [p.fingerprint() for p in self.postconditions],
            "metadata":        dict(self.metadata),
        })


@dataclass(frozen=True, slots=True)
class TaskEdge:
    """Directed dependency edge: ``parent_id`` must complete before
    ``child_id`` may start. Frozen (D-SESS-8). Hashable, so the
    validator can detect duplicates via a set; the canonical edge
    tuple in :class:`TaskGraph` is sorted by ``(parent_id, child_id)``.

    The ``failure_action`` field (D-FAULT-3a) governs cascade behaviour
    when ``parent_id`` fails. Defaults to :py:attr:`FailureAction.SKIP_NODE`
    (sibling-tolerant; sibling-strict requires explicit ``ABORT_COHORT``).
    The field is immutable after :py:meth:`TaskGraph.build` per D-SCHED-8;
    live mutation is FORBIDDEN per D-FAULT-15 #13.
    """
    parent_id:      str
    child_id:       str
    failure_action: FailureAction = FailureAction.SKIP_NODE


# ───────────────────────── internal helpers ─────────────────────────


def _build_child_adjacency(
    node_ids: tuple[str, ...],
    edges: Iterable[TaskEdge],
) -> dict[str, tuple[str, ...]]:
    """Build sorted-children adjacency. Used by cycle detection and
    canonical-order computation. Cites D-SCHED-5 (sorted iteration)."""
    node_set = set(node_ids)
    children: dict[str, list[str]] = {n: [] for n in node_ids}
    for e in edges:
        # Skip malformed edges (self-edges and missing-node-ref edges)
        # so cycle detection on a malformed graph does not crash; the
        # malformed edges are reported separately as their own errors.
        if e.parent_id == e.child_id:
            continue
        if e.parent_id not in node_set or e.child_id not in node_set:
            continue
        children[e.parent_id].append(e.child_id)
    return {n: tuple(sorted(cs)) for n, cs in children.items()}


def _detect_cycle(
    adjacency: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...] | None:
    """Deterministic single-cycle detector. Returns the cycle path as
    a tuple ``(v0, v1, ..., vk, v0)`` where ``v0`` is the
    lex-minimum node in the cycle, traversed in DFS direction.
    Returns ``None`` if no cycle.

    Iterative DFS, sorted-neighbour enumeration, sorted start-node
    enumeration. Cites D-SCHED-2 (canonical traversal) and D-SCHED-8
    (no external graph library).
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in adjacency}
    parent: dict[str, str | None] = {}

    for start in sorted(adjacency.keys()):  # D-SCHED-5
        if color[start] != WHITE:
            continue

        # Iterative DFS stack. Each frame is (node, remaining children
        # as a list — mutated in place to track DFS progress).
        stack: list[tuple[str, list[str]]] = [
            (start, list(adjacency.get(start, ())))
        ]
        color[start] = GRAY
        parent[start] = None

        while stack:
            node, remaining = stack[-1]
            if not remaining:
                color[node] = BLACK
                stack.pop()
                continue
            child = remaining.pop(0)  # first remaining (sorted)

            child_color = color.get(child, BLACK)
            if child_color == WHITE:
                color[child] = GRAY
                parent[child] = node
                stack.append((child, list(adjacency.get(child, ()))))
            elif child_color == GRAY:
                # Back edge: child is an ancestor of node.
                # Reconstruct cycle node → parent[node] → … → child.
                path: list[str] = [node]
                cur = parent.get(node)
                while cur is not None and cur != child:
                    path.append(cur)
                    cur = parent.get(cur)
                path.append(child)
                path.reverse()           # child → … → node
                # Canonicalize: rotate so lex-min node is first.
                min_idx = path.index(min(path))
                rotated = path[min_idx:] + path[:min_idx]
                rotated.append(rotated[0])  # close the cycle
                return tuple(rotated)
            # else BLACK: cross / forward edge — ignore.

    return None


def _compute_depths(
    node_ids: tuple[str, ...],
    edges: Iterable[TaskEdge],
) -> dict[str, int]:
    """Longest-path depth from any root, per node. Assumes the graph
    is acyclic (caller has verified). Iterative DFS to avoid recursion-
    depth limits on wide graphs. Cites D-SCHED-2."""
    node_set = set(node_ids)
    parents: dict[str, list[str]] = {n: [] for n in node_ids}
    for e in edges:
        if e.parent_id == e.child_id:
            continue
        if e.parent_id not in node_set or e.child_id not in node_set:
            continue
        parents[e.child_id].append(e.parent_id)
    # Sort parent lists for deterministic iteration.
    parents_sorted: dict[str, tuple[str, ...]] = {
        n: tuple(sorted(ps)) for n, ps in parents.items()
    }

    depth: dict[str, int] = {}

    def visit(n: str) -> int:
        # Iterative two-phase post-order: first push children to compute,
        # then pop and resolve. Two-state per node: 0=entered, 1=resolved.
        stack: list[tuple[str, int]] = [(n, 0)]
        while stack:
            cur, state = stack.pop()
            if cur in depth:
                continue
            if state == 0:
                ps = parents_sorted[cur]
                # Re-push current as "resolve" then push unresolved parents.
                stack.append((cur, 1))
                for p in ps:
                    if p not in depth:
                        stack.append((p, 0))
            else:
                ps = parents_sorted[cur]
                if not ps:
                    depth[cur] = 0
                else:
                    depth[cur] = max(depth[p] for p in ps) + 1
        return depth[n]

    for n in sorted(node_ids):  # D-SCHED-5
        visit(n)

    return depth


# ───────────────────────────── TaskGraph ─────────────────────────────


@dataclass(frozen=True, slots=True)
class TaskGraph:
    """Immutable orchestration topology.

    Construct via :py:meth:`build`. Direct construction is permitted
    only if the caller has already normalised and validated the inputs
    (the constructor performs no validation — that is :py:meth:`build`'s
    job). For external callers, :py:meth:`build` is the only sane entry
    point.

    Fields
    ------
    nodes:
        ``MappingProxyType[str, TaskNode]`` — read-only, keyed by
        ``node_id``. Insertion order is alphabetical by ``node_id``
        but iteration of this mapping is intentionally not part of the
        public canonical surface (use :py:meth:`canonical_node_ids`).
    edges:
        Tuple of :class:`TaskEdge`, **sorted lex by
        ``(parent_id, child_id)``** (D-SCHED-2). Duplicate edges have
        already been rejected at build().
    depths:
        ``MappingProxyType[str, int]`` — longest-path depth from any
        root. Equal to the depth used by canonical ordering.
    canonical_order:
        Tuple of ``node_id`` in canonical order: primary key ``depth``,
        secondary key ``node_id`` lexicographic (D-SCHED-2/3). This is
        also a valid topological order; ``topological_order()`` returns
        it verbatim.
    """
    nodes:           Mapping[str, TaskNode]
    edges:           tuple[TaskEdge, ...]
    depths:          Mapping[str, int]
    canonical_order: tuple[str, ...]

    # ─────────────── construction ───────────────

    @classmethod
    def validate(
        cls,
        *,
        nodes: Iterable[TaskNode],
        edges: Iterable[TaskEdge],
    ) -> GraphValidationReport:
        """Run all structural checks; return a canonical-ordered
        :class:`GraphValidationReport`. Does NOT raise.

        Checks (each contributes zero or more issues to the report):

          * **Duplicate node_id** (D-SCHED-4): two nodes share the same
            ``node_id``. Issue per duplicate identifier.
          * **Self-edge**: ``parent_id == child_id`` (D-FORBID-4 spirit).
          * **Duplicate edge**: same ``(parent_id, child_id)`` pair
            appears more than once.
          * **Edge references unknown node**: ``parent_id`` or
            ``child_id`` not in nodes.
          * **Cycle** (D-SCHED-2): at least one directed cycle exists.
            Step 4 reports one canonicalised cycle (lex-min start).

        Step 4 emits no warnings; the ``warnings`` tuple is always empty.
        Disconnected sub-graphs are LEGAL (the scheduler decides
        admissibility, per the architecture doc).
        """
        node_list = list(nodes)
        edge_list = list(edges)

        errors: list[GraphValidationIssue] = []

        # ── 1. duplicate node_id (D-SCHED-4) ──
        id_counts: dict[str, int] = {}
        for n in node_list:
            id_counts[n.node_id] = id_counts.get(n.node_id, 0) + 1
        for nid in sorted(id_counts.keys()):
            if id_counts[nid] > 1:
                errors.append(GraphValidationIssue(
                    severity="error",
                    code=ERROR_DUPLICATE_NODE_ID,
                    locator={"node_id": nid, "occurrences": id_counts[nid]},
                    message=(
                        f"node_id={nid!r} appears {id_counts[nid]} times; "
                        f"must be unique"
                    ),
                ))

        # Build the *unique* id set for downstream checks; if duplicates
        # exist they will still appear in the report. We use a sorted
        # tuple so all downstream iteration is canonical.
        unique_ids = tuple(sorted({n.node_id for n in node_list}))

        # ── 2. self-edges ──
        for e in edge_list:
            if e.parent_id == e.child_id:
                errors.append(GraphValidationIssue(
                    severity="error",
                    code=ERROR_SELF_EDGE,
                    locator={"node_id": e.parent_id},
                    message=(
                        f"self-edge on node_id={e.parent_id!r}; "
                        f"self-loops are forbidden"
                    ),
                ))

        # ── 3. duplicate edges ──
        edge_counts: dict[tuple[str, str], int] = {}
        for e in edge_list:
            key = (e.parent_id, e.child_id)
            edge_counts[key] = edge_counts.get(key, 0) + 1
        for key in sorted(edge_counts.keys()):
            if edge_counts[key] > 1:
                errors.append(GraphValidationIssue(
                    severity="error",
                    code=ERROR_DUPLICATE_EDGE,
                    locator={
                        "parent_id":   key[0],
                        "child_id":    key[1],
                        "occurrences": edge_counts[key],
                    },
                    message=(
                        f"edge ({key[0]!r} → {key[1]!r}) appears "
                        f"{edge_counts[key]} times; edges must be unique"
                    ),
                ))

        # ── 4. edges referencing unknown nodes ──
        unique_id_set = set(unique_ids)
        for e in edge_list:
            unknown: list[str] = []
            if e.parent_id not in unique_id_set:
                unknown.append(e.parent_id)
            if e.child_id not in unique_id_set and e.child_id != e.parent_id:
                unknown.append(e.child_id)
            for u in sorted(set(unknown)):
                errors.append(GraphValidationIssue(
                    severity="error",
                    code=ERROR_EDGE_UNKNOWN_NODE,
                    locator={
                        "parent_id":   e.parent_id,
                        "child_id":    e.child_id,
                        "unknown_id":  u,
                    },
                    message=(
                        f"edge ({e.parent_id!r} → {e.child_id!r}) "
                        f"references unknown node_id={u!r}"
                    ),
                ))

        # ── 5. cycle detection ──
        # Build adjacency from edges that reference known nodes only.
        # Cycle detection on a partially-malformed graph is still valuable
        # — but only for edges that resolve.
        adjacency = _build_child_adjacency(unique_ids, edge_list)
        cycle = _detect_cycle(adjacency)
        if cycle is not None:
            errors.append(GraphValidationIssue(
                severity="error",
                code=ERROR_CYCLE,
                locator={"cycle": list(cycle)},
                message=(
                    "directed cycle detected: " + " → ".join(cycle)
                ),
            ))

        # ── canonicalise issue ordering ──
        # Sort by fingerprint, which is canonical-JSON of (severity,
        # code, locator) — deterministic regardless of construction order.
        errors_sorted = tuple(
            sorted(errors, key=lambda i: i.fingerprint())
        )
        warnings_sorted: tuple[GraphValidationIssue, ...] = ()
        error_fingerprints = tuple(i.fingerprint() for i in errors_sorted)

        return GraphValidationReport(
            ok=(len(errors_sorted) == 0),
            errors=errors_sorted,
            warnings=warnings_sorted,
            canonical_error_fingerprints=error_fingerprints,
        )

    @classmethod
    def build(
        cls,
        *,
        nodes: Iterable[TaskNode],
        edges: Iterable[TaskEdge] = (),
    ) -> "TaskGraph":
        """Validate inputs and construct a canonical :class:`TaskGraph`.

        Raises :class:`GraphValidationError` (with the full
        :class:`GraphValidationReport` attached as ``.report``) if any
        structural problem is found. On success, returns a frozen graph
        whose fields are deterministically ordered.
        """
        node_tuple = tuple(nodes)
        edge_tuple = tuple(edges)

        report = cls.validate(nodes=node_tuple, edges=edge_tuple)
        if not report.ok:
            # Build a short human-readable message that names the codes,
            # in canonical order.
            codes = ", ".join(i.code for i in report.errors)
            raise GraphValidationError(
                f"TaskGraph.build failed validation: {codes}",
                report,
            )

        # Canonicalise: sort nodes by node_id, edges by (parent, child).
        # All inputs are already validated to be unique.
        sorted_node_list = sorted(node_tuple, key=lambda n: n.node_id)
        node_map = MappingProxyType(
            {n.node_id: n for n in sorted_node_list}
        )
        canonical_edges = tuple(
            sorted(edge_tuple, key=lambda e: (e.parent_id, e.child_id))
        )

        # Compute derived structures once at build time (D-FORBID-3:
        # no hidden mutable caches; everything is stored as immutable
        # fields).
        node_ids = tuple(sorted(node_map.keys()))
        depths = _compute_depths(node_ids, canonical_edges)
        canonical_order = tuple(sorted(
            node_ids,
            key=lambda n: (depths[n], n),
        ))

        return cls(
            nodes=node_map,
            edges=canonical_edges,
            depths=MappingProxyType(depths),
            canonical_order=canonical_order,
        )

    # ─────────────── read-only inspection ───────────────

    def node_ids(self) -> tuple[str, ...]:
        """All ``node_id``s sorted lex."""
        return tuple(sorted(self.nodes.keys()))

    def topological_order(self) -> tuple[str, ...]:
        """A canonical topological order. Equal to ``canonical_order``;
        ``(depth, node_id)`` is a valid topological key (D-SCHED-2)."""
        return self.canonical_order

    def parents_of(self, node_id: str) -> tuple[str, ...]:
        """Sorted-lex tuple of parent ``node_id``s. Cites D-SCHED-5."""
        return tuple(sorted(
            e.parent_id for e in self.edges if e.child_id == node_id
        ))

    def children_of(self, node_id: str) -> tuple[str, ...]:
        """Sorted-lex tuple of child ``node_id``s. Cites D-SCHED-5."""
        return tuple(sorted(
            e.child_id for e in self.edges if e.parent_id == node_id
        ))

    def roots(self) -> tuple[str, ...]:
        """Sorted-lex tuple of nodes with no parents."""
        with_parent = {e.child_id for e in self.edges}
        return tuple(sorted(n for n in self.nodes if n not in with_parent))

    def leaves(self) -> tuple[str, ...]:
        """Sorted-lex tuple of nodes with no children."""
        with_child = {e.parent_id for e in self.edges}
        return tuple(sorted(n for n in self.nodes if n not in with_child))

    def depth_of(self, node_id: str) -> int:
        """Longest-path depth from any root."""
        return self.depths[node_id]

    # ─────────────── fingerprint ───────────────

    def fingerprint(self) -> str:
        """Canonical-JSON identity of the entire graph. Cites D-SCHED-2.

        Identical graphs (modulo construction order of inputs) produce
        byte-identical fingerprints. Includes:

          * fingerprint schema version,
          * every node's :py:meth:`TaskNode.fingerprint` (in canonical
            ``node_id`` order),
          * every edge as ``[parent_id, child_id]`` (in canonical order).

        Predicates contribute via their own fingerprint strings, treated
        as opaque content tags.
        """
        return canonical_dumps({
            "schema_version": GRAPH_FINGERPRINT_VERSION,
            "nodes": [
                self.nodes[nid].fingerprint()
                for nid in sorted(self.nodes.keys())
            ],
            "edges": [
                [e.parent_id, e.child_id, e.failure_action.value]
                for e in self.edges
            ],
        })
