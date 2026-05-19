"""Unit tests for `reporters.json_reporter`."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from asset_validator import (
    AcceptanceCriteria,
    Issue,
    REPORT_SCHEMA_VERSION,
    Severity,
    build_report,
    write_report,
)


# Fixed "started_at" so reports are byte-identical across runs.
_FIXED_TIME = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


def _issue(code, severity, *, prims=("/A",), validator="overlap"):
    return Issue.create(
        code=code, severity=severity,
        message=f"sample message for {code}",
        prim_paths=prims, validator=validator,
    )


# ============================================================ build_report ==


class TestStructure:
    def test_required_top_level_keys(self):
        r = build_report(
            [], asset_uri="test://x", validators_run=["overlap"],
            duration_seconds=0.0, started_at=_FIXED_TIME,
        )
        for k in ("schema_version", "asset_uri", "started_at", "duration_seconds",
                  "criteria_digest", "criteria_path", "validators_run",
                  "validators_skipped", "seed", "status", "counts", "issues"):
            assert k in r

    def test_schema_version_is_1_1_0(self):
        r = build_report([], asset_uri="t", validators_run=[], duration_seconds=0)
        assert r["schema_version"] == REPORT_SCHEMA_VERSION == "1.1.0"

    def test_counts_zero_filled(self):
        r = build_report([], asset_uri="t", validators_run=[], duration_seconds=0)
        assert r["counts"] == {"INFO": 0, "WARN": 0, "FAIL": 0}

    def test_empty_issues_status_info(self):
        r = build_report([], asset_uri="t", validators_run=[], duration_seconds=0)
        assert r["status"] == "INFO"


# ============================================================ status logic ==


class TestStatus:
    def test_any_fail_sets_status_fail(self):
        issues = [_issue("OVERLAP.X", Severity.FAIL),
                  _issue("OVERLAP.Y", Severity.WARN)]
        r = build_report(issues, asset_uri="t", validators_run=[], duration_seconds=0)
        assert r["status"] == "FAIL"

    def test_only_warns_sets_status_warn(self):
        issues = [_issue("OVERLAP.Y", Severity.WARN)]
        r = build_report(issues, asset_uri="t", validators_run=[], duration_seconds=0)
        assert r["status"] == "WARN"

    def test_only_info_sets_status_info(self):
        issues = [_issue("OVERLAP.Z", Severity.INFO)]
        r = build_report(issues, asset_uri="t", validators_run=[], duration_seconds=0)
        assert r["status"] == "INFO"


# ============================================================ ordering ==


class TestOrdering:
    def test_issues_sorted_severity_desc_then_code(self):
        a = _issue("OVERLAP.A", Severity.WARN)
        b = _issue("OVERLAP.B", Severity.FAIL)
        c = _issue("OVERLAP.C", Severity.FAIL)
        r = build_report([a, b, c], asset_uri="t", validators_run=[], duration_seconds=0)
        codes = [i["code"] for i in r["issues"]]
        # FAILs first (sorted by code), then WARNs
        assert codes == ["OVERLAP.B", "OVERLAP.C", "OVERLAP.A"]


# ============================================================ determinism ==


class TestDeterminism:
    def test_same_input_same_output(self):
        issues = [_issue("OVERLAP.A", Severity.FAIL)]
        r1 = build_report(issues, asset_uri="t", validators_run=["overlap"],
                          duration_seconds=1.0, started_at=_FIXED_TIME)
        r2 = build_report(issues, asset_uri="t", validators_run=["overlap"],
                          duration_seconds=1.0, started_at=_FIXED_TIME)
        # Byte-identical JSON when serialized with sort_keys.
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


# ============================================================ digest ==


class TestCriteriaDigest:
    def test_digest_is_stable_for_same_criteria(self):
        c = AcceptanceCriteria()
        r1 = build_report([], asset_uri="t", validators_run=[], duration_seconds=0, criteria=c)
        r2 = build_report([], asset_uri="t", validators_run=[], duration_seconds=0, criteria=c)
        assert r1["criteria_digest"] == r2["criteria_digest"]
        assert r1["criteria_digest"].startswith("sha256:")

    def test_digest_differs_for_different_criteria(self):
        from asset_validator import GroundingThresholds
        c1 = AcceptanceCriteria()
        c2 = AcceptanceCriteria(grounding=GroundingThresholds(floating_tolerance_m=0.01))
        r1 = build_report([], asset_uri="t", validators_run=[], duration_seconds=0, criteria=c1)
        r2 = build_report([], asset_uri="t", validators_run=[], duration_seconds=0, criteria=c2)
        assert r1["criteria_digest"] != r2["criteria_digest"]


# ============================================================ write_report ==


class TestWriteReport:
    def test_writes_valid_json(self, tmp_path):
        issues = [_issue("OVERLAP.X", Severity.FAIL)]
        out = tmp_path / "sub" / "report.json"
        report = write_report(
            issues, out, asset_uri="t", validators_run=["overlap"],
            duration_seconds=0.5, started_at=_FIXED_TIME,
        )
        assert out.is_file()
        loaded = json.loads(out.read_text())
        # Same content (sort_keys puts both in canonical form)
        assert json.dumps(loaded, sort_keys=True) == json.dumps(report, sort_keys=True)

    def test_creates_missing_parent_dirs(self, tmp_path):
        out = tmp_path / "nested" / "deep" / "report.json"
        write_report([], out, asset_uri="t", validators_run=[], duration_seconds=0)
        assert out.is_file()
