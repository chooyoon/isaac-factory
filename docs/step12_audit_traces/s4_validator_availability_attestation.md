# S4 Validator Availability Attestation

**Filing status:** authored directly at canonical path (post-S3; no deferred filing needed).

Per baseline-init §8 + Layer B §3 catalog. Layer-B-implementing-agent: **claude** (per S0 §M-12 Initial Role Intent under PD-4 Y2).

---

## Baseline-init §8 schema fields

### Per-validator status

| ID | name | status | mechanization | failure class | dry-run result |
|---|---|---|---|---|---|
| V1 | Anchor uniqueness (pre) | READY | mechanical | BLOCKING | PASS (unique anchor → PASS; missing anchor → FAIL as expected) |
| V2 | Anchor stability | READY | mechanical | BLOCKING | PASS (non-overlap → PASS; overlap → FAIL as expected) |
| V3 | Three-section template presence | READY | semi-mechanical | BLOCKING | PASS (good body → PASS; missing citations → FAIL as expected) |
| V4 | Citation classification | READY | semi-mechanical | BLOCKING | PASS (labeled → PASS; unlabeled → FAIL as expected) |
| V5 | Anchor-cite existing-clause | READY | mechanical | BLOCKING | PASS (existing → PASS; nonexistent → FAIL as expected) |
| V6 | Minimal-enforceable-surface | MANUAL | manual checklist | SOFT | MANUAL (no dry-run; checklist at `tools/step12_validators/v06_v20_manual_checklists.md`) |
| V7 | Hidden-widening-language scan | READY | semi-mechanical | SOFT | PASS (no banned phrases → PASS; banned phrase found → SOFT FAIL as expected) |
| V8 | Override-statement presence | READY | mechanical | BLOCKING | PASS (full statement → PASS; missing verb → FAIL as expected) |
| V9 | Framework-reference confinement | READY | semi-mechanical | BLOCKING | PASS (Note-only ref → PASS; Rule-leak → FAIL as expected) |
| V10 | D-FAULT-15 row format | READY | mechanical | BLOCKING | PASS (well-formed → PASS; malformed → FAIL as expected) |
| V11 | Properties A1–A3 (non-SF) | READY | mechanical | BLOCKING | PASS (no diff staged → PASS, zero deletions) |
| V12 | Properties S1–S3 (SF) | READY | mechanical | BLOCKING | PASS (verbatim prefix → PASS; not prefix → FAIL as expected) |
| V13 | Anchor uniqueness (post) | READY | mechanical | BLOCKING | PASS (unique → PASS) |
| V14 | Existing-text byte preservation | READY | mechanical | BLOCKING | PASS (no diff staged → PASS) |
| V15 | Heading-DAG structure | READY | semi-mechanical | BLOCKING | PASS against synthetic; **see §S4-V15-finding for informational note on real-contract pre-existing quirks** |
| V16 | New clause-ID uniqueness | READY | mechanical | BLOCKING | PASS (existing ID single def → PASS; zero defs → FAIL as expected) |
| V17 | Cross-reference resolvability | READY | mechanical | BLOCKING | PASS (valid refs → PASS; invalid ref → FAIL as expected) |
| V18 | Replay-test invariant | READY | mechanical | BLOCKING | PASS (self-comparison + cross-cycle both REPLAY-IDENTICAL) |
| V19 | Inter-wave citation-gap | READY | mechanical | BLOCKING | PASS (resolving refs → PASS; unresolved → FAIL as expected) |
| V20 | Normative-consistency | MANUAL | manual checklist | SOFT | MANUAL (no dry-run; checklist at `tools/step12_validators/v06_v20_manual_checklists.md`) |
| FF1 | Final-form V18 | READY | mechanical (wraps V18) | BLOCKING | PASS (wraps V18) |
| FF2 | Final-form V19 | READY | mechanical (wraps V19) | BLOCKING | PASS (wraps V19) |
| FF3 | Step 12 completeness | READY | mechanical | BLOCKING | PASS — pre-authoring expected FAIL (Step-12 clauses absent; verifies completeness logic correctly detects absence) |
| FF4 | Framework/contract separation aggregate | READY | mechanical (wraps V9) | BLOCKING | PASS (good bodies aggregate → PASS; bad body → FAIL as expected) |
| FF5 | Substrate preservation | READY | mechanical | BLOCKING | PASS (no removals; SHA matches S2 baseline) |

### Layer-B-implementing-agent identifier

**claude** (AI agent; per S0 artifact §M-12 Initial Role Intent under PD-4 Y2). Identity rationale: AI scales for validator-script work and per-AAU validator invocations during Wave 1–6 authoring; aligns with Y2 per-AAU role-multiplexing model where Author = claude, Reviewer = cap2.

### Acceptance-check execution

Date: 2026-05-21 (descriptive only, not constitutionally load-bearing per Layer C §19).

Driver: `tools/step12_validators/run_dry_runs.py` invoked from repository root.

**Total dry-run assertions: 40 (PASS: 40; FAIL: 0).**

Aggregate result: all V1–V20 + FF1–FF5 are READY (mechanical / semi-mechanical) or MANUAL (V6, V20) with explicit dry-run validation. No validator has status DEFERRED.

### S4 gate satisfaction (per baseline-init §8)

| condition | result |
|---|---|
| 1. Every V1–V20 + FF1–FF5 has status READY-or-MANUAL | ✓ (14 mechanical + 4 semi-mechanical + 2 manual + 5 final-form wrappers = 25; all status'd) |
| 2. Every READY validator passes its dry-run | ✓ (40/40 PASS) |
| 3. V18 dry-run against existing baseline produces PASS | ✓ (REPLAY-IDENTICAL for self-comparison + cycle_0001 vs cycle_0002) |
| 4. Layer-B-implementing-agent identifier recorded | ✓ (claude) |
| 5. No validator DEFERRED | ✓ |

**S4 gate: PASSED.**

---

## §S4-marker-syntax decision

Per Layer B §20 deferral and pre-S0 readiness review A6 ambiguity (resolved at S4 time per `phase_4b_pre_s0_adjudications.md` §16.6 expectation):

| section | marker syntax |
|---|---|
| Rule | (implicit) clause-body content from start to `**Citations.**` marker |
| Citations | `**Citations.**` (inline bold; line-anchored start; followed by inline text or content on next line) |
| Note | `*Note.*` or `*Rationale.*` (inline italic; line-anchored start; followed by inline text or content on next line) |

This decision is consistent with the existing contract's `*Rationale.*` convention. The parser (`split_clause_body_into_sections` in `step12_validators.py`) accepts both alone-on-line and inline-with-text forms.

This decision does NOT mutate Layer B §3, §14, or §20. It records the operational choice the Layer-B-implementing-agent made within Layer B's explicit deferral.

---

## §S4-V18-baseline-references

V18 invocations consult the canonical replay baselines recorded at S2:

| scenario | events.jsonl SHA-256 |
|---|---|
| C | `a4e202891836af1c6ef6e0b2e27a33ee13a2a47dd8e12dff87f4307810196c75` |
| D | `fa71aef1ab7f4aafe8dcb27481dffed8fea5f112d5dfdc3b7b2ede6c04b0aee0` |
| E | `76bb808769ab3c0cb87df45edc1c2f56bddf0c8afea0c9ab2a61475e94286fc2` |
| F | `39c8291414a37706db10ace7e580401d4262413a7cd9eee394d49be08b71433c` |

Per Step 10 Direction A §P.1; validated 12/12 cycles bytewise identical under `--reopen-stage-between-cycles` isolation policy.

V18 invocation form: `python3 tools/check_session_replay_identity.py <session_a_path> <session_b_path>`. Returns L3 REPLAY-IDENTICAL / REPLAY-DIVERGENT verdict + observed events.jsonl SHA-256.

**S4 dry-run V18 evidence:** invoked against Step 8 Phase 6 `logs/phase_6_replay_identity/cycle_0001` (self-comparison) and `cycle_0001` vs `cycle_0002`. Both REPLAY-IDENTICAL with observed_sha=`2abc3031b994c32e05bb8d197ed60fb8c988813e4cd349d14814a2273294387a` (Step 8 baseline; distinct from Step 10 canonical baselines per S2). The dry-run validates the TOOL'S BEHAVIOR (it correctly produces REPLAY-IDENTICAL on byte-equal SessionPackages); the actual Step 10 baseline validation occurs at Wave V18 invocations during AAU authoring when Step 10 cycles are re-run.

---

## §S4-V15-finding (informational; not a gate failure)

V15 (heading-DAG structure) against the **real contract** (`docs/phase_4b_deterministic_semantics.md`) detects 3 pre-existing level-skip violations:

| line | violation | context |
|---|---|---|
| 11 | level skip 1→3 | `### Reading this document` follows `# Phase 4B...` title (no `##` intermediate) |
| 832 | level skip 1→4 | `#### 12.7.2 D-CONT-6a — Snapshot identity rule` within §12 nesting |
| 1106 | level skip 1→4 | `#### 13.5.1 D-FAULT-5a — Pose-on-FAIL semantic` within §13 nesting |

**These are pre-existing structural quirks in the contract; they are NOT Step-12-induced. They will NOT affect Step 12 AAU evaluations because:**

- Step 12 AAUs (per Layer A §3 mutation shapes: PTA, STA, FII, SF) do NOT introduce new sub-subsection nesting at the levels where the existing skips occur.
- PTA AAUs append at end-of-section; STA AAUs append at end-of-numbered-subsection; FII AAUs insert at intra-section positions but at existing nesting levels; SF AAUs modify §11 item 1 text without nesting changes.
- V15's per-AAU invocation will only flag NEW level skips introduced by an AAU's mutation, not pre-existing ones in unchanged sections.

**Constitutional posture:** the substrate is not corrupted by these pre-existing quirks; V15 correctly detects them; Step 12 work proceeds normally. A future Step-13+ contract hygiene pass may correct them via additive-supersession, but this is OUT OF Step 12 scope.

**Recorded as a substrate-level finding** for audit completeness, not as a Step-12 blocker.

---

## §S4-V11-V14-pre-mutation-baseline

V11 + V14 use `git diff docs/phase_4b_deterministic_semantics.md` as their evidence source. Pre-AAU (no staged changes), the diff is empty (zero deletions, zero insertions). Dry-run at S4 confirmed this state: V11 returned PASS with `deletions: 0; insertions: 0; A3 satisfied`.

During AAU authoring, V11 is invoked AFTER the Edit tool stages a contract mutation and BEFORE `git commit`. PASS requires: deletions == 0; insertions > 0. SF AAU is exempt from V11; uses V12 instead.

---

## §S4-substrate-stability-re-verification

At the moment of S4 attestation authoring, the substrate state matches S2's frozen captures:

| anchor | value | check |
|---|---|---|
| Contract SHA-256 | `2200d4fc45b2dcef7920d65a62bbfc2abf39ffeb19fef7c608e84c8908109f80` | re-verified via `sha256sum` post-S3 and pre-S4-commit; matches S2 |
| Contract line count | 1392 | unchanged |
| Clause-ID inventory | 121 | unchanged |
| D-FAULT-15 rows | 30 | unchanged |
| §0 glossary entries | 9 | unchanged |
| Replay baselines | 4 scenario hashes per S2 §S2-replay-baseline | unchanged |
| master HEAD | `6daf9b2c24edef63e81a832727eb191726f69afb` | unchanged |

**Substrate is at S2-frozen state throughout S4.** No contract mutation, no runtime mutation, no governance mutation occurred during S4.

---

## §S4-artifacts-produced

The S4 commit lands the following files (all new; all on `phase-4b-step12-codification`; not on `master`):

| path | size | purpose |
|---|---|---|
| `tools/step12_validators/step12_validators.py` | ~600 lines | All 25 validators as Python functions |
| `tools/step12_validators/run_dry_runs.py` | ~250 lines | S4 dry-run driver |
| `tools/step12_validators/synthetic/synthetic_contract.md` | ~20 lines | Synthetic contract fixture |
| `tools/step12_validators/synthetic/synthetic_clause_bodies.py` | ~70 lines | Synthetic clause-body fixtures |
| `tools/step12_validators/v06_v20_manual_checklists.md` | ~55 lines | Manual reviewer checklists |
| `tools/step12_validators/README.md` | ~125 lines | Validator catalog manifest |
| `docs/step12_audit_traces/s4_validator_availability_attestation.md` | (this file) | S4 attestation |

Validators live in `tools/step12_validators/` (under existing `tools/` root; co-located with other repo tooling). The audit attestation lives in `docs/step12_audit_traces/` per Layer D §20 audit-storage convention.

---

## §S4-authority-discipline-preserved

| invariant | preservation mechanism |
|---|---|
| replay-authoritative truth | V18 wraps existing replay tool; S2 baselines are read-only references in validator constants |
| additive-only mutation discipline | S4 commit is one additive commit; no in-place modifications |
| BRANCH-LINEARITY | S4 commit advances codification by 1 (no amend, no rebase, no force-push) |
| AUDIT-COMPLETENESS | this attestation records S4 outcomes durably |
| authority singularity | Layer-B-implementing-agent (claude) does NOT have gate authority; Reviewer + Decision-Owner retain gate authority |
| orchestration_tick supremacy | substrate untouched; runtime untouched |
| deterministic interruption boundaries | substrate untouched |
| contradiction preservation | substrate untouched; D-FAULT-9a text unchanged |
| transport independence | substrate untouched |
| no hidden cleanup | no opportunistic substrate modifications |
| no semantic widening | no clause text authored; validators are documentation-and-tooling only |

**Validators are advisory enforcement assistants. They do NOT redefine truth. The replay-authoritative substrate remains supreme.**

---

## §S4-V18-discipline

Per the brief and Layer B §7.1:

- V18 execution against substrate is DRY-RUN ONLY during S4.
- V18 may compare against S2 anchors (read-only).
- V18 may NOT mutate anchors (confirmed: no mutations).
- V18 may NOT redefine replay identity (confirmed: validator only compares; baseline remains the canonical reference).
- Any replay mismatch MUST trigger explicit HALT (confirmed: V18 returns BLOCKING failure on FAIL; calling code is expected to halt).
- Replay mismatch must NEVER be silently normalized (confirmed: validator reports the observed SHA + comparison verdict; no auto-correction).

S4 V18 dry-run produced PASS on byte-equal SessionPackages. The tool wraps cleanly. Subsequent Wave-time V18 invocations during AAU authoring will validate the actual Step 10 canonical baselines against fresh cycle SessionPackages.

---

## §S4-pd-3-w2-compliance

Per PD-3 W2 (recorded in S0 artifact):
* Map §11 checklists operationally authoritative.
* Baseline-init plan + Layer A/B/C/D plans constitutionally authoritative.
* In conflict, constitutional documents govern.

S4 execution followed map §11.X for operational sequencing (validator mechanization, dry-run execution, attestation authoring, commit) and baseline-init §8 + Layer B §3/§22 for constitutional discipline (validator catalog, mechanization breakdown, failure classes, authority bounds).

No conflict observed between map and baseline-init during S4 execution.

---

## §S4-commit-discipline (PD-2 Z1)

Commit message header form per PD-2 Z1 (recorded in S0 artifact): `Phase 4B Step 12 / Infrastructure — S4 validator mechanization`.

Commit composition: 7 new files (no modifications to existing tracked files; no deletions). Additive-only per Layer A §16 + BRANCH-LINEARITY.

---

## S5 admissibility statement

S4 is now COMPLETE per baseline-init §8 gate. Per baseline-init §9 + map §11.X, S5 (role activation) is CONSTITUTIONALLY PERMISSIBLE. S5 SHALL NOT be executed in the same session that executed S4 per the current session's brief constraint.

S5 will formalize:
* Author assignments per AAU (Y2 multiplexing)
* Reviewer assignments per AAU
* Constitutional Reviewer assignment (third party convened on T3/T8 escalation only)
* Layer-B-implementing-agent identifier (claude; inherited from S4)
* Role-briefing acknowledgments

---

**End of S4 validator availability attestation.**

Layer-B-implementing-agent: claude
Validators registered: 25 (V1–V20 + FF1–FF5)
Mechanization: 14 mechanical + 4 semi-mechanical + 2 manual + 5 final-form wrappers
Dry-run assertions: 40/40 PASS
V18 dry-run: PASS (REPLAY-IDENTICAL on byte-equal SessionPackages)
S4 gate: PASSED
Filing status: direct canonical path (post-S3)
