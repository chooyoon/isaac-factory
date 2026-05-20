# Phase 4B Step 12 — R-FG-1 Additive Patch for Runbook §10

**Status: R-FG-1 ADDITIVE PATCH (2026-05-21).** Per [`phase_4b_step12_refinement_prioritization.md`](phase_4b_step12_refinement_prioritization.md) §17 verdict APPLY-R-FG-1-ONLY, this artifact provides the verbatim additive-supersession text to be appended to [`phase_4b_step12_lineage_execution_runbook.md`](phase_4b_step12_lineage_execution_runbook.md) after §23.

This is an operational documentation patch, not a planning artifact. The patch itself is the deliverable.

---

## Verdict

### **R-FG-1-ADMISSIBLE**

The patch is additive-only, bounded to explicit post-revert recovery commands, introduces no new governance/validator/role semantics, and preserves all 24 invariants. Same admissibility basis as amendment plan §A1–§A4 per refinement prioritization §10.

---

## Application instruction

Decision-Owner appends the verbatim text below (between the `---PATCH-BEGIN---` and `---PATCH-END---` markers) to `docs/phase_4b_step12_lineage_execution_runbook.md`, immediately after §23 ("Preserved invariants under this runbook design"). The runbook's existing §1–§23 content is NOT modified.

Expected runbook line count post-application: ~1105 + ~150 = ~1255 lines.

---

## Patch verbatim text

---PATCH-BEGIN---

```markdown
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
```

---PATCH-END---

---

## Preserved invariants under R-FG-1 application

All 24 inherited invariants preserved:

* replay-authoritative truth ✓
* append-only causality ✓ (patch is additive; recovery sequence is additive)
* additive-only mutation discipline ✓ (Properties A1–A3 analogues at documentation level)
* BRANCH-LINEARITY ✓ (recovery sequence explicit about no-amend/no-rebase/no-force-push)
* AUDIT-COMPLETENESS ✓ (3-commit pattern preserves failure attempt)
* validator supremacy ✓ (no validator changes)
* no semantic widening ✓ (recovery operates within existing §10 scope)
* no hidden cleanup ✓ (additive supersession; original §10 text preserved)
* no authority redistribution ✓ (no role changes)
* no governance recursion spiral ✓ (single targeted patch; no new review cycle triggered)
* no amend ✓ (explicit forbid in §R-FG-1.6)
* no rebase ✓ (explicit forbid in §R-FG-1.6)
* no force-push ✓ (explicit forbid in §R-FG-1.6)
* (plus all other inherited invariants)

None weakened. None widened. None silently dropped.

---

**End of R-FG-1 patch artifact.**

Patch text between `---PATCH-BEGIN---` and `---PATCH-END---` is ready to copy-paste-append to runbook after §23. No further analysis required; no further planning required. After patch application: proceed to runbook Phase 0 per prioritization §17 sequence.
