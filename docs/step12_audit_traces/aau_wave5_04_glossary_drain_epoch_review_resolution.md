# AAU Wave 5 / AAU 5.4 — §0 Glossary `Drain Epoch` Reviewer Resolution

**Filing status:** authored at Reviewer adjudication time per Layer C §19 schema; supersedes REVIEW-PENDING state of `aau_wave5_04_glossary_drain_epoch_review_packet.md` §D adjudication slots. **FIRST glossary row to cite FRAMEWORK references (T3, L1) instead of contract clause-IDs in Step 12 history.**

**Authoring authority.** Reviewer cap2 (Y2 multiplexing per S5). Operationally drafted by claude under cap2's direction. cap2 retains adjudication authority.

**Role-separation invariant note.** Per Y2 §S5 + Layer D §10: Author (claude) ≠ Reviewer (cap2). This adjudication closes AAU 5.4 and admits AAU 5.5 (Ingress Observation Event glossary entry).

---

## §A — V6 manual checklist

§0 Glossary row inspected at contract L36 (HEAD `626ff3b`):

```
| **Drain Epoch** | The (`session_id`, `orchestration_tick`) pair at which a Phase A drain processed an envelope. Authoritative-observation primitive (T3, L1). |
```

| check | result | rationale |
|---|---|---|
| Row states a definition only | ✓ PASS | pure paraphrase deferring to framework T3 + L1 |
| No operational consequences | ✓ PASS | glossary non-normative per §0 convention |
| No implementation details | ✓ PASS | only constitutional vocabulary ("(session_id, orchestration_tick) pair", "Phase A drain", "envelope", "authoritative-observation primitive") |
| No derivation chains | ✓ PASS | two direct framework references; no transitive citation walking |
| No hedging | ✓ PASS | "(T3, L1)" framework-label parenthetical follows existing glossary citation convention |
| Glossary row format consistent | ✓ PASS | `\| **term** \| definition. \|` table format preserved |

**V6 verdict: ✓ PASS.**

---

## §B — V20 normative-consistency checklist

| check | result | rationale |
|---|---|---|
| No new MUST contradicts existing MUST NOT | ✓ PASS | row paraphrases framework L1; no contradiction with D-INGRESS-2 or D-FAULT-15 rows 34/38 |
| No new admittance contradicts foreclosure | ✓ PASS | no admittance introduced; Drain Epoch is the *authoritative* observation primitive (T3, L1); wall-clock observation is foreclosed by rows 34/38 |
| Cite minimalism convention preserved | ✓ PASS | T3 + L1 framework references enumerated only; D-INGRESS-2 (Phase-A-pull positive complement) + D-FAULT-15 rows 34/38 (wall-clock foreclosure positive complements) NOT enumerated |
| Scope consistent with citation chain transitive closure | ✓ PASS | T3 (Phase-A-Only Ingress Observability) + L1 (Drain-Epoch Determinism) jointly imply Drain Epoch as the unique authoritative-observation primitive |
| Row does NOT widen any contract clause | ✓ PASS | framework references; no clause-level invariant introduced |
| Row preserves wall-clock-foreclosure pattern | ✓ PASS | "Authoritative-observation primitive" complements rows 34+38 wall-clock-foreclosure (precedent #4) at glossary level |
| Row preserves AAU 5.1/5.2/5.3 coherence | ✓ PASS | "Phase A drain processed an envelope" links to Channel storage (5.2) + Pull extraction (5.3) + OperatorEnvelope unit (5.1) |
| Glossary remains non-normative per §0 header | ✓ PASS |

**V20 verdict: ✓ PASS.**

---

## §C — V7 SOFT banned-phrase verdict

| check | result |
|---|---|
| Banned phrases | ✓ PASS (0 occurrences) |

**V7 verdict: ✓ PASS.**

---

## §D — V2 PROCEED-SUBSTANTIVE reuse assessment (twenty-third invocation; fourth under PTA-§0-glossary-row sub-variant)

**✓ YES.** Per #9 shape-agnostic generalization. PTA-§0-glossary-row sub-variant stable across 4 invocations.

**Cumulative V2 invocations: 23** (FII × 4 + STA × 2 + PTA × 17).

---

## §E — T3 + L1 framework-reference canonicalization adjudication (§D.5)

### §E.1 — Validity audit

| dimension | Reviewer verdict | evidence |
|---|---|---|
| Framework Theorem T3 (Phase-A-Only Ingress Observability) | ✓ EXISTS at framework §B.3 L106 | byte-preserved (framework doc untouched in Wave 5 window) |
| Framework Lemma L1 (Drain-Epoch Determinism) | ✓ EXISTS at framework §C.1 L151 | byte-preserved |
| L1 Classification (L165) | ✓ "L1 names the drain epoch as the unique authoritative-observation primitive" — directly supports row 13 phrase | byte-preserved |
| D-INGRESS-2 (Phase-A-only-pull positive complement) byte-preserved | ✓ CONFIRMED |
| D-FAULT-15 rows 34+38 (wall-clock-foreclosure positive complements) byte-preserved | ✓ CONFIRMED |
| AAU 5.1 + 5.2 + 5.3 glossary rows byte-preserved | ✓ CONFIRMED |
| Row 13 introduces NO new normative surface | ✓ CONFIRMED |
| Row 13 paraphrases L1 K_drain(E) construction faithfully | ✓ CONFIRMED ("(session_id, orchestration_tick) pair" = L1's K_drain(E) extended with session_id) |
| Row 13 paraphrases T3 Phase-A-only-observation faithfully | ✓ CONFIRMED ("at which a Phase A drain processed an envelope") |
| Cite-set distinction preserved | ✓ CONFIRMED |
| Glossary non-normative convention preserved | ✓ CONFIRMED |

### §E.2 — Framework-reference canonicalization mode

| dimension | Reviewer verdict |
|---|---|
| T3 constitutional role | Framework theorem: Phase-A-Only Ingress Observability (NORMATIVE-CANDIDATE per framework §B.3 classification) |
| L1 constitutional role | Framework lemma: Drain-Epoch Determinism (NORMATIVE-CANDIDATE per framework §C.1 classification; L165 names drain epoch as authoritative-observation primitive) |
| Row 13 constitutional role | Non-normative glossary canonicalization deferring to framework T3 + L1 |
| Canonicalization mode | Framework theorem + framework lemma (analytical) + glossary-form term entry (non-normative) jointly express Drain Epoch's identity |
| FIRST glossary row with framework references in Step 12 | ✓ CONFIRMED |

### §E.3 — §D.5 verdict: ✓ **T3 + L1 FRAMEWORK-REFERENCE CANONICALIZATION COHERENT**

Row 13 is constitutionally clean:
- Framework T3 + L1 byte-preserved + resolvable
- L1 Classification (L165) directly supports "Authoritative-observation primitive" phrasing
- Row paraphrases L1 K_drain(E) + T3 Phase-A-only observability
- D-INGRESS-2 + rows 34/38 positive complements byte-preserved
- AAUs 5.1/5.2/5.3 byte-preserved
- Cite minimalism preserved
- Glossary non-normative convention preserved

---

## §F — FIRST glossary row with framework references — constitutional admissibility adjudication (§D.6)

### §F.1 — Constitutional admissibility analysis

This is the FIRST Step 12 glossary row to cite framework labels (T3, L1) in lieu of contract clause-IDs. Constitutional admissibility rests on:

| dimension | analysis | verdict |
|---|---|---|
| Source provenance | Row text verbatim from `docs/phase_4b_step11_codification_plan.md` §5 L89 | ✓ canonical |
| Pre-existence of framework references in Step 12 prior waves | YES — Wave 1 AAU 4 D-REPLAY-10 cited framework Lemma L4 in Note section (precedent #10 framework-label-Note-materialization) | ✓ framework references are an established constitutional category |
| Glossary-row structural context | Glossary rows are non-normative table rows with no Note section structure; framework labels appear inline in the entry text | ✓ structurally distinct from clause-Note context |
| V9 framework-confinement (Layer B §6.9) | V9 confines framework references to clause Note sections; mechanism doesn't apply to glossary rows (no Note section structure) | ✓ V9 boundary preserved (non-applicability, not violation) |
| Precedent #10 (framework-label-Note-materialization) | Applies to clause bodies with Citations Reference subsections that are omitted; glossary rows have neither | ✓ NOT INVOKED; boundary preserved |
| Glossary-non-normative convention (§0 header) | §0 header reads "Glossary" not "Invariants"; glossary entries are paraphrases or references, not invariants | ✓ semantic surface bounded |
| Drain Epoch concept origin | Framework Lemma L1 ORIGINATES the Drain Epoch concept (framework §C.1 L165: "L1 names the drain epoch as the unique authoritative-observation primitive"); no in-contract clause names Drain Epoch | ✓ framework is the canonical source |
| Wave 5 admissibility evaluation §G.2 | Anticipated this exact case: "AAU 5.4 cross-clause context: row 13 of §0 glossary cites framework Theorem T3 (Phase-A-Only Ingress Observability) + framework Lemma L1 (likely orchestration_tick atomicity); these are FRAMEWORK references, not contract clause-IDs" | ✓ pre-anticipated; not surprise content |

### §F.2 — Anticipated new precedent question

Does AAU 5.4 establish a NEW precedent: "Glossary-row framework-reference admittance"?

**Reviewer verdict: NO new precedent.** This handling is operationally derivable from:
- Layer A §7 PTA-§0-glossary-row sub-variant (mechanic-level cover)
- Precedent #9 V2 shape-agnostic generalization (shape-mechanic continuity)
- Glossary-non-normative convention (§0 header; existing convention, not new)
- V9 scope boundary (clause Note sections, NOT glossary rows; existing boundary, not new)

The handling is a CONSEQUENCE of existing precedents applied to glossary-row context. No new precedent invocation required. 12 production precedents remain stable.

### §F.3 — §D.6 verdict: ✓ **FIRST GLOSSARY ROW WITH FRAMEWORK REFERENCES CONSTITUTIONALLY ADMISSIBLE; NO NEW PRECEDENT ESTABLISHED**

---

## §G — V9 framework-confinement non-applicability adjudication (§D.7)

V9 (Layer B §6.9) mechanically confines framework references to clause Note sections in the contract body. The mechanism interrogates: "for each framework label in a clause body, is the framework label inside the clause's Note section?"

Glossary rows have NO Note section structure. The mechanism's predicate is undefined for glossary rows. V9 is therefore **NOT MECHANICALLY APPLICABLE** to glossary rows. This is a boundary preservation (the V9 mechanism applies precisely where its predicate is defined), NOT a violation.

The semantic surface for glossary rows is bounded by:
1. **§0 header convention** — "Glossary" not "Invariants"; entries are paraphrases/references, not normative content
2. **Layer A §7 PTA-§0-glossary-row sub-variant** — append-only mechanism; existing rows byte-preserved
3. **V14 byte-preservation BLOCKING** — existing-text immutability
4. **Cite minimalism convention** — citations enumerate only structural anchors

**§D.7 verdict: ✓ V9 FRAMEWORK-CONFINEMENT NON-APPLICABILITY TO GLOSSARY ROWS CONFIRMED.** Glossary-non-normative convention bounds the semantic surface in place of V9's clause-Note-section mechanism.

---

## §H — V5 + V16 byte-preservation + additive-only acknowledgement (§D.8)

### §H.1 — V5 glossary rows 1-12 byte preservation

| block | SHA-256 |
|---|---|
| §0 Glossary rows 1-12 (L20–L35) | `970123b4336eb72e2010954af6f884c38ed9e33a3823a88a9d1e0cd96b4bb930` byte-identical |

### §H.2 — Cross-wave + cross-corpus clause byte-preservation

| clause | wave | byte-identical? |
|---|---|---|
| D-FAULT-6b / 6c / SCHED-14 / REPLAY-10 | Wave 1 | ✓ |
| §14 D-INGRESS (D-INGRESS-1/-2/-3/-5/-7) | Wave 2 | ✓ |
| D-FAULT-9a / 9b / 9c | Wave 3 + pre-Step-12 | ✓ |
| D-FAULT-15 rows 31–42 (incl. rows 34/38 wall-clock-foreclosure) | Wave 4 | ✓ |
| AAU 5.1 OperatorEnvelope + 5.2 Channel + 5.3 Pull rows | Wave 5 | ✓ |
| D-FAULT-9 / D-EXEC-13a / D-FAULT-15 #27 / D-FAULT-14 / D-SESS-1/-4/-5 / D-TRACE-2 / D-FORBID-1/-6/-11/-12 / D-SCHED-1/-3/-11/-14 | pre-Step-12 | ✓ |
| §11 Open extensions (items 1-4) | pre-Step-12 | ✓ |
| Framework Theorem T3 (§B.3 L106) | framework | ✓ (framework doc untouched) |
| Framework Lemma L1 (§C.1 L151) | framework | ✓ |

### §H.3 — V16 additive-only

- 1 file modified; 1 insertion / 0 deletions; Property A3 preserved

**§D.8 verdict: ✓ BYTE-PRESERVATION + ADDITIVE-ONLY CONFIRMED.**

---

## §I — Precedent boundary preservation audit

| precedent | application | consistent? |
|---|---|---|
| #1–#3 | 23rd invocation each | ✓ |
| #4 Wall-clock semantics | NOT directly INVOKED at AAU 5.4 (row is positive complement to wall-clock foreclosure via authoritative-observation framing; no foreclosure introduced) | ✓ boundary preserved |
| #5 Reference-citation-deferral | CLOSED-RESOLUTION state preserved | ✓ |
| #6 STA-shape mutation | NOT INVOKED in Wave 5 | ✓ |
| #7 Interrupted-Stage-6-recovery | NOT INVOKED | ✓ |
| #8 Stale-enumeration-disclosure | NOT INVOKED | ✓ |
| #9 V2 shape-agnostic generalization | reinvoked; PTA × 17 cumulative | ✓ |
| #10 Framework-label-Note-materialization | NOT INVOKED at AAU 5.4 (precedent applies to clause bodies with Citations Reference subsections; glossary rows have neither) | ✓ boundary preserved |
| #11 Wave-close readiness pre-attestation | NOT INVOKED at AAU 5.4 | ✓ |
| #12 Pre-commit Stage-3-correction discipline | NOT INVOKED | ✓ |

**12 production precedents preserved with explicit boundaries.** No new precedent established at AAU 5.4 (FIRST glossary row with framework references is operational consequence of existing precedents applied to glossary-row context; see §F.2).

---

## §J — Layer C 3-option verdict (§D.9)

### Verdict: **APPROVE**

### §J.1 — APPROVE rationale (framework / precedent / scope-limit)

**Framework citation:** Row 13 faithfully formalizes `docs/phase_4b_step11_codification_plan.md` §5 L89 verbatim + canonicalizes Drain Epoch per framework Theorem T3 (Phase-A-Only Ingress Observability) + framework Lemma L1 (Drain-Epoch Determinism). L1 Classification (framework L165) explicitly states "L1 names the drain epoch as the unique authoritative-observation primitive."

**Precedent citation:** V2 23rd invocation per #9 shape-agnostic generalization. PTA-§0-glossary-row sub-variant 4th invocation. Framework-reference handling derives from Layer A §7 PTA mechanic + precedent #9 + glossary-non-normative convention; no new precedent required. V9 framework-confinement non-applicability documented (no Note section structure in glossary rows). Precedent #10 NOT INVOKED (boundary preserved).

**Scope-limit citation:** 2 framework cites resolve at framework §B.3 + §C.1; row text verbatim from codification plan §5 L89; cite minimalism preserved; all validators PASS; glossary non-normative convention preserved.

### §J.2 — Verdict not based on intuition

Based on §A through §I explicit verdicts.

### §J.3 — No T1–T8 escalation trigger

| trigger | status |
|---|---|
| T1–T8 | NONE TRIGGERED |

---

## §K — Wave 5 AAU 5.4 closure declaration

### **§0 Glossary `Drain Epoch`: APPROVED AND CLOSED.**

State transition: `AUTHOR-COMPLETE / REVIEW-PENDING` → **`APPROVED-AND-CLOSED`**.

§0 Glossary `Drain Epoch` entry is now an authoritative glossary term at L36 (AAU mutation `dfa0cbe0e179a1140397d74f3ac79e8bad6c3159`; Stage 7+8 completion+packet `626ff3b0727942e24ae5ae7fd7bc7e598e7a17b7`; this Reviewer resolution commit to be assigned).

**FIRST glossary row to cite FRAMEWORK references (T3, L1) instead of contract clause-IDs in Step 12 history.** Constitutional admissibility CONFIRMED; no new precedent established.

---

## §L — Wave 5 AAU 5.5 admissibility declaration

### **§0 Glossary `Ingress Observation Event` entry (Wave 5 AAU 5.5): CONSTITUTIONALLY ADMISSIBLE AND READY FOR AUTHORING.**

Per Layer A §9 sub-finding 9.B + codification plan §5:
- AAU 5.5 anchor = §0 Glossary table; new last row = Drain Epoch (post-AAU-5.4 at L36)
- AAU 5.5 row content (per codification plan §5 L90 verbatim): `| **Ingress Observation Event** | Trace-recorded \`OperatorAbortRequested\` / \`OperatorPauseRequested\` / \`OperatorResumeRequested\` event; the visible authoritative record of an envelope's drain epoch. |`
- AAU 5.5 cross-clause context: row 14 of §0 glossary references event-type names (no clause cite); these are TRACE-RECORD names, not framework or clause references

When Wave 5 AAU 5.5 authoring session begins, Author executes Layer A §15 8-stage protocol under PTA §0-glossary-row sub-variant.

---

## §M — Wave 5 health declaration

### **Wave 5 health: HEALTHY.**

| dimension | state |
|---|---|
| Wave 5 AAUs completed | 4/6 (~67% complete) |
| Wave 5 AAUs admissible | 1 (AAU 5.5 READY FOR AUTHORING) |
| AAU 5.6 SF | NOT yet admissible (gated on AAU 5.5 close per Layer A §9 SF-must-be-final rule) |
| Substrate consistency | preserved |
| Validator infrastructure | operational |
| Escalation status | none |
| Master HEAD | UNCHANGED at `6daf9b2c…` |
| Production precedents | **12** STABLE |

---

## §N — Adjudication metadata

- Reviewer cap2 (Y2 multiplexing per S5; operationally drafted by claude)
- Reviewer-resolution timestamp: 2026-05-22
- Verdict: APPROVE
- Verdict basis: V6 + V20 + V7 + V2 + T3+L1 framework-reference canonicalization + FIRST glossary row with framework references constitutional admissibility + V9 non-applicability + byte-preservation + additive-only + framework + precedent + scope-limit citations + 12-precedent boundary-preservation
- No T1–T8 escalation triggered
- AAU state: APPROVED-AND-CLOSED
- §0 Glossary `Ingress Observation Event` admissibility (AAU 5.5): TRUE
- Wave 5 health: HEALTHY (4/6 = ~67% complete)
- **First glossary row with FRAMEWORK references: CONSTITUTIONALLY ADMISSIBLE; no new precedent established**
- 12 production precedents stable

---

**End of §0 Glossary `Drain Epoch` Wave 5 AAU 5.4 Reviewer resolution.**

Verdict: **APPROVE**
Wave 5 AAU 5.4 state: **APPROVED-AND-CLOSED**
**T3 + L1 framework-reference canonicalization: COHERENT**
**FIRST glossary row with FRAMEWORK references: CONSTITUTIONALLY ADMISSIBLE**
**V9 framework-confinement non-applicability to glossary rows: CONFIRMED**
**No new precedent established**
Wave 5 health: **HEALTHY (4/6 = ~67% complete)**
§0 Glossary `Ingress Observation Event` admissibility (AAU 5.5): **READY FOR AUTHORING**
Escalation: **NONE**

The Reviewer adjudication is now constitutionally complete. The next constitutional action (separately Decision-Owner-authorized) is **Wave 5 AAU 5.5 (§0 Glossary `Ingress Observation Event`) authoring** — trace-record canonicalization (event-type names; no clause cite). After AAU 5.5 closes, AAU 5.6 SF (§11 item 1 → CLOSED) becomes admissible as the FINAL Wave 5 AAU.
