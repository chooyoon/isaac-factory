# Phase 4B Step 12 — Validation Plan (Layer B — Pre-Authoring)

**Status: PRE-AUTHORING LAYER-B PER-CLAUSE VALIDATION PLAN (2026-05-21).** Designs the validation discipline that governs each AAU insertion before normative authoring begins. Inherits the AAU model, four mutation shapes (PTA, STA, FII, SF), insertion-anchor protocol, and Properties A1–A3 / S1–S3 from [`phase_4b_step12_authoring_mechanics_plan.md`](phase_4b_step12_authoring_mechanics_plan.md); inherits the 6-wave citation DAG and three-section clause-body template from [`phase_4b_step11_extraction_plan.md`](phase_4b_step11_extraction_plan.md). Does **not** author clause wording, does **not** mutate the contract document, does **not** design reviewer UI (Layer C), does **not** sequence PRs or test invocations (Layer D).

Layer B specifies *what* must be validated for each AAU, *when* in the AAU lifecycle the validation runs, *how* failures are classified and handled, and *which* validators are mechanizable now versus require Layer-B-implementing-agent work later.

---

## §1. Scope and inheritance

| inherited from | element |
|---|---|
| Layer A §2 | AAU = 1 catalogued insertion = 1 commit (29 AAUs across 6 waves) |
| Layer A §3 | Four mutation shapes (PTA, STA, FII, SF) |
| Layer A §4 | Insertion-anchor protocol (verbatim, unique, local, stable) |
| Layer A §14 | Properties A1–A3 (28 AAUs) and S1–S3 (1 SF AAU) |
| Layer A §15 | 8-stage per-AAU safety protocol (Layer B mechanizes stages 2, 5, 6) |
| Extraction plan §1 | 38-insertion catalog (Layer A bundles into 29 AAUs) |
| Extraction plan §2 + §4 | Citation DAG and per-promoted-clause anchor/reference classification |
| Extraction plan §5 | Framework/contract separation rules |
| Extraction plan §6 | Three-section clause-body template (Rule / Citations / Note) |
| Extraction plan §7 | Minimal-enforceable-surface guideline |
| Extraction plan §8 | Per-clause hidden-widening risks |
| Extraction plan §12 | D-FAULT-9c override-relationship-statement requirement |
| Codification plan §1, §9 | C-1 promotion list + six-phase order (re-decomposed into Layer-A waves) |

Layer B specifies only the per-AAU validation overlay. It does not re-decide any inherited classification.

---

## §2. The four-stage validation lifecycle

A single AAU's validation lifecycle has **four sequential stages** aligned with Layer A's per-AAU safety protocol:

| stage | name | timing relative to mutation | scope | gate |
|---|---|---|---|---|
| **1** | Pre-Mutation Anchor Validation | before any edit; after the AAU's anchor is chosen | per-AAU | BLOCKING |
| **2** | Pre-Mutation Body Validation | before any edit; after the AAU's clause-body draft exists | per-AAU | BLOCKING |
| **3** | Post-Mutation File-State Validation | after Edit tool returns; before `git commit` | per-AAU | BLOCKING |
| **4** | Post-Commit Cross-AAU Validation | after `git commit`; before the next AAU starts | per-AAU + cross-AAU + cross-wave | mixed (see §16) |

Stages 1–3 run for every AAU. Stage 4 runs at AAU boundaries with additional aggregates run at wave boundaries.

**Sub-finding 2.A.** Layer A's 8-stage safety protocol maps onto Layer B's four-stage validation as: Layer A stages 1, 2, 3 → Layer B stage 1; Layer A stage 4 = the mutation itself (no validation); Layer A stages 5, 6, 7 → Layer B stage 3; Layer A stage 8 = the commit itself (no validation); Layer B stage 2 (clause-body) inserts *between* Layer A stage 3 (site read) and Layer A stage 4 (mutation); Layer B stage 4 is new and runs *after* Layer A stage 8.

---

## §3. The validator catalog (V1–V20)

Each validator has a stable ID, a scope, a stage, a mechanization level, and a failure class:

| ID | name | stage | mechanization | failure class | per-shape applicability |
|---|---|---|---|---|---|
| **V1** | Anchor uniqueness (pre) | 1 | mechanical | BLOCKING | all |
| **V2** | Anchor stability | 1 | mechanical | BLOCKING | all |
| **V3** | Three-section template presence | 2 | semi-mechanical | BLOCKING | C-1 promoted clauses (8 AAUs: D-FAULT-6b/6c, D-FAULT-9b/9c, D-SCHED-14, D-REPLAY-10, plus D-INGRESS-1..9 inside §14) |
| **V4** | Citation classification (anchor vs reference) | 2 | semi-mechanical | BLOCKING | C-1 promoted clauses |
| **V5** | Anchor-citation existing-clause check | 2 | mechanical | BLOCKING | C-1 promoted clauses; D-FAULT-15 rows |
| **V6** | Minimal-enforceable-surface check | 2 | manual | SOFT | all clause bodies |
| **V7** | Hidden-widening-language scan | 2 | semi-mechanical | SOFT | C-1 promoted clauses (per extraction-plan §8 risks) |
| **V8** | Override-statement presence | 2 | mechanical | BLOCKING | D-FAULT-9c only |
| **V9** | Framework-reference confinement (Section C only) | 2 | mechanical | BLOCKING | all clause bodies |
| **V10** | D-FAULT-15 row format compliance | 2 | mechanical | BLOCKING | D-FAULT-15 row AAUs (12) |
| **V11** | Properties A1–A3 | 3 | mechanical | BLOCKING | 28 non-SF AAUs |
| **V12** | Properties S1–S3 | 3 | mechanical | BLOCKING | 1 SF AAU |
| **V13** | Anchor uniqueness (post) | 3 | mechanical | BLOCKING | all |
| **V14** | Existing-text byte preservation | 3 | mechanical | BLOCKING | 28 non-SF AAUs |
| **V15** | Heading-DAG structure | 3 | mechanical | BLOCKING | all |
| **V16** | New clause-ID uniqueness across document | 3 | mechanical | BLOCKING | C-1 promoted clauses; D-INGRESS-1..9 |
| **V17** | Cross-reference resolvability | 3 | mechanical | BLOCKING | C-1 promoted clauses; D-FAULT-15 rows; §11 SF |
| **V18** | Replay-test invariant | 4 | mechanical (Layer D defines invocation cadence) | BLOCKING | all (per wave) |
| **V19** | Inter-wave citation-gap | 4 | mechanical | BLOCKING | end of each wave |
| **V20** | Normative-consistency check | 4 | manual | SOFT | C-1 promoted clauses |

**Sub-finding 3.A.** 14 of 20 validators are mechanical, 4 are semi-mechanical (need a markdown-section-aware parser), 2 are manual. Mechanization coverage = 70% strict / 90% if semi-mechanical is counted.

**Sub-finding 3.B.** All 15 BLOCKING validators must pass before `git commit`. The 4 SOFT validators may produce flagged commits whose flags become Layer C reviewer responsibilities (deferred).

---

## §4. Stage 1 — Pre-Mutation Anchor Validation

Runs after the AAU's anchor text is selected; before any Edit tool call.

### §4.1 V1 — Anchor uniqueness (pre)

* **Check.** `grep -Fc '<anchor>' docs/phase_4b_deterministic_semantics.md` returns exactly `1`.
* **Mechanization.** One Bash command.
* **Failure.** BLOCKING. AAU author re-derives a more specific anchor (extends context lines until uniqueness is achieved) and re-runs V1.

### §4.2 V2 — Anchor stability

* **Check.** The anchor text is **outside** the region the AAU's mutation will alter. For PTA/STA/FII the anchor is read-only context; for SF the anchor IS the modified text and V2 is replaced by Property S1's verbatim-prefix check (deferred to V12).
* **Mechanization.** Comparison: anchor text MUST NOT be a substring of the planned `new_string` for non-SF AAUs.
* **Failure.** BLOCKING. AAU author re-derives a non-overlapping anchor.

**Sub-finding 4.A.** V1 and V2 together guarantee the Layer A pre-flight requirement that "the mutation cannot accidentally land in the wrong place" and "the mutation cannot accidentally overwrite the anchor."

---

## §5. Stage 2 — Pre-Mutation Body Validation

Runs after the clause-body draft is composed; before any Edit tool call. Eight validators (V3–V10).

### §5.1 V3 — Three-section template presence

For C-1 promoted clauses (per extraction-plan §6):

* **Check.** The clause body contains:
  * A **Rule section** — a normative paragraph using MUST / MUST NOT / FORBIDDEN / MAY / SHALL.
  * A **Citations section** — an explicit, marker-delimited block listing anchor and reference citations.
  * Optionally a **Note section** — non-normative explanation; if present, marker-delimited.
* **Mechanization.** Semi-mechanical via a markdown-aware parser. Layer B specifies the *contract*: each promoted clause body MUST have detectable markers for Rule and Citations sections (specific marker syntax — e.g., `**Citations.**` or a `### N.N Citations` sub-heading — left to the Layer-B-implementing-agent).
* **Failure.** BLOCKING. AAU author restructures the draft to include all required sections.

### §5.2 V4 — Citation classification

For C-1 promoted clauses (per extraction-plan §4.4):

* **Check.** The Citations section explicitly distinguishes **anchor** citations from **reference** citations. Both labels must be present (a citation list with no classification is invalid even if all citations happen to be anchor-only).
* **Mechanization.** Semi-mechanical. The Citations section must contain detectable "Anchor" / "Reference" sub-markers.
* **Failure.** BLOCKING. AAU author labels each citation explicitly.

### §5.3 V5 — Anchor-citation existing-clause check

For each citation in the **anchor** sub-list of any new clause body:

* **Check.** Each anchor citation resolves to an existing clause-ID either (a) already in the contract at this AAU's commit point, or (b) introduced earlier in the same wave per the wave order, or (c) introduced in an earlier wave. No anchor citation may refer to a clause introduced in a later wave (forward reference).
* **Mechanization.** `grep -F '<cited-clause-ID>' docs/phase_4b_deterministic_semantics.md` must return ≥ 1 match in either the current contract or in already-applied AAU drafts.
* **Failure.** BLOCKING. AAU author corrects the citation (typo) or reorders AAUs within the wave (the wave-internal ordering rules in Layer A §9.B already enforce this; V5 is the mechanical guard).

**Sub-finding 5.A.** V5 prevents the "phantom citation" failure mode where a new clause cites a not-yet-existing clause-ID and the contract becomes internally inconsistent for the lifetime between commits.

### §5.4 V6 — Minimal-enforceable-surface check

For all clause bodies (per extraction-plan §7):

* **Check.** The Rule section states the foreclosure or admittance only. The body does NOT include:
  * Operational consequences (e.g., specific latency floors).
  * Implementation details (e.g., "structural skip" mechanism).
  * Derivation chains.
  * "Borderline" or hedging qualifications.
* **Mechanization.** Manual. (A semi-mechanical scan for known bad-pattern phrases is possible but not load-bearing.)
* **Failure.** SOFT. Layer B records the flag; Layer C reviewer (deferred) makes the final judgment.

### §5.5 V7 — Hidden-widening-language scan

For each promoted C-1 clause body (per extraction-plan §8):

| AAU | banned-phrase patterns (illustrative; final list deferred to Layer-B-implementing-agent) |
|---|---|
| D-FAULT-6b | "next-tick observation", "eventually", "may later be observed" |
| D-FAULT-6c | "observation" used without "ingress event" qualifier |
| D-FAULT-9b | "PAUSED is admissible" without the 5-property conjunctive enumeration |
| D-FAULT-9c | "only manual_advance" (must instead state the general T7 rule) |
| D-SCHED-14 | "input sets closed" without "without explicit clause amendment" |
| D-REPLAY-10 | "scheduled-injection is mandatory" or "MUST inject" (must use MAY) |
| D-INGRESS-8 | "diagnostic metadata" without on-event-not-envelope qualifier; "authoritative metadata" |

* **Mechanization.** Semi-mechanical regex pass per AAU.
* **Failure.** SOFT. AAU author reviews flagged phrases; if intentional, override with rationale; otherwise rewrite.

### §5.6 V8 — Override-statement presence

For **D-FAULT-9c only** (per extraction-plan §12):

* **Check.** The D-FAULT-9c clause body contains an explicit override-relationship statement of the form: "D-FAULT-9c overrides D-FAULT-9a's manual_advance reservation; D-FAULT-9a's reservation language is preserved verbatim for historical citation continuity" (or semantically equivalent wording).
* **Mechanization.** `grep -F 'overrides D-FAULT-9a' <draft-body>` returns ≥ 1 match AND grep for `manual_advance` in the same paragraph.
* **Failure.** BLOCKING. The override statement is constitutive of D-FAULT-9c's coherence with the unmodified D-FAULT-9a; missing it would create a silent contradiction between the two clauses.

### §5.7 V9 — Framework-reference confinement

For all clause bodies (per extraction-plan §4.4 + §5.3):

* **Check.** Framework document filenames (`phase_4b_step11_*.md`, `phase_4b_step12_*.md`, future `phase_4b_step*_*.md`, framework lemma labels L1–L4, framework finding labels F1–F65, framework threat labels) MUST appear ONLY within the Note (Section C) of a clause body. Their appearance in Rule or Citations sections is forbidden.
* **Mechanization.** Markdown-section-aware scan. Identify Section A, Section B, Section C boundaries; grep each region for framework-reference patterns; if found in A or B → FAIL.
* **Failure.** BLOCKING. Framework references in normative sections leak analytical reasoning into enforcement and violate the framework/contract separation rule.

### §5.8 V10 — D-FAULT-15 row format compliance

For each D-FAULT-15 row AAU (12 AAUs, Wave 4):

* **Check.** The new row matches the D-FAULT-15 table's existing column structure (same column count, same column meanings, same alignment characters in the markdown source).
* **Mechanization.** Markdown table parser; compare new row's column structure against the table's header row and against an arbitrary existing row.
* **Failure.** BLOCKING. AAU author re-formats the row to match the existing table shape.

---

## §6. Stage 3 — Post-Mutation File-State Validation

Runs after the Edit tool returns; before `git commit`. Seven validators (V11–V17).

### §6.1 V11 — Properties A1–A3 (28 non-SF AAUs)

* **Check.**
  * **A1 (line preservation):** Every pre-mutation line appears verbatim at position ≥ its pre-mutation position in the post-mutation file.
  * **A2 (character superset):** Pre-mutation character multiset ⊆ post-mutation character multiset.
  * **A3 (diff shape):** `git diff docs/phase_4b_deterministic_semantics.md` shows only `+` content lines and zero `-` content lines (excluding the `---`/`+++` file headers and `@@` hunk headers).
* **Mechanization.**
  * A3 is one Bash command: `git diff docs/phase_4b_deterministic_semantics.md | grep -E '^-[^-]' | wc -l` must equal `0`.
  * A1 is implied by A3 (no deletions ⇒ all pre-existing lines preserved).
  * A2 is implied by A3.
* **Failure.** BLOCKING. The AAU author runs `git checkout -- docs/phase_4b_deterministic_semantics.md` and restarts the AAU from Layer A stage 1.

### §6.2 V12 — Properties S1–S3 (1 SF AAU)

* **Check.**
  * **S1 (verbatim-prefix preservation):** The replaced line's `new_string` contains `old_string` as a verbatim prefix (or as a leading subline if multi-line).
  * **S2 (no character deletion):** Every non-whitespace character of `old_string` appears in `new_string` at the same relative position.
  * **S3 (bounded diff shape):** `git diff` shows exactly one modified region; within that region, each `-` line has a corresponding `+` line that begins with the `-` line's content.
* **Mechanization.** Custom diff inspector: parse the unified diff, locate the single hunk, verify each `-`/`+` line pair satisfies S1+S2.
* **Failure.** BLOCKING. Same reset-and-restart protocol as V11.

### §6.3 V13 — Anchor uniqueness (post)

* **Check.** Repeat V1's grep. The anchor text MUST still return exactly `1` match in the post-mutation file.
* **Mechanization.** Same as V1.
* **Failure.** BLOCKING. Indicates the mutation accidentally duplicated or destroyed the anchor; reset and restart.

### §6.4 V14 — Existing-text byte preservation

* **Check.** For 28 non-SF AAUs: `git diff docs/phase_4b_deterministic_semantics.md` shows only insertion regions; the byte content of every pre-existing line is unchanged.
* **Mechanization.** Implied by V11.A3 + V11.A1. V14 is the named guarantee; V11 is the mechanism.
* **Failure.** BLOCKING. Same as V11.

### §6.5 V15 — Heading-DAG structure

* **Check.** The post-mutation document is a valid markdown heading DAG:
  * Heading levels never skip forward (no `## X` immediately followed by `#### Y`).
  * Section numbering monotonic within each section family (e.g., §13.6.1 → §13.6.2 → §13.6.3, not §13.6.1 → §13.6.3).
  * No orphan content (every paragraph is under some heading).
  * No new top-level section is misnumbered (e.g., §14 D-INGRESS introduces `## 14.` not `## 15.`).
* **Mechanization.** Markdown parser; emit heading tree; verify monotonicity per section.
* **Failure.** BLOCKING.

### §6.6 V16 — New clause-ID uniqueness across document

For C-1 promoted clauses and D-INGRESS-1..9:

* **Check.** The new clause-ID's *defining* heading (e.g., `#### 13.6.2 D-FAULT-6b — ...`) appears exactly once in the post-mutation file. The clause-ID itself may appear additional times as references in other sections, but the heading-anchor definition is unique.
* **Mechanization.** Heading-extraction + grep: `grep -cE '^#### [0-9.]+ D-FAULT-6b ' docs/phase_4b_deterministic_semantics.md` returns `1`.
* **Failure.** BLOCKING.

### §6.7 V17 — Cross-reference resolvability

For each citation (anchor or reference) in the newly-inserted clause body:

* **Check.** Each cited clause-ID resolves to a defining heading or paragraph in the post-mutation document. References to framework documents resolve to existing files at the cited path.
* **Mechanization.**
  * Clause-ID references: `grep -F '<cited-ID>' docs/phase_4b_deterministic_semantics.md` returns ≥ 1.
  * Framework-doc references: file at the cited path exists.
* **Failure.** BLOCKING.

---

## §7. Stage 4 — Post-Commit Cross-AAU Validation

Runs after `git commit`; before the next AAU starts. Three validators (V18–V20).

### §7.1 V18 — Replay-test invariant

* **Check.** The substrate's replay-identity test (`tools/check_session_replay_identity.py`) continues to pass byte-identically across the 3-cycle SessionPackage comparator. The events.jsonl SHA-256 invariant established at Step 8 Phase 6 holds.
* **Scope.** Per-wave (end-of-wave), not per-AAU. Running V18 after every AAU is wasteful (no AAU mutates runtime code).
* **Layer-B-defined mechanism.** Invoke `tools/check_session_replay_identity.py` against the validated cycle baseline.
* **Layer-D-defined cadence.** When V18 runs (after every AAU? end of every wave? end of all 6 waves?) is governed by Layer D's cross-clause governance plan. Layer B specifies only that V18 is BLOCKING when it runs.
* **Failure.** BLOCKING. A replay-test regression after a documentation-only mutation indicates either (a) a contract mutation that runtime code consumes (a fundamental Layer A violation), or (b) a test-harness regression in the replay tool itself. Either case halts the wave and triggers Layer D investigation (deferred).

**Sub-finding 7.1.A.** V18 is the constitutional safety net: even with all 17 Stage 1–3 validators passing, V18 catches the unlikely case where a documentation mutation accidentally affects a runtime-reachable string (e.g., a docstring parsed by runtime code).

### §7.2 V19 — Inter-wave citation-gap

* **Check.** At the end of each wave, every citation in every AAU committed within the wave resolves to a clause-ID present in the contract at end-of-wave. No "phantom forward citation" survives wave commit.
* **Mechanization.** Iterate over all newly-committed clause bodies in the wave; for each citation, run V17. If V17 was BLOCKING per-AAU in Stage 3, V19 is a redundant aggregate check — its independent value is catching the cross-AAU case where citation A→B→C must hold *after* the wave settles.
* **Failure.** BLOCKING. Halt the wave; investigate.

### §7.3 V20 — Normative-consistency check

For C-1 promoted clauses:

* **Check.** The new clause's normative statement does not contradict any existing clause. Specifically, a new MUST does not contradict an existing MUST NOT for the same subject; a new admittance does not contradict an existing foreclosure.
* **Mechanization.** Manual. (Mechanizing this requires a semantic model of the contract; out of scope for Layer B.)
* **Failure.** SOFT. Layer B flags; Layer C reviewer (deferred) makes the final judgment.

**Sub-finding 7.A.** V18 and V19 are the two BLOCKING Stage-4 validators. V20 is SOFT because semantic consistency cannot be mechanized at Layer B's depth.

---

## §8. Mutation-shape-specific validation overlays

Each shape has additional shape-specific validator requirements beyond V1–V20:

### §8.1 PTA (pure-tail append) overlay

| AAU sub-type | extra check | mechanism |
|---|---|---|
| D-FAULT-15 row | row number is strictly N+1 of the prior last row | parse table; verify row 31 follows row 30, row 32 follows row 31, etc. |
| §0 glossary entry | new entry does not duplicate an existing entry's term | grep glossary for the new term |
| §14 D-INGRESS (whole section) | the entire section's internal cross-references (D-INGRESS-N → D-INGRESS-M) all resolve within the same commit | run V17 against §14's internal citation graph |

### §8.2 STA (section-tail append) overlay

| AAU sub-type | extra check | mechanism |
|---|---|---|
| D-SCHED-14 | new subsection number is strictly N+1 of §2's prior last subsection | parse §2 headings |
| D-REPLAY-10 | same, against §4 | parse §4 headings |
| C-2 embedded note (T1, T4, T5, T8) | embedded note does NOT receive a clause-ID (T1/T4/T5/T8 are explanatory only per codification §1) | grep new subsection body for any "D-EXEC-N", "D-SCHED-N", etc. heading-style ID pattern; FAIL if found |

### §8.3 FII (family-internal insertion) overlay — HIGHEST RISK

| AAU | extra check | mechanism |
|---|---|---|
| D-FAULT-6b / D-FAULT-6c | next family heading `### 13.7 D-FAULT-7` is unchanged (text + section number) | pre/post grep + diff inspection |
| D-FAULT-9b / D-FAULT-9c | next family heading `### 13.10 D-FAULT-10` is unchanged | pre/post grep + diff inspection |
| D-FAULT-6c (Wave 1, after 6b) | D-FAULT-6c's anchor was re-derived to use D-FAULT-6b (now-existing) as preceding context | check anchor text for "D-FAULT-6b" presence |
| D-FAULT-9c (Wave 3, after 9b) | same pattern as D-FAULT-6c | same |

**Sub-finding 8.3.A.** FII's "next family heading unchanged" check is the dedicated guard against the renumbering hazard noted in Layer A §6.

### §8.4 SF (status flip) overlay

| extra check | mechanism |
|---|---|
| §11 items 2–4 are byte-identical to pre-mutation | `git diff docs/phase_4b_deterministic_semantics.md` for the §11 region shows changes only within item 1's region; items 2–4 produce zero diff lines |
| The CLOSED marker explicitly cites both Lemma L3 and D-INGRESS-4 (per codification-plan §7) | grep new_string for "L3" AND "D-INGRESS-4" |
| Item 1's original text appears verbatim within the modified region (Property S1) | covered by V12 |

---

## §9. Property A1–A3 mechanization specification

The mechanization of V11 (Properties A1–A3) is defined as follows for the Layer-B-implementing-agent:

**Tooling.** A single Bash check sequence executed after every non-SF AAU's Edit returns:

```
# Sketch — exact incantation deferred to Layer-B-implementing-agent.
DIFF=$(git diff --no-color docs/phase_4b_deterministic_semantics.md)
DELETED_LINES=$(printf '%s\n' "$DIFF" | grep -cE '^-[^-]' || true)
INSERTED_LINES=$(printf '%s\n' "$DIFF" | grep -cE '^\+[^+]' || true)
# Property A3 enforcement:
[ "$DELETED_LINES" = "0" ] || fail "Property A3 violated"
[ "$INSERTED_LINES" -gt 0 ] || fail "AAU produced no insertion"
```

**Sufficiency.** A3 implies A1 (no deletions ⇒ all pre-existing lines preserved at their original or later positions) and A2 (no characters removed ⇒ pre-mutation character multiset preserved).

**Edge case — whitespace-only changes.** Edit may produce a `-`/`+` pair that is purely a trailing-whitespace difference. Layer B treats whitespace-only `-`/`+` pairs as Property-A3 violations because they indicate the mutation accidentally touched a pre-existing line. The AAU author must reset and re-author with a cleaner Edit (likely using a larger `old_string` so the anchor's surrounding context is preserved exactly).

**Edge case — line-ending changes.** Same treatment as whitespace.

---

## §10. Property S1–S3 mechanization specification

The mechanization of V12 (Properties S1–S3) is defined as follows for the SF AAU:

**Tooling.** A diff-aware inspector that:

1. Identifies the single modified region in `git diff docs/phase_4b_deterministic_semantics.md`.
2. For each `-`/`+` line pair in the region, verifies S1: the `+` line starts with the `-` line's content as a prefix.
3. Verifies S2: the `-` line's non-whitespace characters all appear in the `+` line at preserved relative positions.
4. Verifies S3: at most one hunk exists in the diff; that hunk is contained entirely within §11.

**Failure modes to detect:**
* The CLOSED marker replaces (rather than appends to) item 1's text → S1 fails.
* The CLOSED marker is inserted on a different line that reorders item 1's text → S1 fails.
* §11 items 2, 3, or 4 are touched → §8.4 SF overlay fails.

---

## §11. Citation-chain verification workflow

The citation-chain verification workflow operationalizes V5 (pre-mutation), V17 (post-mutation), and V19 (post-wave). It applies to all clause bodies that contain citations.

**Per-AAU citation verification (V5 + V17):**

1. Parse the new clause body into Citations section (per V3 + V4 markers).
2. Extract anchor and reference citation lists.
3. For each citation:
   * If it is a clause-ID: confirm the clause-ID exists in the contract (pre-mutation for V5; post-mutation for V17).
   * If it is a framework-doc reference: confirm it appears in Section C only (V9) AND the file exists at the cited path.
4. Verify citation depth ≤ 1 (per extraction-plan §4.2.A): no anchor citation transitively cites the AAU being authored. Mechanization: graph traversal over the citation DAG.

**Per-wave citation verification (V19):**

After every AAU in a wave is committed, run V17 against every wave-committed clause body and confirm all citations resolve. Aggregate failure if any AAU's citations broke as a consequence of a sibling AAU's mutations.

**Cross-wave citation verification:**

After every wave, confirm no AAU in a *later* wave has its anchor-citation set broken by a mutation in *this* wave. (Practically: this is enforced by Layer A's wave ordering; V19 is the mechanical guard.)

---

## §12. Override-statement verification workflow (V8)

D-FAULT-9c is the only AAU requiring V8. The workflow:

1. After D-FAULT-9c's draft body is composed (Stage 2), V8 runs.
2. V8 checks: the body contains a paragraph that:
   * names D-FAULT-9a explicitly,
   * uses the word "override" (or "overrides", "overriding", "supersedes"),
   * names `manual_advance` explicitly,
   * acknowledges that D-FAULT-9a's text is preserved verbatim.
3. All four conditions must hold. Partial satisfaction = FAIL.

**Why V8 is BLOCKING.** D-FAULT-9a's text is not modified by any AAU. If D-FAULT-9c lacks the override statement, a reader of the post-Wave-3 contract would see D-FAULT-9a reserving `manual_advance` AND D-FAULT-9c forbidding it without explicit acknowledgment of the relationship. This is a silent contradiction that V8 specifically forecloses.

---

## §13. Framework-reference confinement (V9 detail)

The framework-reference confinement rule operationalizes the extraction-plan §5.3 leakage-prevention list.

**Patterns prohibited in Sections A and B:**

| pattern | examples |
|---|---|
| framework filenames | `phase_4b_step11_admissibility_framework.md`, `phase_4b_step11_extraction_plan.md`, `phase_4b_step12_*.md` |
| lemma labels | `L1`, `L2`, `L3`, `L4` (when used as primary citation; clause-IDs that happen to start with `L` are not lemmas) |
| finding labels | `F1`–`F65`, `F58`, `F59`, future `FN` |
| threat-model labels | `Threat 1` … `Threat 8` |
| analysis-document section anchors | `§B.4`, `§D.3`, `§F.8`, `§U.1` (when these refer to framework docs) |

**Patterns permitted in Section C (Note) only:**

All of the above, used as navigational references for the reader.

**Patterns permitted in any section:**

* Clause-ID citations to existing or other-new clauses in the contract.
* Glossary-term references.

**Mechanization complexity.** Distinguishing "L3 the framework lemma" from a hypothetical "L3 the contract clause" requires section-context awareness. Layer B specifies: until a contract clause is named `L<N>`, the regex `^L[0-9]+$|\bL[0-9]+\b` in Sections A/B is BLOCKING. If a future contract introduces an `L`-prefixed clause-ID family, this rule is revisited.

---

## §14. Three-section template enforcement (V3 detail)

The three-section clause-body template per extraction-plan §6 is enforced as follows:

**Required structure for C-1 promoted clauses:**

```
**<clause-ID>** — <one-line clause name>. <normative statement using MUST/MUST NOT/...>

[<extended Rule paragraphs as needed>]

**Citations.**
* Anchor: <list of clause-IDs separated by commas>
* Reference: <optional list of clause-IDs or framework refs>

*Note.* [optional non-normative explanation, mirrors existing *Rationale.* convention; may cite framework documents]
```

**V3 validator:**

1. Confirm the clause body has a first paragraph containing the clause-ID and a normative keyword.
2. Confirm a `**Citations.**` marker (or semantically equivalent — e.g., `### N.N.K Citations` sub-heading) exists.
3. Confirm an optional `*Note.*` or `*Rationale.*` marker (or sub-heading) is recognized if present.
4. Confirm no other content appears between Rule and Citations (no interleaved bullet lists that aren't part of the Rule paragraph).

**Exact marker syntax.** Layer B specifies the *contract* (Rule / Citations / optional Note must be detectable); the Layer-B-implementing-agent chooses the exact marker syntax that the validator parses. Both `**Citations.**` (inline-bold) and `#### N.N.K Citations` (heading) are acceptable as long as the validator handles them consistently.

**V3 applicability.** C-1 promoted clauses only (8 clause-body AAUs: D-FAULT-6b, D-FAULT-6c, D-FAULT-9b, D-FAULT-9c, D-SCHED-14, D-REPLAY-10, plus 9 D-INGRESS clauses inside §14's single AAU = 17 clause bodies total). D-FAULT-15 rows are validated by V10, not V3. C-2 embedded notes (T1, T4, T5, T8) are validated as STA subsections without the three-section template (they are explanatory, not normative).

---

## §15. Validator sequencing per AAU

For one AAU, the validator sequence and ordering rules:

```
[Layer A stage 1: baseline]    git status clean
[Layer A stage 2: anchor]      → V1 (anchor uniqueness pre)
                               → V2 (anchor stability)
[Layer A stage 3: site read]   read anchor region
[Layer B stage 2: body draft]  AAU author composes clause body
                               → V3 (template presence)            [C-1 only]
                               → V4 (citation classification)      [C-1 only]
                               → V5 (anchor-cite existing-clause)  [C-1 + D-FAULT-15]
                               → V6 (minimal-enforceable-surface)  [all bodies; SOFT]
                               → V7 (hidden-widening scan)         [C-1 only; SOFT]
                               → V8 (override-statement presence)  [D-FAULT-9c only]
                               → V9 (framework-ref confinement)    [all bodies]
                               → V10 (D-FAULT-15 row format)       [D-FAULT-15 only]
                               → §8 shape-specific overlay checks
[Layer A stage 4: mutation]    Edit tool executes
[Layer A stage 5: shape]       → V11 (Properties A1–A3) or V12 (Properties S1–S3)
                               → V14 (existing-text byte preservation; covered by V11)
[Layer A stage 6: anchor]      → V13 (anchor uniqueness post)
[Layer A stage 7: structure]   → V15 (heading-DAG structure)
                               → V16 (new clause-ID uniqueness)
                               → V17 (cross-reference resolvability)
[Layer A stage 8: commit]      git commit
[Layer B stage 4: post-commit] → V20 (normative-consistency)        [C-1 only; SOFT]
[end-of-wave]                  → V18 (replay-test invariant)
                               → V19 (inter-wave citation-gap)
[ready for next AAU]
```

**Sub-finding 15.A.** Within Stage 2, validators are order-independent. Within Stage 3, V11/V12 must run before V13–V17 (the post-mutation state must satisfy A1–A3/S1–S3 before subsequent checks are meaningful).

---

## §16. Failure-handling protocol

Failure classes and their handling:

| failure class | action on FAIL | recovery path |
|---|---|---|
| **BLOCKING** | AAU MUST NOT commit | revise the AAU draft or anchor; re-run all validators from Stage 1 or Stage 2 (per failure point) |
| **SOFT** | AAU MAY commit with the flag attached to the commit message | flag becomes a Layer C reviewer responsibility (deferred); Layer B logs the flag but does not block |
| **ADVISORY** | AAU commits normally | informational only; no required action |

**Layer B introduces no ADVISORY failures.** All 20 validators are either BLOCKING (15) or SOFT (V6, V7, V20; 3 validators).

**Recovery from BLOCKING at Stage 3.** If V11–V17 fail after Edit returns:

1. `git checkout -- docs/phase_4b_deterministic_semantics.md` to discard the failed mutation.
2. Return to Layer A stage 1 (baseline).
3. Re-derive the AAU's anchor, body, or mutation strategy per the validator's failure message.
4. Re-run Stages 1–3.

**Recovery from BLOCKING at Stage 4.** If V18, V19, or any post-commit BLOCKING validator fails:

1. The wave is halted.
2. The most-recent AAU's commit is reverted via `git revert <commit-sha>` per Layer A §13.
3. The failure is investigated; the AAU's draft is revised; the AAU is re-authored as a fresh commit.

**No-amend invariant.** Per Layer A §16, failed AAUs are never `git commit --amend`ed. The audit trail (failed AAU → revert → re-authored AAU) is preserved across all failure recovery paths.

---

## §17. Authoring rejection criteria

An AAU is **REJECTED** (vs revised) under any of:

1. The AAU's anchor cannot be made unique without exceeding ±20 lines (Layer A's anchor locality rule).
2. The AAU's clause-body draft, after three revision attempts, still fails V3, V4, V5, V8, V9, or V10.
3. The AAU's intended insertion would violate Properties A1–A3 or S1–S3 inherent in its shape (e.g., a proposed FII that would require renumbering existing sub-subsections).
4. The AAU's citation set requires a forward reference that no wave-reordering can satisfy.

A REJECTED AAU triggers escalation to Layer D (cross-clause governance; deferred): the AAU is removed from the wave plan; the codification plan (`phase_4b_step11_codification_plan.md`) is re-evaluated; the extraction plan is updated; Layers A and B are re-applied to any new AAU substituted in its place.

**Sub-finding 17.A.** REJECTED is an *exceptional* path. Under the Step 11 extraction plan, all 29 AAUs were designed to be authorable; rejection arises only from unanticipated structural barriers discovered during authoring.

---

## §18. Pre-commit validation envelope

The set of validators that MUST pass before `git commit` for a given AAU:

| shape | pre-commit BLOCKING set |
|---|---|
| PTA (D-FAULT-15 row) | V1, V2, V5, V9, V10, V11, V13, V14, V15, V17, §8.1 overlay |
| PTA (§0 glossary entry) | V1, V2, V9, V11, V13, V14, V15, §8.1 overlay |
| PTA (§14 D-INGRESS whole section) | V1, V2, V3, V4, V5, V8 [N/A unless §14 contains D-FAULT-9c text — it doesn't], V9, V11, V13, V14, V15, V16, V17, §8.1 overlay |
| STA (D-SCHED-14, D-REPLAY-10) | V1, V2, V3, V4, V5, V9, V11, V13, V14, V15, V16, V17, §8.2 overlay |
| STA (C-2 embedded note T1/T4/T5/T8) | V1, V2, V9, V11, V13, V14, V15, §8.2 overlay |
| FII (D-FAULT-6b, D-FAULT-6c, D-FAULT-9b) | V1, V2, V3, V4, V5, V9, V11, V13, V14, V15, V16, V17, §8.3 overlay |
| FII (D-FAULT-9c) | V1, V2, V3, V4, V5, V8, V9, V11, V13, V14, V15, V16, V17, §8.3 overlay |
| SF (§11 item 1) | V1, V2 [partial, see §4.2], V12, V13, V15, V17, §8.4 overlay |

**SOFT validators (V6, V7, V20)** run but do not block commit; their flags are recorded and deferred.

---

## §19. Post-commit audit sequencing

After each AAU commits:

1. Run V20 against the new clause body (SOFT; flags attached to next commit if any).
2. If this AAU is the LAST in its wave: run V18 (replay-test invariant) and V19 (inter-wave citation gap).
3. If V18 or V19 fails: halt; trigger §16 recovery.
4. Otherwise: the wave is closed; the next wave's AAU sequence may begin.

**V18 cadence (Layer B's recommendation; final cadence is Layer D's decision):** end-of-wave is the minimum-acceptable cadence. End-of-every-AAU is recommended for the FII AAUs (highest-risk shape) and the SF AAU (the only mutation). Layer D may codify either.

---

## §20. Layer-B open questions (deferred to Layer C / Layer D)

Layer B intentionally does NOT specify:

* The reviewer UI for inspecting validator output (Layer C).
* The clause-body review template shown to the reviewer (Layer C).
* The PR boundary policy that bundles AAU commits into review units (Layer D).
* The replay-test invocation cadence beyond Layer B's "end-of-wave minimum" recommendation (Layer D).
* The cross-clause regression-prevention process beyond the per-AAU + per-wave validators (Layer D).
* The post-authoring sequencing that validates the contract's final form after all 29 AAUs commit (Layer D).
* The mechanization implementation of any validator (deferred to Layer-B-implementing-agent at authoring time).
* The exact marker syntax for Section A / B / C delimiters in clause bodies (deferred to Layer-B-implementing-agent).
* The full list of banned-phrase patterns for V7 per AAU (deferred to Layer-B-implementing-agent; extraction-plan §8 provides the seed list).

---

## §21. Layer-B vocabulary

Layer B introduces three planning-doc terms; none enter the normative contract:

| term | meaning | scope |
|---|---|---|
| Validator (V<N>) | A named, scoped check applied during the AAU lifecycle | this planning doc + Layer-B-implementing-agent |
| Failure class (BLOCKING / SOFT) | The action triggered by a validator FAIL | this planning doc |
| Stage 1–4 | The four-stage AAU validation lifecycle | this planning doc |

None receive clause IDs. Per "no namespace churn" — purely validation-process vocabulary.

---

## §22. Layer-B planning verdict

**LAYER B: READY.**

* 20 validators catalogued (V1–V20) across 4 stages.
* Each validator has stable ID, scope, stage, mechanization level, failure class, per-shape applicability.
* 14 mechanical + 4 semi-mechanical + 2 manual; 70% strict mechanization, 90% if semi-mechanical is counted.
* Three SOFT validators (V6, V7, V20); 17 BLOCKING validators.
* Four-stage validation lifecycle aligned with Layer A's 8-stage safety protocol.
* Shape-specific overlay validators for PTA, STA, FII, SF in §8.
* Property A1–A3 mechanization sketch in §9.
* Property S1–S3 mechanization sketch in §10.
* Citation-chain workflow in §11 covering per-AAU, per-wave, cross-wave.
* Override-statement workflow (V8) for D-FAULT-9c in §12.
* Framework-reference confinement (V9) detailed in §13.
* Three-section template enforcement (V3) detailed in §14.
* Per-AAU validator sequencing in §15.
* Failure-handling protocol (BLOCKING / SOFT) in §16.
* REJECTED criteria + escalation path in §17.
* Pre-commit validation envelope per shape in §18.
* Post-commit audit sequencing in §19.
* Layer C / Layer D dependencies stated; not implemented.

The plan does NOT mutate any artifact. The plan does NOT author clause wording. The plan does NOT design reviewer UI. The plan does NOT sequence PRs. The plan IS the validation overlay on the Layer-A mutation acts.

---

## §23. Preserved invariants under Layer B

| invariant | Layer-B mechanism |
|---|---|
| replay-authoritative truth | V18 (replay-test invariant) enforces byte-identical events.jsonl SHA-256 across the 3-cycle baseline |
| append-only causality | V11 (Properties A1–A3) BLOCKING for 28 AAUs; V12 (Properties S1–S3) BLOCKING for 1 SF AAU |
| authority singularity | V20 (normative-consistency) flags any new clause that admits a second authority for an existing class; SOFT but reviewer-mandatory |
| orchestration_tick supremacy | V18 catches any documentation mutation that runtime code consumes |
| deterministic interruption boundaries | V7 hidden-widening scan banned phrases for D-FAULT-6b (e.g., "next-tick observation") prevent silent semantic drift |
| Phase-A-only observability | V7 banned phrases for D-FAULT-6c prevent unqualified "observation" leaking ingress out of Phase A |
| contradiction preservation | V8 (override-statement) ensures D-FAULT-9c explicitly acknowledges D-FAULT-9a's preserved text |
| transport independence | V9 (framework-ref confinement) ensures T5 embedding doesn't smuggle transport-coupling language into Sections A/B |
| no hidden cleanup | V11 + V14 enforce Property A2 (character superset) |
| no wall-clock authority | V7 banned phrases for D-INGRESS-8 and D-FAULT-15 row 38 prevent wall-clock language in Rule sections |
| no adaptive semantics | V20 flags any new clause introducing conditional / "may eventually" language; SOFT but reviewer-mandatory |
| framework/contract separation | V9 BLOCKING on framework references in Sections A/B |
| additive-only mutation discipline | V11 (Properties A1–A3) and V12 (Properties S1–S3) BLOCKING; the discipline is Layer A's; Layer B is its enforcement |
| replay-preserving extraction safety | V18 + V19 enforce the extraction-plan §9 wave invariants |

All preserved at the validation level.

---

**End of Step 12 Layer B per-clause validation plan.**

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance](phase_4b_step11_f59_manual_advance_analysis.md), [closure verification](phase_4b_step11_closure_verification.md), [codification plan](phase_4b_step11_codification_plan.md), [meta-audit](phase_4b_step11_meta_audit.md), [extraction plan](phase_4b_step11_extraction_plan.md), [Layer A authoring mechanics](phase_4b_step12_authoring_mechanics_plan.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).

Successors (deferred): Layer C (review ergonomics), Layer D (cross-clause governance).
