# S2 Substrate Baseline Capture

**This artifact is the S2-authored content in DEFERRED-FILING SCRATCH state per `phase_4b_s0_authorization_freeze.md` §9.5. At S3 time, this file will be moved to `docs/step12_audit_traces/s2_baseline_substrate_attestation.md` (content preserved verbatim) and committed per PD-2 Z1 convention. Until that S3 move + commit, this scratch file is the authoritative S2 record.**

---

S2 is READ-ONLY substrate inspection. No file in the substrate was modified during capture. All `git`, `sha256sum`, `grep`, `awk`, `wc` invocations are non-mutating reads.

## Baseline-init §6 schema fields

- **Contract document path:** `docs/phase_4b_deterministic_semantics.md`
- **Contract SHA-256:** `2200d4fc45b2dcef7920d65a62bbfc2abf39ffeb19fef7c608e84c8908109f80`
- **Contract line count:** `1392`
- **Existing clause-ID count:** `121` (unique line-anchored `**D-FAMILY-N[a-z]?**` definitions); full list embedded in §S2-clause-inventory below
- **§11 open-extension item-1 text:** verbatim 5-line capture embedded in §S2-section-11-item-1 below
- **D-FAULT-15 row count:** `30` (matches expected pre-Step-12 value per Step 10 Direction A closure)
- **§0 glossary entry count:** `9` (matches expected pre-Step-12 value per codification-plan §5)
- **Existing replay baseline events.jsonl SHA-256:** 4 per-scenario hashes from Step 10 Direction A §P.1 (validated 12/12 cycles bytewise identical); embedded in §S2-replay-baseline below
- **Replay baseline source:** Step 10 Direction A Phase 6 acceptance (landed in master via commit `cc38d68` per the user-stated lineage `cb95a9a → cc38d68 → a35935a → 6daf9b2`); current substrate is at master HEAD `6daf9b2c24edef63e81a832727eb191726f69afb` which is post-`cc38d68` (runtime unchanged from cc38d68 → 6daf9b2; W3 and W4 were docs-only commits)
- **Replay-cycle policy:** `--reopen-stage-between-cycles` (per Step 10 Direction A §P.2 validated isolation policy)

## §S2-substrate-fingerprint summary

| dimension | value |
|---|---|
| Master HEAD SHA | `6daf9b2c24edef63e81a832727eb191726f69afb` |
| Codification branch HEAD SHA | `6daf9b2c24edef63e81a832727eb191726f69afb` (identical to master per S1 §S1-branch-creation) |
| Current checkout | `phase-4b-step12-codification` |
| Contract SHA-256 | `2200d4fc45b2dcef7920d65a62bbfc2abf39ffeb19fef7c608e84c8908109f80` |
| Contract line count | `1392` |
| Contract size on disk | (uncomputed; SHA-256 is the canonical fingerprint) |
| Clause-ID inventory size (unique) | `121` |
| D-FAULT-15 row count | `30` |
| §0 glossary entry count | `9` |
| Replay baseline distinct hashes | `4` (per Step 10 §P.1 scenarios C/D/E/F) |
| Replay baseline 3-cycle identity | byte-identical 3/3 within each scenario; 12/12 total cycles |
| Replay isolation policy | `--reopen-stage-between-cycles` |

## §S2-clause-inventory (canonical, alphabetically sorted)

All 121 unique line-anchored clause-IDs in the contract at S2 time. Source: `grep -oE '^\*\*D-(EXEC|SCHED|BUS|REPLAY|SESS|TRACE|LIFE|FORBID|SCALE|CONT|FAULT)-[0-9]+[a-z]?\*\*' docs/phase_4b_deterministic_semantics.md | sort -u`.

**D-BUS family (12 clauses):** D-BUS-1, D-BUS-2, D-BUS-3, D-BUS-4, D-BUS-5, D-BUS-6, D-BUS-7, D-BUS-8, D-BUS-9, D-BUS-10, D-BUS-11, D-BUS-12.

**D-CONT family (12 clauses):** D-CONT-1, D-CONT-2, D-CONT-3, D-CONT-4, D-CONT-5, D-CONT-5a, D-CONT-6, D-CONT-6a, D-CONT-6b, D-CONT-6c, D-CONT-7, D-CONT-7a.

**D-EXEC family (17 clauses):** D-EXEC-1, D-EXEC-2, D-EXEC-3, D-EXEC-4, D-EXEC-5, D-EXEC-6, D-EXEC-7, D-EXEC-8, D-EXEC-9, D-EXEC-10, D-EXEC-11, D-EXEC-12, D-EXEC-13, D-EXEC-13a, D-EXEC-13b, D-EXEC-13c, D-EXEC-13d.

**D-FAULT family (30 clauses):** D-FAULT-1, D-FAULT-1a, D-FAULT-1b, D-FAULT-2, D-FAULT-3, D-FAULT-3a, D-FAULT-3b, D-FAULT-4, D-FAULT-4a, D-FAULT-5, D-FAULT-5a, D-FAULT-5b, D-FAULT-6, D-FAULT-6a, D-FAULT-7, D-FAULT-8, D-FAULT-8a, D-FAULT-8b, D-FAULT-9, D-FAULT-9a, D-FAULT-10, D-FAULT-11, D-FAULT-11a, D-FAULT-12, D-FAULT-12a, D-FAULT-12b, D-FAULT-12c, D-FAULT-13, D-FAULT-14, D-FAULT-15.

**D-LIFE family (9 clauses):** D-LIFE-1, D-LIFE-2, D-LIFE-3, D-LIFE-4, D-LIFE-5, D-LIFE-6, D-LIFE-7, D-LIFE-8, D-LIFE-9.

**D-REPLAY family (9 clauses):** D-REPLAY-1, D-REPLAY-2, D-REPLAY-3, D-REPLAY-4, D-REPLAY-5, D-REPLAY-6, D-REPLAY-7, D-REPLAY-8, D-REPLAY-9.

**D-SCALE family (3 clauses):** D-SCALE-1, D-SCALE-2, D-SCALE-3.

**D-SCHED family (13 clauses):** D-SCHED-1, D-SCHED-2, D-SCHED-3, D-SCHED-4, D-SCHED-5, D-SCHED-6, D-SCHED-7, D-SCHED-8, D-SCHED-9, D-SCHED-10, D-SCHED-11, D-SCHED-12, D-SCHED-13.

**D-SESS family (8 clauses):** D-SESS-1, D-SESS-2, D-SESS-3, D-SESS-4, D-SESS-5, D-SESS-6, D-SESS-7, D-SESS-8.

**D-TRACE family (8 clauses):** D-TRACE-1, D-TRACE-2, D-TRACE-3, D-TRACE-4, D-TRACE-5, D-TRACE-6, D-TRACE-7, D-TRACE-8.

**Family-count totals:** 12 + 12 + 17 + 30 + 9 + 9 + 3 + 13 + 8 + 8 = 121.

(Note: the contract does NOT contain any D-FORBID-prefixed clause-IDs as line-anchored bold definitions. The `## 8. Forbidden Patterns *(D-FORBID)*` section title references the family name as a labeling convention, but the section's content uses prose without per-pattern bold clause-IDs in the line-anchored-bold form that this inventory captures. This is a known authoring convention, not a substrate defect — the section is normative; the inventory enumerates only the formally-IDed clauses.)

**Future Step-12 additions (NOT YET PRESENT in this baseline):** D-FAULT-6b, D-FAULT-6c, D-FAULT-9b, D-FAULT-9c, D-SCHED-14, D-REPLAY-10, D-INGRESS-1..9, D-FAULT-15 rows 31–42, 5 glossary terms — per `docs/phase_4b_step11_extraction_plan.md` 38-insertion catalog. None of these clause-IDs appears in the S2 baseline; their absence is expected pre-Step-12.

## §S2-section-11-item-1 (verbatim, 5-line capture)

The text of `## 11. Open extensions (future contract revisions)` item 1 at S2 time, verbatim from the contract:

```
The following are recognized gaps that future revisions will need to address. Listing them here marks them as *known-unspecified*, not *forgotten*:

1. **`OperatorOverride` event commutativity.** The contract specifies operator commands enter only at Phase A; it does not yet specify whether two operator commands in the same Phase A drain are processed in arrival order or in a canonical order. Phase 4B step 11 will close this gap.
```

This text is the reference baseline for V12 (Properties S1–S3) when the SF AAU (the §11 item-1 CLOSED-marker append, per Layer A §3 SF shape) is authored in Wave 5. Per the SF AAU's Property S1 (verbatim-prefix preservation), the modified line MUST contain the above text as a verbatim prefix; the post-mutation text appends a CLOSED-marker citing Lemma L3 and D-INGRESS-4 (per codification plan §7).

(Note: the §11 enumeration shows that item 4 has ALREADY been substantively updated to reflect Step 9 closure: "Pinned in §13 D-FAULT (D-FAULT-3, D-FAULT-3a, D-FAULT-4, D-FAULT-7)" — this was the Step 9 in-place modification documented in W1's commit message per the lineage dry-run review §H2.)

## §S2-replay-baseline

Per Step 10 Direction A `docs/phase_4b_step10_direction_a_analysis.md` §P.1 empirical validation matrix:

| scenario | trigger | classification | 3-cycle events.jsonl SHA-256 |
|---|---|---|---|
| **C** | envelope eligible mid-N1 (`requested_at_tick=400`) → predicate trips at boundary 6 (`approach_place`, tick=558) | OPERATOR_ABORT (D-FAULT-3b row 1) | `a4e202891836af1c6ef6e0b2e27a33ee13a2a47dd8e12dff87f4307810196c75` |
| **D** | same as C; focus on cascade-skip behavior | OPERATOR_ABORT | `fa71aef1ab7f4aafe8dcb27481dffed8fea5f112d5dfdc3b7b2ede6c04b0aee0` |
| **E** | `tick_budget_ticks=400` exceeded at boundary 6 (558 > 400) | TIMEOUT_FAILURE (D-FAULT-3b row 2) | `76bb808769ab3c0cb87df45edc1c2f56bddf0c8afea0c9ab2a61475e94286fc2` |
| **F** | same as C; focus on D-FAULT-5b contradiction verification | OPERATOR_ABORT | `39c8291414a37706db10ace7e580401d4262413a7cd9eee394d49be08b71433c` |

Validation: 12/12 cycles bytewise events.jsonl SHA-256 identity (3 cycles per scenario × 4 scenarios = 12), under `--reopen-stage-between-cycles` isolation policy.

These 4 hashes are the canonical replay baselines for V18 (Layer B §7.1) and FF1 (Layer D final-form) invocations during Step 12 authoring. Per baseline-init §14, S2 captures the existing baseline; subsequent V18 invocations during authoring compare against these hashes.

Sub-baseline V18 invocation at Step 12 time will exercise the most-recent applicable scenario; the operator (Layer-B-implementing-agent at S4 mechanization) records the exact V18 invocation convention (which scenario, which cycle, what `tool args`) in the s4 attestation.

## §S2-gate-evaluation (per baseline-init §6 gate)

| gate condition | result | evidence |
|---|---|---|
| 1. All six capture entries present | ✓ PASS | this artifact contains contract SHA, line count, clause-ID inventory, §11 item-1 verbatim, D-FAULT-15 row count, §0 glossary count, replay baseline hashes (extended set), source, policy |
| 2. Contract SHA-256 is computable and stable | ✓ PASS | `sha256sum` returned `2200d4fc...` cleanly; substrate unmutated during capture |
| 3. Replay baseline reference resolves | ✓ PASS | Step 10 Direction A §P.1 located; 4 scenario hashes captured |
| 4a. D-FAULT-15 row count matches expected (30) | ✓ PASS | `30 == 30` |
| 4b. §0 glossary count matches expected (9) | ✓ PASS | `9 == 9` |

**S2 gate: PASSED.**

## §S2-substrate-stability-assertion

This S2 capture asserts that AT CAPTURE TIME on master HEAD `6daf9b2c24edef63e81a832727eb191726f69afb` (= codification branch HEAD), the substrate state is exactly as recorded above. The captures are immutable from this point forward in the bootstrap; any subsequent re-verification (at S4 V18 dry-run, S8 #5 SHA re-check, S8 #6 V18 re-dry-run) MUST produce identical SHA / count / text values, else the substrate has drifted and an investigation is required.

**Substrate read-only invariant during S2:**

- No file in `docs/`, `tools/`, `scripts/`, or `isaac_factory/` was modified during this capture.
- No commit was created on `master` or `phase-4b-step12-codification` during this capture.
- No branch was created or deleted during this capture.
- No git history was rewritten.
- The only working-tree delta this S2 contributes is THIS artifact at the scratch path.

## §S2-replay-authoritative-truth assertion

The 4 per-scenario events.jsonl SHA-256 hashes recorded above are the canonical replay-authoritative baselines for Step 12 authoring. They were established by the Step 10 Direction A Phase 6 acceptance run (12/12 cycles, byte-identical, under validated isolation policy). They are not generated by this S2 capture; they are RECORDED here from §P.1 of the existing analysis document.

No other source of truth — timestamps, wall-clock, log files, MP4 frames, console output — overrides these 4 hashes. Per the bootstrap execution map §5 statement of supremacy: "the replay baseline is the canonical substrate truth."

## Filing protocol (deferred filing per freeze §9.5)

This artifact is authored at S2 time in the scratch path `docs/phase_4b_s2_substrate_baseline_capture_scratch.md` (untracked working-tree file on the codification branch). At S3 time, the operator:

1. Creates `docs/step12_audit_traces/` directory + manifest (S3 work per baseline-init §7).
2. Moves this file: `mv docs/phase_4b_s2_substrate_baseline_capture_scratch.md docs/step12_audit_traces/s2_baseline_substrate_attestation.md`. Content preserved verbatim including this filing-protocol note.
3. `git add docs/step12_audit_traces/s2_baseline_substrate_attestation.md` and stages the other deferred filings (s0 scratch, s1 scratch).
4. Commits per PD-2 Z1 convention: `Phase 4B Step 12 / Infrastructure — S3 audit-trace directory + manifest + S0/S1/S2 deferred filings` (or as Decision-Owner sequences).
5. Once committed, this scratch path no longer holds the authoritative record; the scratch file is removed.

Until that S3 move + commit, this scratch file IS the authoritative S2 record. It MUST NOT be amended per Layer A §16 by analogy + BRANCH-LINEARITY. Corrections via additive supersession: `docs/phase_4b_s2_substrate_baseline_capture_scratch_correction_1.md` (pre-S3) or `docs/step12_audit_traces/s2_baseline_substrate_attestation_correction_1.md` (post-S3 move).

## S3 admissibility statement

S2 is now COMPLETE per baseline-init §6 gate. Per baseline-init §7 + map §11.4, S3 (audit-trace infrastructure initialization) is CONSTITUTIONALLY PERMISSIBLE. S3 SHALL NOT be executed in the same session that executed S2 per the current session's brief constraint; S3 is the next-session action.

S3 will additionally batch-file the three accumulated deferred-filing scratch artifacts (S0, S1, S2) at the formal audit-trace location.

---

**End of S2 substrate baseline capture artifact (scratch, deferred filing).**

Substrate HEAD: 6daf9b2c24edef63e81a832727eb191726f69afb
Contract SHA-256: 2200d4fc45b2dcef7920d65a62bbfc2abf39ffeb19fef7c608e84c8908109f80
Clause-ID count: 121 (unique line-anchored)
D-FAULT-15 rows: 30 (matches expected)
§0 glossary: 9 (matches expected)
Replay baseline: 4 scenarios × 3 cycles = 12/12 bytewise identical
Gate: PASSED
Filing status: deferred-scratch (formal filing at S3)
