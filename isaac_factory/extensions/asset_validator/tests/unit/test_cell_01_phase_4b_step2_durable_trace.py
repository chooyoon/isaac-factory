"""Phase 4B step 2 — durable trace + SessionPackage invariants.

Proves the step-2 set of clauses from the deterministic-semantics
contract [docs/phase_4b_deterministic_semantics.md]:

  D-TRACE-2  — append-only after commit; finalized trace immutable
  D-TRACE-3  — no retroactive mutation; partial traces preserved
  D-TRACE-6  — corrupt prefix detectable via seq monotonicity check
  D-TRACE-7  — integrity verifiable at close
  D-TRACE-8  — manifest schema fixed (PACKAGE_VERSION,
                INVARIANT_CONTRACT_VERSION, event_count, placeholder
                hash/identity fields)

Each test class targets one clause family. All tests are pure-Python;
no Isaac Sim, no PhysX, no async, no threads. Files are written to
``tmp_path`` (pytest fixture).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


# Add cell_authoring extension to sys.path (matches Phase 4A pattern).
_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


from cell_authoring.orchestration import (  # noqa: E402
    DurableTraceRecorder,
    EVENTS_FILENAME,
    EventBus,
    EventEnvelope,
    INVARIANT_CONTRACT_VERSION,
    IntegrityReport,
    InMemoryTraceRecorder,
    MANIFEST_FILENAME,
    Manifest,
    PACKAGE_VERSION,
    SessionPackage,
    TraceRecorderFinalizedError,
    TraceRecorderNotEmptyError,
    fingerprint,
    serialize_envelope,
    serialize_manifest,
    verify_package_integrity,
)


# ───────────────────────────── helpers ─────────────────────────────


def _make_pkg(tmp_path: Path, name: str = "session_0") -> SessionPackage:
    return SessionPackage(tmp_path / name)


def _emit_canonical_sequence(bus: EventBus) -> None:
    """Emit a fixed deterministic stream of events. Used by every
    byte-identity test so the input is exactly the same across runs."""
    bus.emit("JobStarted")
    bus.emit("TaskScheduled", {"node_id": "n0"})
    bus.emit("TaskStarted",   {"node_id": "n0", "extra": [1, 2, 3]})
    bus.emit("TaskCompleted", {"node_id": "n0", "outcome": "PASS"})
    bus.emit("JobCompleted")


# ────────────────── canonical serialization (envelope) ──────────────────


class TestCanonicalEnvelopeSerialization:
    """The serializer is the foundation of every step-2 property —
    byte-identity, integrity, replay identity all transitively depend
    on it being deterministic."""

    def test_envelope_serializes_to_canonical_json_line(self):
        env = EventEnvelope(
            seq=0,
            event_type="JobStarted",
            orchestration_tick=0,
            physx_frame=0,
            node_id=None,
        )
        encoded = serialize_envelope(env)
        # Keys sorted alphabetically (sort_keys=True); compact separators
        # (no spaces around commas / colons); ASCII-only output.
        expected = (
            '{"event_type":"JobStarted",'
            '"logical_time":null,'
            '"node_id":null,'
            '"orchestration_tick":0,'
            '"payload":{},'
            '"physx_frame":0,'
            '"seq":0}'
        )
        assert encoded == expected

    def test_envelope_serialization_is_stable_across_calls(self):
        env = EventEnvelope(seq=7, event_type="X", payload={"b": 2, "a": 1})
        a = serialize_envelope(env)
        b = serialize_envelope(env)
        c = serialize_envelope(env)
        assert a == b == c

    def test_payload_key_order_does_not_affect_output(self):
        """Insertion order of the payload dict must not leak into the
        serialized output. D-TRACE-3 (no insertion-order dependence)."""
        env1 = EventEnvelope(seq=0, event_type="X", payload={"alpha": 1, "beta": 2, "gamma": 3})
        env2 = EventEnvelope(seq=0, event_type="X", payload={"gamma": 3, "alpha": 1, "beta": 2})
        env3 = EventEnvelope(seq=0, event_type="X", payload={"beta": 2, "gamma": 3, "alpha": 1})
        assert serialize_envelope(env1) == serialize_envelope(env2) == serialize_envelope(env3)

    def test_nested_payload_gets_recursive_key_sort(self):
        env1 = EventEnvelope(seq=0, event_type="X",
                             payload={"top": {"z": 1, "a": 2}})
        env2 = EventEnvelope(seq=0, event_type="X",
                             payload={"top": {"a": 2, "z": 1}})
        assert serialize_envelope(env1) == serialize_envelope(env2)

    def test_nan_and_inf_are_rejected(self):
        env = EventEnvelope(seq=0, event_type="X", payload={"x": float("nan")})
        with pytest.raises(ValueError):
            serialize_envelope(env)

    def test_fingerprint_is_alias_for_serialize_envelope(self):
        env = EventEnvelope(seq=0, event_type="X", payload={"k": "v"})
        assert fingerprint(env) == serialize_envelope(env)

    def test_field_equal_envelopes_have_equal_fingerprints(self):
        env_a = EventEnvelope(seq=42, event_type="Hello",
                              orchestration_tick=1, physx_frame=99,
                              node_id="node_x", payload={"k": "v"})
        env_b = EventEnvelope(seq=42, event_type="Hello",
                              orchestration_tick=1, physx_frame=99,
                              node_id="node_x", payload={"k": "v"})
        assert fingerprint(env_a) == fingerprint(env_b)


# ────────────────── canonical serialization (manifest) ──────────────────


class TestCanonicalManifestSerialization:
    """Manifest schema is fixed by D-TRACE-8."""

    def test_manifest_serializes_deterministically(self):
        m = Manifest(
            package_version=PACKAGE_VERSION,
            invariant_contract_version=INVARIANT_CONTRACT_VERSION,
            event_count=5,
        )
        text = serialize_manifest(m)
        # Re-serialize: must be identical.
        assert serialize_manifest(m) == text
        # Decode round-trips to the same field values.
        obj = json.loads(text)
        assert obj["package_version"] == PACKAGE_VERSION
        assert obj["invariant_contract_version"] == INVARIANT_CONTRACT_VERSION
        assert obj["event_count"] == 5
        assert obj["trace_hash"] is None
        assert obj["runtime_hash"] is None
        assert obj["session_identity"] is None

    def test_manifest_schema_fields_are_fixed(self):
        """D-TRACE-8: manifest schema is fixed. The exact set of fields
        is enumerated here so future changes require a deliberate edit
        of this test (and a PACKAGE_VERSION bump)."""
        m = Manifest(
            package_version=PACKAGE_VERSION,
            invariant_contract_version=INVARIANT_CONTRACT_VERSION,
            event_count=0,
        )
        obj = m.to_dict()
        assert set(obj.keys()) == {
            "package_version",
            "invariant_contract_version",
            "event_count",
            "trace_hash",
            "runtime_hash",
            "session_identity",
        }

    def test_manifest_keys_sorted_in_output(self):
        m = Manifest(
            package_version=PACKAGE_VERSION,
            invariant_contract_version=INVARIANT_CONTRACT_VERSION,
            event_count=3,
        )
        text = serialize_manifest(m)
        # First key after the opening `{\n  "` should be event_count
        # (alphabetically before invariant_contract_version).
        # We confirm via a regex-free index check.
        first_key_pos = text.index('"event_count"')
        invariant_pos = text.index('"invariant_contract_version"')
        package_pos   = text.index('"package_version"')
        assert first_key_pos < invariant_pos < package_pos


# ────────────────── package layout + canonical filenames ──────────────────


class TestSessionPackageLayout:
    """The on-disk layout (filenames + paths) is fixed by D-TRACE-8."""

    def test_canonical_filenames(self):
        assert MANIFEST_FILENAME == "manifest.json"
        assert EVENTS_FILENAME == "events.jsonl"

    def test_session_package_exposes_canonical_paths(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        assert pkg.manifest_path == tmp_path / "session_0" / "manifest.json"
        assert pkg.events_path == tmp_path / "session_0" / "events.jsonl"


# ────────────────── durable recorder — basic recording ──────────────────


class TestDurableRecorderBasicFlow:
    """Smoke: create recorder, emit events through the bus, finalize,
    verify the package layout and content."""

    def test_records_n_events_and_finalizes(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)

        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        _emit_canonical_sequence(bus)
        assert rec.committed_count == 5

        manifest = rec.finalize()
        assert rec.is_finalized is True
        assert manifest.event_count == 5
        assert manifest.package_version == PACKAGE_VERSION
        assert manifest.invariant_contract_version == INVARIANT_CONTRACT_VERSION

        # Both canonical files exist.
        assert pkg.manifest_path.is_file()
        assert pkg.events_path.is_file()

        # Five lines in events.jsonl (one per event, LF-terminated).
        lines = pkg.events_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 5
        assert all(line.startswith("{") for line in lines)

    def test_recorder_persists_canonical_lines(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        env0 = bus.emit("E0")
        env1 = bus.emit("E1", {"a": 1})
        rec.finalize()

        # On-disk lines exactly match canonical serialize_envelope output.
        lines = pkg.events_path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == serialize_envelope(env0)
        assert lines[1] == serialize_envelope(env1)


# ────────────────── append-only enforcement (D-TRACE-2) ──────────────────


class TestAppendOnlyEnforcement:
    """D-TRACE-2: post-finalize the trace is immutable."""

    def test_on_event_post_finalize_raises(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        bus.emit("OnlyEvent")
        rec.finalize()

        # Subsequent on_event() raises a TraceRecorderFinalizedError.
        with pytest.raises(TraceRecorderFinalizedError):
            rec.on_event(EventEnvelope(seq=99, event_type="LateEvent"))

    def test_finalize_twice_raises(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        rec.finalize()
        with pytest.raises(TraceRecorderFinalizedError):
            rec.finalize()

    def test_recorder_refuses_pre_existing_package(self, tmp_path):
        """D-TRACE-2: a directory that already contains events.jsonl or
        manifest.json could be authoritative for a prior session;
        overwriting is forbidden."""
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        bus.emit("X")
        rec.finalize()

        with pytest.raises(TraceRecorderNotEmptyError):
            DurableTraceRecorder(pkg)


# ────────────────── byte-identity (the headline property) ──────────────────


class TestByteIdenticalPackageGeneration:
    """Two recorders given identical envelopes produce byte-identical
    package artifacts. This is the step-2 replay-identity proof at the
    on-disk layer."""

    def test_two_recorders_produce_byte_equal_events_jsonl(self, tmp_path):
        pkg_a = _make_pkg(tmp_path, "a")
        pkg_b = _make_pkg(tmp_path, "b")

        for pkg in (pkg_a, pkg_b):
            rec = DurableTraceRecorder(pkg)
            bus = EventBus()
            bus.register(rec)
            bus.freeze()
            _emit_canonical_sequence(bus)
            rec.finalize()

        bytes_a = pkg_a.events_path.read_bytes()
        bytes_b = pkg_b.events_path.read_bytes()
        assert bytes_a == bytes_b
        # Sanity: it's not just both being empty.
        assert b"JobStarted" in bytes_a

    def test_two_recorders_produce_byte_equal_manifest_json(self, tmp_path):
        pkg_a = _make_pkg(tmp_path, "a")
        pkg_b = _make_pkg(tmp_path, "b")
        for pkg in (pkg_a, pkg_b):
            rec = DurableTraceRecorder(pkg)
            bus = EventBus()
            bus.register(rec)
            bus.freeze()
            _emit_canonical_sequence(bus)
            rec.finalize()
        assert pkg_a.manifest_path.read_bytes() == pkg_b.manifest_path.read_bytes()

    def test_dual_recorder_observation_matches_durable(self, tmp_path):
        """A DurableTraceRecorder + InMemoryTraceRecorder attached to the
        same bus see the same envelopes in the same order — the durable
        on-disk lines fingerprint-match the in-memory envelopes."""
        pkg = _make_pkg(tmp_path)
        durable = DurableTraceRecorder(pkg)
        in_mem  = InMemoryTraceRecorder("mem")

        bus = EventBus()
        bus.register(durable)
        bus.register(in_mem)
        bus.freeze()
        _emit_canonical_sequence(bus)
        durable.finalize()

        on_disk_lines = pkg.events_path.read_text(encoding="utf-8").splitlines()
        in_mem_lines  = [serialize_envelope(e) for e in in_mem.events]
        assert on_disk_lines == in_mem_lines


# ────────────────── integrity verification (D-TRACE-6, -7) ──────────────────


class TestIntegrityVerification:
    """D-TRACE-6 + D-TRACE-7: corrupt prefixes detectable; verifiable
    at close."""

    def test_well_formed_package_verifies_ok(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        _emit_canonical_sequence(bus)
        rec.finalize()

        report = verify_package_integrity(pkg)
        assert report.ok is True
        assert report.event_count_manifest == 5
        assert report.event_count_actual == 5
        assert report.seqs_monotone_gap_free is True
        assert report.schema_version_ok is True
        assert report.failures == ()

    def test_missing_manifest_is_detected(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        bus.emit("X")
        rec.finalize()
        pkg.manifest_path.unlink()

        report = verify_package_integrity(pkg)
        assert report.ok is False
        assert any("manifest.json missing" in f for f in report.failures)

    def test_count_mismatch_is_detected(self, tmp_path):
        """Tamper the manifest: claim 99 events when only 5 are on disk.
        The verifier must surface this without any external oracle."""
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        _emit_canonical_sequence(bus)
        rec.finalize()

        # Hand-tamper the manifest. (In step 2 there is no integrity
        # hash; tampering is detectable only via the count check.)
        m = json.loads(pkg.manifest_path.read_text(encoding="utf-8"))
        m["event_count"] = 99
        pkg.manifest_path.write_text(
            json.dumps(m, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

        report = verify_package_integrity(pkg)
        assert report.ok is False
        assert report.event_count_manifest == 99
        assert report.event_count_actual == 5
        assert any("event_count" in f for f in report.failures)

    def test_seq_gap_is_detected(self, tmp_path):
        """Delete the middle line of events.jsonl — the seq sequence
        now has a gap. D-TRACE-6 requires this to be detectable."""
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        _emit_canonical_sequence(bus)  # 5 events, seqs 0..4
        rec.finalize()

        lines = pkg.events_path.read_text(encoding="utf-8").splitlines()
        # Remove line index 2 (the seq=2 event), preserving the rest.
        kept = [lines[0], lines[1], lines[3], lines[4]]
        pkg.events_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        # Also adjust manifest event_count so it matches actual count;
        # this isolates the gap check from the count check.
        m = json.loads(pkg.manifest_path.read_text(encoding="utf-8"))
        m["event_count"] = 4
        pkg.manifest_path.write_text(
            json.dumps(m, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

        report = verify_package_integrity(pkg)
        assert report.ok is False
        assert report.seqs_monotone_gap_free is False
        assert report.event_count_manifest == 4
        assert report.event_count_actual == 4
        assert any("seq" in f for f in report.failures)

    def test_unsupported_schema_version_is_detected(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        bus.emit("X")
        rec.finalize()

        m = json.loads(pkg.manifest_path.read_text(encoding="utf-8"))
        m["package_version"] = 999
        pkg.manifest_path.write_text(
            json.dumps(m, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

        report = verify_package_integrity(pkg)
        assert report.ok is False
        assert report.schema_version_ok is False

    def test_verifier_is_deterministic(self, tmp_path):
        """D-TRACE-6: same package on disk → same IntegrityReport."""
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        _emit_canonical_sequence(bus)
        rec.finalize()

        r1 = verify_package_integrity(pkg)
        r2 = verify_package_integrity(pkg)
        assert r1 == r2


# ────────────────── manifest schema fields (D-TRACE-8) ──────────────────


class TestManifestSchemaFields:
    """D-TRACE-8: manifest fields are exactly what the contract pins."""

    def test_placeholder_fields_are_none_in_step2(self, tmp_path):
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        bus.emit("X")
        manifest = rec.finalize()
        assert manifest.trace_hash is None
        assert manifest.runtime_hash is None
        assert manifest.session_identity is None

    def test_runtime_hash_placeholder_passthrough(self, tmp_path):
        """The recorder stores the runtime_hash placeholder verbatim;
        no computation in step 2."""
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(
            pkg,
            runtime_hash="placeholder-rh",
            session_identity="placeholder-sid",
        )
        manifest = rec.finalize()
        assert manifest.runtime_hash == "placeholder-rh"
        assert manifest.session_identity == "placeholder-sid"

        # Round-trip via on-disk manifest read.
        round_trip = pkg.load_manifest()
        assert round_trip.runtime_hash == "placeholder-rh"
        assert round_trip.session_identity == "placeholder-sid"


# ────────────────── append lifecycle (D-TRACE-3) ──────────────────


class TestAppendLifecycle:
    """The four phases — append_requested → serialized → flushed →
    committed — must each behave per the docstring contract."""

    def test_serialization_failure_does_not_commit(self, tmp_path):
        """If json.dumps raises (NaN/Inf), the recorder does not commit
        the failing envelope. Subsequent events DO commit (the recorder
        is not broken). The trace on disk has a gap in seq — preserved
        as-is per D-TRACE-3, surfaced by the verifier per D-TRACE-6.

        Subtle interaction with D-BUS-12: when json.dumps raises inside
        the durable recorder's on_event, the bus emits a SubscriberError
        event. Per D-BUS-12 the failing subscriber (the durable recorder
        itself) is **suppressed** from receiving its own SubscriberError.
        So the on-disk gap covers BOTH the failed event's seq AND the
        suppressed SubscriberError's seq.
        """
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()

        bus.emit("A")                              # seq=0 — durable commits
        bus.emit("Bad", {"x": float("nan")})       # seq=1 — durable raises,
                                                   # seq=2 — SubscriberError
                                                   #          suppressed from durable
        bus.emit("C")                              # seq=3 — durable commits

        # Recorder committed exactly the two serializable events.
        assert rec.committed_count == 2

        manifest = rec.finalize()
        assert manifest.event_count == 2

        # On-disk: two lines, with a gap (seq 0 then seq 3 — the failing
        # seq=1 was never written; seq=2 SubscriberError was suppressed).
        lines = pkg.events_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        seqs_on_disk = [json.loads(line)["seq"] for line in lines]
        assert seqs_on_disk == [0, 3]

        # The verifier surfaces the gap (D-TRACE-3 + D-TRACE-6).
        report = verify_package_integrity(pkg)
        assert report.ok is False
        assert report.seqs_monotone_gap_free is False
        assert any("seq" in f for f in report.failures)

    def test_committed_count_only_advances_after_fsync(self, tmp_path):
        """Behavioural proof: at any point the on-disk line count equals
        ``rec.committed_count``."""
        pkg = _make_pkg(tmp_path)
        rec = DurableTraceRecorder(pkg)
        bus = EventBus()
        bus.register(rec)
        bus.freeze()
        for i in range(7):
            bus.emit(f"E{i}", {"i": i})
            on_disk = pkg.events_path.read_text(encoding="utf-8").splitlines()
            assert len(on_disk) == rec.committed_count == i + 1


# ────────────────── reproducibility under repeated runs ──────────────────


class TestReproducibilityAcrossRuns:
    """Same event stream → byte-identical package, run after run."""

    def test_repeated_runs_byte_identical(self, tmp_path):
        # Build 3 packages from 3 fresh recorders given identical input.
        bytes_events_each = []
        bytes_manifest_each = []
        for k in range(3):
            pkg = _make_pkg(tmp_path, f"run_{k}")
            rec = DurableTraceRecorder(pkg)
            bus = EventBus()
            bus.register(rec)
            bus.freeze()
            _emit_canonical_sequence(bus)
            rec.finalize()
            bytes_events_each.append(pkg.events_path.read_bytes())
            bytes_manifest_each.append(pkg.manifest_path.read_bytes())

        # All three events.jsonl files are byte-equal.
        assert bytes_events_each[0] == bytes_events_each[1] == bytes_events_each[2]
        # All three manifest.json files are byte-equal.
        assert bytes_manifest_each[0] == bytes_manifest_each[1] == bytes_manifest_each[2]


# ────────────── meta: clause coverage signal ──────────────


def test_step2_covers_minimum_clause_family_set():
    """Documents which D-TRACE clauses step 2 enforces. Updating step N
    should expand the set."""
    covered_clauses = {
        # Step 2 additions (relative to step 1's D-TRACE-1)
        "D-TRACE-2",
        "D-TRACE-3",
        "D-TRACE-6",
        "D-TRACE-7",
        "D-TRACE-8",
    }
    assert len(covered_clauses) >= 5
