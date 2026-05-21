# AAU Wave 5 / AAU 5.4 — §0 Glossary `Drain Epoch` Review Packet

**Filing status:** Stage 7 per Layer C §S7; immutable per Layer D §20. Author claude (Y2); Reviewer cap2 (Y2 multiplexing). **FIRST glossary row to cite FRAMEWORK references (T3, L1) instead of contract clause-IDs.**

---

## §A — AAU summary

| field | value |
|---|---|
| Wave | 5 |
| AAU number | 4 of 6 |
| Clause / row | §0 Glossary entry `Drain Epoch` (new row 13 of glossary) |
| Mutation shape | PTA — §0 glossary entry sub-variant (4th invocation) |
| Mutation commit | `dfa0cbe0e179a1140397d74f3ac79e8bad6c3159` |
| Stage 8 completion attestation | `aau_wave5_04_glossary_drain_epoch_completion.md` |
| Pre-AAU contract SHA | `63c18bdd9e13e2263366abb1e2f1f829f18bd764e623ba2cf7a48593e7887806` |
| Pre-AAU contract lines | 1590 |
| Post-AAU contract lines | 1591 |
| Net delta | +1 / -0 |
| Affected location | §0 Glossary; new row at L36 (post-mutation) |
| **Constitutional significance** | **FIRST glossary row to cite FRAMEWORK references (T3, L1) instead of contract clause-IDs; authoritative-observation primitive canonicalization** |

---

## §B — Row verbatim content

```
| **Drain Epoch** | The (`session_id`, `orchestration_tick`) pair at which a Phase A drain processed an envelope. Authoritative-observation primitive (T3, L1). |
```

**Cite breakdown:**

| cite | resolves to | location | type |
|---|---|---|---|
| T3 | Framework Theorem T3 — Phase-A-Only Ingress Observability | `docs/phase_4b_step11_admissibility_framework.md` §B.3 L106 | **FRAMEWORK reference** |
| L1 | Framework Lemma L1 — Drain-Epoch Determinism | `docs/phase_4b_step11_admissibility_framework.md` §C.1 L151 | **FRAMEWORK reference** |

**Critical distinction:** Both cites are framework labels, NOT contract clause-IDs. This is the FIRST occurrence in Step 12 of a glossary row citing framework references in lieu of contract clause-IDs. Constitutional handling justified in completion §B.3.

---

## §C — Author per-AAU validator self-report

| validator | result |
|---|---|
| V1/V3/V4 | ✓ PASS |
| V2/V15 | ✓ PASS (23rd invocation) |
| V5 | ✓ PASS (glossary rows 1-12 SHA `970123b4…` byte-preserved) |
| V6/V7/V20 | ✓ PASS |
| V8 | ✗ NOT APPLICABLE |
| V9 | ✗ NOT APPLICABLE (glossary row has no Note section; V9 scope = clause Note sections) |
| V10/V11 | ✓ PASS |
| V12 | ✗ NOT APPLICABLE (PTA, not SF) |
| V13/V17 | ✓ PASS (T3 + L1 framework refs resolve; new-row count = 1) |
| V14 | ✓ PASS |
| V16 | ✓ PASS |
| V18/V19 | DEFERRED (BLOCKING at Wave-5-close) |

---

## §D — Reviewer adjudication slots (UNFILLED)

### §D.1 — V6 verdict slot
`_________`

### §D.2 — V7 SOFT verdict slot
`_________`

### §D.3 — V20 verdict slot
`_________`

### §D.4 — V2 reuse slot
`_________`

### §D.5 — T3 + L1 framework-reference canonicalization adjudication slot
`_________`

### §D.6 — **FIRST glossary row with framework references — constitutional admissibility** adjudication slot
`_________`

### §D.7 — V9 framework-confinement non-applicability to glossary rows adjudication slot
`_________`

### §D.8 — V5 + V16 byte-preservation + additive-only slot
`_________`

### §D.9 — Layer C 3-option verdict slot (APPROVE / REVISE / ESCALATE)
`_________`

---

## §E — Reviewer focuses (per directive Required Reviewer Adjudication Focuses 1–8)

1. **Authoritative-observation primitive canonicalization validity** — Verify row 13 stabilizes the Drain Epoch concept as the authoritative-observation primitive (per L1) without modifying or widening any clause-level semantics. The L1 Classification explicitly states "L1 names the drain epoch as the unique authoritative-observation primitive."

2. **T3 + L1 framework-reference resolvability** — Confirm both framework references exist and are stable: T3 (framework §B.3 L106 Theorem — Phase-A-Only Ingress Observability); L1 (framework §C.1 L151 Lemma — Drain-Epoch Determinism). Framework doc untouched in Wave 5 window.

3. **Drain-processing epoch ontology stabilization** — Confirm row formalizes `(session_id, orchestration_tick)` as the canonical drain-epoch tuple. The framework L1 statement constructs K_drain(E) as the unique orchestration_tick at which envelope E was drained; pair with session_id for cross-session disambiguation.

4. **Phase-A drain identity canonicalization** — Confirm row reinforces that drain occurs at Phase A only (per L1's "Phase A of `session.step(K_drain(E))`"). Reinforces D-INGRESS-2 Phase-A-only-pull discipline (positive complement; not cited per cite minimalism).

5. **Replay-authoritative observation vocabulary stabilization** — Confirm row 13 introduces NO new authority surface; Drain Epoch's role as the *replay-meaningful* observation primitive (per L1 Classification: "the only sense in which 'when did the envelope arrive' is replay-meaningful. The wall-clock arrival instant is non-authoritative") is preserved. This sits as positive complement to Wave 4 wall-clock-foreclosure rows 34 + 38.

6. **FIRST glossary row with FRAMEWORK references — constitutional admissibility** — This is the FIRST Step 12 glossary row to cite framework labels (T3, L1) instead of contract clause-IDs. Constitutional handling per completion §B.3:
   - Row text is verbatim from codification plan §5 L89
   - Drain Epoch is a framework-defined primitive (no in-contract clause names it); contract substrate's authoritative-observation surface is named at glossary level deferring to framework derivation
   - Glossary-non-normative convention (§0 header) bounds the semantic surface; framework references don't introduce normative content
   - Precedent #10 (framework-label-Note-materialization, Wave 1 AAU 4 D-REPLAY-10) NOT INVOKED — applies to clause bodies with Citations Reference subsections; glossary rows have neither
   - No new precedent invocation required — Layer A §7 PTA-§0-glossary-row sub-variant + precedent #9 V2 shape-agnostic generalization cover this AAU
   - Wave 5 admissibility evaluation §G.2 anticipated this exact case

7. **V9 framework-confinement non-applicability to glossary rows** — V9 (framework-ref Note-section confinement BLOCKING) applies to clause bodies that have Note section structures. Glossary rows are non-normative single-line table rows with no Note section. V9 does NOT mechanically apply to glossary rows; the glossary-non-normative convention bounds the semantic surface instead.

8. **Additive-only + byte-preservation integrity** — Confirm:
   - 1 insertion / 0 deletions
   - Glossary rows 1-12 SHA `970123b4…` byte-identical pre/post
   - AAU 5.1/5.2/5.3 rows (L33/L34/L35) byte-identical
   - D-INGRESS-1/-2/-3 / D-FAULT-15 rows 34/38 / Wave 1+2+3+4 clauses all byte-preserved
   - §11 byte-preserved (heading shifted L658→L659)
   - Framework T3/L1 byte-preserved (framework doc untouched)

---

## §F — Cross-clause + framework coherence reference

| dimension | content |
|---|---|
| Framework Theorem T3 (§B.3 L106) | "Phase-A-Only Ingress Observability" — every envelope observation is via Phase-A drain at deterministic orchestration_tick |
| Framework Lemma L1 (§C.1 L151) | "Drain-Epoch Determinism" — unique K_drain(E) such that Phase A of session.step(K_drain(E)) is the tick at which E was drained; replay-stable |
| L1 Classification (L165) | "L1 names the drain epoch as the unique authoritative-observation primitive. Under pre-queue, K_drain(E) is implicit in the trace; under live ingress, the same K_drain(E) is the only sense in which 'when did the envelope arrive' is replay-meaningful. The wall-clock arrival instant is non-authoritative." |
| D-INGRESS-2 (§14.4) | positive complement — Phase-A-only-pull discipline; underwrites T3 in the contract |
| D-FAULT-15 row 34 (Wave 4) | positive complement — wall-clock arrival timestamp FORBIDDEN; reinforces L1's "wall-clock arrival instant is non-authoritative" |
| D-FAULT-15 row 38 (Wave 4) | positive complement — PAUSED wall-clock blocking FORBIDDEN |
| AAU 5.1 row 10 (OperatorEnvelope) | sibling Wave 5 glossary entry: the envelope type Drain Epoch observes |
| AAU 5.2 row 11 (Channel) | sibling Wave 5 glossary entry: the storage Drain Epoch's drain extracts from |
| AAU 5.3 row 12 (Pull) | sibling Wave 5 glossary entry: the operation that occurs at the Drain Epoch |
| Row 13 (this AAU) | Drain Epoch canonicalization: the orchestration_tick at which Pull processed an envelope; authoritative-observation primitive |

**Wave 5 ingress-observation quaternary (after AAU 5.4):**

| primitive | role | glossary row |
|---|---|---|
| OperatorEnvelope | unit (what is transferred) | row 10 (AAU 5.1) |
| Channel | storage (where it sits) | row 11 (AAU 5.2) |
| Pull | extraction (how it leaves) | row 12 (AAU 5.3) |
| Drain Epoch | observation (when it is observed) | row 13 (AAU 5.4) |

The quaternary covers the complete ingress-and-observation surface: WHAT × WHERE × HOW × WHEN.

---

## §G — Anchor + diff verification

### §G.1 — Pre-mutation file SHA-256
`63c18bdd9e13e2263366abb1e2f1f829f18bd764e623ba2cf7a48593e7887806`

### §G.2 — Pre-mutation anchor line (Pull row at L35)
```
| **Pull** | Atomic snapshot operation at start of Phase A by which the session captures the channel's current buffer (D-INGRESS-2, D-INGRESS-3). |
```

### §G.3 — Pre-mutation `Drain Epoch` glossary row non-existence
- `grep -cF '| **Drain Epoch** |'` = 0
- `grep -cF 'Drain Epoch'` = 0 (no prior occurrence in contract)

### §G.4 — Post-mutation row
- New row at L36; `grep -cF '| **Drain Epoch** |'` = 1

### §G.5 — Existing-text byte preservation
- Glossary rows 1-12 (L20-L35) SHA `970123b4336eb72e2010954af6f884c38ed9e33a3823a88a9d1e0cd96b4bb930` byte-identical
- AAU 5.1 (L33) + 5.2 (L34) + 5.3 (L35) glossary rows: byte-identical
- D-INGRESS-1/-2/-3: byte-identical
- D-FAULT-15 rows 1-42: byte-identical
- §11 heading (L659 post-mutation): text byte-identical
- Framework T3 (§B.3 L106): byte-identical (framework doc untouched)
- Framework L1 (§C.1 L151): byte-identical
- Glossary terminator `---` at L38 post-mutation (offset +1)
- §1 heading at L40 post-mutation (offset +1)

### §G.6 — Diff summary
- 1 file changed; 1 insertion / 0 deletions; Property A3 preserved

---

## §H — Adjudication metadata

- Author claude (Y2 drafting under cap2 direction)
- Review packet timestamp: 2026-05-22
- §D adjudication slots: UNFILLED in this packet
- Reviewer to consult: framework T3 at `docs/phase_4b_step11_admissibility_framework.md` §B.3 L106; framework L1 at §C.1 L151; codification plan §5 L89 for source provenance; Wave 5 admissibility evaluation §G.2 for anticipated handling

---

**End of §0 Glossary `Drain Epoch` Wave 5 AAU 5.4 Review Packet.**

AAU state at packet authoring: **AUTHOR-COMPLETE / REVIEW-PENDING**
**Constitutional significance: 4th §0 glossary PTA sub-variant invocation; FIRST glossary row to cite FRAMEWORK references (T3, L1) instead of contract clause-IDs; authoritative-observation primitive canonicalization**
Layer C 3-option verdict (Reviewer-filled, separate artifact): `_________`
