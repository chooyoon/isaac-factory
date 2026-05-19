"""Phase 4B step 1 — deterministic EventBus invariant enforcement.

Proves the minimum-viable set of clauses from the deterministic-semantics
contract [docs/phase_4b_deterministic_semantics.md] for the EventBus
skeleton landed in cell_authoring.orchestration:

  * D-BUS-1   synchronous dispatch
  * D-BUS-3   monotone gap-free seq allocation
  * D-BUS-4   no two events share a seq
  * D-BUS-6   register works only pre-freeze
  * D-BUS-7   post-freeze register raises EventBusFrozenError
  * D-BUS-8   unregister always raises
  * D-BUS-9   registration-order dispatch
  * D-BUS-10  non-reentrant emit
  * D-BUS-11  subscriber-exception capture as SubscriberError; dispatch
              continues to remaining subscribers
  * D-BUS-12  SubscriberError suppresses the originating subscriber

  * D-TRACE-1 in-memory ordering capture
  * D-TRACE-2 trace is append-only

  * D-SCHED-11 no wall-clock fields on the envelope (logical-only)
  * D-SESS-8   envelope is frozen post-construction

Each test class targets one clause family. Each test is pure-Python; no
Isaac Sim, no PhysX, no async, no threads.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Add cell_authoring extension to sys.path (matches Phase 4A pattern).
_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


from cell_authoring.orchestration import (  # noqa: E402
    EventBus,
    EventBusFrozenError,
    EventBusReentryError,
    EventEnvelope,
    InMemoryTraceRecorder,
    SUBSCRIBER_ERROR_EVENT_TYPE,
)


# ───────────────────────────── helpers ─────────────────────────────


class _OrderedRecorder:
    """A subscriber that records the (recorder_name, seq, event_type)
    of every event it observes — for cross-subscriber ordering checks."""

    def __init__(self, name: str, shared_log: list[tuple[str, int, str]]):
        self.name = name
        self.shared_log = shared_log

    def on_event(self, envelope: EventEnvelope) -> None:
        self.shared_log.append((self.name, envelope.seq, envelope.event_type))


class _RaisingSubscriber:
    """A subscriber that raises on event N-th invocation. Used to prove
    D-BUS-11 (exception capture) and D-BUS-12 (suppression on its own
    SubscriberError)."""

    def __init__(self, name: str, raise_on_event_type: str | None = None):
        self.name = name
        self.raise_on_event_type = raise_on_event_type
        self.seen: list[str] = []

    def on_event(self, envelope: EventEnvelope) -> None:
        self.seen.append(envelope.event_type)
        if (
            self.raise_on_event_type is not None
            and envelope.event_type == self.raise_on_event_type
        ):
            raise RuntimeError(f"{self.name} failed on {envelope.event_type}")


class _ReentrantSubscriber:
    """A subscriber that tries to re-enter the bus from inside its own
    callback. Used to prove D-BUS-10 raises EventBusReentryError."""

    def __init__(self, bus: EventBus):
        self.bus = bus
        self.captured_reentry: bool = False

    def on_event(self, envelope: EventEnvelope) -> None:
        try:
            self.bus.emit("ReentrantEmit", {"from_seq": envelope.seq})
        except EventBusReentryError:
            self.captured_reentry = True


# ─────────────────────── D-BUS-3 / D-BUS-4 — seq ───────────────────────


class TestMonotoneGapFreeSequence:
    """D-BUS-3 + D-BUS-4: seq is monotone, gap-free, starts at 0, unique."""

    def test_seq_starts_at_zero_and_increments_by_one(self):
        bus = EventBus()
        bus.freeze()
        e0 = bus.emit("E0")
        e1 = bus.emit("E1")
        e2 = bus.emit("E2")
        assert (e0.seq, e1.seq, e2.seq) == (0, 1, 2)

    def test_next_seq_matches_committed_count(self):
        bus = EventBus()
        bus.freeze()
        for _ in range(10):
            bus.emit("Tick")
        assert bus.next_seq == 10
        assert bus.committed_count == 10

    def test_seqs_unique_across_many_emits(self):
        bus = EventBus()
        bus.freeze()
        recorder = InMemoryTraceRecorder()
        # Can't register post-freeze, so do it in a fresh bus:
        bus2 = EventBus()
        bus2.register(recorder)
        bus2.freeze()
        for i in range(256):
            bus2.emit("Tick", {"i": i})
        seqs = recorder.seqs()
        assert seqs == list(range(256))
        assert len(set(seqs)) == len(seqs)  # D-BUS-4: uniqueness


# ─────────────────── D-BUS-6 / D-BUS-7 / D-BUS-8 — topology ───────────────────


class TestFrozenSubscriberTopology:
    """D-BUS-6, D-BUS-7, D-BUS-8: subscriber topology frozen at begin()."""

    def test_register_works_pre_freeze(self):
        bus = EventBus()
        bus.register(InMemoryTraceRecorder("a"))
        bus.register(InMemoryTraceRecorder("b"))
        assert bus.subscriber_count == 2
        assert bus.is_frozen is False

    def test_register_raises_post_freeze(self):
        bus = EventBus()
        bus.register(InMemoryTraceRecorder("a"))
        bus.freeze()
        assert bus.is_frozen is True
        with pytest.raises(EventBusFrozenError, match="D-BUS-6"):
            bus.register(InMemoryTraceRecorder("late"))
        # subscriber count unchanged
        assert bus.subscriber_count == 1

    def test_unregister_always_raises_even_pre_freeze(self):
        """D-BUS-8: unregistration is forbidden, frozen or not."""
        bus = EventBus()
        recorder = InMemoryTraceRecorder("a")
        bus.register(recorder)
        # Pre-freeze: still must fail.
        with pytest.raises(EventBusFrozenError, match="D-BUS-8"):
            bus.unregister(recorder)
        bus.freeze()
        # Post-freeze: same.
        with pytest.raises(EventBusFrozenError, match="D-BUS-8"):
            bus.unregister(recorder)

    def test_freeze_is_idempotent(self):
        bus = EventBus()
        bus.freeze()
        bus.freeze()
        bus.freeze()
        assert bus.is_frozen is True

    def test_topology_freeze_is_load_bearing_across_emits(self):
        """Repeated emits with N subscribers continue to dispatch to the
        same N subscribers — the topology cannot drift mid-session."""
        bus = EventBus()
        log: list[tuple[str, int, str]] = []
        a = _OrderedRecorder("a", log)
        b = _OrderedRecorder("b", log)
        bus.register(a)
        bus.register(b)
        bus.freeze()
        for i in range(5):
            bus.emit("Tick", {"i": i})
        # Both subscribers saw all 5 events. log has 10 entries.
        assert len(log) == 10
        # Per-event, subscriber a appears before b (D-BUS-9; verified in
        # detail later).
        for k in range(5):
            assert log[2 * k][0] == "a"
            assert log[2 * k + 1][0] == "b"


# ───────────────────────── D-BUS-9 — order ─────────────────────────


class TestRegistrationOrderDispatch:
    """D-BUS-9: subscribers receive events in registration order."""

    def test_dispatch_follows_registration_order(self):
        bus = EventBus()
        log: list[tuple[str, int, str]] = []
        bus.register(_OrderedRecorder("first",  log))
        bus.register(_OrderedRecorder("second", log))
        bus.register(_OrderedRecorder("third",  log))
        bus.freeze()
        bus.emit("OnlyEvent")
        assert [entry[0] for entry in log] == ["first", "second", "third"]

    def test_two_recorders_see_identical_seq_ordering(self):
        """Both subscribers see the same seqs in the same order
        (D-BUS-3 ∩ D-BUS-9). This is the deterministic-trace property."""
        bus = EventBus()
        r1 = InMemoryTraceRecorder("r1")
        r2 = InMemoryTraceRecorder("r2")
        bus.register(r1)
        bus.register(r2)
        bus.freeze()
        for i in range(20):
            bus.emit(f"Event{i}", {"i": i})
        assert r1.seqs() == r2.seqs()
        assert r1.event_types() == r2.event_types()


# ────────────────────── D-BUS-10 — non-reentrant ──────────────────────


class TestNonReentrantEmit:
    """D-BUS-10: subscribers may not call emit() from inside their own
    callback. The attempt raises EventBusReentryError, which the bus's
    own try/except converts into a SubscriberError event."""

    def test_reentry_raises_inside_callback(self):
        bus = EventBus()
        reentrant = _ReentrantSubscriber(bus)
        bus.register(reentrant)
        bus.freeze()
        bus.emit("Trigger")
        # Subscriber's internal try/except caught the EventBusReentryError.
        assert reentrant.captured_reentry is True

    def test_unguarded_reentry_surfaces_as_subscriber_error(self):
        """A subscriber that re-enters without catching the error has
        its exception captured as a SubscriberError event by D-BUS-11."""

        class _UnguardedReentrant:
            def __init__(self, bus):
                self.bus = bus

            def on_event(self, envelope):
                # No try/except — let EventBusReentryError propagate.
                if envelope.event_type != SUBSCRIBER_ERROR_EVENT_TYPE:
                    self.bus.emit("NestedEmit")

        bus = EventBus()
        bus.register(_UnguardedReentrant(bus))
        recorder = InMemoryTraceRecorder()
        bus.register(recorder)
        bus.freeze()
        bus.emit("Trigger")
        # We should have seen: Trigger (seq=0), SubscriberError (seq=1).
        types = recorder.event_types()
        assert types[0] == "Trigger"
        assert SUBSCRIBER_ERROR_EVENT_TYPE in types
        # The recorded SubscriberError seq is monotone-after Trigger:
        seqs = recorder.seqs()
        idx_err = types.index(SUBSCRIBER_ERROR_EVENT_TYPE)
        assert seqs[idx_err] == seqs[0] + 1


# ─────────────── D-BUS-11 / D-BUS-12 — exception capture ───────────────


class TestSubscriberExceptionCapture:
    """D-BUS-11 + D-BUS-12: failed subscribers don't halt dispatch; the
    failure is captured as a SubscriberError; the SubscriberError is
    dispatched to everyone EXCEPT the failing subscriber."""

    def test_dispatch_continues_after_subscriber_raises(self):
        bus = EventBus()
        raiser = _RaisingSubscriber("raiser", raise_on_event_type="Trigger")
        recorder = InMemoryTraceRecorder("after")
        bus.register(raiser)
        bus.register(recorder)
        bus.freeze()
        bus.emit("Trigger")
        # The recorder (registered AFTER the raiser) still saw Trigger
        # (D-BUS-11: dispatch continues).
        assert "Trigger" in recorder.event_types()

    def test_subscriber_error_event_emitted_with_next_seq(self):
        bus = EventBus()
        raiser = _RaisingSubscriber("raiser", raise_on_event_type="BadEvent")
        recorder = InMemoryTraceRecorder("post")
        bus.register(raiser)
        bus.register(recorder)
        bus.freeze()
        bus.emit("BadEvent")
        # Recorder saw BadEvent (seq=0) and SubscriberError (seq=1).
        types = recorder.event_types()
        seqs = recorder.seqs()
        assert types == ["BadEvent", SUBSCRIBER_ERROR_EVENT_TYPE]
        assert seqs == [0, 1]
        # The SubscriberError carries the offending subscriber info.
        err_env = recorder.events[1]
        assert err_env.payload["for_event_seq"] == 0
        assert err_env.payload["for_event_type"] == "BadEvent"
        assert err_env.payload["subscriber_index"] == 0
        assert err_env.payload["subscriber_type"] == "_RaisingSubscriber"
        assert err_env.payload["exception_type"] == "RuntimeError"

    def test_failing_subscriber_does_not_receive_its_own_subscriber_error(self):
        """D-BUS-12: the failing subscriber is suppressed when its own
        SubscriberError is dispatched."""
        bus = EventBus()
        raiser = _RaisingSubscriber("raiser", raise_on_event_type="BadEvent")
        recorder = InMemoryTraceRecorder("post")
        bus.register(raiser)
        bus.register(recorder)
        bus.freeze()
        bus.emit("BadEvent")
        # raiser.seen contains the original event (it raised mid-callback,
        # so seen[-1] is "BadEvent"). It must NOT contain SubscriberError.
        assert "BadEvent" in raiser.seen
        assert SUBSCRIBER_ERROR_EVENT_TYPE not in raiser.seen
        # The post-recorder DID receive the SubscriberError.
        assert SUBSCRIBER_ERROR_EVENT_TYPE in recorder.event_types()

    def test_multiple_failing_subscribers_each_produce_one_error_event(self):
        """If subscribers 0 and 2 both raise on the same event, two
        SubscriberError events are committed in subscriber-index order."""
        bus = EventBus()
        r0 = _RaisingSubscriber("r0", raise_on_event_type="X")
        r1 = InMemoryTraceRecorder("r1")  # benign
        r2 = _RaisingSubscriber("r2", raise_on_event_type="X")
        post = InMemoryTraceRecorder("post")
        bus.register(r0)
        bus.register(r1)
        bus.register(r2)
        bus.register(post)
        bus.freeze()
        bus.emit("X")
        # Two SubscriberErrors were committed, with seqs 1 and 2.
        types = post.event_types()
        seqs = post.seqs()
        assert types[0] == "X" and seqs[0] == 0
        assert types[1] == SUBSCRIBER_ERROR_EVENT_TYPE and seqs[1] == 1
        assert types[2] == SUBSCRIBER_ERROR_EVENT_TYPE and seqs[2] == 2
        # First error blames subscriber 0, second blames subscriber 2.
        assert post.events[1].payload["subscriber_index"] == 0
        assert post.events[2].payload["subscriber_index"] == 2


# ─────────────── D-TRACE-1 / D-TRACE-2 — ordering capture ───────────────


class TestTraceOrderingCapture:
    """D-TRACE-1 (authoritative ordering capture) + D-TRACE-2 (append-only)."""

    def test_recorder_captures_events_in_dispatch_order(self):
        bus = EventBus()
        recorder = InMemoryTraceRecorder()
        bus.register(recorder)
        bus.freeze()
        for label in ["alpha", "beta", "gamma"]:
            bus.emit(label)
        assert recorder.event_types() == ["alpha", "beta", "gamma"]
        assert recorder.seqs() == [0, 1, 2]

    def test_events_view_is_read_only_tuple(self):
        """D-TRACE-2: callers cannot mutate the recorded stream."""
        bus = EventBus()
        recorder = InMemoryTraceRecorder()
        bus.register(recorder)
        bus.freeze()
        bus.emit("A")
        view = recorder.events
        assert isinstance(view, tuple)
        with pytest.raises(AttributeError):
            view.append("not-allowed")  # type: ignore[attr-defined]

    def test_replay_two_buses_with_same_input_produce_identical_traces(self):
        """Same event stream → identical ordering. The step-1 ordering
        proof: deterministic semantics under the contract."""

        def run(bus: EventBus, recorder: InMemoryTraceRecorder) -> None:
            bus.register(recorder)
            bus.freeze()
            bus.emit("JobStarted")
            bus.emit("TaskScheduled", {"node_id": "n0"})
            bus.emit("TaskStarted",   {"node_id": "n0"})
            bus.emit("TaskCompleted", {"node_id": "n0"})
            bus.emit("JobCompleted")

        bus_a = EventBus()
        rec_a = InMemoryTraceRecorder("a")
        run(bus_a, rec_a)

        bus_b = EventBus()
        rec_b = InMemoryTraceRecorder("b")
        run(bus_b, rec_b)

        # Bit-equal sequence of (seq, event_type, node_id, orchestration_tick,
        # physx_frame, payload).
        def fingerprint(env: EventEnvelope) -> tuple:
            return (
                env.seq, env.event_type, env.node_id,
                env.orchestration_tick, env.physx_frame,
                dict(env.payload),  # MappingProxyType → comparable dict
            )

        assert [fingerprint(e) for e in rec_a.events] == \
               [fingerprint(e) for e in rec_b.events]


# ───────────────── D-SCHED-11 / D-SESS-8 — envelope shape ─────────────────


class TestEnvelopeShapeAndFreeze:
    """D-SCHED-11: no wall-clock; D-SESS-8: frozen dataclass."""

    def test_envelope_has_no_wallclock_field(self):
        bus = EventBus()
        bus.freeze()
        env = bus.emit("X")
        # The envelope exposes logical_time as a reserved placeholder,
        # always None in step 1.
        assert env.logical_time is None
        # The envelope has no wall_ns / wall_time / timestamp attribute.
        for forbidden in ("wall_ns", "wall_time", "timestamp", "utc", "monotonic"):
            assert not hasattr(env, forbidden), \
                f"envelope must not carry {forbidden!r} (D-SCHED-11)"

    def test_envelope_is_frozen(self):
        """D-SESS-8: frozen dataclass; mutation raises."""
        bus = EventBus()
        bus.freeze()
        env = bus.emit("X")
        with pytest.raises(Exception):  # FrozenInstanceError on Py 3.12
            env.seq = 99  # type: ignore[misc]

    def test_payload_view_is_read_only(self):
        """Payload is wrapped in MappingProxyType — subscribers can't
        mutate it and accidentally change what later subscribers see."""
        bus = EventBus()
        bus.freeze()
        env = bus.emit("X", {"k": "v"})
        with pytest.raises(TypeError):
            env.payload["k"] = "tampered"  # type: ignore[index]


# ───────────────────────── D-BUS-1 — sync ─────────────────────────


class TestSynchronousDispatch:
    """D-BUS-1: emit() returns only after every subscriber has been
    dispatched (or recorded as failed)."""

    def test_emit_returns_after_all_subscribers_invoked(self):
        bus = EventBus()
        invocation_marks: list[str] = []

        class _Marker:
            def __init__(self, name):
                self.name = name

            def on_event(self, env):
                invocation_marks.append(self.name)

        bus.register(_Marker("first"))
        bus.register(_Marker("second"))
        bus.register(_Marker("third"))
        bus.freeze()

        # Pre-emit: nothing has fired.
        assert invocation_marks == []
        bus.emit("Sync")
        # Immediately after emit() returns: all three have fired,
        # in registration order.
        assert invocation_marks == ["first", "second", "third"]


# ────────── meta: count of clauses covered (signal, not assertion) ──────────


def test_step1_covers_minimum_clause_family_set():
    """Documents which contract clauses this test file enforces. This is
    not an assertion of contract conformance — it is a signal to reviewers
    about the scope of step 1. Adding new clause coverage to step N
    should update this test (or a successor file)."""
    covered_clauses = {
        "D-BUS-1",  "D-BUS-3",  "D-BUS-4",
        "D-BUS-6",  "D-BUS-7",  "D-BUS-8",  "D-BUS-9",
        "D-BUS-10", "D-BUS-11", "D-BUS-12",
        "D-TRACE-1", "D-TRACE-2",
        "D-SCHED-11", "D-SESS-8",
    }
    # Step-1 minimum coverage: at least 14 distinct clauses.
    assert len(covered_clauses) >= 14
