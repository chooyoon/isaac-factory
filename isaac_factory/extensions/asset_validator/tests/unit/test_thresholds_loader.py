"""Unit tests for `thresholds.loader.load_criteria`."""

from __future__ import annotations

from pathlib import Path

import pytest

from asset_validator import AcceptanceCriteria, load_criteria
from asset_validator.thresholds.loader import (
    CriteriaLoadError,
    SchemaVersionError,
    UnknownSectionError,
)


_EXT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_YAML = _EXT_ROOT / "configs" / "acceptance_default.yaml"


# ============================================================ default yaml ==


class TestShippedDefault:
    """The YAML mirror must load without errors and produce the same
    threshold values as the dataclass defaults."""

    def test_loads_cleanly(self):
        c = load_criteria(_DEFAULT_YAML)
        assert isinstance(c, AcceptanceCriteria)

    def test_overlap_matches_dataclass_default(self):
        c = load_criteria(_DEFAULT_YAML)
        d = AcceptanceCriteria()
        assert c.overlap == d.overlap

    def test_transform_matches_dataclass_default(self):
        c = load_criteria(_DEFAULT_YAML)
        d = AcceptanceCriteria()
        assert c.transform == d.transform

    def test_collider_matches_dataclass_default(self):
        c = load_criteria(_DEFAULT_YAML)
        d = AcceptanceCriteria()
        assert c.collider == d.collider

    def test_grounding_matches_dataclass_default(self):
        c = load_criteria(_DEFAULT_YAML)
        d = AcceptanceCriteria()
        assert c.grounding == d.grounding

    def test_deterministic_reset_matches_dataclass_default(self):
        c = load_criteria(_DEFAULT_YAML)
        d = AcceptanceCriteria()
        assert c.deterministic_reset == d.deterministic_reset


# ============================================================ override yaml ==


class TestOverrides:
    def test_partial_override_keeps_other_defaults(self, tmp_path):
        yaml_text = """\
schema_version: "1.0.0"
overlap:
  pen_depth_max_m: 0.0005   # tighter than default 0.001
"""
        p = tmp_path / "override.yaml"
        p.write_text(yaml_text)
        c = load_criteria(p)
        assert c.overlap.pen_depth_max_m  == pytest.approx(0.0005)
        # Other overlap fields fall back to dataclass defaults
        assert c.overlap.pen_depth_max_fit_m == pytest.approx(1.0e-4)
        # Other sections untouched
        d = AcceptanceCriteria()
        assert c.transform == d.transform

    def test_tuple_field_coerces_from_list(self, tmp_path):
        yaml_text = """\
schema_version: "1.0.0"
collider:
  dynamic_allowed_approximations: [box, sphere]
"""
        p = tmp_path / "tuple.yaml"
        p.write_text(yaml_text)
        c = load_criteria(p)
        assert isinstance(c.collider.dynamic_allowed_approximations, tuple)
        assert c.collider.dynamic_allowed_approximations == ("box", "sphere")


# ========================================================== error handling ==


class TestErrors:
    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_criteria(tmp_path / "nope.yaml")

    def test_non_mapping_top_level(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("just a string\n")
        with pytest.raises(CriteriaLoadError):
            load_criteria(p)

    def test_unknown_section_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text('schema_version: "1.0.0"\nbogus: {x: 1}\n')
        with pytest.raises(UnknownSectionError):
            load_criteria(p)

    def test_bad_schema_version_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text('schema_version: "9.0.0"\n')
        with pytest.raises(SchemaVersionError):
            load_criteria(p)

    def test_unknown_key_within_section_is_ignored(self, tmp_path, capsys):
        # Forward-compat: extra fields warned but not fatal
        p = tmp_path / "fwd.yaml"
        p.write_text('schema_version: "1.0.0"\noverlap: {nonsense_field: 7}\n')
        c = load_criteria(p)
        # Section produced; warning to stderr
        assert c.overlap == AcceptanceCriteria().overlap
        captured = capsys.readouterr()
        assert "nonsense_field" in captured.err
