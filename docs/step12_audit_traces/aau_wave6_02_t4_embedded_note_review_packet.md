# AAU Wave 6 / AAU 6.2 — §3.7 Framework Theorem T4 embedded note Review Packet

**Filing status:** Stage 7 per Layer C §S7; immutable per Layer D §20. Author claude (Y2); Reviewer cap2 (Y2 multiplexing). **2nd Wave 6 AAU; 2nd C-2 embedded note; T4 home-section tie-break RESOLVED (§3 D-BUS PRIMARY).**

---

## §A — AAU summary

| field | value |
|---|---|
| Wave | 6 |
| AAU number | 2 of 4 |
| Clause / target | §3.7 Framework Theorem T4 — Acquisition-Visibility Tick Alignment (embedded note) |
| Mutation shape | STA — Section-Tail-Append (4th STA invocation cumulative; 2nd Wave 6 STA) |
| Mutation commit | `374c3aec673dec141d983bd62efe6f75410339b5` |
| Stage 8 completion attestation | `aau_wave6_02_t4_embedded_note_completion.md` |
| Pre-AAU contract SHA | `43500fb9ed0a02a357d3526922bb9c295a13ce7934cce3a2acf8e526220a433c` |
| Pre-AAU contract lines | 1606 |
| Post-AAU contract lines | 1622 |
| Net delta | +16 / 0 |
| Affected location | §3 D-BUS; new §3.7 at L307-L323 |
| **Constitutional significance** | **2nd C-2 embedded note in Step 12 history; T4 home-section tie-break RESOLVED (§3 D-BUS PRIMARY); precedent #10 framework-label-Note-materialization cumulative × 3** |

---

## §B — Embedded-note verbatim content

```
### 3.7 Framework Theorem T4 — Acquisition-Visibility Tick Alignment (embedded note)

For every authoritative ingress event in a session, the `orchestration_tick` at which the envelope acquires orchestration authority is identical to the `orchestration_tick` value held by the session at the moment the EventBus emits the corresponding event. Acquisition and visibility are co-located within a single `orchestration_tick`, even when separated across multiple sub-phases of that tick.

Two cases manifest this alignment:

* **Phase-A-drained envelope.** Envelope drains at Phase A of `session.step(K)`. The bus emits `OperatorAbortRequested` (or the corresponding pause/resume event) at that Phase A (D-BUS-1). The session-state transition (e.g., `RUNNING` → `ABORTING`) happens at that Phase A. `orchestration_tick = K` throughout. Acquisition and visibility are both at tick `K`.
* **Deferred-from-Phase-A envelope** (Step 10 Direction A path). Envelope is present in `_pending_envelopes` at execute-entry of `session.step(K)`. Predicate closure captures the envelope. Executor returns `EXECUTION_INTERRUPTED`. The session emits the deferred ingress event at post-Phase-E classification (D-FAULT-3b). The state transition happens at the same post-Phase-E moment. `orchestration_tick = K` throughout. Acquisition and visibility are both at tick `K`.

In both cases, no ingress event acquires authority at tick `K_a` and becomes visible at tick `K_v` with `K_a ≠ K_v`. Phase-of-origin discipline (D-EXEC-2) and Phase-G trace-commit discipline (D-EXEC-7) jointly anchor every emission to a single tick value, and gap-free monotone `seq` (D-BUS-3) preserves the per-tick emission ordering within the trace.

**Citations.**
* Anchor: D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b

*Note.* This embedded explanatory note paraphrases framework Theorem T4 (Acquisition-Visibility Tick Alignment) per `docs/phase_4b_step11_admissibility_framework.md` §B.4. T4 is **NORMATIVE-CANDIDATE** per framework §B.4 classification — formalizing the substrate's distinctive property that multi-phase ingress emissions remain tick-local. The embedded form codifies T4's reasoning without introducing a new clause; the foreclosure of cross-tick acquisition/visibility decoupling is structurally already enforced by the five anchor clauses above (per framework §B.4 hypotheses). No new authority surface, no replay-identity widening, no ingress widening, no scheduler widening, no bus-emission discipline widening. V9 framework-label confinement preserved (the framework label "T4" appears only in this Note section).
```

**Cite breakdown:**

| cite | resolves to | type |
|---|---|---|
| D-BUS-1 | §3.1 EventBus synchronous dispatch (L268) | clause-ID |
| D-BUS-3 | §3.2 EventBus monotone gap-free seq (L274) | clause-ID |
| D-EXEC-2 | §1.1 events out of phase forbidden (L61) | clause-ID |
| D-EXEC-7 | §1.3 Phase G trace commit (L85) | clause-ID |
| D-FAULT-3b | §13.3 declared-order classification at end of Phase E (L1081 post-mutation) | clause-ID |
| T4 (heading + *Note.* section only) | framework Theorem T4 (Acquisition-Visibility Tick Alignment) at framework §B.4 L118 | FRAMEWORK reference (V9-confined) |

---

## §C — Author per-AAU validator self-report

| validator | result |
|---|---|
| V1/V3/V4 | ✓ PASS |
| V2/V15 | ✓ PASS (27th invocation) |
| V5 | ✓ PASS |
| V6/V7/V20 | ✓ PASS |
| V8 | ✗ NOT APPLICABLE |
| **V9 framework-confinement BLOCKING** | ✓ **PASS** (2nd canonical Wave 6 invocation) |
| V10/V11 (Properties A1-A3 BLOCKING) | ✓ PASS |
| V12 | ✗ NOT APPLICABLE (STA, not SF) |
| V13/V17 | ✓ PASS (5 clause-ID cites resolve; framework T4 reference resolvable) |
| V14 | ✓ PASS |
| V16 | ✓ PASS |
| V18/V19 | DEFERRED to Wave-6-close |

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

### §D.5 — Framework T4 embedded-note coherence adjudication slot
`_________`

### §D.6 — V9 framework-confinement BLOCKING adjudication slot
`_________`

### §D.7 — T4 home-section tie-break resolution validity adjudication slot
`_________`

### §D.8 — Author-side speculative-vs-framework-actual anchor reconciliation adjudication slot
`_________`

### §D.9 — V5 + V14 + V16 byte-preservation + additive-only slot
`_________`

### §D.10 — C-2 embedded note vs C-1 clause distinction adjudication slot
`_________`

### §D.11 — Layer C 3-option verdict slot (APPROVE / REVISE / ESCALATE)
`_________`

---

## §E — Reviewer focuses

1. **STA mechanic correctness** — Verify Layer A §5 STA discharged correctly: pre-flight anchor verification, 16-line insertion, post-flight §3.6 byte-identical + §4 byte-identical-with-offset.

2. **T4 home-section tie-break resolution validity** — Verify §3 D-BUS PRIMARY resolution per:
   - Codification plan §8 default
   - Wave 5 admissibility evaluation §G.2 recommended default
   - Wave 6 admissibility evaluation §B.2 primary listing
   - Framework T4 topic alignment (EventBus emission alignment)
   - 2 of 5 framework T4 hypotheses being §3 D-BUS clauses

3. **C-2 embedded note vs C-1 clause distinction** — Verify §3.7 is unambiguously C-2: no `**D-XXX-N**` clause-form definition; heading explicitly "(embedded note)"; Note section cites framework "NORMATIVE-CANDIDATE" classification; no new MUST/MUST NOT.

4. **V9 framework-confinement BLOCKING** — Verify framework label "T4" appears ONLY in heading (subsection identity) + Note section (L323 inline). Body (L308-L319) cites only clause-IDs. Citations subsection (L321-L322) cites only clause-IDs.

5. **Framework T4 body paraphrase faithfulness** — Verify body paraphrases framework §B.4 T4 statement faithfully:
   - Acquisition-visibility tick co-location concept
   - Case 1 (Phase-A-drained envelope): D-BUS-1 synchronous dispatch + same-Phase-A state transition + K_a = K_v = K
   - Case 2 (Deferred-from-Phase-A; Step 10 Direction A path): D-FAULT-3b classification at end of Phase E + same post-Phase-E state transition + K_a = K_v = K
   - Cross-tick decoupling foreclosure: "no ingress event ... K_a ≠ K_v"
   - Anchoring mechanism: D-EXEC-2 + D-EXEC-7 + D-BUS-3

6. **Author-side speculative-vs-framework-actual anchor reconciliation** — Confirm AAU 6.2 followed FRAMEWORK-ACTUAL hypotheses (D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b) per framework §B.4 L130, NOT the directive's speculative anchor set (D-EXEC-1, D-FAULT-2, D-FAULT-6, D-FAULT-15 row 5/27). This is consistent with AAU 6.1 precedent (following framework T1 §B.1 hypotheses faithfully).

7. **No semantic widening** — Confirm:
   - No new MUST/MUST NOT clauses
   - No new clause-IDs
   - No new authority surface
   - No replay-identity widening
   - No ingress widening
   - No scheduler widening
   - **No bus-emission discipline widening** (T4-specific; relevant since T4 is about bus emission alignment)
   - Embedded note is non-normative (paraphrastic; defers to framework + 5 clause-ID anchors)

8. **Byte-preservation integrity** — Confirm:
   - 16 lines inserted / 0 lines deleted
   - §3.6 byte-identical pre/post
   - §4 D-REPLAY text byte-identical (line-shifted +16)
   - §0 Glossary rows 1-14 byte-identical
   - §1.7 T1 embedded note (Wave 6 AAU 6.1) byte-identical at L167-L181 (no offset)
   - §13.15 D-FAULT-15 entire section byte-identical (+16 offset)
   - All Wave 1/2/3/4/5/6-AAU-6.1 clauses byte-identical at appropriate offsets

---

## §F — Cross-clause + framework coherence reference

| dimension | content |
|---|---|
| Framework Theorem T4 (§B.4 L118-L134) | NORMATIVE-CANDIDATE acquisition-visibility tick alignment theorem; substrate's distinctive property (multi-phase ingress emissions remain tick-local) |
| D-BUS-1 (§3.1 L268) | "All event dispatch is **synchronous**" — Case 1 mechanism |
| D-BUS-3 (§3.2 L274) | "Every event carries a `seq: int` field. `seq` is **monotone and gap-free** within one `ExecutionSession`" — anchoring mechanism |
| D-EXEC-2 (§1.1 L61) | "No phase may emit events out of its phase" — anchoring mechanism |
| D-EXEC-7 (§1.3 L85) | "Trace commit happens in Phase G **after** every other phase-G activity completes" — anchoring mechanism |
| D-FAULT-3b (§13.3 L1081 post-mutation) | "session MUST classify the orchestration-level failure class at **end of Phase E**" — Case 2 mechanism |
| §1.7 T1 embedded note (Wave 6 AAU 6.1) | sibling Wave 6 C-2 embedded note (Tick Non-Commensurability; tick-K-frozen-during-Phase-E premise that T4 builds on) |
| §3.7 (this AAU) | C-2 embedded explanatory note for T4; canonical home for T4 paraphrase in contract |

---

## §G — Anchor + diff verification

### §G.1 — Pre-mutation file SHA-256
`43500fb9ed0a02a357d3526922bb9c295a13ce7934cce3a2acf8e526220a433c`

### §G.2 — Pre-mutation anchor lines
- `## 3. EventBus Semantics  *(D-BUS)*` unique at L250
- `### 3.6 Non-goals` unique at L302
- `## 4. Replay Identity Model  *(D-REPLAY)*` unique at L309

### §G.3 — Pre-mutation §3.7 non-existence
- `grep -cE '^### 3\.7'` = 0
- `grep -cF 'Framework Theorem T4 — Acquisition-Visibility Tick Alignment (embedded note)'` = 0
- `grep -cF 'Acquisition-Visibility Tick Alignment'` = 0

### §G.4 — Post-mutation §3.7 + diff shape
- New §3.7 at L307-L323 (17 lines including trailing blank)
- 16 lines inserted; 0 lines deleted
- Property A3 preserved (only `+` lines)

### §G.5 — Existing-text byte preservation (line-offset corrected)
- §3.6 (L302) + body: byte-identical pre/post
- §4 D-REPLAY + downstream content: text byte-identical at +16 line offset
- §0 Glossary rows 1-14 (L20-L37): byte-identical
- §1.7 T1 embedded note (Wave 6 AAU 6.1; L167-L181): byte-identical (no offset; pre-§3.7 region)
- §13.15 D-FAULT-15 entire section: byte-identical at +16 offset
- D-SCHED-11 (pre L234 → post L234): byte-identical (no offset; pre-§3 region)
- D-FAULT-9 (pre L1233 → post L1249): byte-identical
- D-FAULT-9b (pre L1252 → post L1268): byte-identical
- D-INGRESS-1 (pre L1509 → post L1525): byte-identical
- D-INGRESS-4 (pre L1536 → post L1552): byte-identical

### §G.6 — Post-mutation file SHA-256
`7ec3c643960ead55dab7056e8fd446cee9e6c195032f1adf679b8f7e5f9d19ba`

---

## §H — Adjudication metadata

- Author claude (Y2 drafting under cap2 direction)
- Review packet timestamp: 2026-05-22
- §D adjudication slots: UNFILLED in this packet (11 slots)
- Reviewer to consult: framework §B.4 L118-L134 (T4 statement); codification plan §1 row 4 + §8 line 123 for tie-break disposition; AAU 6.1 review resolution `ce43d59` for STA + C-2 embedded note precedent

---

**End of §3.7 T4 embedded note Wave 6 AAU 6.2 Review Packet.**

AAU state at packet authoring: **AUTHOR-COMPLETE / REVIEW-PENDING**
**Constitutional significance: 2nd Wave 6 AAU; 2nd C-2 embedded note in Step 12 history; T4 home-section tie-break RESOLVED (§3 D-BUS PRIMARY); precedent #10 framework-label-Note-materialization cumulative × 3**
Layer C 3-option verdict (Reviewer-filled, separate artifact): `_________`
