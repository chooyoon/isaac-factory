# AAU Wave 1 / AAU 2 — D-FAULT-6c Review Packet

**Filing status:** authored at AAU commit time per Layer C §19 schema. This is the Reviewer-prep packet that hands the AAU from Author (claude) to Reviewer (cap2) for adjudication.

**Adjudication state at AAU commit:** REVIEW-PENDING (Reviewer cap2 has not yet adjudicated; this packet is the handover).

---

## §A — AAU identification

| field | value |
|---|---|
| Wave | 1 |
| AAU sequence | 2 of 4 (FII dependency D-FAULT-6b → D-FAULT-6c; D-FAULT-6b APPROVED-AND-CLOSED at `2893114`) |
| Clause ID | **D-FAULT-6c** |
| Clause name | Phase-A-Only Ingress Observability |
| Mutation shape | FII (Family-Internal Insertion) |
| Source theorem | T3 (per `docs/phase_4b_step11_admissibility_framework.md` §B.3) |
| C-1/C-2 status | C-1 promoted (per codification plan §1 row 3) |
| Author | claude |
| Reviewer | cap2 |
| Layer-B-implementing-agent | claude |
| Decision-Owner | cap2 |

---

## §B — Mutation specification

### §B.1 — Insertion anchor (V1 + V2 record)

**Anchor (Edit `old_string`):** `### 13.7 D-FAULT-7 — Idempotent cancellation`

**V1 pre-mutation uniqueness:** ✓ PASS (anchor occurs exactly 1 time in pre-mutation contract at HEAD `2893114` with contract SHA `01376a00...`; `grep -c '### 13.7 D-FAULT-7 — Idempotent cancellation'` == 1).

**V2 adjudication:** **PROCEED-SUBSTANTIVE** per the Wave 1 AAU 1 (D-FAULT-6b) Decision-Owner-recorded precedent. The literal mechanization (`anchor not substring of new_string`) FAILs because Edit's insertion semantics require `old_string ⊆ new_string` for any insertion. The substantive intent (anchor's text preserved verbatim through mutation; mutation is locally additive; anchor's TEXT lies outside the region the AAU's mutation alters per Layer B §4.2 Check) IS satisfied — `old_string` appears verbatim within `new_string` at exactly one mutation locus (the tail of the new clause body).

Per Decision-Owner-recorded rationale (D-FAULT-6b precedent, applied here without re-litigation): "for insertion-class mutations, the preserved-anchor requirement is satisfied when `old_string` appears verbatim within `new_string` at exactly one mutation locus. Future T5 mechanization refinement may tighten the validator to model insertion semantics explicitly."

Forensic detail: `new_string` contains the new `#### 13.6.3 D-FAULT-6c` subsection + a blank line + the verbatim anchor (`### 13.7 D-FAULT-7 — Idempotent cancellation`). The anchor appears exactly once in `new_string` (at the tail). Post-mutation V13 confirmed the anchor still appears exactly once in the contract.

This adjudication does NOT silently bypass V2 — it records the V2 PROCEED-SUBSTANTIVE precedent established at D-FAULT-6b, applies it under identical Edit-tool insertion semantics, and preserves validator authority integrity by making the bypass-vs-substantive distinction explicit.

### §B.2 — Mutation diff

```
+#### 13.6.3 D-FAULT-6c — Phase-A-Only Ingress Observability
+
+**D-FAULT-6c** — Within a single `session.step(K)` invocation, the session's only observation surface for ingress events is **Phase A**. Sub-Phase pulled observation at Phases B, C, D, E, F, or G, and `pull-at-end-of-Phase-G` observation, are **FORBIDDEN**. Every ingress observation MUST correspond to exactly one (`session_id`, `orchestration_tick`) pair, with `orchestration_tick` value equal to `K` (the value the tick holds throughout the entire `session.step(K)` call).
+
+**Citations.**
+* Anchor: D-EXEC-1, D-EXEC-2, D-FAULT-6
+
+*Note.* This clause asserts framework Theorem T3 (Phase-A-Only Ingress Observability) per `docs/phase_4b_step11_admissibility_framework.md` §B.3. The framework's derivation hypotheses are D-EXEC-1 (7-phase order; no sub-phases), D-EXEC-2 (events out of phase forbidden), D-EXEC-13a (Phase E atomic), and D-FAULT-15 row 27 (mid-execute envelope drain forbidden); framework Theorem T1 (Tick Non-Commensurability) provides the wall-clock-to-orchestration-tick non-commensurability reasoning that underlies "`orchestration_tick` value at observation = `K`". T3 is normative-strengthening (making implicit D-EXEC-1 + D-EXEC-2 + D-FAULT-6 + D-EXEC-13a + D-FAULT-15 row 27 discipline explicit), not normative-additive — it forecloses the post-Phase-A pull, pre-Phase-E pull, and pre-Phase-G pull design temptations.
```

- 9 inserted lines
- 0 deleted lines
- A3 (diff-shape additive-only): ✓ satisfied
- Insertion point: between line 1139 (end of D-FAULT-6b Note) and line 1141 (start of `### 13.7 D-FAULT-7`)

### §B.3 — Citation classification (V4 record)

**Anchor citations** (constitutionally load-bearing; normative dependency):
- D-EXEC-1 (7-phase order; no sub-phases — foundation of T3's "no sub-Phase pulled observation" conclusion)
- D-EXEC-2 (events out of phase forbidden — foundation of T3's "observation MUST correspond to one (`session_id`, `orchestration_tick`) pair")
- D-FAULT-6 (operator abort enters at Phase A only — generalized by T3 to ALL ingress events)

**Reference citations** (navigational "see also"): **OMITTED at Wave 1.**

The extraction plan §4.2 lists "D-FAULT-15 row 32" as a reference citation for D-FAULT-6c. Row 32 is a Wave 4 insertion and does not exist in the contract at Wave 1. Per extraction plan §4.1, reference citations are non-normative navigation aids; omission has zero normative impact. The Author's choice to omit (rather than include a forward-citation that would FAIL V17/V19) preserves the V17 BLOCKING discipline (each cited clause-ID resolves in post-mutation contract) and the V19 end-of-Wave invariant (each cited clause-ID resolves at end-of-wave). The omission is identified for Reviewer awareness; no additional adjudication is requested at this AAU's review.

All cited clause-IDs in the Wave-1-authored body (D-EXEC-1, D-EXEC-2, D-FAULT-6, and the Note's D-EXEC-13a + D-FAULT-15 row 27) confirmed present in pre-mutation contract via V5 dry-run. V17 post-mutation confirmed all citations resolve (D-EXEC-1: 49, D-EXEC-2: 5, D-FAULT-6: 21, D-EXEC-13a: 9, D-FAULT-15 row 27: 3).

### §B.4 — Framework references (V9 confinement record)

Framework refs in this AAU body:
- `docs/phase_4b_step11_admissibility_framework.md` (framework filename) — Note section only ✓
- T3 (framework theorem label) — Note section only ✓
- T1 (framework theorem label) — Note section only ✓

V9 check: Rule section contains zero framework references; Citations section contains zero framework references; all framework refs confined to Note section.

---

## §C — Validator result matrix

### §C.1 — Pre-mutation (Stage 1–2)

| validator | classification | result | detail |
|---|---|---|---|
| V1 (anchor uniqueness pre) | BLOCKING | ✓ PASS | anchor occurs 1 time |
| V2 (anchor stability) | BLOCKING | PROCEED-SUBSTANTIVE adjudicated | per §B.1 record; D-FAULT-6b precedent applies |

### §C.2 — Pre-mutation body (Stage 3)

| validator | classification | result | detail |
|---|---|---|---|
| V3 (template presence) | BLOCKING | ✓ PASS | Rule + Citations + Note sections all present; MUST / FORBIDDEN normative keywords confirmed |
| V4 (citation classification) | BLOCKING | ✓ PASS | Anchor label present; Reference label intentionally absent (no Wave-1-resolvable reference citation; see §B.3) |
| V5 (anchor-cite existing) | BLOCKING | ✓ PASS | all anchor citation clause-IDs (D-EXEC-1, D-EXEC-2, D-FAULT-6) resolve in pre-mutation contract (defining headings at L50, L56, L1116/L1118 respectively) |
| V6 (minimal-enforceable-surface) | SOFT/MANUAL | **DEFERRED to Reviewer** | per `tools/step12_validators/v06_v20_manual_checklists.md` V6 checklist |
| V7 (hidden-widening D-FAULT-6c seed) | SOFT | ✓ PASS | no banned phrases ("sole observation surface" without qualification, "always", "any session" without "ingress" qualifier, etc.) found; extraction plan §6.A guardrail observed — "observation surface" is qualified as "for ingress events" |
| V8 (override-statement) | N/A | N/A | D-FAULT-9c only; not applicable to D-FAULT-6c |
| V9 (framework-ref confinement) | BLOCKING | ✓ PASS | framework refs (T1, T3, phase_4b_step11_admissibility_framework.md) in Note section only |
| V10 (D-FAULT-15 row format) | N/A | N/A | D-FAULT-15 row AAUs only; not applicable |

### §C.3 — Post-mutation (Stage 4)

| validator | classification | result | detail |
|---|---|---|---|
| V11 (Properties A1–A3) | BLOCKING | ✓ PASS | 9 insertions, 0 deletions; A3 satisfied (`git diff` shows 0 `-` content lines); A1 and A2 implied |
| V12 (Properties S1–S3) | N/A | N/A | SF AAU only |
| V13 (anchor uniqueness post) | BLOCKING | ✓ PASS | anchor (`### 13.7 D-FAULT-7 — Idempotent cancellation`) occurs 1 time post-mutation |
| V14 (existing-text byte preservation) | BLOCKING | ✓ PASS | implied by V11 A3 |
| V15 (heading-DAG structure) | BLOCKING | ✓ SUBSTANTIVE PASS per S4 §S4-V15-finding | 3 pre-existing skips detected at lines 11, 832, 1106 (identical to pre-mutation set; ALL pre-existing; AAU introduces ZERO new level skips — insertion at `####` between sibling `####` and parent `###` introduces no level jump) |
| V16 (new clause-ID uniqueness) | BLOCKING | ✓ PASS | D-FAULT-6c definition count = 1; heading-level D-FAULT-6c count = 1 |
| V17 (cross-reference resolvability) | BLOCKING | ✓ PASS | all cited clause-IDs (D-EXEC-1, D-EXEC-2, D-FAULT-6, D-EXEC-13a, D-FAULT-15 row 27) resolve in post-mutation contract; framework doc (80273 bytes) exists at cited path |

### §C.4 — FII §8.3 overlay

| check | result |
|---|---|
| next family heading `### 13.7 D-FAULT-7 — Idempotent cancellation` unchanged | ✓ PASS (verbatim preserved in post-mutation contract; V13 confirms 1 occurrence) |
| preceding family heading `#### 13.6.2 D-FAULT-6b — N-Interior-Phase-E Ingress Cannot Acquire In-Tick Authority` unchanged | ✓ PASS (D-FAULT-6b clause body byte-preserved; verified via A3 / V14) |
| D-FAULT-9b future anchor pre-derived from D-FAULT-6c's post-state | INFORMATIONAL — D-FAULT-9b is Wave 3 AAU; D-FAULT-6c's APPROVE is a prerequisite per extraction plan §4.2 depth-1 citation chain |

### §C.5 — V18 sanity check (informational; not required for AAU 2 of Wave 1)

| check | result |
|---|---|
| V18 replay-test invariant against existing SessionPackages | ✓ PASS — runtime substrate unchanged from D-FAULT-6b commit `b7de4cd` (D-FAULT-6c is documentation-only contract mutation; zero runtime files touched); the V18 invariant (events SHA-256 byte-identical across cycles) is preserved by construction |

V18 is per Layer B §7.1 + Layer D cadence — typically end-of-wave (after Wave 1 AAU 4). Pre-AAU sanity check confirms substrate unchanged; substrate runtime unchanged (D-FAULT-6c is documentation-only).

### §C.6 — FF5 substrate preservation

| check | result |
|---|---|
| FF5 substrate preservation | ✓ PASS — current contract SHA `60f515a47d00a209f240c84387a3e8d5761be5420bacffa00da0870ca032168b` differs from prior `01376a00...` (mutations applied as expected); 0 pre-Step-12 clause-IDs removed; 0 existing-clause text modified |

---

## §D — Reviewer adjudication slots (cap2 fills in)

### §D.1 — V6 manual review

**Reviewer checklist (per `tools/step12_validators/v06_v20_manual_checklists.md` §V6):**

```
[ ] The Rule section states the foreclosure or admittance only.
[ ] The Rule section does NOT include operational consequences (e.g., specific latency floors).
[ ] The Rule section does NOT include implementation details.
[ ] The Rule section does NOT include derivation chains.
[ ] The Rule section does NOT include "borderline" or hedging qualifications.
[ ] The Rule section uses MUST / MUST NOT / FORBIDDEN / SHALL / MAY explicitly.
```

**Reviewer verdict (V6): _________** (PASS / FLAG-REVISE)
**Rationale: _________**

### §D.2 — V20 manual review

**Reviewer checklist (per V20):**

```
[ ] The new MUST does not contradict any existing MUST NOT for the same subject.
[ ] The new admittance does not contradict any existing foreclosure.
[ ] Any clause-pair tension is explicitly acknowledged.
[ ] The new clause's scope is consistent with the citation chain's transitive closure.
```

**Reviewer verdict (V20): _________** (PASS / FLAG-REVISE / ESCALATE)
**Rationale: _________**

### §D.3 — V7 SOFT-flag adjudication (if any)

V7 returned 0 banned phrases. No SOFT flag raised. Reviewer adjudication: N/A.

### §D.4 — Layer C 3-option verdict

**Reviewer verdict: _________** (APPROVE / REVISE / ESCALATE)

**APPROVE-AS-IS rationale (if APPROVE):** MUST cite framework/precedent/scope-limit per Layer C §17 (never intuition).

**REVISE rationale (if REVISE):** specify what needs revision.

**ESCALATE rationale (if ESCALATE):** specify which trigger (T3 / T8); Constitutional Reviewer convening required per Layer D §8.1.

### §D.5 — Reference-citation deferral acknowledgement

The Author has omitted the extraction-plan-listed reference citation "D-FAULT-15 row 32" from this AAU's body (per §B.3 record). Reference citations are non-normative (extraction plan §4.1). The Reviewer is asked to confirm that this omission is constitutionally acceptable for Wave 1 (it does NOT silently widen the clause's normative content; it preserves V17/V19 BLOCKING discipline).

**Reviewer acknowledgement (D.5): _________** (ACCEPTED-DEFERRED / DISAGREE)
**If DISAGREE:** identify the remediation path (e.g., cite section-level "D-FAULT-15" without row number; or defer the entire clause to a later wave).

---

## §E — Reviewer-prep ergonomics aids

### §E.1 — Reading order

1. §A AAU identification — what this AAU IS
2. §B.2 mutation diff — the actual clause text
3. §B.3 + §B.4 citation classification + framework refs — why citations resolve
4. §C validator result matrix — what mechanical checks have passed
5. §D adjudication slots — what cap2 fills in (including §D.5 reference-citation deferral)
6. (Reference) `docs/phase_4b_step11_admissibility_framework.md` §B.3 — full T3 derivation
7. (Reference) `docs/phase_4b_step11_extraction_plan.md` §4.2 — citation rules
8. (Reference) `docs/phase_4b_step11_codification_plan.md` §10 — clause body skeleton expected
9. (Reference) `docs/step12_audit_traces/aau_wave1_01_d_fault_6b_review_packet.md` §B.1 — V2 PROCEED-SUBSTANTIVE precedent invoked here

### §E.2 — Key questions for Reviewer

- Does the Rule section state the Phase-A-only foreclosure narrowly? (V6 check)
- Is the "observation surface for ingress events" qualification correctly scoped (does NOT widen to "observation" generally)? (extraction plan §6.A guardrail)
- Do citations resolve in the correct sense — anchor citations are load-bearing, reference citations are see-also? (V4 check passed mechanically; V20 check confirms semantic correctness)
- Does the Note section's T1/T3 explanation match the analytical framework? (cross-check vs `docs/phase_4b_step11_admissibility_framework.md` §B.3)
- Does the clause's normative-strengthening claim ("not normative-additive") accurately reflect that D-EXEC-1 + D-EXEC-2 + D-FAULT-6 + D-EXEC-13a + D-FAULT-15 row 27 already imply this clause?
- Is the reference-citation deferral (§B.3, §D.5) constitutionally acceptable for Wave 1?
- Is the `(`session_id`, `orchestration_tick`)` pair language consistent with §1 D-SESS semantics?

### §E.3 — Wave 1 dependency note

D-FAULT-9b (Wave 3) cites D-FAULT-6c as anchor (per extraction plan §4.2). D-FAULT-6c's APPROVE verdict is a prerequisite for D-FAULT-9b authoring. If D-FAULT-6c is REVISE'd, D-FAULT-9b authoring waits.

D-INGRESS-2 (Wave 2) also cites D-FAULT-6c. Wave 2 cannot begin until Wave 1 closes with all four AAUs APPROVED.

### §E.4 — Wave 1 precedents invoked

This AAU invokes the following Wave 1 precedents established at D-FAULT-6b:

1. **V2 PROCEED-SUBSTANTIVE** — same Edit-tool insertion semantics; same substantive intent satisfaction; not a silent bypass.
2. **V15 SUBSTANTIVE PASS per S4 §S4-V15-finding** — same 3 pre-existing skips at lines 11, 832, 1106; AAU introduces ZERO new skips.
3. **Wall-clock-as-descriptive precedent** — Note section references "wall-clock-to-orchestration-tick non-commensurability" only as analytical framework context (T1 reasoning), NOT as orchestration authority quantum; `orchestration_tick` remains authority quantum; D-SCHED-11 preserved.

---

## §F — Audit metadata

- AAU commit author: claude (per Layer A §15 8-stage protocol; Wave 1 Y2 multiplexing per S5 role activation)
- AAU commit timestamp: 2026-05-21 (descriptive only; wall-clock is non-authoritative per D-SCHED-11)
- Pre-mutation contract SHA-256: `01376a00832a59a2280496e2a5e663100f2e77dc2d7f0b8804977cedad6dad0d` (HEAD `2893114`, post-D-FAULT-6b state)
- Post-mutation contract SHA-256: `60f515a47d00a209f240c84387a3e8d5761be5420bacffa00da0870ca032168b`
- Substrate impact: +9 lines (documentation-only); 0 runtime mutation; 0 replay-baseline mutation; 0 validator-infrastructure mutation; 0 governance mutation
- Master HEAD: UNCHANGED at `6daf9b2c24edef63e81a832727eb191726f69afb`
- Branch HEAD prior to this AAU: `289311460c2890f06b05ff837b6ddd2cd60c736c`

---

**End of D-FAULT-6c Wave 1 AAU 2 review packet (Reviewer-prep state).**

Reviewer cap2 fills §D.1, §D.2, §D.4, §D.5. On APPROVE: AAU 2 closes; D-SCHED-14 (Wave 1 AAU 3) becomes admissible. On REVISE: Author claude revises; re-commits via git revert + re-author (no amend per Layer A §16; no rebase / no force-push per Layer D §10 + BRANCH-LINEARITY). On ESCALATE: T3/T8 path per Layer D §8.1; Constitutional Reviewer convening triggered.
