"""Synthetic clause-body fixtures for V3/V4/V7/V8/V9/V12 dry-runs.

These are synthetic strings representing clause-body content that validators inspect.
Not real clauses; not for inheritance; not for citation.
"""

# Good clause body — passes V3 + V4 + V9 (no framework refs in Rule/Citations)
GOOD_CLAUSE_BODY_BASIC = """**D-SYN-X** — Synthetic clause. The session MUST behave deterministically.

**Citations.**
* Anchor: D-SYN-1, D-SYN-2
* Reference: D-EXEC-1

*Note.* Synthetic note for dry-run only. May cite framework references here: phase_4b_step11_extraction_plan.md §1.
"""

# Bad clause body — missing Citations section (V3 FAIL)
BAD_CLAUSE_BODY_MISSING_CITATIONS = """**D-SYN-Y** — Synthetic clause without citations. MUST do something.

This body has no Citations marker.
"""

# Bad clause body — framework ref leaks into Rule section (V9 FAIL)
BAD_CLAUSE_BODY_FRAMEWORK_LEAK = """**D-SYN-Z** — Synthetic clause. MUST behave per phase_4b_step11_extraction_plan.md §3.

**Citations.**
* Anchor: D-SYN-1
"""

# D-FAULT-9c shape — passes V8 (override-statement)
GOOD_D_FAULT_9C_BODY = """**D-FAULT-9c** — manual_advance restriction supersedes D-FAULT-9a.

This clause overrides D-FAULT-9a's manual_advance reservation. D-FAULT-9a's reservation
language is preserved verbatim for historical citation continuity.

**Citations.**
* Anchor: D-FAULT-9a
"""

# D-FAULT-9c shape — fails V8 (missing override verb)
BAD_D_FAULT_9C_BODY = """**D-FAULT-9c** — manual_advance restriction.

This clause restricts manual_advance. D-FAULT-9a is also relevant.

**Citations.**
* Anchor: D-FAULT-9a
"""

# D-FAULT-6b — has banned phrase from V7 seed (FAIL SOFT)
BAD_D_FAULT_6B_BODY = """**D-FAULT-6b** — Phase A observation. PAUSED is admissible when next-tick observation conditions hold.

**Citations.**
* Anchor: D-FAULT-6a
"""

# SF AAU — verbatim-prefix preservation (V12 properties S1-S3)
SF_OLD_STRING = "1. **`OperatorOverride` event commutativity.** Open."
SF_NEW_STRING_GOOD = (
    "1. **`OperatorOverride` event commutativity.** Open. "
    "CLOSED per Phase 4B step 11 (cf. Lemma L3 + D-INGRESS-4)."
)
SF_NEW_STRING_BAD = (
    "1. **`OperatorOverride` event commutativity.** Open."  # Replaced, but missing CLOSED
)

# D-FAULT-15 row dry-run fixtures
GOOD_D_FAULT_15_ROW = "| 31 | synthetic forbidden pattern X | D-SYN-1 |"
BAD_D_FAULT_15_ROW = "| 31 synthetic | D-SYN-1 |"  # Wrong number of pipes
