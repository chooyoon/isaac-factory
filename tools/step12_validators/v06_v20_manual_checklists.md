# V6 / V20 Manual Reviewer Checklists

**MANUAL validators per Layer B §22.** These checks cannot be mechanized at Layer B's depth; the Reviewer (per Layer C role) performs them by inspection during AAU review.

## V6 — Minimal-enforceable-surface check

**Scope.** All C-1 promoted clause bodies (per extraction-plan §7).

**Reviewer checks (inspect the Rule section only):**

```
[ ] The Rule section states the foreclosure or admittance only.
[ ] The Rule section does NOT include operational consequences (e.g., specific latency floors).
[ ] The Rule section does NOT include implementation details (e.g., "structural skip" mechanism).
[ ] The Rule section does NOT include derivation chains.
[ ] The Rule section does NOT include "borderline" or hedging qualifications.
[ ] The Rule section uses MUST / MUST NOT / FORBIDDEN / SHALL / MAY explicitly.
```

**Failure class:** SOFT. If a check fails, Reviewer flags REVISE per Layer C; Author revises; re-review.

**Per-AAU adjudication record:** the Reviewer records the V6 inspection result in the per-AAU decision artifact (`docs/step12_audit_traces/aau_<wave>_<id>_decision.md`).

---

## V20 — Normative-consistency check

**Scope.** All C-1 promoted clause bodies.

**Reviewer checks (inspect the new Rule against existing contract):**

```
[ ] The new MUST does not contradict any existing MUST NOT for the same subject.
[ ] The new MUST NOT does not contradict any existing MUST for the same subject.
[ ] The new admittance does not contradict any existing foreclosure.
[ ] The new foreclosure does not contradict any existing admittance.
[ ] Any clause-pair tension is explicitly acknowledged (e.g., D-FAULT-9c's override statement
    of D-FAULT-9a per V8).
[ ] The new clause's scope is consistent with the citation chain's transitive closure.
```

**Failure class:** SOFT. If a check fails, Reviewer flags REVISE; Author revises; or escalates per Layer D §8 if irresolvable (T3 SOFT-flag).

**Per-AAU adjudication record:** Reviewer records V20 inspection result in the per-AAU decision artifact.

---

## Reviewer adjudication authority

V6 and V20 are SOFT validators. Per Layer C §17 (non-authority constraints):
* Reviewer's V6/V20 verdict is recorded in the audit trail with explicit rationale.
* APPROVE-AS-IS verdicts MUST cite framework/precedent/scope-limit (never intuition).
* Default-to-escalate when unsure.

These checklists do not redistribute authority; they preserve Layer D §10 role types.
