# Phase 4B Step 12 / Wave 4 Preparation Artifact

**Filing status:** authored at Wave-4-preparation sub-session per Layer D §10 + Layer A §15 pre-authoring discipline + Wave 3 close corrigendum directive (PTA × 12 governs Wave 4 per authoritative Layer A spec). This artifact is a **planning / topology audit** artifact, NOT an AAU mutation; it commits no contract change and binds no constitutional clause.

**Authoring authority.** Decision-Owner cap2 (Y2 multiplexing per S5; operationally drafted by claude under cap2's direction). cap2 retains authoring + decision authority.

**Role-separation invariant note.** Per Y2 §S5-y2-multiplexing-discipline + Layer D §10. The Y2 operational pattern (AI drafts planning, human attests + authorizes) is constitutionally admissible per execution-readiness review §12.A.

**Scope.** Wave 4 pre-authoring preparation. Reconstructs the Wave 4 baseline; audits §13.15 D-FAULT-15 table topology; identifies PTA insertion anchor sequence for AAUs 1–12 (rows 31–42); declares AAU decomposition per authoritative Layer A spec; enumerates per-AAU row content with citation provenance; flags cross-wave implications (Wave 1 AAU 2 reference-citation-deferral precedent #5 resolution + cross-clause coherence with Wave 2 D-INGRESS + Wave 3 D-FAULT-9b/9c).

This artifact is NOT a Wave 4 AAU; NOT a contract mutation; NOT a Layer A / Layer B / Layer C / Layer D modification; NOT a validator redesign; NOT a runtime mutation; NOT a precedent rewrite. The next constitutional action (separately Decision-Owner-authorized) is the start of **Wave 4 AAU 1 (row 31)** authoring per Layer A §15 8-stage protocol.

---

## §A — Wave 4 baseline reconstruction

### §A.1 — Predecessor state

| dimension | state at Wave-4-preparation entry |
|---|---|
| `master` | `6daf9b2c24edef63e81a832727eb191726f69afb` (UNCHANGED) |
| `phase-4b-step12-codification` HEAD | `c122c96dcd3772703ad38938608f003f2c99ddc0` (Wave 3 close corrigendum) |
| Wave 1 | CLOSED |
| Wave 2 | CLOSED |
| Wave 3 | CLOSED |
| Wave 4 admissibility | ADMISSIBLE (per Wave 3 close + corrigendum) |
| Wave 4 mutation shape | **PTA × 12** (per authoritative Layer A spec; corrigendum directive) |
| Pipeline state | WAVE-3-CLOSED → preparing for Wave 4 authoring |
| AUTHORING-ACTIVE | TRUE |
| 12 production precedents | STABLE (no new at Wave 3 close + corrigendum) |
| V8 BLOCKING | discharged once (Wave 3 AAU 2); NOT applicable to Wave 4 |
| Environment freeze | ACTIVE |
| BRANCH-LINEARITY | preserved |
| additive-only discipline | preserved |
| Escalation status | NONE |
| Replay-authoritative substrate | preserved |
| Validator infrastructure | unchanged from S4 baseline |

### §A.2 — Contract state

- Contract document: `docs/phase_4b_deterministic_semantics.md`
- Contract SHA-256 at HEAD `c122c96`: `f75bce2b905b81bd32fa8f637dd0737f317cbc7e68cd19b301bb79ad49daf56e` (UNCHANGED from Wave-3-close; corrigendum did not modify the contract)
- Contract line count: 1575 lines (UNCHANGED from Wave-3-close)

### §A.3 — Admissibility prerequisites (all satisfied per Wave 3 close + corrigendum)

| prerequisite | satisfied? | evidence |
|---|---|---|
| Wave 3 CLOSED | ✓ | per `wave3_close_resolution.md` §H verdict |
| Replay-authoritative substrate preserved | ✓ | per Wave 3 close §B V18 BLOCKING PASS |
| BRANCH-LINEARITY preserved | ✓ | per Wave 3 close §D + corrigendum lineage (single linear commit appended) |
| additive-only discipline preserved | ✓ | per Wave 3 close §D + corrigendum (0 deletions) |
| validator infrastructure unchanged | ✓ | per Wave 3 close §K + corrigendum §C.2 |
| §13.15 D-FAULT-15 table present and intact | ✓ | per §B audit below |
| §13.15 rows 1–30 byte-preserved | ✓ | per §B audit below |
| No Wave 4 forward citations in pre-Wave-4 contract bodies | ✓ | per Wave 3 close §C.5 forward-gap audit (0 occurrences of D-FAULT-15 rows 31–42) |
| Master untouched | ✓ | `6daf9b2c…` |
| Wave 4 source specification exists | ✓ | per `phase_4b_step11_live_ingress_analysis.md` §Q L1089–L1102 (canonical row 31–42 content) |
| Authoritative shape characterization | ✓ | PTA × 12 per `phase_4b_step12_authoring_mechanics_plan.md` §3 + §7 + §9 + corrigendum directive |

---

## §B — D-FAULT-15 table topology audit

### §B.1 — Current §13.15 structure

| element | location at HEAD | text/state |
|---|---|---|
| §13.15 heading | L1360 | `### 13.15 D-FAULT-15 — Forbidden anti-patterns (failure-path scope)` |
| Pre-table sentence (D-FAULT-15 statement) | L1362 | `**D-FAULT-15** — In addition to D-FORBID-1..-14, the following patterns are **FORBIDDEN** in any code that participates in failure handling:` |
| Table header row | L1364 | `\| # \| forbidden pattern \| cites \|` |
| Table separator row | L1365 | `\|---\|---\|---\|` |
| Row 1 | L1366 | `\| 1 \| implicit rollback of retained state on failure \| D-FAULT-5 \|` |
| Row 30 (last existing) | L1395 | `\| 30 \| live-channel interruption ingress during \`execute()\` (envelopes arriving mid-execute and influencing the predicate) \| D-EXEC-13 (closure captured at execute-entry only) — Step 11 territory \|` |
| Blank line (table-to-section separator) | L1396 | (empty) |
| §13.16 heading (next section) | L1397 | `### 13.16 Step 9 scope restatement` |

### §B.2 — Row enumeration audit

| audit | result |
|---|---|
| Total rows in table | 30 (matches expected pre-Wave-4 state per Layer A §7 L140) |
| Row numbering monotonicity | ✓ rows 1, 2, 3, … 30 sequential; no gaps |
| Row count match Layer A pre-flight expectation | ✓ "must be 30 pre-Wave-4" per Layer A §7 L140 |
| Last existing row text | row 30: live-channel interruption ingress during `execute()` |
| Last existing row cite | D-EXEC-13 (closure captured at execute-entry only) — Step 11 territory |
| Anchor uniqueness for row 30 | ✓ `grep -cF '\| 30 \| live-channel interruption ingress during \`execute()\`'` = 1 |

### §B.3 — PTA insertion topology (per Layer A §7 PTA mechanic, D-FAULT-15 row sub-variant)

**Per Layer A §7:**
- Pre-flight: "Locate the D-FAULT-15 table; identify the last existing row's number (must be 30 pre-Wave-4, then incrementally 31, 32, … through Wave 4's 12 AAUs). Confirm rows 1–N intact (no gaps)."
- Mutation: "Append exactly one row at the end of the table, preserving column alignment and the table's markdown shape."
- Post-flight: "git diff shows only `+` lines. Last pre-existing row/entry text unchanged. Markdown structure remains valid (no orphan content; no broken table boundary)."

**Per AAU sequential anchor derivation:**

| AAU | row | anchor (last-existing-row-before-insertion) | anchor location (at AAU entry) |
|---|---|---|---|
| Wave 4 AAU 1 | row 31 | row 30 (L1395 pre-AAU-1) | L1395 |
| Wave 4 AAU 2 | row 32 | row 31 (post-AAU-1) | L1396 (after AAU 1 +1-line insertion) |
| Wave 4 AAU 3 | row 33 | row 32 (post-AAU-2) | L1397 |
| Wave 4 AAU 4 | row 34 | row 33 (post-AAU-3) | L1398 |
| Wave 4 AAU 5 | row 35 | row 34 (post-AAU-4) | L1399 |
| Wave 4 AAU 6 | row 36 | row 35 (post-AAU-5) | L1400 |
| Wave 4 AAU 7 | row 37 | row 36 (post-AAU-6) | L1401 |
| Wave 4 AAU 8 | row 38 | row 37 (post-AAU-7) | L1402 |
| Wave 4 AAU 9 | row 39 | row 38 (post-AAU-8) | L1403 |
| Wave 4 AAU 10 | row 40 | row 39 (post-AAU-9) | L1404 |
| Wave 4 AAU 11 | row 41 | row 40 (post-AAU-10) | L1405 |
| Wave 4 AAU 12 | row 42 | row 41 (post-AAU-11) | L1406 |

**Each row insertion shifts §13.16 + §13.17 + §14 down by +1 line.** Per Layer A §7 post-flight #2: "Last pre-existing row/entry text unchanged" — anchor text matching is required at each AAU's Stage 2, with the prior row's full line text as the unique anchor (which becomes the new "last existing row" after the prior AAU commits).

**Per Layer A §9 L205 ordering constraint:** "Wave 4: rows 31–42 MUST be authored in ascending row order (each row's anchor is the prior row)." Authoring out-of-order is FORBIDDEN at Wave 4.

---

## §C — Wave 4 AAU decomposition declaration

### §C.1 — AAU count

**Wave 4 = 12 AAUs** (one per row 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42).

### §C.2 — Per-AAU shape

All 12 AAUs = **PTA (Pure-Tail Append) — D-FAULT-15 row sub-variant** per Layer A §3 + §7.

### §C.3 — Per-AAU 8-stage protocol

Per Layer A §15, each AAU executes the standard 8-stage protocol:

1. Stage 1 — AAU baseline reconstruction + admissibility verification
2. Stage 2 — Anchor identification + uniqueness verification
3. Stage 3 — Clause body authoring (in this case: row content + cite text)
4. Stage 4 — Layer B per-clause validator dry-run (PTA per-shape overlay validators applicable)
5. Stage 5 — Pre-commit validation (V13 + V15 + V17 substantive PASS)
6. Stage 6 — Commit ritual (mutation commit; verbatim commit message HEREDOC)
7. Stage 7 — Layer C review packet authoring
8. Stage 8 — Reviewer adjudication (APPROVE / REVISE / ESCALATE)

Per Layer C, Reviewer adjudication produces one of three outcomes per AAU: APPROVE-AND-CLOSED / REVISE / ESCALATE. Each AAU produces 3 commits (mutation + Stage-8 completion attestation + Reviewer resolution).

**Total Wave 4 commits: 12 AAUs × 3 commits per AAU + 1 Wave-close commit = 37 commits.**

### §C.4 — Per-AAU validator profile (Layer B applicability)

| validator | applicable to Wave 4 PTA rows? | rationale |
|---|---|---|
| V1 (anchor existence) | ✓ | per Layer B PTA per-shape overlay |
| V2 (PROCEED-SUBSTANTIVE V-status enumeration) | ✓ | precedent #2 + #9 reapply (8th invocation under PTA shape) |
| V3 (line-position post-mutation check) | ✓ | confirms row N at expected location after AAU N commit |
| V4 (anchor uniqueness pre/post) | ✓ | grep count = 1 invariant per AAU |
| V5 (existing clause pre-mutation byte preservation) | ✓ | rows 1 through (N-1) MUST be byte-preserved |
| V6 (manual checklist — Rule minimal-enforceable-surface) | ✓ | per Layer B; row body MUST be minimal forbidden-pattern statement + cite |
| V7 (banned-phrase detection) | ✓ | per Layer B SOFT validator; expect 0 banned phrases |
| V8 (override-statement BLOCKING) | ✗ **NOT APPLICABLE** | V8 applies ONLY to D-FAULT-9c (per Layer B); discharged once at Wave 3 AAU 2 |
| V9 (framework-ref confinement to Note) | ⚠ **conditional** | D-FAULT-15 rows have no Note section; framework refs (if any) MUST be confined to the cite cell only |
| V10 (clause-ID format) | ✓ | row format `\| N \| pattern \| cites \|` |
| V11 (markdown structural validity) | ✓ | per PTA post-flight #3 |
| V12 (citation existence) | ✓ | each cite MUST resolve to a contract clause-ID or pre-Step-12 contract surface |
| V13 (post-mutation grep count of new clause) | ✓ | new row's unique anchor text grep count = 1 |
| V14 (stale-enumeration disclosure) | ✗ NOT APPLICABLE | precedent #8 boundary preserved (no enumerative-completeness concern for D-FAULT-15 row additions) |
| V15 (S4 substantive-pass interpretation per S4 §S4-V15-finding) | ✓ | 8th invocation; same 3 pre-existing skips at L11/L859/L1133 with line-offset shift from Wave 4 row insertions |
| V16 (additive-only Property A3) | ✓ | 0 deletions per AAU |
| V17 (citation resolvability — V19's per-AAU sibling) | ✓ | all cited clause-IDs MUST resolve at AAU commit time |
| V18 (replay-identity BLOCKING) | end-of-wave only | per Layer B §7.1; defer to Wave-4-close |
| V19 (cross-citation BLOCKING) | end-of-wave only | per Layer B §7.2; defer to Wave-4-close |
| V20 (normative-consistency) | ✓ | per Layer B SOFT validator; per-row consistency check |
| FF1–FF5 (final-form validation) | end-of-wave only | defer to Wave-4-close |

### §C.5 — Per-AAU Layer C review profile

Each AAU produces:
- 1 review packet (Layer C standard schema; per-AAU; fillable §A–§J slots; §D adjudication slots)
- 1 Reviewer resolution artifact (Layer C 3-option verdict: APPROVE / REVISE / ESCALATE)

12 AAUs × 2 Layer C artifacts per AAU = 24 Layer C artifacts across Wave 4.

### §C.6 — Reference-citation-deferral precedent #5 RESOLUTION

**Special significance of AAU 2 (row 32):** Wave 1 AAU 2 (D-FAULT-6c) Reviewer resolution (`0558866`) accepted reference-citation-deferral precedent #5 by deferring the "D-FAULT-15 row 32" reference to a future Wave (now Wave 4). At Wave 4 AAU 2 (row 32) APPROVE, this **first deferral-resolution cycle in Step 12 governance history** completes:

- Wave 1 AAU 2: deferred citation introduced
- Wave 1 close: deferral disclosed + preserved
- Wave 2 close: deferral disclosed + preserved
- Wave 3 close: deferral disclosed + preserved
- **Wave 4 AAU 2 (row 32) APPROVE: deferral RESOLVED — the cited row 32 now exists in the contract**
- Wave 4 close: deferral-resolution confirmed in §C.6 inventory (closure entry)

This is the **first practical operationalization of precedent #5** since its establishment at Wave 1; the Wave 4 close resolution will record the closure entry.

### §C.7 — STA-shape precedent #6 boundary preservation

Precedent #6 (STA-shape mutation) is invoked at D-SCHED-14 (Wave 1 AAU 3) + D-REPLAY-10 (Wave 1 AAU 4). Per Layer A §3 + §7, D-FAULT-15 row additions are **PTA, NOT STA**. The boundary is preserved: precedent #6 STA-shape is NOT invoked at Wave 4. (This corrects the Wave 3 close artifact's incorrect characterization per the corrigendum directive.)

---

## §D — Per-AAU row content (canonical source: `phase_4b_step11_live_ingress_analysis.md` §Q L1091–L1102)

**Each AAU's mutation appends exactly one row of the form `| N | forbidden pattern | cites |` to the §13.15 D-FAULT-15 table.**

| AAU | row # | forbidden pattern | cites |
|---|---|---|---|
| Wave 4 AAU 1 | 31 | live-channel callback registration (any API by which the channel notifies the session of envelope arrival outside Phase A pull) | D-FAULT-15 #16, D-FORBID-1 |
| Wave 4 AAU 2 | 32 | sub-tick channel pull (pulls at Phase B/C/D/E/F/G) | D-EXEC-1, D-EXEC-2 |
| Wave 4 AAU 3 | 33 | mid-Phase-E channel pull (any read of channel state during `executor.execute()`) | D-FAULT-15 #5, #27, D-EXEC-13a |
| Wave 4 AAU 4 | 34 | wall-clock arrival timestamp as authoritative field on `OperatorEnvelope` | D-FORBID-6, D-FAULT-15 #10, #22 |
| Wave 4 AAU 5 | 35 | transport-layer ordering authority over canonical drain order | D-SCHED-1, D-SCHED-5..-7 |
| Wave 4 AAU 6 | 36 | channel state machine observable to orchestration (ack/nack, pending/processed) | D-FAULT-14, D-SESS-4 |
| Wave 4 AAU 7 | 37 | cross-session live-channel state (channel survives `session.close()` in same process) | D-FORBID-12, D-FAULT-15 #12 |
| Wave 4 AAU 8 | 38 | wall-clock blocking in `PAUSED` state (`session.step` blocks on resume arrival) | D-FORBID-11 |
| Wave 4 AAU 9 | 39 | `manual_advance` envelope as scheduler override | D-SCHED-1, D-SCHED-3 |
| Wave 4 AAU 10 | 40 | live-channel observation of session state (`session.session_state`, `session._completed`, etc. — read by the channel for routing decisions) | D-SESS-1, D-SESS-5 |
| Wave 4 AAU 11 | 41 | retroactive ingress event editing (modifying a previously emitted `OperatorAbortRequested` event) | D-TRACE-2 |
| Wave 4 AAU 12 | 42 | non-pull observation of channel contents (peek without consume) by orchestration code outside Phase A | D-FAULT-15 #27, D-EXEC-13a |

**Final-form normalization decision (Author-Stage-3 prerogative).** The verbatim row text MAY be lightly normalized by the Author at Stage 3 to align with the existing rows 1–30's markdown conventions (e.g., backticking of code identifiers; in-text uppercase `PAUSED` / `OperatorEnvelope`; whitespace consistency around `|` separators). Such normalization is constitutionally admissible and does NOT constitute semantic widening per precedent #2 V2 PROCEED-SUBSTANTIVE. The substantive content (forbidden-pattern enumeration + citation set) MUST match the §Q source verbatim; Author MUST NOT add, omit, or substitute citations.

**Codification plan §3 (L60) reaffirmation:** "Row **43** (the T7-related row) is **OMITTED** from the table. Its foreclosure is covered by the promoted D-FAULT-9c clause; duplicating it in D-FAULT-15 would be two citation surfaces for one foreclosure." Wave 4 introduces rows 31–42 ONLY; row 43 is constitutionally omitted.

---

## §E — Cross-clause coherence notes (for Reviewer reference)

### §E.1 — Row 32 ↔ Wave 1 D-FAULT-6c (precedent #5 resolution)

Row 32 forbids "sub-tick channel pull (pulls at Phase B/C/D/E/F/G)". D-FAULT-6c (Wave 1, §13.6.3) establishes "Phase-A-Only Ingress Observability". Row 32 is the D-FAULT-15 anti-pattern citation surface for D-FAULT-6c's positive admissibility statement. Row 32 cites D-EXEC-1 + D-EXEC-2 (Phase-ordering anchors), NOT D-FAULT-6c directly — this preserves the per-row cite minimalism convention (one anti-pattern can be foreclosed by multiple existing clauses; the row cite enumerates the primary structural anchors only).

### §E.2 — Row 33 ↔ Wave 1 D-FAULT-6b

Row 33 forbids "mid-Phase-E channel pull". D-FAULT-6b (Wave 1, §13.6.2) forecloses "N-Interior-Phase-E Ingress Cannot Acquire In-Tick Authority". Row 33 cites D-FAULT-15 #5 + #27 + D-EXEC-13a; the cite chain transitively includes the mid-execute foreclosure established at D-FAULT-6b without redundant citation.

### §E.3 — Row 38 ↔ Wave 3 D-FAULT-9b + Wave 2 D-INGRESS-9

Row 38 forbids "wall-clock blocking in PAUSED state". This is the structural anti-pattern citation for:
- D-FAULT-9b (Wave 3, §13.9.2) property 4: "No wall-clock observation"
- D-INGRESS-9 (Wave 2, §14.10): "Caller-Driven PAUSED Cadence"
- D-SCHED-11 (pre-Step-12, §2.5): "no wall-clock authority"

Row 38 cites D-FORBID-11 (pre-Step-12 wall-clock-blocking foreclosure). The cite minimalism convention applies: D-FORBID-11 is the primary structural anchor; the Wave 2 + Wave 3 admissibility clauses are positive-side complements that the anti-pattern row does not need to enumerate.

### §E.4 — Row 39 ↔ Wave 3 D-FAULT-9c (general T7 boundary)

Row 39 forbids "`manual_advance` envelope as scheduler override". D-FAULT-9c (Wave 3, §13.9.3) establishes the **general T7 Override Admissibility Boundary** with `manual_advance` as a bounded example. Row 39 is the specific manual_advance anti-pattern citation; D-FAULT-9c is the general boundary clause. The two are **complementary, not duplicative**: Row 39 is one specific manifestation of the foreclosure D-FAULT-9c articulates generally. Per the codification plan §3 L60 explicit reasoning, row 43 (T7 general-boundary row) is OMITTED to avoid double-citation, but row 39 (manual_advance-specific row) is RETAINED because it cites different foreclosure surfaces (D-SCHED-1 + D-SCHED-3 scheduler-input authority) than D-FAULT-9c (D-SCHED-14 + D-FAULT-2 + D-FAULT-9a override).

### §E.5 — Row 41 ↔ D-TRACE-2

Row 41 forbids "retroactive ingress event editing". D-TRACE-2 (pre-Step-12) establishes append-only trace discipline. Row 41 cites D-TRACE-2 as the primary structural anchor.

### §E.6 — Row 42 ↔ D-FAULT-15 #27 + Wave 1 D-FAULT-6c

Row 42 forbids "non-pull observation of channel contents (peek without consume) by orchestration code outside Phase A". Row 42 cites D-FAULT-15 #27 (session-side mid-execute envelope drain anti-pattern, Step 10 Direction A row) + D-EXEC-13a. The relationship to D-FAULT-6c (Wave 1 Phase-A-Only Ingress Observability) is positive-side complement: D-FAULT-6c admits Phase-A-only observation; Row 42 forecloses non-Phase-A peek.

---

## §F — Cross-wave reference-citation-deferral resolution audit

### §F.1 — Precedent #5 resolution at Wave 4 AAU 2

Per Wave 1 AAU 2 Reviewer resolution (`0558866`) §D.5 ACCEPTED-DEFERRED: D-FAULT-15 row 32 was cited within D-FAULT-6c's body before row 32 existed in the contract. The deferral was constitutionally accepted with the expectation that row 32 would land at Wave 4.

**At Wave 4 AAU 2 APPROVE:** the deferral closes operationally — the citation "D-FAULT-15 row 32" within D-FAULT-6c's body now resolves to the newly-introduced row 32 in §13.15. The Wave 4 close resolution will record this in §C closure inventory.

### §F.2 — No other Wave-1-or-2-or-3 forward citations to Wave 4 rows

Per Wave 1 close §C.4 + Wave 2 close §C.5 + Wave 3 close §C.5 inter-wave forward-citation gap audits: 0 occurrences of D-FAULT-15 rows 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42 in Wave 1+2+3 bodies. Only row 32 has a pre-existing forward citation (from D-FAULT-6c via precedent #5).

---

## §G — Anticipated precedent invocations across Wave 4

| precedent | expected invocations | rationale |
|---|---|---|
| #1 Full AAU lifecycle | 12× (one per AAU) | 8-stage protocol per AAU |
| #2 V2 PROCEED-SUBSTANTIVE | 12× (8th through 19th invocations cumulative) | PTA shape per precedent #9 shape-agnostic generalization |
| #3 V15 substantive-pass per S4 §S4-V15-finding | 12× (8th through 19th invocations cumulative) | same 3 pre-existing skips at L11/L859/L1133 with cumulative line-offset shift |
| #4 Wall-clock semantics | 12× | D-SCHED-11 byte-preserved; rows 34, 38 reinforce wall-clock foreclosure surface |
| #5 Reference-citation-deferral | RESOLUTION-CLOSURE at Wave 4 AAU 2 | first practical deferral-resolution cycle in Step 12 governance history |
| #6 STA-shape mutation | NOT INVOKED | boundary preserved (Wave 4 is PTA, NOT STA, per Layer A authoritative spec) |
| #7 Interrupted-Stage-6-recovery | NOT INVOKED (anticipated) | no Stage-6 interruption expected in clean Wave 4 progression |
| #8 Stale-enumeration-disclosure | NOT INVOKED | boundary preserved (D-FAULT-15 has no Non-goals enumeration; no enumerative-completeness concern) |
| #9 V2 shape-agnostic generalization | 12× (continued from Wave 3) | PTA per-row series reaffirms shape-agnostic stability; SF remains structurally distinct (Wave 5) |
| #10 Framework-label-Note-materialization | NOT INVOKED (anticipated) | D-FAULT-15 rows have no Note section; framework refs (if any) MUST be confined to the cite cell or omitted per cite minimalism |
| #11 Wave-close readiness pre-attestation | invoked at Wave 4 AAU 12 §D.6 + Wave 4 close | per precedent #11 pattern (Wave 1+2+3 reinvocation) |
| #12 Pre-commit Stage-3-correction discipline | NOT INVOKED (anticipated) | clean Stage-3 → Stage-6 progression expected; precedent boundary preserved if no first-pass defects detected |

### §G.1 — V8 BLOCKING explicitly NOT applicable

V8 BLOCKING applies ONLY to D-FAULT-9c (per Layer B). V8 was discharged exactly once at Wave 3 AAU 2 and PASSED. V8 is NOT applicable at any Wave 4 AAU. Layer B per-shape overlay validator selection for PTA rows excludes V8.

---

## §H — Mandatory preservation constraint audit (per directive)

All Wave-4-preparation-scope preservation constraints satisfied:

| constraint | preserved at Wave-4-preparation? |
|---|---|
| orchestration_tick supremacy | ✓ (no runtime touched) |
| replay-authoritative semantics | ✓ (no replay model touched) |
| D-SCHED-11 semantics exactly | ✓ |
| D-FAULT-6b semantics exactly | ✓ |
| D-FAULT-6c semantics exactly | ✓ |
| D-SCHED-14 semantics exactly | ✓ |
| D-REPLAY-10 semantics exactly | ✓ |
| §14 D-INGRESS semantics exactly | ✓ |
| D-FAULT-9a semantics exactly | ✓ |
| D-FAULT-9b semantics exactly | ✓ |
| D-FAULT-9c semantics exactly | ✓ |
| additive-only discipline | ✓ (this preparation artifact is additive-only; 0 deletions) |
| validator infrastructure unchanged | ✓ |
| audit lineage canonical | ✓ |
| environment freeze ACTIVE | ✓ |
| master untouched | ✓ |

**Wave-4-specific constraints (per directive):**

| constraint | preserved at Wave-4-preparation? |
|---|---|
| rows 31–42 ONLY | ✓ (row 43 explicitly omitted per codification plan §3 L60) |
| no row renumbering | ✓ (rows 1–30 byte-preserved; new rows 31–42 monotonically extend the existing 1–30 sequence) |
| no mutation of rows 1–30 | ✓ (per Layer A §7 post-flight #2; per V5 per-AAU) |
| no mutation outside §13.15 | ✓ (per PTA mechanic; per V5 per-AAU; per V18 BLOCKING at Wave-4-close) |
| no hidden table restructuring | ✓ (markdown column-alignment + cell-separator convention preserved) |
| no semantic widening outside anti-pattern codification | ✓ (per §D verbatim source preservation + V20 normative-consistency per-AAU) |
| preserve reference-citation-deferral precedent integrity | ✓ (precedent #5 RESOLUTION-CLOSURE at AAU 2 is the precedent's first operational closure; boundary discipline preserved) |
| preserve STA-shape precedent integrity | ✓ (Wave 4 is PTA NOT STA per Layer A authoritative spec; precedent #6 boundary preserved per corrigendum directive) |

---

## §I — Wave 4 begin-authorization checklist

Before Wave 4 AAU 1 (row 31) authoring may begin, the Decision-Owner attests:

| item | attested? |
|---|---|
| Wave 4 admissibility confirmed (Wave 3 CLOSED + corrigendum) | ✓ |
| Wave 4 shape confirmed (PTA × 12 per Layer A) | ✓ |
| Wave 4 AAU decomposition declared (12 separate AAUs) | ✓ |
| Wave 4 authoring order declared (ascending 31 → 42) | ✓ |
| Per-AAU validator profile declared (§C.4) | ✓ |
| Per-AAU row content source declared (§D verbatim from §Q L1091–L1102) | ✓ |
| Cross-clause coherence notes available for Reviewer reference (§E) | ✓ |
| Precedent #5 resolution-closure expected at AAU 2 (§F.1) | ✓ |
| Precedent #6 boundary preserved (PTA NOT STA per corrigendum) | ✓ |
| V8 BLOCKING not applicable (§G.1) | ✓ |
| All 16 mandatory preservation constraints satisfied (§H) | ✓ |
| Wave-4-specific constraints satisfied (§H) | ✓ |
| Master HEAD untouched (`6daf9b2c…`) | ✓ |
| Branch HEAD at `c122c96` (post-corrigendum) | ✓ |
| Environment freeze ACTIVE | ✓ |

**State transition upon Decision-Owner authorization:** `WAVE-4-ADMISSIBLE / Wave-4-preparation-COMPLETE` → `WAVE-4-IN-PROGRESS / AAU-1-AUTHORING-ACTIVE`.

---

## §J — Forbidden actions (per directive)

The following are FORBIDDEN at this Wave-4-preparation sub-session AND remain forbidden throughout Wave 4:

| forbidden | explicit at this preparation artifact |
|---|---|
| Wave 5 work | ✓ (this artifact addresses Wave 4 ONLY) |
| PTA Wave (post-Wave 4) work | ✓ (per codification plan §1 sequencing) |
| runtime mutation | ✓ (no runtime files modified) |
| validator mutation | ✓ (no validator files modified) |
| replay-model mutation | ✓ (no replay-model files modified) |
| governance mutation | ✓ (no governance plan modified) |
| hidden cleanup | ✓ (no existing content deleted or rewritten) |
| semantic reinterpretation | ✓ (PTA shape per Layer A; no shape reinterpretation) |
| rebasing/amending | ✓ (corrigendum + this artifact both additive single-commit) |
| force-push | ✓ |
| mutation outside §13.15 rows 31–42 | ✓ (Wave 4 scope is rows 31–42 ONLY; row 43 omitted per codification plan §3 L60) |

---

## §K — Adjudication metadata

- Authoring authority: Decision-Owner cap2 (Y2 multiplexing per S5; operationally drafted by claude under cap2's direction)
- Preparation timestamp: 2026-05-21 (descriptive only per D-SCHED-11)
- Artifact class: Wave-4-preparation planning artifact (NOT an AAU; commits no contract mutation)
- Wave 4 mutation shape: **PTA × 12** (per Layer A authoritative spec; corrigendum directive `c122c96`)
- Wave 4 AAU count: **12** (rows 31–42 inclusive)
- Wave 4 authoring order: **ascending row 31 → 42**
- V8 BLOCKING applicability at Wave 4: **NOT APPLICABLE**
- Reference-citation-deferral precedent #5 resolution: **AT WAVE 4 AAU 2 APPROVE**
- 12 production precedents: **STABLE** (no new at Wave 4 preparation)
- T1–T8 escalation: **NONE**
- CR convening: **NOT REQUIRED**
- Master HEAD: **UNCHANGED** at `6daf9b2c24edef63e81a832727eb191726f69afb`
- Branch HEAD at this preparation artifact: (to be assigned by Layer A §15 Stage 6 ritual)

---

**End of Phase 4B Step 12 Wave 4 Preparation Artifact.**

Wave 4 admissibility: **ADMISSIBLE** (preserved from Wave 3 close)
Wave 4 mutation shape: **PTA × 12** (per Layer A authoritative spec)
Wave 4 AAU count: **12 separate AAUs**
Wave 4 authoring order: **ascending 31 → 42**
Wave 4 V8 BLOCKING: **NOT APPLICABLE**
Wave 4 precedent #5 resolution: **AT AAU 2 (row 32) APPROVE**
12 production precedents: **STABLE**
Escalation: **NONE**

The next constitutional action (separately Decision-Owner-authorized) is **Wave 4 AAU 1 (row 31) authoring** — PTA mutation appending `| 31 | live-channel callback registration (any API by which the channel notifies the session of envelope arrival outside Phase A pull) | D-FAULT-15 #16, D-FORBID-1 |` to the §13.15 D-FAULT-15 table per Layer A §15 8-stage protocol.
