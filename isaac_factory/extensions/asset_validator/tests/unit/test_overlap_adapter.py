"""Integration tests for `PhysXContactSource` against synthetic .usda fixtures.

These tests REQUIRE Isaac Sim Kit Python (Runtime B). Outside Runtime B
the entire module is skipped at collection time (`isaacsim` is the
sentinel — the workspace's conda env doesn't ship a Kit-capable
SimulationApp).

Run under Kit Python::

    $ISAAC_PATH/python.sh -m pytest \
        isaac_factory/extensions/asset_validator/tests/unit/test_overlap_adapter.py -v

Under Runtime A, `python -m pytest` simply skips this file.

The session fixture `sim_app` boots SimulationApp once for the whole
test module; individual tests open a fixture stage into the shared
`omni.usd` context, build a `World`, instantiate `PhysXContactSource`,
step physics, and assert the captured contacts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# `isaacsim` only resolves in Kit Python. Use pytestmark rather than
# pytest.importorskip — the latter raises Skipped at module load, and
# under pytest 9.0.2 that exception can bleed into the collection of
# sibling test modules. pytestmark cleanly skips only THIS module.
try:
    import isaacsim  # noqa: F401
    _ISAAC_AVAILABLE = True
except ImportError:
    _ISAAC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _ISAAC_AVAILABLE,
    reason="Kit Python (Runtime B) required — isaacsim package not importable",
)


_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "overlap"


# ============================================================ sim_app ==


@pytest.fixture(scope="module")
def sim_app():
    """Boot SimulationApp once for all tests in this module.

    Module scope (not session) so the cleanup runs at module end and we
    don't leak the app across the full test run when this module is the
    only Kit-requiring one.
    """
    try:
        from isaacsim import SimulationApp
        app = SimulationApp({"headless": True})
    except Exception as e:                                  # pragma: no cover
        pytest.skip(f"SimulationApp boot failed: {e}")
    yield app
    try:
        app.close()
    except Exception:                                       # pragma: no cover
        pass


@pytest.fixture()
def opened_stage(sim_app, request):
    """Open a fixture .usda into the shared omni.usd context and yield the
    pxr.Usd.Stage. Closes / replaces with a fresh stage on teardown.

    Usage:
        @pytest.mark.parametrize("fixture_name", ["clean_separated"])
        def test_thing(opened_stage, fixture_name): ...

    or:
        def test_thing(opened_stage):
            opened_stage("penetrating_pair")
            ...
    """
    import omni.usd
    ctx = omni.usd.get_context()

    def _open(name: str):
        path = _FIXTURE_DIR / f"{name}.usda"
        assert path.is_file(), f"missing fixture: {path}"
        # omni.usd.UsdContext.open_stage return type varies:
        #   Isaac Sim 5.0+: returns a single `bool`
        #   Isaac Sim <5  : returns a `(bool, error)` tuple
        # Accept both so the fixture is forward- and backward-compatible.
        rv = ctx.open_stage(str(path))
        if isinstance(rv, tuple):
            result, error = rv
            assert result, f"open_stage failed: {error}"
        else:
            assert rv, f"open_stage failed for: {path}"
        return ctx.get_stage()

    yield _open

    # Teardown — drop the stage so subsequent tests start clean.
    ctx.new_stage()


def _build_source_and_run(stage, *, steps: int = 5, seed: int = 0,
                          allowed_pairs=frozenset()):
    """Helper: build World + source, run N steps, return (contacts, source)."""
    from isaacsim.core.api import World
    from asset_validator.adapters.physx_contact_source import PhysXContactSource

    world = World()
    source = PhysXContactSource(stage=stage)
    source.setup(seed=seed)
    for _ in range(steps):
        source.step()
    contacts = list(source.query_contacts())
    return contacts, source, world


# ====================================================== clean stage ==


class TestCleanSeparated:
    def test_no_contacts(self, opened_stage):
        stage = opened_stage("clean_separated")
        contacts, source, world = _build_source_and_run(stage)
        try:
            assert contacts == [], f"expected no contacts; got: {contacts}"
        finally:
            source.close()
            world.clear_instance()


# ====================================================== penetrating ==


class TestPenetratingPair:
    def test_overlap_detected(self, opened_stage):
        stage = opened_stage("penetrating_pair")
        contacts, source, world = _build_source_and_run(stage)
        try:
            assert len(contacts) == 1, f"expected 1 pair, got {len(contacts)}"
            p = contacts[0]
            # Cubes overlap by 0.5m initially; PhysX may have already pushed
            # them apart slightly by the time we sample. Expect > 0.1m.
            assert p.penetration_depth > 0.1, p.penetration_depth
            # Path canonicalisation: /World/A < /World/B
            assert p.prim_a == "/World/A"
            assert p.prim_b == "/World/B"
            # Normal should be roughly (±1, 0, 0)
            assert p.contact_normal is not None
            assert abs(p.contact_normal[0]) > 0.99
            assert abs(p.contact_normal[1]) < 0.05
            assert abs(p.contact_normal[2]) < 0.05
        finally:
            source.close()
            world.clear_instance()

    def test_validator_fires_pen_depth_exceeded(self, opened_stage):
        """End-to-end: PhysX source → OverlapValidator → Issue."""
        from asset_validator import (
            AcceptanceCriteria, OverlapValidator, ValidationContext,
        )
        from asset_validator.validators.overlap import CODE_PEN_DEPTH_EXCEEDED

        stage = opened_stage("penetrating_pair")
        contacts, source, world = _build_source_and_run(stage)
        try:
            assert len(contacts) == 1

            # Build a context that re-uses the captured contacts as a
            # frozen ContactSource — keeps the test deterministic
            # independent of further stepping.
            class _Frozen:
                def setup(self, *, seed): pass
                def step(self): pass
                def query_contacts(self): return contacts

            ctx = ValidationContext(
                asset_uri="test://penetrating",
                criteria=AcceptanceCriteria(),
                contact_source=_Frozen(),
            )
            issues = OverlapValidator(ctx.criteria).run(ctx)
            codes = [i.code for i in issues]
            assert CODE_PEN_DEPTH_EXCEEDED in codes
        finally:
            source.close()
            world.clear_instance()


# ======================================================== tight-fit ==


class TestTightFit:
    def test_fit_pair_classified_as_warn(self, opened_stage):
        """A press-fit pair listed in `expects_contact` triggers the WARN
        path (PEN_DEPTH_EXCEEDED_FIT), not the FAIL path."""
        from asset_validator import (
            AcceptanceCriteria, OverlapValidator, ValidationContext,
        )
        from asset_validator.validators.overlap import (
            CODE_PEN_DEPTH_EXCEEDED,
            CODE_PEN_DEPTH_EXCEEDED_FIT,
        )

        stage = opened_stage("tight_fit_pair")
        contacts, source, world = _build_source_and_run(stage)
        try:
            assert len(contacts) == 1

            class _Frozen:
                def setup(self, *, seed): pass
                def step(self): pass
                def query_contacts(self): return contacts

            ctx = ValidationContext(
                asset_uri="test://tight_fit",
                criteria=AcceptanceCriteria(),
                contact_source=_Frozen(),
                allowed_contact_pairs=frozenset({
                    frozenset({"/World/Bracket", "/World/Pin"}),
                }),
            )
            issues = OverlapValidator(ctx.criteria).run(ctx)
            codes = [i.code for i in issues]
            # The fit pair fires WARN, not the stricter FAIL.
            assert CODE_PEN_DEPTH_EXCEEDED_FIT in codes
            assert CODE_PEN_DEPTH_EXCEEDED not in codes
        finally:
            source.close()
            world.clear_instance()


# ====================================================== determinism ==


class TestDeterminism:
    def test_same_stage_two_runs_same_pairs(self, opened_stage):
        from asset_validator.adapters.physx_contact_source import PhysXContactSource
        from isaacsim.core.api import World

        def _run_once():
            stage = opened_stage("penetrating_pair")
            world = World()
            source = PhysXContactSource(stage=stage)
            source.setup(seed=0)
            for _ in range(5):
                source.step()
            contacts = list(source.query_contacts())
            source.close()
            world.clear_instance()
            return contacts

        a = _run_once()
        b = _run_once()
        # Path canonicalisation + sort must yield the same pair list.
        assert [(p.prim_a, p.prim_b) for p in a] == [(p.prim_a, p.prim_b) for p in b]


# ======================================================== lifecycle ==


class TestLifecycle:
    def test_setup_clears_captured(self, opened_stage):
        from asset_validator.adapters.physx_contact_source import PhysXContactSource
        from isaacsim.core.api import World

        stage = opened_stage("penetrating_pair")
        world = World()
        source = PhysXContactSource(stage=stage)
        source.setup(seed=0)
        # Step once → capture some events
        source.step()
        # ...then setup() again should wipe them
        source.setup(seed=0)
        # query_contacts() after a fresh setup but no step => empty
        assert list(source.query_contacts()) == []
        source.close()
        world.clear_instance()

    def test_context_manager_unsubscribes(self, opened_stage):
        from asset_validator.adapters.physx_contact_source import PhysXContactSource
        from isaacsim.core.api import World

        stage = opened_stage("clean_separated")
        world = World()
        with PhysXContactSource(stage=stage) as source:
            assert source._sub is not None
        assert source._sub is None
        world.clear_instance()
