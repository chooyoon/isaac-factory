"""JSON reporter.

Produces a machine-readable report matching
[docs/asset_validator_report_format.md §2](../../../../../docs/asset_validator_report_format.md).
The schema_version is **1.1.0** (covers all five implemented validators
and the deferred Phase 2 namespaces).

No `pxr`, `omni`, or `isaacsim` imports — pure stdlib.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from ..core.issue   import Issue
from ..core.severity import Severity


REPORT_SCHEMA_VERSION = "1.1.0"


def build_report(
    issues: Iterable[Issue],
    *,
    asset_uri:        str,
    validators_run:   list[str],
    duration_seconds: float,
    seed:             int                  = 0,
    criteria:         object | None        = None,
    criteria_path:    str | Path | None    = None,
    validators_skipped: list[str] | None   = None,
    started_at:       datetime | None      = None,
) -> dict:
    """Return a dict matching the report-format §2 schema.

    ``criteria`` (an :class:`AcceptanceCriteria` instance, optional) is
    used to compute a stable digest for CI hashing; if absent, the
    digest is the empty-string SHA-256.
    """
    issues = sorted(issues, key=Issue.sort_key)
    when   = started_at or datetime.now(timezone.utc)

    counts = {"INFO": 0, "WARN": 0, "FAIL": 0}
    for i in issues:
        counts[i.severity.name] += 1

    if counts["FAIL"]:
        status = "FAIL"
    elif counts["WARN"]:
        status = "WARN"
    else:
        status = "INFO"   # no INFOs either ⇒ vacuously INFO

    digest = "sha256:" + _criteria_digest(criteria)

    return {
        "schema_version":     REPORT_SCHEMA_VERSION,
        "asset_uri":          asset_uri,
        "started_at":         when.isoformat(),
        "duration_seconds":   round(float(duration_seconds), 6),
        "criteria_digest":    digest,
        "criteria_path":      str(criteria_path) if criteria_path else None,
        "validators_run":     list(validators_run),
        "validators_skipped": list(validators_skipped or []),
        "seed":               int(seed),
        "status":             status,
        "counts":             counts,
        "issues":             [i.to_dict() for i in issues],
    }


def write_report(
    issues: Iterable[Issue],
    out_path: str | Path,
    **kwargs,
) -> dict:
    """Build a report and write it to ``out_path`` (JSON, indent=2).

    Returns the dict that was written, so callers can inspect / re-emit
    without re-reading the file.
    """
    report = build_report(issues, **kwargs)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return report


# ============================================================ helpers ==


def _criteria_digest(criteria: object | None) -> str:
    """Stable SHA-256 of a canonicalized JSON of the criteria dataclass."""
    if criteria is None:
        return hashlib.sha256(b"").hexdigest()
    payload = json.dumps(_to_jsonable(criteria), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _to_jsonable(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Mapping):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, Severity):
        return obj.name
    return obj
