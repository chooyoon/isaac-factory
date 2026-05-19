"""Deterministic SessionPackage — manifest + events.jsonl (Phase 4B step 2).

Establishes the durable trace packaging contract. This module is
intentionally minimal:

  * one directory layout: ``manifest.json`` + ``events.jsonl``
  * one canonical serialization for both
  * one minimal-but-sufficient integrity verifier

No persistence backend (sqlite/parquet/etc.), no compression, no async
I/O, no WAL, no background flush worker, no schema registry, no replay
runtime. Those are deliberate later-step deliverables.

Contract clauses honoured by this module
----------------------------------------
D-TRACE-2 — authoritative trace is append-only; once a record is
            serialized to ``events.jsonl`` it is not edited / reordered /
            deleted.
D-TRACE-3 — partial traces are preserved as-is; no retroactive
            regeneration path exists.
D-TRACE-6 — each record carries enough self-identifying information
            (its ``seq`` field) for a corrupt prefix to be detected.
D-TRACE-7 — trace integrity is verifiable at session close via
            :py:func:`verify_package_integrity` (gap-free monotone
            ``seq`` over the event log + event_count agreement).
D-TRACE-8 — manifest schema is fixed; fields enumerated by :class:`Manifest`.

D-SCHED-11 / D-EXEC-7 — no wall-clock fields are written; the file
            mtime is filesystem-dependent and is excluded from any
            byte-identity comparison.

Deferred (NOT in step 2, documented to prevent implicit creep later)
--------------------------------------------------------------------
* Deep payload normalization — payloads are serialized via Python's
  default JSON encoder with ``sort_keys=True``. Nested mappings get
  recursive key sorting, but if a payload contains non-JSON-native
  values (sets, custom dataclass instances, numpy scalars), the
  encoder will raise. A typed schema for payload values is a Phase 4C
  concern.
* Float normalization — floats are encoded via ``json.dumps`` default
  (Python ``repr``). Numerically-equal floats with different IEEE-754
  bit patterns will serialize differently. Step 2 forbids NaN/Inf
  (``allow_nan=False``) but does not normalize. A canonical float
  policy is a later-step concern.
* Enum / typed-tag policy — events currently carry ``event_type: str``.
  A typed ``EventKind`` enum + a string-tag canonical encoding policy
  is deferred to the step that freezes the taxonomy.
* ``trace_hash`` content — placeholder None in step 2. A real content
  hash (likely BLAKE2b over the byte-equal events.jsonl) lands when
  cross-process replay-identity verification is implemented.
* ``runtime_hash`` content — placeholder None in step 2. Real value is
  ``H(isaac_sim_version, physx_version, schema_version, cell_cfg_hash)``,
  computed by the (not-yet-implemented) ExecutionSession at begin().
* ``session_identity`` content — placeholder None in step 2.
* Semantic-replay-equivalence hashing — not in scope for step 2.
* Crash recovery — partial events.jsonl files are valid input to
  :py:func:`verify_package_integrity`, which will report the gap and
  expose the prefix length. No automatic recovery is performed.
* Replay execution engine — deferred to a later phase.
* Pause / resume semantics — deferred.
* Cross-version compatibility policy — ``package_version`` is the
  schema-version axis; the policy on bumping it (additive vs breaking)
  is deferred until the first compatibility break.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .events import EventEnvelope


# ───────────────────────── canonical schema versions ─────────────────────────


PACKAGE_VERSION: int = 1
"""Current SessionPackage on-disk layout version (D-TRACE-8).

Bumped on any layout / schema break. Bumps require an updated reader
and a documented compatibility policy."""


INVARIANT_CONTRACT_VERSION: int = 1
"""Version of the deterministic-semantics contract that this package
was produced under. Equal to 1 while
[docs/phase_4b_deterministic_semantics.md] revision 1 is authoritative."""


# Canonical filenames inside the package directory.
MANIFEST_FILENAME: str = "manifest.json"
EVENTS_FILENAME:   str = "events.jsonl"


# ───────────────────────── canonical serialization ─────────────────────────


CANONICAL_DUMPS_KWARGS: dict[str, Any] = {
    "sort_keys":   True,    # D-TRACE-3: recursive key sort → no insertion-order leak
    "separators":  (",", ":"),  # compact, deterministic (no trailing whitespace)
    "ensure_ascii": True,   # no locale-dependent unicode escaping
    "allow_nan":   False,   # NaN/Inf are forbidden (would be non-portable)
}

# Back-compat private alias (preserves the step-2 internal name for any
# external reference, while exposing the canonical kwargs publicly).
_CANONICAL_DUMPS_KWARGS = CANONICAL_DUMPS_KWARGS


def canonical_dumps(obj: Any) -> str:
    """Canonical JSON encoding helper shared across the orchestration
    package. Cites D-TRACE-3 (no insertion-order leak), D-SCHED-12
    (deterministic, no wall-clock / RNG / object-identity dependence).

    Reused by step 2 (envelope + manifest serialization) and step 3
    (predicate fingerprints). Any new module needing a canonical JSON
    string MUST call this helper; do not call ``json.dumps`` ad-hoc.
    """
    return json.dumps(obj, **CANONICAL_DUMPS_KWARGS)


_CANONICAL_MANIFEST_KWARGS: dict[str, Any] = {
    "sort_keys":   True,
    "indent":      2,       # human-readable; deterministic given sort_keys
    "ensure_ascii": True,
    "allow_nan":   False,
}


def _envelope_to_dict(env: EventEnvelope) -> dict[str, Any]:
    """Convert an :class:`EventEnvelope` to a JSON-ready dict.

    Field ordering here is *not* the on-disk ordering — that is
    controlled by ``sort_keys=True`` in :py:func:`serialize_envelope`.
    This function just lifts the dataclass into a mapping.
    """
    return {
        "seq":                env.seq,
        "event_type":         env.event_type,
        "orchestration_tick": env.orchestration_tick,
        "physx_frame":        env.physx_frame,
        "node_id":            env.node_id,
        "payload":            dict(env.payload) if env.payload else {},
        "logical_time":       env.logical_time,
    }


def serialize_envelope(env: EventEnvelope) -> str:
    """Canonical JSON encoding of one envelope (no trailing newline).

    Output is deterministic across processes: identical envelope fields
    → byte-identical string. Cites D-TRACE-3, D-TRACE-6.

    Two envelopes with field-equal content (same ``seq``, ``event_type``,
    ``orchestration_tick``, ``physx_frame``, ``node_id``, ``payload``,
    ``logical_time``) produce byte-identical canonical encodings.
    """
    return json.dumps(_envelope_to_dict(env), **_CANONICAL_DUMPS_KWARGS)


def fingerprint(env: EventEnvelope) -> str:
    """Deterministic content fingerprint for one envelope.

    Defined as identical to :py:func:`serialize_envelope`. Provided as
    a separate name so callers can document intent: ``fingerprint(env)``
    means "the canonical content key for envelope deduplication /
    identity comparison", not "the on-disk encoding".

    Two field-equal envelopes from different buses (produced by two
    independent sessions given identical input) have byte-identical
    fingerprints — this is the unit of replay-identity at the envelope
    level (Cites D-REPLAY contract, layer L3).
    """
    return serialize_envelope(env)


# ───────────────────────────── Manifest ─────────────────────────────


@dataclass(frozen=True, slots=True)
class Manifest:
    """Manifest schema (D-TRACE-8).

    Step 2 ships **only** the fields below. Hash and identity fields are
    explicit ``None`` placeholders. Adding fields is an additive bump of
    :data:`PACKAGE_VERSION`; removing or renaming is a breaking bump.

    Fields
    ------
    package_version:
        On-disk layout version. Currently ``1``.
    invariant_contract_version:
        Version of [docs/phase_4b_deterministic_semantics.md] this
        package was produced under. Currently ``1``.
    event_count:
        Number of events committed to ``events.jsonl``. Equal to the
        line count of that file under D-TRACE-2 (append-only).
    trace_hash:
        Placeholder. None in step 2. Real value (likely BLAKE2b of
        canonical events.jsonl bytes) lands with replay-identity.
    runtime_hash:
        Placeholder. None in step 2. Real value =
        ``H(isaac_sim_version, physx_version, schema_version,
            cell_cfg_hash)``; computed by ExecutionSession.begin().
    session_identity:
        Placeholder. None in step 2. Will carry the session_id +
        subscriber_set descriptors when the session layer lands.
    """
    package_version:            int
    invariant_contract_version: int
    event_count:                int
    trace_hash:                 str | None = None
    runtime_hash:               str | None = None
    session_identity:           str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-ready dict. Field order here is not the
        on-disk order — that is fixed by ``sort_keys=True``."""
        return {
            "package_version":            self.package_version,
            "invariant_contract_version": self.invariant_contract_version,
            "event_count":                self.event_count,
            "trace_hash":                 self.trace_hash,
            "runtime_hash":               self.runtime_hash,
            "session_identity":           self.session_identity,
        }

    @classmethod
    def from_dict(cls, obj: Mapping[str, Any]) -> "Manifest":
        """Parse from a JSON-loaded mapping. Raises ``KeyError`` if a
        required field is missing — this is the corruption-detector for
        manifest files."""
        return cls(
            package_version            = int(obj["package_version"]),
            invariant_contract_version = int(obj["invariant_contract_version"]),
            event_count                = int(obj["event_count"]),
            trace_hash                 = obj.get("trace_hash"),
            runtime_hash               = obj.get("runtime_hash"),
            session_identity           = obj.get("session_identity"),
        )


def serialize_manifest(manifest: Manifest) -> str:
    """Canonical manifest encoding (indented, sort_keys, no trailing
    newline). Caller adds the trailing newline.

    Cites D-TRACE-8.
    """
    return json.dumps(manifest.to_dict(), **_CANONICAL_MANIFEST_KWARGS)


# ───────────────────────────── SessionPackage ─────────────────────────────


class SessionPackage:
    """A SessionPackage is a directory on disk with a fixed layout.

    Layout (D-TRACE-8)::

        <path>/
          manifest.json
          events.jsonl

    This class is **passive**: it owns the path, exposes the canonical
    child paths, and knows how to load + verify an existing package.
    Writing is the responsibility of :class:`DurableTraceRecorder` (in
    ``trace.py``), which uses the canonical serializers above.

    There is intentionally no ``create()`` / ``write_manifest()``
    interface here — durable writes only happen through the recorder.
    Bypassing the recorder would risk violating D-TRACE-2 (append-only).
    """

    def __init__(self, path: Path | str) -> None:
        self.path: Path = Path(path)

    # ────────── canonical child paths ──────────

    @property
    def manifest_path(self) -> Path:
        return self.path / MANIFEST_FILENAME

    @property
    def events_path(self) -> Path:
        return self.path / EVENTS_FILENAME

    # ────────── readers (no mutation) ──────────

    def load_manifest(self) -> Manifest:
        """Read and validate the manifest. Raises if the file is
        missing, corrupt, or required fields are absent."""
        text = self.manifest_path.read_text(encoding="utf-8")
        obj = json.loads(text)
        return Manifest.from_dict(obj)

    def iter_event_dicts(self) -> "list[dict[str, Any]]":
        """Read every event line as a dict, in on-disk order.

        Returns a list (not a generator) so callers can compare counts
        and pass it to multiple verifiers cheaply. Step 2 packages are
        small enough that loading the whole file is fine.
        """
        text = self.events_path.read_text(encoding="utf-8")
        # ``splitlines()`` consumes any combination of line terminators;
        # for byte-identity we wrote ``\n``, so splitlines() gives us
        # exactly the canonical lines back.
        out: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line:  # skip empty trailing line if present
                continue
            out.append(json.loads(line))
        return out


# ───────────────────────── Integrity verification ─────────────────────────


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    """Outcome of :py:func:`verify_package_integrity`.

    The report itself is deterministic: same package on disk → same
    report. Cites D-TRACE-6, D-TRACE-7.

    Fields
    ------
    ok:
        True iff every check below passed.
    event_count_manifest:
        ``event_count`` field as read from manifest.json.
    event_count_actual:
        Number of non-empty lines in events.jsonl.
    seqs_monotone_gap_free:
        True iff line *i* has ``seq == i`` for every i in
        ``[0, event_count_actual)``.
    schema_version_ok:
        True iff ``package_version`` and ``invariant_contract_version``
        are both equal to the constants we know how to verify.
    failures:
        Ordered tuple of human-readable failure descriptors. Empty when
        ``ok`` is True. Each descriptor is one short line.
    """
    ok:                     bool
    event_count_manifest:   int
    event_count_actual:     int
    seqs_monotone_gap_free: bool
    schema_version_ok:      bool
    failures:               tuple[str, ...] = ()


def verify_package_integrity(pkg: SessionPackage) -> IntegrityReport:
    """Deterministic integrity verification of a SessionPackage.

    Step 2 covers (cites D-TRACE-6, D-TRACE-7):

      1. manifest.json parses and contains all required fields,
      2. ``package_version`` and ``invariant_contract_version`` match
         what this implementation supports,
      3. number of event lines == ``manifest.event_count``,
      4. ``seq`` is monotone gap-free starting at 0 across every
         line in event order.

    NOT covered in step 2 (deferred; see module docstring):

      * cryptographic signing / hash verification,
      * cross-version schema migration,
      * payload-shape validation,
      * runtime-hash agreement.
    """
    failures: list[str] = []

    # ── 1. manifest load ──
    try:
        manifest = pkg.load_manifest()
    except FileNotFoundError:
        return IntegrityReport(
            ok=False,
            event_count_manifest=-1,
            event_count_actual=-1,
            seqs_monotone_gap_free=False,
            schema_version_ok=False,
            failures=("manifest.json missing",),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        return IntegrityReport(
            ok=False,
            event_count_manifest=-1,
            event_count_actual=-1,
            seqs_monotone_gap_free=False,
            schema_version_ok=False,
            failures=(f"manifest.json unreadable: {type(exc).__name__}: {exc}",),
        )

    # ── 2. schema version ──
    schema_version_ok = (
        manifest.package_version == PACKAGE_VERSION
        and manifest.invariant_contract_version == INVARIANT_CONTRACT_VERSION
    )
    if not schema_version_ok:
        failures.append(
            f"package_version={manifest.package_version} / "
            f"invariant_contract_version={manifest.invariant_contract_version} "
            f"differs from supported "
            f"({PACKAGE_VERSION} / {INVARIANT_CONTRACT_VERSION})"
        )

    # ── 3. event count + 4. seq monotonicity ──
    try:
        event_dicts = pkg.iter_event_dicts()
    except FileNotFoundError:
        return IntegrityReport(
            ok=False,
            event_count_manifest=manifest.event_count,
            event_count_actual=-1,
            seqs_monotone_gap_free=False,
            schema_version_ok=schema_version_ok,
            failures=tuple(failures + ["events.jsonl missing"]),
        )
    except json.JSONDecodeError as exc:
        return IntegrityReport(
            ok=False,
            event_count_manifest=manifest.event_count,
            event_count_actual=-1,
            seqs_monotone_gap_free=False,
            schema_version_ok=schema_version_ok,
            failures=tuple(failures + [f"events.jsonl line decode failed: {exc}"]),
        )

    actual_count = len(event_dicts)
    if actual_count != manifest.event_count:
        failures.append(
            f"event_count manifest={manifest.event_count} "
            f"vs events.jsonl lines={actual_count}"
        )

    monotone = True
    for i, obj in enumerate(event_dicts):
        if obj.get("seq") != i:
            monotone = False
            failures.append(
                f"events.jsonl line {i}: seq={obj.get('seq')!r}, "
                f"expected {i} (D-BUS-3 gap-free monotone)"
            )
            break  # one failure is enough; verification is deterministic

    ok = (
        actual_count == manifest.event_count
        and monotone
        and schema_version_ok
    )

    return IntegrityReport(
        ok=ok,
        event_count_manifest=manifest.event_count,
        event_count_actual=actual_count,
        seqs_monotone_gap_free=monotone,
        schema_version_ok=schema_version_ok,
        failures=tuple(failures),
    )
