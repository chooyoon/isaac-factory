# Phase 4B Step 9 — Architecture-First Analysis: Deterministic Failure Semantics

**Status:** **DRAFT — analysis only.** No contract clause in this document is frozen. The companion contract document [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md) §13 D-FAULT-* is intentionally absent and will only be authored after this analysis converges through review.

**Author posture:** Phase 4B Step 9 begins with architecture-first analysis. Implementation is forbidden until the converged contract is frozen, the Mutation Authority Matrix is extended, and pure-Python invariant tests are drafted. See §H for the sequencing.

**Predecessor:** [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md) §12 D-CONT-* (Step 8 closure). This analysis extends the same posture into the failure domain: an explicit, narrow, replay-authoritative contract, never an implicit secondary orchestration system.

**Critical architectural rule binding every section below:**

> Failure handling MUST NOT become an implicit secondary orchestration system.
>
> Every transition, mutation, and verdict in the failure path is as explicit, replay-authoritative, append-only, and mechanically deterministic as a happy-path transition. The system never "silently heals" orchestration state. Recovery semantics are explicit graph semantics, not hidden runtime behaviour.

---

## §A. Failure taxonomy analysis  *(task 1)*

### A.1 Two-tier taxonomy

Phase 4B today has exactly one failure surface: `TaskOutcome` (9 values, 1 PASS + 8 task-level failure verdicts) emitted by the Phase 4A validator and consumed by `ExecutionSession` into the binary `SessionState.{COMPLETED, FAILED}` terminus. This is insufficient. The Step 9 architecture proposes a **two-tier taxonomy**:

* **Outer tier — orchestration-level failure classes** (Step 9, session-owned). Eight categories, each with a distinct origin authority and propagation rule. Not all are validator verdicts; several never touch the validator.
* **Inner tier — task-level failure sub-classifications.** Only `NODE_EXECUTION_FAILURE` has an inner taxonomy today: the existing 8 non-PASS values of `TaskOutcome`. The other seven outer categories have no `TaskOutcome` counterpart and SHALL NOT be retrofitted onto `TaskOutcome` (it stays a per-task verdict produced by the validator, not a session-level enum).

The two tiers exist because the **authorities differ**. `TaskOutcome` is produced by `UnifiedValidator` inside `TaskExecutor.execute()` per D-CONF single-source-of-truth. The Step 9 outer-tier categories are produced by `ExecutionSession`, the scheduler, the operator channel, or a postcondition checker — none of which are the Phase 4A validator. Forcing them through `TaskOutcome` would breach the Mutation Authority Matrix (§13 will extend it).

### A.2 The 8 orchestration-level failure classes

The following are working definitions. Each row is normative *in intent* but not yet pinned as a D-FAULT-* clause.

| # | class | origin authority | propagation rule | retained-state implication | replay expectation | trace requirement |
|---|---|---|---|---|---|---|
| 1 | `NODE_EXECUTION_FAILURE` | `UnifiedValidator` inside `TaskExecutor.execute()`; surfaces as `TaskOutcome != PASS` | Phase G consumes the verdict; session marks the node `failed`; the configured `FailureAction` of the node decides downstream cascade | retained continuity at boundary is determined by whether `ResetScope` was `FULL` or `ACQUIRED_ONLY` AND by D-CONT-5 (no occupancy commit if not PASS) | byte-identical replay reproduces the same verdict; the `TaskOutcome` value is part of the `NodeExecutionCompleted` payload | append `NodeExecutionCompleted` with `passed=False` + `outcome_value` (the task-level sub-class) |
| 2 | `PRECONDITION_FAILURE` | scheduler (D-SCHED-13) | node is not selected; remains pending; never enters Phase B/C; downstream cascade per `FailureAction` | retained state untouched by the affected node (no execution occurred); pre/post boundary snapshots not emitted for this node | replay reproduces the same `blocked_by_precondition` status and the same `first_failure_index` | append a `NodeBlocked` event (NEW; currently the scheduler diagnostic is on-the-record only via `SchedulerDecision`, not via a bus event) |
| 3 | `AUTHORITY_VIOLATION` | `ExecutionSession` postcondition check at Phase G; OR a static-introspection contract test (latter is build-time, not runtime) | session aborts immediately; no further nodes scheduled; session ends `FAILED` with `terminator_reason=AUTHORITY_VIOLATION` | the runtime never reaches a clean boundary; the partially-committed retained state is recorded but explicitly marked as un-trusted in the final snapshot | replay reproduces the same violation at the same `seq` | append `AuthorityViolationDetected` (NEW) carrying the violated clause ID (`D-CONT-5`, `D-SESS-1`, etc.) |
| 4 | `CONTINUITY_VALIDATION_FAILURE` | `ExecutionSession` Phase G boundary-snapshot postcondition (NEW); detects D-CONT-1/-2/-6 violations | session aborts immediately; **no recovery**; replay-identity becomes meaningless past this point | the post-node boundary snapshot is *the* artifact whose validation failed — it is preserved verbatim in the trace | replay reproduces the same failed snapshot | append `ContinuityValidationFailed` (NEW); the snapshot itself is the evidence payload |
| 5 | `TIMEOUT_FAILURE` | `ExecutionSession` tick-budget enforcement at Phase D/E (NEW; budget is a per-`TaskDefinition` constant, NOT wall-clock) | node marked `failed` with `outcome_value=TASK_TICK_BUDGET_EXCEEDED`; cascade per `FailureAction` | retained state preserved up to the last clean tick; the in-progress tick is rolled back to the snapshot at Phase B/C | replay reproduces the same tick count at which the budget tripped | append `NodeTimeoutTripped` (NEW); payload includes `tick_budget_ticks`, `ticks_consumed`, the deterministic break-point |
| 6 | `OPERATOR_ABORT` | `OperatorChannel` envelope (Step 11 originally; **Step 9 may require landing this earlier — see §F open question**) | only honoured at Phase A of the next tick (never mid-tick); session enters `ABORTING`, drains the current node to a clean Phase G if possible, then ends `FAILED` with `terminator_reason=OPERATOR_ABORT` | retained state at the last completed Phase G is preserved as the abort boundary | replay reproduces the abort at the same `seq`; the operator command is part of the trace input | append `OperatorAbortRequested` (event ingress) + `SessionAborted` (terminal state) |
| 7 | `INFRASTRUCTURE_DEGRADATION` | out-of-band detector (Kit subprocess exit, PhysX exception, simulation_app death) | session has no opportunity to record a clean transition; the trace ends mid-tick; the SessionPackage manifest will report a gap | retained state is by definition not authoritative — the last clean Phase G boundary snapshot is the last trustable artifact | replay CANNOT reproduce — this class is fundamentally a non-replayable failure | the trace itself signals the failure via missing-finalize (D-TRACE-2/-6); a post-mortem `InfrastructureDegradationDetected` may be authored by the launch harness (NOT the session — the session is dead) |
| 8 | `REPLAY_INTEGRITY_FAILURE` | replay-identity tool (`tools/check_session_replay_identity.py`, Step 8 Phase 6) detects byte-divergence between two SessionPackages of nominally identical input | replay tool exits non-zero; the divergent SessionPackage(s) are quarantined; no automatic re-run | does not occur during a live session; this is a **meta**-failure detected at verification time | by definition: this IS the replay path detecting non-identity | not appended to a session's events.jsonl (the session itself was clean); recorded in the replay tool's own audit log |

### A.3 Cross-cutting observations

* **Wall-clock is forbidden everywhere.** `TIMEOUT_FAILURE` uses **tick budgets**, not seconds. A per-`TaskDefinition` integer `max_ticks` (or a derived budget from trajectory length × tolerance) is a deterministic property; wall-clock seconds are not. This is non-negotiable per D-FORBID and D-SCHED-9/10/11.
* **Five of the eight classes are NEW outer-tier categories** that have no current event type. Step 9 introduces these event types (see §D.2).
* **`NODE_EXECUTION_FAILURE` inherits TaskOutcome wholesale.** No change to `TaskOutcome`; no new values added by Step 9. The inner taxonomy is closed under Phase 4A's authority.
* **`INFRASTRUCTURE_DEGRADATION` is fundamentally outside replay identity.** The contract MUST acknowledge that some failures are non-replayable. Pretending otherwise breeds silent replay tolerance — exactly what the architectural rule forbids.
* **`REPLAY_INTEGRITY_FAILURE` is a meta-failure** detected by tooling, not by the session. It is in the taxonomy for completeness — the contract should explicitly NAME it so engineers don't quietly invent a "replay healed itself" code path.

### A.4 What is NOT in the taxonomy (deliberate exclusions)

The following are NOT failure classes in Phase 4B Step 9 and SHALL NOT be added by retrofit:

* **`TRANSIENT_FAILURE`** — failures are not classified by reproducibility expectation; every failure is treated as deterministic.
* **`PARTIAL_SUCCESS`** — a task is PASS or it is FAILURE. Phase 4A's validator emits exactly one verdict per execution.
* **`RECOVERABLE_FAILURE`** — recovery is not a property of the failure; it is a property of the graph topology (whether a recovery node follows).
* **`WARNING`** — the architecture has no severity tiers below `failure`. Diagnostic information lives in observational projection (D-CONT-1), not in the failure taxonomy.

Suppressing these now is load-bearing: every one of them is a vector for the "implicit secondary orchestration system" anti-pattern.

---

## §B. Abort / cancellation semantics analysis  *(task 2)*

### B.1 Where in the tick can an abort enter?

The Step 8 D-EXEC tick is:

```
A. operator command drain  (Step 11 — between-node only)
B. scheduler decision
C. preconditions
D. command emission to executor
E. executor.execute()           [PhysX runs here]
F. (post-execute orchestration validation, bundled into E by D-CONF)
G. session commit (D-CONT-5 occupancy + boundary snapshot)
```

The candidate abort entry points:

| candidate | analysis | verdict (draft) |
|---|---|---|
| during Phase E (mid-`execute()`) | breaks D-EXEC-1 (no event out of phase) and D-BUS-6/-7 (topology frozen); would require the executor to introspect the bus mid-step | **forbidden** |
| between Phase A and Phase B | natural fit — Phase A's job is exactly to drain operator commands; an abort drains and goes straight to terminal state | **proposed canonical abort point** |
| between Phase G of node N and Phase A of node N+1 | identical to the above (Phase A of N+1) | **acceptable** |
| at session boundary only (after `complete()`) | too coarse — operator cannot abort a running multi-node job | **insufficient** |

Therefore abort enters at **Phase A** and only at Phase A. The session honors the queued `OperatorAbortRequested` envelope before consulting the scheduler. This generalizes the D-CONT-3 boundary-quiescence discipline: abort happens at the same quiescent interval where retained-state transitions are already legal.

### B.2 Parent→child ordering

A graph with `A → B → C`:

* If `A` is selected and fails (`NODE_EXECUTION_FAILURE`), `B` and `C` see a `failed` parent in their scheduler evaluation. They remain `blocked_by_parents` forever (since `failed != completed`).
* If `OPERATOR_ABORT` enters Phase A, no further nodes are selected. `B` and `C` are not `blocked_by_parents` — they are `cascade_skipped`.
* If `A` is mid-execute and an abort arrives, the executor finishes its current `world.step()` budget, the executor's Phase E returns with the current verdict (PASS or FAIL), Phase G commits per D-CONT-5, and abort drain happens at the *next* Phase A — i.e. before B is selected.

**Open question (§F):** is "finish the current node cleanly" the right abort semantic, or should abort be allowed to interrupt mid-tick at a sub-step boundary inside `execute()` (e.g. between `world.step()` calls)?

* Pro mid-tick interrupt: faster operator response, less wasted simulation work.
* Con mid-tick interrupt: breaks D-EXEC-2 (no event out of phase); makes Phase E non-atomic, requires bus emit inside `execute()`, breaks D-CONT-3 conceptually.

Current analysis posture: **NO mid-tick interrupt.** Phase E is atomic. Abort drains the current node then aborts the next selection.

### B.3 Sibling cancellation semantics

Diamond graph `A → {B, C} → D`:

* If `A` fails, both `B` and `C` are cascade-skipped (not selected).
* If `B` fails after `A` completed, what happens to `C`?

This is the **nested cascade question** the contract doc §11 item 4 pre-staged. Two semantics are possible:

| semantic | meaning |
|---|---|
| **sibling-tolerant** | `C` is independent — if its preconditions still pass, it executes; the graph just records `B` as failed and continues |
| **sibling-strict** | once any sibling fails, the entire fan-out cohort is cancelled (no fairness guarantee about which sibling fails first) |

Both are deterministic provided the choice is pinned per-graph or per-edge. The architecture doc currently *implies* sibling-tolerant via `FailureAction.SKIP_NODE` semantics but does not normatively pin it.

**Proposed analysis posture (open):** sibling-tolerant by default, sibling-strict via an explicit `FailureAction.ABORT_COHORT` field on the parent's downstream edges. Both must be deterministic; the choice is per-graph topology.

### B.4 Graph-wide abort semantics

Three escalation tiers:

1. `FailureAction.SKIP_NODE` — failed node is recorded; downstream subtree is cascade-skipped; rest of graph executes.
2. `FailureAction.ABORT_JOB` — failed node is recorded; session enters `ABORTING`; remaining pending nodes are cascade-skipped uniformly; session ends `FAILED`.
3. `OPERATOR_ABORT` — externally injected, same effect as `ABORT_JOB` but with operator provenance.

`AUTHORITY_VIOLATION`, `CONTINUITY_VALIDATION_FAILURE`, `INFRASTRUCTURE_DEGRADATION` SHALL imply `ABORT_JOB` semantics unconditionally — there is no per-edge `FailureAction` for these because the failure itself indicates the orchestration substrate is broken.

### B.5 Idempotent cancellation

A node cascade-skipped twice (e.g. two parents failed) MUST produce exactly one `TaskCascadeSkipped` event in the trace. The session SHALL track skip-emitted state on `NodeRuntimeState` to suppress duplicate emissions. Cancellation is idempotent at the event level.

An abort issued twice (e.g. operator clicks twice) MUST collapse — the second `OperatorAbortRequested` envelope is observed (entered into the trace) but produces no additional state transition. Idempotency is at the *transition*, not the *envelope*.

### B.6 Retained-state ownership during abort

Critical scenario: node `B` is mid-execute when abort arrives at Phase A drain time. (Equivalent statement: abort was queued during node `B`'s Phase E but is honoured at next-Phase-A.)

The retained state at abort-honour time is:

* Phase G of `B` either committed (if `B`'s execute returned PASS) or not (if FAIL).
* Boundary snapshot for `B.post_node` either exists in the trace or does not.

**Authority ownership at abort:**

* Objects in D-LIFE `available` / `released`: continue to be owned by the registry per D-CONT-1.
* Objects in D-LIFE `attached` / `reserved`: are they released? **OPEN QUESTION (§F).**

The clean answer is: **the abort respects D-CONT-1 as-of the last clean Phase G.** No additional lifecycle transitions occur at abort. If an object was `attached` to the gripper at the last clean Phase G, it remains `attached` in the abort terminal state. Recovery (or operator manual intervention) is the explicit graph step that releases it.

### B.7 Legality of partial world mutation during interruption

If abort enters at Phase A, no partial world mutation occurs — the previous node either fully committed Phase G or did not (failure path). Either way, the boundary snapshot is well-defined.

If `INFRASTRUCTURE_DEGRADATION` strikes mid-Phase-E, partial world mutation by definition exists in the PhysX scene but is non-recoverable. The contract MUST acknowledge: the world state at infrastructure failure is **un-trusted** and **un-replayable**. The last clean Phase G snapshot is the last authoritative state. Partial PhysX state past that point is forensic only.

---

## §C. Retained-state failure posture  *(task 3)*

### C.1 Canonical interrupted-continuity scenario

> Node A: pick from belt → place at FixtureA. PASSES.
> Node B: pick from FixtureA → place at FixtureB. FAILS during transport (`GRASP_LOST_IN_TRANSPORT`).
> What is the authoritative retained state at the post-B boundary?

This is the analysis case. Several positions are possible; none is yet decided.

### C.2 Authority ownership after interruption — analysis

At the post-B boundary, three sets of facts are observable:

1. **Pre-B boundary snapshot**: FixtureA occupied, FixtureB empty, peg at FixtureA pose.
2. **B's TaskResult**: `outcome = GRASP_LOST_IN_TRANSPORT`, evidence carries the peg's last-observed pose during transport.
3. **Post-B boundary snapshot** (assuming it is emitted): D-CONT-5 says NO occupancy commit on non-PASS. Therefore FixtureA still shows `occupied` in the post-B snapshot, FixtureB still shows `empty`. But the **canonical object pose** of the peg — is it where it was dropped, or where it was?

Three candidate semantics:

| semantic | pre-B snapshot peg pose | post-B snapshot peg pose | implication |
|---|---|---|---|
| **C2-a "frozen"** | (0.5, 0.0, 0.1) | (0.5, 0.0, 0.1) | post-snapshot lies about reality — the peg is *not* at FixtureA anymore |
| **C2-b "last-tick truth"** | (0.5, 0.0, 0.1) | (0.7, 0.1, 0.0) — wherever it landed | post-snapshot reflects last-tick observational projection promoted to authoritative |
| **C2-c "two snapshots, both authoritative"** | (0.5, 0.0, 0.1) | a special "last clean pose" + "post-failure pose" both serialized | snapshot schema grows a discriminator |

**Open question (§F):** which semantic does D-FAULT-* pin? Current analytical posture leans toward **C2-b "last-tick truth"** because:

* it matches the existing D-CONT-1 definition of canonical object pose ("the final per-tick `update_object_pose` write"),
* it requires no schema change to the boundary snapshot,
* the failure verdict + TaskOutcome carry the *reason* the pose is anomalous; replay reproduces both verdict and pose byte-equally.

But C2-b has a side effect: a future predicate reading "is the peg at FixtureA?" via the registry post-B will say "NO." That may be desirable (truth in the registry) or undesirable (the fixture is still authoritatively occupied per D-CONT-5 — a contradiction between `fixtures.FixtureA.occupied_by == "peg"` and `objects.peg.pose_m ≠ FixtureA`). The contradiction is real and a recovery node must resolve it explicitly.

### C.3 Legality of rollback — analysis

The instinct on encountering the C2-b contradiction is "roll back FixtureA's occupancy to `None` so the snapshot is internally consistent." This is **forbidden** by the architectural rule:

* Rollback is a *mutation* of retained state.
* If rollback is implicit, it is a hidden orchestration authority.
* D-CONT-5 says occupancy mutates only at Phase G under PASS verdict — there is no clause permitting Phase G mutation on FAIL.
* Adding an implicit "Phase G' on failure" is exactly the implicit secondary orchestration system the rule forbids.

Therefore: **no implicit rollback.** The post-B snapshot records the contradiction faithfully. Recovery is the explicit resolution.

Two recovery topologies are then possible — both are graph-explicit, not runtime-implicit:

* **C3-a explicit recovery node.** After B's failure-edge, the graph routes to a `recover_peg_drop_at_fixtureA` node whose execute attempts to re-acquire the dropped peg. If it succeeds, occupancy is finally resolved.
* **C3-b explicit operator-recovery edge.** Failure routes to an operator-intervention envelope. Operator decides; intervention is the explicit replay-authoritative transition.

Both topologies are pure graph semantics. No hidden code path. No "self-healing." **This is the load-bearing posture of §C: recovery is graph topology, never runtime behaviour.**

### C.4 Recovery-node requirements — analysis

If C3-a is adopted, a recovery node has the same shape as any other `TaskNode`:

* preconditions (e.g. "fixture A still authoritatively occupied AND peg pose not at fixture A")
* a task definition (`RecoverPegTask` — different `task_ref`, different trajectory)
* postconditions (peg back at fixture A OR explicit `failed`)

The recovery node is reachable via an edge condition on the parent's failure verdict. The scheduler treats it identically to any other node. **No new authority is introduced.**

### C.5 Continuity preservation boundaries

The architecture must pin: at what *boundary* is retained-state failure considered "stabilized"?

* Phase G of the failing node? — But D-CONT-5 says no Phase-G occupancy commit on FAIL. So Phase G's snapshot is the last authoritative *snapshot* even on failure (the snapshot is emitted; the occupancy mutation is not).
* The next Phase B precondition evaluation? — Yes, by construction: the next scheduler decision works against post-failure boundary state.

**Proposed analysis posture:** the failure-boundary is the post-node boundary snapshot of the failing node, emitted at Phase G regardless of PASS/FAIL verdict. This snapshot is the authoritative retained-state-at-failure record. It IS replay-authoritative. Recovery-node preconditions consult it.

---

## §D. Failure trace contract analysis  *(task 4)*

### D.1 Append-only discipline extension

D-TRACE-2 already enforces append-only. Step 9 extends the *event coverage* without weakening the discipline. Every failure-class transition is one append. There is no "edit prior event," "retroactively mark a node failed," or "compact failed events." Every state observable in the failure path is reconstructible by replaying events.jsonl in seq order through a stateless reducer.

### D.2 Proposed new event types

The following event types are introduced by Step 9 (numbered identifiers, exact strings to be pinned in contract freeze):

| event type (proposed) | emitted at | payload (sketch) |
|---|---|---|
| `NodeBlocked` | Phase B when scheduler returns no-runnable AND a node has `blocked_by_precondition` OR `blocked_by_predicate_error` AND the operator wants observation | `{node_id, status: "blocked_by_precondition"\|"blocked_by_predicate_error", first_failure_index, predicate_fingerprint}` |
| `TaskCascadeSkipped` | Phase B when scheduler returns no-runnable AND a node's parents include a `failed` node | `{node_id, ancestor_failed: [...], cascade_distance}` |
| `NodeTimeoutTripped` | inside Phase E when tick budget exceeded — emitted by session, NOT executor (executor returns control on budget exhaustion) | `{node_id, tick_budget, ticks_consumed}` |
| `AuthorityViolationDetected` | Phase G postcondition check (NEW) when D-CONT-5 or D-SESS-1 invariant test fails at runtime | `{violated_clause: "D-CONT-5", node_id, evidence}` |
| `ContinuityValidationFailed` | Phase G boundary-snapshot postcondition (NEW) when snapshot fails D-CONT-6 schema or D-CONT-1 allowlist | `{node_id, snapshot_kind, failure_reason, snapshot_hash}` |
| `OperatorAbortRequested` | Phase A envelope drain — the ingress event when operator command arrives | `{requested_at_seq, abort_reason: str}` |
| `SessionAborting` | Phase A right after Operator abort accepted | `{terminator_reason}` |
| `SessionAborted` | terminal — replaces `SessionFailed` when terminator was operator-initiated | `{terminator_reason, last_clean_node_id, last_clean_seq}` |
| `RecoveryNodeEntered` | Phase B selection of a node whose graph metadata flags it as a recovery node | `{node_id, recovers_from_node_id, recovers_from_outcome}` |

Total: 9 new event types. All are append-only, canonical-JSON serialized, fingerprint-stable.

**Open question (§F):** is `NodeBlocked` desirable, or do we keep "blocked-not-emitted" semantics (the scheduler decision is recordable via post-mortem inspection of session state but does not produce a bus event)? Argument for emit: every transition is observable in the trace. Argument against: blocked nodes can be perpetual (depend on a never-completed parent); they'd emit on every scheduler call, polluting the trace.

Current posture: emit `NodeBlocked` **once per node**, not once per scheduler call. The session SHALL track per-node "blocked-emitted" flag.

### D.3 Replay-integrity failure trace handling

`REPLAY_INTEGRITY_FAILURE` is detected by the comparator tool, not by a live session. It SHALL NOT be appended to a session's events.jsonl (the session was successful from its own perspective; the failure is a verification-time discovery). It SHALL be recorded in:

* the comparator tool's exit code (non-zero — already done in Step 8 Phase 6),
* a separate audit artifact (proposed: `replay_audit/<timestamp>_<pkg_a>_vs_<pkg_b>.json`) outside the SessionPackage hierarchy.

### D.4 Operator intervention trace

The operator envelope MUST be the trace-of-record for every operator intervention. No "operator hit a button at wall-time T" detail bypasses the envelope. The envelope carries:

* `kind`: `abort` | `pause` (Step 11 placeholder) | `resume` (Step 11) | `manual_advance` (Step 11)
* `requested_at_seq`: the most recent `seq` the operator observed before issuing the command (proof of provenance)
* `reason`: short string

The operator authority is exposed via `OperatorChannel`, which is the Phase-A-only ingress point. **Open question (§F):** does Step 9 need to land OperatorChannel infrastructure, or can it model abort-as-event-injection without a channel object yet?

Current analytical posture: **defer OperatorChannel object to Step 11 as originally planned**, BUT introduce a minimal abort ingress: the launch harness can inject a pre-queued abort envelope at start time for testing purposes (deterministic — abort fires at known seq). True operator interactivity is Step 11. This lets Step 9 test the abort-handling code paths deterministically without a live operator.

### D.5 Recovery-posture transitions

If recovery nodes are introduced (C3-a), each recovery-node entry emits `RecoveryNodeEntered` with explicit linkage to the failure it recovers from. This makes the trace self-describing: a tail-to-head walk reconstructs "this node ran because node X failed with outcome Y." No implicit linkage.

---

## §E. Replay-divergence risk register  *(task 5)*

Each risk is a non-implementation observation, written so a future contributor can locate and prevent the divergence. Risks are not bugs; they are vectors. Numbering mirrors Step 8's A1-A5 / H1-H13 register.

### E.1 Timeout ordering risk

**Vector:** if `TIMEOUT_FAILURE` is implemented as "stop running steps when wall-clock exceeds X," replay diverges across hardware. **Mitigation:** budget MUST be a per-`TaskDefinition` tick count, never wall-clock. The session counts `world.step()` invocations against the budget. Tick counts are deterministic. Wall-clock is forbidden.

### E.2 Cancellation ordering risk

**Vector:** sibling cancellation order depends on canonical_order (Step 4 D-SCHED-2). If a future contributor introduces "iterate `self._pending` set" for cascade emission, dict ordering varies and traces diverge. **Mitigation:** cascade-skip emission iterates `graph.canonical_order` exactly as scheduler selection does. Tested by introspection.

### E.3 Retained-state mutation during failure risk

**Vector:** the temptation to "clean up" a half-attached object on FAIL ("call `release()` to return the gripper to a known state") implicitly mutates D-LIFE state outside Phase G. **Mitigation:** D-CONT-5a forbids this. Step 9 amends to extend: lifecycle transitions on FAIL are forbidden EXACTLY as on PASS. The state at last clean Phase G is the failure-boundary truth.

### E.4 Operator intervention timing risk

**Vector:** abort envelopes are honoured at Phase A. If the operator sends "abort" twice in quick succession and the second envelope's `requested_at_seq` is unstable across runs, replay diverges. **Mitigation:** in deterministic testing, operator inputs are queued as part of the SessionPackage *inputs*, not as live events. The envelope `requested_at_seq` is the seq the *injection scaffold* assigns, fully deterministic.

### E.5 Partial cleanup semantics risk

**Vector:** `ResetScope.ACQUIRED_ONLY` between nodes preserves grip closure (D-CONT-4). If failure handling introduces a "release the gripper before next node" cleanup, the next node's pre-execute state diverges from non-failure runs. **Mitigation:** failure does NOT trigger cleanup. The grip closure is part of authoritative retained state; recovery may release it explicitly via a graph step.

### E.6 Interruption boundary timing risk

**Vector:** if abort is honoured "as soon as practical" (e.g. between sub-trajectory waypoints inside `execute()`), the precise interruption tick varies across timing-sensitive PhysX runs. **Mitigation:** abort is Phase-A-only. No mid-execute interruption. Phase E is atomic from the orchestration perspective.

### E.7 Failure-fingerprint instability risk

**Vector:** `TaskResult` evidence fields (e.g. `peg_xyz_initial`, `placement_offset_xy_m`) are floats. Two byte-identical runs SHOULD produce byte-identical evidence; if a future float promotion introduces `repr(float)` of an intermediate computed value (rather than a direct PhysX read), encoding instability can leak. **Mitigation:** every evidence field must come from a deterministic PhysX read or a deterministic arithmetic on PhysX reads. Step 8 Phase 6 already proves this for the happy path; Step 9 extends the assertion to all failure-event payloads.

### E.8 Cascade-emission idempotency risk

**Vector:** cascade-skip events are emitted from a scheduler-driven loop. If the loop re-fires (e.g. scheduler called twice for an unrelated reason), a node could receive two `TaskCascadeSkipped` events. **Mitigation:** session-side `_cascade_emitted: set[str]` tracks emission state. Idempotency proven by unit test ("issue cascade twice; observe one event").

### E.9 Authority-violation infinite recursion risk

**Vector:** `AuthorityViolationDetected` is emitted via the EventBus. If the violation IS in the bus or the trace, emitting the violation event itself may re-trigger the violation. **Mitigation:** the session SHALL detect a violation-of-the-violation-emit path and terminate via raised `ExecutionSessionError` rather than re-emit. Last-resort termination is via process exit code, never via further append.

### E.10 Replay-tolerance creep risk

**Vector:** a future PR for "robustness" introduces "if the replay differs by <1ms in seq A vs B, treat as identical." Step 8 contract says: byte-equality, no tolerance. **Mitigation:** the comparator code remains string-equality only; any "approximate" comparator is rejected at review (cite D-FAIL-* and D-REPLAY-1).

### E.11 Recovery-loop divergence risk

**Vector:** if a recovery node itself fails, naive cascade might re-enter the same recovery node. Replay then depends on how the cascade engine handles recovery loops. **Mitigation:** the graph contract says recovery nodes are graph topology — a recovery node failing routes per its own `FailureAction`. Cycles in the graph are already forbidden (Step 4 D-SCHED-8 cycle detection). Recovery loops MUST be encoded as bounded-retry budgets in the graph, not as implicit recurrence.

### E.12 Late-bound failure-action risk

**Vector:** if `FailureAction` is mutated after graph construction (e.g. operator override at runtime), the scheduler's cascade behaviour becomes path-dependent. **Mitigation:** `FailureAction` is part of `TaskGraph` (Step 4 frozen), pinned at `graph.build()`. Operator override is a *separate* graph (a new session); it does not edit a running session's graph.

### E.13 Tick-budget under-the-line risk

**Vector:** a node "almost" exceeds tick budget — actually exceeds in run A by 1 tick, finishes just in time in run B. PhysX numerical sensitivity varies. **Mitigation:** task-level tick budgets MUST be set with margin. Step 9 introduces a `task.tick_budget_ticks` field; trajectory authoring SHALL produce budgets with documented margin. Pure-Python tests assert "trajectory of N ticks → budget ≥ N + margin".

### E.14 Cross-session retained-state risk

**Vector:** a recovery scheme that pulls retained state from a *previous* SessionPackage (e.g. "the peg was at this pose at the end of yesterday's session, resume from there") creates cross-session continuity. **Mitigation:** D-FORBID forbids cross-session shared state. Recovery operates within one session only. Loading a previous session is a *new* session whose inputs include the prior package's terminal boundary snapshot — this is a deliberate operator action, not implicit.

---

## §F. Open architectural questions — RESOLVED  *(Phase 2 closure, 2026-05-20)*

Each question is now closed. Resolution applies a five-lens risk analysis (**RD** replay-divergence, **HA** hidden-authority, **CT** contamination, **IR** implicit-recovery, **LA** lifecycle-ambiguity) and produces a single deterministic ruling. Where the analysis preferred convenience, the ruling chooses replay authority instead.

### §F.1 — `SessionState` granularity

**Question.** Add intermediate states (`ABORTING`, `ABORTED`, `RECOVERING`) or keep statuses node-level only?

**Risk analysis.**
* **RD:** more states → more transitions to fingerprint. Acceptable: each transition is one append.
* **HA:** `RECOVERING` as a session state would license a hidden "we know we are recovering" authority that mutates state outside graph topology. Severe.
* **CT:** none.
* **IR:** `RECOVERING` invites silent healing. Severe.
* **LA:** `ABORTING` without explicit terminus blurs operator-initiated vs validator-initiated failure.

**RULING.** SessionState gains **`ABORTING`** (transient) and **`ABORTED`** (terminal). `RECOVERING` is **FORBIDDEN as a session state** — recovery is graph topology, not a session-level mode. Final state set: `{INITIALIZED, RUNNING, ABORTING, ABORTED, COMPLETED, FAILED}`.

**Rationale.** Explicit terminal classes are replay-authoritative; the comparator distinguishes ABORTED from FAILED at the events.jsonl byte level via the terminal event's `event_type`. A `RECOVERING` session state would invite the implicit-secondary-orchestration anti-pattern; recovery nodes are visible only as ordinary `NodeExecutionStarted` events with explicit `recovery_of` metadata.

### §F.2 — Abort signal ingress

**Question.** Envelope-as-event, method-as-ingress, or both?

**Risk analysis.**
* **RD:** method-as-ingress does not appear in `events.jsonl`; replay cannot reconstruct an abort from canonical inputs. Severe.
* **HA:** method-as-ingress creates a code-only authority that mutates session state outside the trace. Severe.
* **CT:** none.
* **IR:** method-as-ingress could be called from anywhere, including during recovery — a vector for runtime self-healing.
* **LA:** method-as-ingress can be called at any phase, breaking Phase-A-only discipline (§B.1).

**RULING.** **ENVELOPE-AS-EVENT ONLY.** The sole abort ingress is an `OperatorAbortRequested` envelope queued through a constructor parameter (`pending_operator_envelopes: tuple[OperatorEnvelope, ...]`). `ExecutionSession.request_abort()` and any equivalent method are **FORBIDDEN**.

**Rationale.** Replay-identity demands the abort ingress be a canonical input. Pre-queued envelopes at `__init__` are deterministic — they fire at the next Phase A whose orchestration_tick ≥ the envelope's `requested_at_tick`. Live operator interactivity is Step 11.

### §F.3 — Sibling cancellation default

**Question.** Sibling-tolerant or sibling-strict by default?

**Risk analysis.**
* **RD:** undefined default → run-dependent cascade order. Severe.
* **HA:** implicit cohort-cancel would mutate `_skipped` for nodes that have no graph-declared dependency on the failure.
* **CT:** none.
* **IR:** none.
* **LA:** medium — the default needs explicit naming in `FailureAction` enum.

**RULING.** **SIBLING-TOLERANT BY DEFAULT.** `FailureAction.SKIP_NODE` (the default) cascade-skips only the failed node's descendants. Sibling-strict requires explicit `FailureAction.ABORT_COHORT` on the parent's downstream-edge metadata. Mixing within a fan-out is permitted only if each edge declares its policy.

**Rationale.** Tolerant is the truthful default — if there is no graph edge, there is no declared dependency. Hiding cohort-cancellation behind a default would mutate nodes whose only relationship to the failure is fan-out adjacency.

### §F.4 — Retained-state pose semantic on FAIL

**Question.** C2-a "frozen", C2-b "last-tick truth", or C2-c "dual snapshot"?

**Risk analysis.**
* **RD:** C2-a requires implicit rollback (mutation of canonical pose to a value that contradicts D-CONT-1's "final per-tick update_object_pose write"). Severe.
* **HA:** C2-a IS the hidden authority — "the snapshot lies to be consistent."
* **CT:** C2-c bloats the snapshot schema and creates two "truths" to compare against in replay. Significant.
* **IR:** C2-a IS implicit recovery — un-doing reality.
* **LA:** C2-b creates an explicit contradiction (occupancy says X, pose says Y); this is the truthful representation that recovery resolves.

**RULING.** **C2-b — last-tick truth.** Post-failure boundary snapshot reflects the actual canonical pose (the final `update_object_pose` write the failing node made). Fixture occupancy remains unchanged per D-CONT-5 (no PASS verdict → no mutation). The resulting contradiction is **preserved verbatim** and resolved by recovery topology, not by snapshot manipulation.

**Rationale.** C2-b matches the existing D-CONT-1 definition without amendment. Contradiction is forensic truth; truth is replay-authoritative. The architectural rule explicitly prefers explicit contradictory state over hidden runtime healing.

### §F.5 — `NodeBlocked` emission policy

**Question.** Emit once per blocking, never, or once per scheduler call?

**Risk analysis.**
* **RD:** once-per-call pollutes the trace with O(scheduler_calls × blocked_nodes) emissions, but is deterministic.
* **HA:** never-emit makes blocking invisible to replay — replay cannot distinguish "blocked once" from "blocked many times".
* **CT:** too-frequent emission could mask high-signal events.
* **IR:** none.
* **LA:** "once-per-blocking" requires emit-state tracking on `NodeRuntimeState`.

**RULING.** **EMIT-ONCE-PER-BLOCKING-EPISODE.** The session maintains a per-node `_blocked_emission_key: dict[node_id, str]` mapping. The emission key is `(blocking_status, blocking_reason_hash)`. A `NodeBlocked` event fires only when the current key differs from the recorded one. When the node becomes runnable or terminal, the key is cleared so re-blocking re-emits.

**Rationale.** Once-per-episode is bounded, observable, and idempotent. The episode boundary is well-defined (status transition out of blocked). The emission_key is part of the boundary snapshot's per-node runtime state, so replay sees identical emission timing.

### §F.6 — Tick-budget enforcement granularity

**Question.** Per-`world.step()` count, or per executor sub-phase?

**Risk analysis.**
* **RD:** per-`world.step()` count is purely deterministic. Sub-phase counters require the executor to expose sub-phase boundaries to the session — adds authority on the executor side.
* **HA:** sub-phase enforcement adds session-side knowledge of executor internals (D-SESS-1 boundary blur).
* **CT:** sub-phase counters introduce internal state participating in the boundary.
* **IR:** none.
* **LA:** sub-phase tripping would emit `NodeTimeoutTripped` with `sub_phase` payload that is executor-specific.

**RULING.** **PER-`world.step()` COUNT ONLY.** The session counts `world.step()` invocations during Phase E via an executor-returned tick count (executor reports `ticks_consumed` in `TaskResult`). The session checks `ticks_consumed > task.tick_budget_ticks` post-execute and trips `TIMEOUT_FAILURE` if exceeded. Pre-execute interruption is **FORBIDDEN** (preserves Phase E atomicity per §F.6a below).

**Rationale.** Single enforcement point. Single authority (session). No executor introspection. Trajectory authors encode sub-phase margin into the single budget value.

**§F.6a corollary — Phase E remains atomic.** The session does NOT interrupt the executor mid-step on budget exhaustion. The executor runs its declared trajectory to completion; the session then evaluates `ticks_consumed` against `tick_budget_ticks`. Atomicity preserved.

### §F.7 — OperatorChannel earliness

**Question.** Land OperatorChannel object in Step 9, or defer to Step 11 with pre-queued envelopes?

**Risk analysis.**
* **RD:** live channel adds nondeterminism vectors (when does an envelope arrive?). Pre-queued is fully deterministic.
* **HA:** scattered abort code without a unifying channel object risks divergent implementations.
* **CT:** pre-queued envelopes are simpler to test.
* **IR:** none.
* **LA:** delaying OperatorChannel leaves the abort ingress's data structure under-specified.

**RULING.** **DEFER OperatorChannel object to Step 11.** Step 9 introduces `OperatorEnvelope` (the data type) and the `pending_operator_envelopes` constructor parameter on `ExecutionSession`. The Phase-A drain logic is shipped in Step 9 and reused unchanged by Step 11. Step 11 adds only the live ingress (channel object); Step 9 owns the deterministic envelope schema.

**Rationale.** Phase 9 needs the abort code paths and the contract; it does not need live interactivity. Pre-queued envelopes give deterministic test coverage of every abort path Step 11 will exercise. The envelope schema, once frozen in Step 9, is the long-lived contract.

### §F.8 — `InfrastructureDegradationDetected` provenance

**Question.** Who emits it, where, when?

**Risk analysis.**
* **RD:** this class is fundamentally non-replayable (Kit/PhysX death). Honest acknowledgement required.
* **HA:** writing into `events.jsonl` post-session-death would require a separate authority that knows where the session was — severe.
* **CT:** contamination of `events.jsonl` would corrupt the L3 replay-identity surface.
* **IR:** any session-side "recovery" of infrastructure degradation IS the implicit-secondary-orchestration anti-pattern. Forbidden.
* **LA:** without a defined sidecar, post-mortem detection is unstandardized.

**RULING.** **SIDECAR ARTIFACT, OUTSIDE `events.jsonl`.** The launch harness writes `infrastructure_degradation.json` peer to `events.jsonl` and `manifest.json` in the SessionPackage directory. Schema:

```json
{
  "schema_version": 1,
  "detected_by": "launch_harness",
  "detected_at_wall_ns": <int>,
  "last_seen_seq": <int|null>,
  "exit_signal": <str|null>,
  "exit_code": <int|null>,
  "reason": "<short str>"
}
```

The session never emits an infrastructure-degradation event. The replay-identity comparator treats sidecar presence as a **REPLAY-INVALID** verdict (distinct from "divergent" — explicitly unreplayable).

**Rationale.** `detected_at_wall_ns` is the ONLY legitimate wall-clock use in the entire system, justified because the session's deterministic clock has stopped. The sidecar is forensic, not authoritative.

### §F.9 — Retry budget semantics

**Question.** Land retry in Step 9 or defer?

**Risk analysis.**
* **RD:** retries multiply replay-identity vectors (must replay the same retry sequence).
* **HA:** implicit retry is the canonical hidden-authority pattern. Severe.
* **CT:** retried executions may share residual state (e.g. partial gripper closure).
* **IR:** retry IS implicit recovery if not graph-explicit. Severe.
* **LA:** very high — "retry of what?", "retry under what conditions?", "shared state across attempts?".

**RULING.** **NO RETRY IN STEP 9.** Retry semantics are deferred to a future step with a dedicated contract. The Step 5 `retry_counts` parameter remains plumbed-but-unused as forward-compat surface. The only way to re-attempt work in Step 9 is an **explicit recovery node** declared in the graph topology.

**Rationale.** Retry is the single largest source of hidden orchestration in industrial systems. Including it in Step 9 would inflate scope and erode the architectural rule. Graph-explicit recovery is strictly stronger (every attempt is a visible node) and sufficient for current needs.

### §F.10 — Recovery-node graph encoding

**Question.** Metadata flag, node-type enum, or topology-derived?

**Risk analysis.**
* **RD:** topology-derived (inferring "recovery" from graph shape) is replay-stable but invisible without rendering.
* **HA:** topology-derived inference is hidden authority — the inference rule itself becomes part of the contract.
* **CT:** none.
* **IR:** topology-derived inference creates a "recovery happens automatically" appearance.
* **LA:** high without explicit declaration — operators cannot tell from the graph which nodes are recovery vs. ordinary.

**RULING.** **EXPLICIT METADATA FLAG.** `TaskNode.metadata` carries `"recovery_of": "<failed_node_id>"` for recovery nodes (None for ordinary nodes). The scheduler does NOT change behavior based on this flag — it is consumed only by the trace payload of `RecoveryNodeEntered`. Topology-derived inference is **FORBIDDEN**.

**Rationale.** Explicit metadata is operator-visible, replay-stable, and decoupled from scheduler logic. Topology-derived inference would require a contract clause defining the inference rule — an attack surface for divergence.

### §F.11 — `SessionAborted` vs `SessionFailed` distinction

**Question.** Distinct terminal states or shared state with `terminator_reason`?

**Risk analysis.**
* **RD:** both are deterministic if pinned; distinct states are byte-distinguishable in the terminal event type.
* **HA:** overloading FAILED with terminator_reason on a single state hides operator-initiated termination behind a string field.
* **CT:** none.
* **IR:** none.
* **LA:** the SessionState enum should reflect the orthogonal authority that terminated the session.

**RULING.** **DISTINCT TERMINAL STATES.** `SessionState.ABORTED` (terminated by operator envelope) ≠ `SessionState.FAILED` (terminated by validator/scheduler/authority-violation/timeout/continuity-validation). The terminal event types are `SessionAborted` (final event for ABORTED) and `SessionFailed` (final event for FAILED). Both states carry `terminator_reason` in their payload for diagnostic refinement (operator's `reason` string for ABORTED; the failure class enum for FAILED).

**Rationale.** Symmetric with §F.1: explicit states are byte-distinguishable in `events.jsonl`; comparator can verify "this run aborted exactly like that run" without inspecting payload strings. Mirrors D-CONT's authority-discipline posture: distinct authorities → distinct surfaces.

### §F.12 — Failure-trace replay-identity gate scope

**Question.** Extend the byte-identity gate to failure traces?

**Risk analysis.**
* **RD:** without the gate, failure paths are unverified for byte-identity — a divergence channel.
* **HA:** none.
* **CT:** none.
* **IR:** none.
* **LA:** the gate's pass/fail definition for failure traces must be pinned.

**RULING.** **EXTEND THE GATE.** Step 9 Phase 6 (replay-identity gate extension) MUST assert byte-identity across 3+ runs that terminate in the same `SessionState` (FAILED or ABORTED) at the same `seq` with the same `terminator_reason`. The comparator's existing `events.jsonl` + `manifest.json` byte-equality check is extended to cover failure terminations identically to happy-path terminations.

**Rationale.** Step 8's Phase 6 proves byte-identity for happy-path; Step 9 closes the symmetric gap for failure-path. Without this, failure traces would be a privileged-divergent class — a tolerance the architectural rule forbids.

### §F.13 — Authority-violation severity tiers

**Question.** Are warnings permitted?

**Risk analysis.**
* **RD:** severity tiers create branch points where soft-warnings could lead to silent continuation.
* **HA:** WARNINGS are a textbook implicit-secondary-orchestration vector ("we noticed but kept going").
* **CT:** none.
* **IR:** WARNINGS could trigger silent recovery. Severe.
* **LA:** "warning" is undefined — does the session continue, branch, or just log?

**RULING.** **NO WARNINGS.** Authority violation is a single severity. `AUTHORITY_VIOLATION` (D-CONT-5, D-SESS-1, etc.) **MUST** terminate the session via `SessionState.FAILED` with `terminator_reason=AUTHORITY_VIOLATION`. Sub-severity is **FORBIDDEN**. The diagnostic payload carries the violated clause ID, but the session state is terminal.

**Rationale.** Confirms §A.4. The architectural rule forbids any class of failure that does not terminate or escalate explicitly. Warnings are the canonical "implicit secondary orchestration" anti-pattern in disguise.

---

### §F-summary table — resolved postures

| # | resolution |
|---|---|
| F.1 | SessionState += {ABORTING, ABORTED}. RECOVERING FORBIDDEN as a session state. |
| F.2 | Envelope-as-event only. Method-as-ingress FORBIDDEN. Pre-queued via constructor for Step 9. |
| F.3 | Sibling-tolerant default. Strict requires `FailureAction.ABORT_COHORT` per-edge. |
| F.4 | C2-b last-tick truth. Contradiction with occupancy preserved verbatim. |
| F.5 | Emit once per blocking-episode. Emission key cleared on un-block. |
| F.6 | Per-`world.step()` count only. Sub-phase enforcement FORBIDDEN. Phase E remains atomic. |
| F.7 | Defer OperatorChannel object to Step 11. Envelope schema + pre-queue land in Step 9. |
| F.8 | Sidecar `infrastructure_degradation.json` outside `events.jsonl`. Replay verdict REPLAY-INVALID. |
| F.9 | NO retry in Step 9. Re-attempt only via explicit recovery node. |
| F.10 | Explicit `recovery_of` metadata flag. Topology-derived inference FORBIDDEN. |
| F.11 | Distinct terminal states: `ABORTED` ≠ `FAILED`. |
| F.12 | Extend replay-identity gate to failure terminations. Byte-identity REQUIRED. |
| F.13 | No warnings. Authority violation is always terminal. |

---

---

## §G. Ready-for-Integration D-FAULT-* contract clauses

**Posture.** This section contains the **formal, normative D-FAULT-* clauses ready to be moved into §13 of [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md)** in Step 9 Phase 3. The wording matches the §12 D-CONT-* format conventions — bolded clause openings, MUST / MUST NOT / FORBIDDEN / REQUIRED / REPLAY-INVALID, italicized `*Rationale.*` lines. Analysis prose (§A–§F) is not part of the contract; only the clauses below are normative.

Until Phase 3 integration, no production code MAY cite these clause IDs. The numbering is final; the integration is pending.

### §13.0 Scope

This section binds **Step 9 onward** — the first runtime moment at which the deterministic-execution contract acknowledges failure as a first-class participant in orchestration. Up to Step 8, the contract enforced what authority survives a successful boundary handoff. From Step 9 forward, the contract enforces what authority survives an **unsuccessful** transition: failed verdicts, aborted execution, exceeded budgets, broken invariants, and replay-integrity refusals.

Step 9 does not introduce a second orchestration system. It extends the existing single orchestration authority (D-SESS-1) to acknowledge failure deterministically. Every failure is an explicit transition. Every transition is append-only. Every transition is replay-authoritative.

Subsequent implementation steps (10 replay-identity tooling extension, 11 operator channel ingress, 12 conveyor refactor, and any future Phase 4C revision) MUST cite this section for every failure-path assumption they make.

### §13.1 D-FAULT-1 — Orchestration-level failure taxonomy

**D-FAULT-1** — Failure at the orchestration level is **strictly enumerated** as exactly one of the following eight classes:

| class | origin authority | emitted via |
|---|---|---|
| `NODE_EXECUTION_FAILURE` | `UnifiedValidator` inside `TaskExecutor.execute()` | `NodeExecutionCompleted` with `passed=False` and inner `TaskOutcome` |
| `PRECONDITION_FAILURE` | scheduler (D-SCHED-13) | `NodeBlocked` with `status="blocked_by_precondition"` or `"blocked_by_predicate_error"` |
| `AUTHORITY_VIOLATION` | `ExecutionSession` postcondition check at Phase G | `AuthorityViolationDetected` |
| `CONTINUITY_VALIDATION_FAILURE` | `ExecutionSession` boundary-snapshot postcondition at Phase G | `ContinuityValidationFailed` |
| `TIMEOUT_FAILURE` | `ExecutionSession` post-Phase-E tick-budget check (D-FAULT-12) | `NodeTimeoutTripped` |
| `OPERATOR_ABORT` | `OperatorAbortRequested` envelope drained at Phase A | `SessionAborting` / `SessionAborted` |
| `INFRASTRUCTURE_DEGRADATION` | out-of-band detector (launch harness) | sidecar artifact (D-FAULT-13); **NOT** in `events.jsonl` |
| `REPLAY_INTEGRITY_FAILURE` | replay-identity comparator tool | comparator exit code + replay audit artifact (D-FAULT-11); **NOT** in any session's `events.jsonl` |

Expansion of this list is a contract revision, not an implementation detail. A failure mode not in this list is, by D-FAULT-1, not a recognized failure mode.

#### §13.1.1 D-FAULT-1a — Inner sub-classification

**D-FAULT-1a** — The `NODE_EXECUTION_FAILURE` class is sub-classified by `TaskOutcome` (Phase 4A enum, currently 8 non-PASS values). Sub-classification of any other orchestration-level class via `TaskOutcome` is **FORBIDDEN**; `TaskOutcome` is a per-task validator verdict and its mutation authority remains with Phase 4A's `UnifiedValidator`.

*Rationale.* Two-tier taxonomy preserves the Mutation Authority Matrix: orchestration-level classes are session-owned; per-task sub-classification is validator-owned. Conflating the two would breach D-SESS-1.

### §13.2 D-FAULT-2 — Origin authority and emission discipline

**D-FAULT-2** — Each failure class has exactly **one** origin authority (per D-FAULT-1 table). The same class **MUST NOT** be emitted by any authority not listed for it. A would-be second emitter is a contract violation per D-CONT-7a.

*Rationale.* Single-emitter discipline is the failure-path analogue of D-CONT-5's single-mutator discipline. Multiple emitters of the same class allow drift across paths.

### §13.3 D-FAULT-3 — Propagation rules

**D-FAULT-3** — A failure-class emission propagates per the following table:

| emitted class | downstream effect |
|---|---|
| `NODE_EXECUTION_FAILURE` | failed node added to `_failed`; descendants per `FailureAction` (D-FAULT-3a) |
| `PRECONDITION_FAILURE` | node remains pending; no state mutation; descendants stay `blocked_by_parents` |
| `AUTHORITY_VIOLATION` | session → `FAILED` immediately; remaining pending nodes cascade-skipped uniformly; **FailureAction is overridden** |
| `CONTINUITY_VALIDATION_FAILURE` | session → `FAILED` immediately; same as `AUTHORITY_VIOLATION` |
| `TIMEOUT_FAILURE` | failed node added to `_failed`; descendants per `FailureAction` (D-FAULT-3a) |
| `OPERATOR_ABORT` | session → `ABORTING` → `ABORTED`; remaining pending nodes cascade-skipped uniformly; **FailureAction is overridden** |
| `INFRASTRUCTURE_DEGRADATION` | session presumed dead; no further propagation possible in-session |
| `REPLAY_INTEGRITY_FAILURE` | n/a in-session; comparator exits non-zero |

#### §13.3.1 D-FAULT-3a — `FailureAction` enumeration

**D-FAULT-3a** — `FailureAction` is a per-edge enumeration on `TaskGraph`, immutable after `graph.build()`. Permitted values:

| value | meaning |
|---|---|
| `SKIP_NODE` (default) | descendants of failed node cascade-skipped; siblings unaffected |
| `ABORT_COHORT` | descendants AND all fan-out siblings of the failure point cascade-skipped |
| `ABORT_JOB` | session → `FAILED`; all remaining pending nodes cascade-skipped uniformly |

Sibling-tolerant default (D-FAULT-3a `SKIP_NODE`). Sibling-strict requires explicit `ABORT_COHORT` declaration per-edge. Live mutation of `FailureAction` after `graph.build()` is **FORBIDDEN** (D-SCHED-8 frozen-graph invariant).

### §13.4 D-FAULT-4 — `TaskCascadeSkipped` distinct from `NodeFailed`

**D-FAULT-4** — A node whose pending state is resolved by **cascade** (descendant of a `failed` node, or skipped under `ABORT_COHORT` / `ABORT_JOB`) **MUST** be recorded via a distinct `TaskCascadeSkipped` event, **never** via `NodeFailed`. The `_skipped` set is distinct from the `_failed` set in `SessionRuntimeSnapshot`.

*Rationale.* An operator inspecting the trace must distinguish nodes that genuinely failed (their executor ran and produced a non-PASS verdict) from nodes that were skipped (their executor never ran). Conflating them obscures forensic provenance.

#### §13.4.1 D-FAULT-4a — `_skipped` enters authoritative continuity

**D-FAULT-4a** — The `_skipped: frozenset[str]` set is added to the authoritative continuity enumeration defined by D-CONT-1. The boundary snapshot schema is extended (D-CONT-6) to include `_skipped` alongside `_completed`, `_failed`, `_retry_counts`. `BOUNDARY_SNAPSHOT_SCHEMA_VERSION` increments from 1 to 2 at Step 9 Phase 4 landing. Mismatched-version replays are refused per D-CONT-6b.

*Rationale.* `_skipped` participates in continuity (recovery preconditions consult it). It is therefore authoritative per D-CONT-1's definition and MUST appear in the boundary snapshot.

### §13.5 D-FAULT-5 — Retained-state mutation on failure

**D-FAULT-5** — Retained-state mutation on failure is **FORBIDDEN** except as explicitly enumerated by D-CONT-5 (occupancy mutation on PASS). Specifically:

* implicit rollback of canonical object pose: **FORBIDDEN**;
* implicit clearing of fixture occupancy on failed pick: **FORBIDDEN**;
* implicit release of D-LIFE `attached` state on failed transport: **FORBIDDEN**;
* implicit reset of any `NodeRuntimeState` field outside the session's documented transition table: **FORBIDDEN**.

The post-failure boundary snapshot **MUST** reflect the last-tick truth of all authoritative fields. Recovery topology resolves contradictions explicitly.

```python
# FORBIDDEN — implicit rollback to "clean" the snapshot.
if task_result.outcome != TaskOutcome.PASS:
    registry.update_object_pose(peg, pre_failure_pose)   # LIE
    registry.mark_fixture_empty(fixture_a)                # WRONG AUTHORITY
```

```python
# REQUIRED — failure preserves last-tick truth.
if task_result.outcome != TaskOutcome.PASS:
    # No mutation. The session records `_failed.add(node_id)` and emits
    # NodeExecutionCompleted with passed=False. Post-G snapshot serializes
    # the actual canonical pose, the actual fixture occupancy.
    pass
```

#### §13.5.1 D-FAULT-5a — Pose-on-FAIL semantic

**D-FAULT-5a** — The canonical object pose at the post-failure boundary is the **last-tick `update_object_pose` write** the failing node made (D-CONT-1 definition, unchanged). Frozen-pre-failure semantics (snapshot lies about reality) are **FORBIDDEN**. Dual-snapshot semantics (two truths in one snapshot) are **FORBIDDEN**.

#### §13.5.2 D-FAULT-5b — Fixture occupancy on FAIL

**D-FAULT-5b** — Fixture occupancy is **NOT** mutated on failure (D-CONT-5 already requires PASS for mutation). A failed pick from an occupied fixture leaves occupancy unchanged; a failed place at an empty fixture leaves occupancy unchanged. The resulting contradiction between occupancy and canonical pose is **REQUIRED** to be preserved verbatim in the post-failure boundary snapshot.

*Rationale.* Contradictions are forensic truth. The architectural rule forbids silent healing. Recovery nodes (declared in graph topology) resolve contradictions explicitly via subsequent transitions.

### §13.6 D-FAULT-6 — Abort/cancellation boundary phase

**D-FAULT-6** — Operator abort enters orchestration **only at Phase A** of an orchestration tick. The `OperatorAbortRequested` envelope is drained at Phase A; if accepted, the session transitions `RUNNING` → `ABORTING` before any Phase B scheduling. Abort ingress at any other phase is **FORBIDDEN**.

Specifically:

* mid-Phase-E (mid-`execute()`) interrupt is **FORBIDDEN**;
* between-`world.step()` interrupt inside Phase E is **FORBIDDEN**;
* method-as-ingress (e.g. `ExecutionSession.request_abort()`) is **FORBIDDEN**;
* multiple ingress paths for the same abort are **FORBIDDEN**.

#### §13.6.1 D-FAULT-6a — Phase E atomicity

**D-FAULT-6a** — Phase E is **atomic** from the orchestration perspective. The executor runs its declared trajectory to completion (or to executor-internal exception). The session does not interrupt mid-step on budget exhaustion, abort request, or any other condition. Mid-step interrupt would break D-EXEC-2 (no event out of phase) and D-CONT-3 (boundary quiescence).

### §13.7 D-FAULT-7 — Idempotent cancellation

**D-FAULT-7** — Cancellation is idempotent at the **transition**, not the envelope:

* a node cascade-skipped twice (e.g. two failed parents) **MUST** emit exactly one `TaskCascadeSkipped` event;
* an `OperatorAbortRequested` envelope arriving while the session is already in `ABORTING` or `ABORTED` **MUST** be recorded in the trace (as an envelope ingress event) but **MUST NOT** trigger a second state transition;
* a `NodeBlocked` event for a given node fires at most once per blocking-episode, where an episode begins when the node transitions to blocked and ends when it un-blocks (parent completes, predicate succeeds) or transitions to terminal.

The session **MUST** maintain per-node idempotency tracking in `NodeRuntimeState`:

* `_cascade_emitted: bool` (set on `TaskCascadeSkipped` emission);
* `_blocked_emission_key: str | None` (set on `NodeBlocked` emission; cleared on un-block).

These fields are authoritative (D-FAULT-4a extends D-CONT-1).

### §13.8 D-FAULT-8 — Recovery as explicit graph topology

**D-FAULT-8** — Recovery from any failure class is **exclusively** expressed as graph topology: a `TaskNode` whose `metadata["recovery_of"] == "<failed_node_id>"`, reachable via a graph edge from the failure point. Implicit recovery — any runtime code path that re-attempts work without an explicit graph node — is **FORBIDDEN**.

A recovery node:

* is a normal `TaskNode` from the scheduler's perspective (D-SCHED-2/-3 canonical-order applies);
* carries `metadata["recovery_of"]: str | None` (None for non-recovery nodes);
* on entry, emits a `RecoveryNodeEntered` event whose payload includes `recovers_from_node_id` and `recovers_from_outcome` (extracted from the failed node's `TaskResult`).

#### §13.8.1 D-FAULT-8a — Topology-derived recovery inference forbidden

**D-FAULT-8a** — Inferring "recovery node" status from graph topology alone (e.g. "any node downstream of a failure-edge is a recovery node") is **FORBIDDEN**. The `metadata["recovery_of"]` field is the **only** authoritative source. Topology-derived inference is a hidden authority.

#### §13.8.2 D-FAULT-8b — No retry in Step 9

**D-FAULT-8b** — Retry of the same `TaskNode` (re-execution of the same `task_ref` with the same node_id) is **FORBIDDEN** in Step 9. The `retry_counts` parameter on `TopologicalSequentialScheduler.next_runnable_node(...)` remains plumbed-but-unused (Step 5 D-SCHED-§5 forward-compat). Re-attempt is expressed via a distinct recovery node (different `node_id`).

*Rationale.* Retry semantics are the largest source of implicit orchestration in industrial systems. Step 9 prefers graph-explicit recovery; retry returns under a dedicated future contract.

### §13.9 D-FAULT-9 — Operator envelope schema

**D-FAULT-9** — Operator commands enter orchestration via `OperatorEnvelope`, a frozen dataclass with the following schema (canonical-JSON serializable, stable across versions):

```python
@dataclass(frozen=True, slots=True)
class OperatorEnvelope:
    kind:               str          # "abort" (Step 9); Step 11 adds "pause"|"resume"|"manual_advance"
    requested_at_tick:  int          # earliest orchestration_tick at which Phase A drains this envelope
    reason:             str          # short, operator-supplied; participates in fingerprint
    envelope_id:        str          # deterministic UUID-equivalent (e.g. blake2b digest of (kind, tick, reason, sequence_within_pending))
```

Envelopes are passed to `ExecutionSession.__init__` via `pending_operator_envelopes: tuple[OperatorEnvelope, ...]`. The tuple is sorted by `(requested_at_tick, envelope_id)` for canonical ordering. Live-channel ingress (Step 11) **MUST** preserve this schema and the canonical-ordering discipline.

#### §13.9.1 D-FAULT-9a — Step 9 supports only `kind="abort"`

**D-FAULT-9a** — In Step 9, the only permitted `OperatorEnvelope.kind` value is `"abort"`. Other kinds (`pause`, `resume`, `manual_advance`) are reserved for Step 11; an envelope with an unrecognized kind **MUST** be rejected at session construction with `ExecutionSessionError`.

### §13.10 D-FAULT-10 — Failure-event canonical-JSON fingerprinting

**D-FAULT-10** — Every failure-related event (`NodeExecutionCompleted` with `passed=False`, `NodeBlocked`, `TaskCascadeSkipped`, `NodeTimeoutTripped`, `AuthorityViolationDetected`, `ContinuityValidationFailed`, `OperatorAbortRequested`, `SessionAborting`, `SessionAborted`, `SessionFailed`, `RecoveryNodeEntered`) **MUST** be canonical-JSON serialized via `canonical_dumps` (D-TRACE-8). Float fields in failure payloads (e.g. evidence in `TaskOutcome` sub-classification) **MUST** originate from a deterministic PhysX read or deterministic arithmetic on PhysX reads; computed intermediates that introduce float-repr instability are **FORBIDDEN**.

### §13.11 D-FAULT-11 — Replay-integrity failure handling

**D-FAULT-11** — `REPLAY_INTEGRITY_FAILURE` is a **meta-failure** detected by the replay-identity comparator tool (`tools/check_session_replay_identity.py`). It is **NOT** an in-session event:

* it **MUST NOT** be appended to any session's `events.jsonl`;
* it is recorded only via the comparator's exit code (non-zero) and an audit artifact at a comparator-defined location (e.g. `replay_audit/<timestamp>_<pkg_a>_vs_<pkg_b>.json`);
* a session that subsequently fails replay does NOT become retroactively `FAILED` — its own `events.jsonl` remains unchanged.

#### §13.11.1 D-FAULT-11a — Replay-tolerance creep forbidden

**D-FAULT-11a** — The comparator **MUST** apply strict byte-equality (no numerical tolerance, no field-level fuzziness, no "approximately equal" replay). A future PR introducing replay tolerance is rejected at review under this clause and D-REPLAY-1.

### §13.12 D-FAULT-12 — Tick-budget enforcement

**D-FAULT-12** — Task-level timeout is enforced as a **tick budget**, never as wall-clock time:

* every `TaskDefinition` declares `tick_budget_ticks: int`;
* the executor reports `ticks_consumed: int` in `TaskResult`;
* the session evaluates `ticks_consumed > tick_budget_ticks` post-Phase-E and, if true, sets `TIMEOUT_FAILURE`;
* the budget enforcement happens at the per-`world.step()` count granularity, post-execution, not at sub-phase granularity.

Wall-clock based timeout is **FORBIDDEN**. Watchdog threads are **FORBIDDEN**. Asynchronous timeout mutation is **FORBIDDEN**.

#### §13.12.1 D-FAULT-12a — Phase E atomicity preserved on timeout

**D-FAULT-12a** — Timeout detection is post-Phase-E. The executor runs to trajectory completion before the budget check. Mid-Phase-E budget interrupt is **FORBIDDEN** (D-FAULT-6a).

#### §13.12.2 D-FAULT-12b — Margin requirement

**D-FAULT-12b** — Trajectory authoring **MUST** produce `tick_budget_ticks` values with a documented margin over the trajectory's declared tick length. A pure-Python test (Phase 3 of Step 9) asserts `tick_budget_ticks >= trajectory_length_ticks + MARGIN_TICKS` for every registered task. Tight budgets that exceed-by-one in one run and finish-by-one in another are a divergence vector (§E.13).

### §13.13 D-FAULT-13 — Infrastructure-degradation provenance

**D-FAULT-13** — `INFRASTRUCTURE_DEGRADATION` is detected out-of-band (Kit subprocess exit, PhysX exception, simulation_app death). The session **MUST NOT** emit an infrastructure-degradation event (the session is dead by hypothesis). The launch harness **MUST** write a sidecar artifact at `<session_package>/infrastructure_degradation.json` with the schema:

```json
{
  "schema_version": 1,
  "detected_by": "launch_harness",
  "detected_at_wall_ns": <int>,
  "last_seen_seq": <int|null>,
  "exit_signal": <str|null>,
  "exit_code": <int|null>,
  "reason": "<short str>"
}
```

`detected_at_wall_ns` is the **only** legitimate wall-clock use in the entire system (the deterministic clock has stopped). The replay-identity comparator **MUST** treat sidecar presence as **REPLAY-INVALID** (a distinct verdict from "divergent" — explicitly unreplayable).

### §13.14 D-FAULT-14 — No implicit secondary orchestration system

**D-FAULT-14** — Failure handling **MUST NOT** become an implicit secondary orchestration system. Specifically:

* every failure transition is one append to `events.jsonl`;
* every state mutation on failure is justified by exactly one D-FAULT clause;
* recovery is graph topology, never runtime behaviour (D-FAULT-8);
* abort is envelope-driven, never method-driven (D-FAULT-9);
* timeout is tick-budgeted, never wall-clock (D-FAULT-12);
* infrastructure degradation is sidecar, never session-emitted (D-FAULT-13).

A code path that "cleans up" on failure without an emitted event is a contract violation under this clause.

### §13.15 D-FAULT-15 — Forbidden anti-patterns (failure-path scope)

**D-FAULT-15** — In addition to D-FORBID-1..-14, the following patterns are **FORBIDDEN** in any code that participates in failure handling:

| # | forbidden pattern | cites |
|---|---|---|
| 1 | implicit rollback of retained state on failure | D-FAULT-5 |
| 2 | implicit retry without an explicit recovery node | D-FAULT-8, D-FAULT-8b |
| 3 | "transient failure" or "soft failure" suppression | D-FAULT-13 (no warnings) |
| 4 | "approximately equal" replay tolerance for failure traces | D-FAULT-11a |
| 5 | mid-Phase-E interrupt (abort, timeout, anything) | D-FAULT-6, D-FAULT-6a |
| 6 | operator intervention bypassing the OperatorEnvelope schema | D-FAULT-9 |
| 7 | failure-driven cleanup of D-LIFE state outside Phase G | D-FAULT-5, D-CONT-5a |
| 8 | "recovery completed silently" without a `RecoveryNodeEntered` event | D-FAULT-8 |
| 9 | cascade-skip emission iterating an unordered set | D-FAULT-4, D-SCHED-3 |
| 10 | wall-clock timeout budget (per-tick or per-step) | D-FAULT-12 |
| 11 | failure trace mutation of a prior event | D-TRACE-2 (Step 9 explicitly cites) |
| 12 | cross-session retained-state continuity for recovery | D-FORBID, D-FAULT-8 |
| 13 | live-mutating `FailureAction` after `graph.build()` | D-FAULT-3a, D-SCHED-8 |
| 14 | severity tiers ("warning", "minor failure", etc.) | D-FAULT-13 (Phase 2 ruling) |
| 15 | topology-derived recovery inference | D-FAULT-8a |
| 16 | `ExecutionSession.request_abort()` or any method-as-ingress | D-FAULT-6, D-FAULT-9 |
| 17 | inserting infrastructure-degradation events into `events.jsonl` | D-FAULT-13 |
| 18 | `RECOVERING` as a `SessionState` value | D-FAULT (Phase 2 F.1 ruling) |

---

### §G-supplementary — clause-to-question traceback

For audit: every D-FAULT-* clause traces to one or more resolved §F questions. Reviewers verifying the contract freeze should walk this table to confirm no resolution is unrepresented.

| D-FAULT clause | resolves §F question(s) |
|---|---|
| D-FAULT-1, -1a | §A two-tier taxonomy |
| D-FAULT-2 | §A origin authority |
| D-FAULT-3, -3a | §F.3 sibling cancellation; §B.4 escalation tiers |
| D-FAULT-4, -4a | §D.2 TaskCascadeSkipped; D-CONT-1 amendment |
| D-FAULT-5, -5a, -5b | §F.4 pose semantic; §C retained-state posture |
| D-FAULT-6, -6a | §B.1 abort entry phase; §F.2 ingress |
| D-FAULT-7 | §F.5 NodeBlocked emission; §B.5 idempotency |
| D-FAULT-8, -8a, -8b | §F.9 retry; §F.10 recovery-node encoding |
| D-FAULT-9, -9a | §F.7 OperatorChannel earliness; §F.2 ingress |
| D-FAULT-10 | §D failure trace; §E.7 fingerprint stability |
| D-FAULT-11, -11a | §F.12 replay-identity gate; §E.10 tolerance creep |
| D-FAULT-12, -12a, -12b | §F.6 budget granularity; §E.1 timeout ordering; §E.13 under-the-line |
| D-FAULT-13 | §F.8 infrastructure provenance |
| D-FAULT-14 | the architectural rule itself |
| D-FAULT-15 | §F.13 no warnings; all forbidden patterns |

`SessionState` extension {`ABORTING`, `ABORTED`}: covered by §F.1 ruling and consumed by D-FAULT-3 (propagation), D-FAULT-6 (abort transition), D-FAULT-9 (envelope ingress). Not a standalone clause; it is implied by D-FAULT-3 + D-FAULT-6 + D-FAULT-15 #18 (RECOVERING forbidden).

`_skipped` extension to D-CONT-1: covered by D-FAULT-4a, which explicitly amends D-CONT-1 and bumps `BOUNDARY_SNAPSHOT_SCHEMA_VERSION` to 2.

---

## §H. Sequencing discipline  *(task 6)*

Step 9 follows Step 8's six-phase discipline. Each phase is a single commit, each preserves the 32/32 Phase 4A Isaac-Sim regression, each cites D-* clauses.

| phase | scope | gate |
|---|---|---|
| 1 | **Analysis convergence** (this document → final). Address all §F open questions. Architecture review with operator. | analysis-doc reviewed and accepted; no implementation. |
| 2 | **Contract freeze**. Author §13 D-FAULT-* in `phase_4b_deterministic_semantics.md`. Extend Mutation Authority Matrix in `session.py` docstring. No production code changes (matrix doc + contract doc only). | contract section reviewed; D-FAULT-* clauses pinned. |
| 3 | **Pure-Python contract tests**. Add unit tests for: taxonomy enumeration, idempotent cascade, abort-at-Phase-A, no-mid-tick-interrupt, no-implicit-rollback, tick-budget tick-counting, authority-violation detection, NodeBlocked/TaskCascadeSkipped event payload determinism. No Isaac dependency. | tests pass; no production code changes (test scaffolding plus invariant test discovery). |
| 4 | **Runtime wiring**. Add session-level abort path, cascade-emission, tick-budget enforcement, new event types, NodeRuntimeState extension. NodeRuntimeState extension MUST cite migration plan for D-CONT-6 schema-version bump if boundary snapshot changes. | Step 3 tests pass; unit-test suite grows; pure-Python at this point. |
| 5 | **Isaac Sim regression**. Re-run 32/32 Phase 4A regression. Run a deliberately-failing 2-node graph end-to-end on Isaac Sim. Verify failure-event payloads byte-identical across 3 cycles. | 32/32 PASS; 3-cycle failure-trace byte-identity. |
| 6 | **Replay-identity gate extension**. Extend `tools/check_session_replay_identity.py` to assert byte-identity across multiple sessions that terminate in `FAILED` with the same failure class at the same seq. | comparator passes failure-class-equality across 3-cycle failure run. |
| 7 | **Operator MP4 review**. Operator records and reviews the failing 2-node graph + the recovery topology (if recovery nodes are introduced in Phase 4). Verifies visual continuity of failure (no teleport-on-fail, no implicit healing). | operator visual continuity closure for failure paths. |

**Phase 1 is this document.** Phases 2-7 do not begin until §F is resolved and the operator signs off on the converged analysis.

---

## §I. Active hard constraints (mirrored from Step 8 closure)

Step 9 MUST NOT introduce:

* async orchestration
* speculative execution
* adaptive planning
* distributed execution
* generalized mutable replay repair
* replay tolerance semantics
* hidden orchestration authority
* hidden cleanup semantics
* implicit retries
* opportunistic continuation
* adaptive recovery
* silent replay repair
* runtime state healing
* nondeterministic cancellation behaviour

All failure handling remains:

* explicitly modelled
* append-only traceable
* replay-authoritative
* mechanically deterministic

These constraints govern §13 D-FAULT-* drafting and every implementation phase after.

---

## §J. Document lifecycle

This is a **draft analysis document**, not yet the contract. Its life:

1. ✅ **Phase 1 (2026-05-20).** Draft analysis authored (§A–§J initial).
2. ✅ **Phase 2 (2026-05-20).** All 13 §F open questions resolved with 5-lens risk analysis; §G replaced from un-numbered skeleton to formal Ready-for-Integration D-FAULT-* clauses (D-FAULT-1 through D-FAULT-15 plus corollaries -1a, -3a, -4a, -5a, -5b, -6a, -8a, -8b, -9a, -11a, -12a, -12b).
3. ✅ **Phase 3 (2026-05-20).** D-FAULT-* family integrated into [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md) as canonical §13 (sections 13.0 through 13.16 inclusive, all clauses normative-wording-only). §11 item 4 marked resolved. D-CONT-1 amended to include `_skipped` and the per-node idempotency fields; D-CONT-6 snapshot template and "Allowed content" list extended; `BOUNDARY_SNAPSHOT_SCHEMA_VERSION` 1 → 2 declared (runtime wiring lands Phase 5). §12.10 "no retry semantics" updated to reflect D-FAULT-8b deferral. Mutation Authority Matrix in [`session.py`](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py) module docstring extended with Step 9 D-FAULT authorities (abort-drain, envelope ingress, retained-state-during-FAIL, contradiction persistence, cascade-emit, tick-budget-check, authority-violation detection, continuity-validation detection) and two new OUT-OF-SESSION authorities (launch harness for D-FAULT-13 sidecar; replay-identity comparator for D-FAULT-11 meta-failure). Zero production code lines mutated. session.py parses clean.
4. ⏳ **Phase 4 (next).** Pure-Python contract tests (no Isaac dep). Cover: taxonomy enumeration; sibling-tolerant cascade; abort-at-Phase-A; no-mid-tick-interrupt; no-implicit-rollback; tick-budget tick-counting + margin assertion; authority-violation detection; `NodeBlocked` / `TaskCascadeSkipped` payload determinism; envelope schema rejection of unknown kinds; idempotent cancellation transitions.
5. ⏳ Phase 5: runtime wiring (`_skipped` set materialization, `NodeRuntimeState` field additions, abort drain, cascade emission, post-Phase-E tick-budget check, schema_version bump).
6. ⏳ Phase 6: Isaac Sim regression — 32/32 Phase 4A + deliberately-failing 2-node graph end-to-end.
7. ⏳ Phase 7: replay-identity gate extension to failure terminations.
8. ⏳ Phase 8: operator MP4 review of failing + recovery topology.

**This file is now historical.** The normative content lives in §13 of the canonical contract doc. The §A–§F analysis, §E risk register, §F resolutions, and §G clause-to-question traceback remain here as provenance — they are NOT contract-binding, but they document how each clause was derived. Future Step 9 PRs cite D-FAULT clause IDs from the canonical contract doc, never this analysis file.
