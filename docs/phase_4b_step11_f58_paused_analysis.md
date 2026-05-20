# Phase 4B Step 11 — F58: PAUSED Semantics Constitutional Admissibility

**Status: FOCUSED CONSTITUTIONAL ANALYSIS (2026-05-21).** This document discharges open finding **F58** from the [Step 11 Admissibility Framework](phase_4b_step11_admissibility_framework.md): whether a `PAUSED` SessionState (and the corresponding `pause` / `resume` envelope kinds) can exist under the Step 8 / 9 / 10 / 11 substrate without introducing wall-clock authority, dormant execution epochs, hidden visibility windows, or any other constitutional incompatibility.

**Authority order:**

1. [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md) — authoritative contract; frozen at Step 10 Direction A closure (2026-05-21). Citation-only; not modified.
2. [`phase_4b_step11_admissibility_framework.md`](phase_4b_step11_admissibility_framework.md) — Step 11 framework (Theorems T1–T5, Lemmas L1–L5, Disciplines D1–D8, six-object ontology). Citation-only; this document EXTENDS the framework with T6 + D9 + a refinement R1 to L4. No clause weakening.
3. [`phase_4b_step11_live_ingress_analysis.md`](phase_4b_step11_live_ingress_analysis.md) — Step 11 analysis.
4. This document — F58 analysis.

**Brief's central question.** Treat PAUSED strictly as a deterministic causality and authority-topology problem. Determine whether PAUSED can exist:

* without wall-clock authority;
* without dormant execution epochs;
* without violating replay-authoritative causality;
* without hidden visibility windows;
* without new authority epochs;
* under Phase-A governance;
* with replay-reconstructable pause/resume;
* with constitutionally admissible resume authority;
* preserving D-EXEC, D-SCHED, D-REPLAY unchanged;
* preserving T1–T5 and D1–D8 unchanged.

**Forbidden in this session (per brief):** runtime implementation, coroutine/task suspension proposals, thread-based pause semantics, async resume semantics, callback/signal authority, wall-clock waiting semantics, timer-driven resume semantics, external scheduler authority, hidden execution continuation, replay weakening, comparator weakening, transport-authoritative semantics, semantic healing, adaptive recovery, reactive-runtime proposals.

**Preserved absolutely:** replay-authoritative truth, append-only causality, authoritative `orchestration_tick` semantics, deterministic interruption boundaries, Phase E atomicity, contradiction preservation, transport independence, reopen-stage replay identity, no hidden cleanup, no wall-clock authority, no adaptive semantics.

---

## §A. Scope and analytical posture

### §A.1 What F58 is

F58 is one of nine open findings catalogued in [Framework §P.2](phase_4b_step11_admissibility_framework.md#§p2). The Framework's Threat 7 (PAUSED-as-wall-clock-wait) remains open precisely because the eight Disciplines D1–D8 do not by themselves close it. F58 must determine either:

* there exists a constitutionally admissible PAUSED semantic, AND it requires a ninth discipline (D9) to close Threat 7, OR
* there does NOT exist a constitutionally admissible PAUSED semantic, AND the reserved-but-unimplemented `pause` / `resume` kinds in `D-FAULT-9a` must be retired.

The brief instructs F58 to treat PAUSED as "a potential hidden-time-authority risk surface." This is the correct framing: every conceivable PAUSED design has a wall-clock leakage attack surface, and the question is whether any design closes that surface without violating T1–T5 or D1–D8.

### §A.2 What F58 is NOT

F58 is NOT:

* a contract phase for `pause` / `resume` kinds (kind-expansion contract work depends on F58's verdict but is separate);
* an authoring pass for the kinds' on-the-wire schema (D-FAULT-9 admits envelope_kind expansion as additive; F58 does not enumerate fields);
* an implementation phase (no transport, no session.py edit, no test);
* a UX design (PAUSED is not analyzed as a product feature — see §A.3);
* a runtime-modernization exercise (no async, no coroutines, no thread-based suspension).

### §A.3 The mis-framings to reject

Three popular framings would derail F58. They are rejected up-front:

1. **"PAUSED lets operators pause the simulation."** This is the UX framing. The substrate has no concept of "the simulation"; it has `session.step()` calls and `world.step()` calls inside Phase E. "Pausing the simulation" is an operator-side concept that has no substrate referent until it is decomposed into substrate primitives.

2. **"PAUSED is a wait-state."** A wait-state implies the substrate consumes wall-clock duration without producing trace events. Wall-clock duration is non-authoritative (D-FORBID-6 / D-FORBID-11), so a wait-state has no substrate-observable existence. Either PAUSED produces something observable (events, tick advancement) or it has no constitutional referent at all.

3. **"PAUSED suspends the orchestration tick."** This is the most dangerous framing. orchestration_tick advances per `session.step()` invocation (session.py:854, 875); a suspension that prevents tick advancement would either (a) prevent `session.step()` from being callable (caller-side block, wall-clock authority) or (b) decouple tick advancement from `session.step()` invocations (new clock authority). Both are forbidden.

The correct framing: PAUSED, if admissible at all, must be a **state in which `session.step()` is still callable, orchestration_tick still advances, and Phase A still drains envelopes — but Phases B–G are structurally skipped.** This is the only framing that preserves T1–T5 and admits subsequent analytical scrutiny.

### §A.4 Output structure

The document proceeds as follows. §B enumerates four candidate PAUSED semantics and rejects three; §C states the surviving candidate precisely. §D–§I discharge the brief's named sub-questions (suspension boundary, resume acquisition, tick continuity, dormant epoch, ingress admissibility during PAUSED, contradiction timing). §J handles replay-reconstructability, including a small refinement to Lemma L4 needed for late-arriving envelopes (independently relevant to all live ingress, surfaced by PAUSED). §K–§L verify compatibility with T1–T5 and D1–D8. §M proposes Theorem T6 (PAUSED admissibility theorem); §N proposes Discipline D9 (Caller-Driven PAUSED Cadence). §O closes Threat 7. §P–§Q deliver the verdict. §R discusses downstream implications for F42 (kind expansion). §S–§T list open follow-ons and close.

---

## §B. The PAUSED candidate-semantic

### §B.1 Four conceivable PAUSED shapes

| shape | description | admissibility |
|---|---|---|
| **PA — Blocking-wait** | On `pause` drain, `session.step()` enters a wall-clock blocking primitive (lock, semaphore, condition variable, `time.sleep` loop, OS futex). The session does not return until `resume` arrives via the live channel and unblocks the wait. | **INADMISSIBLE.** Wall-clock authority (D-FORBID-6); per-tick wall-time pacing (D-FORBID-11); transport pushes into session (Discipline D5 violation); breaks Theorem T3 (sub-Phase observation surface implied by the wait). |
| **PB — Tick-suspension** | On `pause` drain, the substrate sets a flag that prevents `orchestration_tick` from advancing on subsequent `session.step()` calls. Calls return immediately as no-ops; tick stays at the pause-tick value until `resume` advances it. | **INADMISSIBLE.** Decouples tick advancement from `session.step()` invocations, violating the implicit invariant that one tick = one call (session.py:854, 875). Replay-identity surface (Lemma L1: K_drain) becomes ambiguous: multiple `session.step()` calls at the same tick value. Authority over `orchestration_tick` shifts from "incremented at end of step" to "incremented conditionally by some other rule," opening hidden-causality vectors. |
| **PC — Caller-side hibernation** | The substrate offers no PAUSED state at all. Instead, operators submit `abort` (terminal) and start a new session later with a different `pending_operator_envelopes`. PAUSED is a caller-side / harness-side concept; the substrate doesn't see it. | **ADMISSIBLE BUT NOT INTERESTING.** This is the "drop pause/resume from D-FAULT-9a" option. It is constitutionally clean (no contract change at all) but eliminates the question. If F58 verdicts as "no admissible substrate-level PAUSED," PC is the residue. |
| **PD — No-op-tick PAUSED** | On `pause` drain, the session transitions RUNNING → PAUSED. While in PAUSED, each `session.step()` call runs Phase A normally (envelope drain), then structurally skips Phases B–G (no scheduler decision, no node execution, no boundary snapshot, no Phase G commit), advances `orchestration_tick`, returns. `resume` drained at Phase A transitions PAUSED → RUNNING; `abort` drained at Phase A transitions PAUSED → ABORTING. | **CANDIDATE FOR ADMISSIBILITY.** This is the only shape consistent with T1–T5 and D1–D8. The remainder of this document analyzes it. |

### §B.2 The hidden-time-authority risk lens

The brief's central lens is hidden-time-authority. Every PAUSED design must be evaluated for whether it introduces any of:

* **Implicit wall-clock observation** (the substrate reads time anywhere on a path that influences orchestration state);
* **Implicit wall-clock pacing** (the substrate gates progress on wall-clock duration);
* **Implicit wall-clock dependency** (orchestration decisions branch on wall-clock state, even diagnostically-observable);
* **Implicit external clock** (a second clock — timer, deadline, retry-budget-in-time — that authoritatively influences state);
* **Implicit suspension clock** (a clock that runs only during PAUSED, separate from `orchestration_tick`).

Shape PA introduces all five. Shape PB introduces #4 and #5 explicitly. Shape PC has none (it has no substrate referent). Shape PD must be analyzed for whether it introduces any covertly.

Shape PD's design intent: the substrate makes ZERO wall-clock observations during PAUSED. The caller drives `session.step()` at whatever wall-clock cadence the caller chooses; the substrate counts only ticks, not seconds. If the caller pauses calling for 10 minutes and resumes, the substrate sees an interval of "however many ticks the caller invoked in that time" — possibly zero. The substrate is wall-clock-blind to PAUSED's wall-clock duration.

This is the only design under which Threat 7 closes. The rest of the analysis verifies that Shape PD, as designed, actually achieves this.

### §B.3 Why PB is the trap

Shape PB is the natural design impulse: "if PAUSED means nothing happens, don't advance the tick." It feels minimal. But it is the most dangerous shape because it decouples two invariants that the substrate has been tightly coupling for ten implementation steps:

* `orchestration_tick` advances once per `session.step()` call.
* Each `session.step()` call corresponds to exactly one orchestration tick of work.

Under PB, the first invariant becomes "advances once per session.step() call **unless paused**" — a conditional that opens countless edge cases. Under PB, replay reconstruction becomes ambiguous: which session.step() call corresponds to which tick? The Drain-Epoch Determinism Lemma (L1) loses its uniqueness property.

Shape PD preserves the invariant: tick advances every step. PAUSED just means the work in Phases B–G is structurally null. The clock keeps ticking; only the labor stops. This is the load-bearing distinction that makes PD admissible and PB inadmissible.

---

## §C. The surviving candidate — Shape PD precisely stated

### §C.1 Semantics

**PAUSED is a SessionState value with the following semantics:**

* Entered when an `OperatorEnvelope` with `kind = "pause"` drains at Phase A of `session.step(K_p)`. The session transitions `RUNNING` → `PAUSED` at this drain. The transition emits a `SessionPaused` event (analogous to `SessionAborting`, with payload `{ trigger_envelope_id, paused_at_tick: K_p, reason }`).
* Exited when an `OperatorEnvelope` with `kind = "resume"` drains at Phase A of `session.step(K_r)` (for some K_r > K_p). The session transitions `PAUSED` → `RUNNING` at this drain. The transition emits a `SessionResumed` event with payload `{ trigger_envelope_id, resumed_at_tick: K_r, paused_at_tick: K_p }`. Alternatively exited when `abort` drains: PAUSED → ABORTING.
* While in PAUSED, each call to `session.step()` does the following AND ONLY the following:
  1. Phase A — drain envelopes per D-FAULT-6, D-FAULT-9, Discipline D2, canonical order per Lemma L3. New envelopes may arrive via live channel pull (Discipline D2) as in any other tick. Drains may include `resume`, `abort`, additional `pause` (idempotent per D-FAULT-7), or any other admitted envelope kind.
  2. Skip Phase B (no scheduler call).
  3. Skip Phase C (no precondition checks — there is no candidate node).
  4. Skip Phase D (no node execution; no executor invocation).
  5. Skip Phase E (no `executor.execute()`).
  6. Skip Phase F (no validator; no verdict).
  7. Skip Phase G (no boundary snapshot; no occupancy commit; no D-LIFE transition).
  8. Increment `_orchestration_tick`.
  9. Return a `SessionRuntimeSnapshot` (whatever the existing return type is) reflecting the unchanged session state.

* The orchestration_tick increment is unconditional with respect to PAUSED. PAUSED is a state of the *work* the session does in a tick, not a state of the *clock*. The clock keeps advancing.

### §C.2 State machine extension

```
                    pause envelope drained at Phase A
                ┌─────────────────────────────────────┐
                ▼                                     │
   ┌───────────────┐                          ┌───────────────┐
   │   RUNNING     │                          │   PAUSED      │
   │ (active node  │  abort drain at Phase A  │ (no node      │
   │  execution)   │ ───────────────────────► │  execution;   │
   └───────────────┘                          │  ticks advance│
        │  ▲                                  │  silently)    │
        │  │                                  └───────────────┘
        │  │ resume envelope drained at Phase A      │
        │  └─────────────────────────────────────────┘
        │                                            │
        │ abort drain at Phase A                     │ abort drain at Phase A
        ▼                                            ▼
   ┌───────────────┐                          ┌───────────────┐
   │   ABORTING    │ ───── close() ────────►  │   ABORTED     │
   └───────────────┘                          └───────────────┘
        │
        │ no abort; all nodes resolved
        ▼
   ┌───────────────┐
   │  COMPLETED    │
   └───────────────┘
```

The state machine is **strictly forward-compatible** with the existing one (RUNNING / ABORTING / ABORTED / COMPLETED / FAILED). PAUSED is interposed between RUNNING and any terminal state without modifying any existing transition. The existing transitions remain:

* RUNNING → ABORTING (abort drained while RUNNING) — unchanged.
* RUNNING → COMPLETED (all nodes resolved while RUNNING) — unchanged.
* ABORTING → ABORTED (close() reached) — unchanged.

PAUSED adds:

* RUNNING → PAUSED (pause drained while RUNNING).
* PAUSED → RUNNING (resume drained while PAUSED).
* PAUSED → ABORTING (abort drained while PAUSED).

This is the **minimum** state-machine extension that admits the candidate. No transition is reversed; no existing transition is qualified. Terminal-from-PAUSED requires going via ABORTING (no direct PAUSED → ABORTED or PAUSED → COMPLETED). This preserves the discipline that the session lifecycle ends only via abort or full-completion paths.

### §C.3 What runs and what does not during PAUSED — exhaustive enumeration

| activity | runs during PAUSED? | citation |
|---|---|---|
| Phase A — envelope drain (pre-queue + live-channel pull per D2) | **YES** | D-FAULT-6, D-FAULT-9, Disciplines D2 + D4 |
| Phase A — canonical-order drain iteration | **YES** | Lemma L3 |
| Phase A — bus emission of `OperatorAbortRequested`, `SessionResumed`, etc. | **YES** | D-BUS-1, D-BUS-3 |
| Phase B — scheduler call | **NO** (structurally skipped) | this document |
| Phase B — `next_runnable_node` purity (D-SCHED-1) | preserved trivially (function not called) | D-SCHED-1 |
| Phase C — precondition evaluation | NO | no candidate node |
| Phase D — `NodeSelected`, `NodeExecutionStarted` emission | NO | no node selected |
| Phase D — pre_node boundary snapshot (D-EXEC-10 item 1) | NO | no node selected |
| Phase E — `executor.execute()` invocation | NO | Phase E atomicity preserved trivially |
| Phase E — `world.step()` calls | NO | no execute() invocation |
| Phase E — interruption predicate construction (D-EXEC-13) | NO | no execute() invocation |
| Phase F — verdict evaluation | NO | no node executed |
| Phase G — boundary snapshot (post_node_sim, post_node_validate) | NO | D-EXEC-10 — these are node-bounded |
| Phase G — `mark_fixture_occupied` (D-CONT-5) | NO | not in PASS pathway |
| Phase G — D-LIFE transitions | NO | D-CONT-5a; no node, no transitions |
| Phase G — `NodeExecutionCompleted`, `TaskCascadeSkipped` emission | NO | no node |
| `_orchestration_tick` advance | **YES** (unconditional) | preserves T1 |
| `SessionRuntimeSnapshot` return from `session.step()` | **YES** | session.py:805 contract |
| Diagnostic state (wall_ns timestamps on emitted events) | **YES** (diagnostic only) | D-SESS-5 |
| `CellStateRegistry` mutation | NO | D-SESS-6: only Phase D / Phase G mutate; both skipped |
| Subscriber dispatch on emitted events | **YES** (synchronous; D-BUS-1) | D-BUS-9 |

This enumeration is exhaustive for the existing substrate. Any sub-activity not listed is either (a) part of Phase A (runs), or (b) part of Phases B–G (does not run).

### §C.4 What this is NOT

PAUSED is NOT:

* a coroutine suspension (no async runtime is introduced);
* a thread pause (no thread is suspended);
* a `world.step()` pause (PhysX has no role here; Phase E doesn't run anyway);
* a timer-driven state (no wall-clock authority);
* a watchdog state (no automatic transition on time);
* a "soft" failure (no D-FAULT-1 class is involved);
* an executor state (the executor doesn't know about PAUSED; it's not called).

PAUSED is exclusively a SessionState value that gates Phase-B-onward execution structurally, while preserving all Phase-A ingress + tick-advancement behavior.

---

## §D. Suspension-boundary semantics

The brief asks: "suspension boundary semantics."

### §D.1 The boundary at RUNNING → PAUSED

The transition RUNNING → PAUSED happens at the Phase A drain of `session.step(K_p)` where `K_p` is the orchestration_tick value at which the `pause` envelope was canonical-eligible and drained.

By the existing Phase-A drain mechanics:

* the pause envelope is in `_pending_envelopes` at the start of Phase A of session.step(K_p) (either pre-queued or live-pulled at this step's Phase A pull);
* eligibility check `requested_at_tick <= K_p` passes;
* canonical-order iteration reaches the pause envelope;
* the session, on encountering a pause envelope while in RUNNING state, transitions to PAUSED;
* emits `OperatorPauseRequested` (the envelope ingress event) and `SessionPaused` (the state-transition event);
* both events have `ts_step = K_p` (Theorem T4 — acquisition and visibility tick-aligned);
* drain continues for any subsequent envelopes at this Phase A (multi-envelope drain, Lemma L3);
* after Phase A completes, the session is in PAUSED. Phase B is structurally skipped per §C.3.
* `_orchestration_tick` increments at end of step to K_p + 1.

The suspension boundary is **the Phase A drain instant of session.step(K_p)**. It is event-recorded (single `SessionPaused` event), tick-aligned (K_p), and single-emitter (the session is the sole emitter, per D-FAULT-2 + Theorem T4).

### §D.2 The interaction with concurrent envelopes at K_p

If multiple envelopes are eligible at session.step(K_p)'s Phase A — e.g. both `pause` and `abort` — canonical order determines which transitions first. Per Lemma L3, drain order is `(requested_at_tick, envelope_id)` lexicographic.

* If pause's canonical-order position < abort's: pause drains first (RUNNING → PAUSED). Then abort drains in the SAME Phase A — the session is now in PAUSED. The abort transitions PAUSED → ABORTING. The final state at end of Phase A is ABORTING. Two transitions in one Phase A; both event-recorded; both single-emitter; D-FAULT-7 idempotency preserved (each transition fires exactly once).
* If abort's canonical-order position < pause's: abort drains first (RUNNING → ABORTING). Then pause drains in the same Phase A. Pause-while-ABORTING is constitutionally a no-op transition — the session is committed to abort; pause has no effect. The pause envelope is still recorded as an `OperatorPauseRequested` event for forensic provenance (D-FAULT-7: "envelope arriving while in ABORTING / ABORTED is recorded but produces no second state transition"). The final state is ABORTING.

Both cases are deterministic and replay-stable. Multi-envelope drain at the suspension boundary is well-defined under existing D-FAULT-7 semantics.

### §D.3 The suspension boundary is not a new epoch

Per Lemma L1, the suspension boundary is a Drain Epoch like any other — `(session_id, K_p)`. It is not a new epoch type. No new authority surface is introduced. The boundary is recorded as a tick value and replay-reproducible by Lemma L4 (with the refinement R1 of §J.2 for late-arrival).

### §D.4 The boundary at PAUSED → RUNNING

Symmetric to §D.1. The resume envelope drains at Phase A of session.step(K_r). The session transitions PAUSED → RUNNING at K_r. Emits `OperatorResumeRequested` and `SessionResumed`, both at `ts_step = K_r`. Phase B of session.step(K_r) is now reached (the session is RUNNING again), and normal scheduler-driven execution resumes within the same tick (K_r).

This is the strongest property of Shape PD: **resume re-enters normal execution within the same `session.step()` invocation that drained it.** No extra tick of latency; no separate "transition tick" needed.

### §D.5 Edge case: resume arriving while not in PAUSED

If a resume envelope drains at Phase A while the session is in RUNNING (e.g. operator submitted resume but the prior pause never drained because it was filtered out earlier), the resume is a no-op transition. Per D-FAULT-7, the envelope is event-recorded as `OperatorResumeRequested` but produces no state change.

This case is operationally unlikely but constitutionally well-defined. Future contract phase should write a clause stating "resume while in non-PAUSED state is a forensic no-op."

---

## §E. Resume-acquisition semantics

The brief asks: "resume acquisition semantics."

### §E.1 Resume as ingress, not as control

The resume envelope is a `kind = "resume"` envelope. It is admitted through the same ingress surface as `pause` and `abort`: pre-queue or live-channel pull at Phase A, canonical-order drain, single-emitter at the session, idempotency at the transition.

There is no other resume pathway. Specifically:

* there is no `session.resume()` method (D-FAULT-15 #16: method-as-ingress forbidden);
* there is no callback that triggers resume (Discipline D5: pull-only);
* there is no timer that auto-resumes after wall-clock duration (D-FORBID-6);
* there is no precondition-driven resume (resume is operator-driven, not state-driven);
* there is no resume-on-recovery-node-entry (D-FAULT-8 / D-FAULT-15 #15: topology-derived authority forbidden).

The resume envelope is the **sole** mechanism to exit PAUSED other than abort. This preserves single-emitter discipline.

### §E.2 Resume's authority is the same authority as abort

D-FAULT-2 says each failure class has exactly one origin authority. PAUSED is not a failure class — it is a session lifecycle state that is neither failed nor completed. But the same single-emitter discipline applies to its transitions: only `ExecutionSession.step()`, processing a drained envelope at Phase A, may transition into or out of PAUSED.

There is no second emitter:

* the executor does not emit resume (it is not called during PAUSED);
* the bus does not emit resume (the bus dispatches events; it doesn't drive transitions);
* the channel does not emit resume (Discipline D1: channel opacity);
* subscribers do not drive resume (D-SESS-7: subscribers may not mutate session state);
* the scheduler does not drive resume (Discipline D6 + scheduler purity D-SCHED-1: not called during PAUSED).

### §E.3 Resume is not "the operator's intent" — it is the envelope content

The substrate observes the envelope, not the operator's intent. Two resume envelopes with the same content (kind, requested_at_tick, reason) produce the same envelope_id by content-addressing (D-FAULT-9 + `derive_envelope_id`). The substrate cannot distinguish them.

This is constitutionally significant: a resume envelope is fully described by its (kind, requested_at_tick, reason) tuple. Replay reconstructs from these three fields. No operator-side state is needed for replay-identity.

### §E.4 Resume drained while in ABORTING is no-op

If the session is in ABORTING (operator already aborted) and a resume drains at Phase A, the resume is forensic-only. D-FAULT-7 idempotency: cancellation is idempotent at the transition; subsequent envelopes are recorded but do not re-transition.

There is no mechanism to "un-abort." Abort is terminal. This is consistent with the existing substrate and is not weakened by PAUSED.

### §E.5 Acquisition timing

Acquisition (PAUSED → RUNNING) and visibility (`SessionResumed` event) are tick-aligned at K_r per Theorem T4. The session's `session_state` field becomes RUNNING at the same instant the bus emits the event — both within Phase A of session.step(K_r).

After the transition within Phase A, Phase B of session.step(K_r) proceeds normally: scheduler is called, node is selected, and the rest of the tick executes the selected node. This means **the first work after resume happens in the same tick that drained resume**. No "wake-up tick" delay.

---

## §F. Orchestration_tick continuity under PAUSED

The brief asks: "whether orchestration_tick continuity survives PAUSED states."

### §F.1 The continuity claim

Under Shape PD, `orchestration_tick` advances by exactly 1 at the end of every `session.step()` invocation, regardless of session_state. PAUSED is no exception: each PAUSED-while-in-PAUSED `session.step()` call advances the tick.

This preserves the load-bearing invariant of Theorem T1: **`orchestration_tick` is a strictly monotone gap-free integer counter, advancing once per `session.step()` call.** PAUSED does not introduce a "frozen tick" or "tick gaps."

### §F.2 Why this matters for replay-identity

Lemma L1 (Drain-Epoch Determinism) says K_drain(E) is replay-stable: a fresh session sees the envelope drained at the same orchestration_tick as the original. This depends on the tick advancing at the same rate in both runs.

Under Shape PD, the tick advances uniformly (one per step call) in both original and replay. For replay to produce the same drain ticks, the replay caller must invoke `session.step()` the same number of times as the original. This is the **caller-cadence-equivalence** requirement (formalized in §J.2's Refinement R1).

Under Shape PB (rejected), tick advancement is conditional, breaking this invariant.

### §F.3 The "silent ticks" question

During PAUSED, most `session.step()` calls emit zero events (Phase A may drain envelopes; Phases B–G are skipped). These are **silent ticks**.

Silent ticks do not advance the seq counter (no events emitted), but they DO advance `orchestration_tick` (per §F.1). After 100 silent PAUSED ticks, `_orchestration_tick` has advanced by 100, but the trace's `seq` counter has not advanced at all.

This is constitutionally significant: orchestration_tick and seq are two independent monotone counters. Their values can diverge (orchestration_tick > seq) but never reverse (seq does not exceed orchestration_tick within reason; orchestration_tick does not decrement). Silent ticks make orchestration_tick > seq more dramatic but do not change the monotonicity.

For replay-identity purposes: the trace has no record of how many silent ticks were invoked. Replay can only reconstruct orchestration_tick values from the `ts_step` field on events. If two events are separated by 100 silent ticks in the original, replay can match this IF its caller invokes session.step() exactly 100 times between the two corresponding events.

This is the second piece of caller-cadence-equivalence (formalized in §J.2).

### §F.4 The "PAUSED forever" question

If a session enters PAUSED and never receives resume (or abort), and the caller keeps invoking `session.step()`, the session ticks forever in PAUSED — silent ticks, advancing tick, never producing events. This is a liveness concern, not a determinism concern. The substrate is replay-deterministic; whether it makes operational progress depends on the caller and on whether a resume/abort eventually arrives.

D-FORBID-11 (per-tick wall-time pacing forbidden) already cedes pacing to the caller. PAUSED-forever is a caller-cadence outcome; the substrate is unconcerned.

If the caller stops invoking session.step() during PAUSED (also a possibility), the session simply ceases to make progress until invocation resumes. orchestration_tick stops advancing because the substrate isn't being called. This is the **null-cadence** case; it is constitutionally clean (no ticks, no work, no events — equivalent to the substrate being dormant).

### §F.5 Continuity verdict

**Orchestration_tick continuity is preserved under PAUSED.** PAUSED does not introduce tick gaps, tick reversals, or conditional advancement. The clock keeps ticking deterministically; only the work in the ticks is structurally skipped.

---

## §G. Dormant-epoch analysis

The brief asks: "whether paused intervals are semantic or merely observational" and "whether PAUSED creates dormant execution epochs."

### §G.1 What "dormant epoch" might mean

A "dormant epoch" could mean any of:

1. **Tick value with no events** — a silent tick. Trivially possible (already exists in the substrate: any session.step() that drains no envelopes and finds no runnable node is silent — session.py:874 already handles this).
2. **An interval of ticks with no scheduler activity** — a PAUSED interval. Also already possible under existing substrate (a job whose nodes all fail or block could leave the session running idle).
3. **A new clock dimension** — a "PAUSED clock" that runs only during PAUSED, separate from `orchestration_tick`. **Inadmissible** — would violate Theorem T1 and introduce hidden time authority.
4. **A new observation surface** — events emitted on a different boundary than Phase G. **Inadmissible** — violates D-EXEC-1, Theorem T3.

Under Shape PD, dormant epochs of type (1) and (2) exist trivially. They do NOT constitute new constitutional epochs in the sense of §H of the [Framework](phase_4b_step11_admissibility_framework.md#§h-deterministic-epoch-requirement-analysis-q5) — they are *absences of work*, not new authoritative-observation surfaces.

Dormant epochs of type (3) and (4) are forbidden and Shape PD does not introduce them.

### §G.2 Are PAUSED intervals "semantic" or "merely observational"?

The brief asks this distinction directly.

**Semantic** would mean: the substrate observes a structural property of PAUSED that influences orchestration decisions (e.g. "after 100 ticks in PAUSED, auto-resume" — that would be semantic). Shape PD has no such property. PAUSED is opaque to the substrate beyond "don't run Phase B–G."

**Observational** would mean: external observers can see the PAUSED state (via the manifest or via subscriber dispatch), but the substrate does not condition decisions on PAUSED-interval properties.

Shape PD makes PAUSED **observational but not semantic** in the brief's sense. The session_state field reflects PAUSED; the trace records the `SessionPaused` and `SessionResumed` event pair; observers may compute "PAUSED duration in ticks" as `K_r - K_p`. But the substrate's decisions (scheduler, predicate, validator, registry mutation) do not depend on PAUSED-interval properties beyond "is session_state PAUSED right now?"

This means PAUSED is a **boolean gate** on Phase B–G, not a continuous-valued state. It has two values (in or out), and the only authority that toggles it is envelope drain at Phase A. No other property of PAUSED is observable to substrate decisions.

### §G.3 The dormant-epoch verdict

PAUSED does NOT introduce new constitutional epochs. The silent ticks during PAUSED are observationally distinguishable (their orchestration_tick values appear in the trace via Phase A drain events when envelopes arrive) but not semantically privileged. They are not a new clock, not a new observation surface, not a new authority.

The Phase-A boundary remains the unique authoritative-observation epoch under PAUSED, exactly as under RUNNING. Theorem T3 (Phase-A-Only Observability) is preserved.

---

## §H. Ingress admissibility during PAUSED

The brief asks: "ingress admissibility while paused."

### §H.1 What ingress is permitted during PAUSED

During PAUSED, Phase A runs normally. The full ingress surface is active:

* live-channel pull (if live ingress is admitted under the channel-as-opaque-buffer topology — F58 does NOT depend on live ingress; both are independent investigations);
* `_pending_envelopes` drain in canonical order;
* envelope kinds: any kind admissible under the current substrate, currently `abort`. Under a hypothetical contract phase that admits `pause` / `resume`, those drain too.

If `abort` drains during PAUSED: session transitions PAUSED → ABORTING. Same single-emitter, same canonical order. Cascade-skip remaining pending nodes per D-FAULT-3.

If `resume` drains during PAUSED: session transitions PAUSED → RUNNING. Phase B of this same step proceeds (per §D.4).

If `pause` drains during PAUSED: forensic no-op (D-FAULT-7 idempotency; the session is already PAUSED). Event recorded.

If a hypothetical future kind drains: F58 makes no claim; depends on that kind's own admissibility analysis.

### §H.2 Why ingress during PAUSED is constitutionally clean

The session is the sole drain authority (D-SESS-1). Phase A drain is the sole ingress observation surface (Theorem T3). Canonical order applies (Lemma L3). Single-emitter discipline applies (D-FAULT-2). These do not depend on session_state; they are tick-level invariants.

Therefore, ingress during PAUSED is mechanically identical to ingress during RUNNING. The session_state determines what the drain ultimately *does* (transition or no-op), but the drain mechanism itself is invariant.

### §H.3 Multi-envelope drain during PAUSED

If multiple envelopes drain in one Phase A while session is PAUSED, canonical order applies and each is processed in order:

* a `resume` drained first followed by an `abort`: session transitions PAUSED → RUNNING (resume) → ABORTING (abort). Two transitions in one Phase A; both event-recorded; both single-emitter.
* an `abort` drained first followed by a `resume`: PAUSED → ABORTING (abort). Then resume is forensic-only (session is now in ABORTING). One transition; one forensic event.
* multiple `resume`s: first transitions PAUSED → RUNNING; subsequent are forensic-only (session is RUNNING). One transition; rest forensic.
* multiple `abort`s: first transitions PAUSED → ABORTING; subsequent are forensic-only. One transition; rest forensic.

All cases are deterministic, replay-stable, and single-emitter. D-FAULT-7 covers the idempotency exhaustively.

### §H.4 Ingress admissibility verdict

PAUSED does NOT restrict, alter, or modify the ingress admissibility surface in any way. Ingress during PAUSED is mechanically identical to ingress during RUNNING. The only difference is which transitions the envelopes drive.

---

## §I. Contradiction-timing analysis

The brief asks: "contradiction timing during PAUSED intervals."

### §I.1 The substrate's contradiction class

D-FAULT-5b establishes a class of contradictions: post-failure retained-state contradictions where the canonical pose is "last-tick truth" but the fixture occupancy says "empty" (or vice versa). Step 10 Direction A Phase 6 empirically verified one such contradiction (Scenario F) on real PhysX.

Contradictions are produced by node executions that fail mid-trajectory. They are recorded in the post-failure boundary snapshot (D-CONT-6). They persist until either (a) a recovery node fires (D-FAULT-8) and resolves them, or (b) the session terminates carrying the contradiction in the terminal snapshot.

### §I.2 Contradictions during PAUSED

PAUSED is entered from RUNNING. The session's state at the moment of RUNNING → PAUSED is whatever the previous node-completion left:

* if the previous node PASSed: no contradiction (PASS path commits via D-CONT-5);
* if the previous node FAILed: contradiction state per D-FAULT-5b (peg attached + fixture empty + last-tick pose) is in the registry, captured by the post-failure boundary snapshot at Phase G of that failed node.

PAUSED preserves whatever state the registry has at the moment of entry. During PAUSED:

* no Phase D (no executor; no PhysX mutation);
* no Phase G (no boundary snapshot; no occupancy commit; no D-LIFE transition);
* the `CellStateRegistry` is not mutated (D-SESS-6: registry mutation is at Phase D or Phase G; both are structurally skipped).

Therefore: **the contradiction state at PAUSED entry equals the contradiction state at PAUSED exit (resume or abort).** PAUSED is contradiction-neutral: it does not create, alter, or resolve contradictions.

### §I.3 The "contradiction lifetime extension" question

PAUSED extends the wall-clock lifetime of any existing contradiction. The substrate observes this as a tick-count extension (K_r - K_p ticks of additional silent existence). It is not authoritative — orchestration decisions do not branch on contradiction-lifetime properties.

If the operator desires to abort during PAUSED rather than resume, the contradiction is carried into the terminal ABORTED state per D-FAULT-5b verbatim. This is identical to aborting a session in any other state that holds a contradiction.

### §I.4 Multi-pause / multi-resume contradiction stability

If a session enters PAUSED, resumes, then enters PAUSED again (without any node execution in between), the contradiction state is the same at all four PAUSED-boundary transitions. There is no contradiction drift across multiple PAUSED intervals.

If a node executes between PAUSED intervals (RUNNING → PAUSED → RUNNING → run a node, PASS or FAIL → PAUSED again), the contradiction state may differ at the second PAUSED entry vs the first. This is governed by D-FAULT-5b and Phase G commit semantics, unchanged by PAUSED.

### §I.5 Replay-reconstructable contradiction timing

Lemma L2 (Epoch-Identity) implies: if original drained pause at K_p and resume at K_r (and analogously for replay), and the same intervening nodes executed (or were skipped) at the same orchestration_ticks, then the contradiction state at every tick in [K_p, K_r] is identical between original and replay. Replay reproduces the contradiction timing byte-equal.

### §I.6 Contradiction-timing verdict

PAUSED preserves contradiction timing trivially. No contradiction is created, altered, or resolved during PAUSED. Replay-reconstruction of contradiction state is identical to replay-reconstruction in non-PAUSED runs. D-FAULT-5b is preserved verbatim.

---

## §J. Replay-reconstructability of pause/resume

The brief asks: "whether pause/resume semantics are replay-reconstructable" and "whether replay identity can remain transport-independent under pause/resume."

### §J.1 The early-arrival case

Define **early-arrival** as the case where an envelope arrives in the live channel before its `requested_at_tick` value. The Phase-A pull at orchestration_tick K_pull captures the envelope; if K_pull < envelope.requested_at_tick, the envelope is added to `_pending_envelopes` but is not yet eligible (`requested_at_tick > _orchestration_tick`). At a later Phase A where orchestration_tick reaches envelope.requested_at_tick, eligibility passes and the envelope drains.

In this case:

* K_drain = envelope.requested_at_tick (drains at the eligibility-tick exactly);
* Replay reconstructs envelope with the same content (same envelope_id by content-addressing);
* Replay's session pre-queues the envelope at session.begin();
* Replay's drain happens at the first eligible Phase A = orchestration_tick = envelope.requested_at_tick;
* K_drain(original) = K_drain(replay). ✓

Early-arrival is **trivially replay-reconstructable** under Lemma L4 as stated in the framework.

### §J.2 The late-arrival case — Refinement R1 to Lemma L4

Define **late-arrival** as the case where an envelope arrives in the live channel after its `requested_at_tick` value has passed. The Phase-A pull at K_pull captures the envelope; if K_pull >= envelope.requested_at_tick, the envelope is eligible immediately. Drain happens at K_pull, NOT at envelope.requested_at_tick.

In this case:

* K_drain = K_pull (the actual Phase A drain tick);
* Replay reconstructs envelope with the same content (same envelope_id);
* Replay's session pre-queues the envelope at session.begin();
* Replay's drain happens at the first eligible Phase A. With the envelope in the pre-queue from session.begin(), this is orchestration_tick = envelope.requested_at_tick;
* K_drain(replay) = envelope.requested_at_tick;
* K_drain(original) = K_pull > envelope.requested_at_tick = K_drain(replay);
* **K_drain(original) ≠ K_drain(replay).** Trace `ts_step` values differ. Bytewise replay-identity **FAILS** under the framework's L4 as stated.

This is a real issue. F58 surfaces it because PAUSED's `resume` envelope is the prototypical late-arrival case: the operator submits resume without knowing what orchestration_tick the session is at, typically with `requested_at_tick = 0` or a small value, so arrival is almost always late relative to the eligibility gate.

**Refinement R1 to Lemma L4 (proposed for the Framework).**

For replay to reproduce K_drain(original) under late-arrival, the replay-reconstruction primitive must capture both `envelope.requested_at_tick` AND the actual drain tick K_drain. The trace already records both: payload's `requested_at_tick` is the envelope's gate; event's `ts_step` is K_drain. Replay reconstruction proceeds in two steps:

* **Step 1 (envelope-content reconstruction):** For each `OperatorAbortRequested` / `OperatorPauseRequested` / `OperatorResumeRequested` event in the trace, reconstruct the original `OperatorEnvelope` using payload's `(kind, requested_at_tick, reason)`. The envelope_id is derived by content-addressing, matching the original.
* **Step 2 (scheduled-injection reconstruction):** Replay's session, instead of receiving the envelopes in `pending_operator_envelopes` at session.begin(), receives a **scheduled-injection table** mapping each envelope to its recorded `ts_step` (drain tick). At each Phase A, replay injects envelopes whose scheduled drain tick equals `_orchestration_tick` into `_pending_envelopes` AND THEN runs the existing canonical-order drain. The injection happens in canonical order if multiple envelopes are scheduled at the same tick.

Under Refinement R1, replay reproduces K_drain(original) for every envelope, including late-arrivals. Trace `ts_step` values match. Bytewise replay-identity holds.

**Properties of R1:**

* The replay tool's reconstruction primitive becomes "schedule-injection," a strict superset of "pre-queue." The pre-queue case is recovered by setting scheduled-injection tick = envelope.requested_at_tick.
* No contract change is required: the trace already records both fields. R1 is a refinement to the *replay-tool's reconstruction algorithm*, not to substrate clauses. The substrate's `ExecutionSession` is unchanged.
* R1 does NOT introduce a "scheduled arrival" surface to the production runtime. The production runtime still receives envelopes via live channel pull + pre-queue. R1 is replay-tool-only.
* Transport-independence (Theorem T5) is preserved: the replay tool reads the trace, not the original transport.
* Lemma L4 as stated remains true *under R1*: the trace IS sufficient for byte-equal replay reconstruction, provided the reconstruction primitive is R1-extended.

### §J.3 Transport-independence under pause/resume

The brief asks whether replay identity remains transport-independent under pause/resume.

Under Refinement R1: **YES, fully.** The replay tool's scheduled-injection mechanism reads only the trace (events.jsonl). It does not need access to the original transport. Two transports delivering different envelope sets to two different production sessions produce different traces (by Lemma L2); within each session, the trace alone replays it byte-equal.

This preserves Theorem T5 (Transport-Independence) verbatim.

### §J.4 The PAUSED-specific replay-identity scenario

A typical PAUSED scenario in the trace:

* `OperatorPauseRequested` event at `ts_step = K_p`, payload `requested_at_tick = K_p_req` (with K_p_req <= K_p).
* (silent ticks K_p+1, K_p+2, ...; no events emitted).
* `OperatorResumeRequested` event at `ts_step = K_r`, payload `requested_at_tick = K_r_req` (with K_r_req <= K_r).
* `SessionResumed` event at `ts_step = K_r`.

For replay-identity:

* Under R1 (scheduled-injection): pause is scheduled for K_p, resume is scheduled for K_r. Replay caller invokes session.step() at least K_r + 1 times. At step K_p, pause is injected, drained, transitions RUNNING → PAUSED. Silent ticks K_p+1 ... K_r-1. At step K_r, resume is injected, drained, transitions PAUSED → RUNNING. Trace byte-equal to original. ✓

* Under bare L4 (pre-queue only): pause's requested_at_tick = K_p_req <= K_p; pre-queue drains pause at orchestration_tick = K_p_req (the first eligible step). If K_p_req < K_p, replay's pause drains *before* the original's pause did. ✗

So R1 is **required** for byte-equal replay-identity of pause/resume in the late-arrival case.

### §J.5 Could PAUSED enforce K_p_req == K_p?

A contract-level alternative: require that any envelope drained via live ingress have `requested_at_tick == drain_tick`. The transport-layer or the session itself could refuse envelopes that "missed their tick." This would make late-arrival impossible by convention.

Drawbacks:

* requires the operator to know the orchestration_tick at submission time (operator-side concern; the substrate exposes orchestration_tick via the manifest and per-tick snapshots, but not in real-time);
* introduces a refusal pathway (envelopes that arrive late are rejected; this is itself an authority surface that needs analysis);
* breaks the "forward-looking gate" semantic of `requested_at_tick` established in Framework §C.3.

R1 (scheduled-injection replay) is the cleaner option. F58's recommendation is to adopt R1 as a framework refinement and to leave the late-arrival case admissible at runtime.

### §J.6 Pause/resume replay-reconstructability verdict

**YES, pause/resume is replay-reconstructable, with the small refinement R1 to Lemma L4's reconstruction primitive.** The substrate's contract surface is unchanged; the replay-tool's algorithm is extended from "pre-queue only" to "scheduled-injection." Transport-independence is preserved.

R1 is independently relevant to all live ingress (Step 11 channel mechanism, irrespective of PAUSED). F58 surfaces it; the next framework iteration should incorporate it.

---

## §K. Compatibility with Theorems T1–T5

This section verifies Shape PD against the Framework's five theorems.

### §K.1 T1 (Tick Non-Commensurability) under PAUSED

T1 asserts orchestration_tick and world.step count are non-commensurable clocks. Under PAUSED, world.step() is not called (Phase E does not run). orchestration_tick continues to advance per session.step() invocation.

**Effect on T1:** the world.step counter is frozen during PAUSED (no Phase E). The orchestration_tick continues. The two clocks remain non-commensurable; their ratio (which is meaningful only inside an active Phase E) is undefined during PAUSED. No new clock is introduced.

**T1 preserved.** ✓

### §K.2 T2 (N2-Only-Interruption Impossibility) under PAUSED

T2 asserts that an envelope arriving mid-Phase-E of node N cannot acquire in-tick authority. PAUSED is irrelevant to this theorem: during PAUSED, no node is executing (Phase E does not run), so no mid-Phase-E arrival is possible by definition.

A new scenario PAUSED introduces: an envelope arriving during a PAUSED silent tick. This is NOT a mid-Phase-E case — there is no Phase E in flight. The envelope is captured by the channel and pulled at the next Phase A drain (the next session.step() invocation). Latency floor for PAUSED-arrived envelopes is one tick (next session.step()), bounded above by the caller's cadence.

**Effect on T2:** PAUSED does not introduce new mid-Phase-E scenarios. T2's domain is unaffected.

**T2 preserved.** ✓

### §K.3 T3 (Phase-A-Only Ingress Observability) under PAUSED

T3 asserts Phase A is the only observation surface for ingress within one tick. Under PAUSED, Phase A still runs in every session.step() invocation. Phases B–G are skipped, but no new observation surface is introduced: the channel is still observed only at Phase A; envelopes still drain only at Phase A; events still emit only at Phase A (during PAUSED, no other phase emits — Phases B–G are structurally skipped).

**Effect on T3:** PAUSED reduces the set of phases that emit events (only Phase A emits during PAUSED). This is a strict subset of the existing event-emission surface, not an extension. T3 remains satisfied trivially.

**T3 preserved.** ✓

### §K.4 T4 (Acquisition-Visibility Tick Alignment) under PAUSED

T4 asserts acquisition and visibility happen within the same orchestration_tick. Under PAUSED:

* pause drain at K_p: acquisition (RUNNING → PAUSED) and visibility (`SessionPaused` event) both at K_p.
* resume drain at K_r: acquisition (PAUSED → RUNNING) and visibility (`SessionResumed` event) both at K_r.
* abort drain during PAUSED at K_a: acquisition (PAUSED → ABORTING) and visibility (`SessionAborting` event) both at K_a.

In all cases, the transition and its event emission are co-located within the same Phase A drain, which is within session.step(K)'s Phase A, with orchestration_tick = K throughout.

**Effect on T4:** PAUSED's transitions follow the same Phase-A-aligned acquisition-visibility pattern as abort transitions. T4 is satisfied trivially.

**T4 preserved.** ✓

### §K.5 T5 (Transport-Independence) under PAUSED

T5 asserts substrate behavior is invariant under transport choice. Under PAUSED:

* the substrate makes zero wall-clock observations (per Shape PD's design);
* the live channel is opaque to the substrate (Discipline D1);
* the replay tool reads only the trace (Lemma L4 + Refinement R1);
* two transports delivering the same envelope set at the same drain epochs produce byte-equal trace, regardless of underlying transport mechanism.

**Effect on T5:** PAUSED preserves transport-independence verbatim. The wall-clock duration of PAUSED depends on the caller's cadence and on transport delivery latency, but the substrate's view of PAUSED depends only on tick counts and envelope drain events.

**T5 preserved.** ✓

### §K.6 T1–T5 compatibility verdict

All five theorems are preserved under Shape PD. PAUSED does not require modification, qualification, or weakening of any theorem.

---

## §L. Compatibility with Disciplines D1–D8

This section verifies Shape PD against the Framework's eight disciplines.

### §L.1 D1 (Channel Opacity) under PAUSED

PAUSED does not change the channel's role. The channel remains a passive store; the session pulls at Phase A; the channel emits nothing. **D1 preserved.**

### §L.2 D2 (Phase-A-Only Pull) under PAUSED

PAUSED preserves the single-pull-per-step discipline. Every session.step() invocation (including PAUSED ones) pulls the channel exactly once at Phase A. **D2 preserved.**

### §L.3 D3 (Strict Atomic Snapshot) under PAUSED

The pull's atomic-snapshot mechanism is unchanged under PAUSED. **D3 preserved.**

### §L.4 D4 (Canonical-Order Discipline) under PAUSED

Canonical-order drain applies to envelopes pulled during PAUSED ticks identically to RUNNING ticks. **D4 preserved.**

### §L.5 D5 (Pull-Only Direction) under PAUSED

The channel never pushes to the session, regardless of session_state. No callback, no notification, no signal. **D5 preserved.**

### §L.6 D6 (Predicate Closure Stability) under PAUSED

The interruption predicate is constructed at Phase D execute-entry. Under PAUSED, Phase D does not run; no predicate is constructed; nothing depends on predicate-closure stability during PAUSED. The discipline is vacuously preserved.

When the session resumes (PAUSED → RUNNING) and a node is selected, Phase D constructs a predicate per D-EXEC-13. The predicate closes over `_pending_envelopes` as it stands at execute-entry, which may include envelopes pulled during the PAUSED interval (if live ingress is admitted). This is mechanically identical to predicate-closure under any other RUNNING tick.

**D6 preserved.**

### §L.7 D7 (Per-Session Channel Lifecycle) under PAUSED

The channel is per-session. PAUSED does not extend or otherwise modify the channel's lifecycle. The channel is constructed at or before session.begin() and torn down at session.close(). PAUSED does not introduce cross-session leakage. **D7 preserved.**

### §L.8 D8 (Diagnostic Boundary) under PAUSED

PAUSED does not introduce any new authoritative fields on envelopes or events. Diagnostic fields (wall_ns timestamps on `SessionPaused` / `SessionResumed` events) are subject to D-SESS-5 (not read by orchestration logic). **D8 preserved.**

### §L.9 D1–D8 compatibility verdict

All eight disciplines are preserved under Shape PD. PAUSED does not require modification of any discipline.

---

## §M. Theorem T6 — PAUSED Constitutional Admissibility

The framework's central output for F58 is the following candidate theorem:

### §M.1 Statement

**Theorem T6 — PAUSED Constitutional Admissibility.** A SessionState value `PAUSED`, with the following five properties, is constitutionally admissible under the Step 8 / 9 / 10 / 11 substrate:

1. **Phase-A-governed transitions.** Both transitions into and out of PAUSED (RUNNING → PAUSED via `pause` envelope; PAUSED → RUNNING via `resume` envelope; PAUSED → ABORTING via `abort` envelope) occur exclusively at Phase A drain. No other phase, no other authority, may transition into or out of PAUSED.

2. **Phase B–G structural skip.** During PAUSED, each session.step() invocation runs Phase A normally and structurally skips Phases B through G. No scheduler call, no predicate construction, no executor invocation, no boundary snapshot, no registry mutation, no Phase G commit.

3. **orchestration_tick continuity.** `_orchestration_tick` advances by exactly 1 at the end of every session.step() invocation regardless of session_state, including during PAUSED. PAUSED does not freeze, gate, or otherwise interfere with tick advancement.

4. **No wall-clock observation.** The substrate makes zero wall-clock observations during PAUSED. No `time.time()`, no `time.monotonic()`, no `time.sleep()`, no `time.perf_counter()`. The wall-clock duration of PAUSED is determined entirely by the caller's cadence in invoking session.step().

5. **Single-emitter discipline preserved.** Only `ExecutionSession.step()`, processing a drained envelope at Phase A, may transition into or out of PAUSED. No method-as-ingress (D-FAULT-15 #16). No callback (Discipline D5). No timer (D-FORBID-6). No second emitter.

### §M.2 Proof sketch

Under properties (1)–(5), Theorems T1–T5 and Disciplines D1–D8 are preserved per §K and §L. Threat 7 (PAUSED-as-wall-clock-wait) is closed per (4). The contract surface is purely additive: a new SessionState value, two new event types (`SessionPaused`, `SessionResumed`), two new envelope kinds (`pause`, `resume`), and one new discipline (D9 below). No existing clause is modified. ∎

### §M.3 Citation chain

§B (candidate enumeration); §C (Shape PD specification); §D–§I (sub-question discharges); §J (replay-reconstructability under Refinement R1); §K–§L (T1–T5 + D1–D8 compatibility audits); §O below (Threat 7 closure).

### §M.4 Classification

**NORMATIVE-CANDIDATE.** T6 would be authored as a new clause in a future Step 11 contract phase, alongside any new clauses for `pause` / `resume` envelope kinds and the proposed Discipline D9. The clause body is essentially the five-property enumeration of §M.1.

### §M.5 Non-conditions

T6 does NOT assert:

* that PAUSED is operationally useful (it is a substrate primitive; usefulness is operator-side);
* that PAUSED solves any specific orchestration problem (it provides a deterministic deferred-decision state, nothing more);
* that PAUSED is the only admissible deferred-decision state (other primitives may be admissible in future analyses);
* that PAUSED admits arbitrary nesting (multi-pause is handled by D-FAULT-7 idempotency; semantics are forensic-only for repeated pauses);
* that PAUSED is required (Shape PC — drop pause/resume from D-FAULT-9a — remains a constitutionally clean residue).

---

## §N. Discipline D9 — Caller-Driven PAUSED Cadence

### §N.1 Statement

**Discipline D9 — Caller-Driven PAUSED Cadence.** During PAUSED, the substrate makes no wall-clock observations and consumes no wall-clock duration internally. The wall-clock duration of any PAUSED interval is determined entirely by the cadence at which the caller invokes `session.step()`. The substrate counts only orchestration_ticks; the substrate does not measure, gate on, or observe wall-clock duration during PAUSED.

### §N.2 What D9 forbids

D9 specifically forbids:

* any blocking primitive inside `session.step()` that consumes wall-clock duration (no `lock.acquire(timeout=...)`, no `condition.wait()`, no `time.sleep()`, no spin-wait, no busy-loop);
* any conditional advancement of `_orchestration_tick` based on session_state (the tick advances unconditionally per call);
* any auto-resume mechanism triggered by wall-clock duration ("if PAUSED for N seconds, resume");
* any deadline mechanism ("PAUSED times out after N ticks" — would re-introduce tick-as-time-proxy);
* any internal substrate clock that runs only during PAUSED.

### §N.3 What D9 admits

D9 admits:

* the channel transport using its own internal threading for arrival reception (transport is out-of-substrate; D-FORBID-1 reading per Framework §K.3 of the Analysis);
* the caller using wall-clock to determine when to invoke `session.step()` (this is caller-side; the substrate is wall-clock-blind);
* operators submitting envelopes at any wall-clock instant (the substrate observes them only via Phase A pull; arrival instant is non-authoritative).

### §N.4 Threat 7 closure mechanism

D9 closes Threat 7 (PAUSED-as-wall-clock-wait) by forbidding the substrate from observing wall-clock during PAUSED. The threat's substantive risk — that PAUSED becomes a wall-clock-bound waiting state with hidden time authority — is structurally impossible under D9.

### §N.5 Classification

**NORMATIVE-CANDIDATE.** D9 extends the Framework's Eight Disciplines (D1–D8) to nine. It is required to close the eighth open threat surface from Framework §K.

### §N.6 D9's relationship to existing forbidden patterns

D9 is partially redundant with existing prohibitions:

* D-FORBID-6 already forbids wall-clock-dependent behavior in orchestration code;
* D-FORBID-11 already forbids per-tick wall-time pacing;
* Framework's proposed D-FAULT-15 row #38 forbids wall-clock blocking in PAUSED state specifically.

D9 is a positive statement of these prohibitions specifically in the PAUSED context. Its value is in making the prohibition citable and explicit: "violates D9 — substrate observes wall-clock during PAUSED."

---

## §O. Closure of Threat 7

The Framework's Threat 7 was: "PAUSED-as-wall-clock-wait" — the temptation to implement PAUSED as a blocking primitive that consumes wall-clock duration in the session's main thread.

### §O.1 Threat 7's substantive mechanism

A live channel implementation, on receiving a `pause` envelope, could:

* set the session's state to PAUSED;
* call `condition.wait()` or equivalent in `session.step()`'s execution path;
* block until a `resume` envelope arrives via the live channel and signals the condition.

Under this hypothetical implementation: `session.step()` does not return until resume arrives. The substrate is wall-clock-bound. Replay-determinism is preserved IF the trace records pause and resume events (which it would), but the substrate's operational model has become caller-thread-blocking.

### §O.2 Why Threat 7 is constitutionally incompatible

Several substrate invariants are violated:

* **D-FORBID-11** (per-tick wall-time pacing) — the blocking is wall-time pacing.
* **D-FORBID-6** (wall-clock-dependent behavior) — the blocking is a wall-clock-conditional behavior.
* **Discipline D5** (pull-only direction) — the resume's arrival must signal the condition, requiring channel-to-session push.
* **Theorem T3** (Phase-A-only observability) — the blocking implicitly creates a sub-tick observation surface (the moment the condition is signaled).
* **Theorem T4** (acquisition-visibility tick alignment) — the resume event would be emitted at some orchestration_tick K_r that is determined by wall-clock timing rather than by deterministic step invocation.

Threat 7 is **constitutionally incompatible** with the framework.

### §O.3 D9 as Threat 7's structural mitigation

D9 forbids the substrate from observing wall-clock during PAUSED. Under D9, the blocking primitive of Threat 7 is impossible — there is no `condition.wait()` in session.step() because session.step() does not have a wait-mechanism. Each session.step() either drains envelopes (Phase A), advances the tick, and returns, OR is not called at all (caller-side decision).

The wait that Threat 7 describes happens, if at all, in the **caller**, not in the substrate. The caller decides when to invoke session.step(). The substrate's role is purely passive with respect to wall-clock.

### §O.4 Threat 7 closure verdict

**Under Discipline D9, Threat 7 is constitutionally closed.** The Framework's eight Disciplines plus the new D9 are jointly sufficient to close all eight Analysis threats. Live ingress + PAUSED are jointly constitutionally compatible.

---

## §P. PAUSED contradictions analysis

This section addresses edge cases involving PAUSED interactions with other substrate events.

### §P.1 Multi-pause (pause arriving while already PAUSED)

D-FAULT-7 idempotency: a second pause envelope drained while session is already PAUSED is forensic-only. The envelope is event-recorded as `OperatorPauseRequested`; no second state transition; no `SessionPaused` event re-emitted.

**Outcome:** session remains in PAUSED. Trace records the forensic event.

### §P.2 Multi-resume (resume arriving while already RUNNING)

Symmetric: a resume drained while RUNNING is forensic-only. Event recorded; no state change.

**Outcome:** session remains in RUNNING. Trace records the forensic event.

### §P.3 Pause + abort in the same Phase A

If both pause and abort drain in one Phase A while session is RUNNING:

* canonical order determines drain sequence;
* if pause first: RUNNING → PAUSED, then PAUSED → ABORTING (abort transition);
* if abort first: RUNNING → ABORTING (abort transition), then pause forensic-only (already in ABORTING).

In both cases, terminal state is ABORTING. Trace records all envelopes with their events. Replay reproduces byte-equal.

### §P.4 Pause + resume in the same Phase A

If a pause and resume both drain in the same Phase A while RUNNING (pre-queued or live-arrived):

* canonical order determines drain sequence;
* if pause first: RUNNING → PAUSED, then PAUSED → RUNNING. Net: session stays in RUNNING. Trace records both transitions (`SessionPaused` then `SessionResumed`) with consecutive seq values.
* if resume first: resume is forensic-only (session is RUNNING). Then pause: RUNNING → PAUSED. Net: session ends in PAUSED. Trace records resume as forensic, pause as transition.

These two cases produce different outcomes! Canonical order matters. This is constitutionally well-defined (Lemma L3 + D-FAULT-7) but operationally counterintuitive.

For the framework: this is fine. Determinism is preserved. Operators submitting both pause and resume at the same tick should understand that canonical order applies. The substrate cannot distinguish "operator intent."

### §P.5 PAUSED → ABORTING → ABORTED state path

The session in PAUSED receives an abort. Transitions PAUSED → ABORTING. Per D-FAULT-3, cascade-skips remaining pending nodes (uniformly per row 6 since OPERATOR_ABORT). After cascade-skip, the session.step() returns. Subsequent session.step() calls find no pending nodes and the session is ABORTING; close() emits `SessionAborted`. Standard abort path.

### §P.6 Recovery node and PAUSED

A recovery node (D-FAULT-8: `metadata["recovery_of"] = "<failed_node>"`) is a normal node from the scheduler's perspective. If pause drains while the session is RUNNING with a recovery node pending, the session transitions to PAUSED. The recovery node remains pending. On resume, the scheduler selects it normally and Phase D begins recovery execution.

No special handling required. Recovery nodes compose with PAUSED trivially.

### §P.7 PAUSED during contradiction state

Per §I, contradictions present at PAUSED entry persist through PAUSED unchanged. If the session resumes and a recovery node fires, the recovery may resolve the contradiction (per D-FAULT-8). PAUSED itself does not.

### §P.8 PAUSED edge-case verdict

All enumerated edge cases are constitutionally well-defined. PAUSED composes with existing substrate behavior cleanly. D-FAULT-7 idempotency + Lemma L3 canonical-order + Theorem T4 tick-alignment together cover the edge surface exhaustively.

---

## §Q. Constitutional verdict on F58

### §Q.1 Verdict

**F58 verdict: ADMISSIBLE.** A `PAUSED` SessionState value, implementing Shape PD as specified in §C, is constitutionally admissible under the Step 8 / 9 / 10 / 11 substrate, provided:

* **Theorem T6** (Phase-A-governed PAUSED transitions; Phase B–G structural skip; orchestration_tick continuity; no wall-clock observation; single-emitter discipline) is asserted as a normative clause;
* **Discipline D9** (Caller-Driven PAUSED Cadence) is asserted as a normative clause;
* **Refinement R1** to Lemma L4 (scheduled-injection replay-reconstruction for late-arrival case) is adopted as a framework refinement;
* the supporting envelope kinds (`pause`, `resume`) and event types (`SessionPaused`, `SessionResumed`) are added per D-FAULT-9 envelope-schema additive extension.

### §Q.2 What the verdict closes

F58 closes:

* the kind-expansion question for `pause` and `resume` in D-FAULT-9a (both are constitutionally admissible);
* Framework Threat 7 (PAUSED-as-wall-clock-wait) — closed by D9;
* the SessionState-extension question (PAUSED is constitutionally distinct from RECOVERING; not subject to D-FAULT-15 #18's prohibition);
* the dormant-epoch question (PAUSED does not introduce new epochs);
* the scheduler-authority question (PAUSED does not grant new scheduler authority; scheduler is simply not called during PAUSED, consistent with D-SCHED-1 purity);
* the transport-independence-under-pause-resume question (T5 preserved verbatim).

### §Q.3 What the verdict does NOT close

F58 does NOT close:

* **F59** (`manual_advance` semantics) — a distinct envelope kind requiring its own analysis;
* **F60–F65** — interpretive sub-questions independent of PAUSED;
* the runtime-implementation question (no implementation is authored here);
* the contract-phase question (contract authoring is deferred);
* the question of whether PAUSED is operationally desirable (substrate admissibility ≠ operational desirability; the operator-side argument for pause/resume is outside F58 scope).

### §Q.4 The verdict's degrees of strength

F58's verdict is **strong** in the following senses:

* Shape PD is the unique admissible candidate among the four enumerated; the other three (PA, PB, PC) are either inadmissible or trivial.
* Shape PD's properties are mechanically derivable from existing substrate invariants; T6's five properties are nearly forced.
* No new contract surface is required beyond T6 + D9 + the additive envelope/event kinds.

F58's verdict is **conditional** on Refinement R1: the replay-tool's reconstruction primitive must be extended to handle late-arrival envelopes. R1 is independently necessary for live ingress with late arrivals; F58 surfaces it.

---

## §R. Downstream implications for F42 (kind expansion)

### §R.1 F42's status

F42 in the Framework: "Kind expansion (pause/resume/manual_advance) audit." Marked OPEN pending F58's PAUSED resolution.

### §R.2 Impact on F42 from F58's verdict

F58 admits `pause` and `resume`. Therefore F42 for these two kinds resolves to **ADMITTED** with the conditions of T6 + D9 + R1.

F42 for `manual_advance` is still OPEN — it depends on F59 (which is a separate analytical pass).

### §R.3 D-FAULT-9a's status

D-FAULT-9a currently says: "Step 9 supports only `kind='abort'`. Other kinds (`pause`, `resume`, `manual_advance`) are reserved for Step 11."

After F58: the contract phase, if pursued, can author D-FAULT-9a (or a successor clause) to admit `pause` and `resume` as kind values, with normative references to T6 and D9 governing their semantics. `manual_advance` remains reserved-but-undefined pending F59.

### §R.4 Cascade of dependencies

F58 unblocks:

* the contract phase for PAUSED's clause text;
* the contract phase for `pause` and `resume` envelope kinds;
* the contract phase for `SessionPaused` and `SessionResumed` event types;
* a (possibly minor) update to the Framework to incorporate R1 into Lemma L4.

F58 does NOT unblock:

* the contract phase for `manual_advance` (depends on F59);
* the implementation of any live-channel mechanism (depends on contract phase + implementation phase separately);
* runtime authoring of pause/resume-aware UI / operator tooling (depends on transport-layer design).

---

## §S. Open follow-ons

### §S.1 R1 incorporation into the Framework

The Framework's Lemma L4 should be refined to incorporate scheduled-injection replay-reconstruction. This is a small documentation update to `phase_4b_step11_admissibility_framework.md` §C.4 and §H. It does NOT require a new analytical pass; it is a clarification of an existing lemma.

### §S.2 F59 (`manual_advance` semantics)

F58's resolution does not assist F59. The `manual_advance` envelope's semantics remain constitutionally questionable per Framework §M.5 (no scheduler override per D-SCHED-1; no implicit recovery per D-FAULT-8). F59 must determine either a fundamentally different semantic for `manual_advance` or recommend dropping the reserved name from D-FAULT-9a.

### §S.3 Late-arrival impact on Step 11 live-ingress threat models

Refinement R1 (scheduled-injection) closes the replay-identity question under late-arrival but introduces an open analytical question: does R1 itself introduce new threat models? Two potential concerns:

* the replay tool's scheduled-injection mechanism is a privileged primitive — if it can inject envelopes at specific ticks, can it be misused to falsify replay-identity assertions?
* the replay tool reads ts_step from the trace; if the trace is malformed (e.g. ts_step inconsistent with payload's requested_at_tick), can scheduled-injection produce a "successful" but incorrect replay?

These are **REPLAY TOOL CONCERNS**, not substrate concerns. The substrate produces traces correctly under all admissible execution paths. The replay tool, in implementing R1, must validate trace integrity (D-TRACE-6 / D-TRACE-7) before reconstruction. Beyond integrity validation, R1's introduction of injection authority is bounded by the trace itself — replay cannot inject envelopes that don't appear in the trace.

These follow-ons are **observational** for the framework; they may be classified for clause work in a future Framework pass.

### §S.4 PAUSED + sequencer composition

A future analysis may consider whether `pause` envelopes can be combined with task-graph `FailureAction` for "pause on failure of node X" semantics. This is a graph-topology question, not a substrate question, and is out of F58 scope.

---

## §T. Closure posture

### §T.1 Closure statement

The F58 PAUSED admissibility investigation is **CLOSED** with verdict **ADMISSIBLE**, conditional on T6 + D9 + R1 normalization.

The PAUSED SessionState, implemented as Shape PD (no-op-tick model with caller-driven cadence), is constitutionally compatible with the Step 8 / 9 / 10 / 11 substrate. Theorems T1–T5 and Disciplines D1–D8 are preserved verbatim. A ninth discipline (D9) is required to close the Framework's open Threat 7 (PAUSED-as-wall-clock-wait). A small refinement (R1) to Lemma L4's reconstruction primitive is required to handle late-arrival envelopes (independently relevant to all live ingress).

The substrate posture after F58:

> Replay-authoritative deterministic orchestration substrate with empirically-validated mid-trajectory predicate semantics on real PhysX, with an analytically-derived live-ingress admissibility framework (eight disciplines + scheduled-injection replay primitive), AND a constitutionally-admissible deferred-decision SessionState (PAUSED) governed by caller-driven cadence.

No contract has been authored. No implementation has been authored. The substrate's existing clauses remain unmodified.

### §T.2 What the next session may pursue

If the next session pursues continued Step 11 analytical work, candidates in priority order:

1. **F59** — `manual_advance` semantics. Distinct from F58; needs its own analytical pass. Likely outcome: drop the reserved name from D-FAULT-9a.
2. **Framework R1 incorporation** — small documentation update to integrate Refinement R1 into Lemma L4. Trivial; could be appended to a future Framework iteration.
3. **F60** — D-FAULT-15 #16 reach onto object-method ingress (interpretive question).
4. **F61–F65** — minor interpretive questions.

If the next session pursues a **contract phase** for the channel mechanism + PAUSED (the additive-only delta), F58 + the Framework + the Analysis are sufficient prerequisites. The contract phase would author clauses for T2–T5, T6, L1–L4 (with R1), D1–D9, the proposed D-FAULT-15 rows #31–#42, and the new envelope kinds / event types. No existing clause modification.

If the next session pursues implementation, the contract phase must be completed first.

### §T.3 Final invariants check

This analysis preserved verbatim:

* replay-authoritative truth ✓ (Lemma L4 + R1 reconstructs PAUSED runs byte-equal)
* append-only causality ✓ (PAUSED transitions are events; no retroactive editing)
* authoritative orchestration_tick semantics ✓ (T6 property 3)
* deterministic interruption boundaries ✓ (PAUSED does not introduce mid-Phase-E observation)
* Phase E atomicity ✓ (PAUSED skips Phase E entirely)
* contradiction preservation ✓ (PAUSED is contradiction-neutral; §I)
* transport independence ✓ (T5 preserved; §J.3)
* reopen-stage replay identity ✓ (no new PhysX state introduced)
* no hidden cleanup ✓ (Phase G skipped; no D-LIFE transitions)
* no wall-clock authority ✓ (D9 forbids; §N)
* no adaptive semantics ✓ (PAUSED transitions are envelope-driven, not state-driven)

All preserved.

This document is final for the scope of this session.

---

**End of F58 PAUSED constitutional admissibility analysis.**

Predecessors: [Step 11 admissibility framework](phase_4b_step11_admissibility_framework.md), [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md). Architectural baseline: [phase_4b_orchestration_architecture.md](phase_4b_orchestration_architecture.md).
