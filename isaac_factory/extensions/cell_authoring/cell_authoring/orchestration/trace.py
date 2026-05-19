"""Trace recorders (Phase 4B step 1 + step 2).

Two recorder forms live here, both implementing the
:class:`~cell_authoring.orchestration.events.EventSubscriber` Protocol:

  * :class:`InMemoryTraceRecorder` — step 1; appends to an in-memory list.
    Used by step-1 ordering proofs and by tests that don't need durable
    persistence. Lifecycle is bus-attached; no finalize boundary.

  * :class:`DurableTraceRecorder` — step 2; writes a canonical
    ``events.jsonl`` and a ``manifest.json`` to a SessionPackage
    directory on disk. Has an explicit append lifecycle per event and
    an explicit finalize boundary per session.

Step 2 contract clauses honoured by :class:`DurableTraceRecorder`:

  D-TRACE-2  — append-only; once an event is committed it is not
               edited, reordered, or deleted.
  D-TRACE-3  — partial traces are preserved as-is on failure; no
               retroactive regeneration path exists.
  D-TRACE-6  — each line carries a ``seq`` so a corrupt prefix is
               detectable by :py:func:`package.verify_package_integrity`.
  D-TRACE-7  — integrity is verifiable at close; finalize() writes
               the manifest with the committed count.
  D-TRACE-8  — manifest schema is fixed by :class:`package.Manifest`.

Out of scope for step 2 (deliberate; see package.py docstring for the
full deferred list):

  * crash recovery,
  * compression / WAL / sqlite / external persistence,
  * async I/O,
  * background flush workers,
  * deep payload normalization,
  * non-None ``trace_hash`` / ``runtime_hash`` / ``session_identity``,
  * replay execution engine.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import IO, Sequence

from .events import EventEnvelope
from .package import (
    Manifest,
    PACKAGE_VERSION,
    INVARIANT_CONTRACT_VERSION,
    SessionPackage,
    serialize_envelope,
    serialize_manifest,
)


# ════════════════════════════════════════════════════════════════════
# Step 1 — InMemoryTraceRecorder (unchanged from step 1, kept here as
# the canonical step-1 ordering-proof subscriber).
# ════════════════════════════════════════════════════════════════════


class InMemoryTraceRecorder:
    """Observational EventSubscriber that records dispatch order.

    Provides the minimal surface required by the step-1 ordering tests:

      * :py:meth:`on_event` (EventSubscriber Protocol) — appends the
        envelope to an internal append-only list.
      * :py:attr:`events` — read-only tuple view.
      * :py:meth:`seqs` — convenience: list of ``seq`` values in order.
      * :py:meth:`event_types` — convenience: list of ``event_type``s.

    Contract notes
    --------------
    * Append-only (D-TRACE-2). No remove / edit method.
    * Read-only externally — :py:attr:`events` returns a tuple, so
      callers cannot mutate the internal list.
    * No persistence — use :class:`DurableTraceRecorder` for that.
    * Never re-enters the bus (D-BUS-10, D-FORBID-13).
    """

    __slots__ = ("name", "_events")

    def __init__(self, name: str = "trace") -> None:
        self.name: str = name
        self._events: list[EventEnvelope] = []

    def on_event(self, envelope: EventEnvelope) -> None:
        """Cites D-TRACE-1 (ordering capture) + D-TRACE-2 (append-only)."""
        self._events.append(envelope)

    @property
    def events(self) -> Sequence[EventEnvelope]:
        return tuple(self._events)

    def seqs(self) -> list[int]:
        return [e.seq for e in self._events]

    def event_types(self) -> list[str]:
        return [e.event_type for e in self._events]

    def __len__(self) -> int:
        return len(self._events)


# ════════════════════════════════════════════════════════════════════
# Step 2 — DurableTraceRecorder
# ════════════════════════════════════════════════════════════════════


class TraceRecorderFinalizedError(RuntimeError):
    """Raised on operations that are forbidden post-finalize.

    Cites D-TRACE-2: finalized traces are immutable. Re-finalize, or
    on_event after finalize, are contract violations.
    """


class TraceRecorderNotEmptyError(RuntimeError):
    """Raised when a DurableTraceRecorder is asked to write into a
    directory that already contains a package.

    Cites D-TRACE-2: an existing events.jsonl or manifest.json could
    be authoritative for a prior session; overwriting it would violate
    the append-only / no-retroactive-mutation property.
    """


class DurableTraceRecorder:
    """Append-only durable trace; writes ``events.jsonl`` + ``manifest.json``.

    Per-event append lifecycle (one ``on_event`` call)::

        append_requested  → an on_event(envelope) call entered
              │
              ▼
        serialized        → envelope encoded via package.serialize_envelope
              │
              ▼
        flushed           → bytes written to OS + flush() + fsync()
              │
              ▼
        committed         → committed_count incremented; envelope is
                            now durably authoritative

    Only after the fsync returns does the recorder consider the
    envelope durably authoritative (D-TRACE-2). Failure modes:

      * **Serialization failure**: ``json.dumps`` raises. The envelope
        is **not** committed; no bytes have been written; the
        underlying file is unchanged. The exception propagates to the
        EventBus, which captures it as a ``SubscriberError`` event
        per D-BUS-11. The bus's monotone seq continues — the failed
        envelope still consumed a seq, so the next emit() gets seq+1.
        The on-disk file therefore has a permanent gap at that seq;
        :py:func:`verify_package_integrity` will surface this gap.
      * **Flush failure** (disk full, fd closed): write/flush/fsync
        raises. Bytes may have been partially written. The committed
        counter is **not** advanced. The recorder is left in a
        consistent-but-failed state; finalize() will write a manifest
        whose ``event_count`` reflects the last fully-committed event.
        Partial bytes on disk are preserved per D-TRACE-3.

    Per-session lifecycle::

        __init__   → fresh package directory ready, events file open
                     for append
              │
              ▼
        recording  → 0..N on_event() calls; each commits one line
              │
              ▼
        finalize() → manifest.json written with event_count; events
                     file closed; recorder marked finalized
              │
              ▼
        finalized  → all further on_event() / finalize() calls raise
                     TraceRecorderFinalizedError

    Finalize is **strict-once** (D-TRACE-2): a finalized package is
    immutable; calling finalize again is an error, not a no-op.

    Out of scope for step 2:
      * crash recovery — partial events.jsonl is preserved as-is,
      * compression / external backends,
      * async write / background flush worker,
      * subscriber-mediated event filtering,
      * ``trace_hash`` / ``runtime_hash`` / ``session_identity`` content
        (kept as ``None`` placeholders — see package.Manifest).
    """

    def __init__(
        self,
        package: SessionPackage,
        *,
        runtime_hash: str | None = None,
        session_identity: str | None = None,
        allow_existing_dir: bool = True,
    ) -> None:
        """Open a fresh durable trace into ``package``.

        Parameters
        ----------
        package:
            The on-disk layout target. Must NOT already contain
            ``events.jsonl`` or ``manifest.json`` — those would belong
            to a prior authoritative session (D-TRACE-2). The directory
            itself may exist (controlled by ``allow_existing_dir``).
        runtime_hash:
            Placeholder for the eventual runtime fingerprint
            (see package.Manifest). Step 2 stores it as-is in the
            manifest; computing real values is a later-step concern.
        session_identity:
            Placeholder for the session_id + subscriber descriptors.
            Step 2 stores as-is; real value lands with the session
            layer.
        allow_existing_dir:
            If True (default), an existing empty directory is reused.
            If False, the directory must not exist; this is the strict
            mode for callers who want a guaranteed-fresh package.

        Raises
        ------
        TraceRecorderNotEmptyError:
            If ``events.jsonl`` or ``manifest.json`` already exists
            inside ``package.path``.
        FileExistsError:
            If ``allow_existing_dir=False`` and the directory exists.
        """
        self.package: SessionPackage = package
        self._runtime_hash: str | None = runtime_hash
        self._session_identity: str | None = session_identity

        target = package.path
        if target.exists():
            if not allow_existing_dir:
                raise FileExistsError(
                    f"package directory already exists: {target}"
                )
            # Refuse if a prior package's authoritative files are present.
            if package.events_path.exists() or package.manifest_path.exists():
                raise TraceRecorderNotEmptyError(
                    f"refusing to overwrite existing package at {target}: "
                    f"events.jsonl or manifest.json already present "
                    f"(D-TRACE-2 append-only)"
                )
        else:
            target.mkdir(parents=True, exist_ok=False)

        # Open events.jsonl for write (truncate). We refused above if
        # the file already existed, so this cannot clobber prior data.
        # Buffering is line-buffered (buffering=1) so newline-terminated
        # writes hit the OS quickly; we follow each write with flush +
        # fsync regardless.
        self._events_file: IO[str] = open(
            package.events_path,
            mode="w",
            encoding="utf-8",
            newline="\n",       # canonical LF only
            buffering=1,        # line-buffered
        )
        self._committed_count: int = 0
        self._finalized: bool = False

    # ────────── EventSubscriber Protocol ──────────

    def on_event(self, envelope: EventEnvelope) -> None:
        """Append one envelope to ``events.jsonl``.

        Executes the four-phase append lifecycle documented in the
        class docstring. Cites D-TRACE-2 (append-only) and D-TRACE-3
        (no retroactive mutation). On exception, no partial commit is
        recorded — the committed_count is only advanced after a
        successful fsync.
        """
        # Phase: append_requested
        if self._finalized:
            raise TraceRecorderFinalizedError(
                "DurableTraceRecorder.on_event() called after finalize() "
                "(D-TRACE-2 — finalized trace is immutable)"
            )

        # Phase: serialized — canonical JSON encoding (no trailing newline)
        line = serialize_envelope(envelope)

        # Phase: flushed — write + flush + fsync
        # Note: we write line + "\n" explicitly to avoid any platform
        # newline translation. The file was opened with newline="\n",
        # which already disables translation; the explicit "\n" makes
        # the contract self-documenting.
        self._events_file.write(line + "\n")
        self._events_file.flush()
        os.fsync(self._events_file.fileno())

        # Phase: committed — durably authoritative AFTER fsync returns
        self._committed_count += 1

    # ────────── session finalize ──────────

    def finalize(self) -> Manifest:
        """Close ``events.jsonl`` and write ``manifest.json``.

        Strict-once (D-TRACE-2): a second call raises
        :class:`TraceRecorderFinalizedError`. There is no "re-open" or
        "amend" path — partial / failed packages are preserved as-is
        per D-TRACE-3.

        Returns
        -------
        Manifest
            The manifest that was written to disk. Useful for callers
            that want to assert on ``event_count`` immediately.
        """
        if self._finalized:
            raise TraceRecorderFinalizedError(
                "DurableTraceRecorder.finalize() called twice "
                "(D-TRACE-2 — finalized trace is immutable)"
            )

        # Close the events file BEFORE writing the manifest so the
        # events.jsonl file is on disk and complete when the manifest
        # is written. (Even if writing the manifest fails, the
        # events.jsonl file is already durable, so an integrity check
        # can still detect the missing-manifest condition.)
        try:
            self._events_file.flush()
            os.fsync(self._events_file.fileno())
        finally:
            self._events_file.close()

        manifest = Manifest(
            package_version            = PACKAGE_VERSION,
            invariant_contract_version = INVARIANT_CONTRACT_VERSION,
            event_count                = self._committed_count,
            trace_hash                 = None,                       # D-TRACE-8 placeholder
            runtime_hash               = self._runtime_hash,         # D-TRACE-8 placeholder
            session_identity           = self._session_identity,     # D-TRACE-8 placeholder
        )

        # Canonical manifest text + trailing newline for line-friendliness.
        text = serialize_manifest(manifest) + "\n"

        # Write atomically-enough for step 2: open, write, flush, fsync.
        # No tmp+rename rename-dance in step 2 — crash recovery is
        # explicitly deferred.
        with open(
            self.package.manifest_path,
            mode="w",
            encoding="utf-8",
            newline="\n",
        ) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

        self._finalized = True
        return manifest

    # ────────── read-only inspection (test-friendly) ──────────

    @property
    def committed_count(self) -> int:
        """Number of envelopes durably committed so far. Equal to the
        line count of events.jsonl at any moment under D-TRACE-2."""
        return self._committed_count

    @property
    def is_finalized(self) -> bool:
        return self._finalized

    @property
    def runtime_hash_placeholder(self) -> str | None:
        return self._runtime_hash

    @property
    def session_identity_placeholder(self) -> str | None:
        return self._session_identity
