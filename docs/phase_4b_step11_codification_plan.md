# Phase 4B Step 11 — Codification Planning (Pre-Contract Architecture)

**Status: PRE-CONTRACT CODIFICATION ARCHITECTURE PLANNING (2026-05-21).** This document plans the structural integration of the Step 11 framework (T1–T9, L1–L4 with R1, D1–D9, D-FAULT-15 rows #31–#42, 6-object ontology) into the existing [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md) contract document for a future Step 11 contract-authoring phase.

**No clause text is authored.** No contract document is mutated. No implementation is proposed. The deliverable is the codification topology — where each framework element would live, what clause-ID it would receive, and how to preserve additive-only extension at all levels.

---

## §1. Two-tier theorem codification

Five framework theorems warrant promotion to normative clauses (**C-1**); four are best codified as embedded explanatory notes within existing sections (**C-2**):

| theorem | treatment | placement | clause-ID |
|---|---|---|---|
| T1 Tick Non-Commensurability | C-2 embedded | §1 D-EXEC | — |
| T2 N2-only-Interruption Impossibility | C-1 promoted | §13 D-FAULT | **D-FAULT-6b** |
| T3 Phase-A-Only Ingress Observability | C-1 promoted | §13 D-FAULT | **D-FAULT-6c** |
| T4 Acquisition-Visibility Tick Alignment | C-2 embedded | §3 D-BUS or §13.2 | — |
| T5 Transport-Independence | C-2 embedded | §4 D-REPLAY | — |
| T6 PAUSED Constitutional Admissibility | C-1 promoted | §13 D-FAULT (alongside D-FAULT-9a) | **D-FAULT-9b** |
| T7 Manual-Advance Constitutional Incompatibility | C-1 promoted | §13 D-FAULT (alongside D-FAULT-9a) | **D-FAULT-9c** |
| T8 Authority Singularity | C-2 embedded | §5 D-SESS | — |
| T9 Orchestration-Decision Input Whitelist Closure | C-1 promoted | §2 D-SCHED | **D-SCHED-14** |

**Rationale.** Premise-source theorems that are derivable-but-non-redundant are best embedded as explanatory subsections. They provide citation surfaces in the framework and analysis documents but do not need normative-clause status in the contract because the underlying clauses already enforce them. Foreclosure and load-bearing-novel theorems warrant promotion because future PR reviewers cite them as rejection criteria.

**Inflation control.** Embedding T1/T4/T5/T8 saves 4 clauses of contract-surface inflation while preserving all citation needs.

---

## §2. New §14 D-INGRESS section

The nine disciplines D1–D9 are placed in a new top-level section **§14 Live Ingress Admissibility Contract (D-INGRESS)**:

```
§14.1   Scope
§14.2   D-INGRESS-1 Channel Opacity
§14.3   D-INGRESS-2 Phase-A-Only Pull
§14.4   D-INGRESS-3 Strict Atomic Snapshot
§14.5   D-INGRESS-4 Canonical-Order Discipline
§14.6   D-INGRESS-5 Pull-Only Direction
§14.7   D-INGRESS-6 Predicate Closure Stability
§14.8   D-INGRESS-7 Per-Session Channel Lifecycle
§14.9   D-INGRESS-8 Diagnostic Boundary
§14.10  D-INGRESS-9 Caller-Driven PAUSED Cadence
§14.11  Step 11 scope restatement
```

**Structural mirror.** §14 mirrors §12 (D-CONT) and §13 (D-FAULT) patterns. Scope and restatement bracket the discipline subsections.

**Why a new section.** Distributed embedding (placing each Di under §1, §2, §3, §5, §6, §13) would fragment the ingress contract across six sections. Subsection of D-FAULT (D-FAULT-INGRESS-N) miscategorizes ingress as a failure family. A new top-level §14 is the cleanest topical home and preserves all existing numbering.

---

## §3. D-FAULT-15 row-extension strategy

The framework proposes rows #31–#43. After codification:

* Rows **31–42** added to the existing D-FAULT-15 table (continuing the sequence from row 30 added at Step 10 Direction A).
* Row **43** (the T7-related row) is **OMITTED** from the table. Its foreclosure is covered by the promoted D-FAULT-9c clause; duplicating it in D-FAULT-15 would be two citation surfaces for one foreclosure.

**Presentation.** Continuous table (no sub-grouping by phase). Row 30 is the last Step-10 row; row 31 is the first Step-11 row. The table reads as a single forbidden-pattern enumeration.

**Citation discipline.** Tests and reviews continue to cite "D-FAULT-15 row N" with N now in range 1–42.

---

## §4. R1 (scheduled-injection) placement

Refinement R1 to Lemma L4 is codified as a new clause in §4 D-REPLAY:

* **D-REPLAY-10 Scheduled-Injection Replay Primitive.**

Rationale: R1 is a *replay-tool* primitive (how the comparator reconstructs envelope drain ticks from the trace), not a substrate-runtime discipline. It belongs alongside the existing layered-identity clauses (D-REPLAY-1 through D-REPLAY-9), not inside §14 D-INGRESS.

The §14 D-INGRESS section cites D-REPLAY-10 by reference where appropriate.

---

## §5. Glossary integration (§0 expansion)

Five new entries appended to §0:

| entry | one-line definition |
|---|---|
| OperatorEnvelope | "Frozen dataclass per D-FAULT-9; sole orchestration ingress unit; content-addressed envelope_id." |
| Channel | "Per-session passive store of OperatorEnvelopes pushed by transport; observed only by session at Phase A pull (D-INGRESS-1, D-INGRESS-2)." |
| Pull | "Atomic snapshot operation at start of Phase A by which the session captures the channel's current buffer (D-INGRESS-2, D-INGRESS-3)." |
| Drain Epoch | "The (session_id, orchestration_tick) pair at which a Phase A drain processed an envelope. Authoritative-observation primitive (T3, L1)." |
| Ingress Observation Event | "Trace-recorded `OperatorAbortRequested` / `OperatorPauseRequested` / `OperatorResumeRequested` event; the visible authoritative record of an envelope's drain epoch." |

**Buffer** is NOT added to glossary; it is an implementation-detail of Channel, mentioned only within D-INGRESS-3's clause body.

**Glossary growth:** 9 entries → 14 entries. Existing entries remain in current order; new entries appended.

---

## §6. D-FAULT-9a preservation

F59 recommends retiring `manual_advance` from D-FAULT-9a's reserved set, but D-FAULT-9a's clause text is **NOT** modified. Instead, the new D-FAULT-9c clause (T7 promotion) explicitly forecloses `manual_advance` as inadmissible. D-FAULT-9a's existing reservation language becomes a historical reference that D-FAULT-9c overrides.

**Rationale.** Preserving D-FAULT-9a's text verbatim maintains backward citation stability. Tests and analyses citing D-FAULT-9a continue to resolve. The override pattern is constitutionally clean: a later clause supersedes an earlier reservation.

D-FAULT-9a's body could optionally be extended (additively) to mention `pause`/`resume` as admitted kinds per D-FAULT-9b, but this is not strictly required — D-FAULT-9b's body covers the admission.

---

## §7. Open-extensions §11 update

§11 of the contract document currently lists four open extensions. Row 1 ("`OperatorOverride` event commutativity") was reserved for Step 11. After codification, this row is marked CLOSED with reference to L3 (Canonical-Order Commutativity) and the D-INGRESS-4 (canonical-order discipline) clause.

The other three open-extension items remain.

---

## §8. Aggregate codification delta

| section | additions | new clause-IDs |
|---|---|---|
| §0 Glossary | 5 new entries | — |
| §1 D-EXEC | embedded T1 note | — |
| §2 D-SCHED | T9 promotion | **D-SCHED-14** |
| §3 D-BUS | embedded T4 note (or §13.2) | — |
| §4 D-REPLAY | R1 promotion, embedded T5 note | **D-REPLAY-10** |
| §5 D-SESS | embedded T8 note | — |
| §6 D-TRACE | (none) | — |
| §7 D-LIFE | (none) | — |
| §8 D-FORBID | (none) | — |
| §9 D-SCALE | (none) | — |
| §10 Conformance | (none) | — |
| §11 Open extensions | row 1 marked CLOSED | — |
| §12 D-CONT | (none) | — |
| §13 D-FAULT | T2, T3, T6, T7 promotions; D-FAULT-15 rows 31–42 | **D-FAULT-6b, D-FAULT-6c, D-FAULT-9b, D-FAULT-9c** |
| §14 D-INGRESS (NEW) | D-INGRESS-1 through D-INGRESS-9 + scope + restatement | **D-INGRESS-1 through D-INGRESS-9** |

**Totals.** 1 new top-level section; 6 new clauses in existing sections (D-SCHED-14, D-REPLAY-10, D-FAULT-6b, D-FAULT-6c, D-FAULT-9b, D-FAULT-9c); 9 new clauses in §14 (D-INGRESS-1 through -9); 12 new D-FAULT-15 rows; 5 new glossary entries; 4 embedded explanatory notes (T1, T4, T5, T8).

**Migration impact:** ZERO existing clauses modified; ZERO existing IDs renumbered; ZERO existing sections shifted; ALL existing citations remain valid.

---

## §9. Six-phase contract-authoring order

If a future session pursues the contract phase, the recommended order:

1. **Glossary + scope.** Add 5 glossary entries to §0; optional brief Step 11 scope note.
2. **T-promotions in existing sections.** Add D-FAULT-6b (T2), D-FAULT-6c (T3), D-FAULT-9b (T6), D-FAULT-9c (T7), D-SCHED-14 (T9), D-REPLAY-10 (R1).
3. **New section §14 D-INGRESS.** Author D-INGRESS-1 through D-INGRESS-9 + §14.1 scope + §14.11 restatement.
4. **D-FAULT-15 row extensions.** Add rows 31–42 to D-FAULT-15.
5. **Embedded theorem notes.** Add T1, T4, T5, T8 as embedded explanatory subsections within their home sections.
6. **Open-extensions update.** Mark §11 row 1 CLOSED with L3 reference.

Each phase is independently reviewable. No phase modifies existing clauses. Phases 1, 2, 5 are smallest; Phase 3 is largest.

---

## §10. Hidden semantic-widening control

Each promoted clause's body explicitly cites the framework as the authoritative derivation reference. Example body skeleton:

> D-FAULT-6b — N2-only-Interruption Impossibility. [Narrow statement.] Per Framework Theorem T2 (see `docs/phase_4b_step11_admissibility_framework.md` §B); derivation cites D-FAULT-6, D-EXEC-13a, D-EXEC-13c, D-FAULT-15 #27.

This pattern keeps clause text minimal and the framework document as the analytical record. The contract enforces; the framework explains. Each promoted theorem must use this pattern to resist the temptation to "improve" wording during codification.

---

## §11. What this plan does not decide

* Exact wording of any clause body — left to contract-phase authoring.
* Whether to author the contract phase at all — separate decision.
* Timing of the contract phase — separate decision.
* Any implementation following the contract phase — separate decision.
* Resolution of any open finding F60–F65 — separate analytical passes.

What the plan DOES decide (analytically):

* Placement strategy for each framework element.
* C-1 vs C-2 treatment for each theorem.
* Discipline namespace: new §14 D-INGRESS.
* Row-extension strategy for D-FAULT-15: continuous numbering 31–42, row 43 omitted.
* Glossary-integration strategy: 5 entries appended.
* Migration-minimization: no existing clause modification.
* Section-level placement plan.
* Contract-phase ordering plan.

---

## §12. Preserved invariants under codification

| invariant | codification mechanism |
|---|---|
| replay-authoritative truth | preserved (no clause modification) |
| append-only causality | preserved |
| authority singularity | T8 embedding |
| orchestration_tick supremacy | T1 embedding |
| Phase-A-only observability | D-FAULT-6c (T3 promoted) |
| deterministic interruption boundaries | D-FAULT-6b (T2 promoted) |
| Phase E atomicity | D-FAULT-6a preserved verbatim |
| contradiction preservation | D-FAULT-5b preserved verbatim |
| transport independence | T5 embedding |
| reopen-stage replay identity | Step 10 Direction A Phase 6 preserved verbatim |
| no hidden cleanup | D-FAULT-15 #1 preserved verbatim |
| no wall-clock authority | D-INGRESS-9 (D9 promoted) + D-FAULT-15 row 38 |
| no adaptive semantics | D-FAULT-15 #2/#8/#15 preserved verbatim |

All preserved. None weakened, none widened.

---

## §13. Codification-planning verdict

**Codification plan: READY.**

* Additive-only constitutional extension preserved at all levels (section, clause, row, glossary, citation).
* Backward citation stability preserved (no renumbering, no relocation).
* Promotion-worthy theorems distinguished from embedded-derivation theorems (inflation bounded).
* Live-ingress disciplines coherent in new §14 D-INGRESS (not fragmented).
* 6-object ontology integrated as glossary-level only (no clause-level over-specification).
* R1 placed as single D-REPLAY-10 clause (replay-tool primitive).
* D-FAULT-15 row numbering continued (31–42).
* Roughly 80% of analysis content remains framework-only (framework-vs-contract separation preserved).
* Six-phase ordering for contract phase allows incremental review.

No clause text authored. No contract mutated. No implementation proposed. The plan is analytical-only; the contract-phase decision remains a future session.

---

**End of Step 11 codification-planning analysis.**

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [Step 11 admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED analysis](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance analysis](phase_4b_step11_f59_manual_advance_analysis.md), [Step 11 closure verification](phase_4b_step11_closure_verification.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).
