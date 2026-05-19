"""Phase 3N — temporal grasp-integrity gates.

See the cycle helper in ``_helper_cycle_audit.py`` for the per-tick
instrumentation. This file declares the test cases that turn that
instrumentation into pass/fail gates.

The endpoint-only tests (peg final XY near place, peg lifted, peg not on
floor, three-cycle determinism) stay in
``test_cell_01_pick_place_cycle.py``. This file adds the *temporal*
layer: pad contact must persist, no surface contact before release,
visual-believability ceilings on wrist_3 / peg z, and release-timing
correctness.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


try:
    import isaacsim                                       # noqa: F401
    _ISAAC_AVAILABLE = True
except ImportError:
    _ISAAC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _ISAAC_AVAILABLE,
    reason="Kit Python (Runtime B) required",
)


from ._helper_cycle_audit import (
    CELL_STAGE_PATH,
    PHYSICS_DT_S,
    MIN_PAD_PEG_PENETRATION_MM,
    PEG_MAX_Z_GATE_M,
    RELEASE_FIXTURE_TOLERANCE_STEPS,
    WRIST_3_MAX_Z_GATE_M,
    load_cfg,
    run_full_cycle_audited,
    _WORKSPACE,
)


@pytest.fixture(scope="module")
def sim_app():
    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    yield app
    app.close()


@pytest.fixture
def cell_stage(sim_app):
    import omni.usd
    ctx = omni.usd.get_context()
    assert CELL_STAGE_PATH.is_file(), f"missing stage: {CELL_STAGE_PATH}"
    r = ctx.open_stage(str(CELL_STAGE_PATH))
    ok = bool(r[0]) if isinstance(r, tuple) else bool(r)
    assert ok
    yield ctx.get_stage()


@pytest.fixture
def world(cell_stage):
    from isaacsim.core.api import World
    w = World(physics_dt=PHYSICS_DT_S, rendering_dt=PHYSICS_DT_S)
    w.reset()
    w.play()
    yield w
    w.clear_instance()


class TestTemporalGraspIntegrity:
    """The peg must be retained throughout transport — proven per-tick."""

    @pytest.fixture
    def audit(self, world, cell_stage):
        cfg = load_cfg()
        summary, trace = run_full_cycle_audited(world, cell_stage, cfg)
        out = _WORKSPACE / "logs" / "phase_3n_grasp_integrity_test.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w") as fh:
            fh.write(json.dumps(summary) + "\n")
            for r in trace:
                fh.write(json.dumps(r) + "\n")
        print(f"\n[3n-test] summary: {json.dumps(summary, indent=2)}")
        return summary

    def test_grasp_acquired_before_lift(self, audit):
        assert audit["grasp_acquired_step"] is not None, (
            "no sustained pad contact ever achieved"
        )
        assert audit["grasp_acquired_step"] <= audit["lift_end_step"], (
            f"sustained pad contact acquired at step {audit['grasp_acquired_step']}, "
            f"after lift ended at {audit['lift_end_step']}"
        )

    def test_no_sustained_pad_break_before_release(self, audit):
        assert audit["grasp_lost_in_transport_step"] is None, (
            f"pads released the peg at step {audit['grasp_lost_in_transport_step']}, "
            f"before the intended release at step {audit['release_start_step']}"
        )

    def test_no_pre_release_floor_or_belt_contact(self, audit):
        assert audit["floor_or_belt_first_post_close_step"] is None, (
            f"peg touched floor/belt at step "
            f"{audit['floor_or_belt_first_post_close_step']} during the "
            f"grasp/transport/place window (release starts at step "
            f"{audit['release_start_step']}) — that means the peg fell or "
            f"was dragged across the belt"
        )

    def test_wrist_3_stays_below_ceiling(self, audit):
        assert audit["wrist_3_max_z_m"] <= WRIST_3_MAX_Z_GATE_M, (
            f"wrist_3 reached world z = {audit['wrist_3_max_z_m']:.3f} m at "
            f"step {audit['wrist_3_max_z_step']}, exceeding the "
            f"{WRIST_3_MAX_Z_GATE_M:.2f} m gate. Joint-space LERP is taking "
            f"the arm through a fully-extended-overhead pose."
        )

    def test_peg_stays_below_ceiling(self, audit):
        assert audit["peg_max_z_m"] <= PEG_MAX_Z_GATE_M, (
            f"peg reached world z = {audit['peg_max_z_m']:.3f} m at step "
            f"{audit['peg_max_z_step']}, exceeding the {PEG_MAX_Z_GATE_M:.2f} m "
            f"gate. Either the peg was launched ballistically OR the arm "
            f"hoisted it above the work envelope."
        )

    def test_fixture_contact_only_after_release_starts(self, audit):
        fc = audit["fixture_first_post_close_step"]
        if fc is None:
            pytest.skip("no fixture contact recorded — test windowed too short")
        rs = audit["release_start_step"]
        delta = fc - rs
        assert delta >= -RELEASE_FIXTURE_TOLERANCE_STEPS, (
            f"peg touched the work fixture at step {fc}, "
            f"{abs(delta)} steps BEFORE the release phase began at step {rs} "
            f"— that's an unintended drop, not a placement"
        )

    def test_pad_clamp_active_throughout_transport(self, audit):
        assert audit["pad_pen_min_during_transport_mm"] >= MIN_PAD_PEG_PENETRATION_MM, (
            f"min pad-peg penetration during the lift→place window = "
            f"{audit['pad_pen_min_during_transport_mm']:.3f} mm, below "
            f"{MIN_PAD_PEG_PENETRATION_MM:.2f} mm — at some point the pads "
            f"barely touched the peg, suggesting marginal friction grasp"
        )
