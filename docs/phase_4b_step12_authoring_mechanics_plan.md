# Phase 4B Step 12 — Authoring Mechanics Plan (Layer A — Pre-Authoring)

**Status: PRE-AUTHORING LAYER-A MUTATION-MECHANICS PLAN (2026-05-21).** Designs the *physical act* of mutating [`phase_4b_deterministic_semantics.md`](phase_4b_deterministic_semantics.md) during the future Step 12 contract-authoring phase. Inherits the 38-insertion catalog, 6-wave order, and citation discipline from [`phase_4b_step11_extraction_plan.md`](phase_4b_step11_extraction_plan.md). Does **not** author clause wording. Does **not** mutate the contract document. Does **not** change *what* is codified — only *how* each insertion is physically performed safely.

This is Layer A of the four-layer transition plan. Layers B (per-clause validation), C (review ergonomics), and D (cross-clause governance) are deferred to subsequent planning passes.

---

## §1. Scope and inheritance

| inherited from | element |
|---|---|
| Step 11 codification plan §1–§8 | what is codified, where, at which clause-ID |
| Step 11 extraction plan §1–§13 | 38-insertion catalog, 6-wave order, citation DAG, three-section clause-body template, override-statement discipline |
| Step 11 meta-audit §15 | architectural-coherence verdict (no structural defects) |
| this document | per-AAU mutation shape, anchor protocol, pre/post-flight checks, commit cadence, reversibility, Edit-tool-only discipline |

Layer A specifies only the safety overlay on the *physical insertion act*. It does not interpret, expand, or modify any inherited decision.

---

## §2. The Atomic Authoring Unit (AAU)

An **Atomic Authoring Unit** is the indivisible insertion act, defined as:

* One AAU = exactly one of the 38 catalogued insertions from extraction-plan §1, with the §14 D-INGRESS section treated as a single coherent AAU (see §2.1).
* One AAU = one git commit.
* One AAU = one set of contiguous file edits in a single tool invocation cycle (Read → Edit → verify → commit), with no interleaving against any other AAU.

The 1-AAU-to-1-commit invariant is the structural prerequisite for the reversibility envelope of §13.

### §2.1 §14 D-INGRESS treated as one AAU

Extraction-plan §1 enumerates §14 as "1 section + 9 clauses + scope + restatement" (11 insertions). Layer A designates §14 as **one AAU committed atomically**.

**Rationale.** The §14 internal coherence requirement (scope must reference all D-INGRESS clauses; the restatement bookends the section; D-INGRESS-N may cross-reference D-INGRESS-M for M < N) makes a sequence of 11 partial-§14 commits structurally fragile — each intermediate commit would publish an incomplete-cross-reference §14. One coherent §14 commit eliminates that fragility.

The §14-as-one-AAU choice is the only Layer-A commit-cadence decision that diverges from a strict insertion-by-insertion mapping. All 27 other AAUs map 1:1 to the catalog.

**Sub-finding 2.1.A.** Total AAU count: 4 (Wave 1) + 1 (Wave 2) + 2 (Wave 3) + 12 (Wave 4) + 6 (Wave 5) + 4 (Wave 6) = **29 AAUs across 6 waves**.

---

## §3. The four mutation shapes

The 29 AAUs partition into four mutation shapes, each with a distinct safety surface:

| shape | description | AAUs |
|---|---|---|
| **Pure-tail append (PTA)** | Insertion at the very tail of an existing structural unit (table, list, or document body) — no insertion-point selection beyond "after the last existing element" | D-FAULT-15 rows 31–42 (12); §0 glossary entries (5); §14 D-INGRESS whole new section (1) |
| **Section-tail append (STA)** | New subsection appended at the end of an existing top-level section, immediately before the next top-level section's heading | D-SCHED-14; D-REPLAY-10; C-2 embedded notes T1, T4, T5, T8 (4) |
| **Family-internal insertion (FII)** | New sub-subsection inserted *between* existing sub-subsections of a clause family, with no existing-text modification | D-FAULT-6b; D-FAULT-6c; D-FAULT-9b; D-FAULT-9c |
| **Status flip (SF)** | Modification of existing text to append a status marker, preserving the original text verbatim as a prefix of the modified text | §11 open-extension item 1 → CLOSED (one AAU) |

**Sub-finding 3.A.** PTA = 18 AAUs, STA = 6 AAUs, FII = 4 AAUs, SF = 1 AAU. Total = 29.

**Sub-finding 3.B.** Only the single SF AAU mutates pre-existing contract text. The other 28 AAUs are pure additions. Layer A's safety properties (§14) treat the SF case under a distinct property set.

---

## §4. Insertion anchors

Each AAU MUST specify an **insertion anchor** — a verbatim text excerpt from the current contract document used to identify the insertion point unambiguously.

**Anchor properties (REQUIRED):**

| property | rule |
|---|---|
| Verbatim | The anchor text MUST be copy-pasted from the current contract, not paraphrased or summarized. |
| Unique | `grep -c '<anchor>' phase_4b_deterministic_semantics.md` MUST return exactly `1`. |
| Local | The anchor MUST be within ±20 lines of the insertion point. |
| Stable | For non-SF AAUs, the anchor MUST NOT overlap any text the AAU modifies (the AAU only inserts adjacent to the anchor). |

For the single SF AAU, the anchor IS the text being modified, and the mutation is structured as Edit's `old_string` → `new_string` per §8.

For all 28 non-SF AAUs, the anchor is read-only context and the mutation is a pure insertion adjacent to the anchor.

**Anchor specification ownership.** The precise anchor text for each of the 29 AAUs is to be authored as part of the Layer B per-clause checklist; Layer A specifies only the *requirement structure* for anchors, not their final strings.

---

## §5. Section-tail append (STA) mechanic

Applies to: **D-SCHED-14, D-REPLAY-10, T1 embedded note, T4 embedded note, T5 embedded note, T8 embedded note** (6 AAUs).

**Pre-flight.**

1. Identify the next top-level section header (e.g., for D-SCHED-14: `^## 3\. EventBus`); confirm exactly one match.
2. Identify the current last subsection of the target section (e.g., for §2 D-SCHED: `### 2.6 Non-goals`); confirm exactly one match.
3. Read the ±20-line region around the boundary between the two; confirm only blank line(s) separate them.

**Mutation.**

* Insert the new subsection immediately AFTER the last subsection's full body, BEFORE the next top-level section heading.
* New subsection heading uses the next sequential subsection number within the target section (e.g., `### 2.7 D-SCHED-14 — …`).
* New subsection ends with exactly one trailing blank line before the next top-level heading.

**Post-flight.**

1. `git diff` shows only `+` lines (Property A3 — see §14).
2. The previous last subsection heading still returns exactly one grep match (existing-text unchanged).
3. The next top-level section heading is unmodified and unmoved (its content is unchanged; its line number shifts downward by the insertion delta).

---

## §6. Family-internal insertion (FII) mechanic — HIGHEST RISK

Applies to: **D-FAULT-6b, D-FAULT-6c, D-FAULT-9b, D-FAULT-9c** (4 AAUs).

**Pre-flight.**

1. Identify the last existing sub-subsection of the target family (e.g., for D-FAULT-6b: §13.6.1 D-FAULT-6a Phase E atomicity); confirm exactly one match.
2. Identify the next family's first subsection (e.g., for D-FAULT-6b: §13.7 D-FAULT-7); confirm exactly one match.
3. Read the ±20-line region across the family boundary; confirm only blank line(s) separate the two.

**Mutation.**

* Insert the new sub-subsection immediately AFTER the last sub-subsection of the target family, BEFORE the next family's first subsection heading.
* New sub-subsection heading uses the next sequential sub-subsection number (e.g., `#### 13.6.2 D-FAULT-6b — …`; or `#### 13.6.3 D-FAULT-6c — …` after D-FAULT-6b is in place).
* For Wave 1's two family-internal AAUs in the same family (D-FAULT-6b and D-FAULT-6c), commit D-FAULT-6b FIRST, then re-derive the anchor for D-FAULT-6c (whose immediately-preceding sub-subsection is now D-FAULT-6b, not D-FAULT-6a). Same discipline for D-FAULT-9b / D-FAULT-9c in Wave 3.

**Post-flight.**

1. `git diff` shows only `+` lines.
2. The next family's first subsection heading (`### 13.7 D-FAULT-7`, `### 13.10 D-FAULT-10`) is unchanged in text and unchanged in numbering. **NO renumbering of D-FAULT-7 to D-FAULT-8 or similar.**
3. Sub-subsection numbers within the target family monotonically increase (e.g., 13.6.1 → 13.6.2 → 13.6.3).

**Specific hazard.** A naïve author or a misconfigured tool might "promote" D-FAULT-6b by renaming D-FAULT-7 to D-FAULT-8 (treating sequence-letter promotion as sequence-number renumbering). This would break every citation of D-FAULT-7..D-FAULT-15 in the contract, tests, and analyses. Post-flight check #2 is the dedicated guard. Layer B's automated check (deferred) will mechanize this.

**Sub-finding 6.A.** FII is the highest-risk shape because the insertion point sits between *two* protected regions, both of which must remain unchanged. PTA and STA each have only one protected boundary.

---

## §7. Pure-tail append (PTA) mechanic

Applies to: **D-FAULT-15 rows 31–42 (12), §0 glossary entries (5), §14 D-INGRESS as one whole new section (1)** — 18 AAUs.

**Pre-flight (per shape sub-variant).**

* **D-FAULT-15 row.** Locate the D-FAULT-15 table; identify the last existing row's number (must be 30 pre-Wave-4, then incrementally 31, 32, … through Wave 4's 12 AAUs). Confirm rows 1–N intact (no gaps).
* **§0 glossary entry.** Locate the glossary structure (table or definition list); identify the last existing entry. Confirm prior entries intact.
* **§14 D-INGRESS (single AAU).** Confirm §13's closing content; confirm no §14 currently exists; confirm the file's trailing content (closing matter, if any) is positioned where §14 will be appended.

**Mutation.**

* **D-FAULT-15 row.** Append exactly one row at the end of the table, preserving column alignment and the table's markdown shape.
* **§0 glossary entry.** Append one new entry to the glossary list/table. Layer A does not mandate alphabetical ordering; codification-plan §5 enumerates the 5 entries.
* **§14 D-INGRESS.** Append the full §14 (heading + scope §14.1 + D-INGRESS-1..9 as §14.2..§14.10 + restatement §14.11) after the last content line of §13 and before any document end-matter.

**Post-flight.**

1. `git diff` shows only `+` lines.
2. Last pre-existing row/entry text unchanged.
3. Markdown structure remains valid (no orphan content; no broken table boundary).
4. For §14: heading number is exactly `## 14.`; no §15 emerges.

---

## §8. Status-flip (SF) mechanic — UNIQUE CASE

Applies to: **§11 open-extension item 1 → CLOSED** (1 AAU).

This is the only AAU in the entire 38-insertion plan that mutates existing contract text. Layer A treats it under a dedicated discipline (Properties S1–S3, §14).

**Pre-flight.**

1. Read §11 verbatim. Identify item 1's exact text (the `OperatorOverride` event commutativity entry).
2. Confirm items 2–4 of §11 are present and unchanged from current state.
3. Plan the modification: prepend or append a `**CLOSED** (see L3, D-INGRESS-4)` marker; preserve the original item 1 text verbatim within the modified line(s).

**Mutation.**

* Use the Edit tool with `old_string` → `new_string`.
* `old_string` is the exact item-1 text, padded with enough adjacent context (preceding line, following line) to be unique within the file.
* `new_string` is `old_string` with the CLOSED marker added as a suffix or as a new adjacent line; the original item-1 text must appear verbatim within `new_string`.

**Post-flight.**

1. `git diff` shows: one modified region containing item 1 + CLOSED marker; original item 1 text preserved verbatim within the modified region (Properties S1–S3).
2. Items 2–4 of §11 unchanged (zero `-` or `+` lines elsewhere in §11).
3. Total mutation: zero deletions of meaningful content (only line-ending change at most).

**Special discipline.** Because this AAU mutates existing text, it MUST be authored as the *last* AAU of Wave 5 and MUST receive a dedicated review pass (Layer C, deferred). The reviewer's task is to confirm that no Step-8/-9/-10 reader could misread the result as "item 1 silently dropped."

---

## §9. Wave-to-AAU map and commit cadence

| wave | AAUs | shape mix | commit count |
|---|---|---|---|
| 1 | D-FAULT-6b (FII), D-FAULT-6c (FII), D-SCHED-14 (STA), D-REPLAY-10 (STA) | 2 FII + 2 STA | 4 |
| 2 | §14 D-INGRESS whole-section (PTA) | 1 PTA | 1 |
| 3 | D-FAULT-9b (FII), D-FAULT-9c (FII) | 2 FII | 2 |
| 4 | D-FAULT-15 rows 31–42 (PTA × 12) | 12 PTA | 12 |
| 5 | §0 glossary entries × 5 (PTA), §11 item 1 status flip (SF) | 5 PTA + 1 SF | 6 |
| 6 | C-2 embedded notes T1, T4, T5, T8 (STA × 4) | 4 STA | 4 |
| **total** | | 18 PTA + 6 STA + 4 FII + 1 SF | **29 commits** |

**Sub-finding 9.A.** Wave 4 is the largest by commit count (12). Wave 2 is the largest by content volume in a single commit (full §14 D-INGRESS).

**Sub-finding 9.B.** Within a wave, AAU order is constrained only where one AAU's anchor depends on another AAU's prior insertion:

* Wave 1: D-FAULT-6c MUST follow D-FAULT-6b (its anchor is now-inserted D-FAULT-6b). Independent: D-SCHED-14 and D-REPLAY-10 may be authored in either order.
* Wave 3: D-FAULT-9c MUST follow D-FAULT-9b. D-FAULT-9c additionally carries the explicit override-relationship statement per extraction-plan §12.
* Wave 4: rows 31–42 MUST be authored in ascending row order (each row's anchor is the prior row).
* Wave 5: §11 SF AAU MUST be the final AAU of the wave.
* Waves 2, 6: order-independent within the wave (single AAU in Wave 2; four independent STAs in Wave 6).

---

## §10. Per-wave authoring sequence

For each wave:

1. **Pre-wave verification.** Confirm prior waves are complete (last commit SHA matches expected) and the working tree is clean. Confirm the contract document matches the prior wave's post-flight baseline.
2. **AAU execution loop.** For each AAU in wave order:
   * Read anchor region (Read tool, narrow line range).
   * Verify anchor uniqueness (Bash grep, count == 1).
   * Verify pre-flight per shape (§5, §6, §7, or §8).
   * Execute mutation (one Edit tool call).
   * Verify post-flight (Bash `git diff` + grep checks).
   * Commit (one AAU = one commit; message format per §11).
   * (Layer B-defined per-clause validation runs here; deferred.)
3. **Post-wave verification.** Run extraction-plan §9 wave invariants:
   * Replay-identity guarantee unchanged (Layer D test invocation; deferred).
   * No inter-wave citation gap (Layer B citation check; deferred).
   * Preserved invariants table (extraction-plan §15) re-confirmed.

---

## §11. Commit-message convention

Each AAU commit message follows:

```
Phase 4B Step 12 / Wave <N> — <AAU label>

<one-line rationale linking to the framework citation>
```

Where `<AAU label>` is one of:
* `D-FAULT-6b promotion (T2)`
* `D-SCHED-14 promotion (T9)`
* `§14 D-INGRESS section (D1–D9)`
* `D-FAULT-15 row 31`
* `§0 glossary entry: OperatorEnvelope`
* `§11 item 1 → CLOSED (L3)`
* etc.

The rationale line cites the framework document, not the analysis chain. Example:

```
Phase 4B Step 12 / Wave 1 — D-FAULT-6c promotion (T3)

Per phase_4b_step11_admissibility_framework.md §B.T3; codified per
phase_4b_step11_codification_plan.md §1; extraction order per
phase_4b_step11_extraction_plan.md §3 Wave 1.
```

**Sub-finding 11.A.** The commit message is the durable record linking the AAU back to its framework derivation; it is not a substitute for the Section C "Note" in the clause body (which Layer B specifies).

---

## §12. Tool-use discipline

| operation | tool | rationale |
|---|---|---|
| Read anchor region (±20 lines) | Read | line-numbered output enables precise insertion verification |
| Verify anchor uniqueness | Bash (`grep -c`) | mechanical count of matches |
| Verify pre-flight | Bash (`grep`, `git diff --stat`) | one-shot pass/fail signal |
| Execute mutation (non-SF AAU) | Edit | preserves line-level git diff; supports `old_string` + insertion via `new_string = old_string + "\n" + inserted` |
| Execute mutation (SF AAU) | Edit | native old/new pattern |
| Verify post-flight | Bash (`git diff`, `grep -c`) | additive-only confirmation |
| Commit | Bash (`git commit`) | one-AAU-one-commit invariant |
| **Write tool on contract document** | **FORBIDDEN** | whole-file replacement loses line-level diff hygiene and produces "all-modified" diffs unreadable by Layer C reviewer |

**Sub-finding 12.A.** The Write tool is permissible for new framework documents (analyses, plans, this doc) but is FORBIDDEN on `phase_4b_deterministic_semantics.md` during the entire Step 12 authoring phase.

---

## §13. Reversibility envelope

Each AAU is reversible via `git revert <AAU-commit-sha>` because:

1. Each AAU = one commit (§2 invariant).
2. Each non-SF commit = pure insertion (Properties A1–A3, §14); `git revert` produces a clean inverse deletion.
3. The single SF commit modifies one region with the original text preserved verbatim (Property S1–S3); `git revert` cleanly removes the appended marker.
4. No commit deletes any pre-existing contract text.

**Reversion sequence (if a Layer B/C/D validation fails post-commit):**

```
git revert <failed-AAU-sha>           # creates inverse commit (clean)
# author the corrected AAU per Layer B/C feedback
git commit                            # re-introduce as a fresh AAU commit
```

**Reversibility hazard.** If two AAUs share a commit (against §2's 1:1 rule), `git revert` necessarily un-does both. The 1:1 invariant is the structural prerequisite for surgical reversibility. This is why §2.1 keeps §14 as one AAU (one revertible unit) rather than 11 partial-§14 AAUs that would force coupled reverts on internal-§14 review feedback.

---

## §14. Additive-only mutation discipline (formal properties)

For each of the 28 non-SF AAUs:

* **Property A1 — Line preservation.** ∀ pre-existing line L at position p, the post-mutation file contains L verbatim at some position p' ≥ p (lines may shift downward by the insertion delta; line contents are preserved).
* **Property A2 — Character superset.** The multiset of characters in the pre-mutation contract file is a subset of the multiset of characters in the post-mutation contract file.
* **Property A3 — Diff shape.** `git diff` shows only `+` lines and zero `-` lines.

For the single SF AAU:

* **Property S1 — Verbatim-prefix preservation.** The modified line's `new_string` contains `old_string` verbatim as a prefix (or as a leading subline if multi-line).
* **Property S2 — No character deletion.** Every non-whitespace character of `old_string` appears in `new_string` at the same relative position.
* **Property S3 — Bounded diff shape.** `git diff` shows the SF region as one or two `-` lines and one or more `+` lines, where the `+` lines reproduce the `-` line content verbatim plus the CLOSED marker.

These properties are mechanically verifiable post-commit and form the Layer-A safety contract.

**Sub-finding 14.A.** Properties A1–A3 and S1–S3 are the formal expression of the "additive-only mutation discipline" invariant from the codification-plan posture. Layer A operationalizes them; Layer B will mechanize their verification (deferred).

---

## §15. Per-AAU safety protocol (8 stages)

| stage | check | tool | failure action |
|---|---|---|---|
| 1. baseline | working tree clean | `git status --porcelain` returns empty | resolve uncommitted state before starting |
| 2. anchor uniqueness (pre) | `grep -c '<anchor>' phase_4b_deterministic_semantics.md` returns `1` | Bash | choose a more specific anchor; abort if no unique anchor exists |
| 3. site read | read ±20-line region around insertion point | Read | inspect mismatch; re-derive anchor |
| 4. mutation | execute the planned insertion | Edit | inspect tool error; abort |
| 5. shape | `git diff` matches Properties A1–A3 (non-SF) or S1–S3 (SF) | `git diff --stat` + `git diff` | `git checkout -- phase_4b_deterministic_semantics.md` and restart from stage 1 |
| 6. anchor uniqueness (post) | `grep -c '<anchor>'` still returns `1` | Bash | restart |
| 7. structure | document is a valid markdown heading DAG (no orphan content) | manual for Wave 1 AAU 1; Layer B mechanizes later | restart |
| 8. commit | one AAU = one commit; message per §11 | `git commit` (HEREDOC body) | resolve hook failures; create NEW commit (never amend per §16) |

Any stage failure = abort AAU, reset working tree to baseline (stage 1), investigate before retrying.

---

## §16. No-amend discipline

For Layer A:

* `git commit --amend` is **FORBIDDEN** during the authoring phase. A failed AAU is reverted (`git revert`) and re-authored, producing two commits (the inverse + the corrected). Never one amended commit.

**Rationale.** Amending after a hook failure or post-flight failure rewrites history in a way that defeats the §13 reversibility envelope. Audit-trail clarity (visible failed AAU → visible revert → visible re-authored AAU) is preferred over a clean linear history.

---

## §17. Layer A open questions (deferred to Layers B/C/D)

Layer A intentionally does NOT specify:

* Clause-body wording validation rules (Layer B).
* Citation-link verification mechanism (Layer B).
* The mechanized check for Property A1–A3 / S1–S3 enforcement (Layer B).
* Reviewer UI / clause-body review template (Layer C).
* Cross-AAU PR boundary policy and reviewer assignment (Layer D).
* Post-wave test-invocation policy (Layer D).
* Replay-comparator verification cadence relative to wave commits (Layer D).
* Definition of the "extraction-plan §9 wave invariants" automation harness (Layer D).

These remain explicitly out of scope for this document.

---

## §18. Layer-A vocabulary

Layer A introduces three planning-doc terms; none are clause-level namespace:

| term | meaning | scope |
|---|---|---|
| AAU | Atomic Authoring Unit | this planning doc + Layer B/C/D planning docs |
| mutation shape | one of {PTA, STA, FII, SF} | this planning doc + Layer B/C/D planning docs |
| anchor | verbatim text excerpt used to locate insertion point | this planning doc + Layer B per-clause checklists |

None of these terms enter the normative contract. None receive clause IDs. Per "no namespace churn" — they are purely authoring-process vocabulary.

---

## §19. Layer-A planning verdict

**LAYER A: READY.**

* 4 mutation shapes catalogued; safety surface differentiated.
* 1:1 AAU-to-commit cadence specified.
* 29-commit total wave-to-commit decomposition.
* §14 D-INGRESS designated as one coherent AAU (single deviation from 1:1 catalog mapping; rationalized).
* Insertion-anchor requirement formalized (verbatim, unique, local, stable).
* Per-shape pre-flight + mutation + post-flight protocols specified.
* Reversibility via `git revert` guaranteed by 1:1 invariant and additive-only properties.
* Additive-only discipline formalized as Properties A1–A3 (28 AAUs) and S1–S3 (1 SF AAU).
* 8-stage per-AAU safety protocol specified.
* Edit-tool-only for contract mutations; Write tool prohibited on contract document.
* No-amend discipline established.
* Commit-message convention specified.
* Layer B/C/D dependencies stated; not implemented.

The plan does NOT mutate any artifact. The plan does NOT author clause wording. The plan IS the safety overlay on the *physical act* of insertion.

---

## §20. Preserved invariants under Layer A

| invariant | Layer-A mechanism |
|---|---|
| replay-authoritative truth | pure insertion preserves all replay-load-bearing text (Property A1) |
| append-only causality | Properties A1–A3 (28 AAUs); Property S1–S3 (1 SF AAU preserves prior text verbatim) |
| authority singularity | no existing-clause modification (28 AAUs); SF AAU modifies §11 metadata only, not an authority binding |
| orchestration_tick supremacy | T1 embedding as STA (Wave 6) |
| Phase-A-only observability | D-FAULT-6c promotion as FII (Wave 1) |
| deterministic interruption boundaries | D-FAULT-6b promotion as FII (Wave 1) |
| Phase E atomicity | D-FAULT-6a preserved verbatim by Property A1 (Wave 1 FII inserts AFTER D-FAULT-6a) |
| contradiction preservation | D-FAULT-5b preserved verbatim by Property A1 (no Wave touches §13.5) |
| transport independence | T5 embedding as STA (Wave 6) |
| reopen-stage replay identity | no test-affecting clause modification across any of 29 AAUs |
| no hidden cleanup | Property A2 (character superset) precludes silent deletion |
| no wall-clock authority | D-INGRESS-9 as part of §14 PTA (Wave 2) + D-FAULT-15 row 38 PTA (Wave 4) |
| no adaptive semantics | no existing-clause modification; SF AAU is metadata-only |

All preserved at the mechanics level. Layer A does not weaken, widen, or weaken-by-mechanism any constitutional invariant.

---

**End of Step 12 Layer A authoring-mechanics plan.**

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance](phase_4b_step11_f59_manual_advance_analysis.md), [closure verification](phase_4b_step11_closure_verification.md), [codification plan](phase_4b_step11_codification_plan.md), [meta-audit](phase_4b_step11_meta_audit.md), [extraction plan](phase_4b_step11_extraction_plan.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).

Successors (deferred): Layer B (per-clause validation), Layer C (review ergonomics), Layer D (cross-clause governance).
