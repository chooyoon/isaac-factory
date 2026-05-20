"""Operator command envelopes — D-FAULT-9 / D-FAULT-9a.

Phase 4B Step 9 Phase 5 (runtime wiring): deterministic operator-command
envelope schema. Step 9 supports only ``kind="abort"``; Step 11 will
extend the schema to include ``pause`` / ``resume`` / ``manual_advance``
without breaking the on-disk fingerprint of existing envelopes.

Envelopes are pre-queued at :class:`ExecutionSession` construction via
``pending_operator_envelopes=...``. Phase A of every orchestration tick
drains them in canonical (replay-stable) order. Live channel ingress
(Step 11) MUST reuse this schema and the same canonical-ordering
discipline.

References:
    D-FAULT-9 — envelope schema + canonical ordering.
    D-FAULT-9a — Step 9 supports only ``kind="abort"``.
    D-FAULT-6 — abort ingress occurs only at Phase A.
    D-FAULT-14 — every failure transition is one append-only event.
    D-FAULT-15 #16 — ``ExecutionSession.request_abort()`` (method-as-
                     ingress) is FORBIDDEN; envelope-as-event is the
                     sole ingress.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


# Step-9 permitted ``OperatorEnvelope.kind`` values (D-FAULT-9a).
# Step 11 will extend this set; do not remove members.
_PERMITTED_KINDS_STEP_9: frozenset[str] = frozenset({"abort"})


class OperatorEnvelopeError(ValueError):
    """Raised on schema or kind violations of an :class:`OperatorEnvelope`.

    Cites D-FAULT-9, D-FAULT-9a.
    """


@dataclass(frozen=True, slots=True)
class OperatorEnvelope:
    """Frozen operator command envelope (D-FAULT-9).

    The envelope is the **sole** ingress for operator intervention into
    orchestration. Method-as-ingress (``request_abort``, ``force_abort``,
    etc.) is FORBIDDEN per D-FAULT-15 #16.

    Fields
    ------
    kind:
        One of the Step-9 permitted kinds (currently ``"abort"`` only).
        Step 11 extends.
    requested_at_tick:
        Earliest orchestration_tick at which Phase A drains this
        envelope. Allows pre-queued envelopes to fire at a specific
        tick boundary for replay-stable test scenarios.
    reason:
        Operator-supplied short string. Participates in the envelope
        fingerprint via :func:`derive_envelope_id`.
    envelope_id:
        Deterministic UUID-equivalent. Identical content
        ``(kind, requested_at_tick, reason)`` produces identical
        ``envelope_id`` via blake2b digest — replay-stable, no UUID4,
        no wall-clock, no randomness. Forbidden id sources are
        enforced by Phase 4 test
        ``TestForbiddenPatterns.test_canonical_envelope_id_is_deterministic_text``.
    """

    kind:              str
    requested_at_tick: int
    reason:            str
    envelope_id:       str

    def __post_init__(self) -> None:
        if self.kind not in _PERMITTED_KINDS_STEP_9:
            raise OperatorEnvelopeError(
                f"OperatorEnvelope.kind={self.kind!r} is not permitted in Step 9; "
                f"expected one of {sorted(_PERMITTED_KINDS_STEP_9)}. Cites D-FAULT-9a."
            )
        if not isinstance(self.requested_at_tick, int) or isinstance(
            self.requested_at_tick, bool
        ):
            raise OperatorEnvelopeError(
                "OperatorEnvelope.requested_at_tick must be a non-bool int"
            )
        if self.requested_at_tick < 0:
            raise OperatorEnvelopeError(
                f"OperatorEnvelope.requested_at_tick must be >= 0; "
                f"got {self.requested_at_tick}"
            )
        if not isinstance(self.reason, str):
            raise OperatorEnvelopeError("OperatorEnvelope.reason must be str")
        if not isinstance(self.envelope_id, str) or not self.envelope_id:
            raise OperatorEnvelopeError(
                "OperatorEnvelope.envelope_id must be a non-empty str"
            )


def derive_envelope_id(*, kind: str, requested_at_tick: int, reason: str) -> str:
    """Derive a deterministic envelope_id from envelope content (D-FAULT-9).

    Uses blake2b (16-byte hex digest) of the canonicalized tuple. Identical
    content produces identical id — replay-stable. No wall-clock, no
    ``uuid``, no ``random``, no ``os.urandom``.
    """
    h = hashlib.blake2b(digest_size=16)
    h.update(b"OperatorEnvelope/v1\n")
    h.update(kind.encode("utf-8"))
    h.update(b"\n")
    h.update(str(int(requested_at_tick)).encode("ascii"))
    h.update(b"\n")
    h.update(reason.encode("utf-8"))
    return h.hexdigest()


def canonical_envelope_order(
    envelopes: tuple[OperatorEnvelope, ...],
) -> tuple[OperatorEnvelope, ...]:
    """Sort envelopes by ``(requested_at_tick, envelope_id)`` (D-FAULT-9).

    Stable; identical inputs in any permutation produce identical output.
    """
    return tuple(
        sorted(envelopes, key=lambda e: (e.requested_at_tick, e.envelope_id))
    )


def normalize_pending_envelopes(
    envelopes: tuple[OperatorEnvelope, ...] | None,
) -> tuple[OperatorEnvelope, ...]:
    """Validate + canonical-order envelopes provided to ExecutionSession.

    Accepts ``None`` (treated as empty) or a tuple of
    :class:`OperatorEnvelope`. Raises :class:`OperatorEnvelopeError` on
    any non-envelope element. Returned tuple is canonically sorted.
    """
    if envelopes is None:
        return ()
    if not isinstance(envelopes, tuple):
        raise OperatorEnvelopeError(
            f"pending_operator_envelopes must be a tuple; got "
            f"{type(envelopes).__name__}"
        )
    for i, e in enumerate(envelopes):
        if not isinstance(e, OperatorEnvelope):
            raise OperatorEnvelopeError(
                f"pending_operator_envelopes[{i}] is not an OperatorEnvelope"
            )
    return canonical_envelope_order(envelopes)


__all__ = (
    "OperatorEnvelope",
    "OperatorEnvelopeError",
    "canonical_envelope_order",
    "derive_envelope_id",
    "normalize_pending_envelopes",
)
