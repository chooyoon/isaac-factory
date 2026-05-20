# Phase 4B Step 11 — Live Ingress: Causality & Authority-Topology Analysis

**Status:** **ANALYSIS ONLY (2026-05-21).** No contract mutation, no implementation, no comparator change, no snapshot-schema change, no event taxonomy change, no envelope-schema change. This document interrogates whether **runtime-visible orchestration authority** can exist on top of the validated Step 8 + Step 9 + Step 10 Direction A substrate without introducing hidden causality.

**Predecessor closures (frozen baseline):**

* Step 8 ARCHITECTURALLY CLOSED — D-CONT-1..-7a (retained-state continuity, occupancy authority, allowlist-only snapshot projection, ACQUIRED_ONLY hardening, byte-identical SessionPackage across cycles).
* Step 9 ARCHITECTURALLY CLOSED — D-FAULT-1..-15 (failure taxonomy, single-emitter discipline, retained-state contradiction preservation, Phase-A-only abort ingress, tick-budget timeout, graph-explicit recovery).
* Step 10 Direction A ARCHITECTURALLY CLOSED 2026-05-21 — D-EXEC-13 a/b/c/d, D-FAULT-1b, D-FAULT-3b, D-FAULT-12c (sub-Phase-E predicate, mechanically-neutral `EXECUTION_INTERRUPTED`, declared-order classification, integer `ticks_consumed`). 4/4 deferred scenarios C/D/E/F empirically validated; 12/12 cycles byte-identical under `--reopen-stage-between-cycles`.

**Scope (per session brief).** Step 11 is a **compatibility-boundary investigation**, not a redesign initiative, not a flexibility initiative, not a runtime-modernization effort. The analysis treats live ingress primarily as a deterministic-causality and authority-topology problem, NOT as an interrupt-feature problem.

**Frozen baseline interaction.** Every clause of every prior closure (D-EXEC-1..-13, D-SCHED, D-BUS, D-REPLAY, D-SESS, D-TRACE, D-LIFE, D-FORBID, D-CONT-1..-7a, D-FAULT-1..-15, D-CONF) is treated as **load-bearing and immutable** for the duration of this analysis. The acceptable shape of any future Step 11 implementation is bounded above by the requirement that the substrate posture survive byte-equal in every replay-authoritative surface.

**Document objective.** Determine: is there a live-ingress topology that

* is fully explainable through append-only deterministic history,
* admits replay-authoritative reconstruction,
* preserves explicit causal ordering,
* exposes only observable authority transitions,
* and does NOT widen the orchestration authority surface (no new emitters; no hidden causality channels; no mid-Phase-E observation; no wall-clock authority)?

If yes — describe its causal contract. If no — describe why and what the impossibility theorem looks like.

This document does NOT propose contract clauses, does NOT propose implementation, and does NOT recommend a shape. Section §V (analysis verdict) summarizes the compatibility boundary.

---

## §A. Posture & analytical framing

### §A.1 The mis-framings to reject

Three framings are popular but mislead the analysis. They are explicitly rejected here:

1. **"Step 11 is about letting operators send commands during execute."** This is the interrupt-feature framing. It conflates *user-facing ergonomics* with *causal topology*. The substrate has no notion of "during execute" that is operator-visible — Phase E is atomic by D-FAULT-6a and the orchestration tick is the only observable timing unit. A framing that begins with "during execute" already assumes a non-existent observation surface.

2. **"Step 11 is about pause/resume/manual_advance."** D-FAULT-9a names these as Step 11 envelope kinds, but naming them does not license the runtime states they imply. `pause` implies a wall-clock waiting state; `manual_advance` implies external control over `session.step()` invocation cadence. Both are runtime-modernization framings disguised as scope expansions. The analytical question is whether the *envelope* `pause` can be introduced without the *runtime state* PAUSED — i.e. whether pause can be a deferred orchestration decision rather than a wall-clock-bound waiting state.

3. **"Step 11 is the operator-channel feature."** §8 of the architecture doc, [phase_4b_orchestration_architecture.md §8 risk #8](phase_4b_orchestration_architecture.md), describes `OperatorChannel` as a "synchronous between-node command queue; commands NEVER fire mid-tick." That is the pre-queue posture, generalized to a live source. The framing risk: treating Step 11 as "implementing the operator channel" instead of as "proving that the live source can preserve the pre-queue's replay-authority discipline."

### §A.2 The correct framing

Step 11 asks: **under what conditions can a session observe externally-arriving ingress events such that the trace alone reconstructs WHEN each event became authoritative and WHY it became authoritative at that boundary?**

The substrate already has the answer for *pre-queued* envelopes (D-FAULT-9, D-FAULT-9a, D-FAULT-6, D-FAULT-7). Step 11's question is whether the same answer survives generalization to envelopes whose existence is not known at `session.__init__`.

The analysis proceeds by treating the **drain epoch** — not the wall-clock arrival — as the load-bearing observation primitive. See §F.

### §A.3 What this analysis is forbidden to produce

Per the session brief, this document does NOT produce:

* runtime implementation
* contract mutation
* comparator redesign
* snapshot-schema redesign
* replay weakening
* adaptive recovery
* hidden cleanup
* replay healing
* semantic-tolerance introduction
* async authority introduction
* thread authority introduction
* signal/callback authority introduction
* event-bus redesign proposals
* reactive-runtime proposals
* speculative-synchronization proposals

These are non-products. The analysis below references them only to demonstrate where the compatibility boundary cuts them out.

---

## §B. The N2-only interruption impossibility — formalized

The session brief asserts (and the analysis confirms):

> Under the current execute-entry frozen predicate model, N2-only interruption is provably impossible because orchestration authority advances per `session.step()`, not per `world.step()`.

This subsection formalizes the theorem because every later section ([§I](#§i-authority-acquisition-vs-authority-visibility-boundary), [§J](#§j-interruption-timing-authority-under-live-ingress), [§N](#§n-visibility-boundary-semantics)) cites it.

### §B.1 The clock asymmetry

Two clocks coexist in the substrate; they are not commensurable.

| clock | unit | advances at | mutation authority | visibility to orchestration |
|---|---|---|---|---|
| **orchestration_tick** | one `session.step()` | end of `session.step()` (`_orchestration_tick += 1`) | session-owned (D-SESS-1, D-SESS-6) | every phase observes it |
| **world.step() count** | one PhysX step | inside Phase E only (`world.step()` call inside `_run_cycle`) | executor-owned (D-EXEC-4) | invisible outside Phase E |

The orchestration tick is the **only** clock that defines an observation epoch for envelope drain (D-FAULT-6 — abort ingress at Phase A only). The `world.step()` count is the **only** clock against which a predicate can evaluate intra-execute boundaries (D-EXEC-13 b — `segment_tick` is a count of completed boundaries within one `execute()` invocation).

Crucially: **the two clocks are not nested in a way that lets one reference the other**. From the orchestration's perspective, `world.step()` counts inside Phase E are unobservable until Phase E returns (D-FAULT-6a, D-EXEC-13a). From the executor's perspective during Phase E, `_orchestration_tick` is *frozen at the value captured at execute-entry* (`base_tick`, D-EXEC-13).

### §B.2 The "N2-only interruption" question, stated precisely

Suppose a two-node job N1 → N2. Suppose an external operator submits an abort envelope at wall-clock instant `W`. Suppose `W` falls strictly inside the wall-clock interval during which `session.step()` is executing N2's Phase E. Can the substrate honor the abort such that:

1. N1 ran to completion (PASS),
2. N2's Phase E was interrupted mid-trajectory,
3. N2's `TaskResult` carries `outcome = EXECUTION_INTERRUPTED`,
4. The interruption is classified as `OPERATOR_ABORT` (D-FAULT-3b row 1),
5. The trace records the abort as having become authoritative at N2's mid-Phase-E moment?

### §B.3 Why item 5 fails

Items 1–4 are mechanically achievable under the existing Step 10 Direction A surface **if and only if** the envelope was visible at N2's execute-entry. The envelope's visibility at N2's execute-entry is determined by:

* the envelope's `requested_at_tick` (D-FAULT-9);
* the envelope's presence in `_pending_envelopes` at the moment N2's `_build_interrupt_predicate` ran (which happens *before* `executor.execute()` is called, inside N2's `session.step()`).

For the envelope to be visible at N2's execute-entry under the current substrate, it must have been in the pre-queue (`pending_operator_envelopes` constructor parameter). It must have existed at `session.__init__`. The current substrate has no other ingress.

If a hypothetical Step 11 live channel exists, the envelope can arrive between N1's completion and N2's execute-entry — that is, during the very narrow wall-clock interval covering N2's Phase A drain through N2's Phase D snapshot. If the live channel's drain happens at N2's Phase A, the envelope IS visible at N2's execute-entry. If the live channel's drain at N2's Phase A does NOT see the envelope (because the envelope arrived after Phase A), the envelope cannot influence N2's predicate.

**Item 5 fails because:** if the envelope arrives strictly inside N2's Phase E (wall-clock instant `W` lies inside the Phase E interval), the substrate has no observation surface for it. The next Phase A drain happens at N3's `session.step()` (or post-N2's complete()). The envelope's drain epoch is N3's Phase A, not N2's mid-execute. The trace records "abort drained at N3's Phase A, N2 ran to mechanical completion" — not "N2 interrupted mid-execute by an abort that arrived at instant W."

### §B.4 The theorem

For any envelope arriving via any live ingress mechanism whose arrival instant `W` is strictly inside the wall-clock interval of a node N's Phase E:

* the envelope CANNOT influence N's interruption predicate (predicate is closed at execute-entry, D-EXEC-13);
* the envelope CANNOT be drained mid-N's-Phase-E (D-FAULT-6, D-FAULT-6a, D-FAULT-15 #5, #27);
* the envelope CANNOT terminate N's execute via any orchestration-observable mechanism (D-EXEC-13a);
* the envelope CAN ONLY become authoritative at the next Phase A drain, which is the Phase A of the next `session.step()` invocation.

The earliest authority-acquisition boundary for a mid-Phase-E arrival is the **next** session.step()'s Phase A. The orchestration sees a node-boundary-aligned abort, not a mid-N-execute abort. The trace records this boundary alignment, and replay reproduces it byte-equal.

**Corollary.** The latency between wall-clock arrival and orchestration-observable authority acquisition is bounded below by the wall-clock duration of the remainder of the current node's Phase E. This latency is **not a deficiency** — it is the substrate's invariant. It is the price of replay-authoritative single-emitter discipline.

### §B.5 What the theorem rules out

The theorem rules out, *for all time*, the following questions:

* "Can we abort node N at world.step() count 247 of its execute?" — No, no observation surface.
* "Can we react instantly to operator input?" — No, latency floor = remainder of current node's Phase E.
* "Can the operator preempt a running trajectory at any granularity finer than authored segment boundaries?" — No, segment boundaries are the finest observation grain (D-EXEC-13 condition 4), and they are predicate-only; the predicate is closed at execute-entry.

### §B.6 What the theorem does NOT rule out

The theorem leaves open:

* **Phase-A-aligned abort under live arrival.** If the envelope arrived BEFORE Phase A drain of `session.step(t)`, the substrate can drain it at that Phase A, abort the session, and cascade-skip remaining pending nodes — including nodes that have never run. This is what `pending_operator_envelopes` already enables under pre-queue.
* **Execute-entry-aligned interruption under live arrival.** If the envelope arrived AFTER Phase A drain of `session.step(t)` but BEFORE Phase D execute-entry of the same step, the substrate could (subject to the analysis below) capture it in the predicate's closure at execute-entry. This requires a second observation epoch inside one `session.step()`, between Phase A and Phase D. See [§F.4](#§f4-the-pre-execute-second-epoch-question) for the analytical implications.
* **Next-Phase-A drain under any mid-Phase-E arrival.** This is the boundary-aligned fallback. It is observationally identical to a pre-queued envelope drained at the same orchestration_tick.

The theorem does not say "live ingress is impossible." It says "live ingress cannot beat the orchestration_tick observation grain." The analysis below uses this as the load-bearing premise.

---

## §C. Live ingress ontology — what IS an ingress event?

### §C.1 The ingress event as observation, not as transport

An ingress event is **not** the network message that carried the envelope. An ingress event is **not** the moment a transport layer accepted the envelope. An ingress event is **not** the operator's keystroke. None of those have replay-authority — they happen in wall-clock time on layers the substrate does not own.

An ingress event IS: **the orchestration's observation that an envelope exists, anchored to an orchestration tick and an `OperatorAbortRequested` event seq**.

This distinction matters because the answer to "when did the ingress happen" depends on which definition you accept. Under the orchestration-observation definition (the only replay-authoritative one), the ingress happened at the Phase A drain that observed it. Under the transport-arrival definition, the ingress happened at some wall-clock instant the substrate cannot observe. Replay-authority requires the first definition. The transport-arrival definition is diagnostic (D-SESS-5).

### §C.2 The OperatorEnvelope as the unit of ingress

The envelope is the unit. It carries `kind` (D-FAULT-9a: `abort`; Step 11 envisions `pause`/`resume`/`manual_advance`), `requested_at_tick` (the earliest orchestration_tick at which Phase A drain considers it eligible), `reason` (operator-supplied; participates in fingerprint), and `envelope_id` (deterministic blake2b digest of the other three; replay-stable).

The envelope is content-addressed: two envelopes with identical `(kind, requested_at_tick, reason)` have identical `envelope_id` by construction (see [`envelopes.py:101-115`](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/envelopes.py#L101-L115)). This is load-bearing for §F's epoch formalism — content-addressed envelopes can be canonically ordered without any sequence-number or transport-layer ordering.

### §C.3 The `requested_at_tick` field: what it means and does not mean

`requested_at_tick` is the **earliest orchestration tick at which Phase A drain considers the envelope eligible**. It is NOT the tick at which the envelope arrived. It is NOT the tick at which the envelope was created. It is a **futures-style** gate: the envelope is invisible to Phase A drains before this tick, eligible after.

Under pre-queue (Step 9), all envelopes are present at `session.__init__` and `requested_at_tick` gates when they become drainable. A pre-queued envelope with `requested_at_tick = 5` is invisible at session.step(0..4) Phase A drains and visible at session.step(5+).

Under live ingress, two distinct concepts collapse onto `requested_at_tick`:

* the envelope's **earliest eligibility tick** (gate semantics, same as pre-queue);
* the envelope's **earliest known tick** (arrival semantics — i.e. the smallest orchestration_tick at which the channel had the envelope).

The semantic question: is `requested_at_tick` interpretable as "the operator asked for this to fire no earlier than tick N," OR as "the operator's submission was first observable at tick N"? The current schema (D-FAULT-9) uses the first interpretation. Live ingress requires both, and the schema must hold up against:

* an operator submitting an envelope with `requested_at_tick = 100` at wall-clock instant when orchestration_tick = 5 (gate semantics: not eligible until tick 100);
* an operator submitting an envelope with `requested_at_tick = 0` at wall-clock instant when orchestration_tick = 50 (gate semantics: eligible at the very next Phase A drain, which is at tick 50; but the envelope didn't exist before tick 50 — does that matter? *No* — gate semantics is forward-looking only).

The analytical finding: `requested_at_tick` has **forward-looking gate semantics** under both pre-queue and any candidate live-ingress shape, and its semantics survive generalization. There is no ambiguity to resolve.

### §C.4 The drain seq as the secondary identifier

Every drained envelope produces exactly one `OperatorAbortRequested` event (D-FAULT-7). That event carries a `seq` (D-BUS-3, gap-free monotone per session). The pair `(envelope_id, ingress_seq)` is the canonical orchestration-side identifier of the ingress observation.

`envelope_id` is content-addressed → reproducible from envelope contents alone.
`ingress_seq` is order-addressed → reproducible from the trace's seq counter.

Two replays of identical inputs produce identical (envelope_id, ingress_seq) tuples. This pair is the load-bearing replay-identity hook for live-ingress envelopes.

### §C.5 Forbidden ingress-event fields

For any candidate Step 11 schema, the following fields are FORBIDDEN as members of `OperatorEnvelope` or `OperatorAbortRequested` payload, by direct citation:

* `arrival_wall_ns` — D-FORBID-6, D-FAULT-15 #10, D-FAULT-15 #22. (May be a sidecar / diagnostic-state field per D-TRACE-5; never authoritative.)
* `transport_id`, `connection_id`, `operator_session_id` — not replay-authoritative; would be hidden authority if they entered the fingerprint.
* `submission_order_within_transport` — transport-layer ordering authority; D-SCHED-1, D-SCHED-5..7 forbid leakage of transport order into orchestration ordering.
* `arrival_order_within_orchestration_tick` — sub-tick ordering authority; collapses to `envelope_id` canonical order at the drain epoch (see §F).

Any candidate schema that includes any of these as authoritative is rejected at the analysis-doc level, before contract authoring.

---

## §D. Orchestration authority topology — current shape & projected shape

### §D.1 Current single-emitter discipline

D-FAULT-2: "Each failure class has exactly **one** origin authority." The current emitter table is concrete:

| failure class | emitter | mutation |
|---|---|---|
| OPERATOR_ABORT (D-FAULT-1) | ExecutionSession Phase A drain (pre-queue) | RUNNING → ABORTING |
| OPERATOR_ABORT via deferred-from-Phase-A (D-FAULT-3b row 1) | ExecutionSession post-Phase-E (Step 10 Direction A) | RUNNING → ABORTING |
| TIMEOUT_FAILURE (D-FAULT-3b row 2) | ExecutionSession post-Phase-E | none beyond cascade |
| NODE_EXECUTION_FAILURE (D-FAULT-3b row 3) | ExecutionSession post-Phase-E | none beyond cascade |
| AUTHORITY_VIOLATION | ExecutionSession Phase G | session abort |
| CONTINUITY_VALIDATION_FAILURE | ExecutionSession Phase G | session abort |
| INFRASTRUCTURE_DEGRADATION | sidecar (D-FAULT-13) | none (session dead) |
| REPLAY_INTEGRITY_FAILURE | comparator tool out-of-session (D-FAULT-11) | none |

The session is the sole orchestration-state emitter. The executor reports `TaskOutcome` (Phase 4A authority); the session classifies into D-FAULT-1 classes.

### §D.2 The "second emitter" temptation under live ingress

A naïve live-ingress shape would put the live channel itself in the OPERATOR_ABORT emission path: the channel listens for arrivals, fires `OperatorAbortRequested` directly, and notifies the session. This is **a second emitter** for the same failure class — D-FAULT-2 violation, D-FAULT-15 #16 (method-as-ingress) violation, D-FAULT-14 (implicit secondary orchestration) violation.

Any candidate shape that produces ingress events from outside `ExecutionSession.step()` is constitutionally rejected before further analysis. The analytical constraint: **only `ExecutionSession.step()` emits `OperatorAbortRequested` and `SessionAborting`**, regardless of where the envelope arrived.

### §D.3 The "channel as opaque buffer" topology

The constraint in §D.2 forces a specific topology: the live channel is an **opaque pull-target** that the session queries at Phase A. The channel itself emits nothing. The channel is a passive store.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │            ExecutionSession (the sole emitter)                   │
  │                                                                  │
  │   for each session.step():                                       │
  │     Phase A:                                                     │
  │       1. _pull_live_channel()  ← pure: drains channel buffer    │
  │          into _pending_envelopes (subject to canonical sort)    │
  │       2. _drain_phase_a_envelopes()  ← unchanged from Step 9    │
  │     Phase B–G: unchanged                                        │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘
            ▲                                            
            │ pull only                                  
            │                                            
  ┌─────────┴───────────────┐                            
  │   LiveIngressChannel    │  ← passive buffer; no emission        
  │     append-only         │     no callbacks; no notifications    
  │     buffer of           │     no thread authority over          
  │     envelopes           │     session state                     
  └─────────────────────────┘                            
            ▲                                            
            │ transport-layer push                       
            │                                            
  ┌─────────┴───────────────┐                            
  │   Transport (WebRTC,    │  ← out-of-band wall-clock surface     
  │     websocket, etc.)    │     non-authoritative, diagnostic     
  └─────────────────────────┘                            
```

The channel has no observation authority over session state; the session has no read authority over transport state. The pull is from a frozen-by-Phase-A buffer.

This topology preserves D-FAULT-2 trivially: the session is still the sole emitter. The channel produces nothing observable; it merely stores.

### §D.4 The "buffer freezing" question

A subtle topology issue: when the session pulls at Phase A, what is the cutoff point between "envelopes the session sees this tick" and "envelopes that arrive after the pull starts"? Three sub-options:

* **Strict snapshot.** At the start of Phase A, the channel's current buffer is atomically swapped with an empty new buffer. The session reads the snapshot. New arrivals go to the new buffer.
* **Drain-to-empty.** The session reads the channel until empty. If an arrival happens during the read loop, it is captured. Risk: the read loop runs in wall-clock and its termination is not deterministic from the session's perspective.
* **Tick-gated arrival.** Each arrival timestamps itself with `(arrived_at_orchestration_tick, arrived_seq_within_tick)`. The session reads only those whose `arrived_at_orchestration_tick < current_orchestration_tick`. Arrivals during the read loop self-classify as "next tick."

Option 1 (strict snapshot) is the only one without hidden authority. The atomic swap is implementable as a lock-free CAS or as a `with lock: snapshot = buffer; buffer = []` block. The session reads the snapshot deterministically.

Option 2 (drain-to-empty) has a hidden wall-clock authority: whether arrival X is captured this tick depends on whether X arrived before or after the read loop's iteration over the buffer's then-current end. This is a hidden race.

Option 3 (tick-gated arrival) requires arrivals to read `_orchestration_tick` at arrival time, which means the transport layer has read authority over orchestration state. D-SESS-5 violation (diagnostic state read by orchestration-decision code), and the inverse: transport reading orchestration state without owning a synchronization discipline.

The analysis prefers Option 1 by elimination. Note this is *topological* preference, not contract clause.

### §D.5 What changes in the session.py topology

Under the channel-as-opaque-buffer topology, the changes to session.py are surgical:

* one new method `_pull_live_channel()` inside Phase A;
* `_pending_envelopes` becomes the **union** of (initial pre-queue) + (live-arrived envelopes since session.begin), maintained in canonical order after each pull;
* the existing `_drain_phase_a_envelopes()` is **unchanged** — it iterates `_pending_envelopes` in canonical order, drains eligibility-met envelopes, emits `OperatorAbortRequested` events at Phase A only;
* the trace `events.jsonl` payload of `OperatorAbortRequested` is **unchanged** — the same canonical schema (envelope_id, kind, requested_at_tick, reason);
* `pending_operator_envelopes` constructor parameter is **unchanged**; live-ingress is purely additive.

No new event types. No new SessionState values. No new envelope kind needed *for the live-channel mechanism itself* (kind expansion to `pause`/`resume`/`manual_advance` is a separate orthogonal question; see §M.5).

The topology preserves every D-FAULT-15 anti-pattern row. It is constitutionally compatible — provided the channel itself is a passive store and the session is the sole pull authority.

### §D.6 The transport layer is unconstrained

The substrate has no opinion on the transport. WebRTC, websocket, ZeroMQ, named-pipe, file-system polling, an HTTP POST endpoint behind a queue, an in-process callback — all are acceptable transports. Constraints apply only to *what the substrate observes*: a pull from a passive buffer at Phase A. The transport's wall-clock behavior, retries, deduplication, authentication are all out-of-scope.

A live-ingress design that conflates transport choice with substrate semantics has misread the boundary. Step 11 is a substrate question.

---

## §E. Deterministic ingress ordering — closing the §11.1 commutativity gap

### §E.1 What §11 of the contract says

[`phase_4b_deterministic_semantics.md §11`](phase_4b_deterministic_semantics.md) explicitly opens this gap:

> 1. `OperatorOverride` event commutativity. The contract specifies operator commands enter only at Phase A; it does not yet specify whether two operator commands in the same Phase A drain are processed in arrival order or in a canonical order. Phase 4B step 11 will close this gap.

The gap exists already under pre-queue: if two pre-queued envelopes have `requested_at_tick ≤ orchestration_tick`, both eligible at the same Phase A drain, the current implementation (`_drain_phase_a_envelopes` at [session.py:1357-1414](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py#L1357-L1414)) iterates `_pending_envelopes` in its canonical order (sorted by `(requested_at_tick, envelope_id)` at construction, via `normalize_pending_envelopes`). It drains every eligible envelope before returning.

So the current code already enforces canonical order. But the *contract* has not yet pinned this — that is what §11.1 is reserving for Step 11.

### §E.2 The ordering options analyzed

| option | description | replay-stable? | pre-queue compatible? | live-arrival compatible? |
|---|---|---|---|---|
| **Arrival order** | drain in the order envelopes arrived at the channel | NO — transport-layer leakage | N/A (pre-queue has no arrival order) | NO |
| **Canonical order** | sort by `(requested_at_tick, envelope_id)`; blake2b-derived envelope_id is content-addressed | YES | YES — already in use | YES — channel's buffer is sorted at pull time |
| **`requested_at_tick` only** | sort by requested_at_tick; break ties by submission order | NO — ties broken by transport | YES (no ties in current pre-queue) | NO under ties |
| **External sequence number** | operator assigns a monotonic seq | NO — depends on operator UI | NO (no field in current schema) | YES but adds authority |

The canonical-order option (which the implementation already follows) is the only one that preserves replay-stability under both pre-queue and live-arrival.

### §E.3 The commutativity claim

If the drain order at Phase A is `(requested_at_tick, envelope_id)` canonical, then for any two envelopes A and B both eligible at the same drain:

* A drains before B iff `(A.requested_at_tick, A.envelope_id) < (B.requested_at_tick, B.envelope_id)` lexicographically;
* this order is **independent of arrival order**, transport, channel buffering, scheduler choices, anything;
* it is **deterministic from envelope content alone** (envelope_id is content-addressed);
* commutativity holds: drain order does not depend on the order arrivals were stored in the channel.

The commutativity gap from §11.1 closes by **explicitly stating** this canonical order is the drain order — i.e., the contract has already been implementing canonical-order; Step 11's contract delta is to *name* it as normative. (This is a clause-authoring observation, not a clause proposal — see §S.)

### §E.4 The `requested_at_tick` collision question

Under live ingress, two operators could submit envelopes with the same `requested_at_tick` and different `reason` (and therefore different `envelope_id`). Canonical order disambiguates: smaller `envelope_id` (lexicographic) drains first.

Operators have no incentive to coordinate `envelope_id` — it is derived. There is no DoS attack via envelope_id collision because envelope_id is the blake2b digest of content (D-FAULT-9, `derive_envelope_id` at [envelopes.py:101](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/envelopes.py#L101)). Collision implies identical content.

### §E.5 The "two aborts" idempotency interaction (D-FAULT-7)

D-FAULT-7 makes cancellation idempotent at the transition, not the envelope. Two abort envelopes drained in the same Phase A: the first transitions RUNNING → ABORTING and emits `SessionAborting`; the second is recorded as an `OperatorAbortRequested` event but produces no second transition.

Under live ingress, this discipline holds without modification. If three operators concurrently submit aborts during the same wall-clock interval covering one Phase A pull, all three are pulled into `_pending_envelopes`, canonical-ordered, drained at that Phase A; the smallest-envelope_id one transitions the session; the other two are forensic.

### §E.6 Replay-reconstructable ordering

The trace records each `OperatorAbortRequested` event with its `seq` (D-BUS-3). The order of drains at one Phase A maps to a contiguous block of `seq` values. Replay reads the trace, reconstructs the envelope set at session.begin(), and the canonical order is deterministically reproduced.

If a replay reads the trace and finds three `OperatorAbortRequested` events at consecutive seq values 47/48/49 in canonical-order, then a parallel run that produces seq values 47/48/49 with the same canonical-order yields a byte-identical events.jsonl (modulo wall_ns). This is the replay-authority of live ingress reduced to the replay-authority of pre-queue.

---

## §F. Ingress observation epochs — the central formalization

### §F.1 The epoch concept

Define **ingress observation epoch** as a discrete, orchestration-tick-aligned interval at which the session can observe envelope arrivals. The epoch is identified by `(session_id, orchestration_tick)`. The epoch's boundaries are the Phase A entries of consecutive `session.step()` invocations.

Inside one epoch, the session has no observation surface for envelope arrivals (Phase E is atomic, the bus is synchronous, no callbacks). Outside Phase A, the channel may be receiving arrivals but the session does not see them. At the next Phase A entry, the session pulls; the snapshot defines the epoch's observation surface.

Formally:

* **Epoch K** = the interval `[Phase A entry of session.step(K), Phase A entry of session.step(K+1))`.
* **Epoch-K visibility**: the set of envelopes the session pulled at session.step(K)'s Phase A. This set is determined at the pull instant and is invariant during epoch K.
* **Epoch-K drain**: the subset of epoch-K visibility whose `requested_at_tick <= K`. Drained envelopes emit `OperatorAbortRequested`.

### §F.2 Epoch boundaries and orchestration-tick advancement

Reading [session.py:854](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py#L854) and [session.py:875](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py#L875), `_orchestration_tick` advances at *the end* of `session.step()` (after Phase G). The tick value during one session.step() invocation is the value the previous invocation left.

This means epoch K has orchestration_tick = K throughout, and the pull at epoch K's Phase A sees the tick value K. The next pull at epoch K+1's Phase A sees tick value K+1. The two epochs have distinct tick values, so eligibility comparisons (`requested_at_tick <= orchestration_tick`) at the two epochs may produce different drain decisions for the same envelope.

The epoch concept makes the latency story explicit: an envelope that arrived during epoch K is first observable at epoch K+1's Phase A pull. It is not observable mid-epoch-K. (Unless epoch K's Phase A pull happened to catch it — see §F.4.)

### §F.3 The single-pull-per-epoch discipline

Strictly: there is one and only one channel pull per session.step() invocation, at Phase A. Allowing two pulls (one at Phase A, another at Phase E end) would create a sub-epoch boundary that is not visible to D-EXEC-1's seven-phase order. It would also introduce mid-Phase-E observation (D-FAULT-15 #27, #30).

So the discipline is: **one pull per epoch, at Phase A, before the existing `_drain_phase_a_envelopes`**.

### §F.4 The pre-execute second-epoch question

A subtle wrinkle: within one `session.step()`, the orchestration tick is fixed at value K throughout. The Phase A pull happens at the start; the Phase D execute-entry happens later in the same step. Could an envelope that arrived BETWEEN Phase A pull and Phase D execute-entry be visible to the predicate's closure capture?

The mechanism: at Phase D execute-entry, the session builds the interruption predicate by snapshotting `_pending_envelopes` (D-EXEC-13). If between Phase A pull and Phase D execute-entry the channel received a new arrival, AND if we pulled again before the predicate snapshot, the new arrival could enter the predicate's closure.

**The analytical conclusion: NO second pull.** Reasons:

1. **D-EXEC-1 forbids interleaving.** The 7-phase order is Phase A → B → C → D → E → F → G. A second pull between A and D would be a Phase A.5, not in the contract.

2. **Phase A is the unique ingress observation surface.** D-FAULT-6 says abort ingress is at Phase A only. A second pull is a second ingress observation, which is a second observation epoch within one orchestration tick — visibility-boundary contradiction.

3. **The "envelope captured at execute-entry" rule** in D-EXEC-13 reads `_pending_envelopes` as it stands at that moment. If `_pending_envelopes` was last mutated at Phase A pull, the predicate captures the post-Phase-A state. If we allow a second pull at execute-entry, we re-mutate `_pending_envelopes` mid-step, and D-EXEC-13's closure stops being a Phase-A-aligned read.

The cleanest discipline: `_pending_envelopes` is mutated only at Phase A (by pull + drain), and the predicate's closure capture at Phase D reads `_pending_envelopes` as Phase A left it. The "pre-execute second epoch" idea is rejected as a hidden epoch boundary.

This rejection has a cost: an envelope arriving between Phase A pull and Phase D execute-entry, both within the same session.step(K), waits until session.step(K+1)'s Phase A. Latency increases by one tick. The cost is accepted because the alternative is a sub-tick observation boundary that is not in the contract.

### §F.5 The Drain-Epoch invariant

For every ingress event recorded in the trace, the field `drained_at_tick` (currently implicit in the event's `ts_step` or the surrounding orchestration tick context — see §G) equals the orchestration_tick at which Phase A drained the envelope. This is the **drain epoch**.

The drain epoch is replay-stable because:

* it is recorded in the trace;
* it is deterministic from the envelope's `requested_at_tick` + the sequence of pulls (which is deterministic given the channel's deterministic arrival behavior — see §F.6);
* it is not a wall-clock value.

### §F.6 The "deterministic channel" question

Is the channel itself deterministic? Under replay, will the same envelopes arrive in the same epochs?

Under **pre-queue**, trivially yes: the envelopes are passed at session construction, frozen, canonical-ordered, observed at every Phase A.

Under **live arrival**, the answer is: yes for replay-authority purposes, no for wall-clock determinism. The trace records every ingress event with `drained_at_tick`. Replay can reconstruct the live-arrived envelopes by reading the trace and reproducing the pre-queue *as if* every envelope had been pre-queued with the recorded `(envelope_id, kind, requested_at_tick, reason)` from the start. The replay session does not need a transport at all — it has the trace.

This is the load-bearing replay-authority claim for live ingress: **the trace is sufficient to reconstruct the ingress history; the transport is not needed at replay time.** A replay tool that reads a SessionPackage and reconstructs the run does so by reading `events.jsonl`'s `OperatorAbortRequested` events and treating them as a pre-queue with the recorded ticks.

### §F.7 Replay determinism does not require live-channel determinism

This is the critical point. The live channel does not need to be deterministic in any wall-clock sense. The trace's events.jsonl encodes which envelopes were observed in which epochs. Two runs of the same job with different wall-clock arrival patterns produce different traces — they are different sessions. Replay-identity is per-session: a session's trace is replay-stable.

Replay-identity holds **within** a session (D-REPLAY-1 layer L3 — bit-identical replay). It does NOT hold across sessions that received different live arrivals — those are different sessions in the first place. The comparator already refuses cross-session comparisons that don't match `manifest.runtime_hash + manifest.cell_cfg_hash + envelope_set` (the last via per-task fingerprint, transitively).

This isolates the live channel's wall-clock indeterminism from the replay-authority surface. The wall-clock arrival times are non-authoritative (diagnostic-only). The orchestration's observation of those arrivals at Phase A epochs IS authoritative.

### §F.8 The Epoch-Identity Lemma (analytical)

**Lemma.** Let S₁ and S₂ be two execution sessions of the same `Job`, same `seed`, same `runtime_hash`, same `cell_cfg`. Let the live channel deliver envelopes ψ₁ to S₁ and ψ₂ to S₂. If for every orchestration_tick K, the set of envelopes pulled by S₁ at session.step(K)'s Phase A equals the set of envelopes pulled by S₂ at session.step(K)'s Phase A (call this the **Epoch-Identity Condition**), then S₁'s `events.jsonl` and S₂'s `events.jsonl` are byte-identical (modulo `wall_ns`).

*Proof sketch.* Under Epoch-Identity, the canonical drain order at every Phase A is identical (canonical order is content-addressed). The `OperatorAbortRequested` event sequence is identical. The session state transitions are identical (D-FAULT-7 idempotency makes the first abort the transition). The predicate at every execute-entry closes over identical `_pending_envelopes`. Every executor outcome is identical (Phase 3P bit-identity inherits). Every Phase G commit is identical. The trace's seq counter advances identically. □

**Corollary.** Replay identity for live ingress reduces to Epoch-Identity. Two sessions with different transports, different network latencies, different operator submission instants, can still be byte-equal IFF the channel happened to deliver the same envelope sets in the same epochs.

This corollary is non-trivial: it means **two replays of a live-ingress session can be byte-identical even when the transport is non-deterministic**, provided the trace records the drain-epoch alignment. This is what makes live ingress constitutionally compatible.

---

## §G. Append-only ingress history semantics

### §G.1 The trace's role under live ingress

D-TRACE-2: the trace is append-only. D-TRACE-3: the trace cannot be regenerated retroactively. D-TRACE-7: the trace is integrity-verified at session close.

Under live ingress, every observed envelope produces exactly one `OperatorAbortRequested` event. The event is appended at the seq the Phase A drain assigns it. The trace records the full ingress history without any retroactive editing.

If three envelopes arrive in epoch K and one in epoch K+1, the trace has four `OperatorAbortRequested` events. The first three have ts_step values reflecting the orchestration state at epoch K's Phase A; the fourth at epoch K+1's. The seq counter advances monotonically.

### §G.2 Reconstruction primitive

A replay reads the trace and identifies the set of `OperatorAbortRequested` events. For each, it extracts `(envelope_id, kind, requested_at_tick, reason)` from the payload. It builds an `OperatorEnvelope` instance per row. The result is a tuple of envelopes equivalent to the original `_pending_envelopes` at session.begin(), modulo timing.

A replay-session can re-run the same job by passing this reconstructed envelope tuple as `pending_operator_envelopes` to a fresh `ExecutionSession`. The pre-queue model handles it: at each Phase A, the eligibility predicate drains the right envelopes at the right ticks. The result is byte-identical to the original.

This reduces **live-ingress replay** to **pre-queue replay**. There is no separate "live-ingress comparator" required. `tools/check_session_replay_identity.py` is unchanged (D-FAULT-11a strict byte-equality on `events.jsonl`).

### §G.3 The "trace as source of truth" for the channel

Under §G.2's reconstruction, **the trace IS the channel** at replay time. The replay does not need the original transport, does not need network access, does not need any wall-clock awareness. The session reads the reconstructed pre-queue, drains at the documented epochs, produces byte-equal output.

This is a strong claim: live ingress's *implementation* requires a transport, but live ingress's *replay-authority* requires only the trace. The transport is not part of the substrate's replay surface.

### §G.4 No retroactive ingress event editing

D-TRACE-2 forbids editing past events. Under live ingress, two scenarios that would tempt editing:

* **"Late envelope" — an envelope arrives at the channel before epoch K but is not observed by the pull (e.g., the channel's atomic-snapshot missed it).** No retro-edit: the envelope is observed at epoch K+1's pull. The trace's epoch-K block is unchanged. The epoch-K+1 block contains the late envelope. This is the natural drain-epoch alignment.
* **"Duplicate envelope" — the channel delivers the same envelope twice (transport-layer bug, retry).** The envelope_id is content-addressed; the second copy has the same envelope_id as the first. The session's `_drained_envelope_ids` set (already at [session.py:699](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py#L699)) suppresses re-emission. D-FAULT-7 idempotency. The trace records the duplicate as a no-op observation (or, equivalently, the duplicate is silently dropped at the pull layer's deduplication step — implementation choice).

In neither case is the trace edited. Both cases preserve D-FAULT-14 ("every failure transition is one append").

### §G.5 The "rebuild pre-queue from trace" primitive is the replay tool's job

The substrate does not need a new tool. `tools/check_session_replay_identity.py` already compares `events.jsonl` byte-equal. Replay is implemented by spawning a new `ExecutionSession` with the reconstructed envelope tuple — the rest is mechanical. This is testable as a pure-Python test (no Isaac dependency): given a trace, produce a fresh pre-queue tuple, run a new session, byte-compare the resulting trace.

---

## §H. Replay-authoritative reconstruction proof sketch

### §H.1 The proof obligation

For live ingress to be constitutionally compatible, the trace must prove WHY each ingress became authoritative at a specific boundary. The proof obligation:

> Given the trace's `OperatorAbortRequested` event at seq S and orchestration_tick K, replay-reconstructing the session from session.begin() produces an `OperatorAbortRequested` at the same seq S and the same orchestration_tick K, with the same envelope_id, and the same effect on session state.

### §H.2 The proof sketch

(*Sketch* — this is an analysis, not a verification. A formal proof would discharge each step against contract clauses.)

1. **Pre-queue reconstruction.** Build `pending_operator_envelopes` from the trace's `OperatorAbortRequested` payloads. Each payload yields a `(envelope_id, kind, requested_at_tick, reason)` tuple; build the corresponding `OperatorEnvelope`.

2. **Session initialization.** Construct a new `ExecutionSession` with the reconstructed envelope tuple. `normalize_pending_envelopes` canonical-orders them. The internal `_pending_envelopes` matches the original session's `_pending_envelopes` at session.begin() — but with one difference: under live arrival, some envelopes may have been *not yet in the pre-queue* at session.begin(). The reconstructed pre-queue has them all.

3. **Drain timing.** At each session.step(K)'s Phase A, the drain considers envelopes with `requested_at_tick <= K`. Under reconstructed pre-queue, every envelope is present from session.begin(); eligibility is purely a function of `requested_at_tick`. The drain produces the same envelopes at the same epoch as the original session — because the original session's drain happened at the orchestration_tick K (recorded in the trace) and the reconstructed session reaches the same K via the same scheduler decisions (pure functions per D-SCHED-1).

4. **Predicate closure.** At each Phase D execute-entry, the predicate closes over `_pending_envelopes` minus drained-so-far. The set is deterministic from the eligibility rule + the trace's drain history.

5. **Executor execution.** Phase E's executor.execute() is deterministic given (task, predicate-closure-state, base_tick, runtime_hash). The reconstructed session's predicate matches the original; executor reaches the same outcome.

6. **Classification + cascade.** Session classifies post-Phase-E via D-FAULT-3b's pure function. Cascade emission iterates `graph.canonical_order` (D-SCHED-3). Both deterministic.

7. **Seq advancement.** EventBus assigns seq monotonically. Each step's events are emitted in the same order. Seq matches the original.

8. **Trace identity.** Append-only writes produce byte-identical `events.jsonl` (modulo `wall_ns`).

The sketch shows that the trace is sufficient to reconstruct the session. The wall-clock arrival pattern of the original transport is not part of the proof — only the trace's epoch-aligned ingress events are.

### §H.3 The proof sketch's failure modes

The sketch fails if:

* **Drain order is not canonical.** If the original session drained in arrival order (forbidden — §E.2), the reconstructed pre-queue drains in canonical order, and the seq sequence diverges. → strictly enforce canonical drain order at Phase A.

* **Predicate closes over wall-clock state.** If the predicate reads `time.time()` (forbidden — D-EXEC-13 B.2), the reconstructed predicate's closure differs. → strictly enforce predicate purity.

* **Session reads transport state directly.** If `session.step()` queries the transport for non-envelope state (e.g., "is the channel still connected?") and branches on it, replay reconstruction fails. → strictly enforce channel-as-opaque-buffer.

* **Channel callback re-enters session.** D-FAULT-15 #16 forbidden. → strictly enforce pull-only.

Each failure mode is already a contract violation under the existing substrate. The proof sketch holds **iff** the implementation does not introduce any of them.

### §H.4 The proof sketch's non-obvious property

The trace alone, without the transport, suffices for replay. This is the substrate's strongest replay claim:

> Reconstructability of live ingress from the trace alone, without transport access, with byte-equal replay-identity.

This property is what makes live ingress "explainable entirely through append-only deterministic history" (session-brief requirement).

---

## §I. Authority acquisition vs authority visibility boundary

### §I.1 Two distinct surfaces

The session brief asks the analysis to "explicitly analyze authority acquisition boundaries [vs] authority visibility boundaries." These are distinct:

* **Authority acquisition boundary.** The moment at which an external signal *can* influence orchestration state. Under D-FAULT-6, this is Phase A. Under D-EXEC-13 (Step 10 Direction A), this is the predicate's closure capture at execute-entry, which is at end-of-Phase-C / start-of-Phase-D.

* **Authority visibility boundary.** The moment at which the orchestration trace records the influence. Under D-EXEC-2 / D-EXEC-7, this is Phase G — events are emitted at trace commit.

The two boundaries are different even when the signal is the same. An envelope acquires authority at Phase A drain (transition RUNNING → ABORTING); the visibility (`OperatorAbortRequested` event in trace) happens at the same drain — but via the bus (D-BUS-1), which is synchronous, so the visibility is contemporaneous with the acquisition.

Under Step 10 Direction A's deferred-from-Phase-A ingress: an envelope acquires authority at execute-entry (predicate closure) but visibility is *deferred* to post-Phase-E classification (D-FAULT-3b row 1 emits the `OperatorAbortRequested` only after Phase E returns, at session.py around line 1056). The acquisition is at execute-entry; the visibility is at post-Phase-E. The two are split.

### §I.2 Why the split matters under live ingress

Under live ingress, the split persists. Consider an envelope arriving at epoch K's pull:

* **Acquisition at Phase A:** the envelope is now in `_pending_envelopes`. The session's state at Phase A's end can be ABORTING (if the envelope drained and was abort).
* **Visibility at Phase A:** the bus emits `OperatorAbortRequested` synchronously during the drain. Trace records it. Same epoch.

The pure pre-queue path under live ingress collapses acquisition and visibility at the same Phase A.

Consider the deferred-from-Phase-A path (envelope visible at execute-entry, drained post-Phase-E):

* **Acquisition at execute-entry:** the predicate's closure includes the envelope. The executor will return EXECUTION_INTERRUPTED at the next eligible segment boundary.
* **Visibility at post-Phase-E:** the session's D-FAULT-3b classification emits the deferred `OperatorAbortRequested`. The trace records it.

Same epoch (same orchestration tick), but multi-phase. The bus's seq counter advances correctly because the deferred emission happens during the same `session.step()`.

### §I.3 The boundary alignment under live ingress

The substrate's invariant (analytical, not novel):

> Authority acquisition and authority visibility happen within the same orchestration tick.

This is preserved under live ingress IFF:

* The pull at Phase A is the sole acquisition surface (channel-as-opaque-buffer).
* The drain at Phase A is the sole visibility surface for Phase-A-drained envelopes.
* The deferred-from-Phase-A emission at post-Phase-E is the sole visibility surface for execute-entry-captured envelopes.
* No other surface acquires authority or makes it visible.

Both surfaces are inside one `session.step()`. The orchestration tick at which both happen is the same K. The trace records the visibility at the seq the bus assigns. Replay reconstructs both deterministically.

### §I.4 Hidden authority acquisition (the threat)

The threat is acquisition without visibility, OR visibility without acquisition, OR acquisition + visibility at different boundaries.

* **Acquisition without visibility** = silent influence. If the channel's pull at Phase A subtly changes session state (e.g., a transport-layer error reduces the session's retry budget by reading from the transport), the influence is acquired but not visible in the trace. D-FAULT-14 violation.

* **Visibility without acquisition** = stub events. If the bus emits an event that has no orchestration-state effect, it would be diagnostic dressed up as authoritative. The current substrate doesn't have this pattern (every emitted event corresponds to an authority transition).

* **Boundary misalignment** = acquisition at tick K, visibility at tick K' ≠ K. This requires either retroactive emission (D-TRACE-2 violation) or delayed acquisition with deferred visibility — but the deferred-from-Phase-A pattern in Step 10 Direction A *aligns* acquisition and visibility within one tick. Step 11 must not break this alignment.

The analysis finds: the channel-as-opaque-buffer topology preserves boundary alignment. The pre-execute second-epoch rejection (§F.4) preserves it. The pull-only constraint preserves it.

### §I.5 Replay-proof of "WHY this boundary"

The session brief asks: "whether replay can prove WHY an ingress became authoritative at a specific boundary."

Under the channel-as-opaque-buffer + canonical-drain + epoch-aligned topology, the trace records:

* the envelope_id (content);
* the seq (order);
* the orchestration_tick at drain (epoch);
* the session's `_terminator_reason` (transition's cause: `"OPERATOR_ABORT"`);
* the post-drain state transition (SessionAborting event payload's `terminator_reason` + `trigger_envelope_id`, at [session.py:1408-1411](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py#L1408-L1411)).

These five pieces of information answer "why did this ingress become authoritative at this orchestration_tick K?":

* because the envelope's `requested_at_tick <= K` (eligibility),
* because it was present in `_pending_envelopes` at K's Phase A pull (visibility),
* because the canonical order made it the first or only abort to drain (causality),
* because the session was in RUNNING state at the drain (state-predicate),
* because the bus seq sequence is gap-free (replay-stability).

Replay reconstructs all five from the trace. The "WHY" question is fully discharged.

---

## §J. Interruption-timing authority under live ingress

### §J.1 Restating §B's theorem in live-ingress terms

A live-arrived envelope can influence:

* **N's Phase A drain** if the envelope was visible at N's Phase A pull (i.e., arrived strictly before the pull) AND `requested_at_tick <= K_N`. Effect: session transitions to ABORTING before any scheduler decision for N.
* **N's execute-entry predicate** if the envelope was visible at N's Phase A pull (post-drain `_pending_envelopes` still contains it — possible only if it didn't drain, e.g., its `requested_at_tick > K_N` initially but became eligible later, OR if its kind is non-abort and doesn't trigger transition). Open question: under abort kind, the envelope drains immediately at Phase A; it cannot survive into Phase D for execute-entry predicate. Under hypothetical Step 11 kinds (`pause`, `manual_advance`), the eligibility-at-Phase-A versus consumption-at-Phase-D semantics need clause-level disambiguation. See §M.5.

The live channel does NOT enable any new mid-Phase-E influence pathway. The theorem of §B.4 holds: mid-Phase-E arrival → next-tick observation, with the substrate-mandated latency.

### §J.2 The latency-floor framing (analytical)

The latency floor between wall-clock arrival and orchestration-observable authority is:

* **best case** = ~0 ticks: envelope arrives in the wall-clock interval immediately before Phase A pull. Drained that same Phase A. Effect at Phase B / E of the same tick.
* **typical case** = 1 tick: envelope arrives between Phase A pull of session.step(K) and Phase A pull of session.step(K+1). Effect at session.step(K+1).
* **worst case** = current-node's-Phase-E-remainder ticks: envelope arrives mid-Phase-E of session.step(K). Effect at session.step(K+1) Phase A, but observed only after Phase E of K completes — wall-clock duration depends on the trajectory.

The "typical case" and "worst case" agree on the epoch (K+1) but differ on the wall-clock duration of waiting. The trace records the epoch; wall-clock is diagnostic.

### §J.3 Recovery-node interaction is unchanged

D-FAULT-8 makes recovery exclusively graph-explicit. A live-arrived envelope cannot influence which recovery node fires; only the graph's edge structure does. The envelope can ABORT the session (cascade-skip all remaining pending nodes), but cannot select a recovery node.

If Step 11 introduces non-abort kinds (`manual_advance`), the analysis must check whether they create implicit recovery surfaces. Specifically:

* `manual_advance` as "operator forces the scheduler to select node X next" would create a hidden authority over scheduler decisions, violating D-SCHED-1 (pure-function discipline).
* `manual_advance` as "operator submits a new graph-explicit recovery node" would need a runtime graph-mutation surface, violating D-FORBID-4 (no runtime graph mutation) + D-FAULT-15 #13 (no live-mutating FailureAction).

Both interpretations of `manual_advance` are constitutionally incompatible under the current substrate. The kind is reserved in D-FAULT-9a but its semantics have no constitutionally-compatible form. The analytical finding: **`manual_advance` reserved name SHOULD NOT be implemented as Step 11 scope** unless a separate compatibility analysis discharges its semantics. See §M.5 for the kinds-by-kind audit.

### §J.4 The "abort during recovery" question

If the session is currently executing a recovery node (one with `metadata["recovery_of"] = "..."`), and a live-arrived abort envelope drains at the recovery node's Phase A, can the abort interrupt the recovery?

The substrate's answer is yes — abort transitions RUNNING → ABORTING regardless of which node is current. Recovery nodes are normal nodes from the scheduler's perspective (D-FAULT-8). Cascade-skip applies uniformly.

The analytical implication: live ingress does not need special handling for recovery nodes. The recovery-as-graph-topology discipline composes with abort-as-Phase-A-drain trivially.

### §J.5 The "tick budget under live abort" interaction

Under D-FAULT-12, tick budget enforcement is post-Phase-E. If a node times out (ticks_consumed > tick_budget_ticks) AND a live-arrived abort envelope drained at the same tick's Phase A, the session must classify per D-FAULT-3b's declared-order rule:

* Row 1: envelope eligible → OPERATOR_ABORT.
* Row 2: budget exceeded → TIMEOUT_FAILURE.

D-FAULT-3b is declared-order. Row 1 fires first. The session classifies as OPERATOR_ABORT, not TIMEOUT_FAILURE. This is the current Step 10 Direction A behavior; live ingress does not alter it.

The analytical implication: live ingress preserves D-FAULT-3b's priority ordering. No new classification rule is needed.

---

## §K. Phase E atomicity preservation under live ingress

### §K.1 The atomicity invariant (D-FAULT-6a + D-EXEC-13a)

Phase E is atomic from the orchestration's perspective. The session calls `executor.execute()` once, observes one `TaskResult` return, and proceeds to Phase F/G. The session must NOT, during a single Phase E:

* interleave Phase A envelope drains (D-EXEC-13a explicitly forbids this);
* dispatch the EventBus;
* emit events;
* take boundary snapshots;
* observe `segment_tick` values or per-segment events.

### §K.2 Where live ingress could violate it

Three temptations:

1. **Mid-Phase-E channel pull.** Tempting: "the live channel has an envelope, let's drain it now to abort the executor mid-trajectory." Forbidden — D-FAULT-15 #5 (orchestration-observable mid-Phase-E interrupt), #27 (mid-execute envelope drain).

2. **Channel-driven executor signal.** Tempting: "let the live channel signal the executor directly, bypassing the predicate, to terminate execute()." Forbidden — D-FAULT-15 #16 (method-as-ingress), #20 (predicate constructed outside session), #28 (async/signal interrupt mechanism), #29 (predicate mutation mid-execute).

3. **Background thread mutating `_pending_envelopes` during Phase E.** Tempting: "let a background listener thread append to `_pending_envelopes` while Phase E runs; the next Phase A drain catches them." Subtle violation — D-FORBID-1 (no async/threading in orchestration code), D-SESS-1 (session is the sole mutator). Even if the mutation only affects the next Phase A drain and is invisible during this Phase E, the existence of a background mutator threatens replay-stability if the mutation order (within the thread) depends on wall-clock.

The channel-as-opaque-buffer topology in §D.3 sidesteps all three by making the channel a passive store the session reads only at Phase A.

### §K.3 The "atomic-snapshot pull" mechanic

§D.4 prefers option 1 (strict snapshot). The pull operation at Phase A is:

```
with channel.lock:
    snapshot = tuple(channel.buffer)
    channel.buffer = []
# 'snapshot' is the epoch's envelope set
```

The lock is held briefly; the mutation is atomic. During Phase B–G of this tick, the channel can receive new arrivals freely (into the new empty buffer); they are invisible to this tick.

The lock IS a thread-synchronization primitive, but it does NOT grant mutation authority over orchestration state. It only synchronizes access to the channel's buffer. The session holds the lock momentarily; the transport holds it momentarily on push. Neither has read or write authority over orchestration state via the lock.

This is *not* D-FORBID-1 violation. D-FORBID-1 forbids `asyncio`, `async def`, `await`, etc., in *orchestration code*. The channel's lock is *transport-layer infrastructure*, not orchestration logic. The distinction matters: locks for buffer protection are mechanical; locks as synchronization primitives over orchestration state would be authority violations.

If a Step 11 implementation uses `threading.Lock` (or equivalent) for buffer atomic-snapshot, it does so at the channel layer, not at the session layer. The session sees a sync, deterministic pull return value.

### §K.4 The "channel pull cost" question

Pulling the channel at every Phase A costs O(buffer size) per tick. For a typical job with a handful of envelopes per session, this is negligible. For a long-running session with thousands of envelopes (an extreme operator-spam scenario), the pull is still O(n) per tick. Replay-stability holds regardless.

This is an implementation observation, not a contract concern.

### §K.5 Phase E remains atomic. Empirical evidence.

Step 10 Direction A's Phase 6 closure (12/12 cycles byte-identical) shows that under the existing pre-queue + execute-entry-predicate topology, Phase E atomicity is empirically preserved. Live ingress adds a Phase A pull but does not alter Phase E. The atomicity proof carries forward.

---

## §L. Contradiction preservation under live ingress

### §L.1 D-FAULT-5b restated

If a node interrupts after acquire but before place (the F-scenario), the retained state is the contradiction-preserving state:

* peg D-LIFE state = `attached` (last observable);
* fixture occupancy = unchanged (no PASS, no D-CONT-5 commit);
* peg canonical pose = last-tick write (D-CONT-1, D-FAULT-5a);
* result: contradiction between occupancy ("nothing here") and pose ("the peg is here").

D-FAULT-5b: the contradiction is REQUIRED to be preserved verbatim. No implicit cleanup. No rollback. The recovery node (D-FAULT-8) resolves it explicitly.

### §L.2 Live-ingress impact on contradiction preservation

A live-arrived abort envelope, draining at epoch K+1 after the original session.step(K) interrupted N1 mid-transport, produces:

* N1's `TaskResult.outcome = EXECUTION_INTERRUPTED` (from the original predicate's True return — but wait, the original predicate at N1's execute-entry didn't see the envelope, because the envelope arrived after Phase A of K and during Phase E of K).
* Actually, under the theorem (§B.4), the predicate at N1's execute-entry did not see the envelope; the executor ran N1 to mechanical completion (or to a different EXECUTION_INTERRUPTED triggered by some other predicate condition).
* The envelope drains at K+1's Phase A. By that point, N1 has either completed PASS or completed with some outcome (the session is now post-Phase-G of K). The session is in RUNNING state.
* Phase A drain transitions to ABORTING. Cascade-skip all remaining pending nodes.

The contradiction state from D-FAULT-5b applies if N1's outcome was non-PASS — independent of whether the live envelope was involved. Live ingress does not alter D-FAULT-5b's applicability. The contradiction preservation discipline is unchanged.

### §L.3 The cross-cycle contradiction interaction

The `--reopen-stage-between-cycles` isolation policy validated in Step 10 Direction A's Phase 6 (Bucket B finding) was needed because PhysX articulation state survived `World.reset()` across cycles. The retained-state contradiction at end-of-cycle-1 (peg attached + FixtureA empty + peg pose moved) was preserved authoritatively; the divergence was a launcher-level isolation problem.

Live ingress doesn't change this story. The contradiction state is identical between (i) a pre-queue session interrupted at boundary 6 and (ii) a live-ingress session interrupted at boundary 6 via an envelope that arrived after Phase A pull. The retained state is byte-equal. The isolation policy carries forward.

### §L.4 The "live abort during contradiction" question

If a session is in the contradiction state (post-N1-fail, pre-recovery-node), and the operator submits a live abort:

* The abort drains at the next Phase A.
* Session transitions to ABORTING.
* Cascade-skip remaining pending nodes (including the recovery node).
* Session closes in ABORTED state.
* The contradiction state at session close is the same contradiction state that existed at Phase G of N1's failure — D-FAULT-5/5a/5b preserve it.
* The trace records: N1 NodeExecutionCompleted (passed=False), the post-N1 boundary snapshot (with contradiction), then post-K+1 Phase-A drain emits OperatorAbortRequested + SessionAborting + cascade-skips for recovery node and any others, then close emits SessionAborted.

The contradiction is preserved through the abort. No cleanup. The recovery node was skipped, not executed. D-FAULT-5b holds.

### §L.5 The "contradiction timing" question

The session brief asks about "contradiction timing semantics." Under live ingress, contradictions persist across orchestration ticks identically to pre-queue: each tick's boundary snapshot serializes the current state via D-CONT-6 allowlist-only projection; the contradiction (if any) is materialized in the snapshot. No new tick or epoch produces a new contradiction; no cleanup elides one. The temporal evolution of the contradiction is a sequence of identical snapshots (canonical_hash byte-equal) until either (a) a recovery node fires and resolves it, or (b) the session terminates carrying the contradiction in the final snapshot.

Live ingress preserves this. The analytical finding: contradiction timing is **a function of the session's failure-event history, not of the ingress channel**. Live ingress's only effect on contradiction timing is potentially shortening the contradiction's lifetime (by aborting before a recovery node fires, leaving the contradiction in the terminal snapshot). This is a no-op for D-FAULT-5b; the contradiction is preserved verbatim either way.

---

## §M. Interaction with D-FAULT, D-CONT, D-EXEC

### §M.1 D-FAULT-1 (failure taxonomy)

Unchanged. The eight orchestration-level classes are immutable. Live ingress does not introduce a new class. `OPERATOR_ABORT` is the only class live ingress activates; it is the existing class (D-FAULT-1 row "OPERATOR_ABORT").

### §M.2 D-FAULT-2 (single-emitter discipline)

Preserved IFF the channel is opaque-pull-only (§D.3). The session remains the sole emitter of `OperatorAbortRequested`. The channel emits nothing.

### §M.3 D-FAULT-3 (propagation rules)

Unchanged. OPERATOR_ABORT cascades uniformly via `_cascade_skip_remaining_pending(reason="OPERATOR_ABORT")` (already at [session.py:853](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py#L853) and [session.py:1108](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py#L1108)). Live ingress feeds the same path.

### §M.4 D-FAULT-3b (declared-order classification)

Unchanged. The classification rule operates on (envelope_snapshot, base_tick, ticks_consumed, tick_budget_ticks). The envelope_snapshot under live ingress comes from `_pending_envelopes` at execute-entry, which now incorporates live-arrived envelopes. The classifier itself is pure-function; live ingress doesn't alter its inputs' types or sources.

### §M.5 D-FAULT-9 / D-FAULT-9a (envelope schema and kind whitelist)

D-FAULT-9 specifies the envelope schema. D-FAULT-9a reserves `pause`/`resume`/`manual_advance` for Step 11. Each kind needs a kind-by-kind compatibility audit:

* **`abort`** (Step 9, Step 10 Direction A — empirically validated). Constitutionally compatible. Cascades via OPERATOR_ABORT (D-FAULT-1, D-FAULT-3 row 6). Live-ingress generalizable.

* **`pause`** — implies a session-state where `session.step()` returns but Phase B does NOT select a node, and the session waits for `resume`. This is a RECOVERING-like state (D-FAULT-15 #18 forbids `RECOVERING`). It requires the orchestration tick to stop advancing or to advance with no scheduler decision. The latter is supportable: a no-op Phase B at each tick. But the wall-clock semantics ("how long does the session wait?") have no contract surface. The session ticks idly until `resume` envelope arrives. Idle ticking is constitutionally compatible IFF tick advancement remains deterministic (one tick per session.step() call).
  * **Implication**: PAUSED is potentially a deterministic state (idle no-op ticks), but only if the caller drives the cadence. If the implementation introduces a wall-clock wait (e.g., sleep until resume arrives), the wall-clock is leaking into orchestration. The clean shape: PAUSED is a state in which `session.step()` is callable, Phase A drains envelopes (catching `resume`), Phase B selects nothing, tick advances. The caller decides cadence; the substrate doesn't time.
  * **Open analytical question**: does the contract permit a SessionState value for PAUSED, given D-FAULT-15 #18's strong prohibition on RECOVERING? RECOVERING was rejected because it muddled D-FAULT-3 propagation. PAUSED would have different semantics — it freezes propagation entirely (no scheduler decisions). Whether this is constitutionally analogous to RECOVERING or a clean separate concept is **open** for Step 11's contract phase.

* **`resume`** — symmetric to `pause`. Drains at Phase A of a PAUSED session; transitions PAUSED → RUNNING; subsequent Phase B selects nodes again. Constitutionally compatible IFF PAUSED is.

* **`manual_advance`** — semantically ambiguous. Two readings:
  * "Operator forces selection of a specific node next" — violates D-SCHED-1 (scheduler is pure-function over graph/registry/completed/failed/retry_counts). The scheduler must not branch on operator input.
  * "Operator advances the session by one tick" — already the caller's job. The caller chooses when to call session.step(). No new envelope needed.
  * Both readings are problematic. The analytical finding: **`manual_advance` has no constitutionally-compatible semantic under the current substrate**. Either Step 11 redefines its meaning (preferably: drop it from the reserved set) or Step 11 omits it.

The kind-by-kind audit shows: live ingress's channel mechanism is orthogonal to the envelope-kind set. The channel can support `abort` immediately. `pause`/`resume` need a separate analysis on PAUSED state semantics. `manual_advance` needs a fundamental reinterpretation or removal from the reserved set.

### §M.6 D-FAULT-12 / D-FAULT-12a (tick-budget enforcement)

Unchanged. Live ingress does not alter ticks_consumed accounting. The classifier's row 2 (TIMEOUT_FAILURE) still applies; D-FAULT-3b declared-order still fires row 1 first if both envelope-eligibility and budget-exceeded are true.

### §M.7 D-FAULT-14 (no implicit secondary orchestration)

Preserved IFF the channel is opaque-pull-only AND the trace records every ingress event. Implicit secondary orchestration would arise if the channel:

* triggered side effects without a recorded event (D-FAULT-14 violation);
* maintained its own state machine (e.g., "pending abort" / "acknowledged abort" — a second orchestration system);
* coordinated with the session via any non-pull mechanism.

The opaque-buffer topology has none of these. Strictly: the channel is a list; the session pulls; the trace records.

### §M.8 D-FAULT-15 row impact

Live ingress adds zero new anti-patterns... if implemented per the channel-as-opaque-buffer topology. If implemented with a callback or thread-driven mutation of session state, multiple rows (5, 16, 22, 27, 28, 29, 30) are violated simultaneously.

Step 11's hard non-introduction list (§Q below) extends D-FAULT-15 with rows specific to live-channel anti-patterns. (Analytical observation, not clause proposal.)

### §M.9 D-CONT family

* **D-CONT-1** (authoritative continuity enumeration) — unchanged. The live-arrived envelope's record in trace events is not retained-continuity state per se; it's an event-stream observation. Boundary snapshots don't include live-channel state.
* **D-CONT-2** (non-authoritative continuity inputs) — strengthened by §C.5: transport-layer metadata is non-authoritative.
* **D-CONT-3** (boundary PhysX-quiescence) — unchanged. Phase A's channel pull does not call world.step(); no PhysX activity.
* **D-CONT-4** (ACQUIRED_ONLY semantics) — unchanged. The live channel does not alter cross-node reset behavior.
* **D-CONT-5** (occupancy authority) — unchanged. Live abort does not commit occupancy; it can only abort an in-progress session, leaving occupancy unchanged from session_initial.
* **D-CONT-6** (boundary snapshot canonicality, allowlist-only) — unchanged. The allowlist explicitly excludes live-channel state; boundary snapshots don't serialize transport metadata. The trace's `OperatorAbortRequested` events are separate from boundary snapshots.
* **D-CONT-7** (observational projection discipline) — unchanged.
* **D-CONT-7a** (field classification on landing) — applies to any new field in the envelope payload. The session brief frames Step 11 as not introducing new fields; the audit confirms no field additions are required for the channel mechanism (only for the kind expansion in §M.5).

### §M.10 D-EXEC family

* **D-EXEC-1** (7-phase order) — unchanged. The Phase A pull happens *at the start* of Phase A, before envelope drain. It's a sub-phase-A activity, not a new phase.
* **D-EXEC-2** (events out of phase forbidden) — unchanged. The OperatorAbortRequested event is emitted at Phase A (or, in the deferred-from-Phase-A case, post-Phase-E in the same tick).
* **D-EXEC-3** (one transition per tick) — unchanged.
* **D-EXEC-4..-12** — unchanged.
* **D-EXEC-13 a/b/c/d** — unchanged. The predicate's closure capture at execute-entry reads `_pending_envelopes` as Phase A's drain + pull left it. The predicate is still session-constructed.

### §M.11 D-SCHED family

* **D-SCHED-1..-13** — unchanged. The scheduler does not read the live channel directly. The session feeds it the same inputs.

### §M.12 D-BUS family

* **D-BUS-1..-12** — unchanged. The bus is synchronous, ordered. The pull at Phase A is not a bus operation. The drain emits via the bus identically to pre-queue.

### §M.13 D-REPLAY family

* **D-REPLAY-1..-9** — unchanged. The replay-identity layers L1–L4 hold under live ingress per the §H proof sketch.

### §M.14 D-SESS family

* **D-SESS-1..-8** — unchanged. The session is still the sole mutable-state authority. The channel is not session state; it's transport infrastructure.

### §M.15 D-TRACE family

* **D-TRACE-1..-8** — unchanged. The trace records `OperatorAbortRequested` events identically. Manifest fields might gain a diagnostic `live_ingress_enabled: bool` flag, but this is non-authoritative.

### §M.16 D-LIFE family

* **D-LIFE-1..-9** — unchanged. Live ingress does not alter object lifecycle transitions.

### §M.17 D-FORBID family

* **D-FORBID-1..-14** — unchanged in spirit. D-FORBID-1 (no async/threading in orchestration code) requires careful reading: the channel may use threading internally for transport reception, but the session's pull is synchronous. The orchestration code itself remains synchronous.

### §M.18 Summary of contract interaction

No clause requires weakening. No clause requires extension to admit live ingress at the channel-mechanism level. The kind-expansion (M.5) is a separate question that may require clause work (PAUSED semantics, manual_advance redefinition). The channel mechanism itself is constitutionally compatible.

---

## §N. Visibility-boundary semantics

### §N.1 The intra-cycle visibility question

Session brief: "whether intra-cycle visibility is constitutionally compatible." A "cycle" here is one `session.step()` (one orchestration tick).

Intra-cycle visibility candidates:

* **Phase A pull → drain → emit `OperatorAbortRequested` at Phase A**: same-cycle visibility. Already in the substrate.
* **Phase A pull → execute-entry predicate closure → execute returns EXECUTION_INTERRUPTED → Phase F/G emit deferred `OperatorAbortRequested`**: same-cycle visibility, multi-phase. Step 10 Direction A.
* **Mid-Phase-E pull → mid-Phase-E observation**: forbidden. Not a candidate.
* **Phase G pull → post-emission**: would create a post-tick observation surface. Currently no clause forbids it explicitly, but it duplicates the Phase A pull. Analytical preference: single pull at Phase A.

Intra-cycle visibility is constitutionally compatible for the two candidates that already exist in the substrate. Live ingress operates within both.

### §N.2 The cross-cycle visibility question

An envelope arrives during cycle K's Phase E (between Phase A pull and Phase G commit). Visibility at cycle K+1's Phase A pull. The cross-cycle observation is the typical case from §J.2.

Cross-cycle visibility is the substrate's default behavior. No new clause needed.

### §N.3 Visibility latency formalization

For an envelope arriving at wall-clock instant W:

* Let K = the orchestration tick at which the *next* Phase A pull happens at wall-clock instant ≥ W. (Well-defined if `session.step()` is being called; trivially "the next call's Phase A pull.")
* Visibility latency = K's wall-clock instant - W = duration from arrival to next pull.
* Bounded above by: the remainder of the current cycle's Phase E (if W falls inside Phase E) + any pre-step delay (if the caller pauses between session.step() calls).
* Bounded below by: zero (if W falls immediately before Phase A pull).

The substrate has no opinion on the wall-clock magnitude. Replay-authority is preserved because visibility latency is non-authoritative.

### §N.4 The "starvation" question (analytical only)

If `session.step()` is never called (e.g., the caller has stalled), live-arrived envelopes pile in the channel buffer indefinitely. They are not lost; they are observed at the next Phase A pull, whenever that happens. The substrate's replay-authority does not depend on bounded wall-clock latency.

A caller that wants bounded latency must drive session.step() at the desired cadence. The substrate does not pace. This is consistent with D-FORBID-11 (per-tick wall-time pacing forbidden) — the substrate does not impose a tick rate.

---

## §O. Three candidate ingress shapes (analysis only, no recommendation)

This section enumerates three candidate live-ingress shapes for analytical completeness. **No recommendation is made.** Step 11's contract phase (deferred indefinitely from this analysis-only session) would select one or reject all.

### §O.1 Shape A: Constructor-supplied passive buffer

The caller constructs `ExecutionSession` with a `live_envelope_source: Callable[[], tuple[OperatorEnvelope, ...]]` parameter — a pull function. At each Phase A, the session calls the function and merges its return value into `_pending_envelopes`.

* **Pro**: explicit, declarative, no runtime mutation of session-owned state by external entities.
* **Pro**: trivial to test (pass a callable that returns a fixed sequence; replay-equivalent to pre-queue).
* **Con**: the callable itself can have wall-clock dependencies (the caller's responsibility to make it deterministic at replay time, which contradicts the use case — live channels are non-deterministic).
* **Con**: requires the substrate to invoke external code at Phase A. The external code IS, by construction, a transport layer.

### §O.2 Shape B: External-mutator buffer protocol

`ExecutionSession` exposes a `LiveIngressBuffer` object (owned by the session, mutable-from-outside) with an `append(env: OperatorEnvelope)` method. External agents (transport, test fixture) call `buffer.append(env)` at any time. The session reads the buffer at Phase A.

* **Pro**: clean separation of transport and session.
* **Pro**: buffer's mutation discipline is local to the buffer object.
* **Con**: a public mutator method on a session-owned object is a soft authority surface. Requires the buffer's `append` to be replay-stable (e.g., it records the appended envelope to the trace immediately, OR it defers recording to Phase A).
* **Con**: tempts D-FAULT-15 #16 (method-as-ingress) — `buffer.append(env)` IS a method-as-ingress, just on a different object than `session.request_abort()`. The clause's spirit applies: any method that admits orchestration input is method-as-ingress.

*Open analytical question*: does `buffer.append()` constitute method-as-ingress under D-FAULT-15 #16's strict reading? The clause cites `ExecutionSession.request_abort()`. The buffer's append is one layer removed. Whether the spirit of the clause covers it is open.

### §O.3 Shape C: Sidecar file polling

The session reads a directory at every Phase A. The directory contains `*.envelope.json` files dropped by external processes. The session reads them, canonical-orders by filename + content, and treats them as the live-arrived set.

* **Pro**: zero IPC complexity. The transport is the filesystem.
* **Pro**: replay-trivially: the test fixture can drop files between session.step() calls.
* **Con**: filesystem-as-transport has performance costs (mostly irrelevant — Phase A is not perf-critical).
* **Con**: tempts wall-clock leakage via file mtime (filename-only ordering avoids this).
* **Con**: a directory poll at every Phase A introduces filesystem I/O into the orchestration tick. Not forbidden, but creates a portability concern.

### §O.4 Shape comparison

| dimension | Shape A | Shape B | Shape C |
|---|---|---|---|
| transport-agnostic | yes (callable) | yes (object) | no (filesystem) |
| pull-only | yes | no (push-API on the buffer) | yes (poll the directory) |
| D-FAULT-2 single-emitter compatible | yes | yes (buffer doesn't emit) | yes |
| D-FAULT-15 #16 compatible | yes | open (see §O.2 con) | yes |
| D-FORBID-1 thread compatible | yes (callable owns its threads, if any) | yes (buffer owns its threads) | yes (no threading) |
| replay-stable | iff callable is | iff buffer's mutation is | yes (filenames are content-addressable) |
| testability | trivial | easy | easy |
| transport extension | requires caller-side glue | requires buffer-side glue | requires filesystem watcher |

No shape is uniformly best. The choice depends on Step 11's chosen transport stack and on the resolution of §O.2's open question.

### §O.5 What all three shapes share

All three shapes preserve:

* the canonical-drain order at Phase A;
* the trace's `OperatorAbortRequested` event payload schema;
* the D-FAULT-2 single-emitter discipline;
* the §H replay-reconstruction proof sketch;
* the §B.4 N2-only-interruption impossibility theorem;
* the §F drain-epoch quantization.

The shapes differ in transport semantics. They do not differ in causal topology. Any of them, implemented per §D.3's channel-as-opaque-buffer constraint, preserves the substrate's constitutional posture.

---

## §P. Hidden-authority threat models

### §P.1 Threat model 1: Callback authority

A live channel implementation registers a callback at session construction: `session.on_envelope(callback)`. When the channel receives an envelope, it invokes the callback, which mutates `_pending_envelopes` directly.

* **Authority surface**: the callback runs in the channel's thread (or async task), mutating session state.
* **Violations**: D-FAULT-15 #16 (method-as-ingress via callback registration); D-FORBID-1 (async/threading in orchestration code if the callback is invoked asynchronously); D-SESS-1 (session is sole mutator — callback is external mutator); D-BUS-6/7/8 (subscriber topology frozen — but `on_envelope` is not a subscriber per se; still smells).

* **Mitigation**: do not expose callbacks. Channel-as-opaque-buffer (§D.3).

### §P.2 Threat model 2: Sub-tick observation

A live channel implementation, observing that envelopes can arrive during Phase E, polls the channel at multiple points within `session.step()` — e.g., at end of Phase A, end of Phase D, start of Phase F. This creates sub-tick observation epochs.

* **Authority surface**: each poll observes a different envelope set. The session has multiple ingress observation points within one tick.
* **Violations**: D-EXEC-1 (7-phase order, no sub-phases); D-EXEC-2 (events out of phase forbidden if any poll triggers emission); D-FAULT-15 #27 (mid-execute envelope drain — applies if a poll happens during Phase E).

* **Mitigation**: single pull at Phase A. The pre-execute second-epoch rejection (§F.4).

### §P.3 Threat model 3: Wall-clock arrival as authority

A live channel implementation records `arrived_at_wall_ns` on each envelope. The session reads `arrived_at_wall_ns` to break ties when multiple envelopes have the same `requested_at_tick`.

* **Authority surface**: wall-clock timestamps enter the orchestration's ordering decision.
* **Violations**: D-FORBID-6 (wall-clock-dependent behavior); D-FAULT-15 #10 (wall-clock budget); D-SCHED-11 (wall-clock in scheduler decisions forbidden — the ordering of drained envelopes affects which abort wins under non-idempotent kinds).

* **Mitigation**: canonical order by `(requested_at_tick, envelope_id)`. Content-addressed envelope_id (§C.4).

### §P.4 Threat model 4: Transport-layer ordering as authority

A live channel implementation orders envelopes by transport-layer arrival sequence (e.g., websocket message order). The session inherits this order.

* **Authority surface**: transport order leaks into orchestration order.
* **Violations**: D-SCHED-1 (scheduler is pure function over documented inputs — transport is not a documented input); D-SCHED-5..-7 (iteration must use canonical orderings, not transport-defined).

* **Mitigation**: canonical-order discipline at Phase A. Discard transport order at the pull boundary.

### §P.5 Threat model 5: Channel-as-state-machine

A live channel implementation maintains its own state ("pending", "acknowledged", "rejected") and exposes that state to subscribers. Some subscribers branch on it.

* **Authority surface**: a second state machine, not in `events.jsonl`, influences orchestration decisions.
* **Violations**: D-FAULT-14 (implicit secondary orchestration); D-SESS-4 (derived state must be recomputable from authoritative inputs — channel state is not recomputable from the trace).

* **Mitigation**: the channel is a list. No state. Append + pop. No ack semantics. No retry. No backoff. The transport may have these; the substrate's view is stateless.

### §P.6 Threat model 6: Predicate substitution mid-execute

A live channel implementation, observing an envelope arriving during Phase E, attempts to substitute the executor's interruption predicate with a new one that includes the new envelope. The executor honors the new predicate at the next segment boundary.

* **Authority surface**: predicate mutation during execute is a hidden runtime channel.
* **Violations**: D-EXEC-13c (predicate substitution mid-execute forbidden); D-FAULT-15 #29 (adaptive interruption forbidden); D-EXEC-13a (Phase E atomicity).

* **Mitigation**: predicate captured at execute-entry; immutable for the duration of execute. Step 10 Direction A's frozen discipline (D-EXEC-13c).

### §P.7 Threat model 7: PAUSED-as-wall-clock-wait

A live channel implementation, on receiving a `pause` envelope, blocks the calling thread until a `resume` envelope arrives. `session.step()` does not return.

* **Authority surface**: the substrate is now wall-clock-bound. Replay-determinism is intact (the trace records `pause` and `resume`), but the substrate's tick-cadence has become caller-non-deterministic.
* **Violations**: D-FORBID-11 (per-tick wall-time pacing forbidden, though arguably this is between-tick pacing — open).

* **Mitigation**: PAUSED is a state in which `session.step()` returns no-op snapshots, not blocks. The caller drives cadence. The wait is at the caller layer, not the substrate.

### §P.8 Threat model 8: Cross-session live channel state

A live channel implementation maintains a connection that survives across multiple sessions in the same process. The connection's state (last-seen envelope_id, retry queue) leaks into subsequent sessions.

* **Authority surface**: cross-session state contaminates within-session determinism.
* **Violations**: D-FORBID-12 (cross-session shared state forbidden); D-FAULT-15 #12 (cross-session retained-state continuity for recovery — but this is broader).

* **Mitigation**: the channel is per-session. Constructed at `session.begin()`, torn down at `session.close()`. No process-global state.

### §P.9 Aggregate mitigation: channel-as-opaque-buffer + Phase-A-only pull

All eight threat models collapse if the live channel is:

* opaque (no observable state beyond its contents);
* pull-only (no callbacks, no notifications);
* read only at Phase A (no sub-tick observation);
* per-session (no cross-session leak);
* canonical-ordering at the pull boundary (no transport-layer order leak);
* without wall-clock fields in its envelope set;
* without retry/state-machine semantics observable to the substrate;
* without ability to mutate `_pending_envelopes` after Phase A.

This is the analytical conclusion: **the threat-mitigated topology is the channel-as-opaque-buffer of §D.3.**

---

## §Q. Hard non-introduction list (Step 11 extension to D-FAULT-15)

The following anti-patterns extend D-FAULT-15's existing rows 1–30. They are **analytical proposals**, not normative clauses; if Step 11 proceeds to contract phase, the clause authors will decide which to incorporate.

| # (proposed) | proposed forbidden pattern | cites |
|---|---|---|
| 31 | live-channel callback registration (any API by which the channel notifies the session of envelope arrival outside Phase A pull) | D-FAULT-15 #16, D-FORBID-1 |
| 32 | sub-tick channel pull (pulls at Phase B/C/D/E/F/G) | D-EXEC-1, D-EXEC-2 |
| 33 | mid-Phase-E channel pull (any read of channel state during executor.execute()) | D-FAULT-15 #5, #27, D-EXEC-13a |
| 34 | wall-clock arrival timestamp as authoritative field on OperatorEnvelope | D-FORBID-6, D-FAULT-15 #10, #22 |
| 35 | transport-layer ordering authority over canonical drain order | D-SCHED-1, D-SCHED-5..-7 |
| 36 | channel state machine observable to orchestration (ack/nack, pending/processed) | D-FAULT-14, D-SESS-4 |
| 37 | cross-session live-channel state (channel survives `session.close()` in same process) | D-FORBID-12, D-FAULT-15 #12 |
| 38 | wall-clock blocking in PAUSED state (session.step blocks on resume arrival) | D-FORBID-11 |
| 39 | `manual_advance` envelope as scheduler override | D-SCHED-1, D-SCHED-3 |
| 40 | live-channel observation of session state (`session.session_state`, `session._completed`, etc. — read by the channel for routing decisions) | D-SESS-1, D-SESS-5 |
| 41 | retroactive ingress event editing (modifying a previously emitted `OperatorAbortRequested` event) | D-TRACE-2 |
| 42 | non-pull observation of channel contents (peek without consume) by orchestration code outside Phase A | D-FAULT-15 #27, D-EXEC-13a |

These twelve proposed rows (31–42) tighten Step 11's compatibility boundary by enumerating concrete anti-patterns at the channel layer. They are derived from §P's threat models. They are analysis-output, not contract clauses.

---

## §R. Substrate invariants carry-forward audit

The session brief enumerates 11 invariants to preserve. The analysis confirms each survives the channel-as-opaque-buffer topology:

| invariant | preservation under live ingress |
|---|---|
| replay-authoritative truth | ✅ trace records every ingress at Phase A; replay reconstructs from trace alone (§H) |
| append-only traces | ✅ no retroactive edit; every ingress = one append (§G.4) |
| deterministic failure ontology | ✅ D-FAULT-1 eight classes unchanged; OPERATOR_ABORT pathway unchanged (§M.1) |
| contradiction preservation | ✅ D-FAULT-5b unaltered; live abort during contradiction preserves it (§L.4) |
| deterministic interruption boundaries | ✅ predicate consultation discipline (D-EXEC-13) unchanged (§J.1) |
| authoritative ticks_consumed | ✅ D-FAULT-12c integer-count discipline unchanged (§M.6) |
| replay identity under reopen isolation | ✅ same isolation policy applies; live ingress doesn't alter PhysX state evolution (§L.3) |
| no hidden cleanup | ✅ no implicit channel-driven mutation (channel-as-opaque-buffer §D.3) |
| no replay-healing | ✅ trace is authoritative; channel state at replay time is reconstructed-from-trace, not regenerated (§G.3) |
| no adaptive recovery | ✅ recovery remains graph-explicit (D-FAULT-8); live envelopes can abort but cannot select recovery (§J.3) |
| no wall-clock authority | ✅ canonical order is content-addressed; `requested_at_tick` is integer (§E.3, §C.5) |

All 11 invariants survive.

---

## §S. Frozen-clause-preservation analysis

For each Step 8/9/10 frozen clause, the analysis identifies the survival mechanism under live ingress.

| clause | preservation mechanism |
|---|---|
| D-EXEC-1..-12 | unchanged — Phase A pull is sub-phase-A activity, not a new phase |
| D-EXEC-13 a/b/c/d | unchanged — predicate's closure capture reads `_pending_envelopes` as Phase A left it; the channel pull happened before |
| D-SCHED-1..-13 | unchanged — scheduler is still pure-function over (graph, registry, completed, failed, retry_counts) |
| D-BUS-1..-12 | unchanged — bus is synchronous; live ingress emits via the bus identically to pre-queue |
| D-REPLAY-1..-9 | unchanged — replay-identity is per-session; live ingress reconstructs from trace (§H) |
| D-SESS-1..-8 | unchanged — session is sole orchestration-state mutator; channel is non-state |
| D-TRACE-1..-8 | unchanged — trace is append-only; manifest may carry a non-authoritative diagnostic flag |
| D-LIFE-1..-9 | unchanged — lifecycle transitions are unrelated to live ingress |
| D-FORBID-1..-14 | unchanged — async/threading remains forbidden in orchestration code; channel transport may use threads internally |
| D-CONT-1..-7a | unchanged — boundary snapshot allowlist does not include channel state |
| D-FAULT-1..-15 | unchanged in normative content; D-FAULT-9a kinds may be revisited (§M.5) |
| D-CONF-1..-4 | unchanged — conformance discipline carries forward |

**No clause requires weakening, modification, or replacement** for the channel-as-opaque-buffer topology. The Step 11 contract phase (if pursued) would add new clauses, not modify existing ones.

If the kind expansion (§M.5) is in scope:

* `pause`/`resume` would require a new D-FAULT clause defining PAUSED as a SessionState value and its transitions.
* `manual_advance` cannot be admitted under the current substrate without contradicting D-SCHED-1; the clause is either re-interpreted or removed.

These kind-level clause additions are **separate from the channel-mechanism clause work**. The analytical finding: the channel mechanism is contract-additive only (new clauses; no edits to existing ones).

---

## §T. Open analytical questions

These are deferred to a future Step 11 analysis phase, if Step 11 contract work proceeds:

### §T.1 Buffer freezing discipline

§D.4 prefers strict snapshot (option 1) by elimination. A formal proof that strict snapshot is the *only* topology that closes all hidden-authority threats is open.

### §T.2 PAUSED semantics

§M.5 sketches PAUSED as a state in which `session.step()` returns no-op snapshots. Whether PAUSED is constitutionally distinct from RECOVERING (forbidden, D-FAULT-15 #18) is open. The clause-level disambiguation requires its own analysis pass.

### §T.3 `manual_advance` redefinition

§M.5 finds `manual_advance` has no constitutionally-compatible semantic. Whether to drop the reserved name from D-FAULT-9a or to re-define its semantic (e.g., as "operator confirms acceptance of a notification") is open.

### §T.4 D-FAULT-15 #16 strict reading on object-method ingress

§O.2 raises the question: does D-FAULT-15 #16 ("method-as-ingress forbidden") cover `buffer.append(env)` on a session-owned but externally-mutable object? The clause cites `ExecutionSession.request_abort()` directly; whether its spirit covers buffer mutators is open.

### §T.5 Diagnostic-state fields on OperatorAbortRequested

Could the payload carry `arrived_at_wall_ns` as a diagnostic-only field (similar to event `wall_ns`)? D-SESS-5 forbids diagnostic state read by orchestration logic; D-TRACE-5 allows diagnostic records outside the authoritative path. Whether the diagnostic field on the *event* (not on the envelope) is acceptable is open.

### §T.6 Subscriber-set extension for live channels

D-BUS-6/-7/-8 freeze subscriber topology at session start. If a live channel's transport layer wants to subscribe to bus events (for back-channel ack to operator), the subscriber must be registered at session.begin(). Whether this is operationally clean or whether it tempts cross-session subscriber persistence (D-FORBID-12) is open.

### §T.7 The "session._pending_envelopes contents in boundary snapshot" question

Currently, boundary snapshots (D-CONT-6 allowlist) do NOT include `_pending_envelopes`. Under pre-queue this is fine because the envelope tuple is recoverable from session construction. Under live ingress, `_pending_envelopes` is built progressively; a mid-session boundary snapshot does not reflect future arrivals. Whether boundary snapshots should serialize `_pending_envelopes` for completeness (e.g., for replay-from-snapshot scenarios) is open.

### §T.8 Liveness vs determinism trade-off

If a caller stalls (`session.step()` is never called again after some tick K), live-arrived envelopes pile in the channel indefinitely. This is not a determinism violation, but it is a liveness concern: the session is technically replay-deterministic but operationally non-progressing. Whether the substrate should expose a (diagnostic-only) "buffer depth" surface for caller visibility is open.

### §T.9 Strict-snapshot lock ordering

Under §D.4 option 1 (strict snapshot), the channel's lock is held briefly during the swap. If multiple sessions share a transport infrastructure (multiple ExecutionSession instances in one process — though D-FORBID-12 forbids cross-session state, this can occur if the transport itself is a singleton serving multiple sessions), lock ordering between transport-layer threads and session-layer threads needs analysis. This is implementation-detail-level and out of scope for the substrate.

These nine open questions catalog the remaining ambiguity. None of them affect the analytical verdict in §U.

---

## §U. Compatibility-boundary findings

### §U.1 The verdict

Live ingress is **constitutionally compatible** with the Step 8/9/10 substrate IFF implemented per the channel-as-opaque-buffer topology described in §D.3, with the additional disciplines:

1. The channel is a passive buffer; only the session reads it.
2. The session pulls the buffer exactly once per `session.step()`, at Phase A, before envelope drain.
3. The pull is a strict atomic snapshot (§D.4 option 1).
4. Canonical-order discipline applies after the pull (sort by `(requested_at_tick, envelope_id)`).
5. The pull's snapshot is merged into `_pending_envelopes`; the existing `_drain_phase_a_envelopes` runs unchanged.
6. Mid-Phase-E, no channel observation occurs.
7. The trace's `OperatorAbortRequested` event records the drain epoch and envelope_id; replay reconstructs the live-arrived set from the trace.
8. The transport layer is unconstrained except by negative constraints (no transport-state leak into orchestration, no callbacks into session, no cross-session persistence).

Under these eight disciplines, the analytical sketch (§H) shows replay-authoritative reconstruction is possible. No constitutional clause requires weakening. No hidden authority surface is introduced.

### §U.2 The "what live ingress cannot do" boundary

Live ingress does NOT enable:

* **mid-Phase-E interruption from a live arrival** (§B.4 theorem; latency floor = current node's Phase E remainder);
* **N2-only interruption from a mid-N2-Phase-E arrival** (same theorem);
* **wall-clock-bound responsiveness** (no clock authority in the substrate);
* **transport-driven session-state mutation** (no callback authority);
* **scheduler override via operator command** (D-SCHED-1; this rules out a class of `manual_advance` semantics);
* **runtime graph mutation in response to operator command** (D-FORBID-4 + D-FAULT-15 #13).

These limits are not "missing features." They are the load-bearing substrate invariants.

### §U.3 The "what live ingress does enable" boundary

Live ingress DOES enable:

* **Phase-A-aligned abort under operator command at any orchestration tick** (the primary use case);
* **deferred-from-Phase-A interruption** if the envelope arrives between session.step(K-1)'s Phase G and session.step(K)'s Phase D execute-entry, with effect at the next eligible segment boundary inside session.step(K)'s Phase E (existing Step 10 Direction A path, generalized to live arrival);
* **forensic provenance of operator commands** via `OperatorAbortRequested` events in the trace, byte-identical to pre-queued envelopes;
* **replay-authoritative reconstruction from trace alone**, without transport replay (§H).

The substrate's expressiveness is generalized but not weakened.

### §U.4 The compatibility-boundary statement

Step 11 live ingress, framed as a deterministic causality and authority-topology problem (not as an interrupt-feature problem), is constitutionally compatible with the Step 8/9/10 substrate under the channel-as-opaque-buffer topology. The compatibility boundary is precisely the eight disciplines of §U.1.

Any Step 11 implementation that exceeds these disciplines crosses the compatibility boundary. Any Step 11 implementation that strictly observes these disciplines preserves the substrate's posture and the load-bearing replay-authority discipline.

The N2-only-interruption impossibility theorem (§B.4) is **not weakened** by live ingress — it is a substrate invariant that lives alongside live ingress and constrains its expressiveness without contradicting its existence.

The §11.1 commutativity gap from `phase_4b_deterministic_semantics.md` closes by naming canonical-order (already in-implementation) as normative. No semantic change is required.

The kind expansion (D-FAULT-9a's reserved `pause`/`resume`/`manual_advance`) is a separate constitutional question; the channel mechanism is orthogonal to it. The audit (§M.5) found:

* `abort`: compatible (already validated).
* `pause`/`resume`: open on PAUSED state semantics.
* `manual_advance`: no constitutionally-compatible semantic under D-SCHED-1; analytical recommendation is to drop the reserved name or fundamentally redefine its meaning.

### §U.5 Substrate posture under Step 11 (analytical projection)

If Step 11 lands the channel-as-opaque-buffer topology (channel-mechanism only, no kind expansion), the substrate's posture becomes:

> **deterministic interruption-aware orchestration substrate with empirically-validated mid-trajectory predicate semantics on real PhysX, and replay-authoritative live-ingress under canonical-order drain epochs.**

If Step 11 also lands the `pause`/`resume` kind expansion (subject to a separate PAUSED clause analysis), the posture becomes:

> **deterministic interruption-aware orchestration substrate with empirically-validated mid-trajectory predicate semantics on real PhysX, replay-authoritative live-ingress under canonical-order drain epochs, and operator-driven session pause/resume with deterministic tick cadence.**

These are projected postures only. They are not committed-to by this analysis.

### §U.6 What this analysis explicitly DOES NOT do

* No clause text is proposed (only §Q's analytical row sketches);
* No comparator change is proposed;
* No snapshot-schema change is proposed;
* No event-bus extension is proposed;
* No subscriber-set extension is proposed;
* No reactive-runtime pattern is proposed;
* No speculative-synchronization mechanism is proposed;
* No specific transport choice is recommended (§O is options analysis only);
* No phase plan is authored;
* No implementation file edits are proposed;
* No tests are added;
* No production-ready architecture is committed.

The analysis is purely a compatibility-boundary investigation. Its terminus is §U.4's compatibility-boundary statement.

---

## §V. Analysis closure & next-phase prerequisites

### §V.1 Analysis status

This document is **ANALYSIS COMPLETE** as a single-pass investigation. It discharges the session brief's analytical objectives:

* live ingress ontology ✅ (§C)
* orchestration authority topology ✅ (§D)
* deterministic ingress ordering ✅ (§E)
* replay-authoritative dynamic abort semantics ✅ (§F, §G, §H)
* interaction with D-FAULT / D-CONT / D-EXEC ✅ (§M)
* causal ordering implications ✅ (§B, §F)
* interruption-timing authority ✅ (§J)
* visibility-boundary semantics ✅ (§I, §N)
* ingress observation epochs ✅ (§F)
* contradiction-preservation under live ingress ✅ (§L)
* deterministic channel semantics ✅ (§D, §O)
* isolation of orchestration authority ✅ (§D, §I)
* replay-reconstructable ingress ordering ✅ (§E, §G)
* Phase E atomicity preservation ✅ (§K)
* isolation-boundary implications ✅ (§I, §K)
* contradiction timing semantics ✅ (§L.5)
* authority acquisition boundaries ✅ (§I)
* authority visibility boundaries ✅ (§I)
* orchestration epoch integrity ✅ (§F)
* replay-authoritative observation timing ✅ (§F, §G)
* append-only ingress history semantics ✅ (§G)
* whether live ingress introduces hidden authority surfaces ✅ (§P)
* whether intra-cycle visibility is constitutionally compatible ✅ (§N)
* whether replay can prove WHY an ingress became authoritative at a specific boundary ✅ (§I.5, §H)

### §V.2 Next-phase prerequisites (if Step 11 proceeds)

If Step 11 proceeds to a contract phase, the prerequisites are:

1. **A separate analytical pass on PAUSED state semantics** — closing §T.2 and §M.5 around `pause`/`resume`.
2. **A formal disposition of `manual_advance`** — drop, redefine, or defer (§T.3, §M.5).
3. **A formal disposition of D-FAULT-15 #16's reach onto object-method ingress** — closing §T.4 and §O.2's open question.
4. **A formal disposition of the buffer-freezing discipline** — closing §T.1 and proving strict snapshot is the unique threat-closed topology.
5. **A formal disposition of liveness vs. determinism trade-off** — closing §T.8 around caller-pacing.

Each prerequisite is its own analysis-doc pass. None should be collapsed into "Step 11 implementation."

### §V.3 Closure statement

The Step 11 architectural analysis is closed at the **compatibility-boundary investigation** level. The next-phase decision (whether to proceed to a Step 11 contract phase, and what scope to admit) is reserved for a separate session.

The frozen Step 8 / Step 9 / Step 10 Direction A substrate is preserved verbatim in every conclusion of this analysis. No clause weakening, no implementation, no contract mutation, no comparator change, no snapshot-schema change, no replay tolerance, no async/thread/signal/callback authority, no event-bus redesign, no reactive runtime, no speculative synchronization, no hidden cleanup, no replay-healing, no adaptive recovery, no wall-clock authority has been introduced or admitted by this analysis.

The N2-only-interruption impossibility theorem (§B.4) is established as a substrate invariant for the duration of Phase 4B and any successor phase that does not rewrite the orchestration tick / world.step() relationship.

The compatibility boundary for live ingress, if Step 11 proceeds, is precisely the eight disciplines of §U.1.

This analysis is final for the scope of this session.

---

**End of Step 11 architectural analysis.**

Predecessor closures: [Step 8](phase_4b_deterministic_semantics.md), [Step 9](phase_4b_step9_failure_semantics_analysis.md), [Step 10 Direction A](phase_4b_step10_direction_a_analysis.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md). Authority topology: [phase_4b_orchestration_architecture.md](phase_4b_orchestration_architecture.md).
