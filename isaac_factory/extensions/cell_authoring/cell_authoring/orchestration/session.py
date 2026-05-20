"""ExecutionSession — first runtime-execution layer (Phase 4B step 6).

Step 6 is the **first runtime-execution step**. It introduces mutable
orchestration state and the TaskExecutor integration boundary. The
structural-determinism layers (steps 1-5) remain untouched and continue
to provide the deterministic substrate: EventBus, durable trace,
predicates, TaskGraph, and node-selection scheduler.

ExecutionSession is the **sole mutable orchestration-state authority**
(D-SESS-1). Every other component is read-only with respect to
orchestration state: the scheduler is pure-function, the predicate
layer is pure, the trace recorder is append-only, the event bus
sequences events but does not interpret them. Only the TaskExecutor —
deliberately subordinate to ExecutionSession — mutates simulation
world state.

Scope of step 6
---------------
Single-node execution only. The session can be begun, stepped once
(to execute exactly one ready node), and completed. There is no:

  * multi-node orchestration / DAG traversal at runtime
  * retries
  * recovery
  * pause / resume
  * branching
  * parallel execution
  * dynamic graph mutation

Step 6 proves the runtime-integration plumbing first. Multi-node
runtime is step 8 per the architecture-doc roadmap.


Mutation Authority Matrix  (load-bearing — D-SESS-1, D-SESS-2)
==============================================================

Every piece of state is owned by exactly one component. The matrix
below is **normative**: a code path that violates it is a contract
violation, full stop.

+------------------------+-----------------------------------------------+
| component              | may mutate                                    |
+========================+===============================================+
| ExecutionSession       | orchestration state:                          |
|                        |   * SessionState (lifecycle phase)            |
|                        |   * completed: frozenset[str]                 |
|                        |   * failed: frozenset[str]                    |
|                        |   * retry_counts: Mapping[str, int]           |
|                        |   * NodeRuntimeState per node                 |
|                        | Drives:                                       |
|                        |   * TaskExecutor.prepare/reset/execute/close  |
|                        |   * EventBus.emit (via _emit helper)          |
|                        |   * DurableTraceRecorder.finalize (via close) |
+------------------------+-----------------------------------------------+
| Scheduler              | (none — pure function; D-SCHED-1)             |
+------------------------+-----------------------------------------------+
| Predicate layer        | (none — pure functions; D-SCHED-12)           |
+------------------------+-----------------------------------------------+
| TraceRecorder          | append-only on-disk events.jsonl AND          |
|                        | manifest.json at finalize. May NOT mutate     |
|                        | orchestration state. (D-TRACE-2/3.)           |
+------------------------+-----------------------------------------------+
| EventBus               | seq counter + ordered subscriber dispatch.    |
|                        | May NOT mutate orchestration state.           |
|                        | Subscriber topology is frozen at begin()      |
|                        | (D-BUS-6/7/8).                                |
+------------------------+-----------------------------------------------+
| TaskExecutor           | simulation world only: PhysX scene, robot     |
|                        | drives, object transforms, contact streams.   |
|                        | May NOT mutate: scheduler state, graph state, |
|                        | trace state, EventBus topology, orchestration |
|                        | registry. (D-SESS-1 enforcement.)             |
+------------------------+-----------------------------------------------+
| UnifiedValidator       | validation outputs only — assigns             |
|                        | ``TaskResult.outcome``/``outcome_detail``.    |
|                        | Runs INSIDE Phase 4A's ``TaskExecutor.execute |
|                        | ``; ExecutionSession reads its verdict but    |
|                        | does not re-run it. (D-CONF: single-source-   |
|                        | of-truth validation.)                         |
+------------------------+-----------------------------------------------+

There is no "hidden orchestration mutation path". A would-be Phase 4C
extension that adds a new mutator (e.g. a CheckpointEngine, a
RecoveryCoordinator) MUST extend this matrix in this docstring and
cite the new contract clauses governing its authority.


Execution tick ordering  (cites D-EXEC-1, D-EXEC-2)
===================================================

One call to :py:meth:`ExecutionSession.step` runs the orchestration
tick. Step 6 implements the following sub-phases in fixed order::

   1. scheduler decision         — pure call; reads only inputs
   2. node transition update     — set NodeRuntimeState["running"]
   3. emit NodeSelected          — trace commit
   4. emit NodeExecutionStarted  — trace commit
   5. (pre-execution snapshot)   — captured implicitly via the prior
                                   trace commit + the session snapshot
   6. TaskExecutor.execute(...)  — single mutation path into PhysX;
                                   Phase 4A's execute() runs the
                                   UnifiedValidator INTERNALLY and
                                   returns the validated TaskResult
   7. node transition update     — set NodeRuntimeState["completed"/
                                   "failed"] based on result.passed
   8. emit NodeExecutionCompleted — trace commit
   9. (post-execution snapshot)  — captured implicitly via the prior
                                   trace commit + the session snapshot

Sub-phases 3, 4, 8 are atomic event-emissions; the bus's monotone
seq (D-BUS-3) gives them an unambiguous total order. No phase may be
skipped or reordered.

For step 6 the F-phase (validation) of the D-EXEC-1 7-phase contract
is BUNDLED INTO the D-phase (execute), because Phase 4A's
TaskExecutor.execute() invokes UnifiedValidator internally. This is
correct under the contract — D-CONF requires a single validation
authority, and Phase 4A's design *is* that authority — but means the
ExecutionSession does NOT re-validate after execute() returns. A later
step that introduces post-execute orchestration-level validation
(e.g. registry-level postconditions) would re-introduce a distinct F
phase between sub-phases 7 and 8.


What's deferred (documented to prevent semantic creep)
------------------------------------------------------
* multi-node execution                (step 8)
* retries / retry_budget consumption  (step 9)
* recovery flows                      (later)
* pause / resume                      (later)
* checkpoint continuation             (later)
* distributed execution               (forever out of scope — D-SCALE)
* resource arbitration                (later)
* temporal scheduling                 (later)
* execution parallelism               (forever — D-SCALE-1)
* cross-session orchestration         (later)

What's explicitly NOT in this module
------------------------------------
async execution · thread pools · worker queues · speculative execution
· distributed runtimes · automatic retries · adaptive scheduling ·
optimization passes · metrics dashboards · telemetry pipelines.

These are out of scope by D-SCALE-1, D-FORBID-1, D-FORBID-2,
D-FORBID-9 and the step-6 brief's §12 non-goals list.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from ..tasks.executor import ResetScope
from .events import EventBus, EventEnvelope
from .graph import TaskGraph, TaskNode
from .package import canonical_dumps
from .predicates import PredicateContext
from .scheduler import (
    NODE_STATUS_SELECTED,
    SchedulerDecision,
    SchedulerDecisionReason,
    SchedulerEvaluationError,
    TopologicalSequentialScheduler,
)
from .snapshot import (
    BOUNDARY_SNAPSHOT_KIND_POST_NODE,
    BOUNDARY_SNAPSHOT_KIND_PRE_NODE,
    BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
    BOUNDARY_SNAPSHOT_SCHEMA_VERSION,
    boundary_snapshot,
    boundary_snapshot_hash,
)
from .trace import DurableTraceRecorder


# ───────────────────────── version / constants ─────────────────────────


SESSION_SNAPSHOT_FINGERPRINT_VERSION: int = 2
"""Canonical SessionRuntimeSnapshot fingerprint schema version.

Version history:
  1 — initial schema (Phase 4B Step 6).
  2 — Phase 4B Step 8 / Phase 2: per-task result fingerprint now
      includes ``peg_xyz_initial`` (additive field, replay-authoritative
      under D-CONT-1 when present on the result).
"""


# Runtime event types — stable strings used in trace.jsonl.
# Bumping a name requires a fingerprint-version bump.
EVENT_SESSION_STARTED:          str = "SessionStarted"
EVENT_NODE_SELECTED:            str = "NodeSelected"
EVENT_NODE_EXECUTION_STARTED:   str = "NodeExecutionStarted"
EVENT_NODE_EXECUTION_COMPLETED: str = "NodeExecutionCompleted"
EVENT_SESSION_COMPLETED:        str = "SessionCompleted"
EVENT_SESSION_FAILED:           str = "SessionFailed"
# Phase 4B Step 8 / Phase 2 — authoritative occupancy transitions
# emitted exclusively from ExecutionSession.step() Phase G under
# D-CONT-5. Never emitted from the executor, the validator, the
# scheduler, or any subordinate component.
EVENT_FIXTURE_STATE_CHANGED:    str = "FixtureStateChanged"
# Phase 4B Step 8 / Phase 3 — replay-authoritative boundary snapshot
# emissions. One per checkpoint kind per node-tick (plus one at
# session_initial). Cites D-EXEC-10, D-EXEC-11, D-CONT-6.
# Event payload is minimal (kind + node_id + seq + canonical_hash +
# schema_version) — the full snapshot body lives in the trace via the
# replay tool's snapshot-store, never inside the event.
EVENT_NODE_BOUNDARY_SNAPSHOT:   str = "NodeBoundarySnapshot"


# Per-node runtime statuses — stable strings used in fingerprints.
NODE_RT_PENDING:   str = "pending"
NODE_RT_RUNNING:   str = "running"
NODE_RT_COMPLETED: str = "completed"
NODE_RT_FAILED:    str = "failed"
NODE_RT_SKIPPED:   str = "skipped"   # reserved for later steps; unused in step 6


# ───────────────────────────── errors ─────────────────────────────


class ExecutionSessionError(RuntimeError):
    """Raised on illegal lifecycle transitions or step-6 scope violations.

    Examples:
      * ``step()`` before ``begin()``
      * ``begin()`` after ``begin()`` (re-begin)
      * ``complete()`` before ``begin()``
      * (step 6 only) ``step()`` more than once after the single node
        terminates — step 6 supports single-node only, so subsequent
        ticks are explicit no-ops, NOT errors. The error is raised
        only on lifecycle mistakes, not on idempotent calls.
    """


# ─────────────────────────── enums / state ───────────────────────────


class SessionState(enum.Enum):
    """Top-level lifecycle phase of an ExecutionSession.

    Stable string values used in :class:`SessionRuntimeSnapshot`
    fingerprints (D-SESS-3 — replay-authoritative state).
    """
    INITIALIZED = "INITIALIZED"   # constructed but begin() not called
    RUNNING     = "RUNNING"       # begin() complete; step() pending or in progress
    COMPLETED   = "COMPLETED"     # complete() reached, all nodes terminal-pass
    FAILED      = "FAILED"        # complete() reached, at least one node failed


# ─────────────────────────── frozen value types ───────────────────────────


@dataclass(frozen=True, slots=True)
class NodeRuntimeState:
    """Per-node runtime view. Frozen (D-SESS-8).

    External callers see this via :class:`SessionRuntimeSnapshot`.
    ExecutionSession constructs fresh NodeRuntimeState instances on
    every transition — there is no in-place mutation.
    """
    node_id: str
    status:  str   # NODE_RT_*
    outcome_value:           str  = ""
    task_result_fingerprint: str  = ""


@dataclass(frozen=True, slots=True)
class SessionRuntimeSnapshot:
    """Immutable external view of session state at a point in time.

    Frozen (D-SESS-8). Cites D-SESS-3 (replay-authoritative state must
    be reconstructable). All fields are deterministic; no wall-clock.

    Fields
    ------
    session_state:
        Lifecycle phase.
    completed / failed:
        Frozen-set views of node_ids in each terminal category.
    nodes:
        ``MappingProxyType[node_id, NodeRuntimeState]`` — read-only.
    event_count:
        Number of events emitted on the session's bus so far.
        Equals ``bus.committed_count``.
    """
    session_state: SessionState
    completed:     frozenset[str]
    failed:        frozenset[str]
    nodes:         Mapping[str, NodeRuntimeState]
    event_count:   int

    def fingerprint(self) -> str:
        """Canonical-JSON identity of this snapshot. Two byte-equal
        snapshots from two independent sessions (same inputs) produce
        byte-identical fingerprints."""
        return canonical_dumps({
            "schema_version": SESSION_SNAPSHOT_FINGERPRINT_VERSION,
            "session_state":  self.session_state.value,
            "completed":      sorted(self.completed),
            "failed":         sorted(self.failed),
            "nodes": [
                {
                    "node_id":                 self.nodes[nid].node_id,
                    "status":                  self.nodes[nid].status,
                    "outcome_value":           self.nodes[nid].outcome_value,
                    "task_result_fingerprint": self.nodes[nid].task_result_fingerprint,
                }
                for nid in sorted(self.nodes.keys())
            ],
            "event_count": self.event_count,
        })


# ─────────────────────────── TaskExecutor Protocol ───────────────────────────


@runtime_checkable
class TaskExecutorLike(Protocol):
    """The narrowest TaskExecutor surface ExecutionSession depends on.

    Phase 4A's :class:`cell_authoring.tasks.executor.TaskExecutor`
    conforms structurally; tests can use a pure-Python fake that
    implements the same methods.

    Contract (cites Mutation Authority Matrix above):

      * ``prepare()`` — set up underlying simulation handles. Idempotent.
      * ``reset(scope)`` — restore the cell to a known state. Step 6
        uses ``ResetScope.FULL`` at begin() and ``ResetScope.ACQUIRED_ONLY``
        for between-node resets (the between-node path is not exercised
        in step 6 — single-node only).
      * ``execute(task, **kwargs)`` — run one task end-to-end. Runs
        UnifiedValidator INSIDE Phase 4A's implementation. Returns an
        object whose ``passed`` (bool) and ``outcome`` (string or
        string-valued enum) are read by ExecutionSession.
      * ``close()`` — release simulation handles.

    Implementations MUST NOT mutate orchestration state. They may only
    mutate the simulation world they own.
    """
    def prepare(self) -> None: ...
    def reset(self, scope: ResetScope = ResetScope.FULL) -> None: ...
    def execute(self, task: Any, **kwargs: Any) -> Any: ...
    def close(self) -> None: ...


# ─────────────────────── result extraction helpers ───────────────────────


def _extract_result_passed(result: Any) -> bool:
    """Read ``passed`` from a TaskExecutor result.

    Phase 4A's ``TaskResult`` exposes ``passed`` as a property. Fakes
    and other implementations may expose either ``passed`` (bool) or
    set it via ``outcome == TaskOutcome.PASS``. Default: False.
    """
    return bool(getattr(result, "passed", False))


def _extract_result_outcome_value(result: Any) -> str:
    """Read a stable outcome string from a TaskExecutor result.

    Handles:
      * ``result.outcome`` is an enum with ``.value``,
      * ``result.outcome`` is a plain string,
      * neither — returns ``"UNKNOWN"``.

    Used in event payloads and NodeRuntimeState fingerprints. Strict
    determinism: no wall-clock fields, no Python repr() of objects.
    """
    outcome = getattr(result, "outcome", None)
    if outcome is None:
        return "UNKNOWN"
    if hasattr(outcome, "value"):
        return str(outcome.value)
    return str(outcome)


# ───────────────────────────── ExecutionSession ─────────────────────────────


class ExecutionSession:
    """Sole mutable orchestration-state authority for one job lifetime.

    Cites the Mutation Authority Matrix in this module's docstring.

    Construction
    ------------
    ``__init__`` is pure: no I/O, no event emission, no executor
    setup. Side effects begin only at :py:meth:`begin`.

    Step-6 simplifications (relative to the full architecture-doc
    design):

      * Single-node only. ``step()`` evaluates one tick; if a runnable
        node exists it is executed; if not, ``step()`` is a no-op.
        Calling ``step()`` again after the node terminates is allowed
        (idempotent — re-emits no events, returns the current
        snapshot).
      * No retry consumption. ``retry_counts`` is held internally and
        passed to the scheduler, but the scheduler does not yet
        consult it (step 5) and the session does not yet update it
        (step 9 will).
      * No registry-level postconditions. Step-3 predicates run only
        as scheduler preconditions; postconditions are deferred to a
        later step that introduces orchestration-level validation.

    Order of operations on a step-6 run::

        begin() → step() → complete()
    """

    # ─────────── construction (pure; no side effects) ───────────

    def __init__(
        self,
        *,
        graph:               TaskGraph,
        task_executor:       TaskExecutorLike,
        event_bus:           EventBus,
        trace_recorder:      DurableTraceRecorder | None = None,
        scheduler:           TopologicalSequentialScheduler | None = None,
        predicate_context_provider: Callable[[], PredicateContext] | None = None,
        task_resolver:       Callable[[TaskNode], Any] | None = None,
        execute_kwargs:      Mapping[str, Any] | None = None,
        reset_scope_between_nodes: ResetScope = ResetScope.ACQUIRED_ONLY,
    ) -> None:
        """Construct an ExecutionSession. No side effects.

        Parameters
        ----------
        graph:
            The frozen orchestration topology (Step 4).
        task_executor:
            The (subordinate) execution-layer object — Phase 4A's
            ``TaskExecutor`` in production, a pure-Python fake in
            tests. Must satisfy :class:`TaskExecutorLike`.
        event_bus:
            A fresh :class:`EventBus`. Step 6 calls ``bus.freeze()``
            during ``begin()`` (D-BUS-6/7/8 — topology frozen at
            session start). Callers MUST register subscribers
            (including the trace recorder, if any) before ``begin()``.
        trace_recorder:
            Optional :class:`DurableTraceRecorder`. If provided, it
            should already be registered as a subscriber on
            ``event_bus``. ExecutionSession only uses it to call
            ``finalize()`` at session close.
        scheduler:
            Optional :class:`TopologicalSequentialScheduler`. Defaults
            to a fresh instance — the scheduler is stateless so this
            is safe.
        predicate_context_provider:
            Callable that returns the current
            :class:`PredicateContext` when the scheduler needs one.
            ``None`` defaults to an empty context (no predicates
            attached to nodes will hit a real registry).
        task_resolver:
            Maps a :class:`TaskNode` to the concrete task object that
            ``task_executor.execute`` will receive. ``None`` defaults
            to passing the node itself (the executor must accept that).
        execute_kwargs:
            Extra kwargs forwarded to ``task_executor.execute``.
            ``None`` ⇒ no extras. Defensively wrapped in
            ``MappingProxyType`` at construction time.
        reset_scope_between_nodes:
            Scope used for resets between nodes. Defaults to
            ``ResetScope.ACQUIRED_ONLY``. The first reset (at
            ``begin()``) is ALWAYS ``ResetScope.FULL`` so the cell
            starts from authored conditions.
        """
        self._graph:           TaskGraph = graph
        self._task_executor:   TaskExecutorLike = task_executor
        self._event_bus:       EventBus = event_bus
        self._trace_recorder:  DurableTraceRecorder | None = trace_recorder
        self._scheduler:       TopologicalSequentialScheduler = (
            scheduler if scheduler is not None
            else TopologicalSequentialScheduler()
        )

        self._predicate_context_provider: Callable[[], PredicateContext] = (
            predicate_context_provider
            if predicate_context_provider is not None
            else (lambda: PredicateContext.build())
        )
        self._task_resolver: Callable[[TaskNode], Any] = (
            task_resolver if task_resolver is not None
            else (lambda node: node)
        )
        self._execute_kwargs: Mapping[str, Any] = MappingProxyType(
            dict(execute_kwargs) if execute_kwargs is not None else {}
        )
        self._reset_scope_between_nodes: ResetScope = reset_scope_between_nodes

        # ── mutable orchestration state — ExecutionSession is its sole
        # author (Mutation Authority Matrix).
        self._session_state: SessionState = SessionState.INITIALIZED
        self._completed:     frozenset[str] = frozenset()
        self._failed:        frozenset[str] = frozenset()
        self._retry_counts:  dict[str, int] = {}
        # Per-node runtime: initialised lazily at begin() to "pending".
        self._node_runtime:  dict[str, NodeRuntimeState] = {}

    # ─────────── snapshots / inspection (read-only) ───────────

    def snapshot(self) -> SessionRuntimeSnapshot:
        """Return a frozen snapshot of the current session state.

        Pure read; never mutates anything. Cites D-SESS-8 (frozen
        snapshot value type).
        """
        return SessionRuntimeSnapshot(
            session_state=self._session_state,
            completed=self._completed,
            failed=self._failed,
            nodes=MappingProxyType(dict(self._node_runtime)),
            event_count=self._event_bus.committed_count,
        )

    @property
    def state(self) -> SessionState:
        return self._session_state

    @property
    def graph(self) -> TaskGraph:
        return self._graph

    # ─────────── lifecycle: begin ───────────

    def begin(self) -> None:
        """Transition INITIALIZED → RUNNING. Idempotent? NO — re-begin
        is an illegal-state error (D-SESS-1, lifecycle integrity).

        Side effects, in order:
          1. Freeze the EventBus subscriber topology (D-BUS-6).
          2. Initialise per-node runtime state to "pending".
          3. Emit ``SessionStarted`` event.
          4. ``task_executor.prepare()`` (idempotent in Phase 4A).
          5. ``task_executor.reset(scope=FULL)`` (Phase 4A path).
          6. Transition state → RUNNING.
        """
        if self._session_state != SessionState.INITIALIZED:
            raise ExecutionSessionError(
                f"ExecutionSession.begin() called in state "
                f"{self._session_state.value}; only INITIALIZED is valid "
                f"(D-SESS-1 lifecycle integrity)"
            )

        # 1. Freeze bus topology.
        self._event_bus.freeze()

        # 2. Initialise per-node runtime — every graph node starts pending.
        for nid in self._graph.canonical_order:
            self._node_runtime[nid] = NodeRuntimeState(
                node_id=nid, status=NODE_RT_PENDING,
            )

        # 3. Emit SessionStarted.
        self._emit(EVENT_SESSION_STARTED, payload={
            "graph_fingerprint": self._graph.fingerprint(),
            "node_count":        len(self._graph.nodes),
        })

        # 4. + 5. Prepare + initial full reset (Phase 4A path).
        self._task_executor.prepare()
        self._task_executor.reset(scope=ResetScope.FULL)

        # 5b. Phase 4B Step 8 / Phase 3 — session_initial boundary
        # snapshot (D-EXEC-11). Captures the authoritative continuity
        # state immediately before the first orchestration tick, after
        # the executor has populated the registry via prepare() +
        # FULL reset.
        self._emit_boundary_snapshot(
            kind=BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
            node_id=None,
        )

        # 6. Transition.
        self._session_state = SessionState.RUNNING

    # ─────────── lifecycle: step ───────────

    def step(self) -> SessionRuntimeSnapshot:
        """Run one orchestration tick. Returns the post-tick snapshot.

        Step-6 simplifications:

          * Single-node execution. If the scheduler selects a node,
            it is executed inline within this call. If not, the tick
            is a no-op.
          * Idempotent after terminal. Calling ``step()`` after the
            session reaches an effective terminal state (no more
            runnable nodes) is a clean no-op that re-emits no events.

        Order of operations (see module docstring "Execution tick
        ordering"). Cites D-EXEC-1, D-EXEC-2, D-EXEC-7.
        """
        if self._session_state != SessionState.RUNNING:
            raise ExecutionSessionError(
                f"ExecutionSession.step() called in state "
                f"{self._session_state.value}; only RUNNING is valid "
                f"(D-SESS-1)"
            )

        # 1. Scheduler decision (pure call).
        try:
            decision: SchedulerDecision = self._scheduler.next_runnable_node(
                self._graph,
                self._predicate_context_provider(),
                completed=self._completed,
                failed=self._failed,
                retry_counts=self._retry_counts,
            )
        except SchedulerEvaluationError:
            # Illegal scheduler state should not happen in step 6 because
            # ExecutionSession owns and validates these inputs. Re-raise.
            raise

        # If nothing runnable, the tick is a no-op.
        if decision.selected_node_id is None:
            return self.snapshot()

        node_id = decision.selected_node_id
        node = self._graph.nodes[node_id]

        # 2. Node transition update → "running".
        self._node_runtime[node_id] = NodeRuntimeState(
            node_id=node_id,
            status=NODE_RT_RUNNING,
        )

        # 3. Emit NodeSelected.
        self._emit(EVENT_NODE_SELECTED, payload={
            "node_id":                       node_id,
            "scheduler_decision_fingerprint": decision.fingerprint(),
        })

        # Phase 4B Step 8 / Phase 4 — reset_scope determination.
        # First node of a job uses FULL (Phase 4A authored initial
        # conditions); every subsequent node uses
        # ``self._reset_scope_between_nodes`` (defaults to
        # ACQUIRED_ONLY per D-CONT-4 selective authoritative persistence).
        is_first_node = (len(self._completed) + len(self._failed)) == 0
        node_reset_scope = (
            ResetScope.FULL if is_first_node
            else self._reset_scope_between_nodes
        )

        # 4. Emit NodeExecutionStarted. The reset_scope payload now
        # reflects the actual scope passed to the executor for THIS
        # node — load-bearing for replay-identity comparators.
        self._emit(EVENT_NODE_EXECUTION_STARTED, payload={
            "node_id":     node_id,
            "task_ref":    node.task_ref,
            "reset_scope": node_reset_scope.value,
        })

        # 5. Phase 4B Step 8 / Phase 3 — pre_node boundary snapshot
        # (D-EXEC-10 item 1, "end of Phase C, before any command is
        # issued"). Authoritative-continuity projection only
        # (D-CONT-6). The trace commit at this point becomes the
        # canonical-hash anchor that pre-tick replay-identity
        # comparison keys on.
        self._emit_boundary_snapshot(
            kind=BOUNDARY_SNAPSHOT_KIND_PRE_NODE,
            node_id=node_id,
        )

        # 6. TaskExecutor.execute(...). Phase 4A's execute() runs
        #    UnifiedValidator internally and returns a fully-validated
        #    TaskResult. ExecutionSession does NOT re-validate.
        # Phase 4B Step 8 / Phase 4 — reset_scope is computed by the
        # session and passed through ``execute_kwargs``. A caller that
        # explicitly set ``reset_scope`` in the session's
        # ``execute_kwargs`` overrides this (escape hatch for tests);
        # production callers rely on session-driven scoping.
        task = self._task_resolver(node)
        exec_kwargs = dict(self._execute_kwargs)
        exec_kwargs.setdefault("reset_scope", node_reset_scope)
        result = self._task_executor.execute(task, **exec_kwargs)

        # 7. Node transition update based on result.
        passed = _extract_result_passed(result)
        outcome_value = _extract_result_outcome_value(result)
        task_result_fp = _result_fingerprint(result)
        final_status = NODE_RT_COMPLETED if passed else NODE_RT_FAILED
        self._node_runtime[node_id] = NodeRuntimeState(
            node_id=node_id,
            status=final_status,
            outcome_value=outcome_value,
            task_result_fingerprint=task_result_fp,
        )
        if passed:
            self._completed = self._completed | {node_id}
        else:
            self._failed = self._failed | {node_id}

        # 7c. Phase G — D-CONT-5 authoritative occupancy commit.
        # Single mutation point for fixture occupancy across the
        # entire codebase. Conditioned on PASS verdict + declared
        # fixture transitions in the task definition. Cites D-CONT-5,
        # D-CONT-5a, D-LIFE-6, D-LIFE-7.
        if passed:
            self._commit_phase_g_occupancy(task, node_id, result)

        # 7d. Phase 4B Step 8 / Phase 3 — post_node boundary snapshot
        # (D-EXEC-10 items 2+3 collapsed to one checkpoint in Step 6's
        # bundled-phase model). Taken AFTER the Phase-G occupancy
        # commit so the fixture-state mutation is captured in the
        # authoritative projection. Trace commit follows the action
        # (D-EXEC-7). The closing NodeExecutionCompleted event is
        # next; its seq strictly follows this snapshot's seq.
        self._emit_boundary_snapshot(
            kind=BOUNDARY_SNAPSHOT_KIND_POST_NODE,
            node_id=node_id,
        )

        # 8. Emit NodeExecutionCompleted.
        self._emit(EVENT_NODE_EXECUTION_COMPLETED, payload={
            "node_id":                  node_id,
            "outcome_value":            outcome_value,
            "passed":                   passed,
            "task_result_fingerprint":  task_result_fp,
        })

        return self.snapshot()

    # ─────────── lifecycle: complete ───────────

    def complete(self) -> SessionRuntimeSnapshot:
        """Transition RUNNING → COMPLETED or FAILED.

        Side effects, in order:
          1. Determine terminal state from completed / failed sets.
          2. Emit ``SessionCompleted`` or ``SessionFailed``.
          3. ``trace_recorder.finalize()`` (if provided).
          4. ``task_executor.close()``.
          5. Transition state.
        """
        if self._session_state != SessionState.RUNNING:
            raise ExecutionSessionError(
                f"ExecutionSession.complete() called in state "
                f"{self._session_state.value}; only RUNNING is valid "
                f"(D-SESS-1)"
            )

        # 1. Determine terminal state.
        if len(self._failed) == 0:
            new_state = SessionState.COMPLETED
            event_type = EVENT_SESSION_COMPLETED
            payload = {
                "completed_count": len(self._completed),
                "failed_count":    0,
                "node_count":      len(self._graph.nodes),
            }
        else:
            new_state = SessionState.FAILED
            event_type = EVENT_SESSION_FAILED
            payload = {
                "completed_count":   len(self._completed),
                "failed_count":      len(self._failed),
                "node_count":        len(self._graph.nodes),
                "first_failure":     sorted(self._failed)[0],
            }

        # 2. Emit terminal event.
        self._emit(event_type, payload=payload)

        # 3. Finalize trace.
        if self._trace_recorder is not None and not self._trace_recorder.is_finalized:
            self._trace_recorder.finalize()

        # 4. Close executor.
        self._task_executor.close()

        # 5. Transition.
        self._session_state = new_state
        return self.snapshot()

    # ─────────── helpers ───────────

    def _emit_boundary_snapshot(self, *, kind: str, node_id: str | None) -> None:
        """Construct and emit one D-CONT-6 boundary snapshot.

        Cites D-CONT-6, D-CONT-6c (purity), D-EXEC-7 (trace commit
        follows the action), D-EXEC-10/-11 (checkpoint placement).

        The full snapshot dict is **not** placed on the event payload
        — it lives in a dedicated artifact store (Step-8 Phase 4+).
        The event carries the minimal identity tuple:

          * ``snapshot_kind``    — one of the three D-EXEC kinds
          * ``node_id``          — None for session_initial
          * ``snapshot_seq``     — same as the envelope's seq; redundant
                                   but explicit for downstream tooling
          * ``canonical_hash``   — SHA-256 of the canonical-JSON encoding
          * ``schema_version``   — D-CONT-6b

        Forgiving on missing registry: a ``task_executor`` without a
        ``.registry`` attribute (test-fake) yields a snapshot built
        from empty mappings. The event still emits; the hash is the
        hash of an empty-cell snapshot at this seq.
        """
        registry = getattr(self._task_executor, "registry", None)
        if registry is not None:
            objects  = registry.objects
            fixtures = registry.fixtures
        else:
            objects  = {}
            fixtures = {}

        # The seq the snapshot will be associated with is the bus's
        # next-to-commit seq (current committed_count).
        snapshot_seq = self._event_bus.committed_count

        snap = boundary_snapshot(
            kind=kind,
            node_id=node_id,
            seq=snapshot_seq,
            objects=objects,
            fixtures=fixtures,
            session_completed=self._completed,
            session_failed=self._failed,
            session_retry_counts=self._retry_counts,
        )
        canonical_hash = boundary_snapshot_hash(snap)

        self._emit(EVENT_NODE_BOUNDARY_SNAPSHOT, payload={
            "snapshot_kind":   kind,
            "node_id":         node_id,
            "snapshot_seq":    snapshot_seq,
            "canonical_hash":  canonical_hash,
            "schema_version":  BOUNDARY_SNAPSHOT_SCHEMA_VERSION,
        })

    def _commit_phase_g_occupancy(
        self, task: Any, node_id: str, result: Any,
    ) -> None:
        """Sole D-CONT-5 occupancy mutation point.

        Cites D-CONT-5, D-CONT-5a, D-LIFE-6, D-LIFE-7. Called from
        Phase G of ``step()`` after the verdict is known to be PASS.

        Mutation ordering (load-bearing — fixes D-EXEC-7 / D-EXEC-8
        "trace commit follows the action"):

          1. registry.mark_fixture_empty(pick)  [mutation]
          2. emit FixtureStateChanged(pick)     [trace commit]
          3. registry.mark_fixture_occupied(place)  [mutation]
          4. emit FixtureStateChanged(place)    [trace commit]

        Subsequent `NodeExecutionCompleted` (emitted by the caller)
        is the last event of the orchestration tick — preserves
        D-BUS-3 monotone gap-free seq.

        Forgiving on missing fields: a resolved ``task`` that does
        not expose ``pick_source`` / ``place_target`` (e.g. a
        non-PickPlace task type, or a unit-test fake whose task is a
        bare ``TaskNode``) yields no commits. Production Phase 4A
        ``PickPlaceTask`` always carries both.

        Forgiving on missing registry: a ``task_executor`` without
        a ``.registry`` attribute (test fakes that don't model
        registry state) yields no commits. Production Phase 4A
        ``TaskExecutor`` always carries one.
        """
        pick_source  = getattr(task, "pick_source",  None)
        place_target = getattr(task, "place_target", None)

        # The pick-side ``fixture_id`` is optional on Phase 4A's
        # ``PickSource`` (today's PickSource only carries ``source_kind``
        # such as "static"/"conveyor"/"tray_slot" — no fixture). A
        # later phase that adds from-fixture picks will populate this
        # attribute and the same commit logic activates.
        pick_fixture_id  = getattr(pick_source,  "fixture_id", None) if pick_source  is not None else None
        pick_object_id   = getattr(pick_source,  "object_id",  None) if pick_source  is not None else None
        place_fixture_id = getattr(place_target, "fixture_id", None) if place_target is not None else None

        if pick_fixture_id is None and place_fixture_id is None:
            return

        registry = getattr(self._task_executor, "registry", None)
        if registry is None:
            return

        # 1+2. Pick-side empty (only if the task picks from a fixture).
        if pick_fixture_id is not None and pick_object_id is not None:
            f = registry.fixtures.get(pick_fixture_id)
            prev_occupied_by = f.occupied_by if f is not None else None
            registry.mark_fixture_empty(pick_fixture_id, pick_object_id)
            self._emit(EVENT_FIXTURE_STATE_CHANGED, payload={
                "fixture_id":        pick_fixture_id,
                "prev_occupied_by":  prev_occupied_by,
                "new_occupied_by":   None,
                "by_node_id":        node_id,
                "transition":        "empty",
            })

        # 3+4. Place-side occupied.
        if place_fixture_id is not None and pick_object_id is not None:
            f = registry.fixtures.get(place_fixture_id)
            prev_occupied_by = f.occupied_by if f is not None else None
            registry.mark_fixture_occupied(place_fixture_id, pick_object_id)
            self._emit(EVENT_FIXTURE_STATE_CHANGED, payload={
                "fixture_id":        place_fixture_id,
                "prev_occupied_by":  prev_occupied_by,
                "new_occupied_by":   pick_object_id,
                "by_node_id":        node_id,
                "transition":        "occupied",
            })

    def _emit(self, event_type: str, *, payload: Mapping[str, Any]) -> EventEnvelope:
        """Single mutation path into the bus. Cites D-BUS-1/3/9.

        Step 6 emits every event with ``orchestration_tick`` = current
        committed_count BEFORE this emit (i.e. the event's own seq is
        ``committed_count_before``; we expose the tick as that value so
        downstream replay can correlate). ``physx_frame`` is left at 0
        — step 6 does not record physics ticks (they are inside the
        TaskExecutor's execute() and are not exposed to the bus).
        """
        return self._event_bus.emit(
            event_type,
            payload,
            orchestration_tick=self._event_bus.committed_count,
            physx_frame=0,
        )


# ───────────────────────── fingerprint helpers ─────────────────────────


def _result_fingerprint(result: Any) -> str:
    """Canonical-JSON fingerprint of a TaskExecutor result.

    Step 6 + Phase 2 includes ONLY replay-safe fields:
      * ``passed`` (derived from ``result.passed``)
      * ``outcome_value`` (derived from ``result.outcome.value`` or
        ``result.outcome`` string)
      * ``peg_xyz_initial`` if present (Phase 4B Step 8 / Phase 2,
        replay-authoritative under D-CONT-1) — last-tick canonical
        pose; used by inter-node continuity verification.
      * ``peg_xyz_final`` if present (Phase 4A) — rounded to deterministic
        precision via direct serialisation through canonical_dumps,
        which forbids NaN/Inf (D-TRACE-3 allow_nan=False)

    Excludes (deliberately):
      * ``wall_clock_s`` (Phase 4A diagnostic-only; D-SCHED-11)
      * placement evidence (``placement_offset_xy_m``,
        ``pick_lift_off_step``, ``place_landing_step``) —
        authoritative-evidence per D-CONT-5 (input to occupancy
        commit), but bounded to per-task semantics; their presence
        in replay identity is deferred until the boundary-snapshot
        projector lands in Phase 3 of the Step 8 sequence.
      * any field whose presence would make the fingerprint
        non-deterministic across processes

    A future step's replay-identity tool can widen this fingerprint by
    bumping :data:`SESSION_SNAPSHOT_FINGERPRINT_VERSION` and adjusting
    this helper.
    """
    fp_payload: dict[str, Any] = {
        "passed":        _extract_result_passed(result),
        "outcome_value": _extract_result_outcome_value(result),
    }
    peg_xyz_init = getattr(result, "peg_xyz_initial", None)
    if peg_xyz_init is not None:
        fp_payload["peg_xyz_initial"] = list(peg_xyz_init)
    peg_xyz = getattr(result, "peg_xyz_final", None)
    if peg_xyz is not None:
        fp_payload["peg_xyz_final"] = list(peg_xyz)
    return canonical_dumps(fp_payload)
