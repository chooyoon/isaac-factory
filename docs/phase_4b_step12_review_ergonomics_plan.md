# Phase 4B Step 12 — Review Ergonomics Plan (Layer C — Pre-Authoring)

**Status: PRE-AUTHORING LAYER-C BOUNDED-REVIEWER-WORKFLOW PLAN (2026-05-21).** Designs the bounded reviewer workflow that wraps each AAU and each wave, without introducing any semantic-widening authority. Inherits the AAU model + 4 mutation shapes + Properties A1–A3 / S1–S3 from [`phase_4b_step12_authoring_mechanics_plan.md`](phase_4b_step12_authoring_mechanics_plan.md); inherits the 20-validator catalog + 4-stage validation lifecycle + BLOCKING/SOFT classes from [`phase_4b_step12_validation_plan.md`](phase_4b_step12_validation_plan.md). Does **not** author clause wording, does **not** mutate the contract document, does **not** define PR boundaries or reviewer-identity governance (Layer D), does **not** specify response-time SLAs or notification mechanisms.

Layer C specifies *what the reviewer sees*, *what decisions the reviewer is empowered to make* (and which they are not), *how validator outputs are presented to the reviewer*, and *how reviewer decisions are recorded for audit*. The reviewer is structurally subordinate to the validator suite; Layer C operationalizes that subordination.

---

## §1. Scope and inheritance

| inherited from | element |
|---|---|
| Layer A §2, §3 | AAU = 1 commit; 4 mutation shapes (PTA, STA, FII, SF) |
| Layer A §14 | Properties A1–A3 / S1–S3 (additive-only discipline) |
| Layer A §15 | 8-stage per-AAU safety protocol |
| Layer B §2 | 4-stage validation lifecycle (Stages 1–4) |
| Layer B §3 | 20-validator catalog (V1–V20); 17 BLOCKING + 3 SOFT (V6, V7, V20) |
| Layer B §8 | Shape-specific overlay validators |
| Layer B §16 | Failure-handling protocol (BLOCKING resets AAU; SOFT flags commit) |
| Layer B §17 | REJECTED criteria (AAU unauthorable → escalate) |

Layer C specifies only the reviewer's interface to those inherited mechanisms. It does not modify any inherited validator, rule, or property.

---

## §2. The reviewer's bounded role

The reviewer is, by Layer C's design:

* **An adjudicator of SOFT-validator flags** — the 3 SOFT validators (V6 minimal-enforceable-surface, V7 hidden-widening, V20 normative-consistency) produce flags that require human judgment because semantic content cannot be mechanized at Layer B's depth.
* **A visual integrity net for shape-specific overlays** — particularly the FII "next family heading unchanged" check and the SF "items 2–4 unchanged" check, where mechanical post-flight checks are mirrored by human visual confirmation as belt-and-suspenders.
* **A wave-closure integrity check** — at end-of-wave, the reviewer confirms V18 (replay-test invariant) and V19 (inter-wave citation-gap) both PASSED before the wave is closed.

The reviewer is, by Layer C's design, NOT:

* An authority for clause-body semantic decisions (those are author + framework decisions, made before Stage 1).
* An override for BLOCKING validator results (BLOCKING FAIL aborts the AAU; the reviewer never sees a BLOCKING-FAIL commit).
* A gate that introduces additional rules beyond Layers A and B.
* A re-runner of mechanical validators (validator outputs are the reviewer's trusted input).
* A modifier of clause-body wording (revisions are author-only; reviewer requests REVISE but does not edit).

**Sub-finding 2.A.** The reviewer's role is structurally narrow. The vast majority of constitutional safety is enforced by Layers A and B mechanically; Layer C is the residual human surface for the residue that cannot be mechanized.

---

## §3. The validator-supremacy invariant

The fundamental anti-drift invariant Layer C must preserve:

> **The reviewer MUST NOT override any BLOCKING validator result; the reviewer MUST NOT introduce constitutional rules not already established by Layers A and B; the reviewer MUST NOT exercise discretionary semantic reinterpretation.**

Operationally:

| validator state | reviewer power |
|---|---|
| BLOCKING PASS | reviewer cannot retroactively block (the AAU is mechanically valid) |
| BLOCKING FAIL | reviewer never sees this state — the AAU was aborted by Layer B §16 |
| SOFT PASS | reviewer cannot retroactively flag (the validator did not flag) |
| SOFT FAIL (flagged) | reviewer adjudicates: APPROVE-AS-IS with rationale, or REVISE-REQUESTED, or ESCALATE |

The reviewer's adjudication authority is confined to the SOFT-flag decision surface and the wave-level integrity confirmation. No other authority is granted.

**Sub-finding 3.A.** Layer C is the only layer where a human is permitted to influence the contract's authoring. Layer A and Layer B are mechanical/protocol layers. The validator-supremacy invariant ensures that "human" influence cannot mutate into "human override."

---

## §4. The three-option reviewer decision surface

For each AAU and for each wave-close event, the reviewer's decision surface is **exactly three options**:

| decision | semantics | downstream action |
|---|---|---|
| **APPROVE** | All BLOCKING validators PASSED; all SOFT flags either are unflagged or have been adjudicated with rationale; the AAU/wave proceeds | next AAU begins (per-AAU) or next wave begins (per-wave) |
| **REVISE** | One or more SOFT flags require author revision (e.g., V7-flagged phrase must be rewritten); the AAU is reverted via Layer A §13 reversion sequence and re-authored as a fresh AAU | author re-drafts; revised AAU re-enters Layer B Stage 1 |
| **ESCALATE** | Situation is outside the joint scope of Layers A + B + C; defer to Layer D process (deferred) | wave is paused; Layer D escalation triggered |

Layer C explicitly forbids the reviewer introducing a fourth option (e.g., "approve with caveat," "conditional approval," "approve pending"). Any such impulse is encoded as REVISE (require the caveat-resolution before approval) or ESCALATE (defer to Layer D).

**Sub-finding 4.A.** The three-option surface is the formal operationalization of "reviewer decision-surface minimization." Each option has a fully-defined downstream action; no option leaves an AAU in an indeterminate state.

---

## §5. Reviewer visibility boundaries

What the reviewer sees, by default, in the per-AAU review session:

| visible | rationale |
|---|---|
| AAU ID, mutation shape, target clause / row / section | identification |
| Pre-mutation anchor text + grep count | confirms anchor uniqueness (V1) and locality |
| Full `git diff` of the AAU's commit | confirms diff-shape (V11/V12) and shape-specific overlay (§8 of Layer B) |
| Validator-results table (all 20 validators relevant to this AAU's shape) | confirms which BLOCKING all passed; which SOFT are flagged |
| For each SOFT-flagged validator: the flagged text and the validator's recommended action | gives reviewer the minimum context to adjudicate |
| Citation list extracted from the AAU's clause body (anchor + reference) | for citation-audit (§13) |
| Cross-reference resolvability summary (per V17) | confirms each citation resolved |
| Shape-specific overlay results (§8 of Layer B) | per-shape confirmation |

What the reviewer does NOT see by default:

| not in default view | rationale |
|---|---|
| Framework analytical documents (`phase_4b_step11_*.md`) | preserving validator supremacy — the reviewer adjudicates the validator's output, not the framework's "intended" interpretation; framework docs are available on demand but not the default surface |
| Codification plan rationale | same — keeps reviewer focused on the AAU's mechanical correctness, not the codification's why |
| The AAU author's drafting notes / scratch | the reviewer reviews the committed artifact, not its drafting process |
| Cross-AAU comparison views | per-AAU review is per-AAU; cross-AAU is wave-level (§16) |
| Reviewer-decision history for prior AAUs | each AAU is reviewed on its own merits; precedent-following is anti-pattern (semantic-drift risk) |

**Sub-finding 5.A.** The "default-not-visible" set is deliberately constructed to prevent reviewer-side semantic drift. Framework docs and codification rationale ARE accessible on demand for adjudicating SOFT flags, but they are not the primary view; this asymmetry makes mechanical-validator-output the reviewer's baseline reality, not the framework's narrative.

---

## §6. The AAU Review Packet structure

The structured packet shown to the reviewer for each AAU has a fixed schema:

```
┌──────────────────────────────────────────────────────────────────┐
│ AAU Review Packet                                                │
├──────────────────────────────────────────────────────────────────┤
│ AAU-ID:          <e.g., "Wave 1 / AAU 1 / D-FAULT-6b">           │
│ Mutation shape:  <PTA | STA | FII | SF>                          │
│ Commit SHA:      <40-char hash>                                  │
│ Author message:  <commit message per Layer A §11>                │
├──────────────────────────────────────────────────────────────────┤
│ Anchor                                                           │
│  text:           <verbatim anchor excerpt, ≤ 5 lines>            │
│  grep-count pre: 1                                               │
│  grep-count post:1                                               │
│  location:       <line N in pre-mutation file>                   │
├──────────────────────────────────────────────────────────────────┤
│ Diff (rendered)                                                  │
│  <unified diff, color-coded, ≤ 100 lines unless §14 D-INGRESS>   │
├──────────────────────────────────────────────────────────────────┤
│ Validator results                                                │
│  V1  anchor-uniqueness-pre  ✓ PASS                              │
│  V2  anchor-stability       ✓ PASS                              │
│  V3  template-presence      ✓ PASS                              │
│  V4  citation-classification ✓ PASS                             │
│  V5  anchor-cite-existing   ✓ PASS                              │
│  V6  minimal-surface        ⚑ SOFT FLAG (see below)             │
│  V7  hidden-widening        ✓ PASS                              │
│  V8  override-statement     n/a (D-FAULT-9c only)               │
│  V9  framework-confinement  ✓ PASS                              │
│  V10 D-FAULT-15-row         n/a (not a D-FAULT-15 AAU)          │
│  V11 Properties A1–A3       ✓ PASS                              │
│  V13 anchor-uniqueness-post ✓ PASS                              │
│  V15 heading-DAG            ✓ PASS                              │
│  V16 clause-ID-uniqueness   ✓ PASS                              │
│  V17 cross-ref-resolvability ✓ PASS                             │
│  shape overlay (§8.3 FII)   ✓ PASS                              │
├──────────────────────────────────────────────────────────────────┤
│ SOFT flags requiring adjudication                                │
│  V6 — minimal-enforceable-surface                                │
│       flagged text: "<excerpt of flagged content>"               │
│       validator recommendation: "<recommendation>"               │
│       reviewer options: APPROVE-AS-IS (with rationale) | REVISE  │
├──────────────────────────────────────────────────────────────────┤
│ Citation list (extracted from clause body)                       │
│  Anchor:    D-FAULT-6, D-EXEC-13a, D-EXEC-13c, D-FAULT-15 #27    │
│  Reference: D-FAULT-15 #5                                        │
│  depth:     0                                                    │
├──────────────────────────────────────────────────────────────────┤
│ Decision surface: APPROVE | REVISE | ESCALATE                    │
└──────────────────────────────────────────────────────────────────┘
```

The packet schema is fixed; per-AAU content is variable. The reviewer's view is constrained to this packet (plus on-demand framework-doc access for SOFT-flag adjudication).

**Sub-finding 6.A.** The packet is the single trusted surface for the reviewer's decision. Information not in the packet is, by Layer C's design, not load-bearing for the decision. This bounds the reviewer's decision space and prevents drift into general-architectural review (which would re-derive the framework, defeating Layer A/B's mechanization).

---

## §7. Validator output presentation semantics

For each validator, the presentation in the AAU Review Packet uses three states:

| state | symbol | meaning |
|---|---|---|
| **PASS** | ✓ | validator ran and confirmed the AAU satisfies the check |
| **BLOCKING FAIL** | ✗ | validator ran and the AAU violates the check |
| **SOFT FAIL (flagged)** | ⚑ | validator ran and flagged the AAU for human adjudication |
| **n/a** | — | validator does not apply to this AAU's shape (e.g., V10 D-FAULT-15-row for a non-D-FAULT-15 AAU) |
| **deferred** | … | validator runs at wave-level or post-commit (V18, V19, V20) — not in per-AAU packet |

**BLOCKING FAIL** is never seen by the reviewer for a committed AAU — per Layer B §16, BLOCKING FAIL aborts the AAU before commit, so no review packet is generated for a BLOCKING-failed AAU.

**Sub-finding 7.A.** The reviewer's view of "BLOCKING FAIL" exists only in the abstract (as a "what would happen if"). In practice, every AAU that reaches the reviewer has BLOCKING all-PASS by Layer B's invariant.

---

## §8. SOFT-validator adjudication workflow

For each SOFT-flagged validator in an AAU Review Packet, the reviewer performs:

1. **Read the flag context** — the flagged text excerpt and the validator's recommendation.
2. **Inspect** — read the relevant section(s) of the AAU's clause body in full (the packet's diff view).
3. **Optionally consult framework doc** — for V6 (minimal-enforceable-surface): the extraction-plan §7 guideline; for V7 (hidden-widening): the extraction-plan §8 per-clause risks; for V20 (normative-consistency): the contract's existing clauses adjacent to the new clause.
4. **Adjudicate** — choose exactly one:
   * **APPROVE-AS-IS** — the flagged content stands; rationale MUST be recorded (per §19).
   * **REVISE-REQUESTED** — the flagged content must be rewritten by the author; specific guidance recorded.
   * **ESCALATE** — adjudication exceeds reviewer scope; defer to Layer D (deferred).
5. **Record** — the adjudication is appended to the audit trace (§19).

**APPROVE-AS-IS guardrails:**

* APPROVE-AS-IS requires a rationale that cites either (a) the framework derivation explicitly, or (b) an existing contract precedent, or (c) the SOFT validator's own scope limit.
* APPROVE-AS-IS MUST NOT cite reviewer intuition or "common sense" — those are discretionary-semantic-reinterpretation paths that Layer C §3 forbids.
* APPROVE-AS-IS MUST NOT introduce a new principle ("from now on, hidden-widening means …"); that's namespace churn forbidden in the session brief.

**REVISE-REQUESTED guardrails:**

* REVISE-REQUESTED specifies the flagged content + the requested change in shape ("rewrite to remove 'may eventually'"), NOT in wording ("rewrite as 'X MUST NOT Y'"). Reviewer does not author replacement text.
* REVISE-REQUESTED triggers Layer A §13 reversion: `git revert <AAU-commit-sha>` → author re-drafts → AAU re-enters Layer B Stage 1 with the revised draft.

**Sub-finding 8.A.** The SOFT-adjudication workflow's structural shape — adjudicate, then either accept-with-rationale, refuse-with-shape-guidance, or escalate — is the entire reviewer-as-author-checker interface. There is no fourth move.

---

## §9. BLOCKING-validator failure presentation

Because BLOCKING FAIL aborts the AAU before commit, the reviewer never sees a BLOCKING-FAIL packet. However, Layer C specifies the presentation semantics for an *audit-log view* of historical BLOCKING failures (visible to the reviewer in a separate non-decision-making view):

| audit-log field | content |
|---|---|
| AAU-ID (failed-attempt) | identifies the failed authoring attempt |
| Validator | which V1–V17 BLOCKING validator returned FAIL |
| Failure detail | the specific failure message |
| Author response | what the author did (re-derived anchor / rewrote body / abandoned) |
| Outcome | abandoned / re-attempted (with new commit SHA) |

This audit-log view exists for **post-hoc transparency only**; it does not present a decision surface to the reviewer. BLOCKING failures are mechanically resolved by Layer B; the reviewer's only relationship to them is read-only audit.

**Sub-finding 9.A.** Separating the BLOCKING-failure audit log from the reviewer's decision surface preserves validator supremacy: the reviewer cannot retroactively contest a BLOCKING failure by adding context, because the failure was mechanically determined and the AAU was aborted before reaching review.

---

## §10. Per-mutation-shape review guidance

Each shape gets a small review-checklist overlay specific to its characteristic risk:

### §10.1 PTA (pure-tail append) review guidance

| AAU sub-type | reviewer focus |
|---|---|
| D-FAULT-15 row | confirm row number is strictly N+1; confirm row content matches the table's column meanings; minimal additional risk |
| §0 glossary entry | confirm term not duplicated; definition fits the glossary's one-line style |
| §14 D-INGRESS (whole section) | structured sub-checklist: walk 9 D-INGRESS clauses + scope + restatement; confirm three-section template (V3) on each clause; confirm intra-§14 cross-references resolve |

**§14-specific note.** Because §14 is one AAU (Layer A §2.1) but encloses 11 sub-elements, the §14 review is structurally larger than any other AAU's review. The packet's diff view for §14 may exceed 1000 lines; Layer C recommends presenting §14's review as a nested sub-packet per D-INGRESS-N + a top-level summary, but exact UI is Layer D / implementation-time.

### §10.2 STA (section-tail append) review guidance

| AAU sub-type | reviewer focus |
|---|---|
| D-SCHED-14 / D-REPLAY-10 | standard C-1 review: three-section template, citation classification, minimal-surface, hidden-widening, framework-confinement |
| C-2 embedded note (T1, T4, T5, T8) | confirm subsection is explanatory only (no normative MUST/MUST NOT); confirm NOT assigned a clause-ID; reviewer's role is "confirm this is an embedded note, not a smuggled promotion" |

### §10.3 FII (family-internal insertion) review guidance — see §11

### §10.4 SF (status flip) review guidance — see §12

---

## §11. FII high-risk review protocol

FII is the highest-risk shape because it inserts between two protected regions and could (if mis-authored or mis-validated) trigger sub-subsection renumbering downstream. Every FII AAU gets a dedicated mandatory reviewer checklist:

1. **Confirm anchor uniqueness pre and post (V1, V13)** — visually verify both grep-count rows in the packet show `1`.
2. **Confirm next family heading text byte-identical pre/post (§8.3 overlay)** — for D-FAULT-6b/6c: the next heading is `### 13.7 D-FAULT-7` and its text appears unchanged in the diff context. For D-FAULT-9b/9c: similarly for `### 13.10 D-FAULT-10`.
3. **Confirm next family heading section number unchanged** — `### 13.7` did NOT become `### 13.8`. This is the dedicated guard against the renumbering hazard from Layer A §6.
4. **Confirm new sub-subsection number is N+1** — for D-FAULT-6b after D-FAULT-6a: new heading is `#### 13.6.2`. For D-FAULT-6c after D-FAULT-6b: new heading is `#### 13.6.3`.
5. **For Wave 1 sequence (6b then 6c) and Wave 3 sequence (9b then 9c)** — confirm the second AAU's anchor was re-derived to use the first AAU's (now-existing) heading as preceding context.
6. **For D-FAULT-9c specifically** — confirm V8 (override-statement) is PASS in the validator-results table; confirm the override statement is visually present in the diff.

The FII reviewer pass is **MANDATORY** for every FII AAU; the reviewer cannot skip any step. APPROVE for an FII AAU requires all 6 (or 5 for non-9c) checks confirmed visually in addition to the validator-results table.

**Sub-finding 11.A.** FII review is the one shape where human visual confirmation is explicitly redundant to mechanical checks. The redundancy is intentional: the renumbering hazard is the highest-consequence Layer-A failure mode, and visual + mechanical confirmation provides defense-in-depth.

---

## §12. SF mutation review protocol

SF is the unique case — the only AAU that mutates existing contract text. Every SF AAU (there is exactly one: §11 item 1 → CLOSED) gets a dedicated mandatory reviewer checklist:

1. **Confirm Property S1 (verbatim-prefix) visually in the diff** — the `+` line(s) start with the `-` line(s) content as a verbatim prefix.
2. **Confirm §11 items 2, 3, and 4 produce zero diff lines (§8.4 overlay)** — visually scan the diff context outside item 1's region for any change; expect none.
3. **Confirm CLOSED marker explicitly cites L3 (Canonical-Order Commutativity) AND D-INGRESS-4** — `grep` results in the validator output confirm; reviewer visually confirms in the diff.
4. **Confirm no character of item 1's original text is deleted** — for each character of `old_string`, locate the corresponding character in `new_string` at the same relative position.
5. **Confirm V12 (Properties S1–S3) PASS** in the validator-results table.

The SF reviewer pass is **MANDATORY**. Because SF is the only existing-text mutation, the SF reviewer is the most consequential per-AAU reviewer pass in the entire 29-AAU sequence. APPROVE for the SF AAU requires all 5 checks confirmed visually.

**Sub-finding 12.A.** The SF reviewer pass is also the only per-AAU review whose failure mode is "silent contract corruption" (a §11 item silently dropped, a non-item-1 region silently mutated). Visual confirmation backs up the mechanical S1–S3 check explicitly because the consequences of a missed mutation here are unbounded.

---

## §13. Citation-audit ergonomics

For the citation-audit portion of each AAU Review Packet, the reviewer sees:

| field | content |
|---|---|
| Anchor citations | list of clause-IDs (e.g., `D-FAULT-6, D-EXEC-13a, D-EXEC-13c, D-FAULT-15 #27`) |
| Reference citations | list of clause-IDs and framework refs (e.g., `D-FAULT-15 #5`) |
| Citation depth | 0 (no Step-11 new-clause dependencies) or 1 (cites one Step-11 new clause) |
| Per-citation resolvability | for each cited ID: the heading at which it resolves in the current contract (excerpted) |
| Per-framework-ref containment | each framework ref is shown with the section of the AAU body in which it appears (must be Section C only, per V9) |

The reviewer's citation-audit role:

* **Confirm citations are semantically sensible** — e.g., D-FAULT-6b's anchor citation set includes D-FAULT-6 (parent family), D-EXEC-13a/c (interruption-surface clauses), and D-FAULT-15 #27 (a related forbidden pattern). The reviewer confirms this set "makes sense" in light of the new clause's content.
* **Confirm no missing citation** — if the new clause's Rule paragraph mentions a concept governed by an existing clause that isn't in the citation list, that's a SOFT flag (V20 candidate); reviewer requests REVISE.
* **Confirm no spurious citation** — if a cited ID is present but not actually referenced in the clause body, REVISE.

The reviewer does NOT:

* Re-evaluate the codification plan's classification of which citations are anchor vs reference (V4 mechanical; settled).
* Add new citations or remove existing ones (REVISE-REQUESTED returns to author).

**Sub-finding 13.A.** Citation-audit is the one area where the reviewer exercises the most semantic judgment, but it is judgment about *correspondence between body text and citation list*, not about *which citations should be normative*. The latter is the codification plan's territory.

---

## §14. Anchor-audit ergonomics

For the anchor portion of each AAU Review Packet, the reviewer sees:

| field | content |
|---|---|
| Anchor text | verbatim excerpt (≤ 5 lines) |
| Grep-count pre | must be 1 (V1 confirmed) |
| Grep-count post | must be 1 (V13 confirmed) |
| Line location pre | line N in pre-mutation file |
| Anchor-to-insertion distance | confirms ±20 line locality per Layer A §4 |

The reviewer's anchor-audit role:

* **Confirm anchor is sensible** — e.g., for D-FAULT-6b's STA-like insertion: anchor is the closing sentence of D-FAULT-6a's *Rationale.* paragraph (read-only context). The reviewer confirms the anchor identifies the right insertion point.
* **Confirm grep-counts match** — visually verify both rows show `1`.
* **Confirm locality** — the anchor is local to the insertion (no anchoring on a §0 sentence to insert in §13).

The reviewer does NOT:

* Re-derive the anchor (anchor selection is author + Layer B; the reviewer reviews the chosen anchor).
* Override V1 / V13 / V2 mechanical results.

**Sub-finding 14.A.** Anchor-audit is brief — usually a 30-second visual confirmation per AAU — because the mechanical layer is robust. The reviewer's role is "sanity check that nothing weird happened" rather than independent anchor design.

---

## §15. Replay-invariant review ergonomics (wave-level)

At end-of-wave, the reviewer sees the wave-closure packet:

```
┌──────────────────────────────────────────────────────────────────┐
│ Wave Closure Packet                                              │
├──────────────────────────────────────────────────────────────────┤
│ Wave:        <N> of 6                                            │
│ AAU count:   <e.g., 4 (Wave 1)>                                  │
│ Commit SHAs: <list of N AAU commits>                             │
├──────────────────────────────────────────────────────────────────┤
│ V18 — Replay-test invariant                                      │
│  Pre-wave SessionPackage SHA-256:  <hash>                        │
│  Post-wave SessionPackage SHA-256: <hash>                        │
│  Match: ✓ PASS                                                   │
│  (or for FAIL: full divergence diff)                             │
├──────────────────────────────────────────────────────────────────┤
│ V19 — Inter-wave citation-gap                                    │
│  Total citations in wave: N                                      │
│  Unresolved citations:    0                                      │
│  Result: ✓ PASS                                                  │
├──────────────────────────────────────────────────────────────────┤
│ Wave-internal consistency                                        │
│  No AAU in wave broke a sibling AAU's citation                   │
│  Result: ✓ PASS                                                  │
├──────────────────────────────────────────────────────────────────┤
│ Preserved-invariant table                                        │
│  replay-authoritative truth          ✓ CONFIRMED                 │
│  append-only causality               ✓ CONFIRMED                 │
│  authority singularity               ✓ CONFIRMED                 │
│  [... 11 more invariants ...]                                    │
├──────────────────────────────────────────────────────────────────┤
│ Per-AAU adjudication summary                                     │
│  AAU 1: APPROVED (0 SOFT flags)                                  │
│  AAU 2: APPROVED (1 SOFT flag, APPROVE-AS-IS, rationale: ...)    │
│  AAU 3: APPROVED (0 SOFT flags)                                  │
│  AAU 4: APPROVED (2 SOFT flags, REVISE then APPROVED on retry)   │
├──────────────────────────────────────────────────────────────────┤
│ Decision surface: APPROVE WAVE-CLOSE | ESCALATE                  │
└──────────────────────────────────────────────────────────────────┘
```

The wave-close decision surface is two options (REVISE does not apply at wave-level — wave-level revisions are always per-AAU re-authorings):

* **APPROVE WAVE-CLOSE** — V18 and V19 PASS, all per-AAU adjudications APPROVED, preserved invariants confirmed; wave is closed; next wave may begin.
* **ESCALATE** — V18 or V19 FAIL, or a preserved invariant is reported as NOT CONFIRMED; defer to Layer D process.

The reviewer's wave-level role:

* **Confirm V18 PASS visually** — the SessionPackage SHA-256 strings match.
* **Confirm V19 PASS visually** — unresolved citation count is 0.
* **Confirm preserved-invariant table is all-CONFIRMED** — 14 rows; any NOT-CONFIRMED row triggers ESCALATE.
* **Confirm per-AAU adjudication summary is all-APPROVED** — no PENDING / REVISE / ESCALATE entries.

**Sub-finding 15.A.** The wave-close packet is the integrity net at the end of every wave. The reviewer's role here is the most binary in Layer C: every field is either GREEN (APPROVE) or RED (ESCALATE). There is no middle ground at wave-close.

---

## §16. Reviewer non-authority constraints (formal enumeration)

The reviewer:

| MUST NOT | rationale |
|---|---|
| Override a BLOCKING validator result | Layer B mechanical decision; reviewer never sees a BLOCKING-FAIL commit |
| Modify clause-body wording themselves | wording is author-only; REVISE returns to author |
| Introduce new validators or new BLOCKING rules | namespace churn; out of Layer C scope |
| Skip a SOFT-flag adjudication | every flag MUST be adjudicated (APPROVE-AS-IS / REVISE / ESCALATE) |
| Approve an AAU that introduces a fresh constitutional principle | semantic redesign forbidden in this session brief; ESCALATE instead |
| Alter the codification plan or extraction plan | those are settled at the Step 11 layer; out of Layer C scope |
| Re-run a mechanical validator on their own initiative | validator outputs are trusted input; re-running is anti-pattern (would indicate validator-supremacy violation by the reviewer) |
| Add a citation or remove a citation from a clause body | citation set is author-decided + V5/V17 mechanically checked; REVISE for changes |
| Adjudicate based on reviewer intuition ("feels off") | APPROVE-AS-IS requires cited rationale; REVISE requires cited validator-recommendation; ESCALATE requires named-trigger condition |
| Compare AAUs against each other for precedent | each AAU is reviewed on its own merits; cross-AAU is only at wave-level integrity |
| Approve a packet with a NOT-CONFIRMED preserved invariant | always ESCALATE |
| Author the audit-trace entry's rationale text after the decision (post-hoc) | rationale MUST be authored at decision time, not retrofitted |

**Sub-finding 16.A.** This enumeration is the formal statement of "validator supremacy over reviewer intuition." Each forbidden action is specifically traceable to a possible drift path (override, semantic creep, namespace expansion, etc.); Layer C closes each path explicitly.

---

## §17. Anti-semantic-drift reviewer rules

Specific rules to prevent slow erosion of substrate integrity through reviewer accumulation:

| rule | concrete operationalization |
|---|---|
| **Rationale-citation requirement** | every APPROVE-AS-IS rationale MUST cite either: (a) the framework derivation explicitly (e.g., "per extraction-plan §8 — D-FAULT-6c hidden-widening risk row, scope of 'observation' is qualified by 'ingress event' in this AAU's Rule paragraph"), or (b) an existing contract precedent (e.g., "per D-FAULT-1a's similar phrasing, this conditional formulation is precedent-consistent"), or (c) the SOFT validator's own scope limit (e.g., "V7 banned-phrase 'may eventually' is absent; the flagged 'may' is in 'MAY use scheduled-injection' which is a permissive normative form, not a hedging form"). |
| **No-precedent-creation rule** | a REVISE or APPROVE-AS-IS decision MUST NOT be framed as establishing a precedent for future AAUs ("from now on, hidden-widening means …"). Each AAU is adjudicated on its own merits using the inherited validator scopes. |
| **No-wording-author rule** | REVISE-REQUESTED specifies the *shape* of the requested change ("remove the hedge"; "tighten the scope to ingress events"), never the *exact wording* ("rewrite as 'X MUST NOT Y'"). The author re-drafts; the reviewer does not. |
| **No-bundling rule** | each SOFT flag is adjudicated individually. The reviewer cannot batch-approve all SOFT flags in an AAU; each flag gets its own rationale or shape-guidance. |
| **No-framework-override rule** | the reviewer cannot override a framework derivation. If the framework (e.g., Theorem T6's 5 properties) says X, and the AAU's Rule paragraph asserts X, the reviewer cannot APPROVE-AS-IS-with-rationale that effectively weakens X to "X usually." That's semantic widening; ESCALATE instead. |
| **No-implementation-driven adjudication** | the reviewer cannot argue "the runtime can't yet handle this; let's soften the clause." The contract precedes the runtime; runtime conformance is downstream. If a soften-for-implementation impulse arises, ESCALATE. |

**Sub-finding 17.A.** These rules collectively encode the constitutional posture: the reviewer's authority is to *ratify or refer up*, never to *adjust to make life easier*. The latter would be convenience-driven restructuring, explicitly forbidden in the session brief.

---

## §18. Validator-to-reviewer boundary

The sharp line between mechanical and human territory:

| dimension | validator territory | reviewer territory |
|---|---|---|
| Input | the AAU's committed/about-to-commit state | the validator's output + the AAU's diff + the AAU's packet |
| Output | PASS / BLOCKING FAIL / SOFT FAIL | APPROVE / REVISE / ESCALATE |
| Authority | deterministic mechanical check | adjudicate SOFT flags; visually confirm shape-overlays; wave-close integrity |
| Time | runs at AAU lifecycle stages 1, 2, 3, 4 (Layer B) | runs after Stage 3 / Stage 4 per AAU; runs at wave-close |
| Mutability of output | validator outputs are determinate (re-running gives same result) | reviewer decisions are bounded by §4's three options |
| Failure handling | BLOCKING aborts AAU; SOFT flags commit | REVISE reverts AAU; ESCALATE pauses wave |
| Visibility to other | validator outputs visible to reviewer (always) and to audit trace | reviewer decisions visible to audit trace (always); not to validator (validator is mechanical) |

The handoff:

* Validator → reviewer: validator output is the reviewer's primary input. The reviewer reads the validator-results table, the SOFT flags, the shape-overlay results.
* Reviewer → validator: NONE. The reviewer never feeds anything back into the validator suite. The validators are mechanical and operate purely on file state + AAU draft + commit.

**Sub-finding 18.A.** The reviewer-to-validator direction is empty: this is the structural enforcement of validator supremacy. If the reviewer's judgment could feed back to alter validator behavior, the reviewer would have de facto override power; Layer C forecloses this by making the validator suite write-only-from-reviewer-perspective.

---

## §19. Audit-trace preservation

Every reviewer decision MUST be recorded as a structured audit-trace artifact. The audit-trace schema:

| field | content |
|---|---|
| Decision-ID | unique identifier (e.g., `step12-wave1-aau1-decision`) |
| AAU-ID | reference to the AAU |
| Commit SHA | the AAU's commit hash |
| Validator-results snapshot | full table of V1–V20 results at decision time |
| Decision | APPROVE / REVISE / ESCALATE |
| Per-SOFT-flag adjudication | for each SOFT flag: APPROVE-AS-IS (with rationale) / REVISE-REQUESTED (with shape-guidance) / ESCALATE |
| Rationale (free-text) | for APPROVE-AS-IS: cited derivation per §17; for REVISE: shape-guidance per §17; for ESCALATE: trigger condition per §21 |
| Reviewer identifier | anonymized OK (e.g., "Reviewer-A"); Layer D defines real-identity policy |
| Timestamp | wall-clock time of decision (informational only; not constitutionally load-bearing — Layer C does not violate "no wall-clock authority" because wall-clock here is descriptive, not normative) |
| Preserved-invariant table | (wave-close decisions only) full table per §15 |

The audit-trace artifact lives in a Layer-D-defined location (likely git: as a structured commit-trailer, or as a sibling file under `docs/step12_audit_traces/`; exact location deferred).

**Persistence requirements:**

* Each decision artifact MUST be created at decision time (not retroactively).
* Each artifact MUST be immutable after creation (additive-only at the audit layer too).
* Corrections (e.g., reviewer realizes a rationale was incomplete) MUST be appended as a new decision artifact, not as a mutation of the original.

**Sub-finding 19.A.** The audit-trace is the durable record of human influence on the contract. It is the artifact that, in retrospect (months or years later), explains why each SOFT flag was adjudicated the way it was. Without it, the reviewer's judgment is opaque; with it, the reviewer's judgment is auditable and the constitutional posture remains defensible.

---

## §20. Reviewer handoff sequencing

Within a wave, between AAUs:

| event | constraint |
|---|---|
| AAU N's mutation completed (Stage 3 commit) | AAU N's review MUST begin before AAU N+1's mutation begins |
| AAU N's review decision: APPROVE | AAU N+1's authoring (Stage 1) may begin |
| AAU N's review decision: REVISE | AAU N+1 does NOT begin; AAU N is reverted (Layer A §13); author re-drafts; AAU N re-enters Layer B Stage 1; on re-completion, AAU N+1 begins |
| AAU N's review decision: ESCALATE | wave is paused; Layer D process triggered; AAU N+1 does NOT begin until escalation resolves |

Between waves:

| event | constraint |
|---|---|
| Wave N's final AAU APPROVED | wave-close review may begin |
| Wave-close decision: APPROVE WAVE-CLOSE | Wave N+1's first AAU may begin (Stage 1) |
| Wave-close decision: ESCALATE | wave N is paused at close; Layer D process triggered; Wave N+1 does NOT begin |

**No-skip rule.** AAU and wave reviews MUST be sequenced (no parallel adjudication of multiple AAUs in the same wave, no out-of-order AAU review). The mechanical reason is anchor-derivation: each FII AAU's anchor depends on prior FII AAUs in the same wave; out-of-order review would invalidate anchor-audit (§14).

**Sub-finding 20.A.** Layer C's handoff sequencing is deliberately strict to mirror Layer A's atomicity. AAU review parallelism would create review-order vs commit-order divergence — analyzable but unnecessary complexity; Layer C avoids it.

---

## §21. Reviewer escalation protocol

The reviewer ESCALATES (vs APPROVE or REVISE) under any of the following triggers:

| trigger | per | rationale |
|---|---|---|
| V18 (replay-test invariant) FAILs at wave-close | wave | constitutional safety net failure; outside Layer C scope |
| V19 (inter-wave citation-gap) FAILs at wave-close | wave | aggregate citation failure; investigate via Layer D |
| A SOFT flag is irresolvable (author and reviewer cannot agree on REVISE shape) | AAU | adjudication exceeds reviewer-author dyad |
| The AAU appears to introduce a fresh constitutional principle | AAU | semantic redesign forbidden; Layer D decides whether to update Step 11 |
| An anchor or shape requires re-derivation that exceeds Layer A's allowed scope | AAU | Layer A modification required; not Layer C's authority |
| A REJECTED AAU per Layer B §17 | AAU | extraction plan revision required; Layer D scope |
| A preserved-invariant table entry shows NOT-CONFIRMED | wave | substrate integrity threat; pause and investigate |
| The reviewer becomes uncertain whether a decision is within Layer C scope | any | default-to-escalate when unsure |

Escalation target: the Layer D process (deferred). Layer C specifies only WHAT triggers ESCALATE; Layer D will specify WHO receives the escalation and HOW it is resolved.

**Sub-finding 21.A.** "Default-to-escalate when unsure" is the conservative reviewer posture. The cost of unnecessary escalation is process-overhead; the cost of approving-when-uncertain is silent constitutional drift. Layer C explicitly biases toward the former.

---

## §22. Layer-C open questions (deferred to Layer D / implementation)

Layer C intentionally does NOT specify:

* The reviewer-identity policy (anonymous? named? rotating? — Layer D).
* The reviewer-assignment mechanism (Layer D).
* The reviewer's response-time SLAs (Layer D).
* The notification mechanism for AAU-ready-for-review (implementation).
* The exact UI for rendering the AAU Review Packet (implementation).
* The exact UI for rendering the Wave Closure Packet (implementation).
* The escalation-resolution process (Layer D).
* The audit-trace storage location and format (Layer D / implementation).
* The cross-reviewer agreement protocol if multiple reviewers per AAU (Layer D, if multi-reviewer is adopted).
* The metrics / dashboards for tracking reviewer throughput (out of scope).

---

## §23. Layer-C vocabulary

Layer C introduces several planning-doc terms; none enter the normative contract:

| term | meaning | scope |
|---|---|---|
| AAU Review Packet | the fixed-schema structured artifact shown to the reviewer per AAU | this planning doc |
| Wave Closure Packet | the fixed-schema structured artifact shown to the reviewer at wave-close | this planning doc |
| Reviewer decision surface | the set of options the reviewer may choose (APPROVE / REVISE / ESCALATE per AAU; APPROVE WAVE-CLOSE / ESCALATE per wave) | this planning doc |
| SOFT-flag adjudication | the reviewer's per-flag decision (APPROVE-AS-IS / REVISE-REQUESTED / ESCALATE) | this planning doc |
| Audit trace | the durable record of reviewer decisions | this planning doc + Layer D |
| Validator-to-reviewer boundary | the structural separation between mechanical and human territory | this planning doc |

None receive clause IDs. Per "no namespace churn" — purely review-process vocabulary.

---

## §24. Layer-C planning verdict

**LAYER C: READY.**

* Reviewer's bounded role enumerated (§2): SOFT-validator adjudicator + shape-overlay integrity net + wave-close integrity check.
* Validator-supremacy invariant formalized (§3): no BLOCKING override, no discretionary semantics, no new rules.
* Three-option decision surface (APPROVE / REVISE / ESCALATE) specified (§4); fourth option explicitly forbidden.
* Visibility boundaries set (§5): default view = AAU + validator output; framework docs on-demand only.
* AAU Review Packet schema fixed (§6).
* Validator output presentation semantics specified (§7); BLOCKING FAIL never reaches reviewer.
* SOFT-validator adjudication workflow specified (§8): adjudicate → APPROVE-AS-IS (with rationale) / REVISE-REQUESTED (with shape) / ESCALATE.
* BLOCKING-validator audit-log presentation specified (§9) as read-only post-hoc transparency.
* Per-shape review guidance (§10): PTA / STA / FII / SF with shape-specific checklists.
* FII high-risk review protocol mandatory (§11): 6-step (or 5-step) checklist; visual confirmation redundant to mechanical.
* SF mutation review protocol mandatory (§12): 5-step checklist; the only existing-text mutation gets the most scrutiny.
* Citation-audit ergonomics (§13): reviewer confirms semantic correspondence between body and citation list; cannot alter citation list directly.
* Anchor-audit ergonomics (§14): reviewer confirms sensibility + locality; cannot re-derive anchor.
* Replay-invariant review ergonomics (§15): wave-close packet with V18 + V19 + preserved-invariant table.
* Reviewer non-authority constraints enumerated formally (§16): 12 explicit MUST-NOTs.
* Anti-semantic-drift reviewer rules (§17): rationale-citation, no-precedent-creation, no-wording-author, no-bundling, no-framework-override, no-implementation-driven adjudication.
* Validator-to-reviewer boundary explicit (§18): one-way handoff; no feedback from reviewer to validator.
* Audit-trace preservation specified (§19): structured artifact per decision; immutable, additive-only.
* Reviewer handoff sequencing (§20): strict in-order AAU and wave review.
* Reviewer escalation protocol (§21): 8 named triggers; default-to-escalate when unsure.
* Layer D dependencies stated (§22); not implemented.

The plan does NOT mutate any artifact. The plan does NOT author clause wording. The plan does NOT define PR boundaries or reviewer-identity policy. The plan IS the bounded reviewer-workflow overlay on the Layer A mutation acts and Layer B validator suite.

---

## §25. Preserved invariants under Layer C

| invariant | Layer-C mechanism |
|---|---|
| replay-authoritative truth | Wave Closure Packet (§15) shows V18 result explicitly; reviewer ESCALATEs on V18 FAIL |
| append-only causality | reviewer cannot modify wording; REVISE returns to author (Layer A §13 reversion path) |
| authority singularity | reviewer non-authority constraints (§16) explicitly forbid the reviewer becoming a second authority |
| orchestration_tick supremacy | reviewer cannot override V18 (replay-test invariant) on a documentation mutation |
| deterministic interruption boundaries | reviewer cannot APPROVE-AS-IS a V7-flagged hedging phrase in D-FAULT-6b (no-framework-override rule §17) |
| Phase-A-only observability | same for D-FAULT-6c V7 flag |
| contradiction preservation | reviewer cannot APPROVE-AS-IS a D-FAULT-9c that lacks the V8 override-statement (V8 is BLOCKING; reviewer never sees the FAIL) |
| transport independence | reviewer cannot APPROVE-AS-IS a V9-flagged framework reference in Sections A/B (V9 is BLOCKING) |
| no hidden cleanup | reviewer cannot approve an AAU whose Property A2 was flagged (V11 BLOCKING; never reaches reviewer) |
| no wall-clock authority | reviewer cannot APPROVE-AS-IS V7-flagged wall-clock language in D-INGRESS-8 / D-FAULT-15 row 38 (no-framework-override rule) |
| no adaptive semantics | reviewer cannot APPROVE-AS-IS conditional or "may eventually" language (V7 / no-framework-override rule) |
| framework/contract separation | V9 BLOCKING + reviewer's no-framework-override rule both protect this; reviewer cannot promote a framework ref into Section A/B by REVISE-shape guidance |
| additive-only mutation discipline | reviewer cannot APPROVE-AS-IS a Property A1–A3 / S1–S3 violation (V11/V12 BLOCKING; never reaches reviewer) |
| replay-preserving extraction safety | Wave Closure Packet's V18 + V19 + preserved-invariant table; ESCALATE on any failure |
| validator supremacy over reviewer intuition | §3 explicit invariant; §16 non-authority enumeration; §18 one-way validator→reviewer handoff |
| no semantic widening authority | §16 + §17 rules; reviewer cannot widen scope of any clause; reviewer cannot approve scope-widening phrasing |
| no reviewer discretionary reinterpretation | §17 rationale-citation rule; APPROVE-AS-IS requires cited framework/precedent/scope-limit, not intuition |
| no hidden override pathways | §18 one-way boundary; reviewer never feeds back into validator suite |
| no authority redistribution | reviewer is bounded to SOFT adjudication + shape-overlay + wave-close; no new authority granted |

All preserved at the reviewer-workflow level.

---

**End of Step 12 Layer C bounded-reviewer-workflow plan.**

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance](phase_4b_step11_f59_manual_advance_analysis.md), [closure verification](phase_4b_step11_closure_verification.md), [codification plan](phase_4b_step11_codification_plan.md), [meta-audit](phase_4b_step11_meta_audit.md), [extraction plan](phase_4b_step11_extraction_plan.md), [Layer A authoring mechanics](phase_4b_step12_authoring_mechanics_plan.md), [Layer B per-clause validation](phase_4b_step12_validation_plan.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).

Successors (deferred): Layer D (cross-clause governance).
