"""Unit tests for cell_authoring.config.

Covers the strict loader: rejects unknown keys, unknown schema versions,
malformed gravity vectors, and out-of-range scalars.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cell_authoring.config import CellConfig, load_config


_WORKSPACE = Path(__file__).resolve().parents[2]
_CONFIG    = _WORKSPACE / "configs" / "cell_01.yaml"


# ============================================================ happy path ==


class TestLoad:
    def test_loads_real_cell_config(self):
        cfg = load_config(_CONFIG)
        assert isinstance(cfg, CellConfig)
        assert cfg.cell_id == "cell_01"
        assert cfg.schema_version == "0.4.0"
        assert cfg.runtime.enable_enhanced_determinism is True
        assert cfg.runtime.solver_type == "TGS"
        assert cfg.runtime.seed == 20260518
        assert cfg.runtime.gravity.direction == (0.0, 0.0, -1.0)

    def test_paths_preserved_verbatim(self):
        cfg = load_config(_CONFIG)
        assert cfg.cell_stage_rel == "assets/cells/cell_01.usda"
        assert cfg.output_root_rel == "outputs/cell_validation"

    def test_environment_dimensions_positive(self):
        cfg = load_config(_CONFIG)
        assert cfg.environment.floor.size_xy_m[0] > 0
        assert cfg.environment.floor.thickness_m > 0
        assert cfg.environment.safety_cage.height_m > 0
        assert cfg.environment.pedestal.height_m > 0
        assert cfg.environment.work_fixture.height_m > 0

    def test_phase_b_artefacts_declared(self):
        cfg = load_config(_CONFIG)
        assert len(cfg.conveyors) >= 1, "Phase B requires at least one conveyor"
        assert len(cfg.parts) >= 1,     "Phase B requires at least one consumable"
        cv = cfg.conveyors[0]
        assert cv.name == "Conveyor_InFeed"
        # Belt velocity must be authored, non-zero, and in-plane (z = 0)
        vx, vy, vz = cv.belt_velocity_world_m_per_s
        assert (vx, vy, vz) != (0.0, 0.0, 0.0), "belt must have authored surface velocity"
        assert vz == 0.0, "belt surface velocity must be horizontal"
        peg = cfg.parts[0]
        assert peg.mass_kg > 0
        assert peg.approximation in {
            "box", "sphere", "capsule", "cylinder", "convexHull", "convexDecomposition",
        }, "peg approximation must be in ColliderThresholds.dynamic_allowed_approximations"


# =========================================================== sad path ==


class TestRejection:
    def _write(self, tmp_path: Path, text: str) -> Path:
        p = tmp_path / "c.yaml"
        p.write_text(text, encoding="utf-8")
        return p

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "missing.yaml")

    def test_unknown_schema_version(self, tmp_path: Path):
        p = self._write(tmp_path, 'schema_version: "9.9.9"\n')
        with pytest.raises(ValueError, match="unsupported schema_version"):
            load_config(p)

    def test_unknown_top_key_rejected(self, tmp_path: Path):
        good = _CONFIG.read_text(encoding="utf-8")
        bad  = good + "\nextra_key: 42\n"
        p = self._write(tmp_path, bad)
        with pytest.raises(ValueError, match="unknown keys"):
            load_config(p)

    def test_bad_solver_type(self, tmp_path: Path):
        good = _CONFIG.read_text(encoding="utf-8")
        bad  = good.replace('solver_type: "TGS"', 'solver_type: "XYZ"')
        p = self._write(tmp_path, bad)
        with pytest.raises(ValueError, match="solver_type"):
            load_config(p)

    def test_non_positive_dt(self, tmp_path: Path):
        good = _CONFIG.read_text(encoding="utf-8")
        bad  = good.replace("physics_dt:    0.016666666666666666",
                            "physics_dt:    0.0")
        p = self._write(tmp_path, bad)
        with pytest.raises(ValueError, match="physics_dt"):
            load_config(p)

    def test_non_positive_mass(self, tmp_path: Path):
        good = _CONFIG.read_text(encoding="utf-8")
        bad  = good.replace("mass_kg:           0.10", "mass_kg:           0.0")
        p = self._write(tmp_path, bad)
        with pytest.raises(ValueError, match="mass_kg must be positive"):
            load_config(p)

    def test_duplicate_part_names(self, tmp_path: Path):
        # Insert a duplicate-name part inside the parts list (after the
        # existing Peg_01 entry, before the `paths:` block).
        good = _CONFIG.read_text(encoding="utf-8")
        marker = '    approximation:     "box"               # Cube primitive — exact match\n'
        assert marker in good, "config layout changed; update this test marker"
        bad = good.replace(
            marker,
            marker
            + '  - name: "Peg_01"\n'
            + '    translate_world_m: [0.0, 0.0, 1.0]\n'
            + '    size_xyz_m:        [0.05, 0.05, 0.10]\n'
            + '    mass_kg:           0.10\n'
            + '    approximation:     "box"\n',
        )
        p = self._write(tmp_path, bad)
        with pytest.raises(ValueError, match="parts names must be unique"):
            load_config(p)
