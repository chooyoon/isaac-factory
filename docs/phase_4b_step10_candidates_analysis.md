# Phase 4B Step 10 — Candidate Architecture Analysis

**Status:** DRAFT — analysis only. No production code change in this phase.

**Predecessor:** Phase 4B Step 9 architecturally closed 2026-05-20 ([Step 9 closure summary](../.claude/projects/-home-cap2-last/memory/project_phase_4b_step9.md); D-FAULT contract integrated as §13 of [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md)).

**Project posture as of Step 9 closure:**

* Step 8 — deterministic continuity orchestration substrate.
* Step 9 — deterministic failure orchestration substrate with replay-authoritative failure traces.
* Validated on real Isaac Sim 5.0 / Kit Python 3.11.13 / RTX 5090; byte-identical replay across happy-path AND failure-terminal sessions; MP4 recording proven replay-non-contaminating.

The next move is architectural re-scoping. This document maps six candidate Step 10 directions, applies a uniform five-lens risk analysis, classifies each by architectural layer, takes a deep dive on the most-likely candidate (executor evolution), and produces a recommendation ordering.

---

## §A. Substrate invariants (stabilized; NOT negotiable)

Step 10 candidates **MUST** compose with the following stabilized invariants. None of these may be relaxed by any Step 10 direction:

| invariant | citation | what it means for Step 10 |
|---|---|---|
| replay-authoritative truth | D-REPLAY-1, D-CONT-1, D-FAULT-1..-15 | every observable artifact reconstructable from canonical inputs |
| append-only traces | D-TRACE-2 | no mutation of prior events; finalize is one-way |
| deterministic failure ontology | D-FAULT-1, D-FAULT-2 | 8 failure classes, one origin authority each; no new failure modes without contract revision |
| contradiction preservation on FAIL | D-FAULT-5, D-FAULT-5a, D-FAULT-5b | no implicit rollback; pose-on-FAIL is last-tick truth |
| Phase-A-only abort ingress | D-FAULT-6 | no mid-tick interrupt; envelope-as-event only |
| atomic Phase E | D-FAULT-6a, D-FAULT-12a | executor runs to declared trajectory completion; no in-Phase-E orchestration mutation |
| no hidden cleanup | D-FAULT-5, D-FAULT-15 #7 | failure does NOT trigger D-LIFE transitions outside Phase G |
| no replay-healing | D-FAULT-11a | strict byte-equality; no tolerance, no normalization |
| no adaptive recovery | D-FAULT-8, D-FAULT-15 #2 | recovery is graph topology, not runtime behaviour |
| no wall-clock authority | D-FAULT-12, D-SCHED-11, D-FORBID | tick budgets only; the only legitimate wall-clock use in the system is the D-FAULT-13 infrastructure-degradation sidecar `detected_at_wall_ns` |

A Step 10 direction that requires weakening any of these is a contract revision — not a Step 10 candidate.

---

## §B. Step 10 candidate map

Six candidate directions, named A–F as in the brief:

### B.A — Deterministic executor interruption surfaces

**Goal**: unlock the Step 9 Phase 8 deferred scenarios C–F (operator-abort after acquire, cascade-skip on real failure, tick-budget timeout on Isaac, contradiction-preserving mid-execute interruption).

**Scope hints**:

* Phase 4A `TaskExecutor.execute()` evolves from one atomic call to a sequence of *checkpointed atomic segments*. Each segment is bounded by a deterministic interruption window — between `world.step()` calls, at trajectory-waypoint boundaries.
* `TaskResult.ticks_consumed` populated by the executor (already exists as a field per Step 9 Phase 5; the executor wiring is missing).
* Per-tick verdict-callback or post-segment `interrupt_requested` poll — the session can request abort at segment boundaries (NOT mid-step).
* `ResetScope.ACQUIRED_ONLY` continues to apply between nodes; new `ResetScope.MID_SEGMENT_INTERRUPT` may be needed for the case where execution was interrupted mid-trajectory.

**What it delivers**: real failure injection scenarios on Isaac Sim. Closes the Phase 4A executor-adapter capability gap that Step 9 documented as non-blocking but real.

**Critical constraint**: must preserve **atomic Phase E from the orchestration perspective**. The executor exposes interruption *internally* (sub-trajectory segments), but the session sees one `execute()` call. D-FAULT-6a remains intact.

### B.B — Recovery-topology orchestration

**Goal**: materialize the D-FAULT-8 recovery-node semantics. Contract already exists (`metadata["recovery_of"]`, `RecoveryNodeEntered` event); the runtime side is scaffolded but not exercised.

**Scope hints**:

* Graph-level validation: a node with `metadata["recovery_of"] = X` SHALL have a reachable edge from X (or a descendant of X) — otherwise the recovery node is unreachable and the validation should catch it at `graph.build()`.
* Scheduler awareness: when X fails, the scheduler should prefer the recovery node over downstream-of-X non-recovery nodes (but per Step 9 we said the scheduler does NOT change behavior based on this flag — only the trace emits `RecoveryNodeEntered`). This needs revisiting.
* Recovery lineage tracing: `RecoveryNodeEntered` payload carries `recovers_from_node_id` + `recovers_from_outcome` — sufficient for forensic provenance.
* Contradiction resolution: a recovery node EXPLICITLY resolves the post-FAIL contradiction (occupancy ≠ canonical pose). Its preconditions read the contradictory state; its execution restores invariants.

**What it delivers**: explicit graph-topology recovery. No new runtime authority introduced — recovery is just a normal `TaskNode` from the scheduler's perspective.

### B.C — Branching / cross-cell orchestration

**Goal**: conditional graph branches; multi-cell sessions with retained-state transfer.

**Scope hints**:

* Conditional edges: an edge could carry a predicate that decides whether the child is enabled based on the parent's `TaskResult`. Today, edges are unconditional.
* Cross-cell: each cell has its own `CellStateRegistry`; cross-cell continuity needs a `MultiCellSession` or equivalent that owns multiple sub-sessions and orchestrates handoff via boundary snapshots.
* Cross-cell replay identity: how does `boundary_snapshot()` interact with multiple cells? The current allowlist (D-CONT-1) is single-cell-scoped.

**What it delivers**: significantly expanded orchestration capability. But the contract doc §11 item 3 explicitly says cross-cell is "deferred to a hypothetical Phase 5+ cross-cell contract." This is large.

### B.D — Long-horizon deterministic sessions

**Goal**: sessions with thousands of nodes / hours of physics time; trace archival without replay mutation.

**Scope hints**:

* Boundary-snapshot cadence: today's session emits 1 + 2N snapshots (1 initial + 2 per node). For 1000-node jobs that's 2001 snapshots — large but tractable.
* Trace compaction: WITHOUT replay mutation. Compaction would mean periodically writing a manifest-checkpoint that summarizes events up to seq N, with the option to verify replay by re-running from the checkpoint forward. The checkpoint is itself replay-authoritative content; D-TRACE-2 append-only is preserved as long as the checkpoint is an APPEND, not a rewrite.
* Archival posture: after `complete()`, the SessionPackage is closed. Long-horizon sessions might want to write incremental compressed snapshots to a separate archive directory peer to the SessionPackage.

**What it delivers**: scale. The current substrate works at 2-node demonstrations; long-horizon validation would prove it scales without contract violations.

### B.E — Operator workflow semantics

**Goal**: materialize `OperatorChannel` (deferred from Step 9 Phase 5 to Step 11 in the original plan). Add pause/inspect/approve/continue command kinds, multi-envelope flows, authority gating.

**Scope hints**:

* `OperatorEnvelope.kind` extends from `{"abort"}` (Step 9 D-FAULT-9a) to `{"abort", "pause", "resume", "approve", "manual_advance"}`. Each kind needs its own state-transition rule.
* Live ingress (vs. Step 9's pre-queued-only): the channel object accepts envelopes during a running session. Must preserve replay-authority — live envelopes get the same `requested_at_tick` discipline as pre-queued ones, and the channel queue is replay-deterministic.
* Authority gating: operator commands have permission levels (`approve` requires a privileged operator; `manual_advance` requires emergency authority). This is policy, not orchestration substrate.
* Forensic audit: per-envelope provenance (who, when, why) — but wall-clock provenance is FORBIDDEN. The provenance is `requested_at_tick` + a deterministic envelope_id + a free-form `reason` string.

**What it delivers**: the operator interaction layer. Pre-queued envelopes already work (Step 9); live ingress is the next step.

### B.F — Deterministic pause / resume semantics

**Goal**: pause a session at a clean boundary; resume from the resulting snapshot to produce byte-identical continuation.

**Scope hints**:

* `SessionState` gains `PAUSED` (transient) and possibly `RESUMED` (transient back to `RUNNING`). D-FAULT-15 #18 forbids `RECOVERING`; `PAUSED` is conceptually different (no implicit healing) but still needs careful contract treatment.
* Resume must read the boundary snapshot of the last Phase G; recreate the session with the snapshot as input; replay continues byte-identically from there.
* What does the executor look like across pause/resume? Probably: the executor is destroyed at pause; a fresh executor is constructed at resume from the snapshot.
* Phase 4A executor doesn't currently support construction-from-snapshot — needs evolution.

**What it delivers**: long-running sessions can be paused and resumed. Useful for multi-day runs.

---

## §C. Per-candidate five-lens risk analysis

Risk lenses (same five lenses used for Step 9 §F resolutions):

* **RD** — replay-divergence risk
* **HA** — hidden-authority risk
* **CT** — contamination risk
* **IR** — implicit-recovery risk
* **LA** — lifecycle-ambiguity risk

Severity scale: ★ (low) → ★★★★★ (severe).

### B.A — Executor interruption surfaces

| lens | severity | analysis |
|---|---|---|
| RD | ★★ | low if interruption windows are between deterministic `world.step()` calls (PhysX produces same result for same inputs at each step). Higher if mid-step interruption is permitted (FORBIDDEN per D-FAULT-6a). |
| HA | ★★ | low if the executor exposes interruption via an explicit `interrupt_at_segment_boundary` poll the session reads. High if the executor "decides" when to interrupt — that's a hidden authority. |
| CT | ★ | none unless the executor leaks segment-internal state (joint velocities, contact manifolds) into the TaskResult — D-CONT-2 already forbids this. |
| IR | ★★ | low if interruption produces a clean `TaskResult` with `outcome = TIMEOUT_FAILURE` (the session decides). High if the executor "recovers" mid-segment — FORBIDDEN. |
| LA | ★★★ | medium — the executor's pre-existing single-`execute()` lifecycle gets internal sub-phases. The contract must clearly state that sub-phases are NOT D-EXEC phases (which are orchestration-level). |

**Net risk**: medium-low. The interruption is *internal to the executor*; from the session's perspective the change is purely additive — the executor now populates `ticks_consumed` honestly and can return an outcome from a partial trajectory. D-FAULT-6a (atomic Phase E) is preserved because the session still sees one `execute()` call.

### B.B — Recovery-topology orchestration

| lens | severity | analysis |
|---|---|---|
| RD | ★ | low — recovery is a normal `TaskNode`; scheduler iterates `canonical_order`; replay is byte-identical by D-SCHED-2/-3. |
| HA | ★★★★ | high — the temptation to "automatically" route to a recovery node when the parent fails is exactly the hidden authority D-FAULT-8a forbids. Must remain operator-graph-explicit. |
| CT | ★ | none |
| IR | ★★★★ | severe if recovery node is reached implicitly. The graph must declare an explicit edge from the failure point (or operator must inject a new graph for the recovery session). |
| LA | ★★ | medium — `RecoveryNodeEntered` is in the event constants but not yet emitted by the runtime; needs clear emission rules. |

**Net risk**: medium-high. Recovery is where implicit secondary orchestration creeps in. The contract (D-FAULT-8 / -8a / -8b) is tight; runtime implementation must mechanically enforce.

### B.C — Branching / cross-cell orchestration

| lens | severity | analysis |
|---|---|---|
| RD | ★★★★★ | severe — conditional branches mean a graph's behavior depends on per-cycle `TaskResult` values. If `TaskResult` carries any non-replay-authoritative content, branching becomes nondeterministic. |
| HA | ★★★★★ | severe — cross-cell would introduce a `MultiCellSession` authority that owns multiple sub-sessions. Risks fragmenting D-SESS-1's single-mutation-authority discipline. |
| CT | ★★★★ | high — cross-cell retained-state transfer requires expanding D-CONT-1's allowlist; every new authoritative field is a new contamination surface. |
| IR | ★★ | medium |
| LA | ★★★★★ | severe — multi-session lifecycle is a brand-new concept; the contract has no clauses for it. |

**Net risk**: very high. This is the largest direction; would require substantial contract revision. Should NOT be Step 10 — needs a dedicated multi-step program.

### B.D — Long-horizon deterministic sessions

| lens | severity | analysis |
|---|---|---|
| RD | ★★ | medium — checkpoint cadence must not influence replay identity. Two sessions with same input but different cadence policies would produce different SessionPackages — that's a per-policy fingerprint surface. |
| HA | ★★ | medium — checkpoint logic is a new mutation site (writes the checkpoint file). Must be append-only, single-emitter (session). |
| CT | ★★★ | medium-high — what enters the checkpoint? If it's purely a re-projection of the existing boundary snapshots, it's safe. If it's a *summary* (compressed events.jsonl), the summary is itself a replay-authoritative artifact and the compression must be deterministic. |
| IR | ★ | low |
| LA | ★★ | medium |

**Net risk**: medium. Tractable but needs careful contract work on checkpoint cadence + compaction semantics.

### B.E — Operator workflow semantics

| lens | severity | analysis |
|---|---|---|
| RD | ★★ | medium — live envelope ingress means the envelope queue grows asynchronously from operator input. Replay determinism requires recording the queue's deterministic interleaving. |
| HA | ★★★ | medium-high — operator commands are by definition out-of-band. Authority gating (who can issue `approve`) is policy; substrate must record the gate without enforcing the policy. |
| CT | ★★ | low-medium — envelope payloads may carry operator-supplied strings; canonical-JSON discipline must hold. |
| IR | ★ | low — operator commands are explicit; no automatic recovery implied. |
| LA | ★★★★ | high — multi-kind operator envelopes (pause/resume/approve/manual_advance) each have distinct state-transition implications. Need clauses for each. |

**Net risk**: medium. The Step 9 D-FAULT-9 schema is ready; the ingress channel is the new work.

### B.F — Deterministic pause / resume semantics

| lens | severity | analysis |
|---|---|---|
| RD | ★★★★ | high — resume must produce byte-identical continuation. The boundary snapshot at pause time must be sufficient to recreate the runtime exactly. Today's snapshot may not capture every replay-authoritative input. |
| HA | ★★★ | medium — resume reads from a snapshot file; the read operation is itself an authoritative input. Snapshot read failure paths need clear semantics. |
| CT | ★★★★ | high — what is the boundary between "paused-session state" and "fresh-session input from snapshot"? Easy to leak non-authoritative state in. |
| IR | ★★★★ | high — temptation to "smooth over" small differences in resume state is exactly the hidden recovery anti-pattern. |
| LA | ★★★★★ | severe — `SessionState.PAUSED` is a new lifecycle state; `RESUMED` is conceptually fraught (a "resumed" session is a NEW session or the SAME session?). |

**Net risk**: very high. Needs careful contract design before runtime work.

---

## §D. Layer classification

Each candidate maps to one or more architectural layers. Avoiding layer collapse is a substrate concern.

| candidate | primary layer | secondary layer | layer-collapse risk |
|---|---|---|---|
| A. Executor interruption surfaces | **execution adapter** | (none) | low — stays in Phase 4A's `TaskExecutor`; orchestration substrate unchanged. The session sees the same `execute(task) → TaskResult` interface. |
| B. Recovery-topology orchestration | **orchestration substrate** | (none) | low — extends D-FAULT-8 runtime behaviour; no new layers. |
| C. Branching / cross-cell orchestration | **orchestration substrate** | **operator workflow** | high — multi-cell needs a new top-layer authority (MultiCellSession or equivalent), risks fragmenting D-SESS-1. |
| D. Long-horizon deterministic sessions | **orchestration substrate** | **observational tooling** | medium — checkpoint cadence is substrate; archival is observational. Must keep them separate. |
| E. Operator workflow semantics | **operator workflow** | (none, if implemented as a channel over the existing envelope) | low — Step 9 D-FAULT-9 schema already exists; this materializes the ingress. |
| F. Deterministic pause / resume | **orchestration substrate** | **observational tooling** | high — pause-resume blurs "session" identity; needs careful contract work to avoid creating a hidden authority over session boundaries. |

The four layers in this project:

* **Orchestration substrate** — `cell_authoring/orchestration/` + the deterministic-semantics contract.
* **Execution adapter** — `cell_authoring/tasks/` (Phase 4A `TaskExecutor`, validators, definitions).
* **Operator workflow** — out-of-band command + audit surface; today's envelope schema is the first step.
* **Observational tooling** — comparator, MP4 recording, archival, metrics dashboards (when they exist).

A Step 10 candidate that requires a *new layer* (e.g. a cross-cell coordinator layer) is by definition more ambitious than a Step 10 candidate that operates within an existing layer.

---

## §E. Executor evolution deep-dive (direction A)

Direction A is the most natural Step 10 candidate because:

1. It is the **direct continuation** of the Step 9 deferral. Scenarios C–F were documented as "executor-adapter capability limitation, NOT contract gaps."
2. It operates within **one layer** (execution adapter); orchestration substrate unchanged.
3. The contract surface already exists — `result.ticks_consumed`, `task.tick_budget_ticks`, the cascade machinery — they just don't get exercised because the executor doesn't expose deterministic interruption.

### E.1 — What the executor needs to expose

Today's Phase 4A `TaskExecutor.execute()` is one atomic call. It runs the full trajectory to completion (or to PhysX-internal exception) and returns a `TaskResult`.

For Step 10 direction A, the executor needs to expose:

| capability | how | replay-authority implication |
|---|---|---|
| **honest `ticks_consumed`** | post-`execute()` field on `TaskResult` (already a field; just populate it) | none — integer count of `world.step()` invocations; pure-deterministic |
| **per-segment outcome** | executor's internal trajectory is composed of N segments (approach, grasp, lift, transport, place, release); each segment has a known tick length. Executor evaluates the validator's verdict after each segment. | none if the verdict is reproducible per segment; the executor must NOT use wall-clock to gate the evaluation |
| **mid-trajectory failure** | a real PhysX condition (e.g. peg slips, gripper torque limit, joint limit) detected by the executor; the executor short-circuits the remaining segments and returns a TaskResult with the appropriate non-PASS `TaskOutcome` | the failure verdict must be deterministic for given inputs; PhysX-version-specific behaviour is a known risk (D-CONT-2) |
| **abort-on-segment-boundary** | the session's pre-queued `OperatorEnvelope` becomes visible to the executor between segments; executor returns a TaskResult with `outcome = OPERATOR_ABORT_ACQUIRED` (NEW outcome value, would need contract addition) | this is the contentious one — it lets abort enter Phase E, which D-FAULT-6 forbids. ALTERNATIVE: the session computes `interrupt_at_next_segment` flag and the executor polls it between segments, returning whatever partial-trajectory result it has. The outcome is "node failed mid-execute"; the session classifies it appropriately. |

### E.2 — Resolving the D-FAULT-6 tension

D-FAULT-6 says: "Operator abort enters orchestration **only at Phase A** of an orchestration tick."

The naive reading: abort cannot affect a running `execute()` call. Phase E must complete to its end.

The Step 10 evolution: abort still enters at Phase A *of the next orchestration tick*. What changes is that the session's notion of a "tick" becomes finer-grained. Today, one `step()` invocation = one node execution. Tomorrow, a node execution that takes 100 PhysX ticks could expose ~10 segment boundaries, each of which is a candidate for the session to observe the next pre-queued envelope.

**BUT**: this would mean the session's `step()` calls multiple times during one node execution. That's a major change to the orchestration tick.

**Cleaner alternative**: the session does NOT step during execute. The executor itself accepts a `should_interrupt: Callable[[int], bool]` argument that it polls between segments. The callable is bound to the session's envelope queue. The callable is **pure** — it takes the current segment count and returns True/False based on whether there is a pre-queued envelope with `requested_at_tick <= current_segment_tick`. The callable IS a session-side authority but it is read-only from the executor's perspective.

This preserves:

* D-FAULT-6 — abort still enters via the envelope, drained at the segment boundary (which IS the executor's Phase E sub-boundary)
* D-FAULT-6a — Phase E from the orchestration perspective is still atomic; the session does not interleave Phase A drains with the executor
* D-FAULT-15 #16 — no method-as-ingress; the callable is purely a *read* of the existing envelope queue

### E.3 — New contract clauses likely needed

If direction A is Step 10, the following contract additions/amendments are likely:

* **D-EXEC-6+ (new corollary)**: Phase E sub-boundary definition. The executor MAY expose sub-segment boundaries internally; at each, it MAY consult the session's interrupt predicate. The predicate is pure.
* **D-FAULT-12c (new corollary)**: `ticks_consumed` is REQUIRED to be the deterministic count of `world.step()` invocations the executor performed during the most recent `execute()` call.
* **D-FAULT (new clause)**: `OPERATOR_ABORT_ACQUIRED` as a new TaskOutcome value (sub-classifier of NODE_EXECUTION_FAILURE per D-FAULT-1a) for the case where abort was honoured during execute.
* **D-EXEC-X (new clause)**: pure-predicate discipline for executor-consumed callables. Callables passed to the executor by the session MUST be deterministic, side-effect-free, and consult only authoritative inputs.

### E.4 — Scope sketch (NOT a commitment)

If Step 10 = direction A, the phases would parallel Step 9's:

1. Architecture analysis (this document evolved into a Step 10-specific analysis).
2. Contract freeze — new D-EXEC + D-FAULT corollaries.
3. Pure-Python contract tests (no Isaac).
4. Runtime wiring — executor evolution; `should_interrupt` callable; segment-boundary verdict evaluation.
5. Isaac Sim regression — exercise scenarios C–F end-to-end.
6. Replay-identity gate — extend comparator coverage for the new outcome values.
7. Operator MP4 review — confirm visual coherence of mid-execute interruption.

Total scope roughly comparable to Step 9 (perhaps 30–50% smaller — orchestration substrate barely changes; most work is in `cell_authoring/tasks/executor.py`).

---

## §F. Recommendation ordering

Based on the §C risk analysis + §D layer classification + §E deep dive, the recommended Step 10 / Step 11+ ordering:

| order | candidate | rationale |
|---|---|---|
| **1 (Step 10)** | **A. Deterministic executor interruption surfaces** | natural continuation of Step 9 deferral; one-layer change; net risk medium-low; unlocks scenarios C–F |
| 2 (Step 11) | E. Operator workflow semantics (OperatorChannel live ingress) | already designed in D-FAULT-9 schema; original §9 placement; medium risk |
| 3 (Step 12) | B. Recovery-topology orchestration | designed in D-FAULT-8 already; medium-high risk concentrated in mechanical-enforcement against hidden authority |
| 4 (Step 13) | D. Long-horizon deterministic sessions | medium risk; tractable once recovery + executor evolution are done |
| 5 (later) | F. Deterministic pause / resume semantics | very high risk; needs dedicated contract work before runtime |
| **6 (deferred)** | C. Branching / cross-cell orchestration | very high risk; explicitly out of Phase 4B scope per §11 of the contract; reserve for a dedicated cross-cell program |

**Why direction A first**:

* It is the smallest *layer-scoped* change that unlocks the largest user-visible capability gain (Step 9 scenarios C–F empirically validated on real PhysX).
* It maintains substrate stability — orchestration substrate is unchanged.
* It produces immediate empirical evidence that the substrate scales (timeout, real failure, mid-execute abort all behave per contract on real PhysX).
* It is the most-tested direction in the project's existing test surface (Phase 3M/N/O/P plus Phase 9 P4/P7 already exercise close-adjacent behaviours).

**Why C is deferred**:

* The contract doc §11 item 3 explicitly defers cross-cell.
* Cross-cell requires a brand-new authority (MultiCellSession or equivalent) that would fragment D-SESS-1.
* Replay identity across cells is undefined; would need substantial contract revision.

**Why F is later**:

* `SessionState.PAUSED` semantics are conceptually fraught — is a paused-then-resumed session ONE session or TWO?
* The boundary snapshot today is sufficient for replay-from-input; sufficient-for-resume is a strictly stronger requirement.
* High HA + LA risk.

---

## §G. Open architectural questions

These would resolve in Step 10 Phase 1 / Phase 2 (analysis + contract) if direction A is adopted:

1. **Segment vs tick granularity** — should the executor's interruption boundary be per-`world.step()` (max granularity) or per-trajectory-segment (coarser, easier to reason about)? Probably the latter; the former makes failure mode classification harder.
2. **Segment naming** — should segments be named (`approach`, `grasp`, etc.) or numbered? Names are operator-visible (better forensics) but trajectory-author-coupled.
3. **`OPERATOR_ABORT_ACQUIRED` as a TaskOutcome value** — or use a session-level classification instead? Step 9's D-FAULT-1a says TaskOutcome only sub-classifies NODE_EXECUTION_FAILURE; abort is OPERATOR_ABORT (session-level). So abort-during-execute is conceptually a session-level OPERATOR_ABORT that the executor honored at a segment boundary. The session classifies the terminal state; the executor just signals "I stopped early."
4. **Should the interrupt predicate live in the session or be passed via `execute_kwargs`?** Probably via `execute_kwargs` for testability; the executor sees a `Callable[[int], bool]` and never knows about envelopes.
5. **Is the segment-tick counter authoritative for replay?** If two cycles produce different segment-tick counts at the interruption boundary, the cycles are not replay-identical. So the segment-tick counter MUST be deterministic.
6. **What is the behaviour when interrupt fires AT segment boundary 0 (before any `world.step()`)?** That's equivalent to no execute at all. The session should treat it as a clean abort, not a failure.

---

## §H. Hard constraints carry-forward

Step 10, whichever direction, MUST NOT introduce:

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
* wall-clock based gating in orchestration
* `RECOVERING` as a `SessionState` value (D-FAULT-15 #18)
* method-as-ingress for operator commands (D-FAULT-15 #16)

These are now substrate invariants. Step 10 candidates that require any of these are not Step 10 candidates.

---

## §I. Document lifecycle

1. ✅ **Phase 1 (this document, 2026-05-20)**: draft Step 10 candidate map + risk analysis + layer classification + executor deep-dive + recommendation ordering.
2. ⏳ **Phase 2**: review with operator; converge on a single Step 10 direction. Open questions in §G resolved.
3. ⏳ **Phase 3**: if direction A is selected, author Step 10 Phase 1 analysis doc (executor evolution specifics) + draft new contract clauses.
4. ⏳ **Phase 4+**: contract freeze → tests → wiring → Isaac validation → MP4 review (mirroring Step 9's discipline).

Until Phase 2 convergence, no production code changes. The substrate posture established by Steps 8 + 9 is the immovable baseline; Step 10 must compose with it, not weaken it.

---

## §J. Closing posture

The project is now a deterministic industrial orchestration substrate with replay-authoritative execution semantics. Step 10 will extend the substrate's *reach* (executor evolution → scenarios C–F) or its *interaction surface* (operator workflow), but the substrate itself is stable.

New capabilities **must compose with deterministic replay authority, not bypass it.** A Step 10 direction that proposes any form of replay-healing, implicit recovery, hidden authority, or wall-clock dependence is rejected at the analysis gate, before any implementation work.
