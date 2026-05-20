# Phase 4B Step 12 — B1 Lineage Normalization Plan (Pre-Bootstrap Operational Landing)

**Status: PRE-BOOTSTRAP LINEAGE-NORMALIZATION PLAN (2026-05-21).** Resolves B1 ("master HEAD discrepancy") identified in [`phase_4b_step12_execution_readiness_review.md`](phase_4b_step12_execution_readiness_review.md). Designs the exact commit/topology sequence required to land the existing Step 9 + Step 10 Direction A + Step 11 + Step 12 planning work from working-tree state into canonical git history on master, so that the codification branch's S1 creation can safely proceed.

Does **not** execute any commit. Does **not** create branches. Does **not** mutate the contract document. Does **not** begin S0–S8 bootstrap. Does **not** author AAUs. The deliverable is the operational landing pathway; execution is the Decision-Owner's prerogative.

The blocker (B1) is operational lineage normalization, not constitutional insufficiency. The four-layer pre-authoring framework + admissibility evaluation + baseline-init plan + readiness review remain VALID. This plan specifies the prerequisite "tidy up master before bootstrap" operation.

---

## §1. Scope and inheritance

| inherited from | element |
|---|---|
| Execution-readiness review §3 | B1 BLOCKER definition + resolution requirement |
| Step 8 commit pattern (`5a3a815` → `cb95a9a`) | precedent for closure-style landing on master |
| Layer A §16 | no-amend discipline (extended to lineage normalization) |
| Layer D §5 | branch-linearity (extended to master during normalization) |
| Layer D §18 | AUDIT-COMPLETENESS invariant |
| Layer C §19 | append-only causality at the audit layer (applied to commit history) |

The plan specifies only the operational landing pathway. It does not introduce new validators, layers, governance mechanisms, or invariants. It does not change *what* will be committed (the working-tree content is preserved verbatim); it specifies only *how* and *in what sequence*.

---

## §2. Empirical state recap

Per execution-readiness review §2:

* Master HEAD: `cb95a9a` (Step 8 Phase 6 closure)
* Only branch: `master`
* Stashes: none
* Working-tree modifications (M): 10 files
* Working-tree untracked (??): 19+ files
* Contract document diff: +508 / −8 lines vs master

The working-tree state is the post-Step-10-Direction-A + post-Step-11 + post-Step-12-planning state. The codification work that ought to have landed in master after Step 8 closure exists only in the working tree.

---

## §3. Target end-state

After lineage normalization completes, the project state shall be:

| dimension | target |
|---|---|
| Master HEAD | "post-everything substrate" — Step 8 + Step 9 + Step 10 Direction A + Step 11 framework + Step 12 planning all landed |
| Working tree | clean (`git status --porcelain` returns empty) |
| Branch count | `master` only (no intermediate branches; landing happens directly on master per §17) |
| Artifact content | byte-identical to current working-tree content (no edits during landing; only staging + commits) |
| Replay baseline | the Step 10 Direction A validated baseline still PASS on the new master HEAD |
| Audit trail | each landing commit's message documents what landed (per Step 8 precedent's commit message richness) |
| Closure tags | optional `step9-closed`, `step10-direction-a-closed`, `step11-planning-complete`, `step12-planning-complete` tags applied to corresponding wave commits |

**Sub-finding 3.A.** After this target end-state, the codification branch's S1 creation (per baseline-init §5) becomes safe: branch base SHA = post-everything master HEAD, working tree clean, no surprise content.

---

## §4. Landing-wave overview

The normalization proceeds in **4 sequential landing waves** (analogous to but distinct from Step 12's 6 codification waves):

| wave | label | scope | wave commit count (range) |
|---|---|---|---|
| **W1** | Step 9 closure landing | Step 9 runtime + Step 9 contract additions + Step 9 tests + Step 9 analysis docs | 1–8 (see §6 / §11) |
| **W2** | Step 10 Direction A closure landing | Step 10 runtime delta + Step 10 contract additions + Step 10 tests + Step 10 analysis docs | 1–6 (see §7 / §11) |
| **W3** | Step 11 analytical pipeline landing | 8 Step 11 framework docs (docs-only; no runtime, no contract) | 1 |
| **W4** | Step 12 planning framework landing | 8 Step 12 docs (4 Layer plans + admissibility + baseline-init + readiness-review + this lineage plan) (docs-only) | 1 |

**Sub-finding 4.A.** Waves are strictly sequential: W1 → W2 → W3 → W4. No parallelism. Each wave's content depends on or follows from prior waves' content.

**Sub-finding 4.B.** Total landing-commit count: minimum 4 (one per wave); maximum 16 if W1 and W2 are decomposed per-phase. Pragmatic range: 4–6 commits total.

---

## §5. File-to-wave attribution

Per inspection of working-tree files and the project memory state:

### §5.1 Wave W1 — Step 9 attribution

**Runtime (subset of working-tree runtime; see §12 separation challenge):**
* `isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/__init__.py` (partially Step 9)
* `isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/graph.py` (partially Step 9)
* `isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py` (partially Step 9)
* `isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/snapshot.py` (partially Step 9)
* `isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/envelopes.py` (new module, Step 9 per filename context)
* `isaac_factory/extensions/cell_authoring/cell_authoring/tasks/definitions.py` (partially Step 9)
* `isaac_factory/extensions/cell_authoring/cell_authoring/tasks/executor.py` (partially Step 9)
* `tools/check_session_replay_identity.py` (Step 9 P7 replay comparator per filename context)

**Contract (subset of contract diff; see §11 separation challenge):**
* Step 9 portion of `docs/phase_4b_deterministic_semantics.md` — D-FAULT-1 through D-FAULT-14 introductions; §13 D-FAULT contract; D-FAULT-15 rows 1–18

**Tests:**
* `isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step9_p4_fault_contract.py` (untracked, Step 9 P4)
* `isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step9_p7_replay_comparator.py` (untracked, Step 9 P7)
* `isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step8_p6_replay_identity.py` (modified — likely Step 9 refinement to Step 8 P6 test)

**Scripts:**
* `scripts/launch_phase_5_two_node.py` (modified — Step 9 P5 "two-node runtime exercise on Isaac Sim" per Step 8 commit message convention)
* `scripts/launch_phase_9p6_step9_abort.py` (untracked — Step 9 P6 abort launcher per filename)

**Docs:**
* `docs/phase_4b_step9_failure_semantics_analysis.md` (untracked — Step 9 analysis)

### §5.2 Wave W2 — Step 10 Direction A attribution

**Runtime (delta on top of W1):**
* Step 10 portions of the same orchestration/tasks files modified in W1 — specifically, the D-EXEC-13 sub-Phase-E interruption surface + D-FAULT-1b executor-reported interruption handling

**Contract (delta on top of W1):**
* Step 10 portion of `docs/phase_4b_deterministic_semantics.md` — §1.5 (Sub-Phase-E interruption surface) + D-EXEC-13 a/b/c/d + D-FAULT-1b + D-FAULT-3b + D-FAULT-12c + D-FAULT-15 rows 19–30

**Tests:**
* `isaac_factory/extensions/asset_validator/tests/unit/test_cell_01_phase_4b_step10_p3_direction_a_contract.py` (untracked — Step 10 P3)

**Scripts:**
* `scripts/launch_phase_10_p6_isaac.py` (untracked — Step 10 P6 launcher)
* `scripts/diag_stream_minimal.py` (untracked — diagnostic; possibly Step 10)
* `scripts/diag_stream_smoke.py` (untracked — diagnostic; possibly Step 10)

**Docs:**
* `docs/phase_4b_step10_candidates_analysis.md` (untracked)
* `docs/phase_4b_step10_direction_a_analysis.md` (untracked)
* `docs/phase_4b_step10_p6_isaac_acceptance.md` (untracked)

### §5.3 Wave W3 — Step 11 attribution

**Docs (all untracked):**
* `docs/phase_4b_step11_live_ingress_analysis.md`
* `docs/phase_4b_step11_admissibility_framework.md`
* `docs/phase_4b_step11_f58_paused_analysis.md`
* `docs/phase_4b_step11_f59_manual_advance_analysis.md`
* `docs/phase_4b_step11_closure_verification.md`
* `docs/phase_4b_step11_codification_plan.md`
* `docs/phase_4b_step11_meta_audit.md`
* `docs/phase_4b_step11_extraction_plan.md`

No runtime, no contract, no tests. Pure analytical docs.

### §5.4 Wave W4 — Step 12 planning attribution

**Docs (all untracked):**
* `docs/phase_4b_step12_authoring_mechanics_plan.md`
* `docs/phase_4b_step12_validation_plan.md`
* `docs/phase_4b_step12_review_ergonomics_plan.md`
* `docs/phase_4b_step12_governance_plan.md`
* `docs/phase_4b_step12_admissibility_evaluation.md`
* `docs/phase_4b_step12_baseline_initialization_plan.md`
* `docs/phase_4b_step12_execution_readiness_review.md`
* `docs/phase_4b_step12_lineage_normalization_plan.md` (this doc itself)

No runtime, no contract, no tests. Pure planning docs.

### §5.5 Attribution uncertainty notice

For files attributed "partially Step 9 / partially Step 10" (the runtime files in §5.1), the precise per-step decomposition requires inspection of the actual diffs at landing time. See §11 + §12 for the separation strategy.

If decomposition proves infeasible at landing time, the fallback is the combined W1+W2 commit option (per §11.3); this loses per-step granularity but preserves correctness.

---

## §6. Wave W1 protocol — Step 9 closure landing

**Preconditions.**

1. Working tree contains all Step 9 + Step 10 + Step 11 + Step 12 content (current state).
2. Master HEAD is at `cb95a9a` (Step 8 P6 closure).
3. No prior W1 commit attempt exists on master.

**Activity (Decision-Owner executes; this plan specifies sequence):**

1. **Decompose**: separate Step 9 content from Step 10 content in shared files (runtime + contract) per §11 + §12.
2. **Stage**: `git add` only the Step 9 attributed files (per §5.1) + the Step 9 portion of shared files.
3. **Verify staging**: `git diff --cached` matches expected Step 9 content; no Step 10 content staged.
4. **Commit**: single commit "Phase 4B Step 9 — D-FAULT deterministic failure semantics + runtime + comparator" (or per-phase decomposition per §11.1 if Option A chosen).
5. **Post-commit verify**: `git status --porcelain` shows only Step 10/11/12 content remaining (the W1 content is now in history); replay-test invariant against Step 9 baseline (or accept that Step 10 baseline applies post-W2; see §13 + §21).

**Output state.**

| | pre-W1 | post-W1 |
|---|---|---|
| Master HEAD | `cb95a9a` | `<W1-SHA>` |
| Master HEAD subject | "Phase 4B Step 8 / Phase 6 — ... STEP 8 CLOSURE" | "Phase 4B Step 9 — D-FAULT closure ..." |
| Contract has Step 9 D-FAULT additions | no | yes |
| Contract has Step 10 D-EXEC-13 additions | no | no (still in working tree) |
| Step 9 runtime in git | no | yes |
| Step 10 runtime delta in git | no | no (still in working tree) |
| Step 11/12 docs in git | no | no (still untracked) |

**Optional tag.** Apply `step9-closed` tag at `<W1-SHA>`.

**Gate.** W1 complete iff: commit succeeds, working-tree state matches "Step 10/11/12 content remaining," and (if runtime touched) post-commit replay test PASS (or accepted-deferred per §13).

---

## §7. Wave W2 protocol — Step 10 Direction A closure landing

**Preconditions.**

1. W1 complete; master HEAD = `<W1-SHA>`.
2. Working tree contains Step 10 runtime delta + Step 10 contract additions + Step 10 tests + Step 10 docs + Step 11 docs + Step 12 docs.

**Activity:**

1. **Stage**: `git add` only the Step 10 attributed files (per §5.2) + Step 10 portion of shared files (now reduced to the post-W1 delta).
2. **Verify staging**: `git diff --cached` matches expected Step 10 content; no Step 11/12 content staged.
3. **Commit**: single commit "Phase 4B Step 10 Direction A — D-EXEC-13 sub-Phase-E interruption + D-FAULT-1b/3b/12c + 12-cycle Isaac validation" (or per-phase decomposition).
4. **Post-commit verify**: `git status --porcelain` shows only Step 11 + Step 12 content; **MUST run V18 replay test against the validated Step 10 baseline; MUST PASS** (this is the critical replay-preservation checkpoint; see §13).

**Output state.**

| | pre-W2 | post-W2 |
|---|---|---|
| Master HEAD | `<W1-SHA>` | `<W2-SHA>` |
| Contract has Step 10 D-EXEC-13 additions | no | yes |
| Step 10 runtime in git | no | yes |
| Step 10 replay baseline byte-stable | n/a | YES (V18 PASS) |
| Step 11/12 docs in git | no | no |

**Optional tag.** Apply `step10-direction-a-closed` tag at `<W2-SHA>`.

**Gate.** W2 complete iff: commit succeeds, V18 PASS, working-tree state matches "Step 11 + Step 12 content remaining."

---

## §8. Wave W3 protocol — Step 11 analytical pipeline landing

**Preconditions.** W2 complete; master HEAD = `<W2-SHA>`.

**Activity:**

1. **Stage**: `git add` the 8 Step 11 docs per §5.3.
2. **Verify staging**: only `docs/phase_4b_step11_*.md` files staged; no runtime, no contract, no tests.
3. **Commit**: single commit "docs: Phase 4B Step 11 — live ingress analytical pipeline (8 framework artifacts)".
4. **Post-commit verify**: `git status --porcelain` shows only Step 12 docs remaining.

**Output state.**

| | pre-W3 | post-W3 |
|---|---|---|
| Master HEAD | `<W2-SHA>` | `<W3-SHA>` |
| 8 Step 11 docs in git | no | yes |
| Step 12 docs in git | no | no |
| Runtime / contract unchanged | yes | yes |

**Optional tag.** Apply `step11-planning-complete` tag at `<W3-SHA>`.

**Gate.** W3 complete iff: commit succeeds, working-tree shows only Step 12 docs. V18 not required (no runtime/contract change).

---

## §9. Wave W4 protocol — Step 12 planning framework landing

**Preconditions.** W3 complete; master HEAD = `<W3-SHA>`.

**Activity:**

1. **Stage**: `git add` the 8 Step 12 docs per §5.4.
2. **Verify staging**: only `docs/phase_4b_step12_*.md` files staged.
3. **Commit**: single commit "docs: Phase 4B Step 12 — pre-authoring transition planning framework (4 Layer plans + admissibility evaluation + baseline-init plan + execution-readiness review + lineage normalization plan)".
4. **Post-commit verify**: `git status --porcelain` returns empty (working tree fully clean).

**Output state.**

| | pre-W4 | post-W4 |
|---|---|---|
| Master HEAD | `<W3-SHA>` | `<W4-SHA>` |
| 8 Step 12 docs in git | no | yes |
| Working tree clean | no | YES |
| Master ready for bootstrap S0 | no | YES |

**Optional tag.** Apply `step12-planning-complete` tag at `<W4-SHA>`.

**Gate.** W4 complete iff: commit succeeds, working tree clean. V18 not required (no runtime/contract change). This is the **final landing wave**; on successful W4 completion, master HEAD is the "post-everything substrate" state.

---

## §10. Per-wave landing protocol (formal)

For each wave W1–W4:

```
Stage 1: Verify preconditions (prior wave complete; working-tree state as expected)
Stage 2: Decompose (W1/W2 only — separate this wave's content from later waves'; see §11, §12)
Stage 3: Stage (git add the wave's files; verify no over-staging or under-staging)
Stage 4: Commit (single closure-style commit with rich message; see §18)
Stage 5: Post-commit verify (git status; replay test if runtime touched; tag if desired)
Stage 6: Confirm wave complete; proceed to next wave
```

**Failure at any stage.** Use additive recovery (`git revert <wave-commit-sha>`) — NOT `git reset --hard`, NOT amend, NOT force-push. Re-attempt after correction. This preserves BRANCH-LINEARITY and AUDIT-COMPLETENESS even during normalization.

---

## §11. Contract-diff separation challenge

The contract document has a single working-tree state combining Step 9 + Step 10 additions on top of Step 8 closure. Cleanly separating into per-step commits requires deciding which contract content belongs to which step.

### §11.1 Option A — full per-phase decomposition (mirrors Step 8 precedent)

Decompose the contract diff into per-phase chunks matching Step 9's 8 phases and Step 10's 6 phases. W1 becomes 8 commits; W2 becomes 6 commits.

* **Pro**: cleanest possible audit; matches Step 8 Phase 1–6 precedent
* **Con**: requires deep code/contract archaeology to reconstruct what each phase added; error-prone if no per-phase records exist

### §11.2 Option B — combined Step 9 + Step 10 commit

Single commit covering both Step 9 and Step 10 contract additions. W1 and W2 collapse into one wave.

* **Pro**: avoids contract-diff decomposition entirely
* **Con**: loses per-step granularity; one commit's revert would unwind both Step 9 and Step 10

### §11.3 Option C (RECOMMENDED) — per-step decomposition

Two commits: W1 contains Step 9 contract additions only; W2 contains Step 10 contract additions only. Contract content of W1's commit = post-Step-8 contract + Step 9 §13 D-FAULT introductions; contract content of W2's commit = additionally + §1.5 Sub-Phase-E + D-EXEC-13 + D-FAULT-1b + D-FAULT-3b + D-FAULT-12c + D-FAULT-15 rows 19–30.

* **Pro**: matches the Step boundary structure; each commit independently reflects a Step's substrate state
* **Con**: requires the Decision-Owner / contributor to identify "Step 9 only" contract content vs Step 10 additions

**Implementation hint for Option C.** At W1 commit time, the contributor:
1. Identifies the Step 10 additions in the working-tree contract (D-EXEC-13 family, D-FAULT-1b, D-FAULT-3b, D-FAULT-12c, §1.5, D-FAULT-15 rows 19–30).
2. Temporarily removes them from the staged contract (so staged = Step 8 + Step 9 only).
3. Commits W1.
4. Restores the Step 10 additions (they're still in the working tree; they were only un-staged, not deleted from working tree).
5. At W2: stages the Step 10 additions; commits W2.

This is operationally straightforward git work; no rebasing or amending. Both commits are additive vs their predecessor.

### §11.4 Recommendation

**Option C is recommended.** It matches the Step boundary structure, preserves per-step granularity, and is operationally simple. Options A and B are fallbacks if the Decision-Owner determines Option C is infeasible.

---

## §12. Runtime-diff separation challenge

Similar to §11 for runtime files. The shared runtime files (`graph.py`, `session.py`, `snapshot.py`, etc.) have Step 9 + Step 10 changes intermixed.

### §12.1 Option A — full per-phase decomposition

Identical pros/cons to §11.1.

### §12.2 Option B — combined Step 9 + Step 10 commit

Identical to §11.2.

### §12.3 Option C — per-step decomposition

Two commits split runtime changes by Step. Requires identifying which runtime changes serve Step 9 (D-FAULT runtime: failure handling, abort propagation) vs Step 10 (D-EXEC-13 runtime: sub-Phase-E interruption predicate consultation, ticks_consumed tracking, segment-boundary semantics).

* **Pro**: clean per-step substrate
* **Con**: requires runtime archaeology

### §12.4 Coupling consideration

Runtime decomposition is coupled to contract decomposition: if Option C is chosen for contract (§11), Option C should be chosen for runtime (§12), so that each commit's runtime + contract are consistent. Mismatched decomposition (e.g., Option C for contract but Option B for runtime) creates a commit boundary where the contract documents clauses that the runtime doesn't yet implement, or vice versa.

### §12.5 Recommendation

**Match the contract option.** If §11.4's Option C is chosen, use Option C here too. If Option B is chosen (combined W1+W2), use Option B for runtime as well.

---

## §13. Replay-baseline preservation during landing

The validated replay baseline (Step 10 Direction A: "12/12 cycles bytewise replay-identical under --reopen-stage-between-cycles") was established with the runtime in its current working-tree state. This baseline corresponds to:

* Runtime: complete working-tree state of orchestration + tasks + tools files
* Contract: complete working-tree state of `phase_4b_deterministic_semantics.md`

**Per-wave replay-baseline behavior:**

| wave | runtime state at post-commit master HEAD | replay baseline expected |
|---|---|---|
| Pre-W1 | Step 8 runtime | Step 8 baseline (`cb95a9a`'s validated state) |
| Post-W1 | Step 9 runtime (Option C) OR combined Step 9+10 runtime (Option B) | Step 9-only baseline (Option C) OR Step 10 baseline (Option B). **NEW baseline either way.** |
| Post-W2 | Combined Step 9 + Step 10 runtime | Step 10 baseline (the current validated baseline). MUST PASS V18. |
| Post-W3 | unchanged from W2 | Step 10 baseline. V18 not required. |
| Post-W4 | unchanged from W2 | Step 10 baseline. V18 not required. |

**Critical assertion.** Post-W2 master HEAD must produce the validated Step 10 replay baseline byte-identically. This is the V18 PASS at §7's gate. Failure here indicates either decomposition error (W1 captured runtime that should be in W2 or vice versa) or genuine replay regression (investigate root cause).

**Post-W1 replay test.** If Option C is used, W1's master HEAD has Step 9 runtime only. A separate "Step 9 replay baseline" is needed. If no such baseline exists historically, two acceptable paths:

* **Capture a new Step 9 baseline post-W1** (run cycle suite, record events.jsonl SHA-256). This becomes the canonical Step 9 baseline going forward.
* **Defer V18 PASS to post-W2** (acknowledge that the canonical replay baseline is the Step 10 one). Document this in the W1 commit message.

**Sub-finding 13.A.** Replay-baseline preservation requires W2's post-commit V18 to PASS against the current Step 10 baseline. W1's V18 is optional (can be deferred to post-W2 in Option C).

---

## §14. Working-tree contamination risk analysis

| risk | mitigation |
|---|---|
| W1 commit stages too much (includes Step 10 content) | Stage 3 verification (§10) confirms `git diff --cached` matches expected Step 9 content only |
| W1 commit stages too little (Step 9 content remains in working tree post-commit) | Stage 5 verification confirms working tree shows "only Step 10/11/12 remaining" |
| W2 onwards inherits orphan changes from W1's contamination | per-wave Stage 1 precondition verifies working-tree state matches expected |
| Untracked artifacts accidentally staged in W1/W2 | use explicit `git add <files>` rather than `git add .` or `git add -A`; verify with `git diff --cached` |

**Sub-finding 14.A.** Contamination risk is bounded by per-wave staging discipline + verification gates.

---

## §15. Partial-commit hazard analysis

A "partial commit" — staging some files but not others within a wave's intended scope — would leave master in an inconsistent state. Specifically:

* Partial W1 (e.g., commits Step 9 runtime but not Step 9 contract): the post-W1 master has runtime implementing clauses not documented in the contract. Inconsistent.
* Partial W2 (e.g., commits Step 10 contract but not Step 10 runtime): the post-W2 master has contract documenting clauses not yet implemented. Inconsistent + likely V18 FAIL.
* Partial W3/W4 (some docs but not others): less severe; docs only; can be completed by an additive follow-up commit if discovered post-merge.

**Mitigation:** Per-wave Stage 3 (Verify staging) explicitly checks the staged set matches the wave's planned content (per §5). The Decision-Owner reviews `git diff --cached` before commit.

**Sub-finding 15.A.** Partial-commit hazard is mitigated by explicit staging verification. Failure to verify is the primary risk.

---

## §16. Untracked-artifact landing policy

All currently-untracked files become tracked at their respective wave commit:

| wave | untracked files newly tracked |
|---|---|
| W1 | Step 9 tests (`test_cell_01_phase_4b_step9_p4_fault_contract.py`, `test_cell_01_phase_4b_step9_p7_replay_comparator.py`), `envelopes.py`, Step 9 launcher script, Step 9 analysis doc |
| W2 | Step 10 tests (`test_cell_01_phase_4b_step10_p3_direction_a_contract.py`), Step 10 launchers + diag scripts, 3 Step 10 docs |
| W3 | 8 Step 11 docs |
| W4 | 8 Step 12 docs |

**Sub-finding 16.A.** All current untracked files map to a wave. No untracked file is "ownerless"; every untracked file lands somewhere.

---

## §17. Branch-vs-master landing strategy

**Decision: land directly on master.** Rationale:

| consideration | rationale |
|---|---|
| Step 8 precedent | Phase 1–6 landed directly on master (no intermediate branch) |
| Audit simplicity | one linear history; no merge commits from intermediate branches |
| Effort | direct landing requires 4–14 commits; intermediate-branch landing adds 4 merge commits + branch creation overhead |
| Risk | direct landing exposes intermediate-wave states on master (acceptable — master is the canonical history) vs intermediate-branch landing isolates risk but adds complexity |

**Alternative (rejected):** Create a `lineage-normalization` branch; land waves on it; merge to master at end. This would add merge commits and complicate the linear history; rejected for symmetry with Step 8 precedent.

**Sub-finding 17.A.** Direct landing on master is the Step 8-precedent-consistent choice. The codification branch for Step 12 (created later at bootstrap S1) is a SEPARATE structure unrelated to lineage normalization.

---

## §18. Commit-message convention

Following Step 8 precedent (e.g., `cb95a9a` = "Phase 4B Step 8 / Phase 6 — deterministic replay verification + STEP 8 CLOSURE"):

| wave | recommended commit message form |
|---|---|
| W1 | `Phase 4B Step 9 — D-FAULT deterministic failure semantics contract + runtime + comparator + Isaac validation (STEP 9 CLOSURE, 8 phases)` |
| W2 | `Phase 4B Step 10 Direction A — D-EXEC-13 sub-Phase-E interruption + D-FAULT-1b/3b/12c + 12-cycle Isaac replay validation (STEP 10 DIRECTION A CLOSURE, 6 phases)` |
| W3 | `docs: Phase 4B Step 11 — live ingress analytical pipeline (live-ingress + admissibility framework + F58 + F59 + closure verification + codification plan + meta-audit + extraction plan)` |
| W4 | `docs: Phase 4B Step 12 — pre-authoring transition planning framework (4 Layer plans + admissibility evaluation + baseline-init plan + execution-readiness review + lineage normalization plan)` |

**Per-commit body** should include:
* List of phases included (W1, W2) per memory entries
* Reference to the closure-verification memory (e.g., `project_phase_4b_step9.md`)
* For W1/W2: V18 result (PASS) at post-commit verification
* For W3/W4: confirmation that no runtime / contract was modified

**Sub-finding 18.A.** Commit messages serve as the per-wave audit-trace for lineage normalization (no separate audit artifacts are produced; this is pre-bootstrap, and the bootstrap audit-trail directory doesn't exist yet).

---

## §19. Commit-dependency DAG

```
master @ cb95a9a (Step 8 P6 closure)
        │
        ▼
W1: Step 9 closure
        │
        ▼
W2: Step 10 Direction A closure
        │
        ▼
W3: Step 11 analytical pipeline (docs)
        │
        ▼
W4: Step 12 planning framework (docs)
        │
        ▼
master @ <W4-SHA> = "post-everything substrate" (ready for bootstrap S0)
```

Strict linear; no parallel waves; no skipping; no reordering.

**Sub-finding 19.A.** The dependency DAG matches the Step boundary semantics: Step 10 builds on Step 9; Step 11 docs reference Step 9+10 outcomes; Step 12 planning references Step 11 framework.

---

## §20. Safe landing order

**Order: W1 → W2 → W3 → W4. Strictly sequential.**

Rationale:

| ordering choice | rationale |
|---|---|
| W1 before W2 | Step 9 closure precedes Step 10 (Step 10 builds on Step 9 D-FAULT scaffolding) |
| W2 before W3 | Step 11 docs reference D-FAULT and D-EXEC-13 clauses introduced in W1+W2; W3 references would be unresolved if landed first |
| W3 before W4 | Step 12 docs reference Step 11 framework (per Step 12 codification plan's reliance on Step 11 extraction plan); W4 references would be unresolved if landed first |

**Sub-finding 20.A.** Reverse ordering or skipping breaks reference chains in commit content. Strict W1→W2→W3→W4 preserves causality at every commit boundary.

---

## §21. Replay-regression revalidation cadence

| event | V18 invocation | gating |
|---|---|---|
| Post-W1 | optional (Option C); if Option B, V18 covers full Step 10 baseline | optional-PASS or deferred-to-W2 |
| Post-W2 | **MUST run V18 against current Step 10 baseline; MUST PASS** | BLOCKING |
| Post-W3 | not required (docs-only commit) | n/a |
| Post-W4 | not required (docs-only commit) | n/a |
| Pre-bootstrap-S0 (final check) | re-run V18 on master HEAD as confirmation | recommended |

**Total BLOCKING V18 invocations during normalization: 1** (post-W2).
**Total RECOMMENDED V18 invocations: 2** (optional post-W1; recommended pre-S0).

**Sub-finding 21.A.** Normalization V18 cadence is lighter than bootstrap V18 cadence (8 BLOCKING per baseline-init). Justified because normalization doesn't introduce new content — it only records existing working-tree content into git history.

---

## §22. Post-landing verification checkpoints

After each wave:

| wave | checkpoint |
|---|---|
| W1 | `git log -1` shows W1 commit; `git status` shows "Step 10/11/12 content remaining" |
| W2 | `git log -1` shows W2 commit; `git status` shows "Step 11/12 content remaining"; V18 PASS |
| W3 | `git log -1` shows W3 commit; `git status` shows "Step 12 content remaining" |
| W4 | `git log -1` shows W4 commit; `git status --porcelain` returns empty; master HEAD is post-everything substrate |

**Final master-ready-for-S0 verification** (after W4):

1. `git status --porcelain` returns empty.
2. `git log --oneline -5` shows: W4 commit, W3 commit, W2 commit, W1 commit, `cb95a9a`.
3. `git diff cb95a9a HEAD` shows the aggregate addition (Step 9 + Step 10 + Step 11 + Step 12 planning); zero deletions from `cb95a9a`'s contract content (additive throughout).
4. V18 final dry-run PASS against Step 10 baseline.
5. All Step 11 + Step 12 planning docs present in `docs/` directory.

---

## §23. Contract/runtime synchronization guarantee

Each W1, W2 closure commit lands BOTH the contract additions AND the runtime changes for that step together. This guarantees:

* At W1's commit boundary: contract documents Step 9 D-FAULT clauses; runtime implements Step 9 D-FAULT behavior. Consistent.
* At W2's commit boundary: contract documents Step 9 + Step 10 clauses; runtime implements both. Consistent.

This avoids "runtime ahead of contract" (runtime implements a clause not yet documented) or "contract ahead of runtime" (contract documents a clause not yet implemented).

**Sub-finding 23.A.** Synchronization is achieved by co-committing runtime + contract per Step. Splitting them across commits would create transient inconsistency windows; Option C of §11+§12 specifically avoids this.

---

## §24. Rollback strategy during landing

If a wave commit reveals a defect post-commit (e.g., W2 V18 FAILs):

**FORBIDDEN approaches:**
* `git reset --hard <prior-SHA>` — violates BRANCH-LINEARITY (rewrites history)
* `git commit --amend` — violates no-amend (Layer A §16 + Layer D §14 extended)
* Force-push — violates BRANCH-LINEARITY
* Squash on retry — violates additive-only

**ALLOWED approaches:**
* `git revert <wave-commit-SHA>` — produces an additive inverse commit; preserves history
* After revert: correct the underlying issue; re-stage; commit a NEW wave commit (preserves audit trail of failed attempt + revert + corrected re-attempt)

**Three-commit audit pattern for failed wave recovery:**

```
W_N (original wave attempt)
W_N_revert (inverse commit; produced by `git revert`)
W_N_v2 (corrected re-attempt)
```

Same pattern as Layer A §13 reversibility + Layer D §16 re-authoring governance. Lineage normalization uses the same additive-recovery discipline.

**Sub-finding 24.A.** Rollback discipline during normalization mirrors the bootstrap-time discipline. No special pre-bootstrap exemptions.

---

## §25. Landing-phase auditability

Per §18 commit message convention: each wave commit's message documents:

* Wave label (W1–W4)
* Step boundary and phase count
* Files committed (high-level summary)
* V18 result (for W1/W2)
* Reference to memory entries describing the work

No separate audit-trace artifacts are produced for lineage normalization (the bootstrap audit-trace directory at `docs/step12_audit_traces/` is created later by bootstrap S3, not by normalization).

**Sub-finding 25.A.** Landing-phase auditability is achieved through commit-message content. Each wave commit is a durable record of what landed.

---

## §26. Lineage continuity preservation

After normalization, master history reads:

```
<W4-SHA>  docs: Phase 4B Step 12 — pre-authoring transition planning framework ...
<W3-SHA>  docs: Phase 4B Step 11 — live ingress analytical pipeline ...
<W2-SHA>  Phase 4B Step 10 Direction A — D-EXEC-13 sub-Phase-E interruption ...
<W1-SHA>  Phase 4B Step 9 — D-FAULT deterministic failure semantics ...
cb95a9a   Phase 4B Step 8 / Phase 6 — deterministic replay verification + STEP 8 CLOSURE
eb8d005   Phase 4B Step 8 / Phase 5 — two-node runtime exercise on Isaac Sim
...
```

Linear chain. Each commit references its predecessor by parent-SHA (git's intrinsic structure). No reordering, no rebasing.

**Optional tags** at each wave for navigation:
* `step9-closed` → `<W1-SHA>`
* `step10-direction-a-closed` → `<W2-SHA>`
* `step11-planning-complete` → `<W3-SHA>`
* `step12-planning-complete` → `<W4-SHA>`

Tags are additive; tag deletion is FORBIDDEN per BRANCH-LINEARITY transitivity.

---

## §27. Closure-proof preservation

Step 9 and Step 10 Direction A closure proofs live in:

| proof element | location |
|---|---|
| Per-step closure narrative | project memory entries (`project_phase_4b_step9.md`, `project_phase_4b_step10.md`) — already present |
| Per-step analytical docs | Step 9: `docs/phase_4b_step9_failure_semantics_analysis.md` (in W1); Step 10: 3 docs in W2 |
| Per-step tests | per §5.1 / §5.2 |
| Per-step closure-verification | implicit in commit message + memory; no separate doc (precedent: Step 8 had no separate closure doc either; closure was implicit in `cb95a9a`'s message) |
| Replay baseline result | V18 PASS at post-W2 commit |

**No closure proofs are lost during normalization.** All evidence is preserved either in committed content or in commit-message references to memory entries.

---

## §28. Final "master-ready-for-S0" criteria

After successful W1 → W2 → W3 → W4, master is ready for bootstrap S0 iff ALL of:

| # | criterion | verification |
|---|---|---|
| 1 | Master HEAD = `<W4-SHA>` | `git log -1` |
| 2 | Working tree clean | `git status --porcelain` returns empty |
| 3 | Linear history: cb95a9a → W1 → W2 → W3 → W4 | `git log --oneline cb95a9a..HEAD` shows exactly 4 commits |
| 4 | No force-push or amend in normalization history | git's intrinsic structure preserves this; reflog inspection confirms |
| 5 | V18 PASS on master HEAD against Step 10 baseline | `tools/check_session_replay_identity.py` run |
| 6 | Contract document present and at post-Step-10 form | grep for D-EXEC-13, D-FAULT-1b, D-CONT-6 confirms |
| 7 | All Step 11 docs present in `docs/` | `ls docs/phase_4b_step11_*.md` returns 8 files |
| 8 | All Step 12 planning docs present in `docs/` | `ls docs/phase_4b_step12_*.md` returns 8 files |
| 9 | Decision-Owner attests master is ready | explicit attestation (per baseline-init S0 pattern) |

**Upon all 9 ✓:** Bootstrap S0 may begin. The baseline-init plan §5's S1 precondition ("Current master HEAD is in expected state") is now satisfied.

**Cross-reference to readiness review R1.** This §28 verification is the operational answer to R1's recommended S8 check #15 ("Master HEAD has been confirmed at the expected post-Step-N-closure SHA before S0/S1"). If R1 is adopted as a baseline-init plan amendment, the S8 check would reference this §28 verification.

---

## §29. Lineage-normalization vocabulary

Lineage normalization introduces several operational terms; none enter the normative contract:

| term | meaning | scope |
|---|---|---|
| Landing wave | one of W1–W4 in the normalization sequence | this plan |
| Wave commit | the single commit (or set of per-phase commits) landing a wave's content | this plan |
| Per-step closure commit | a wave commit specifically for Step 9 or Step 10 closure | this plan |
| Contract-diff separation | the operational act of decomposing the working-tree contract diff into per-step chunks | this plan |
| Runtime-diff separation | analogous for runtime files | this plan |
| Post-everything substrate | the master HEAD state after W4, ready for bootstrap S0 | this plan |

None receive clause IDs.

---

## §30. Preserved invariants under lineage normalization

| invariant | preservation mechanism |
|---|---|
| replay-authoritative truth | V18 PASS at W2 confirms runtime + contract produce validated baseline |
| append-only causality | all wave commits are additive; revert recovery is additive; no rebase, no force-push, no amend |
| authority singularity | normalization does not modify clause authority structure; substrate authorities preserved |
| orchestration_tick supremacy | substrate unchanged in any clause sense; just records existing state |
| deterministic interruption boundaries | preserved by D-EXEC-13 landing in W2 |
| Phase-A-only observability | preserved (no contract content alteration) |
| contradiction preservation | preserved (no clause modification) |
| transport independence | preserved (no clause modification) |
| no hidden cleanup | all working-tree content lands; nothing silently discarded |
| no wall-clock authority | normalization timestamps are descriptive only |
| no adaptive semantics | no clause adapts during normalization |
| framework/contract separation | contract changes are in W1+W2 commits; planning docs are in W3+W4; clean separation |
| additive-only mutation discipline | each wave commit is additive vs prior wave; Option C ensures per-step additivity |
| replay-preserving extraction safety | V18 PASS at W2 confirms |
| validator supremacy over reviewer intuition | no reviewer involvement; normalization is operational |
| no semantic widening authority | no clause widens during normalization; content is byte-preserved from working tree |
| no hidden override pathways | all reverts are visible commits per §24 |
| BRANCH-LINEARITY | no rebase, no force-push, no amend; revert recovery only |
| AUDIT-COMPLETENESS | each wave commit's message documents what landed |

All preserved at the normalization level.

---

## §31. Lineage-normalization planning verdict

**LINEAGE NORMALIZATION PLAN: READY.**

* 4 landing waves specified with sequential dependency DAG (§4, §19).
* File-to-wave attribution provided for all modified + untracked files (§5).
* Per-wave landing protocols (Stages 1–6) defined (§10).
* Contract-diff and runtime-diff separation challenges acknowledged with three options each; Option C recommended (§11, §12).
* Replay-baseline preservation cadence: 1 BLOCKING V18 (post-W2) + 2 RECOMMENDED (§13, §21).
* Working-tree contamination + partial-commit hazards bounded by per-wave staging discipline (§14, §15).
* Untracked-artifact landing policy: all currently-untracked files map to a wave (§16).
* Branch-vs-master decision: land directly on master per Step 8 precedent (§17).
* Commit-message convention specified (§18).
* Rollback discipline: additive `git revert` only; no rebase/amend/force-push/squash (§24).
* Closure-proof preservation: no proofs lost during normalization (§27).
* Final master-ready-for-S0 criteria: 9 verification points (§28).
* All 19 inherited constitutional invariants + 5 governance invariants preserved at the normalization level (§30).

The plan does NOT execute any commit. The plan does NOT create branches. The plan does NOT mutate the contract document. The plan IS the operational pathway the Decision-Owner uses to close B1 (per execution-readiness review §3) and reach the "post-everything substrate" master state required for bootstrap S0.

---

## §32. Coordination with readiness-review refinements

This plan resolves B1 from the execution-readiness review. The four readiness refinements (R1–R4) from that review are NOT addressed here:

* **R1** (S8 check #15) — to be applied as a documentation patch to baseline-init §12 + §13 after normalization. The patch itself becomes part of a future W4-supplementary docs commit or a follow-up commit.
* **R2** (multi-agent role-multiplexing protocol) — to be applied as a patch to Layer D §10 (out of this plan's scope).
* **R3** (V18 re-baseline protocol) — to be applied as a patch to Layer D §5 or baseline-init §14 (out of scope).
* **R4** (infrastructure-commit message convention) — to be applied as a patch to baseline-init §7 + §11 (out of scope).

R1–R4 may be applied as additive amendments to the relevant docs at any time before bootstrap S0; they are not blockers. The Decision-Owner may incorporate them during normalization (as part of the W4 commit, after appending the refinement text to the affected docs) or after normalization (as a separate "documentation refinement" commit on master).

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

---

**End of Step 12 lineage normalization plan.**

This plan is the operational answer to B1. Decision-Owner may execute the 4-wave landing per §6–§9 protocols. After successful W4 + §28 verification, bootstrap S0 (per baseline-init plan §4) becomes admissible.

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance](phase_4b_step11_f59_manual_advance_analysis.md), [closure verification](phase_4b_step11_closure_verification.md), [codification plan](phase_4b_step11_codification_plan.md), [meta-audit](phase_4b_step11_meta_audit.md), [extraction plan](phase_4b_step11_extraction_plan.md), [Layer A authoring mechanics](phase_4b_step12_authoring_mechanics_plan.md), [Layer B per-clause validation](phase_4b_step12_validation_plan.md), [Layer C review ergonomics](phase_4b_step12_review_ergonomics_plan.md), [Layer D cross-clause governance](phase_4b_step12_governance_plan.md), [admissibility evaluation](phase_4b_step12_admissibility_evaluation.md), [baseline initialization plan](phase_4b_step12_baseline_initialization_plan.md), [execution readiness review](phase_4b_step12_execution_readiness_review.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).

Successor: B1 closure (Decision-Owner executes W1–W4 per §6–§9); then bootstrap S0 (per baseline-init §4); then S1–S8; then AUTHORING-ACTIVE.
