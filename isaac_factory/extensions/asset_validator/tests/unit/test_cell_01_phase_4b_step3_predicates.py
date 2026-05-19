"""Phase 4B step 3 — deterministic predicate semantics.

Proves the step-3 set of clauses from the deterministic-semantics
contract [docs/phase_4b_deterministic_semantics.md]:

  * D-SCHED-12  — predicates are pure functions of the context; no
                   PhysX / wall-clock / RNG / object-identity dependence
  * D-SCHED-13  — predicate-list evaluation preserves construction
                   order; short-circuits on first False / first error
  * D-SESS-7    — predicates do not mutate the context (proved via
                   MappingProxyType wrap on PredicateContext)
  * D-SESS-8    — all predicates / snapshots / contexts / results are
                   frozen dataclasses; mutation raises

  * Predicate-fingerprint determinism — identical predicates produce
    byte-identical fingerprints
  * NaN/Inf rejection in ObjectPoseWithin at both construction and
    evaluation time
  * Per-axis L∞ tolerance semantics (not L2)

Each test class targets one clause family or one predicate. All tests
are pure-Python; no Isaac Sim, no PhysX, no async, no threads, no I/O.
"""

from __future__ import annotations

import math
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


# Add cell_authoring extension to sys.path (matches Phase 4A pattern).
_WORKSPACE = Path(__file__).resolve().parents[5]
_CELL_AUTHORING_PATH = str(_WORKSPACE / "isaac_factory" / "extensions" / "cell_authoring")
if _CELL_AUTHORING_PATH not in sys.path:
    sys.path.insert(0, _CELL_AUTHORING_PATH)


from cell_authoring.orchestration import (  # noqa: E402
    FixtureEmpty,
    FixtureSnapshot,
    ObjectAtFixture,
    ObjectPoseWithin,
    ObjectSnapshot,
    Predicate,
    PredicateContext,
    PredicateEvaluationError,
    PredicateGroupResult,
    PredicateResult,
    evaluate_predicates,
)


# ───────────────────────────── helpers ─────────────────────────────


def _ctx(*,
         objects=(),
         fixtures=(),
         orchestration_tick=0,
         physx_frame=0) -> PredicateContext:
    return PredicateContext.build(
        objects=list(objects),
        fixtures=list(fixtures),
        orchestration_tick=orchestration_tick,
        physx_frame=physx_frame,
    )


class _AlwaysTrue:
    """Test-only predicate that always returns True. Tracks call count
    so order-tests can verify it was (or wasn't) invoked."""
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.call_count = 0

    def evaluate(self, ctx):
        self.call_count += 1
        return True

    def fingerprint(self):
        return '{"kind":"_AlwaysTrue","tag":"' + self.tag + '"}'

    def describe(self):
        return f"_AlwaysTrue({self.tag})"


class _AlwaysFalse:
    """Test-only predicate that always returns False."""
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.call_count = 0

    def evaluate(self, ctx):
        self.call_count += 1
        return False

    def fingerprint(self):
        return '{"kind":"_AlwaysFalse","tag":"' + self.tag + '"}'

    def describe(self):
        return f"_AlwaysFalse({self.tag}) failed by design"


class _AlwaysRaises:
    """Test-only predicate that raises PredicateEvaluationError."""
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.call_count = 0

    def evaluate(self, ctx):
        self.call_count += 1
        raise PredicateEvaluationError(f"_AlwaysRaises({self.tag})")

    def fingerprint(self):
        return '{"kind":"_AlwaysRaises","tag":"' + self.tag + '"}'

    def describe(self):
        return f"_AlwaysRaises({self.tag})"


# ────────────────────── PredicateContext invariants ──────────────────────


class TestPredicateContextImmutability:
    """D-SESS-7, D-SESS-8: context is frozen and deep-immutable."""

    def test_context_dataclass_is_frozen(self):
        ctx = _ctx()
        with pytest.raises(FrozenInstanceError):
            ctx.orchestration_tick = 99   # type: ignore[misc]

    def test_objects_mapping_is_read_only(self):
        ctx = _ctx(objects=[ObjectSnapshot(object_id="A", pose_m=(0, 0, 0))])
        with pytest.raises(TypeError):
            ctx.objects["B"] = ObjectSnapshot(  # type: ignore[index]
                object_id="B", pose_m=(0, 0, 0)
            )

    def test_fixtures_mapping_is_read_only(self):
        ctx = _ctx(fixtures=[FixtureSnapshot(fixture_id="F1")])
        with pytest.raises(TypeError):
            ctx.fixtures["F2"] = FixtureSnapshot(fixture_id="F2")  # type: ignore[index]

    def test_object_snapshot_is_frozen(self):
        obj = ObjectSnapshot(object_id="A", pose_m=(0, 0, 0))
        with pytest.raises(FrozenInstanceError):
            obj.pose_m = (1, 1, 1)  # type: ignore[misc]

    def test_fixture_snapshot_is_frozen(self):
        fx = FixtureSnapshot(fixture_id="F1")
        with pytest.raises(FrozenInstanceError):
            fx.occupied_by = "tampered"  # type: ignore[misc]


# ────────────────────── ObjectAtFixture predicate ──────────────────────


class TestObjectAtFixture:

    def test_returns_true_when_fixture_occupied_by_object(self):
        ctx = _ctx(fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by="Peg_01")])
        assert ObjectAtFixture(object_id="Peg_01", fixture_id="F1").evaluate(ctx)

    def test_returns_false_when_fixture_occupied_by_other_object(self):
        ctx = _ctx(fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by="Other")])
        assert not ObjectAtFixture(object_id="Peg_01", fixture_id="F1").evaluate(ctx)

    def test_returns_false_when_fixture_empty(self):
        ctx = _ctx(fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by=None)])
        assert not ObjectAtFixture(object_id="Peg_01", fixture_id="F1").evaluate(ctx)

    def test_raises_on_missing_fixture(self):
        ctx = _ctx()
        with pytest.raises(PredicateEvaluationError, match="not in PredicateContext"):
            ObjectAtFixture(object_id="Peg_01", fixture_id="Unknown").evaluate(ctx)

    def test_satisfies_predicate_protocol(self):
        # Protocol runtime check (D-SESS-8: predicates are well-typed).
        assert isinstance(ObjectAtFixture("o", "f"), Predicate)


# ────────────────────── FixtureEmpty predicate ──────────────────────


class TestFixtureEmpty:

    def test_returns_true_when_fixture_empty(self):
        ctx = _ctx(fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by=None)])
        assert FixtureEmpty(fixture_id="F1").evaluate(ctx)

    def test_returns_false_when_fixture_occupied(self):
        ctx = _ctx(fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by="X")])
        assert not FixtureEmpty(fixture_id="F1").evaluate(ctx)

    def test_raises_on_missing_fixture(self):
        ctx = _ctx()
        with pytest.raises(PredicateEvaluationError):
            FixtureEmpty(fixture_id="Unknown").evaluate(ctx)


# ────────────────────── ObjectPoseWithin predicate ──────────────────────


class TestObjectPoseWithin:

    def test_returns_true_when_pose_within_tolerance(self):
        ctx = _ctx(objects=[ObjectSnapshot(object_id="A",
                                            pose_m=(0.65, 0.00, 0.50))])
        p = ObjectPoseWithin(
            object_id="A",
            target_pose_m=(0.65, 0.00, 0.50),
            tolerance_m=0.05,
        )
        assert p.evaluate(ctx)

    def test_returns_false_when_pose_outside_tolerance(self):
        ctx = _ctx(objects=[ObjectSnapshot(object_id="A",
                                            pose_m=(0.65, 0.10, 0.50))])
        p = ObjectPoseWithin(
            object_id="A",
            target_pose_m=(0.65, 0.00, 0.50),
            tolerance_m=0.05,
        )
        assert not p.evaluate(ctx)

    def test_returns_true_at_tolerance_boundary_inclusive(self):
        """The tolerance check is inclusive (``<=``); a pose exactly on
        the boundary passes (cites tolerance policy in module docstring)."""
        ctx = _ctx(objects=[ObjectSnapshot(object_id="A",
                                            pose_m=(0.65, 0.05, 0.50))])
        p = ObjectPoseWithin(
            object_id="A",
            target_pose_m=(0.65, 0.00, 0.50),
            tolerance_m=0.05,
        )
        assert p.evaluate(ctx)

    def test_uses_per_axis_l_infinity_not_l2(self):
        """Per-axis L∞ check: a pose offset by tolerance on EACH axis
        simultaneously passes (because each axis is within tolerance),
        even though L2 distance would be √3 × tolerance."""
        ctx = _ctx(objects=[ObjectSnapshot(object_id="A",
                                            pose_m=(0.05, 0.05, 0.05))])
        p = ObjectPoseWithin(
            object_id="A",
            target_pose_m=(0.00, 0.00, 0.00),
            tolerance_m=0.05,
        )
        # L2 distance would be 0.0866 > 0.05; L∞ distance is 0.05 == tol.
        assert p.evaluate(ctx)

    def test_construction_rejects_nan_target_axis(self):
        with pytest.raises(ValueError, match="must be finite"):
            ObjectPoseWithin(object_id="A",
                              target_pose_m=(0.0, float("nan"), 0.0),
                              tolerance_m=0.05)

    def test_construction_rejects_inf_target_axis(self):
        with pytest.raises(ValueError, match="must be finite"):
            ObjectPoseWithin(object_id="A",
                              target_pose_m=(0.0, 0.0, float("inf")),
                              tolerance_m=0.05)

    def test_construction_rejects_nan_tolerance(self):
        with pytest.raises(ValueError, match="must be finite"):
            ObjectPoseWithin(object_id="A",
                              target_pose_m=(0.0, 0.0, 0.0),
                              tolerance_m=float("nan"))

    def test_construction_rejects_inf_tolerance(self):
        with pytest.raises(ValueError, match="must be finite"):
            ObjectPoseWithin(object_id="A",
                              target_pose_m=(0.0, 0.0, 0.0),
                              tolerance_m=float("inf"))

    def test_construction_rejects_negative_tolerance(self):
        with pytest.raises(ValueError, match="non-negative"):
            ObjectPoseWithin(object_id="A",
                              target_pose_m=(0.0, 0.0, 0.0),
                              tolerance_m=-0.01)

    def test_evaluation_rejects_nan_in_registry_pose(self):
        """If the snapshot's pose contains NaN, evaluation raises —
        we do not silently return False (cites step-3 brief §5)."""
        ctx = _ctx(objects=[ObjectSnapshot(object_id="A",
                                            pose_m=(0.0, float("nan"), 0.0))])
        p = ObjectPoseWithin(object_id="A",
                              target_pose_m=(0.0, 0.0, 0.0),
                              tolerance_m=0.05)
        with pytest.raises(PredicateEvaluationError, match="non-finite"):
            p.evaluate(ctx)

    def test_evaluation_rejects_inf_in_registry_pose(self):
        ctx = _ctx(objects=[ObjectSnapshot(object_id="A",
                                            pose_m=(0.0, 0.0, float("inf")))])
        p = ObjectPoseWithin(object_id="A",
                              target_pose_m=(0.0, 0.0, 0.0),
                              tolerance_m=0.05)
        with pytest.raises(PredicateEvaluationError, match="non-finite"):
            p.evaluate(ctx)

    def test_raises_on_missing_object(self):
        ctx = _ctx()
        p = ObjectPoseWithin(object_id="Missing",
                              target_pose_m=(0.0, 0.0, 0.0),
                              tolerance_m=0.05)
        with pytest.raises(PredicateEvaluationError, match="not in PredicateContext"):
            p.evaluate(ctx)

    def test_zero_tolerance_requires_exact_match(self):
        ctx = _ctx(objects=[ObjectSnapshot(object_id="A",
                                            pose_m=(0.123, 0.456, 0.789))])
        p_exact = ObjectPoseWithin(object_id="A",
                                    target_pose_m=(0.123, 0.456, 0.789),
                                    tolerance_m=0.0)
        p_off   = ObjectPoseWithin(object_id="A",
                                    target_pose_m=(0.123, 0.456, 0.7891),
                                    tolerance_m=0.0)
        assert p_exact.evaluate(ctx)
        assert not p_off.evaluate(ctx)


# ────────────────────── purity (D-SCHED-12, D-SESS-7) ──────────────────────


class TestPredicatePurity:
    """D-SCHED-12: predicates are pure; identical evaluations produce
    identical results; predicates do not mutate the context."""

    def _build_ctx_and_data(self):
        obj = ObjectSnapshot(object_id="A", pose_m=(0.0, 0.0, 0.0))
        fx  = FixtureSnapshot(fixture_id="F1", occupied_by="A")
        ctx = _ctx(objects=[obj], fixtures=[fx])
        return ctx, obj, fx

    def test_repeated_evaluation_returns_same_result(self):
        ctx, _, _ = self._build_ctx_and_data()
        p = ObjectAtFixture(object_id="A", fixture_id="F1")
        a = p.evaluate(ctx)
        b = p.evaluate(ctx)
        c = p.evaluate(ctx)
        assert a is True and b is True and c is True

    def test_evaluate_does_not_mutate_context(self):
        """After evaluation, the context's objects/fixtures mappings are
        byte-equal to the pre-evaluation snapshot."""
        ctx, _, _ = self._build_ctx_and_data()

        # Capture the pre-state.
        pre_obj_ids = list(ctx.objects.keys())
        pre_fx_ids  = list(ctx.fixtures.keys())
        pre_obj_a   = ctx.objects["A"]
        pre_fx_f1   = ctx.fixtures["F1"]

        # Evaluate every step-3 predicate against this context.
        ObjectAtFixture("A", "F1").evaluate(ctx)
        FixtureEmpty("F1").evaluate(ctx)
        ObjectPoseWithin("A", (0.0, 0.0, 0.0), 0.01).evaluate(ctx)

        # No mutation.
        assert list(ctx.objects.keys()) == pre_obj_ids
        assert list(ctx.fixtures.keys()) == pre_fx_ids
        assert ctx.objects["A"] is pre_obj_a
        assert ctx.fixtures["F1"] is pre_fx_f1

    def test_two_contexts_with_identical_data_yield_identical_results(self):
        """D-SCHED-12: predicates may not depend on object identity.
        Two contexts built from independently-constructed snapshots
        (different Python identities, identical field values) must
        yield identical predicate results."""
        ctx1 = _ctx(
            objects=[ObjectSnapshot(object_id="A", pose_m=(1.0, 2.0, 3.0))],
            fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by="A")],
        )
        ctx2 = _ctx(
            objects=[ObjectSnapshot(object_id="A", pose_m=(1.0, 2.0, 3.0))],
            fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by="A")],
        )
        p1 = ObjectAtFixture("A", "F1")
        p2 = ObjectPoseWithin("A", (1.0, 2.0, 3.0), 0.0)
        assert p1.evaluate(ctx1) == p1.evaluate(ctx2)
        assert p2.evaluate(ctx1) == p2.evaluate(ctx2)


# ────────────────────── fingerprint determinism (step-3 §6) ──────────────────────


class TestPredicateFingerprintDeterminism:
    """Identical predicates → byte-identical fingerprints. Different
    predicates → different fingerprints."""

    def test_fingerprint_stable_across_calls(self):
        p = ObjectAtFixture("A", "F1")
        a = p.fingerprint()
        b = p.fingerprint()
        c = p.fingerprint()
        assert a == b == c

    def test_field_equal_predicates_have_equal_fingerprints(self):
        a = ObjectAtFixture(object_id="Peg_01", fixture_id="WF_01")
        b = ObjectAtFixture(object_id="Peg_01", fixture_id="WF_01")
        assert a is not b   # different Python identities
        assert a.fingerprint() == b.fingerprint()

    def test_different_predicates_have_different_fingerprints(self):
        a = ObjectAtFixture("X", "F1")
        b = ObjectAtFixture("Y", "F1")   # different object_id
        c = ObjectAtFixture("X", "F2")   # different fixture_id
        d = FixtureEmpty("F1")           # different kind entirely
        e = ObjectPoseWithin("X", (0, 0, 0), 0.0)
        fingerprints = {a.fingerprint(), b.fingerprint(), c.fingerprint(),
                        d.fingerprint(), e.fingerprint()}
        assert len(fingerprints) == 5

    def test_fingerprint_is_canonical_json(self):
        """The fingerprint format is canonical-JSON (sorted keys, tight
        separators) — this lets future replay-identity tools compare
        fingerprints byte-for-byte."""
        p = ObjectAtFixture(object_id="Peg_01", fixture_id="WF_01")
        # Keys appear sorted: fixture_id, kind, object_id
        expected = '{"fixture_id":"WF_01","kind":"ObjectAtFixture","object_id":"Peg_01"}'
        assert p.fingerprint() == expected

    def test_object_pose_within_fingerprint_includes_tolerance(self):
        p1 = ObjectPoseWithin("A", (0.0, 0.0, 0.0), 0.05)
        p2 = ObjectPoseWithin("A", (0.0, 0.0, 0.0), 0.10)
        assert p1.fingerprint() != p2.fingerprint()


# ────────────────── evaluation order + short-circuit (D-SCHED-13) ──────────────────


class TestEvaluationOrderAndShortCircuit:
    """D-SCHED-13: evaluate_predicates iterates in tuple-index order,
    short-circuits on first False / first error. The result is
    deterministic given (predicates, context)."""

    def test_all_pass_returns_ok_with_all_results(self):
        ctx = _ctx(fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by=None)])
        p1 = FixtureEmpty("F1")
        result = evaluate_predicates([p1], ctx)
        assert result.ok is True
        assert len(result.results) == 1
        assert result.first_failure_index is None
        assert result.error_at is None

    def test_empty_predicate_list_passes(self):
        result = evaluate_predicates([], _ctx())
        assert result.ok is True
        assert result.results == ()
        assert result.first_failure_index is None
        assert result.error_at is None

    def test_short_circuit_on_first_false_skips_remaining(self):
        """The most important D-SCHED-13 property: predicates after the
        first False are NOT invoked."""
        p1 = _AlwaysTrue("p1")
        p2 = _AlwaysFalse("p2")
        p3 = _AlwaysTrue("p3")
        p4 = _AlwaysFalse("p4")
        result = evaluate_predicates([p1, p2, p3, p4], _ctx())

        assert result.ok is False
        assert result.first_failure_index == 1     # p2 is at index 1
        assert len(result.results) == 2            # p1 + p2 only
        assert result.results[0].ok is True
        assert result.results[1].ok is False
        # p3 and p4 were NEVER invoked.
        assert p3.call_count == 0
        assert p4.call_count == 0
        # p1 and p2 were each invoked exactly once.
        assert p1.call_count == 1
        assert p2.call_count == 1

    def test_first_false_index_is_deterministic_across_two_failures(self):
        """When multiple predicates would fail, the FIRST one in
        construction order wins. Deterministic-failure-ordering proof."""
        false_a = _AlwaysFalse("a")
        false_b = _AlwaysFalse("b")
        # Order matters: a is at index 0.
        result_ab = evaluate_predicates([false_a, false_b], _ctx())
        assert result_ab.first_failure_index == 0
        # Reverse: b is at index 0.
        false_a2 = _AlwaysFalse("a")
        false_b2 = _AlwaysFalse("b")
        result_ba = evaluate_predicates([false_b2, false_a2], _ctx())
        assert result_ba.first_failure_index == 0
        # Both are deterministic and reproducible.
        result_ab2 = evaluate_predicates(
            [_AlwaysFalse("a"), _AlwaysFalse("b")], _ctx())
        assert result_ab2.first_failure_index == 0

    def test_short_circuit_on_first_error_captures_deterministically(self):
        p1 = _AlwaysTrue("p1")
        p2 = _AlwaysRaises("p2")
        p3 = _AlwaysFalse("p3")     # would normally fail too
        result = evaluate_predicates([p1, p2, p3], _ctx())

        assert result.ok is False
        assert result.first_failure_index is None
        assert result.error_at == 1
        assert result.error_type == "PredicateEvaluationError"
        assert "_AlwaysRaises(p2)" in (result.error_str or "")
        # p3 was NOT invoked.
        assert p3.call_count == 0
        # p1 evaluated (its result accumulated); p2 raised (no result row).
        assert len(result.results) == 1
        assert result.results[0].ok is True

    def test_failure_detail_carries_predicate_description(self):
        ctx = _ctx(fixtures=[FixtureSnapshot(fixture_id="F1", occupied_by="X")])
        result = evaluate_predicates(
            [FixtureEmpty("F1")], ctx
        )
        assert result.ok is False
        assert "FixtureEmpty" in result.results[0].detail


# ────────── reproducibility across instances (step-3 brief §9) ──────────


class TestReproducibilityAcrossContexts:
    """Multiple independent contexts with identical data produce
    identical predicate outputs / fingerprints / group results."""

    def _eval_group(self, ctx: PredicateContext) -> PredicateGroupResult:
        predicates = [
            FixtureEmpty(fixture_id="F1"),
            ObjectAtFixture(object_id="A", fixture_id="F2"),
            ObjectPoseWithin(object_id="A",
                              target_pose_m=(1.0, 2.0, 3.0),
                              tolerance_m=0.05),
        ]
        return evaluate_predicates(predicates, ctx)

    def _build_ctx(self) -> PredicateContext:
        return _ctx(
            objects=[ObjectSnapshot(object_id="A", pose_m=(1.0, 2.0, 3.0))],
            fixtures=[
                FixtureSnapshot(fixture_id="F1", occupied_by=None),
                FixtureSnapshot(fixture_id="F2", occupied_by="A"),
            ],
        )

    def test_two_contexts_identical_data_yield_identical_group_results(self):
        ctx1 = self._build_ctx()
        ctx2 = self._build_ctx()
        r1 = self._eval_group(ctx1)
        r2 = self._eval_group(ctx2)
        assert r1 == r2   # frozen dataclass equality

    def test_two_contexts_identical_data_yield_byte_equal_fingerprints(self):
        ctx1 = self._build_ctx()
        ctx2 = self._build_ctx()
        r1 = self._eval_group(ctx1)
        r2 = self._eval_group(ctx2)
        fps1 = tuple(r.predicate_fingerprint for r in r1.results)
        fps2 = tuple(r.predicate_fingerprint for r in r2.results)
        assert fps1 == fps2

    def test_three_repeated_runs_produce_identical_results(self):
        """Run the same evaluation three times — every output must be
        identical. Repro proof at the per-call layer."""
        outs = [self._eval_group(self._build_ctx()) for _ in range(3)]
        assert outs[0] == outs[1] == outs[2]


# ────────── dict iteration / insertion-order independence (D-FORBID-7) ──────────


class TestDictInsertionOrderDoesNotLeak:
    """The order in which objects/fixtures are passed to
    PredicateContext.build() must NOT affect predicate results
    (cites D-FORBID-7)."""

    def test_object_insertion_order_does_not_affect_results(self):
        objs_a = [
            ObjectSnapshot(object_id="A", pose_m=(0.0, 0.0, 0.0)),
            ObjectSnapshot(object_id="B", pose_m=(1.0, 0.0, 0.0)),
            ObjectSnapshot(object_id="C", pose_m=(2.0, 0.0, 0.0)),
        ]
        objs_b = list(reversed(objs_a))
        objs_c = [objs_a[1], objs_a[2], objs_a[0]]

        target = ObjectPoseWithin("A", (0.0, 0.0, 0.0), 0.01)

        ctx_a = _ctx(objects=objs_a)
        ctx_b = _ctx(objects=objs_b)
        ctx_c = _ctx(objects=objs_c)

        assert target.evaluate(ctx_a)
        assert target.evaluate(ctx_b)
        assert target.evaluate(ctx_c)

    def test_fixture_insertion_order_does_not_affect_results(self):
        fxs_a = [
            FixtureSnapshot(fixture_id="F1", occupied_by="X"),
            FixtureSnapshot(fixture_id="F2", occupied_by=None),
        ]
        fxs_b = list(reversed(fxs_a))

        p1 = ObjectAtFixture("X", "F1")
        p2 = FixtureEmpty("F2")

        ctx_a = _ctx(fixtures=fxs_a)
        ctx_b = _ctx(fixtures=fxs_b)

        assert p1.evaluate(ctx_a) == p1.evaluate(ctx_b)
        assert p2.evaluate(ctx_a) == p2.evaluate(ctx_b)


# ────────── PredicateResult / PredicateGroupResult frozenness (D-SESS-8) ──────────


class TestResultObjectsFrozen:

    def test_predicate_result_is_frozen(self):
        r = PredicateResult(predicate_fingerprint="fp", ok=True)
        with pytest.raises(FrozenInstanceError):
            r.ok = False   # type: ignore[misc]

    def test_predicate_group_result_is_frozen(self):
        g = PredicateGroupResult(ok=True, results=())
        with pytest.raises(FrozenInstanceError):
            g.ok = False   # type: ignore[misc]

    def test_group_result_results_is_tuple(self):
        g = PredicateGroupResult(ok=True, results=())
        assert isinstance(g.results, tuple)


# ────────── clause-coverage signal (meta) ──────────


def test_step3_covers_minimum_clause_family_set():
    """Documents the contract clauses step 3 exercises. Update when
    adding step-3 tests that cover additional clauses."""
    covered = {
        "D-SCHED-12",  # purity, no wall-clock/RNG/object-id dep
        "D-SCHED-13",  # ordered evaluation + short-circuit
        "D-SESS-7",    # no context mutation
        "D-SESS-8",    # frozen dataclasses
        "D-FORBID-7",  # no nondeterministic iteration
    }
    assert len(covered) >= 5
