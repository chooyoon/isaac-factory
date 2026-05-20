# Phase 4B Step 11 — Closure Verification & Framework Refinements

**Status: CONSTITUTIONAL CLOSURE-VERIFICATION ANALYSIS (2026-05-21).** This document verifies that the Step 11 framework (T1–T7 + L1–L5 + D1–D9 + D-FAULT-15 rows #31–#43 + 6-object ontology), as established by [analysis](phase_4b_step11_live_ingress_analysis.md) + [framework](phase_4b_step11_admissibility_framework.md) + [F58](phase_4b_step11_f58_paused_analysis.md) + [F59](phase_4b_step11_f59_manual_advance_analysis.md), constitutes a valid candidate constitutional closure system, and proposes three refinements (T8, T9, L5-fold) to reach final closure.

No contract authoring. No implementation. No clause mutation. Documentation-only.

---

## §1. Verification scope

Six closure properties evaluated:

| property | criterion |
|---|---|
| internal completeness | every Step 11 surface is covered by some theorem/lemma/discipline |
| internal non-contradiction | dependency graph is a DAG; no implementation coincidence; no transport/wall-clock leakage |
| minimal sufficiency | no element can be removed without weakening a guarantee |
| hidden-authority gap-freedom | no adversarial pathway grants orchestration authority without violating some framework element |
| unclassified-ingress-surface gap-freedom | every substrate ingress path is classified |
| stability for contract-authoring | citation surfaces are in place; no further analytical prerequisite |

---

## §2. Theorem mutual sufficiency

Each T1–T7 has a distinct, non-empty constitutional domain:

| theorem | domain |
|---|---|
| T1 | clock topology (orchestration_tick vs world.step) |
| T2 | mid-Phase-E latency floor |
| T3 | sub-tick ingress observation surface |
| T4 | acquisition-visibility tick alignment |
| T5 | transport-substrate boundary |
| T6 | PAUSED admissibility |
| T7 | envelope-semantic foreclosure |

**Theorem 2.A (Mutual Sufficiency).** Step 11 introduces ingress channel, drain epoch, predicate-closure capture, PAUSED state, and envelope kind expansion. Each maps to exactly one T1–T7 domain:
- channel → T3 + T5;
- drain epoch → T3 + T4;
- predicate-closure capture → T2 + T4;
- PAUSED → T6;
- kind expansion (admit side) → T6; (foreclosure side) → T7.

∴ T1–T7 cover the Step 11 surface. Mutually sufficient. No theorem-gap.

---

## §3. Derivability and redundancy

Per-theorem audit:

| theorem | derivable from existing clauses? | redundant? | reason kept |
|---|---|---|---|
| T1 | yes (D-EXEC-1, D-EXEC-4, session.py invariant) | no | premise for T2/T3/T6 |
| T2 | yes (T1, D-FAULT-6, D-EXEC-13, D-FAULT-15 rows) | no | latency-floor consequence operationally critical |
| T3 | yes (D-EXEC-1, D-EXEC-2, D-FAULT-6, T1) | no | positive sole-observation-surface statement |
| T4 | yes (partial) (D-BUS-1, D-EXEC-7, D-FAULT-2, T3) | no | deferred-from-Phase-A property non-trivial |
| T5 | yes (D1, D4, D5, D8, L4) | no | transport-independence consequence-statement |
| T6 | partially (T1, T3, T4, D9, D-FAULT-2) | no | Property 2 (structural skip) is novel |
| T7 | yes (D-SCHED-1, D-SCHED-12, D-SESS-6, D-EXEC-13c, D-FAULT-2) | no | forecloses class of proposals |

**Theorem 3.A (Non-Redundancy).** No T1–T7 is redundant. Each captures a non-obvious synthesis or consequence that future contract-authoring would otherwise need to re-derive.

Per-lemma audit:

| lemma | derivable? | redundant? | status |
|---|---|---|---|
| L1 | yes (T3, D-FAULT-9, L3) | no | keep — names drain epoch |
| L2 | yes (L1, L3, D-REPLAY-2) | no | keep — load-bearing replay claim |
| L3 | yes (D-FAULT-9, content-addressing) | no | keep — closes §11.1 commutativity gap |
| L4 + R1 | yes (L2, L3, D-TRACE-2; R1 essential) | no | keep — R1 part of L4 |
| L5 | yes (L2, L3, D6) | **marginal** | recommend fold into L2 |

**Sub-finding 3.B.** L5 is marginal: derivable from L2 + L3 + D6, sharpens L2's "implies" to "IFF," but does not add separately-citable content. Recommended fold-into-L2-as-corollary.

---

## §4. T8 Authority Singularity (promotion candidate)

### §4.1 Statement

**Candidate T8 — Authority Singularity.** Every orchestration concern has exactly one authoritative emitter/mutator. The substrate's authority topology is a function:

```
authority : Concern → Authority    with |authority(c)| = 1 ∀ c
```

with concrete bindings (already established by clauses):

| concern | authority | citation |
|---|---|---|
| node selection | scheduler pure function | D-SCHED-1 |
| predicate verdict | predicate pure function | D-SCHED-12 |
| node execution / PhysX mutation | TaskExecutor (Phase E) | D-SESS-1 + D-FAULT-6a |
| Phase-D observational projection | TaskExecutor | D-CONT-5a |
| occupancy commit | session (Phase G, PASS verdict) | D-CONT-5 |
| cascade-skip emission | session (Phase G, canonical order) | D-FAULT-3 + D-FAULT-4 |
| recovery determination | graph topology (metadata) | D-FAULT-8 + D-FAULT-8a |
| `orchestration_tick` advancement | session.step() return | T1 |
| envelope ingress emission | session at Phase A | D-FAULT-6 + T4 |
| session_state transition | session at Phase A (or post-Phase-E classification) | D-FAULT-2 + T4 |
| event bus seq assignment | EventBus at emit time | D-BUS-3/-4 |

### §4.2 Derivability

T8 is implied by D-FAULT-2 (single-emitter) + D-SESS-1 (sole mutator) + D-SCHED-1 + D-SCHED-12 (pure-function discipline). Aggregate consequence; derivable.

### §4.3 Promotion rationale

* F58 and F59 derivations repeatedly invoke "authority singularity" as if it were a single proposition. Promotion gives those derivations a citable label.
* Future ingress-kind proposals can be tested against T8 directly. Without T8, each proposal must re-cite D-FAULT-2 + D-SESS-1 + D-SCHED-1/-12.
* T8 captures the substrate's authority topology *as a whole* — a property deeper than any single existing clause.

**Recommendation:** PROMOTE T8 to normative-candidate.

---

## §5. T9 Input Whitelist Closure (promotion candidate)

### §5.1 Statement

**Candidate T9 — Orchestration-Decision Input Whitelist Closure.** The orchestration-decision pure functions' input sets are constitutionally closed at:

* scheduler: `(graph, registry, completed, failed, retry_counts)` (D-SCHED-1);
* predicate: `registry` (D-SCHED-12);
* registry mutation (Phase D): observational projection from PhysX (D-CONT-5a);
* registry mutation (Phase G): PASS-verdict-conditioned mutations (D-CONT-5, D-FAULT-3);
* executor predicate closure: `(envelope snapshot, base_tick, tick_budget_ticks, task_id)` at execute-entry (D-EXEC-13c).

No additional inputs may be added without weakening at least one existing clause. The whitelist is *closed*.

### §5.2 Relationship to T7

T7 is T9's contrapositive applied to envelope kinds. T7 ⟸ T9 + D-FAULT-2.

If T9 holds, T7 follows: an envelope kind cannot widen the input whitelist; ∴ no kind beyond Lemma 2.2's effect set is admissible.

T7 remains in the inventory because it states the envelope-kind specialization explicitly.

### §5.3 Promotion rationale

* T9 captures the *closure property* of the input-whitelist set, logically prior to T7.
* Future framework work beyond envelopes (observers, instrumentation, validation extensions) needs T9 as its citation surface; without T9, each such proposal must re-derive the closure property.
* T9 makes the "no fifth surface" emergent property explicit and citable.

**Recommendation:** PROMOTE T9 to normative-candidate.

---

## §6. L5 fold-into-L2

### §6.1 L5 statement (current)

L5 — Sufficient Identity Conditions: Epoch-Identity (C1) alone is necessary and sufficient for byte-equal trace identity (collapses C1/C2/C3 to C1).

### §6.2 Derivation

L5 ⟸ L2 + L3 + D6. L5 sharpens L2's "implies" (Epoch-Identity ⇒ Trace Identity) to "IFF" (Epoch-Identity ⇔ Trace Identity).

### §6.3 Fold rationale

* L5 adds no separately-citable content; every concrete use cites L2 + L3 + D6 jointly anyway.
* L2's statement can be extended in the framework document to include the "necessary" direction as a corollary, without a separate lemma label.

**Recommendation:** FOLD L5 into L2 as a corollary in any future framework revision.

---

## §7. Discipline completeness

D1–D9 cover all eight original Step 11 threat models (Framework §G, §P) plus the F58-introduced Threat 7 (PAUSED-as-wall-clock-wait) closed by D9.

### §7.1 Adversarial threat-search beyond the original eight

Six additional vectors evaluated:

* **HA1 Channel-side event observation** — covered by D-SESS-7 + T5.
* **HA2 Mid-session subscriber registration** — covered by D-BUS-6/-7/-8.
* **HA3 Module-level state manipulation** — covered by D-FORBID-3 + D-SCHED-1.
* **HA4 PhysX-state perturbation** — covered by D-FORBID-12 + D-SESS-1 + D-FAULT-6a.
* **HA5 Subscriber-via-transport feedback loop** — constitutionally clean (substrate sees only Phase A drain; transport-side action is out-of-substrate).
* **HA6 Time-travel via reopen-stage** — covered by D-FORBID-12; reopen-stage is cycle isolation, not state restoration.

**Sub-finding 7.A.** No additional threat surface requires a new discipline. D1–D9 are **complete**.

### §7.2 Minimality

Per Framework §G.3 + §15 of this document's preceding analysis: removing any Di reopens at least one threat. D1–D9 are **minimal**.

---

## §8. Unclassified-ingress-surface check

Eight substrate ingress paths enumerated:

1. `Job` construction at session.begin() — frozen (D-FORBID-4).
2. `CellConfig` at construction — frozen.
3. `pending_operator_envelopes` at construction — D-FAULT-9, T6, T7.
4. Live channel pull at Phase A — D1–D9.
5. `session.step()` invocations — caller-side; D-FORBID-11 + D9.
6. Subscriber registration at construction — D-BUS-6/-7/-8.
7. PhysX state from Isaac Sim — D-CONT-5a observational projection.
8. Asset loads at session start — runtime_hash + cell_cfg_content_hash.

All eight classified. Sub-paths covered.

**Sub-finding 8.A.** No unclassified ingress surface remains.

---

## §9. Hidden-authority path audit

Six attack vectors (§7.1) evaluated. None constitutes an uncaught hidden-authority path.

The subscriber-via-transport feedback loop (HA5) is **constitutionally clean** but **operationally surprising**: a substrate subscriber may cause transport-side action that injects a new envelope into the channel. The substrate observes only the eventual Phase A drain; the trace records it transparently. Replay reconstructs identically.

**Sub-finding 9.A.** Hidden-authority closure is complete.

---

## §10. Causality DAG closure under T1–T7

Every causal arc in the substrate traces through:

```
trace[seq] → (envelope drain | node lifecycle | state transition | boundary snapshot)
            → recorded contemporaneously (T4)
            → reproducible via pure-function re-evaluation on identical inputs
```

Five candidate gaps (sub-tick mutations, subscriber-side state, transport state, wall-clock observations, PhysX internal state) evaluated — each is constitutionally barred.

**Sub-finding 10.A.** Replay-authoritative causality is closed under T1–T7 + existing clauses.

---

## §11. Circular-dependency audit

Theorem dependency graph (constructed):

```
T1 (no theorem dependencies) → supports T2, T3, T6
T3 ⟸ T1 → supports T4, T6, L1
T4 ⟸ T3 → supports L2, T6
T2 ⟸ T1
T5 ⟸ L4 (depth 2)
T6 ⟸ T1, T3, T4
T7 ⟸ T9 (proposed)
T8 (proposed, no theorem dependencies)
T9 (proposed, no theorem dependencies)
```

DAG. No cycles. All theorems trace back to base clauses or strictly lower-depth theorems.

Lemma graph:

```
L3 → L1 → L2 → L4 (+ R1)
                → L5 (marginal)
```

DAG. No cycles.

**Sub-finding 11.A.** No circular dependencies anywhere in the framework.

---

## §12. Implementation-coincidence audit

Per theorem: no dependency on CPython behavior, libc behavior, OS scheduling, or external library coincidence. Every theorem depends on substrate-mandated properties.

Edge case `derive_envelope_id` (uses `hashlib.blake2b`): blake2b is a substrate-acceptable deterministic, collision-resistant, version-portable hash. Choice of algorithm is implementation; *property* is substrate-mandated.

**Sub-finding 12.A.** No theorem leaks implementation coincidence.

---

## §13. Transport / wall-clock leakage audit

Per theorem and per lemma: no transport reference; no wall-clock reference; all timing statements in `orchestration_tick` terms; `wall_ns` consistently diagnostic.

**Sub-finding 13.A.** No transport or wall-clock leakage in any theorem or lemma.

---

## §14. Constitutional minimality verdict

* T1–T7: keep all (each captures non-obvious synthesis or consequence; removal forces re-derivation in future authoring).
* L1–L4 (with R1): keep all.
* L5: marginal; recommend fold into L2.
* D1–D9: keep all (Framework §G.3 + §7.2 confirm minimality).
* T8, T9: promotion candidates (§4, §5).

**Sub-finding 14.A.** Framework is constitutionally minimal modulo L5-fold + T8/T9 promotion. Three refinements bring it to final closure.

---

## §15. Aggregate closure-verification verdict

| closure property | verdict |
|---|---|
| internal completeness | YES (§2) |
| internal non-contradiction | YES (§11, §12, §13) |
| minimal sufficiency | YES modulo L5 (§14) |
| hidden-authority gap-freedom | YES (§9) |
| unclassified-ingress-surface gap-freedom | YES (§8) |
| stability for contract-authoring | YES (§14 + this section) |

**Closure-verification verdict: COMPLETE.** The Step 11 + F58 + F59 framework constitutes a valid candidate constitutional closure system. Three refinements are recommended:

1. PROMOTE T8 (Authority Singularity) to normative-candidate.
2. PROMOTE T9 (Orchestration-Decision Input Whitelist Closure) to normative-candidate.
3. FOLD L5 into L2 as a corollary.

After these three refinements, the framework reaches **constitutional closure** at:
- T1–T9 (9 theorems);
- L1–L4 with R1 (4 lemmas + 1 refinement);
- D1–D9 (9 disciplines);
- D-FAULT-15 rows #31–#43 (13 forbidden-pattern row analytical proposals);
- 6-object ingress ontology.

The framework is **stable for contract-authoring**. A future Step 11 contract phase can author normative clauses citing the framework's labels directly without re-derivation.

The framework's "additive-only" property (Framework §L.1) is preserved: no existing contract clause requires modification; the framework's new clauses purely extend.

No new substrate analysis is required to begin contract authoring. The framework discharges all conceivable Step 11 constitutional questions within its closure surface. Remaining open items (F60–F65 from Framework §P.2) are interpretive sub-questions whose resolution does not affect the framework's closure.

---

## §16. Preserved invariants

Every invariant under closure verification:

* replay-authoritative truth ✓
* append-only causality ✓
* authority singularity ✓ (now formalized via candidate T8)
* `orchestration_tick` supremacy ✓ (formalized via T1)
* Phase-A-only observability ✓ (formalized via T3)
* deterministic interruption boundaries ✓ (formalized via T2)
* Phase E atomicity ✓ (D-FAULT-6a + D-EXEC-13a unchanged)
* contradiction preservation ✓ (D-FAULT-5b unchanged)
* transport independence ✓ (formalized via T5)
* reopen-stage replay identity ✓ (Step 10 Direction A Phase 6 unchanged)
* no hidden cleanup ✓
* no wall-clock authority ✓ (formalized via D9 + multiple clauses)
* no adaptive semantics ✓

All preserved verbatim.

---

**End of Step 11 closure-verification analysis.**

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [Step 11 admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED analysis](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance analysis](phase_4b_step11_f59_manual_advance_analysis.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).
