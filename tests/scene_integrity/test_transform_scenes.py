"""Scene-level integration tests for TransformValidator.

Builds multi-prim USD-like scenes (via the StageInspector mock) and
verifies isolation, cascade, and severity behaviour at the scene level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from asset_validator import (
    AcceptanceCriteria,
    StageInspector,
    TransformOp,
    TransformValidator,
    Severity,
    ValidationContext,
    XformablePrim,
)
from asset_validator.validators.transform import (
    CODE_CASCADE_INVALID_WORLD,
    CODE_FLOATING_HEURISTIC,
    CODE_NAN_VALUE,
    CODE_NON_POSITIVE_SCALE,
    CODE_ZERO_SCALE,
)


# --------------------------------------------------------------- mock --


@dataclass
class _Stage:
    prims: list[XformablePrim] = field(default_factory=list)

    def iter_xformable_prims(self) -> Iterable[XformablePrim]:
        return list(self.prims)


_: StageInspector = _Stage()


# --- op helpers ---


def _translate(values, **kw) -> TransformOp:
    return TransformOp(
        op_name="xformOp:translate",
        op_type="translate",
        values=tuple(float(v) for v in values),
        **kw,
    )


def _scale(values=(1.0, 1.0, 1.0)) -> TransformOp:
    return TransformOp(
        op_name="xformOp:scale", op_type="scale",
        values=tuple(float(v) for v in values),
    )


def _prim(path, ops=(), **kw) -> XformablePrim:
    return XformablePrim(path=path, ops=tuple(ops), **kw)


def _run(prims):
    ctx = ValidationContext(
        asset_uri="test://scene",
        criteria=AcceptanceCriteria(),
        stage_inspector=_Stage(prims=list(prims)),
    )
    return TransformValidator(ctx.criteria).run(ctx)


# ============================================================== scenes ==


class TestFactoryAssemblyClean:
    """Five well-formed prims — a workbench, bracket, two parts, fastener."""

    def test_clean_scene_passes(self):
        prims = [
            _prim("/Cell/Workbench", ops=[_translate((0, 0, 0)), _scale()]),
            _prim("/Cell/Bracket",   parent_path="/Cell/Workbench", ops=[_translate((0.1, 0, 0.5)), _scale()]),
            _prim("/Cell/PartA",     parent_path="/Cell/Workbench", ops=[_translate((0.2, 0, 0.6)), _scale()]),
            _prim("/Cell/PartB",     parent_path="/Cell/Workbench", ops=[_translate((0.3, 0, 0.6)), _scale()]),
            _prim("/Cell/Fastener",  parent_path="/Cell/Bracket",   ops=[_translate((0.0, 0, 0.05)), _scale()]),
        ]
        assert _run(prims) == []


class TestNaNRootCascades:
    """A NaN at the root must mark all descendants as cascade-invalid."""

    def test_cascade_propagates(self):
        prims = [
            _prim("/Root",        ops=[_scale((float("nan"), 1.0, 1.0))]),         # FAIL
            _prim("/Root/Child1", parent_path="/Root",        ops=[_translate((0, 0, 0))]),
            _prim("/Root/Child1/Grandchild", parent_path="/Root/Child1", ops=[_translate((0, 0, 0))]),
            _prim("/Root/Child2", parent_path="/Root",        ops=[_translate((0, 0, 0))]),
            _prim("/Other",       ops=[_translate((0, 0, 0))]),                    # unaffected sibling
        ]
        issues = _run(prims)

        # The NaN itself
        nans = [i for i in issues if i.code == CODE_NAN_VALUE]
        assert len(nans) == 1 and nans[0].prim_paths == ("/Root",)

        # Cascade INFO for both direct and indirect descendants under /Root
        cascade_paths = sorted(
            i.prim_paths[0] for i in issues if i.code == CODE_CASCADE_INVALID_WORLD
        )
        assert cascade_paths == ["/Root/Child1", "/Root/Child1/Grandchild", "/Root/Child2"]

        # /Other is not under /Root and gets no cascade
        assert all("/Other" not in i.prim_paths for i in issues
                   if i.code == CODE_CASCADE_INVALID_WORLD)


class TestMixedIssuesIsolation:
    """Three prims, three different issue types, each isolated to its prim."""

    def test_per_prim_isolation(self):
        prims = [
            _prim("/A", ops=[_scale((0.0, 1.0, 1.0))]),       # ZERO_SCALE FAIL
            _prim("/B", ops=[_scale((-1.0, 1.0, 1.0))]),      # NON_POSITIVE_SCALE WARN
            _prim("/C", ops=[_translate((0, 0, 250.0))]),     # FLOATING_HEURISTIC WARN (default 100m)
        ]
        issues = _run(prims)
        per_path = {}
        for i in issues:
            per_path.setdefault(i.prim_paths[0], []).append(i.code)

        assert per_path["/A"] == [CODE_ZERO_SCALE]
        assert per_path["/B"] == [CODE_NON_POSITIVE_SCALE]
        assert per_path["/C"] == [CODE_FLOATING_HEURISTIC]


class TestMirroredPartsAllowed:
    """Mirrored part with `customData['mirror']=True` should not warn."""

    def test_mirror_metadata_suppresses_warning(self):
        prims = [
            _prim("/MirrorPart",
                  ops=[_scale((-1.0, 1.0, 1.0))],
                  custom_data=(("mirror", True),)),
            _prim("/PlainPart",
                  ops=[_scale((-1.0, 1.0, 1.0))]),            # no mirror flag → WARN
        ]
        issues = _run(prims)
        # Only PlainPart should appear; MirrorPart is suppressed.
        non_pos = [i for i in issues if i.code == CODE_NON_POSITIVE_SCALE]
        assert len(non_pos) == 1
        assert non_pos[0].prim_paths == ("/PlainPart",)


class TestSceneDeterminism:
    """Different input order, identical report."""

    def test_input_order_invariance(self):
        prims = [
            _prim("/Z", ops=[_scale((0.0, 1.0, 1.0))]),
            _prim("/A", ops=[_scale((-1.0, 1.0, 1.0))]),
            _prim("/M", ops=[_translate((0, 0, 200))]),
        ]
        assert _run(prims) == _run(list(reversed(prims)))
