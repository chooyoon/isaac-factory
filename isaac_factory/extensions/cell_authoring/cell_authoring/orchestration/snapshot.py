"""Boundary snapshot — replay-authoritative continuity projection.

Phase 4B Step 8 / Phase 3. Cites
[docs/phase_4b_deterministic_semantics.md] section 12 (D-CONT clauses).

This module is **the replay-authoritative canonicalization boundary**
for inter-node continuity. It is NOT a generic registry serializer; it
is the precise interface at which the runtime's open-world state is
projected down to a closed-world replay identity.

Two concepts must never be conflated:

  A. Full diagnostic registry snapshot — :py:meth:`CellStateRegistry
     .snapshot` (Phase 4A). Includes every registry field, observational
     and authoritative alike. **Diagnostic-only.** Never feeds replay
     identity. Cites D-CONT-7.

  B. Boundary snapshot — :py:func:`boundary_snapshot` (this module).
     Allowlist-only. Pure-function. Deterministic. Canonical JSON.
     Participates in every L3 replay-identity comparison
     (D-REPLAY-1). Cites D-CONT-6, D-CONT-6a, D-CONT-6b, D-CONT-6c.

Contract clauses enforced
=========================

D-CONT-1   — allowlisted authoritative continuity fields only:
             object D-LIFE state (Phase 4 will add; Step-8 Phase 3
             ships the structural slot via ``dlife_state``-less
             projection — object pose + fixture occupancy + session
             sets are the Step-8-Phase-3 surface).
D-CONT-2   — never reads any forbidden non-authoritative state.
D-CONT-6   — allowlist-only serialization. No
             ``registry.to_dict() ; del snapshot["velocity"]`` pattern.
             Adding a field to the registry has NO effect on the
             snapshot unless this function's enumeration is updated
             (a deliberate, reviewable contract revision).
D-CONT-6a  — snapshot identity = byte-equality of canonical-JSON
             encoding; no sidecar artifacts contribute.
D-CONT-6b  — ``schema_version`` is mandatory; mismatches are refused
             by downstream comparators.
D-CONT-6c  — pure-function, side-effect free, deterministic,
             allowlist-only, clock-independent, simulator-state-
             independent, incidental-registry-field-independent.
D-CONT-7   — registry membership confers NO authority. Presence in
             :class:`CellStateRegistry` is not a continuity claim.

Field-classification table (Step 8 / Phase 3 surface)
=====================================================

The projection in this module reads EXACTLY these fields:

  Authoritative (read, included in snapshot):
    * ``registry.objects[oid].pose_m``           (D-CONT-1)
    * ``registry.objects[oid].yaw_rad``          (D-CONT-1, mirrors pose)
    * ``registry.fixtures[fid].occupied_by``     (D-CONT-1, D-CONT-5)
    * session ``_completed``                      (D-SESS-1)
    * session ``_failed``                         (D-SESS-1)
    * session ``_retry_counts``                   (D-SESS-1)
    * ``schema_version`` / ``kind`` / ``node_id`` / ``seq`` (envelope)

  Forbidden (never read by this function — D-CONT-2 / D-CONT-7):
    * ``registry.objects[oid].contact_with``     (observational)
    * ``registry.objects[oid].metadata``         (diagnostic scratchpad)
    * ``registry.fixtures[fid].metadata``        (diagnostic scratchpad)
    * ``registry.robots`` (entire mapping)       (observational)
    * ``registry.contact`` (entire ContactState) (observational, D-CONT-2)
    * ``registry.task`` (entire TaskState)       (diagnostic)
    * ``registry.metrics`` (free-form scratchpad)(diagnostic)
    * any wall-clock derived value                (D-SCHED-11)
    * any per-tick aggregate / motion peak        (D-CONT-2)
    * any rigid-body velocity / angular velocity  (D-CONT-2)
    * any contact manifold / solver cache state   (D-CONT-2)

A future contributor who needs a new field in the snapshot MUST:
  (1) amend D-CONT-1 in
      [docs/phase_4b_deterministic_semantics.md] section 12.2;
  (2) extend this module's allowlist table (above) and projection;
  (3) bump :data:`BOUNDARY_SNAPSHOT_SCHEMA_VERSION`;
  (4) provide a forward-compat plan per D-CONT-6b.

There is no "just add it for debugging" path. The snapshot is the
contract.
"""

from __future__ import annotations

import hashlib
from typing import AbstractSet, Any, Mapping

from .package import canonical_dumps


# ───────────────────────── version / kind constants ─────────────────────────


BOUNDARY_SNAPSHOT_SCHEMA_VERSION: int = 2
"""Canonical boundary-snapshot schema version (D-CONT-6b).

Version history:
  1 — initial schema (Phase 4B Step 8 / Phase 3): objects (pose_m + yaw_rad),
      fixtures (occupied_by), session (completed + failed + retry_counts),
      envelope (schema_version + kind + node_id + seq).
  2 — Phase 4B Step 9 Phase 5 (D-FAULT-4a): session block extended with
      ``skipped`` (cascade-skipped node_ids, D-FAULT-4) alongside the
      existing completed / failed / retry_counts. Backward-compatible at
      the API surface: ``boundary_snapshot()`` accepts ``session_skipped``
      with a default of ``frozenset()`` so existing callers that have not
      yet been updated continue to function. The on-disk schema version
      is 2 in all cases; replay against a stored ``schema_version == 1``
      snapshot is refused per D-CONT-6b.

Any addition, removal, rename, or semantic change to the snapshot
allowlist requires a version bump. Downstream comparators that read a
snapshot at replay time refuse to compare across mismatched versions
(D-CONT-6b).
"""


BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL: str = "session_initial"
"""Snapshot taken at end of :py:meth:`ExecutionSession.begin` — before
the first orchestration tick (D-EXEC-11)."""

BOUNDARY_SNAPSHOT_KIND_PRE_NODE: str = "pre_node"
"""Snapshot taken at end of Phase C — after preconditions clear, before
any command is issued (D-EXEC-10, item 1)."""

BOUNDARY_SNAPSHOT_KIND_POST_NODE: str = "post_node"
"""Snapshot taken at end of Phase G — after the verdict-driven
mutations (occupancy commit, registry rollback) but before the closing
:data:`EVENT_NODE_EXECUTION_COMPLETED`. In Phase 4B Step 6's bundled-
phase model, this collapses the ``post_node_sim`` (D-EXEC-10 item 2)
and ``post_node_validate`` (item 3) checkpoints into one. A later step
that re-splits Phase E from Phase F will introduce the second
checkpoint."""


_VALID_KINDS: frozenset[str] = frozenset({
    BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL,
    BOUNDARY_SNAPSHOT_KIND_PRE_NODE,
    BOUNDARY_SNAPSHOT_KIND_POST_NODE,
})


# ───────────────────────────── errors ─────────────────────────────


class BoundarySnapshotError(ValueError):
    """Raised on construction violations of the snapshot contract.

    Examples:
      * unknown ``kind`` (not in the three-element D-EXEC kind set);
      * ``kind == pre_node`` or ``post_node`` but ``node_id is None``;
      * ``kind == session_initial`` but ``node_id is not None``;
      * ``seq`` is negative.
    """


# ───────────────────────────── projector ─────────────────────────────


def boundary_snapshot(
    *,
    kind:                 str,
    node_id:              str | None,
    seq:                  int,
    objects:              Mapping[str, Any],
    fixtures:             Mapping[str, Any],
    session_completed:    AbstractSet[str],
    session_failed:       AbstractSet[str],
    session_retry_counts: Mapping[str, int],
    session_skipped:      AbstractSet[str] = frozenset(),
    schema_version:       int = BOUNDARY_SNAPSHOT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Project authoritative continuity state to a canonical-JSON dict.

    Pure-function. Cites D-CONT-6, D-CONT-6c.

    Parameters
    ----------
    kind:
        One of :data:`BOUNDARY_SNAPSHOT_KIND_SESSION_INITIAL`,
        :data:`BOUNDARY_SNAPSHOT_KIND_PRE_NODE`,
        :data:`BOUNDARY_SNAPSHOT_KIND_POST_NODE`. Any other value raises
        :class:`BoundarySnapshotError`.
    node_id:
        The node_id this snapshot brackets. Required for
        ``pre_node`` / ``post_node``; must be ``None`` for
        ``session_initial`` (which has no node context yet).
    seq:
        The orchestration-tick ``seq`` at which this snapshot is taken
        (typically ``event_bus.committed_count`` at the call site).
        Stored in the snapshot for replay-identity diagnostics
        (D-EXEC-12).
    objects:
        ``Mapping[object_id, ObjectState-like]``. The projection reads
        ONLY ``.pose_m`` and ``.yaw_rad`` from each value. Anything else
        on the value (``.contact_with``, ``.metadata``, future fields)
        is **not** read, not iterated, not probed for existence
        (D-CONT-6c "incidental registry fields independent").
    fixtures:
        ``Mapping[fixture_id, FixtureState-like]``. Reads ONLY
        ``.occupied_by`` (a singleton ``str | None`` per D-LIFE-6,
        D-CONT-5).
    session_completed:
        Set of node_ids in the session's ``_completed`` collection.
        Iterated as ``sorted(set)`` to satisfy D-SCHED-7.
    session_failed:
        Set of node_ids in the session's ``_failed`` collection.
        Same iteration discipline.
    session_retry_counts:
        ``Mapping[node_id, int]``. Iterated as
        ``sorted(mapping.keys())`` to satisfy D-SCHED-5/-6.
    schema_version:
        Defaulted to :data:`BOUNDARY_SNAPSHOT_SCHEMA_VERSION`. Callers
        should NOT override.

    Returns
    -------
    dict[str, Any]
        A canonical, JSON-serializable dict. Field order matches the
        canonical-JSON sort order (``canonical_dumps`` does
        ``sort_keys=True``, so insertion order is preserved only as a
        nicety; iteration order of nested mappings is enforced via
        sorted comprehension at construction time).

    Pure-function discipline (D-CONT-6c)
    ------------------------------------
    Does NOT:
      * call ``time.time()`` / ``time.monotonic()`` / ``datetime.now()``;
      * call ``uuid.uuid4()`` / ``random.*`` / ``os.urandom`` /
        ``secrets.*``;
      * touch :class:`CellStateRegistry` methods other than attribute
        reads on the values it was passed;
      * read object identity (``id(obj)``);
      * log, emit events, or write to disk;
      * mutate any input.

    Two calls with identical authoritative inputs produce
    byte-identical canonical-JSON output (proved by the contamination
    test suite at
    ``tests/unit/test_cell_01_phase_4b_step8_p3_boundary_snapshot.py``).
    """
    if kind not in _VALID_KINDS:
        raise BoundarySnapshotError(
            f"unknown snapshot kind {kind!r}; expected one of "
            f"{sorted(_VALID_KINDS)}"
        )
    if kind in (BOUNDARY_SNAPSHOT_KIND_PRE_NODE, BOUNDARY_SNAPSHOT_KIND_POST_NODE):
        if node_id is None:
            raise BoundarySnapshotError(
                f"snapshot kind {kind!r} requires a non-None node_id"
            )
    else:  # session_initial
        if node_id is not None:
            raise BoundarySnapshotError(
                f"snapshot kind {kind!r} requires node_id is None; "
                f"got {node_id!r}"
            )
    if seq < 0:
        raise BoundarySnapshotError(f"seq must be >= 0; got {seq}")
    if not isinstance(schema_version, int) or schema_version < 1:
        raise BoundarySnapshotError(
            f"schema_version must be a positive int; got {schema_version!r}"
        )

    # Allowlist projection — explicit enumeration. Adding a field to
    # ``ObjectState`` / ``FixtureState`` does NOT leak into the
    # snapshot unless this code is changed (a contract revision).
    projected_objects: dict[str, dict[str, Any]] = {
        oid: {
            "pose_m":  (None if objects[oid].pose_m is None
                        else [float(x) for x in objects[oid].pose_m]),
            "yaw_rad": float(objects[oid].yaw_rad),
        }
        for oid in sorted(objects.keys())
    }
    projected_fixtures: dict[str, dict[str, Any]] = {
        fid: {
            "occupied_by": fixtures[fid].occupied_by,  # str | None
        }
        for fid in sorted(fixtures.keys())
    }
    projected_session: dict[str, Any] = {
        "completed":    sorted(session_completed),
        "failed":       sorted(session_failed),
        "retry_counts": [
            [nid, int(session_retry_counts[nid])]
            for nid in sorted(session_retry_counts.keys())
        ],
        "skipped":      sorted(session_skipped),   # D-FAULT-4a (schema_version=2)
    }

    return {
        "schema_version": int(schema_version),
        "kind":           kind,
        "node_id":        node_id,
        "seq":            int(seq),
        "objects":        projected_objects,
        "fixtures":       projected_fixtures,
        "session":        projected_session,
    }


# ───────────────────────────── hash helper ─────────────────────────────


def boundary_snapshot_canonical_json(snapshot: Mapping[str, Any]) -> str:
    """Return the canonical-JSON string for a snapshot dict.

    Wrapper around :func:`canonical_dumps` so call sites can be grepped
    for "what produces the replay-identity surface." Two snapshots
    produce equal canonical-JSON iff they are identity-equal
    (D-CONT-6a).
    """
    return canonical_dumps(snapshot)


def boundary_snapshot_hash(snapshot: Mapping[str, Any]) -> str:
    """SHA-256 hex digest of the canonical-JSON encoding.

    Used as the ``canonical_hash`` field on
    :data:`EVENT_NODE_BOUNDARY_SNAPSHOT` event payloads — small,
    constant-size, comparable byte-for-byte across runs.

    Cites D-CONT-6a (byte-equal canonical-JSON ⇒ identity-equal ⇒
    equal hash) and D-CONT-6c (deterministic, no clock dependence).
    SHA-256 chosen for: deterministic across implementations
    (stdlib ``hashlib``), no truncation ambiguity (full 64-hex
    output), no need for collision resistance against adversarial
    inputs in this use case.
    """
    return hashlib.sha256(
        boundary_snapshot_canonical_json(snapshot).encode("utf-8")
    ).hexdigest()
