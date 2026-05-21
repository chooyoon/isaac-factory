# AAU Wave 6 / AAU 6.3 — §4.6 Framework Theorem T5 embedded note Review Packet

**Filing status:** Stage 7 per Layer C §S7; immutable per Layer D §20. Author claude (Y2); Reviewer cap2 (Y2 multiplexing). **3rd Wave 6 AAU; 3rd C-2 embedded note; D-REPLAY-10 forward reference to T5 CLOSED (precedent #5 RESOLUTION-CLOSURE cumulative × 3).**

---

## §A — AAU summary

| field | value |
|---|---|
| Wave | 6 |
| AAU number | 3 of 4 |
| Clause / target | §4.6 Framework Theorem T5 — Transport-Independence (embedded note) |
| Mutation shape | STA (5th cumulative; 3rd Wave 6 STA) |
| Mutation commit | `4b3b251a65e96cde29684db5b3001d0575a5cd0d` |
| Stage 8 completion attestation | `aau_wave6_03_t5_embedded_note_completion.md` |
| Pre-AAU contract SHA | `7ec3c643960ead55dab7056e8fd446cee9e6c195032f1adf679b8f7e5f9d19ba` |
| Pre-AAU contract lines | 1622 |
| Post-AAU contract lines | 1640 |
| Net delta | +18 / 0 |
| Affected location | §4 D-REPLAY; new §4.6 at L385-L402 |
| **Constitutional significance** | **3rd Wave 6 AAU; 3rd C-2 embedded note; D-REPLAY-10 forward reference to T5 CLOSED (precedent #5 RESOLUTION-CLOSURE cumulative × 3); directive-vs-framework reconciliation (T5 = Transport-Independence at §I.1, not "replay-identity / visibility coherence" at §B.5)** |

---

## §B — Embedded-note verbatim content

```
### 4.6 Framework Theorem T5 — Transport-Independence (embedded note)

The substrate's observable behavior — events, state transitions, replay-identity, fingerprints, retained state, contradiction preservation — is **invariant under change of transport**. Two implementations of the live channel that deliver the same envelope sets to the session at the same drain epochs produce a byte-equal authoritative trace, regardless of:

* network protocol or local IPC mechanism (WebRTC, websocket, HTTP, ZeroMQ, gRPC, named-pipe, message-queue, filesystem-polling, in-process queue);
* threading model in the transport layer;
* retry, backoff, or deduplication policies in the transport layer;
* serialization format on the wire;
* number of concurrent operator connections;
* transport-layer wall-clock delivery latency.

The transport sits **outside** the substrate boundary defined by §14 D-INGRESS. The substrate observes ingress only via the canonical Phase A pull (D-INGRESS-5) of an opaque passive store (D-INGRESS-1); the merged `_pending_envelopes` set is canonical-ordered by `(requested_at_tick, envelope_id)` at Phase A (D-INGRESS-4), discarding transport-layer arrival order; transport-arrival timestamps and connection metadata are diagnostic-only (D-INGRESS-8) and excluded from replay-identity comparisons. Replay reconstructs from the authoritative trace alone (D-REPLAY-10's scheduled-injection primitive), never from the transport. Together these clauses make the transport's identity invisible to every replay-identity surface.

**Citations.**
* Anchor: D-INGRESS-1, D-INGRESS-4, D-INGRESS-5, D-INGRESS-8, D-REPLAY-10

*Note.* [framework references confined here per V9]
```

**Cite breakdown:**

| cite | resolves to | type |
|---|---|---|
| D-INGRESS-1 | §14.2 Channel Opacity (framework D1) | clause-ID |
| D-INGRESS-4 | §14.5 Canonical-Order Discipline (framework D4) | clause-ID |
| D-INGRESS-5 | §14.6 Pull-Only Direction (framework D5) | clause-ID |
| D-INGRESS-8 | §14.9 Diagnostic Boundary (framework D8) | clause-ID |
| D-REPLAY-10 | §4.5 Scheduled-Injection Replay Primitive (framework L4 refinement R1) | clause-ID |
| T5 (heading + Note only) | framework Theorem T5 — Transport-Independence at framework §I.1 L673 | FRAMEWORK reference (V9-confined) |
| L4 (Note only) | framework Lemma L4 — Replay-Reconstruction From Trace Alone | FRAMEWORK reference (V9-confined) |
| D1/D4/D5/D8 (Note only) | framework Disciplines D1/D4/D5/D8 (codified as D-INGRESS-1/-4/-5/-8) | FRAMEWORK references (V9-confined) |

---

## §C — Author per-AAU validator self-report

| validator | result |
|---|---|
| V1/V3/V4 | ✓ PASS |
| V2/V15 | ✓ PASS (28th invocation) |
| V5 | ✓ PASS |
| V6/V7/V20 | ✓ PASS |
| V8 | ✗ NOT APPLICABLE |
| **V9 framework-confinement BLOCKING** | ✓ **PASS** (3rd Wave 6 canonical invocation) |
| V10/V11 (Properties A1-A3 BLOCKING) | ✓ PASS |
| V12 | ✗ NOT APPLICABLE |
| V13/V17 | ✓ PASS (5 clause-ID cites resolve; framework T5 + L4 references resolvable; D-REPLAY-10 forward ref CLOSED) |
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

### §D.5 — Framework T5 embedded-note coherence adjudication slot
`_________`

### §D.6 — V9 framework-confinement BLOCKING adjudication slot
`_________`

### §D.7 — D-REPLAY-10 forward-reference closure + precedent #5 RESOLUTION-CLOSURE (cumulative × 3) adjudication slot
`_________`

### §D.8 — Directive-vs-framework reconciliation validity adjudication slot
`_________`

### §D.9 — V5 + V14 + V16 byte-preservation + additive-only slot
`_________`

### §D.10 — C-2 embedded note vs C-1 clause distinction adjudication slot
`_________`

### §D.11 — Layer C 3-option verdict slot (APPROVE / REVISE / ESCALATE)
`_________`

---

## §E — Reviewer focuses

1. **STA mechanic correctness** — Verify Layer A §5 STA discharged correctly (5th cumulative STA invocation; mechanic identical to AAU 6.1 + 6.2).

2. **Directive-vs-framework reconciliation validity** — Confirm AAU 6.3 followed framework-actual:
   - T5 = "Transport-Independence" (NOT directive's "replay-identity / visibility coherence")
   - T5 at framework §I.1 L673 (NOT directive's §B.5; §B.5 is just a theorem-citation summary table)
   - T5 hypotheses: D1, D4, D5, D8, L4 per framework §I.1 L684
   - Per AAU 6.2 §H precedent; framework is authoritative for embedded notes

3. **C-2 embedded note vs C-1 clause distinction** — Verify §4.6 is unambiguously C-2: no `**D-XXX-N**` clause-form definition; heading explicitly "(embedded note)"; Note cites framework "NORMATIVE-CANDIDATE"; no new MUST/MUST NOT.

4. **V9 framework-confinement BLOCKING** — Verify framework labels T5/L4/D1/D4/D5/D8 appear ONLY in heading (subsection identity) + Note section. Body cites only clause-IDs (D-INGRESS-1/-4/-5/-8, D-REPLAY-10). Citations subsection has only clause-IDs.

5. **Framework T5 body paraphrase faithfulness** — Verify body paraphrases framework §I.1 T5 faithfully:
   - Substrate behavior invariant under change of transport
   - 6-item enumeration of transport-layer variables not affecting byte-equal trace (protocol/threading/retry/serialization/connections/latency)
   - Structural derivation via §14 D-INGRESS (D1/D4/D5/D8 codification) + D-REPLAY-10 (L4 refinement R1)
   - Transport sits OUTSIDE substrate boundary
   - Transport identity invisible to every replay-identity surface

6. **D-REPLAY-10 forward-reference closure (precedent #5 RESOLUTION-CLOSURE cumulative × 3)** — Verify:
   - D-REPLAY-10 Note (§4.5; Wave 1 AAU 4 commit `263e2d6`) reads "transport-independence (framework Theorem T5) is preserved (the replay tool reads only the trace)" — forward reference to T5
   - AAU 6.3 §4.6 SATISFIES this forward reference by materializing T5's canonical contract paraphrase
   - 3rd cumulative precedent #5 RESOLUTION-CLOSURE invocation

7. **No semantic widening** — Confirm:
   - No new MUST/MUST NOT clauses
   - No new clause-IDs
   - No new authority surface
   - No replay-identity widening
   - No ingress widening
   - No transport-discipline widening
   - Embedded note is non-normative (paraphrastic; defers to framework + 5 clause-ID anchors)

8. **Byte-preservation integrity** — Confirm:
   - 18 lines inserted / 0 lines deleted
   - §4.5 D-REPLAY-10 (L374) byte-identical pre/post
   - §5 D-SESS + downstream content byte-identical at +18 line offset
   - §0 Glossary + §1.7 + §3.7 byte-identical (no offset; pre-§4.6 region)
   - §13.15 D-FAULT-15 entire section byte-identical (+18 offset)
   - All Wave 1/2/3/4/5/6-AAU-6.1/6.2 clauses byte-identical at appropriate offsets

---

## §F — Cross-clause + framework coherence reference

| dimension | content |
|---|---|
| Framework Theorem T5 (§I.1 L673-L702) | NORMATIVE-CANDIDATE transport-independence theorem; substrate behavior invariant under change of transport |
| Framework Lemma L4 (referenced in framework §I.1 L684 hypotheses) | replay reconstructs from trace alone, not from transport; codified as D-REPLAY-10 via refinement R1 |
| Framework Disciplines D1/D4/D5/D8 (referenced in framework §I.1 L684 hypotheses) | codified as D-INGRESS-1/-4/-5/-8 in Wave 2 |
| D-INGRESS-1 (§14.2 L1543 post-mutation) | Channel Opacity — channel as passive store; framework D1 |
| D-INGRESS-4 (§14.5 L1570 post-mutation) | Canonical-Order Discipline — drain canonical-ordered by `(requested_at_tick, envelope_id)`; framework D4 |
| D-INGRESS-5 (§14.6) | Pull-Only Direction — no callback/notification/signal flow from channel; framework D5 |
| D-INGRESS-8 (§14.9) | Diagnostic Boundary — wall-clock arrival timestamps + transport identifiers + connection state are diagnostic-only; framework D8 |
| D-REPLAY-10 (§4.5 L374) | Scheduled-Injection Replay Primitive — replay reconstructs from trace alone; framework L4 + refinement R1 |
| D-REPLAY-10 Note forward-reference to T5 | "transport-independence (framework Theorem T5) is preserved (the replay tool reads only the trace)" — CLOSED by §4.6 |
| §1.7 (AAU 6.1) T1 embedded note | sibling Wave 6 C-2 embedded note |
| §3.7 (AAU 6.2) T4 embedded note | sibling Wave 6 C-2 embedded note |
| §4.6 (this AAU) | C-2 embedded explanatory note for T5; canonical home for T5 paraphrase in contract |

---

## §G — Anchor + diff verification

### §G.1 — Pre-mutation file SHA-256
`7ec3c643960ead55dab7056e8fd446cee9e6c195032f1adf679b8f7e5f9d19ba`

### §G.2 — Pre-mutation anchor lines
- `## 4. Replay Identity Model  *(D-REPLAY)*` unique at L309
- `### 4.5 D-REPLAY-10 — Scheduled-Injection Replay Primitive` unique at L374
- `## 5. ExecutionSession Authority Boundary  *(D-SESS)*` unique at L387

### §G.3 — Pre-mutation §4.6 non-existence
- `grep -cE '^### 4\.6'` = 0
- `grep -cF 'Transport-Independence'` = 0

### §G.4 — Post-mutation §4.6 + diff shape
- New §4.6 at L385-L402 (18 content lines)
- 18 lines inserted; 0 lines deleted
- Property A3 preserved (only `+` lines)

### §G.5 — Existing-text byte preservation (line-offset corrected)
- §4.5 D-REPLAY-10 (L374-L383): byte-identical pre/post
- §5 D-SESS + downstream content: text byte-identical at +18 line offset
- §0 Glossary rows 1-14 (L20-L37): byte-identical (no offset)
- §1.7 T1 embedded note (L167-L181): byte-identical (no offset)
- §3.7 T4 embedded note (L307-L323): byte-identical (no offset)
- §13.15 D-FAULT-15 entire section: byte-identical at +18 offset
- D-SCHED-11 (L234): byte-identical (no offset; pre-§4 region)
- D-FAULT-9 (pre L1249 → post L1267): byte-identical
- D-FAULT-9b (pre L1268 → post L1286): byte-identical
- D-INGRESS-1 (pre L1525 → post L1543): byte-identical
- D-INGRESS-4 (pre L1552 → post L1570): byte-identical
- D-SESS-1 (pre L391 → post L409): byte-identical

### §G.6 — Post-mutation file SHA-256
`aa61f17e29c86cc5a42599cf17a1521c32e6b236bfc33cd892f564b90ca544c9`

---

## §H — Adjudication metadata

- Author claude (Y2 drafting under cap2 direction)
- Review packet timestamp: 2026-05-22
- §D adjudication slots: UNFILLED in this packet (11 slots)
- Reviewer to consult: framework §I.1 L673-L702 (T5 statement); codification plan §1 row 6 (T5 → C-2 embedded → §4 D-REPLAY); Wave 1 AAU 4 D-REPLAY-10 review resolution `263e2d6` (forward-reference source); AAU 6.1/6.2 precedent for STA + V9 confinement pattern

---

**End of §4.6 T5 embedded note Wave 6 AAU 6.3 Review Packet.**

AAU state at packet authoring: **AUTHOR-COMPLETE / REVIEW-PENDING**
**Constitutional significance: 3rd Wave 6 AAU; 3rd C-2 embedded note; D-REPLAY-10 forward reference to T5 CLOSED; precedent #5 RESOLUTION-CLOSURE cumulative × 3; precedent #10 framework-label-Note-materialization cumulative × 4; directive-vs-framework reconciliation valid**
Layer C 3-option verdict (Reviewer-filled, separate artifact): `_________`
