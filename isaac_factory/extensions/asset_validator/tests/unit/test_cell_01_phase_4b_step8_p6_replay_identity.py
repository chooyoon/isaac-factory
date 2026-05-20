"""Phase 4B Step 8 / Phase 6 — replay-identity comparator tests.

Pure-Python tests for ``tools/check_session_replay_identity.py`` plus
end-to-end tests that two ExecutionSessions wired through
``DurableTraceRecorder`` produce L3 replay-identical SessionPackages.

Coverage
========

  * TestComparatorContract           — strict byte-equality behaviour;
                                        divergences detected;
                                        missing/corrupt inputs rejected;
                                        no tolerance.
  * TestSessionPackageReplayIdentity — two ExecutionSession runs with
                                        identical inputs produce
                                        byte-equal SessionPackages
                                        (manifest.json + events.jsonl).
  * TestContaminationResistance      — perturbing forbidden registry
                                        state between session runs does
                                        NOT alter SessionPackage bytes.

Cites D-REPLAY-1, D-REPLAY-2, D-CONT-6, D-CONT-6a, D-CONT-7.

All tests pure-Python; no Isaac Sim, no PhysX. Real-host verification
runs via ``scripts/launch_phase_6_replay_identity.py``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)

_TOOLS_PATH = _WORKSPACE / "tools"
_COMPARATOR_PATH = _TOOLS_PATH / "check_session_replay_identity.py"
if str(_TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(_TOOLS_PATH))


from cell_authoring.orchestration import (  # noqa: E402
    DurableTraceRecorder,
    EventBus,
    ExecutionSession,
    ResetScope,
    SessionPackage,
)
from cell_authoring.orchestration.phase_5_two_node import (  # noqa: E402
    build_phase_5_graph,
    build_phase_5_task_resolver,
    register_phase_5_fixtures,
)
from cell_authoring.tasks import (  # noqa: E402
    CellStateRegistry,
    ContactState,
    FixtureState,
    ObjectState,
    RobotState,
)


# Import the comparator module to test its in-process behaviour.
import check_session_replay_identity as comparator  # noqa: E402


# ───────────────────────────── fakes ─────────────────────────────


@dataclass(frozen=True)
class _FakeOutcome:
    value: str


@dataclass(frozen=True)
class _FakeResult:
    passed: bool
    outcome: Any
    peg_xyz_initial: tuple[float, float, float] | None = None
    peg_xyz_final:   tuple[float, float, float] | None = None


class _Phase6FakeExecutor:
    """Same as Phase 5's fake but with Phase 5 fixtures pre-registered.
    Reusable across sessions in a single test."""

    def __init__(self):
        self.call_log: list[tuple] = []
        self.registry = CellStateRegistry()
        self.registry.register_object(ObjectState(
            object_id="Peg_01", pose_m=(-0.80, 0.0, 0.701),
        ))
        self.registry.register_fixture(FixtureState(fixture_id="WorkFixture_01"))
        register_phase_5_fixtures(self.registry)

    def prepare(self) -> None:
        self.call_log.append(("prepare",))

    def reset(self, scope: ResetScope = ResetScope.FULL) -> None:
        self.call_log.append(("reset", scope))
        if scope == ResetScope.FULL:
            self.registry.update_object_pose("Peg_01", (-0.80, 0.0, 0.701), 0.0)

    def execute(self, task: Any, **kwargs: Any) -> _FakeResult:
        self.call_log.append(("execute", task))
        initial = self.registry.objects["Peg_01"].pose_m
        place = task.place_target.world_pose_m
        self.registry.update_object_pose("Peg_01", place, 0.0)
        return _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_initial=tuple(initial),
            peg_xyz_final=tuple(place),
        )

    def close(self) -> None:
        self.call_log.append(("close",))


def _run_two_node_session_to_disk(pkg_dir: Path,
                                    executor: _Phase6FakeExecutor) -> SessionPackage:
    """Run the Phase 5 2-node session through DurableTraceRecorder
    writing to ``pkg_dir``. Returns the SessionPackage."""
    pkg = SessionPackage(pkg_dir)
    rec = DurableTraceRecorder(pkg)
    bus = EventBus()
    bus.register(rec)
    # Reset Phase 5 fixtures BEFORE each session so two sessions start
    # from identical authoritative state.
    register_phase_5_fixtures(executor.registry)
    session = ExecutionSession(
        graph=build_phase_5_graph(),
        task_executor=executor,
        event_bus=bus,
        trace_recorder=rec,
        task_resolver=build_phase_5_task_resolver(),
    )
    session.begin()
    session.step()
    session.step()
    session.complete()
    return pkg


def _make_minimal_package(pkg_dir: Path,
                           *,
                           events_lines: list[str] | None = None,
                           manifest: dict | None = None) -> SessionPackage:
    """Construct a SessionPackage on disk with hand-authored contents.
    Used for comparator-contract tests.

    Default events stream is a minimal-but-valid Phase-5+ trace:
    one NodeBoundarySnapshot carrying ``schema_version=2`` and one
    terminal SessionCompleted. The Step 9 Phase 7 comparator
    requires both for a meaningful compare; callers that want to
    test pre-Phase-5 / INCOMPLETE / divergent-terminus behaviour
    override ``events_lines``.
    """
    pkg_dir.mkdir(parents=True, exist_ok=True)
    if events_lines is None:
        events_lines = [
            ('{"seq":0,"event_type":"NodeBoundarySnapshot",'
             '"payload":{"canonical_hash":"h","node_id":null,'
             '"schema_version":2,"snapshot_kind":"session_initial",'
             '"snapshot_seq":0}}'),
            ('{"seq":1,"event_type":"SessionCompleted",'
             '"payload":{"completed_count":0,"failed_count":0,'
             '"node_count":0}}'),
        ]
    (pkg_dir / "events.jsonl").write_text("\n".join(events_lines) + "\n",
                                          encoding="utf-8")
    if manifest is None:
        manifest = {
            "package_version": 1,
            "invariant_contract_version": 1,
            "event_count": len(events_lines),
            "trace_hash": None,
            "runtime_hash": None,
            "session_identity": None,
        }
    (pkg_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return SessionPackage(pkg_dir)


# ═══════════════════════════════════════════════════════════════════════
class TestComparatorContract:
    """Strict byte-equality behaviour. No tolerance, no filtering."""

    def test_identical_packages_compare_pass(self, tmp_path):
        a = _make_minimal_package(tmp_path / "a")
        b = _make_minimal_package(tmp_path / "b")
        rc = comparator.compare_session_packages(a.path, b.path)
        assert rc == 0

    def test_one_byte_events_difference_compares_fail(self, tmp_path):
        a = _make_minimal_package(tmp_path / "a")
        # B differs from A in payload — same terminus + schema, so
        # divergence is REPLAY-DIVERGENT (1), not REPLAY-INVALID.
        b = _make_minimal_package(
            tmp_path / "b",
            events_lines=[
                ('{"seq":0,"event_type":"NodeBoundarySnapshot",'
                 '"payload":{"canonical_hash":"DIFFERENT","node_id":null,'
                 '"schema_version":2,"snapshot_kind":"session_initial",'
                 '"snapshot_seq":0}}'),
                ('{"seq":1,"event_type":"SessionCompleted",'
                 '"payload":{"completed_count":0,"failed_count":0,'
                 '"node_count":0}}'),
            ],
        )
        rc = comparator.compare_session_packages(a.path, b.path)
        assert rc == 1

    def test_one_byte_manifest_difference_compares_fail(self, tmp_path):
        a = _make_minimal_package(tmp_path / "a")
        # B's manifest has a different event_count.
        b = _make_minimal_package(
            tmp_path / "b",
            manifest={
                "package_version": 1,
                "invariant_contract_version": 1,
                "event_count": 999,
                "trace_hash": None,
                "runtime_hash": None,
                "session_identity": None,
            },
        )
        rc = comparator.compare_session_packages(a.path, b.path)
        assert rc == 1

    def test_missing_session_directory_returns_2(self, tmp_path):
        a = _make_minimal_package(tmp_path / "a")
        rc = comparator.compare_session_packages(a.path, tmp_path / "no_such_dir")
        assert rc == 2

    def test_missing_events_file_returns_2(self, tmp_path):
        a = _make_minimal_package(tmp_path / "a")
        b_dir = tmp_path / "b"
        b_dir.mkdir()
        (b_dir / "manifest.json").write_text("{}", encoding="utf-8")
        # events.jsonl missing.
        rc = comparator.compare_session_packages(a.path, b_dir)
        assert rc == 2

    def test_missing_manifest_file_returns_2(self, tmp_path):
        a = _make_minimal_package(tmp_path / "a")
        b_dir = tmp_path / "b"
        b_dir.mkdir()
        (b_dir / "events.jsonl").write_text("{}\n", encoding="utf-8")
        # manifest.json missing.
        rc = comparator.compare_session_packages(a.path, b_dir)
        assert rc == 2

    def test_cli_invocation_returns_correct_exit_code(self, tmp_path):
        # Sanity test the script-mode entry point.
        a = _make_minimal_package(tmp_path / "a")
        b = _make_minimal_package(tmp_path / "b")
        result = subprocess.run(
            [sys.executable, str(_COMPARATOR_PATH), str(a.path), str(b.path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"CLI returned {result.returncode}; stdout: {result.stdout!r}; "
            f"stderr: {result.stderr!r}"
        )
        assert "L3 REPLAY-IDENTITY: REPLAY-IDENTICAL" in result.stdout

    def test_cli_invocation_reports_failure_clearly(self, tmp_path):
        a = _make_minimal_package(tmp_path / "a")
        # Phase 7: same terminus + schema, but payload differs → divergent.
        b = _make_minimal_package(
            tmp_path / "b",
            events_lines=[
                ('{"seq":0,"event_type":"NodeBoundarySnapshot",'
                 '"payload":{"canonical_hash":"DIFFERENT","node_id":null,'
                 '"schema_version":2,"snapshot_kind":"session_initial",'
                 '"snapshot_seq":0}}'),
                ('{"seq":1,"event_type":"SessionCompleted",'
                 '"payload":{"completed_count":0,"failed_count":0,'
                 '"node_count":0}}'),
            ],
        )
        result = subprocess.run(
            [sys.executable, str(_COMPARATOR_PATH), str(a.path), str(b.path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "L3 REPLAY-IDENTITY: REPLAY-DIVERGENT" in result.stdout

    def test_no_tolerance_on_numeric_values(self, tmp_path):
        # The comparator MUST NOT collapse near-identical numbers.
        # Replay identity is strict byte-equality (D-FAULT-11a).
        # Both packages need a terminal event + boundary snapshot for
        # the Phase 7 comparator to classify them comparable; only the
        # payload float value differs.
        a = _make_minimal_package(
            tmp_path / "a",
            events_lines=[
                ('{"seq":0,"event_type":"NodeBoundarySnapshot",'
                 '"payload":{"canonical_hash":"h","node_id":null,'
                 '"schema_version":2,"snapshot_kind":"session_initial",'
                 '"snapshot_seq":0}}'),
                ('{"seq":1,"event_type":"SessionCompleted",'
                 '"payload":{"x":0.10000000000000001}}'),
            ],
        )
        b = _make_minimal_package(
            tmp_path / "b",
            events_lines=[
                ('{"seq":0,"event_type":"NodeBoundarySnapshot",'
                 '"payload":{"canonical_hash":"h","node_id":null,'
                 '"schema_version":2,"snapshot_kind":"session_initial",'
                 '"snapshot_seq":0}}'),
                ('{"seq":1,"event_type":"SessionCompleted",'
                 '"payload":{"x":0.1}}'),
            ],
        )
        rc = comparator.compare_session_packages(a.path, b.path)
        assert rc == 1, (
            "Comparator must NOT apply numeric tolerance — replay "
            "identity is strict byte-equality (D-FAULT-11a)"
        )


# ═══════════════════════════════════════════════════════════════════════
class TestSessionPackageReplayIdentity:
    """Two ExecutionSession runs with identical inputs produce
    byte-equal SessionPackages."""

    def test_two_runs_through_durable_recorder_byte_equal(self, tmp_path):
        ex_a = _Phase6FakeExecutor()
        ex_b = _Phase6FakeExecutor()
        pkg_a = _run_two_node_session_to_disk(tmp_path / "run_a", ex_a)
        pkg_b = _run_two_node_session_to_disk(tmp_path / "run_b", ex_b)
        # Bytewise equality through the comparator.
        rc = comparator.compare_session_packages(pkg_a.path, pkg_b.path)
        assert rc == 0, "two identical-input runs must produce byte-equal SessionPackages"

    def test_events_jsonl_byte_equal_directly(self, tmp_path):
        ex_a = _Phase6FakeExecutor()
        ex_b = _Phase6FakeExecutor()
        pkg_a = _run_two_node_session_to_disk(tmp_path / "run_a", ex_a)
        pkg_b = _run_two_node_session_to_disk(tmp_path / "run_b", ex_b)
        bytes_a = pkg_a.events_path.read_bytes()
        bytes_b = pkg_b.events_path.read_bytes()
        assert bytes_a == bytes_b

    def test_manifest_json_byte_equal_directly(self, tmp_path):
        ex_a = _Phase6FakeExecutor()
        ex_b = _Phase6FakeExecutor()
        pkg_a = _run_two_node_session_to_disk(tmp_path / "run_a", ex_a)
        pkg_b = _run_two_node_session_to_disk(tmp_path / "run_b", ex_b)
        bytes_a = pkg_a.manifest_path.read_bytes()
        bytes_b = pkg_b.manifest_path.read_bytes()
        assert bytes_a == bytes_b

    def test_event_count_is_consistent(self, tmp_path):
        # Sanity: the 2-node session emits a deterministic number of
        # events. (SessionStarted + session_initial + 2×[NodeSelected
        # + NodeExecutionStarted + pre_node + FixtureStateChanged
        # variations + post_node + NodeExecutionCompleted] +
        # SessionCompleted.)
        ex = _Phase6FakeExecutor()
        pkg = _run_two_node_session_to_disk(tmp_path / "run", ex)
        events = pkg.iter_event_dicts()
        # 1 SessionStarted
        # 1 NodeBoundarySnapshot(session_initial)
        # 1 NodeSelected (N1)
        # 1 NodeExecutionStarted (N1)
        # 1 NodeBoundarySnapshot(pre_node, N1)
        # 1 FixtureStateChanged (FixtureA occupied)
        # 1 NodeBoundarySnapshot(post_node, N1)
        # 1 NodeExecutionCompleted (N1)
        # 1 NodeSelected (N2)
        # 1 NodeExecutionStarted (N2)
        # 1 NodeBoundarySnapshot(pre_node, N2)
        # 1 FixtureStateChanged (FixtureA empty)
        # 1 FixtureStateChanged (FixtureB occupied)
        # 1 NodeBoundarySnapshot(post_node, N2)
        # 1 NodeExecutionCompleted (N2)
        # 1 SessionCompleted
        # ───
        # 16 events total
        assert len(events) == 16


# ═══════════════════════════════════════════════════════════════════════
class TestContaminationResistance:
    """Perturbing forbidden registry state between session runs MUST
    NOT alter the SessionPackage bytes. This is the load-bearing
    Phase-6 contamination assertion at the session-on-disk layer."""

    def _baseline(self, tmp_path) -> tuple[SessionPackage, _Phase6FakeExecutor]:
        ex = _Phase6FakeExecutor()
        pkg = _run_two_node_session_to_disk(tmp_path / "baseline", ex)
        return pkg, ex

    def test_baseline_run_passes_self_comparison(self, tmp_path):
        """Sanity: a baseline + a fresh run with no perturbation
        produce byte-equal packages."""
        baseline_pkg, _ = self._baseline(tmp_path)
        fresh_ex = _Phase6FakeExecutor()
        fresh_pkg = _run_two_node_session_to_disk(tmp_path / "fresh", fresh_ex)
        rc = comparator.compare_session_packages(baseline_pkg.path, fresh_pkg.path)
        assert rc == 0

    def _perturbed_executor_with(self, **registry_perturbations) -> _Phase6FakeExecutor:
        """Return a Phase-6 fake executor whose registry has the given
        D-CONT-2 forbidden / D-CONT-7 observational state perturbed
        BEFORE the session starts."""
        ex = _Phase6FakeExecutor()
        for k, v in registry_perturbations.items():
            if k == "contact":
                ex.registry.contact = v
            elif k == "robot":
                ex.registry.register_robot(v)
            elif k == "metrics":
                for name, val in v.items():
                    ex.registry.set_metric(name, val)
            elif k == "task":
                ex.registry.start_task(v["task_id"], v["started_at_step"])
                if "phase" in v:
                    ex.registry.set_task_phase(v["phase"])
            elif k == "object_contact_with":
                ex.registry.objects["Peg_01"].contact_with = v
            elif k == "object_metadata":
                ex.registry.objects["Peg_01"].metadata.update(v)
            else:
                raise ValueError(f"unknown perturbation: {k}")
        return ex

    def test_contact_state_perturbation_does_not_change_session_package(self, tmp_path):
        baseline_pkg, _ = self._baseline(tmp_path)
        ex = self._perturbed_executor_with(contact=ContactState(
            pad_L_contact=True, pad_R_contact=True,
            floor_contact=True, belt_contact=True, fixture_contact=True,
            pad_pen_max_mm=99.9,
        ))
        perturbed_pkg = _run_two_node_session_to_disk(tmp_path / "perturbed_contact", ex)
        rc = comparator.compare_session_packages(baseline_pkg.path, perturbed_pkg.path)
        assert rc == 0, "contact-state perturbation contaminated SessionPackage bytes"

    def test_robot_state_perturbation_does_not_change_session_package(self, tmp_path):
        baseline_pkg, _ = self._baseline(tmp_path)
        ex = self._perturbed_executor_with(robot=RobotState(
            robot_id="UR10e",
            joint_velocities_rad_s=(7.0,) * 6,
            joint_positions_rad=(0.5,) * 6,
            wrist_3_xyz=(0.3, 0.4, 0.5),
            gripper_state="close",
            gripper_drive_target=-0.030,
        ))
        perturbed_pkg = _run_two_node_session_to_disk(tmp_path / "perturbed_robot", ex)
        rc = comparator.compare_session_packages(baseline_pkg.path, perturbed_pkg.path)
        assert rc == 0, "robot-state perturbation contaminated SessionPackage bytes"

    def test_metrics_perturbation_does_not_change_session_package(self, tmp_path):
        baseline_pkg, _ = self._baseline(tmp_path)
        ex = self._perturbed_executor_with(metrics={
            "peg_max_z_m":      99.9,
            "joint_vel_peak":   42.0,
            "anything_else":    {"nested": [1, 2, 3]},
        })
        perturbed_pkg = _run_two_node_session_to_disk(tmp_path / "perturbed_metrics", ex)
        rc = comparator.compare_session_packages(baseline_pkg.path, perturbed_pkg.path)
        assert rc == 0, "metrics perturbation contaminated SessionPackage bytes"

    def test_object_contact_with_perturbation_does_not_change_session_package(self, tmp_path):
        baseline_pkg, _ = self._baseline(tmp_path)
        ex = self._perturbed_executor_with(
            object_contact_with=("LeftPad", "RightPad", "Floor"),
        )
        perturbed_pkg = _run_two_node_session_to_disk(tmp_path / "perturbed_obj_contact", ex)
        rc = comparator.compare_session_packages(baseline_pkg.path, perturbed_pkg.path)
        assert rc == 0, "object.contact_with perturbation contaminated SessionPackage bytes"

    def test_object_metadata_perturbation_does_not_change_session_package(self, tmp_path):
        baseline_pkg, _ = self._baseline(tmp_path)
        ex = self._perturbed_executor_with(object_metadata={
            "mass_kg": 0.5, "debug": "anything",
        })
        perturbed_pkg = _run_two_node_session_to_disk(tmp_path / "perturbed_obj_metadata", ex)
        rc = comparator.compare_session_packages(baseline_pkg.path, perturbed_pkg.path)
        assert rc == 0, "object.metadata perturbation contaminated SessionPackage bytes"

    def test_task_state_perturbation_does_not_change_session_package(self, tmp_path):
        baseline_pkg, _ = self._baseline(tmp_path)
        ex = self._perturbed_executor_with(task={
            "task_id": "spurious_task",
            "started_at_step": 999,
            "phase": "executing",
        })
        perturbed_pkg = _run_two_node_session_to_disk(tmp_path / "perturbed_task", ex)
        rc = comparator.compare_session_packages(baseline_pkg.path, perturbed_pkg.path)
        assert rc == 0, "task-state perturbation contaminated SessionPackage bytes"

    def test_all_forbidden_perturbations_combined_does_not_change_session_package(self, tmp_path):
        """The strict combined contamination test: every D-CONT-2 /
        D-CONT-7 perturbation applied simultaneously. SessionPackage
        must STILL be byte-identical to the baseline."""
        baseline_pkg, _ = self._baseline(tmp_path)
        ex = _Phase6FakeExecutor()
        ex.registry.contact = ContactState(
            pad_L_contact=True, pad_pen_max_mm=99.0,
        )
        ex.registry.register_robot(RobotState(
            robot_id="UR10e",
            joint_velocities_rad_s=(7.0,) * 6,
        ))
        ex.registry.start_task("xx", started_at_step=42)
        ex.registry.set_metric("peg_max_z_m", 7.7)
        ex.registry.objects["Peg_01"].contact_with = ("Foo", "Bar")
        ex.registry.objects["Peg_01"].metadata["debug"] = "X"
        perturbed_pkg = _run_two_node_session_to_disk(tmp_path / "perturbed_all", ex)
        rc = comparator.compare_session_packages(baseline_pkg.path, perturbed_pkg.path)
        assert rc == 0, (
            "ALL-FORBIDDEN combined contamination perturbation altered "
            "SessionPackage bytes — this is the load-bearing Phase-6 "
            "assertion and a failure here means D-CONT-6 contamination "
            "resistance is broken"
        )


# ═══════════════════════════════════════════════════════════════════════
class TestStep8ClosureSanityChecks:
    """Cross-checks tying Step 8's deliverables together."""

    def test_comparator_tool_file_exists(self):
        assert _COMPARATOR_PATH.is_file(), (
            f"comparator script missing at {_COMPARATOR_PATH}"
        )

    def test_phase_6_runner_script_exists(self):
        runner = _WORKSPACE / "scripts" / "launch_phase_6_replay_identity.py"
        assert runner.is_file(), f"Phase 6 runner missing at {runner}"

    def test_comparator_module_exports_main_api(self):
        # The function-level API the runner calls.
        assert callable(comparator.compare_session_packages)
        assert callable(comparator.main)
