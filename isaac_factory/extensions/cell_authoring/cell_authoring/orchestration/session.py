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


Mutation Authority Matrix  (load-bearing — D-SESS-1, D-SESS-2; extended Step 9 D-FAULT)
=========================================================================================

Every piece of state is owned by exactly one component. The matrix
below is **normative**: a code path that violates it is a contract
violation, full stop.

+------------------------+--------------------------------------------------+
| component              | may mutate                                       |
+========================+==================================================+
| ExecutionSession       | orchestration state (Step 6 baseline):           |
|                        |   * SessionState (lifecycle phase)               |
|                        |       — Step 9 D-FAULT-3 extends with            |
|                        |         {ABORTING, ABORTED}; RECOVERING is       |
|                        |         FORBIDDEN (D-FAULT-15 #18)               |
|                        |   * completed: frozenset[str]                    |
|                        |   * failed:    frozenset[str]                    |
|                        |   * skipped:   frozenset[str]                    |
|                        |       — D-FAULT-4, D-FAULT-4a (cascade-skip set; |
|                        |         schema_version 2 onward; runtime         |
|                        |         wiring lands in Step 9 Phase 4)          |
|                        |   * retry_counts: Mapping[str, int]              |
|                        |       — D-FAULT-8b: plumbed-but-unused; no       |
|                        |         retry in Step 9                          |
|                        |   * NodeRuntimeState per node, including the     |
|                        |     Step-9 idempotency fields                    |
|                        |     `_cascade_emitted: bool` and                 |
|                        |     `_blocked_emission_key: str | None`          |
|                        |     (D-FAULT-7; runtime wiring lands in Step 9   |
|                        |     Phase 4)                                     |
|                        |                                                  |
|                        | Step 9 D-FAULT authorities (contract surface;    |
|                        | runtime wiring lands in Step 9 Phase 4):         |
|                        |   * abort ingress drain at Phase A only          |
|                        |     (D-FAULT-6); envelope-as-event only          |
|                        |     (D-FAULT-9; method-as-ingress FORBIDDEN by   |
|                        |     D-FAULT-15 #16)                              |
|                        |   * operator-envelope ingress via                |
|                        |     pending_operator_envelopes constructor       |
|                        |     parameter (D-FAULT-9, D-FAULT-9a)            |
|                        |   * retained-state authority during FAIL: NO     |
|                        |     mutation beyond D-CONT-5 PASS path           |
|                        |     (D-FAULT-5, D-FAULT-5a, D-FAULT-5b);         |
|                        |     contradictions between fixture occupancy     |
|                        |     and canonical pose preserved verbatim        |
|                        |   * contradiction persistence authority:         |
|                        |     post-failure boundary snapshot serializes    |
|                        |     last-tick truth; no rollback (D-FAULT-5a)    |
|                        |   * cascade-abort emission authority:            |
|                        |     iterates graph.canonical_order (D-FAULT-4,   |
|                        |     D-SCHED-3); idempotent at the transition     |
|                        |     (D-FAULT-7)                                  |
|                        |   * timeout accounting authority: post-Phase-E   |
|                        |     tick-budget check; per-world.step() count    |
|                        |     only; no wall-clock, no watchdog, no async   |
|                        |     (D-FAULT-12, D-FAULT-12a, D-FAULT-12b);      |
|                        |     Phase E remains atomic (D-FAULT-6a)          |
|                        |   * authority-violation detection at Phase G     |
|                        |     postcondition (D-FAULT-1, D-FAULT-2 emits    |
|                        |     AuthorityViolationDetected)                  |
|                        |   * continuity-validation detection at Phase G   |
|                        |     boundary-snapshot postcondition (D-FAULT-1,  |
|                        |     emits ContinuityValidationFailed)            |
|                        |                                                  |
|                        | Step 10 Direction A authorities (D-EXEC-13,      |
|                        | D-FAULT-1b, D-FAULT-3b, D-FAULT-12c — contract   |
|                        | frozen Phase 2; runtime wiring landed Phase 4):  |
|                        |   * interruption-predicate construction:         |
|                        |     SESSION-EXCLUSIVE (D-EXEC-13c, D-FAULT-15    |
|                        |     #20). The predicate is built from a frozen   |
|                        |     snapshot of pending operator envelopes +     |
|                        |     base_tick captured at execute-entry; the     |
|                        |     executor consumes it as opaque (D-EXEC-13d). |
|                        |     Predicate is pure (no I/O, no wall-clock,    |
|                        |     no mutation; D-EXEC-13 closure-whitelist).   |
|                        |   * post-execute classification of               |
|                        |     EXECUTION_INTERRUPTED returns per the        |
|                        |     D-FAULT-3b declared-order rule (envelope     |
|                        |     eligible → OPERATOR_ABORT; budget exceeded   |
|                        |     → TIMEOUT_FAILURE; otherwise →               |
|                        |     NODE_EXECUTION_FAILURE with EXECUTION_       |
|                        |     INTERRUPTED inner sub-classifier per         |
|                        |     D-FAULT-1a, D-FAULT-1b). Pure function of    |
|                        |     (envelope_snapshot, base_tick,               |
|                        |     ticks_consumed, tick_budget_ticks).          |
|                        |   * deferred-from-Phase-A ingress event          |
|                        |     emission: for row 1 (OPERATOR_ABORT) the     |
|                        |     session emits OperatorAbortRequested +       |
|                        |     SessionAborting post-Phase-E and marks the   |
|                        |     consumed envelope drained; for row 2         |
|                        |     (TIMEOUT_FAILURE) emits NodeTimeoutTripped.  |
|                        |     The session_state transitions to ABORTING    |
|                        |     on row 1 mirroring the Phase-A drain path.   |
|                        |   * Phase E remains ATOMIC from the              |
|                        |     orchestration perspective (D-FAULT-6a,      |
|                        |     D-EXEC-13a). Sub-Phase-E predicate           |
|                        |     consultation is EXECUTOR-INTERNAL; the       |
|                        |     session observes only the post-execute       |
|                        |     TaskResult. No mid-execute envelope drain,   |
|                        |     no mid-execute event emission, no mid-       |
|                        |     execute boundary snapshot.                   |
|                        |                                                  |
|                        | Drives:                                          |
|                        |   * TaskExecutor.prepare/reset/execute/close     |
|                        |     (execute() now accepts an opaque             |
|                        |     should_interrupt kwarg; classification of    |
|                        |     the resulting outcome remains session-side)  |
|                        |   * EventBus.emit (via _emit helper)             |
|                        |   * DurableTraceRecorder.finalize (via close)    |
+------------------------+--------------------------------------------------+
| Scheduler              | (none — pure function; D-SCHED-1)                |
+------------------------+--------------------------------------------------+
| Predicate layer        | (none — pure functions; D-SCHED-12)              |
+------------------------+--------------------------------------------------+
| TraceRecorder          | append-only on-disk events.jsonl AND             |
|                        | manifest.json at finalize. May NOT mutate        |
|                        | orchestration state. (D-TRACE-2/3.) Failure-     |
|                        | event payloads are canonical-JSON-fingerprinted  |
|                        | via the same append path (D-FAULT-10).           |
+------------------------+--------------------------------------------------+
| EventBus               | seq counter + ordered subscriber dispatch.       |
|                        | May NOT mutate orchestration state.              |
|                        | Subscriber topology is frozen at begin()         |
|                        | (D-BUS-6/7/8).                                   |
+------------------------+--------------------------------------------------+
| TaskExecutor           | simulation world only: PhysX scene, robot        |
|                        | drives, object transforms, contact streams.      |
|                        | May NOT mutate: scheduler state, graph state,    |
|                        | trace state, EventBus topology, orchestration    |
|                        | registry. (D-SESS-1 enforcement.) On FAIL,       |
|                        | MUST NOT trigger any cleanup or rollback of      |
|                        | retained state (D-FAULT-5, D-FAULT-15 #1, #7).   |
|                        | Reports ticks_consumed in TaskResult for the     |
|                        | session's post-Phase-E tick-budget check         |
|                        | (D-FAULT-12; field added in Step 9 Phase 4).     |
|                        | Step 10 Direction A (D-EXEC-13, D-FAULT-1b):     |
|                        | execute() consumes a session-supplied opaque     |
|                        | interruption predicate at deterministic segment  |
|                        | boundaries; on first True at a boundary,         |
|                        | returns a TaskResult with                        |
|                        | outcome=EXECUTION_INTERRUPTED (the mechanically  |
|                        | neutral sub-classifier per D-FAULT-1a/-1b). The  |
|                        | executor does NOT classify the orchestration-    |
|                        | level cause (D-FAULT-15 #26); the session does,  |
|                        | per D-FAULT-3b. ticks_consumed is populated      |
|                        | from world.step() counts only (D-FAULT-12c, no   |
|                        | wall-clock derivation).                          |
+------------------------+--------------------------------------------------+
| UnifiedValidator       | validation outputs only — assigns                |
|                        | ``TaskResult.outcome``/``outcome_detail``.       |
|                        | Runs INSIDE Phase 4A's ``TaskExecutor.execute    |
|                        | ``; ExecutionSession reads its verdict but       |
|                        | does not re-run it. (D-CONF: single-source-      |
|                        | of-truth validation.) TaskOutcome is the inner   |
|                        | sub-classification of NODE_EXECUTION_FAILURE     |
|                        | only; the validator MUST NOT be repurposed to    |
|                        | classify orchestration-level failure classes     |
|                        | (D-FAULT-1a; FORBIDDEN).                         |
+------------------------+--------------------------------------------------+
| Launch harness         | OUT-OF-SESSION authority. Writes the             |
| (Step 9, D-FAULT-13)   | infrastructure-degradation sidecar artifact at   |
|                        | <session_package>/infrastructure_degradation.    |
|                        | json when Kit subprocess / PhysX / simulation_   |
|                        | app dies. MUST NOT append to any session's       |
|                        | events.jsonl (the session is dead by             |
|                        | hypothesis). The sidecar's `detected_at_wall_ns` |
|                        | is the ONLY legitimate wall-clock use in the     |
|                        | entire system, justified by the failed           |
|                        | deterministic clock. Sidecar presence is treated |
|                        | as REPLAY-INVALID by the comparator.             |
+------------------------+--------------------------------------------------+
| Replay-identity        | OUT-OF-SESSION authority. The tool at            |
| comparator             | tools/check_session_replay_identity.py is the    |
| (Step 9, D-FAULT-11)   | sole detector of REPLAY_INTEGRITY_FAILURE.       |
|                        | MUST apply strict byte-equality (no tolerance;   |
|                        | D-FAULT-11a). MUST NOT append to any session's   |
|                        | events.jsonl (the meta-failure is not an in-     |
|                        | session event; D-FAULT-11). Writes its audit     |
|                        | record to a comparator-defined location outside  |
|                        | the SessionPackage hierarchy.                    |
+------------------------+--------------------------------------------------+

There is no "hidden orchestration mutation path". The Step 9 D-FAULT
extension expanded ExecutionSession's contract surface (Phase 3
documentation freeze) and added two OUT-OF-SESSION authorities
(launch harness, replay-identity comparator) for non-replayable and
meta-failure handling. A would-be future extension that adds a new
mutator (a CheckpointEngine, a TimeoutWatchdog, etc.) MUST extend
this matrix in this docstring and cite the new contract clauses
governing its authority. Per D-FAULT-14, no "implicit secondary
orchestration system" may exist — every authority is enumerated
above or it does not exist.


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
from .envelopes import OperatorEnvelope, normalize_pending_envelopes
from .events import EventBus, EventEnvelope
from .graph import FailureAction, TaskGraph, TaskNode
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


SESSION_SNAPSHOT_FINGERPRINT_VERSION: int = 3
"""Canonical SessionRuntimeSnapshot fingerprint schema version.

Version history:
  1 — initial schema (Phase 4B Step 6).
  2 — Phase 4B Step 8 / Phase 2: per-task result fingerprint now
      includes ``peg_xyz_initial`` (additive field, replay-authoritative
      under D-CONT-1 when present on the result).
  3 — Phase 4B Step 9 Phase 5 (D-FAULT-4a, D-FAULT-7): session snapshot
      gains ``skipped`` (cascade-skipped node_ids, D-FAULT-4); per-node
      ``cascade_emitted`` + ``blocked_emission_key`` idempotency fields
      (D-FAULT-7). All three are authoritative continuity per D-CONT-1
      (amended by D-FAULT-4a).
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
# Phase 4B Step 9 Phase 5 — D-FAULT event types (D-FAULT-10).
# Each event is canonical-JSON-fingerprinted via canonical_dumps
# (D-TRACE-8). The session is the sole emitter (D-FAULT-2); subordinate
# components MUST NOT emit these.
EVENT_TASK_CASCADE_SKIPPED:      str = "TaskCascadeSkipped"
EVENT_NODE_BLOCKED:              str = "NodeBlocked"
EVENT_NODE_TIMEOUT_TRIPPED:      str = "NodeTimeoutTripped"
EVENT_AUTHORITY_VIOLATION:       str = "AuthorityViolationDetected"
EVENT_CONTINUITY_VALIDATION_FAILED: str = "ContinuityValidationFailed"
EVENT_OPERATOR_ABORT_REQUESTED:  str = "OperatorAbortRequested"
EVENT_SESSION_ABORTING:          str = "SessionAborting"
EVENT_SESSION_ABORTED:           str = "SessionAborted"
EVENT_RECOVERY_NODE_ENTERED:     str = "RecoveryNodeEntered"


# Per-node runtime statuses — stable strings used in fingerprints.
NODE_RT_PENDING:   str = "pending"
NODE_RT_RUNNING:   str = "running"
NODE_RT_COMPLETED: str = "completed"
NODE_RT_FAILED:    str = "failed"
NODE_RT_SKIPPED:   str = "skipped"   # D-FAULT-4 — cascade-skipped (Step 9 Phase 5)


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

    Phase 4B Step 9 Phase 5 (D-FAULT-3) added ``ABORTING`` (transient,
    entered when an operator abort envelope is drained at Phase A) and
    ``ABORTED`` (terminal, operator-initiated). ``ABORTED`` is
    byte-distinguishable from ``FAILED`` (validator/scheduler/authority/
    timeout/continuity-validation-initiated). ``RECOVERING`` as a
    SessionState value is FORBIDDEN per D-FAULT-15 #18.
    """
    INITIALIZED = "INITIALIZED"   # constructed but begin() not called
    RUNNING     = "RUNNING"       # begin() complete; step() pending or in progress
    ABORTING    = "ABORTING"      # operator abort drained at Phase A; transient
    ABORTED     = "ABORTED"       # complete() reached after operator abort
    COMPLETED   = "COMPLETED"     # complete() reached, all nodes terminal-pass
    FAILED      = "FAILED"        # complete() reached, at least one node failed


# ─────────────────────────── frozen value types ───────────────────────────


@dataclass(frozen=True, slots=True)
class NodeRuntimeState:
    """Per-node runtime view. Frozen (D-SESS-8).

    External callers see this via :class:`SessionRuntimeSnapshot`.
    ExecutionSession constructs fresh NodeRuntimeState instances on
    every transition — there is no in-place mutation.

    Phase 4B Step 9 Phase 5 (D-FAULT-7) added per-node idempotency
    tracking fields:

    * ``cascade_emitted`` — True iff a :data:`EVENT_TASK_CASCADE_SKIPPED`
      event has already been emitted for this node. Guards double-skip
      emission when a node has multiple failed parents.
    * ``blocked_emission_key`` — content key
      ``"<status>:<reason_hash>"`` of the most recent
      :data:`EVENT_NODE_BLOCKED` emission for this node. ``None`` when
      no episode is active. Cleared when the node un-blocks
      (parent completes, predicate succeeds, or node terminates).
    """
    node_id: str
    status:  str   # NODE_RT_*
    outcome_value:           str  = ""
    task_result_fingerprint: str  = ""
    cascade_emitted:         bool = False
    blocked_emission_key:    str | None = None


@dataclass(frozen=True, slots=True)
class SessionRuntimeSnapshot:
    """Immutable external view of session state at a point in time.

    Frozen (D-SESS-8). Cites D-SESS-3 (replay-authoritative state must
    be reconstructable). All fields are deterministic; no wall-clock.

    Fields
    ------
    session_state:
        Lifecycle phase.
    completed / failed / skipped:
        Frozen-set views of node_ids in each terminal category.
        ``skipped`` (D-FAULT-4a) was added at Step 9 Phase 5 — it is
        distinct from ``failed`` (a skipped node never ran; a failed
        node ran and produced a non-PASS verdict).
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
    skipped:       frozenset[str] = frozenset()

    def fingerprint(self) -> str:
        """Canonical-JSON identity of this snapshot. Two byte-equal
        snapshots from two independent sessions (same inputs) produce
        byte-identical fingerprints."""
        return canonical_dumps({
            "schema_version": SESSION_SNAPSHOT_FINGERPRINT_VERSION,
            "session_state":  self.session_state.value,
            "completed":      sorted(self.completed),
            "failed":         sorted(self.failed),
            "skipped":        sorted(self.skipped),
            "nodes": [
                {
                    "node_id":                 self.nodes[nid].node_id,
                    "status":                  self.nodes[nid].status,
                    "outcome_value":           self.nodes[nid].outcome_value,
                    "task_result_fingerprint": self.nodes[nid].task_result_fingerprint,
                    "cascade_emitted":         self.nodes[nid].cascade_emitted,
                    "blocked_emission_key":    self.nodes[nid].blocked_emission_key,
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
        pending_operator_envelopes: tuple[OperatorEnvelope, ...] | None = None,
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

        # Phase 4B Step 9 Phase 5 — pre-queued operator envelopes
        # (D-FAULT-9). Canonical-ordered at construction; immutable.
        # Live channel ingress (Step 11) MUST honor the same schema and
        # order. ``request_abort()`` and any method-as-ingress are
        # FORBIDDEN per D-FAULT-15 #16; envelopes are the sole ingress.
        self._pending_envelopes: tuple[OperatorEnvelope, ...] = (
            normalize_pending_envelopes(pending_operator_envelopes)
        )
        # Drained envelopes — track for forensic provenance + idempotency
        # (D-FAULT-7: late envelopes are recorded but produce no second
        # state transition).
        self._drained_envelope_ids: set[str] = set()
        # Logical orchestration tick counter (D-EXEC-12). Incremented
        # at the start of every step() invocation regardless of whether a
        # node is selected. Used by Phase A envelope drain to determine
        # which pre-queued envelopes are eligible
        # (envelope.requested_at_tick <= current tick).
        self._orchestration_tick: int = 0

        # ── mutable orchestration state — ExecutionSession is its sole
        # author (Mutation Authority Matrix).
        self._session_state: SessionState = SessionState.INITIALIZED
        self._completed:     frozenset[str] = frozenset()
        self._failed:        frozenset[str] = frozenset()
        # Phase 4B Step 9 Phase 5 (D-FAULT-4 / D-FAULT-4a) — cascade-skipped
        # node_ids. Distinct from ``_failed`` (a skipped node never ran;
        # a failed node ran with non-PASS verdict). Authoritative
        # continuity per D-CONT-1 (extended by D-FAULT-4a).
        self._skipped:       frozenset[str] = frozenset()
        self._retry_counts:  dict[str, int] = {}
        # Per-node runtime: initialised lazily at begin() to "pending".
        self._node_runtime:  dict[str, NodeRuntimeState] = {}
        # Terminator reason — set when the session enters ABORTING or
        # is on a path to FAILED with a specific D-FAULT class. Used in
        # complete()'s terminal-event payload.
        self._terminator_reason: str | None = None

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
            skipped=self._skipped,
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

        Phase 4B Step 9 Phase 5 (D-FAULT) wiring:

          * **Phase A** — drain pending operator envelopes whose
            ``requested_at_tick <= current orchestration tick``. The
            session transitions ``RUNNING`` → ``ABORTING`` on the first
            abort envelope. Subsequent envelopes are recorded for
            forensic provenance (D-FAULT-7) but produce no second
            transition.
          * Mid-Phase-E interrupt is FORBIDDEN (D-FAULT-6, D-FAULT-6a).
          * Cascade emission for node failure runs at Phase G and
            iterates ``graph.canonical_order`` per FailureAction
            (D-FAULT-3, D-FAULT-3a, D-FAULT-4); emission is idempotent
            at the transition per D-FAULT-7.
          * Post-Phase-E tick-budget check (D-FAULT-12); wall-clock
            FORBIDDEN.

        Order of operations (see module docstring "Execution tick
        ordering"). Cites D-EXEC-1, D-EXEC-2, D-EXEC-7.
        """
        if self._session_state not in (SessionState.RUNNING, SessionState.ABORTING):
            raise ExecutionSessionError(
                f"ExecutionSession.step() called in state "
                f"{self._session_state.value}; only RUNNING (or transient "
                f"ABORTING for drain completion) is valid (D-SESS-1)"
            )

        # Phase A — operator-envelope drain (D-FAULT-6, D-FAULT-9).
        # MUST execute before any scheduler decision so that an abort
        # request enters orchestration at the canonical phase boundary.
        # No method-as-ingress is permitted (D-FAULT-15 #16).
        self._drain_phase_a_envelopes()

        # If the abort drain transitioned us to ABORTING, cascade-skip
        # all remaining pending nodes uniformly per D-FAULT-3
        # (OPERATOR_ABORT overrides FailureAction) and return.
        if self._session_state == SessionState.ABORTING:
            self._cascade_skip_remaining_pending(reason="OPERATOR_ABORT")
            self._orchestration_tick += 1
            return self.snapshot()

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

        # If nothing runnable, the tick is a no-op. Increment the tick
        # counter so future Phase A drains can advance past pre-queued
        # envelope tick gates even on no-op ticks.
        if decision.selected_node_id is None:
            self._orchestration_tick += 1
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

        # 6a. Phase 4B Step 10 Direction A — capture authoritative
        # inputs at execute-entry and build the interruption predicate
        # (D-EXEC-13). The snapshot is frozen by execute-entry; the
        # predicate closes over it (D-EXEC-13 whitelist). Predicate
        # construction is session-exclusive (D-EXEC-13c, D-FAULT-15 #20).
        # The executor consumes the predicate as opaque (D-EXEC-13d).
        #
        # Phase 6 semantic completion: the session pre-computes the
        # task's deterministic boundary-tick projection
        # (TaskExecutor.compute_segment_boundary_ticks — pure function
        # over the trajectory's authored waypoint sequence) and passes
        # the immutable tuple to the predicate closure. This brings
        # the predicate's trigger surface up to the contract D-FAULT-3b
        # row-1/row-2 formula (`requested_at_tick <= base_tick +
        # ticks_consumed_at_boundary`), so envelopes that become
        # eligible mid-trajectory trip the predicate at the
        # corresponding boundary. The boundary tuple is derived solely
        # from authored trajectory ontology; no PhysX state, no
        # wall-clock, no runtime cadence.
        envelopes_at_execute_entry = self._pending_envelopes
        base_tick_for_predicate = self._orchestration_tick
        # ``compute_segment_boundary_ticks`` is a Phase 6 surface; the
        # executor MAY not implement it (e.g. test fakes). Fall back to
        # an empty tuple, in which case the predicate uses entry-
        # eligibility only (Phase 4 conservative semantic). This
        # preserves bytewise behaviour with executor stand-ins used
        # across the pure-Python regression suite.
        if hasattr(self._task_executor, "compute_segment_boundary_ticks"):
            try:
                boundary_ticks_consumed = tuple(
                    self._task_executor.compute_segment_boundary_ticks(task)
                )
            except Exception:
                boundary_ticks_consumed = ()
        else:
            boundary_ticks_consumed = ()
        interrupt_predicate = self._build_interrupt_predicate(
            envelopes_snapshot=envelopes_at_execute_entry,
            base_tick=base_tick_for_predicate,
            boundary_ticks_consumed=boundary_ticks_consumed,
            tick_budget_ticks=getattr(task, "tick_budget_ticks", None),
        )
        if interrupt_predicate is not None:
            exec_kwargs.setdefault("should_interrupt", interrupt_predicate)

        result = self._task_executor.execute(task, **exec_kwargs)

        # 6b. Phase 4B Step 10 Direction A — post-Phase-E classification
        # of EXECUTION_INTERRUPTED returns per D-FAULT-3b. When the
        # executor short-circuited via the interruption predicate, the
        # session applies the declared-order rule (envelope-eligibility
        # → OPERATOR_ABORT; budget-exceeded → TIMEOUT_FAILURE; else →
        # NODE_EXECUTION_FAILURE). Pure function of authoritative
        # inputs; no wall-clock, no PhysX state, no observational
        # projection. Returns None when the result is not
        # EXECUTION_INTERRUPTED → the existing Phase 9 flow runs.
        interrupt_classification = self._classify_execution_interrupted(
            result=result, task=task,
            envelopes_snapshot=envelopes_at_execute_entry,
            base_tick=base_tick_for_predicate,
        )

        # 6c. Phase 4B Step 9 Phase 5 — post-Phase-E tick-budget check
        # (D-FAULT-12). Mid-Phase-E interrupt is FORBIDDEN (D-FAULT-6a,
        # D-EXEC-13a from orchestration perspective); the check happens
        # AFTER execute() returns. Skipped when the D-FAULT-3b
        # classifier already resolved the orchestration-level class
        # for an EXECUTION_INTERRUPTED return (the classifier's row 2
        # subsumes this case via the same `ticks_consumed > budget`
        # rule). Wall-clock budgets are FORBIDDEN (D-FAULT-15 #10).
        if interrupt_classification is None:
            timeout_tripped = self._check_tick_budget(task, node_id, result)
        else:
            timeout_tripped = False

        # 7. Node transition update based on result. D-FAULT-3b
        # classification (when present) supersedes the validator
        # verdict and the legacy tick-budget check; D-FAULT-1a's inner
        # sub-classifier (TaskOutcome string) is preserved on row 3.
        if interrupt_classification is not None:
            passed = False
            cls_class, _cls_envelope = interrupt_classification
            if cls_class == "NODE_EXECUTION_FAILURE":
                # Row 3 — preserve the executor-reported inner
                # sub-classifier on the fingerprint surface
                # (D-FAULT-1a, D-FAULT-1b). outcome_value carries
                # "EXECUTION_INTERRUPTED" for forensic provenance; the
                # orchestration-level class NODE_EXECUTION_FAILURE is
                # the propagation target per D-FAULT-3.
                outcome_value = "EXECUTION_INTERRUPTED"
            else:
                # Row 1 (OPERATOR_ABORT) or Row 2 (TIMEOUT_FAILURE) —
                # the orchestration-level class IS the outcome_value
                # recorded on the fingerprint (consistent with the
                # existing TIMEOUT_FAILURE path).
                outcome_value = cls_class
        elif timeout_tripped:
            passed = False
            outcome_value = "TIMEOUT_FAILURE"
        else:
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

        # 7b. Phase 4B Step 10 Direction A — D-FAULT-3b row 1 ingress
        # event emission (OPERATOR_ABORT path). When the classifier
        # identified an eligible envelope, the deferred-from-Phase-A
        # ingress event is emitted now (recorded for forensics, D-FAULT-7
        # append-only). The session transitions RUNNING → ABORTING and
        # the consumed envelope is removed from the pending queue so
        # subsequent Phase A drains do not re-emit the same event.
        if interrupt_classification is not None and interrupt_classification[0] == "OPERATOR_ABORT":
            _abort_class, _abort_env = interrupt_classification
            if _abort_env is not None:
                self._drained_envelope_ids.add(_abort_env.envelope_id)
                self._pending_envelopes = tuple(
                    e for e in self._pending_envelopes
                    if e.envelope_id != _abort_env.envelope_id
                )
                self._emit(EVENT_OPERATOR_ABORT_REQUESTED, payload={
                    "envelope_id":       _abort_env.envelope_id,
                    "kind":              _abort_env.kind,
                    "requested_at_tick": _abort_env.requested_at_tick,
                    "reason":            _abort_env.reason,
                })
            if self._session_state == SessionState.RUNNING:
                self._session_state = SessionState.ABORTING
                self._terminator_reason = "OPERATOR_ABORT"
                self._emit(EVENT_SESSION_ABORTING, payload={
                    "terminator_reason":   "OPERATOR_ABORT",
                    "trigger_envelope_id": (
                        _abort_env.envelope_id if _abort_env is not None else None
                    ),
                })

        # 7c. Phase 4B Step 10 Direction A — D-FAULT-3b row 2 ingress
        # event emission (TIMEOUT_FAILURE path). Mirrors the existing
        # _check_tick_budget event surface so downstream consumers see
        # the same NodeTimeoutTripped record regardless of whether the
        # budget violation was discovered post-PASS (existing path) or
        # post-interrupt (Step 10 path).
        if interrupt_classification is not None and interrupt_classification[0] == "TIMEOUT_FAILURE":
            self._emit(EVENT_NODE_TIMEOUT_TRIPPED, payload={
                "node_id":           node_id,
                "tick_budget_ticks": int(getattr(task, "tick_budget_ticks", 0) or 0),
                "ticks_consumed":    int(getattr(result, "ticks_consumed", 0) or 0),
            })

        # 7d. Phase G — D-CONT-5 authoritative occupancy commit.
        # Single mutation point for fixture occupancy across the
        # entire codebase. Conditioned on PASS verdict + declared
        # fixture transitions in the task definition. Cites D-CONT-5,
        # D-CONT-5a, D-LIFE-6, D-LIFE-7.
        if passed:
            self._commit_phase_g_occupancy(task, node_id, result)
        elif interrupt_classification is not None and interrupt_classification[0] == "OPERATOR_ABORT":
            # D-FAULT-3 row 6 (OPERATOR_ABORT): FailureAction is
            # overridden; cascade-skip remaining pending nodes
            # uniformly. Mirrors the Phase-A-drain path so downstream
            # cascade semantics are byte-identical regardless of
            # whether the abort drained at Phase A or post-execute.
            self._cascade_skip_remaining_pending(reason="OPERATOR_ABORT")
        else:
            # Phase 4B Step 9 Phase 5 — cascade-skip propagation on FAIL
            # (D-FAULT-3, D-FAULT-3a, D-FAULT-4). Iterates
            # graph.canonical_order (D-SCHED-3); idempotent per node
            # via cascade_emitted flag (D-FAULT-7). Sibling-tolerant by
            # default (SKIP_NODE); ABORT_COHORT extends to siblings;
            # ABORT_JOB collapses all remaining pending nodes. Covers
            # the TIMEOUT_FAILURE and NODE_EXECUTION_FAILURE rows of
            # D-FAULT-3b and the existing validator-driven FAIL path.
            self._propagate_cascade_on_failure(node_id)

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

        # Increment orchestration tick counter — one per executed step.
        self._orchestration_tick += 1
        return self.snapshot()

    # ─────────── lifecycle: complete ───────────

    def complete(self) -> SessionRuntimeSnapshot:
        """Transition RUNNING → COMPLETED / FAILED, or ABORTING → ABORTED.

        Side effects, in order:
          1. Determine terminal state from session_state + completed /
             failed / skipped sets.
          2. Emit terminal event (``SessionCompleted`` / ``SessionFailed``
             / ``SessionAborted`` — distinct event types per
             D-FAULT-3 / F.11 ruling).
          3. ``trace_recorder.finalize()`` (if provided).
          4. ``task_executor.close()``.
          5. Transition state.
        """
        if self._session_state not in (SessionState.RUNNING, SessionState.ABORTING):
            raise ExecutionSessionError(
                f"ExecutionSession.complete() called in state "
                f"{self._session_state.value}; only RUNNING or ABORTING is valid "
                f"(D-SESS-1)"
            )

        # 1. Determine terminal state.
        if self._session_state == SessionState.ABORTING:
            # Phase 4B Step 9 Phase 5 (D-FAULT-3, F.11 ruling) — operator
            # abort path: ABORTING → ABORTED. Byte-distinguishable from
            # FAILED via the terminal event_type.
            new_state = SessionState.ABORTED
            event_type = EVENT_SESSION_ABORTED
            payload = {
                "completed_count": len(self._completed),
                "failed_count":    len(self._failed),
                "skipped_count":   len(self._skipped),
                "node_count":      len(self._graph.nodes),
                "terminator_reason": (
                    self._terminator_reason
                    if self._terminator_reason is not None
                    else "OPERATOR_ABORT"
                ),
            }
        elif len(self._failed) == 0:
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
                "skipped_count":     len(self._skipped),
                "node_count":        len(self._graph.nodes),
                "first_failure":     sorted(self._failed)[0],
                "terminator_reason": (
                    self._terminator_reason
                    if self._terminator_reason is not None
                    else "NODE_EXECUTION_FAILURE"
                ),
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
            session_skipped=self._skipped,
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

    # ─────────── D-FAULT helpers (Phase 4B Step 9 Phase 5) ───────────

    def _drain_phase_a_envelopes(self) -> None:
        """Phase A — drain pending operator envelopes (D-FAULT-6, D-FAULT-9).

        Envelopes whose ``requested_at_tick`` is ``<= self._orchestration_tick``
        are eligible. Drained in canonical order
        (``requested_at_tick``, ``envelope_id``). The first abort envelope
        transitions the session to ``ABORTING`` and emits
        :data:`EVENT_SESSION_ABORTING`. Subsequent envelopes are recorded
        for forensic provenance (D-FAULT-7) but produce no second state
        transition.

        Method-as-ingress (``request_abort``, ``force_abort`` etc.) is
        FORBIDDEN per D-FAULT-15 #16 — this helper is the ONLY ingress
        path.
        """
        if not self._pending_envelopes:
            return
        eligible: list[OperatorEnvelope] = []
        remaining: list[OperatorEnvelope] = []
        for env in self._pending_envelopes:
            if env.envelope_id in self._drained_envelope_ids:
                # Already drained on a prior tick — should not happen
                # because we rebuild _pending_envelopes after drain, but
                # be defensive.
                continue
            if env.requested_at_tick <= self._orchestration_tick:
                eligible.append(env)
            else:
                remaining.append(env)
        if not eligible:
            return

        for env in eligible:
            self._drained_envelope_ids.add(env.envelope_id)
            # Append-only event ingress — recorded in canonical-order
            # iteration; D-FAULT-10 fingerprinting via _emit().
            self._emit(EVENT_OPERATOR_ABORT_REQUESTED, payload={
                "envelope_id":       env.envelope_id,
                "kind":              env.kind,
                "requested_at_tick": env.requested_at_tick,
                "reason":            env.reason,
            })
            if (
                env.kind == "abort"
                and self._session_state == SessionState.RUNNING
            ):
                # First abort envelope: transition RUNNING → ABORTING.
                # Subsequent envelopes (while ABORTING / ABORTED) are
                # recorded but do not re-transition (D-FAULT-7).
                self._session_state = SessionState.ABORTING
                self._terminator_reason = "OPERATOR_ABORT"
                self._emit(EVENT_SESSION_ABORTING, payload={
                    "terminator_reason": "OPERATOR_ABORT",
                    "trigger_envelope_id": env.envelope_id,
                })
        # Rebuild pending tuple — drop drained, preserve canonical order
        # of the remainder.
        self._pending_envelopes = tuple(remaining)

    def _propagate_cascade_on_failure(self, failed_node_id: str) -> None:
        """Phase G — cascade-skip emission on node failure.

        Cites D-FAULT-3 (propagation rules), D-FAULT-3a (FailureAction
        enum), D-FAULT-4 (TaskCascadeSkipped distinct from NodeFailed),
        D-FAULT-7 (idempotent at the transition; per-node
        ``cascade_emitted`` flag prevents duplicate emission).

        Iteration order is ``graph.canonical_order`` (D-SCHED-3) so two
        replay-equivalent runs produce byte-identical cascade traces.
        """
        # Determine cascade targets from outgoing edges' FailureAction.
        # If ANY outgoing edge declares ABORT_JOB, the whole job is
        # cascade-skipped uniformly (D-FAULT-3a).
        # If ANY outgoing edge declares ABORT_COHORT, descendants AND
        # fan-out siblings of the failed node are cascade-skipped.
        # Otherwise (default SKIP_NODE), only descendants of the failed
        # node are cascade-skipped.
        outgoing = tuple(
            e for e in self._graph.edges if e.parent_id == failed_node_id
        )
        # Collect the maximum-severity action across outgoing edges.
        if any(e.failure_action == FailureAction.ABORT_JOB for e in outgoing):
            action = FailureAction.ABORT_JOB
        elif any(e.failure_action == FailureAction.ABORT_COHORT for e in outgoing):
            action = FailureAction.ABORT_COHORT
        else:
            action = FailureAction.SKIP_NODE

        if action == FailureAction.ABORT_JOB:
            self._cascade_skip_remaining_pending(reason="ABORT_JOB")
            return

        targets: set[str] = set(self._descendants_of(failed_node_id))
        if action == FailureAction.ABORT_COHORT:
            for sibling in self._siblings_of(failed_node_id):
                targets.add(sibling)
                targets |= self._descendants_of(sibling)

        # Iterate canonical_order so emission ordering is deterministic.
        for nid in self._graph.canonical_order:
            if nid not in targets:
                continue
            self._emit_cascade_skipped(nid, ancestor_failed_id=failed_node_id)

    def _cascade_skip_remaining_pending(self, *, reason: str) -> None:
        """Cascade-skip every node still in ``pending`` (D-FAULT-3
        ABORT_JOB / OPERATOR_ABORT path). Iterates canonical_order;
        idempotent per D-FAULT-7."""
        for nid in self._graph.canonical_order:
            rt = self._node_runtime.get(nid)
            if rt is None:
                continue
            if rt.status != NODE_RT_PENDING:
                continue
            self._emit_cascade_skipped(nid, ancestor_failed_id=None, reason=reason)

    def _emit_cascade_skipped(
        self,
        node_id: str,
        *,
        ancestor_failed_id: str | None,
        reason: str = "SKIP_NODE",
    ) -> None:
        """Single emission point for :data:`EVENT_TASK_CASCADE_SKIPPED`.

        Idempotent per D-FAULT-7 via the per-node ``cascade_emitted``
        flag on :class:`NodeRuntimeState`. A node cascade-skipped twice
        (e.g. two failed parents) emits exactly one event.
        """
        rt = self._node_runtime.get(node_id)
        if rt is None:
            return
        if rt.cascade_emitted:
            return  # D-FAULT-7 idempotency guard
        if rt.status in (NODE_RT_COMPLETED, NODE_RT_FAILED, NODE_RT_SKIPPED):
            return
        # Transition to skipped + record emission.
        self._node_runtime[node_id] = NodeRuntimeState(
            node_id=node_id,
            status=NODE_RT_SKIPPED,
            cascade_emitted=True,
        )
        self._skipped = self._skipped | {node_id}
        self._emit(EVENT_TASK_CASCADE_SKIPPED, payload={
            "node_id":            node_id,
            "ancestor_failed_id": ancestor_failed_id,
            "reason":             reason,
        })

    def _descendants_of(self, node_id: str) -> set[str]:
        """Reachable descendants via DFS over graph edges."""
        descendants: set[str] = set()
        frontier = [node_id]
        while frontier:
            cur = frontier.pop()
            for e in self._graph.edges:
                if e.parent_id == cur and e.child_id not in descendants:
                    descendants.add(e.child_id)
                    frontier.append(e.child_id)
        return descendants

    def _siblings_of(self, node_id: str) -> set[str]:
        """Sibling node_ids — those sharing any parent with ``node_id``."""
        siblings: set[str] = set()
        parents = {e.parent_id for e in self._graph.edges if e.child_id == node_id}
        for e in self._graph.edges:
            if e.parent_id in parents and e.child_id != node_id:
                siblings.add(e.child_id)
        return siblings

    def _check_tick_budget(
        self, task: Any, node_id: str, result: Any
    ) -> bool:
        """Post-Phase-E tick-budget check (D-FAULT-12).

        Returns True iff the budget is exceeded and a
        :data:`EVENT_NODE_TIMEOUT_TRIPPED` was emitted; the caller then
        overrides the outcome to ``TIMEOUT_FAILURE`` per D-FAULT-3.

        Wall-clock budgets are FORBIDDEN (D-FAULT-15 #10); this helper
        consults only the integer ``ticks_consumed`` reported by the
        executor on :class:`TaskResult`.
        """
        budget = getattr(task, "tick_budget_ticks", None)
        if budget is None:
            return False
        ticks_consumed = int(getattr(result, "ticks_consumed", 0) or 0)
        if ticks_consumed <= int(budget):
            return False
        self._emit(EVENT_NODE_TIMEOUT_TRIPPED, payload={
            "node_id":           node_id,
            "tick_budget_ticks": int(budget),
            "ticks_consumed":    ticks_consumed,
        })
        return True

    @staticmethod
    def _build_interrupt_predicate(
        *,
        envelopes_snapshot: tuple[OperatorEnvelope, ...],
        base_tick: int,
        boundary_ticks_consumed: tuple[int, ...] = (),
        tick_budget_ticks: int | None = None,
    ) -> Callable[[int], bool] | None:
        """Phase 4B Step 10 Direction A — interruption predicate factory.

        Constructs a pure callable ``(segment_tick: int) -> bool`` per
        D-EXEC-13 from a frozen snapshot of authoritative state captured
        at execute-entry.

        Closure inputs (D-EXEC-13 whitelist):
          * ``envelopes_snapshot`` — pending operator envelopes at
            execute-entry (D-FAULT-9 canonical-ordered tuple);
          * ``base_tick`` — session's ``_orchestration_tick`` at
            execute-entry;
          * ``boundary_ticks_consumed`` (Phase 6 semantic completion)
            — the cumulative ``world.step()`` count at each segment
            boundary terminus for the task's trajectory, derived
            authoritatively from the trajectory's authored waypoint
            sequence via :meth:`TaskExecutor.compute_segment_boundary_ticks`.
            The tuple is monotone non-decreasing; ``boundary_ticks_consumed[K-1]``
            is the cumulative tick count AT boundary K (boundary 0 is
            implicitly tick 0). Captured by the closure as an immutable
            tuple; the predicate consults it but never mutates it.
            Empty tuple means the predicate cannot evaluate
            boundary-aware eligibility and falls back to entry-
            eligibility only;
          * ``tick_budget_ticks`` — per-task budget for D-FAULT-3b row 2
            mid-trajectory short-circuit (envelope-eligibility row 1
            still takes priority in classification).

        The predicate is **session-constructed only** (D-EXEC-13c,
        D-FAULT-15 #20); the executor consumes it as opaque.

        Semantics (D-FAULT-3b alignment): returns True at boundary K
        iff at least one ``kind == "abort"`` envelope satisfies
        ``requested_at_tick <= base_tick + boundary_ticks_consumed[K-1]``
        OR (budget set AND ``boundary_ticks_consumed[K-1] > tick_budget_ticks``).
        This brings the predicate's trigger surface up to the contract
        D-FAULT-3b row-1/row-2 formula, so envelopes that become
        eligible mid-trajectory (envelope requested at a future tick
        that the cumulative tick advance crosses) trip the predicate
        at the corresponding boundary. Envelope-eligibility at
        execute-entry (``requested_at_tick <= base_tick``) trips at
        boundary 1 (first segment-end), mirroring the deferred-from-
        Phase-A semantic.

        Returns ``None`` when no envelope or budget condition could
        ever trigger — the executor then runs the trajectory to
        completion unmodified (Phase 4A behaviour, byte-equivalent
        to executor without ``should_interrupt`` argument).
        """
        # D-FAULT-9a — only kind="abort" envelopes participate (Step 9).
        abort_envelopes = tuple(
            env for env in envelopes_snapshot if env.kind == "abort"
        )
        # If no abort envelope AND no budget, no triggering condition.
        if not abort_envelopes and tick_budget_ticks is None:
            return None
        # Earliest envelope requested_at_tick (or None if no envelopes).
        earliest_requested_at_tick: int | None = (
            min(env.requested_at_tick for env in abort_envelopes)
            if abort_envelopes else None
        )
        # If boundary_ticks_consumed is empty, fall back to
        # entry-eligibility only (Phase 4 conservative semantic). The
        # executor will still run; the predicate triggers at boundary
        # >= 1 iff the envelope was already eligible at base_tick.
        if not boundary_ticks_consumed:
            if earliest_requested_at_tick is None:
                return None
            if earliest_requested_at_tick > base_tick:
                return None
            def predicate_entry_only(segment_tick: int) -> bool:
                return segment_tick >= 1
            return predicate_entry_only

        # Pure, deterministic, side-effect-free, no wall-clock, no
        # closure-state mutation (D-EXEC-13). The closure captures
        # immutable tuples + plain ints; nothing it reads can change
        # during execute().
        _btc = boundary_ticks_consumed  # alias for clarity in closure
        _earliest = earliest_requested_at_tick
        _base = base_tick
        _budget = tick_budget_ticks

        def predicate(segment_tick: int) -> bool:
            # Boundary 0 (pre-execute) — the predicate is consulted
            # before any world.step(). Phase A drain semantics SHOULD
            # have already caught any envelope already eligible at
            # base_tick; treating boundary 0 as a trigger would
            # double-drain. Do NOT trip at boundary 0.
            if segment_tick <= 0:
                return False
            # Lookup cumulative ticks at boundary `segment_tick`.
            # Indices are 1-based on the contract surface; the tuple
            # is 0-based, so boundary K maps to _btc[K-1]. If the
            # executor consults a boundary index beyond the trajectory's
            # authored landmark count, treat as ineligible (predicate
            # is conservative — never speculative).
            if segment_tick - 1 >= len(_btc):
                return False
            ticks_at_boundary = _btc[segment_tick - 1]
            # Row 1 — envelope eligibility (D-FAULT-3b).
            if _earliest is not None and _base + ticks_at_boundary >= _earliest:
                return True
            # Row 2 — budget exhaustion (mid-trajectory short-circuit).
            if _budget is not None and ticks_at_boundary > _budget:
                return True
            return False
        return predicate

    @staticmethod
    def _classify_execution_interrupted(
        *,
        result: Any,
        task: Any,
        envelopes_snapshot: tuple[OperatorEnvelope, ...],
        base_tick: int,
    ) -> tuple[str, OperatorEnvelope | None] | None:
        """Phase 4B Step 10 Direction A — D-FAULT-3b declared-order classifier.

        Pure function of ``(envelopes_snapshot, base_tick,
        result.ticks_consumed, task.tick_budget_ticks)``. Returns:

          * ``None`` — when ``result.outcome`` is not
            ``EXECUTION_INTERRUPTED``; the caller falls back to the
            existing Phase 4A / Step 9 classification flow.
          * ``("OPERATOR_ABORT", envelope)`` — D-FAULT-3b row 1: at
            least one ``kind == "abort"`` envelope satisfies
            ``requested_at_tick <= base_tick + ticks_consumed``. The
            envelope returned is the deferred-from-Phase-A trigger and
            is recorded in the post-execute ingress event.
          * ``("TIMEOUT_FAILURE", None)`` — D-FAULT-3b row 2:
            ``ticks_consumed > task.tick_budget_ticks``.
          * ``("NODE_EXECUTION_FAILURE", None)`` — D-FAULT-3b row 3:
            no envelope eligible, budget not exceeded. The fingerprint
            outcome_value remains ``"EXECUTION_INTERRUPTED"`` (the
            inner sub-classifier of NODE_EXECUTION_FAILURE per
            D-FAULT-1a / D-FAULT-1b).

        Classification ordering is **declared, not best-fit**: the
        first matching row applies. Pure deterministic; no wall-clock,
        no PhysX state, no observational projection.
        """
        outcome_attr = getattr(result, "outcome", None)
        outcome_value = getattr(outcome_attr, "value", outcome_attr)
        if outcome_value != "EXECUTION_INTERRUPTED":
            return None
        ticks_consumed = int(getattr(result, "ticks_consumed", 0) or 0)
        # Row 1 — envelope eligibility (D-FAULT-3b).
        for env in envelopes_snapshot:
            if env.kind != "abort":
                continue
            if env.requested_at_tick <= base_tick + ticks_consumed:
                return ("OPERATOR_ABORT", env)
        # Row 2 — budget exhaustion.
        budget = getattr(task, "tick_budget_ticks", None)
        if budget is not None and ticks_consumed > int(budget):
            return ("TIMEOUT_FAILURE", None)
        # Row 3 — predicate-driven stop with no recognized cause.
        return ("NODE_EXECUTION_FAILURE", None)

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
    # Phase 4B Step 10 Direction A (D-FAULT-12c) — ticks_consumed
    # enters the per-task fingerprint as authoritative-evidence. The
    # observational ``interrupted_at_segment_*`` fields are
    # deliberately EXCLUDED per D-EXEC-13b: they are derivable from
    # ticks_consumed plus the trajectory's static segment-tick map, so
    # duplicating them here would double-bind replay-identity to the
    # same underlying fact (D-CONT-7a projection-purity discipline).
    fp_payload["ticks_consumed"] = int(getattr(result, "ticks_consumed", 0) or 0)
    return canonical_dumps(fp_payload)
