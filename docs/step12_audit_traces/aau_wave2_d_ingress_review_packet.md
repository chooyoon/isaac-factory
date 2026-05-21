# AAU Wave 2 — §14 D-INGRESS Review Packet

**Filing status:** authored at AAU commit time per Layer C §19 schema. This is the Reviewer-prep packet that hands the AAU from Author (claude) to Reviewer (cap2) for adjudication.

**Adjudication state at AAU commit:** REVIEW-PENDING (Reviewer cap2 has not yet adjudicated; this packet is the handover).

---

## §A — AAU identification

| field | value |
|---|---|
| Wave | 2 |
| AAU sequence | 1 of 1 (Wave 2 contains a SINGLE PTA AAU per codification plan §2 + extraction plan §3) |
| Section | **§14 Live Ingress Admissibility Contract  *(D-INGRESS)*** |
| Clauses | D-INGRESS-1, D-INGRESS-2, D-INGRESS-3, D-INGRESS-4, D-INGRESS-5, D-INGRESS-6, D-INGRESS-7, D-INGRESS-8, D-INGRESS-9 (9 clauses) + §14.1 Scope + §14.11 Step 11 scope restatement |
| Mutation shape | **PTA (Pure Tail Append)** — FIRST PTA-shape AAU of Step 12 |
| Source theorems / disciplines | Framework Disciplines D1–D9 (per `docs/phase_4b_step11_admissibility_framework.md` §G.1 for D1–D8; `docs/phase_4b_step11_f58_paused_analysis.md` §N.1 for D9) |
| C-1/C-2 status | C-1 promoted (per codification plan §2; framework Disciplines D1–D9 are all NORMATIVE-CANDIDATE per closure_verification §7) |
| Author | claude |
| Reviewer | cap2 |
| Layer-B-implementing-agent | claude |
| Decision-Owner | cap2 |

---

## §B — Mutation specification

### §B.1 — Insertion anchor (V1 + V2 record)

**Anchor (Edit `old_string`, multi-line):**

```
If Step 10 Direction A lands but any of these load-bearing assertions does not hold, Step 10 Direction A has not landed.

---

**End of deterministic-semantics contract.**
```

The multi-line anchor uniquely identifies the §13-to-end-matter boundary. The `**End of deterministic-semantics contract.**` string is itself unique (V13 PASS confirms 1 occurrence post-mutation).

**V1 pre-mutation uniqueness:** ✓ PASS (`End of deterministic-semantics contract.` occurs exactly 1 time in pre-mutation contract at HEAD `5d1c21c` with contract SHA `683e8654...`; `grep -c "End of deterministic-semantics contract."` == 1).

**V2 adjudication:** **PROCEED-SUBSTANTIVE** per the Wave 1 V2 shape-agnostic generalization precedent (#9, formalized at AAU 3 §C.3; confirmed at AAU 4 §C.3). **FIFTH invocation**; **FIRST under PTA shape**. The shape-agnostic generalization holds: Edit-tool insertion semantics (`old_string ⊆ new_string`) apply to all insertion-class shapes (FII / STA / PTA). The mechanization conditions for this AAU are identical to D-SCHED-14's (AAU 3) and D-REPLAY-10's (AAU 4) STA invocations: `old_string` appears verbatim within `new_string` at exactly one mutation locus (sandwich form: §13-final-sentence + new §14 content + `---` + end-matter); V13 confirms anchor uniqueness post-mutation; substantive intent satisfied.

Forensic detail: `new_string` contains the §13 final sentence verbatim, then the entire new §14 D-INGRESS section body (heading + scope + 9 clauses + restatement), then the `---` separator and `**End of deterministic-semantics contract.**` block verbatim. Both anchor-flanking blocks appear exactly once each in `new_string`. Post-mutation V13 confirmed the anchor still appears exactly once.

### §B.2 — Mutation diff overview

- 107 inserted lines (entire §14 section with heading + scope + 9 D-INGRESS clauses + restatement)
- 0 deleted lines
- A3 (diff-shape additive-only): ✓ satisfied
- Insertion point: between L1432 (last §13 content line) and L1434 (`---` separator before end-matter)
- Line-number impact: end-matter lines shift down by 107 (purely offset; no content modified)

### §B.3 — Pre-commit Stage-3-correction record (NEW disclosure)

**Stage 3 first-pass authoring contained 3 forward-citation defects detected at Stage 4 validator execution. Stage 3 was re-entered for working-tree correction BEFORE Stage 6 commit. The corrected mutation is what this AAU commits.**

**Detected defects (pre-correction):**

1. **D-INGRESS-9 Rule:** parenthetical "(admitted per D-FAULT-9b's PAUSED constitutional compatibility, Wave 3)" — forward citation to D-FAULT-9b (Wave 3 clause).
2. **D-INGRESS-9 Note:** sentence "The forward citation to D-FAULT-9b's PAUSED constitutional compatibility (Wave 3) is contextual scoping — D-INGRESS-9 binds the wall-clock-foreclosure surface within PAUSED regardless of whether D-FAULT-9b lands; ..." — forward citation to D-FAULT-9b.
3. **§14.11 restatement:** sentence "Subsequent waves of Step 12 codification cite §14 from §13 D-FAULT extensions (D-FAULT-9b/9c per Wave 3) and from D-FAULT-15 row extensions (rows 31–42 per Wave 4) ..." — forward references to D-FAULT-9b, D-FAULT-9c, and D-FAULT-15 rows 31–42 (all Wave 3+ insertions).

**Defect classification.** These citations were NOT in the extraction plan §4.2 row table for D-INGRESS-*. Per extraction plan §4.2 row 3, the dependency direction is D-FAULT-9b → D-INGRESS-9 (Wave 3 cites Wave 2), not the reverse. The forward citations were Stage-3-authoring errors introduced by the Author's misreading of the framework's PAUSED dependency chain.

**Correction performed.** Two surgical `Edit` operations to the working tree (pre-commit):
- Edit 1 (D-INGRESS-9): removed parenthetical; replaced with "D-INGRESS-9 applies conditionally on `PAUSED` being an admitted session state; when `PAUSED` is constitutionally admitted, this discipline becomes binding without modification of this clause." Note section: removed D-FAULT-9b discussion; replaced with "The substrate's wall-clock foreclosure (D-SCHED-11) is already in force pre-Step-12 and remains the controlling constitutional discipline for non-PAUSED contexts; D-INGRESS-9 extends the same foreclosure surface specifically into the PAUSED state."
- Edit 2 (§14.11 restatement): removed forward-wave clause/row references; replaced with "the specific cross-section citation graph is the next-wave authoring concern and is not pre-bound here."

**Constitutional rationale for the correction discipline:**
- Per Layer A §15 8-stage protocol: if Stage 4 BLOCKING validators detect a defect, the Author re-enters Stage 3 to correct the working-tree mutation BEFORE Stage 6 commit. This is NOT amend / rebase / force-push (which would mutate a landed commit); this is normal pre-commit working-tree correction.
- The corrected mutation is what Stage 6 commits. There is no "pre-correction" commit to revert; the correction happened in the working tree only.
- Per Layer A §16 no-amend: applied (no commit to amend, since no commit has landed).

**Disclosure status.** EXPLICIT in this §B.3 + AAU commit message + completion attestation. NOT silent. NOT hidden cleanup.

**New Wave-2 precedent candidate.** This is the FIRST documented invocation of pre-commit Stage-3-correction in Step 12. The pattern is constitutionally distinct from precedent #7 (Interrupted-Stage-6-recovery), which applies to post-Stage-6 commit interruption recovery. **The Reviewer's §D.7 adjudication establishes the Wave-2 precedent.**

### §B.4 — Citation classification (V4 record)

Per-clause anchor citations:

| clause | anchor citations | reference | framework refs (Note) |
|---|---|---|---|
| D-INGRESS-1 (D1 Channel Opacity) | D-FAULT-9, D-BUS-1 | — | D1, admissibility_framework.md §G.1 |
| D-INGRESS-3 (D3 Strict Atomic Snapshot) | D-FAULT-9, D-FAULT-6 | — | D3 |
| D-INGRESS-2 (D2 Phase-A-Only Pull) | D-FAULT-6, **D-FAULT-6c (Wave 1)**, D-EXEC-1 | — | D2, T3 alignment |
| D-INGRESS-4 (D4 Canonical-Order) | D-FAULT-9, D-SCHED-1 | — | D4 |
| D-INGRESS-5 (D5 Pull-Only Direction) | D-FAULT-9, D-BUS-2 | — | D5 |
| D-INGRESS-6 (D6 Predicate Closure) | D-EXEC-13c, D-EXEC-13d, D-FAULT-9 | — | D6 |
| D-INGRESS-7 (D7 Channel Lifecycle) | D-FAULT-9, D-CONT-1 | — | D7 |
| D-INGRESS-8 (D8 Diagnostic Boundary) | D-FAULT-9, D-SESS-5, D-FAULT-10, D-SCHED-11 | — | D8, three-sub-rule guardrail |
| D-INGRESS-9 (D9 PAUSED Cadence) | D-SCHED-11, D-FAULT-9, D-FAULT-9a | — | D9, f58_paused_analysis.md §N.1 |

**Only Wave-1-introduced citation:** D-INGRESS-2 → D-FAULT-6c (the single planned cross-wave anchor per extraction plan §3).

**Reference subsections:** NONE for any D-INGRESS clause. The framework Discipline labels (D1–D9) and framework-doc paths are all materialized in the Note sections per V9 confinement.

**Per-clause hidden-widening guardrails:**

- **D-INGRESS-8** (highest-widening-risk per extraction plan §6.A): three sub-rules (D-INGRESS-8a/b/c) jointly prevent diagnostic metadata from acquiring orchestration authority. Sub-rule 8a (on-event-not-envelope); sub-rule 8b (not-read-by-orchestration); sub-rule 8c (not-in-fingerprint). All three are explicit in the Rule.
- **D-INGRESS-9**: conditional-PAUSED scoping ("applies conditionally on `PAUSED` being an admitted session state") prevents the discipline from binding non-PAUSED behavior or pre-supposing the Wave-3 PAUSED admission.

All cited clause-IDs (D-FAULT-9, D-BUS-1, D-FAULT-6, D-FAULT-6c, D-EXEC-1, D-EXEC-13c, D-EXEC-13d, D-SESS-5, D-FAULT-10, D-SCHED-11, D-SCHED-1, D-BUS-2, D-FAULT-9a, D-CONT-1) confirmed present in pre-mutation contract via V5 dry-run. V17 post-mutation confirmed all citations resolve.

### §B.5 — Framework references (V9 confinement record)

Framework refs in this AAU body:
- `docs/phase_4b_step11_admissibility_framework.md` (cited by D-INGRESS-1/2/3/4/5/6/7/8 Notes) — Note section only ✓
- `docs/phase_4b_step11_f58_paused_analysis.md` (cited by D-INGRESS-9 Note + §14.11 restatement) — Note + restatement only; both are non-normative ✓
- `docs/phase_4b_step11_closure_verification.md` (cited by §14.11 restatement) — restatement only; non-normative ✓
- D1, D2, ..., D9 framework discipline labels — Note sections only ✓
- T3 framework theorem label (in D-INGRESS-2 Note for alignment with D-FAULT-6c) — Note section only ✓

V9 check: Rule sections of D-INGRESS-1..9 contain ZERO framework-doc references; Citations sections contain ZERO framework-doc references; all framework-doc paths confined to Note sections + §14.11 non-normative restatement.

### §B.6 — Post-correction forward-citation status

Post-correction grep verification at the corrected working-tree contract:
- D-FAULT-9b: 0 occurrences (forward citations removed)
- D-FAULT-9c: 0 occurrences (forward citations removed)
- D-FAULT-15 row 31 through row 42: 0 occurrences each (forward enumerations removed)

ZERO forward citations to Wave 3+ insertions remain. V17/V19 BLOCKING preserved by construction.

---

## §C — Validator result matrix (post-correction)

### §C.1 — Pre-mutation (Stage 1–2)

| validator | classification | result | detail |
|---|---|---|---|
| V1 (anchor uniqueness pre) | BLOCKING | ✓ PASS | "End of deterministic-semantics contract." occurs 1 time |
| V2 (anchor stability) | BLOCKING | PROCEED-SUBSTANTIVE | 5th invocation; 1st under PTA; per §B.1 record; shape-agnostic precedent applies |

### §C.2 — Pre-mutation body (Stage 3, post-correction)

| validator | classification | result | detail |
|---|---|---|---|
| V3 (template presence) | BLOCKING | ✓ PASS | each D-INGRESS clause has Rule + Citations + Note; MUST/MUST NOT/MAY normative keywords confirmed |
| V4 (citation classification) | BLOCKING | ✓ PASS | Anchor labeled in each clause; Reference labels intentionally absent (no extraction-plan-listed references for any D-INGRESS clause) |
| V5 (anchor-cite existing) | BLOCKING | ✓ PASS | all anchor citation clause-IDs resolve in pre-mutation contract |
| V6 (minimal-enforceable-surface) | SOFT/MANUAL | **DEFERRED to Reviewer** | per `tools/step12_validators/v06_v20_manual_checklists.md` V6 checklist |
| V7 (hidden-widening D-INGRESS seed) | SOFT | ✓ PASS | extraction plan §6.A D-INGRESS-8 three-sub-rule guardrail observed; no banned phrases |
| V8 (override-statement) | N/A | N/A | D-FAULT-9c only |
| V9 (framework-ref confinement) | BLOCKING | ✓ PASS | framework refs in Note sections + §14.11 non-normative restatement only; ZERO framework refs in Rule or Citations sections |
| V10 (D-FAULT-15 row format) | N/A | N/A | D-FAULT-15 row AAUs only |

### §C.3 — Post-mutation (Stage 4, post-correction)

| validator | classification | result | detail |
|---|---|---|---|
| V11 (Properties A1–A3) | BLOCKING | ✓ PASS | 107 insertions, 0 deletions; A3 satisfied |
| V12 (Properties S1–S3) | N/A | N/A | PTA shape, not SF |
| V13 (PTA post-flight) | BLOCKING | ✓ PASS | §14 heading = 1 occurrence; §15 = 0 occurrences (no §15 emerges); end-of-doc end-matter byte-preserved |
| V14 (existing-text byte preservation) | BLOCKING | ✓ PASS | D-FAULT-6b body SHA `ae9a500e…` identical pre/post AAU; D-FAULT-6c body SHA `6d27d9ce…` identical; D-SCHED-14 body SHA `afd82de5…` identical; D-REPLAY-10 body SHA `deec8fa6…` identical; pre-Step-12 sample clauses preserved; end-matter line preserved verbatim |
| V15 (heading-DAG structure) | BLOCKING | ✓ SUBSTANTIVE PASS per S4 §S4-V15-finding (5th invocation) | 3 pre-existing skips at lines 11, 859, 1133 (unchanged from Wave 1 close); AAU introduces ZERO new level skips — §14 insertion at `##` level 2 between sibling `##` level 2 (§13) and end-matter; D-INGRESS-1..9 at `###` level 3 within §14 |
| V16 (new clause-ID uniqueness) | BLOCKING | ✓ PASS | D-INGRESS-1 through D-INGRESS-9 each = 1 definition |
| V17 (cross-reference resolvability) | BLOCKING | ✓ PASS | all cited clause-IDs resolve in post-mutation contract; ZERO forward citations to Wave 3+ clauses; framework docs exist at cited paths (admissibility_framework 80273B; f58_paused_analysis 77531B; closure_verification 16031B) |

### §C.4 — PTA §7 mechanic post-flight overlay

| check | result |
|---|---|
| §7 post-flight #1: `git diff` shows only `+` lines | ✓ PASS (107 insertions, 0 deletions) |
| §7 post-flight #2: last pre-existing content (§13 final sentence) unchanged | ✓ PASS |
| §7 post-flight #3: markdown structure valid (no orphan content; no broken table boundary) | ✓ PASS |
| §7 post-flight #4: §14 heading exact `## 14.`; no §15 emerges | ✓ PASS |
| Document end-matter (the "End of deterministic-semantics contract." block) byte-preserved | ✓ PASS |

### §C.5 — V18 sanity check (informational; not required for this AAU)

| check | result |
|---|---|
| V18 replay-test invariant against existing SessionPackages | ✓ PASS — runtime substrate unchanged from Wave 1 close (`5d1c21c`); documentation-only contract mutation; events SHA-256 invariant preserved by construction |

**Critical caveat:** V18 end-of-Wave-2 BLOCKING execution and V19 end-of-Wave-2 BLOCKING execution are deferred to the Wave 2 close sub-session (separately Decision-Owner-authorized), NOT this AAU adjudication session. The pre-attestation precedent (#11) applies.

### §C.6 — FF5 substrate preservation

| check | result |
|---|---|
| FF5 substrate preservation | ✓ PASS — current contract SHA `41b8b894…` differs from prior `683e8654…` (mutations applied as expected); 0 pre-Step-12 clause-IDs removed; 0 existing-clause text modified |

---

## §D — Reviewer adjudication slots (cap2 fills in)

### §D.1 — V6 manual review

**Reviewer checklist (per `tools/step12_validators/v06_v20_manual_checklists.md` §V6, applied to each of D-INGRESS-1..9):**

```
[ ] Each clause's Rule states the foreclosure or admittance only.
[ ] Each clause's Rule does NOT include operational consequences.
[ ] Each clause's Rule does NOT include implementation details.
[ ] Each clause's Rule does NOT include derivation chains.
[ ] Each clause's Rule does NOT include "borderline" or hedging qualifications.
[ ] Each clause's Rule uses MUST / MUST NOT / FORBIDDEN / SHALL / MAY explicitly.
```

**Reviewer verdict (V6): _________** (PASS / FLAG-REVISE — per clause if FLAG-REVISE)
**Rationale: _________**

### §D.2 — V20 manual review

**Reviewer checklist (per V20):**

```
[ ] No new MUST contradicts any existing MUST NOT for the same subject.
[ ] No new admittance contradicts any existing foreclosure.
[ ] Any clause-pair tension is explicitly acknowledged.
[ ] Each new clause's scope is consistent with the citation chain's transitive closure.
[ ] D-INGRESS-2's alignment with D-FAULT-6c (Wave 1) is explicit and constitutionally sound.
[ ] D-INGRESS-9's conditional-PAUSED scoping does NOT pre-commit Wave-3 PAUSED admission.
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

### §D.5 — Highest-widening-risk clause acknowledgement (D-INGRESS-8)

Per extraction plan §6.A: D-INGRESS-8 is the highest-widening-risk D-INGRESS clause. The Author observed the recommended three-sub-rule mitigation (D-INGRESS-8a on-event-not-envelope; D-INGRESS-8b not-read-by-orchestration; D-INGRESS-8c not-in-fingerprint).

**Reviewer acknowledgement (§D.5): _________** (THREE-SUB-RULE-ADEQUATE / FLAG-WIDENING-RISK)

If FLAG-WIDENING-RISK: identify which sub-rule is inadequate.

### §D.6 — D-INGRESS-2 / D-FAULT-6c alignment acknowledgement

D-INGRESS-2 (Phase-A-Only Pull) is the only D-INGRESS clause that cites a Wave-1 clause (D-FAULT-6c). D-INGRESS-2 bounds the *pull mechanism* to Phase A; D-FAULT-6c bounds the *observation surface for ingress events* to Phase A. The two clauses are complementary.

**Reviewer acknowledgement (§D.6): _________** (ALIGNMENT-CONFIRMED / FLAG-CONTRADICTION)

If FLAG-CONTRADICTION: identify the specific tension.

### §D.7 — Pre-commit Stage-3-correction acknowledgement (NEW precedent candidate)

Per §B.3 record, the Author detected 3 forward-citation defects at Stage 4 validator execution and re-entered Stage 3 for working-tree correction BEFORE Stage 6 commit. The corrected mutation is what this AAU commits. This is the FIRST documented invocation of pre-commit Stage-3-correction in Step 12.

The pattern is constitutionally distinct from precedent #7 (Interrupted-Stage-6-recovery), which applies to post-Stage-6 commit interruption. Pre-commit Stage-3-correction is the standard Layer A §15 cycle (Stage 4 failure → Stage 3 re-author → Stage 4 re-verify → Stage 5+), explicitly disclosed here for audit visibility.

**Reviewer acknowledgement (§D.7): _________** (ACCEPTED-STAGE-3-CORRECTION-DISCLOSURE / DISAGREE)

If DISAGREE: identify the constitutional violation and the remediation path.

---

## §E — Reviewer-prep ergonomics aids

### §E.1 — Reading order

1. §A AAU identification — what this AAU IS (SINGLE PTA containing 9 D-INGRESS clauses + scope + restatement)
2. §B.2 mutation diff overview
3. **§B.3 pre-commit Stage-3-correction record — NEW disclosure**
4. §B.4 + §B.5 citation classification + framework refs
5. §B.6 post-correction forward-citation status
6. §C validator result matrix
7. §D adjudication slots (including NEW §D.5/§D.6/§D.7)
8. (Reference) `docs/phase_4b_step11_admissibility_framework.md` §G.1 — D1–D8 framework statements
9. (Reference) `docs/phase_4b_step11_f58_paused_analysis.md` §N.1 — D9 framework statement
10. (Reference) `docs/phase_4b_step11_extraction_plan.md` §4.2 row 3 — D-FAULT-9b → D-INGRESS-9 dependency direction
11. (Reference) `docs/phase_4b_step12_authoring_mechanics_plan.md` §7 — PTA mechanic
12. (Reference) `docs/step12_audit_traces/aau_wave1_04_d_replay_10_review_resolution.md` §C.3 — V2 shape-agnostic generalization precedent (now in 5th invocation)

### §E.2 — Key questions for Reviewer

- Are D-INGRESS-1..9 faithful restatements of framework Disciplines D1..D9?
- Is the conditional-PAUSED scoping of D-INGRESS-9 constitutionally sound (i.e., binds nothing in the absence of PAUSED admission)?
- Does the three-sub-rule mitigation of D-INGRESS-8 adequately prevent diagnostic-to-authoritative widening?
- Is the D-INGRESS-2 / D-FAULT-6c alignment correctly stated (complementary, not redundant)?
- Is the pre-commit Stage-3-correction discipline (§B.3 + §D.7) constitutionally acceptable as a Wave-2 precedent?
- Are all Wave 1 clause bodies byte-preserved across the §14 PTA insertion? (V14 PASS; §C.3)
- Does §14.11's non-normative restatement avoid pre-binding future-wave codification?

### §E.3 — Wave 2 dependency note

This is the SINGLE Wave 2 AAU. Post-APPROVE:
- 1/1 Wave 2 AAU APPROVED-AND-CLOSED.
- Wave 2 close adjudication sub-session begins (separately Decision-Owner-authorized).
- V18 BLOCKING + V19 BLOCKING execute against Wave 2's substrate footprint.
- If both PASS: Wave 2 CLOSED; Wave 3 (D-FAULT-9b/9c) becomes admissible.
- If either FAILs: Wave-close BLOCKED; Reviewer/Decision-Owner determines remediation.

D-FAULT-9b (Wave 3) will cite D-INGRESS-9 (this Wave) and D-FAULT-6c (Wave 1) as anchors. D-FAULT-9c (Wave 3) will cite D-SCHED-14 (Wave 1) as anchor. Both dependencies will become resolvable when this AAU lands.

### §E.4 — Wave 2 precedents

This AAU invokes:
1. V2 PROCEED-SUBSTANTIVE (5th invocation; 1st under PTA — confirms V2 shape-agnostic generalization across FII + STA + PTA per precedent #9)
2. V15 SUBSTANTIVE PASS per S4 §S4-V15-finding (5th invocation)
3. Wall-clock-as-descriptive precedent (D-INGRESS clauses cite D-SCHED-11; D-INGRESS-9 extends D-SCHED-11's wall-clock foreclosure into PAUSED conditionally)
4. Reference-citation-deferral (NOT invoked here) — no extraction-plan-listed Reference citations for any D-INGRESS clause; precedent boundary preserved exactly
5. Framework-label-Note-materialization (NOT directly invoked) — framework-doc paths in Note sections only; no name-collision with local clause-IDs detected for any D-INGRESS framework reference
6. PTA-shape mutation precedent (FIRST PTA invocation; per §7 mechanic + post-flight overlay)

This AAU introduces:

7. **(NEW)** Pre-commit Stage-3-correction discipline — §B.3 + §D.7. The FIRST documented invocation of Stage 4 validator-failure-driven working-tree correction in Step 12. Reviewer §D.7 verdict sets the Wave-2 precedent.

---

## §F — Audit metadata

- AAU commit author: claude (per Layer A §15 8-stage protocol; Wave 2 Y2 multiplexing per S5 role activation)
- AAU commit timestamp: 2026-05-21 (descriptive only; wall-clock is non-authoritative per D-SCHED-11)
- Pre-mutation contract SHA-256: `683e8654cbccecd516364474b6c4b644f135ba78d825df57d605c17ced2af234` (HEAD `5d1c21c`, post-Wave-1-close state)
- Post-mutation contract SHA-256: `41b8b8941fa0ad57eab00422698e5468c41a64132b83d70ae410ec9d6d381bc3`
- Substrate impact: +107 lines (documentation-only); 0 runtime mutation; 0 replay-baseline mutation; 0 validator-infrastructure mutation; 0 governance mutation
- Master HEAD: UNCHANGED at `6daf9b2c24edef63e81a832727eb191726f69afb`
- Branch HEAD prior to this AAU: `5d1c21c5b0ad7c72f2c9890403133a8b21a6b545`
- Wave 1 byte-preservation lineage SHAs (all preserved across Wave 2): D-FAULT-6b `ae9a500e…` / D-FAULT-6c `6d27d9ce…` / D-SCHED-14 `afd82de5…` / D-REPLAY-10 `deec8fa6…`

---

**End of Wave 2 D-INGRESS review packet (Reviewer-prep state).**

Reviewer cap2 fills §D.1, §D.2, §D.4, §D.5, §D.6, §D.7. On APPROVE: Wave 2 AAU closes; Wave 2 close sub-session admitted (V18/V19 BLOCKING executes separately). On REVISE: Author re-authors via additive `git revert` + re-author (no amend / no rebase / no force-push per Layer D §10). On ESCALATE: T3/T8 path per Layer D §8.1; Constitutional Reviewer convening triggered.
