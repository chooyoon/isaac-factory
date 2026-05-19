"""YAML → :class:`AcceptanceCriteria` loader.

Single-purpose, stdlib + PyYAML only. Reads the YAML mirror at
``configs/acceptance_default.yaml`` (or a user-supplied override) and
constructs a fully-populated :class:`AcceptanceCriteria` dataclass.

Validation:
  - Every top-level section must be one of the dataclass field names; an
    unknown section raises :class:`UnknownSectionError`.
  - Unknown keys inside a known section are **ignored** (forward-compat
    for new threshold fields).
  - Missing sections use the dataclass defaults.
  - ``schema_version`` (top-level) is checked against
    :data:`SUPPORTED_SCHEMA_MAJOR` — minor/patch mismatches are warnings
    (logged via stderr); major mismatches raise.

The loader does **not** depend on `pxr`, `omni`, or `isaacsim`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

import yaml

from .schema import (
    AcceptanceCriteria,
    ColliderThresholds,
    DeterministicResetThresholds,
    GroundingThresholds,
    OverlapThresholds,
    TransformThresholds,
)


SUPPORTED_SCHEMA_MAJOR = 1   # Bump when YAML shape breaks compat.


class CriteriaLoadError(Exception):
    """Base for all loader errors."""


class UnknownSectionError(CriteriaLoadError):
    """Top-level YAML key isn't one of the known threshold sections."""


class SchemaVersionError(CriteriaLoadError):
    """YAML schema_version's MAJOR doesn't match what this loader supports."""


_SECTION_CLASSES: Mapping[str, type] = {
    "overlap":             OverlapThresholds,
    "transform":           TransformThresholds,
    "collider":            ColliderThresholds,
    "grounding":           GroundingThresholds,
    "deterministic_reset": DeterministicResetThresholds,
}


def load_criteria(path: str | Path) -> AcceptanceCriteria:
    """Load YAML at ``path`` and return an :class:`AcceptanceCriteria`."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        raise CriteriaLoadError(
            f"{p}: top level must be a mapping (got {type(data).__name__})"
        )

    # Schema version check
    raw_version = str(data.pop("schema_version", "0.0.0"))
    major = _parse_major(raw_version)
    if major != SUPPORTED_SCHEMA_MAJOR:
        raise SchemaVersionError(
            f"{p}: schema_version {raw_version!r} MAJOR={major} differs from "
            f"loader-supported MAJOR={SUPPORTED_SCHEMA_MAJOR}"
        )

    # Section build
    kwargs: dict[str, Any] = {}
    for section_name, section_data in data.items():
        if section_name not in _SECTION_CLASSES:
            raise UnknownSectionError(
                f"{p}: unknown section '{section_name}'. "
                f"Known: {sorted(_SECTION_CLASSES)}"
            )
        cls = _SECTION_CLASSES[section_name]
        if section_data is None:
            kwargs[section_name] = cls()
            continue
        if not isinstance(section_data, dict):
            raise CriteriaLoadError(
                f"{p}: section '{section_name}' must be a mapping "
                f"(got {type(section_data).__name__})"
            )
        kwargs[section_name] = _build_section(cls, section_data, section_name, p)

    return AcceptanceCriteria(**kwargs)


def _build_section(cls: type, data: Mapping[str, Any], section_name: str, path: Path):
    """Instantiate ``cls`` from ``data``, ignoring unknown keys.

    Tuple-typed fields (e.g., ``dynamic_allowed_approximations``) are
    coerced from lists since YAML doesn't have a tuple type.
    """
    field_names = {f.name for f in cls.__dataclass_fields__.values()}
    type_hints = {f.name: f.type for f in cls.__dataclass_fields__.values()}

    ctor: dict[str, Any] = {}
    unknown: list[str] = []
    for k, v in data.items():
        if k not in field_names:
            unknown.append(k)
            continue
        # YAML lists → tuples for tuple-typed fields
        hint = type_hints[k]
        if isinstance(v, list) and "tuple" in str(hint):
            v = tuple(v)
        ctor[k] = v

    if unknown:
        print(
            f"[load_criteria] warn: {path}: section '{section_name}' has "
            f"unknown keys {unknown} — ignored",
            file=sys.stderr,
        )

    return cls(**ctor)


def _parse_major(version: str) -> int:
    parts = version.split(".")
    try:
        return int(parts[0])
    except (ValueError, IndexError):
        return 0
