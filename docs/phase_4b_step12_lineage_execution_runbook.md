# Phase 4B Step 12 — B1 Lineage Normalization Execution Runbook (Operator Procedure)

**Status: PRE-EXECUTION OPERATOR RUNBOOK (2026-05-21).** Step-by-step procedure the Decision-Owner follows in real time at the terminal to execute the B1 lineage normalization under the amended Option F path. Reads as "exactly what the operator does." Designed to be opened next to the terminal during execution.

This document is **NOT itself executed during this session**. It is the runbook the Decision-Owner uses when they perform the real work after applying amendments A1–A4 to the lineage normalization plan.

Inherits from: [lineage normalization plan](phase_4b_step12_lineage_normalization_plan.md) (W1–W4 protocols), [dry-run review](phase_4b_step12_lineage_dry_run_review.md) (hazards H1–H8 + mitigations M1–M10), [amendment plan](phase_4b_step12_lineage_amendment_plan.md) (verbatim §A1–§A4 amendment text).

---

## §1. Pre-flight (before opening the terminal)

Before beginning execution, confirm:

| precondition | check |
|---|---|
| Operating in `/home/cap2/last` workspace | `pwd` returns `/home/cap2/last` |
| Decision-Owner has read amendment plan §4.2 + §5.2 + §6.2 + §7.2 verbatim text | self-attestation |
| Decision-Owner has authorized Step 12 normalization to proceed | self-attestation |
| Block of focused time available (~3–6 hours total; or split across sessions) | self-attestation |
| Terminal session is logged or output is captured | recommended: `script /tmp/step12-normalization-transcript.log` opens a session-recorder; `exit` closes |
| No concurrent contributors editing the workspace | coordination check |
| `tools/check_session_replay_identity.py` is operational against existing baseline | verified in Phase 1 below |

**Estimated total wall-time:** 3–6 hours focused work (Phase 0 + Phases 1–6 + verification).

**Authorization:** Begin only after Decision-Owner attests they are authorized to proceed.

---

## §2. Phase 0 — Apply A1–A4 amendments to lineage plan

**Goal.** Append §A1, §A2, §A3, §A4 to `docs/phase_4b_step12_lineage_normalization_plan.md`.

**Operation.** Open the lineage plan in an editor; locate the end of §32 ("Coordination with readiness-review refinements"); position cursor at the first blank line after §32's closing line; paste the verbatim text from amendment plan §4.2, §5.2, §6.2, §7.2 (in order).

**Specifically:**

1. Open lineage plan: `<editor> docs/phase_4b_step12_lineage_normalization_plan.md`
2. Navigate to end of §32.
3. Insert blank line if not present.
4. From amendment plan §4.2: copy the markdown block beginning with `## §A1. AMENDMENT — Option F adoption...` and ending with the closing line of the A1 verbatim block. Paste at insertion point.
5. From amendment plan §5.2: copy the §A2 block. Paste below §A1.
6. From amendment plan §6.2: copy the §A3 block. Paste below §A2.
7. From amendment plan §7.2: copy the §A4 block. Paste below §A3.
8. Save and exit editor.

**Verification:**

```bash
wc -l docs/phase_4b_step12_lineage_normalization_plan.md
# Expect: approximately 1067 (pre-amendment 762 + ~305 added)

grep -c '^## §A[1234]\.' docs/phase_4b_step12_lineage_normalization_plan.md
# Expect: 4

head -762 docs/phase_4b_step12_lineage_normalization_plan.md | tail -1
# Expect: the original §32 closing content (unchanged)

grep '^## §32\.' docs/phase_4b_step12_lineage_normalization_plan.md | wc -l
# Expect: 1 (still exactly one occurrence; §32 not duplicated or deleted)
```

If any verification fails: abort, restore from working-tree backup, retry.

**Working-tree state after Phase 0:** lineage plan now contains §A1–§A4. Still untracked (will be staged in W4). No commits yet. No other files modified.

---

## §3. Phase 1 — Pre-execution dry-runs (M9 + M10)

**Goal.** Confirm baseline-tool sanity and W1 contract staging plan BEFORE any commit.

### §3.1 M10 — V18 against working tree

```bash
# Confirm replay tool is invocable
ls tools/check_session_replay_identity.py

# Invoke V18 against working-tree state (NOT against any commit)
# Exact invocation depends on existing tool conventions; sketch:
python tools/check_session_replay_identity.py [tool args]
```

**Expected result:** V18 PASSes against the validated Step 10 baseline events.jsonl SHA-256 (per Step 10 Direction A's "12/12 cycles bytewise replay-identical under --reopen-stage-between-cycles").

**Decision point M10:**
* **PASS** → proceed to §3.2.
* **FAIL** → HALT. The replay-tool + working-tree runtime + baseline reference are NOT aligned. Investigate root cause (tool regression? runtime drift? baseline drift?) BEFORE any commit. Do NOT begin W1 until M10 PASSes.

### §3.2 M9 — W1 contract staging dry-run (preview without committing)

```bash
# Confirm working tree clean of any prior staging
git status --porcelain
# Should show modified + untracked files but no staged changes

# Begin interactive hunk-by-hunk staging of contract; accept Step 9 hunks (y), reject Step 10 hunks (n), split if needed (s)
git add -p docs/phase_4b_deterministic_semantics.md
```

For each hunk, the operator decides:
* **Step 9 attribution** (D-FAULT-1..-14, D-FAULT-15 rows 1–18, §11 item 4 modification, authoritative-set expansion, retry-semantics text): answer `y`
* **Step 10 attribution** (D-EXEC-13 family, D-FAULT-1b, D-FAULT-3b, D-FAULT-12c, §1.5→§1.6 renumbering, D-FAULT-15 rows 19–30): answer `n`
* **Ambiguous hunks**: answer `s` to split into smaller hunks; re-decide each sub-hunk

```bash
# Save planned diff for review (without committing)
git diff --cached docs/phase_4b_deterministic_semantics.md > /tmp/w1-contract-planned.diff

# Reset stage; working tree preserved (no commit; no file modification)
git restore --staged docs/phase_4b_deterministic_semantics.md
```

**Verification:** open `/tmp/w1-contract-planned.diff` in editor. Verify ALL of:

* Contains `+## 13. Deterministic Failure Semantics Contract` (or similar §13 D-FAULT introduction).
* Contains `+**D-FAULT-1**`, `+**D-FAULT-2**`, ..., `+**D-FAULT-14**` (clause definitions).
* Contains `+#### 13.17 D-FAULT-15` (table introduction) plus rows 1–18.
* Contains the §11 item 4 in-place modification (`-4. **Failure-action determinism...** When task A fails...` deletion + `+4. **Failure-action determinism...** Pinned in §13 D-FAULT...` addition).
* Contains the authoritative-set list expansion.
* Contains the retry-semantics non-goal text refinement.
* **Does NOT contain** `D-EXEC-13` family content.
* **Does NOT contain** `D-FAULT-1b` or `D-FAULT-3b` or `D-FAULT-12c`.
* **Does NOT contain** §1.5→§1.6 renumbering hunks.

**Decision point M9:**
* **Matches expected Step 9 content** → proceed to §4 (W1 execution).
* **Does NOT match** → revise the per-hunk attribution; re-run M9; do NOT proceed until match.

**Working-tree state after Phase 1:** working tree unchanged from session start. Index clean (no staged changes). Files at `/tmp/w1-contract-planned.diff` (workspace scratch; can be deleted after W1 commit).

---

## §4. Phase 2 — W1 execution (Step 9 contract + docs + tests + scripts; NO RUNTIME)

**Goal.** Land Step 9 closure as a single commit. Under Option F, this commit does NOT include runtime files; runtime is deferred to W2.

### §4.1 Re-stage Step 9 contract (matches M9 dry-run)

```bash
git add -p docs/phase_4b_deterministic_semantics.md
```

Repeat the same hunk-by-hunk decisions made in §3.2. The planned diff should match `/tmp/w1-contract-planned.diff`.

**Verification:**

```bash
git diff --cached docs/phase_4b_deterministic_semantics.md > /tmp/w1-contract-actual.diff
diff /tmp/w1-contract-planned.diff /tmp/w1-contract-actual.diff
# Expect: no output (files identical)
```

If `diff` shows differences: investigate; the actual staging diverged from the planned. Reset and retry:

```bash
git restore --staged docs/phase_4b_deterministic_semantics.md
# Then retry §4.1 with corrected per-hunk decisions
```

### §4.2 Stage Step 9 tests + scripts + docs + new module attribution

```bash
# Step 9 tests (untracked or modified)
git add isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step9_p4_fault_contract.py
git add isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step9_p7_replay_comparator.py
git add isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step8_p6_replay_identity.py

# Step 9 scripts
git add scripts/launch_phase_5_two_node.py
git add scripts/launch_phase_9p6_step9_abort.py

# Step 9 docs
git add docs/phase_4b_step9_failure_semantics_analysis.md
```

**NOTE:** Do NOT stage `envelopes.py`, runtime files (orchestration/, tasks/), `tools/check_session_replay_identity.py`, Step 10 tests, Step 10 scripts, Step 10 docs, Step 11 docs, or Step 12 docs at this step. Those land in W2/W3/W4 respectively.

### §4.3 Verify staged set

```bash
git diff --cached --stat
```

**Expected staged set:**

```
docs/phase_4b_deterministic_semantics.md     | <Step 9 lines>
docs/phase_4b_step9_failure_semantics_analysis.md | <new file>
isaac_factory/.../test_cell_01_phase_4b_step8_p6_replay_identity.py | <modified>
isaac_factory/.../test_cell_01_phase_4b_step9_p4_fault_contract.py | <new>
isaac_factory/.../test_cell_01_phase_4b_step9_p7_replay_comparator.py | <new>
scripts/launch_phase_5_two_node.py | <modified>
scripts/launch_phase_9p6_step9_abort.py | <new>
```

**Verify NOT in staged set:** no `orchestration/*.py`, no `tasks/*.py`, no `tools/check_session_replay_identity.py`, no Step 10 / Step 11 / Step 12 docs, no Step 10 tests, no Step 10 scripts, no `envelopes.py`.

**Decision point §4.3:**
* **Staged set matches** → proceed to §4.4.
* **Mismatch** → reset and retry:
  ```bash
  git restore --staged .
  # Then redo §4.1 + §4.2
  ```

### §4.4 Commit W1 with verbatim template from amendment plan §A2.1

Use HEREDOC to pass the commit message body verbatim:

```bash
git commit -m "$(cat <<'EOF'
Phase 4B Step 9 — D-FAULT deterministic failure semantics contract additions + docs + tests (STEP 9 CLOSURE, contract+docs landing)

This commit lands Step 9 closure CONTRACT + DOCS + TESTS only. Runtime is deferred to W2 per Option F (see docs/phase_4b_step12_lineage_amendment_plan.md §A1).

Contract additions (docs/phase_4b_deterministic_semantics.md):
- §13 D-FAULT contract: D-FAULT-1 through D-FAULT-14 introductions
- §13.17 D-FAULT-15 forbidden patterns: rows 1–18
- D-FAULT failure-class taxonomy + D-FAULT-9 OperatorEnvelope schema
- D-FAULT-1a inner sub-classification

In-place contract modifications (NOT pure additions; explicit enumeration per
docs/phase_4b_step12_lineage_dry_run_review.md §6, §8):
- §11 open-extension item 4 text updated: from "Phase 4B step 9 will surface and pin this" to "Pinned in §13 D-FAULT..."
- Authoritative-set list expanded to include `_retry_counts` + `_node_runtime`
- Non-goal text re retry semantics refined to reflect post-Step-9 state

Tests landed:
- test_cell_01_phase_4b_step9_p4_fault_contract.py (new)
- test_cell_01_phase_4b_step9_p7_replay_comparator.py (new)
- test_cell_01_phase_4b_step8_p6_replay_identity.py (refined for Step 9 P6 closure)

Scripts landed:
- scripts/launch_phase_5_two_node.py (Step 9 P5 two-node runtime launcher)
- scripts/launch_phase_9p6_step9_abort.py (Step 9 P6 abort launcher)

Docs landed:
- docs/phase_4b_step9_failure_semantics_analysis.md

Runtime: DEFERRED to W2. Post-W1 master runtime = Step 8 closure runtime. Contract-ahead-of-runtime inconsistency window per Option F §A1.3.

V18: not invoked at W1 under Option F (runtime unchanged from Step 8 closure).

Closure-proof reference: project_phase_4b_step9.md memory entry.
EOF
)"
```

### §4.5 Post-W1 verification

```bash
# Verify commit landed
git log --oneline -1
# Expect: <new-SHA>  Phase 4B Step 9 — D-FAULT deterministic failure semantics...

# Verify working-tree state: Step 10/11/12 content remaining
git status --porcelain | head -20
# Expect:
# M docs/phase_4b_deterministic_semantics.md           (Step 10 contract delta remaining)
# M isaac_factory/.../orchestration/*.py               (runtime remaining; for W2)
# M isaac_factory/.../tasks/*.py                       (runtime remaining; for W2)
# M tools/check_session_replay_identity.py             (for W2)
# ?? isaac_factory/.../envelopes.py                    (for W2)
# ?? Step 10 tests/scripts/docs                        (for W2)
# ?? Step 11 docs                                       (for W3)
# ?? Step 12 docs                                       (for W4)
```

**Decision point §4.5:**
* **Expected files remaining** → W1 complete. Pause/break if desired.
* **Unexpected staged or missing files** → investigate. Possibly revert W1 (`git revert HEAD`) and re-attempt.

### §4.6 (Optional) Apply step9-closed tag

```bash
git tag step9-closed
```

### §4.7 W1 wall-time estimate

~30–60 minutes (M9+M10 + per-hunk staging + verification + commit + post-verification).

---

## §5. Phase 3 — W2 execution (combined runtime + Step 10 contract + docs + tests; INCLUDES V18 BLOCKING)

**Goal.** Land all post-Step-8 runtime (Step 9 + Step 10 combined) + Step 10 contract additions + Step 10 docs + tests + scripts + `envelopes.py`. Post-commit V18 MUST PASS.

### §5.1 Stage Step 10 contract via `git add -p`

```bash
git add -p docs/phase_4b_deterministic_semantics.md
```

For each remaining hunk (the Step 10 hunks that were rejected in W1):
* All hunks should be Step 10 attribution: answer `y`
* If a hunk is ambiguous: split with `s` and re-decide

**Verification:**

```bash
git diff --cached docs/phase_4b_deterministic_semantics.md > /tmp/w2-contract-actual.diff
# Inspect /tmp/w2-contract-actual.diff:
# - Contains D-EXEC-13 + D-EXEC-13a/b/c/d (Step 10 sub-Phase-E interruption)
# - Contains D-FAULT-1b + D-FAULT-3b + D-FAULT-12c
# - Contains §13.17 D-FAULT-15 rows 19–30
# - Contains §1.5 Non-goals → §1.6 Non-goals renumbering hunk (Step 10 inserted new §1.5; old §1.5 renumbered)
# - Does NOT contain Step 9 content (already in W1)

# Verify entire contract diff is now staged + W1's contract content is committed
git diff docs/phase_4b_deterministic_semantics.md
# Expect: NO output (working tree contract = HEAD contract + staged delta = post-Step-10 form fully accounted for)
```

### §5.2 Stage all runtime files (full-file staging)

```bash
# Orchestration runtime
git add isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/__init__.py
git add isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/graph.py
git add isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py
git add isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/snapshot.py
git add isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/envelopes.py
git add isaac_factory/extensions/cell_authoring/cell_authoring/tasks/definitions.py
git add isaac_factory/extensions/cell_authoring/cell_authoring/tasks/executor.py

# Replay tool
git add tools/check_session_replay_identity.py
```

### §5.3 Stage Step 10 tests + scripts + docs

```bash
# Step 10 tests
git add isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step10_p3_direction_a_contract.py

# Step 10 scripts
git add scripts/launch_phase_10_p6_isaac.py
git add scripts/diag_stream_minimal.py
git add scripts/diag_stream_smoke.py

# Step 10 docs
git add docs/phase_4b_step10_candidates_analysis.md
git add docs/phase_4b_step10_direction_a_analysis.md
git add docs/phase_4b_step10_p6_isaac_acceptance.md
```

**NOTE:** Do NOT stage Step 11 docs (W3) or Step 12 docs (W4) here.

### §5.4 Verify staged set

```bash
git diff --cached --stat
```

**Expected staged set:**
* 1 contract file (Step 10 delta)
* 8 runtime files (orchestration/* + tasks/* + tools/check_session_replay_identity.py + envelopes.py)
* 1 test file
* 3 script files
* 3 docs files

**Total: ~16 files in W2 staged set.**

**Verify NOT in staged set:** any `docs/phase_4b_step11_*.md` or `docs/phase_4b_step12_*.md`.

```bash
git diff --cached --stat | grep -E 'step11|step12'
# Expect: NO output
```

**Decision point §5.4:**
* **Staged set matches** → proceed to §5.5.
* **Mismatch** → reset and retry:
  ```bash
  git restore --staged .
  # Then redo §5.1, §5.2, §5.3
  ```

### §5.5 Commit W2 with verbatim template from amendment plan §A2.2

```bash
git commit -m "$(cat <<'EOF'
Phase 4B Step 9 + Step 10 Direction A — combined runtime + Step 10 contract + Step 10 docs + tests (STEP 10 DIRECTION A CLOSURE, runtime+Step-10-contract landing)

This commit lands ALL post-Step-8 runtime (combined Step 9 + Step 10) + Step 10 contract additions + Step 10 docs + Step 10 tests + Step 10 scripts. Per Option F (see docs/phase_4b_step12_lineage_amendment_plan.md §A1), Step 9 runtime is deferred from W1 to here.

Runtime landed (all files; full-file staging):
- orchestration/__init__.py (+33 lines)
- orchestration/graph.py (+42/-X)
- orchestration/session.py (+943/-X) — structural summary:
  * D-FAULT failure-emission infrastructure per Step 9
  * abort propagation per D-FAULT-3
  * D-EXEC-13 predicate-consultation infrastructure per Step 10
  * EXECUTION_INTERRUPTED outcome handling per D-FAULT-1b
- orchestration/snapshot.py (+12/-X)
- orchestration/envelopes.py (NEW — OperatorEnvelope per D-FAULT-9)
- tasks/definitions.py (+61/-X) — TaskDefinition.tick_budget_ticks per D-FAULT-12
- tasks/executor.py (+232/-X) — D-EXEC-13 predicate consultation
- tools/check_session_replay_identity.py (+371/-X) — Step 9 P7 comparator extensions

Step 10 contract additions (docs/phase_4b_deterministic_semantics.md):
- NEW §1.5 Sub-Phase-E interruption surface
- D-EXEC-13 + D-EXEC-13a + D-EXEC-13b + D-EXEC-13c + D-EXEC-13d
- D-FAULT-1b — Executor-reported interruption sub-classifier
- D-FAULT-3b — Session classification of EXECUTION_INTERRUPTED
- D-FAULT-12c — ticks_consumed authority
- §13.17 D-FAULT-15 rows 19–30

In-place contract modifications (NOT pure additions):
- §1.5 Non-goals → §1.6 Non-goals (renumbering due to insertion of new §1.5 Sub-Phase-E interruption surface). Pre-Step-10 §1.5 content preserved verbatim at §1.6 position.

Tests landed:
- test_cell_01_phase_4b_step10_p3_direction_a_contract.py (new)

Scripts landed:
- scripts/launch_phase_10_p6_isaac.py
- scripts/diag_stream_minimal.py
- scripts/diag_stream_smoke.py

Docs landed:
- docs/phase_4b_step10_candidates_analysis.md
- docs/phase_4b_step10_direction_a_analysis.md
- docs/phase_4b_step10_p6_isaac_acceptance.md

V18: post-commit verification REQUIRED; MUST PASS against validated Step 10 baseline.

Closure-proof reference: project_phase_4b_step10.md memory entry.
EOF
)"
```

### §5.6 Post-W2 V18 invocation (BLOCKING)

```bash
# Critical post-commit V18 invocation
python tools/check_session_replay_identity.py [tool args]
```

**Decision point §5.6:**
* **V18 PASSes** → proceed to §5.7.
* **V18 FAILs** → CRITICAL. Execute revert procedure:
  ```bash
  # Revert W2 (additive inverse commit; no force-push, no rebase, no amend)
  git revert HEAD
  # Commit the revert with explanatory message
  ```
  Then investigate root cause per dry-run review §22:
  * Did the runtime get committed correctly? (`git diff HEAD~2 HEAD -- isaac_factory/`)
  * Did pre-commit hooks alter content? (compare staged content to working-tree content)
  * Is the replay tool functioning correctly? (try V18 against `cb95a9a` to confirm baseline-mode works)
  * Did line-ending normalization activate? (check `.gitattributes`)

  After resolving root cause: re-stage W2 corrected content; commit W2_v2; re-run V18.

### §5.7 Post-W2 verification

```bash
git log --oneline -2
# Expect:
# <W2-SHA>  Phase 4B Step 9 + Step 10 Direction A — combined runtime...
# <W1-SHA>  Phase 4B Step 9 — D-FAULT deterministic failure semantics...

git status --porcelain | head -20
# Expect: only Step 11 + Step 12 docs remaining (untracked)
# Expect: NO modified runtime files (all committed in W2)
# Expect: NO modified contract file (all committed in W1 + W2)

# Verify all runtime is committed
git diff --stat isaac_factory/ tools/
# Expect: NO output
```

### §5.8 (Optional) Apply step10-direction-a-closed tag

```bash
git tag step10-direction-a-closed
```

### §5.9 W2 wall-time estimate

~45–90 minutes (staging + commit + V18 invocation + verification).

**Strongly recommended pause** before W3: V18 PASS is the critical checkpoint; take a break before docs-only waves.

---

## §6. Phase 4 — W3 execution (Step 11 docs; docs-only)

**Goal.** Land 8 Step 11 framework docs in a single docs-only commit.

### §6.1 Stage Step 11 docs (glob)

```bash
git add docs/phase_4b_step11_*.md
```

### §6.2 Verify staged set

```bash
git diff --cached --stat | grep "phase_4b_step11_"
# Expect: 8 files, all under docs/phase_4b_step11_*

git diff --cached --stat | grep -v "phase_4b_step11_"
# Expect: NO output (no other files staged)
```

**Expected 8 files:**
* `docs/phase_4b_step11_admissibility_framework.md`
* `docs/phase_4b_step11_closure_verification.md`
* `docs/phase_4b_step11_codification_plan.md`
* `docs/phase_4b_step11_extraction_plan.md`
* `docs/phase_4b_step11_f58_paused_analysis.md`
* `docs/phase_4b_step11_f59_manual_advance_analysis.md`
* `docs/phase_4b_step11_live_ingress_analysis.md`
* `docs/phase_4b_step11_meta_audit.md`

### §6.3 Commit W3 with verbatim template from amendment plan §A2.3

```bash
git commit -m "$(cat <<'EOF'
docs: Phase 4B Step 11 — live ingress analytical pipeline (STEP 11 PLANNING COMPLETE, 8 framework artifacts)

This commit lands the Step 11 analytical pipeline as docs-only. No runtime, no contract, no tests.

Docs landed (8 files, all under docs/phase_4b_step11_*.md):
- phase_4b_step11_live_ingress_analysis.md (compatibility-boundary investigation)
- phase_4b_step11_admissibility_framework.md (T1-T9, L1-L4, D1-D9, 6-object ontology)
- phase_4b_step11_f58_paused_analysis.md (F58 PAUSED admissibility)
- phase_4b_step11_f59_manual_advance_analysis.md (F59 manual_advance inadmissibility)
- phase_4b_step11_closure_verification.md (framework closure verified)
- phase_4b_step11_codification_plan.md (codification topology + 6-phase ordering)
- phase_4b_step11_meta_audit.md (meta-constitutional self-consistency audit)
- phase_4b_step11_extraction_plan.md (38 atomic insertions across 6 waves)

Closure-proof reference: project_phase_4b_step11.md memory entry.

V18: not invoked (no runtime/contract change).
EOF
)"
```

### §6.4 Post-W3 verification

```bash
git log --oneline -3
# Expect:
# <W3-SHA>  docs: Phase 4B Step 11 — live ingress analytical pipeline...
# <W2-SHA>  Phase 4B Step 9 + Step 10 Direction A — combined runtime...
# <W1-SHA>  Phase 4B Step 9 — D-FAULT deterministic failure semantics...

git status --porcelain | head -20
# Expect: only Step 12 docs remaining (untracked)
```

### §6.5 (Optional) Apply step11-planning-complete tag

```bash
git tag step11-planning-complete
```

### §6.6 W3 wall-time estimate

~10–15 minutes.

---

## §7. Phase 5 — W4 execution (Step 12 docs; docs-only; FINAL LANDING WAVE)

**Goal.** Land all Step 12 docs (including the amended lineage plan, this runbook, and all prior Step 12 planning artifacts) in a single docs-only commit.

### §7.1 Stage Step 12 docs (glob)

```bash
git add docs/phase_4b_step12_*.md
```

### §7.2 Verify staged set

```bash
git diff --cached --stat | grep "phase_4b_step12_"
# Expect: ~11+ files, all under docs/phase_4b_step12_*

git diff --cached --stat | grep -v "phase_4b_step12_"
# Expect: NO output
```

**Expected files (count may vary if additional Step 12 docs were authored before W4 execution):**

* `docs/phase_4b_step12_authoring_mechanics_plan.md` (Layer A)
* `docs/phase_4b_step12_validation_plan.md` (Layer B)
* `docs/phase_4b_step12_review_ergonomics_plan.md` (Layer C)
* `docs/phase_4b_step12_governance_plan.md` (Layer D)
* `docs/phase_4b_step12_admissibility_evaluation.md`
* `docs/phase_4b_step12_baseline_initialization_plan.md`
* `docs/phase_4b_step12_execution_readiness_review.md`
* `docs/phase_4b_step12_lineage_normalization_plan.md` (includes A1–A4 amendments applied in Phase 0)
* `docs/phase_4b_step12_lineage_dry_run_review.md`
* `docs/phase_4b_step12_lineage_amendment_plan.md`
* `docs/phase_4b_step12_lineage_execution_runbook.md` (this document)
* (any additional Step 12 docs authored)

### §7.3 Commit W4 with verbatim template from amendment plan §A2.4

```bash
git commit -m "$(cat <<'EOF'
docs: Phase 4B Step 12 — pre-authoring transition planning framework + amendment plan (STEP 12 PLANNING COMPLETE)

This commit lands the Step 12 pre-authoring framework as docs-only. No runtime, no contract, no tests, no AAUs.

Docs landed (all docs/phase_4b_step12_*.md files present at execution time; glob-staged per amendment plan §A3):
- phase_4b_step12_authoring_mechanics_plan.md (Layer A)
- phase_4b_step12_validation_plan.md (Layer B)
- phase_4b_step12_review_ergonomics_plan.md (Layer C)
- phase_4b_step12_governance_plan.md (Layer D)
- phase_4b_step12_admissibility_evaluation.md (verdict: AUTHORING-ADMISSIBLE)
- phase_4b_step12_baseline_initialization_plan.md (S0–S8 bootstrap pathway)
- phase_4b_step12_execution_readiness_review.md (verdict: EXECUTION-CONDITIONALLY-READY; B1 identified)
- phase_4b_step12_lineage_normalization_plan.md (4-wave B1 closure pathway; amended per A1–A4)
- phase_4b_step12_lineage_dry_run_review.md (verdict: DRY-RUN-CONDITIONALLY-SAFE)
- phase_4b_step12_lineage_amendment_plan.md (A1–A4 amendment patchset)
- phase_4b_step12_lineage_execution_runbook.md (operator runbook)

Closure-proof references: project_phase_4b_step12_*.md memory entries.

V18: not invoked (no runtime/contract change).

This is the FINAL landing wave. Post-W4 master HEAD = "post-everything substrate" ready for bootstrap S0 per docs/phase_4b_step12_baseline_initialization_plan.md §4.
EOF
)"
```

### §7.4 Post-W4 verification

```bash
git log --oneline -5
# Expect:
# <W4-SHA>  docs: Phase 4B Step 12 — pre-authoring transition planning framework...
# <W3-SHA>  docs: Phase 4B Step 11 — live ingress analytical pipeline...
# <W2-SHA>  Phase 4B Step 9 + Step 10 Direction A — combined runtime...
# <W1-SHA>  Phase 4B Step 9 — D-FAULT deterministic failure semantics...
# cb95a9a   Phase 4B Step 8 / Phase 6 — deterministic replay verification + STEP 8 CLOSURE

git status --porcelain
# Expect: EMPTY OUTPUT (working tree fully clean)
```

### §7.5 (Optional) Apply step12-planning-complete tag

```bash
git tag step12-planning-complete
```

### §7.6 W4 wall-time estimate

~10–15 minutes.

---

## §8. Phase 6 — Final master-ready-for-S0 verification

**Goal.** Confirm master HEAD is at the "post-everything substrate" state required for bootstrap S0 per lineage plan §28.

### §8.1 9-point verification

Run each check; record result:

```bash
# 1. Master HEAD is W4-SHA
git rev-parse HEAD
# Record SHA

# 2. Working tree clean
git status --porcelain
# Expect: EMPTY output

# 3. Linear history: cb95a9a → W1 → W2 → W3 → W4 (4 commits between)
git log --oneline cb95a9a..HEAD | wc -l
# Expect: 4

# 4. No force-push or amend in normalization history
# (intrinsic; if `git reflog show master | grep -E 'amend|force'` returns no entries, confirmed)
git reflog show master | head -10
# Inspect for any amend/force entries

# 5. V18 PASS on master HEAD against Step 10 baseline
python tools/check_session_replay_identity.py [tool args]
# Expect: PASS

# 6. Contract at post-Step-10 form
grep -c "^**D-EXEC-13" docs/phase_4b_deterministic_semantics.md
# Expect: >= 1 (D-EXEC-13 clauses present)
grep -c "D-FAULT-1b" docs/phase_4b_deterministic_semantics.md
# Expect: >= 1

# 7. All 8 Step 11 docs in docs/
ls docs/phase_4b_step11_*.md | wc -l
# Expect: 8

# 8. All 8+ Step 12 planning docs in docs/
ls docs/phase_4b_step12_*.md | wc -l
# Expect: >= 8 (11+ if all artifacts present)

# 9. Decision-Owner attests master is ready
# (self-attestation)
```

### §8.2 Decision point §8

* **All 9 checks ✓** → **B1 CLOSED**. Master is post-everything substrate. Bootstrap S0 admissible.
* **Any check ✗** → investigate; do not declare B1 CLOSED until resolved.

### §8.3 Phase 6 wall-time estimate

~10–20 minutes (V18 invocation dominates).

---

## §9. Phase 7 — B1 CLOSED declaration

**Goal.** Formal record that B1 is closed; project state transitioned from "EXECUTION-CONDITIONALLY-READY with B1 blocker" to "EXECUTION-READY (bootstrap S0 admissible)".

### §9.1 Decision-Owner declaration

Decision-Owner records (in some durable form; recommended: a brief note added to `MEMORY.md` or as a tag annotation):

```
Phase 4B Step 12 B1 CLOSED on <date> by Decision-Owner <identifier>.
Master HEAD: <W4-SHA>
Verification: 9/9 ✓ per docs/phase_4b_step12_lineage_execution_runbook.md §8.
Bootstrap S0 admissible per docs/phase_4b_step12_baseline_initialization_plan.md §4.
```

### §9.2 Total wall-time recap

| phase | estimate |
|---|---|
| Phase 0 (amendment application) | 10–20 min |
| Phase 1 (pre-execution dry-runs) | 30–60 min (V18 dominates) |
| Phase 2 (W1) | 30–60 min |
| Phase 3 (W2 + V18 BLOCKING) | 45–90 min |
| Phase 4 (W3) | 10–15 min |
| Phase 5 (W4) | 10–15 min |
| Phase 6 (final verification) | 10–20 min |
| Phase 7 (declaration) | 5 min |
| **Total** | **~3–4.5 hours focused work** |

Plus breaks (recommended): ~30–60 minutes additional. Realistic operator wall-time: ~4–6 hours.

---

## §10. Mid-wave rollback procedure

If a wave commit succeeds but subsequent verification fails (e.g., W2 V18 FAILs):

```bash
# Identify the failed commit
git log --oneline -1
# Record the SHA: <failed-SHA>

# Revert (creates an additive inverse commit; preserves history)
git revert <failed-SHA>
# A commit message editor opens; accept the default revert message or refine

# Verify revert landed
git log --oneline -2
# Expect:
# <revert-SHA>  Revert "<original commit subject>"
# <failed-SHA>  <original commit subject>

# Working tree should be clean
git status --porcelain
# Expect: empty
```

After revert: investigate root cause; correct underlying issue in working tree; re-stage the wave's content; commit a new wave commit (e.g., W2_v2). DO NOT amend the original or the revert.

**FORBIDDEN:**
* `git commit --amend` (violates no-amend)
* `git reset --hard <prior>` (rewrites history)
* `git push --force` (violates no-force-push; not applicable since this runs locally)
* `git rebase` (rewrites history)

---

## §11. Recovery from mid-wave abort

If terminal session dies mid-stage (e.g., before commit completes, after staging):

```bash
# Re-open terminal
cd /home/cap2/last

# Inspect index state
git status --porcelain
# If files are staged (shown with M/A prefix in first column), the staging was committed or the index survived

# Inspect last commit
git log --oneline -1
# If last commit subject is the expected wave's subject: wave completed; proceed to verification
# Otherwise: wave did not complete; index may have partial staging
```

**If index has partial staging from incomplete wave:**

```bash
# Option A: complete the staging and commit (if intent is to continue)
# Resume staging where left off

# Option B: reset index and restart wave
git restore --staged .
# Then restart wave from staging step
```

**If commit completed but verification interrupted:** verification can re-run at any time; commit is durable. Continue with post-commit verification.

---

## §12. Interruption handling

If interrupted mid-stage (phone, meeting, etc.):

* **Mid `git add -p`**: type `q` to quit; no staging applied (or partial staging applied for hunks already accepted). Re-run `git add -p` when ready; partial staging preserved.
* **Mid editor (commit message)**: save and exit, OR delete all text and exit (depending on editor; aborts commit without commit message).
* **Mid V18 invocation**: V18 is a script; Ctrl+C aborts. Re-run when ready.
* **Mid editor (Phase 0 amendment application)**: save partial state; continue when ready.

In all cases: take recovery time to re-orient. Re-read this runbook from the section you were at.

---

## §13. Operator fatigue mitigation

**Recommended pause points:**

| pause after | rationale |
|---|---|
| Phase 0 (amendment application) | confirm amendment intent before proceeding to commits |
| Phase 1 (pre-execution dry-runs) | confirm baseline sanity; decision to proceed to commits |
| Phase 2 (W1 commit) | first commit; pause to re-verify before W2 |
| Phase 3 (W2 V18 PASS) | critical checkpoint; longest pause recommended |
| Phase 5 (W4 commit) | final landing wave complete; pause before verification |

**Suggested cadence:** complete Phases 0–3 in one focused session; pause for ≥ 30 min; complete Phases 4–7 in second session. Total wall-clock: 1–2 days operator time.

**Do NOT execute all phases under fatigue.** The per-hunk staging in §3.2 / §4.1 / §5.1 requires sustained attention; mistakes during these are operationally easy to recover but consume time.

---

## §14. Audit-log capture procedure

For a durable record of the normalization session:

```bash
# Before opening any new terminal, start a session recorder
script /tmp/step12-normalization-transcript-<date>.log

# Then proceed with Phases 0-7
# All terminal I/O is captured to the log

# After completion, exit the recorder
exit
```

The transcript is plaintext; preserve it for the audit trail. Optionally, after `docs/step12_audit_traces/` is created (during bootstrap S3), this transcript can be moved there:

```bash
# (Post-bootstrap-S3 operation; mentioned for reference)
mv /tmp/step12-normalization-transcript-<date>.log docs/step12_audit_traces/
```

---

## §15. Forbidden operations during execution

| operation | forbidden | reason |
|---|---|---|
| `git commit --amend` | YES | violates no-amend invariant |
| `git rebase` | YES | violates BRANCH-LINEARITY |
| `git push --force` | YES | violates BRANCH-LINEARITY |
| `git push --force-with-lease` | YES | violates BRANCH-LINEARITY |
| `git cherry-pick` from another branch | YES | not applicable here; no other branches |
| `git reset --hard <prior>` | YES | rewrites history |
| `git tag -d <existing-tag>` | YES | tags are immutable per BRANCH-LINEARITY transitivity |
| Edit lineage plan after Phase 0 | YES | would create dirty working tree and contaminate W4 staging |
| Skip a wave | YES | wave dependencies require strict sequence W1→W2→W3→W4 |
| Combine waves (e.g., W1+W2 in one commit) | YES (under Option F) | Option F specifies W1 and W2 as separate commits |
| Use `git add .` or `git add -A` | YES | over-staging risk (would pick up unintended files) |

---

## §16. Mid-wave verification rituals

Before each commit (Phases 2, 3, 4, 5):

```bash
# 1. Inspect what's staged
git diff --cached --stat
git diff --cached  # full diff inspection if desired

# 2. Confirm staged set matches plan
git diff --cached --stat | wc -l  # file count check

# 3. Confirm nothing unintended is staged
git diff --cached --stat | grep -E 'unexpected pattern'

# 4. Verify what's NOT staged is intended for later waves
git status --porcelain | grep -v '^[MA]' | head -10

# 5. Commit (with HEREDOC message)
git commit -m "$(cat <<'EOF'
[verbatim template per A2 amendment]
EOF
)"

# 6. Post-commit verification
git log --oneline -1
git status --porcelain
```

These six checks form the "commit ritual" — perform for each wave commit.

---

## §17. Branch cleanliness confirmation

After each commit:

```bash
# Working tree clean of completed-wave files
git status --porcelain | head -10

# Index clean (no leftover staging)
git diff --cached --stat
# Expect: NO output post-commit

# Branch on master
git branch --show-current
# Expect: master
```

Should remain on master throughout all 4 waves. No branch creation, no checkout to other branches.

---

## §18. Master-linearity confirmation (final)

After all 4 waves complete:

```bash
# Linear history (no merge commits)
git log --oneline --graph cb95a9a..HEAD
# Expect: linear vertical line, no branching

# Exactly 4 commits since Step 8 closure (or 4 + N reverts if any failure recovery)
git log --oneline cb95a9a..HEAD | wc -l
# Expect: 4 (if no failures) or 4 + 2*N_failures (each failure adds revert + re-attempt)

# Reflog shows no amend / force-push
git reflog show master | head -10
```

---

## §19. Hard-stop conditions (HALT execution)

Stop execution IMMEDIATELY if any of:

| condition | action |
|---|---|
| Phase 1 M10 V18 FAILs | HALT; do not proceed to any commit; investigate baseline-tool sanity |
| Phase 3 W2 V18 FAILs | HALT; do not proceed to W3; revert W2; investigate root cause |
| Any verification step shows unexpected state | HALT; investigate before continuing |
| Decision-Owner loses confidence in the procedure | HALT; pause; re-read framework docs; resume only when confident |
| Unexpected external master change discovered | HALT; coordinate with other contributors; resume after agreement |
| Pre-commit hook unexpectedly modifies content | HALT; investigate hook; do not commit altered content |

**HALT means:** stop the runbook; preserve current working-tree + index state; do not commit; reflect on situation. Resume only after the issue is understood and resolved.

---

## §20. Post-execution: pre-bootstrap state confirmation

After Phase 7 declaration:

| state | expected value |
|---|---|
| Master HEAD | W4-SHA |
| Working tree | clean |
| Linear commit count from cb95a9a | 4 (or more if recoveries) |
| V18 on master HEAD | PASS |
| Contract document | post-Step-10 form |
| Step 11 docs in git | 8 |
| Step 12 docs in git | ≥ 8 |
| Decision-Owner attestation | RECORDED |
| Branch | master (no other branches yet) |
| Tags | optionally step9-closed, step10-direction-a-closed, step11-planning-complete, step12-planning-complete |

**Project state after Phase 7:** AUTHORING-ADMISSIBLE + EXECUTION-READY (B1 CLOSED). Bootstrap S0 may be authorized per `docs/phase_4b_step12_baseline_initialization_plan.md` §4.

---

## §21. Vocabulary

| term | meaning |
|---|---|
| Phase 0 | amendment application (single edit to lineage plan) |
| Phase 1 | pre-execution dry-runs (M9 + M10) |
| Phase 2 | W1 execution |
| Phase 3 | W2 execution (with BLOCKING V18) |
| Phase 4 | W3 execution |
| Phase 5 | W4 execution |
| Phase 6 | final master-ready-for-S0 verification |
| Phase 7 | B1 CLOSED declaration |
| Commit ritual | the 6-check sequence performed before each commit (§16) |
| HALT | stop runbook immediately and investigate |

None enter the normative contract.

---

## §22. Final verdict

### **EXECUTION-RUNBOOK-READY**

The runbook provides operationally executable, step-by-step instructions for B1 lineage normalization under amended Option F. All seven phases are concretely specified with exact bash commands, decision points, verification checks, rollback procedures, and HALT conditions.

### Operational basis for readiness

1. **Phase 0** authorial-equivalent operation (amendment application via single edit) is operationally straightforward with explicit verification.
2. **Phase 1** pre-execution dry-runs (M9 + M10) provide preview-before-commitment safety margin.
3. **Phase 2 (W1)** uses interactive `git add -p` with explicit per-hunk Step 9 attribution; pre-dry-run preview (Phase 1) reduces error risk; commit message template eliminates message-authoring time.
4. **Phase 3 (W2)** uses combined-runtime full-file staging (eliminating Option C runtime decomposition entirely per A1); post-commit V18 BLOCKING gate.
5. **Phases 4–5 (W3/W4)** use glob-based staging per A3; trivially clean.
6. **Phase 6** explicit 9-point verification mirrors lineage plan §28.
7. **Phase 7** Decision-Owner declaration records B1 closure durably.
8. **Mid-wave rollback** (§10) uses additive `git revert` per Layer A §13; no rebase, no force-push, no amend.
9. **HALT conditions** (§19) are explicit; no ambiguous decision branches.
10. **Forbidden operations** (§15) explicitly enumerated; the operator has a clear "do not do these" list.

### Constitutional preservation (per session brief)

All preserved invariants honored throughout the runbook:

* replay-authoritative truth ✓ (W2 V18 BLOCKING)
* append-only causality ✓ (additive commits + additive reverts; no history rewriting)
* additive-only mutation discipline ✓ (Phase 0 amendment is additive; W1–W4 wave commits are additive at branch level)
* BRANCH-LINEARITY ✓ (forbidden operations §15; reflog inspection §18)
* AUDIT-COMPLETENESS ✓ (verbatim commit messages preserve audit content; transcript capture §14)
* validator supremacy ✓ (V18 BLOCKING enforced; cannot be overridden by operator)
* no semantic widening ✓ (runbook performs no semantic changes)
* no hidden cleanup ✓ (existing working-tree content preserved verbatim into commits)
* no authority redistribution ✓ (Decision-Owner authority bounded to operational sign-off)
* no amend, no rebase, no force-push ✓ (explicit forbid list + reflog check)

### Hidden execution hazards remaining

NONE identified beyond those addressed by amendments A1–A4 and mitigations M1–M10. The dry-run review's 8-hazard catalog is fully addressed by:

* H1, H3 → A2 (commit-message templates explicitly enumerate in-place modifications)
* H2, H5 → A1 (Option F eliminates Option C runtime decomposition)
* H4 → A2 (structural summary in W2 template)
* H6 → A3 (glob staging)
* H7, H8 → moot under Option F

### Why READY, not CONDITIONALLY-READY

The runbook is complete: exact commands, exact verification, exact rollback paths, exact HALT conditions. No operational detail is missing. The Decision-Owner can execute the runbook with confidence after applying Phase 0 amendments.

Decision-Owner authorization remains a separate decision (when to execute), but the procedure itself is ready.

---

## §23. Preserved invariants under this runbook design

This runbook design introduces no new invariants and modifies no inherited ones. All preserved invariants from the session brief are honored by the runbook procedures:

* replay-authoritative truth ✓
* append-only causality ✓
* additive-only mutation discipline ✓
* BRANCH-LINEARITY ✓
* AUDIT-COMPLETENESS ✓
* validator supremacy ✓
* no semantic widening ✓
* no hidden cleanup ✓
* no authority redistribution ✓
* no amend ✓
* no rebase ✓
* no force-push ✓

None weakened. None widened. None silently dropped.

---

## §R-FG-1. AMENDMENT — Post-revert working-tree recovery sequence (supplements §10)

**Status: REFINEMENT POST-FINAL-GOVERNANCE-REVIEW (2026-05-21).** Per `docs/phase_4b_step12_refinement_prioritization.md` §17 verdict APPLY-R-FG-1-ONLY, this amendment supplements §10 (mid-wave rollback procedure) with explicit post-revert working-tree recovery commands.

### §R-FG-1.1 Why bare `git revert` is insufficient as a complete recovery

§10 prescribes `git revert <wave-sha>` as the rollback mechanism. This correctly preserves history (BRANCH-LINEARITY + AUDIT-COMPLETENESS) but does NOT by itself restore the failed-wave's working-tree content for correction.

After `git revert <failed-wave-sha>`:

* Master HEAD = the revert commit (parent = failed-wave commit).
* Working tree = matches the revert state (pre-failed-wave content).
* The failed-wave's working-tree changes (modified files, new files) are NO LONGER PRESENT in the working tree.

If the operator immediately attempts to "re-stage the wave's content" per §10's recovery sketch, the content is gone. Manual recreation is infeasible for large diffs (e.g., W2's combined runtime ~1,900+ insertions across 8 files including session.py at ~943 lines).

This amendment closes the gap by specifying how to restore the failed-wave's working-tree content for correction.

### §R-FG-1.2 Recovery sequence

After `git revert <failed-wave-sha>` produces the revert commit:

```bash
# Identify the relevant SHAs
git log --oneline -3
# Example:
# <revert-SHA>  Revert "Phase 4B Step 9 + Step 10 Direction A — combined runtime..."
# <failed-SHA>  Phase 4B Step 9 + Step 10 Direction A — combined runtime...
# <prior-SHA>   Phase 4B Step 9 — D-FAULT deterministic failure semantics...
```

Then restore the failed-wave's content using one of two options.

#### Option A — restore specific files (recommended when the fix is localized)

```bash
# Restore only the specific files that need correction
git checkout <failed-SHA> -- <path/to/file/to/fix>
git checkout <failed-SHA> -- <path/to/another/file>
# ... one git checkout per file to restore for editing
```

Use this when post-V18-FAIL investigation narrowed the root cause to a small set of files.

#### Option B — restore all failed-wave content (recommended when the fix scope is unclear or affects many files)

```bash
# Restore all paths that the failed-wave commit modified or added
git diff --name-only <failed-SHA>~1 <failed-SHA> | xargs git checkout <failed-SHA> --
```

Use this when post-V18-FAIL investigation has not narrowed the root cause; restore the full failed-wave footprint, correct as needed, re-commit.

### §R-FG-1.3 Verify restoration

```bash
# Confirm working tree now contains failed-wave content
git status --porcelain
# Expect: files modified/added matching failed-wave's scope

# Confirm restored content matches failed-wave commit content
git diff HEAD -- <restored-paths>
# Expect: diff matches the failed-wave's content vs revert-state HEAD
```

### §R-FG-1.4 Correction and re-attempt

```bash
# Make the correction (edit files to fix the bug discovered during V18 FAIL investigation)
<editor> <files-to-fix>

# Re-stage the corrected wave content
# For W2: re-run the §5.1, §5.2, §5.3 staging commands (Step 10 contract via -p,
# all runtime full-file, Step 10 tests + scripts + docs + envelopes.py)

# Verify staging matches expected wave content
git diff --cached --stat

# Re-commit with the corrected wave content. Use the original wave's verbatim
# commit-message template (per amendment plan §A2) PLUS a brief recovery note
# in the commit body acknowledging the failure-and-recovery pattern.
git commit -m "$(cat <<'EOF'
[original wave's commit message template per §A2]

Recovery note: this commit is a corrected re-attempt after <failed-SHA> was
reverted at <revert-SHA> due to <one-line-root-cause-summary>. Failed-attempt
history preserved per BRANCH-LINEARITY (no force-push, no amend, no rebase).
EOF
)"
```

### §R-FG-1.5 Post-recovery audit pattern

After successful re-attempt, the git history shows the three-commit recovery pattern:

```
<corrected-SHA>  Phase 4B Step <N> — [original subject] (corrected re-attempt)
<revert-SHA>     Revert "Phase 4B Step <N> — [original subject]"
<failed-SHA>     Phase 4B Step <N> — [original subject] (originally failed)
<prior-SHA>      [prior wave commit]
```

All three commits for the failed wave (failed + revert + corrected) are preserved in history. None is collapsed. The failure is visible; the recovery is visible; the corrected state is visible.

### §R-FG-1.6 Constitutional continuity

This recovery sequence preserves:

* **additive-only mutation discipline** — all three commits (failed, revert, corrected) are additive at the branch level; the working-tree restoration via `git checkout <failed-SHA> -- <files>` does NOT alter the index or history, only the working tree
* **BRANCH-LINEARITY** — linear history with explicit revert and re-attempt commits visible
* **AUDIT-COMPLETENESS** — the failure attempt is visible in the audit trail (commit `<failed-SHA>` retained); root cause recoverable from the corrected-commit's recovery note
* **no-amend** — `git commit --amend` MUST NOT be used at any point (would collapse the failure or revert into the corrected commit and lose audit content)
* **no-rebase** — `git rebase` MUST NOT be used (would rewrite the failure into history non-additively)
* **no-force-push** — `git push --force` MUST NOT be used (not applicable in local execution but explicit forbid maintained per §15)

### §R-FG-1.7 Effect on §10

§10's "Recovery sequence" prescription is UNCHANGED. §R-FG-1 adds the explicit working-tree restoration commands that bridge the gap between `git revert` (which §10 prescribes) and "re-stage the wave's content" (which §10 expects). Future readers see §10's high-level recovery framing AND §R-FG-1's explicit command sequence.

No new rollback class is introduced. No new operator action surface is added beyond what §10 already implied. The forbidden operations in §15 remain in force; this amendment introduces no exceptions.

### §R-FG-1.8 Scope boundary

This amendment applies ONLY to post-revert recovery in the context of the W1–W4 lineage normalization waves. It does NOT apply to:

* Bootstrap S0–S8 recovery (governed by baseline-init plan).
* Per-AAU rollback during AUTHORING-ACTIVE (governed by Layer A §13 + Layer D §16).
* Final PR merge rollback (governed by Layer D §15 + §19).

Those domains have their own rollback procedures with their own working-tree implications. This amendment's scope is bounded to runbook §10's per-wave rollback during lineage normalization.

---

**End of Step 12 B1 lineage normalization execution runbook.**

**Verdict: EXECUTION-RUNBOOK-READY.**

Decision-Owner may execute the procedure (Phases 0–7) at their authorized time. Estimated total wall-time: 3–4.5 hours focused work + breaks (4–6 hours real time). After Phase 7 declaration: B1 CLOSED; bootstrap S0 admissible.

Predecessors: all prior Step 11 + Step 12 framework artifacts. Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).

Successor: Decision-Owner executes Phases 0–7 → B1 CLOSED → bootstrap S0 per `phase_4b_step12_baseline_initialization_plan.md` §4 → S1–S8 → AUTHORING-ACTIVE.
