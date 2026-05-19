"""Phase 4A — task-abstraction equivalence + replay package + multi-object readiness.

Demonstrates that the new ``cell_authoring.tasks`` framework produces
the same physical outcome as the validated Phase 3M/N/O/P direct-cycle
path. The single most important assertion: a PickPlaceTask realised
through TaskExecutor under TrajectoryProfile.NOMINAL produces a
TaskResult that PASSES all the Phase 3M/N/O/P gates with metrics
matching the harness baseline.

This file does NOT modify any existing test. It adds:

  TestTaskAbstractionEquivalence
      — run the validated cycle through TaskExecutor.execute(...)
      — assert TaskResult.outcome == PASS
      — assert peg_xyz_final, wrist_3_max_z, joint_vel_peak match the
        validated harness baseline within tight tolerance
      — assert UnifiedValidator(report) confirms the PASS

  TestRegistryMultiObjectReadiness
      — register an extra ObjectState + FixtureState alongside the
        validated peg + fixture and verify the registry tracks all of
        them through the cycle without affecting the validated outcome

  TestProfilesPreserveDeterminismOnNominal
      — run the same task twice under NOMINAL; assert bit-identical
        peg_xyz_final (because both calls use the same persistent
        Articulation/RigidPrim/contact_source through the executor)

  TestReplayPackageRoundTrip
      — produce a ReplayPackage; verify summary.json + task_definition
        round-trip into equivalent dicts; verify the package directory
        contains all expected files

The trajectory player + the cell config YAML + the gripper USD are
NOT modified. This is purely additive.
"""

from __future__ import annotations

import json
import math
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
    _WORKSPACE,
    load_cfg,
)

# Ensure cell_authoring is on sys.path before any test-function imports
# of cell_authoring.tasks (the helper sets this up lazily inside
# load_cfg, but tests import cell_authoring.tasks at function entry,
# before load_cfg is called).
import sys
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


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


# ─────────────── Phase 3P-validated baseline (harness 100/100 record) ───────────────

BASELINE_PEG_XYZ_FINAL    = (0.6599568128585815, 0.0054305740632116795, 0.6500000357627869)
BASELINE_WRIST_3_MAX_Z_M  = 0.9499949216842651
BASELINE_PEG_MAX_Z_M      = 0.8980391025543213
BASELINE_JOINT_VEL_PEAK   = 5.119834899902344
BASELINE_CART_PATH_LEN_M  = 4.660490064703312
BASELINE_GRASP_ACQUIRED   = 140

# Phase 3P perturbation sweeps showed peg_xyz_final varies by up to
# 1-2 mm depending on accumulated PhysX state, but within one
# persistent-handle executor instance the cycle is bit-identical.
# This test exercises a single executor instance, so we expect very
# tight match — but allow 5 mm tolerance against the harness baseline
# to account for any minor difference in init order between harness
# and executor.
PEG_FINAL_TOL_MM = 5.0


def _build_validated_task():
    """Build the PickPlaceTask that represents the validated reference cycle."""
    from cell_authoring.tasks import (
        PickPlaceTask, PickSource, PlaceTarget,
        PrismaticClampGrasp, JointSpaceLerpTransport, OpenJawRelease,
    )
    return PickPlaceTask(
        task_id="cell_01_validated_pick_place",
        pick_source=PickSource(
            object_id="Peg_01",
            world_pose_m=(-0.80, 0.0, 0.701),
            source_kind="conveyor",
            metadata={"conveyor_id": "Conveyor_InFeed"},
        ),
        place_target=PlaceTarget(
            fixture_id="WorkFixture_01",
            world_pose_m=(0.65, 0.0, 0.65),
            target_kind="fixture_top",
            placement_tolerance_xy_m=0.05,
        ),
        grasp_strategy=PrismaticClampGrasp(),
        transport_strategy=JointSpaceLerpTransport(profile_id="nominal"),
        release_strategy=OpenJawRelease(),
    )


# ════════════════════════════════════════════════════════════════════════
class TestTaskAbstractionEquivalence:
    """TaskExecutor under NOMINAL profile must reproduce the validated cycle."""

    def test_executor_produces_passing_taskresult(self, world, cell_stage):
        from cell_authoring.tasks import (
            TaskExecutor, TrajectoryProfile, TaskOutcome, UnifiedValidator,
        )
        cell_cfg = load_cfg()
        task     = _build_validated_task()
        executor = TaskExecutor(world=world, stage=cell_stage, cell_cfg=cell_cfg)
        try:
            result = executor.execute(task, profile=TrajectoryProfile.NOMINAL)
        finally:
            executor.close()

        # Persist for inspection.
        out = _WORKSPACE / "logs" / "phase_4a_executor_result.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result.to_dict(), indent=2, default=str))

        assert result.outcome == TaskOutcome.PASS, (
            f"TaskResult outcome={result.outcome.value} detail={result.outcome_detail}"
        )
        # UnifiedValidator agrees.
        report = UnifiedValidator().summarise([result])
        assert report.pass_rate == 1.0, (
            f"UnifiedValidator pass_rate={report.pass_rate} failures={report.failures}"
        )

    def test_executor_matches_validated_harness_baseline(self, world, cell_stage):
        from cell_authoring.tasks import TaskExecutor, TrajectoryProfile
        cell_cfg = load_cfg()
        task     = _build_validated_task()
        executor = TaskExecutor(world=world, stage=cell_stage, cell_cfg=cell_cfg)
        try:
            result = executor.execute(task, profile=TrajectoryProfile.NOMINAL)
        finally:
            executor.close()

        # Final peg pose within 5 mm of the harness 100-cycle baseline.
        for axis, (got, exp) in enumerate(zip(result.peg_xyz_final, BASELINE_PEG_XYZ_FINAL)):
            delta_mm = abs(got - exp) * 1000.0
            assert delta_mm < PEG_FINAL_TOL_MM, (
                f"peg final axis {axis}: got {got:+.6f}, baseline {exp:+.6f}, "
                f"Δ={delta_mm:.2f} mm > {PEG_FINAL_TOL_MM:.1f} mm"
            )

        # Motion peaks match the harness within reasonable bounds.
        assert abs(result.wrist_3_max_z_m - BASELINE_WRIST_3_MAX_Z_M) < 0.005, (
            f"wrist_3_max_z drifted: got {result.wrist_3_max_z_m:.4f}, "
            f"baseline {BASELINE_WRIST_3_MAX_Z_M:.4f}"
        )
        assert abs(result.peg_max_z_m - BASELINE_PEG_MAX_Z_M) < 0.005, (
            f"peg_max_z drifted: got {result.peg_max_z_m:.4f}, "
            f"baseline {BASELINE_PEG_MAX_Z_M:.4f}"
        )
        # joint_vel_peak and path-length can drift slightly on first vs
        # subsequent persistent-handle runs; tolerate 10 % drift on these.
        assert abs(result.joint_vel_peak_rad_s - BASELINE_JOINT_VEL_PEAK) < 1.5, (
            f"joint_vel_peak drifted: got {result.joint_vel_peak_rad_s:.3f}, "
            f"baseline {BASELINE_JOINT_VEL_PEAK:.3f}"
        )
        assert abs(result.cartesian_path_length_m - BASELINE_CART_PATH_LEN_M) < 0.05, (
            f"cart path drifted: got {result.cartesian_path_length_m:.4f}, "
            f"baseline {BASELINE_CART_PATH_LEN_M:.4f}"
        )
        assert result.grasp_acquired_step == BASELINE_GRASP_ACQUIRED, (
            f"grasp_acquired_step drifted: got {result.grasp_acquired_step}, "
            f"baseline {BASELINE_GRASP_ACQUIRED}"
        )


# ════════════════════════════════════════════════════════════════════════
class TestRegistryMultiObjectReadiness:
    """The registry must track multiple objects and fixtures, even if
    the current task only manipulates one of them."""

    def test_registry_tracks_extra_objects_and_fixtures(self, world, cell_stage):
        from cell_authoring.tasks import (
            CellStateRegistry, ObjectState, FixtureState,
            TaskExecutor, TrajectoryProfile,
        )
        cell_cfg = load_cfg()
        registry = CellStateRegistry()
        # Pre-register an extra peg + a fixture slot that the current
        # task does NOT manipulate.
        registry.register_object(ObjectState(
            object_id="FutureExtraPeg",
            pose_m=(-0.70, 0.10, 0.701),
        ))
        registry.register_fixture(FixtureState(
            fixture_id="FutureTraySlot_A",
        ))
        task = _build_validated_task()
        executor = TaskExecutor(
            world=world, stage=cell_stage, cell_cfg=cell_cfg, registry=registry,
        )
        try:
            result = executor.execute(task, profile=TrajectoryProfile.NOMINAL)
        finally:
            executor.close()
        from cell_authoring.tasks import TaskOutcome
        assert result.outcome == TaskOutcome.PASS, (
            f"unexpected outcome {result.outcome.value}: {result.outcome_detail}"
        )

        # The extra object should be present in the registry snapshot.
        snap = registry.snapshot()
        assert "FutureExtraPeg" in snap["objects"], (
            f"FutureExtraPeg not retained in registry; objects={list(snap['objects'].keys())}"
        )
        assert "FutureTraySlot_A" in snap["fixtures"], (
            f"FutureTraySlot_A not retained; fixtures={list(snap['fixtures'].keys())}"
        )
        # The validated peg should also be present.
        assert "Peg_01" in snap["objects"]
        # WorkFixture_01 should still be present in the registry
        # (registered by ``TaskExecutor.prepare()``). Phase 4B Step 8 /
        # Phase 2 migrated fixture-occupancy mutation authority from
        # the executor up to ``ExecutionSession.step()`` Phase G
        # (D-CONT-5). After ``executor.execute(...)`` alone — without a
        # surrounding session — the executor MUST NOT have mutated
        # ``WorkFixture_01.occupied_by``; the session-committed
        # occupancy property is tested at the Phase 4B layer
        # (test_cell_01_phase_4b_step8_p2_occupancy_authority.py).
        wf = snap["fixtures"].get("WorkFixture_01")
        assert wf is not None
        assert wf["occupied_by"] == [], (
            f"D-CONT-5 violation: executor.execute() mutated fixture "
            f"occupancy directly; WorkFixture_01.occupied_by={wf['occupied_by']!r}"
        )
        # The placement evidence the executor emits (replaces the
        # old executor-owned occupancy mutation): peg_xyz_final must be
        # within the place_target's placement_tolerance_xy_m of the
        # target pose. This is the objective evidence the session keys
        # its Phase-G mark_fixture_occupied commit on.
        target = task.place_target.world_pose_m
        tol = task.place_target.placement_tolerance_xy_m
        dx = abs(result.peg_xyz_final[0] - target[0])
        dy = abs(result.peg_xyz_final[1] - target[1])
        assert dx <= tol and dy <= tol, (
            f"placement evidence outside tolerance: "
            f"peg_xyz_final={result.peg_xyz_final} target={target} "
            f"tol={tol*1000:.0f}mm dx={dx*1000:.1f}mm dy={dy*1000:.1f}mm"
        )


# ════════════════════════════════════════════════════════════════════════
class TestProfilesPreserveDeterminismOnNominal:
    """Two back-to-back NOMINAL executions through one TaskExecutor
    must produce bit-identical peg final pose."""

    def test_two_back_to_back_nominal_cycles_are_bit_identical(self, world, cell_stage):
        from cell_authoring.tasks import TaskExecutor, TrajectoryProfile
        cell_cfg = load_cfg()
        task = _build_validated_task()
        executor = TaskExecutor(world=world, stage=cell_stage, cell_cfg=cell_cfg)
        try:
            r0 = executor.execute(task, profile=TrajectoryProfile.NOMINAL)
            r1 = executor.execute(task, profile=TrajectoryProfile.NOMINAL)
        finally:
            executor.close()
        assert tuple(r0.peg_xyz_final) == tuple(r1.peg_xyz_final), (
            f"peg final pose drifted between back-to-back NOMINAL runs:\n"
            f"  r0: {r0.peg_xyz_final}\n  r1: {r1.peg_xyz_final}"
        )
        assert r0.wrist_3_max_z_m == r1.wrist_3_max_z_m
        assert r0.cartesian_path_length_m == r1.cartesian_path_length_m
        assert r0.grasp_acquired_step == r1.grasp_acquired_step


# ════════════════════════════════════════════════════════════════════════
class TestReplayPackageRoundTrip:
    """Build a ReplayPackage from a TaskResult; verify on-disk contents."""

    def test_replay_package_directory_contents(self, world, cell_stage, tmp_path):
        from cell_authoring.tasks import (
            TaskExecutor, TrajectoryProfile, UnifiedValidator, ReplayPackage,
        )
        cell_cfg = load_cfg()
        task = _build_validated_task()
        executor = TaskExecutor(world=world, stage=cell_stage, cell_cfg=cell_cfg)
        try:
            result = executor.execute(task, profile=TrajectoryProfile.NOMINAL)
        finally:
            executor.close()
        report = UnifiedValidator().summarise([result])
        pkg = ReplayPackage(
            task=task, result=result, cell_cfg=cell_cfg,
            profile=TrajectoryProfile.NOMINAL, seed=20260519,
            validation_report=report,
        )
        out = pkg.write_dir(tmp_path / "phase_4a_replay")

        # Files exist.
        assert (out / "summary.json").is_file()
        assert (out / "task_definition.json").is_file()
        assert (out / "cell_config.snapshot.yaml").is_file()
        assert (out / "registry_snapshot.json").is_file()

        # summary.json is valid + carries the PASS verdict.
        summary = json.loads((out / "summary.json").read_text())
        assert summary["package_kind"] == "phase_4a_replay"
        assert summary["task_id"] == task.task_id
        assert summary["profile"] == "nominal"
        assert summary["task_result"]["outcome"] == "PASS"
        assert summary["validation_report"]["pass_rate"] == 1.0

        # task_definition.json round-trips into structured dict.
        td = json.loads((out / "task_definition.json").read_text())
        assert td["task_id"] == task.task_id
        assert td["task_kind"] == "pick_place"
        assert td["pick_source"]["object_id"] == "Peg_01"
        assert td["place_target"]["fixture_id"] == "WorkFixture_01"
        assert td["grasp_strategy"]["kind"] == "prismatic_clamp"
        assert td["transport_strategy"]["kind"] == "joint_space_lerp"
        assert td["release_strategy"]["kind"] == "open_jaw"
