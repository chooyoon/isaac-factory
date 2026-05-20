# Phase 4B Step 12 — Lineage Normalization Plan Amendment Patchset (A1–A4)

**Status: PRE-AMENDMENT PATCHSET DESIGN (2026-05-21).** Designs the exact additive amendment patchset that updates [`phase_4b_step12_lineage_normalization_plan.md`](phase_4b_step12_lineage_normalization_plan.md) from the SAFETY-CRITICAL Option C runtime guidance to the operationally-safe Option F guidance, per the dry-run review's [§27 required amendments](phase_4b_step12_lineage_dry_run_review.md). Provides verbatim text for each amendment (A1–A4) + exact insertion locations + additive-only verification + per-invariant compatibility audit.

Does **not** apply the amendments. Does **not** execute commits. Does **not** mutate the contract document. Does **not** create branches. Does **not** author clauses. The deliverable is the patchset specification; application is a Decision-Owner operation.

This plan is itself an additive document — a sibling to the lineage normalization plan, not a modification of it.

---

## §1. Scope and method

The amendment plan proceeds in five passes:

1. **Inheritance** — accept the dry-run review's hazard analysis + amendment requirements as inputs.
2. **Verbatim amendment authoring** — provide complete A1–A4 text ready for append to the lineage plan.
3. **Additive-only verification** — confirm the patchset adds only new sections; deletes nothing.
4. **Compatibility audit** — verify amendments preserve constitutional framework + four-layer plans + admissibility verdict + baseline-init + execution-readiness review + 24 invariants.
5. **Verdict** — AMENDMENT-NOT-ADMISSIBLE / AMENDMENT-CONDITIONALLY-ADMISSIBLE / AMENDMENT-ADMISSIBLE.

---

## §2. Inheritance

| inherited from | element |
|---|---|
| Dry-run review §5–§13 | 8-hazard catalog; H2 and H5 SAFETY-CRITICAL Option-C-specific |
| Dry-run review §27 | required amendments A1–A4 specifications + rationale |
| Dry-run review §28 | mitigation cross-reference M1–M10 |
| Lineage normalization plan §11.4 + §12.5 | superseded recommendation (Option C for runtime) |
| Lineage normalization plan §18 | commit-message convention (supplemented by A2) |
| Lineage normalization plan §8 + §9 | W3/W4 protocols (supplemented by A3) |
| Lineage normalization plan §10 | per-wave landing protocol (supplemented by A4) |
| Lineage normalization plan §32 | (last section; A1–A4 append after this) |
| All four-layer pre-authoring plans + admissibility evaluation + baseline-init + readiness review | constitutional bounds the amendments must respect |

This plan introduces no new framework concept. It only refines operational guidance within the lineage normalization plan's existing scope.

---

## §3. Amendment design philosophy: additive supersession

The amendments use **additive supersession** rather than in-place modification:

* The existing lineage plan §§1–§32 remain byte-identical after amendment application.
* The amendments are appended as NEW sections §A1–§A4 at the end of the lineage plan.
* Each amendment explicitly cites the section it supersedes or supplements.
* Future readers of the lineage plan see BOTH the original §11.4 (Option C recommendation) and the §A1 amendment (Option F adoption); the evolution is auditable.

**Why additive supersession.**

* Preserves the original recommendation's text for audit (e.g., "why did the plan originally suggest Option C? — read §11.4; why was it amended? — read §A1's rationale citing dry-run review").
* Compatible with the project's append-only-causality discipline at the documentation level (mirrors the discipline at the runtime/contract level).
* Mirrors Layer C §19's audit-trace pattern: corrections via supersession artifacts, not in-place modification.
* No hidden cleanup (per "no hidden cleanup" preserved invariant).

**Operational pattern.**

```
[lineage plan §§1–§32 unchanged]
---
[NEW: §A1 amendment]
[NEW: §A2 amendment]
[NEW: §A3 amendment]
[NEW: §A4 amendment]
```

---

## §4. Amendment A1 — Adopt Option F for runtime (supersedes §11.4 + §12.5 runtime recommendation)

### §4.1 A1 insertion location

* **Position in lineage plan**: appended as new section §A1, immediately after §32 (the current end-of-plan section).
* **Supersedes**: lineage plan §11.4 recommendation (recommended Option C for contract) + §12.5 recommendation (recommended matching Option C for runtime).
* **Supersession scope**: contract decomposition recommendation in §11.4 is UNCHANGED (Option C remains tractable for contract); runtime decomposition recommendation in §12.5 is SUPERSEDED (Option C → Option F for runtime).

### §4.2 A1 verbatim insertion text

```markdown
## §A1. AMENDMENT — Option F adoption for runtime decomposition (supersedes §12.5 runtime recommendation; supplements §11.4 contract recommendation)

**Status: AMENDMENT POST-DRY-RUN-REVIEW (2026-05-21).** Per [`phase_4b_step12_lineage_dry_run_review.md`](phase_4b_step12_lineage_dry_run_review.md) §27 + §7 (hazards H2 + H5, both SAFETY-CRITICAL under Option C), this amendment supersedes §12.5's "match the contract option" recommendation and adopts **Option F (hybrid)** for the W1/W2 landing of Step 9 + Step 10 work.

### §A1.1 Option F definition

**Option F = per-Step contract decomposition + combined-runtime W2 commit.**

* **W1 stages**: Step 9 contract additions (per Option C contract decomposition per §11.3 + §11.4) + Step 9 docs + Step 9 tests + Step 9 launchers + Step 9-attributed scripts. **NO runtime files staged at W1.**
* **W2 stages**: ALL runtime files (combined Step 9 + Step 10 runtime as full-file staging) + Step 10 contract additions (per Option C contract decomposition) + Step 10 docs + Step 10 tests + Step 10 launchers + Step 10-attributed scripts + `envelopes.py`.

### §A1.2 Rationale (per dry-run review §7 + §17)

* **Contract decomposition (Option C) remains tractable**: clauses are well-named (D-FAULT-1..-14 for Step 9; D-EXEC-13 family + D-FAULT-1b + D-FAULT-3b + D-FAULT-12c for Step 10). Identification by clause name + section heading takes ~30 minutes of focused work.
* **Runtime decomposition (Option C) is SAFETY-CRITICAL**: `session.py` alone has 943 changed lines with Step 9 (D-FAULT machinery) and Step 10 (D-EXEC-13 machinery) intermixed within methods. Per-line attribution requires deep code knowledge. Mis-attribution can produce silent false-PASS V18 + test results (dry-run review §7 + §10).
* **Combined runtime in W2 (Option F)** eliminates the mis-attribution risk surface entirely. The runtime lands atomically; either it produces the validated Step 10 baseline (V18 PASS) or it does not.

### §A1.3 W1-to-W2 inconsistency window

Under Option F, the post-W1 master state has:

* Contract documenting Step 9 D-FAULT clauses.
* Runtime: pre-Step-9 (i.e., Step 8 closure runtime).

This is a "contract-ahead-of-runtime" inconsistency window. It is acceptable because:

* The window is typically minutes if W1 and W2 are executed in immediate succession.
* The runtime is documentation in the contract sense, not executed by the contract. Tests still pass against the Step 8 runtime (the Step 9 contract additions describe behavior that the runtime doesn't yet implement, but no test fails due to clauses being "documented but not implemented").
* The window closes at W2 commit; post-W2 master has contract + runtime consistent at Step 10 closure form.

If for operational reasons the window is expected to exceed an hour, the Decision-Owner should weigh:

* Acceptable: continue with Option F as documented.
* Unacceptable: collapse to Option B (single combined W1+W2 commit; loses per-Step contract granularity but eliminates the window).

### §A1.4 Effect on lineage plan §11 + §12

* **§11.4 contract recommendation**: UNCHANGED. Option C for contract remains tractable and recommended.
* **§12.5 runtime recommendation**: SUPERSEDED. The original guidance ("match the contract option") is replaced by §A1.1's Option F specification for runtime.
* **§7 W2 protocol**: updated by §A1.1's W2 staging list (combined Step 9 + Step 10 runtime instead of Step 10 runtime delta only).
* **§6 W1 protocol**: updated by §A1.1's W1 staging list (NO runtime files at W1; runtime deferred to W2).

### §A1.5 Compatibility note

This amendment does not alter any constitutional invariant, validator, governance layer, or framework artifact. It refines W1/W2 operational guidance only. All 24 preserved invariants remain preserved (per per-amendment compatibility audit in `phase_4b_step12_lineage_amendment_plan.md` §18).
```

### §4.3 A1 length estimate

~80 lines of verbatim insertion text.

---

## §5. Amendment A2 — Per-wave commit-message templates (supplements §18)

### §5.1 A2 insertion location

* **Position in lineage plan**: appended as new section §A2, immediately after §A1.
* **Supplements**: lineage plan §18 commit-message convention.
* **Supersession scope**: §18's generic "follow Step 8 precedent" guidance is UNCHANGED; A2 adds specific templates for W1/W2 under Option F including in-place modification enumeration (M1 + M3).

### §5.2 A2 verbatim insertion text

```markdown
## §A2. AMENDMENT — Per-wave commit-message templates under Option F (supplements §18)

**Status: AMENDMENT POST-DRY-RUN-REVIEW (2026-05-21).** Per `phase_4b_step12_lineage_dry_run_review.md` §27 mitigations M1, M3, M4, this amendment provides verbatim commit-message templates for W1, W2, W3, W4 under §A1's Option F adoption.

### §A2.1 W1 commit message template (under Option F)

```
Phase 4B Step 9 — D-FAULT deterministic failure semantics contract additions + docs + tests (STEP 9 CLOSURE, contract+docs landing)

This commit lands Step 9 closure CONTRACT + DOCS + TESTS only. Runtime is deferred to W2 per Option F (see `phase_4b_step12_lineage_amendment_plan.md` §A1).

Contract additions (`docs/phase_4b_deterministic_semantics.md`):
- §13 D-FAULT contract: D-FAULT-1 through D-FAULT-14 introductions
- §13.17 D-FAULT-15 forbidden patterns: rows 1–18
- D-FAULT failure-class taxonomy + D-FAULT-9 OperatorEnvelope schema
- D-FAULT-1a inner sub-classification

In-place contract modifications (NOT pure additions; explicit enumeration per
`phase_4b_step12_lineage_dry_run_review.md` §6, §8):
- §11 open-extension item 4 text updated: from "Phase 4B step 9 will surface and pin this" to "Pinned in §13 D-FAULT (D-FAULT-3, D-FAULT-3a, D-FAULT-4, D-FAULT-7)..."
- Authoritative-set list (§5.X) expanded to include `_retry_counts` + `_node_runtime`
- Non-goal text re retry semantics refined to reflect post-Step-9 state

Tests landed:
- isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step9_p4_fault_contract.py (new)
- isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step9_p7_replay_comparator.py (new)
- isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step8_p6_replay_identity.py (refined for Step 9 P6 closure)

Scripts landed:
- scripts/launch_phase_5_two_node.py (Step 9 P5 two-node runtime launcher)
- scripts/launch_phase_9p6_step9_abort.py (Step 9 P6 abort launcher)

Docs landed:
- docs/phase_4b_step9_failure_semantics_analysis.md

Runtime: DEFERRED to W2. Post-W1 master runtime = Step 8 closure runtime. Contract-ahead-of-runtime inconsistency window per §A1.3.

V18: not invoked at W1 under Option F (runtime unchanged from Step 8 closure).

Closure-proof reference: `project_phase_4b_step9.md` memory entry.
```

### §A2.2 W2 commit message template (under Option F)

```
Phase 4B Step 9 + Step 10 Direction A — combined runtime + Step 10 contract + Step 10 docs + tests (STEP 10 DIRECTION A CLOSURE, runtime+Step-10-contract landing)

This commit lands ALL post-Step-8 runtime (combined Step 9 + Step 10) + Step 10 contract additions + Step 10 docs + Step 10 tests + Step 10 scripts. Per Option F (§A1), Step 9 runtime is deferred from W1 to here.

Runtime landed (all files; full-file staging):
- isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/__init__.py (+33 lines)
- isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/graph.py (+42/-X)
- isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py (+943/-X) — structural summary:
  * D-FAULT failure-emission infrastructure per Step 9
  * abort propagation per D-FAULT-3
  * D-EXEC-13 predicate-consultation infrastructure per Step 10
  * EXECUTION_INTERRUPTED outcome handling per D-FAULT-1b
- isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/snapshot.py (+12/-X)
- isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/envelopes.py (NEW — OperatorEnvelope per D-FAULT-9)
- isaac_factory/extensions/cell_authoring/cell_authoring/tasks/definitions.py (+61/-X) — TaskDefinition.tick_budget_ticks per D-FAULT-12
- isaac_factory/extensions/cell_authoring/cell_authoring/tasks/executor.py (+232/-X) — D-EXEC-13 predicate consultation
- tools/check_session_replay_identity.py (+371/-X) — Step 9 P7 comparator extensions

Step 10 contract additions (`docs/phase_4b_deterministic_semantics.md`):
- NEW §1.5 Sub-Phase-E interruption surface
- D-EXEC-13 + D-EXEC-13a + D-EXEC-13b + D-EXEC-13c + D-EXEC-13d
- D-FAULT-1b — Executor-reported interruption sub-classifier
- D-FAULT-3b — Session classification of EXECUTION_INTERRUPTED
- D-FAULT-12c — ticks_consumed authority
- §13.17 D-FAULT-15 rows 19–30

In-place contract modifications (NOT pure additions; explicit per §A2):
- §1.5 Non-goals → §1.6 Non-goals (renumbering due to insertion of new §1.5 Sub-Phase-E interruption surface). Pre-Step-10 §1.5 content preserved verbatim at §1.6 position.

Tests landed:
- isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step10_p3_direction_a_contract.py (new)

Scripts landed:
- scripts/launch_phase_10_p6_isaac.py (Step 10 P6 launcher)
- scripts/diag_stream_minimal.py (diagnostic)
- scripts/diag_stream_smoke.py (diagnostic)

Docs landed:
- docs/phase_4b_step10_candidates_analysis.md
- docs/phase_4b_step10_direction_a_analysis.md
- docs/phase_4b_step10_p6_isaac_acceptance.md

V18: post-commit verification REQUIRED; MUST PASS against validated Step 10 baseline (12/12 cycles bytewise replay-identical under --reopen-stage-between-cycles). FAILURE halts normalization; investigate per dry-run review §22.

Closure-proof reference: `project_phase_4b_step10.md` memory entry.
```

### §A2.3 W3 commit message template

```
docs: Phase 4B Step 11 — live ingress analytical pipeline (STEP 11 PLANNING COMPLETE, 8 framework artifacts)

This commit lands the Step 11 analytical pipeline as docs-only. No runtime, no contract, no tests.

Docs landed (8 files, all under `docs/phase_4b_step11_*.md`):
- phase_4b_step11_live_ingress_analysis.md (compatibility-boundary investigation)
- phase_4b_step11_admissibility_framework.md (T1-T9, L1-L4, D1-D9, 6-object ontology)
- phase_4b_step11_f58_paused_analysis.md (F58 PAUSED admissibility)
- phase_4b_step11_f59_manual_advance_analysis.md (F59 manual_advance inadmissibility)
- phase_4b_step11_closure_verification.md (framework closure verified)
- phase_4b_step11_codification_plan.md (codification topology + 6-phase ordering)
- phase_4b_step11_meta_audit.md (meta-constitutional self-consistency audit)
- phase_4b_step11_extraction_plan.md (38 atomic insertions across 6 waves)

Closure-proof reference: `project_phase_4b_step11.md` memory entry.

V18: not invoked (no runtime/contract change).
```

### §A2.4 W4 commit message template

```
docs: Phase 4B Step 12 — pre-authoring transition planning framework + amendment plan (STEP 12 PLANNING COMPLETE)

This commit lands the Step 12 pre-authoring framework as docs-only. No runtime, no contract, no tests, no AAUs.

Docs landed (all `docs/phase_4b_step12_*.md` files present at execution time; glob-staged per §A3):
- phase_4b_step12_authoring_mechanics_plan.md (Layer A)
- phase_4b_step12_validation_plan.md (Layer B)
- phase_4b_step12_review_ergonomics_plan.md (Layer C)
- phase_4b_step12_governance_plan.md (Layer D)
- phase_4b_step12_admissibility_evaluation.md (verdict: AUTHORING-ADMISSIBLE)
- phase_4b_step12_baseline_initialization_plan.md (S0–S8 bootstrap pathway)
- phase_4b_step12_execution_readiness_review.md (verdict: EXECUTION-CONDITIONALLY-READY; B1 identified)
- phase_4b_step12_lineage_normalization_plan.md (4-wave B1 closure pathway)
- phase_4b_step12_lineage_dry_run_review.md (verdict: DRY-RUN-CONDITIONALLY-SAFE)
- phase_4b_step12_lineage_amendment_plan.md (A1–A4 amendment patchset)

Closure-proof references: `project_phase_4b_step12_*.md` memory entries.

V18: not invoked (no runtime/contract change).

This is the FINAL landing wave. Post-W4 master HEAD = "post-everything substrate" ready for bootstrap S0 per `phase_4b_step12_baseline_initialization_plan.md` §4.
```

### §A2.5 Effect on lineage plan §18

§18's generic guidance is UNCHANGED. The specific templates above operationalize it for Option F execution.
```

### §5.3 A2 length estimate

~120 lines of verbatim insertion text (longest of the four amendments due to verbatim templates).

---

## §6. Amendment A3 — Glob-based W3/W4 staging (supplements §8 + §9)

### §6.1 A3 insertion location

* **Position in lineage plan**: appended as new section §A3, immediately after §A2.
* **Supplements**: lineage plan §8 (W3 protocol) + §9 (W4 protocol).

### §6.2 A3 verbatim insertion text

```markdown
## §A3. AMENDMENT — Glob-based W3/W4 staging (supplements §8 + §9)

**Status: AMENDMENT POST-DRY-RUN-REVIEW (2026-05-21).** Per `phase_4b_step12_lineage_dry_run_review.md` §11 (H6 untracked file accumulation), this amendment specifies glob-based staging for W3 and W4 to ensure robustness against doc-list drift between plan-authoring and execution.

### §A3.1 W3 staging command

Replace the §8 implicit "stage 8 specific docs" with explicit glob-based staging:

```
git add docs/phase_4b_step11_*.md
```

This command stages ALL files matching the pattern at execution time. If additional Step 11 docs are authored between this amendment's authoring and W3 execution (e.g., a Step 11 supplementary note added later), they are captured automatically.

**Pre-commit verification:**

```
git diff --cached --stat | grep "docs/phase_4b_step11_"
```

Confirms exactly the matched files are staged; no other paths.

### §A3.2 W4 staging command

Replace the §9 implicit "stage 8 specific docs" with:

```
git add docs/phase_4b_step12_*.md
```

This command stages ALL files matching the pattern at execution time. This is REQUIRED because:

* The lineage normalization plan's §5.4 was authored when 8 Step 12 docs existed.
* The lineage normalization plan itself (`phase_4b_step12_lineage_normalization_plan.md`) is the 9th.
* The dry-run review (`phase_4b_step12_lineage_dry_run_review.md`) is the 10th.
* This amendment plan (`phase_4b_step12_lineage_amendment_plan.md`) is the 11th.
* Future Step 12 planning sessions may add more before execution.

Glob-based staging is robust against this drift.

**Pre-commit verification:**

```
git diff --cached --stat | grep "docs/phase_4b_step12_"
```

### §A3.3 Wave attribution invariant

This amendment does NOT change wave attribution semantics:

* All `docs/phase_4b_step11_*.md` → W3.
* All `docs/phase_4b_step12_*.md` → W4.
* All other docs → not in W3/W4 scope (require separate attribution per §5).

If a new doc namespace emerges (e.g., `docs/phase_4b_step13_*.md`), it would NOT be captured by W3/W4 globs and would require its own wave or attribution decision.

### §A3.4 Effect on lineage plan §8 + §9

§8 + §9 implicit file enumeration is UNCHANGED; §A3 adds the operational glob command + verification. Future readers see both: §8 enumerates 8 docs; §A3 specifies "glob-stage all matching files at execution time."
```

### §6.3 A3 length estimate

~45 lines of verbatim insertion text.

---

## §7. Amendment A4 — Pre-execution dry-run protocols (supplements §10)

### §7.1 A4 insertion location

* **Position in lineage plan**: appended as new section §A4, immediately after §A3.
* **Supplements**: lineage plan §10 (per-wave landing protocol).

### §7.2 A4 verbatim insertion text

```markdown
## §A4. AMENDMENT — Pre-execution dry-run protocols (supplements §10)

**Status: AMENDMENT POST-DRY-RUN-REVIEW (2026-05-21).** Per `phase_4b_step12_lineage_dry_run_review.md` §27 mitigations M9 + M10, this amendment adds pre-execution dry-run stages to §10's per-wave landing protocol.

### §A4.1 M9 — Pre-W1 contract staging dry-run (RECOMMENDED)

Before executing W1 (per §6 of lineage plan + §A1.1's Option F W1 staging list), Decision-Owner should perform a non-committing preview of the W1 contract staging:

```
# Stage Step 9 contract additions via -p (interactive hunk-by-hunk)
git add -p docs/phase_4b_deterministic_semantics.md

# Capture planned W1 contract diff (without committing)
git diff --cached docs/phase_4b_deterministic_semantics.md > /tmp/w1-contract-planned.diff

# Reset stage (no commit; working tree preserved)
git restore --staged docs/phase_4b_deterministic_semantics.md
```

Decision-Owner reviews `/tmp/w1-contract-planned.diff` against expected Step 9 content:

* D-FAULT-1 through D-FAULT-14 clause definitions in §13.
* D-FAULT-15 rows 1–18 in §13.17.
* §11 item 4 in-place modification (per A2 W1 message template).
* Authoritative-set list expansion (per A2 W1 message template).
* Retry-semantics text refinement (per A2 W1 message template).
* NO D-EXEC-13 family content (Step 10).
* NO D-FAULT-1b / -3b / -12c content (Step 10).
* NO §1.5 → §1.6 renumbering content (Step 10).

If the planned diff matches expectations: repeat the staging at execution time and commit.
If the planned diff does NOT match: re-derive the per-hunk attribution; re-run the dry-run; do not commit until match.

### §A4.2 M10 — Pre-execution V18 against working tree (RECOMMENDED)

Before executing any wave commit, Decision-Owner should run V18 against the current working-tree state to confirm baseline-tooling sanity:

```
# Run V18 against the working-tree (NOT against any commit)
python tools/check_session_replay_identity.py [args per existing invocation convention]
```

Expected result: PASS against the validated Step 10 baseline events.jsonl SHA-256 (per Step 10 Direction A's "12/12 cycles bytewise replay-identical under --reopen-stage-between-cycles").

If PRE-EXECUTION V18 PASSes:
* The replay-tool + working-tree runtime + baseline reference are all aligned.
* W2 post-commit V18 (per §7 of lineage plan + §A1.1's W2 V18 BLOCKING requirement) should also PASS, since post-W2 master will be byte-identical to working tree at the runtime level (under Option F full-file runtime staging).

If PRE-EXECUTION V18 FAILs:
* The baseline reference itself is in question; investigate root cause BEFORE any wave commit.
* Possible causes: replay-tool regression since baseline establishment; runtime drift since baseline establishment; baseline drift due to external substrate change.
* HALT normalization; resolve before proceeding.

### §A4.3 Per-wave landing protocol integration (supplements §10)

The §10 per-wave landing protocol's "Stage 1: Verify preconditions" expands under this amendment:

```
Stage 1a (per-wave): Verify prior wave complete; working-tree state as expected
Stage 1b (W1 only):  Run M9 pre-W1 contract staging dry-run
Stage 1c (W1 only):  Run M10 pre-execution V18 against working tree
Stage 2-6 (per §10): unchanged
```

Stages 1b + 1c are RECOMMENDED but not BLOCKING. Their value is preventing operational errors before commit-time discovery.

### §A4.4 Effect on lineage plan §10

§10 stages 1-6 remain UNCHANGED in scope. §A4.3 ADDS sub-stages 1b + 1c as recommended additions to stage 1. The original stage 1 ("verify preconditions") expands to include the pre-execution dry-runs.
```

### §7.3 A4 length estimate

~60 lines of verbatim insertion text.

---

## §8. Aggregate amendment size

| amendment | lines | scope |
|---|---|---|
| A1 (Option F adoption) | ~80 | supersedes §12.5 runtime guidance |
| A2 (commit-message templates) | ~120 | supplements §18; verbatim templates for W1/W2/W3/W4 |
| A3 (glob-based staging) | ~45 | supplements §8 + §9 |
| A4 (pre-execution dry-runs) | ~60 | supplements §10 |
| **Total** | **~305 lines** | **appended to lineage plan §32** |

Pre-amendment lineage plan: 762 lines. Post-amendment lineage plan: ~1,067 lines (305 lines additive, zero lines deleted).

---

## §9. Amendment-as-patch dry-run

**Operation:** append §A1, §A2, §A3, §A4 (in that order) to the end of `docs/phase_4b_step12_lineage_normalization_plan.md`, preserving all prior content byte-identically.

**Pre-amendment state:**
* Lineage plan exists in working tree (untracked).
* Length: 762 lines.
* Last section: §32 "Coordination with readiness-review refinements".

**Post-amendment state (if amendments applied):**
* Lineage plan length: ~1,067 lines.
* Last section: §A4 (continued from §32 in section order).
* §32 unchanged byte-identically.
* §§1–§31 unchanged byte-identically.

**Verification (post-application by Decision-Owner):**
* `wc -l docs/phase_4b_step12_lineage_normalization_plan.md` returns ~1,067.
* `grep '^## §32' docs/phase_4b_step12_lineage_normalization_plan.md` returns one match (§32 unchanged).
* `grep '^## §A' docs/phase_4b_step12_lineage_normalization_plan.md` returns 4 matches (§A1, §A2, §A3, §A4).
* `head -<n-of-original-end> docs/phase_4b_step12_lineage_normalization_plan.md` byte-equal to pre-amendment file content.

---

## §10. Additive-only verification (Properties A1–A3 analogues)

Each amendment is analyzed against documentation analogues of Layer A's Properties A1–A3:

| property | applies to | satisfied? |
|---|---|---|
| **Line preservation** — every pre-existing line in the lineage plan appears verbatim at the same or later position in the amended file | A1+A2+A3+A4 (each individually + aggregate) | ✓ |
| **Character superset** — pre-existing characters preserved in amended file | A1+A2+A3+A4 | ✓ |
| **Diff shape** — `git diff <pre-amendment> <post-amendment>` would show only `+` lines and zero `-` lines | A1+A2+A3+A4 | ✓ |

**Sub-finding 10.A.** All four amendments satisfy the additive-only discipline at the documentation level. Application produces a pure-additive diff against the pre-amendment lineage plan.

---

## §11. Non-semantic verification

The amendments alter no substrate semantics:

| check | result |
|---|---|
| New validators introduced? | NO (V1–V20 + FF1–FF5 unchanged) |
| New governance layers? | NO (Layers A/B/C/D unchanged) |
| New constitutional principles? | NO (no new theorems, lemmas, disciplines, or invariants) |
| New clause-IDs? | NO (zero clauses authored) |
| New escalation triggers? | NO (T1–T8 unchanged) |
| New role types? | NO (Author/Reviewer/Constitutional Reviewer/Decision-Owner unchanged) |
| Validator scope changes? | NO |
| Reviewer authority changes? | NO |
| Contract content changes? | NO (zero contract mutations) |
| Runtime content changes? | NO (zero runtime mutations) |
| Test content changes? | NO |

**Sub-finding 11.A.** The amendments are purely operational refinements to W1/W2/W3/W4 landing guidance. No semantic content is altered.

---

## §12. No-authority-redistribution verification

* **Decision-Owner authority**: unchanged. Decision-Owner still authorizes (S0), still confirms G8, still attests at S7. Amendments do not give Decision-Owner new powers.
* **Author authority**: unchanged. Authors still author AAUs per Layer A; amendments are pre-bootstrap and have no AAU implications.
* **Reviewer authority**: unchanged. Reviewers still operate per Layer C §16's 12 MUST-NOTs; amendments don't expand reviewer scope.
* **Constitutional Reviewer authority**: unchanged. Constitutional Reviewer still operates per Layer D §8.1; amendments don't expand scope.
* **Layer-B-implementing-agent authority**: unchanged. Validator mechanization scope per S4 unchanged.

**Sub-finding 12.A.** No role acquires new authority. No role's authority widens. ROLE-SEPARATION invariant preserved.

---

## §13. No-governance-layer-expansion verification

* Layer A (mutation mechanics): unchanged.
* Layer B (per-clause validation): unchanged.
* Layer C (bounded reviewer workflow): unchanged.
* Layer D (cross-clause governance): unchanged.
* No fifth layer introduced.
* No new pipeline states (BASELINE / WAVE-IN-PROGRESS / WAVE-PAUSED-ESCALATION / WAVE-CLOSED / ALL-WAVES-CLOSED / FINAL-FORM-VALIDATION / PR-OPEN-FOR-MERGE / MERGED-TO-MASTER / STEP-12-FROZEN per Layer D §2 — unchanged).
* No new pre-merge gates (G1–G8 unchanged).
* No new final-form checks (FF1–FF5 unchanged).

**Sub-finding 13.A.** No governance-layer expansion. The amendments operate within the existing operational + governance structure.

---

## §14. No-reviewer-authority-expansion verification

* Layer C §16's 12 MUST-NOTs: unchanged.
* Layer C §17's anti-drift rules: unchanged.
* Layer C §18's validator-to-reviewer one-way boundary: unchanged.
* Layer D §11's most-restrictive-wins for multi-reviewer: unchanged.

**Sub-finding 14.A.** Reviewer's bounded role is preserved. Amendments do not introduce reviewer discretion or override paths.

---

## §15. Compatibility with admissibility evaluation

The admissibility evaluation's 15 sufficiency criteria are checked against amended lineage plan:

| criterion | unchanged-by-amendments? |
|---|---|
| C1 Transition-layer completeness | ✓ (Layers A/B/C/D unchanged) |
| C2 Inter-layer dependency closure | ✓ (deferrals + closures unchanged) |
| C3 Invariant-coverage (24) | ✓ (per §18 below) |
| C4 Validator-governance consistency | ✓ (V/FF/G unchanged) |
| C5 Replay-preservation sufficiency | ✓ (V18 cadence unchanged in baseline-init; amendments operate on pre-bootstrap normalization, not on bootstrap) |
| C6 Escalation-topology sufficiency | ✓ (T1–T8 unchanged) |
| C7 Merge/freeze sufficiency | ✓ (G1–G8 unchanged; §21 freeze unchanged) |
| C8 Reviewer-boundary sufficiency | ✓ (§14 above) |
| C9 Additive-only enforcement sufficiency | ✓ (Properties A1–A3/S1–S3 unchanged; amendments themselves additive at docs level) |
| C10 Constitutional-freeze sufficiency | ✓ (§23 criteria unchanged) |
| C11 Audit-completeness sufficiency | ✓ (audit-trace mechanisms unchanged; amendments add more audit content) |
| C12 AAU-governance completeness | ✓ (per-AAU lifecycle unchanged) |
| C13 Branch-linearity sufficiency | ✓ (no rebase/force-push/amend rules unchanged) |
| C14 Residual ambiguity inventory | ✓ (amendments REDUCE ambiguity by being more explicit) |
| C15 Residual semantic-widening risk | ✓ (amendments don't introduce widening; M2 prevents safety-critical hazard) |

**Sub-finding 15.A.** AUTHORING-ADMISSIBLE verdict UNCHANGED by amendments. Admissibility evaluation does not need to be re-issued.

---

## §16. Compatibility with baseline-init plan

The baseline-init plan's S0–S8 stages are checked against amended lineage plan:

* S0 (Decision-Owner authorization): unchanged — Decision-Owner authorizes after B1 closure (per §A1+§A2+§A3+§A4 amended lineage normalization).
* S1 (codification branch initialization): unchanged — branch base = post-W4 master HEAD (per amended §28 verification still applies).
* S2 (substrate baseline capture): unchanged.
* S3 (audit-trace infrastructure): unchanged.
* S4 (validator mechanization): unchanged.
* S5 (role activation): unchanged.
* S6 (environment freeze): unchanged.
* S7 (BASELINE attestation): unchanged.
* S8 (AAU-0 readiness gate; 14-point checklist): unchanged.

**Sub-finding 16.A.** Baseline-init plan does not need re-issuing. The amendments operate in pre-bootstrap territory; bootstrap itself is unchanged.

---

## §17. Compatibility with execution-readiness review

| readiness dimension | unchanged-by-amendments? |
|---|---|
| Dependency integrity | ✓ |
| Operational deadlock | ✓ |
| Validator circularity | ✓ |
| Branch-bootstrap safety | ✓ (still conditional on B1 closure; B1 closure pathway now via Option F per amendments) |
| Audit lifecycle | ✓ |
| S8 gate completeness | ✓ (R1 refinement still applies; orthogonal to amendments) |
| Wave-1 activation | ✓ |
| Rollback sufficiency | ✓ |
| Role scalability | ✓ (R2 refinement still applies) |
| Validator maintenance | ✓ |
| Audit volume | ✓ (amendments add ~305 lines of audit content to lineage plan; manageable) |
| Governance complexity | ✓ |
| Branch linearity feasibility | ✓ |
| Replay baseline durability | ✓ (R3 refinement still applies) |
| Long-running stability | ✓ |
| AAU throughput | ✓ |
| Escalation frequency | ✓ |
| Infrastructure-commit boundary | ✓ (R4 refinement still applies) |
| Operational fatigue | ✓ |
| Constitutional survivability | ✓ |

Plus the explicit hazard handling:
* H2 + H5 SAFETY-CRITICAL → MITIGATED by A1 (Option F adoption).
* H1 + H3 in-place modification → MITIGATED by A2 (commit-message templates).
* H4 large diff size → MITIGATED by A2 (structural summary in W2 template).
* H6 untracked accumulation → MITIGATED by A3 (glob staging).
* H7 + H8 (Option-C-specific) → MOOT under Option F.

**Sub-finding 17.A.** Execution-readiness review's EXECUTION-CONDITIONALLY-READY verdict UPGRADED toward EXECUTION-READY by amendments. (The B1 blocker remains until W1–W4 actually executes; once executed under Option F, B1 closes.)

---

## §18. Compatibility with 24 preserved invariants

| invariant | preserved under amendments? | mechanism |
|---|---|---|
| replay-authoritative truth | ✓ | W2 V18 BLOCKING requirement preserved by A2 W2 template |
| append-only causality | ✓ | A1+A2+A3+A4 are additive (no deletions); pure append |
| authority singularity | ✓ | no authority changes |
| orchestration_tick supremacy | ✓ | runtime semantics unchanged |
| deterministic interruption boundaries | ✓ | contract content unchanged |
| Phase-A-only observability | ✓ | contract content unchanged |
| contradiction preservation | ✓ | contract content unchanged |
| transport independence | ✓ | contract content unchanged |
| no hidden cleanup | ✓ | existing lineage plan content preserved verbatim; supersession via append, not in-place edit |
| no wall-clock authority | ✓ | amendment timestamps descriptive only |
| no adaptive semantics | ✓ | no semantic changes |
| framework/contract separation | ✓ | amendments are framework-document only; no contract content |
| additive-only mutation discipline | ✓ | A1+A2+A3+A4 are pure additions (Properties A1–A3 analogues per §10) |
| replay-preserving extraction safety | ✓ | replay safety mechanisms unchanged |
| validator supremacy over reviewer intuition | ✓ | validator authority unchanged |
| no semantic widening authority | ✓ | no semantic changes |
| no reviewer discretionary reinterpretation | ✓ | reviewer authority unchanged |
| no hidden override pathways | ✓ | no new pathways |
| no authority redistribution | ✓ | per §12 |
| WAVE-ATOMICITY | ✓ | wave structure unchanged |
| BRANCH-LINEARITY | ✓ | no rebase/force-push/amend rules unchanged |
| MERGE-ATOMICITY | ✓ | merge mechanics unchanged |
| AUDIT-COMPLETENESS | ✓ | amendments ADD audit content (commit-message templates, dry-run protocols, explicit hazard enumeration); audit completeness enhanced |
| ROLE-SEPARATION | ✓ | per §12 |

All 24 invariants preserved. None weakened. None widened. None silently dropped.

---

## §19. Amendment-wave sequencing

The amendments A1–A4 are designed to be applied in a SINGLE append session:

* Single Decision-Owner action: append all four amendments (§A1 + §A2 + §A3 + §A4) to the lineage plan in one edit.
* No incremental authoring (e.g., apply A1 in one edit, A2 in another) — this would create intermediate "partially amended" lineage plan states which could confuse readers between edits.
* All-or-nothing: either all four are applied OR none.

**Operational note.** Application is a single file edit on the lineage plan. The amendment plan does not require a wave commit; the amended lineage plan becomes part of the W4 docs-only landing per the lineage plan §9 + §A3 glob staging.

**Sub-finding 19.A.** Amendments are application-atomic. Apply all four together as one Decision-Owner action.

---

## §20. Amendment-review requirements

* **Decision-Owner**: REQUIRED to review amendments before application (Decision-Owner is the authority that adopts the amended lineage plan as governing).
* **Reviewer** (Layer C role): OPTIONAL but RECOMMENDED. Layer C role applies to AAU authoring; amendments are pre-bootstrap. Decision-Owner may consult Reviewer for second-opinion if desired.
* **Constitutional Reviewer**: NOT REQUIRED. No constitutional change; Constitutional Reviewer escalation venue per Layer D §8.1 is for AAU-time T3/T8 escalations only.

**Sub-finding 20.A.** Decision-Owner unilateral application is constitutionally adequate. The amendments are operational refinements, not constitutional changes.

---

## §21. Amendment-risk classification

| risk class | classification |
|---|---|
| Constitutional risk | ZERO (no constitutional content altered) |
| Semantic risk | ZERO (no substrate semantics altered) |
| Operational risk | LOW (amendments REDUCE operational risk by eliminating H2/H5 SAFETY-CRITICAL hazards) |
| Audit-trail risk | NONE (amendments ADD audit content) |
| Reviewer-confusion risk | LOW (supersession via append preserves original guidance for context) |
| Rollback risk | LOW (amendments can be reverted by additional append-supersession; never in-place) |

**Sub-finding 21.A.** Aggregate risk: minimal. Amendments are net risk-reducing (eliminating SAFETY-CRITICAL hazards H2 + H5 outweighs the trivial operational overhead of having extra documentation).

---

## §22. Amendment-revert survivability

If the amended lineage plan is found to be INCORRECT post-application (e.g., Option F turns out to have a previously-unidentified issue):

* DO NOT delete §A1–§A4.
* Instead: append a NEW amendment §A5 "supersession of §A1" (or similar) that explains the issue and provides corrected guidance.
* The §A1–§A4 text remains in place; §A5 supersedes it.
* This preserves AUDIT-COMPLETENESS (history of operational decisions is visible).

This mirrors Layer C §19's audit-trace correction discipline.

**Sub-finding 22.A.** Amendments are themselves additive at the meta-level: future corrections go via append-supersession.

---

## §23. Amendment-auditability

The amendments produce the following audit trail:

* This amendment plan (`phase_4b_step12_lineage_amendment_plan.md`) — explains WHY the amendments are needed and provides the verbatim text. Lands in W4 per §A3 glob staging.
* The amended lineage plan (after Decision-Owner application) — contains the original §1–§32 + new §A1–§A4. Lands in W4 per §A3 glob staging.
* The dry-run review (`phase_4b_step12_lineage_dry_run_review.md`) — explains the hazards that motivate the amendments. Lands in W4.

Future readers can trace: "Why Option F? See lineage plan §A1. Why §A1? See lineage amendment plan + dry-run review."

**Sub-finding 23.A.** Audit trail is self-contained in the framework docs.

---

## §24. Amendment-content authoring boundary

This plan SPECIFIES the amendment content (verbatim text in §4.2, §5.2, §6.2, §7.2). It does NOT apply the amendments.

**Application is a Decision-Owner operation**: editing `docs/phase_4b_step12_lineage_normalization_plan.md` by appending the four §A1–§A4 sections after §32, using the verbatim text from this plan.

**Operational equivalent**: copy-paste the §4.2 + §5.2 + §6.2 + §7.2 text blocks (the inner `markdown` code blocks) into the lineage plan's end, with appropriate section-header adjustment for the lineage plan's section numbering.

**No commits required at application time** — the application is a working-tree edit to a docs file. The edit lands in W4 docs-only commit per the (now-amended) lineage plan §9 + §A3.

---

## §25. Plan amendment vocabulary

| term | meaning | scope |
|---|---|---|
| Additive supersession | append new content that supersedes prior recommendation without deleting prior content | this plan |
| Amendment patchset | the set of A1–A4 amendments authored together | this plan |
| Verbatim insertion text | the exact text added to the lineage plan upon application | this plan |
| Application-atomic | all four amendments applied in a single edit (not incremental) | this plan |

None enter the normative contract.

---

## §26. Final verdict

### **AMENDMENT-ADMISSIBLE**

The A1–A4 patchset is constitutionally safe. All four amendments are documentation-level refinements that preserve every inherited invariant, do not introduce new validators / governance layers / constitutional principles, and reduce net operational risk by eliminating SAFETY-CRITICAL Option-C-specific hazards H2 and H5.

### Constitutional basis for admissibility

1. **All 24 invariants preserved** (per §18 mapping table; none weakened, widened, or silently dropped).
2. **No semantic content altered** (per §11; zero new validators, layers, principles, roles, escalations).
3. **No authority redistribution** (per §12; all role types' authorities unchanged).
4. **No governance-layer expansion** (per §13; Layers A/B/C/D + pipeline state machine + gates + final-form checks all unchanged).
5. **No reviewer-authority expansion** (per §14; Layer C non-authority constraints preserved).
6. **Pure additive at documentation level** (per §10; Properties A1–A3 analogues satisfied).
7. **Compatibility verified** with admissibility evaluation (AUTHORING-ADMISSIBLE unchanged), baseline-init plan (S0–S8 unchanged), execution-readiness review (verdict upgradeable post-execution under Option F).

### Operational basis

* **A1 (Option F adoption)**: eliminates SAFETY-CRITICAL H2 (runtime decomposition difficulty) and H5 (false-PASS via mis-attribution). Net effect: per-Step runtime audit granularity sacrificed; safety significantly improved.
* **A2 (commit-message templates)**: addresses H1 (renumbering) + H3 (in-place modifications) + H4 (large diff auditor burden) by explicit enumeration in commit-message body.
* **A3 (glob-based staging)**: addresses H6 (untracked file accumulation) via pattern-based staging robust against doc-list drift.
* **A4 (pre-execution dry-runs)**: provides preview-before-commit safety margin via M9 + M10.

### Pre-application checklist (recommended)

Before Decision-Owner applies the amendments to the lineage plan:

1. Read this amendment plan in full.
2. Read dry-run review §27 (the amendment requirements).
3. Verify the §4.2 + §5.2 + §6.2 + §7.2 verbatim text matches intent.
4. Apply all four amendments in a single edit to `docs/phase_4b_step12_lineage_normalization_plan.md`.
5. Verify post-application `wc -l` matches expectation (~1,067 lines).
6. The amended lineage plan now governs B1 closure via Option F.

After application: B1 closure may proceed via Option F W1–W4 per amended lineage plan. The amendment plan itself becomes part of W4's docs-only commit per A3 glob staging.

### Hidden blockers

NONE identified. The amendments are operational refinements within the established framework. No new constitutional, governance, validator, or role concerns surface.

---

## §27. Preserved invariants under this amendment plan

This amendment plan introduces no new invariants and modifies no inherited ones. All 24 inherited invariants confirmed preserved at the amendment-design level:

* replay-authoritative truth ✓
* append-only causality ✓ (amendment plan is itself additive sibling doc)
* additive-only mutation discipline ✓ (per §10 + §18)
* BRANCH-LINEARITY ✓
* AUDIT-COMPLETENESS ✓
* validator supremacy ✓
* no semantic widening ✓
* no hidden cleanup ✓ (supersession via append; original guidance preserved)
* no authority redistribution ✓
* no governance-layer expansion ✓
* no reviewer-authority expansion ✓
* no runtime semantic mutation ✓
* no contract semantic mutation ✓
* (plus all remaining invariants per §18)

None weakened. None widened. None silently dropped.

---

**End of Step 12 lineage normalization amendment plan.**

**Verdict: AMENDMENT-ADMISSIBLE.**

The A1–A4 patchset is constitutionally safe and operationally beneficial. Decision-Owner may apply (single edit appending §A1+§A2+§A3+§A4 to lineage plan, using verbatim text from §4.2+§5.2+§6.2+§7.2 of this plan) at any time before W1 execution.

After application: B1 closure proceeds via amended lineage plan under Option F + M1/M3/M6 mitigations.

Predecessors: all prior Step 11 + Step 12 framework artifacts (see lineage normalization plan and dry-run review for full enumeration).

Successor: Decision-Owner applies amendments (single working-tree edit); then B1 closure via Option F W1–W4 per amended lineage plan; then bootstrap S0 per baseline-init §4; then S1–S8; then AUTHORING-ACTIVE.
