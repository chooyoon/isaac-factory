"""Phase 4B Step 8 / Phase 2 — occupancy authority migration tests.

Proves the contract clauses landed in section 12 of
[docs/phase_4b_deterministic_semantics.md] for the first time in code:

  * D-CONT-5    — fixture occupancy mutation is callable only from
                  ``ExecutionSession.step()`` Phase G, conditioned on
                  PASS verdict + declared fixture transitions.
  * D-CONT-5a   — TaskExecutor performs observational projection only;
                  no categorical lifecycle transitions.
  * D-LIFE-6    — binary fixture occupancy (empty ↔ occupied(object_id)).
  * D-LIFE-7    — no transition between two distinct occupied(...) states
                  without an intervening empty.
  * D-CONT-7    — registry membership does NOT imply continuity authority;
                  ``FixtureState.occupied_by`` shape is singleton.
  * D-EXEC-7/8  — trace commit follows the action; FixtureStateChanged
                  emits ordered between the registry mutation and the
                  closing NodeExecutionCompleted of the same orchestration
                  tick.

All tests pure-Python; no Isaac Sim, no PhysX. The fake executor exposes
a ``.registry`` attribute so the session's D-CONT-5 commit logic can
be exercised end-to-end without simulation.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


from cell_authoring.orchestration import (  # noqa: E402
    EventBus,
    EVENT_FIXTURE_STATE_CHANGED,
    EVENT_NODE_EXECUTION_COMPLETED,
    EVENT_NODE_EXECUTION_STARTED,
    EVENT_NODE_SELECTED,
    EVENT_SESSION_COMPLETED,
    EVENT_SESSION_FAILED,
    EVENT_SESSION_STARTED,
    ExecutionSession,
    InMemoryTraceRecorder,
    ResetScope,
    TaskGraph,
    TaskNode,
)
from cell_authoring.tasks import (  # noqa: E402
    CellStateRegistry,
    FixtureState,
    PickPlaceTask,
    PickSource,
    PlaceTarget,
    PrismaticClampGrasp,
    JointSpaceLerpTransport,
    OpenJawRelease,
    RegistryStateError,
    TaskOutcome,
    TaskResult,
)


# ───────────────────────────── fakes ─────────────────────────────


@dataclass(frozen=True)
class _FakeOutcome:
    """Stand-in for a ``TaskOutcome`` enum value (exposes ``.value``)."""
    value: str


@dataclass(frozen=True)
class _FakeResult:
    """Minimum surface ExecutionSession reads from a result."""
    passed: bool
    outcome: Any
    peg_xyz_final:   tuple[float, float, float] | None = None
    peg_xyz_initial: tuple[float, float, float] | None = None
    placement_offset_xy_m: tuple[float, float] | None = None
    pick_lift_off_step: int | None = None
    place_landing_step: int | None = None


class _FakeRegistryAwareExecutor:
    """Pure-Python TaskExecutor stand-in with a ``.registry``.

    The session's D-CONT-5 commit logic reads ``self._task_executor
    .registry``; this fake exposes a real :class:`CellStateRegistry`
    so we can test the commit end-to-end without simulation.

    Records every method call into ``call_log`` so tests can verify
    that the executor itself never invokes ``mark_fixture_*``
    (D-CONT-5a — observational projection only).
    """

    def __init__(self, *, execute_result: _FakeResult, registry: CellStateRegistry | None = None):
        self.call_log: list[tuple] = []
        self.registry = registry if registry is not None else CellStateRegistry()
        self._execute_result = execute_result

    def prepare(self) -> None:
        self.call_log.append(("prepare",))

    def reset(self, scope: ResetScope = ResetScope.FULL) -> None:
        self.call_log.append(("reset", scope))

    def execute(self, task: Any, **kwargs: Any) -> _FakeResult:
        self.call_log.append(("execute", task))
        return self._execute_result

    def close(self) -> None:
        self.call_log.append(("close",))


# ───────────────────────── builders / helpers ─────────────────────────


def _pick_place_task(
    *,
    task_id: str = "t",
    pick_object_id: str = "Peg_01",
    pick_fixture_id: str | None = None,
    place_fixture_id: str = "FixtureB",
    place_pose: tuple[float, float, float] = (0.65, 0.0, 0.65),
) -> PickPlaceTask:
    """Build a PickPlaceTask. Optionally a ``pick_source`` carrying a
    ``fixture_id`` attribute (Phase 4A's PickSource has no fixture_id;
    we monkey-attach one to a frozen replacement for from-fixture pick
    testing).
    """
    pick_source = PickSource(
        object_id=pick_object_id,
        world_pose_m=(-0.80, 0.0, 0.701),
        source_kind=("fixture" if pick_fixture_id is not None else "conveyor"),
    )
    if pick_fixture_id is not None:
        # PickSource is frozen; bolt the fixture_id via object.__setattr__
        # on a copy. Forward-compat hack for tests until Phase 5 adds
        # a proper fixture-source-aware PickSource subclass.
        object.__setattr__(pick_source, "fixture_id", pick_fixture_id)
    return PickPlaceTask(
        task_id=task_id,
        pick_source=pick_source,
        place_target=PlaceTarget(
            fixture_id=place_fixture_id,
            world_pose_m=place_pose,
            placement_tolerance_xy_m=0.05,
        ),
        grasp_strategy=PrismaticClampGrasp(),
        transport_strategy=JointSpaceLerpTransport(profile_id="nominal"),
        release_strategy=OpenJawRelease(),
    )


def _single_node_graph(node_id: str = "n0", task_ref: str = "t") -> TaskGraph:
    return TaskGraph.build(nodes=[TaskNode(node_id=node_id, task_ref=task_ref)])


def _session(
    *,
    task: Any,
    result: _FakeResult,
    registry: CellStateRegistry | None = None,
) -> tuple[ExecutionSession, EventBus, _FakeRegistryAwareExecutor, InMemoryTraceRecorder]:
    """Build a single-node session whose task_resolver returns the
    fixed ``task`` regardless of the node passed in.
    """
    reg = registry if registry is not None else CellStateRegistry()
    ex = _FakeRegistryAwareExecutor(execute_result=result, registry=reg)
    bus = EventBus()
    rec = InMemoryTraceRecorder()
    bus.register(rec)
    session = ExecutionSession(
        graph=_single_node_graph(),
        task_executor=ex,
        event_bus=bus,
        task_resolver=lambda _node: task,
    )
    return session, bus, ex, rec


# ═══════════════════════════════════════════════════════════════════════
class TestRegistryBinaryOccupancySemantics:
    """D-LIFE-6 / D-LIFE-7 — singleton occupancy + transition discipline."""

    def test_fixture_state_occupied_by_is_singleton_optional_str(self):
        f = FixtureState(fixture_id="F")
        assert f.occupied_by is None
        f2 = FixtureState(fixture_id="G", occupied_by="Peg_01")
        assert f2.occupied_by == "Peg_01"

    def test_mark_fixture_occupied_on_empty_sets_singleton(self):
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="F"))
        reg.mark_fixture_occupied("F", "Peg_01")
        assert reg.fixtures["F"].occupied_by == "Peg_01"

    def test_mark_fixture_occupied_idempotent_on_same_object(self):
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="F"))
        reg.mark_fixture_occupied("F", "Peg_01")
        reg.mark_fixture_occupied("F", "Peg_01")  # idempotent
        assert reg.fixtures["F"].occupied_by == "Peg_01"

    def test_mark_fixture_occupied_rejects_conflicting_occupant(self):
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="F"))
        reg.mark_fixture_occupied("F", "Peg_01")
        with pytest.raises(RegistryStateError, match="D-LIFE-7"):
            reg.mark_fixture_occupied("F", "Peg_02")
        # Original occupant preserved.
        assert reg.fixtures["F"].occupied_by == "Peg_01"

    def test_mark_fixture_empty_on_occupied_clears(self):
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="F", occupied_by="Peg_01"))
        reg.mark_fixture_empty("F", "Peg_01")
        assert reg.fixtures["F"].occupied_by is None

    def test_mark_fixture_empty_idempotent_on_already_empty(self):
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="F"))
        reg.mark_fixture_empty("F", "Peg_01")  # no-op
        assert reg.fixtures["F"].occupied_by is None

    def test_mark_fixture_empty_rejects_object_id_mismatch(self):
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="F", occupied_by="Peg_01"))
        with pytest.raises(RegistryStateError, match="not the recorded occupant"):
            reg.mark_fixture_empty("F", "Peg_02")
        # Occupant unchanged.
        assert reg.fixtures["F"].occupied_by == "Peg_01"

    def test_mark_fixture_occupied_auto_registers_missing_fixture(self):
        reg = CellStateRegistry()
        reg.mark_fixture_occupied("NewFixture", "Peg_01")
        assert "NewFixture" in reg.fixtures
        assert reg.fixtures["NewFixture"].occupied_by == "Peg_01"

    def test_mark_fixture_empty_auto_registers_missing_fixture(self):
        reg = CellStateRegistry()
        reg.mark_fixture_empty("NewFixture", "Peg_01")  # registers as empty
        assert "NewFixture" in reg.fixtures
        assert reg.fixtures["NewFixture"].occupied_by is None

    def test_snapshot_serialises_occupancy_as_list_of_one_or_empty(self):
        # Backward-compat: snapshot["occupied_by"] is list-shaped so
        # ``"Peg_01" in snap["fixtures"]["F"]["occupied_by"]`` still works.
        # The registry's internal representation is singleton (D-LIFE-6);
        # the snapshot shape is the legacy boundary.
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="F"))
        snap_empty = reg.snapshot()
        assert snap_empty["fixtures"]["F"]["occupied_by"] == []
        reg.mark_fixture_occupied("F", "Peg_01")
        snap_full = reg.snapshot()
        assert snap_full["fixtures"]["F"]["occupied_by"] == ["Peg_01"]


# ═══════════════════════════════════════════════════════════════════════
class TestPhaseGOccupancyCommit_PlaceSide:
    """D-CONT-5 — session commits place-side occupancy on PASS."""

    def test_pass_commits_mark_fixture_occupied(self):
        task = _pick_place_task(
            pick_object_id="Peg_01",
            place_fixture_id="FixtureB",
        )
        result = _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        session, _bus, ex, _rec = _session(task=task, result=result)
        session.begin()
        session.step()
        session.complete()
        assert ex.registry.fixtures["FixtureB"].occupied_by == "Peg_01"

    def test_pass_emits_fixture_state_changed_event(self):
        task = _pick_place_task(place_fixture_id="FixtureB")
        result = _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        _session_, _bus, _ex, rec = _session(task=task, result=result)
        _session_.begin(); _session_.step(); _session_.complete()
        kinds = [e.event_type for e in rec.events]
        assert kinds.count(EVENT_FIXTURE_STATE_CHANGED) == 1
        fsc = next(e for e in rec.events if e.event_type == EVENT_FIXTURE_STATE_CHANGED)
        assert fsc.payload["fixture_id"]       == "FixtureB"
        assert fsc.payload["prev_occupied_by"] is None
        assert fsc.payload["new_occupied_by"]  == "Peg_01"
        assert fsc.payload["by_node_id"]       == "n0"
        assert fsc.payload["transition"]       == "occupied"

    def test_fail_does_not_commit_occupancy(self):
        task = _pick_place_task(place_fixture_id="FixtureB")
        result = _FakeResult(
            passed=False, outcome=_FakeOutcome("PLACEMENT_MISS"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        session, _bus, ex, rec = _session(task=task, result=result)
        session.begin(); session.step(); session.complete()
        # Fixture was never auto-registered because no occupancy commit
        # fired.
        assert "FixtureB" not in ex.registry.fixtures
        # No FixtureStateChanged event emitted.
        kinds = [e.event_type for e in rec.events]
        assert EVENT_FIXTURE_STATE_CHANGED not in kinds


# ═══════════════════════════════════════════════════════════════════════
class TestPhaseGOccupancyCommit_PickSide:
    """D-CONT-5 — session commits pick-side mark_fixture_empty when the
    task picks from a fixture. Phase 4A's PickSource doesn't carry
    fixture_id natively; we use the test helper's monkey-attached
    attribute to exercise the forward-compatible session logic."""

    def test_pass_with_pick_fixture_emits_two_fixture_events_in_order(self):
        # Pre-populate FixtureA with the peg so the empty commit is
        # semantically valid (D-LIFE-7).
        reg = CellStateRegistry()
        reg.register_fixture(FixtureState(fixture_id="FixtureA", occupied_by="Peg_01"))
        task = _pick_place_task(
            pick_object_id="Peg_01",
            pick_fixture_id="FixtureA",
            place_fixture_id="FixtureB",
        )
        result = _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        session, _bus, ex, rec = _session(task=task, result=result, registry=reg)
        session.begin(); session.step(); session.complete()

        # End state: A empty, B occupied by Peg_01.
        assert ex.registry.fixtures["FixtureA"].occupied_by is None
        assert ex.registry.fixtures["FixtureB"].occupied_by == "Peg_01"

        # Event order: pick-side empty THEN place-side occupied
        # (D-EXEC-7 — trace commit follows the action). And both
        # precede NodeExecutionCompleted.
        fsc_events = [e for e in rec.events if e.event_type == EVENT_FIXTURE_STATE_CHANGED]
        assert len(fsc_events) == 2
        assert fsc_events[0].payload["fixture_id"] == "FixtureA"
        assert fsc_events[0].payload["transition"] == "empty"
        assert fsc_events[0].payload["prev_occupied_by"] == "Peg_01"
        assert fsc_events[0].payload["new_occupied_by"] is None
        assert fsc_events[1].payload["fixture_id"] == "FixtureB"
        assert fsc_events[1].payload["transition"] == "occupied"
        # Seq monotonicity (D-BUS-3).
        seq_pick   = fsc_events[0].seq
        seq_place  = fsc_events[1].seq
        seq_node_complete = next(
            e.seq for e in rec.events if e.event_type == EVENT_NODE_EXECUTION_COMPLETED
        )
        assert seq_pick < seq_place < seq_node_complete

    def test_phase_4a_belt_source_yields_no_pick_side_commit(self):
        # Phase 4A's PickSource has no fixture_id; ``getattr`` returns
        # None and the pick-side branch is skipped.
        task = _pick_place_task(place_fixture_id="FixtureB")  # pick_fixture_id=None
        result = _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        _session_, _bus, _ex, rec = _session(task=task, result=result)
        _session_.begin(); _session_.step(); _session_.complete()
        # Exactly one FixtureStateChanged (place-side only).
        fsc = [e for e in rec.events if e.event_type == EVENT_FIXTURE_STATE_CHANGED]
        assert len(fsc) == 1
        assert fsc[0].payload["fixture_id"] == "FixtureB"


# ═══════════════════════════════════════════════════════════════════════
class TestExecutorNeverMutatesOccupancy:
    """D-CONT-5a — the executor is observational-only. The fake records
    every method call; we assert no ``mark_fixture_*`` ever appears
    in the call log. (Phase 4A's real TaskExecutor is verified
    separately by Isaac Sim regression.)"""

    def test_fake_executor_call_log_contains_only_observational_methods(self):
        task = _pick_place_task(place_fixture_id="FixtureB")
        result = _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        session, _bus, ex, _rec = _session(task=task, result=result)
        session.begin(); session.step(); session.complete()
        # Allowed methods: prepare / reset / execute / close. Nothing
        # named ``mark_*`` or ``register_*`` is permitted on this surface.
        method_names = {call[0] for call in ex.call_log}
        assert method_names <= {"prepare", "reset", "execute", "close"}
        assert "mark_fixture_occupied" not in method_names
        assert "mark_fixture_empty"    not in method_names


# ═══════════════════════════════════════════════════════════════════════
class TestEventOrderingPhaseG:
    """D-EXEC-2 / D-EXEC-7 — phase-correct event ordering."""

    def test_full_event_sequence_for_passing_pickplace(self):
        task = _pick_place_task(place_fixture_id="FixtureB")
        result = _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        session, _bus, _ex, rec = _session(task=task, result=result)
        session.begin(); session.step(); session.complete()
        kinds = [e.event_type for e in rec.events]
        # Required order (single-node, single place-fixture transition).
        expected = [
            EVENT_SESSION_STARTED,
            EVENT_NODE_SELECTED,
            EVENT_NODE_EXECUTION_STARTED,
            EVENT_FIXTURE_STATE_CHANGED,    # Phase G mutation trace.
            EVENT_NODE_EXECUTION_COMPLETED, # Closing event of the tick.
            EVENT_SESSION_COMPLETED,
        ]
        assert kinds == expected
        # Seq gap-free monotone (D-BUS-3).
        seqs = [e.seq for e in rec.events]
        assert seqs == list(range(len(seqs)))

    def test_failing_node_emits_no_fixture_state_changed(self):
        task = _pick_place_task(place_fixture_id="FixtureB")
        result = _FakeResult(
            passed=False, outcome=_FakeOutcome("GRASP_NEVER_ACQUIRED"),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        session, _bus, _ex, rec = _session(task=task, result=result)
        session.begin(); session.step(); session.complete()
        kinds = [e.event_type for e in rec.events]
        # Session-failed terminal event is emitted; no fixture event.
        assert EVENT_FIXTURE_STATE_CHANGED not in kinds
        assert EVENT_SESSION_FAILED in kinds


# ═══════════════════════════════════════════════════════════════════════
class TestResultFingerprintIncludesPegXyzInitial:
    """D-CONT-1 — peg_xyz_initial is replay-authoritative; enters the
    per-task fingerprint when present on the result."""

    def test_fingerprint_contains_peg_xyz_initial_when_provided(self):
        task = _pick_place_task(place_fixture_id="F")
        result = _FakeResult(
            passed=True, outcome=_FakeOutcome("PASS"),
            peg_xyz_initial=(-0.80, 0.0, 0.701),
            peg_xyz_final=(0.65, 0.0, 0.65),
        )
        session, _bus, _ex, _rec = _session(task=task, result=result)
        session.begin(); snap = session.step()
        fp = snap.nodes["n0"].task_result_fingerprint
        assert '"peg_xyz_initial"' in fp
        assert '"peg_xyz_final"'   in fp

    def test_fingerprint_omits_peg_xyz_initial_when_absent(self):
        # _FakeResult defaults peg_xyz_initial to None; should be
        # absent from the fingerprint (backward-compat with Step 6 fakes).
        task = _pick_place_task(place_fixture_id="F")
        result = _FakeResult(passed=True, outcome=_FakeOutcome("PASS"))
        session, _bus, _ex, _rec = _session(task=task, result=result)
        session.begin(); snap = session.step()
        fp = snap.nodes["n0"].task_result_fingerprint
        assert '"peg_xyz_initial"' not in fp


# ═══════════════════════════════════════════════════════════════════════
class TestTaskResultEvidenceFields:
    """The four Phase-2 evidence fields exist on TaskResult with the
    documented default-None semantics."""

    def test_default_taskresult_has_all_evidence_fields_none(self):
        r = TaskResult(task_id="x", profile_id="nominal", outcome=TaskOutcome.PASS)
        assert r.peg_xyz_initial    is None
        assert r.placement_offset_xy_m is None
        assert r.pick_lift_off_step is None
        assert r.place_landing_step is None

    def test_to_dict_serialises_evidence_fields(self):
        r = TaskResult(
            task_id="x", profile_id="nominal", outcome=TaskOutcome.PASS,
            peg_xyz_initial=(1.0, 2.0, 3.0),
            placement_offset_xy_m=(0.001, -0.002),
            pick_lift_off_step=42,
            place_landing_step=99,
        )
        d = r.to_dict()
        assert d["peg_xyz_initial"]       == [1.0, 2.0, 3.0]
        assert d["placement_offset_xy_m"] == [0.001, -0.002]
        assert d["pick_lift_off_step"]    == 42
        assert d["place_landing_step"]    == 99


# ═══════════════════════════════════════════════════════════════════════
class TestSessionAuthorityWithoutRegistry:
    """A test executor without a ``.registry`` attribute must not
    crash the session. The session's commit logic is forgiving by
    design — commits are skipped when the executor doesn't expose a
    registry (test-fake without registry state). The remaining
    orchestration behaviour is unchanged."""

    def test_session_runs_to_completion_without_registry_on_executor(self):
        # Build the standard Step-6 fake (no .registry attribute).
        class _NoRegistryFake:
            def __init__(self): self.call_log = []
            def prepare(self): self.call_log.append(("prepare",))
            def reset(self, scope=ResetScope.FULL): self.call_log.append(("reset", scope))
            def execute(self, task, **kw):
                self.call_log.append(("execute", task))
                return _FakeResult(passed=True, outcome=_FakeOutcome("PASS"))
            def close(self): self.call_log.append(("close",))

        ex = _NoRegistryFake()
        bus = EventBus()
        rec = InMemoryTraceRecorder()
        bus.register(rec)
        task = _pick_place_task(place_fixture_id="F")
        session = ExecutionSession(
            graph=_single_node_graph(),
            task_executor=ex,
            event_bus=bus,
            task_resolver=lambda _node: task,
        )
        session.begin()
        session.step()
        session.complete()
        # No crash; no FixtureStateChanged (no registry to mutate).
        kinds = [e.event_type for e in rec.events]
        assert EVENT_FIXTURE_STATE_CHANGED not in kinds
