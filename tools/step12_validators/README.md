# Step 12 Validator Catalog

Mechanized V1–V20 + FF1–FF5 per `docs/phase_4b_step12_validation_plan.md` (Layer B) §3 + §22. Authored at S4 time by the Layer-B-implementing-agent (claude, per S0 §M-12 Initial Role Intent under PD-4 Y2).

**Constitutional posture.** Validators are advisory only. They detect violations; they do NOT mutate substrate, do NOT auto-correct, do NOT redefine truth. The replay-authoritative substrate (V18 baselines from S2) governs in any conflict. Per PD-3 W2: baseline-init plan + Layer A/B/C/D plans remain constitutionally authoritative.

---

## Contents

| file | purpose |
|---|---|
| `step12_validators.py` | All 25 validators as Python functions (V1–V20 + FF1–FF5) |
| `run_dry_runs.py` | S4 dry-run driver — exercises every validator against synthetic + real fixtures |
| `synthetic/synthetic_contract.md` | Minimal synthetic contract for V1/V5/V13/V15/V16/V17/V19/FF3/FF5 dry-runs |
| `synthetic/synthetic_clause_bodies.py` | Synthetic clause-body strings for V3/V4/V7/V8/V9/V10/V12/FF4 dry-runs |
| `v06_v20_manual_checklists.md` | MANUAL checklists for V6 + V20 (Reviewer-performed at Layer C time) |

---

## Marker syntax decision (S4)

Per Layer B §20 deferral and readiness review A6 ambiguity resolution: clause-body sections use the following marker syntax:

| section | marker |
|---|---|
| Rule | clause-body content before `**Citations.**` marker (no explicit marker; implicit prefix) |
| Citations | `**Citations.**` (inline bold, line-anchored; followed by inline text or content on next line) |
| Note | `*Note.*` or `*Rationale.*` (inline italic, line-anchored; followed by inline text or content on next line) |

The parser (`split_clause_body_into_sections` in `step12_validators.py`) accepts both `**Citations.**` alone-on-line and `**Citations.** <inline text>`. Same for Note/Rationale.

---

## Validator catalog (summary)

| ID | name | stage | mechanization | failure class |
|---|---|---|---|---|
| V1 | Anchor uniqueness (pre) | 1 | mechanical (`grep -Fc`) | BLOCKING |
| V2 | Anchor stability | 1 | mechanical (substring check) | BLOCKING |
| V3 | Three-section template presence | 2 | semi-mechanical (markdown section parser) | BLOCKING |
| V4 | Citation classification | 2 | semi-mechanical | BLOCKING |
| V5 | Anchor-cite existing-clause | 2 | mechanical | BLOCKING |
| V6 | Minimal-enforceable-surface | 2 | MANUAL | SOFT |
| V7 | Hidden-widening-language scan | 2 | semi-mechanical (per-AAU banned phrases) | SOFT |
| V8 | Override-statement presence (D-FAULT-9c) | 2 | mechanical | BLOCKING |
| V9 | Framework-reference confinement | 2 | semi-mechanical | BLOCKING |
| V10 | D-FAULT-15 row format | 2 | mechanical | BLOCKING |
| V11 | Properties A1–A3 (non-SF) | 3 | mechanical (`git diff`) | BLOCKING |
| V12 | Properties S1–S3 (SF) | 3 | mechanical | BLOCKING |
| V13 | Anchor uniqueness (post) | 3 | mechanical (wraps V1) | BLOCKING |
| V14 | Existing-text byte preservation | 3 | mechanical (wraps V11) | BLOCKING |
| V15 | Heading-DAG structure | 3 | semi-mechanical (markdown heading parser) | BLOCKING |
| V16 | New clause-ID uniqueness | 3 | mechanical | BLOCKING |
| V17 | Cross-reference resolvability | 3 | mechanical | BLOCKING |
| V18 | Replay-test invariant | 4 | mechanical (wraps `tools/check_session_replay_identity.py`) | BLOCKING |
| V19 | Inter-wave citation-gap | 4 | mechanical (aggregate of V17) | BLOCKING |
| V20 | Normative-consistency | 4 | MANUAL | SOFT |
| FF1 | Final-form V18 | post-Wave-6 | mechanical (wraps V18) | BLOCKING |
| FF2 | Final-form V19 | post-Wave-6 | mechanical (wraps V19) | BLOCKING |
| FF3 | Step 12 completeness | post-Wave-6 | mechanical | BLOCKING |
| FF4 | Framework/contract separation aggregate | post-Wave-6 | mechanical (wraps V9) | BLOCKING |
| FF5 | Substrate preservation vs S2 baseline | post-Wave-6 | mechanical | BLOCKING |

Total: 14 mechanical + 4 semi-mechanical + 2 MANUAL + 5 final-form wrappers = 25 validators.

---

## Invocation

```bash
# Print registry status
python3 tools/step12_validators/step12_validators.py

# Run all dry-runs against synthetic + real fixtures
python3 tools/step12_validators/run_dry_runs.py
```

Per Layer B §15 invocation sequencing: during AAU authoring, validators are invoked in stage order (1 → 2 → 3 → 4) per AAU. The dry-run driver exercises representative cases per validator; full per-AAU invocation is the Author's + Reviewer's responsibility during authoring.

---

## Substrate anchors (frozen by S2)

Embedded in `step12_validators.py` as constants:

* `S2_CONTRACT_SHA256 = "2200d4fc45b2dcef7920d65a62bbfc2abf39ffeb19fef7c608e84c8908109f80"`
* `S2_CLAUSE_ID_COUNT = 121`
* `S2_D_FAULT_15_ROW_COUNT = 30`
* `S2_SECTION_0_GLOSSARY_COUNT = 9`
* `S2_REPLAY_BASELINES_BY_SCENARIO` (4 per-scenario events.jsonl SHA-256 hashes from Step 10 §P.1)
* `S2_REPLAY_CYCLE_POLICY = "--reopen-stage-between-cycles"`

These are read-only references. Validators consult them but never mutate them.

---

## Authority discipline

Per Layer B §22 + Layer D §10:

* Validators are **constitutional enforcement assistants**, not constitutional authorities.
* Validator output flows into the Reviewer's adjudication per Layer C; the Reviewer's verdict is recorded in per-AAU decision artifacts.
* SOFT validators (V6, V7, V20) flag for adjudication but do NOT block commits; the Reviewer makes final calls.
* BLOCKING validators (15 of 25) prevent commit on FAIL; the Author must revise and re-run.
* Validators do NOT redistribute authority; role-types per Layer D §10 are unchanged.

---

## Mutation discipline

* Validators are READ-ONLY against the substrate.
* Validators MUST NOT modify any file in `docs/phase_4b_deterministic_semantics.md`, `isaac_factory/`, `tools/` (other than dry-running their own scripts), or `scripts/`.
* Validators MUST NOT mutate the replay baseline reference (S2's recorded SHAs).
* Validators MUST NOT create commits, push, or rebase.
* Validators MUST NOT auto-correct; corrections route through Author + Reviewer per Layer C/D.

---

## V7 banned-phrase list

Per Layer B §5.5: V7's effective list is per-AAU. The seed list (per extraction-plan §8) is embedded in `step12_validators.py` as `V7_BANNED_PHRASES_SEED`. The Layer-B-implementing-agent (claude) extends the list per AAU during authoring; extensions are recorded in the per-AAU decision artifact in the audit-trace dir.
