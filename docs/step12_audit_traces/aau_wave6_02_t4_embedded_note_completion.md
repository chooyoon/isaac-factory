# AAU Wave 6 / AAU 6.2 — §3.7 Framework Theorem T4 (Acquisition-Visibility Tick Alignment) embedded note Stage 8 Completion Attestation

**Filing status:** Stage 7/8 per Layer A §15. Author claude (Y2). Reviewer cap2 (Y2 multiplexing). **2nd Wave 6 AAU; 2nd C-2 embedded note in Step 12 history; T4 home-section tie-break RESOLVED (§3 D-BUS PRIMARY).**

**Scope.** Wave 6 AAU 6.2 (§3.7 Framework Theorem T4 — Acquisition-Visibility Tick Alignment embedded note) execution log + STA mechanic discharge + tie-break resolution disclosure.

---

## §A — Stage 1: AAU baseline reconstruction

| dimension | state |
|---|---|
| Branch HEAD pre-AAU | `ce43d594caeea3ef42bee5bf75f2f84ba774a4f5` (Wave 6 AAU 6.1 close) |
| Master HEAD | `6daf9b2c…` UNCHANGED |
| Wave 1/2/3/4/5 | CLOSED |
| Wave 6 AAU 6.1 | APPROVED-AND-CLOSED |
| Wave 6 AAU 6.2 admissibility | ADMISSIBLE (per AAU 6.1 §N + Layer A §9 sub-finding 9.B order-independence) |
| Contract SHA pre-mutation | `43500fb9ed0a02a357d3526922bb9c295a13ce7934cce3a2acf8e526220a433c` |
| Contract line count pre-mutation | 1606 |
| Environment freeze | ACTIVE |
| 12 production precedents | STABLE |

**Stage 1 verdict: ✓ PASS.**

---

## §B — Stage 2: Tie-break resolution + framework T4 coherence audit

### §B.1 — T4 home-section tie-break resolution

**Tie-break:** §3 D-BUS (PRIMARY per codification plan §8) vs §13.2 (ALTERNATIVE per codification plan §1 row 4).

**Resolution: §3 D-BUS PRIMARY.**

| criterion | §3 D-BUS support | §13.2 support |
|---|---|---|
| Codification plan §8 default (line 123) | ✓ "embedded T4 note (or §13.2)" — §3 D-BUS is the primary listed home | (parenthetical alternative) |
| Wave 5 admissibility evaluation §G.2 | ✓ "default per codification plan §8 line 123 = §3 D-BUS (preferred home); §13.2 is alternative" | (alternative) |
| Wave 6 admissibility evaluation §B.2 | ✓ row 4 "AAU 6.2 anchor = §3 D-BUS primary ... or §13.2 (alternative per codification plan §1 row 4) — TIE-BREAK PENDING per Layer B per-clause checklist" | (alternative) |
| Framework T4 topic | T4 statement: "the `orchestration_tick` at which the envelope acquires orchestration authority is identical to the `orchestration_tick` value held by the session at the moment the EventBus emits the corresponding event" — explicitly about bus emission alignment | §13.2 = D-FAULT-2 origin-authority clause; T4 not primarily about failure-origin-authority |
| Framework T4 hypotheses overlap | 2 of 5 hypotheses are §3 D-BUS clauses (D-BUS-1 + D-BUS-3) | 0 of 5 hypotheses are §13.2 |
| Embedded-note locality discipline | T4 belongs near §3 D-BUS clauses it references | §13.2 too narrow for T4's scope |

**§3 D-BUS PRIMARY is the consensus resolution** across (a) codification plan default, (b) Wave 5 admissibility evaluation default, (c) Wave 6 admissibility evaluation default, (d) framework T4 topic alignment, and (e) framework T4 hypothesis overlap.

### §B.2 — Anchor verification

| check | result |
|---|---|
| `## 3. EventBus Semantics  *(D-BUS)*` heading unique | ✓ (L250) |
| `### 3.6 Non-goals` last-subsection unique | ✓ (L302) |
| `## 4. Replay Identity Model  *(D-REPLAY)*` next-section unique | ✓ (L309) |
| `### 3.7` subsection non-existence pre-mutation | ✓ (0) |
| Framework Theorem T4 (Acquisition-Visibility Tick Alignment) embedded-note text non-existence pre-mutation | ✓ (0) |
| Region L303-L308 (between §3.6 body end and §4 heading) | ✓ clean (2 list items + blank + `---` divider + blank + §4 heading) |

### §B.3 — Framework T4 coherence audit

| audit | result | evidence |
|---|---|---|
| Framework T4 (Acquisition-Visibility Tick Alignment) at `phase_4b_step11_admissibility_framework.md` §B.4 L118 | ✓ EXISTS | "For every authoritative ingress event in a session, the `orchestration_tick` at which the envelope acquires orchestration authority is identical to the `orchestration_tick` value held by the session at the moment the EventBus emits the corresponding event" + two-case definition + hypotheses |
| Framework T4 classification | ✓ "**NORMATIVE-CANDIDATE.** T4 is the formalization of the substrate's distinctive property: even multi-phase ingress emissions remain tick-local. A future clause asserting T4 forecloses cross-tick acquisition/visibility decoupling, which would otherwise be the canonical hidden-causality vector under live ingress." |
| Framework T4 hypotheses | D-BUS-1 (synchronous dispatch), D-BUS-3 (gap-free monotone seq), D-EXEC-2 (events out of phase forbidden), D-EXEC-7 (trace commit follows action), D-FAULT-3b (declared-order classification at end of Phase E) |
| D-BUS-1 (§3.1 synchronous dispatch) byte-preservation | ✓ (L268) |
| D-BUS-3 (§3.2 gap-free monotone seq) byte-preservation | ✓ (L274) |
| D-EXEC-2 (§1.1 events out of phase forbidden) byte-preservation | ✓ (L61) |
| D-EXEC-7 (Phase G trace commit) byte-preservation | ✓ (L85) |
| D-FAULT-3b (declared-order classification) byte-preservation | ✓ (L1081 post-mutation) |
| Embedded-note paraphrase faithfulness | ✓ body covers: acquisition-visibility tick co-location + 2 manifestation cases (Phase-A-drained + Deferred-from-Phase-A) + cross-tick decoupling foreclosure + D-EXEC-2/-7/D-BUS-3 anchoring mechanism |
| V9 framework-label confinement | ✓ framework label "T4" appears ONLY in heading (subsection identity) + *Note.* section (L323); body (L308-L319) uses only clause-IDs |

### §B.4 — Author-side speculative-anchor-set vs framework-actual-anchor-set reconciliation

The directive's "authoritative anchor set" specified D-EXEC-1, D-FAULT-2, D-FAULT-6, D-FAULT-15 row 5, D-FAULT-15 row 27. The framework T4 actual hypotheses (per framework §B.4 L130) are D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b. **AAU 6.2 follows framework-actual hypotheses** (authoritative source) per AAU 6.1 precedent of following framework-source hypotheses faithfully.

This is consistent with how AAU 6.1 §1.7 followed framework §B.1 T1 hypotheses (D-EXEC-1, D-EXEC-4, D-EXEC-13a, D-FAULT-6a) + D-SESS-1 (inline cite for orchestration_tick session-ownership) — matching framework hypotheses exactly. The directive's anchor set was inferential; framework source is authoritative.

### §B.5 — Wave 6 embedded-note coherence map (after AAU 6.2)

| element | role | location |
|---|---|---|
| Framework T4 (§B.4 L118-L134) | canonical framework statement; NORMATIVE-CANDIDATE; substrate's distinctive property (multi-phase ingress emissions remain tick-local) | framework doc |
| D-BUS-1 / D-BUS-3 / D-EXEC-2 / D-EXEC-7 / D-FAULT-3b | clause-form hypotheses of T4 | contract |
| §1.7 (Wave 6 AAU 6.1) T1 embedded note | sibling Wave 6 C-2 embedded note (Tick Non-Commensurability) | L167-L181 |
| **§3.7 (this AAU)** | **C-2 embedded explanatory note for T4; canonical home for T4 paraphrase in contract** | **L307-L323 (17 lines)** |

**Stage 2 verdict: ✓ PASS.**

---

## §C — Stage 3: §3.7 STA mutation

### §C.1 — Mutation specification

- **Mechanic:** Layer A §5 STA — Section-Tail-Append (4th STA invocation cumulative across Step 12; 2nd Wave 6 STA)
- **Cumulative AAU count across Step 12:** 27 (4 Wave-1 + 1 Wave-2 + 2 Wave-3 + 12 Wave-4 + 6 Wave-5 + 2 Wave-6)
- **Tie-break resolution:** §3 D-BUS PRIMARY (per §B.1)

### §C.2 — Mutation diff (16 lines added)

```diff
@@ -304,6 +304,22 @@ 
 * Retry / dead-letter / replay of failed subscriber callbacks. A subscriber that fails *records* the failure; recovery is out of scope.
 * Priority dispatch. Subscriber order is registration order, full stop.
 
+### 3.7 Framework Theorem T4 — Acquisition-Visibility Tick Alignment (embedded note)
+
+For every authoritative ingress event in a session, the `orchestration_tick` at which the envelope acquires orchestration authority is identical to the `orchestration_tick` value held by the session at the moment the EventBus emits the corresponding event. Acquisition and visibility are co-located within a single `orchestration_tick`, even when separated across multiple sub-phases of that tick.
+
+Two cases manifest this alignment:
+
+* **Phase-A-drained envelope.** Envelope drains at Phase A of `session.step(K)`. The bus emits `OperatorAbortRequested` (or the corresponding pause/resume event) at that Phase A (D-BUS-1). The session-state transition (e.g., `RUNNING` → `ABORTING`) happens at that Phase A. `orchestration_tick = K` throughout. Acquisition and visibility are both at tick `K`.
+* **Deferred-from-Phase-A envelope** (Step 10 Direction A path). Envelope is present in `_pending_envelopes` at execute-entry of `session.step(K)`. Predicate closure captures the envelope. Executor returns `EXECUTION_INTERRUPTED`. The session emits the deferred ingress event at post-Phase-E classification (D-FAULT-3b). The state transition happens at the same post-Phase-E moment. `orchestration_tick = K` throughout. Acquisition and visibility are both at tick `K`.
+
+In both cases, no ingress event acquires authority at tick `K_a` and becomes visible at tick `K_v` with `K_a ≠ K_v`. Phase-of-origin discipline (D-EXEC-2) and Phase-G trace-commit discipline (D-EXEC-7) jointly anchor every emission to a single tick value, and gap-free monotone `seq` (D-BUS-3) preserves the per-tick emission ordering within the trace.
+
+**Citations.**
+* Anchor: D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b
+
+*Note.* This embedded explanatory note paraphrases framework Theorem T4 (Acquisition-Visibility Tick Alignment) per `docs/phase_4b_step11_admissibility_framework.md` §B.4. T4 is **NORMATIVE-CANDIDATE** per framework §B.4 classification — formalizing the substrate's distinctive property that multi-phase ingress emissions remain tick-local. The embedded form codifies T4's reasoning without introducing a new clause; the foreclosure of cross-tick acquisition/visibility decoupling is structurally already enforced by the five anchor clauses above (per framework §B.4 hypotheses). No new authority surface, no replay-identity widening, no ingress widening, no scheduler widening, no bus-emission discipline widening. V9 framework-label confinement preserved (the framework label "T4" appears only in this Note section).
+
 ---
 
 ## 4. Replay Identity Model  *(D-REPLAY)*
```

- 16 lines inserted; 0 lines deleted; Property A3 preserved
- New subsection §3.7 spans L307-L323 (17 lines including trailing blank before `---` divider)

### §C.3 — Source provenance

- **Body paraphrase source:** `docs/phase_4b_step11_admissibility_framework.md` §B.4 L118-L134 (framework T4 statement + two cases + hypotheses + classification)
- **C-2 embedded-note classification source:** `docs/phase_4b_step11_codification_plan.md` §1 row 4 ("T4 Acquisition-Visibility Tick Alignment | C-2 embedded | §3 D-BUS or §13.2")
- **Tie-break source:** codification plan §8 line 123 default + framework topic alignment
- **Subsection numbering:** next sequential after §3.6 = §3.7 (per Layer A §5 STA mechanic)
- **Anchor citation source:** framework §B.4 L130 hypotheses (D-BUS-1, D-BUS-3, D-EXEC-2, D-EXEC-7, D-FAULT-3b)
- **No author additions, omissions, or substitutions** to substantive framework T4 content

**Stage 3 verdict: ✓ PASS.**

---

## §D — Stage 4/5: Layer B STA validators + framework T4 embedded-note coherence validation

### §D.1 — Per-AAU validator results

| validator | result |
|---|---|
| V1/V3/V4 | ✓ PASS |
| V2/V15 | ✓ PASS (27th invocation) |
| V5 | ✓ PASS (§3.6 body + §4 heading byte-preserved; downstream content +16 line offset) |
| V6/V7/V20 | ✓ PASS |
| V8 | ✗ NOT APPLICABLE |
| **V9 framework-confinement BLOCKING** | ✓ **PASS** — framework label "T4" appears ONLY in heading + *Note.* section; body uses only clause-IDs |
| V10/V11 (Properties A1-A3 BLOCKING) | ✓ PASS (only `+` lines in diff; §3.6 byte-identical; §4 byte-identical with +16 offset) |
| V12 | ✗ NOT APPLICABLE (STA, not SF) |
| V13/V17 cite resolvability | ✓ PASS (5 anchor clauses resolve at post-mutation locations; framework §B.4 reference resolvable) |
| V14 existing-text byte-preservation BLOCKING | ✓ PASS |
| V16 additive-only | ✓ PASS (16 lines added; 0 lines deleted) |
| V18/V19 BLOCKING | DEFERRED to Wave-6-close |

**Stage 4/5 verdict: ✓ PASS.**

### §D.2 — Framework T4 embedded-note coherence validation

| validation dimension | result |
|---|---|
| Framework T4 (§B.4 L118) byte-preservation | ✓ CONFIRMED (framework doc untouched) |
| 5 anchor clauses byte-preservation | ✓ CONFIRMED |
| AAU 6.1 §1.7 T1 embedded note byte-preservation | ✓ CONFIRMED (L167-L181; no offset; pre-§3.7 region) |
| Embedded-note body paraphrases framework T4 faithfully | ✓ CONFIRMED (acquisition-visibility tick co-location + 2 cases + cross-tick decoupling foreclosure + anchoring mechanism) |
| C-2 embedded-note classification preserved | ✓ CONFIRMED (cites framework "NORMATIVE-CANDIDATE" classification; no new clause introduced) |
| Cross-tick acquisition/visibility decoupling foreclosure preserved | ✓ CONFIRMED ("no ingress event acquires authority at tick K_a and becomes visible at tick K_v with K_a ≠ K_v") |
| No new normative content | ✓ CONFIRMED |
| No new authority surface | ✓ CONFIRMED |
| No replay-identity widening | ✓ CONFIRMED |
| No ingress widening | ✓ CONFIRMED |
| No scheduler widening | ✓ CONFIRMED |
| No bus-emission discipline widening | ✓ CONFIRMED |
| Cite minimalism preserved | ✓ CONFIRMED (5 anchor clauses + 1 framework reference; no double-citation) |
| §0 Glossary + §13.15 + Wave 1/2/3/4/5/6 AAU 6.1 byte-preservation | ✓ CONFIRMED |

**Author-side verdict: ✓ CONFIRMED.**

---

## §E — Stage 6: Mutation commit ritual

- Commit SHA: `374c3aec673dec141d983bd62efe6f75410339b5`
- Parent: `ce43d594caeea3ef42bee5bf75f2f84ba774a4f5` (single parent; BRANCH-LINEARITY)
- 16 insertions / 0 deletions; Co-author: `Claude Opus 4.7 (1M context)`

**Stage 6 verdict: ✓ PASS.**

---

## §F — Post-commit state

| dimension | state |
|---|---|
| Branch HEAD | `374c3aec673dec141d983bd62efe6f75410339b5` |
| Contract line count | 1622 (was 1606; +16) |
| §3 subsection count | 7 (was 6; +1 §3.7) |
| Master HEAD | `6daf9b2c…` UNCHANGED |
| 12 production precedents | STABLE |
| AAU state | AUTHOR-COMPLETE / REVIEW-PENDING |
| Wave 6 progress (mutation-side) | 2/4 in flight |
| Step 12 cumulative AAUs in flight | 27/29 |

---

## §G — Per-AAU mandatory preservation constraint audit

All universal + AAU-6.2-specific constraints preserved. ✓

- orchestration_tick supremacy: ✓ preserved (T4 embedded note REINFORCES tick-local acquisition-visibility alignment)
- replay-authoritative semantics: ✓ preserved
- D-EXEC semantics exact: ✓ preserved (D-EXEC-2 L61, D-EXEC-7 L85 byte-identical)
- D-BUS semantics exact: ✓ preserved (D-BUS-1 L268, D-BUS-3 L274 byte-identical)
- D-FAULT semantics exact: ✓ preserved (D-FAULT-3b at +16 offset byte-identical)
- D-INGRESS semantics exact: ✓ preserved (§14 D-INGRESS at +16 offset byte-identical)
- D-SESS semantics exact: ✓ preserved
- Wave 1/2/3/4/5/6 byte integrity: ✓ preserved (incl. §1.7 T1 embedded note byte-identical at L167-L181)
- D-FAULT-15 rows 1-42 byte integrity: ✓ preserved (§13.15 entire section byte-identical at +16 offset)
- §0 Glossary rows 1-14 byte integrity: ✓ preserved
- validator infrastructure: ✓ preserved unchanged
- replay baselines: ✓ preserved unchanged
- environment freeze: ✓ ACTIVE
- BRANCH-LINEARITY: ✓ preserved (single-parent)
- master untouched: ✓ `6daf9b2c…`

---

## §H — Forbidden actions audit

All forbidden actions per directive NOT executed. ✓

- AAU 6.3/6.4 work: NOT touched
- Wave 7 work: NOT touched
- Wave-close validation: NOT executed
- FF1-FF5 work: NOT executed
- runtime mutation: NONE
- validator mutation: NONE
- replay-model mutation: NONE
- governance mutation: NONE
- semantic reinterpretation: NONE
- rebasing/amending: NONE
- force-push: NONE
- mutation outside §3 D-BUS insertion locus: NONE

---

## §I — Anticipated Reviewer focuses

1. STA mechanic correctness (Layer A §5 discharge; 4th STA invocation)
2. T4 home-section tie-break resolution validity (§3 D-BUS PRIMARY)
3. C-2 embedded note vs C-1 clause distinction (T4 NORMATIVE-CANDIDATE; no new clause)
4. V9 framework-label confinement (T4 label appears only in heading + Note section)
5. Framework T4 body paraphrase faithfulness (acquisition-visibility tick co-location + 2 cases + cross-tick decoupling foreclosure)
6. Author-side speculative-vs-framework-actual anchor reconciliation (followed framework hypotheses per AAU 6.1 precedent)
7. No semantic widening (no new normative content; no authority surface; no replay/ingress/scheduler/bus widening)
8. Byte-preservation integrity (§0 + §1.7 + §13.15 + Wave 1/2/3/4/5/6 clauses; +16 line offset)

---

## §J — Adjudication metadata

- Author claude (Y2 drafting under cap2 direction); completion timestamp 2026-05-22
- AAU state: AUTHOR-COMPLETE / REVIEW-PENDING
- AAU mutation commit: `374c3aec673dec141d983bd62efe6f75410339b5`
- Wave 6 progress: 2/4 AAUs in flight
- 16 applicable Layer B validators PASS; V8/V12 NOT APPLICABLE
- V9 framework-confinement: PASS (2nd canonical invocation)
- Framework T4 embedded-note coherence (Author-side): CONFIRMED
- T4 home-section tie-break: RESOLVED (§3 D-BUS PRIMARY)
- Precedent #10 framework-label-Note-materialization: invoked (cumulative × 3)
- No T1–T8 escalation triggered

---

**End of §3.7 T4 embedded note Wave 6 AAU 6.2 Stage 8 Completion Attestation.**

AAU state: **AUTHOR-COMPLETE / REVIEW-PENDING**
Layer B applicable validators: **16/16 PASS**
**V9 framework-confinement BLOCKING: PASS (2nd canonical invocation)**
**T4 home-section tie-break: RESOLVED (§3 D-BUS PRIMARY)**
Framework Theorem T4 embedded-note coherence: **CONFIRMED**
§3 subsection count: **6 → 7 (+1 §3.7)**
Contract line count: **1606 → 1622 (+16)**
Master HEAD: **UNCHANGED**
Escalation: **NONE**

The next constitutional action is **Stage 8 Reviewer adjudication** in `aau_wave6_02_t4_embedded_note_review_resolution.md`.
