# Phase 4B Step 12 — Baseline Initialization Plan (Pre-Authoring Operational Bootstrap)

**Status: PRE-AUTHORING OPERATIONAL BOOTSTRAP PLAN (2026-05-21).** Defines the exact operational sequence that transitions the project from **AUTHORING-ADMISSIBLE** (constitutionally verified per [`phase_4b_step12_admissibility_evaluation.md`](phase_4b_step12_admissibility_evaluation.md)) to **AUTHORING-ACTIVE** (Wave 1's first AAU may begin). Inherits the four-layer pre-authoring transition-planning framework (Layers A/B/C/D) and the admissibility evaluation's operational prerequisites enumeration (§20).

Does **not** author clause wording. Does **not** mutate `phase_4b_deterministic_semantics.md`. Does **not** create any AAU. Does **not** introduce new validators, layers, or governance mechanisms. Does **not** authorize Step 12 to begin — authorization remains the Decision-Owner's prerogative (per Layer D §10, §25). This plan defines the *sequence* the Decision-Owner uses to operationalize authorization once granted.

---

## §1. Scope and inheritance

| inherited from | element |
|---|---|
| Admissibility evaluation §21 | AUTHORING-ADMISSIBLE verdict (constitutional precondition met) |
| Admissibility evaluation §20 | 6 operational prerequisites (this plan operationalizes them as 8 sequenced stages) |
| Layer A §5 | branch isolation strategy |
| Layer A §11 | commit-message convention |
| Layer A §15 | 8-stage per-AAU safety protocol (stage 1 baseline depends on this plan's S7 attestation) |
| Layer B §3 | validator catalog (this plan's S4 mechanizes them) |
| Layer C §10 | role types |
| Layer C §19 | audit-trace artifact schema |
| Layer D §2 | end-to-end pipeline state machine (this plan operationalizes the BASELINE → first WAVE-IN-PROGRESS transition) |
| Layer D §5 | codification-branch specifics |
| Layer D §10 | four named roles |
| Layer D §20 | audit-trace storage at `docs/step12_audit_traces/` |
| Layer D §22 | full audit-trail enumeration |

This plan specifies only the *operational bootstrap*. It does not alter any inherited mechanism, threshold, or invariant.

---

## §2. The five readiness dimensions

Operational readiness comprises five distinct dimensions; all five MUST reach a verified state before AUTHORING-ACTIVE is admissible:

| dimension | meaning | bootstrap stage |
|---|---|---|
| **D1 — Branch & repository readiness** | codification branch created from current master; clean working tree; no force-push history; tracking configured | S1 |
| **D2 — Role & agent readiness** | Author, Reviewer, Constitutional Reviewer, Layer-B-implementing-agent activated with explicit assignments; role-separation verified | S5 |
| **D3 — Tooling & validator readiness** | V1–V20 + FF1–FF5 mechanization implemented (mechanical and semi-mechanical) or manual-execution protocols in place (V6, V20) | S4 |
| **D4 — Audit infrastructure readiness** | `docs/step12_audit_traces/` directory exists; manifest in place; baseline-attestation artifact authored; audit-trail location confirmed writable | S3 + S7 |
| **D5 — Substrate baseline readiness** | pre-Step-12 contract SHA-256 captured; pre-Step-12 replay baseline captured (V18 reference); pre-Step-12 clause-ID inventory snapshotted (V16 reference) | S2 |

The five dimensions are independent in scope but sequenced in execution (D1 before D2-D4 mechanically; D5 in parallel with D3; D2 last).

---

## §3. The eight-stage bootstrap sequence

The bootstrap from AUTHORING-ADMISSIBLE → AUTHORING-ACTIVE proceeds in **8 sequential stages**:

| stage | name | dimension(s) | output |
|---|---|---|---|
| **S0** | Decision-Owner authorization | (governance) | authorization-decision artifact |
| **S1** | Codification-branch initialization | D1 | branch created; HEAD at base SHA |
| **S2** | Substrate baseline capture | D5 | baseline-attestation entries (contract SHA, replay baseline, clause-ID inventory) |
| **S3** | Audit-trace infrastructure initialization | D4 | `docs/step12_audit_traces/` directory + manifest |
| **S4** | Validator mechanization | D3 | validator-availability attestation (per-validator status) |
| **S5** | Role activation | D2 | role-assignment artifact (Author/Reviewer/Constitutional Reviewer activated) |
| **S6** | Pre-authoring environment freeze | (coordination) | environment-freeze acknowledgment artifact |
| **S7** | BASELINE attestation | all dimensions | consolidated `baseline_attestation.md` artifact (immutable) |
| **S8** | AAU-0 readiness gate | (state-machine transition) | PROCEED → AUTHORING-ACTIVE, or HALT → defects classified |

Each stage produces a durable artifact in `docs/step12_audit_traces/` (created at S3). Stages are sequential: stage N+1 may not begin until stage N's output is present and CONFIRMED.

**Sub-finding 3.A.** Total bootstrap artifact count after S0–S7 = 7 attestation artifacts + 1 directory + 1 manifest = 9 operational artifacts. None contains clause wording. None mutates the contract.

---

## §4. Stage S0 — Decision-Owner authorization

**Purpose.** Explicit, recorded decision by the Decision-Owner that Step 12 normative authoring is authorized to begin operational bootstrap.

**Preconditions.**

* Admissibility evaluation (`phase_4b_step12_admissibility_evaluation.md`) present and verdict = AUTHORING-ADMISSIBLE.
* Decision-Owner is identified and available.

**Activity.**

1. Decision-Owner reads the admissibility evaluation in full.
2. Decision-Owner consults any operational concerns outside the admissibility verdict (resource availability, scheduling, agent availability).
3. Decision-Owner makes the explicit authorization decision.

**Output artifact.**

`docs/step12_audit_traces/s0_authorization_decision.md` with schema:

```
- Decision-Owner identifier: <name or anonymized ID>
- Decision: AUTHORIZED
- Decision timestamp: <ISO-8601; descriptive only, not constitutionally load-bearing>
- Authorization basis: phase_4b_step12_admissibility_evaluation.md verdict §21 AUTHORING-ADMISSIBLE
- Initial role intent (per S5; finalized at S5): <Author=X; Reviewer=Y; Constitutional Reviewer=Z; Layer-B-implementing-agent=W>
- Acknowledgment: Decision-Owner has read admissibility evaluation §21 constitutional basis and §20 operational prerequisites
```

**Gate.** S0 complete iff artifact exists and Decision-Owner identifier is non-null.

**Alternate outcome.** If Decision-Owner decides NOT to authorize: this plan exits at S0; no further stages execute; the project remains in AUTHORING-ADMISSIBLE state indefinitely. This is a valid terminal state — admissibility is the framework's verdict; authorization is the Decision-Owner's choice.

---

## §5. Stage S1 — Codification-branch initialization

**Purpose.** Create the long-lived `phase-4b-step12-codification` branch per Layer D §5.

**Preconditions.**

* S0 complete.
* Current master HEAD is in expected state (no unexpected uncommitted changes; clean working tree).
* No prior `phase-4b-step12-codification` branch exists (or, if a prior abandoned branch exists, it has been explicitly archived or deleted per Decision-Owner direction).

**Activity (operational commands; not yet executed by this plan):**

```
# Sketch — actual execution at Decision-Owner direction.
git checkout master
git pull --ff-only origin master      # ensure local master matches remote
git checkout -b phase-4b-step12-codification
git push -u origin phase-4b-step12-codification
```

**Output artifact.**

`docs/step12_audit_traces/s1_branch_initialization.md` with schema:

```
- Branch name: phase-4b-step12-codification
- Branch base SHA: <40-char hash of master HEAD at creation>
- Branch HEAD SHA: <same as base SHA; no commits yet>
- Remote tracking: configured to <remote>/phase-4b-step12-codification
- Working tree status: clean (git status --porcelain returns empty)
```

**Gate.** S1 complete iff:

1. Branch exists locally and remotely.
2. Branch HEAD SHA equals branch base SHA (no commits on branch yet).
3. Working tree clean.
4. Branch is the current checkout.

**Failure modes.**

* Branch already exists: investigate (prior abandoned attempt?); Decision-Owner directs disposition; do NOT silently reuse.
* Working tree not clean: HALT at S1; resolve uncommitted changes before re-attempting.
* Remote push fails: investigate connectivity / permissions; HALT S1 until resolved.

---

## §6. Stage S2 — Substrate baseline capture

**Purpose.** Snapshot the pre-Step-12 substrate state so that Layer B's V11/V14/V16/V18 and Layer D's FF1/FF3/FF5 have an authoritative reference for later comparison.

**Preconditions.** S1 complete.

**Activity.**

1. **Contract SHA-256 capture.** Compute SHA-256 of `phase_4b_deterministic_semantics.md` at branch HEAD (which equals master HEAD).
2. **Replay baseline capture.** Confirm the existing Step 8/9/10 replay baselines are still valid: events.jsonl SHA-256 from the most recent validated cycle suite. Reference the existing post-Step-10 baseline established at Step 10 Direction A Phase 6 (per `cb95a9a` and prior closures). No new simulation runs required at S2 if existing baselines are still authoritative; otherwise re-run `tools/check_session_replay_identity.py` to produce a fresh baseline.
3. **Clause-ID inventory snapshot.** Extract the full list of existing clause-IDs from the contract (D-EXEC-*, D-SCHED-*, D-BUS-*, D-REPLAY-*, D-SESS-*, D-TRACE-*, D-LIFE-*, D-FORBID-*, D-SCALE-*, D-CONT-*, D-FAULT-*) for later V16 (new clause-ID uniqueness) reference.
4. **§11 open-extension item-1 text capture.** Record verbatim the current text of §11 open-extension item 1 (the `OperatorOverride` event commutativity entry) for later V12 (Properties S1–S3) reference when the SF AAU is authored.
5. **D-FAULT-15 row-count capture.** Confirm current D-FAULT-15 table has exactly 30 rows (per Step 10 Direction A closure).
6. **§0 glossary entry-count capture.** Confirm current §0 glossary has exactly 9 entries (per codification-plan §5).

**Output artifact.**

`docs/step12_audit_traces/s2_baseline_substrate_attestation.md` with schema:

```
- Contract document path: docs/phase_4b_deterministic_semantics.md
- Contract SHA-256: <64-char hash>
- Contract line count: <line count>
- Existing clause-ID count: <count>; full list attached
- §11 open-extension item-1 text (verbatim, 5-line capture): <text>
- D-FAULT-15 row count: 30
- §0 glossary entry count: 9
- Existing replay baseline: events.jsonl SHA-256 = <hash from post-Step-10 baseline>
- Replay baseline source: <commit SHA of last validated cycle, e.g., cb95a9a or subsequent>
- Replay-cycle policy: --reopen-stage-between-cycles (per Step 10 Direction A validation)
```

**Gate.** S2 complete iff:

1. All six capture entries present.
2. Contract SHA-256 is computable and stable (no concurrent file mutation).
3. Replay baseline reference resolves (the cited commit exists and the baseline events.jsonl SHA-256 is recorded).
4. D-FAULT-15 row count and §0 glossary count match the expected pre-Step-12 values (30 rows, 9 entries respectively). Mismatch indicates substrate has drifted since Step 10 closure; HALT and investigate.

**Read-only invariant.** S2 is purely read-only relative to the contract document. No mutation; no AAU creation; this stage only records the pre-Step-12 reference state.

---

## §7. Stage S3 — Audit-trace infrastructure initialization

**Purpose.** Create the persistent audit-trace directory and manifest where all Step 12 governance artifacts will live.

**Preconditions.** S0 complete (S1, S2 may proceed in parallel with S3 if desired; this plan sequences S3 after S2 for ordered output).

**Activity.**

1. Create directory `docs/step12_audit_traces/` on the codification branch.
2. Author manifest `docs/step12_audit_traces/README.md` declaring:
   * Purpose: Step 12 audit-trace storage per Layer D §20.
   * Schema reference: Layer C §19 audit-trace artifact schema.
   * Immutability: artifacts in this directory are append-only; modifications are additive (new artifact, not edit of existing).
   * Expected contents (post-completion): S0–S7 attestation artifacts + per-AAU decision artifacts (29) + per-wave-close decision artifacts (6) + per-escalation resolution artifacts (N) + S8 readiness-gate artifact.
3. Commit S3 setup as a discrete commit on the codification branch.

**Output artifact.**

`docs/step12_audit_traces/s3_audit_infrastructure_init.md` with schema:

```
- Directory path: docs/step12_audit_traces/
- Manifest path: docs/step12_audit_traces/README.md
- Manifest schema declared: yes
- Immutability convention declared: yes
- Directory commit SHA: <commit hash for S3 setup>
```

**Gate.** S3 complete iff:

1. Directory exists.
2. Manifest exists and contains the four required declarations (purpose, schema reference, immutability convention, expected contents).
3. S3 setup is committed (visible in `git log`).

**Layer A interaction note.** S3 produces the FIRST commit on the codification branch. This commit is NOT an AAU per Layer A §2 — it does not mutate `phase_4b_deterministic_semantics.md` and does not insert clause content. It is an infrastructure commit. Per Layer A §16, the no-amend discipline applies to AAU commits; infrastructure commits are not AAUs, but Layer D §5 branch-linearity applies (no amend, no force-push) — so S3's commit is effectively also no-amend.

---

## §8. Stage S4 — Validator mechanization

**Purpose.** Implement or verify each validator's invocation tooling such that V1–V20 and FF1–FF5 are runnable on demand during AAU authoring.

**Preconditions.** S1 complete (branch exists for any tooling that lives in-tree); S3 complete (audit trace location available for recording).

**Activity.** Per the Layer-B-implementing-agent activation:

| validator | mechanization activity | expected output |
|---|---|---|
| V1 anchor uniqueness (pre) | wrap `grep -Fc '<anchor>'` invocation | shell function or script |
| V2 anchor stability | substring check planned-mutation vs anchor | shell function or script |
| V3 template presence | markdown-section-aware parser; exact marker syntax fixed at S4 | parser script or module |
| V4 citation classification | parser detecting anchor/reference labels in Citations section | extension to V3 parser |
| V5 anchor-cite existing-clause | grep cited IDs in current contract | shell function |
| V6 minimal-enforceable-surface | manual; no automation | reviewer checklist annotation |
| V7 hidden-widening | per-AAU regex pass; per-AAU banned-phrase list fixed at S4 | regex tooling + per-AAU pattern files |
| V8 override-statement (D-FAULT-9c) | grep for required phrase patterns | shell function |
| V9 framework-ref confinement | section-aware parser scanning Sections A/B for framework refs | extension of V3/V4 parser |
| V10 D-FAULT-15 row format | markdown table parser; column-structure compare | parser script |
| V11 Properties A1–A3 | `git diff` shell pipeline (per Layer B §9 sketch) | shell function |
| V12 Properties S1–S3 | diff-aware inspector (per Layer B §10 sketch) | script or function |
| V13 anchor uniqueness (post) | repeat V1's grep post-mutation | wraps V1 |
| V14 existing-text byte preservation | implied by V11.A3 | wraps V11 |
| V15 heading-DAG structure | markdown heading parser; level + monotonicity check | parser script |
| V16 new clause-ID uniqueness | regex against contract for heading-anchor uniqueness | shell function |
| V17 cross-reference resolvability | grep cited IDs in post-mutation contract; verify framework-ref file paths | shell function |
| V18 replay-test invariant | wrap `tools/check_session_replay_identity.py` invocation | wraps existing tool |
| V19 inter-wave citation-gap | aggregate of V17 across wave commits | shell function |
| V20 normative consistency | manual; no automation | reviewer checklist annotation |
| FF1 final-form V18 | wraps V18 | wraps V18 |
| FF2 final-form V19 | wraps V19 over all 29 AAUs | wraps V19 |
| FF3 Step 12 completeness | aggregate completeness check per Layer D §12 | script combining grep+count |
| FF4 framework/contract separation aggregate | wraps V9 across all 17 new clause bodies | wraps V9 |
| FF5 substrate preservation | diff against S2 substrate baseline (contract SHA-256 + clause-ID inventory + §11 item-1 text) | script |

**Acceptance check (dry-run).** Before declaring S4 complete:

1. Each mechanical validator is invoked against a SYNTHETIC test case (not against `phase_4b_deterministic_semantics.md` for any reason that could be confused with authoring).
2. Synthetic test cases produce expected PASS / FAIL results.
3. V18 is dry-run against the existing post-Step-10 baseline; expected result: PASS (current replay baseline is byte-identical to itself).
4. V20 and V6: confirm reviewer-checklist annotations are produced (manual; no automation expected).

**Output artifact.**

`docs/step12_audit_traces/s4_validator_availability_attestation.md` with schema:

```
- For each validator V1–V20: name + mechanization status (READY / MANUAL / DEFERRED) + dry-run result if READY
- For each final-form check FF1–FF5: same
- Layer-B-implementing-agent identifier
- Acceptance-check execution timestamp
- Aggregate result: all validators READY-or-MANUAL with no DEFERRED
```

**Gate.** S4 complete iff:

1. Every V1–V20 and FF1–FF5 has status READY (mechanical / semi-mechanical) or MANUAL (V6, V20).
2. Every READY validator passes its dry-run.
3. V18 dry-run against existing baseline produces PASS.
4. Layer-B-implementing-agent identifier recorded.
5. No validator has status DEFERRED.

**Failure modes.**

* A mechanical validator cannot be implemented as planned: investigate root cause; if Layer B's specification has a gap, escalate per Layer D §8 (T5 anchor/shape requires Layer-A/B modification, applied to validator spec); revise Layer B and re-attempt S4.
* V18 dry-run FAILs: investigate (test harness regression? baseline drift since Step 10?). HALT S4 until resolved; this is a substrate-integrity concern.

---

## §9. Stage S5 — Role activation

**Purpose.** Specifically assign agents to each named role per Layer D §10 and verify role-separation invariant.

**Preconditions.** S0 complete (Decision-Owner indicated initial role intent in S0 artifact); S4 complete (Layer-B-implementing-agent identified and recorded).

**Activity.**

1. **Author assignment.** Decision-Owner names the Author. The Author MAY be a single agent or a defined sequence of agents (e.g., wave-by-wave). The S5 artifact records the assignment as a wave-by-wave or AAU-by-AAU mapping.
2. **Reviewer assignment.** Decision-Owner names the Reviewer (default single Reviewer per Layer C §15; multi-reviewer optional per Layer D §11).
3. **Constitutional Reviewer assignment.** Decision-Owner names at least one Constitutional Reviewer for T3/T8 escalations.
4. **Role-separation verification.** Confirm:
   * For each AAU: Author ≠ Reviewer.
   * For each escalation: Constitutional Reviewer ≠ Author AND ≠ Reviewer for the escalating AAU.
   * Layer-B-implementing-agent MAY be any of the above or none.
5. **Role-briefing acknowledgments.** Each named role-holder acknowledges they have read the relevant Layer documents:
   * Author: Layer A + Layer B (Stage 2 body validators relevant to drafting).
   * Reviewer: Layer C in full.
   * Constitutional Reviewer: Layer D §8.1 + Layer C §17 (anti-drift rules they are bound by).

**Output artifact.**

`docs/step12_audit_traces/s5_role_activation.md` with schema:

```
- Author assignments: per-AAU or per-wave mapping <agent identifier>
- Reviewer assignments: per-AAU or per-wave mapping <agent identifier>
- Constitutional Reviewer assignments: list of agents available <agent identifiers>
- Layer-B-implementing-agent: <agent identifier> (from S4)
- Decision-Owner: <agent identifier> (from S0)
- Role-separation verification: for each AAU, Author ≠ Reviewer confirmed
- Role-briefing acknowledgments: per agent, signed acknowledgment of read Layer docs
```

**Gate.** S5 complete iff:

1. Author, Reviewer, Constitutional Reviewer all assigned for at least Wave 1.
2. Role-separation invariant verified for all assigned AAUs in Wave 1 (forward assignments may be added later but Wave 1 must be complete).
3. All assigned role-holders have acknowledged role-briefing.

**Role-extension note.** Role assignments MAY extend wave-by-wave (Wave 2 assignments added after Wave 1 commences). S5 requires Wave 1's roles fully assigned; later waves' assignments may be added in supplementary S5 artifacts (`s5_role_activation_wave_N.md`) as needed. Each extension is additive per the audit-completeness invariant.

---

## §10. Stage S6 — Pre-authoring environment freeze

**Purpose.** Establish the operational convention that no Step-12-affecting changes occur outside the codification branch during authoring, and notify stakeholders.

**Preconditions.** S1–S5 complete.

**Activity.**

1. Decision-Owner notifies stakeholders (project members, contributors, anyone with master-push rights) that Step 12 authoring is about to commence on `phase-4b-step12-codification`.
2. Decision-Owner declares the "environment freeze" convention:
   * Master MAY receive non-Step-12 changes during authoring; codification branch will NOT rebase.
   * If master receives changes, the final PR (Layer D §6) handles integration via merge commit per Layer D §19.
   * No stakeholder will attempt to push Step-12-content changes outside the codification branch.
3. Stakeholders acknowledge.

**Output artifact.**

`docs/step12_audit_traces/s6_environment_freeze_acknowledgment.md` with schema:

```
- Freeze announcement timestamp: <ISO-8601>
- Stakeholders notified: <list>
- Acknowledgments received: <list>
- Freeze convention summary: per §10 above
- Anticipated authoring start: <Decision-Owner intent; informational only>
```

**Gate.** S6 complete iff:

1. Stakeholders notified.
2. Freeze convention recorded.
3. (Acknowledgments are operationally desired but not strictly BLOCKING — the freeze is a Decision-Owner declaration regardless of acknowledgments; missing acknowledgments are documented but do not HALT.)

**Operational note.** S6 is the most lightweight stage. Its primary purpose is to ensure no stakeholder is surprised by Step 12 activity on the codification branch. It does not impose constitutional constraints beyond what Layer D §5 already enforces.

---

## §11. Stage S7 — BASELINE attestation

**Purpose.** Author the single consolidated attestation artifact summarizing all of S0–S6, declaring that BASELINE has been established.

**Preconditions.** S0–S6 all complete.

**Activity.**

1. Read each S0–S6 artifact.
2. Verify each artifact's gate was satisfied.
3. Author the consolidated baseline attestation.
4. Commit the artifact on the codification branch (as a discrete infrastructure commit, NOT an AAU).

**Output artifact.**

`docs/step12_audit_traces/s7_baseline_attestation.md` with schema:

```
# Step 12 BASELINE Attestation

- S0 Authorization decision: CONFIRMED (reference: s0_authorization_decision.md)
- S1 Branch initialization: CONFIRMED
    - Branch: phase-4b-step12-codification
    - Base SHA: <hash>
- S2 Substrate baseline capture: CONFIRMED
    - Contract SHA-256: <hash>
    - Replay baseline events.jsonl SHA-256: <hash>
    - Existing clause-ID count: <N>
    - D-FAULT-15 row count: 30
    - §0 glossary entry count: 9
    - §11 item-1 text captured: yes
- S3 Audit-trace infrastructure: CONFIRMED
    - Directory: docs/step12_audit_traces/
    - Manifest: present
- S4 Validator availability: CONFIRMED
    - All V1–V20: READY-or-MANUAL
    - All FF1–FF5: READY-or-MANUAL
    - Layer-B-implementing-agent: <identifier>
    - V18 dry-run: PASS
- S5 Role activation: CONFIRMED
    - Author (Wave 1): <identifier>
    - Reviewer (Wave 1): <identifier>
    - Constitutional Reviewer: <identifier>
    - Role-separation invariant: VERIFIED for Wave 1
    - Briefing acknowledgments: complete
- S6 Environment freeze: CONFIRMED
    - Stakeholders notified
    - Convention declared

# Aggregate BASELINE Verdict: ESTABLISHED

# Attestation timestamp: <ISO-8601; descriptive only>
# Attestation author: Decision-Owner <identifier>
```

**Gate.** S7 complete iff:

1. All six S0–S6 confirmations present and verified.
2. Aggregate verdict = ESTABLISHED.
3. Artifact is committed.
4. Decision-Owner has authored the attestation (or explicitly delegated; delegation recorded).

**Immutability.** Per Layer D §20, the S7 attestation is immutable after creation. Errors are corrected by appending a supersession artifact (`s7_baseline_attestation_correction_<N>.md`); the original is preserved.

---

## §12. Stage S8 — AAU-0 readiness gate (transition to AUTHORING-ACTIVE)

**Purpose.** The final operational gate. PROCEED transitions the pipeline from BASELINE → first WAVE-IN-PROGRESS (Wave 1's AAU 1 may begin). HALT classifies defects and requires resolution before re-attempting.

**Preconditions.** S0–S7 all complete; S7 attestation present.

**Activity (the AAU-0 readiness checklist).**

The Decision-Owner (or delegated role) performs the following 14-point checklist:

| # | check | mechanism | result |
|---|---|---|---|
| 1 | S7 baseline attestation present and ESTABLISHED | inspect `s7_baseline_attestation.md` | ✓ / ✗ |
| 2 | Codification branch HEAD is at expected state (S7 attestation SHA chain valid) | `git log --oneline` matches expected: master-base + S3 infrastructure commit + S7 attestation commit | ✓ / ✗ |
| 3 | Working tree clean | `git status --porcelain` returns empty | ✓ / ✗ |
| 4 | No uncommitted changes | implied by #3 | ✓ / ✗ |
| 5 | Contract document byte-identical to S2 baseline | re-compute SHA-256; compare to S2-captured SHA-256 | ✓ / ✗ |
| 6 | Replay baseline reference still valid | re-run V18 dry-run; expect PASS | ✓ / ✗ |
| 7 | All validators V1–V20 still READY-or-MANUAL | re-inspect S4 attestation; quick smoke test of one mechanical validator | ✓ / ✗ |
| 8 | All FF1–FF5 still READY-or-MANUAL | same as #7 | ✓ / ✗ |
| 9 | Wave 1 Author assigned and briefed | inspect S5 artifact | ✓ / ✗ |
| 10 | Wave 1 Reviewer assigned and briefed | inspect S5 artifact | ✓ / ✗ |
| 11 | Constitutional Reviewer assigned and briefed | inspect S5 artifact | ✓ / ✗ |
| 12 | Role-separation invariant verified for Wave 1's 4 AAUs (D-FAULT-6b, D-FAULT-6c, D-SCHED-14, D-REPLAY-10) | inspect S5 artifact | ✓ / ✗ |
| 13 | Audit-trace directory writable; no prior AAU artifacts present | inspect `docs/step12_audit_traces/` | ✓ / ✗ |
| 14 | No pending operational concerns (Decision-Owner declaration) | Decision-Owner attestation | ✓ / ✗ |

**Decision.**

* **All 14 checks ✓ → PROCEED.** Pipeline state transitions BASELINE → WAVE-IN-PROGRESS (Wave 1). Wave 1's first AAU (recommended: D-FAULT-6b per Layer A §9 Wave 1 sequence — the FII order requires D-FAULT-6b before D-FAULT-6c, and the four-AAU Wave 1 can otherwise begin with any of the independent T-promotions) may begin Layer A stage 1.
* **Any check ✗ → HALT.** Classify defects per §15 (operational readiness classification); resolve; re-attempt S8.

**Output artifact.**

`docs/step12_audit_traces/s8_aau_zero_readiness_gate.md` with schema:

```
- Gate evaluation timestamp: <ISO-8601>
- Gate evaluator: Decision-Owner <identifier>
- 14-point checklist results: per-check ✓ / ✗ + per-check evidence reference
- Aggregate result: PROCEED / HALT
- If PROCEED: pipeline state transitioned to WAVE-IN-PROGRESS at <timestamp>; first AAU may begin
- If HALT: defect classification per §15; resolution path
```

**Gate.** S8 PROCEED iff all 14 checks ✓ AND Decision-Owner declares PROCEED. S8 HALT iff any check ✗ OR Decision-Owner declares HALT for operational reasons.

**Sub-finding 12.A.** S8 is the operational analogue of Layer C's wave-close gate. Like the wave-close gate, S8 has only two outcomes (PROCEED or HALT/ESCALATE-equivalent); no middle ground; no "proceed with caveat."

---

## §13. The AAU-0 readiness checklist — detailed breakdown

The §12 14-point checklist categorized:

| category | check #s | nature |
|---|---|---|
| Attestation integrity | 1, 2 | inspect prior artifacts; confirm chain |
| Branch hygiene | 3, 4 | working-tree clean; no surprise commits |
| Substrate stability | 5, 6 | contract + replay baseline byte-stable since S2 |
| Tooling availability | 7, 8 | validators still operational |
| Role readiness | 9, 10, 11, 12 | agents assigned, briefed, role-separation verified |
| Audit readiness | 13 | directory writable, no contamination from prior abandoned attempts |
| Operational sign-off | 14 | Decision-Owner final attestation |

**Mechanical vs manual breakdown:**

* Mechanical (8 checks): #2, #3, #4, #5, #6, #7 (smoke test), #8 (smoke test), #13.
* Manual (6 checks): #1 (inspect artifact), #9, #10, #11, #12, #14.

Roughly 57% mechanical, 43% manual. The manual checks are inspection or attestation, not judgment.

---

## §14. Replay-baseline capture protocol (S2 detail)

**Why replay-baseline capture matters.** Layer B's V18 (replay-test invariant) and Layer D's FF1 (final-form replay check) require an authoritative reference SessionPackage SHA-256 to compare against. S2 captures that reference; subsequent V18 invocations during authoring confirm post-AAU SessionPackages match the reference.

**Replay-baseline source.** The existing Step 10 Direction A baseline (post-`cb95a9a` validated cycles) is the recommended reference. Per memory: "12/12 cycles bytewise replay-identical under the validated --reopen-stage-between-cycles isolation policy" — this baseline is mature and proven.

**S2 verification activity.**

1. Locate the most recent validated SessionPackage from Step 10 Direction A closure.
2. Compute its events.jsonl SHA-256.
3. Record in S2 attestation as `<hash>`.
4. This hash becomes V18's "expected" value for all 8 BLOCKING + 5 RECOMMENDED V18 invocations during Step 12 authoring.

**What V18 actually checks during AAU authoring.** V18 confirms that re-running `tools/check_session_replay_identity.py` against the codification-branch HEAD produces a SessionPackage whose events.jsonl SHA-256 matches the S2-captured reference. Because Step 12 AAUs are documentation-only (per the framework/contract separation), V18 should always PASS — the runtime is unchanged. V18's role is the safety net catching unintended runtime coupling.

**Re-baseline conditions.** If V18 dry-run at S4 FAILs, S2's baseline is invalid. Re-baseline by re-running the cycle suite on current master; capture fresh hash; update S2 attestation via correction-supersession artifact (per §11 immutability). HALT S2 until baseline is stable.

---

## §15. Operational readiness classification

If any S0–S8 stage fails its gate:

| classification | meaning | recovery |
|---|---|---|
| **READY** | all S0–S7 complete; S8 PROCEED | proceed to AUTHORING-ACTIVE |
| **BLOCKED-AT-STAGE-S<N>** | S0..S(N-1) complete; stage S<N> has unresolved defect | resolve S<N>; if not resolvable, escalate per Layer D §8 (likely T5 anchor/shape requires modification, applied to this plan's stage S<N>) |
| **HALTED-AT-S8** | S0–S7 complete; S8 returned HALT | classify which of the 14 checks failed; resolve; re-attempt S8 |
| **AUTHORIZATION-DEFERRED** | S0 not completed (Decision-Owner chose not to authorize) | terminal state until Decision-Owner re-evaluates; project remains in AUTHORING-ADMISSIBLE indefinitely |

**Sub-finding 15.A.** Operational readiness has four named states. None of them are "partial readiness." Either AUTHORING-ACTIVE is achieved (READY + S8 PROCEED) or it is not.

---

## §16. Operational handoff boundaries

| handoff | trigger | precondition |
|---|---|---|
| Decision-Owner → Layer-B-implementing-agent | S0 complete | Decision-Owner names the implementing agent |
| Layer-B-implementing-agent → all role-holders | S4 complete | validators available for use |
| Decision-Owner → Author | S5 complete (Author assigned and briefed) | role-separation verified |
| Decision-Owner → Reviewer | S5 complete (Reviewer assigned and briefed) | role-separation verified |
| Decision-Owner → first AAU author | S8 PROCEED | all 14 checks ✓ |
| Author → Reviewer | per Layer C §20 (after each AAU commit) | (during authoring, not part of baseline init) |
| Reviewer → Constitutional Reviewer | per Layer D §8.1 (T3/T8 escalation) | (during authoring) |

Baseline initialization handoffs are bounded to S0–S8. Authoring-time handoffs (Author → Reviewer per AAU; Reviewer → Constitutional Reviewer per escalation) are governed by Layers C and D.

---

## §17. Escalation-channel initialization

Pre-authoring, the 8 escalation triggers (T1–T8 per Layer D §8) have defined resolution paths. Bootstrap requires:

1. **T1/T2 (V18/V19 FAIL)** — resolution mechanism: revert + investigate. Channel: any role-holder reports; investigation by Layer-B-implementing-agent + Author. Already operationally reachable via S4+S5.
2. **T3/T8 (irresolvable SOFT flag / reviewer uncertainty)** — resolution venue: constitutional review per Layer D §8.1. Channel: convene Author + Reviewer + Constitutional Reviewer. Requires Constitutional Reviewer to be reachable; S5 confirms assignment.
3. **T4 (fresh constitutional principle)** — resolution: Step 11 re-opening. Channel: notify Decision-Owner; halt Step 12. Always reachable.
4. **T5 (anchor/shape requires Layer-A modification)** — resolution: revise Layer A plan. Channel: notify Decision-Owner; engage framework holders for Layer A revision.
5. **T6 (REJECTED AAU per Layer B §17)** — resolution: codification + extraction plan re-evaluation. Channel: notify Decision-Owner.
6. **T7 (NOT-CONFIRMED preserved invariant)** — resolution: immediate pause; root-cause investigation. Channel: notify Decision-Owner urgently.

**S5 + S6 implicitly initialize escalation channels** by ensuring all role-holders are identified and have communication paths. No separate "escalation initialization" stage is required; S5 + S6 suffice.

---

## §18. Pre-authoring rollback readiness

If baseline initialization itself fails (S8 HALT or any S0–S7 stage blocks), the rollback is trivial:

* No AAU commits exist (only infrastructure commits S3 and S7).
* No contract mutations have occurred.
* The codification branch may be retained (for re-attempt) or deleted (for clean restart).
* The BASELINE attestation artifacts (S0–S7) are preserved in `docs/step12_audit_traces/` — they record that the initialization attempt occurred even if it did not reach PROCEED.

**No rollback at the substrate level is needed** because no substrate mutation has occurred during baseline initialization. The substrate state is identical to pre-S0.

**Sub-finding 18.A.** Baseline initialization is fully reversible. The investment cost of a failed S8 is the S0–S7 setup time; no constitutional impact.

---

## §19. Step-12-start gate definition (formal)

**The Step-12-start gate is exactly Stage S8.**

| input | output |
|---|---|
| BASELINE state (S0–S7 complete) | one of PROCEED or HALT |
| PROCEED | pipeline state transitions BASELINE → WAVE-IN-PROGRESS (Wave 1); first AAU may begin Layer A stage 1; the project is now in AUTHORING-ACTIVE state |
| HALT | pipeline remains in BASELINE; defects classified per §15; resolution per §17 if escalation needed |

The gate is binary. No partial PROCEED.

The gate is the formal moment when "AUTHORING-ADMISSIBLE" becomes "AUTHORING-ACTIVE." Before S8 PROCEED, the contract is untouched; after S8 PROCEED, the first AAU may begin (which itself is governed by Layer A's 8-stage safety protocol per AAU).

---

## §20. Forbidden operations during baseline initialization

Per the session brief, the following operations are FORBIDDEN during S0–S8:

| forbidden | rationale |
|---|---|
| Authoring AAUs | AAUs may only begin after S8 PROCEED |
| Mutating `phase_4b_deterministic_semantics.md` | the contract is read-only during baseline init; S2 captures it byte-stably |
| Running validators against the actual contract document for purposes other than (a) S2 SHA-256 capture, (b) V18 dry-run at S4, (c) S8 #5 SHA re-check, (d) S8 #6 V18 re-dry-run | the contract is the artifact under future mutation; pre-AAU runs are read-only |
| Skipping any stage S0–S8 | sequencing is BLOCKING; each stage's gate is BLOCKING for the next |
| Combining stages out of order | sequencing depends on prior outputs as preconditions |
| Recording fake or proxy attestations | violates AUDIT-COMPLETENESS invariant |
| Force-pushing the codification branch | violates BRANCH-LINEARITY invariant |
| Rebasing the codification branch | violates BRANCH-LINEARITY invariant |
| Amending S3 or S7 infrastructure commits | violates Layer A §16 no-amend (extended cross-stage per Layer D §14 + §18) |
| Creating supplementary branches forking from the codification branch | violates branch-isolation rationale (Layer D §5) |
| Authoring clause text in any artifact | this plan is operational; no clause wording authored |

---

## §21. Preserved invariants under baseline initialization

All 24 inherited invariants preserved:

| invariant | preservation mechanism |
|---|---|
| replay-authoritative truth | S2 captures replay baseline; S4 dry-runs V18; S8 #6 re-confirms; substrate unmutated |
| append-only causality | S3 and S7 infrastructure commits are additive; no amends; no force-push |
| authority singularity | Decision-Owner authorization is bounded (per Layer D §10, §13 G8) to operational sign-off, not substrate decisions |
| orchestration_tick supremacy | V18 dry-runs and re-runs verify; no AAU yet |
| deterministic interruption boundaries | substrate unmutated |
| Phase-A-only observability | substrate unmutated |
| contradiction preservation | substrate unmutated; D-FAULT-9a text unchanged through S0–S8 |
| transport independence | substrate unmutated |
| no hidden cleanup | no mutation; S2 captures pre-Step-12 state for later FF5 comparison |
| no wall-clock authority | S0/S2/S6/S7/S8 timestamps are descriptive only, not normative (per Layer C §19) |
| no adaptive semantics | substrate unmutated |
| framework/contract separation | no clause text in any baseline artifact; framework references only in attestation references to prior framework docs |
| additive-only mutation discipline | the only mutations during S0–S8 are: branch creation, directory creation, artifact creations in `docs/step12_audit_traces/`; none mutate the contract |
| replay-preserving extraction safety | substrate unmutated; replay baseline captured for later verification |
| validator supremacy over reviewer intuition | reviewer not active during baseline init; S5 confirms reviewer roles for use during authoring |
| no semantic widening authority | baseline initialization introduces no constitutional principles |
| no reviewer discretionary reinterpretation | reviewer not active |
| no hidden override pathways | all baseline-init actions produce durable artifacts; no shadow operations |
| no authority redistribution | role-types per Layer D §10 unchanged; baseline init only ASSIGNS agents to existing role types |
| WAVE-ATOMICITY | no waves begin during baseline init |
| BRANCH-LINEARITY | S3, S7 commits are linear; no rebase, no force-push, no amend |
| MERGE-ATOMICITY | no merge during baseline init |
| AUDIT-COMPLETENESS | every S0–S8 stage produces a durable, immutable artifact |
| ROLE-SEPARATION | verified at S5 for Wave 1 |

All preserved at the operational-bootstrap level.

---

## §22. Baseline-initialization completion verdict

After successful execution of S0–S8 with S8 PROCEED:

* **BASELINE-INITIALIZATION-COMPLETE.**
* The project state transitions from AUTHORING-ADMISSIBLE → AUTHORING-ACTIVE.
* The pipeline state machine (Layer D §2) is now in WAVE-IN-PROGRESS (Wave 1).
* The first AAU (D-FAULT-6b recommended, per Layer A §9 Wave 1 sequence constraint that D-FAULT-6b precedes D-FAULT-6c; D-SCHED-14 or D-REPLAY-10 are also admissible as first AAU since they are order-independent within Wave 1) may begin Layer A stage 1 of its 8-stage safety protocol.

The first AAU is governed by all four layers (A, B, C, D) operating in concert; baseline initialization's role concludes at S8 PROCEED.

---

## §23. Vocabulary

Baseline initialization introduces several operational terms; none enter the normative contract:

| term | meaning | scope |
|---|---|---|
| BASELINE state | the project state during S0–S8, pre-AUTHORING-ACTIVE | this plan |
| AUTHORING-ACTIVE state | the project state after S8 PROCEED; Wave 1 may begin | this plan + Layer D state machine |
| BASELINE attestation | the consolidated S7 artifact | this plan |
| AAU-0 readiness gate | the formal S8 gate | this plan |
| Operational handoff boundary | the moment when one role's bootstrap responsibility transfers to another | this plan |
| Validator-availability attestation | the S4 output | this plan |
| Substrate baseline | the S2-captured pre-Step-12 reference state | this plan + Layer B + Layer D |

None receive clause IDs. Per "no namespace churn" — purely baseline-initialization vocabulary.

---

## §24. Baseline-initialization planning verdict

**BASELINE INITIALIZATION PLAN: READY.**

* 8-stage bootstrap sequence specified (S0–S8) covering 5 readiness dimensions (D1–D5).
* Each stage has explicit preconditions, activities, output artifact schema, and gate.
* AAU-0 readiness gate (S8) defined with 14-point checklist.
* Replay-baseline capture protocol detailed (§14).
* Operational readiness classification (§15) gives 4 named states.
* Operational handoff boundaries enumerated (§16).
* Escalation channels initialized via S5 + S6 (§17).
* Pre-authoring rollback is trivial (§18).
* Step-12-start gate formally defined as S8 (§19).
* Forbidden operations enumerated (§20).
* All 24 inherited invariants preserved (§21).
* Plan does NOT begin authoring, mutate contract, create AAUs, or alter any constitutional mechanism.

This plan does NOT itself authorize Step 12 to begin. It specifies the operational sequence the Decision-Owner uses once authorization is granted. The Decision-Owner's authorization at S0 is the consequential decision; this plan provides the mechanical path from authorization to first-AAU readiness.

---

**End of Step 12 baseline initialization plan.**

Predecessors: [Step 11 live-ingress analysis](phase_4b_step11_live_ingress_analysis.md), [admissibility framework](phase_4b_step11_admissibility_framework.md), [F58 PAUSED](phase_4b_step11_f58_paused_analysis.md), [F59 manual_advance](phase_4b_step11_f59_manual_advance_analysis.md), [closure verification](phase_4b_step11_closure_verification.md), [codification plan](phase_4b_step11_codification_plan.md), [meta-audit](phase_4b_step11_meta_audit.md), [extraction plan](phase_4b_step11_extraction_plan.md), [Layer A authoring mechanics](phase_4b_step12_authoring_mechanics_plan.md), [Layer B per-clause validation](phase_4b_step12_validation_plan.md), [Layer C review ergonomics](phase_4b_step12_review_ergonomics_plan.md), [Layer D cross-clause governance](phase_4b_step12_governance_plan.md), [admissibility evaluation](phase_4b_step12_admissibility_evaluation.md). Constitutional substrate: [phase_4b_deterministic_semantics.md](phase_4b_deterministic_semantics.md).

Successor: AUTHORING-ACTIVE (Wave 1 AAU 1, governed by Layers A/B/C/D in concert) at S8 PROCEED.
