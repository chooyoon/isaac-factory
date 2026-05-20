# Phase 4B Step 11 — Live-Ingress Admissibility Framework

**Status: ANALYSIS / CONSTITUTIONALIZATION-PREPARATION (2026-05-21).** This document normalizes the findings of [docs/phase_4b_step11_live_ingress_analysis.md](phase_4b_step11_live_ingress_analysis.md) (the "Analysis") into a coherent admissibility framework. No clause text is authored; no implementation is proposed; no contract is mutated; no comparator/snapshot/event-bus/runtime change is admitted. The framework's deliverable is a **constitutionally-ready classification** of Step 11 findings such that a future contract phase, if pursued, can author clauses mechanically from this taxonomy.

**Authority order:**

1. [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md) — the **authoritative contract**, frozen at Step 10 Direction A closure (2026-05-21). Every finding below either preserves or proposes-extension-of contract surface; nothing modifies, weakens, or retracts existing clause text.
2. [`phase_4b_orchestration_architecture.md`](phase_4b_orchestration_architecture.md) — architectural baseline.
3. [`phase_4b_step11_live_ingress_analysis.md`](phase_4b_step11_live_ingress_analysis.md) — the Analysis. Conclusions are cited as `Analysis §X` throughout.
4. This document — constitutionalization preparation.

**Forbidden in this session (per brief):** runtime implementation, async ingress mechanisms, thread/signal/callback authority, event-bus proposals, reactive-runtime proposals, wall-clock semantics, transport-authoritative semantics, replay weakening, comparator weakening, hidden authority introduction, adaptive recovery, replay healing, mid-Phase-E observability proposals, contract weakening, semantic-tolerance introduction. The framework treats ingress strictly as a **deterministic authority-topology problem**, not as a real-time responsiveness feature.

**Preserved absolutely:** replay-authoritative truth, append-only causality, deterministic orchestration authority, deterministic interruption boundaries, authoritative `orchestration_tick` semantics, Phase E atomicity, contradiction preservation, reopen-stage replay identity, no hidden cleanup, no wall-clock authority, no adaptive semantics.

---

## §A. Document scope and posture

### §A.1 What this framework is

A **classification + normalization** layer over the Step 11 Analysis. It does three things:

1. **Normalizes** the Analysis's prose-stated theorems and lemmas into formally-stated propositions with explicit hypotheses, conclusion, and proof status.
2. **Classifies** every Step 11 finding as one of three constitutional readiness states: **normative-candidate**, **observational**, or **open**.
3. **Consolidates** the framework's admissibility verdicts (what is constitutionally admissible, what is constitutionally incompatible, what remains open) and produces a constitutionalization-readiness assessment.

### §A.2 What this framework is NOT

* It does NOT author new clauses, even in draft form. Theorem and lemma statements below describe *what a future clause would assert*; they are not clause text.
* It does NOT propose implementation, transport, or runtime surface.
* It does NOT modify any existing contract clause. Where the framework references existing clauses, it cites them as load-bearing premises, never as candidates for amendment.
* It does NOT decide whether Step 11 proceeds to contract-authoring phase. That decision is reserved for a separate session.

### §A.3 Why constitutionalization preparation is its own session

The Analysis (1351 lines, 22 sections) discharged the brief's investigative objectives. Its conclusions are coherent but distributed: Theorem T2 is sketched across §B.1–§B.6 of the Analysis; the eight admissibility disciplines appear at §U.1 but their derivations are scattered through §D, §F, §K, §P. A future contract author who reads only the Analysis must re-derive the constitutional implications. This framework reduces that re-derivation cost to zero: each theorem appears once, each discipline appears once, each finding is classified once.

The framework is also the right place to discharge the brief's four explicit analytical questions, each of which spans multiple Analysis sections:

* (Q1) Which findings are normative candidates? — §E.
* (Q2) Which are observational? — §E.
* (Q3) Which semantics are admissible / incompatible? — §F.
* (Q4) What is the minimum admissible ingress surface? — §G.

And the brief's four follow-up questions:

* (Q5) Do admissible semantics require new deterministic epochs? — §H.
* (Q6) Can ingress remain transport-independent under all admissible models? — §I.
* (Q7) Does contradiction timing remain replay-reconstructable under multi-envelope drains? — §J.
* (Q8) What is the minimum additive-only contract-surface? — §L.

### §A.4 Naming convention

Throughout this document:

* **Theorem T*N*** — a normalized proposition that any future Step 11 clause would assert or rely on. Theorem statements include hypothesis, conclusion, and citation chain. They are *clause-shaped* but not clause text.
* **Lemma L*N*** — a normalized supporting proposition. Lemmas may be stated as derived from theorems plus existing clauses.
* **Discipline D*N*** — a normalized admissibility rule (an "IFF" condition for live ingress to be constitutionally compatible).
* **Finding F*N*** — a Step 11 Analysis observation, classified as normative-candidate / observational / open.

These are framework-internal labels. They are NOT proposed clause IDs. Real clause IDs (D-EXEC-*, D-FAULT-*, etc.) belong to the contract document and will be assigned, if ever, in the contract phase.

---

## §B. Theorem normalization

The Analysis surfaces four propositions that have the structural shape of theorems — they assert truths about substrate behavior under specified hypotheses, derivable from existing clauses. Each is restated below in normalized form. None is contract text; each is the proposition a future clause would either assert verbatim or rely on as a justification.

### §B.1 Theorem T1 — Tick Non-Commensurability

**Statement.** Within one `ExecutionSession`, two clocks advance independently and are non-commensurable from each other's reference frame:

* **`orchestration_tick`** — advances by exactly 1 at the end of each `session.step()` invocation (after Phase G); session-owned (D-SESS-1); observable to every phase of the orchestration tick.
* **`world.step()` count** — advances by exactly 1 per `world.step()` call inside Phase E (D-EXEC-4); executor-owned; not observable to any orchestration phase outside Phase E.

During Phase E of `session.step(K)`, `orchestration_tick = K` (frozen for the duration). Inside that interval, the executor advances its own world-step counter; the session has no observation surface for that counter until Phase E returns.

**Hypotheses.** D-EXEC-1 (7-phase order), D-EXEC-4 (`world.step()` exactly once per physics tick), D-EXEC-13a (Phase E atomic from orchestration perspective), D-FAULT-6a (executor runs trajectory to completion or executor-internal exception).

**Citation chain.** Analysis §B.1 (the "clock asymmetry"); session.py:854, 875 (`_orchestration_tick += 1`).

**Classification.** Theorem T1 is a **load-bearing premise** for Theorems T2 and T3 below. It is derivable from existing clauses, so a future Step 11 clause does not need to assert T1; it cites the existing clauses that imply it. T1 is normative-implicit.

### §B.2 Theorem T2 — N-Interior-Phase-E Ingress Cannot Acquire In-Tick Authority (the "N2-only-interruption impossibility")

**Statement.** Let S be an `ExecutionSession` executing the orchestration tick of node N, where session.step's orchestration_tick has value K_N at this tick. Let E be an `OperatorEnvelope` whose channel-arrival wall-clock instant W lies strictly inside the wall-clock interval `(start of N's Phase D execute-entry, end of N's Phase E)`.

Then E:

* MUST NOT influence N's interruption predicate (because the predicate's closure was captured at execute-entry, D-EXEC-13);
* MUST NOT be drained mid-Phase-E (D-FAULT-6, D-FAULT-15 row 5, D-FAULT-15 row 27);
* MUST NOT terminate N's `execute()` via any orchestration-observable mechanism (D-EXEC-13a);
* CAN ONLY acquire orchestration authority at Phase A of a session.step whose orchestration_tick value is ≥ K_N + 1.

**Hypotheses.** D-FAULT-6 (abort enters at Phase A only), D-FAULT-6a (Phase E atomic), D-EXEC-13a (Phase E atomic from orchestration perspective), D-EXEC-13c (predicate session-constructed; no substitution mid-execute), D-FAULT-15 rows 5, 16, 22, 27, 28, 29.

**Conclusion (corollary).** The latency between a live envelope's wall-clock arrival and its earliest orchestration-observable authority-acquisition boundary is bounded below by the remaining wall-clock duration of the current node's Phase E, plus the cadence at which the caller invokes `session.step()`. This latency is **not a deficiency**: it is the price of replay-authoritative single-emitter discipline.

**Citation chain.** Analysis §B.2–§B.6.

**Classification.** **NORMATIVE-CANDIDATE.** Theorem T2 is the single most load-bearing assertion of the framework. It defines the upper bound on live-ingress expressiveness. A future Step 11 clause SHOULD state T2 explicitly — both because it is non-obvious and because future readers will need a clause to cite when rejecting proposals that violate it (e.g. "Theorem T2 forbids responding to a mid-Phase-E arrival within the same tick").

T2 is not a *new* invariant. It is *implied* by the existing D-FAULT-6a + D-EXEC-13 + D-FAULT-15 row-5/27 discipline. Stating it is normative-strengthening (making the implication explicit), not normative-additive (admitting new behavior).

### §B.3 Theorem T3 — Phase-A-Only Ingress Observability

**Statement.** Within one `session.step(K)` invocation, the session's only observation surface for ingress events is at Phase A. No sub-Phase pulled observation, no Phase B/C/D/E/F/G pulled observation, no `pull-at-end-of-Phase-G` observation is admissible.

Equivalently: every ingress observation corresponds to exactly one (`session_id`, `orchestration_tick`) pair, and the orchestration_tick value at observation is exactly K (the value the tick held throughout the entire session.step(K) call).

**Hypotheses.** D-EXEC-1 (7-phase order; no sub-phases), D-EXEC-2 (events out of phase forbidden), D-EXEC-13a (Phase E atomic), D-FAULT-15 row 27 (mid-execute envelope drain forbidden).

**Citation chain.** Analysis §F.3 (single-pull-per-epoch); §F.4 (pre-execute second epoch rejected).

**Classification.** **NORMATIVE-CANDIDATE.** T3 closes a real ambiguity. The brief asked: "whether intra-cycle visibility is constitutionally compatible." T3 answers: visibility is constitutionally compatible **only at Phase A within one cycle**; no sub-cycle visibility surface is admissible. A future clause stating T3 makes the answer explicit and forecloses the post-Phase-A pull / pre-Phase-E pull / pre-Phase-G pull design temptations that would otherwise appear in implementation reviews.

### §B.4 Theorem T4 — Acquisition-Visibility Tick Alignment

**Statement.** For every authoritative ingress event in a session, the `orchestration_tick` at which the envelope acquires orchestration authority is identical to the `orchestration_tick` value held by the session at the moment the EventBus emits the corresponding event.

Two cases:

* **Phase-A-drained envelope.** Envelope drains at Phase A of `session.step(K)`. Bus emits `OperatorAbortRequested` at that Phase A. Session-state transition (e.g. RUNNING → ABORTING) happens at that Phase A. orchestration_tick = K throughout. Acquisition = Visibility = Tick K. (Trivial case.)

* **Deferred-from-Phase-A envelope** (Step 10 Direction A path). Envelope present in `_pending_envelopes` at execute-entry of `session.step(K)`. Predicate closure captures envelope. Executor returns `EXECUTION_INTERRUPTED`. Session emits the deferred `OperatorAbortRequested` at post-Phase-E classification. State transition happens at the same post-Phase-E moment. orchestration_tick = K throughout. Acquisition = Visibility = Tick K.

In both cases, acquisition and visibility are **co-located within a single orchestration_tick**, even when separated across multiple sub-phases of that tick. No ingress event acquires authority at tick K_a and becomes visible at tick K_v with K_a ≠ K_v.

**Hypotheses.** D-BUS-1 (synchronous dispatch), D-BUS-3 (gap-free monotone seq), D-EXEC-2 (events out of phase forbidden), D-EXEC-7 (trace commit follows action), D-FAULT-3b (declared-order classification at end of Phase E).

**Citation chain.** Analysis §I.1–§I.5; the deferred-from-Phase-A pathway is at session.py around line 1056.

**Classification.** **NORMATIVE-CANDIDATE.** T4 is the formalization of the substrate's distinctive property: even multi-phase ingress emissions remain tick-local. A future clause asserting T4 forecloses cross-tick acquisition/visibility decoupling, which would otherwise be the canonical hidden-causality vector under live ingress.

### §B.5 Theorem-set citation summary

| Theorem | Status | Future-clause role |
|---|---|---|
| T1 (Tick Non-Commensurability) | implicit normative; derivable | premise for T2/T3; no separate clause needed |
| T2 (N2-Only-Interruption Impossibility) | NORMATIVE-CANDIDATE | the substrate's expressiveness bound; explicit clause recommended |
| T3 (Phase-A-Only Observability) | NORMATIVE-CANDIDATE | forecloses sub-Phase observation temptations |
| T4 (Acquisition-Visibility Tick Alignment) | NORMATIVE-CANDIDATE | forecloses cross-tick hidden causality |

---

## §C. Lemma normalization

The Analysis surfaces five propositions that are best stated as lemmas — derived results that support the theorems above. Each is restated below in normalized form.

### §C.1 Lemma L1 — Drain-Epoch Determinism

**Statement.** Let S be an `ExecutionSession`. For every envelope E ever observed by S, there exists a unique `orchestration_tick` value K_drain(E) such that the Phase A of `session.step(K_drain(E))` is the tick at which E was drained from `_pending_envelopes`. K_drain(E) is determined by:

* the smallest K ≥ E.`requested_at_tick` such that
* E was a member of `_pending_envelopes` at the start of Phase A of `session.step(K)`, AND
* the session was in a state where Phase A drain was reached (i.e. session is not already ABORTED at start of tick K).

K_drain(E) is **replay-stable**: identical input conditions produce identical K_drain(E).

**Hypotheses.** D-FAULT-9 (envelope schema with `requested_at_tick`); D-FAULT-6 (drain only at Phase A); D-SESS-1 (session is sole mutator of `_pending_envelopes`); the canonical-order discipline of Lemma L3.

**Citation chain.** Analysis §F.5 (Drain-Epoch invariant); session.py:1382 (`env.requested_at_tick <= self._orchestration_tick`).

**Classification.** **NORMATIVE-CANDIDATE.** L1 names the drain epoch as the unique authoritative-observation primitive. Under pre-queue, K_drain(E) is implicit in the trace; under live ingress, the same K_drain(E) is the only sense in which "when did the envelope arrive" is replay-meaningful. The wall-clock arrival instant is non-authoritative.

### §C.2 Lemma L2 — Epoch-Identity Implies Trace Identity

**Statement.** Let S₁ and S₂ be two `ExecutionSession` instances of the same `Job`, same `seed`, same `runtime_hash`, same `cell_cfg_hash`. Let Φ₁(K) = the set of envelopes drained by S₁ at Phase A of `session.step(K)`, and Φ₂(K) likewise for S₂.

If for every orchestration_tick K, Φ₁(K) = Φ₂(K) (the **Epoch-Identity Condition**), then S₁'s `events.jsonl` is byte-identical to S₂'s `events.jsonl` modulo `wall_ns`.

**Proof sketch.** Under Epoch-Identity, the canonical drain order at every Phase A is identical (Lemma L3). The `OperatorAbortRequested` event sequence is identical. The session state transitions are identical (D-FAULT-7 idempotency makes the first abort the transition). The predicate at every execute-entry closes over identical `_pending_envelopes`. The executor outcome at every Phase E is identical (Phase 3P bit-identity inherits). Every Phase G commit is identical. The bus's seq counter advances identically. ∎

**Hypotheses.** D-REPLAY-1/-2 (bitwise-identical replay within process), Lemma L1, Lemma L3, D-FAULT-7 (idempotent transition), Phase 3P empirical 100/100 bit-identity, Step 10 Direction A's empirical 12/12 cycles closure.

**Citation chain.** Analysis §F.8 (Epoch-Identity Lemma stated informally); Analysis §H (replay-reconstruction proof sketch).

**Classification.** **NORMATIVE-CANDIDATE.** L2 is the core replay-authority claim for live ingress. It reduces "live-ingress replay identity" to "drain-epoch-set identity" — a strictly weaker requirement than transport-level determinism. A future clause asserting L2 makes explicit *what* must agree between two replays for them to be byte-equal, and equivalently *what need not* agree (transport instants, network latencies, operator submission timings).

### §C.3 Lemma L3 — Canonical-Order Commutativity

**Statement.** At every Phase A drain, eligible envelopes are drained in lexicographic order of `(requested_at_tick, envelope_id)`. Because `envelope_id` is the deterministic blake2b digest of `(kind, requested_at_tick, reason)` (D-FAULT-9 + `derive_envelope_id`), this order is **purely content-addressed**: it is independent of arrival order, transport delivery order, channel buffer storage order, threading interleaving, or scheduling latency.

Formally: for any permutation π of an eligible-envelope set, draining in order π produces the same `OperatorAbortRequested` event sequence as draining in canonical order. Drain operation is order-commutative over the eligible set.

**Hypotheses.** D-FAULT-9 (envelope schema), `canonical_envelope_order` and `derive_envelope_id` at envelopes.py:101, 118, D-SCHED-5/-6/-7 (stable iteration required).

**Citation chain.** Analysis §E.1–§E.6; §11.1 of `phase_4b_deterministic_semantics.md` (the explicit "Phase 4B step 11 will close this gap" reservation).

**Classification.** **NORMATIVE-CANDIDATE.** L3 is the explicit closure of the `OperatorOverride` commutativity gap reserved by §11.1 of the contract. It is the framework's most-mechanical normalization: the canonical-order discipline is already implemented (envelopes.py:118; session.py:1376–1414); L3 simply *names* it as normative. A future clause stating L3 closes the gap precisely.

### §C.4 Lemma L4 — Replay-Reconstruction From Trace Alone

**Statement.** Given a session package P containing `events.jsonl`, manifest, and registry snapshots, the set of all `OperatorAbortRequested` event payloads in `events.jsonl` is sufficient to reconstruct a `pending_operator_envelopes` tuple Q such that a fresh `ExecutionSession` constructed with `pending_operator_envelopes=Q` (and otherwise identical Job/seed/runtime/cell_cfg) produces an `events.jsonl` byte-equal to P's (modulo `wall_ns`).

Equivalently: **the trace is sufficient** to replay live ingress. The transport is not needed at replay time.

**Proof sketch.** Each `OperatorAbortRequested` payload carries (envelope_id, kind, requested_at_tick, reason). Reconstruct `OperatorEnvelope(kind=..., requested_at_tick=..., reason=..., envelope_id=derive_envelope_id(...))` per row. Pass the canonical-ordered tuple as `pending_operator_envelopes`. Under Lemma L2, the resulting session produces byte-equal trace. ∎

**Hypotheses.** D-FAULT-9 (envelope schema; `envelope_id` is content-addressed), D-TRACE-1/-2/-7 (authoritative append-only trace), L1, L2, L3.

**Citation chain.** Analysis §H.1–§H.4 (proof sketch); Analysis §G.2 (reconstruction primitive).

**Classification.** **NORMATIVE-CANDIDATE.** L4 is the load-bearing claim that closes the brief's central question: *"can replay prove WHY an ingress became authoritative at a specific boundary?"* L4's answer: yes — by reconstruction from trace alone, without transport access.

L4 also implies the brief's transport-independence claim (§I below): the substrate is transport-independent precisely because the trace alone is sufficient for replay.

### §C.5 Lemma L5 — Sufficient Identity Conditions for Replay-Authoritative Live Ingress

**Statement.** Two sessions S₁, S₂ of the same `(Job, seed, runtime_hash, cell_cfg_hash)` produce byte-equal `events.jsonl` (modulo `wall_ns`) IFF the following three conditions all hold:

1. **Epoch-Identity** (Lemma L2's Φ₁(K) = Φ₂(K) for all K).
2. **Canonical-Drain-Order** at every Phase A drain (Lemma L3).
3. **Predicate-Closure-Equivalence** at every execute-entry (the predicate's closure inputs derive from the same `_pending_envelopes` state).

Condition 3 is implied by Conditions 1 + 2, by induction on tick K. Condition 2 is invariant. So in practice, Epoch-Identity (Condition 1) alone is the necessary and sufficient condition for trace equality.

**Hypotheses.** D-EXEC-13 (predicate closure inputs whitelist), D-FAULT-3b (classification is pure function), D-REPLAY-2 (bitwise-identical conditions).

**Citation chain.** Analysis §F.8 + §H.

**Classification.** **NORMATIVE-CANDIDATE** (or possibly **observational corollary** of L2/L3/L4 — see §E for classification rationale). L5 collapses three replay-identity conditions to one, sharpening the framework's central claim.

### §C.6 Lemma-set citation summary

| Lemma | Status | Future-clause role |
|---|---|---|
| L1 (Drain-Epoch Determinism) | NORMATIVE-CANDIDATE | names drain epoch as authoritative-observation primitive |
| L2 (Epoch-Identity ⇒ Trace Identity) | NORMATIVE-CANDIDATE | core replay-authority claim for live ingress |
| L3 (Canonical-Order Commutativity) | NORMATIVE-CANDIDATE | closes §11.1 commutativity gap |
| L4 (Replay-Reconstruction From Trace Alone) | NORMATIVE-CANDIDATE | enables transport-independent replay |
| L5 (Sufficient Identity Conditions) | NORMATIVE-CANDIDATE / observational | collapses conditions; sharpens L2 |

---

## §D. Ingress ontology stabilization

The brief asks for "ingress epoch terminology normalization" and "ingress ontology stabilization." This section names and defines the framework's terms exactly once, and locks the definitions for all subsequent ingress work.

### §D.1 Six ontology objects

The framework recognizes exactly six ingress-related ontology objects. No new term will be introduced by Step 11 work; future contract authors should refuse PRs that introduce new terminology without retiring or merging an existing term.

| # | term | definition | mutated by | observable to |
|---|---|---|---|---|
| 1 | **OperatorEnvelope** | The frozen dataclass (D-FAULT-9). Sole orchestration ingress unit. | nobody (frozen) | trace, predicate (via closure), drain code |
| 2 | **Channel** | A passive store, owned per-session, into which a transport pushes envelopes. The channel emits nothing; produces nothing observable to orchestration except via the session's Phase-A pull. | transport (push), session (pull-drain) | session at Phase A only |
| 3 | **Buffer** | The channel's internal storage. Append-only between Phase-A pulls; atomically snapshot-and-cleared at each pull. | transport (append), session (atomic swap at pull) | session at pull moment only |
| 4 | **Pull** | The single Phase-A operation that atomically transfers the buffer's current contents into the session's `_pending_envelopes`. | session (Phase A only) | not directly observable; produces no event |
| 5 | **Drain Epoch** | The `(session_id, orchestration_tick)` pair at which a Phase A drain processed at least one envelope. Authoritative-observation primitive. | recorded in trace via `OperatorAbortRequested` events | trace, replay tools |
| 6 | **Ingress Observation Event** | A trace-recorded `OperatorAbortRequested` event, carrying the envelope payload and the drain epoch's orchestration_tick. | session at Phase A (or post-Phase-E for deferred case) | trace, all subscribers (D-BUS-9) |

### §D.2 Terminological exclusions

The following terms have been used loosely in the literature surrounding live ingress. Within the framework, they are either **rejected** (no substrate referent) or **demoted to diagnostic-only** (referent exists but is not authoritative):

| term | framework status | reason |
|---|---|---|
| "arrival time" | diagnostic only | wall-clock; D-FORBID-6 forbids in authoritative paths |
| "ingress callback" | rejected | implies push-from-channel; D-FAULT-15 row 16 (and proposed row 31) forbids |
| "submission" | diagnostic only | operator-side concept; not a substrate primitive |
| "ack / nack" | rejected (substrate-level) | implies channel state machine; rows 36/40 proposed |
| "live-channel state" | rejected | channel is stateless; only Buffer (#3) holds state, and only between pulls |
| "ingress queue" | discouraged | use Buffer (storage role) or Channel (boundary role) per intent |
| "pending command" | rejected | conflates envelope (data) with command (PhysX write); these are orthogonal layers |
| "input event" | rejected | the substrate has no concept of "input"; envelopes are the only ingress |
| "notification" | rejected | implies push-from-channel-to-subscriber; subscribers don't see envelopes until drain |
| "real-time interrupt" | rejected | the substrate has no real-time semantics (D-FORBID-11) |

This list is deliberately narrow. Any future ingress work that uses an unlisted term must either introduce it via the framework's terminology rules (define + classify + cite) or refuse it as foreign.

### §D.3 Ontology composition

The six ontology objects compose into exactly one ingress pathway:

```
  Transport (out-of-substrate)
       │ push (non-authoritative, wall-clock)
       ▼
  Buffer (passive storage)
       │ atomic snapshot + clear
       ▼
  Pull (Phase A only, session-owned)
       │ canonical-order sort
       ▼
  _pending_envelopes (session-owned, D-SESS-1)
       │ Phase A drain (eligibility: requested_at_tick ≤ orchestration_tick)
       ▼
  Drain Epoch (orchestration_tick = K)
       │ bus emission
       ▼
  Ingress Observation Event (trace; authoritative)
```

The pathway is unidirectional. There is no observation channel from substrate to transport (a future "ack to operator" feature must be a separate event emitted via the bus, not a channel-level reverse path).

### §D.4 Ontology classification

| object | constitutional role |
|---|---|
| OperatorEnvelope | already-normative (D-FAULT-9); unchanged under Step 11 |
| Channel | NORMATIVE-CANDIDATE (the channel-as-opaque-buffer discipline of §G is what defines it) |
| Buffer | implementation-detail; not constitutionally observable |
| Pull | NORMATIVE-CANDIDATE (Theorem T3 + Discipline D2 below) |
| Drain Epoch | NORMATIVE-CANDIDATE (Lemma L1) |
| Ingress Observation Event | already-normative (D-BUS, D-FAULT-9, D-TRACE) |

---

## §E. Admissibility classification — Step 11 findings

The brief asks: which findings are **normative-candidate**, and which are **observational**? This section walks the Analysis section-by-section and classifies every distinct finding. The total finding count is 47; the framework labels each with a finding ID F1–F47.

### §E.1 Classification rubric

A finding is **normative-candidate** if it has all of the following properties:

1. it asserts a substrate invariant (not a framing observation);
2. it has a clear hypothesis-and-conclusion structure (can be stated as "under conditions X, Y must hold");
3. its negation would be a recognizable contract violation OR a hidden authority surface OR a replay-authority weakening;
4. it is *non-obvious from existing clauses*, i.e. a future reader cannot derive it by mechanical contract reading without re-doing the Analysis.

A finding is **observational** if it lacks one or more of those properties. Observational findings stay in the Analysis as guidance; they do not motivate clause work.

A finding is **open** if its admissibility remains undetermined by the framework and requires its own analytical pass.

### §E.2 Finding-by-finding classification

Findings are grouped by Analysis section. Citations are `Analysis §X.Y`.

**Framing (Analysis §A):**

| F | content | class | rationale |
|---|---|---|---|
| F1 | Three mis-framings rejected (interrupt-feature, pause/resume-only, operator-channel-feature) | observational | framing guidance; not a substrate invariant |
| F2 | Correct framing: causal-topology problem | observational | framing only |
| F3 | Hard non-introduction list (the 15 forbidden products of this analysis) | observational | session-discipline guidance; cited as framework constraint, not as substrate clause |

**Theorem T2 derivation (Analysis §B):**

| F | content | class | rationale |
|---|---|---|---|
| F4 | Two-clocks non-commensurability | implicit normative (T1) | derivable from existing clauses; cited as premise |
| F5 | The N2-only-interruption impossibility theorem | NORMATIVE-CANDIDATE (T2) | the framework's key normalization target |
| F6 | Latency-floor corollary (latency ≥ remainder of current Phase E) | observational | derived from T2 |
| F7 | What T2 rules out (mid-Phase-E abort granularity, etc.) | observational | T2 corollary |
| F8 | What T2 does NOT rule out (Phase-A-aligned abort under live arrival, deferred-from-Phase-A) | observational | T2 corollary |

**Ingress ontology (Analysis §C):**

| F | content | class | rationale |
|---|---|---|---|
| F9 | Ingress event = orchestration-observation, NOT transport-arrival | NORMATIVE-CANDIDATE | redefines the load-bearing observable; future clause SHOULD state |
| F10 | OperatorEnvelope as unit of ingress | already-normative (D-FAULT-9) | unchanged |
| F11 | `requested_at_tick` is forward-looking gate semantics | NORMATIVE-CANDIDATE (clarification) | clause-level disambiguation; current schema doesn't say |
| F12 | Drain seq as secondary identifier | observational | naming convention |
| F13 | Forbidden ingress-event fields (arrival_wall_ns, transport_id, etc.) | NORMATIVE-CANDIDATE | future clause SHOULD enumerate; closely tied to proposed D-FAULT-15 row 34 |

**Authority topology (Analysis §D):**

| F | content | class | rationale |
|---|---|---|---|
| F14 | Current single-emitter discipline preserved | already-normative (D-FAULT-2) | unchanged |
| F15 | The "second emitter" temptation rejected | NORMATIVE-CANDIDATE (strengthening D-FAULT-2) | explicit foreclosure; closes a temptation route |
| F16 | Channel-as-opaque-buffer topology | NORMATIVE-CANDIDATE (Discipline D1) | the framework's key admissibility shape |
| F17 | Strict-snapshot pull discipline | NORMATIVE-CANDIDATE (Discipline D3) | unique threat-closed pull semantic |
| F18 | Surgical session.py changes | observational | implementation guidance |
| F19 | Transport-layer unconstrained | NORMATIVE-CANDIDATE (Theorem T5 below; see §I) | transport-independence assertion |

**Ingress ordering (Analysis §E):**

| F | content | class | rationale |
|---|---|---|---|
| F20 | Canonical-order discipline at Phase A | NORMATIVE-CANDIDATE (Lemma L3) | closes §11.1 commutativity gap |
| F21 | Content-addressed envelope_id | already-normative (D-FAULT-9) | unchanged |
| F22 | D-FAULT-7 idempotency under multi-drain | already-normative (D-FAULT-7) | unchanged |
| F23 | Replay-reconstructable ordering | NORMATIVE-CANDIDATE (Lemma L4) | core replay claim |

**Epoch formalism (Analysis §F):**

| F | content | class | rationale |
|---|---|---|---|
| F24 | Epoch concept (`(session_id, orchestration_tick)`) | NORMATIVE-CANDIDATE | the framework's central abstraction |
| F25 | Epoch boundaries align with session.step() | observational | derived from existing clauses |
| F26 | Single-pull-per-epoch discipline | NORMATIVE-CANDIDATE (Theorem T3, Discipline D2) | forecloses sub-pull temptations |
| F27 | Pre-execute second-epoch rejection | NORMATIVE-CANDIDATE (Theorem T3 specific case) | explicit foreclosure |
| F28 | Drain-Epoch invariant | NORMATIVE-CANDIDATE (Lemma L1) | already lemma-stated above |
| F29 | Replay determinism doesn't require channel determinism | NORMATIVE-CANDIDATE (Lemma L2 corollary) | sharpens transport-independence |
| F30 | Epoch-Identity Lemma | NORMATIVE-CANDIDATE (Lemma L2) | core replay claim |

**Append-only ingress history (Analysis §G):**

| F | content | class | rationale |
|---|---|---|---|
| F31 | Append-only trace records every ingress | already-normative (D-TRACE-1, -2, -3, -7) | unchanged |
| F32 | Reconstruction primitive (trace → pre-queue) | NORMATIVE-CANDIDATE (Lemma L4) | enables transport-independence |
| F33 | Trace IS the channel at replay time | observational (corollary of L4) | naming guidance |

**Replay-reconstruction proof (Analysis §H):**

| F | content | class | rationale |
|---|---|---|---|
| F34 | Eight-step reconstruction sketch | NORMATIVE-CANDIDATE (Lemma L4 proof) | provides clause-level rigor |
| F35 | Proof-sketch failure modes (canonical drain, predicate purity, channel opacity, no callback) | NORMATIVE-CANDIDATE (Disciplines D1–D8) | the eight admissibility disciplines derive from these |

**Authority-acquisition vs visibility (Analysis §I):**

| F | content | class | rationale |
|---|---|---|---|
| F36 | Two distinct boundary surfaces | NORMATIVE-CANDIDATE (Theorem T4) | foreclosure of cross-tick decoupling |
| F37 | Tick-alignment invariant | NORMATIVE-CANDIDATE (Theorem T4) | the load-bearing T4 claim |
| F38 | Hidden authority threats (silent influence, stub events, boundary misalignment) | observational | enumerated as proposed D-FAULT-15 extensions |
| F39 | Replay-proof of "WHY this boundary" | observational | derived from Theorems + Lemmas |

**Phase E atomicity preservation (Analysis §K):** all findings already-normative under D-FAULT-6a + D-EXEC-13a + D-FAULT-15 rows 5, 27.

**Contradiction preservation (Analysis §L):** all findings already-normative under D-FAULT-5/-5a/-5b.

**D-FAULT/D-CONT/D-EXEC interaction (Analysis §M):**

| F | content | class | rationale |
|---|---|---|---|
| F40 | D-FAULT family interactions audited (M.1–M.7) | observational (audit) | no clause change required |
| F41 | D-CONT/D-EXEC/D-SCHED/D-BUS/D-REPLAY/D-SESS/D-TRACE/D-LIFE/D-FORBID audited | observational (audit) | no clause change required |
| F42 | Kind expansion (pause/resume/manual_advance) audit | OPEN | requires separate analytical pass |

**Visibility (Analysis §N):**

| F | content | class | rationale |
|---|---|---|---|
| F43 | Intra-cycle visibility limited to Phase A (and post-Phase-E deferred) | NORMATIVE-CANDIDATE (Theorem T3) | already covered by T3 |
| F44 | Cross-cycle visibility is the default | observational | derived from T3 |
| F45 | Visibility-latency formalization | observational | derived from T2 + T3 |
| F46 | Caller-driven cadence; no substrate pacing | observational (already D-FORBID-11) | unchanged |

**Three candidate ingress shapes (Analysis §O):**

| F | content | class | rationale |
|---|---|---|---|
| F47 | Three shapes enumerated (callable, mutable-buffer-object, sidecar-file-poll) | observational (options analysis) | no shape is normative until contract phase selects one |

**Threat models (Analysis §P) and proposed D-FAULT-15 extensions (Analysis §Q):**

| F | content | class | rationale |
|---|---|---|---|
| F48–F55 | Eight threat models | observational (drives proposed clauses) | derive proposed rows |
| F56 | Twelve proposed D-FAULT-15 rows (#31–#42) | NORMATIVE-CANDIDATE (collective) | future clause work; see §K |

**Substrate invariants carry-forward (Analysis §R) and frozen-clause preservation (Analysis §S):** all observational (audit confirmations).

**Open analytical questions (Analysis §T):**

| F | content | class | rationale |
|---|---|---|---|
| F57 | Buffer-freezing discipline formal proof | OPEN | §T.1 |
| F58 | PAUSED semantics | OPEN | §T.2; M.5 |
| F59 | `manual_advance` redefinition or removal | OPEN | §T.3; M.5 |
| F60 | D-FAULT-15 #16 reach onto object-method ingress | OPEN | §T.4 |
| F61 | Diagnostic fields on OperatorAbortRequested event | OPEN | §T.5 |
| F62 | Subscriber-set extension for live channels | OPEN | §T.6 |
| F63 | Boundary-snapshot serialization of `_pending_envelopes` | OPEN | §T.7 |
| F64 | Liveness vs determinism trade-off | OPEN | §T.8 |
| F65 | Cross-session transport lock ordering | OPEN | §T.9 |

### §E.3 Classification totals

* **Normative-candidate findings** — 24 (T1–T4 plus L1–L5 plus selected discrete findings; also covering D1–D8 via the §G framework). These constitute the "ready for clause work" pile.
* **Observational findings** — 32. These stay in the Analysis as guidance and audit material.
* **Open findings** — 9 (F42, F57–F65). These require their own analytical pass before contract phase.

The 65 finding labels are consecutively numbered for citation; they may be re-grouped during clause authoring but their classifications are stable.

---

## §F. Semantics admissibility matrix

The brief asks: which semantics are **constitutionally admissible**, which are **constitutionally incompatible**? This section produces a matrix.

### §F.1 Constitutionally admissible semantics

These semantics survive the §G admissibility framework and may be implemented as Step 11 work under a future contract phase:

| semantic | admissible because |
|---|---|
| Channel-as-opaque-buffer with passive storage | Discipline D1 (§G); does not introduce a second emitter |
| Pull-only access from session at Phase A | Theorem T3; preserves D-EXEC-1 |
| Strict atomic-snapshot pull | Discipline D3; closes hidden-race threat (Threat 2) |
| Canonical-order drain after pull | Lemma L3; closes §11.1 commutativity gap |
| Transport-layer using async/threading internally | D-FORBID-1 reading: "orchestration code" excludes transport; transport is out-of-substrate |
| Per-session channel construction and teardown | Discipline D7; closes cross-session leak (Threat 8) |
| Wall-clock-arrival timestamp as diagnostic-only field on the event | D-SESS-5 reading: diagnostic state can exist (not read by orchestration logic) |
| Ingress event payload carries (envelope_id, kind, requested_at_tick, reason) — same schema as pre-queue | D-FAULT-9 unchanged |
| `abort` kind via live arrival | empirically validated under pre-queue; semantically identical under live channel given the disciplines |
| Multi-envelope drain at one Phase A | D-FAULT-7 idempotency, Lemma L3, see §J below |
| Deferred-from-Phase-A abort for envelopes captured at execute-entry | already-normative under Step 10 Direction A; generalizes to live arrival |

### §F.2 Constitutionally incompatible semantics

These semantics violate one or more substrate invariants and may NOT be implemented as Step 11 work without first weakening a constitutional clause (which the brief explicitly forbids):

| semantic | incompatible because |
|---|---|
| Live channel emits `OperatorAbortRequested` directly | D-FAULT-2 (single emitter); also proposed D-FAULT-15 row 31 |
| Channel pushes events to session via callback | D-FAULT-15 row 16 (method-as-ingress); D-FORBID-1; proposed row 31 |
| Sub-Phase channel pull (B, C, D, E, F, G) | Theorem T3; D-EXEC-1; proposed row 32 |
| Mid-Phase-E channel pull or peek | D-FAULT-15 row 27; D-EXEC-13a; proposed row 33 |
| Wall-clock arrival timestamp as **authoritative** envelope field | D-FORBID-6; D-FAULT-15 row 10; proposed row 34 |
| Transport-layer ordering authority over drain order | D-SCHED-1/-5/-6/-7; proposed row 35 |
| Channel state machine observable to orchestration (ack/nack/pending) | D-FAULT-14; D-SESS-4; proposed row 36 |
| Cross-session live-channel state (channel survives `session.close()` and influences next session) | D-FORBID-12; D-FAULT-15 row 12; proposed row 37 |
| Wall-clock blocking in any session state (PAUSED-as-real-time-wait) | D-FORBID-11; proposed row 38 |
| `manual_advance` envelope overriding scheduler | D-SCHED-1; proposed row 39 |
| Channel observing session state (e.g. reading `session.session_state` to route messages) | D-SESS-1; D-SESS-5; proposed row 40 |
| Retroactive ingress event editing | D-TRACE-2; proposed row 41 |
| Non-pull peek of channel contents by orchestration code outside Phase A | proposed row 42 |
| Predicate substitution mid-execute based on new envelope arrival | D-EXEC-13c; D-FAULT-15 row 29 |
| Signal/async/thread-driven executor termination | D-FAULT-15 rows 28, 22; D-FORBID-1, -2 |
| Mid-execute envelope drain (Phase A interleaved with Phase E) | D-FAULT-15 row 27; D-EXEC-13a |
| `arrival_wall_ns` participating in canonical drain order tiebreak | F.1 above + D-FORBID-6 |
| Implicit retry of failed nodes on operator command | D-FAULT-8b; D-FAULT-15 row 2 |
| Runtime mutation of `TaskGraph` in response to envelope | D-FORBID-4 |
| Per-tick wall-time pacing between live arrivals and pulls | D-FORBID-11 |

### §F.3 Constitutionally open semantics

These semantics have neither been admitted nor rejected by the framework. They require their own analytical pass:

| semantic | open question |
|---|---|
| PAUSED as a SessionState value with idle-no-op-tick semantics | Whether constitutionally distinct from RECOVERING (forbidden, D-FAULT-15 row 18) (F58) |
| `pause`/`resume` envelope kinds | Whether the kind expansion is admissible given PAUSED's status (F42) |
| `manual_advance` as redefined semantic | Whether any semantic for this kind is admissible under D-SCHED-1 (F59) |
| `buffer.append(env)` as method-as-ingress | Whether D-FAULT-15 row 16's spirit covers buffer-object mutators (F60) |
| `arrival_wall_ns` as diagnostic-only event field | Whether diagnostic fields on the event (not on the envelope) are acceptable (F61) |
| Late-binding subscriber registration for live channel back-channel | Whether D-BUS-6/-7/-8 admits a stable per-session subscriber set that includes live-channel-aware subscribers (F62) |
| Boundary-snapshot serialization of `_pending_envelopes` | Whether mid-session boundary snapshots should reflect future arrivals or stay session-initial-equivalent (F63) |
| Buffer-depth visibility as diagnostic surface for caller | Whether the channel may expose buffer state without granting orchestration authority (F64) |

The brief forbids resolving these in this session. They are catalogued as **constitutionalization prerequisites** for any subsequent contract phase.

---

## §G. Minimum admissible ingress surface

The brief asks for the "minimum admissible ingress surface." This section names the eight disciplines that together close every known threat model and define the unique admissibility shape.

### §G.1 The Eight Disciplines

Each discipline is a **necessary condition** for live ingress to be constitutionally compatible with the Step 8/9/10 substrate. The eight together are **sufficient** to close all eight threat models from Analysis §P.

**Discipline D1 — Channel Opacity.** The channel is a passive store. It produces no observable behavior to the orchestration substrate except through the session's Phase-A pull. The channel emits no events, registers no subscribers, exposes no state-machine, and does not observe session state. (Closes Threat 1, Threat 5, Threat 8.)

**Discipline D2 — Phase-A-Only Pull.** The session pulls the channel exactly once per `session.step()`, at the start of Phase A, before the existing `_drain_phase_a_envelopes`. No sub-phase pull, no Phase E pull, no Phase G pull. (Closes Threat 2, Threat 3, Threat 6.)

**Discipline D3 — Strict Atomic Snapshot.** The pull operation atomically captures the channel's current buffer contents and atomically clears the buffer. The operation holds whatever synchronization primitive the channel uses internally; the session sees the snapshot as a deterministic return value. New arrivals after the snapshot are invisible to this tick. (Closes Threat 2 hidden-race specifics.)

**Discipline D4 — Canonical-Order Discipline.** After the pull, the merged `_pending_envelopes` set is canonical-ordered by `(requested_at_tick, envelope_id)`. The drain iterates this canonical order. Transport-layer order, arrival order, and buffer storage order do not influence drain order. (Closes Threat 4.)

**Discipline D5 — Pull-Only Direction.** No callback, no notification, no signal, no async task, no event ever flows from channel into session except via the session's pull. The session is always the initiator. (Closes Threat 1 explicitly.)

**Discipline D6 — Predicate Closure Stability.** The execute-entry predicate closes over `_pending_envelopes` as Phase A left it. No subsequent mutation of `_pending_envelopes` (e.g. a second pull) happens within the same `session.step()`. The predicate is constructed by the session (D-EXEC-13c) and consumed opaquely by the executor (D-EXEC-13d). (Closes Threat 6 explicitly.)

**Discipline D7 — Per-Session Channel Lifecycle.** The channel is constructed at or before `session.begin()` and torn down at `session.close()`. Channel state does NOT survive into subsequent sessions in the same process. The transport may persist; the substrate's view of the channel does not. (Closes Threat 8.)

**Discipline D8 — Diagnostic Boundary.** Wall-clock arrival, transport identifiers, connection state, and any other non-authoritative metadata MAY be recorded on `OperatorAbortRequested` events as **explicitly diagnostic** payload (subject to D-SESS-5: not read by orchestration logic; not entering the fingerprint; not influencing replay-identity comparisons), OR MUST be omitted entirely. They MUST NOT enter the envelope schema (D-FAULT-9), the canonical-drain order (D-SCHED), the predicate closure (D-EXEC-13), or any authoritative continuity surface (D-CONT-1). (Closes Threat 3, partial Threat 7 via diagnostic-field discipline.)

### §G.2 Sufficiency claim

**Sufficiency claim.** Under D1 ∧ D2 ∧ D3 ∧ D4 ∧ D5 ∧ D6 ∧ D7 ∧ D8, every threat model from Analysis §P (Threats 1–8) is closed AND every existing substrate invariant (D-EXEC, D-SCHED, D-BUS, D-REPLAY, D-SESS, D-TRACE, D-LIFE, D-FORBID, D-CONT, D-FAULT) is preserved.

**Proof sketch (per threat).**

| threat | which discipline closes it | mechanism |
|---|---|---|
| 1 Callback authority | D1, D5 | channel emits no callbacks; pull-only |
| 2 Sub-tick observation | D2, D3 | one pull at Phase A; atomic snapshot |
| 3 Wall-clock arrival as authority | D4, D8 | canonical-order is content-addressed; diagnostic boundary |
| 4 Transport-layer ordering authority | D4 | canonical-order at pull boundary |
| 5 Channel-as-state-machine | D1 | channel is opaque storage |
| 6 Predicate substitution mid-execute | D6 | predicate captured at execute-entry; no re-pull |
| 7 PAUSED-as-wall-clock-wait | (not closed by these disciplines; see §F.3) | PAUSED is OPEN |
| 8 Cross-session live-channel state | D7 | per-session lifecycle |

Threat 7 (PAUSED-as-wall-clock-wait) is open under the framework; it requires a separate analytical pass per F58. The eight disciplines close seven of eight threats; the eighth is constitutionally open.

### §G.3 Necessity claim

**Necessity claim.** Each discipline closes a distinct, irreducible threat surface. Removing any one of D1–D8 reintroduces at least one threat:

* Remove D1 → channel can emit (Threat 1 reopens)
* Remove D2 → sub-phase pull (Threat 2)
* Remove D3 → race-on-buffer (Threat 2 variant)
* Remove D4 → arrival order leaks (Threats 3, 4)
* Remove D5 → push from channel (Threat 1 variant)
* Remove D6 → predicate substitution (Threat 6)
* Remove D7 → cross-session leak (Threat 8)
* Remove D8 → wall-clock authority (Threat 3 variant)

The eight disciplines are minimal: no smaller set is sufficient. (Formal minimality proof requires a separate pass; this is a sketch.)

### §G.4 What the Minimum Surface Does NOT Require

The Minimum Surface explicitly does NOT require:

* **A new SessionState value.** RUNNING / ABORTING / ABORTED / COMPLETED / FAILED are sufficient; live abort goes through ABORTING.
* **A new event type.** `OperatorAbortRequested`, `SessionAborting`, `SessionAborted`, `TaskCascadeSkipped` are sufficient.
* **A new envelope schema.** D-FAULT-9's existing schema is sufficient.
* **A new boundary snapshot field.** D-CONT-6's allowlist remains unchanged.
* **A new comparator surface.** `tools/check_session_replay_identity.py` remains unchanged; live-ingress events appear in `events.jsonl` and are byte-compared identically to pre-queue events.
* **A new replay-identity layer.** L1–L4 of D-REPLAY are unchanged.
* **A new orchestration phase.** D-EXEC-1's seven-phase order remains unchanged; the pull is sub-Phase-A.
* **Modification of any existing clause.** Every existing clause is preserved verbatim.

This is the framework's strongest claim: the Minimum Surface is **purely additive** to the contract. The contract phase, if pursued, authors new clauses; it does not edit any existing ones.

### §G.5 The Minimum Contract Delta

A future contract phase would (analytically; this is sketch, not authorship):

* add Theorem T2 as a normative clause (extension to D-FAULT-6 or as new D-FAULT-6b);
* add Theorem T3 as a normative clause (extension to D-EXEC-13 or as new D-EXEC-14);
* add Theorem T4 as a normative clause (extension to D-FAULT-2 or as new D-FAULT-2a);
* add Lemmas L1–L4 (or L2 + L3 as load-bearing, with L1, L4, L5 as derivable);
* add Disciplines D1–D8 (as a numbered admissibility list, e.g. new section §14 or as extensions to existing §13 D-FAULT);
* add the twelve D-FAULT-15 rows (#31–#42) from Analysis §Q.

Estimated delta: ~one new section to `phase_4b_deterministic_semantics.md`, structure parallel to §13's D-FAULT layout. No retraction. No modification. Pure addition.

This is **estimated scope only**; the contract phase will determine exact clause structure.

---

## §H. Deterministic-epoch requirement analysis (Q5)

The brief asks: "whether any admissible ingress semantics require new deterministic epochs."

### §H.1 The question precisely stated

A **deterministic epoch** is a recurrent, well-defined boundary in orchestration time that the substrate observes and that influences orchestration decisions. The existing epochs:

* per-`session.step()` orchestration tick (D-EXEC-1's 7-phase tick);
* per-`world.step()` physics tick (D-EXEC-4);
* per-segment boundary inside execute (D-EXEC-13 condition 4).

The question: does live ingress require introduction of a **new** epoch — e.g. a "per-arrival epoch" or "per-second epoch" or "per-Phase-A.5 epoch"?

### §H.2 Analytical answer

**No new deterministic epoch is required.** The Phase-A boundary of the existing orchestration tick is the unique authoritative-observation epoch for ingress. The framework's Discipline D2 (Phase-A-only pull) makes this explicit.

**Justification:**

* Theorem T3 establishes that Phase-A is the only constitutionally admissible observation surface within one tick.
* The Phase-A pull is a **sub-Phase-A activity** (within the existing Phase A's role of "intake / drain operator"), NOT a new phase.
* Lemma L1 (Drain-Epoch Determinism) names `(session_id, orchestration_tick)` as the authoritative observation primitive — already an existing primitive, not new.
* Sub-tick boundaries (Threat 2, F27 pre-execute second epoch rejection) are all rejected by the framework.

### §H.3 The "feels-like-an-epoch" temptation

A future implementation reader might be tempted to name the channel's atomic snapshot a "channel epoch" or the buffer's clear-time a "buffer epoch." These are not constitutionally meaningful epochs — they are internal channel-layer events with no orchestration observable. The framework's terminology (§D.1) recognizes only the **Drain Epoch** as the authoritative-observation epoch. Channel-internal timing has no substrate referent.

### §H.4 Conclusion

Q5 answered: **No new deterministic epoch is admissible or required.** Live ingress fits entirely within the existing orchestration-tick epoch structure. Any implementation that *appears* to require a new epoch is either misframing the problem (treating channel-internal timing as orchestrational) or proposing a constitutionally incompatible shape.

---

## §I. Transport-independence analysis (Q6)

The brief asks: "whether ingress can remain transport-independent under all admissible models."

### §I.1 Transport-Independence Theorem (T5, normative-candidate)

**Theorem T5 — Transport-Independence.** Under Disciplines D1–D8, the substrate's behavior (events, state transitions, replay-identity, fingerprints, retained state, contradiction preservation) is **invariant under change of transport**. Two implementations of the live channel that deliver the same envelope sets to the session at the same drain epochs produce byte-equal trace, regardless of:

* network protocol (WebRTC, websocket, HTTP, ZeroMQ, gRPC, named-pipe, message-queue, filesystem-polling),
* threading model in the transport layer,
* retry / backoff / deduplication policies in the transport layer,
* serialization format on the wire,
* number of concurrent operator connections,
* transport-layer wall-clock delivery latency.

**Hypotheses.** Disciplines D1, D5 (transport cannot influence orchestration state directly); D4 (canonical-order at pull boundary discards transport order); D8 (transport-arrival timestamps are diagnostic-only); Lemma L4 (replay reconstructs from trace alone, not from transport).

**Citation chain.** Analysis §D.6 (transport unconstrained); §F.7 (replay determinism doesn't require channel determinism); §I (transport orthogonality).

**Classification.** **NORMATIVE-CANDIDATE.** T5 is the formal statement of transport-independence. It is implied by D1, D4, D5, D8 + L4, but stating it explicitly as a theorem makes the property a citable invariant.

### §I.2 What transport-independence implies for contract authoring

The contract phase, if pursued, would NOT author any clause about specific transports. It would author clauses about:

* what the channel must do (Disciplines D1, D3, D5, D7);
* what the session must do (Disciplines D2, D4, D6);
* what fields can appear (D8 diagnostic boundary).

The transport's identity is invisible to the contract. A WebRTC implementation, a websocket implementation, and a sidecar-file-polling implementation are **identically conformant** if they all expose the same opaque-pull interface.

### §I.3 Conclusion

Q6 answered: **Yes, ingress remains transport-independent under all admissible models.** The eight disciplines define the substrate boundary; the transport sits outside that boundary and can vary freely. Theorem T5 names this property explicitly.

---

## §J. Multi-envelope-drain contradiction-timing analysis (Q7)

The brief asks: "whether contradiction timing remains replay-reconstructable under multi-envelope drains."

### §J.1 The multi-envelope drain question

In one Phase A drain, multiple eligible envelopes may be present in `_pending_envelopes` (whether pre-queued or live-arrived). They drain in canonical order (Lemma L3). The first abort envelope transitions RUNNING → ABORTING; subsequent envelopes are recorded forensically per D-FAULT-7 idempotency.

The question: under live ingress, can the drain order produce a non-replay-reconstructable contradiction timing?

### §J.2 D-FAULT-7 idempotency under multi-drain

D-FAULT-7: "an `OperatorAbortRequested` envelope arriving while the session is already in `ABORTING` or `ABORTED` MUST be recorded in the trace (as an envelope ingress event) but MUST NOT trigger a second state transition."

Under multi-envelope drain at one Phase A:

* First abort (canonical-smallest envelope_id at canonical-smallest requested_at_tick): transitions RUNNING → ABORTING; emits `OperatorAbortRequested` + `SessionAborting`.
* Subsequent aborts in the same drain: recorded as `OperatorAbortRequested` events at consecutive seq values; produce no further state transition (idempotent).
* The contradiction timing (which envelope "caused" the abort): the `SessionAborting` event payload carries `trigger_envelope_id` (at session.py:1410), which is the first abort's envelope_id. Replay reproduces this identifier byte-equal.

### §J.3 Replay-reconstructability under multi-drain

Under Lemma L4 + Lemma L2:

* The trace records each envelope's `OperatorAbortRequested` at its drain seq.
* The `SessionAborting` event records `trigger_envelope_id`.
* Replay reconstructs the pre-queue (Lemma L4).
* A replay session, draining in canonical order, identifies the same first abort (by canonical-smallest `(requested_at_tick, envelope_id)`).
* Replay's `SessionAborting` payload carries the same `trigger_envelope_id`.

The contradiction timing (which envelope caused the transition, when the transition happened, which envelopes were forensic-only) is **fully replay-reconstructable**. Multi-envelope drain does not introduce any non-determinism.

### §J.4 Contradiction-state-of-the-session timing

Beyond the abort cause, "contradiction timing" can also refer to the substrate-level contradictions D-FAULT-5b describes (peg attached + fixture empty + peg pose moved). Under live ingress:

* The contradiction state at the moment of abort is determined by the session's pre-abort node-execution history, NOT by the ingress timing.
* Multi-envelope drain at one Phase A does not interleave with Phase D/E of any node — the drain is at Phase A, before scheduler decision (Phase B). No node execution happens during the drain.
* Therefore: multi-envelope drain has zero effect on D-FAULT-5b contradiction state. Contradictions, if any, are inherited from the previous tick's Phase G (the last completed node's terminal state).

### §J.5 Two contradictory aborts at the same Phase A

A degenerate case: two operators submit abort envelopes that both arrive in the channel before Phase A pull of `session.step(K)`. Both are eligible (`requested_at_tick ≤ K`). Canonical order picks one as the transition cause.

Is this constitutionally problematic? **No.** The substrate has no concept of "the operator's intent" beyond the envelope payload. Two envelopes with the same kind and the same requested_at_tick but different reason are constitutionally distinct (different envelope_id via content-addressing). Their canonical order is deterministic. D-FAULT-7 makes the second forensic. Replay reproduces the choice byte-equal.

The "contradiction" in this case is operator-side (two operators thought they were acting first), not substrate-side. The substrate's job is to record both with full forensic provenance; it does so.

### §J.6 Conclusion

Q7 answered: **Yes, contradiction timing remains replay-reconstructable under multi-envelope drains.** Lemma L3's canonical order + D-FAULT-7's idempotency + L4's reconstruction sketch together discharge the multi-drain question without additional clauses. Multi-envelope drain is constitutionally well-formed under the existing substrate plus the proposed Lemma L3 normalization.

---

## §K. Threat-model consolidation

The Analysis enumerated eight threat models (§P.1–§P.8). The framework consolidates them into a **single Mitigation Theorem**, supported by the Eight Disciplines (§G).

### §K.1 Mitigation Theorem (M, normative-candidate)

**Theorem M — Threat-Model Closure.** Under Disciplines D1–D8 (§G.1), all eight threat models from Analysis §P are constitutionally closed:

* Threat 1 (Callback authority) → closed by D1 + D5.
* Threat 2 (Sub-tick observation) → closed by D2 + D3.
* Threat 3 (Wall-clock arrival as authority) → closed by D4 + D8.
* Threat 4 (Transport-layer ordering as authority) → closed by D4.
* Threat 5 (Channel-as-state-machine) → closed by D1.
* Threat 6 (Predicate substitution mid-execute) → closed by D6.
* Threat 7 (PAUSED-as-wall-clock-wait) → **OPEN** under §F.3; not closed by D1–D8.
* Threat 8 (Cross-session live-channel state) → closed by D7.

For seven of eight threats, the Eight Disciplines are sufficient. For Threat 7, additional analytical work (F58) is required before constitutional compatibility can be asserted.

**Classification.** **NORMATIVE-CANDIDATE.** A future clause asserting Theorem M provides a single citable proposition for rejecting non-conformant Step 11 PRs: "violates Theorem M (threat model X reopens) — see Discipline DY."

### §K.2 Threat-model citation summary

The framework treats threat models as **historical-derivation** material. They are NOT themselves normative; the Disciplines are. The Disciplines are the load-bearing artifacts; the threat models are the evidence-of-need.

This separation matters because future contract reviewers must be able to evaluate proposed PRs without re-deriving the threat models. The Disciplines are the reading surface. Threat models live in the Analysis as historical record.

---

## §L. Additive-only contract-surface analysis (Q8)

The brief asks (implicitly via §G): what is the additive-only contract-surface delta?

### §L.1 What additive-only means

A contract delta is **additive-only** if it:

* introduces new clause text;
* does NOT modify any existing clause text;
* does NOT delete any existing clause;
* does NOT relax / weaken / qualify any existing invariant;
* may strengthen existing invariants by adding explicit foreclosures (e.g. T2 strengthens D-FAULT-6 by making the N2-only-impossibility explicit), but never weakens.

The framework's central additive-only claim: **Step 11's contract delta, if authored from this framework, is purely additive.**

### §L.2 Enumeration of additive-only delta

A future contract phase authoring from this framework would add:

1. **Theorems T1–T4 + T5** as new clauses (or as additions to existing sections):
   * T1 likely no separate clause (implicit; cite existing clauses);
   * T2 as new D-FAULT-6b OR extension to §13.6 D-FAULT-6;
   * T3 as new D-EXEC-14 OR extension to §1 D-EXEC;
   * T4 as new D-FAULT-2a OR extension to §13.2 D-FAULT-2;
   * T5 as new D-REPLAY-10 OR extension to §4 D-REPLAY.

2. **Lemmas L1–L4 (+ optionally L5)** as supporting clauses, OR as commentary attached to the Theorem clauses.

3. **Disciplines D1–D8** as a numbered admissibility list, likely as a new subsection (e.g. §14 "Live Ingress Admissibility" or as §13.18 within D-FAULT).

4. **The twelve proposed D-FAULT-15 rows (#31–#42)** as a row-extension to §13.15 D-FAULT-15 (the existing anti-pattern enumeration).

5. **Ontology terminology (§D.1)** as a glossary extension to §0 of `phase_4b_deterministic_semantics.md`.

Estimated total delta: one new top-level section (or extension to §13), plus a §0 glossary addition, plus 12 D-FAULT-15 rows.

### §L.3 What is NOT additive (i.e., what is forbidden in the delta)

A future contract phase MUST NOT:

* modify any existing clause's text;
* weaken D-EXEC-13 (e.g. by admitting predicate mutation mid-execute);
* weaken D-FAULT-6 / D-FAULT-6a (e.g. by admitting mid-Phase-E ingress);
* weaken D-FAULT-9 (e.g. by removing the canonical-ordering field);
* relax D-CONT-1's allowlist to include live-channel state;
* relax D-TRACE-2's append-only discipline;
* weaken D-REPLAY-1's layered identity model;
* introduce a new SessionState value beyond what existing clauses admit (RECOVERING remains forbidden by D-FAULT-15 #18);
* introduce a new orchestration phase beyond D-EXEC-1's seven;
* introduce wall-clock authority anywhere.

These are framework-level non-introductions, mirroring the brief's forbidden list. Any contract author who finds themselves authoring text that would do any of the above is at the wrong session — they need a separate analysis pass first.

### §L.4 Q8 answered

Q8 (implicit, via §G.4–§G.5): the minimum additive-only contract-surface delta is one new section + glossary extension + 12 D-FAULT-15 rows. No existing clause changes.

---

## §M. Replay-authoritative ingress identity conditions

This section explicitly enumerates the conditions under which two live-ingress sessions produce byte-equal trace. The brief explicitly asks for this.

### §M.1 The three identity conditions (Lemma L5 restated)

Two sessions S₁, S₂ of the same `(Job, seed, runtime_hash, cell_cfg_hash)` produce byte-equal `events.jsonl` (modulo `wall_ns`) IFF:

1. **Epoch-Identity (C1).** For every orchestration_tick K, the envelope sets drained at K's Phase A are equal: Φ₁(K) = Φ₂(K).
2. **Canonical-Drain-Order (C2).** Both sessions drain in canonical order at every Phase A.
3. **Predicate-Closure-Equivalence (C3).** At every execute-entry, both predicates close over identical state derived from the same `_pending_envelopes`.

C2 is invariant under Discipline D4. C3 is implied by C1 + C2 + D6. So Epoch-Identity (C1) alone is the necessary and sufficient condition.

### §M.2 What C1 requires

Epoch-Identity requires that the channel deliver to the session, at each Phase A pull, the same envelope set in both sessions. This is **not** a transport-determinism requirement — it is a delivery-pattern equivalence requirement. Two transports can be wildly different in wall-clock behavior yet deliver the same envelope sets at the same epochs.

In practice, C1 is achieved by:

* in test scenarios: pre-queue all envelopes (degenerate case — C1 trivially holds);
* in replay scenarios: reconstruct envelopes from the trace via Lemma L4 (also degenerate);
* in production scenarios: by accepting that two production runs with different transports/network conditions are **different sessions** with potentially different `events.jsonl`. Cross-production replay-identity is not asserted.

### §M.3 The "replay vs production" distinction

Replay-identity holds between (production-session, replay-of-that-session). It does NOT hold between (production-session-1, production-session-2) when both face live arrivals. This is the same boundary D-REPLAY-8 already draws for `(Job, seed)` across different `ExecutionSession` instances (within-instance bit-identical, cross-instance within-tolerance).

The framework's central replay-authority claim under live ingress is therefore: **a session's trace is sufficient to replay that session**, byte-equal. The trace is the authority. Cross-session-with-different-live-arrivals divergence is expected and not a violation.

### §M.4 The identity conditions are clause-shaped

C1, C2, C3 are stated such that a future contract clause could assert them verbatim. They are the framework's most-mechanical normalization candidates.

---

## §N. Phase-A visibility formalization

This section locks the Phase-A visibility model exactly once.

### §N.1 The Phase-A Visibility Surface

Define the **Phase-A Visibility Surface** of `session.step(K)` as the deterministic function:

```
Φ(K) : envelopes that the session observes during session.step(K)'s Phase A drain
```

Φ(K) is determined by:

* the contents of `_pending_envelopes` at the start of Phase A of `session.step(K)`, plus
* the contents of the channel buffer at the moment of Phase A pull, minus
* any envelope whose `requested_at_tick > K` (still gated for future ticks), minus
* any envelope already in `_drained_envelope_ids` (D-FAULT-7 idempotency forensics).

### §N.2 The Phase-A Ordering Invariant

Within Φ(K), drain order is determined by `(requested_at_tick, envelope_id)` lexicographic sort (Lemma L3). Two envelopes in Φ(K) drain in this order regardless of arrival path.

### §N.3 The Phase-A Visibility Boundary

The boundary between "visible to session.step(K)" and "visible to session.step(K+1) or later" is exactly the moment of Phase A pull in session.step(K). Arrivals before that instant: visible at K. Arrivals after: visible at K+1 or later.

This boundary is **wall-clock-defined but not wall-clock-authoritative**: the boundary's wall-clock instant is the moment of pull, but the substrate does not record this instant (it is captured only as diagnostic `wall_ns` on the resulting events). Replay reconstructs Φ(K) from the trace alone (Lemma L4); wall-clock is not needed.

### §N.4 Clause-shape claim

A future clause could state: "The Phase-A Visibility Surface Φ(K) is the unique authoritative observation surface for ingress at orchestration tick K. Sub-tick observation surfaces are FORBIDDEN. Φ(K) is determined deterministically by the channel state at pull instant and the `_pending_envelopes` state at Phase A entry."

This is **NORMATIVE-CANDIDATE**. It is Theorem T3 + Lemma L1 + Discipline D2 stated as one combined assertion.

---

## §O. Atomicity preservation requirements

The brief asks for "atomicity preservation requirements."

### §O.1 Three atomicity surfaces

The framework recognizes three distinct atomicity surfaces:

* **Phase E atomicity** (D-FAULT-6a) — the executor's `execute()` is one atomic call from the session's perspective. Preserved under live ingress (§K of Analysis).
* **Phase A atomicity** (proposed under Discipline D3) — the channel pull is an atomic operation; the session sees a deterministic snapshot. New under Step 11 framework; required by Discipline D3.
* **Per-tick mutation-window atomicity** — within one `session.step(K)`, the session's mutable orchestration state mutates only in well-defined moments (Phase A drain, Phase D registry updates, Phase G commits). No external thread mutates session state at any other moment.

### §O.2 Phase E atomicity preservation requirements

Live ingress MUST NOT:

* observe channel state during Phase E;
* trigger executor termination from the channel directly;
* substitute the predicate mid-execute;
* emit any orchestration event during Phase E.

These are all forbidden by D-FAULT-6a + D-EXEC-13a + D-FAULT-15 rows 5, 16, 22, 27, 28, 29. The framework does not need to restate them; it cites them as preserved.

### §O.3 Phase A atomicity preservation requirements

Live ingress MUST ensure that the Phase A pull is atomic with respect to:

* the channel's internal write side (transport pushing arrivals);
* the session's read side (the pull operation);
* the canonical-order discipline applied to the merged envelope set.

This is Discipline D3 (strict atomic snapshot). Implementation may use a lock, a CAS, a lock-free queue with snapshot semantics, etc. The constitutional requirement is the atomicity of the observation, not the choice of mechanism.

### §O.4 Per-tick mutation-window atomicity

The session is the sole mutator of orchestration state (D-SESS-1). Under live ingress, the channel is NOT a session-state mutator — it mutates only its own buffer, and the session reads (and clears) the buffer at Phase A.

Critically, the session must NOT expose any mutator API to the channel (no `session.append_envelope()`, no `session.queue_abort()`). The session's mutation happens only:

* in Phase A drain code (modifying `_pending_envelopes` after pull);
* in Phase D registry-update code (already-existing);
* in Phase G commit code (already-existing).

This is the mutation-window discipline. Live ingress preserves it under D1 + D5.

### §O.5 Atomicity-preservation requirements summarized

A future Step 11 implementation, to satisfy the framework, must:

* preserve Phase E atomicity (D-FAULT-6a, already required);
* introduce Phase A atomicity at the channel-pull boundary (Discipline D3, new);
* preserve per-tick mutation-window atomicity (D-SESS-1, already required; implementation must not expose new mutator APIs to the channel).

---

## §P. Constitutionalization readiness assessment

The framework's terminal output: an assessment of what is ready for the contract phase and what remains as analytical prerequisites.

### §P.1 Ready for clause work

* **Theorem T2** (N2-only-Interruption Impossibility) — fully derived, citation-complete.
* **Theorem T3** (Phase-A-Only Observability) — fully derived.
* **Theorem T4** (Acquisition-Visibility Tick Alignment) — fully derived.
* **Theorem T5** (Transport-Independence) — fully derived.
* **Lemma L1** (Drain-Epoch Determinism) — fully derived.
* **Lemma L2** (Epoch-Identity ⇒ Trace Identity) — fully derived; proof sketch in Analysis §H.
* **Lemma L3** (Canonical-Order Commutativity) — fully derived; closes §11.1 gap.
* **Lemma L4** (Replay-Reconstruction From Trace Alone) — fully derived.
* **Discipline D1–D8** — fully derived; mitigation claims (Theorem M) discharged for 7/8 threats.
* **Ontology terminology** — six objects defined; terminological exclusions enumerated.
* **Proposed D-FAULT-15 rows #31–#42** — fully enumerated in Analysis §Q.

These items are **NORMATIVE-CANDIDATE** and would constitute the contract-phase deliverable.

### §P.2 NOT ready for clause work (open prerequisites)

* **F42 / F58** PAUSED state semantics — requires its own analytical pass before `pause`/`resume` envelope kinds are admissible.
* **F59** `manual_advance` redefinition or removal — requires its own analytical pass.
* **F60** D-FAULT-15 #16 reach onto object-method ingress — interpretation question.
* **F61** Diagnostic-field semantics on the event — minor interpretive question.
* **F62** Subscriber-set extension for live channel — minor interpretive question.
* **F63** Boundary-snapshot serialization of `_pending_envelopes` — interpretation question.
* **F64** Liveness vs determinism trade-off — operational interpretive question.
* **F65** Cross-session transport lock ordering — implementation-detail; out of substrate scope.
* **Threat 7 closure** — depends on F58's PAUSED resolution.

These items are **OPEN** and would require their own analysis-only sessions before contract phase can author the corresponding clauses.

### §P.3 Recommended sequencing

If Step 11 proceeds to contract phase, the framework recommends (analytically, not prescriptively):

1. **First analytical pass:** F58 (PAUSED semantics). Closes Threat 7. Determines whether the `pause`/`resume` envelope kinds are admissible.
2. **Second analytical pass:** F59 (`manual_advance` disposition). May result in dropping the reserved name.
3. **Third analytical pass:** F60–F64 batch (interpretive clarifications).
4. **Contract phase:** authors the additive-only delta per §L.2, citing the framework's theorems/lemmas/disciplines.
5. **Implementation phase:** (out of scope for analytical sessions; would happen only after contract phase closes).

Each of (1), (2), (3) is its own session. Combining them with (4) risks under-analysis. Combining (4) with (5) violates the brief's "no runtime implementation yet" discipline.

### §P.4 Constitutionalization-readiness verdict

The framework is **READY** to support a Step 11 contract phase covering:

* the channel-as-opaque-buffer topology;
* the Eight Disciplines D1–D8;
* the canonical-order discipline (Lemma L3);
* the proposed D-FAULT-15 row extensions #31–#42;
* Theorems T2–T5 and Lemmas L1–L4 (or a subset).

The framework is **NOT READY** to support:

* `pause`/`resume`/`manual_advance` kind expansions (depends on F58/F59);
* PAUSED state semantics (depends on F58);
* any kind-specific clauses beyond `abort`.

A contract phase that authored only the channel-mechanism delta would be a constitutionally clean, additive-only landing. A contract phase that tried to land the kind expansion alongside would be premature.

---

## §Q. Step 11 closure posture

### §Q.1 What this framework closes

This document closes the **constitutionalization-preparation** phase of Step 11. Specifically, it closes:

* normalization of theorems and lemmas (§B, §C);
* ingress ontology stabilization (§D);
* finding-by-finding admissibility classification (§E);
* semantics admissibility matrix (§F);
* minimum admissible ingress surface (§G);
* deterministic-epoch requirement analysis (§H);
* transport-independence analysis (§I);
* multi-envelope drain contradiction-timing analysis (§J);
* threat-model consolidation (§K);
* additive-only contract-surface analysis (§L);
* replay-authoritative ingress identity conditions (§M);
* Phase-A visibility formalization (§N);
* atomicity preservation requirements (§O);
* constitutionalization readiness assessment (§P).

The framework discharges every item in the brief's primary focus list and explicit-analysis list.

### §Q.2 What this framework does NOT close

* **Step 11 itself is NOT closed.** No contract is authored. No clauses are added to `phase_4b_deterministic_semantics.md`. The contract document remains exactly as it was at Step 10 Direction A closure (2026-05-21).
* **PAUSED / pause / resume / manual_advance** are NOT resolved. They require their own analytical passes (F58, F59) before contract phase can address them.
* **Implementation** is NOT authored. No code is added. No transport choice is made. No tests are written.
* **Step 11 contract phase** is NOT begun. The contract phase is the next session's prerogative, if pursued.

### §Q.3 Substrate posture under this framework

The substrate posture, after this analytical session:

> **Replay-authoritative deterministic orchestration substrate with empirically-validated mid-trajectory predicate semantics on real PhysX, with an analytically-derived live-ingress admissibility framework specifying eight necessary-and-sufficient disciplines for live-channel constitutional compatibility, plus four normative-candidate theorems and four normative-candidate lemmas ready for contract-phase authoring.**

The posture extends Step 10 Direction A's closure posture by adding the framework's analytical output. No new empirical evidence has been produced (no Isaac validation runs; no new tests). No contract surface has changed. No code has been altered.

### §Q.4 Next-session preconditions

If a future session pursues Step 11 contract phase, the preconditions are:

* this framework remains the authoritative classification (any deviation is a constitutionalization regression);
* the open items F42 / F57–F65 have been addressed or explicitly deferred from the contract phase;
* the contract authors honor the additive-only discipline (§L.3);
* the contract authors cite the framework's theorem/lemma/discipline labels rather than re-deriving them.

If a future session pursues a different open item first (e.g. F58 PAUSED analysis), the framework's existing classifications carry forward unchanged; only the F-labeled open items advance.

### §Q.5 Closure statement

The Step 11 architectural-analysis state is now constitutionally stabilized. The findings of the Analysis are normalized into theorems, lemmas, disciplines, and an ontology. Every finding is classified. Every constitutional question the brief asked has an explicit answer with citation.

The substrate's load-bearing invariants — replay-authoritative truth, append-only causality, deterministic orchestration authority, Phase E atomicity, contradiction preservation, no wall-clock authority — are preserved verbatim and cited as load-bearing throughout.

The N2-only-interruption impossibility theorem (Theorem T2) is the framework's central claim about the substrate's expressiveness bound. The Eight Disciplines (D1–D8) are the framework's central claim about the unique admissibility shape. The Epoch-Identity Lemma (L2) is the framework's central claim about replay-authority under live ingress. The Transport-Independence Theorem (T5) is the framework's central claim about the substrate's transport-orthogonality.

No clause has been weakened. No implementation has been authored. No hidden authority has been admitted.

This document is final for the scope of this session.

---

**End of Step 11 admissibility framework.**

Predecessor: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md). Architectural baseline: [phase_4b_orchestration_architecture.md](phase_4b_orchestration_architecture.md). Predecessor closures: [Step 8 / 9](phase_4b_deterministic_semantics.md), [Step 10 Direction A](phase_4b_step10_direction_a_analysis.md).
