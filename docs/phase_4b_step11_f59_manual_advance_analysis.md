# Phase 4B Step 11 — F59: manual_advance Semantics Constitutional Admissibility

**Status: FOCUSED CONSTITUTIONAL ANALYSIS (2026-05-21).** F59 discharge from the [Step 11 Admissibility Framework](phase_4b_step11_admissibility_framework.md): whether the reserved-but-unimplemented `manual_advance` envelope kind admits any constitutionally-distinct semantic under the Step 8 / 9 / 10 / 11 + F58 substrate.

This document is purely analytical; no contract clauses are authored, no runtime is implemented, no scheduler proposal is made.

---

## §1. Candidate-semantic enumeration

Ten readings of `manual_advance` are evaluated. Each is checked against existing substrate clauses.

**R1. Force-select.** Envelope carries `target_node_id`; session forces that node's selection at next Phase B. → **D-SCHED-1, D-SCHED-3** violations (scheduler purity + canonical-order).

**R2. Force-runnable.** Envelope marks a node with non-completed parents as runnable. → **D-SCHED-2, D-FAULT-4** violations (topological-order + cascade-skip semantics).

**R3. Skip-node.** Envelope adds a pending node directly to `_skipped`. → **D-FAULT-2, D-FAULT-4, D-CONT-1** violations (cascade-emission single-emitter; D-FAULT-4 cascade scope; authoritative-continuity field write outside authorized site).

**R4. Precondition-override.** Envelope makes a predicate's verdict `True` regardless of registry state. → **D-SCHED-12** violation (predicate purity).

**R5. Mid-execute-preempt.** Envelope terminates currently-executing node's Phase E. → **D-FAULT-6a, D-EXEC-13a, D-EXEC-13c, D-FAULT-15 #5/#27/#29** violations. Equivalent to Framework Threat 6.

**R6. Tick-advance.** Envelope advances `orchestration_tick` by some delta. → **T1** violation (clock authority widening); equivalent to F58 Shape PB.

**R7. Step-through.** Operator manually invokes `session.step()` one at a time. → No substrate referent. Caller already controls cadence (D-FORBID-11). Reduces to no envelope.

**R8. Force-recovery.** Envelope marks a failed node "manually resolved" without a graph-explicit recovery node. → **D-FAULT-8, D-FAULT-8a, D-FAULT-8b, D-FAULT-15 #2/#8/#15** violations.

**R9. Permission-gate.** Graph contains a pre-declared "manual gate" node whose precondition becomes satisfied when manual_advance drains. → Whichever satisfaction mechanism: **D-SESS-6** (registry mutation outside Phase D/G), **D-SCHED-12** (predicate reading envelope queue), or **D-SCHED-1** (scheduler reading `session_state`) — at least one violation.

**R10. Trace-injection.** Envelope causes a synthetic event to be recorded. → **D-FAULT-14, D-TRACE-1** violations.

**Sub-finding 1.A.** Every reading R1–R10 violates at least one existing substrate clause. R7 is the sole exception with no violation — but reduces to no substrate envelope.

**Sub-finding 1.B.** No constitutionally-admissible distinct semantic appears in the enumerated set.

---

## §2. The reduction theorem

### §2.1 Orchestration-decision input whitelist

**Lemma 2.1.** The substrate's orchestration-decision evaluations have the following exhaustive input set:

| evaluation site | authoritative inputs | citation |
|---|---|---|
| scheduler selection | `(graph, registry, completed, failed, retry_counts)` | D-SCHED-1 |
| precondition / postcondition predicate | `registry` | D-SCHED-12 |
| registry mutation (executor) | Phase D observational projection from PhysX | D-SESS-6, D-CONT-5a |
| registry mutation (session) | Phase G PASS verdict + D-CONT-1-enumerated outcome data | D-SESS-6, D-CONT-5 |
| executor interruption predicate construction | envelope snapshot + base_tick + tick_budget_ticks + task_id, captured at execute-entry by **session** | D-EXEC-13c, D-EXEC-13 whitelist |

No other input enters orchestration calculus.

### §2.2 Envelope-drain effect whitelist

**Lemma 2.2.** An `OperatorEnvelope` drained at Phase A produces effects in exactly the following set:

* `session_state` transition (D-FAULT-6: RUNNING → ABORTING under `abort`; T6: RUNNING ↔ PAUSED under `pause`/`resume`);
* forensic ingress event recorded in `events.jsonl` (D-FAULT-7 idempotency).

No other envelope-drain effect is currently admitted.

### §2.3 Structural-gating-only property of session_state

**Lemma 2.3.** `session_state` is not an authoritative input to any orchestration-decision evaluation in Lemma 2.1. Specifically:

* D-SCHED-1 input list does not include `session_state`. The session bypasses the scheduler entirely when `session_state ∈ {ABORTING, PAUSED}`; the scheduler is NOT given a state-dependent input.
* D-SCHED-12 predicate input list (registry only) does not include `session_state`.
* D-EXEC-13c whitelist does not include `session_state`. The predicate is constructed only when Phase D is reached.

∴ `session_state` is **structural-gating only**. It governs *which phases execute* (uniform structural skip), not *what decisions phases make*.

### §2.4 The reduction theorem

**Theorem T7 — Manual-Advance Constitutional Incompatibility.**

Let E be an `OperatorEnvelope` whose effect on the substrate is not (a) a `session_state` transition AND not (b) a forensic event recording. Then E's effect F must enter at least one orchestration-decision-evaluation site (Lemma 2.1). For each candidate site:

* Site 1 (scheduler): adding E's content to scheduler inputs violates D-SCHED-1.
* Site 2 (predicate): adding E's content to predicate inputs violates D-SCHED-12.
* Site 3 (registry mutation, Phase D): only the executor mutates from PhysX observational projection; envelope-driven mutation here violates D-CONT-5a.
* Site 3' (registry mutation, Phase G): only verdict-conditioned occupancy commit (D-CONT-5); envelope-driven mutation violates D-SESS-6.
* Site 4 (executor predicate closure): adding E's content beyond the D-EXEC-13 whitelist violates D-EXEC-13c.

∴ Every non-whitelisted envelope effect violates at least one substrate clause. ∎

**Corollary 2.4 (Reduction).** Every constitutionally-admissible reading of `manual_advance` reduces to:

* `pause`/`resume` semantics (T6 + D9 — operator controls cadence of session_state structural-gating, no decision influence);
* `abort` semantics (D-FAULT-6 — session terminus);
* caller-side cadence (R7 — caller drives session.step(), no envelope needed).

No distinct semantic remains.

**Corollary 2.5 (Distinct-Semantic Impossibility).** ∄ a semantic S for `manual_advance` such that:
- S is distinct from `pause` / `resume` / `abort` / caller-cadence, AND
- S preserves T1–T6 ∪ D1–D9 ∪ D-SCHED-1 ∪ D-SCHED-12 ∪ D-SESS-6 ∪ D-EXEC-13c ∪ D-FAULT-2 ∪ D-FAULT-6 ∪ D-FAULT-6a ∪ D-FAULT-8 ∪ D-FAULT-14.

∴ `manual_advance` has empty constitutional content as a distinct envelope kind.

---

## §3. Discharge of brief's enumerated questions

### Q3.1 Constitutionally admissible at all?

**No** for distinct-semantic readings (Theorem T7). **Vacuously yes** if reduced to existing kinds (Corollary 2.4), but then the kind name is redundant.

### Q3.2 Second execution authority surface?

**Yes** for R1, R2, R3, R5, R6, R8, R9, R10. Each non-trivial reading creates a second authority for at least one of: scheduler selection, predicate evaluation, registry mutation, tick advancement, cascade emission, or recovery determination. Authority singularity (D-FAULT-2 generalization) is violated.

### Q3.3 D-SCHED-1 violation?

**Direct yes** in R1, R2, R9.
**Indirect yes** in R3 (the cascade-emission authority migrates from scheduler-companion logic), R4 (predicate-purity violation is structurally adjacent to D-SCHED-1 in the input-whitelist sense).
**No direct violation** in R5, R6, R7, R8, R10 — those violate other clauses.

### Q3.4 Fractures orchestration epoch integrity?

**Yes**: R5 (forces a mid-Phase-E observation surface, violating T3); R6 (introduces a non-session.step() tick-advancement, violating T1 and breaking Lemma L1 K_drain uniqueness); R9 (introduces a gate-resolution epoch beyond Phase A).

### Q3.5 Hidden scheduler authority?

**Yes** in R1, R2, R9. The trace would record the envelope drain (visible) and the resulting selection (visible) without recording the causal arc through pure-function evaluation (hidden). Analogous to D-FAULT-15 #15 (topology-derived recovery inference) but for node selection.

### Q3.6 Replay-authoritative causality?

**No** under distinct-semantic readings. Replay reconstruction requires every authoritative state change to be replay-reproducible via the trace + the orchestration-decision pure functions. Manual_advance's hypothetical authority does not have a recording surface in those pure functions; even if the envelope is recorded, the replay's pure-function evaluations cannot reproduce the divergence. Lemma L2 (Epoch-Identity ⇒ Trace Identity) fails.

### Q3.7 Phase-A-governed possible?

**Drain yes; effect no** for distinct-semantic readings. Manual_advance's envelope drain could be at Phase A (T3-compatible). Its effect leaks into Phase B / D / G as a non-uniform, selective decision-shift. Compare PAUSED: drain at Phase A, effect is uniform structural-skip (admissible). Manual_advance's effect is selective decision modification (inadmissible).

**Lemma 3.7.1.** Uniform structural skip via `session_state` is admissible at Phase A drain. Selective decision-making via envelope-content reading at any post-A phase is not.

### Q3.8 Externally-directed execution branching?

**Yes** under all non-trivial readings. The substrate's branch authorities (scheduler, predicate, validator, cascade-decision) are each pure-function. Manual_advance introduces operator-direct branch determination, violating authority singularity.

### Q3.9 Append-only execution semantics?

**Trace-level yes; causal-singularity-level no.** The envelope itself is appended (D-TRACE-2). The selective decision modification it causes is forward-causal (not retroactive). But "append-only execution semantics" in the brief includes causal singularity — the substrate's decision authorities form a singular DAG of pure functions. Manual_advance widens this DAG with a non-causal input arc.

### Q3.10 New epoch categories?

**Yes** in R5 (mid-Phase-E preempt-observation epoch), R6 (envelope-driven tick-advance epoch), R9 (gate-resolution epoch). **No** in R1, R2, R3, R4, R8, R10 — those violate other surfaces without new epochs.

### Q3.11 Transport-independent?

**Vacuously yes** for the reduce-to-existing-kinds path (no distinct semantic to be transport-dependent).
**Vacuously no** for the distinct-semantic path (no admissible distinct semantic exists, so transport-independence of a non-existent surface is undefined).

### Q3.12 Reducible to ordinary ingress semantics?

**Yes.** Corollary 2.4 enumerates the reductions: `pause`/`resume`, `abort`, or caller cadence. Each constitutionally-admissible reading reduces.

### Q3.13 Violates T1–T6 or D1–D9?

**Direct violations to Step 11 framework:**
* R5 violates T2 (N2-only impossibility — manual_advance is the explicit mid-Phase-E ingress that T2 forbids), T3 (Phase-A-only observability), D6 (predicate closure stability).
* R6 violates T1 (Tick Non-Commensurability — introduces a second tick-advancement authority).

Other readings violate older clauses (D-SCHED-1, D-FAULT-8, etc.) without directly engaging T1–T6 or D1–D9.

**Sub-finding 3.13.1.** The Step 11 framework does NOT need a new theorem specifically for manual_advance — older clauses already preclude every distinct semantic. T7 is normative-candidate as a foreclosure clause, not as a new invariant.

---

## §4. Explicit-analysis-point discharges

### Scheduler ownership boundaries

D-SCHED-1 establishes scheduler as pure function of `(graph, registry, completed, failed, retry_counts)`. Manual_advance, in any non-trivial reading, requires either input-list extension (violation) or output override by parallel authority (also violation). Ownership is sharp; envelope cannot enter.

### Node-selection authority

Single substrate authority: scheduler at Phase B. D-FAULT-2 (single-emitter) generalizes to single-authority: each orchestration-decision class has exactly one authority. Manual_advance would split the selection authority.

### Externally-directed continuation semantics

Continuation governed by three pure-function paths: scheduler (D-SCHED-1), predicate (D-SCHED-12), failure-action propagation (D-FAULT-3). All three are envelope-blind. Externally-directing any of them requires entering its input set — violation.

### Execution ownership continuity

`TaskExecutor` owns node execution within Phase E (D-SESS-1 subordinate, D-FAULT-6a atomic). R5 splits this between executor and envelope — direct D-FAULT-6a violation.

### Replay reconstruction implications

For replay to reproduce a manual_advance-influenced run, both the envelope drain AND the resulting orchestration-decision divergence must be recorded. The envelope drain is recordable (D-FAULT-7). The decision divergence has no recording surface — the substrate's decision pure functions don't take envelope content as input, so there's no causal arc to reconstruct. ∴ structurally non-replayable.

### Interaction with continuation snapshots

D-CONT-1 enumerates authoritative retained continuity: `_completed`, `_failed`, `_skipped`, `_retry_counts`, `_node_runtime`, registry. Manual_advance state (e.g., "advanced past predicate X") would need its own field. D-CONT-7a requires every continuity field to be authoritative-emission-paired. Manual_advance has no Phase-G emission site (drain is Phase A; Phase G is reserved for occupancy commit). The continuity surface has no admissible slot.

### Interaction with interruption semantics

D-EXEC-13 whitelist (envelopes, base_tick, budget, task_id, all at execute-entry) is exhaustive. Adding "manual_advance pending" as a closure input widens the whitelist. T2's domain (mid-Phase-E ingress) cannot accommodate manual_advance without violating T2's hypothesis. R5 is exactly T2's forbidden case.

### Contradiction timing under externally-directed advancement

D-FAULT-5b enumerates contradictions: post-failure last-tick-truth pose + unchanged occupancy. Manual_advance could produce a different contradiction class — "advanced past a precondition the registry says is unsatisfied." The substrate has no representation for this contradiction class. Adding one is D-CONT-1 modification, which the brief forbids.

### Non-causal execution selection

R1's force-select: cause is operator intent (envelope drain at Phase A); effect is node X selected at Phase B. Causal arc would need to flow through scheduler's pure function — D-SCHED-1 forbids. Without the arc, selection is non-causal in the substrate's decision DAG.

### Authority singularity collapse

D-FAULT-2 ∪ D-SESS-1 ∪ D-SCHED-1 ∪ D-SCHED-12 jointly establish: each orchestration concern has exactly one authority. Manual_advance's distinct-semantic readings each introduce a second authority for at least one concern. Authority singularity is the substrate's deepest invariant; collapsing it is the fundamental constitutional violation.

### Runtime authority widening

Substrate's runtime-authority surface: (i) session.step() invocation (caller); (ii) envelope ingress at Phase A (operator → session); (iii) executor invocation in Phase E (session → executor). No fourth surface "operator → orchestration-decision directly" exists or can be added without violating Lemma 2.1.

---

## §5. Theorem T7 and downstream implications

### §5.1 Theorem T7 (final statement)

**Theorem T7 — Manual-Advance Constitutional Incompatibility.** No `OperatorEnvelope.kind` value admits an effect outside Lemma 2.2's whitelist (`session_state` transition + forensic event) without violating at least one of:

D-SCHED-1, D-SCHED-12, D-SESS-6, D-EXEC-13c, D-CONT-5a, D-FAULT-2, D-FAULT-6a, D-FAULT-8, D-FAULT-14, D-FAULT-15 rows #2/#5/#8/#15/#16/#27/#29, T1, T2, T3, D6.

In particular, no semantic for `manual_advance` distinct from existing kinds (`abort`/`pause`/`resume`) exists.

**Proof.** §2.4 derivation; §1 enumeration showing every conceivable reading violates at least one clause. ∎

### §5.2 D-FAULT-9a disposition recommendation

D-FAULT-9a currently reserves `manual_advance` for Step 11. F59 finds this reservation has no admissible content.

**Option A — DROP** (recommended). Retire `manual_advance` from D-FAULT-9a's reserved set in any future contract phase. Reserved kinds become `{pause, resume}`.

**Option B — REPURPOSE.** Redefine `manual_advance` as an alias for an existing reduction (pause/resume sequence or caller cadence). Net effect: noise-bearing alias with no distinct semantic. Not recommended.

**Option C — DEFER INDEFINITELY.** Leave reserved-but-undefined. Future implementers will encounter Theorem T7 from below, wasting analytical capacity. Not recommended.

The framework's analytical hygiene favors Option A.

### §5.3 Framework integration

T7 is classified **NORMATIVE-CANDIDATE**. It would be authored in a future Step 11 contract phase alongside T2–T6, the Disciplines D1–D9, and the D-FAULT-15 row extensions #31–#42 (Step 11 Framework §Q). T7 forecloses manual_advance-style envelope semantics generally — not just the literal `manual_advance` name. Any future envelope kind proposal must demonstrate non-entry into Lemma 2.1's whitelist.

**Proposed Framework D-FAULT-15 row #43:**

> #43 — Envelope kinds whose effect includes entering an orchestration-decision pure-function's input set beyond Lemma 2.2's whitelist (scheduler input via D-SCHED-1, predicate input via D-SCHED-12, executor predicate closure beyond D-EXEC-13 whitelist, registry mutation from Phase A drain).
>
> Cites: T7, D-SCHED-1, D-SCHED-12, D-EXEC-13c, D-SESS-6.

### §5.4 Framework F42 resolution

F42 (kind expansion) was OPEN pending F58 + F59. After F58: `pause`/`resume` ADMITTED with T6 + D9 + R1. After F59: `manual_advance` INADMISSIBLE; reserved name should be dropped.

**F42 status:** RESOLVED.
* `pause` — ADMITTED.
* `resume` — ADMITTED.
* `manual_advance` — INADMISSIBLE; recommend dropping reserved name.

---

## §6. F59 closure verdict

**F59 INADMISSIBLE.**

No constitutionally-distinct semantic for `manual_advance` exists under the Step 8 / 9 / 10 / 11 + F58 substrate. Theorem T7 establishes this. The reserved name in D-FAULT-9a has empty admissible content. The substrate's authority singularity, scheduler purity, predicate purity, registry mutation discipline, and Phase-E atomicity jointly preclude any envelope kind from acquiring decision-making authority beyond `session_state` transitions and forensic event recording.

The Framework's F42 (kind expansion) is now RESOLVED:
* `pause` / `resume`: ADMITTED via F58 (T6 + D9 + R1).
* `manual_advance`: INADMISSIBLE via F59 (T7).

The reserved-kinds set in D-FAULT-9a should be reduced to `{pause, resume}` in any future contract phase.

**Preserved invariants:**

| invariant | preserved? |
|---|---|
| replay-authoritative truth | ✓ (no new authority added) |
| append-only causality | ✓ (no retroactive edits proposed) |
| deterministic orchestration authority | ✓ (authority singularity defended) |
| orchestration_tick continuity | ✓ (no new tick authority) |
| Phase-A-only observability | ✓ (T3 preserved by rejecting R5) |
| Phase E atomicity | ✓ (D-FAULT-6a preserved by rejecting R5) |
| contradiction preservation | ✓ (D-FAULT-5b unchanged) |
| transport independence | ✓ (vacuously) |
| reopen-stage replay identity | ✓ (no new state introduced) |
| no hidden cleanup | ✓ |
| no wall-clock authority | ✓ |
| no adaptive semantics | ✓ |

No clause weakened. No new authority admitted. No new epoch category introduced.

This document is final for the scope of this session.

---

**End of F59 manual_advance constitutional admissibility analysis.**

Predecessors: [Step 11 admissibility framework](phase_4b_step11_admissibility_framework.md), [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [F58 PAUSED analysis](phase_4b_step11_f58_paused_analysis.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).
