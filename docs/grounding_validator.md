# GroundingValidator — Runtime Implementation

**Package**: `isaac_factory/extensions/asset_validator/asset_validator/`
**Validator**: `validators/grounding.py` (pure-logic; unchanged since first introduction)
**Runtime adapter**: `adapters/usd_grounding_inspector.py` (Phase 1, 2026-05-18)
**Reporter**: `reporters/json_reporter.py` (writes the workflow's machine-readable artefact)
**Threshold loader**: `thresholds/loader.py` (YAML ↔ `AcceptanceCriteria`)
**Companion specs**: [acceptance §5.B](asset_validator_acceptance.md#5b-static-grounding--status-implemented), [workflow §3 step 4](scene_validation_workflow.md), [report format §2](asset_validator_report_format.md#2-the-validationreport-object)
**Last revised**: 2026-05-18

This document is the operational manual for the **static raycast-based** grounding pipeline. The dynamic (settle-based) variant in acceptance §5.A remains deferred to Phase 2.

---

## 1. End-to-end runtime path

```
.usda asset                                                          report.json
    │                                                                    ▲
    ▼                                                                    │
pxr.Usd.Stage.Open(asset)                                                │
    │                                                                    │
    ▼                                                                    │
UsdGroundingInspector(stage)                                             │
    │ raycast-downward per `customData.asset_validator.grounded` prim    │
    │ → list[GroundingProbe]                                             │
    ▼                                                                    │
ValidationContext(asset_uri=…, criteria=…, grounding_inspector=…)        │
    │                                                                    │
    ▼                                                                    │
GroundingValidator(criteria).run(ctx)                                    │
    │ → list[Issue]                                                      │
    ▼                                                                    │
reporters.json_reporter.write_report(…)  ───────────────────────────────┘
```

No `omni.*`, no `isaacsim.*` imports anywhere — the entire path runs on **`usd-core 26.3` + `pyyaml 6.0.3`** under the `research` profile (conda `env_isaaclab`, Python 3.10.12). Switching to PhysX scene queries is a drop-in adapter swap and does not affect the validator or reporter contracts.

---

## 2. The raycast algorithm (`UsdGroundingInspector`)

For every prim that carries `customData["asset_validator"]["grounded"]`, the inspector performs a downward AABB-vs-vertical-ray intersection against every active `UsdGeom.Gprim` on the stage that isn't itself or one of its descendants.

```
Per candidate C with world AABB [min_x, min_y, min_z] – [max_x, max_y, max_z]:

  cx, cy      = (min_x + max_x)/2,  (min_y + max_y)/2          # XY centre
  origin_z    = max_z                                          # ray origin at AABB top
  bottom_z    = min_z                                          # reported as aabb_bottom_z_m
  min_search  = origin_z - search_distance_m                   # default 10 m

  best        = None
  for each other geometric prim S with world AABB:
      if cx outside [S.min_x, S.max_x]: continue               # XY projection miss
      if cy outside [S.min_y, S.max_y]: continue
      if S.max_z > origin_z:            continue               # above the ray origin
      if S.max_z < min_search:          continue               # beyond search distance

      if best is None or S.max_z > best.max_z:
          best = S                                             # closest below origin

  yield GroundingProbe(
      path             = C.path,
      grounded_intent  = customData token,
      aabb_bottom_z_m  = bottom_z,                             # NOT origin_z
      support_hit_path = best.path if best else None,
      support_hit_z_m  = best.max_z if best else None,
  )
```

### Why the ray starts at the AABB top, not the bottom

Buried candidates have `bottom_z < support_top_z`. A ray cast strictly *below* the bottom would miss the support entirely and report `GROUNDING.NO_SUPPORT_FOUND`. Casting from the AABB top lets the algorithm find a support whose top sits inside the candidate's volume, producing the correct negative-gap `GROUNDING.BURIED` instead.

The reported `aabb_bottom_z_m` (and therefore the signed gap) is still computed from the bottom — that's the physically-meaningful surface for grounding analysis.

### Why the support pool is `UsdGeom.Gprim` only

A generic `Xform` container's world AABB is the union of its descendants' AABBs. For a stage with `/World/Box` and `/World/Floor`, `/World`'s AABB contains both — and the algorithm would happily select `/World` as the closest "support below the box top", which is nonsense.

`UsdGeom.Gprim` is the USD base class for concrete geometry (Cube, Sphere, Capsule, Cylinder, Cone, Mesh, Points, …). Restricting the pool to Gprims keeps the inspector honest while remaining type-agnostic (any geometry primitive counts).

### Determinism

The inspector yields probes in **lexicographic prim-path order**. Ties on `support_hit_z_m` are broken by support prim path, also lexicographically. Two runs over the same stage produce **bit-identical** probe sequences — verified by `tests/unit/test_usd_grounding_inspector.py::TestDeterminism`.

---

## 3. Authoring contract for assets

A prim is a grounding candidate iff it carries:

```usda
def Cube "Box" (
    customData = {
        dictionary asset_validator = {
            token grounded = "true"        # or "false" | "kinematic"
        }
    }
)
{
    double size = 1
    double3 xformOp:translate = (0, 0, 0.5)
    uniform token[] xformOpOrder = ["xformOp:translate"]
}
```

Recognised values of `grounded`:

| Value         | Validator behaviour |
|---|---|
| `"true"`      | Full pipeline: support detection + gap classification (FLOATING / BURIED). |
| `"false"`     | All checks skipped — the asset is explicitly non-grounded (e.g., a balloon). |
| `"kinematic"` | Only `NO_SUPPORT_FOUND` is checked — pose is user-driven, gap is irrelevant. |
| missing / other | `GROUNDING.NO_INTENT_TAG` (WARN) emitted; defaults to `"true"` for the rest of the run. |

Bools are also accepted (`true` → `"true"`, `false` → `"false"`).

---

## 4. Thresholds and YAML integration

Defaults are defined in [`thresholds/schema.py:GroundingThresholds`](../isaac_factory/extensions/asset_validator/asset_validator/thresholds/schema.py) and mirrored in [`configs/acceptance_default.yaml`](../isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml):

```yaml
grounding:
  floating_tolerance_m:  0.005       # 5 mm — gap > this ⇒ FLOATING
  buried_tolerance_m:    0.005       # 5 mm — gap < -this ⇒ BURIED
```

Override per run with the loader:

```python
from asset_validator import load_criteria
criteria = load_criteria("path/to/strict.yaml")
```

- Missing sections fall back to dataclass defaults.
- Unknown sections raise `UnknownSectionError`.
- Unknown keys within a known section are warned to stderr but tolerated (forward-compat).
- `schema_version` MAJOR must equal `1` (current schema is `"1.0.0"`).

---

## 5. JSON report

Produced by `reporters.json_reporter.build_report(...)` and `write_report(...)`. The shape matches [report_format.md §2](asset_validator_report_format.md#2-the-validationreport-object); `schema_version` is `"1.1.0"`.

Top-level fields written for every run:

| Field | Type | Notes |
|---|---|---|
| `schema_version`     | str          | always `"1.1.0"` |
| `asset_uri`          | str          | file:// URI of the stage |
| `started_at`         | ISO-8601 str | UTC, microsecond precision |
| `duration_seconds`   | float        | wall clock |
| `criteria_digest`    | str          | `"sha256:" + sha256(canonical-json(criteria))` — bit-identical across runs |
| `criteria_path`      | str \| null  | YAML path if `load_criteria` was used |
| `validators_run`     | list[str]    | e.g., `["grounding"]` |
| `validators_skipped` | list[str]    | currently always empty |
| `seed`               | int          | CLI-overridable; default 0 |
| `status`             | "INFO"\|"WARN"\|"FAIL" | derived from issue severities |
| `counts`             | {INFO,WARN,FAIL} | zero-filled |
| `issues`             | list[Issue]  | sorted per Issue.sort_key |

Example: see `tests/fixtures/grounding/expected_reports/floating_box.report.json` (paste-friendly excerpt below).

```json
{
  "schema_version": "1.1.0",
  "asset_uri": "file:///.../floating_box.usda",
  "status": "FAIL",
  "counts": {"FAIL": 1, "INFO": 0, "WARN": 0},
  "issues": [
    {
      "code":       "GROUNDING.FLOATING",
      "severity":   "FAIL",
      "validator":  "grounding",
      "prim_paths": ["/World/Box"],
      "metric":     {"gap_m": 1.0, "aabb_bottom_z_m": 1.0, "support_hit_z_m": 0.0},
      "threshold":  {"floating_tolerance_m": 0.005},
      "message":    "Object '/World/Box' is floating: AABB bottom is 1000.000 mm above support '/World/Floor' (threshold 5.000 mm)."
    }
  ]
}
```

### Bit-identical determinism

For a fixed `(asset, criteria, seed, started_at)`, the JSON serialization is byte-identical. The runner script's hashable diff excludes `started_at` and `duration_seconds`; everything else stays stable. CI can hash the rest to detect silent drift.

---

## 6. Fixtures shipped with the runtime

Under `tests/fixtures/grounding/`:

| Fixture                       | Expected status | Expected codes |
|---|---|---|
| `grounded_box_on_floor.usda`  | INFO            | (none) |
| `floating_box.usda`           | FAIL            | `GROUNDING.FLOATING` |
| `buried_box.usda`             | FAIL            | `GROUNDING.BURIED` |
| `lonely_box.usda`             | FAIL            | `GROUNDING.NO_SUPPORT_FOUND` |
| `kinematic_anchor.usda`       | INFO            | (none — intent=`"kinematic"`) |

Each has a paired expected report in `tests/fixtures/grounding/expected_reports/<name>.report.json`, regenerated by re-running validation. The integration tests in `tests/unit/test_usd_grounding_inspector.py` assert that each fixture produces the expected issue set.

---

## 7. Programmatic usage

End-to-end run from the `research` profile:

```python
from pxr import Usd
from asset_validator import (
    GroundingValidator, ValidationContext,
    load_criteria, write_report,
)
from asset_validator.adapters.usd_grounding_inspector import UsdGroundingInspector

criteria = load_criteria(
    "isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml"
)

stage = Usd.Stage.Open("path/to/your/asset.usd")
inspector = UsdGroundingInspector(stage=stage, search_distance_m=10.0)

ctx = ValidationContext(
    asset_uri=f"file://{stage.GetRootLayer().identifier}",
    criteria=criteria,
    grounding_inspector=inspector,
)
issues = GroundingValidator(criteria).run(ctx)

write_report(
    issues,
    "outputs/asset_validation/run-001/report.json",
    asset_uri=ctx.asset_uri,
    validators_run=["grounding"],
    duration_seconds=0.0,
    criteria=criteria,
    criteria_path="…/acceptance_default.yaml",
)
```

Result: a `report.json` matching the schema in §5.

---

## 8. Limitations and out-of-scope items

These are deliberate non-features for v1 — listed so they don't surprise consumers.

- **AABB-based, not mesh-based.** A concave geometry whose AABB is much larger than its actual silhouette will produce conservative supports. Acceptable for static factory-floor scenes where most geometry is convex or near-convex.
- **No multi-pass settle.** No physics, no velocity, no time evolution — the dynamic grounding (acceptance §5.A) is deferred and would emit a different code namespace.
- **No support-side validation.** The inspector picks the closest "below" AABB but does not check whether the support itself has a collider or rigid body. That's `ColliderValidator`'s job.
- **No Omniverse URI support.** Only `file://` paths. Adding `omniverse://` only requires the underlying USD resolver to be configured; no code change in the validator.
- **Single-asset orientation.** Z-up, right-handed only (USD default, Isaac Sim convention). Y-up assets need to be re-authored first.
- **One probe per candidate, one support per probe.** Multi-contact scenarios (e.g., bridge between two pillars) are not modelled; the validator picks one nearest support.

---

## 9. Test coverage summary

| Suite                                | File                                       | Cases | Profile |
|---|---|---|---|
| Validator logic (mocked inspector)   | `tests/unit/test_grounding.py`             | 30+   | research |
| Real adapter (USD fixtures)          | `tests/unit/test_usd_grounding_inspector.py` | 11    | research |
| Threshold loader                     | `tests/unit/test_thresholds_loader.py`     | 12    | research |
| JSON reporter                        | `tests/unit/test_json_reporter.py`         | 11    | research |
| Scene-integrity (mocked, multi-prim) | `tests/scene_integrity/test_grounding_scenes.py` | 6 | research |

All five suites run under the `research` profile in well under a second. None requires Kit or PhysX.

---

## 10. Relationship to other docs

| Document | Role |
|---|---|
| [docs/asset_validator_design.md](asset_validator_design.md)             | Validator architecture and module layout |
| [docs/asset_validator_acceptance.md](asset_validator_acceptance.md) §5.B | Threshold values and acceptance codes |
| [docs/asset_validator_report_format.md](asset_validator_report_format.md) | On-disk report shape |
| [docs/scene_validation_workflow.md](scene_validation_workflow.md) §3 step 4 | Where step 4 fits in the 8-step workflow |
| [docs/runtime_policy.md](runtime_policy.md) §6                            | USD import policy (which Python may import `pxr`) |
| [docs/storage_policy.md](storage_policy.md)                               | Where `outputs/asset_validation/<run-id>/report.json` lands |
