# Phase 4B Step 11 — Constitutional Extraction Plan (Pre-Authoring Mechanics)

**Status: PRE-AUTHORING EXTRACTION-MECHANICS PLAN (2026-05-21).** Designs the *mechanics* of converting the closed Step 11 framework into additive-only normative contract deltas. Does not author clause wording, does not mutate the contract, does not propose changes to *what* gets codified (per `phase_4b_step11_codification_plan.md`) — only to *how* the codification is performed safely.

---

## §1. Extraction unit catalog

Six unit types totaling 38 atomic insertions:

| unit | count | mechanic |
|---|---|---|
| Glossary entry | 5 | append to §0 |
| C-2 embedded note | 4 | append subsection within home section |
| C-1 promoted clause (existing family) | 6 | insert new clause-ID with anchor citations |
| New section §14 D-INGRESS | 1 section + 9 clauses + scope + restatement | append top-level §14 |
| D-FAULT-15 row | 12 | append rows 31–42 |
| §11 open-extension closure | 1 | mark item 1 CLOSED |

---

## §2. Dependency DAG

Within Step 11 new clauses:

**Layer 0 (no Step-11 dependencies):** D-FAULT-6b, D-FAULT-6c, D-SCHED-14, D-REPLAY-10, D-INGRESS-1, D-INGRESS-3, D-INGRESS-4, D-INGRESS-5, D-INGRESS-6, D-INGRESS-7, D-INGRESS-8, D-INGRESS-9.

**Layer 1 (cites one Step-11 clause):** D-INGRESS-2 (→ D-FAULT-6c).

**Layer 2 (cites multiple Step-11 clauses):** D-FAULT-9b (→ D-FAULT-6c, D-INGRESS-9), D-FAULT-9c (→ D-SCHED-14).

D-FAULT-15 rows, glossary, and embedded notes are dependency-free.

---

## §3. Six-wave extraction order

| wave | content | dependencies |
|---|---|---|
| **1** | D-FAULT-6b, D-FAULT-6c, D-SCHED-14, D-REPLAY-10 | existing clauses only |
| **2** | §14 D-INGRESS (scope + D-INGRESS-1..9 + restatement) | Wave 1's D-FAULT-6c (cited by D-INGRESS-2) |
| **3** | D-FAULT-9b, D-FAULT-9c | Wave 1 + Wave 2 |
| **4** | D-FAULT-15 rows 31–42 | various existing + new (per row) |
| **5** | §0 glossary entries + §11 closure of item 1 | reference Waves 1–4 |
| **6** | C-2 embedded notes T1, T4, T5, T8 | none |

**Sub-finding 3.A.** All citation chains satisfied at the moment of each wave's insertion.

**Codification-plan refinement.** The codification plan's Phase 2 lists all T-promotions as a single phase; this extraction plan splits T-promotions into Wave 1 (D-FAULT-6b/6c, D-SCHED-14, D-REPLAY-10) and Wave 3 (D-FAULT-9b/9c) with Wave 2 (§14 D-INGRESS) between them. Codification Phase 3 (§14) is promoted to Wave 2.

---

## §4. Citation-chain construction rules

### §4.1 Two citation modes

* **Anchor citations.** Normative dependencies. X cites Y as load-bearing premise.
* **Reference citations.** Navigational "see also." X cites Y for context; X's content is self-standing.

### §4.2 Per-promoted-clause citation classification

| new clause | anchor citations | reference citations | depth |
|---|---|---|---|
| D-FAULT-6b (T2) | D-FAULT-6, D-EXEC-13a, D-EXEC-13c, D-FAULT-15 #27, T1 (note) | D-FAULT-15 #5 | 0 |
| D-FAULT-6c (T3) | D-EXEC-1, D-EXEC-2, D-FAULT-6, T1 (note) | D-FAULT-15 row 32 | 0 |
| D-FAULT-9b (T6) | D-FAULT-6c, D-INGRESS-9, D-FAULT-6a, D-FAULT-2, D-FAULT-9 | D-FAULT-15 #18, D-FAULT-7 | 1 |
| D-FAULT-9c (T7) | D-SCHED-14, D-FAULT-2, D-FAULT-9a | D-FAULT-15 #16, D-SCHED-1, D-SCHED-12, D-EXEC-13c, D-SESS-6 | 1 |
| D-SCHED-14 (T9) | D-SCHED-1, D-SCHED-12, D-SESS-6, D-EXEC-13c | — | 0 |
| D-REPLAY-10 (R1) | D-REPLAY-1, D-REPLAY-2, D-TRACE-2, D-FAULT-9 | L4 framework label | 0 |

**Sub-finding 4.2.A.** All citation chains have depth ≤ 1. No recursive citation hazard.

### §4.3 T7-cites-T9 resolution

D-FAULT-9c (T7) cites D-SCHED-14 (T9) as anchor. D-SCHED-14 cites only existing clauses. The citation graph is a DAG (D-FAULT-9c → D-SCHED-14 → existing). No normative recursion.

### §4.4 Citation-classification standard

Each promoted clause body MUST distinguish anchor from reference citations explicitly. Framework documents (analyses, F58, F59, this plan, etc.) MAY be cited only in non-normative *Note* sections as navigational aids — never as anchor citations.

---

## §5. Framework/contract separation rules

### §5.1 What stays framework-only

* L1–L4 lemmas (with L5 folded into L2).
* 65 finding classifications.
* Eight threat models + Mitigation Theorem M.
* Three candidate ingress shapes (Framework §O).
* F58/F59 derivation chains.
* Closure-verification reasoning.
* Codification, extraction, audit documents.

### §5.2 What becomes contract

* 5 promoted theorems (T2, T3, T6, T7, T9).
* 9 disciplines D1–D9 → D-INGRESS-1..9.
* R1 → D-REPLAY-10.
* 12 D-FAULT-15 rows.
* 5 glossary entries.
* 4 C-2 embedded notes (T1, T4, T5, T8).

### §5.3 Leakage prevention

Clause bodies MUST NOT include:
* Derivation chains as enforceable rules.
* Lemma names (L1–L4) as anchor citations.
* Threat-model numbers as anchor citations.
* Framework finding labels (F1–F65) as anchor citations.
* Analytical commentary or "borderline" qualifications.
* Implementation-suggestion language.

Clause bodies MAY include:
* Reference citations to framework documents in *Note* sections only.
* Cross-references to other clauses.
* The minimal enforceable rule.

---

## §6. Three-section clause-body template

Each promoted clause body uses three sections:

* **Section A — Rule.** Normative MUST/MUST NOT statement.
* **Section B — Citations.** Anchor + reference citations.
* **Section C — Note.** Optional non-normative explanation (mirrors existing contract's *Rationale* convention).

Section C is the only section where framework documents may be cited.

---

## §7. Minimal-enforceable-surface guideline

Each promoted clause states the *rule* in Section A:
* States the foreclosure (for forbidding clauses) or admittance (for admitting clauses).
* Cites anchors in Section B.
* Omits operational consequences (e.g., latency floors are derived; not enforceable).
* Omits implementation details (e.g., "structural skip" mechanism is implementation, not enforceable).

---

## §8. Hidden-semantic-widening risks

| clause | widening risk | mitigation |
|---|---|---|
| D-FAULT-6b | "next-tick observation" reading admits delayed mid-Phase-E observation | use foreclosure language; "cannot acquire," "is FORBIDDEN" |
| D-FAULT-6c | "sole observation surface" without qualification | qualify "ingress event observation," not "observation" generally |
| D-FAULT-9b | "PAUSED is admissible" without conditions | enumerate all 5 properties as conjunctive |
| D-FAULT-9c | naming only manual_advance | state general T7 rule + manual_advance as example |
| D-SCHED-14 | "input sets closed" without amendment-clause | state "without explicit clause amendment" |
| D-REPLAY-10 | "scheduled-injection is admitted" as mandatory | use permissive language ("MAY") |
| D-INGRESS-8 | "diagnostic metadata" expanding to authoritative | three sub-rules: on-event-not-envelope, not-read-by-orchestration, not-in-fingerprint |

**Sub-finding 8.A.** D-INGRESS-8 is the highest-widening-risk D-INGRESS clause. All other widening risks are mitigable via careful wording in the authoring phase.

---

## §9. Incremental safety per wave

| wave | replay guarantee | new clause coherence | inter-wave gap |
|---|---|---|---|
| 1 | unchanged | self-contained (existing-clause anchors) | none |
| 2 | unchanged | full §14 D-INGRESS coherent; D-INGRESS-2 cites Wave 1 | none |
| 3 | unchanged | D-FAULT-9b/9c cite Wave 1 + Wave 2 | none |
| 4 | unchanged | D-FAULT-15 rows independent | none |
| 5 | unchanged | glossary + closure independent | none |
| 6 | unchanged | C-2 embedded notes self-contained | none |

**Sub-finding 9.A.** The extraction is **monotonically restrictive**. No wave admits behavior that a later wave forbids.

---

## §10. Sequencing-induced asymmetries

| asymmetry | mitigation |
|---|---|
| Post-Wave-1: forward-protecting clauses (D-FAULT-6b, D-SCHED-14) without §14 context | PR description references upcoming Wave 2 |
| Post-Wave-2: PAUSED admissibility still undefined (D-FAULT-9b not yet) | PR description references upcoming Wave 3 |
| D-FAULT-9a (preserved) + D-FAULT-9c (override) relationship | D-FAULT-9c body explicitly states the override; D-FAULT-9a text unchanged |

**Sub-finding 10.A.** All asymmetries mitigable through PR-description notes and one explicit override-relationship statement in D-FAULT-9c. No structural problem.

---

## §11. Family-insertion mechanics

| family | growth | pattern |
|---|---|---|
| D-FAULT-6 | 2 → 4 (add 6b, 6c) | alphabetical-suffix |
| D-FAULT-9 | 2 → 4 (add 9b, 9c) | alphabetical-suffix |
| D-SCHED | -13 → -14 | sequential |
| D-REPLAY | -9 → -10 | sequential |
| D-INGRESS | new family, -1..-9 | new-family pattern |
| D-FAULT-15 rows | 30 → 42 | continuous row numbering |
| §0 glossary | 9 → 14 entries | append |

**Sub-finding 11.A.** All families grow cleanly. No ID renumbering. No family churn.

---

## §12. D-FAULT-9c override-relationship

D-FAULT-9a (existing) body still references `manual_advance` as Step 11 reserved. D-FAULT-9c (new, Wave 3) forecloses `manual_advance` per T7. D-FAULT-9a is NOT modified.

**D-FAULT-9c's body must explicitly state the override relationship** (per §9.4.A of preceding analysis): "D-FAULT-9c overrides D-FAULT-9a's manual_advance reservation; D-FAULT-9a's reservation language is preserved verbatim for historical citation continuity." This makes the override explicit without retroactive editing.

---

## §13. Five codification-plan refinements

1. **Phase 2 sub-phasing.** Codification Phase 2 splits into Wave 1 (independent T-promotions: D-FAULT-6b, D-FAULT-6c, D-SCHED-14, D-REPLAY-10) and Wave 3 (dependent T-promotions: D-FAULT-9b, D-FAULT-9c). Wave 2 (§14 D-INGRESS) intervenes.
2. **Phase 3 precedence.** Wave 2 (§14) must precede Wave 3 (D-FAULT-9b cites D-INGRESS-9).
3. **Citation-classification standard.** Each clause body distinguishes anchor vs reference citations.
4. **D-FAULT-9c override-relationship statement.** Explicit override statement preserves D-FAULT-9a verbatim.
5. **Three-section clause-body template.** (Rule / Citations / Note) structure isolates normative from explanatory content.

**Sub-finding 13.A.** Refinements are extraction-mechanics-level only. Codification plan's structural decisions are unchanged.

---

## §14. Extraction-planning verdict

**EXTRACTION PLAN: READY.**

* 38 atomic insertions across 6 waves.
* All citation chains depth ≤ 1.
* No recursive citation.
* No inter-wave citation gap.
* Monotonically restrictive replay guarantees.
* Framework/contract separation enforced via citation-classification standard.
* Three-section clause-body template isolates normative from explanatory.
* Minimal-enforceable-surface guideline prevents over-specification.
* Hidden-widening risks identified per clause with mitigations.
* Three sequencing asymmetries identified with mitigations.
* D-FAULT-9c override-relationship explicit; D-FAULT-9a preserved.

The plan does NOT mutate any existing artifact. The plan does NOT author any clause wording. The plan IS the sequencing + classification + safety overlay on the codification plan.

---

## §15. Preserved invariants

| invariant | preserved across all waves |
|---|---|
| replay-authoritative truth | ✓ (monotonically restrictive) |
| append-only causality | ✓ (no retroactive edits) |
| authority singularity | ✓ (no new authorities) |
| orchestration_tick supremacy | ✓ (T1 in Wave 6 embedding) |
| Phase-A-only observability | ✓ (D-FAULT-6c Wave 1) |
| deterministic interruption boundaries | ✓ (D-FAULT-6b Wave 1) |
| Phase E atomicity | ✓ (D-FAULT-6a unchanged) |
| contradiction preservation | ✓ (D-FAULT-5b unchanged) |
| transport independence | ✓ (T5 in Wave 6 embedding) |
| reopen-stage replay identity | ✓ (unchanged) |
| no hidden cleanup | ✓ |
| no wall-clock authority | ✓ (D-INGRESS-9 Wave 2 + D-FAULT-15 row 38 Wave 4) |
| no adaptive semantics | ✓ |

All preserved verbatim across all six waves.

---

**End of Step 11 extraction plan.**

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance](phase_4b_step11_f59_manual_advance_analysis.md), [closure verification](phase_4b_step11_closure_verification.md), [codification plan](phase_4b_step11_codification_plan.md), [meta-audit](phase_4b_step11_meta_audit.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).
