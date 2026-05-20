# Phase 4B Step 12 — Governance Plan (Layer D — Pre-Authoring, Final Transition-Planning Layer)

**Status: PRE-AUTHORING LAYER-D CROSS-CLAUSE-GOVERNANCE PLAN (2026-05-21).** Designs the final governance/sequencing layer that coordinates Layers A, B, and C into a constitutionally bounded end-to-end authoring pipeline. Inherits the AAU model + 4 mutation shapes + reversibility envelope from [`phase_4b_step12_authoring_mechanics_plan.md`](phase_4b_step12_authoring_mechanics_plan.md); inherits the 20-validator catalog + 4-stage validation lifecycle from [`phase_4b_step12_validation_plan.md`](phase_4b_step12_validation_plan.md); inherits the bounded-reviewer workflow + audit-trace model from [`phase_4b_step12_review_ergonomics_plan.md`](phase_4b_step12_review_ergonomics_plan.md). Does **not** author clause wording, does **not** mutate the contract document, does **not** introduce reviewer-override mechanisms or validator-bypass pathways, does **not** redistribute authority.

Layer D is the **final transition-planning layer**. After Layer D, the four-layer pre-authoring framework is complete and Step 12 normative authoring admissibility may be evaluated by the decision-owner. Layer D does not itself authorize authoring; it specifies the conditions under which authoring becomes admissible.

---

## §1. Scope and inheritance

| inherited from | element |
|---|---|
| Layer A §2, §3, §13, §16 | AAU = 1 commit; 4 mutation shapes; `git revert` reversibility; no-amend discipline |
| Layer B §3, §16, §17 | 20-validator catalog; BLOCKING/SOFT failure protocol; REJECTED criteria |
| Layer C §4, §15, §19, §21 | 3-option decision surface; Wave Closure Packet; immutable audit trace; 8 escalation triggers |
| Step 11 extraction plan §3 | 6-wave order and inter-wave dependencies |
| Step 11 codification plan §11 | what Step 11 does/does not decide (Layer D inherits "does not decide" as authoring-time territory) |

Layer D specifies only the cross-AAU + cross-wave + branch-and-merge governance overlay. It does not modify any inherited mechanism. It does not introduce new BLOCKING rules at the AAU or wave level beyond aggregating inherited validators at the governance level.

---

## §2. The end-to-end pipeline state machine

The Step 12 authoring pipeline has eight named states:

```
[BASELINE] ─→ [WAVE-IN-PROGRESS] ⇄ [WAVE-PAUSED-ESCALATION]
                       │
                       ▼ (all AAUs APPROVED + wave-close APPROVED)
            [WAVE-CLOSED] ─→ [next wave: WAVE-IN-PROGRESS] (waves 1–6)
                       │
                       ▼ (all 6 waves CLOSED)
            [ALL-WAVES-CLOSED] ─→ [FINAL-FORM-VALIDATION]
                       │
                       ▼ (all final-form checks PASS)
            [PR-OPEN-FOR-MERGE] ─→ [MERGED-TO-MASTER]
                       │
                       ▼ (audit-trace archived + closure-verification doc written)
            [STEP-12-FROZEN]
```

| state | meaning | gating to exit |
|---|---|---|
| BASELINE | pre-Wave-1; codification branch created; no AAUs yet | first AAU of Wave 1 begins |
| WAVE-IN-PROGRESS | AAUs being authored, validated, and reviewed within a wave | wave's final AAU APPROVED |
| WAVE-PAUSED-ESCALATION | escalation triggered mid-wave; Layer D escalation protocol engaged | escalation RESOLVED per §17 |
| WAVE-CLOSED | wave-close review APPROVED; wave-closure tag applied | next wave's first AAU begins, or ALL-WAVES-CLOSED if wave was Wave 6 |
| ALL-WAVES-CLOSED | all 6 waves complete | final-form validation begins |
| FINAL-FORM-VALIDATION | governance-level final checks running | all final-form checks PASS |
| PR-OPEN-FOR-MERGE | final PR opened; 8 pre-merge gates evaluated | all gates PASS + human merge approval |
| MERGED-TO-MASTER | branch merged | audit-trace archived + closure doc written |
| STEP-12-FROZEN | terminal state; contract at post-Step-12 form | next constitutional update cycle (Step 13+) opens its own pipeline |

**Sub-finding 2.A.** Layer D's state machine is strictly linear (modulo wave-internal escalation pause/resume). No state admits parallelism across waves. No state admits a shortcut transition.

---

## §3. Wave-governance topology

Each of the 6 waves is a discrete governance unit with its own lifecycle:

| stage | meaning | Layer reference |
|---|---|---|
| WAVE-START | wave's first AAU begins authoring | Layer A §10 (pre-wave verification) |
| WAVE-IN-PROGRESS | AAUs being authored + validated + reviewed in wave order | Layer A §9.B (intra-wave ordering); Layer B §15 (per-AAU sequencing); Layer C §20 (handoff sequencing) |
| WAVE-AAU-COMPLETE | wave's final AAU APPROVED (per Layer C) | Layer C §15 wave-close review may begin |
| WAVE-CLOSE-IN-REVIEW | wave-close packet under reviewer adjudication | reviewer decision per Layer C §15 |
| WAVE-CLOSED | wave-close APPROVED; tag applied | next wave's WAVE-START, OR ALL-WAVES-CLOSED |

**Wave-closure tag.** Upon WAVE-CLOSED, a git tag `step12-wave-N-closed` is applied to the wave's final AAU commit (or to a wave-close marker commit; see §14). Tags are immutable and serve as wave checkpoints visible in `git log --tags`.

**Wave-internal vs cross-wave authority.** Within a wave, Layer A + Layer B + Layer C are sufficient. Across waves, Layer D mediates: cross-wave dependencies are enforced by inter-wave citation gap validation (V19) at each wave-close, and by the no-skip rule (§4) at wave-sequencing.

**Sub-finding 3.A.** The wave is the governance unit. Six waves = six discrete governance episodes. Each wave's outcome is binary (CLOSED or ESCALATED); no partial-wave state escapes to the next wave.

---

## §4. Cross-wave sequencing discipline

Waves are strictly sequential:

| rule | enforcement |
|---|---|
| **No parallel waves** | only one wave is WAVE-IN-PROGRESS at any time |
| **Wave N+1 may not begin until Wave N is CLOSED** | state machine transition (§2) |
| **Wave order is fixed: 1 → 2 → 3 → 4 → 5 → 6** | per extraction plan §3; Layer D does not re-order |
| **Cross-wave revert is exceptional** | per §15; requires constitutional-reviewer approval |
| **No mid-wave amendment of earlier waves** | per §14 wave-freeze; Layer A no-amend invariant extended |

**Cross-wave invariants** (verified at each wave-close by V19):

* Every citation in any wave-N AAU resolves to a clause-ID present at end-of-wave-N.
* No wave-N AAU cites a clause-ID introduced in wave-N+1 or later.
* No wave-N AAU's citation set was broken by a sibling AAU's commit within wave N.

**Sub-finding 4.A.** The sequencing discipline mirrors the Step 11 extraction plan's wave-order dependency graph. Layer D does not introduce new dependencies; it enforces the inherited ones at the governance level.

---

## §5. Branch isolation strategy

Step 12 authoring uses a **single long-lived codification branch** with a single integration point at the final merge:

| element | specification |
|---|---|
| Branch name | `phase-4b-step12-codification` (or equivalent; exact name set at authoring start) |
| Branch base | created from `master` at the SHA where master sits at authoring start (current master is at `cb95a9a` Step 8 Phase 6 closure plus subsequent Step 9/10 closures per memory state) |
| Branch lifetime | created at BASELINE; closed at MERGED-TO-MASTER |
| Master interaction during authoring | **NONE**. Master is frozen relative to the Step 12 contract content for the duration of authoring |
| Rebase against master | **FORBIDDEN** during authoring (would rewrite history; would defeat audit trail) |
| Force-push | **FORBIDDEN** at all times on this branch |
| Commits on branch | strictly AAU commits (per Layer A §11) + revert commits (per Layer A §13) + optional wave-close marker commits (per §14) |

**Why single long-lived branch.** Six per-wave branches would create six integration points to master, each producing a partial-codification master state. The substrate's "Step 12 codification" is one atomic constitutional update; master sees it as one atomic addition.

**Concurrent master changes (out-of-scope but acknowledged).** If master receives non-Step-12 changes during authoring (e.g., runtime fixes, Step 8/9/10 maintenance), Layer D specifies: the codification branch does NOT rebase. If a non-fast-forward merge results at PR time, a single merge commit is created at the PR boundary; the codification branch's linear history is preserved as one parent of that merge.

**Sub-finding 5.A.** Branch isolation is the structural enforcement of Step 12's constitutional atomicity. Master never observes a partially-codified contract.

---

## §6. PR boundary planning

**Decision: ONE final PR for all 29 AAUs.** Rationale enumerated:

| candidate | rejection reason |
|---|---|
| 29 PRs (one per AAU) | too granular; PR review overhead per AAU is wasteful; Layer C already provides per-AAU review at the validator/reviewer level — duplicating it at PR level is convenience-driven restructuring forbidden in the session brief |
| 6 PRs (one per wave) | each PR merge to master would create a partial-codification master state (6 intermediate states); violates §5 branch-isolation rationale; also requires master-rebase between waves |
| 1 PR (all 29 AAUs) | matches branch-isolation rationale; matches Step 12 constitutional atomicity; PR's review surface is the final-form validation report + the audit trace, not per-AAU re-review |

**PR lifecycle:**

| event | timing |
|---|---|
| Draft PR opened | after Wave 1 CLOSED (gives external visibility into branch progress; not a review surface) |
| Draft PR updated | after each wave CLOSED (additional commits visible) |
| Draft PR promoted to ready-for-review | after ALL-WAVES-CLOSED + FINAL-FORM-VALIDATION all PASS |
| PR review | per §13 pre-merge governance gates |
| PR merge | per §19 merge admissibility protocol |
| Branch close | per §20 branch-close conditions |

**Sub-finding 6.A.** The single PR is "Phase 4B Step 12 — Live Ingress Codification (29 AAUs across 6 waves)". Its review surface is the governance artifacts, not per-AAU re-review. Per-AAU review already happened on-branch.

---

## §7. Replay-test invocation cadence

Layer B §7.1 recommended end-of-wave as the minimum cadence for V18 (replay-test invariant). Layer D codifies the actual cadence:

| cadence | scope | gating |
|---|---|---|
| **End of every wave** | V18 + V19 | BLOCKING for wave-close per Layer C §15 |
| **End of every FII AAU** | V18 | RECOMMENDED (not BLOCKING); 4 invocations across Waves 1 + 3 |
| **End of the SF AAU** | V18 | RECOMMENDED (not BLOCKING); 1 invocation in Wave 5 |
| **End of ALL-WAVES-CLOSED, before final PR** | V18 + V19 + final-form checks (§12) | BLOCKING for FINAL-FORM-VALIDATION exit |
| **At PR-OPEN-FOR-MERGE, before merge** | V18 (re-confirm on PR-ready commit) | BLOCKING for merge admissibility per §19 |

**Total BLOCKING V18 invocations:** 6 (one per wave-close) + 1 (final-form) + 1 (pre-merge) = **8 BLOCKING invocations**.

**Total RECOMMENDED V18 invocations:** 4 (FII) + 1 (SF) = **5 RECOMMENDED invocations**.

**Maximum total V18 invocations:** 13 across the entire Step 12 authoring phase.

**Rationale for end-of-FII RECOMMENDED:** FII is the highest-risk shape per Layer A §6 and Layer B §8.3. Per-FII V18 catches the rare case where a family-internal insertion's edit accidentally affected a runtime-consumed string. RECOMMENDED (not BLOCKING) because the FII overlay validators already cover the renumbering hazard; V18 is belt-and-suspenders.

**Sub-finding 7.A.** Layer D's V18 cadence is the operational answer to Layer B §7.1's deferred question. The 8 BLOCKING invocations are the minimum constitutional safety net; the 5 RECOMMENDED invocations are operator discretion.

---

## §8. Escalation-resolution topology

Layer C §21 named 8 escalation triggers (T1–T8). Layer D defines the resolution topology for each:

| trigger | category | resolution path |
|---|---|---|
| **T1: V18 FAIL at wave-close** | substrate integrity | identify root cause (runtime consumes docstring? test harness regressed?) → revert offending AAU(s) → re-author with corrected approach; if root cause is a Layer-A or Layer-B violation, escalate further to Step 11 re-opening |
| **T2: V19 FAIL at wave-close** | citation integrity | citation-graph re-analysis → identify which AAU introduced the gap → revert + re-author |
| **T3: irresolvable SOFT flag** | semantic adjudication | constitutional review (see §8.1); decision recorded as constitutional-resolution artifact |
| **T4: fresh constitutional principle detected** | scope violation | Step 11 codification plan MUST be re-opened; Step 12 is HALTED until Step 11 re-closes; if Step 11 re-closure changes Step 12's AAU plan, Step 12 restarts from BASELINE with the updated extraction plan |
| **T5: anchor/shape requires Layer-A modification** | governance violation | Layer A plan revised; Step 12 paused at current state; resume after Layer A re-issued |
| **T6: REJECTED AAU per Layer B §17** | unauthorability | codification plan + extraction plan re-evaluated; replacement AAU (if any) introduced; if no replacement is possible, Step 11 re-opening per T4 |
| **T7: NOT-CONFIRMED preserved invariant** | substrate integrity | IMMEDIATE pause; full invariant audit; same recovery as T1 if root cause is identifiable; otherwise Step 11 re-opening |
| **T8: reviewer uncertainty (default-to-escalate)** | adjudication boundary | constitutional review (see §8.1); same as T3 |

### §8.1 The constitutional review

For T3 and T8 escalations, Layer D specifies a **constitutional review** as the resolution venue. The constitutional review:

* Convenes the AAU's Author, the AAU's Reviewer, and at least one Constitutional Reviewer (role defined in §10).
* Re-reads the relevant framework documents (Step 11 framework, codification plan, extraction plan).
* Adjudicates the escalation by EXPLICIT unanimous agreement of all participants.
* If unanimous agreement is not achieved, the constitutional review ESCALATES FURTHER to Step 11 re-opening (the only escalation path beyond Layer D's scope).
* Records the decision as a constitutional-resolution artifact (per §17) appended to the audit trace.

**Sub-finding 8.A.** The constitutional review is the only Layer-D-internal escalation venue. Its decision authority is bounded: it adjudicates the SOFT-flag or scope-uncertainty in question; it does NOT introduce new constitutional principles (that would itself be T4 and would re-open Step 11). The constitutional review is the human-judgment safety net for the adjudication space Layer C cannot resolve alone.

---

## §9. Author/reviewer separation policy

Layer D specifies role-separation as a governance invariant:

| pair | constraint |
|---|---|
| Author and Reviewer for the same AAU | MUST be different agents |
| Author and Constitutional Reviewer for the same AAU's escalation | MUST be different agents |
| Reviewer and Constitutional Reviewer for the same AAU's escalation | MUST be different agents |
| Author for two different AAUs | MAY be the same agent (no rotation requirement) |
| Reviewer for two different AAUs | MAY be the same agent (no rotation requirement) |
| Per-AAU Reviewer and Wave-Close Reviewer for the same wave | MAY be the same agent |
| Wave-Close Reviewer and Final-Form Reviewer | MAY be the same agent |

**Why separation.** Self-approval is a structural override of validator supremacy; the author has invested intent in the AAU and cannot adjudicate SOFT flags on it without bias. Separation enforces independent verification.

**Why no rotation requirement.** Mandatory rotation introduces scheduling complexity without constitutional benefit. The validator-supremacy invariant (Layer C §3) bounds reviewer authority enough that "same reviewer for many AAUs" does not create drift; per-AAU reviewer-decision-surface minimization (Layer C §4) bounds the decision space such that consistency from one reviewer is not problematic.

---

## §10. Role definitions

Layer D names **four roles**; assignment of specific agents to roles is operational (out of scope for Layer D):

| role | responsibilities | constraints |
|---|---|---|
| **Author** | drafts AAUs per Layer A + Layer B Stage 2 body validation; iterates after REVISE | NOT the reviewer for own AAU (§9); MAY author multiple AAUs across waves |
| **Reviewer** | adjudicates per Layer C: per-AAU APPROVE/REVISE/ESCALATE; wave-close APPROVE WAVE-CLOSE/ESCALATE | NOT the author for the AAUs reviewed (§9); MAY review multiple AAUs |
| **Constitutional Reviewer** | adjudicates T3/T8 escalations via constitutional review (§8.1); decision authority bounded to the specific escalation | NOT the author or reviewer for the escalating AAU (§9); MUST have framework-document context |
| **Decision-Owner** | authorizes Step 12 to begin (at BASELINE); confirms G8 merge approval (§13); declares Step 12 ARCHITECTURALLY CLOSED (per §24) | role of operational authority; assignment is project-level |

**Sub-finding 10.A.** Layer D specifies role TYPES, not specific agents. Concrete assignments (e.g., "Alice is Reviewer for Wave 1; Bob is Reviewer for Waves 2 and 3") are operational decisions made by the Decision-Owner at authoring-start.

---

## §11. Multi-reviewer conflict protocol

The default model is **one reviewer per AAU and one reviewer per wave-close** (Layer C §15 implies one reviewer; Layer D confirms this as the default).

If multiple reviewers are assigned to the same AAU or wave-close (operational choice; not required):

| scenario | resolution |
|---|---|
| All reviewers APPROVE | AAU/wave proceeds |
| All reviewers REVISE (same shape-guidance) | AAU reverted; author re-drafts per shape-guidance |
| All reviewers REVISE (different shape-guidance) | the AAU enters constitutional review (§8.1) — reviewers' divergence on shape is itself a T8 trigger |
| Any reviewer ESCALATE | the AAU/wave is ESCALATED regardless of other reviewers' positions (the most restrictive decision wins) |
| Mixed APPROVE + REVISE | the AAU is treated as REVISE (any non-APPROVE decision blocks; this is consistent with validator supremacy — the most restrictive interpretation governs) |

**No majority-vote mechanism.** Majority vote would admit a path where one reviewer's REVISE is overridden by two APPROVES — that's discretionary semantic reinterpretation and is forbidden. Layer D's resolution is "the most restrictive decision wins"; this preserves the no-override invariant.

**Sub-finding 11.A.** Multi-reviewer is operationally permissible but governance-neutral: it adds belt-and-suspenders without changing the decision algebra. Single-reviewer is the default; multi-reviewer requires no Layer D changes.

---

## §12. Final-form validation sequencing

After ALL-WAVES-CLOSED, before PR-OPEN-FOR-MERGE, Layer D specifies five **final-form checks** that run as the FINAL-FORM-VALIDATION state. These are aggregate or completeness checks; they do not introduce new V-numbered validators in the Layer B namespace.

| check | description | mechanism |
|---|---|---|
| **FF1** | V18 (replay-test invariant) on branch HEAD | one-shot invocation of `tools/check_session_replay_identity.py` against the 3-cycle baseline |
| **FF2** | V19 (citation gap) across all 29 AAUs | full graph traversal of the post-all-waves citation DAG |
| **FF3** | Step 12 completeness check | confirm all 38 catalogued insertions present (per extraction plan §1); confirm 15 new clause-IDs exist (D-FAULT-6b, D-FAULT-6c, D-FAULT-9b, D-FAULT-9c, D-SCHED-14, D-REPLAY-10, D-INGRESS-1..9); confirm §14 D-INGRESS exists with 9 clauses + scope + restatement; confirm D-FAULT-15 row count = 42; confirm §0 glossary has 14 entries; confirm T1/T4/T5/T8 embedded notes present in §1/§3/§4/§5; confirm §11 item 1 marked CLOSED |
| **FF4** | Framework/contract separation aggregate check | aggregate run of V9 across all 17 new clause bodies (8 standalone + 9 inside §14); confirm zero framework references in Sections A/B; confirm Section C framework references resolve to existing file paths |
| **FF5** | Substrate preservation check | confirm pre-Step-12 baseline contract (extracted at BASELINE branch creation time) is byte-identical to post-Step-12 contract MINUS the 29 AAU insertions and minus the SF status flip; no other modification, no deletion |

All five final-form checks are BLOCKING. Failure of any halts FINAL-FORM-VALIDATION; resolution per the escalation topology of §8 (typically T1 or T2 path).

**The final-form validation report.** A consolidated report `docs/phase_4b_step12_final_form_validation_report.md` is produced at FF-PASS. Schema:

```
- FF1 result: PASS / FAIL (with hash details)
- FF2 result: PASS / FAIL (with unresolved citation list if any)
- FF3 result: PASS / FAIL (with missing-insertion list if any)
- FF4 result: PASS / FAIL (with leaked-reference list if any)
- FF5 result: PASS / FAIL (with unexpected-modification diff if any)
- Aggregate AAU count: 29 (29 expected)
- Aggregate revert count: <N> (per-AAU REVISE-trigger history)
- Aggregate escalation count: <N> (per-AAU + per-wave + constitutional-review history)
- Preserved-invariant table: 19 rows, all CONFIRMED
```

**Sub-finding 12.A.** Final-form validation is the substrate-level equivalent of Layer C's wave-close review. It confirms the 29-AAU aggregate is consistent before master sees it.

---

## §13. Pre-merge governance gates

Eight gates between PR-OPEN-FOR-MERGE and MERGED-TO-MASTER. All BLOCKING:

| gate | requirement |
|---|---|
| **G1** | FF1–FF5 all PASS (per §12); final-form validation report attached to PR |
| **G2** | All 29 per-AAU reviews APPROVED + recorded in audit trace |
| **G3** | All 6 wave-close reviews APPROVED + recorded in audit trace |
| **G4** | All escalations RESOLVED (none OPENED or IN-RESOLUTION) per §17 |
| **G5** | Branch has exactly 29 AAU commits + N revert/re-author commits as audit trail; no force-pushed history; `git log --oneline` shows linear chronological additions |
| **G6** | All commit messages match Layer A §11 convention (form: `Phase 4B Step 12 / Wave <N> — <AAU label>` + framework-citation rationale) |
| **G7** | Audit trace artifacts (per Layer C §19) all present at their permanent location (`docs/step12_audit_traces/` per §20) |
| **G8** | Decision-Owner human merge approval — a person with merge rights confirms G1–G7 verified |

Any gate FAIL halts merge until resolved. The resolution path depends on which gate failed: G1 failures → re-enter FINAL-FORM-VALIDATION; G2/G3 failures → re-enter Layer C review; G4 failures → escalation resolution per §17; G5/G6/G7 failures → audit-trail repair (additive-only; never history-rewriting); G8 = pending Decision-Owner action.

**Sub-finding 13.A.** G8 is the only gate that admits human discretionary judgment, and it is bounded: the Decision-Owner confirms G1–G7 verification, they do NOT re-adjudicate AAU content. G8 is operational sign-off, not constitutional approval.

---

## §14. Post-wave freeze protocol

After WAVE-CLOSED:

| rule | enforcement |
|---|---|
| Wave's AAU commits are TAGGED `step12-wave-N-closed` | git tag at AAU final commit |
| Subsequent waves MAY NOT amend earlier waves' commits | Layer A §16 no-amend invariant extended cross-wave |
| Subsequent waves MAY revert earlier waves' commits | only via Layer A §13 revert; ONLY with constitutional-reviewer approval per §15 |
| Wave-closure tag is immutable | never delete, never move (additive-only at the tag layer) |
| Wave's audit-trace artifacts are immutable | per Layer C §19 |

**Optional wave-close marker commit.** Layer D recommends (but does not require) appending an empty marker commit at wave-close with message `Phase 4B Step 12 / Wave <N> CLOSED` and the wave-closure validator summary in the body. This marker, if present, is the tag target; if absent, the tag targets the wave's final AAU commit directly. Operational choice.

**Sub-finding 14.A.** Post-wave freeze extends Layer A's no-amend discipline across waves. The audit trail is preserved by additive-only governance just as the contract is preserved by additive-only mutation.

---

## §15. Rollback governance discipline

Three rollback scenarios, each with distinct governance:

| scenario | governance |
|---|---|
| **Per-AAU rollback** (REVISE within a wave, AAU not yet APPROVED) | No Layer D approval needed; standard Layer A §13 revert + re-author |
| **Wave-internal rollback after wave-close APPROVED, before next wave starts** | Requires constitutional-reviewer approval (T8 path); documented as cross-wave reversion artifact; wave-closure tag preserved but a "wave-close-reverted" tag added to the revert commit |
| **Cross-wave rollback** (revert a wave-N commit after wave-N+1 or later has begun) | Requires Step 11 re-opening (T4 path); Step 12 HALTED at current state; all subsequent waves' commits potentially affected; full re-evaluation of extraction plan |

**Sub-finding 15.A.** The three scenarios are increasingly severe. Per-AAU rollback is routine. Wave-internal post-close rollback is exceptional. Cross-wave rollback effectively re-opens Step 11. Layer D enforces each scenario's governance to prevent silent escalation severity.

---

## §16. Re-authoring governance after REVISE

When Layer C issues REVISE on AAU N (within an active wave):

1. AAU N is reverted via Layer A §13: `git revert <AAU-N-commit-sha>` produces a revert commit.
2. Author re-drafts AAU N per the reviewer's shape-guidance (Layer C §17 no-wording-author rule).
3. The re-authored AAU N enters Layer B Stage 1 (Anchor Validation) — full revalidation, not partial.
4. On Stage-3 commit, AAU N occupies its same slot in the wave sequence (no slot insertion; same wave-internal ordering).
5. Audit-trace shows three commits for AAU N: original AAU-N commit + revert commit + re-authored AAU-N commit. All preserved; none collapsed.
6. The re-authored AAU N enters Layer C review (per Layer C §20 handoff sequencing).

**Reviewer assignment for re-authored AAU.** MAY be the same Reviewer or a different one. Layer D does not require rotation. The new review is a fresh Layer C decision, not a continuation of the prior one.

**Tracking REVISE history.** The audit trace at PR time (G2) includes the REVISE history for every AAU: how many REVISE iterations occurred, the shape-guidance for each, the final APPROVE rationale. Multi-REVISE AAUs are visible in the trace but not flagged as problematic per se — REVISE is the system working as designed.

**Sub-finding 16.A.** The 3-commit audit pattern (original + revert + re-author) for every REVISE is the operational analogue of Layer A's reversibility envelope. The audit trail grows linearly with REVISE activity; no rebasing or history-rewriting masks REVISE history.

---

## §17. Escalation lifecycle management

Every escalation has a strict 4-state lifecycle:

```
[OPENED] ─→ [IN-RESOLUTION] ─→ [RESOLVED] ─→ [RECORDED]
```

| state | transition into | transition gating |
|---|---|---|
| OPENED | escalation trigger fires; reviewer ESCALATE recorded; or auto-triggered by V18/V19 FAIL | escalation kind (T1–T8) classified |
| IN-RESOLUTION | resolution path per §8 engaged | per resolution kind: constitutional review convened / Step 11 re-opening initiated / Layer A revision drafted / etc. |
| RESOLVED | resolution decision made | decision artifact authored |
| RECORDED | resolution artifact appended to audit trace | always reachable from RESOLVED; no escape backwards |

**Concurrent escalations.** Multiple escalations MAY be OPENED simultaneously on different AAUs or waves. Each progresses through its own lifecycle independently. The pipeline state (§2) is WAVE-PAUSED-ESCALATION while ANY escalation is OPENED or IN-RESOLUTION; resumes WAVE-IN-PROGRESS only after ALL are RECORDED.

**No-skip rule.** OPENED → IN-RESOLUTION → RESOLVED → RECORDED is strict. An escalation cannot jump from OPENED directly to RECORDED. The IN-RESOLUTION state is the explicit human-judgment window; skipping it would be a discretionary-semantic-reinterpretation path.

**Sub-finding 17.A.** The 4-state lifecycle ensures every escalation is auditable end-to-end. The audit trace contains the trigger, the resolution path, the decision, and the artifact reference for every escalation that ever occurred.

---

## §18. Governance-level invariant preservation

Layer D introduces five governance-level invariants that operate at the pipeline-and-branch level:

| invariant | enforcement |
|---|---|
| **WAVE-ATOMICITY** | A wave is either WAVE-CLOSED or not; master never observes a partial-wave state |
| **BRANCH-LINEARITY** | The codification branch is linear; reverts are explicit commits, never rebases or force-pushes |
| **MERGE-ATOMICITY** | The final PR is one merge to master; Step 12 codification appears in master atomically |
| **AUDIT-COMPLETENESS** | Every decision (author commit, reviewer adjudication, escalation resolution) recorded in audit trace |
| **ROLE-SEPARATION** | Author ≠ Reviewer; Constitutional Reviewer ≠ Author and ≠ Reviewer for the same AAU (per §9) |

These five complement the inherited Layer A/B/C invariants without introducing new constitutional principles.

**Sub-finding 18.A.** The five governance invariants are operational, not constitutional. They ensure the pipeline's *process* preserves the substrate's *constitution*. They do not themselves modify what the substrate enforces.

---

## §19. Merge admissibility protocol

The merge to master is admissible iff all of:

1. All 8 pre-merge governance gates (§13) PASS.
2. The branch is fast-forward-mergeable to master, OR a single non-fast-forward merge commit is permissible per master's merge policy.
3. The merge commit message references all 6 wave-closure tags (e.g., `Merges step12-wave-1-closed, step12-wave-2-closed, ..., step12-wave-6-closed`).
4. The merge commit message references the final-form validation report path.
5. The audit-trace artifacts are present at their permanent location in the branch and visible in the PR's review surface.
6. The Decision-Owner has affirmed G8.

Merge execution:

* If fast-forward: `git merge --ff-only <branch>` on master.
* If non-fast-forward: `git merge --no-ff <branch>` on master, with the merge commit message structured per (3) and (4).

**Post-merge:** wave-closure tags are preserved (not deleted). The branch may be archived (kept with `archived/` prefix) or deleted at operational discretion — preserved branch is the conservative choice for audit-traceability.

**Sub-finding 19.A.** The merge is the pipeline's single transactional event with master. Its admissibility is fully determined by mechanical gates (G1–G7) plus one human confirmation (G8); no discretionary substrate-level decisions occur at merge.

---

## §20. Branch-close conditions

The codification branch is CLOSED when:

| condition | requirement |
|---|---|
| Merge to master succeeded | per §19 |
| Wave-closure tags preserved | `step12-wave-1-closed` through `step12-wave-6-closed` all present on master |
| Audit-trace artifacts persisted to permanent location | `docs/step12_audit_traces/` directory present on master; structure: one file per AAU decision, one file per wave-close decision, one file per escalation resolution |
| Final-form validation report archived | `docs/phase_4b_step12_final_form_validation_report.md` on master |
| Closure-verification doc written | `docs/phase_4b_step12_closure_verification.md` on master (analogous to `phase_4b_step11_closure_verification.md`) |

**Branch retention.** Layer D recommends KEEPING the codification branch with rename to `archived/phase-4b-step12-codification` after merge. This preserves the pre-merge linear history independently of master's post-merge state. Operational discretion.

---

## §21. Final codification freeze protocol

After MERGED-TO-MASTER:

| rule | enforcement |
|---|---|
| `phase_4b_deterministic_semantics.md` is at "post-Step-12" form | inspectable on master HEAD |
| The contract is FROZEN at this state | no further mutations until a new constitutional update cycle (Step 13+) opens its own Layer-A-through-D pipeline |
| Runtime work MAY consume the new clauses | downstream of Step 12; outside Layer D scope but acknowledged |
| Subsequent Step 12 modifications are FORBIDDEN | any further constitutional change requires a fresh Step-N cycle with its own codification plan + extraction plan + Layers A/B/C/D |
| The 29 AAU commits + revert commits + audit trace are immutable on master | git history; preserved |

**Why "frozen until next Step-N cycle."** This preserves Step 12's identity as a coherent constitutional update. A future Step 13 may revise or extend the substrate further, but it does so as a SEPARATE atomic update with its own pipeline. No "small fix to Step 12" pathway exists; that pathway would be convenience-driven restructuring and is explicitly forbidden.

**Sub-finding 21.A.** The freeze protocol prevents post-merge drift via incremental "small fixes." All further constitutional change requires the full Layer A/B/C/D pipeline; no shortcuts.

---

## §22. Governance auditability

At STEP-12-FROZEN, the full audit trail comprises:

| artifact | location | count (expected) |
|---|---|---|
| AAU commits | git history on master (post-merge) | 29 |
| Revert commits | git history on master | N (per REVISE-trigger history; 0 in ideal case, possibly several in practice) |
| Re-authored AAU commits | git history on master | matches revert count |
| Wave-close marker commits (optional) | git history on master | 0 or 6 |
| Wave-closure tags | git tags on master | 6 (`step12-wave-1-closed` through `step12-wave-6-closed`) |
| Per-AAU audit-trace artifacts | `docs/step12_audit_traces/aau_<id>_decision.md` | 29 (one per APPROVED AAU; if multi-REVISE, the artifact references all decisions) |
| Per-wave-close audit-trace artifacts | `docs/step12_audit_traces/wave_<N>_close_decision.md` | 6 |
| Escalation resolution artifacts | `docs/step12_audit_traces/escalation_<id>_resolution.md` | N (per escalation; 0 in ideal case) |
| Final-form validation report | `docs/phase_4b_step12_final_form_validation_report.md` | 1 |
| Closure-verification doc | `docs/phase_4b_step12_closure_verification.md` | 1 |
| Merge commit | git history on master | 1 |

All persistent. No deletion. No rebasing. No history rewriting. The full audit trail is reconstructable from git + the docs directory at any future time.

---

## §23. Constitutional freeze criteria

Step 12 is **constitutionally frozen** when ALL of:

1. The 5 governance invariants of §18 hold on master HEAD.
2. All 19 preserved invariants from Layers A/B/C hold at master HEAD (verified by §25 mapping table).
3. FF1–FF5 PASS on master HEAD (re-run as final confirmation).
4. No escalation is OPENED or IN-RESOLUTION across the project state.
5. The closure-verification doc is written and references all the above.

Verification is mechanical: re-run FF1–FF5 on master HEAD; inspect audit-trace; confirm no open escalation. Result is binary: FROZEN or NOT-FROZEN.

**Sub-finding 23.A.** Constitutional freeze is the substrate's terminal state for Step 12. After freeze, the substrate's constitutional posture is "live-ingress-codified, replay-authoritative, additive-only-mutated, with the Step 11 framework folded into the contract as 29 AAUs across 6 waves." Any further work consumes this frozen substrate; it does not modify it.

---

## §24. Authoring completion criteria

Step 12 normative authoring is **COMPLETE** when:

| criterion | source |
|---|---|
| Constitutional freeze verified | §23 |
| Audit trail complete | §22 |
| Branch closed (or archived) | §20 |
| Final PR merged | §19 |
| Closure-verification doc written | §20 + §22 |
| MEMORY index updated to reflect post-Step-12 substrate | per project memory convention |

The Decision-Owner declares Step 12 ARCHITECTURALLY CLOSED, analogous to the closure declarations for Step 8 / Step 9 / Step 10 Direction A. The closure declaration includes:

* Reference to the merge commit SHA.
* Reference to the closure-verification doc.
* Confirmation of all 5 closure dimensions (mechanical, replay-authoritative, contamination-isolation, retained-state continuity, operator MP4 review where applicable — Layer D notes that Step 12 is a docs-only update and MP4 dimension may not apply; closure-verification doc adjudicates).
* Updated substrate posture (e.g., "deterministic interruption-aware orchestration substrate with codified live-ingress contract").

**Sub-finding 24.A.** Authoring completion is the operational analogue of constitutional freeze. The former is the Decision-Owner's declaration; the latter is the substrate state that warrants it. Both are required.

---

## §25. Pre-authoring admissibility

Step 12 normative authoring becomes ADMISSIBLE TO BEGIN when:

| criterion | source |
|---|---|
| All four transition-planning layers complete | Layer A + Layer B + Layer C + Layer D (this doc) |
| Step 11 codification plan + extraction plan unchanged since pre-authoring planning began | per memory: completed 2026-05-21; verified unchanged before BASELINE |
| Constitutional posture verified preserved across all transition-planning artifacts | per §25 of Layers A/B/C and §26 of this doc |
| Branch creation conditions satisfied | per §5 |
| Roles assigned per §10 (Author, Reviewer, Constitutional Reviewer, Decision-Owner) | operational decision by Decision-Owner |
| Decision-Owner authorizes Step 12 to begin | explicit decision |

**Layer D does NOT itself authorize Step 12 authoring to begin.** It specifies the conditions under which the Decision-Owner may evaluate admissibility. Authorization is a Decision-Owner action made at BASELINE.

**Sub-finding 25.A.** The four-layer transition-planning framework is now complete. The Decision-Owner may evaluate admissibility at any time. Until evaluated and authorized, Step 12 remains in the pre-authoring state with all four layers as the durable record of the safety overlay that will govern authoring when it begins.

---

## §26. Layer-D open questions (operational, deferred)

Layer D intentionally does NOT specify:

* Specific role assignments (Author = X, Reviewer = Y, etc.) — operational, Decision-Owner's choice at BASELINE.
* Authoring start date — Decision-Owner's choice.
* Tooling implementation for FF1–FF5 — implementation work at FINAL-FORM-VALIDATION time.
* Tooling implementation for audit-trace artifact generation — implementation work, can use git-trailers or sibling files.
* Notification mechanisms (alerts on AAU-ready-for-review, on wave-close, on escalation OPENED) — operational/implementation.
* CI integration (auto-running V18 on each AAU commit, etc.) — operational/implementation.
* The closure-verification doc's exact structure — to be authored at STEP-12-FROZEN time, modeled on `phase_4b_step11_closure_verification.md`.
* Runtime adoption of the new clauses — outside Step 12 scope; future work.

---

## §27. Layer-D vocabulary

Layer D introduces several governance-process terms; none enter the normative contract:

| term | meaning | scope |
|---|---|---|
| Codification branch | the single long-lived branch for Step 12 authoring | this planning doc |
| Wave-closure tag | the immutable git tag at WAVE-CLOSED | this planning doc |
| Pre-merge governance gate (G1–G8) | the 8 gates between PR-OPEN and MERGED | this planning doc |
| Final-form check (FF1–FF5) | the 5 governance-level aggregate checks | this planning doc |
| Constitutional review | the resolution venue for T3/T8 escalations | this planning doc |
| Constitutional freeze | the terminal substrate state for Step 12 | this planning doc |
| Authoring completion criteria | the Decision-Owner's declaration conditions | this planning doc |
| Role types (Author, Reviewer, Constitutional Reviewer, Decision-Owner) | role enumeration | this planning doc |

None receive clause IDs. Per "no namespace churn" — purely governance-process vocabulary.

---

## §28. Layer-D planning verdict

**LAYER D: READY.**

* End-to-end pipeline state machine specified (§2): 9 states, strict transitions.
* Wave-governance topology (§3): per-wave lifecycle with wave-closure tags.
* Cross-wave sequencing (§4): strict sequential; cross-wave invariants enforced by V19.
* Branch isolation strategy (§5): single long-lived branch; no rebase against master.
* PR boundary decision (§6): one final PR for all 29 AAUs; rationale captured.
* Replay-test invocation cadence (§7): 8 BLOCKING + 5 RECOMMENDED invocations of V18.
* Escalation-resolution topology (§8): per-trigger resolution paths; constitutional-review venue for T3/T8.
* Author/reviewer separation (§9): role-separation invariants.
* Role definitions (§10): 4 named roles; specific assignments operational.
* Multi-reviewer conflict protocol (§11): most-restrictive-wins; no majority vote.
* Final-form validation sequencing (§12): 5 BLOCKING checks (FF1–FF5).
* Pre-merge governance gates (§13): 8 BLOCKING gates (G1–G8).
* Post-wave freeze protocol (§14): no-amend extended cross-wave; immutable tags.
* Rollback governance discipline (§15): 3 scenarios, increasing severity.
* Re-authoring governance after REVISE (§16): 3-commit audit pattern preserved.
* Escalation lifecycle (§17): 4-state strict lifecycle.
* Governance invariants (§18): 5 governance-level invariants (operational, not constitutional).
* Merge admissibility protocol (§19): mechanical gates + single human confirmation.
* Branch-close conditions (§20): branch may be archived; not deleted.
* Final codification freeze (§21): no post-merge incremental fixes; next cycle requires full Layer-A-through-D.
* Governance auditability (§22): full audit trail enumerated.
* Constitutional freeze criteria (§23): binary mechanical verification.
* Authoring completion criteria (§24): Decision-Owner declaration; analogue of Step 8/9/10 closures.
* Pre-authoring admissibility (§25): four-layer framework now complete; Decision-Owner may evaluate.

The plan does NOT mutate any artifact. The plan does NOT author clause wording. The plan does NOT authorize Step 12 to begin. The plan IS the governance overlay that coordinates Layers A, B, and C into a constitutionally bounded end-to-end pipeline.

**This is the final transition-planning artifact.** The four-layer framework (A: mechanics, B: validation, C: review ergonomics, D: governance) is complete. Step 12 authoring admissibility may now be evaluated by the Decision-Owner.

---

## §29. Preserved invariants under Layer D

| invariant | Layer-D mechanism |
|---|---|
| replay-authoritative truth | V18 at 8 BLOCKING + 5 RECOMMENDED cadence (§7); FF1 at final-form (§12); re-run at constitutional-freeze verification (§23) |
| append-only causality | branch-linearity invariant (§18); no force-push, no rebase, no history rewrite (§5); revert is additive (§15, §16) |
| authority singularity | role-separation invariant (§18, §9); no role acquires authority over substrate clauses; Decision-Owner authority is operational, not constitutional (§10, §13 G8) |
| orchestration_tick supremacy | V18 catches any AAU that mutates a runtime-consumed string; cadence per §7 |
| deterministic interruption boundaries | V7 BLOCKING (Layer B) carried through into Layer D's FF aggregate; no Layer D bypass |
| Phase-A-only observability | same as above |
| contradiction preservation | V8 BLOCKING (Layer B) for D-FAULT-9c carried into FF3 completeness check (§12) |
| transport independence | V9 BLOCKING + FF4 aggregate framework/contract separation check (§12) |
| no hidden cleanup | branch-linearity + revert-is-additive (§15, §16); never history-rewriting; FF5 substrate-preservation check (§12) |
| no wall-clock authority | wave-closure tags are git tags (timeless from constitutional standpoint); audit-trace timestamp is descriptive not normative (per Layer C §19); no Layer D rule introduces wall-clock-derived authority |
| no adaptive semantics | constitutional-review (§8.1) decisions cannot widen scope; T4 (fresh constitutional principle) triggers Step 11 re-opening, not in-stream adaptation |
| framework/contract separation | V9 BLOCKING carried through; FF4 aggregate check at final-form (§12) |
| additive-only mutation discipline | Properties A1–A3 / S1–S3 from Layer A carried through; FF5 substrate-preservation check confirms cross-AAU additive-only at branch level |
| replay-preserving extraction safety | V18 + V19 at 8 BLOCKING cadence; FF1 + FF2 at final-form; verified at constitutional freeze |
| validator supremacy over reviewer intuition | constitutional-review (§8.1) decisions cannot override BLOCKING validators (would be T4 escalation back); no Layer D mechanism grants reviewer or Constitutional Reviewer authority over Layer B mechanical results |
| no semantic widening authority | T4 trigger isolates "fresh constitutional principle" detection; halts Step 12 and requires Step 11 re-opening; no Layer D in-stream widening pathway |
| no reviewer discretionary reinterpretation | multi-reviewer most-restrictive-wins (§11) preserves Layer C's no-discretionary-reinterpretation; constitutional review (§8.1) bound to specific escalation, not general principle |
| no hidden override pathways | all overrides are explicit: per-AAU revert (Layer A §13), wave-internal post-close revert (constitutional-reviewer approval per §15), cross-wave revert (Step 11 re-opening); no shortcut paths |
| no authority redistribution | Layer D names 4 role types; specific assignments operational; no Layer D mechanism elevates any role's authority above Layer A/B/C bounds |
| WAVE-ATOMICITY (new) | §18; state machine §2 enforces; master never observes partial wave |
| BRANCH-LINEARITY (new) | §18; §5; no rebase, no force-push; reverts are explicit commits |
| MERGE-ATOMICITY (new) | §18; §19; one merge to master; Step 12 appears atomically |
| AUDIT-COMPLETENESS (new) | §18; §22; every decision recorded in audit trace; immutable |
| ROLE-SEPARATION (new) | §18; §9; Author ≠ Reviewer; Constitutional Reviewer ≠ both |

All 19 inherited invariants preserved. 5 governance-level invariants added (operational, not constitutional).

---

## §30. The four-layer framework: completion summary

The four pre-authoring transition-planning layers are now in place:

| layer | doc | scope | invariants |
|---|---|---|---|
| **A** | [authoring mechanics](phase_4b_step12_authoring_mechanics_plan.md) | physical insertion act per AAU | additive-only Properties A1–A3 / S1–S3 |
| **B** | [validation](phase_4b_step12_validation_plan.md) | per-clause + per-AAU + per-wave validators | 17 BLOCKING + 3 SOFT validators across 4 stages |
| **C** | [review ergonomics](phase_4b_step12_review_ergonomics_plan.md) | bounded reviewer workflow | validator supremacy; 3-option decision surface; immutable audit trace |
| **D** | this doc | cross-clause governance | wave-atomicity; branch-linearity; merge-atomicity; audit-completeness; role-separation |

Together: 4 layers, ~2400 lines of planning documentation, 19 preserved constitutional invariants, 5 new governance invariants, zero clause text authored, zero contract modifications.

The four-layer framework constitutes the complete pre-authoring safety overlay for Step 12. Authoring admissibility may now be evaluated by the Decision-Owner per §25.

---

**End of Step 12 Layer D cross-clause-governance plan.**

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance](phase_4b_step11_f59_manual_advance_analysis.md), [closure verification](phase_4b_step11_closure_verification.md), [codification plan](phase_4b_step11_codification_plan.md), [meta-audit](phase_4b_step11_meta_audit.md), [extraction plan](phase_4b_step11_extraction_plan.md), [Layer A authoring mechanics](phase_4b_step12_authoring_mechanics_plan.md), [Layer B per-clause validation](phase_4b_step12_validation_plan.md), [Layer C review ergonomics](phase_4b_step12_review_ergonomics_plan.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).

Successors: Step 12 BASELINE (if and when the Decision-Owner authorizes authoring per §25); ultimately, post-Step-12 substrate at STEP-12-FROZEN per §21.
