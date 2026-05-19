"""Phase A integration test: build cell_01.usda + run Phase 1A validators.

Phase 1A exit gate (sprint §5):

    TransformValidator + GroundingValidator (static) → 0 FAIL, 0 WARN
    on assets/cells/cell_01.usda.

Determinism gate (sprint §6 acceptance 8): two consecutive builds of the
same config produce byte-identical ``.usda`` content modulo the USD
authoring banner.

This file stays Phase 1A-scoped — Phase 1B/1C tests are in
``test_phase_b_build.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pxr = pytest.importorskip("pxr")
from pxr import Usd                                                  # noqa: E402

from asset_validator import (                                         # noqa: E402
    AcceptanceCriteria,
    GroundingValidator,
    TransformValidator,
    ValidationContext,
)
from asset_validator.adapters.usd_grounding_inspector import (       # noqa: E402
    UsdGroundingInspector,
)
from asset_validator.adapters.usd_stage_inspector import (           # noqa: E402
    UsdStageInspector,
)
from cell_authoring import build_cell, load_config                   # noqa: E402


_WORKSPACE = Path(__file__).resolve().parents[2]
_CONFIG    = _WORKSPACE / "configs" / "cell_01.yaml"


@pytest.fixture
def built_stage(tmp_path: Path) -> Path:
    """Build cell_01.usda into a tmp workspace mirror and return its path."""
    cfg = load_config(_CONFIG)
    out = build_cell(cfg, workspace_root=tmp_path)
    assert out.is_file(), f"build did not produce a file: {out}"
    return out


# ============================================================== shape ==


class TestStageShape:
    """Top-level cell-stage invariants."""

    def test_world_is_default_prim(self, built_stage: Path):
        stage = Usd.Stage.Open(str(built_stage))
        assert stage is not None
        assert stage.GetDefaultPrim().GetPath().pathString == "/World"

    def test_physics_scene_exists_with_determinism(self, built_stage: Path):
        stage = Usd.Stage.Open(str(built_stage))
        prim = stage.GetPrimAtPath("/World/PhysicsScene")
        assert prim and prim.IsValid()
        attr = prim.GetAttribute("physxScene:enableEnhancedDeterminism")
        assert attr and attr.IsValid()
        assert attr.Get() is True

    def test_solver_type_authoritative(self, built_stage: Path):
        stage = Usd.Stage.Open(str(built_stage))
        attr = stage.GetPrimAtPath("/World/PhysicsScene") \
                    .GetAttribute("physxScene:solverType")
        assert attr.Get() == "TGS"

    def test_floor_top_sits_at_world_z_zero(self, built_stage: Path):
        stage = Usd.Stage.Open(str(built_stage))
        floor = stage.GetPrimAtPath("/World/Environment/Floor")
        t = floor.GetAttribute("xformOp:translate").Get()
        visual = stage.GetPrimAtPath("/World/Environment/Floor/visual")
        scale = visual.GetAttribute("xformOp:scale").Get()
        thickness = float(scale[2])
        assert float(t[2]) == pytest.approx(-thickness / 2.0, abs=1e-9)


# ============================================================ validators ==


class TestValidatorsClean:
    """Sprint §5 Phase 1A exit gate."""

    def test_transform_validator_zero_issues(self, built_stage: Path):
        stage = Usd.Stage.Open(str(built_stage))
        ctx = ValidationContext(
            asset_uri=str(built_stage),
            criteria=AcceptanceCriteria(),
            stage_inspector=UsdStageInspector(stage=stage),
        )
        issues = TransformValidator(ctx.criteria).run(ctx)
        assert issues == [], (
            f"expected 0 transform issues; got "
            f"{[(i.severity.name, i.code, i.prim_paths) for i in issues]}"
        )

    def test_grounding_validator_zero_issues(self, built_stage: Path):
        stage = Usd.Stage.Open(str(built_stage))
        ctx = ValidationContext(
            asset_uri=str(built_stage),
            criteria=AcceptanceCriteria(),
            grounding_inspector=UsdGroundingInspector(stage=stage),
        )
        issues = GroundingValidator(ctx.criteria).run(ctx)
        assert issues == [], (
            f"expected 0 grounding issues; got "
            f"{[(i.severity.name, i.code, i.prim_paths) for i in issues]}"
        )


# ============================================================ determinism ==


class TestDeterministicBuild:
    """Sprint §6 acceptance 8: same config → byte-identical .usda."""

    def test_two_consecutive_builds_byte_identical(self, tmp_path: Path):
        cfg = load_config(_CONFIG)

        ws_a = tmp_path / "build_a"
        ws_b = tmp_path / "build_b"
        out_a = build_cell(cfg, workspace_root=ws_a)
        out_b = build_cell(cfg, workspace_root=ws_b)

        bytes_a = out_a.read_bytes()
        bytes_b = out_b.read_bytes()

        assert bytes_a == bytes_b, (
            "Builds diverged. First 200 bytes of A:\n"
            f"{bytes_a[:200]!r}\nFirst 200 bytes of B:\n{bytes_b[:200]!r}"
        )
