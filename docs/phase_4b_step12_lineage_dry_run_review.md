# Phase 4B Step 12 — B1 Lineage-Normalization Dry-Run Review (Pre-Execution Operational Simulation)

**Status: PRE-EXECUTION DRY-RUN OPERATIONAL SIMULATION (2026-05-21).** Simulates the W1–W4 landing sequence specified in [`phase_4b_step12_lineage_normalization_plan.md`](phase_4b_step12_lineage_normalization_plan.md) against the empirical working-tree state, to identify hidden execution hazards before the Decision-Owner performs real landing commits.

Does **not** execute any commit. Does **not** stage any file. Does **not** mutate working-tree content. Does **not** create branches. Does **not** mutate the contract document. Does **not** author clauses. The deliverable is the hazard catalog + per-hazard mitigation + the verdict, derived from read-only inspection of actual diffs.

This review is a meta-meta-operational layer: it audits the lineage-normalization plan against operational reality, before the plan is executed.

---

## §1. Scope and method

The review proceeds in five analytical passes:

1. **Empirical inspection** — read actual `git diff` content for the contract document and the runtime files; quantify what is actually in the working tree.
2. **Hazard identification** — surface specific risks visible only at execution time.
3. **Per-hazard severity** — classify each hazard (BLOCKER / SAFETY-CRITICAL / OPERATIONAL).
4. **Mitigation enumeration** — for each hazard, the additional execution-time discipline that bounds the risk.
5. **Verdict** — DRY-RUN-NOT-SAFE / DRY-RUN-CONDITIONALLY-SAFE / DRY-RUN-SAFE.

The review treats the lineage normalization plan as the design document and asks: "If we executed exactly what this plan says, would the result be operationally survivable?"

---

## §2. Empirical state inspection (read-only)

Direct `git diff` and `git status` inspection at session-resume reveals:

| measurement | value | source |
|---|---|---|
| Contract diff insertions | +508 lines | `git diff --stat docs/phase_4b_deterministic_semantics.md` |
| Contract diff deletions | −8 lines | same |
| Runtime files modified | 8 files | `git diff --stat isaac_factory/.../orchestration/ isaac_factory/.../tasks/ tools/ scripts/` |
| Runtime aggregate insertions | +1916 lines | same |
| Runtime aggregate deletions | −147 lines | same |
| Largest single-file runtime diff | `session.py` (943 lines changed) | same |
| Step 11 docs in working tree | 8 (all untracked) | `ls docs/phase_4b_step11_*.md` |
| Step 12 docs in working tree | 8 (all untracked) | `ls docs/phase_4b_step12_*.md` |
| Other untracked files | scripts, tests, `envelopes.py` | `git status --porcelain` |

**Sub-finding 2.A.** The lineage normalization plan §4 estimated runtime diff size implicitly; the empirical measurement (~2,000 changed lines across 8 files; one file alone at ~950 lines) is materially larger than a "simple closure landing." This is real operational weight, not theoretical.

**Sub-finding 2.B.** The contract diff has 8 deletion lines — NOT pure-additive at the line level. These are in-place modifications, not new insertions.

**Sub-finding 2.C.** Working-tree contains 16 Step 11/12 docs (8 + 8). Matches the plan's §5.3 + §5.4 expectations.

---

## §3. Contract-diff structural inspection

Sampling the contract diff reveals at least four classes of in-place modification embedded in the Step 9 + Step 10 work:

| modification class | example location | step attribution |
|---|---|---|
| **Section heading renumbering** | `### 1.5 Non-goals` → `### 1.6 Non-goals` (because new `### 1.5 Sub-Phase-E interruption surface` inserted) | Step 10 |
| **Open-extension text update** | §11 item 4 text changed from "Phase 4B step 9 will surface and pin this" → "Pinned in §13 D-FAULT (D-FAULT-3, D-FAULT-3a, D-FAULT-4, D-FAULT-7) — sibling-tolerant default..." | Step 9 (Step 9 closure changed the cross-reference) |
| **Authoritative-set list expansion** | `* **session orchestration sets** — `_completed`, `_failed`, ...` line replaced with expanded list including `_retry_counts`, `_node_runtime` | Step 9 (retry semantics) |
| **Non-goal text refinement** | `* **No retry semantics.** ...Step 9 lands retries...` text modified to reflect post-Step-9 state | Step 9 |

**Sub-finding 3.A.** The 8 contract-deletion lines correspond to legitimate Step 9 + Step 10 in-place modifications. They are not arbitrary; each has a clear Step attribution. But they are NOT pure additions, contrary to the lineage plan §30's "additive-only mutation discipline" framing.

**Sub-finding 3.B.** The framing reconciliation: "additive-only mutation discipline" at the BRANCH level (no rebase, no force-push, no amend) is preserved — each wave commit is additive in master's commit DAG. But at the CONTENT level (line-by-line), the wave commits ARE in-place modifications because Step 9 + Step 10 work themselves contained in-place edits. The discipline-at-branch-level is preserved; the discipline-at-line-level is not (and was never required for pre-Step-12 work, which is not bound by Layer A Properties A1–A3).

---

## §4. Runtime-diff structural inspection

| file | changed lines | observation |
|---|---|---|
| `orchestration/session.py` | 943 | dominant; both Step 9 (D-FAULT failure-emission, abort propagation, session classification per D-FAULT-3) and Step 10 (D-EXEC-13 predicate consultation, ticks_consumed tracking, EXECUTION_INTERRUPTED handling) intermixed |
| `tasks/executor.py` | 232 | Step 10 D-EXEC-13 predicate-consultation infrastructure dominant; some Step 9 outcome-classification logic |
| `tools/check_session_replay_identity.py` | 371 | Step 9 P7 comparator extensions for D-FAULT replay-identity |
| `scripts/launch_phase_5_two_node.py` | 369 | Step 9 P5 two-node runtime launcher |
| `tasks/definitions.py` | 61 | Step 10 TaskDefinition.tick_budget_ticks; some Step 9 fields |
| `orchestration/graph.py` | 42 | likely Step 9 cascade-skip logic |
| `orchestration/__init__.py` | 33 | exports for new modules (envelopes.py et al.); could be either Step |
| `orchestration/snapshot.py` | 12 | Step 9 D-FAULT snapshot fields |

**Sub-finding 4.A.** **session.py is the runtime decomposition pain-point.** 943 lines of intermixed Step 9 + Step 10 changes within a single file. Per-line attribution to Step 9 vs Step 10 requires deep knowledge of which method/region serves which Step.

**Sub-finding 4.B.** Total runtime: 1,916 insertions / 147 deletions. The 147 deletions are in-place modifications to pre-Step-9 (i.e., Step 8 closure) runtime code — analogous to the contract's 8 deletions.

---

## §5. Hazard catalog

The dry-run identifies **eight execution hazards** that the lineage normalization plan does not fully address:

| ID | hazard | severity |
|---|---|---|
| **H1** | §1.5/1.6 section renumbering creates an in-place modification that "additive-only" framing didn't fully acknowledge | OPERATIONAL |
| **H2** | Option C runtime decomposition is operationally HARD (session.py 943 lines intermixed) | SAFETY-CRITICAL |
| **H3** | Multiple in-place contract modifications (§1.5 → §1.6, §11 item 4, authoritative-set list expansion, retry-semantics text) need explicit per-wave commit-message acknowledgment | OPERATIONAL |
| **H4** | Diff size — single-file 943-line diff in session.py creates substantial auditor burden | OPERATIONAL |
| **H5** | Tests depend on specific runtime behavior; if Option C runtime decomposition mis-attributes a line, tests may pass falsely at W1 while breaking semantically | SAFETY-CRITICAL |
| **H6** | New untracked files may accumulate between plan-authoring and execution (e.g., this very dry-run-review doc itself is now an untracked file in W4's scope) | OPERATIONAL |
| **H7** | Per-step attribution of shared-file changes (especially `orchestration/__init__.py`, `tasks/definitions.py`) is judgment-based without per-phase records | OPERATIONAL |
| **H8** | Tool dependency cascade — `tools/check_session_replay_identity.py` (the V18 invocation target) is itself modified +371 lines; the tool used for V18 verification is itself a landing artifact | OPERATIONAL |

Two of these (H2, H5) are SAFETY-CRITICAL: incorrect handling could produce a master state that LOOKS correct (V18 PASS, tests PASS) but is semantically wrong. The other six are OPERATIONAL: they create burden or risk of process error but cannot silently corrupt the substrate.

---

## §6. H1 — Section renumbering hazard

**Observed.** The diff contains:
```
-### 1.5 Non-goals
+### 1.5 Sub-Phase-E interruption surface  *(Step 10 Direction A extension)*
+
+[... new §1.5 content ...]
+
+### 1.6 Non-goals
```

The old `### 1.5 Non-goals` line is deleted; a new `### 1.5 Sub-Phase-E ...` is added; the old `### 1.5 Non-goals` text reappears one heading-level later as `### 1.6 Non-goals`. From git's perspective, this is a single hunk with a deletion + multiple insertions.

**Why the plan didn't acknowledge.** Lineage normalization plan §30 listed "additive-only mutation discipline" as preserved, framed at branch-level. But the W2 commit's per-line diff will show a `-### 1.5 Non-goals` line — a reviewer skimming the diff might misread this as "the §1.5 Non-goals section was removed."

**Severity.** OPERATIONAL. Real but mitigable.

**Mitigation M1.** W2 commit message MUST explicitly note: "includes section renumbering: §1.5 Non-goals → §1.6 Non-goals (due to insertion of new §1.5 Sub-Phase-E interruption surface). Pre-Step-10 §1.5 content preserved verbatim at new §1.6 position."

---

## §7. H2 — Option C runtime decomposition difficulty (SAFETY-CRITICAL)

**Observed.** The lineage plan §11.3–§11.4 recommends Option C (per-step decomposition) for both contract and runtime. The plan acknowledged §12's "runtime-diff separation challenge" but did not measure its actual difficulty.

The empirical measurement: session.py has 943 changed lines with Step 9 (D-FAULT failure handling, abort propagation, session classification) and Step 10 (D-EXEC-13 predicate consultation, ticks_consumed tracking) intermixed within methods, not segregated by region.

**Operational requirement for Option C runtime.** The Decision-Owner would need to:

1. Read every method in session.py with changes.
2. Attribute every changed line to Step 9 or Step 10 by understanding the line's purpose (D-FAULT machinery → Step 9; D-EXEC-13 machinery → Step 10; supporting infrastructure → judgment call).
3. Use selective staging (`git add -p` hunk-by-hunk) to stage Step-9-attributed hunks at W1, leaving Step-10-attributed hunks unstaged.
4. Commit W1.
5. Stage remaining Step-10-attributed hunks at W2.

**Risk surfaces:**

* **Mis-attribution.** A line might be ambiguous; the Decision-Owner might choose wrong. If a Step 10 line is staged at W1, W1's master has runtime that implements an undocumented (in W1's contract) feature; if a Step 9 line is staged at W2, W1's master is missing Step 9 functionality.
* **Hunk-boundary mismatch.** Git's hunk granularity may straddle Step 9 / Step 10 boundaries; sub-hunk splitting is possible (`git add -p` supports `s` to split) but tedious.
* **Test failure misinterpretation.** If W1's master fails Step 9 tests due to a mis-attributed line, the failure is operational debugging — but if W1's master PASSES Step 9 tests despite mis-attribution (because the missing Step 9 line is also exercised by Step 10 runtime intermixed), the failure is silent.

**Severity.** SAFETY-CRITICAL. The risk of false-PASS due to intermixed runtime is the worst-case path.

**Mitigation M2.** **REVISE the lineage normalization plan recommendation.** For runtime, fall back to **Option B (combined Step 9 + Step 10 runtime in a single commit)** or to **Option F (hybrid: per-step contract decomposition + combined runtime in W2)**.

* **Option B for runtime + contract:** single combined W1+W2 commit. Loses per-Step audit granularity but eliminates mis-attribution risk entirely.
* **Option F (RECOMMENDED):** W1 commits Step 9 contract additions + Step 9 docs + Step 9 tests (NO runtime); W2 commits all runtime (Step 9 + Step 10) + Step 10 contract additions + Step 10 docs + Step 10 tests. Trade-off: W1's master has Step 9 contract documented but no Step 9 runtime in place (a "contract-ahead-of-runtime" inconsistency window between W1 and W2 commits — typically minutes if executed in immediate succession).

Both Option B and Option F preserve all constitutional invariants. They sacrifice the per-Step runtime audit granularity that Option C aspired to provide, in exchange for elimination of the mis-attribution silent-failure path.

**Plan amendment required.** Lineage normalization plan §11.4 + §12.5 should be amended to:

```
For contract decomposition: Option C feasible (clauses are well-named; identification is tractable).
For runtime decomposition: Option B or Option F STRONGLY RECOMMENDED over Option C.
Reason: per-line Step attribution in intermixed runtime files (especially session.py at 943 lines)
is operationally hard and SAFETY-CRITICAL (mis-attribution can produce false-PASS V18/test results).
```

---

## §8. H3 — Multiple in-place contract modifications

**Observed.** The 8 contract-deletion lines correspond to four classes of in-place modification (per §3):

1. §1.5 → §1.6 renumbering (Step 10).
2. §11 item 4 text update (Step 9).
3. Authoritative-set list expansion (Step 9 — `_retry_counts`, `_node_runtime` added).
4. Non-goal text refinement re retry semantics (Step 9).

The lineage plan §3 framed everything as "additive at branch level" without enumerating these specific in-place modifications.

**Severity.** OPERATIONAL.

**Mitigation M3.** Both W1 and W2 commit messages MUST enumerate the in-place modifications they include:

* W1 commit message body: "Includes in-place modifications to existing contract content: §11 item 4 reference updated to point at §13 D-FAULT; authoritative-set list (§5.X) expanded with `_retry_counts` + `_node_runtime`; retry-semantics non-goal text refined. These are Step 9 closure modifications, not new clauses."
* W2 commit message body: "Includes in-place modifications: §1.5 Non-goals → §1.6 Non-goals (renumbering due to insertion of new §1.5 Sub-Phase-E interruption surface). Pre-Step-10 §1.5 'Non-goals' content preserved verbatim at §1.6."

This explicit documentation closes the H1+H3 ambiguity surface for future auditors.

---

## §9. H4 — Large diff size (auditor burden)

**Observed.** session.py at 943 changed lines is large for a single commit (even a closure commit). Step 8's largest single-phase commit landed similar-scale runtime changes (per `cb95a9a` content), so this is not unprecedented, but it does create operational burden.

**Severity.** OPERATIONAL.

**Mitigation M4.** Commit message body should provide structural summary of the runtime delta:

* "session.py changes: (a) D-FAULT failure-emission infrastructure per Step 9 (lines ~XXX); (b) abort propagation per D-FAULT-3 (lines ~YYY); (c) D-EXEC-13 predicate-consultation infrastructure per Step 10 (lines ~ZZZ); (d) EXECUTION_INTERRUPTED outcome handling per D-FAULT-1b (lines ~WWW)."

This is content-summary, not a comprehensive code review. It orients future auditors.

**Defense-in-depth.** This burden is INDEPENDENT of the Option C/B/F choice — even Option B (combined commit) faces it; Option C splits it into two but does not reduce total burden.

---

## §10. H5 — Test runtime dependency (SAFETY-CRITICAL)

**Observed.** Working tree includes:

* `test_cell_01_phase_4b_step8_p6_replay_identity.py` (modified — Step 9 refinement to Step 8 P6 test)
* `test_cell_01_phase_4b_step9_p4_fault_contract.py` (untracked — Step 9 P4)
* `test_cell_01_phase_4b_step9_p7_replay_comparator.py` (untracked — Step 9 P7)
* `test_cell_01_phase_4b_step10_p3_direction_a_contract.py` (untracked — Step 10 P3)

These tests exercise specific runtime behavior. Under Option C runtime decomposition:

* Post-W1 master = Step 9 runtime only (Option C ideal). Step 9 tests SHOULD pass. Step 10 tests do not exist in master yet (they're staged for W2).
* Post-W2 master = full Step 9+10 runtime + Step 10 tests added. All tests SHOULD pass.

**Failure modes under Option C mis-attribution:**

* **Silent test PASS at W1 due to intermixed runtime.** If a Step 10 line accidentally lands at W1 (mis-attribution), Step 9 tests still pass; the mis-attribution is invisible to test signals. V18 may also PASS (runtime is closer-to-Step-10 than to pure-Step-9).
* **Test FAIL at W1 due to missing Step 9 line.** Obvious failure; easier to diagnose; recoverable via revert + re-stage.
* **Spurious PASS at W2.** If W1 was mis-attributed but tests happened to pass, W2 lands additional Step 10 + remaining mis-attributed-correction; the COMBINED W1+W2 master is correct, even though W1 was wrong. The W1 wrongness is silent in the final state but visible in the per-commit content.

**Severity.** SAFETY-CRITICAL. Silent W1 mis-attribution that gets corrected at W2 produces a final-state-correct master with internally-inconsistent commit history.

**Mitigation M5.** Under Option C: run all Step 9 tests at post-W1 verification (BLOCKING). If any FAIL, revert W1 and re-attribute. Under Option B/F (recommended per H2): the SAFETY-CRITICAL risk is eliminated because runtime lands atomically.

---

## §11. H6 — Untracked file accumulation

**Observed.** The dry-run review session itself adds NEW untracked files:

* `docs/phase_4b_step12_lineage_dry_run_review.md` (this file)
* `docs/phase_4b_step12_lineage_normalization_plan.md` (prior session; already listed in W4 scope per lineage plan §5.4)
* `docs/phase_4b_step12_execution_readiness_review.md` (prior session; in W4 scope)
* Memory files in `/home/cap2/.claude/projects/-home-cap2-last/memory/` (NOT in last/ workspace; not affected)

The lineage normalization plan §5.4 listed 8 Step 12 docs at the time of authoring. Now there are 9 (with this dry-run review). Future sessions may add more before execution.

**Severity.** OPERATIONAL.

**Mitigation M6.** Immediately before W1 execution, re-run `git status --porcelain` and update the W3/W4 file-to-wave attribution. Specifically, all `docs/phase_4b_step12_*.md` files present in working tree at W4 commit time should be staged in W4, regardless of whether they were enumerated in the original lineage plan.

**Refinement.** The lineage plan should be amended to specify: "W4 stages ALL `docs/phase_4b_step12_*.md` files present at execution time (glob-based staging), not a fixed enumeration." This makes W4 robust against later-authored Step 12 planning docs.

---

## §12. H7 — Per-step attribution uncertainty for shared files

**Observed.** Several files have ambiguous Step attribution:

* `orchestration/__init__.py` (33 lines) — exports for new modules; could be Step 9 or Step 10
* `tasks/definitions.py` (61 lines) — TaskDefinition.tick_budget_ticks (Step 10) + possibly some Step 9 fields
* `scripts/diag_stream_minimal.py` / `scripts/diag_stream_smoke.py` (untracked) — no Step prefix in filename; likely Step 10 (diagnostic streams introduced for D-EXEC-13) but could be Step 9
* `envelopes.py` (untracked) — likely Step 9 (D-FAULT-9 OperatorEnvelope) but not certain

**Severity.** OPERATIONAL.

**Mitigation M7.** Under Option B/F (recommended): attribution uncertainty becomes moot — all runtime lands in W2 regardless of per-Step attribution. Under Option C: Decision-Owner inspects each shared file; consults memory entries `project_phase_4b_step9.md` and `project_phase_4b_step10.md` to attribute.

---

## §13. H8 — Tool dependency cascade

**Observed.** `tools/check_session_replay_identity.py` is the V18 invocation target. It has +371 lines in the working tree — substantial modifications.

**Cascade pattern:**

1. The Step 10 replay baseline ("12/12 cycles bytewise replay-identical") was established using the WORKING-TREE version of `check_session_replay_identity.py`.
2. At W1, if `check_session_replay_identity.py` is committed in W1 (per lineage plan §5.1 attribution — Step 9 P7 comparator), the post-W1 master has the new tool.
3. If V18 is invoked post-W1 against pure-Step-9 runtime (Option C), it uses the new tool against a runtime state that may differ from the runtime state when the baseline was established.

**Outcome:**

* Under Option C: post-W1 V18 may PASS (if the tool's new logic happens to produce the same SessionPackage SHA-256) or FAIL (more likely, since the tool was developed alongside Step 9 runtime expecting full Step 9 behavior).
* Under Option B/F: V18 runs only at post-W2 (combined runtime); tool version matches runtime version; baseline matches.

**Severity.** OPERATIONAL. Workaround exists (defer V18 to W2).

**Mitigation M8.** Under Option C: deferring V18 to W2 (as already noted in lineage plan §13.A) is acceptable; the post-W1 V18 is RECOMMENDED-not-BLOCKING. Under Option B/F: this hazard does not arise.

---

## §14. Per-hazard severity matrix

| hazard | severity | option-dependence | mitigation |
|---|---|---|---|
| H1 §1.5/1.6 renumbering | OPERATIONAL | option-independent | M1 (W2 commit message) |
| H2 Option C runtime decomposition difficulty | **SAFETY-CRITICAL** | Option C only | M2 (revise plan to Option B/F) |
| H3 In-place contract modifications | OPERATIONAL | option-independent | M3 (per-wave commit message enumeration) |
| H4 Large diff size | OPERATIONAL | option-independent | M4 (commit message structural summary) |
| H5 Test runtime dependency | **SAFETY-CRITICAL** | Option C only | M5 (under C: post-W1 test BLOCKING; under B/F: eliminated) |
| H6 Untracked file accumulation | OPERATIONAL | option-independent | M6 (glob-based W4 staging) |
| H7 Per-step attribution uncertainty | OPERATIONAL | Option C primarily | M7 (under C: inspect; under B/F: moot) |
| H8 Tool dependency cascade | OPERATIONAL | Option C primarily | M8 (under C: defer V18 to W2; under B/F: moot) |

**Observation.** Five of eight hazards (H2, H5, H7, H8, plus partial dependence in H6) are Option-C-specific. Adopting Option B or Option F eliminates or reduces the dominant safety-critical risk surface.

---

## §15. W1 staging-boundary simulation

**Under Option C (as planned):**

| element | staged | source |
|---|---|---|
| Step 9 contract additions (subset of `docs/phase_4b_deterministic_semantics.md` diff) | YES | requires per-hunk staging |
| Step 9 runtime (subset of 8 runtime files) | YES | requires per-hunk staging; **HARDEST step** |
| Step 9 tests (2 untracked + 1 modified) | YES | full-file staging |
| Step 9 launchers (scripts) | YES | full-file staging |
| Step 9 docs (1 untracked) | YES | full-file staging |
| `envelopes.py` | YES | new file; full-file staging |

**Risk:** the per-hunk staging operations (contract + runtime) are where mis-attribution silently slips through. The "stage Step 9 contract additions" task is tractable (clauses have names; D-FAULT-1 through D-FAULT-14 are clearly Step 9). The "stage Step 9 runtime" task is HARD (session.py 943 lines).

**Under Option B/F:**

| element | staged | source |
|---|---|---|
| Step 9 contract additions | YES (under F) / part of combined (under B) | clause-name attribution |
| Step 9 runtime | NO (deferred to W2) | runtime lands atomically |
| Step 9 tests | YES (full-file) | unchanged |
| Step 9 launchers | YES | unchanged |
| Step 9 docs | YES | unchanged |
| `envelopes.py` | NO (deferred to W2; classified as runtime) | runtime lands atomically |

**Simulation verdict:** Option C W1 staging is operationally delicate (per-hunk decisions on 1,000+ lines). Option F W1 staging is operationally simple (full-file staging for docs + tests + scripts; per-hunk staging only for contract clauses which are tractable). Option B W1 collapses into combined W1+W2.

---

## §16. W2 staging-boundary simulation

**Under Option C:**

| element | staged | source |
|---|---|---|
| Step 10 contract additions (D-EXEC-13 family, D-FAULT-1b, etc., +§1.5/1.6 renumbering) | YES | per-hunk |
| Step 10 runtime delta | YES | per-hunk; depends on W1 having staged Step 9 runtime correctly |
| Step 10 tests | YES | full-file |
| Step 10 launchers + diag scripts | YES | full-file |
| Step 10 docs | YES | full-file |

**Under Option F (recommended):**

| element | staged | source |
|---|---|---|
| Step 10 contract additions | YES | per-hunk (tractable) |
| **All runtime (Step 9 + Step 10)** | **YES** | full-file staging for all 8 runtime files |
| Step 10 tests | YES | full-file |
| Step 10 launchers + diag scripts | YES | full-file |
| Step 10 docs | YES | full-file |
| `envelopes.py` (deferred from W1) | YES | new file |

**Under Option B:**

| element | staged | source |
|---|---|---|
| All Step 9 + Step 10 contract additions (combined) | YES | per-hunk by Step 9 OR Step 10 attribution doesn't matter |
| All runtime | YES | full-file |
| All Step 9 + Step 10 tests + scripts + docs | YES | full-file |

**Simulation verdict:** Option B simplest (single combined commit). Option F next simplest (per-step contract; combined runtime). Option C most fragile.

---

## §17. Option-C feasibility verification (final assessment)

Per the empirical inspection, Option C's two sub-decompositions have very different difficulty:

| component | Option C feasibility |
|---|---|
| Contract decomposition (per-clause, by clause name) | TRACTABLE — Step 9 clauses (D-FAULT-1..14, D-FAULT-15 rows 1–18, §13 D-FAULT section) and Step 10 clauses (D-EXEC-13 family, D-FAULT-1b, D-FAULT-3b, D-FAULT-12c, D-FAULT-15 rows 19–30, §1.5 Sub-Phase-E) are identifiable by clause name + section heading. Decision-Owner reads contract and identifies. ~30 minutes of focused work. |
| Runtime decomposition (per-line, by Step) | NOT TRACTABLE WITHOUT ARCHAEOLOGY — session.py 943 lines, intermixed by method, no per-phase records. Decision-Owner would need deep knowledge of which line serves which Step's behavioral semantics. Hours-to-days of focused work; high error risk. |

**Conclusion.** Option C is feasible for contract; impractical for runtime. The hybrid Option F is the operationally correct synthesis.

**Sub-finding 17.A.** The lineage normalization plan §11.4 + §12.5 should be amended to recommend Option C-for-contract + Option B-for-runtime (which is exactly Option F). This is a documentation refinement to the plan, NOT a constitutional change.

---

## §18. Temporary-unstage safety analysis

Under Option C contract decomposition, the Decision-Owner uses `git add` + `git reset HEAD` (or `git restore --staged`) to temporarily un-stage Step 10 contract additions at W1 commit time.

**Operations:**
1. `git add docs/phase_4b_deterministic_semantics.md` — stages full contract diff
2. `git diff --cached` — inspect staged diff
3. `git restore --staged docs/phase_4b_deterministic_semantics.md` — un-stage everything (return to working tree)
4. Use `git add -p docs/phase_4b_deterministic_semantics.md` — stage hunk-by-hunk; accept Step 9 hunks (y), reject Step 10 hunks (n), split if needed (s)
5. `git diff --cached` — verify only Step 9 content staged
6. `git commit` — W1
7. `git add -p docs/phase_4b_deterministic_semantics.md` — stage remaining Step 10 hunks at W2
8. `git diff --cached` — verify only Step 10 content staged
9. `git commit` — W2

**Risks:**

* Forgetting step 4's `git add -p` interactive prompts; accidentally accepting wrong hunks
* `git restore --staged` not understood; replaced with `git reset HEAD` which is similar but has subtle differences
* Working-tree state preserved: yes — `git add` / un-stage operations modify index only, not working tree

**Mitigation M9 (NEW).** Pre-execution dry-run: produce the W1 planned diff (without committing) by:
```
git add -p docs/phase_4b_deterministic_semantics.md   # interactively stage Step 9
git diff --cached > /tmp/w1-contract-planned.diff      # save planned diff
git restore --staged docs/phase_4b_deterministic_semantics.md  # reset
```

Decision-Owner reviews `/tmp/w1-contract-planned.diff` against expected Step 9 content (D-FAULT-1..-14, D-FAULT-15 rows 1–18, §11 item 4 modification, etc.). If correct, repeats the staging at execution time and commits.

This dry-run gives a low-risk preview of what W1 will commit before committing.

**Operational verdict:** temporary unstage IS safe with M9 dry-run discipline. Without M9, the human-error surface is real but bounded (you can re-do the staging if you make a mistake).

---

## §19. Replay-baseline continuity simulation

Under Option F (recommended):

| event | runtime state | replay baseline status |
|---|---|---|
| Pre-W1 | Step 8 (`cb95a9a`) | Step 8 baseline applies |
| W1 commit | Step 9 contract + docs + tests (NO runtime) | Step 8 baseline still applies to runtime; V18 not meaningful (runtime unchanged from Step 8) |
| Post-W1 | Same as above | V18 against Step 8 baseline PASS (runtime is Step 8) |
| W2 commit | Combined Step 9+10 runtime + Step 10 contract + docs + tests | Step 10 baseline applies |
| **Post-W2 V18** | Combined runtime | **MUST PASS against validated Step 10 baseline** |
| W3 commit | docs-only | runtime unchanged; V18 not meaningful |
| W4 commit | docs-only | runtime unchanged; V18 not meaningful |
| Final | full state | Step 10 baseline applies |

**Under Option C:** post-W1 V18 would require a "Step 9 baseline" (which doesn't exist as a separately-validated artifact). Could either capture a new one (costs cycle-suite runtime) or defer V18 to W2 (acceptable per lineage plan §13.A but loses W1 validation).

**Under Option B:** V18 only meaningful at post-combined-commit; same as Option F's post-W2.

**Simulation verdict:** Option F preserves the validated Step 10 baseline cleanly. V18 BLOCKING at post-W2 is the operational checkpoint.

---

## §20. Post-W2 V18 survivability analysis

The validated Step 10 baseline was established when:
* Runtime = current working-tree state
* Contract = current working-tree state
* Tool (`check_session_replay_identity.py`) = current working-tree state

After W2 under Option F:
* Runtime = byte-identical to working-tree state (all runtime files committed verbatim)
* Contract = byte-identical to working-tree state (all contract content committed)
* Tool = byte-identical to working-tree state (`tools/check_session_replay_identity.py` committed in W2 under F; recommend bundling tool with runtime even though attributed to Step 9 P7 in lineage plan §5.1)

**Expected V18 result.** PASS (post-W2 master byte-identical to the working-tree state that established the baseline).

**Failure scenarios:**
* If runtime decomposition mis-attributes a line (Option C only): possible FAIL
* If contract decomposition mis-attributes (any option): contract changes don't affect runtime → V18 still PASS (contract is documentation, not executed)
* If pre-commit hook modifies content during commit (e.g., formatter): possible FAIL
* If `.gitattributes` or autocrlf normalizes line endings: possible FAIL

**Mitigation M10 (NEW).** Pre-W2 dry-run: invoke V18 against the working-tree state (BEFORE any commit) to confirm it currently PASSes with the working-tree content. This establishes the baseline-tooling sanity. Then execute W2; post-commit V18 should produce the same result.

If pre-W2 dry-run V18 FAILs against the working tree, the baseline reference itself is in question; investigate before any landing.

---

## §21. Docs-wave cleanliness verification (W3, W4)

Working-tree inspection confirmed 16 docs (8 Step 11 + 8 Step 12). With this dry-run review added, the count becomes 17. Future planning sessions may add more.

**W3 cleanliness:** all 8 `docs/phase_4b_step11_*.md` files; no runtime, no contract, no tests. Single commit; full-file staging via `git add docs/phase_4b_step11_*.md`. Trivially clean.

**W4 cleanliness:** all `docs/phase_4b_step12_*.md` files. Single commit; full-file staging via `git add docs/phase_4b_step12_*.md`. Trivially clean.

**M6 reminder:** glob-based staging for W4 (per §11) ensures all Step 12 docs present at execution time are captured.

**Simulation verdict:** W3 and W4 are operationally low-risk. No hazards beyond H6 (untracked file accumulation, mitigated by glob-based staging).

---

## §22. Revert-path survivability simulation

**Scenario:** W2 post-commit V18 FAILs.

**Recovery sequence (per lineage plan §24):**
1. `git revert <W2-SHA>` — creates additive revert commit; master HEAD goes back to W1 state (no rebase, no force-push)
2. Investigate V18 failure: did decomposition mis-attribute? did runtime have a bug discovered only post-commit? did the tool diverge from baseline?
3. Correct the underlying issue in working tree (which is restored to pre-W2 state by the revert)
4. Re-stage W2 content
5. `git commit` — new W2 commit (W2_v2)

**Audit pattern post-recovery:**
```
W2_v2  (corrected re-attempt)
W2_revert  (additive inverse)
W2  (original failed attempt)
W1   (Step 9 closure)
cb95a9a  (Step 8 closure)
```

**Survivability:** ✓ Revert is additive; history preserved; recovery clean.

**Constitutional check:** BRANCH-LINEARITY preserved (no rebase, no force-push, no amend); AUDIT-COMPLETENESS preserved (failed attempt + revert + corrected attempt all visible in history).

---

## §23. Master-linearity survivability

Under Option F:
* `cb95a9a` (Step 8 closure)
* `<W1-SHA>` (Step 9 closure: contract + docs + tests; no runtime)
* `<W2-SHA>` (Step 10 closure: all runtime + Step 10 contract + Step 10 docs + tests)
* `<W3-SHA>` (Step 11 docs)
* `<W4-SHA>` (Step 12 docs)
* (post-recovery commits if any failures encountered)

All commits linear. No rebase. No force-push. No amend.

**Constitutional check:** BRANCH-LINEARITY preserved.

---

## §24. Operational ergonomics under real execution

| metric | Option C | Option F (recommended) | Option B |
|---|---|---|---|
| Decision-Owner attribution effort | high (per-line runtime + per-clause contract) | medium (per-clause contract only) | low (no decomposition) |
| Risk of silent mis-attribution | HIGH (runtime) | LOW (no runtime per-step) | NONE |
| Per-Step git-commit granularity | full | contract-only | none (combined) |
| Per-Step audit clarity in git log | strongest | moderate (Step 9 contract + Step 10 runtime collapse) | weakest (one combined commit) |
| Total normalization wall time | days (with archaeology) | hours | hours |
| Recovery complexity if W2 fails | high | medium | medium |

**Operational verdict:** Option F is the operationally pragmatic choice. Option C ideal-but-impractical; Option B simplest but loses contract-Step granularity.

---

## §25. Minimum-safe-operator procedure

The simplest reliably-safe procedure (Option F + all mitigations M1–M10):

```
PRE-EXECUTION CHECKS:
  - Verify git status matches expected (untracked files inventory current)
  - Run V18 against working tree to confirm baseline-tool sanity (M10)
  - For W1 contract decomposition: dry-run staging with /tmp/w1-contract-planned.diff (M9)
  - Confirm no pre-commit hooks alter content (M10)

W1 EXECUTION:
  - git add (Step 9 contract via -p, Step 9 docs, Step 9 tests, Step 9 launchers)
  - git diff --cached  ->  verify Step 9 content only
  - git commit with rich message (per M3: enumerate in-place modifications)
  - git status --porcelain  ->  verify Step 10/11/12 content remaining

W2 EXECUTION:
  - git add (Step 10 contract via -p, all runtime files full-file, envelopes.py, Step 10 tests, Step 10 scripts, Step 10 docs)
  - git diff --cached  ->  verify Step 10 content + all runtime staged
  - git commit with rich message (per M1, M3, M4: enumerate renumbering + structural summary)
  - **MUST run V18 against Step 10 baseline; MUST PASS**

W3 EXECUTION:
  - git add docs/phase_4b_step11_*.md  (glob-based per M6)
  - git diff --cached  ->  verify only Step 11 docs
  - git commit

W4 EXECUTION:
  - git add docs/phase_4b_step12_*.md  (glob-based per M6)
  - git diff --cached  ->  verify only Step 12 docs
  - git commit

POST-EXECUTION VERIFICATION (§28 of lineage plan):
  - 9-point master-ready-for-S0 verification
```

**Sub-finding 25.A.** With Option F + M1–M10, the procedure is ~hours of focused work; risk surface is bounded; recovery paths are clean.

---

## §26. Mitigation catalog summary

| ID | mitigation | applies to | required? |
|---|---|---|---|
| M1 | W2 commit message: explicit §1.5/1.6 renumbering acknowledgment | H1 | REQUIRED |
| M2 | Plan amendment: Option C→Option F recommendation for runtime | H2 (eliminates SAFETY-CRITICAL) | REQUIRED |
| M3 | Per-wave commit message: enumerate in-place contract modifications | H3 | REQUIRED |
| M4 | Commit message: structural summary of large-file changes | H4 | RECOMMENDED |
| M5 | Under Option C: BLOCKING test run post-W1 | H5 (Option C only) | REQUIRED IF Option C ADOPTED |
| M6 | Glob-based staging for W3/W4 | H6 | REQUIRED |
| M7 | Under Option C: attribution by inspection for shared files | H7 (Option C only) | REQUIRED IF Option C ADOPTED |
| M8 | Under Option C: defer V18 to W2 | H8 (Option C only) | REQUIRED IF Option C ADOPTED |
| M9 | Pre-execution dry-run staging of W1 contract decomposition | operational | RECOMMENDED |
| M10 | Pre-execution V18 against working tree | operational | RECOMMENDED |

**Sub-finding 26.A.** Under recommended Option F: M1, M2, M3, M4, M6 are REQUIRED; M9, M10 are RECOMMENDED. M5/M7/M8 are Option-C-specific and not needed under F.

---

## §27. Required lineage-plan amendments

The lineage normalization plan §11.4 + §12.5 should be amended to:

**Amendment A1 (replaces §11.4 recommendation):**

> For contract decomposition: **Option C recommended** — clauses are well-named (D-FAULT-1..-14 for Step 9; D-EXEC-13 family for Step 10); identification is tractable in ~30 minutes of focused work; supports per-Step audit granularity at contract level.
>
> For runtime decomposition: **Option B (combined runtime in W2) STRONGLY RECOMMENDED over Option C.** Reason: per-line Step attribution in intermixed runtime files (especially session.py at 943 lines) is operationally difficult and SAFETY-CRITICAL (mis-attribution can produce false-PASS V18/test results). Combined runtime in W2 trades per-Step runtime audit granularity for elimination of mis-attribution silent-failure risk.
>
> The hybrid is named **Option F** (per-step contract decomposition + combined runtime in W2). Under Option F: W1 = Step 9 contract + Step 9 docs + Step 9 tests + Step 9 launchers (NO runtime); W2 = all runtime + Step 10 contract + Step 10 docs + Step 10 tests + Step 10 scripts + Step 10 launchers + `envelopes.py`. Trade-off: W1-to-W2 inconsistency window (contract documents Step 9 D-FAULT without runtime implementing it) typically minutes if executed in immediate succession; acceptable.

**Amendment A2 (per-wave commit message templates with M1+M3 inclusions).**

**Amendment A3 (glob-based staging for W3/W4 per M6).**

**Amendment A4 (pre-execution dry-run M9 + M10 in §10 per-wave landing protocol).**

These amendments are documentation-level refinements to the lineage normalization plan. They do not alter the constitutional framework, do not introduce new validators or governance, do not change Step 12's authoring framework. They can be applied as additive text appended to the lineage plan (or as a follow-up superseding note in §32 of the lineage plan).

---

## §28. Final verdict

### **DRY-RUN-CONDITIONALLY-SAFE**

The W1–W4 landing sequence is operationally executable IF the following conditions are satisfied:

1. **The lineage normalization plan §11.4 + §12.5 are amended per A1** to recommend Option F (per-step contract + combined runtime) instead of strict Option C. This eliminates the SAFETY-CRITICAL hazards H2 and H5.
2. **Mitigations M1, M3, M4, M6 are observed** during execution (commit message enumerations + glob-based staging).
3. **Recommended mitigations M9 + M10 are observed** (pre-execution staging dry-run + pre-execution V18 against working tree) for additional safety margin.

Without these conditions: SAFETY-CRITICAL Option C path remains the plan's recommendation; high risk of silent mis-attribution producing false-PASS post-W1 verification. With these conditions: execution is operationally bounded and the framework is survivable.

### Hazards and severity recap

| ID | hazard | severity | mitigated by |
|---|---|---|---|
| H1 | Section renumbering | OPERATIONAL | M1 |
| **H2** | **Option C runtime decomposition difficulty** | **SAFETY-CRITICAL** | **M2 (plan amendment to Option F)** |
| H3 | In-place contract modifications | OPERATIONAL | M3 |
| H4 | Large diff size | OPERATIONAL | M4 |
| **H5** | **Test runtime dependency under Option C** | **SAFETY-CRITICAL** | **M2 (eliminated under F) / M5 (mandatory under C)** |
| H6 | Untracked file accumulation | OPERATIONAL | M6 |
| H7 | Per-step attribution uncertainty | OPERATIONAL | M7 (Option C only) / moot under F |
| H8 | Tool dependency cascade | OPERATIONAL | M8 (Option C only) / moot under F |

Two SAFETY-CRITICAL hazards; both Option-C-specific. Switching to Option F eliminates both.

### Constitutional impact of amendments

A1–A4 are documentation patches to the lineage normalization plan. They:

* Do NOT alter the four-layer pre-authoring framework (Layers A/B/C/D unchanged).
* Do NOT alter the admissibility evaluation verdict (AUTHORING-ADMISSIBLE unchanged).
* Do NOT alter the baseline initialization plan (S0–S8 unchanged).
* Do NOT alter the execution-readiness review verdict (EXECUTION-CONDITIONALLY-READY; B1 still the operational blocker).
* Do NOT mutate the contract document.
* Do NOT modify any normative clause or invariant.

The amendments only refine *how* Step 9 + Step 10 + Step 11 + Step 12 planning work is landed onto master before bootstrap S0. The substantive framework is unchanged.

### Operational basis for conditional safety

The framework's operational safety with amendments rests on:

1. **Option F eliminates SAFETY-CRITICAL Option C runtime decomposition risk.** Combined runtime in W2 + per-step contract decomposition is the safest viable hybrid.
2. **Per-wave commit messages document in-place modifications explicitly.** Future auditors can read commit messages to understand structural changes (renumbering, text updates).
3. **Glob-based W3/W4 staging is robust against doc-list drift.** Whatever Step 11/12 docs exist at execution time get staged; no fragile enumeration.
4. **Pre-execution dry-runs (M9 + M10) provide preview before commitment.** Decision-Owner can validate W1 contract staging without committing; can verify V18 against working tree before any W2 risk.
5. **Recovery paths preserved.** `git revert` + re-attempt remains the additive recovery mechanism; BRANCH-LINEARITY + AUDIT-COMPLETENESS hold throughout.

### Hidden blockers

After this dry-run review: NONE identified beyond H2 and its mitigation via plan amendment. The original B1 (master HEAD discrepancy) remains the BLOCKER; this dry-run identifies that B1 RESOLUTION should adopt Option F instead of Option C, but B1 itself is resolvable via the W1–W4 sequence.

---

## §29. Hazards specifically NOT identified (negative findings)

To confirm scope: the dry-run review did NOT discover hazards in the following areas:

* **W3/W4 docs-only isolation** — clean per §21
* **Constitutional posture preservation** — all 24 invariants preserved per §30
* **Audit-trail mechanics** — commit-message convention sufficient per §18 of lineage plan
* **Direct-master-landing strategy** — §17 of lineage plan reaffirmed (no intermediate branch needed)
* **Wave ordering (W1→W2→W3→W4)** — sequential ordering robust per §19/§20 of lineage plan
* **Branch-linearity invariant** — preserved by additive-only commits + revert-recovery
* **Bootstrap framework compatibility** — post-W4 master HEAD satisfies baseline-init §5's S1 precondition (assuming W2 V18 PASSes)

No additional hidden blockers beyond H1–H8 identified.

---

## §30. Preserved invariants under this review

This review introduces no new invariants and modifies no inherited ones. All 24 inherited invariants confirmed preserved at the dry-run analysis level:

* replay-authoritative truth ✓ (V18 PASS at post-W2 confirms)
* append-only causality ✓ (additive landing; revert-only recovery)
* additive-only mutation discipline ✓ (at branch level; content-level acknowledged in §3.B as Step 9/10 internal artifact, not Step 12 AAU constraint)
* BRANCH-LINEARITY ✓ (no rebase, no force-push, no amend in any wave)
* AUDIT-COMPLETENESS ✓ (commit messages + recovery patterns preserve history)
* no amend ✓
* no rebase ✓
* no force-push ✓
* no hidden cleanup ✓ (working-tree content fully landed; nothing silently discarded)
* no semantic widening ✓ (no clause widens during normalization; content byte-preserved from working tree)
* no authority redistribution ✓ (no role-type changes during normalization)
* plus all other inherited invariants from the four-layer framework + admissibility verdict + baseline-init + readiness review

None weakened. None widened. None silently dropped.

---

**End of Step 12 lineage normalization dry-run review.**

**Verdict: DRY-RUN-CONDITIONALLY-SAFE.**

The W1–W4 landing sequence is operationally executable conditional on:
1. Amendment A1 (Option F instead of Option C for runtime) applied to the lineage normalization plan;
2. Mitigations M1, M3, M4, M6 observed during execution (REQUIRED);
3. Mitigations M9, M10 observed (RECOMMENDED for additional safety margin).

After these conditions are met: Decision-Owner may execute W1–W4 per the Option F procedure. After successful W4 + lineage-plan §28 verification: bootstrap S0 admissible.

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance](phase_4b_step11_f59_manual_advance_analysis.md), [closure verification](phase_4b_step11_closure_verification.md), [codification plan](phase_4b_step11_codification_plan.md), [meta-audit](phase_4b_step11_meta_audit.md), [extraction plan](phase_4b_step11_extraction_plan.md), [Layer A authoring mechanics](phase_4b_step12_authoring_mechanics_plan.md), [Layer B per-clause validation](phase_4b_step12_validation_plan.md), [Layer C review ergonomics](phase_4b_step12_review_ergonomics_plan.md), [Layer D cross-clause governance](phase_4b_step12_governance_plan.md), [admissibility evaluation](phase_4b_step12_admissibility_evaluation.md), [baseline initialization plan](phase_4b_step12_baseline_initialization_plan.md), [execution readiness review](phase_4b_step12_execution_readiness_review.md), [lineage normalization plan](phase_4b_step12_lineage_normalization_plan.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).

Successor: lineage-plan amendments A1–A4 applied (additive); then B1 closure via Option F W1–W4 execution; then bootstrap S0; then S1–S8; then AUTHORING-ACTIVE.
