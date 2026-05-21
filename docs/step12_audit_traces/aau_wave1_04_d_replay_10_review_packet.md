# AAU Wave 1 / AAU 4 — D-REPLAY-10 Review Packet

**Filing status:** authored at AAU commit time per Layer C §19 schema. This is the Reviewer-prep packet that hands the AAU from Author (claude) to Reviewer (cap2) for adjudication.

**Adjudication state at AAU commit:** REVIEW-PENDING (Reviewer cap2 has not yet adjudicated; this packet is the handover).

---

## §A — AAU identification

| field | value |
|---|---|
| Wave | 1 |
| AAU sequence | 4 of 4 (**FINAL Wave 1 authoring AAU**; post-APPROVE will gate end-of-Wave-1 V18+V19 BLOCKING checks) |
| Clause ID | **D-REPLAY-10** |
| Clause name | Scheduled-Injection Replay Primitive |
| Mutation shape | **STA (Section-Tail Append)** — 2nd STA-shape AAU (1st was D-SCHED-14) |
| Source theorem | Framework refinement R1 to Lemma L4 (per `docs/phase_4b_step11_admissibility_framework.md` §C.4 and `docs/phase_4b_step11_f58_paused_analysis.md` §J.2). NOT a T-theorem promotion; R1 is a refinement-class promotion (per codification plan §4: "R1 placed as single D-REPLAY-10 clause") |
| C-1/C-2 status | C-1 promoted (per codification plan §4 + §1 footer table row "§4 D-REPLAY \| R1 promotion") |
| Author | claude |
| Reviewer | cap2 |
| Layer-B-implementing-agent | claude |
| Decision-Owner | cap2 |

---

## §B — Mutation specification

### §B.1 — Insertion anchor (V1 + V2 record)

**Anchor (Edit `old_string`, multi-line):**

```
**D-REPLAY-9** — The session manifest **must** record subscriber identities (stable type names and constructor argument hashes, where available). L3 replay comparison requires identical subscriber sets; mismatched subscriber sets are compared at L4 only.

---

## 5. ExecutionSession Authority Boundary  *(D-SESS)*
```

The multi-line anchor uniquely identifies the §4/§5 boundary. The single-line core (`## 5. ExecutionSession Authority Boundary  *(D-SESS)*`) is itself unique (V13 PASS confirms 1 occurrence post-mutation).

**V1 pre-mutation uniqueness:** ✓ PASS (`## 5. ExecutionSession Authority Boundary  *(D-SESS)*` occurs exactly 1 time in pre-mutation contract at HEAD `265180a` with contract SHA `32e7fc0c...`; `grep -cF '## 5. ExecutionSession Authority Boundary  *(D-SESS)*'` == 1).

**V2 adjudication:** **PROCEED-SUBSTANTIVE** per the Wave 1 precedent (D-FAULT-6b at `b7de4cd`, D-FAULT-6c at `d789f4d`, D-SCHED-14 at `e30bc03`). **FOURTH invocation**; **SECOND under STA shape**. The V2 PROCEED-SUBSTANTIVE precedent was formalized at AAU 3 Reviewer resolution (`265180a` §C.3) as shape-agnostic: Edit-tool insertion semantics (`old_string ⊆ new_string`) hold for any insertion-class shape regardless of family-internal vs section-tail placement. The mechanization conditions for D-REPLAY-10 are identical to D-SCHED-14's: `old_string` appears verbatim within `new_string` at exactly one mutation locus (sandwich form: `D-REPLAY-9 body`...`[new §4.5 content]`...`---`...`## 5.`); V13 confirms anchor uniqueness post-mutation; substantive intent satisfied; literal-mechanization gap explicitly disclosed (NOT a silent bypass).

### §B.2 — Mutation diff

```
+### 4.5 D-REPLAY-10 — Scheduled-Injection Replay Primitive
+
+**D-REPLAY-10** — A replay tool **MAY** reconstruct a session's `pending_operator_envelopes` content from the authoritative trace via a **scheduled-injection** primitive: for each `OperatorAbortRequested` / `OperatorPauseRequested` / `OperatorResumeRequested` event, reconstruct an `OperatorEnvelope` from payload `(kind, requested_at_tick, reason)` with `envelope_id` content-addressed per D-FAULT-9; associate each envelope with the event's `ts_step` as its scheduled drain tick; at each Phase A, inject envelopes whose scheduled drain tick equals the current `orchestration_tick` into `_pending_envelopes` before the canonical-order drain. The pre-queue primitive (envelopes passed to `pending_operator_envelopes` at `session.begin()`) is the special case where each envelope's scheduled drain tick equals its `requested_at_tick`.
+
+Scheduled-injection is a **replay-tool reconstruction algorithm**, not a substrate-runtime obligation. The production `ExecutionSession` is unchanged: production envelope intake remains live channel pull and pre-queue per the existing D-FAULT-9 contract.
+
+**Citations.**
+* Anchor: D-REPLAY-1, D-REPLAY-2, D-TRACE-2, D-FAULT-9
+
+*Note.* This clause asserts framework refinement R1 to Lemma L4 (Replay-Reconstruction From Trace Alone) per `docs/phase_4b_step11_admissibility_framework.md` §C.4 and `docs/phase_4b_step11_f58_paused_analysis.md` §J.2. R1 extends L4's reconstruction primitive from "pre-queue only" to "scheduled-injection," resolving the late-arrival case where an envelope's Phase A drain tick differs from its `requested_at_tick`. D-REPLAY-10 is normative-strengthening (making explicit the replay-tool reconstruction primitive that the trace + D-FAULT-9 content-addressing already enable), not normative-additive — it introduces no new production-runtime semantics, no new ingress surfaces, and no new authority quanta; `orchestration_tick` remains the authority quantum (D-SCHED-11 preserved); transport-independence (framework Theorem T5) is preserved (the replay tool reads only the trace). The extraction plan §4.2 row 6 reference to "L4 framework label" is materialized in this Note section to preserve V9 framework-ref confinement; the Citations Reference subsection is intentionally omitted to avoid V17 ambiguity with the contract's local "L4" label (§4.1 Semantic Validation Identity layer, an unrelated concept).
```

- 11 inserted lines
- 0 deleted lines
- A3 (diff-shape additive-only): ✓ satisfied
- Insertion point: between line 337 (§4.4 D-REPLAY-9 body end) and line 339 (`---` separator), as new §4.5 inserted into §4 D-REPLAY tail
- Line-number impact: lines 338+ of pre-mutation contract shift down by 11 lines in post-mutation contract (purely offset; no content modified)

### §B.3 — Citation classification (V4 record)

**Anchor citations** (constitutionally load-bearing; normative dependency; per extraction plan §4.2 row 6):
- D-REPLAY-1 (§4.1; L1⊇L2⊇L3⊇L4 strictness ordering; foundation for replay-identity discipline that D-REPLAY-10's reconstruction primitive operates within)
- D-REPLAY-2 (§4.2; bitwise-identical replay conditions; the conditions D-REPLAY-10's primitive helps satisfy)
- D-TRACE-2 (§6; authoritative append-only trace; the trace that D-REPLAY-10's primitive reads from)
- D-FAULT-9 (§13.9; operator envelope schema with content-addressed `envelope_id`; the schema D-REPLAY-10's primitive reconstructs from)

**Reference citations:** INTENTIONALLY ABSENT (Citations Reference subsection omitted; framework reference materialized in Note per §B.5).

The extraction plan §4.2 row 6 lists "L4 framework label" as the reference. L4 is a FRAMEWORK CONCEPT (Lemma L4 — Replay-Reconstruction From Trace Alone), NOT a contract clause-ID. Additionally, the contract's §4.1 (lines 296–301) uses the label "L4" with a DIFFERENT meaning ("L4 — Semantic Validation Identity"). Materializing "L4 framework label" as a Reference subsection entry would risk:

1. **V9 framework-ref confinement violation:** including the framework-doc path in Citations would breach the Note-only confinement.
2. **V17 ambiguity:** `grep -F 'L4'` against the contract returns matches for the contract's local L4 (§4.1) not the framework's L4 (Lemma); the mechanical V17 check passes by coincidence but the cited concept is semantically distinct.
3. **Cross-clause reader confusion:** a reader scanning Citations for "L4" would correctly find the contract's local "L4 — Semantic Validation Identity" rather than the intended framework concept.

**Resolution:** the framework Lemma L4 reference is materialized in the Note section (where framework refs belong per V9). The Citations Reference subsection is intentionally omitted. This handling is constitutionally distinguishable from:
- D-FAULT-6c (AAU 2)'s reference-citation deferral: a forward-reference to a Wave-4 not-yet-existing clause-ID
- D-SCHED-14 (AAU 3)'s no-reference: extraction plan said "—" (no reference specified)
- D-REPLAY-10 (AAU 4)'s framework-label-Note-materialization: extraction plan listed a framework label as reference, which is categorically not a contract clause-ID and must be materialized in Note per V9 confinement

This introduces a **new disclosure pattern at AAU 4** — Reviewer §D.5 acknowledgement REQUIRED.

All cited clause-IDs (D-REPLAY-1, D-REPLAY-2, D-TRACE-2, D-FAULT-9) confirmed present in pre-mutation contract via V5 dry-run. V17 post-mutation confirmed all citations resolve (D-REPLAY-1: 8, D-REPLAY-2: 2, D-TRACE-2: 3, D-FAULT-9: 15).

### §B.4 — Framework references (V9 confinement record)

Framework refs in this AAU body:
- `docs/phase_4b_step11_admissibility_framework.md` (framework filename) — Note section only ✓
- `docs/phase_4b_step11_f58_paused_analysis.md` (analytical-extension filename) — Note section only ✓
- R1 (framework refinement label) — Note section only ✓
- L4 (framework Lemma label) — Note section only ✓ (NOT in Citations Reference subsection per §B.3)
- Theorem T5 (framework theorem label, for transport-independence preservation claim) — Note section only ✓

V9 check: Rule section contains zero framework references; Citations section contains zero framework references; all framework refs confined to Note section. **First AAU to cite TWO framework docs** (`admissibility_framework.md` for L4 + `f58_paused_analysis.md` for R1's full statement at §J.2); both are constitutionally-admissible framework artifacts per Step 11 analytical pipeline.

### §B.5 — Framework-label-Note-materialization disclosure (NEW concern at AAU 4)

**Concern.** Extraction plan §4.2 row 6 lists "L4 framework label" as D-REPLAY-10's reference citation. L4 is a framework Lemma label, not a contract clause-ID. The contract's local §4.1 layered-identity table also uses "L4" (Semantic Validation Identity layer), an unrelated concept.

**Author handling.** Materialize the L4 framework reference in the Note section (per V9 framework-ref confinement); omit the Citations Reference subsection entirely. This preserves V9 + V17 BLOCKING discipline while honoring the extraction plan's intent (the L4 framework concept IS referenced; it is just referenced from the appropriate location — the Note — rather than in Citations).

**Disclosure status.**
- EXPLICIT: review packet §B.3 + §B.5 + §D.5 (NEW Reviewer-acknowledgement slot) + the clause Note itself (which closes with: "the Citations Reference subsection is intentionally omitted to avoid V17 ambiguity with the contract's local 'L4' label").
- NOT hidden
- NOT silently normalized
- NOT silently self-adjudicated by Author

**Constitutional reasoning (Author's view for Reviewer).** The handling is constitutionally distinct from:
- D-FAULT-6c's reference-citation deferral (a forward-reference to a not-yet-existing clause-ID; Wave 4 row 32).
- D-SCHED-14's no-reference (extraction plan §4.2 row 5 = "—"; no reference specified at all).
- D-REPLAY-10's framework-label-Note-materialization (extraction plan specified a framework label as reference; framework labels constitutionally belong in Note per V9; Citations Reference subsection is reserved for contract clause-IDs; therefore the planned reference is materialized in the Note rather than the Reference subsection).

Each pattern preserves V14/V17/V19 BLOCKING discipline and the additive-only invariant; each is explicitly disclosed; each requires its own Reviewer acknowledgement.

---

## §C — Validator result matrix

### §C.1 — Pre-mutation (Stage 1–2)

| validator | classification | result | detail |
|---|---|---|---|
| V1 (anchor uniqueness pre) | BLOCKING | ✓ PASS | anchor `## 5. ExecutionSession Authority Boundary  *(D-SESS)*` occurs 1 time |
| V2 (anchor stability) | BLOCKING | PROCEED-SUBSTANTIVE adjudicated | per §B.1 record; D-FAULT-6b/6c/D-SCHED-14 precedent; 4th invocation; 2nd under STA |

### §C.2 — Pre-mutation body (Stage 3)

| validator | classification | result | detail |
|---|---|---|---|
| V3 (template presence) | BLOCKING | ✓ PASS | Rule + Citations + Note sections all present; MAY admittance + replay-tool-only scope qualifier confirmed |
| V4 (citation classification) | BLOCKING | ✓ PASS | Anchor label present; Reference label intentionally absent per §B.3 framework-label-Note-materialization disclosure |
| V5 (anchor-cite existing) | BLOCKING | ✓ PASS | all anchor citation clause-IDs (D-REPLAY-1, D-REPLAY-2, D-TRACE-2, D-FAULT-9) resolve in pre-mutation contract (defining clauses at L303, L307, L409, L1201 respectively) |
| V6 (minimal-enforceable-surface) | SOFT/MANUAL | **DEFERRED to Reviewer** | per `tools/step12_validators/v06_v20_manual_checklists.md` V6 checklist |
| V7 (hidden-widening D-REPLAY-10 seed) | SOFT | ✓ PASS | extraction plan §6.A guardrail observed: clause uses PERMISSIVE "**MAY**" language for the scheduled-injection admittance (NOT "MUST" / "is admitted" / "is mandatory"); no banned phrases found |
| V8 (override-statement) | N/A | N/A | D-FAULT-9c only; not applicable to D-REPLAY-10 |
| V9 (framework-ref confinement) | BLOCKING | ✓ PASS | framework refs (R1, L4, T5, admissibility_framework.md, f58_paused_analysis.md) all in Note section only; Rule + Citations contain ZERO framework refs |
| V10 (D-FAULT-15 row format) | N/A | N/A | D-FAULT-15 row AAUs only; not applicable |

### §C.3 — Post-mutation (Stage 4)

| validator | classification | result | detail |
|---|---|---|---|
| V11 (Properties A1–A3) | BLOCKING | ✓ PASS | 11 insertions, 0 deletions; A3 satisfied (`git diff` shows 0 `-` content lines); A1 and A2 implied |
| V12 (Properties S1–S3) | N/A | N/A | STA shape, not SF |
| V13 (anchor uniqueness post) | BLOCKING | ✓ PASS | anchor (`## 5. ExecutionSession Authority Boundary  *(D-SESS)*`) occurs 1 time post-mutation |
| V14 (existing-text byte preservation) | BLOCKING | ✓ PASS | implied by V11 A3; D-FAULT-6b body SHA `ae9a500e…` (identical pre/post AAU 4); D-FAULT-6c body SHA `6d27d9ce…` (identical pre/post AAU 4); D-SCHED-14 body SHA `afd82de5…` (newly recorded for byte-preservation lineage); §2.6 stale-enumeration text remains byte-preserved |
| V15 (heading-DAG structure) | BLOCKING | ✓ SUBSTANTIVE PASS per S4 §S4-V15-finding | 3 pre-existing skips detected at lines 11, 859, 1133 post-mutation (= original S4 lines 11, 832, 1106 shifted by +11-line offset from D-REPLAY-10's §4.5 insertion at L338 on top of D-FAULT-6b/c +19 cumulative + D-SCHED-14 +16 cumulative; identical heading content; ALL pre-existing; AAU introduces ZERO new level skips — insertion at `###` level 3 between sibling `###` level 3 and parent `##` level 2 introduces no level jump) |
| V16 (new clause-ID uniqueness) | BLOCKING | ✓ PASS | D-REPLAY-10 definition count = 1; heading-level D-REPLAY-10 count = 1 |
| V17 (cross-reference resolvability) | BLOCKING | ✓ PASS | all cited clause-IDs (D-REPLAY-1, D-REPLAY-2, D-TRACE-2, D-FAULT-9, plus D-SCHED-11 and D-FAULT-6 referenced in Note context) resolve in post-mutation contract; both framework docs (admissibility_framework.md 80273 bytes; f58_paused_analysis.md 77531 bytes) exist at cited paths |

### §C.4 — STA §5 mechanic post-flight overlay

| check | result |
|---|---|
| §5 post-flight #1: `git diff` shows only `+` lines | ✓ PASS (11 insertions, 0 deletions) |
| §5 post-flight #2: previous last subsection content (`### 4.4 Identity boundaries` body ending with D-REPLAY-9) still returns exactly 1 grep match for D-REPLAY-9 def (existing-text unchanged) | ✓ PASS |
| §5 post-flight #3: next top-level section heading (`## 5. ExecutionSession Authority Boundary  *(D-SESS)*`) unmodified and unmoved (content unchanged; line offset shifted by insertion delta) | ✓ PASS (heading text byte-identical; line shifted from 341 to 352 = +11) |
| §5 mutation #2: new subsection heading uses next sequential subsection number (`### 4.5`) | ✓ PASS (next after §4.4) |
| §5 mutation #3: new subsection ends with exactly one trailing blank line before next top-level heading | ✓ PASS (blank line then `---` separator unchanged; `## 5.` heading at L352) |

### §C.5 — Stale-enumeration check (AAU 3 precedent application)

| check | result |
|---|---|
| §4 D-REPLAY contains an "Non-goals" subsection enumerating "D-REPLAY-1 through D-REPLAY-N" | ✗ NO (no §4 Non-goals subsection exists) |
| Any existing §4 text becomes incomplete due to D-REPLAY-10 insertion | ✗ NO |
| AAU 3 stale-enumeration precedent invocation required | ✗ NO |

**Stale-enumeration concern: ABSENT at AAU 4.** Unlike AAU 3 (which introduced the stale-enumeration-disclosure precedent due to §2.6 Non-goals' "D-SCHED-1 through D-SCHED-13" enumeration), §4 D-REPLAY has no analogous enumeration to become stale. The AAU 3 precedent boundaries are preserved exactly (per directive requirement 11): the precedent applies only when a non-normative existing enumeration becomes incomplete; the absence of such enumeration in §4 means the precedent is NOT invoked.

### §C.6 — V18 sanity check (informational; not required at AAU 4 itself; but BLOCKING at end-of-Wave-1 post-AAU-4 APPROVE)

| check | result |
|---|---|
| V18 replay-test invariant against existing SessionPackages | ✓ PASS — runtime substrate unchanged from D-SCHED-14 commit `e30bc03` (D-REPLAY-10 is documentation-only contract mutation; zero runtime files touched); the V18 invariant (events SHA-256 byte-identical across cycles) is preserved by construction |

**Critical AAU 4 caveat (per directive `Critical Wave-1 context`):** V18 end-of-Wave-1 BLOCKING execution MUST NOT occur during this AAU authoring session. This packet records V18 sanity-PASS only. The end-of-Wave-1 V18 BLOCKING check fires AFTER Reviewer cap2 APPROVEs D-REPLAY-10 and during the Wave-close adjudication sub-session.

### §C.7 — FF5 substrate preservation

| check | result |
|---|---|
| FF5 substrate preservation | ✓ PASS — current contract SHA `683e8654cbccecd516364474b6c4b644f135ba78d825df57d605c17ced2af234` differs from prior `32e7fc0c...` (mutations applied as expected); 0 pre-Step-12 clause-IDs removed; 0 existing-clause text modified (verified via V14 PASS + AAU 1/2/3 body SHA preservation in §C.3) |

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

**Special note for V6 at AAU 4:** D-REPLAY-10 is an ADMITTANCE clause (MAY-only), not a foreclosure. The Rule's algorithmic specification (envelope reconstruction; scheduled-injection mechanism; pre-queue special case) is the *content of the admittance* — it specifies WHAT replay tools MAY do. Reviewer should evaluate whether the algorithmic specification crosses into implementation-detail territory.

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

**Special focus for V20 at AAU 4:** D-REPLAY-10's MAY-admittance for the scheduled-injection primitive MUST NOT widen replay authority into production-runtime semantics. The clause's "replay-tool reconstruction algorithm, not a substrate-runtime obligation" qualifier is the key normative-consistency anchor. Reviewer should verify this scope boundary against D-INGRESS (Wave 2 future) intuition — D-INGRESS will specify production-runtime ingress; D-REPLAY-10 must not pre-empt D-INGRESS or introduce a parallel ingress surface.

**Reviewer verdict (V20): _________** (PASS / FLAG-REVISE / ESCALATE)
**Rationale: _________**

### §D.3 — V7 SOFT-flag adjudication (if any)

V7 returned 0 banned phrases. No SOFT flag raised. Reviewer adjudication: N/A.

### §D.4 — Layer C 3-option verdict

**Reviewer verdict: _________** (APPROVE / REVISE / ESCALATE)

**APPROVE-AS-IS rationale (if APPROVE):** MUST cite framework/precedent/scope-limit per Layer C §17 (never intuition).

**REVISE rationale (if REVISE):** specify what needs revision.

**ESCALATE rationale (if ESCALATE):** specify which trigger (T3 / T8); Constitutional Reviewer convening required per Layer D §8.1.

### §D.5 — Framework-label-Note-materialization acknowledgement (NEW concern at AAU 4)

Per §B.5 record, the extraction-plan-listed reference "L4 framework label" is materialized in the Note section rather than the Citations Reference subsection. This handling:
- Preserves V9 framework-ref confinement (framework refs in Note only).
- Avoids V17 ambiguity (contract has its own local "L4" in §4.1 with unrelated meaning).
- Honors extraction plan's intent (L4 framework reference IS present in the clause, just in the appropriate location).
- Is constitutionally distinguishable from D-FAULT-6c's deferral and D-SCHED-14's no-reference.

**Reviewer acknowledgement (§D.5): _________** (ACCEPTED-NOTE-MATERIALIZATION / DISAGREE)

If DISAGREE: identify the constitutional violation and remediation path (e.g., move framework reference back to Citations Reference subsection — but this conflicts with V9; or omit L4 reference entirely — but this loses framework-context citation that the extraction plan specified).

### §D.6 — Wave 1 close-readiness pre-attestation

Per directive `Critical Wave-1 context`: this session is AAU 4 authoring ONLY. Wave-close V18/V19 BLOCKING checks MUST NOT execute during this session.

This slot records Author's pre-attestation that the conditions for **future** Wave-close V18/V19 BLOCKING checks are NOT compromised by this AAU:

- V18 sanity at AAU 4: ✓ PASS (per §C.6); runtime untouched
- All Wave 1 clause bodies byte-preserved (per V14 in §C.3): D-FAULT-6b (`ae9a500e…`), D-FAULT-6c (`6d27d9ce…`), D-SCHED-14 (`afd82de5…`)
- No Wave-1 inter-clause citation gaps introduced (all anchor citations resolve mechanically; reference citations either present-and-resolving or explicitly disclosed via established precedents)
- 4-of-4 Wave-1 AAU clause-IDs unique and defined at end-of-this-AAU
- Post-AAU-4-APPROVE, the Reviewer/Decision-Owner sub-session executes V18 BLOCKING + V19 BLOCKING; if both PASS, Wave 1 CLOSED; if either FAILs, Wave-close BLOCKED with Reviewer-determined remediation path

**Reviewer pre-attestation (§D.6): _________** (PRE-CONDITIONS-PRESERVED / DISAGREE)

If DISAGREE: identify the pre-condition that is NOT preserved and the required remediation BEFORE Wave-close V18/V19 execution.

---

## §E — Reviewer-prep ergonomics aids

### §E.1 — Reading order

1. §A AAU identification — what this AAU IS (and that it is the FINAL Wave 1 AAU)
2. §B.2 mutation diff — the actual clause text
3. §B.3 + §B.4 citation classification + framework refs — why citations resolve
4. **§B.5 framework-label-Note-materialization disclosure — NEW concern at AAU 4**
5. §C validator result matrix — what mechanical checks have passed
6. §C.4 STA mechanic post-flight overlay — STA-specific checks
7. §C.5 stale-enumeration check — AAU 3 precedent NOT invoked (boundary preserved)
8. §D adjudication slots — what cap2 fills in (including §D.5 framework-label-Note-materialization + §D.6 Wave-close pre-attestation)
9. (Reference) `docs/phase_4b_step11_admissibility_framework.md` §C.4 — Lemma L4 statement + hypotheses
10. (Reference) `docs/phase_4b_step11_f58_paused_analysis.md` §J.2 — full R1 refinement specification
11. (Reference) `docs/phase_4b_step11_codification_plan.md` §4 — R1 placement rationale (replay-tool primitive, not §14 D-INGRESS)
12. (Reference) `docs/phase_4b_step11_extraction_plan.md` §4.2 row 6 — citation list with reference = "L4 framework label"
13. (Reference) `docs/phase_4b_step12_authoring_mechanics_plan.md` §5 — STA mechanic specification
14. (Reference) `docs/step12_audit_traces/aau_wave1_03_d_sched_14_review_resolution.md` §C.3 — V2 shape-agnostic generalization (now in 4th invocation)

### §E.2 — Key questions for Reviewer

- Does the Rule section state the MAY-admittance narrowly (replay-tool reconstruction primitive only, not production-runtime obligation)? (V6 + §6.A guardrail check)
- Is the "replay-tool reconstruction algorithm, not a substrate-runtime obligation" qualifier adequate to prevent semantic widening into production-runtime ingress? (V6 + V20 check)
- Do citations resolve in the correct sense — anchor citations are load-bearing? (V4 + V17 PASS confirmed)
- Does the Note section's R1 + L4 + T5 explanation match the analytical framework? (cross-check vs `docs/phase_4b_step11_admissibility_framework.md` §C.4 + `docs/phase_4b_step11_f58_paused_analysis.md` §J.2)
- Does the clause's normative-strengthening claim ("not normative-additive") accurately reflect that D-FAULT-9 content-addressing + D-TRACE-2 append-only trace + D-REPLAY-1/2 strictness already enable the scheduled-injection reconstruction? (V20 + transitive-closure check)
- **Is the framework-label-Note-materialization handling constitutionally acceptable?** (§D.5 / §B.5)
- Is the V2 PROCEED-SUBSTANTIVE 4th invocation (2nd under STA) acceptable as continued precedent application?
- Are D-FAULT-6b, D-FAULT-6c, and D-SCHED-14 bodies all byte-preserved across the D-REPLAY-10 insertion? (V14 PASS; §C.3 SHA lineage)
- **Are Wave-close V18/V19 pre-conditions preserved for the future Wave-close sub-session?** (§D.6 pre-attestation; explicit NO Wave-close execution at this AAU)

### §E.3 — Wave 1 dependency note

D-REPLAY-10 is the FINAL Wave 1 AAU. Post-APPROVE:
- 4-of-4 Wave 1 AAUs APPROVED-AND-CLOSED.
- Wave-close adjudication sub-session begins.
- V18 BLOCKING (end-of-Wave-1 replay-test invariant) executes.
- V19 BLOCKING (end-of-Wave-1 inter-wave citation-gap check) executes.
- If both PASS: Wave 1 CLOSED; Wave 2 (§14 D-INGRESS) becomes admissible.
- If either FAILs: Wave-close BLOCKED; Reviewer/Decision-Owner determines remediation path.

D-FAULT-9b (Wave 3) cites D-REPLAY-10's framework precondition (transport-independence; L4-refined replay reconstruction) indirectly via D-INGRESS-9 (Wave 2). D-INGRESS-2 (Wave 2) cites D-FAULT-6c which cites D-EXEC-1/2/D-FAULT-6 — no direct D-REPLAY-10 anchor citation in Wave 2 or Wave 3 per extraction plan §4.2.

### §E.4 — Wave 1 precedents invoked

This AAU invokes the following Wave 1 precedents established at D-FAULT-6b / D-FAULT-6c / D-SCHED-14:

1. **V2 PROCEED-SUBSTANTIVE** — 4th invocation; 2nd under STA shape. Shape-agnostic generalization formalized at AAU 3 §C.3 applies directly.
2. **V15 SUBSTANTIVE PASS per S4 §S4-V15-finding** — 4th invocation. Same 3 pre-existing skips with cumulative offset to L11, L859, L1133. ZERO new skips.
3. **Wall-clock-as-descriptive precedent** — D-REPLAY-10 references `requested_at_tick` and `ts_step` (orchestration_tick values), not wall-clock; D-SCHED-11 preserved verbatim.
4. **Reference-citation-deferral precedent (NOT invoked here)** — D-FAULT-6c's deferral was for forward-clause-ID reference; D-REPLAY-10's framework-label handling is constitutionally distinct (per §B.3 + §B.5).
5. **STA-shape mutation precedent** — 2nd STA invocation; AAU 3's precedent directly applies (multi-line anchor with single-line uniqueness core; STA §5 post-flight overlay).
6. **Interrupted-Stage-6-recovery precedent** — NOT invoked at this AAU; commit proceeds normally without interruption.
7. **Stale-enumeration-disclosure precedent (NOT invoked here)** — §4 D-REPLAY has no Non-goals enumeration to become stale (per §C.5); AAU 3 precedent boundaries preserved exactly.
8. **V2 shape-agnostic generalization** — directly applies to 2nd STA invocation.

This AAU introduces:

9. **(NEW concern) Framework-label-Note-materialization pattern** — §B.5 / §D.5. The first AAU where the extraction-plan-listed reference is a framework label (not a contract clause-ID); framework labels constitutionally belong in Note per V9; Citations Reference subsection is reserved for contract clause-IDs. Reviewer's adjudication at §D.5 sets the Wave-1 precedent.

---

## §F — Audit metadata

- AAU commit author: claude (per Layer A §15 8-stage protocol; Wave 1 Y2 multiplexing per S5 role activation)
- AAU commit timestamp: 2026-05-21 (descriptive only; wall-clock is non-authoritative per D-SCHED-11)
- Pre-mutation contract SHA-256: `32e7fc0cd6305b9e9ee663e0a466d99419d03d67ef8d2f5a8de69dd1a16b3696` (HEAD `265180a`, post-D-SCHED-14-APPROVE state)
- Post-mutation contract SHA-256: `683e8654cbccecd516364474b6c4b644f135ba78d825df57d605c17ced2af234`
- Substrate impact: +11 lines (documentation-only); 0 runtime mutation; 0 replay-baseline mutation; 0 validator-infrastructure mutation; 0 governance mutation
- Master HEAD: UNCHANGED at `6daf9b2c24edef63e81a832727eb191726f69afb`
- Branch HEAD prior to this AAU: `265180aecf3014a89b29e439a0a2d5e1459266c6`
- Wave 1 byte-preservation lineage SHAs (D-FAULT-6b, D-FAULT-6c, D-SCHED-14 all byte-preserved across AAU 4): `ae9a500e…` / `6d27d9ce…` / `afd82de5…`

---

**End of D-REPLAY-10 Wave 1 AAU 4 review packet (Reviewer-prep state).**

Reviewer cap2 fills §D.1, §D.2, §D.4, §D.5, §D.6. On APPROVE: AAU 4 closes; **Wave 1 ENTERS WAVE-CLOSE GATE** (V18 BLOCKING + V19 BLOCKING execute in a SEPARATE sub-session, NOT in this AAU authoring session per directive). On REVISE: Author claude revises; re-commits via git revert + re-author (no amend per Layer A §16; no rebase / no force-push per Layer D §10 + BRANCH-LINEARITY). On ESCALATE: T3/T8 path per Layer D §8.1; Constitutional Reviewer convening triggered.
