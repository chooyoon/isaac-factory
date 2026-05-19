# TransformValidator — Runtime Implementation

**Package**: `isaac_factory/extensions/asset_validator/asset_validator/`
**Validator**: `validators/transform.py` (pure-logic; unchanged since Phase 0)
**Runtime adapter**: `adapters/usd_stage_inspector.py` (Phase 1, 2026-05-18)
**Companion specs**: [acceptance §2](asset_validator_acceptance.md#2-invalid-transform-rules), [workflow §3 step 2](scene_validation_workflow.md), [report format §3.2](asset_validator_report_format.md#32-transform--15-codes-14--1-guard)
**Last revised**: 2026-05-18

This document is the operational manual for the static transform-validation runtime. The validator detects 14 distinct conditions across NaN/Inf values, invalid scales, invalid rotations, malformed xformOp authoring, the static "floating heuristic," and cascade markers on descendants of failing prims.

---

## 1. End-to-end runtime path

```
.usda asset                                                          report.json
    │                                                                    ▲
    ▼                                                                    │
pxr.Usd.Stage.Open(asset)                                                │
    │                                                                    │
    ▼                                                                    │
UsdStageInspector(stage)                                                 │
    │ enumerate Xformable prims; flatten xformOps; resolve xformOpOrder; │
    │ detect physics schemas; freeze customData → XformablePrim records  │
    ▼                                                                    │
ValidationContext(asset_uri=…, criteria=…, stage_inspector=…)            │
    │                                                                    │
    ▼                                                                    │
TransformValidator(criteria).run(ctx)                                    │
    │   pass 1: per-prim numeric + structural checks                     │
    │   pass 2: cascade INFOs on descendants of failing prims            │
    │   pass 3: floating heuristic                                       │
    │   final: deterministic sort                                        │
    │ → list[Issue]                                                      │
    ▼                                                                    │
reporters.json_reporter.write_report(…)  ───────────────────────────────┘
```

No `omni.*`, no `isaacsim.*`. Runs entirely on `usd-core 26.3 + pyyaml 6.0.3` under the `research` profile. The optional `pxr.UsdPhysics` import is gated behind a try/except so the adapter still works when only the geometry layer of OpenUSD is available.

---

## 2. What the adapter extracts (`UsdStageInspector`)

For every active `UsdGeom.Xformable` prim, the adapter walks `xformOps` and produces one `XformablePrim` record:

```python
@dataclass(frozen=True)
class XformablePrim:
    path:                       str
    parent_path:                str | None    # None for top-level prims under /
    is_active:                  bool
    has_collision_api:          bool          # via UsdPhysics.CollisionAPI if importable
    is_likely_dynamic:          bool          # RigidBody/Articulation API OR customData.asset_validator.is_dynamic
    ops:                        tuple[TransformOp, ...]
    xform_op_order_unresolved:  tuple[str, ...]   # names in xformOpOrder with no matching attr
    custom_data:                tuple[tuple[str, Any], ...]  # frozen for hashability
```

Each `TransformOp` is the flattened, canonical form of a single op:

| `op_type`         | values length | shape                                            |
|---|---|---|
| `translate`       | 3 | `(tx, ty, tz)`                                   |
| `scale`           | 3 | `(sx, sy, sz)`                                   |
| `rotate_axis`     | 1 | `(angle_deg,)` for `xformOp:rotateX/Y/Z`         |
| `rotate_euler`    | 3 | `(rx_deg, ry_deg, rz_deg)` for `rotateXYZ`/etc.  |
| `rotate_quat`     | 4 | `(w, x, y, z)` from `xformOp:orient`             |
| `transform_matrix`| 16 | row-major flatten of `xformOp:transform`        |

### Mapping pxr → canonical op_type

The adapter uses a single dispatch table keyed on `UsdGeom.XformOp.GetOpType()`:

```python
_OP_TYPE_MAP = {
    UsdGeom.XformOp.TypeTranslate: "translate",
    UsdGeom.XformOp.TypeScale:     "scale",
    UsdGeom.XformOp.TypeRotateX:   "rotate_axis",   # also Y, Z
    UsdGeom.XformOp.TypeRotateXYZ: "rotate_euler",  # all 6 Euler permutations
    UsdGeom.XformOp.TypeOrient:    "rotate_quat",
    UsdGeom.XformOp.TypeTransform: "transform_matrix",
}
```

Unknown types fall back to `transform_matrix` as a defensive default.

### Detecting xformOpOrder corruption

A prim's `xformOpOrder` attribute is the source of truth for op application order. If an entry names an attribute that doesn't exist on the prim, pxr's `Xformable.GetOrderedXformOps()` silently drops it (and prints a warning) — but the named-but-missing op is a real corruption. The adapter explicitly compares:

```python
raw_order      = Xformable.GetXformOpOrderAttr().Get()        # full list as authored
resolved_names = {op.GetOpName() for op in Xformable.GetOrderedXformOps()}
unresolved     = tuple(n for n in raw_order if n not in resolved_names)
```

`unresolved` populates `XformablePrim.xform_op_order_unresolved`. The validator emits `TRANSFORM.XFORMOP_ORDER_INVALID` (FAIL) per affected prim.

### Detecting dynamic / collider prims

When `pxr.UsdPhysics` is importable (it is in env_isaaclab's `usd-core` install):

| Signal                                | Result on `XformablePrim`       |
|---|---|
| `HasAPI(UsdPhysics.CollisionAPI)`     | `has_collision_api = True`      |
| `HasAPI(UsdPhysics.RigidBodyAPI)`     | `is_likely_dynamic = True`      |
| `HasAPI(UsdPhysics.ArticulationRootAPI)` | `is_likely_dynamic = True`   |
| `customData.asset_validator.is_dynamic = true` | `is_likely_dynamic = True`  |

When `UsdPhysics` is unavailable the adapter degrades to defaults of `False`. Tests pass even in that case because the fixtures use the explicit `customData` route when they need a "dynamic" prim.

### Freezing custom data

The adapter snapshots only the small slice of `customData` the validator reads:

- `mirror` (bool) — suppresses `TRANSFORM.NON_POSITIVE_SCALE` warnings
- `asset_validator.is_dynamic` (bool) — same effect as physics APIs

Stored as a sorted tuple of `(key, value)` pairs to keep `XformablePrim` hashable / frozen.

### Determinism

Prims are emitted in **lexicographic prim-path order**. The validator re-sorts its Issue output by `Issue.sort_key`, so the final report is bit-identical across runs of the same `.usda` — asserted by `TestDeterminism` in `tests/unit/test_usd_stage_inspector.py`.

---

## 3. Mapping fixture → expected report

| Fixture                          | Expected status | Codes emitted                                |
|---|---|---|
| `clean_transforms.usda`          | INFO            | (none)                                        |
| `nan_translation.usda`           | FAIL            | `TRANSFORM.NAN_VALUE`                         |
| `inf_scale.usda`                 | FAIL            | `TRANSFORM.INF_VALUE`                         |
| `zero_scale.usda`                | FAIL            | `TRANSFORM.ZERO_SCALE`                        |
| `negative_scale.usda`            | WARN            | `TRANSFORM.NON_POSITIVE_SCALE`                |
| `mirror_allowed.usda`            | INFO            | (none — `customData.mirror` waives the WARN)  |
| `denormal_quat.usda`             | FAIL            | `TRANSFORM.QUATERNION_DENORMAL`               |
| `non_orthogonal_matrix.usda`     | FAIL            | `TRANSFORM.ROTATION_NON_ORTHOGONAL`           |
| `floating_high.usda`             | WARN            | `TRANSFORM.FLOATING_HEURISTIC`                |
| `cascade_invalid.usda`           | FAIL            | `TRANSFORM.NAN_VALUE` (parent) + `TRANSFORM.CASCADE_INVALID_WORLD` (descendant, INFO) |
| `time_sampled_static.usda`       | WARN            | `TRANSFORM.TIME_SAMPLED_ON_STATIC`            |
| `xformop_order_corrupt.usda`     | FAIL            | `TRANSFORM.XFORMOP_ORDER_INVALID`             |

Each fixture has a pinned expected report under `tests/fixtures/transform/expected_reports/<name>.report.json` (regeneratable via the same script that produced the grounding-validator fixtures). The reports are byte-identical across runs given a fixed `started_at`.

---

## 4. Authoring conventions

### NaN / Inf

`.usda` text accepts the literal tokens `nan` and `inf`:

```usda
double3 xformOp:translate = (nan, 0, 0)
double3 xformOp:scale     = (inf, 1, 1)
```

These parse cleanly under `pxr 26.3` and trigger the validator's non-finite checks. Older USD versions may reject them — in that case, author via a small Python fixture generator using `Usd.Stage.CreateNew(...)`.

### Quaternions

`xformOp:orient` uses the `quatd` / `quatf` / `quath` type. USD literal order is `(real, i, j, k)` — i.e., `(w, x, y, z)`:

```usda
quatd xformOp:orient = (1, 0, 0, 0)        # identity
quatd xformOp:orient = (0.5, 0, 0, 0)      # magnitude 0.5 → DENORMAL FAIL
```

### Matrices

`matrix4d xformOp:transform = ((r0c0, r0c1, r0c2, r0c3), (r1...), ...)` — row-major. The rotation submatrix is the upper-left 3×3 (`m[i][j]` for `i,j ∈ 0..2`). Add shear to one off-diagonal to deliberately fail orthogonality:

```usda
matrix4d xformOp:transform = ( (1, 0.5, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1) )
```

### Mirror metadata waiver

Negative scale is a `WARN` by default (escalates to `FAIL` if the prim has a `CollisionAPI`). Add the mirror flag to waive the WARN entirely:

```usda
def Cube "MirroredPart" (
    customData = { bool mirror = true }
)
{
    double3 xformOp:scale = (-1, 1, 1)
    uniform token[] xformOpOrder = ["xformOp:scale"]
}
```

### Time-sampled values on static prims

```usda
double3 xformOp:translate = (0, 0, 0)
double3 xformOp:translate.timeSamples = {
    0: (0, 0, 0),
    1: (1, 0, 0),
}
```

Triggers `TRANSFORM.TIME_SAMPLED_ON_STATIC` unless the prim has a physics dynamic API or `customData.asset_validator.is_dynamic = true`.

---

## 5. Programmatic usage

```python
from pxr import Usd
from asset_validator import (
    TransformValidator, ValidationContext,
    load_criteria, write_report,
)
from asset_validator.adapters.usd_stage_inspector import UsdStageInspector

criteria = load_criteria(
    "isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml"
)

stage = Usd.Stage.Open("path/to/asset.usd")
inspector = UsdStageInspector(stage=stage)

ctx = ValidationContext(
    asset_uri=f"file://{stage.GetRootLayer().identifier}",
    criteria=criteria,
    stage_inspector=inspector,
)
issues = TransformValidator(criteria).run(ctx)

write_report(
    issues,
    "outputs/asset_validation/run-001/report.json",
    asset_uri=ctx.asset_uri,
    validators_run=["transform"],
    duration_seconds=0.0,
    criteria=criteria,
    criteria_path="…/acceptance_default.yaml",
)
```

Result: a `report.json` with `schema_version: "1.1.0"` matching the shape in [report_format.md §2](asset_validator_report_format.md).

---

## 6. Limitations

- **Default-time-code sampling.** The adapter reads each `xformOp` at `Usd.TimeCode.Default()`. If a prim is purely time-sampled (no default value), USD returns the value at the earliest sample, which may not reflect the asset's intent. To inspect a specific time, construct `UsdStageInspector(stage, time_code=Usd.TimeCode(t))`.
- **No layer-stack inspection.** The validator sees the *composed* stage. Authoring opinions that get overridden in a stronger layer are not flagged — that's a different validator's job.
- **Per-prim cascade, not per-op.** If a prim has one NaN translate op, *all* its descendants are flagged with `TRANSFORM.CASCADE_INVALID_WORLD`. Fine-grained "which child branch survives the bad parent op" is not modelled.
- **No analysis of `xformOp:resetXformOpStack`.** USD allows a prim to ignore its parent's transform via this attribute; the adapter treats every prim's parent path as authoritative. In practice this only matters for the cascade pass and would produce slightly conservative reports.
- **No matrix decomposition.** A 4×4 transform op encoding scale-plus-rotation will only have its rotation submatrix checked for orthogonality. Shear caused by non-uniform scale is correctly flagged. Recovering separate scale / rotation from a matrix would require SVD; out of scope.

---

## 7. Test coverage summary

| Suite                                | File                                          | Cases | Profile |
|---|---|---|---|
| Validator logic (mocked inspector)   | `tests/unit/test_transform.py`                | 40    | research |
| Real adapter (USD fixtures)          | `tests/unit/test_usd_stage_inspector.py`      | 18    | research |
| Scene-integrity (mocked, multi-prim) | `tests/scene_integrity/test_transform_scenes.py` | 5  | research |

All three suites run under the `research` profile in well under a second.

---

## 8. Relationship to other docs

| Document | Role |
|---|---|
| [docs/asset_validator_design.md](asset_validator_design.md)             | Validator architecture and module layout |
| [docs/asset_validator_acceptance.md](asset_validator_acceptance.md) §2  | Threshold values and acceptance codes |
| [docs/asset_validator_report_format.md](asset_validator_report_format.md) §3.2 | TRANSFORM code registry |
| [docs/scene_validation_workflow.md](scene_validation_workflow.md) §3 step 2 | Where step 2 fits in the 8-step workflow |
| [docs/grounding_validator.md](grounding_validator.md)                    | Sibling Phase 1 adapter — same patterns, different validator |
| [docs/runtime_policy.md](runtime_policy.md) §6                            | USD import policy |
| [docs/storage_policy.md](storage_policy.md)                               | Where `outputs/asset_validation/<run-id>/report.json` lands |
