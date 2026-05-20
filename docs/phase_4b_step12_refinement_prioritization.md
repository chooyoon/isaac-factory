# Phase 4B Step 12 — R-FG Refinement Prioritization

**Status: PRE-EXECUTION REFINEMENT PRIORITIZATION (2026-05-21).** Practical/governance decision on whether to apply the four R-FG refinements (identified in [`phase_4b_step12_final_governance_review.md`](phase_4b_step12_final_governance_review.md) §27) before Decision-Owner begins runbook execution. This session is a prioritization decision, NOT redesign.

The framework has reached 20 docs and ~13,900 lines of pre-authoring planning with zero actual work executed. The session brief explicitly lists "no governance recursion spiral" and "no analysis-for-its-own-sake" as preserved invariants. This prioritization is conducted under that constraint.

---

## §1. Scope and method

The review proceeds in three passes:

1. **Per-refinement analysis** — value, cost, ambiguity risk, semantic impact for each of R-FG-1 through R-FG-4.
2. **Saturation analysis** — whether the framework has reached the point where further pre-execution planning becomes governance recursion.
3. **Verdict** — selection from PROCEED-AS-IS / APPLY-R-FG-1-ONLY / APPLY-R-FG-1-THROUGH-4 / REFINE-THEN-REVIEW-AGAIN / ANALYSIS-SATURATION-REACHED.

This document does NOT apply refinements; it specifies which (if any) the Decision-Owner should apply.

---

## §2. The four refinements (recap)

From final governance review §27:

| ID | refinement | classification |
|---|---|---|
| R-FG-1 | Runbook §10 expand post-revert recovery sequence (explicit `git checkout <failed-sha> -- <files>` after `git revert`) | OPERATIONAL, LOW severity, recommended before Phase 3 |
| R-FG-2 | Runbook §13 explicit mid-stage break protocol (e.g., during `git add -p`) | OPERATIONAL, MINIMAL severity, optional |
| R-FG-3 | Pre-bootstrap state machine naming (formalize AUTHORING-ADMISSIBLE → EXECUTION-RUNBOOK-READY states) | DOCUMENTATION, MINIMAL severity, optional |
| R-FG-4 | Runbook Phase 0 add "copy only inner code-block content, not ```markdown wrapper" warning | OPERATIONAL, LOW severity, optional |

All four are non-blocking by classification.

---

## §3. Per-refinement analysis dimensions

Each refinement is evaluated against:

| dimension | meaning |
|---|---|
| **Trigger probability** | how often the issue the refinement addresses actually arises during execution |
| **Value-if-triggered** | how much the refinement helps when the issue arises |
| **Application cost** | effort to author and apply the refinement |
| **New-ambiguity risk** | whether the refinement itself introduces new confusion |
| **Requires own dry-run?** | whether applying the refinement needs its own validation cycle |
| **Alters runbook semantics?** | whether the refinement changes existing operator procedure |
| **Alters governance semantics?** | whether the refinement changes role authority or validator scope |
| **Affects audit lineage?** | whether the refinement changes commit content or audit-trace format |

---

## §4. R-FG-1 analysis (post-revert recovery sequence)

| dimension | assessment |
|---|---|
| Trigger probability | LOW (only triggers on W2 V18 FAIL; dry-run review §20 estimated 0–1 such incidents across whole authoring) |
| Value-if-triggered | HIGH (post-revert working-tree restoration is operationally non-obvious; explicit `git checkout <failed-sha> -- <files>` guidance reduces moment-of-failure stress significantly) |
| Application cost | LOW (~20–30 lines of additional runbook §10 content; can be appended as additive supersession per amendment plan §A1–§A4 pattern) |
| New-ambiguity risk | VERY LOW (purely additive content; doesn't replace existing §10 language) |
| Requires own dry-run? | NO (the refinement is a documentation patch; same additive-supersession discipline as A1–A4 already verified admissible) |
| Alters runbook semantics? | NO (extends recovery path with explicit commands; doesn't change which recovery path is taken) |
| Alters governance semantics? | NO |
| Affects audit lineage? | NO (no impact on commits or audit-trace) |

**Sub-finding 4.A.** R-FG-1 has the most favorable value/cost ratio of the four refinements: low cost, high value when the rare failure case arises, no semantic risk. The Decision-Owner facing a W2 V18 FAIL without R-FG-1 must improvise post-revert recovery; with R-FG-1, the runbook tells them exactly what to do.

**Recommendation:** APPLY R-FG-1.

---

## §5. R-FG-2 analysis (mid-stage break protocol)

| dimension | assessment |
|---|---|
| Trigger probability | HIGH (operators take breaks all the time; mid-`git add -p` pauses are common) |
| Value-if-triggered | LOW (git's behavior during interactive staging is well-known; index persists across terminal pauses; quitting `git add -p` via `q` is standard knowledge) |
| Application cost | LOW (~5–10 lines of additional runbook §13 content) |
| New-ambiguity risk | VERY LOW |
| Requires own dry-run? | NO |
| Alters runbook semantics? | NO |
| Alters governance semantics? | NO |
| Affects audit lineage? | NO |

**Sub-finding 5.A.** R-FG-2 addresses a common operational scenario with well-known semantics. An attentive operator already knows how to handle mid-stage breaks. The refinement provides marginal documentation polish without addressing any real safety gap.

**Recommendation:** OPTIONAL (skip; the operator's general git fluency covers this case).

---

## §6. R-FG-3 analysis (pre-bootstrap state machine naming)

| dimension | assessment |
|---|---|
| Trigger probability | LOW (the planning narrative is sequentially clear; operators reading the framework understand the progression) |
| Value-if-triggered | LOW (orthogonal documentation; doesn't change what the operator does) |
| Application cost | MEDIUM (would require a new section in Layer D §2 or a new framework doc; significant text; potentially affects 5+ existing docs that already reference informal state names) |
| New-ambiguity risk | MEDIUM (introduces formal state-name vocabulary not currently present in 19 docs; informal names like "AUTHORING-ADMISSIBLE" already in use; potential conflicts with informal usage) |
| Requires own dry-run? | POTENTIALLY (would need cross-doc consistency review to ensure formal names don't conflict with informal ones — this is itself a recursive review) |
| Alters runbook semantics? | NO |
| Alters governance semantics? | NO (state names are informational) |
| Affects audit lineage? | NO |

**Sub-finding 6.A.** R-FG-3 has unfavorable cost-to-value ratio. The MEDIUM new-ambiguity risk is the strongest argument against: introducing formal vocabulary risks creating exactly the confusion the framework is designed to avoid. The 19 existing docs already use informal state names that are clear in context.

**Recommendation:** DEFER (do not apply before execution; may be considered as post-STEP-12-FROZEN documentation cleanup if found useful).

---

## §7. R-FG-4 analysis (Phase 0 markdown code-block wrapper warning)

| dimension | assessment |
|---|---|
| Trigger probability | MEDIUM (markdown copy-paste is fiddly; the amendment plan §4.2 et al. show verbatim text inside ```markdown wrappers) |
| Value-if-triggered | MEDIUM (if mis-paste occurs, the result is visually obvious — extra triple-backtick lines in lineage plan — easy to detect and fix; verification step `wc -l` would catch length anomaly) |
| Application cost | VERY LOW (~3–5 lines of additional runbook Phase 0 content) |
| New-ambiguity risk | VERY LOW |
| Requires own dry-run? | NO |
| Alters runbook semantics? | NO (clarifies existing instruction) |
| Alters governance semantics? | NO |
| Affects audit lineage? | NO |

**Sub-finding 7.A.** R-FG-4 has cheap cost and moderate value (prevents a real friction point at Phase 0). But the verification at end of Phase 0 (`wc -l docs/phase_4b_step12_lineage_normalization_plan.md` ≈ 1067) would catch any wrapper-inclusion mis-paste; the failure is self-detecting.

**Recommendation:** OPTIONAL (low cost; marginal value beyond what existing verification catches; can skip without operational risk).

---

## §8. Aggregate refinement-value matrix

| ID | trigger prob | value-if | cost | ambiguity risk | self-detecting failure? | recommendation |
|---|---|---|---|---|---|---|
| R-FG-1 | LOW | **HIGH** | LOW | VERY LOW | NO (operator stuck) | **APPLY** |
| R-FG-2 | HIGH | LOW | LOW | VERY LOW | YES (intuition handles) | optional/skip |
| R-FG-3 | LOW | LOW | MEDIUM | **MEDIUM** | n/a | DEFER/SKIP |
| R-FG-4 | MEDIUM | MEDIUM | VERY LOW | VERY LOW | YES (`wc -l` check) | optional |

**Sub-finding 8.A.** R-FG-1 is structurally distinct from the others: it is the only refinement whose failure mode is NOT self-detecting (W2 V18 FAIL leaves operator without clear recovery path) and the only one with HIGH value when triggered. R-FG-2/R-FG-3/R-FG-4 are operational polish; R-FG-1 is genuine safety-margin improvement.

---

## §9. Is R-FG-1 effectively mandatory despite "non-blocking" classification?

The final governance review classified R-FG-1 as "non-blocking" because the framework can execute without it; the operator can improvise post-revert recovery from general git knowledge.

But "non-blocking" describes whether the framework is technically executable, not whether the refinement is operationally important.

R-FG-1 is:
* **Technically optional** (framework executes without it).
* **Operationally important** (without it, a Decision-Owner facing W2 V18 FAIL is forced to improvise git recovery commands in a high-stress moment).
* **Constitutionally safe to apply** (additive supersession; no new validators, layers, or invariants).

The classification "non-blocking" should not be read as "skip if convenient." R-FG-1's case is: low-probability scenario, high-consequence scenario, low-cost mitigation. Standard cost-benefit favors application.

**Sub-finding 9.A.** R-FG-1 is functionally mandatory in cost-benefit terms even though formally optional. Skipping it is a real (small) risk acceptance.

---

## §10. Does applying R-FG-1 require its own review/dry-run?

R-FG-1 application would:

* Append additive content to runbook §10 (similar pattern to amendment plan §A1–§A4 appending to lineage plan)
* Not alter any other doc
* Not change runbook semantics (extends recovery path with explicit commands)
* Not change governance/validator/role/invariant
* Not require its own admissibility evaluation (the additive-supersession pattern is already verified admissible per amendment plan §10–§18)
* Not require its own dry-run (no operational decisions changed; only added)
* Not affect audit lineage (no commits during application; W4 glob captures runbook either way)

**Sub-finding 10.A.** R-FG-1 application is parallel to amendment plan A1–A4 application: same additive-supersession discipline; same admissibility basis. No new review cycle required. Decision-Owner can apply directly as a documentation patch.

---

## §11. Saturation analysis

The framework has reached substantial size and depth:

| metric | value |
|---|---|
| Pre-authoring framework docs | 20 |
| Total lines | ~13,900 |
| Contract mutations | 0 |
| Clauses authored | 0 |
| Git commits | 0 |
| Constitutional verdicts rendered | 7 (AUTHORING-ADMISSIBLE, EXECUTION-CONDITIONALLY-READY, DRY-RUN-CONDITIONALLY-SAFE, AMENDMENT-ADMISSIBLE, EXECUTION-RUNBOOK-READY, FINAL-REVIEW-CONDITIONALLY-READY, and this prioritization verdict) |
| Average lines per doc | ~695 |
| Time from session start to here | sustained multi-session planning |

**Diminishing returns assessment:**

| review iteration | new constitutional concerns surfaced |
|---|---|
| Admissibility evaluation | 0 (15 sufficiency criteria all PASS; M1 noted as doc refinement) |
| Execution readiness review | 1 (B1 BLOCKER) + 4 refinements R1–R4 |
| Lineage normalization plan | 0 (operational pathway designed within bounds) |
| Lineage dry-run review | 2 SAFETY-CRITICAL hazards (H2, H5) → amendments A1–A4 |
| Amendment plan | 0 (amendments verified admissible) |
| Execution runbook | 0 (operationally complete) |
| Final governance review | 0 SAFETY concerns + 4 minor refinements R-FG-1 through R-FG-4 |
| This prioritization review | 0 (purely prioritizing among already-identified refinements) |

**Trajectory:** the rate of new substantive concerns has dropped to ZERO over the last 3+ reviews. Each new review confirms prior verdicts and identifies progressively smaller refinements (from constitutional → operational → documentation polish).

**Sub-finding 11.A.** The framework has reached **constitutional saturation**: no new constitutional concerns are emerging from further analysis. The 4 refinements identified by the final governance review are documentation-level; not safety-critical.

**Sub-finding 11.B.** The framework has reached **operational saturation** modulo the R-FG-1 patch: the runbook is operationally complete except for the post-revert recovery sequence explicit guidance.

---

## §12. Governance-recursion-spiral risk assessment

**REFINE-THEN-REVIEW-AGAIN trajectory analysis:**

If the Decision-Owner adopts REFINE-THEN-REVIEW-AGAIN:

1. Apply R-FG-1 through R-FG-4 (4 refinements; ~50–100 lines of additive content across runbook + new framework doc)
2. Conduct review of applied refinements (new doc 22; ~500–700 lines)
3. Review might surface new minor refinements (R-FG-5, R-FG-6...)
4. Apply those (or defer)
5. Review again (doc 23)
6. ...

Each iteration:
* Consumes hours of effort
* Adds documents to the corpus
* Risks introducing new ambiguity (each refinement is a potential confusion source)
* Delays actual execution
* Marginal value approaches zero

The session brief's "no governance recursion spiral" preserved invariant is specifically designed to prevent this trajectory.

**Sub-finding 12.A.** REFINE-THEN-REVIEW-AGAIN would initiate governance recursion. Verdict-rubric option REFINE-THEN-REVIEW-AGAIN should be REJECTED.

**Sub-finding 12.B.** APPLY-R-FG-1-THROUGH-4 (without subsequent review) is borderline — it commits to applying all four refinements which includes R-FG-3 (the medium-ambiguity risk). Better to be selective.

**Sub-finding 12.C.** PROCEED-AS-IS skips R-FG-1 — leaves operator without explicit recovery guidance at the moment of W2 failure. Acceptable but suboptimal.

**Sub-finding 12.D.** ANALYSIS-SATURATION-REACHED captures the meta-finding (no more pre-execution analysis adds value) but does not specifically resolve whether to apply R-FG-1.

**Sub-finding 12.E.** APPLY-R-FG-1-ONLY captures: apply the single highest-value refinement; defer everything else; STOP further pre-execution analysis. This is the surgically-correct verdict.

---

## §13. Refinement-grouping question

If refinements are to be applied, should they be applied as a single patch or individually?

**Single patch (R-FG-1 through R-FG-4 together):**
* Pro: one Decision-Owner action; everything addressed
* Con: includes R-FG-3 (medium new-ambiguity risk); larger diff for runbook + new state-machine doc

**Selective patches (per refinement):**
* Pro: each refinement applied on its own merits; can skip unfavorable ones
* Con: more Decision-Owner actions

**Recommended:** SELECTIVE — apply only R-FG-1; skip the others.

This matches the APPLY-R-FG-1-ONLY verdict.

---

## §14. Does applying R-FG-1 alter the runbook's verbatim commit-message templates?

No. R-FG-1 extends runbook §10 (mid-wave rollback procedure) with explicit post-revert recovery commands. The HEREDOC commit-message templates (§4.4, §5.5, §6.3, §7.3 of runbook) are unaffected.

Specifically, R-FG-1 would add ~20–30 lines to runbook §10 along these lines (verbatim text would be authored by Decision-Owner when applying):

```
After `git revert <failed-wave-sha>`:

# Restore failed-wave working-tree content for correction
git checkout <failed-wave-sha> -- <files-to-fix>
# OR for all files in the failed wave:
git diff <failed-wave-sha>~1 <failed-wave-sha> -- . | git apply

# Make corrections to working tree
# Re-stage corrected content
git add <corrected-files>

# Commit corrected wave (with revised HEREDOC message)
```

Plus brief explanation of why this is needed (revert removes working-tree content; restoration enables correction).

**Sub-finding 14.A.** R-FG-1 application is operationally trivial (~5 minutes of editing) and constitutionally safe. The change is fully bounded to runbook §10.

---

## §15. Saturation declaration

Based on §11 + §12 analyses:

**Constitutional saturation: REACHED.** No new constitutional concerns have emerged in the last 3+ reviews. The 24 invariants are preserved through 20 docs of planning. Further pre-execution constitutional review would not surface new concerns.

**Operational saturation: REACHED modulo R-FG-1.** The runbook is operationally complete except for the post-revert recovery sequence explicit guidance. R-FG-1 closes this single remaining operational gap.

**Pre-execution planning saturation: REACHED.** After R-FG-1 application (if chosen), further pre-execution planning would become governance recursion (per §12). The next valuable action is operational execution.

**Sub-finding 15.A.** The framework has reached pre-execution saturation. Further analysis violates "no analysis-for-its-own-sake" preserved invariant.

---

## §16. Operator-confusion risk from refinement churn

Each refinement applied between now and execution increases the operator's cognitive load:

* They must re-read the runbook to know what changed
* They must verify the refinement matches their understanding
* If multiple refinements are applied, they must integrate the changes mentally

Applying just R-FG-1 (one targeted patch to one section) is minimal cognitive load. Applying all four (4 patches across 2+ docs) is more.

**Sub-finding 16.A.** Operator-confusion risk scales linearly with refinement count. R-FG-1-only minimizes operator-confusion risk while still capturing the highest-value safety improvement.

---

## §17. Final prioritization verdict

### **APPLY-R-FG-1-ONLY**

Apply R-FG-1 (post-revert recovery sequence) as a small additive supersession patch to runbook §10. Defer R-FG-2 (mid-stage break protocol — operator intuition handles it). Defer R-FG-3 (pre-bootstrap state-machine naming — medium new-ambiguity risk; questionable value). Defer R-FG-4 (Phase 0 wrapper warning — self-detecting via `wc -l` verification).

After R-FG-1 application: proceed to runbook Phase 0 → Phases 1–7 → B1 CLOSED → bootstrap S0 → S1–S8 → AUTHORING-ACTIVE.

Do NOT conduct further pre-execution analysis. The framework has reached saturation; additional planning becomes governance recursion.

### Why APPLY-R-FG-1-ONLY (not other options)

| candidate verdict | rejection reason |
|---|---|
| PROCEED-AS-IS | leaves W2 V18 FAIL recovery path implicit; standard cost-benefit favors applying R-FG-1 |
| APPLY-R-FG-1-THROUGH-4 | includes R-FG-3 with medium new-ambiguity risk; includes R-FG-2/R-FG-4 which add minimal value; over-application risks operator confusion |
| REFINE-THEN-REVIEW-AGAIN | initiates governance recursion spiral; each review consumes hours with diminishing value; violates "no governance recursion" preserved invariant |
| ANALYSIS-SATURATION-REACHED | accurate meta-finding but doesn't specifically resolve R-FG-1 application; APPLY-R-FG-1-ONLY captures both the saturation finding AND the R-FG-1 decision |

### Recommended sequence (post-this-verdict)

1. **Decision-Owner reads §17 verdict + §4 R-FG-1 analysis.**
2. **Decision-Owner authors R-FG-1 additive supersession** — append ~20–30 lines to runbook §10 with explicit `git checkout <failed-sha> -- <files>` post-revert recovery commands. Pattern: same as amendment plan §A1–§A4 (additive supersession; no in-place modification of existing §10 text).
3. **Verify runbook line count grew by ~20–30 lines** (single-step verification).
4. **Proceed to runbook Phase 0** (amendment application to lineage plan).
5. **Proceed through Phases 1–7** per runbook.
6. **B1 CLOSED.**
7. **Bootstrap S0–S8.**
8. **AUTHORING-ACTIVE** — first AAU = D-FAULT-6b per Layer A §9.

### Constitutional basis for this verdict

* R-FG-1 application is additive-supersession (same admissibility as amendment plan §A1–§A4 per §10).
* All 24 invariants preserved.
* "no governance recursion spiral" honored (single targeted patch; no new review cycle).
* "no analysis-for-its-own-sake" honored (R-FG-1 has concrete operational value; further planning has zero new value).
* Decision-Owner unilateral application is sufficient (no Reviewer or Constitutional Reviewer required — parallel to amendment plan §20).

---

## §18. Post-verdict: what does NOT happen

Per the saturation finding, the following are FORBIDDEN as next actions:

* Authoring a new framework doc to review whether R-FG-1 application is correct.
* Conducting a dry-run of R-FG-1.
* Designing R-FG-5 / R-FG-6 etc.
* Re-evaluating the admissibility evaluation in light of R-FG-1.
* Re-evaluating the dry-run review in light of R-FG-1.
* Adding new validator classes for "recovery completeness" or similar.
* Adding new review layer for "refinement application review."
* Convening a constitutional review for R-FG-1.

These actions are governance recursion. The framework explicitly forbids them.

The next valuable action is **operational execution** (runbook Phase 0 onward).

---

## §19. Vocabulary

| term | meaning |
|---|---|
| Refinement prioritization | the practical decision on which non-blocking refinements to apply pre-execution |
| Saturation | the framework state where further pre-execution analysis surfaces no new substantive concerns |
| Governance recursion spiral | the trajectory where each refinement triggers a review which surfaces more refinements which trigger more reviews |

None enter the normative contract.

---

## §20. Preserved invariants under this prioritization

This prioritization introduces no new invariants and modifies no inherited ones. All 24 inherited invariants confirmed preserved:

* replay-authoritative truth ✓
* append-only causality ✓
* additive-only mutation discipline ✓
* BRANCH-LINEARITY ✓
* AUDIT-COMPLETENESS ✓
* validator supremacy ✓
* no semantic widening ✓
* no hidden cleanup ✓
* no authority redistribution ✓
* **no governance recursion spiral** ✓ (this verdict explicitly avoids recursion)
* **no analysis-for-its-own-sake** ✓ (this verdict declares pre-execution planning saturation)
* (plus all other inherited invariants)

None weakened. None widened. None silently dropped.

---

**End of Step 12 R-FG refinement prioritization.**

**Verdict: APPLY-R-FG-1-ONLY.**

Apply R-FG-1 as a small additive supersession patch to runbook §10 (post-revert recovery sequence). Defer R-FG-2/R-FG-3/R-FG-4. Then proceed directly to runbook Phase 0 execution. Conduct no further pre-execution analysis — the framework has reached saturation.

**Saturation declaration:** the pre-authoring constitutional + operational corpus is now COMPLETE modulo R-FG-1 application. Further pre-execution planning is governance recursion, not risk reduction.

Predecessors: all 20 prior Step 11 + Step 12 framework artifacts.

Successor: Decision-Owner applies R-FG-1 (single additive patch to runbook §10) → runbook Phase 0 → Phases 1–7 → B1 CLOSED → bootstrap S0 → S1–S8 → AUTHORING-ACTIVE → 29 AAUs across 6 codification waves → STEP-12-FROZEN.
