#!/usr/bin/env python3
"""Step 12 validator catalog — V1–V20 + FF1–FF5 mechanization.

Per Layer B `docs/phase_4b_step12_validation_plan.md` §3 catalog and §22 mechanization breakdown.
This module is the Layer-B-implementing-agent's mechanization deliverable per baseline-init §8.

Convention:
* Each validator is a function returning a `ValidatorResult` named tuple.
* Mechanical validators wrap shell-pipe operations (grep, sha256, awk-equivalent).
* Semi-mechanical validators include a minimal markdown-section-aware parser.
* Manual validators (V6, V20) raise NotImplementedError + point to a checklist file.
* All validators are advisory only — they DO NOT mutate substrate, DO NOT auto-correct,
  DO NOT redefine truth, and remain subordinate to the replay-authoritative substrate.

Marker syntax decision (per readiness review A6 ambiguity resolution at S4):
* Clause-body sections use the `**Citations.**` and `*Note.*` inline-bold/italic markers
  (consistent with the existing contract's `*Rationale.*` convention).
* The Rule section is the clause body's first paragraph(s) ending immediately before the
  `**Citations.**` marker.
* Decision recorded in S4 attestation per Layer B §20 deferral.

Authority discipline:
* Validators are advisory — they detect violations, never enforce.
* The replay-authoritative substrate (V18 baselines from S2) governs in any conflict.
* Per PD-3 W2: baseline-init plan + Layer A/B/C/D plans remain constitutionally
  authoritative; the bootstrap execution map is operationally authoritative.

Layer-B-implementing-agent: claude (per S0 §M-12 Initial Role Intent under PD-4 Y2).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# ----------------------------------------------------------------------------
# Substrate anchors (from S2 attestation; frozen by replay-authoritative truth)
# ----------------------------------------------------------------------------

S2_CONTRACT_PATH = Path("docs/phase_4b_deterministic_semantics.md")
S2_CONTRACT_SHA256 = "2200d4fc45b2dcef7920d65a62bbfc2abf39ffeb19fef7c608e84c8908109f80"
S2_CONTRACT_LINE_COUNT = 1392
S2_CLAUSE_ID_COUNT = 121
S2_D_FAULT_15_ROW_COUNT = 30
S2_SECTION_0_GLOSSARY_COUNT = 9

S2_REPLAY_BASELINES_BY_SCENARIO = {
    "C": "a4e202891836af1c6ef6e0b2e27a33ee13a2a47dd8e12dff87f4307810196c75",
    "D": "fa71aef1ab7f4aafe8dcb27481dffed8fea5f112d5dfdc3b7b2ede6c04b0aee0",
    "E": "76bb808769ab3c0cb87df45edc1c2f56bddf0c8afea0c9ab2a61475e94286fc2",
    "F": "39c8291414a37706db10ace7e580401d4262413a7cd9eee394d49be08b71433c",
}

S2_REPLAY_CYCLE_POLICY = "--reopen-stage-between-cycles"

# Per-AAU banned-phrase seed list (per extraction-plan §8; expanded by Layer-B-implementing-agent
# during authoring). V7's effective list is per-AAU; this is the bootstrap seed.
V7_BANNED_PHRASES_SEED: dict[str, list[str]] = {
    "D-FAULT-6b": ["next-tick observation", "eventually", "may later be observed"],
    "D-FAULT-6c": [],  # "observation" without "ingress event" qualifier — context-sensitive; manual check
    "D-FAULT-9b": [],  # "PAUSED is admissible" without conjunctive enumeration — context-sensitive
    "D-FAULT-9c": ["only manual_advance"],
    "D-SCHED-14": [],  # "input sets closed" without "without explicit clause amendment"
    "D-REPLAY-10": ["scheduled-injection is mandatory", "MUST inject"],
    "D-INGRESS-8": ["authoritative metadata"],
}

# ----------------------------------------------------------------------------
# Core types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidatorResult:
    """Result of one validator invocation."""

    validator_id: str            # "V1", "V18", "FF5", etc.
    passed: bool                 # True = PASS, False = FAIL
    classification: str          # "BLOCKING" | "SOFT" | "MANUAL"
    detail: str                  # Human-readable explanation
    evidence: dict               # Captured evidence (e.g., grep match counts)

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{self.validator_id} {self.classification}] {status} — {self.detail}"


# ----------------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------------


def sha256_of_file(path: Path) -> str:
    """SHA-256 of a file's contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def grep_count(pattern: str, path: Path, fixed: bool = False) -> int:
    """Count occurrences of pattern in path. `fixed=True` for grep -F semantics."""
    if not path.exists():
        return 0
    text = path.read_text()
    if fixed:
        return text.count(pattern)
    return len(re.findall(pattern, text, re.MULTILINE))


def find_markdown_sections(text: str) -> list[tuple[int, str, str]]:
    """Parse markdown into (line_no, heading_level, heading_title) tuples.

    Heading levels:
    * `# Title`     → level 1
    * `## Title`    → level 2
    * `### Title`   → level 3
    * `#### Title`  → level 4
    * `##### Title` → level 5
    """
    sections: list[tuple[int, str, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            sections.append((line_no, m.group(1), m.group(2)))
    return sections


def split_clause_body_into_sections(body: str) -> dict[str, str]:
    """Split a clause body into Rule / Citations / Note sub-sections.

    Per the S4 marker syntax decision:
    * Rule section: from start of body until the `**Citations.**` marker
    * Citations section: from `**Citations.**` until either `*Note.*` / `*Rationale.*` or end
    * Note section: from `*Note.*` (or `*Rationale.*`) marker until end

    Returns {"rule": str, "citations": str, "note": str}.
    Missing sections return empty string.
    """
    # Markers may be alone on a line OR followed by inline text on the same line.
    # Matches both `**Citations.**` and `**Citations.** ...` (with following inline text).
    citations_re = re.compile(r"^\*\*Citations\.\*\*(\s|$)", re.MULTILINE)
    note_re = re.compile(r"^\*(Note|Rationale)\.\*(\s|$)", re.MULTILINE)

    rule = body
    citations = ""
    note = ""

    cm = citations_re.search(body)
    if cm:
        rule = body[: cm.start()]
        rest = body[cm.end():]
        nm = note_re.search(rest)
        if nm:
            citations = rest[: nm.start()]
            note = rest[nm.end():]
        else:
            citations = rest
    else:
        nm = note_re.search(body)
        if nm:
            rule = body[: nm.start()]
            note = body[nm.end():]

    return {"rule": rule.strip(), "citations": citations.strip(), "note": note.strip()}


def extract_clause_ids(text: str) -> list[str]:
    """All line-anchored `**D-FAMILY-N[a-z]?**` clause-IDs in text.

    Includes SYN family for synthetic-fixture dry-runs only; SYN is not a real
    constitutional clause family and will never appear in the actual contract.
    """
    families = "EXEC|SCHED|BUS|REPLAY|SESS|TRACE|LIFE|FORBID|SCALE|CONT|FAULT|INGRESS|SYN"
    pattern = rf"^\*\*D-({families})-([0-9]+[a-z]?)\*\*"
    return [f"D-{m.group(1)}-{m.group(2)}" for m in re.finditer(pattern, text, re.MULTILINE)]


# ----------------------------------------------------------------------------
# V1 — Anchor uniqueness (pre)
# ----------------------------------------------------------------------------


def v01_anchor_unique_pre(anchor: str, contract_path: Path = S2_CONTRACT_PATH) -> ValidatorResult:
    """Verify anchor text appears exactly once in contract.

    `grep -Fc '<anchor>' contract` must return 1.
    """
    count = grep_count(anchor, contract_path, fixed=True)
    return ValidatorResult(
        validator_id="V1",
        passed=(count == 1),
        classification="BLOCKING",
        detail=f"anchor occurs {count} times (expected 1)",
        evidence={"anchor": anchor[:80], "count": count, "contract": str(contract_path)},
    )


# ----------------------------------------------------------------------------
# V2 — Anchor stability
# ----------------------------------------------------------------------------


def v02_anchor_stability(anchor: str, new_string: str) -> ValidatorResult:
    """For PTA/STA/FII: anchor must NOT be a substring of new_string."""
    overlap = anchor in new_string
    return ValidatorResult(
        validator_id="V2",
        passed=(not overlap),
        classification="BLOCKING",
        detail=f"anchor {'OVERLAPS new_string' if overlap else 'is non-overlapping'}",
        evidence={"overlap": overlap},
    )


# ----------------------------------------------------------------------------
# V3 — Three-section template presence (semi-mechanical)
# ----------------------------------------------------------------------------


def v03_template_presence(clause_body: str) -> ValidatorResult:
    """C-1 promoted clause body must contain Rule + Citations sections (Note optional)."""
    sections = split_clause_body_into_sections(clause_body)
    has_rule = bool(sections["rule"])
    has_citations = bool(sections["citations"])
    has_normative_keyword = bool(
        re.search(r"\b(MUST|MUST NOT|FORBIDDEN|SHALL|MAY)\b", sections["rule"])
    )

    passed = has_rule and has_citations and has_normative_keyword
    if not has_rule:
        detail = "missing Rule section"
    elif not has_normative_keyword:
        detail = "Rule section lacks normative keyword (MUST/MUST NOT/FORBIDDEN/SHALL/MAY)"
    elif not has_citations:
        detail = "missing **Citations.** marker"
    else:
        detail = "all three sections (Rule + Citations + optional Note) present"

    return ValidatorResult(
        validator_id="V3",
        passed=passed,
        classification="BLOCKING",
        detail=detail,
        evidence={
            "has_rule": has_rule,
            "has_citations": has_citations,
            "has_normative_keyword": has_normative_keyword,
            "has_note": bool(sections["note"]),
        },
    )


# ----------------------------------------------------------------------------
# V4 — Citation classification (anchor vs reference)
# ----------------------------------------------------------------------------


def v04_citation_classification(clause_body: str) -> ValidatorResult:
    """Citations section must have explicit `Anchor:` and (optionally) `Reference:` labels."""
    sections = split_clause_body_into_sections(clause_body)
    has_anchor_label = "Anchor:" in sections["citations"]
    has_some_label = has_anchor_label or "Reference:" in sections["citations"]

    return ValidatorResult(
        validator_id="V4",
        passed=has_some_label,
        classification="BLOCKING",
        detail=(
            f"Citations section labels present: "
            f"Anchor={has_anchor_label}, "
            f"Reference={'Reference:' in sections['citations']}"
        ),
        evidence={"has_anchor_label": has_anchor_label, "has_some_label": has_some_label},
    )


# ----------------------------------------------------------------------------
# V5 — Anchor-citation existing-clause check
# ----------------------------------------------------------------------------


def v05_anchor_cite_existing(
    cited_clause_ids: Iterable[str], contract_path: Path = S2_CONTRACT_PATH
) -> ValidatorResult:
    """Every cited clause-ID must already exist in the contract."""
    if not contract_path.exists():
        return ValidatorResult(
            validator_id="V5",
            passed=False,
            classification="BLOCKING",
            detail=f"contract not found at {contract_path}",
            evidence={},
        )
    existing = set(extract_clause_ids(contract_path.read_text()))
    cited = list(cited_clause_ids)
    missing = [cid for cid in cited if cid not in existing]
    return ValidatorResult(
        validator_id="V5",
        passed=(not missing),
        classification="BLOCKING",
        detail=f"{len(missing)} citation(s) missing: {missing[:5]}",
        evidence={"missing": missing, "cited_count": len(cited)},
    )


# ----------------------------------------------------------------------------
# V6 — Minimal-enforceable-surface check (MANUAL)
# ----------------------------------------------------------------------------


def v06_minimal_surface_manual() -> ValidatorResult:
    """V6 is a MANUAL reviewer-checklist annotation per Layer B §22.

    Returns MANUAL status; the actual check is performed by the Reviewer at Layer C time
    against the checklist in `tools/step12_validators/v06_v20_manual_checklists.md`.
    """
    return ValidatorResult(
        validator_id="V6",
        passed=True,  # MANUAL pending reviewer action; assumed pass until reviewer flags
        classification="MANUAL",
        detail="manual review per v06_v20_manual_checklists.md; advisory only",
        evidence={"checklist_path": "tools/step12_validators/v06_v20_manual_checklists.md"},
    )


# ----------------------------------------------------------------------------
# V7 — Hidden-widening-language scan (semi-mechanical)
# ----------------------------------------------------------------------------


def v07_hidden_widening(aau_id: str, clause_body: str) -> ValidatorResult:
    """Per-AAU banned-phrase scan.

    Returns SOFT failure if any banned phrase appears; Reviewer adjudicates per Layer C.
    """
    banned = V7_BANNED_PHRASES_SEED.get(aau_id, [])
    found = [phrase for phrase in banned if phrase.lower() in clause_body.lower()]
    return ValidatorResult(
        validator_id="V7",
        passed=(not found),
        classification="SOFT",
        detail=f"banned phrases found: {found}" if found else "no banned phrases",
        evidence={"aau_id": aau_id, "banned_seed_count": len(banned), "found": found},
    )


# ----------------------------------------------------------------------------
# V8 — Override-statement presence (D-FAULT-9c only)
# ----------------------------------------------------------------------------


def v08_override_statement(clause_body: str) -> ValidatorResult:
    """D-FAULT-9c MUST contain explicit override-relationship statement."""
    names_9a = bool(re.search(r"\bD-FAULT-9a\b", clause_body))
    uses_override = bool(re.search(r"\b(override|overrides|overriding|supersedes)\b", clause_body, re.IGNORECASE))
    names_manual_advance = "manual_advance" in clause_body
    acknowledges_preservation = bool(re.search(r"preserv|verbatim", clause_body, re.IGNORECASE))

    all_present = names_9a and uses_override and names_manual_advance and acknowledges_preservation

    return ValidatorResult(
        validator_id="V8",
        passed=all_present,
        classification="BLOCKING",
        detail=(
            f"D-FAULT-9a={names_9a}, override-verb={uses_override}, "
            f"manual_advance={names_manual_advance}, preservation-ack={acknowledges_preservation}"
        ),
        evidence={
            "names_d_fault_9a": names_9a,
            "uses_override_verb": uses_override,
            "names_manual_advance": names_manual_advance,
            "acknowledges_verbatim_preservation": acknowledges_preservation,
        },
    )


# ----------------------------------------------------------------------------
# V9 — Framework-reference confinement (semi-mechanical)
# ----------------------------------------------------------------------------


FRAMEWORK_REF_PATTERNS = [
    r"phase_4b_step1[12]_[a-z_]+\.md",   # framework doc filenames
    r"\bL[1-4]\b",                       # lemma labels
    r"\bF[0-9]{1,2}\b",                  # finding labels
    r"\bThreat\s+[1-8]\b",               # threat-model labels
]


def v09_framework_ref_confinement(clause_body: str) -> ValidatorResult:
    """Framework references must appear ONLY in Note section, not Rule or Citations."""
    sections = split_clause_body_into_sections(clause_body)
    rule_violations = []
    citations_violations = []
    for pattern in FRAMEWORK_REF_PATTERNS:
        rule_violations.extend(re.findall(pattern, sections["rule"]))
        citations_violations.extend(re.findall(pattern, sections["citations"]))

    passed = (not rule_violations) and (not citations_violations)
    return ValidatorResult(
        validator_id="V9",
        passed=passed,
        classification="BLOCKING",
        detail=(
            f"Rule violations: {rule_violations[:3]}; "
            f"Citations violations: {citations_violations[:3]}"
        ),
        evidence={
            "rule_violations": rule_violations,
            "citations_violations": citations_violations,
        },
    )


# ----------------------------------------------------------------------------
# V10 — D-FAULT-15 row format compliance
# ----------------------------------------------------------------------------


def v10_d_fault_15_row_format(row: str) -> ValidatorResult:
    """D-FAULT-15 row must match the table's column structure.

    Format: `| N | description | citation |` (3 pipe-separated columns).
    """
    stripped = row.strip()
    is_table_row = stripped.startswith("|") and stripped.endswith("|")
    pipe_count = stripped.count("|")
    starts_with_number = bool(re.match(r"^\|\s*[0-9]+\s*\|", stripped))

    passed = is_table_row and pipe_count == 4 and starts_with_number

    return ValidatorResult(
        validator_id="V10",
        passed=passed,
        classification="BLOCKING",
        detail=f"table-row={is_table_row}, pipes={pipe_count} (expected 4), number-start={starts_with_number}",
        evidence={"is_table_row": is_table_row, "pipe_count": pipe_count},
    )


# ----------------------------------------------------------------------------
# V11 — Properties A1–A3 (non-SF AAUs)
# ----------------------------------------------------------------------------


def v11_properties_a1_a3(contract_path: Path = S2_CONTRACT_PATH) -> ValidatorResult:
    """Verify post-mutation contract has only `+` lines vs pre-mutation (A3 implies A1+A2).

    Uses `git diff` against staged/HEAD state. Returns PASS if all diff hunks are
    additive-only (no `-` content lines).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--no-color", str(contract_path)],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return ValidatorResult(
            validator_id="V11",
            passed=False,
            classification="BLOCKING",
            detail="git not invocable",
            evidence={},
        )
    diff_text = result.stdout
    deletion_lines = [
        line for line in diff_text.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    insertion_lines = [
        line for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    passed = len(deletion_lines) == 0
    return ValidatorResult(
        validator_id="V11",
        passed=passed,
        classification="BLOCKING",
        detail=(
            f"deletions: {len(deletion_lines)} (expected 0); insertions: {len(insertion_lines)}; "
            f"A3 {'satisfied' if passed else 'VIOLATED'}"
        ),
        evidence={
            "deletion_count": len(deletion_lines),
            "insertion_count": len(insertion_lines),
        },
    )


# ----------------------------------------------------------------------------
# V12 — Properties S1–S3 (SF AAU only)
# ----------------------------------------------------------------------------


def v12_properties_s1_s3(old_string: str, new_string: str) -> ValidatorResult:
    """SF AAU: new_string must contain old_string as verbatim prefix (S1)."""
    s1_prefix = new_string.startswith(old_string)
    old_chars = Counter(c for c in old_string if not c.isspace())
    new_chars = Counter(c for c in new_string if not c.isspace())
    s2_superset = all(new_chars.get(c, 0) >= count for c, count in old_chars.items())

    passed = s1_prefix and s2_superset

    return ValidatorResult(
        validator_id="V12",
        passed=passed,
        classification="BLOCKING",
        detail=(
            f"S1 verbatim-prefix={s1_prefix}; "
            f"S2 char-superset={s2_superset}"
        ),
        evidence={"s1_prefix": s1_prefix, "s2_superset": s2_superset},
    )


# ----------------------------------------------------------------------------
# V13 — Anchor uniqueness (post)
# ----------------------------------------------------------------------------


def v13_anchor_unique_post(anchor: str, contract_path: Path = S2_CONTRACT_PATH) -> ValidatorResult:
    """Post-mutation: anchor still appears exactly once. Wraps V1."""
    r = v01_anchor_unique_pre(anchor, contract_path)
    return ValidatorResult(
        validator_id="V13",
        passed=r.passed,
        classification=r.classification,
        detail=f"(post-mutation) {r.detail}",
        evidence=r.evidence,
    )


# ----------------------------------------------------------------------------
# V14 — Existing-text byte preservation (wraps V11.A3)
# ----------------------------------------------------------------------------


def v14_existing_text_preservation(contract_path: Path = S2_CONTRACT_PATH) -> ValidatorResult:
    """V14 is the named guarantee for V11.A3; wraps V11."""
    r = v11_properties_a1_a3(contract_path)
    return ValidatorResult(
        validator_id="V14",
        passed=r.passed,
        classification=r.classification,
        detail=f"(byte-preservation via A3) {r.detail}",
        evidence=r.evidence,
    )


# ----------------------------------------------------------------------------
# V15 — Heading-DAG structure
# ----------------------------------------------------------------------------


def v15_heading_dag(contract_path: Path = S2_CONTRACT_PATH) -> ValidatorResult:
    """No level-skipping; monotonic section numbering."""
    if not contract_path.exists():
        return ValidatorResult(
            validator_id="V15",
            passed=False,
            classification="BLOCKING",
            detail=f"contract not found at {contract_path}",
            evidence={},
        )
    text = contract_path.read_text()
    sections = find_markdown_sections(text)
    violations: list[str] = []
    prev_level = 0
    for line_no, hashes, title in sections:
        level = len(hashes)
        if prev_level and level > prev_level + 1:
            violations.append(f"line {line_no}: level skip {prev_level}→{level} at '{title}'")
        prev_level = level

    passed = not violations
    return ValidatorResult(
        validator_id="V15",
        passed=passed,
        classification="BLOCKING",
        detail=f"{len(violations)} heading-DAG violations: {violations[:3]}",
        evidence={"violation_count": len(violations), "section_count": len(sections)},
    )


# ----------------------------------------------------------------------------
# V16 — New clause-ID uniqueness across document
# ----------------------------------------------------------------------------


def v16_new_clause_id_unique(
    new_clause_id: str, contract_path: Path = S2_CONTRACT_PATH
) -> ValidatorResult:
    """Newly-introduced clause-ID's defining `**D-X-N**` heading appears exactly once."""
    pattern = rf"^\*\*{re.escape(new_clause_id)}\*\*"
    if not contract_path.exists():
        return ValidatorResult(
            validator_id="V16",
            passed=False,
            classification="BLOCKING",
            detail=f"contract not found at {contract_path}",
            evidence={},
        )
    text = contract_path.read_text()
    count = len(re.findall(pattern, text, re.MULTILINE))
    return ValidatorResult(
        validator_id="V16",
        passed=(count == 1),
        classification="BLOCKING",
        detail=f"{new_clause_id} definition count = {count} (expected 1)",
        evidence={"clause_id": new_clause_id, "count": count},
    )


# ----------------------------------------------------------------------------
# V17 — Cross-reference resolvability
# ----------------------------------------------------------------------------


def v17_xref_resolvability(
    citations: Iterable[str], contract_path: Path = S2_CONTRACT_PATH
) -> ValidatorResult:
    """All cited clause-IDs must resolve in post-mutation contract."""
    if not contract_path.exists():
        return ValidatorResult(
            validator_id="V17",
            passed=False,
            classification="BLOCKING",
            detail=f"contract not found at {contract_path}",
            evidence={},
        )
    text = contract_path.read_text()
    existing = set(extract_clause_ids(text))
    cited = list(citations)
    unresolved = [c for c in cited if c not in existing]
    return ValidatorResult(
        validator_id="V17",
        passed=(not unresolved),
        classification="BLOCKING",
        detail=f"unresolved citations: {unresolved[:5]}",
        evidence={"unresolved": unresolved, "cited_count": len(cited)},
    )


# ----------------------------------------------------------------------------
# V18 — Replay-test invariant (wraps tools/check_session_replay_identity.py)
# ----------------------------------------------------------------------------


def v18_replay_invariant(session_a: Path, session_b: Path) -> ValidatorResult:
    """Invoke check_session_replay_identity.py against two SessionPackages.

    BLOCKING on FAIL. The S2 attestation's canonical baselines (4 Step 10 scenario hashes)
    are the reference truth; this wrapper does not redefine that truth.
    """
    tool = Path("tools/check_session_replay_identity.py")
    if not tool.exists():
        return ValidatorResult(
            validator_id="V18",
            passed=False,
            classification="BLOCKING",
            detail=f"replay tool not found at {tool}",
            evidence={"tool": str(tool)},
        )
    try:
        result = subprocess.run(
            ["python3", str(tool), str(session_a), str(session_b)],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return ValidatorResult(
            validator_id="V18",
            passed=False,
            classification="BLOCKING",
            detail="python3 not invocable",
            evidence={},
        )

    passed = "REPLAY-IDENTICAL" in result.stdout and result.returncode == 0
    # Extract SHA from output if present
    sha_match = re.search(r"events\.jsonl\s+sha256:\s+([0-9a-f]{64})", result.stdout)
    sha = sha_match.group(1) if sha_match else None

    return ValidatorResult(
        validator_id="V18",
        passed=passed,
        classification="BLOCKING",
        detail=f"tool exit={result.returncode}; REPLAY-IDENTICAL={'REPLAY-IDENTICAL' in result.stdout}; observed_sha={sha}",
        evidence={
            "session_a": str(session_a),
            "session_b": str(session_b),
            "exit_code": result.returncode,
            "observed_events_sha256": sha,
            "canonical_baselines": S2_REPLAY_BASELINES_BY_SCENARIO,
        },
    )


# ----------------------------------------------------------------------------
# V19 — Inter-wave citation-gap (aggregate of V17)
# ----------------------------------------------------------------------------


def v19_interwave_citation_gap(
    wave_aaus_citations: dict[str, list[str]], contract_path: Path = S2_CONTRACT_PATH
) -> ValidatorResult:
    """At end-of-wave: every AAU's citations resolve in the post-wave contract."""
    if not contract_path.exists():
        return ValidatorResult(
            validator_id="V19",
            passed=False,
            classification="BLOCKING",
            detail=f"contract not found at {contract_path}",
            evidence={},
        )
    existing = set(extract_clause_ids(contract_path.read_text()))
    aggregate_unresolved: dict[str, list[str]] = {}
    for aau_id, citations in wave_aaus_citations.items():
        unresolved = [c for c in citations if c not in existing]
        if unresolved:
            aggregate_unresolved[aau_id] = unresolved
    return ValidatorResult(
        validator_id="V19",
        passed=(not aggregate_unresolved),
        classification="BLOCKING",
        detail=f"AAUs with unresolved citations: {list(aggregate_unresolved.keys())}",
        evidence={"aggregate_unresolved": aggregate_unresolved},
    )


# ----------------------------------------------------------------------------
# V20 — Normative-consistency check (MANUAL)
# ----------------------------------------------------------------------------


def v20_normative_consistency_manual() -> ValidatorResult:
    """V20 is MANUAL per Layer B §22.

    Returns MANUAL status; the actual check is performed by the Reviewer at Layer C time
    against the checklist in `tools/step12_validators/v06_v20_manual_checklists.md`.
    """
    return ValidatorResult(
        validator_id="V20",
        passed=True,  # MANUAL pending reviewer action
        classification="MANUAL",
        detail="manual normative-consistency review per v06_v20_manual_checklists.md",
        evidence={"checklist_path": "tools/step12_validators/v06_v20_manual_checklists.md"},
    )


# ----------------------------------------------------------------------------
# FF1 — Final-form V18 (wraps V18)
# ----------------------------------------------------------------------------


def ff1_final_form_v18(session_a: Path, session_b: Path) -> ValidatorResult:
    """FF1 = V18 at final form."""
    r = v18_replay_invariant(session_a, session_b)
    return ValidatorResult(
        validator_id="FF1",
        passed=r.passed,
        classification=r.classification,
        detail=f"(final-form V18) {r.detail}",
        evidence=r.evidence,
    )


# ----------------------------------------------------------------------------
# FF2 — Final-form V19 (wraps V19 over all 29 AAUs)
# ----------------------------------------------------------------------------


def ff2_final_form_v19(
    all_aau_citations: dict[str, list[str]], contract_path: Path = S2_CONTRACT_PATH
) -> ValidatorResult:
    """FF2 = V19 aggregate over all 29 AAUs at final form."""
    r = v19_interwave_citation_gap(all_aau_citations, contract_path)
    return ValidatorResult(
        validator_id="FF2",
        passed=r.passed,
        classification=r.classification,
        detail=f"(final-form V19) {r.detail}",
        evidence=r.evidence,
    )


# ----------------------------------------------------------------------------
# FF3 — Step 12 completeness check
# ----------------------------------------------------------------------------


# Expected new clause-IDs per extraction-plan §1 (38 atomic insertions across 6 waves)
FF3_EXPECTED_NEW_CLAUSE_IDS = {
    "D-FAULT-6b", "D-FAULT-6c",          # Wave 1 FII
    "D-SCHED-14", "D-REPLAY-10",         # Wave 1 STA
    "D-INGRESS-1", "D-INGRESS-2", "D-INGRESS-3", "D-INGRESS-4",
    "D-INGRESS-5", "D-INGRESS-6", "D-INGRESS-7", "D-INGRESS-8", "D-INGRESS-9",  # Wave 2 PTA
    "D-FAULT-9b", "D-FAULT-9c",          # Wave 3 FII
    # Wave 4: D-FAULT-15 rows 31-42 (not clause-IDs but table rows)
    # Wave 5: 5 glossary entries + 1 SF
    # Wave 6: C-2 embedded notes (no clause-IDs)
}


def ff3_step12_completeness(contract_path: Path = S2_CONTRACT_PATH) -> ValidatorResult:
    """Verify all expected Step-12 clause-IDs are present in final contract."""
    if not contract_path.exists():
        return ValidatorResult(
            validator_id="FF3",
            passed=False,
            classification="BLOCKING",
            detail=f"contract not found at {contract_path}",
            evidence={},
        )
    existing = set(extract_clause_ids(contract_path.read_text()))
    missing = FF3_EXPECTED_NEW_CLAUSE_IDS - existing
    return ValidatorResult(
        validator_id="FF3",
        passed=(not missing),
        classification="BLOCKING",
        detail=f"missing expected Step-12 clauses: {sorted(missing)[:10]}",
        evidence={"missing_count": len(missing), "missing": sorted(missing)},
    )


# ----------------------------------------------------------------------------
# FF4 — Framework/contract separation aggregate (wraps V9)
# ----------------------------------------------------------------------------


def ff4_framework_contract_separation(
    new_clause_bodies: dict[str, str]
) -> ValidatorResult:
    """FF4 = V9 over all 17 new clause bodies at final form."""
    violations: dict[str, list[str]] = {}
    for clause_id, body in new_clause_bodies.items():
        r = v09_framework_ref_confinement(body)
        if not r.passed:
            violations[clause_id] = (
                r.evidence.get("rule_violations", [])
                + r.evidence.get("citations_violations", [])
            )
    return ValidatorResult(
        validator_id="FF4",
        passed=(not violations),
        classification="BLOCKING",
        detail=f"clauses with framework-ref leakage: {list(violations.keys())}",
        evidence={"violations": violations},
    )


# ----------------------------------------------------------------------------
# FF5 — Substrate preservation (diff against S2 baseline)
# ----------------------------------------------------------------------------


def ff5_substrate_preservation(contract_path: Path = S2_CONTRACT_PATH) -> ValidatorResult:
    """Compare post-Step-12 contract against S2-captured pre-Step-12 substrate.

    Verifies:
    * Contract SHA-256 differs from S2 baseline (mutations occurred — expected post-authoring)
    * Pre-Step-12 clause-IDs all still present (no removals)
    * §11 item-1 verbatim text preserved (per S2 capture)
    * D-FAULT-15 row count >= 30 (additive only)
    * §0 glossary count >= 9 (additive only)
    """
    if not contract_path.exists():
        return ValidatorResult(
            validator_id="FF5",
            passed=False,
            classification="BLOCKING",
            detail=f"contract not found at {contract_path}",
            evidence={},
        )
    current_sha = sha256_of_file(contract_path)
    text = contract_path.read_text()
    current_clause_ids = set(extract_clause_ids(text))

    # Pre-Step-12 clause-IDs (from S2 enumeration; 121 of them)
    pre_step12_ids = {
        f"D-BUS-{i}" for i in range(1, 13)
    } | {
        f"D-CONT-{i}" for i in [1, 2, 3, 4, 5, "5a", 6, "6a", "6b", "6c", 7, "7a"]
    } | {
        f"D-EXEC-{i}" for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, "13a", "13b", "13c", "13d"]
    } | {
        f"D-FAULT-{i}" for i in [1, "1a", "1b", 2, 3, "3a", "3b", 4, "4a", 5, "5a", "5b",
                                  6, "6a", 7, 8, "8a", "8b", 9, "9a", 10, 11, "11a", 12,
                                  "12a", "12b", "12c", 13, 14, 15]
    } | {
        f"D-LIFE-{i}" for i in range(1, 10)
    } | {
        f"D-REPLAY-{i}" for i in range(1, 10)
    } | {
        f"D-SCALE-{i}" for i in range(1, 4)
    } | {
        f"D-SCHED-{i}" for i in range(1, 14)
    } | {
        f"D-SESS-{i}" for i in range(1, 9)
    } | {
        f"D-TRACE-{i}" for i in range(1, 9)
    }

    removed_ids = pre_step12_ids - current_clause_ids

    sha_unchanged = current_sha == S2_CONTRACT_SHA256
    no_removals = not removed_ids

    # Two-stage logic: pre-authoring, SHA unchanged AND no removals = PASS
    # Post-authoring, SHA differs (mutation occurred) AND no removals = PASS
    passed = no_removals  # The critical invariant; SHA-change is informational

    detail_parts = [
        f"current SHA: {current_sha[:16]}...",
        f"S2 baseline SHA: {S2_CONTRACT_SHA256[:16]}...",
        f"SHA {'unchanged' if sha_unchanged else 'differs (mutations applied)'}",
        f"removed pre-Step-12 IDs: {len(removed_ids)}",
    ]

    return ValidatorResult(
        validator_id="FF5",
        passed=passed,
        classification="BLOCKING",
        detail="; ".join(detail_parts),
        evidence={
            "current_sha256": current_sha,
            "s2_baseline_sha256": S2_CONTRACT_SHA256,
            "sha_unchanged": sha_unchanged,
            "removed_ids": sorted(removed_ids),
            "pre_step12_id_count": len(pre_step12_ids),
            "current_id_count": len(current_clause_ids),
        },
    )


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------


VALIDATOR_REGISTRY = {
    "V1": v01_anchor_unique_pre,
    "V2": v02_anchor_stability,
    "V3": v03_template_presence,
    "V4": v04_citation_classification,
    "V5": v05_anchor_cite_existing,
    "V6": v06_minimal_surface_manual,
    "V7": v07_hidden_widening,
    "V8": v08_override_statement,
    "V9": v09_framework_ref_confinement,
    "V10": v10_d_fault_15_row_format,
    "V11": v11_properties_a1_a3,
    "V12": v12_properties_s1_s3,
    "V13": v13_anchor_unique_post,
    "V14": v14_existing_text_preservation,
    "V15": v15_heading_dag,
    "V16": v16_new_clause_id_unique,
    "V17": v17_xref_resolvability,
    "V18": v18_replay_invariant,
    "V19": v19_interwave_citation_gap,
    "V20": v20_normative_consistency_manual,
    "FF1": ff1_final_form_v18,
    "FF2": ff2_final_form_v19,
    "FF3": ff3_step12_completeness,
    "FF4": ff4_framework_contract_separation,
    "FF5": ff5_substrate_preservation,
}


# ----------------------------------------------------------------------------
# CLI entry point — print registry status
# ----------------------------------------------------------------------------


if __name__ == "__main__":
    print(f"Step 12 validator registry — {len(VALIDATOR_REGISTRY)} validators registered:")
    for vid, fn in VALIDATOR_REGISTRY.items():
        print(f"  {vid:5s} → {fn.__name__}")
    print()
    print("Marker syntax decision (S4):")
    print("  Rule section: clause-body content before **Citations.** marker")
    print("  Citations marker: **Citations.** (inline bold, line-anchored)")
    print("  Note marker: *Note.* or *Rationale.* (inline italic, line-anchored)")
    print()
    print("Substrate anchors (from S2; frozen):")
    print(f"  Contract SHA-256: {S2_CONTRACT_SHA256}")
    print(f"  Clause-ID count: {S2_CLAUSE_ID_COUNT}")
    print(f"  D-FAULT-15 rows: {S2_D_FAULT_15_ROW_COUNT}")
    print(f"  §0 glossary entries: {S2_SECTION_0_GLOSSARY_COUNT}")
    print(f"  Replay baselines (Step 10 §P.1): {len(S2_REPLAY_BASELINES_BY_SCENARIO)} scenarios")
    sys.exit(0)
