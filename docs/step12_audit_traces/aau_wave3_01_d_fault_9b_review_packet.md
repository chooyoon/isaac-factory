# AAU Wave 3 / AAU 1 — D-FAULT-9b Review Packet

**Filing status:** authored at AAU commit time per Layer C §19 schema. Adjudication state at AAU commit: REVIEW-PENDING.

---

## §A — AAU identification

| field | value |
|---|---|
| Wave | 3 |
| AAU sequence | 1 of 2 (D-FAULT-9c is Wave 3 AAU 2) |
| Clause ID | **D-FAULT-9b** |
| Clause name | PAUSED Constitutional Admissibility |
| Mutation shape | **FII (Family-Internal Insertion)** |
| Source theorem | T6 (per `docs/phase_4b_step11_f58_paused_analysis.md` §M.1) |
| C-1/C-2 status | C-1 promoted (per codification plan §1 row T6) |
| Author | claude |
| Reviewer | cap2 |
| Decision-Owner | cap2 |
| Y2 multiplexing | Author=claude / Reviewer=cap2 per S5 |

---

## §B — Mutation specification

### §B.1 — Insertion anchor (V1 + V2 record)

**Anchor (Edit `old_string`):** `### 13.10 D-FAULT-10 — Failure-event canonical-JSON fingerprinting`

**V1 pre-mutation uniqueness:** ✓ PASS (1 occurrence at L1231 in pre-mutation contract at HEAD `33405a4` with contract SHA `41b8b894…`).

**V2 adjudication:** **PROCEED-SUBSTANTIVE** per V2 shape-agnostic generalization precedent #9 (formalized at Wave 1 AAU 3; confirmed at AAU 4 + Wave 2 PTA). This is the **SIXTH invocation** of V2 PROCEED-SUBSTANTIVE and the **THIRD under FII shape**. Same mechanization conditions as D-FAULT-6b (Wave 1 AAU 1) and D-FAULT-6c (Wave 1 AAU 2): `old_string ⊆ new_string` at exactly one position (the anchor `### 13.10` heading appears verbatim at the tail of `new_string`); V13 post-mutation confirms anchor uniqueness = 1.

Forensic detail: `new_string` = `[new §13.9.2 D-FAULT-9b sub-subsection]` + blank line + `### 13.10 D-FAULT-10 — Failure-event canonical-JSON fingerprinting`. Both anchor-flanking blocks appear exactly once each.

### §B.2 — Mutation diff

```
+#### 13.9.2 D-FAULT-9b — PAUSED Constitutional Admissibility
+
+**D-FAULT-9b** — A `SessionState` value `PAUSED` is constitutionally admissible IF AND ONLY IF all five of the following properties hold conjunctively:
+
+1. **Phase-A-governed transitions.** Both transitions into and out of `PAUSED` (`RUNNING` → `PAUSED` via `pause` envelope; `PAUSED` → `RUNNING` via `resume` envelope; `PAUSED` → `ABORTING` via `abort` envelope) **MUST** occur exclusively at Phase A drain. No other phase, and no other authority, **MAY** transition into or out of `PAUSED`.
+2. **Phase B–G structural skip.** During `PAUSED`, each `session.step()` invocation runs Phase A normally and structurally **MUST** skip Phases B through G. No scheduler call, no predicate construction, no executor invocation, no boundary snapshot, no registry mutation, and no Phase G commit **MAY** occur.
+3. **`orchestration_tick` continuity.** `_orchestration_tick` **MUST** advance by exactly 1 at the end of every `session.step()` invocation regardless of `session_state`, including during `PAUSED`. `PAUSED` **MUST NOT** freeze, gate, or otherwise interfere with tick advancement.
+4. **No wall-clock observation.** The substrate **MUST** make zero wall-clock observations during `PAUSED`. The wall-clock duration of any `PAUSED` interval **MUST** be determined entirely by the caller's cadence in invoking `session.step()` (per D-INGRESS-9).
+5. **Single-emitter discipline preserved.** Only `ExecutionSession.step()`, processing a drained envelope at Phase A, **MAY** transition into or out of `PAUSED`. No method-as-ingress, no callback, no timer, and no second-emitter pathway **MAY** introduce or remove `PAUSED`.
+
+Admittance of `PAUSED` without ALL of properties 1–5 holding conjunctively is **FORBIDDEN**.
+
+**Citations.**
+* Anchor: D-FAULT-6c, D-INGRESS-9, D-FAULT-6a, D-FAULT-2, D-FAULT-9
+* Reference: D-FAULT-15 row 18, D-FAULT-7
+
+*Note.* [framework citation + scope-limit attestation — see commit body]
```

- 18 inserted lines
- 0 deleted lines
- A3 (additive-only): ✓ satisfied
- Insertion point: between line 1229 (§13.9.1 D-FAULT-9a body) and line 1231 (`### 13.10` heading)

### §B.3 — Citation classification (V4 record)

**Anchor citations** (constitutionally load-bearing; depth 1 per extraction plan §4.2 row 3):
- D-FAULT-6c (Wave 1; Phase-A-only ingress observation surface) — bounds property 1 transition surface
- D-INGRESS-9 (Wave 2; Caller-Driven PAUSED Cadence) — provides property 4 caller-cadence discipline
- D-FAULT-6a (pre-Step-12; Phase E atomicity) — preserved by property 2's structural skip
- D-FAULT-2 (pre-Step-12; single-origin authority) — preserved by property 5's single-emitter discipline
- D-FAULT-9 (pre-Step-12; envelope schema) — provides `pause` / `resume` envelope kinds

**Reference citations** (navigational; per extraction plan §4.2 row 3):
- D-FAULT-15 row 18 (`RECOVERING` as a `SessionState` value FORBIDDEN) — SessionState-additions discipline context
- D-FAULT-7 (idempotent cancellation) — transition-not-envelope idempotency context

All cited clause-IDs confirmed present in pre-mutation contract via V5; V17 post-mutation confirmed all citations resolve.

### §B.4 — Framework references (V9 confinement record)

Framework refs in this AAU body:
- `docs/phase_4b_step11_f58_paused_analysis.md` (cited in Note: §M.1 + §O) — Note section only ✓
- T6 (framework theorem label) — Note section only ✓
- "Threat 7 (PAUSED-as-wall-clock-wait)" — Note section only ✓

V9 check: Rule contains zero framework references; Citations contains zero framework references; framework refs confined to Note section.

### §B.5 — Hidden-widening guardrail compliance

Per extraction plan §6.A row 3: D-FAULT-9b widening risk = "'PAUSED is admissible' without conditions"; mitigation = "enumerate all 5 properties as conjunctive". Observed mitigations:

1. The opening clause uses "IF AND ONLY IF" + "all five of the following properties hold conjunctively" — the conjunctive constraint is explicit on the admittance side.
2. Each of the 5 properties is enumerated separately with explicit MUST / MUST NOT keywords.
3. The closing sentence reinforces: "Admittance of `PAUSED` without ALL of properties 1–5 holding conjunctively is **FORBIDDEN**." — the conjunctive constraint is explicit on the foreclosure side as well.

No "PAUSED is admissible" appears without immediate conjunctive qualifier. The hidden-widening risk is mitigated through bidirectional (admittance + foreclosure) conjunctive framing.

---

## §C — Validator result matrix

### §C.1 — Pre-mutation (Stage 1–2)

| validator | result | detail |
|---|---|---|
| V1 (anchor uniqueness pre) | ✓ PASS | 1 occurrence |
| V2 (anchor stability) | PROCEED-SUBSTANTIVE | per §B.1; 6th invocation; 3rd under FII; shape-agnostic precedent #9 applies |

### §C.2 — Pre-mutation body (Stage 3)

| validator | result | detail |
|---|---|---|
| V3 (template presence) | ✓ PASS | Rule + Citations + Note all present |
| V4 (citation classification) | ✓ PASS | Anchor + Reference both labeled per extraction plan §4.2 row 3 |
| V5 (anchor-cite existing) | ✓ PASS | all 5 anchor citations defined pre-mutation; all 2 reference citations defined pre-mutation |
| V6 (minimal-enforceable-surface) | MANUAL | deferred to Reviewer cap2 |
| V7 (hidden-widening) | ✓ PASS | extraction plan §6.A row 3 guardrail observed (bidirectional conjunctive framing per §B.5) |
| V8 (override-statement) | N/A | D-FAULT-9c only |
| V9 (framework-ref confinement) | ✓ PASS | framework refs in Note section only |
| V10 (D-FAULT-15 row format) | N/A | not a row AAU |

### §C.3 — Post-mutation (Stage 4)

| validator | result | detail |
|---|---|---|
| V11 (Properties A1–A3) | ✓ PASS | 18 insertions, 0 deletions |
| V12 (Properties S1–S3) | N/A | FII shape, not SF |
| V13 (anchor uniqueness post) | ✓ PASS | 1 occurrence |
| V14 (existing-text byte preservation) | ✓ PASS — Wave 1+2 lineage byte-identical | D-FAULT-6b `ae9a500e…` / D-FAULT-6c `6d27d9ce…` / D-SCHED-14 `afd82de5…` / D-REPLAY-10 `deec8fa6…` / §14 D-INGRESS section `87cf9ac1…` / D-FAULT-9 body + D-FAULT-9a body all byte-preserved |
| V15 (heading-DAG structure) | ✓ SUBSTANTIVE PASS per S4 §S4-V15-finding (6th invocation) | 3 pre-existing skips at L11/L859/L1133 (offset solely from D-FAULT-9b's +18 lines at L1230+; same heading content as S4 finding); ZERO new skips |
| V16 (new clause-ID uniqueness) | ✓ PASS | D-FAULT-9b = 1 definition + 1 heading |
| V17 (cross-reference resolvability) | ✓ PASS | all 7 cited clause-IDs resolve; framework doc exists (77531 bytes); ZERO forward citations to D-FAULT-9c (next Wave 3 AAU) or Wave 4+ clauses |

### §C.4 — FII §6 mechanic post-flight overlay

| check | result |
|---|---|
| §6 post-flight #1: `git diff` shows only `+` lines | ✓ PASS (18 insertions, 0 deletions) |
| §6 post-flight #2: next family heading (`### 13.10 D-FAULT-10`) unchanged | ✓ PASS (byte-identical; D-FAULT-7 through D-FAULT-15 numbering unchanged) |
| §6 post-flight #3: sub-subsection numbering monotonic (13.9.1 → 13.9.2) | ✓ PASS |
| §6 post-flight #4: no renumbering of D-FAULT-10..D-FAULT-15 | ✓ PASS (all sibling D-FAULT-N numbering byte-preserved) |

### §C.5 — V18 sanity check (informational; not required at AAU level)

| check | result |
|---|---|
| V18 replay-test invariant against existing SessionPackages | ✓ PASS — runtime substrate unchanged from `33405a4`; documentation-only contract mutation; events SHA-256 invariant preserved by construction |

V18 BLOCKING + V19 BLOCKING execute at Wave-3-close per precedent #11.

### §C.6 — FF5 substrate preservation

| check | result |
|---|---|
| FF5 substrate preservation | ✓ PASS — contract SHA `5b4fd865…` differs from prior `41b8b894…` (mutations applied as expected); 0 pre-Step-12 clause-IDs removed; 0 existing-clause text modified |

---

## §D — Reviewer adjudication slots (cap2 fills in)

### §D.1 — V6 manual review

**Reviewer checklist (per V6):**

```
[ ] Rule states the foreclosure or admittance only.
[ ] Rule does NOT include operational consequences.
[ ] Rule does NOT include implementation details.
[ ] Rule does NOT include derivation chains.
[ ] Rule does NOT include "borderline" or hedging qualifications.
[ ] Rule uses MUST / MUST NOT / FORBIDDEN / SHALL / MAY explicitly.
```

**Reviewer verdict (V6): _________** (PASS / FLAG-REVISE)
**Rationale: _________**

### §D.2 — V20 manual review

**Reviewer checklist (per V20):**

```
[ ] No new MUST contradicts any existing MUST NOT for the same subject.
[ ] No new admittance contradicts any existing foreclosure.
[ ] Any clause-pair tension is explicitly acknowledged.
[ ] The new clause's scope is consistent with the citation chain's transitive closure.
[ ] D-FAULT-9b's PAUSED admission preserves D-INGRESS-9's conditional-PAUSED scoping.
[ ] D-FAULT-9b's PAUSED admission does NOT widen ingress authority beyond D-FAULT-9 envelope schema.
```

**Reviewer verdict (V20): _________** (PASS / FLAG-REVISE / ESCALATE)
**Rationale: _________**

### §D.3 — V7 SOFT-flag adjudication (if any)

V7 returned 0 banned phrases. No SOFT flag raised.

### §D.4 — Layer C 3-option verdict

**Reviewer verdict: _________** (APPROVE / REVISE / ESCALATE)

**APPROVE-AS-IS rationale (if APPROVE):** MUST cite framework/precedent/scope-limit per Layer C §17.

### §D.5 — Hidden-widening mitigation acknowledgement (extraction plan §6.A row 3)

Per §B.5: bidirectional conjunctive framing ("IF AND ONLY IF all five ... conjunctively" + closing "FORBIDDEN without ALL of properties 1–5") mitigates the "PAUSED is admissible without conditions" widening risk.

**Reviewer acknowledgement (§D.5): _________** (CONJUNCTIVE-MITIGATION-ADEQUATE / FLAG-WIDENING-RISK)

### §D.6 — D-INGRESS-9 conditional preservation acknowledgement

D-INGRESS-9 (Wave 2) explicitly states "applies conditionally on `PAUSED` being an admitted session state". With D-FAULT-9b admitting `PAUSED`, D-INGRESS-9 becomes binding. The conditional-extension precedent established at Wave 2 §C.4 is preserved: D-INGRESS-9 binds upon PAUSED admission without modification to D-INGRESS-9.

**Reviewer acknowledgement (§D.6): _________** (CONDITIONAL-PRESERVATION-CONFIRMED / FLAG-CONTRADICTION)

### §D.7 — Caller-driven cadence acknowledgement (directive review-risk focus 1)

D-FAULT-9b property 3 (orchestration_tick continuity) + property 4 (no wall-clock observation; caller-cadence-driven duration) jointly preserve caller-owned cadence. Property 4 explicitly cites D-INGRESS-9. Property 5 forecloses callback/timer/method-as-ingress pathways.

**Reviewer acknowledgement (§D.7): _________** (CALLER-DRIVEN-PRESERVED / FLAG-AUTONOMOUS-PROGRESSION-RISK)

---

## §E — Reviewer-prep ergonomics aids

### §E.1 — Reading order

1. §A AAU identification
2. §B.2 mutation diff
3. §B.3 + §B.4 citations + framework refs
4. §B.5 hidden-widening mitigation (extraction plan §6.A row 3)
5. §C validator result matrix
6. §D adjudication slots (V6, V20, Layer C, §D.5 widening, §D.6 D-INGRESS-9 preservation, §D.7 caller-driven)
7. (Reference) `docs/phase_4b_step11_f58_paused_analysis.md` §M.1 (T6 statement) + §M.2 (proof sketch) + §O (Threat 7 closure)
8. (Reference) `docs/phase_4b_step11_extraction_plan.md` §4.2 row 3 (citation list)

### §E.2 — Key questions for Reviewer

- Are the 5 conjunctive properties faithful to T6's framework statement (F58 §M.1)?
- Is the bidirectional conjunctive framing (admittance + foreclosure) adequate to mitigate the "PAUSED is admissible without conditions" widening risk?
- Does D-FAULT-9b's PAUSED admission preserve D-INGRESS-9's conditional-PAUSED scoping per Wave 2 §C.4?
- Does property 4 correctly defer wall-clock cadence to D-INGRESS-9 (no duplicate authority surface)?
- Does property 5's single-emitter discipline correctly cite D-FAULT-2 (no new authority emitter)?
- Are all Wave 1+2 clause bodies byte-preserved across this FII insertion?

### §E.3 — Wave 3 dependency note

D-FAULT-9c (Wave 3 AAU 2) is independent of D-FAULT-9b per extraction plan §4.2 row 4 (D-FAULT-9c anchors are D-SCHED-14, D-FAULT-2, D-FAULT-9a; no D-FAULT-9b dependency). Either AAU may proceed after the other's APPROVE. The directive specifies AAU 1 = D-FAULT-9b first; AAU 2 = D-FAULT-9c follows.

### §E.4 — Wave 3 precedents invoked

This AAU invokes:
1. V2 PROCEED-SUBSTANTIVE (6th invocation; 3rd FII; shape-agnostic precedent #9)
2. V15 SUBSTANTIVE PASS per S4 §S4-V15-finding (6th invocation)
3. Wall-clock-as-descriptive (D-SCHED-11 preserved; property 4 forecloses wall-clock observation during PAUSED)
4. Reference-citation handling (extraction-plan-listed References cited; no deferral needed; no framework-label-Note-materialization needed)
5. FII-shape mutation (3rd FII invocation; same mechanic as D-FAULT-6b/6c)
6. Pre-commit Stage-3-correction (NOT invoked — no Stage 4 defects detected pre-commit)

---

## §F — Audit metadata

- AAU commit author: claude (per Layer A §15; Wave 3 Y2 multiplexing per S5)
- AAU commit timestamp: 2026-05-21 (descriptive only per D-SCHED-11)
- Pre-mutation contract SHA-256: `41b8b8941fa0ad57eab00422698e5468c41a64132b83d70ae410ec9d6d381bc3` (HEAD `33405a4`)
- Post-mutation contract SHA-256: `5b4fd8656a2f716869eb30549590e0f516f2c5a276a57fe751e788d965387d53`
- Substrate impact: +18 lines (documentation-only)
- Master HEAD: UNCHANGED at `6daf9b2c…`
- Branch HEAD prior to this AAU: `33405a4c…`

---

**End of D-FAULT-9b Wave 3 AAU 1 review packet.** Reviewer cap2 fills §D.1, §D.2, §D.4, §D.5, §D.6, §D.7.
