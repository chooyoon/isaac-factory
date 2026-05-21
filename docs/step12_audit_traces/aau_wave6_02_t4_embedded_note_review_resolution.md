# AAU Wave 6 / AAU 6.2 — §3.7 Framework Theorem T4 embedded note Reviewer Resolution

**Filing status:** authored at Reviewer adjudication time per Layer C §19 schema; supersedes REVIEW-PENDING state of `aau_wave6_02_t4_embedded_note_review_packet.md` §D adjudication slots.

**Authoring authority.** Reviewer cap2 (Y2 multiplexing per S5). Operationally drafted by claude under cap2's direction. cap2 retains adjudication authority.

**Role-separation invariant note.** Per Y2 §S5 + Layer D §10: Author (claude) ≠ Reviewer (cap2). This adjudication closes the 2nd Wave 6 AAU.

---

## §A — V6 manual checklist

§3.7 embedded note inspected at contract L307-L323 (HEAD `d399db5`).

| check | result | rationale |
|---|---|---|
| Subsection format correct | ✓ PASS | `### 3.7 Framework Theorem T4 — Acquisition-Visibility Tick Alignment (embedded note)` heading + body + Citations + Note per STA convention |
| C-2 embedded-note form (not C-1 clause) | ✓ PASS | NO `**D-XXX-N**` clause-form definition; heading explicitly "(embedded note)"; Note section cites framework "NORMATIVE-CANDIDATE" classification |
| Body paraphrases framework T4 faithfully | ✓ PASS | acquisition-visibility tick co-location + 2 manifestation cases (Phase-A-drained + Deferred-from-Phase-A) + cross-tick decoupling foreclosure + anchoring mechanism (D-EXEC-2 + D-EXEC-7 + D-BUS-3) |
| Citations subsection contains only clause-IDs | ✓ PASS | D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b (exactly matching framework §B.4 hypotheses) |
| Note section materializes framework references | ✓ PASS | T4 framework label appears in *Note.* section only (L323) |
| Tie-break resolution documented | ✓ PASS | completion §B.1 + review packet §E + this resolution §G explicitly document §3 D-BUS PRIMARY resolution |

**V6 verdict: ✓ PASS.**

---

## §B — V20 normative-consistency checklist

| check | result | rationale |
|---|---|---|
| No new MUST contradicts existing MUST NOT | ✓ PASS | embedded note introduces no new MUST/MUST NOT |
| No new admittance contradicts foreclosure | ✓ PASS | no admittance; paraphrastic only |
| Cite minimalism convention preserved | ✓ PASS | 5 anchor clause-IDs + 1 framework label (T4) in heading + Note only |
| Scope consistent with citation chain | ✓ PASS | framework T4 hypotheses (D-BUS-1/-3, D-EXEC-2/-7, D-FAULT-3b) jointly imply T4; embedded note states the implication |
| Embedded note does NOT widen framework T4 | ✓ PASS | body content matches framework §B.4 L118-L134 statement faithfully |
| Bus-emission discipline preserved | ✓ PASS | T4 paraphrase reinforces D-BUS-1 synchronous dispatch + D-BUS-3 monotone gap-free seq without widening either |
| Wave 6 AAU 6.1 §1.7 T1 embedded note coherence | ✓ PASS | T1 establishes tick-K-frozen-during-Phase-E premise; T4 builds on this for acquisition-visibility tick alignment; consistent layering |
| C-2 embedded form codifies T4 without new clause | ✓ PASS | no `**T4**` clause-form definition; reasoning is paraphrastic |

**V20 verdict: ✓ PASS.**

---

## §C — V7 SOFT banned-phrase verdict

| check | result |
|---|---|
| Banned phrases | ✓ PASS (0 occurrences) |

**V7 verdict: ✓ PASS.**

---

## §D — V2 PROCEED-SUBSTANTIVE reuse assessment (twenty-seventh invocation; fourth STA invocation cumulative)

**✓ YES.** Per #9 shape-agnostic generalization. STA mechanic stable across 4 invocations (Wave 1 AAU 3 D-SCHED-14 + Wave 1 AAU 4 D-REPLAY-10 + Wave 6 AAU 6.1 T1 + this AAU 6.2 T4).

**Cumulative V2 invocations: 27** (FII × 4 + STA × 4 + PTA × 18 + SF × 1).

---

## §E — Framework T4 embedded-note coherence adjudication (§D.5)

### §E.1 — Validity audit

| dimension | Reviewer verdict | evidence |
|---|---|---|
| Framework Theorem T4 (§B.4 L118-L134) byte-preservation | ✓ CONFIRMED (framework doc untouched throughout Wave 6) |
| 5 anchor clauses byte-preservation | ✓ CONFIRMED (D-BUS-1 L268; D-BUS-3 L274; D-EXEC-2 L61; D-EXEC-7 L85; D-FAULT-3b at +16 offset = L1097 post-mutation; all byte-identical) |
| Embedded note paraphrases framework T4 faithfully | ✓ CONFIRMED | body content covers: tick co-location concept + Case 1 (Phase-A-drained → D-BUS-1 synchronous dispatch + same-Phase-A state transition + K_a = K_v = K) + Case 2 (Deferred-from-Phase-A → D-FAULT-3b end-of-Phase-E classification + same post-Phase-E state transition + K_a = K_v = K) + cross-tick decoupling foreclosure + anchoring mechanism |
| C-2 embedded note vs C-1 clause distinction | ✓ CONFIRMED |
| No new normative content | ✓ CONFIRMED |
| No new authority surface | ✓ CONFIRMED |
| No replay-identity widening | ✓ CONFIRMED |
| No ingress widening | ✓ CONFIRMED |
| No scheduler widening | ✓ CONFIRMED |
| No bus-emission discipline widening | ✓ CONFIRMED |
| Cite minimalism preserved | ✓ CONFIRMED |

### §E.2 — Framework T4 ↔ §3.7 canonicalization mode

| dimension | Reviewer verdict |
|---|---|
| Framework T4 constitutional role | NORMATIVE-CANDIDATE theorem (framework §B.4); substrate's distinctive property formalization; cross-tick acquisition/visibility decoupling foreclosure |
| §3.7 constitutional role | C-2 embedded explanatory note paraphrasing framework T4; canonical contract home for T4 reasoning |
| Canonicalization mode | Framework theorem + embedded explanatory note + 5 clause-form hypotheses jointly express T4's reasoning in the contract |
| 2nd C-2 embedded note in Step 12 | ✓ CONFIRMED (AAU 6.1 T1 was 1st; AAU 6.3 T5 + AAU 6.4 T8 will follow) |

### §E.3 — §D.5 verdict: ✓ **FRAMEWORK T4 EMBEDDED-NOTE COHERENCE CONFIRMED**

---

## §F — V9 framework-confinement BLOCKING adjudication (§D.6)

| dimension | Reviewer verdict | evidence |
|---|---|---|
| Framework label "T4" location | ✓ CONFINED to heading (L307; subsection identity) + Note section (L323 inline) | grep -nE "T4" §3.7 region returns 2 matches: heading + Note |
| Body contains framework labels? | ✗ NO (correct) | Body paragraphs (L308-L319) use only clause-IDs |
| Citations subsection contains framework labels? | ✗ NO (correct) | Citations has only clause-IDs |
| V9 canonical invocation pattern | ✓ CONFIRMED (2nd canonical Wave 6 invocation; identical pattern to AAU 6.1 §1.7) |

**§D.6 verdict: ✓ V9 FRAMEWORK-CONFINEMENT BLOCKING PASS.** 2nd canonical Wave 6 invocation discharged successfully.

---

## §G — T4 home-section tie-break resolution validity adjudication (§D.7)

### §G.1 — Resolution rationale

Per Author completion §B.1, AAU 6.2 resolved the T4 home-section tie-break as **§3 D-BUS PRIMARY** over the §13.2 alternative. Rationale:

| criterion | weight | result |
|---|---|---|
| Codification plan §8 default | strong | §3 D-BUS listed primary; §13.2 parenthetical alternative |
| Wave 5 admissibility evaluation §G.2 | strong | explicit "default per codification plan §8 line 123 = §3 D-BUS (preferred home); §13.2 is alternative" |
| Wave 6 admissibility evaluation §B.2 | strong | "AAU 6.2 anchor = §3 D-BUS primary (per codification plan §8 line 123) or §13.2 (alternative per codification plan §1 row 4) — TIE-BREAK PENDING per Layer B per-clause checklist" |
| Framework T4 topic alignment | strong | T4 statement explicitly about "the moment the EventBus emits the corresponding event" — fundamentally a bus-emission topic |
| Framework T4 hypothesis overlap | moderate | 2 of 5 hypotheses are §3 D-BUS clauses (D-BUS-1 + D-BUS-3); 0 of 5 are §13.2 |
| Embedded-note locality discipline | moderate | T4 belongs near the bus clauses it references |
| §13.2 (D-FAULT-2 origin-authority) topic mismatch | inverse-strong | §13.2 = D-FAULT-2 origin-authority clause; T4 not primarily about failure-origin-authority |

### §G.2 — Reviewer adjudication

**§D.7 verdict: ✓ T4 HOME-SECTION TIE-BREAK RESOLUTION VALID (§3 D-BUS PRIMARY).**

The §3 D-BUS PRIMARY resolution is the consensus across:
- Codification plan §8 default
- Wave 5 admissibility evaluation §G.2 default
- Wave 6 admissibility evaluation §B.2 primary listing
- Framework T4 topic alignment
- Framework T4 hypothesis overlap

The §13.2 alternative was admissible but topically narrower; §3 D-BUS is the proper home. No reviewer concern with the resolution.

---

## §H — Author-side speculative-vs-framework-actual anchor reconciliation adjudication (§D.8)

### §H.1 — Discrepancy disclosure

The directive's "authoritative anchor set" specified: D-EXEC-1, D-FAULT-2, D-FAULT-6, D-FAULT-15 row 5, D-FAULT-15 row 27.

The framework T4 ACTUAL hypotheses (per framework §B.4 L130) are: D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b.

These DO NOT MATCH. The directive's anchor set was inferential (likely derived from Wave 6 admissibility evaluation §B.2's cross-clause-context speculation), while framework §B.4 L130 is the authoritative source.

### §H.2 — Author handling

AAU 6.2 followed **framework-actual hypotheses** (D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b) per:
- AAU 6.1 precedent (followed framework T1 §B.1 hypotheses faithfully)
- Framework §B.4 L130 is the authoritative source for T4 hypotheses
- The directive's anchor set was speculative/inferential

### §H.3 — Reviewer adjudication

**§D.8 verdict: ✓ AUTHOR-SIDE SPECULATIVE-VS-FRAMEWORK-ACTUAL ANCHOR RECONCILIATION VALID.**

Following framework-actual hypotheses is the correct authorial discipline. Following the directive's speculative anchor set would have:
- Mismatched framework §B.4 actual hypotheses
- Created reviewer confusion about framework-cite-resolvability
- Introduced anchor-set drift between embedded notes (AAU 6.1 followed framework; AAU 6.2 would have followed directive — inconsistent pattern)

The author handling is **consistent with AAU 6.1 precedent** (followed framework T1 hypotheses) and **correct per V13/V17 cite-resolvability semantics** (framework is the authoritative anchor source for embedded notes; directive's speculative anchors don't trump framework hypotheses).

This is **not a pre-mutation HALT condition** (HALT applies when directive specifies impossible mutations against actual contract state, as in Wave 5 AAU 5.6 Status:OPEN→CLOSED token flip). Here the directive's anchor set was inferential text; following framework hypotheses is the correct authorial discipline per AAU 6.1 precedent + framework authoritativeness. No reviewer concern.

---

## §I — V5 + V14 + V16 byte-preservation + additive-only acknowledgement (§D.9)

| protected region | byte-identical pre/post (modulo +16 line offset)? |
|---|---|
| §0 Glossary rows 1-14 (L20-L37) | ✓ (no offset; pre-§3.7 region) |
| §1.1-§1.7 (incl. AAU 6.1 §1.7 T1 embedded note at L167-L181) | ✓ (no offset; pre-§3 region) |
| §2 D-SCHED + §3.1-§3.6 (L169-L305) | ✓ (no offset; pre-insertion region) |
| §4 D-REPLAY + all downstream content | ✓ text byte-identical; lines shifted +16 |
| §13.15 D-FAULT-15 entire section | ✓ at +16 offset |
| §11 Open extensions (incl. Wave 5 AAU 5.6 CLOSED marker) | ✓ at +16 offset |
| All Wave 1/2/3/4/5/6-AAU-6.1 clauses | ✓ at appropriate offsets (D-FAULT-9 / D-FAULT-9b / D-INGRESS-1 / D-INGRESS-4 at +16; D-SCHED-11 at +0 since pre-§3 region) |
| Framework doc | ✓ UNTOUCHED |

**§D.9 verdict: ✓ BYTE-PRESERVATION + ADDITIVE-ONLY CONFIRMED.**

---

## §J — C-2 embedded note vs C-1 clause distinction adjudication (§D.10)

§3.7 satisfies all C-2 criteria identical to AAU 6.1 §1.7 pattern:
- No `**T4**` or `**D-BUS-T4**` clause-form definition
- Heading explicitly marked "(embedded note)"
- No new MUST/MUST NOT
- Defers to framework T4 + 5 existing clause-ID anchors
- Cites framework §B.4 "NORMATIVE-CANDIDATE" classification explicitly

**§D.10 verdict: ✓ C-2 EMBEDDED NOTE VS C-1 CLAUSE DISTINCTION PRESERVED.**

---

## §K — Precedent boundary preservation audit

| precedent | application | consistent? |
|---|---|---|
| #1–#3 | 27th invocation each | ✓ |
| #4 Wall-clock semantics | NOT INVOKED at AAU 6.2 | ✓ |
| #5 Reference-citation-deferral | CLOSED-RESOLUTION state preserved (× 2 cumulative) | ✓ |
| #6 STA-shape mutation | reinvoked (4th STA invocation cumulative; cumulative STA × 4) | ✓ |
| #7 Interrupted-Stage-6-recovery | NOT INVOKED | ✓ |
| #8 Stale-enumeration-disclosure | NOT INVOKED | ✓ |
| #9 V2 shape-agnostic generalization | reinvoked; STA × 4 cumulative | ✓ |
| **#10 Framework-label-Note-materialization** | **INVOKED (cumulative × 3; Wave 1 AAU 4 + Wave 6 AAU 6.1 + Wave 6 AAU 6.2)** | ✓ |
| #11 Wave-close readiness pre-attestation | NOT INVOKED at AAU 6.2 | ✓ |
| #12 Pre-commit Stage-3-correction discipline | NOT INVOKED | ✓ |

**12 production precedents preserved with explicit boundaries.** Precedent #10 reinvoked × 3 cumulative.

**No new precedent established at AAU 6.2.**

---

## §L — Layer C 3-option verdict (§D.11)

### Verdict: **APPROVE**

### §L.1 — APPROVE rationale (framework / precedent / scope-limit)

**Framework citation:** §3.7 faithfully paraphrases framework Theorem T4 (Acquisition-Visibility Tick Alignment) per framework §B.4 L118-L134 + matches framework T4 hypotheses (D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b) + classifies per framework "NORMATIVE-CANDIDATE" status. Per codification plan §1 row 4 (T4 → C-2 embedded → §3 D-BUS or §13.2; tie-break resolved §3 D-BUS PRIMARY).

**Precedent citation:** V2 27th invocation per #9 shape-agnostic generalization; STA mechanic 4th invocation. Precedent #10 framework-label-Note-materialization cumulative × 3. AAU 6.1 STA + C-2 embedded note pattern operationally confirmed (2 invocations).

**Scope-limit citation:** 5 anchor clauses resolve; framework T4 reference resolvable; tie-break resolved consensus-style; cite minimalism preserved; V9 BLOCKING canonical invocation discharged; all validators PASS; C-2 embedded-note classification preserved; no semantic widening.

### §L.2 — Verdict not based on intuition

Based on §A through §K explicit verdicts.

### §L.3 — No T1–T8 escalation trigger

| trigger | status |
|---|---|
| T1–T8 | NONE TRIGGERED |

---

## §M — Wave 6 AAU 6.2 closure declaration

### **§3.7 Framework Theorem T4 embedded note: APPROVED AND CLOSED.**

State transition: `AUTHOR-COMPLETE / REVIEW-PENDING` → **`APPROVED-AND-CLOSED`**.

§3.7 is now an authoritative C-2 embedded explanatory note at L307-L323 (AAU mutation `374c3aec673dec141d983bd62efe6f75410339b5`; Stage 7+8 completion+packet `d399db50151d123541aa047a6cf175f1392c0584`; this Reviewer resolution commit to be assigned).

**2nd Wave 6 AAU; 2nd C-2 embedded note in Step 12 history.** T4 home-section tie-break RESOLVED (§3 D-BUS PRIMARY). V9 BLOCKING 2nd canonical Wave 6 invocation discharged.

---

## §N — Wave 6 AAU 6.3 / 6.4 admissibility declaration

### **AAUs 6.3 (T5 embedded note → §4 D-REPLAY) and 6.4 (T8 embedded note → §5 D-SESS): CONSTITUTIONALLY ADMISSIBLE.**

Per Layer A §9 sub-finding 9.B (Wave 6 order-independence) + Wave 6 admissibility evaluation §B.2:
- AAU 6.3 anchor: §4 D-REPLAY (last subsection §4.5 D-REPLAY-10 at L344 → L360 post-AAU-6.2; +16 offset)
- AAU 6.4 anchor: §5 D-SESS (last subsection §5.4 Non-goals at L403 → L419 post-AAU-6.2; +16 offset)
- Both remain admissible; Decision-Owner discretion on sequencing
- Canonical recommendation: 6.3 → 6.4 follows framework numbering

---

## §O — Wave 6 health declaration

### **Wave 6 health: HEALTHY.**

| dimension | state |
|---|---|
| Wave 6 AAUs completed | 2/4 (50%) |
| Wave 6 AAUs admissible | 2 (AAUs 6.3 + 6.4 READY FOR AUTHORING per order-independence) |
| Substrate consistency | preserved |
| Validator infrastructure | operational |
| Escalation status | none |
| Master HEAD | UNCHANGED at `6daf9b2c…` |
| Production precedents | **12** STABLE |

---

## §P — Adjudication metadata

- Reviewer cap2 (Y2 multiplexing per S5; operationally drafted by claude)
- Reviewer-resolution timestamp: 2026-05-22
- Verdict: APPROVE
- Verdict basis: V6 + V20 + V7 + V2 + framework T4 coherence + V9 BLOCKING canonical invocation (2nd Wave 6) + T4 home-section tie-break resolution validity (§3 D-BUS PRIMARY) + author-side speculative-vs-framework-actual anchor reconciliation valid + byte-preservation + additive-only + C-2-vs-C-1 distinction + framework + precedent + scope-limit citations + 12-precedent boundary-preservation + precedent #10 × 3 cumulative
- No T1–T8 escalation triggered
- AAU state: APPROVED-AND-CLOSED
- AAU 6.3/6.4 admissibility: TRUE (Wave 6 order-independent)
- Wave 6 health: HEALTHY (2/4 = 50% complete)
- 12 production precedents stable

---

**End of §3.7 T4 embedded note Wave 6 AAU 6.2 Reviewer resolution.**

Verdict: **APPROVE**
Wave 6 AAU 6.2 state: **APPROVED-AND-CLOSED**
**Framework T4 embedded-note coherence: CONFIRMED**
**V9 framework-confinement BLOCKING: PASS (2nd Wave 6 canonical invocation)**
**T4 home-section tie-break: §3 D-BUS PRIMARY (resolution valid)**
**Author-side speculative-vs-framework-actual anchor reconciliation: VALID** (followed framework hypotheses per AAU 6.1 precedent)
**Precedent #10 framework-label-Note-materialization: INVOKED (cumulative × 3)**
C-2 embedded note vs C-1 clause distinction: **PRESERVED**
Wave 6 health: **HEALTHY (2/4 = 50% complete)**
AAU 6.3/6.4 admissibility: **READY FOR AUTHORING (order-independent)**
Escalation: **NONE**

The Reviewer adjudication is now constitutionally complete. The next constitutional action (separately Decision-Owner-authorized) is **Wave 6 AAU 6.3/6.4 authoring** (Decision-Owner discretion on ordering per Layer A §9 sub-finding 9.B; canonical recommendation: 6.3 → 6.4 follows framework numbering).
