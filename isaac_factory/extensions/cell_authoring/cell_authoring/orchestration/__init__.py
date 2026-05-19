"""cell_authoring.orchestration — Phase 4B orchestration spine.

This package implements the deterministic orchestration layer described in
[docs/phase_4b_orchestration_architecture.md] and bound by the contract in
[docs/phase_4b_deterministic_semantics.md].

Step 1 (landed): deterministic EventBus skeleton + invariant-enforcement
plumbing + a minimal in-memory trace stub used to prove ordering
reproducibility.

Step 2 (landed): durable trace + SessionPackage deterministic on-disk
layout (``manifest.json`` + ``events.jsonl``) + integrity verifier.
Establishes append-only / immutable-finalized-trace authority.

Step 3 (landed): deterministic predicate primitives + frozen
PredicateContext + 3 concrete predicates (ObjectAtFixture / FixtureEmpty
/ ObjectPoseWithin) + ordered short-circuit evaluator. Establishes
predicate purity and replay-safe decision semantics.

Step 4 (landed): deterministic TaskGraph topology — immutable TaskNode
/ TaskEdge / TaskGraph + canonical ordering + acyclicity validation +
canonical fingerprint. Pure-declarative; no execution.

Step 5 (landed): deterministic node-selection scheduler —
TopologicalSequentialScheduler + SchedulerDecision +
SchedulerEvaluationError. Pure-function topology + predicate +
completed/failed-state → selected node_id + full per-node diagnostics.

Step 6 (landed): ExecutionSession — first runtime-execution layer.
Single-node execution. ExecutionSession is the sole mutable
orchestration-state authority; TaskExecutor is the subordinate
execution-layer; explicit Mutation Authority Matrix in session.py.
Adds ResetScope (FULL / ACQUIRED_ONLY) to Phase 4A's TaskExecutor.reset()
additively — default FULL preserves Phase 4A behaviour byte-for-byte.
Still no multi-node, no retries, no recovery, no pause/resume.

Contract clauses honoured by the current code

  Step 1:
    D-BUS-1 .. D-BUS-12          (sync bus, monotone seq, frozen topology,
                                  registration-order dispatch,
                                  non-reentrant, subscriber-error capture)
    D-TRACE-1                    (in-memory ordering capture)
    D-SCHED-11                   (no wall-clock fields)
    D-SESS-8                     (frozen envelopes)

  Step 2:
    D-TRACE-2                    (append-only after commit)
    D-TRACE-3                    (no retroactive mutation; partial
                                  traces preserved)
    D-TRACE-6                    (records carry seq; corrupt prefix
                                  detectable)
    D-TRACE-7                    (integrity verifiable at close)
    D-TRACE-8                    (manifest schema fixed)

  Step 3:
    D-SCHED-12                   (predicates are pure functions; no
                                  PhysX / wall-clock / RNG / object-id
                                  dependence)
    D-SCHED-13                   (predicate-list evaluation preserves
                                  construction order; short-circuits
                                  on first False / first error)

  Step 4:
    D-SCHED-2                    (canonical DAG traversal:
                                  (depth, node_id))
    D-SCHED-3                    (same canonical key used everywhere)
    D-SCHED-4                    (duplicate node_id rejected)
    D-SCHED-5/6/7/8              (no dict/set/library-driven traversal)
    D-FORBID-4                   (runtime graph mutation impossible)

  Step 5:
    D-SCHED-1                    (scheduler decision is a pure function)
    D-SCHED-2/3                  (selection iterates canonical_order;
                                  first runnable wins)
    D-SCHED-9/10/11              (no randomness, no UUID, no wall-clock)
    D-SCHED-12/13                (predicate evaluation via Step-3
                                  aggregator; ordered short-circuit)
    D-FORBID-9                   (no speculative execution; scheduler
                                  never invokes a task)

  Step 6:
    D-SESS-1/2/3                 (ExecutionSession is sole mutable
                                  orchestration authority; replay-
                                  authoritative state reconstructable
                                  from trace)
    D-EXEC-1/2                   (orchestration tick has fixed phase
                                  order; sub-phases sequenced)
    D-EXEC-7/8                   (trace commit follows the action)
    D-BUS-6                      (subscriber topology frozen at begin())

Public API (intentionally tiny)

  EventEnvelope                — frozen record describing one event
  EventSubscriber              — Protocol; subscribers expose on_event
  EventBus                     — synchronous freeze-able dispatcher
  EventBusFrozenError          — raised on register/unregister after freeze
  EventBusReentryError         — raised when a subscriber re-enters emit
  SUBSCRIBER_ERROR_EVENT_TYPE  — canonical kind for capture events

  InMemoryTraceRecorder        — step-1 in-memory ordering recorder
  DurableTraceRecorder         — step-2 append-only on-disk recorder
  TraceRecorderFinalizedError  — raised on post-finalize mutations
  TraceRecorderNotEmptyError   — raised when the target package dir is
                                  already populated

  SessionPackage               — passive on-disk layout (manifest.json
                                  + events.jsonl)
  Manifest                     — manifest schema (step-2 minimal form)
  IntegrityReport              — verifier output (deterministic)
  verify_package_integrity     — minimal integrity verifier
  serialize_envelope           — canonical JSON for one envelope
  serialize_manifest           — canonical JSON for one manifest
  fingerprint                  — alias for serialize_envelope; semantic
                                  intent is "content key for identity
                                  comparison", not "on-disk encoding"
  PACKAGE_VERSION              — current on-disk layout version (1)
  INVARIANT_CONTRACT_VERSION   — current contract version (1)
  MANIFEST_FILENAME            — canonical filename inside the package
  EVENTS_FILENAME              — canonical filename inside the package

Anything beyond this surface is out of scope for steps 1 + 2.
"""

from .events import (
    EventEnvelope,
    EventSubscriber,
    EventBus,
    EventBusFrozenError,
    EventBusReentryError,
    SUBSCRIBER_ERROR_EVENT_TYPE,
)
from .package import (
    CANONICAL_DUMPS_KWARGS,
    EVENTS_FILENAME,
    INVARIANT_CONTRACT_VERSION,
    IntegrityReport,
    MANIFEST_FILENAME,
    Manifest,
    PACKAGE_VERSION,
    SessionPackage,
    canonical_dumps,
    fingerprint,
    serialize_envelope,
    serialize_manifest,
    verify_package_integrity,
)
from .graph import (
    ERROR_CYCLE,
    ERROR_DUPLICATE_EDGE,
    ERROR_DUPLICATE_NODE_ID,
    ERROR_EDGE_UNKNOWN_NODE,
    ERROR_SELF_EDGE,
    GRAPH_FINGERPRINT_VERSION,
    GraphValidationError,
    GraphValidationIssue,
    GraphValidationReport,
    TaskEdge,
    TaskGraph,
    TaskNode,
)
from .predicates import (
    FixtureEmpty,
    FixtureSnapshot,
    ObjectAtFixture,
    ObjectPoseWithin,
    ObjectSnapshot,
    Predicate,
    PredicateContext,
    PredicateEvaluationError,
    PredicateGroupResult,
    PredicateResult,
    evaluate_predicates,
)
from .scheduler import (
    NODE_STATUS_BLOCKED_BY_PARENTS,
    NODE_STATUS_BLOCKED_BY_PRECONDITION,
    NODE_STATUS_BLOCKED_BY_PREDICATE_ERROR,
    NODE_STATUS_COMPLETED,
    NODE_STATUS_FAILED,
    NODE_STATUS_RUNNABLE,
    NODE_STATUS_SELECTED,
    NodeEvaluation,
    SCHEDULER_DECISION_FINGERPRINT_VERSION,
    SchedulerDecision,
    SchedulerDecisionReason,
    SchedulerEvaluationError,
    TopologicalSequentialScheduler,
)
from .session import (
    EVENT_NODE_EXECUTION_COMPLETED,
    EVENT_NODE_EXECUTION_STARTED,
    EVENT_NODE_SELECTED,
    EVENT_SESSION_COMPLETED,
    EVENT_SESSION_FAILED,
    EVENT_SESSION_STARTED,
    ExecutionSession,
    ExecutionSessionError,
    NODE_RT_COMPLETED,
    NODE_RT_FAILED,
    NODE_RT_PENDING,
    NODE_RT_RUNNING,
    NODE_RT_SKIPPED,
    NodeRuntimeState,
    SESSION_SNAPSHOT_FINGERPRINT_VERSION,
    SessionRuntimeSnapshot,
    SessionState,
    TaskExecutorLike,
)
from ..tasks.executor import ResetScope
from .trace import (
    DurableTraceRecorder,
    InMemoryTraceRecorder,
    TraceRecorderFinalizedError,
    TraceRecorderNotEmptyError,
)


__all__ = [
    # Step 1 — EventBus / events
    "EventEnvelope",
    "EventSubscriber",
    "EventBus",
    "EventBusFrozenError",
    "EventBusReentryError",
    "SUBSCRIBER_ERROR_EVENT_TYPE",
    # Step 1 — in-memory recorder
    "InMemoryTraceRecorder",
    # Step 2 — durable recorder + errors
    "DurableTraceRecorder",
    "TraceRecorderFinalizedError",
    "TraceRecorderNotEmptyError",
    # Step 2 — package surface
    "SessionPackage",
    "Manifest",
    "IntegrityReport",
    "verify_package_integrity",
    "serialize_envelope",
    "serialize_manifest",
    "fingerprint",
    "canonical_dumps",
    "CANONICAL_DUMPS_KWARGS",
    # Step 2 — constants
    "PACKAGE_VERSION",
    "INVARIANT_CONTRACT_VERSION",
    "MANIFEST_FILENAME",
    "EVENTS_FILENAME",
    # Step 3 — predicate primitives
    "Predicate",
    "PredicateContext",
    "PredicateResult",
    "PredicateGroupResult",
    "PredicateEvaluationError",
    "ObjectSnapshot",
    "FixtureSnapshot",
    "ObjectAtFixture",
    "FixtureEmpty",
    "ObjectPoseWithin",
    "evaluate_predicates",
    # Step 4 — TaskGraph topology
    "TaskNode",
    "TaskEdge",
    "TaskGraph",
    "GraphValidationError",
    "GraphValidationIssue",
    "GraphValidationReport",
    "GRAPH_FINGERPRINT_VERSION",
    "ERROR_DUPLICATE_NODE_ID",
    "ERROR_DUPLICATE_EDGE",
    "ERROR_SELF_EDGE",
    "ERROR_EDGE_UNKNOWN_NODE",
    "ERROR_CYCLE",
    # Step 5 — deterministic scheduler
    "TopologicalSequentialScheduler",
    "SchedulerDecision",
    "SchedulerDecisionReason",
    "SchedulerEvaluationError",
    "NodeEvaluation",
    "SCHEDULER_DECISION_FINGERPRINT_VERSION",
    "NODE_STATUS_COMPLETED",
    "NODE_STATUS_FAILED",
    "NODE_STATUS_BLOCKED_BY_PARENTS",
    "NODE_STATUS_BLOCKED_BY_PRECONDITION",
    "NODE_STATUS_BLOCKED_BY_PREDICATE_ERROR",
    "NODE_STATUS_RUNNABLE",
    "NODE_STATUS_SELECTED",
    # Step 6 — runtime ExecutionSession
    "ExecutionSession",
    "ExecutionSessionError",
    "SessionState",
    "SessionRuntimeSnapshot",
    "NodeRuntimeState",
    "TaskExecutorLike",
    "SESSION_SNAPSHOT_FINGERPRINT_VERSION",
    "NODE_RT_PENDING",
    "NODE_RT_RUNNING",
    "NODE_RT_COMPLETED",
    "NODE_RT_FAILED",
    "NODE_RT_SKIPPED",
    "EVENT_SESSION_STARTED",
    "EVENT_NODE_SELECTED",
    "EVENT_NODE_EXECUTION_STARTED",
    "EVENT_NODE_EXECUTION_COMPLETED",
    "EVENT_SESSION_COMPLETED",
    "EVENT_SESSION_FAILED",
    "ResetScope",   # re-export from cell_authoring.tasks (step-6 additive)
]
