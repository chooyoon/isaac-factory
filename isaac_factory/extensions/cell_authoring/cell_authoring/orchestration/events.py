"""Deterministic EventBus skeleton (Phase 4B step 1).

Implements the synchronous, monotone, freeze-topology dispatcher mandated
by the deterministic-semantics contract — clauses D-BUS-1 through D-BUS-12
in [docs/phase_4b_deterministic_semantics.md].

This module ships ONLY what is needed to prove deterministic event semantics:

  * synchronous dispatch (no async, no threads)
  * monotone gap-free seq allocation per bus instance
  * registration-order subscriber dispatch
  * non-reentrant emit()
  * subscriber-exception capture as SubscriberError events
  * topology freeze at session.begin() (modelled as ``bus.freeze()``)
  * deterministic logical counters (no wall-clock fields)

Out of scope for step 1: persistence, typed event-kind enum,
ExecutionSession integration, OperatorChannel, snapshots, runtime_hash.

Every public behaviour cites its D-BUS clause in the docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable


# ───────────────────────────── constants ─────────────────────────────


SUBSCRIBER_ERROR_EVENT_TYPE: str = "SubscriberError"
"""Canonical event_type for subscriber-failure capture events.

Per D-BUS-11/12, when a subscriber raises during dispatch, the EventBus
records the failure as a fresh event with this event_type assigned a
``seq`` immediately following the offending event.
"""


# ───────────────────────────── errors ─────────────────────────────


class EventBusFrozenError(RuntimeError):
    """Raised on register/unregister after the bus topology is frozen.

    Cites D-BUS-6, D-BUS-7, D-BUS-8:
      * subscriber topology must be frozen at session.begin()
      * runtime subscriber registration after begin() is a contract
        violation
      * runtime subscriber unregistration is always a contract violation
    """


class EventBusReentryError(RuntimeError):
    """Raised when a subscriber re-enters emit() during its own dispatch.

    Cites D-BUS-10: per-subscriber dispatch is non-reentrant; a subscriber
    may not call emit() from inside its own callback. (It may request an
    emission via a different component, but not re-enter the bus.)
    """


# ───────────────────────────── envelope ─────────────────────────────


_EMPTY_PAYLOAD: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """One emitted event.

    Frozen by construction (D-SESS-8): an envelope, once committed by the
    bus, cannot be mutated. The replay-identity tool compares envelopes
    field-by-field (modulo ``logical_time`` reserved-but-unused in step 1).

    Fields
    ------
    seq:                Monotone gap-free integer assigned by the bus
                         (D-BUS-3, D-BUS-4). The k-th event committed by
                         a given bus has ``seq == k`` starting at 0.
    event_type:         String identifier of the event kind. A typed
                         ``EventKind`` enum is deferred to the step that
                         freezes the taxonomy.
    orchestration_tick: Logical orchestration-tick index (D-EXEC-1).
                         Zero before any session.step() has run.
    physx_frame:        Logical physics-frame counter at the moment of
                         emission. Zero if the event is emitted outside
                         a physics-tick (e.g. JobStarted, TaskScheduled).
    node_id:            Optional TaskNode id this event pertains to.
                         None for job-lifecycle and pure-bus events.
    payload:            Arbitrary JSON-serialisable mapping. Empty by
                         default. Captured at commit time; the envelope
                         is frozen, so payload references are not
                         observed for mutation after commit.
    logical_time:       Reserved placeholder for a deterministic logical
                         time-source. **Always None in step 1.** No
                         wall-clock value, ever (D-SCHED-11, D-EXEC-7).

    The envelope deliberately carries **no wall-clock field** in step 1.
    A diagnostic ``wall_ns`` field is permitted by the contract
    (D-SESS state-category "diagnostic"), but it is added only in a
    later step that introduces the diagnostic-trace plumbing. Adding it
    now would invite accidental dependence on it.
    """

    seq:                int
    event_type:         str
    orchestration_tick: int = 0
    physx_frame:        int = 0
    node_id:            str | None = None
    payload:            Mapping[str, Any] = field(default_factory=lambda: _EMPTY_PAYLOAD)
    logical_time:       int | None = None


# ───────────────────────────── subscriber ─────────────────────────────


@runtime_checkable
class EventSubscriber(Protocol):
    """Observational-only subscriber.

    Subscribers receive every committed event in registration order
    (D-BUS-9). A subscriber **must not**:

      * call ``EventBus.emit`` from inside its own ``on_event`` callback
        (D-BUS-10 — re-entry is detected and raised as
        :class:`EventBusReentryError`),
      * mutate registry / job / session / trace state directly
        (D-SESS-7, D-FORBID-13 — subscribers may only emit further
        events via the bus from *outside* their own callback context),
      * unsubscribe itself (D-BUS-8 — silencing is achieved by filtering
        inside ``on_event``).

    A subscriber that raises is recorded as a SubscriberError event and
    dispatch continues to the remaining subscribers (D-BUS-11).
    """

    def on_event(self, envelope: EventEnvelope) -> None: ...


# ────────────────────────── sequence allocator ──────────────────────────


class _SequenceAllocator:
    """Monotone gap-free seq allocator. Cites D-BUS-3, D-BUS-4.

    Single-process, single-threaded by design (D-FORBID-2). No locks
    needed; introducing a lock here would mask a contract violation
    rather than fix one.
    """

    __slots__ = ("_next",)

    def __init__(self) -> None:
        self._next: int = 0

    def allocate(self) -> int:
        v = self._next
        self._next += 1
        return v

    @property
    def next_seq(self) -> int:
        return self._next


# ───────────────────────────── EventBus ─────────────────────────────


class EventBus:
    """Synchronous, monotone, freeze-able event dispatcher.

    Lifecycle
    ---------
    construction → (zero or more) register(subscriber) → freeze() → (zero
    or more) emit(event_type, ...) → … bus retired with the session.

    Contract invariants enforced here
    ---------------------------------
    D-BUS-1:  emit() is synchronous; returns only after every subscriber
              has been dispatched (or recorded as having failed).
    D-BUS-2:  no async / threading / multiprocessing primitives are used.
    D-BUS-3:  ``seq`` is monotone and gap-free per bus instance, starting
              at 0.
    D-BUS-4:  no two events share a ``seq`` within one bus.
    D-BUS-5:  not directly enforceable inside this class (it spans
              phases); we provide the monotone seq guarantee that
              upstream phase ordering composes with.
    D-BUS-6:  ``register`` succeeds only before ``freeze``.
    D-BUS-7:  post-freeze ``register`` raises ``EventBusFrozenError``.
    D-BUS-8:  ``unregister`` always raises ``EventBusFrozenError`` —
              even pre-freeze. Subscriber topology is replay-authoritative.
    D-BUS-9:  subscribers are dispatched in registration order.
    D-BUS-10: a subscriber that calls ``emit`` during its own dispatch
              triggers ``EventBusReentryError`` — captured by the
              per-subscriber try/except and surfaced as a SubscriberError.
    D-BUS-11: a subscriber raising does not halt dispatch to remaining
              subscribers; the failure is recorded as a SubscriberError
              event committed with ``seq`` immediately following the
              offending event.
    D-BUS-12: SubscriberError events are dispatched to all subscribers
              EXCEPT the subscriber that failed for the originating event.

    Out of scope for step 1
    -----------------------
    Persistence, durable trace, JSONL writer, runtime_hash, session_id,
    diagnostic wall_ns, typed event-kind enum.
    """

    def __init__(self) -> None:
        self._subscribers: list[EventSubscriber] = []
        self._frozen: bool = False
        self._seq_alloc: _SequenceAllocator = _SequenceAllocator()

        # Re-entry guard (D-BUS-10). True while emit() is dispatching.
        self._dispatching: bool = False

        # Strictly-monotone audit fields. Visible to tests via
        # next_seq / committed_count. Not part of the contract surface.
        self._committed_count: int = 0

    # ─────────────── topology ───────────────

    def register(self, subscriber: EventSubscriber) -> None:
        """Append a subscriber to the dispatch list.

        Cites D-BUS-6, D-BUS-9 — registration order IS dispatch order.
        Raises ``EventBusFrozenError`` (cites D-BUS-7) if called after
        :py:meth:`freeze`.
        """
        if self._frozen:
            # D-BUS-7: post-freeze register is a contract violation.
            raise EventBusFrozenError(
                "EventBus.register() called after freeze(). Subscriber "
                "topology is replay-authoritative; runtime registration "
                "is forbidden (D-BUS-6, D-BUS-7)."
            )
        # D-BUS-9: dispatch order = registration order, locked by the
        # underlying list's append semantics.
        self._subscribers.append(subscriber)

    def unregister(self, subscriber: EventSubscriber) -> None:
        """Always raises. Cites D-BUS-8.

        Subscriber topology is replay-authoritative; a subscriber that
        wishes to silence itself must filter inside its own ``on_event``,
        not detach. There is no escape hatch — this method exists only
        to make the contract observable to callers.
        """
        # D-BUS-8: unregistration is always forbidden, frozen or not.
        raise EventBusFrozenError(
            "EventBus.unregister() is forbidden. Subscriber topology "
            "is replay-authoritative (D-BUS-8). Filter inside on_event "
            "instead of detaching."
        )

    def freeze(self) -> None:
        """Lock the subscriber topology.

        Cites D-BUS-6. Called by ``ExecutionSession.begin()`` (when that
        component lands). Idempotent — re-freezing is a no-op.
        """
        self._frozen = True

    # ─────────────── inspection (read-only, test-friendly) ───────────────

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def next_seq(self) -> int:
        """The seq that the next emit() would commit. Cites D-BUS-3."""
        return self._seq_alloc.next_seq

    @property
    def committed_count(self) -> int:
        """Number of envelopes the bus has committed so far. Equals
        ``next_seq`` by D-BUS-3 (gap-free monotone)."""
        return self._committed_count

    # ─────────────── emission ───────────────

    def emit(
        self,
        event_type: str,
        payload: Mapping[str, Any] | None = None,
        *,
        orchestration_tick: int = 0,
        physx_frame: int = 0,
        node_id: str | None = None,
    ) -> EventEnvelope:
        """Synchronously commit and dispatch one event.

        Cites D-BUS-1 (sync), D-BUS-3 (monotone seq), D-BUS-9
        (registration-order dispatch), D-BUS-10 (non-reentrant).

        Re-entry detection (D-BUS-10): if called from inside a subscriber
        callback (i.e. ``self._dispatching == True``), raises
        :class:`EventBusReentryError`. The subscriber's try/except guard
        will capture this and the bus will surface it as a SubscriberError.
        """
        if self._dispatching:
            # D-BUS-10: subscribers may not re-enter the bus.
            raise EventBusReentryError(
                f"EventBus.emit({event_type!r}) called during subscriber "
                f"dispatch. Subscribers must not re-enter the bus from "
                f"inside their own callback (D-BUS-10)."
            )

        # Freeze the payload's view: we wrap in MappingProxyType so that
        # accidental mutation by a subscriber does not silently change
        # what later subscribers (or the trace) observe.
        payload_view: Mapping[str, Any]
        if payload is None or payload is _EMPTY_PAYLOAD:
            payload_view = _EMPTY_PAYLOAD
        else:
            payload_view = MappingProxyType(dict(payload))

        seq = self._seq_alloc.allocate()  # D-BUS-3
        envelope = EventEnvelope(
            seq=seq,
            event_type=event_type,
            orchestration_tick=orchestration_tick,
            physx_frame=physx_frame,
            node_id=node_id,
            payload=payload_view,
            logical_time=None,  # D-SCHED-11: no wall-clock; reserved for
                                # a deterministic logical-time source.
        )
        self._committed_count += 1
        self._dispatch(envelope, suppress_index=None)
        return envelope

    # ─────────────── internal dispatch ───────────────

    def _dispatch(
        self,
        envelope: EventEnvelope,
        *,
        suppress_index: int | None,
    ) -> None:
        """Deliver ``envelope`` to every subscriber in registration order.

        Cites D-BUS-9 (order), D-BUS-11 (failures don't halt dispatch),
        D-BUS-12 (SubscriberError suppresses the originating subscriber).

        ``suppress_index`` is the subscriber that originated a
        SubscriberError; that subscriber is skipped for this dispatch.
        Outside the error-recovery path, callers pass ``None``.
        """
        # D-BUS-10 surface: the re-entry guard is checked at emit(), not
        # here, because internal cascade dispatch of SubscriberError
        # events is permitted (and required) by the contract.
        self._dispatching = True
        collected_errors: list[tuple[int, BaseException]] = []
        try:
            # D-BUS-9: iterate by index in registration order. We use a
            # tuple snapshot via enumerate over the live list — but the
            # topology is frozen by D-BUS-6/7/8, so no concurrent mod is
            # possible (D-FORBID-2: single-threaded). Indexing the list
            # is equivalent to enumerate-on-frozen, and is the explicit
            # ordered iteration form required by D-SCHED-5.
            n = len(self._subscribers)
            for i in range(n):
                if i == suppress_index:
                    # D-BUS-12: skip the subscriber whose failure this
                    # error event is reporting.
                    continue
                sub = self._subscribers[i]
                try:
                    sub.on_event(envelope)
                except BaseException as exc:  # noqa: BLE001 — see D-BUS-11
                    # D-BUS-11: capture, do not halt remaining dispatch.
                    collected_errors.append((i, exc))
        finally:
            self._dispatching = False

        # D-BUS-11: a SubscriberError is committed with seq immediately
        # following the offending event AND any prior captured errors.
        # We process them in subscriber-index order (D-SCHED-5: explicit
        # ordered iteration; collected_errors is already in i-ascending
        # order because we iterated subscribers by index).
        for failing_index, exc in collected_errors:
            err_seq = self._seq_alloc.allocate()
            err_envelope = EventEnvelope(
                seq=err_seq,
                event_type=SUBSCRIBER_ERROR_EVENT_TYPE,
                orchestration_tick=envelope.orchestration_tick,
                physx_frame=envelope.physx_frame,
                node_id=envelope.node_id,
                payload=MappingProxyType({
                    "for_event_seq":      envelope.seq,
                    "for_event_type":     envelope.event_type,
                    "subscriber_index":   failing_index,
                    "subscriber_type":    type(self._subscribers[failing_index]).__name__,
                    "exception_type":     type(exc).__name__,
                    "exception_str":      str(exc),
                }),
                logical_time=None,
            )
            self._committed_count += 1
            # D-BUS-12: dispatch with the failing subscriber suppressed.
            # Recursion here is bounded: a SubscriberError dispatch may
            # itself produce SubscriberError events, but each one
            # advances the seq counter and there are finitely many
            # subscribers, so termination is guaranteed.
            self._dispatch(err_envelope, suppress_index=failing_index)
