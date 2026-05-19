"""Deterministic predicate primitives (Phase 4B step 3).

Predicates are **pure-function decision primitives** that orchestration
will later use for precondition / postcondition checks at task-node
boundaries. Step 3 ships exactly the surface the contract pins:

  * one ``Predicate`` Protocol (no abstract base; concrete predicates
    are independent frozen dataclasses)
  * one ``PredicateContext`` (frozen, deep-immutable view over a
    snapshot of objects + fixtures)
  * exactly three concrete predicates:
        - ``ObjectAtFixture``
        - ``FixtureEmpty``
        - ``ObjectPoseWithin``
  * one ``evaluate_predicates`` aggregator with deterministic
    short-circuit semantics (D-SCHED-13)
  * one ``PredicateEvaluationError`` for context-mismatch failures
  * a ``fingerprint()`` method per predicate, returning canonical JSON

Contract clauses honoured
-------------------------
D-SCHED-12 — Predicates are pure functions of the registry/context. No
              PhysX touch, no wall-clock, no RNG, no Python-object-identity
              dependence.
D-SCHED-13 — Predicate-list evaluation preserves construction order;
              short-circuits on first False.
D-SESS-7   — Predicates may not mutate the context (they don't have a
              mutable reference to mutate; PredicateContext exposes only
              read-only mappings).
D-SESS-8   — All predicates and snapshots are ``@dataclass(frozen=True,
              slots=True)``.
D-FORBID-3 — No hidden mutable caches: predicates are stateless.
D-FORBID-6 — No wall-clock-dependent behavior.
D-FORBID-7 — No nondeterministic iteration (we use Mapping views; tests
              prove dict-insertion-order independence).
D-FORBID-8 — No hidden replay dependencies: PredicateContext is the
              complete input.

Explicitly deferred (documented to prevent implicit re-invention)
-----------------------------------------------------------------
* Compound / boolean-tree predicates (AND/OR/NOT/XOR over predicates).
* Scheduler integration — Phase 4B step 5 wires predicate evaluation
  into the scheduler; step 3 only defines the primitives.
* Dynamic predicates whose result depends on history.
* Live-sensor predicates (would require PhysX touch — forbidden).
* Temporal predicates ("X for at least N ticks").
* Learned / probabilistic predicates.
* Async / streaming / reactive predicates.
* Symbolic / SAT / constraint solvers.
* Predicate caching / memoization (Step 3 evaluations are stateless;
  callers may memoize at a higher layer if needed, but the predicate
  layer itself does not cache).
* Predicate deserialisation from string fingerprints (Step 3 only
  serialises via ``fingerprint()``; reconstruction is a later step).
* Float normalisation beyond the ``allow_nan=False`` rule and the
  ``isfinite`` rejection in ``ObjectPoseWithin``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol, Sequence, runtime_checkable

from .package import canonical_dumps


# ───────────────────────────── errors ─────────────────────────────


class PredicateEvaluationError(RuntimeError):
    """Raised when a predicate cannot evaluate against the given context.

    Typical causes (cites D-SCHED-12 purity invariant):

      * the predicate references an ``object_id`` or ``fixture_id`` not
        present in :class:`PredicateContext`;
      * the context contains a non-finite (NaN / Inf) numeric value
        that the predicate cannot interpret.

    The aggregator :py:func:`evaluate_predicates` captures this
    exception deterministically into the :class:`PredicateGroupResult`
    (cites D-SCHED-13 deterministic failure propagation).
    """


# ───────────────────────────── snapshots ─────────────────────────────


@dataclass(frozen=True, slots=True)
class ObjectSnapshot:
    """Immutable view of one object's state at predicate-evaluation time.

    Predicates **only** operate on snapshots — never on live registry
    objects, never on PhysX handles (cites D-SCHED-12, D-FORBID-6).
    The orchestration layer (step 6+) will provide a converter from the
    Phase 4A ``CellStateRegistry.objects`` map into a tuple of
    :class:`ObjectSnapshot`s; step 3 keeps the types independent.
    """
    object_id: str
    pose_m:    tuple[float, float, float]
    yaw_rad:   float = 0.0


@dataclass(frozen=True, slots=True)
class FixtureSnapshot:
    """Immutable view of one fixture's state at predicate-evaluation time.

    ``occupied_by`` is either an ``object_id`` (the object placed on
    this fixture) or ``None`` (fixture empty). Step 3's
    :class:`ObjectAtFixture` and :class:`FixtureEmpty` predicates
    consult this single field.
    """
    fixture_id:  str
    occupied_by: str | None = None


# ───────────────────────────── context ─────────────────────────────


@dataclass(frozen=True, slots=True)
class PredicateContext:
    """Frozen, deep-immutable evaluation context.

    Contract guarantees (cites D-SCHED-12):

      * the dataclass itself is frozen (D-SESS-8) — its attributes
        cannot be reassigned;
      * ``objects`` and ``fixtures`` are :class:`types.MappingProxyType`
        instances wrapping internal dicts — direct mutation raises
        ``TypeError``;
      * snapshots inside the mappings are themselves frozen dataclasses;
      * no field references PhysX handles, USD stages, threads,
        sockets, or wall-clock sources.

    Construct via :py:meth:`build` (recommended). Direct construction
    is permitted but caller must pre-wrap the mappings.
    """
    objects:            Mapping[str, ObjectSnapshot]
    fixtures:           Mapping[str, FixtureSnapshot]
    orchestration_tick: int = 0
    physx_frame:        int = 0

    @classmethod
    def build(
        cls,
        *,
        objects:            Iterable[ObjectSnapshot] = (),
        fixtures:           Iterable[FixtureSnapshot] = (),
        orchestration_tick: int = 0,
        physx_frame:        int = 0,
    ) -> "PredicateContext":
        """Friendly constructor — accepts iterables of snapshots and
        wraps the resulting mappings in :class:`MappingProxyType`.

        Deterministic discipline: the iteration order of ``objects`` /
        ``fixtures`` does not affect predicate results (proved by
        ``TestContextImmutability::test_dict_insertion_order_does_not_leak``
        in the step-3 test suite). Iteration over the proxied mapping
        happens in dict insertion order, but no predicate in step 3
        iterates the mapping — they all use ``.get(...)`` lookup,
        which is order-independent.
        """
        obj_map: dict[str, ObjectSnapshot]   = {o.object_id:   o for o in objects}
        fix_map: dict[str, FixtureSnapshot]  = {f.fixture_id:  f for f in fixtures}
        return cls(
            objects=MappingProxyType(obj_map),
            fixtures=MappingProxyType(fix_map),
            orchestration_tick=orchestration_tick,
            physx_frame=physx_frame,
        )


# ───────────────────────────── Predicate Protocol ─────────────────────────────


@runtime_checkable
class Predicate(Protocol):
    """Pure-function decision primitive (cites D-SCHED-12).

    Three methods, all pure:

      * :py:meth:`evaluate` returns ``True`` or ``False`` for one
        context. Raises :class:`PredicateEvaluationError` when the
        context lacks the data the predicate needs.
      * :py:meth:`fingerprint` returns a canonical JSON string that
        uniquely identifies this predicate's *configuration* (its
        identity), independent of any context. Two equal predicates
        produce byte-identical fingerprints (cites step-3 brief §6).
      * :py:meth:`describe` returns a short human-readable failure
        explanation, used when a predicate returns ``False``. Pure;
        no I/O, no side effects.

    Implementations are frozen dataclasses (D-SESS-8). No predicate
    in step 3 holds any mutable state.
    """

    def evaluate(self, ctx: PredicateContext) -> bool: ...

    def fingerprint(self) -> str: ...

    def describe(self) -> str: ...


# ───────────────────────────── results ─────────────────────────────


@dataclass(frozen=True, slots=True)
class PredicateResult:
    """Outcome of evaluating one predicate against one context.

    Frozen (D-SESS-8). Fingerprint is derived from the predicate's
    own ``fingerprint()`` — two field-equal predicates yield equal
    ``PredicateResult.predicate_fingerprint`` values.

    Fields
    ------
    predicate_fingerprint:
        Canonical JSON identity of the predicate at evaluation time.
    ok:
        ``True`` iff the predicate returned ``True``.
    detail:
        Human-readable failure explanation. Empty string when ``ok``.
    """
    predicate_fingerprint: str
    ok:                    bool
    detail:                str = ""


@dataclass(frozen=True, slots=True)
class PredicateGroupResult:
    """Aggregated outcome of evaluating an ordered list of predicates
    against one context. Frozen (D-SESS-8).

    Aggregation semantics (cites D-SCHED-13):

      * predicates are evaluated in **tuple-index order**;
      * evaluation **short-circuits on first False** — predicates with
        higher index are not invoked;
      * evaluation **short-circuits on first PredicateEvaluationError**
        — the error is captured into ``error_at`` / ``error_type`` /
        ``error_str`` and re-raise is the caller's choice. Predicates
        with higher index are not invoked.

    Fields
    ------
    ok:
        ``True`` iff every evaluated predicate returned ``True`` and
        no predicate raised.
    results:
        Tuple of per-predicate results, in evaluation order. Length is
        ``index_of_first_failure + 1`` on failure, ``len(predicates)``
        on full pass. **On an evaluation error, ``results`` excludes
        the failing predicate** — the error is captured separately.
    first_failure_index:
        Index of the first predicate that returned ``False``, or
        ``None`` if no predicate returned ``False`` (group passed, or
        an error short-circuited before any False).
    error_at:
        Index of the predicate that raised, or ``None``.
    error_type:
        Type name of the raised exception, or ``None``.
    error_str:
        ``str(exc)`` of the raised exception, or ``None``.
    """
    ok:                  bool
    results:             tuple[PredicateResult, ...]
    first_failure_index: int | None = None
    error_at:            int | None = None
    error_type:          str | None = None
    error_str:           str | None = None


def evaluate_predicates(
    predicates: Sequence[Predicate],
    ctx: PredicateContext,
) -> PredicateGroupResult:
    """Deterministic ordered evaluation. Cites D-SCHED-13.

    Iterates ``predicates`` in **index order** (the caller's tuple /
    list construction order); evaluates each via
    :py:meth:`Predicate.evaluate`. Short-circuits on:

      * first ``False`` returned (records the index, returns),
      * first :class:`PredicateEvaluationError` raised (captures the
        error info, returns).

    The aggregator itself is **pure**: same ``predicates`` + same
    ``ctx`` → byte-equal :class:`PredicateGroupResult`.
    """
    accumulated: list[PredicateResult] = []
    for i, p in enumerate(predicates):
        try:
            ok = p.evaluate(ctx)
        except PredicateEvaluationError as exc:
            # D-SCHED-13 deterministic error propagation: capture and
            # return; do not invoke predicates with higher index.
            return PredicateGroupResult(
                ok=False,
                results=tuple(accumulated),
                first_failure_index=None,
                error_at=i,
                error_type=type(exc).__name__,
                error_str=str(exc),
            )

        result = PredicateResult(
            predicate_fingerprint=p.fingerprint(),
            ok=ok,
            detail=("" if ok else p.describe()),
        )
        accumulated.append(result)
        if not ok:
            # D-SCHED-13 short-circuit on first False.
            return PredicateGroupResult(
                ok=False,
                results=tuple(accumulated),
                first_failure_index=i,
            )

    return PredicateGroupResult(
        ok=True,
        results=tuple(accumulated),
    )


# ───────────────────────────── concrete predicates ─────────────────────────────


@dataclass(frozen=True, slots=True)
class ObjectAtFixture:
    """True iff ``ctx.fixtures[fixture_id].occupied_by == object_id``.

    Raises :class:`PredicateEvaluationError` if ``fixture_id`` is not
    in the context.
    """
    object_id:  str
    fixture_id: str

    def evaluate(self, ctx: PredicateContext) -> bool:
        fixture = ctx.fixtures.get(self.fixture_id)
        if fixture is None:
            raise PredicateEvaluationError(
                f"fixture_id={self.fixture_id!r} not in PredicateContext "
                f"(ObjectAtFixture)"
            )
        return fixture.occupied_by == self.object_id

    def fingerprint(self) -> str:
        return canonical_dumps({
            "kind":       "ObjectAtFixture",
            "object_id":  self.object_id,
            "fixture_id": self.fixture_id,
        })

    def describe(self) -> str:
        return (
            f"ObjectAtFixture(object_id={self.object_id!r}, "
            f"fixture_id={self.fixture_id!r}): not satisfied"
        )


@dataclass(frozen=True, slots=True)
class FixtureEmpty:
    """True iff ``ctx.fixtures[fixture_id].occupied_by is None``.

    Raises :class:`PredicateEvaluationError` if ``fixture_id`` is not
    in the context.
    """
    fixture_id: str

    def evaluate(self, ctx: PredicateContext) -> bool:
        fixture = ctx.fixtures.get(self.fixture_id)
        if fixture is None:
            raise PredicateEvaluationError(
                f"fixture_id={self.fixture_id!r} not in PredicateContext "
                f"(FixtureEmpty)"
            )
        return fixture.occupied_by is None

    def fingerprint(self) -> str:
        return canonical_dumps({
            "kind":       "FixtureEmpty",
            "fixture_id": self.fixture_id,
        })

    def describe(self) -> str:
        return f"FixtureEmpty(fixture_id={self.fixture_id!r}): not satisfied"


@dataclass(frozen=True, slots=True)
class ObjectPoseWithin:
    """True iff ``object``'s pose is within ``tolerance_m`` of the
    target pose, **per-axis** (L∞ / Chebyshev) — i.e. for every axis
    *i*, ``abs(pose[i] - target[i]) <= tolerance_m``.

    Tolerance policy (cites D-SCHED-12, step-3 brief §5)
    ----------------------------------------------------
    * **Metric**: L∞ per-axis. Chosen over L2 because L2 would require
      ``math.sqrt`` whose IEEE-754 bit-level result varies across
      libm implementations; L∞ uses only ``abs`` + ``<=``, both of
      which are bit-deterministic for finite IEEE-754 floats.
      Per-axis matches the Phase 3M placement gate
      (``abs(dx) > TOL or abs(dy) > TOL``).
    * **Boundary**: ``<= tolerance_m`` (inclusive). A pose exactly on
      the tolerance boundary passes.
    * **NaN / Inf**:
        - **At construction**: any non-finite value in
          ``target_pose_m`` or in ``tolerance_m`` raises ``ValueError``.
          Negative ``tolerance_m`` also raises ``ValueError`` — a
          predicate with negative tolerance can never be True; that is
          ill-formed by construction.
        - **At evaluation**: any non-finite value in the snapshot's
          ``pose_m`` raises :class:`PredicateEvaluationError`. We do
          not silently return False — the registry should never
          contain non-finite poses; surfacing the violation loudly
          prevents silent bug propagation.

    Sophisticated numeric normalization (ULP-aware comparison,
    quaternion-aware orientation tolerance, etc.) is **explicitly
    deferred** (see module docstring).
    """
    object_id:     str
    target_pose_m: tuple[float, float, float]
    tolerance_m:   float

    def __post_init__(self) -> None:
        # NaN/Inf rejection at CONSTRUCTION time. (Cites step-3 brief §5.)
        for axis, v in enumerate(self.target_pose_m):
            if not math.isfinite(v):
                raise ValueError(
                    f"ObjectPoseWithin.target_pose_m[{axis}] must be finite; "
                    f"got {v!r}"
                )
        if not math.isfinite(self.tolerance_m):
            raise ValueError(
                f"ObjectPoseWithin.tolerance_m must be finite; "
                f"got {self.tolerance_m!r}"
            )
        if self.tolerance_m < 0:
            raise ValueError(
                f"ObjectPoseWithin.tolerance_m must be non-negative; "
                f"got {self.tolerance_m!r}"
            )

    def evaluate(self, ctx: PredicateContext) -> bool:
        obj = ctx.objects.get(self.object_id)
        if obj is None:
            raise PredicateEvaluationError(
                f"object_id={self.object_id!r} not in PredicateContext "
                f"(ObjectPoseWithin)"
            )
        for axis, v in enumerate(obj.pose_m):
            if not math.isfinite(v):
                raise PredicateEvaluationError(
                    f"object_id={self.object_id!r} pose_m[{axis}] is "
                    f"non-finite ({v!r}); registry contained an invalid "
                    f"pose (ObjectPoseWithin)"
                )
        # L∞ per-axis tolerance check. Order of axes is fixed (0, 1, 2).
        # Short-circuits on the first axis exceeding tolerance, which
        # is deterministic and does not affect the boolean result.
        for axis in range(3):
            if abs(obj.pose_m[axis] - self.target_pose_m[axis]) > self.tolerance_m:
                return False
        return True

    def fingerprint(self) -> str:
        # ``list(...)`` here is for JSON compatibility; canonical_dumps
        # serializes the same bytes whether the input is tuple-of-floats
        # or list-of-floats. Using a list makes the JSON output read
        # naturally.
        return canonical_dumps({
            "kind":          "ObjectPoseWithin",
            "object_id":     self.object_id,
            "target_pose_m": list(self.target_pose_m),
            "tolerance_m":   self.tolerance_m,
        })

    def describe(self) -> str:
        return (
            f"ObjectPoseWithin(object_id={self.object_id!r}, "
            f"target_pose_m={self.target_pose_m!r}, "
            f"tolerance_m={self.tolerance_m!r}): not satisfied"
        )
