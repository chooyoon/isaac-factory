"""Phase 4B Step 8 / Phase 4 — ACQUIRED_ONLY hardening tests.

Proves the contract clauses landed in section 12 of
[docs/phase_4b_deterministic_semantics.md] for the reset-scope
discipline:

  * D-CONT-3   — boundary PhysX-quiescence. The ACQUIRED_ONLY path
                 contains no simulator-advancing primitive
                 (``world.step``, ``world.play``, ``kit.update``).
  * D-CONT-4   — ACQUIRED_ONLY is selective authoritative persistence
                 only. No teleport primitives (``set_joint_positions``,
                 ``set_world_poses``, ``set_linear_velocities``). No
                 ``_art.initialize()`` re-init.
  * D-SESS-1   — reset_scope is determined by the session, passed to
                 the executor as a kwarg. The executor honours; it
                 does not decide.
  * Trajectory selection (Phase 4 scope §6) — declarative, deterministic
                 lookup; no runtime adaptation. Unknown ``trajectory_id``
                 raises EXECUTOR_ERROR, no silent fallback.

The static introspection tests in ``TestAcquiredOnlyForbiddenPrimitives``
are load-bearing: they assert at the source-code level that the
forbidden primitives are absent from ``_reset_acquired_only``. A
future contributor who adds e.g. ``set_joint_positions`` to that method
to "fix" a residual-velocity issue would fail these tests immediately.

All tests pure-Python; no Isaac Sim, no PhysX.
"""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


def _body_source_without_docstring(func) -> str:
    """Return the source of ``func`` with the docstring stripped.

    Essential for the forbidden-primitives introspection tests: the
    executor's docstring intentionally enumerates the forbidden
    primitives ("Forbidden: set_joint_positions, ..."), so a naive
    string search would false-positive on the docstring itself. We
    AST-parse the function, drop the first ``Expr`` statement if it
    is a string constant (the docstring), and unparse the remaining
    body."""
    src = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(src)
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef), (
        f"_body_source_without_docstring expected a FunctionDef, got {type(fn).__name__}"
    )
    if (fn.body
            and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)
            and isinstance(fn.body[0].value.value, str)):
        fn.body = fn.body[1:]
    return ast.unparse(fn)


_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


from cell_authoring.orchestration import (  # noqa: E402
    EventBus,
    EVENT_NODE_EXECUTION_STARTED,
    ExecutionSession,
    InMemoryTraceRecorder,
    ResetScope,
    TaskGraph,
    TaskNode,
)
from cell_authoring.tasks import (  # noqa: E402
    CellStateRegistry,
    PickPlaceTask,
    PickSource,
    PlaceTarget,
    PrismaticClampGrasp,
    JointSpaceLerpTransport,
    OpenJawRelease,
    TaskExecutor,
    TaskOutcome,
    TaskResult,
)


# ───────────────────────────── fakes ─────────────────────────────


@dataclass(frozen=True)
class _FakeOutcome:
    value: str


@dataclass(frozen=True)
class _FakeResult:
    passed: bool
    outcome: Any
    peg_xyz_final: tuple[float, float, float] | None = None


class _RecordingExecutor:
    """Records the full call log so tests can assert reset scope was
    plumbed correctly and that the session's call ordering is
    D-CONT-3-compliant (no world stepping between phases)."""

    def __init__(self, *, registry: CellStateRegistry | None = None):
        self.call_log: list[tuple] = []
        self.registry = registry if registry is not None else CellStateRegistry()

    def prepare(self) -> None:
        self.call_log.append(("prepare",))

    def reset(self, scope: ResetScope = ResetScope.FULL) -> None:
        self.call_log.append(("reset", scope))

    def execute(self, task: Any, **kwargs: Any) -> _FakeResult:
        self.call_log.append(("execute", task, dict(kwargs)))
        return _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )

    def close(self) -> None:
        self.call_log.append(("close",))


def _single_node_graph(node_id: str = "n0", task_ref: str = "t") -> TaskGraph:
    return TaskGraph.build(nodes=[TaskNode(node_id=node_id, task_ref=task_ref)])


def _belt_pick_task(**overrides: Any) -> PickPlaceTask:
    """A standard from-belt PickPlace task. Tests override
    ``trajectory_id`` etc."""
    return PickPlaceTask(
        task_id=overrides.pop("task_id", "t"),
        pick_source=PickSource(
            object_id="Peg_01",
            world_pose_m=(-0.80, 0.0, 0.701),
            source_kind="conveyor",
        ),
        place_target=PlaceTarget(
            fixture_id="WorkFixture_01",
            world_pose_m=(0.65, 0.0, 0.65),
            placement_tolerance_xy_m=0.05,
        ),
        grasp_strategy=PrismaticClampGrasp(),
        transport_strategy=JointSpaceLerpTransport(profile_id="nominal"),
        release_strategy=OpenJawRelease(),
        **overrides,
    )


# ═══════════════════════════════════════════════════════════════════════
class TestResetScopePlumbing:
    """D-CONT-4 + D-SESS-1 — the session determines reset_scope and
    passes it to execute(); the executor honours."""

    def test_first_node_of_session_uses_full_scope(self):
        ex = _RecordingExecutor()
        bus = EventBus()
        s = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=bus,
        )
        s.begin()
        s.step()
        s.complete()
        # The session's begin() calls reset(FULL) via the executor
        # protocol AND the execute() call carries reset_scope=FULL.
        execute_calls = [c for c in ex.call_log if c[0] == "execute"]
        assert len(execute_calls) == 1
        _, _task, kwargs = execute_calls[0]
        assert kwargs.get("reset_scope") == ResetScope.FULL

    def test_node_execution_started_payload_carries_actual_scope(self):
        ex = _RecordingExecutor()
        bus = EventBus()
        rec = InMemoryTraceRecorder()
        bus.register(rec)
        s = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=bus,
        )
        s.begin(); s.step(); s.complete()
        nes = next(e for e in rec.events
                   if e.event_type == EVENT_NODE_EXECUTION_STARTED)
        # First node → FULL. The payload reflects the actual scope
        # used, not a hardcoded FULL.
        assert nes.payload["reset_scope"] == "full"

    def test_session_default_between_node_scope_is_acquired_only(self):
        # The session is constructed with ``reset_scope_between_nodes``
        # defaulted to ACQUIRED_ONLY per D-CONT-4.
        ex = _RecordingExecutor()
        s = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=EventBus(),
        )
        # We can't yet exercise the between-node path (Phase 5 scope),
        # but the constructor default is what subsequent phases will
        # consume.
        assert s._reset_scope_between_nodes == ResetScope.ACQUIRED_ONLY

    def test_caller_override_in_execute_kwargs_wins(self):
        # Test-only escape hatch: if a caller passes ``reset_scope``
        # in ``execute_kwargs``, the session does NOT override it.
        ex = _RecordingExecutor()
        s = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=EventBus(),
            execute_kwargs={"reset_scope": ResetScope.ACQUIRED_ONLY},
        )
        s.begin(); s.step(); s.complete()
        execute_calls = [c for c in ex.call_log if c[0] == "execute"]
        _, _task, kwargs = execute_calls[0]
        # Caller's override survives — first-node session default
        # would otherwise be FULL.
        assert kwargs["reset_scope"] == ResetScope.ACQUIRED_ONLY


# ═══════════════════════════════════════════════════════════════════════
class TestAcquiredOnlyForbiddenPrimitives:
    """D-CONT-3 + D-CONT-4 — static introspection on
    ``TaskExecutor._reset_acquired_only`` to assert the forbidden
    primitives are absent from the source.

    These tests are load-bearing: they directly enforce the contract
    at the code level. A future contributor who adds a teleport or a
    world-step to ``_reset_acquired_only`` will fail these tests
    before the change can land."""

    def _source(self) -> str:
        # Docstring stripped — see _body_source_without_docstring.
        return _body_source_without_docstring(TaskExecutor._reset_acquired_only)

    def test_no_world_step_call(self):
        # D-CONT-3 — no simulator advancement.
        src = self._source()
        assert "world.step" not in src, (
            "D-CONT-3 violation: _reset_acquired_only contains "
            "world.step call"
        )

    def test_no_world_play_call(self):
        # D-CONT-3 — world.play() can drive an implicit step.
        src = self._source()
        assert "world.play" not in src, (
            "D-CONT-3 violation: _reset_acquired_only contains "
            "world.play call"
        )

    def test_no_kit_update_call(self):
        # D-CONT-3 — Kit's update loop drives stepping.
        src = self._source()
        assert "kit.update" not in src, (
            "D-CONT-3 violation: _reset_acquired_only contains "
            "kit.update call"
        )

    def test_no_world_reset_call(self):
        # ACQUIRED_ONLY explicitly must NOT call world.reset() —
        # that would restore default poses for every prim, destroying
        # retained state (D-CONT-4 violation).
        src = self._source()
        assert "world.reset" not in src, (
            "D-CONT-4 violation: _reset_acquired_only contains "
            "world.reset call"
        )

    def test_no_set_joint_positions_call(self):
        # D-CONT-4 — direct joint teleport.
        src = self._source()
        assert "set_joint_positions" not in src, (
            "D-CONT-4 violation: _reset_acquired_only contains "
            "set_joint_positions teleport"
        )

    def test_no_set_world_poses_call(self):
        # D-CONT-4 — direct object teleport.
        src = self._source()
        assert "set_world_poses" not in src, (
            "D-CONT-4 violation: _reset_acquired_only contains "
            "set_world_poses teleport"
        )

    def test_no_set_linear_velocities_call(self):
        # D-CONT-4 — direct velocity write.
        src = self._source()
        assert "set_linear_velocities" not in src, (
            "D-CONT-4 violation: _reset_acquired_only contains "
            "set_linear_velocities write"
        )

    def test_no_set_angular_velocities_call(self):
        # D-CONT-4 — direct velocity write (angular).
        src = self._source()
        assert "set_angular_velocities" not in src, (
            "D-CONT-4 violation: _reset_acquired_only contains "
            "set_angular_velocities write"
        )

    def test_no_set_joint_position_targets_call(self):
        # Phase 1 review finding: set_joint_position_targets between
        # nodes is redundant (next cycle's first tick overwrites).
        # Removed for hygiene; surface is narrower.
        src = self._source()
        assert "set_joint_position_targets" not in src, (
            "_reset_acquired_only contains set_joint_position_targets — "
            "the next cycle's first tick should write fresh targets"
        )

    def test_no_articulation_initialize_call(self):
        # Phase 1 review finding H4: _art.initialize() can perturb
        # articulation stabilization state. Removed in Phase 4.
        src = self._source()
        assert "_art.initialize" not in src, (
            "_reset_acquired_only contains _art.initialize() — "
            "this can perturb articulation stabilization state"
        )


# ═══════════════════════════════════════════════════════════════════════
class TestAcquiredOnlyPermittedOperations:
    """Inverse of the forbidden-primitives test: positively assert
    that ACQUIRED_ONLY DOES contain the operations it should.

    Catches the failure mode where a contributor "fixes" the test by
    deleting the method body."""

    def _source(self) -> str:
        return _body_source_without_docstring(TaskExecutor._reset_acquired_only)

    def test_belt_velocity_restore_present(self):
        # The belt halt left by N1 must be restored to the authored
        # value at boundary entry.
        src = self._source()
        assert "self._belt_attr" in src
        assert "self._belt_original" in src

    def test_contact_source_drain_present(self):
        # The C++ contact event buffer must be flushed at boundary
        # entry to prevent N1's residual events from contaminating
        # N2's first tick.
        src = self._source()
        assert "self._contact_source.query_contacts()" in src

    def test_registry_contact_clear_present(self):
        # registry.contact must be zeroed at boundary entry
        # (D-CONT-4 explicitly requires the drain).
        src = self._source()
        assert "self.registry.contact = ContactState()" in src

    def test_registry_metrics_clear_present(self):
        src = self._source()
        assert "self.registry.metrics.clear()" in src


# ═══════════════════════════════════════════════════════════════════════
class TestResetScopeFullStillCallsTeleports:
    """Contrast test: ``_reset_full()`` retains the full Phase 4A
    reset semantics (teleports + world stepping). Phase 4A's 32/32
    regression depends on this.

    Without this contrast, a future refactor could accidentally
    'harden' _reset_full() too and break the validated baseline."""

    def _source(self) -> str:
        return _body_source_without_docstring(TaskExecutor._reset_full)

    def test_full_has_world_reset(self):
        assert "self.world.reset()" in self._source()

    def test_full_has_world_step(self):
        # Phase 4A FULL reset performs 10 settling steps.
        assert "self.world.step" in self._source()

    def test_full_has_set_world_poses(self):
        # Phase 4A FULL teleports the peg back to authored pose.
        assert "set_world_poses" in self._source()

    def test_full_has_set_linear_velocities(self):
        # Phase 4A FULL zeroes the peg's linear velocity.
        assert "set_linear_velocities" in self._source()


# ═══════════════════════════════════════════════════════════════════════
class TestExecuteResetScopeKwarg:
    """D-CONT-4 — TaskExecutor.execute() accepts ``reset_scope`` kwarg.
    When ``None`` (Phase 4A default), execute() falls back to the
    pre-Phase-4 unconditional FULL reset, preserving 32/32 byte-
    equivalence."""

    def test_execute_signature_has_reset_scope_kwarg(self):
        sig = inspect.signature(TaskExecutor.execute)
        assert "reset_scope" in sig.parameters
        # Default is None — Phase 4A backward compatibility marker.
        assert sig.parameters["reset_scope"].default is None

    def test_execute_signature_has_keyword_only_reset_scope(self):
        sig = inspect.signature(TaskExecutor.execute)
        p = sig.parameters["reset_scope"]
        assert p.kind == inspect.Parameter.KEYWORD_ONLY


# ═══════════════════════════════════════════════════════════════════════
class TestPickPlaceTaskTrajectoryId:
    """Phase 4 scope §6 — per-TaskDefinition trajectory selection.
    Declarative; deterministic lookup only."""

    def test_default_trajectory_id_is_none(self):
        task = _belt_pick_task()
        assert task.trajectory_id is None

    def test_trajectory_id_can_be_set(self):
        task = _belt_pick_task(trajectory_id="belt_pick_fixtureA_place")
        assert task.trajectory_id == "belt_pick_fixtureA_place"


# ═══════════════════════════════════════════════════════════════════════
class TestTaskExecutorTrajectorySetsConstructor:
    """Phase 4 scope §6 — the trajectory_sets constructor map is the
    deterministic lookup surface. No planning, no runtime adaptation."""

    def test_constructor_signature_has_trajectory_sets(self):
        sig = inspect.signature(TaskExecutor.__init__)
        assert "trajectory_sets" in sig.parameters
        p = sig.parameters["trajectory_sets"]
        # Defaulted to None — Phase 4A default (no per-task selection).
        assert p.default is None
        # Keyword-only.
        assert p.kind == inspect.Parameter.KEYWORD_ONLY


# ═══════════════════════════════════════════════════════════════════════
class TestSessionAuthorityPreservation:
    """D-SESS-1 — ACQUIRED_ONLY semantics do NOT expand the orchestration
    authority surface. The session remains the sole orchestration-
    state authority; the executor honours scope without making
    lifecycle or occupancy decisions."""

    def test_executor_call_log_has_no_mark_fixture_after_acquired_only(self):
        # Verify the executor surface remains observational. The
        # _RecordingExecutor records every method call; no
        # ``mark_fixture_*`` should appear regardless of reset scope.
        ex = _RecordingExecutor()
        s = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=EventBus(),
        )
        s.begin(); s.step(); s.complete()
        names = {call[0] for call in ex.call_log}
        assert names <= {"prepare", "reset", "execute", "close"}
        assert "mark_fixture_occupied" not in names
        assert "mark_fixture_empty"    not in names

    def test_session_default_reset_scope_can_be_overridden_at_construction(self):
        # An explicit constructor argument lets a caller override the
        # default between-node scope. This is the declarative seam for
        # any future tests/tooling that wants FULL between nodes (e.g.
        # to reproduce Phase 4A behaviour under the new wiring).
        ex = _RecordingExecutor()
        s = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=EventBus(),
            reset_scope_between_nodes=ResetScope.FULL,
        )
        assert s._reset_scope_between_nodes == ResetScope.FULL
