# Asset Validator — Report Format

**Companion to**: [docs/asset_validator_design.md](asset_validator_design.md) §4.1, §4.2
**Status**: Authoritative for the on-disk and on-stream format of validator output.
**Last revised**: 2026-05-18

This document specifies the **machine-readable JSON shape** that the validator emits, plus the text rendering used by the CLI. Every reporter (`JsonReporter`, `TextReporter`, `JunitReporter`) must produce output consistent with this spec. Stable field names and issue codes are a contract — Sprint Contracts and CI gates depend on them.

---

## 1. The `Issue` object

The primitive unit. Every validator emits zero or more `Issue` instances; the report is essentially a list of these.

### 1.1 JSON shape

```json
{
  "code":       "OVERLAP.PEN_DEPTH_EXCEEDED",
  "severity":   "FAIL",
  "message":    "Unexpected contact between '/World/A' and '/World/B' penetrates 2.000 mm (threshold 1.000 mm).",
  "prim_paths": ["/World/A", "/World/B"],
  "metric":     { "penetration_depth_m": 0.002 },
  "threshold":  { "pen_depth_max_m": 0.001 },
  "validator":  "overlap"
}
```

### 1.2 Field reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `code`       | `string`                    | yes | Namespaced stable id: `<VALIDATOR>.<CONDITION>`. See §3 for the registry. |
| `severity`   | `"INFO" \| "WARN" \| "FAIL"` | yes | Uppercase enum name (not integer). |
| `message`    | `string`                    | yes | Human-readable, single line. Numbers in human units (mm, °) when natural. |
| `prim_paths` | `array<string>`             | yes | USD `Sdf.Path` strings, lexicographically sorted, 0..N entries. |
| `metric`     | `object<string, number>`    | yes (object; empty if none) | Raw measurements in **SI units**. Keys snake_case with unit suffix (`_m`, `_rad`, `_kg`). |
| `threshold`  | `object<string, number>`    | yes (object; empty if none) | Threshold values from `AcceptanceCriteria` keyed by the same convention. |
| `validator`  | `string`                    | yes | Lowercase validator name (`overlap`, `collider`, …). Same string as `Validator.name`. |

### 1.3 Severity values

| Name | Integer (internal) | Meaning |
|---|---|---|
| `INFO` | 0 | Advisory; never blocks. |
| `WARN` | 1 | Degraded but usable; may block per `--fail-on warn`. |
| `FAIL` | 2 | Blocks. Exit code 1. |

The integer values exist only inside the Python `Severity` enum (`IntEnum`) for ordering; JSON output is always the string name.

### 1.4 Code naming rules

- Namespace prefix matches the validator: `OVERLAP.*`, `COLLIDER.*`, `TRANSFORM.*`, `HIERARCHY.*`, `GROUNDING.*`, `RESET.*`.
- All upper-case, dot-separated, no spaces.
- Codes are **append-only** — once shipped, a code cannot be renamed or removed without a major version bump of the validator extension.
- New codes must appear in the relevant table of [docs/asset_validator_acceptance.md](asset_validator_acceptance.md) in the same change.

---

## 2. The `ValidationReport` object

> Implementation note: `ValidationReport` itself is **not** in the v1 implementation. The OverlapValidator emits a `list[Issue]`; the pipeline (deferred) is responsible for wrapping that into a report. This section specifies the target shape so the report-format contract is fixed up front.

### 2.1 JSON shape

```json
{
  "schema_version": "1.1.0",
  "asset_uri":      "file:///home/cap2/last/assets/example.usd",
  "started_at":     "2026-05-18T11:23:45.001234+00:00",
  "duration_seconds": 4.182,
  "criteria_digest": "sha256:7c0a2f…",
  "criteria_path":   "/home/cap2/last/isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml",
  "validators_run": ["hierarchy", "transform", "collider", "overlap", "grounding", "reset"],
  "validators_skipped": [],
  "seed": 0,
  "status": "FAIL",
  "counts": { "INFO": 0, "WARN": 2, "FAIL": 1 },
  "issues": [
    { "code": "...", "severity": "FAIL", "...": "..." },
    { "code": "...", "severity": "WARN", "...": "..." }
  ]
}
```

### 2.2 Field reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version`     | `string`               | yes | Semver. Bump `MAJOR` on any non-additive change to issue/report shape. |
| `asset_uri`          | `string`               | yes | `file://` URI for local; supports `omniverse://` if used. |
| `started_at`         | `string` (RFC 3339)    | yes | UTC, microsecond precision. |
| `duration_seconds`   | `number`               | yes | Wall clock for the pipeline run. |
| `criteria_digest`    | `string`               | yes | SHA-256 of the loaded `AcceptanceCriteria` dataclass tree (canonical JSON). Lets CI prove which thresholds were applied. |
| `criteria_path`      | `string` or `null`     | yes | Absolute path of the YAML loaded; `null` if defaults were used in-code. |
| `validators_run`     | `array<string>`        | yes | Names in execution order. |
| `validators_skipped` | `array<string>`        | yes | Validators in the requested set that were not run (e.g., dynamic phase skipped after strict-static FAIL). |
| `seed`               | `integer`              | yes | Seed used at pipeline start. |
| `status`             | `"INFO" \| "WARN" \| "FAIL"` | yes | Max severity across all issues, or `"INFO"` if empty. |
| `counts`             | `object<Severity,int>` | yes | Always all three keys, zero-filled. |
| `issues`             | `array<Issue>`         | yes | Sorted per §2.3. |

### 2.3 Issue ordering

`issues` is sorted by:

1. `severity` descending (`FAIL` first)
2. `code` ascending (lexicographic)
3. `prim_paths` ascending (lexicographic, tuple compare)
4. `validator` ascending

This ordering is the same as `Issue.sort_key()` and is enforced by every reporter.

### 2.4 Determinism

For a given asset + criteria + seed, the report is **bit-identical** modulo `started_at`, `duration_seconds`, and `asset_uri`. The same inputs produce the same `issues` list in the same order, with the same `criteria_digest`. CI gates can hash the report (excluding the three time/path fields) to detect silent drift.

---

## 3. Issue-code registry

Covers all codes emitted by the five currently-implemented validators (Overlap, Transform, Collider, Grounding, DeterministicReset). Cross-reference: each code's authoritative rule + numeric threshold is in [docs/asset_validator_acceptance.md](asset_validator_acceptance.md).

Conventions: **✓** = implemented & emitted; **△** = reserved name (deferred or collapsed — see acceptance doc for the exact reason). Reserved codes will not be re-used for another meaning.

### 3.1 OVERLAP — 5 codes (3 ✓ / 2 △)

| Code | Severity | Status | Rule | Trigger |
|---|---|---|---|---|
| `OVERLAP.PEN_DEPTH_EXCEEDED`     | FAIL | ✓ | [§1.1](asset_validator_acceptance.md#1-overlap-thresholds) | Non-fit contact pair with penetration > `pen_depth_max_m` (default 1.0 mm) |
| `OVERLAP.PEN_DEPTH_EXCEEDED_FIT` | WARN | ✓ | [§1.2](asset_validator_acceptance.md#1-overlap-thresholds) | `expects_contact` pair with penetration > `pen_depth_max_fit_m` (default 0.1 mm) |
| `OVERLAP.UNEXPECTED_CONTACT`     | FAIL | △ collapsed into §1.1 | [§1.3](asset_validator_acceptance.md#1-overlap-thresholds) | Reserved; no emit in v1 |
| `OVERLAP.CONVERGENCE_FAILURE`    | FAIL | △ deferred (multi-step) | [§1.4](asset_validator_acceptance.md#1-overlap-thresholds) | Reserved; no emit in v1 |
| `OVERLAP.SELF_INTERSECTION`      | FAIL | ✓ | [§1.5](asset_validator_acceptance.md#1-overlap-thresholds) | Contact pair where `prim_a == prim_b` (collider cooking artifact) |

### 3.2 TRANSFORM — 15 codes (14 ✓ + 1 guard)

| Code | Severity | Status | Rule | Trigger |
|---|---|---|---|---|
| `TRANSFORM.NAN_VALUE`                | FAIL | ✓ | [§2.1](asset_validator_acceptance.md#2-invalid-transform-rules)  | NaN in any xformOp value |
| `TRANSFORM.INF_VALUE`                | FAIL | ✓ | [§2.2](asset_validator_acceptance.md#2-invalid-transform-rules)  | ±Inf in any xformOp value |
| `TRANSFORM.ZERO_SCALE`               | FAIL | ✓ | [§2.3](asset_validator_acceptance.md#2-invalid-transform-rules)  | `\|scale_axis\| < min_scale_magnitude` |
| `TRANSFORM.SCALE_OUT_OF_RANGE`       | FAIL | ✓ | [§2.4](asset_validator_acceptance.md#2-invalid-transform-rules)  | `\|scale_axis\| > max_scale_magnitude` |
| `TRANSFORM.NON_POSITIVE_SCALE`       | WARN/FAIL | ✓ | [§2.5](asset_validator_acceptance.md#2-invalid-transform-rules)  | Negative scale without `customData["mirror"]: true`; FAIL if collider present |
| `TRANSFORM.QUATERNION_DENORMAL`      | FAIL | ✓ | [§2.6](asset_validator_acceptance.md#2-invalid-transform-rules)  | Quaternion magnitude outside `[0.999, 1.001]` |
| `TRANSFORM.ROTATION_NON_ORTHOGONAL`  | FAIL | ✓ | [§2.7](asset_validator_acceptance.md#2-invalid-transform-rules)  | Matrix rotation submatrix Frobenius `‖RᵀR − I‖_F > rotation_orthogonality_eps` |
| `TRANSFORM.TRANSLATION_OUT_OF_RANGE` | WARN | ✓ | [§2.8](asset_validator_acceptance.md#2-invalid-transform-rules)  | `‖t‖₂ > max_translation_magnitude_m` |
| `TRANSFORM.TIME_SAMPLED_ON_STATIC`   | WARN | ✓ | [§2.9](asset_validator_acceptance.md#2-invalid-transform-rules)  | xformOp has time samples on prim flagged static |
| `TRANSFORM.MIXED_OP_ORDER`           | WARN | ✓ | [§2.10](asset_validator_acceptance.md#2-invalid-transform-rules) | Prim mixes `xformOp:transform` with separate translate/rotate/scale ops |
| `TRANSFORM.XFORMOP_ORDER_INVALID`    | FAIL | ✓ | [§2.11](asset_validator_acceptance.md#2-invalid-transform-rules) | `xformOpOrder` references an op not present on the prim |
| `TRANSFORM.CASCADE_INVALID_WORLD`    | INFO | ✓ | [§2.12](asset_validator_acceptance.md#2-invalid-transform-rules) | Descendant of a prim that failed §2.* rules — world matrix unreliable |
| `TRANSFORM.FLOATING_HEURISTIC`       | WARN | ✓ | [§2.13](asset_validator_acceptance.md#2-invalid-transform-rules) | Local `translate.z > floating_heuristic_z_m` (static heuristic) |
| `TRANSFORM.OP_VALUE_COUNT_MISMATCH`  | FAIL | ✓ | [§2.14](asset_validator_acceptance.md#2-invalid-transform-rules) | xformOp value-array length mismatches op type |
| `TRANSFORM.NO_STAGE_INSPECTOR`       | FAIL | ✓ guard | [§7](asset_validator_acceptance.md#7-infrastructure-guard-codes) | `ctx.stage_inspector is None` — pipeline misconfiguration |

### 3.3 COLLIDER — 13 codes (12 ✓ + 1 guard)

| Code | Severity | Status | Rule | Trigger |
|---|---|---|---|---|
| `COLLIDER.NO_RIGID_BODY_ANCESTOR`        | FAIL | ✓ | [§3.1](asset_validator_acceptance.md#3-collider-requirements)  | Collider with no RB ancestor and no `static_collider` flag |
| `COLLIDER.RIGID_BODY_WITHOUT_COLLIDER`   | FAIL | ✓ | [§3.2](asset_validator_acceptance.md#3-collider-requirements)  | RigidBody with no descendant CollisionAPI |
| `COLLIDER.MESH_ON_DYNAMIC`               | FAIL | ✓ | [§3.3](asset_validator_acceptance.md#3-collider-requirements)  | Dynamic body's collider approximation outside the allowed set |
| `COLLIDER.CONVEX_DECOMP_HULL_LIMIT`      | WARN/FAIL | ✓ | [§3.4](asset_validator_acceptance.md#3-collider-requirements)  | Convex-decomp hull count > 32 (WARN) / > 64 (FAIL) |
| `COLLIDER.AABB_MISMATCH`                 | WARN | ✓ | [§3.5](asset_validator_acceptance.md#3-collider-requirements)  | Collider AABB per-axis ratio vs visual AABB > `aabb_ratio_max` |
| `COLLIDER.MISSING_COLLISION_GROUP`       | WARN | ✓ | [§3.6](asset_validator_acceptance.md#3-collider-requirements)  | CollisionAPI without explicit `physxCollision:filterGroup` |
| `COLLIDER.COOKING_FAILED`                | FAIL | ✓ | [§3.7](asset_validator_acceptance.md#3-collider-requirements)  | PhysX cooking reported an error for this collider |
| `COLLIDER.STATIC_MISSING_KINEMATIC_FLAG` | WARN | △ collapsed into §3.1 | [§3.8](asset_validator_acceptance.md#3-collider-requirements) | Reserved; no emit in v1 |
| `COLLIDER.MASS_OUT_OF_RANGE`             | WARN | ✓ | [§3.9](asset_validator_acceptance.md#3-collider-requirements)  | RigidBody mass outside `[mass_min_kg, mass_max_kg]` |
| `COLLIDER.MASS_DENSITY_CONFLICT`         | WARN | ✓ | [§3.10](asset_validator_acceptance.md#3-collider-requirements) | `\|mass − density·volume\|/mass > mass_density_tolerance` |
| `COLLIDER.DEGENERATE_AABB`               | WARN | ✓ | [§3.11](asset_validator_acceptance.md#3-collider-requirements) | Collider AABB min-axis extent < `min_aabb_extent_m` |
| `COLLIDER.EXTREME_ASPECT_RATIO`          | WARN | ✓ | [§3.12](asset_validator_acceptance.md#3-collider-requirements) | Collider AABB max/min axis ratio > `max_aabb_aspect_ratio` |
| `COLLIDER.NO_COLLIDER_INSPECTOR`         | FAIL | ✓ guard | [§7](asset_validator_acceptance.md#7-infrastructure-guard-codes) | `ctx.collider_inspector is None` |

### 3.4 HIERARCHY — 11 codes (all △ deferred to Phase 2)

All entries reserved for the future `HierarchyValidator`. See [acceptance §4](asset_validator_acceptance.md#4-hierarchy-rules--status-deferred-to-phase-2) for full rule definitions. Consumers must accept these as valid codes in the schema; they will not be emitted by v1.

| Code | Severity | Status |
|---|---|---|
| `HIERARCHY.MAX_DEPTH_EXCEEDED`             | WARN/FAIL | △ |
| `HIERARCHY.MAX_CHILDREN_EXCEEDED`          | WARN/FAIL | △ |
| `HIERARCHY.MISSING_DEFAULT_PRIM`           | FAIL | △ |
| `HIERARCHY.NESTED_RIGID_BODY`              | FAIL | △ |
| `HIERARCHY.MULTIPLE_ARTICULATION_ROOTS`    | FAIL | △ |
| `HIERARCHY.ORPHAN_COLLIDER`                | FAIL | △ |
| `HIERARCHY.UNRESOLVED_REFERENCE`           | FAIL | △ |
| `HIERARCHY.PURPOSE_GUIDE_WITH_PHYSICS`     | FAIL | △ |
| `HIERARCHY.INSTANCEABLE_PROTOTYPE_INVALID` | FAIL | △ |
| `HIERARCHY.NON_XFORM_PARENT_FOR_RIGID_BODY`| FAIL | △ |
| `HIERARCHY.SCHEMA_ON_INACTIVE_PRIM`        | WARN | △ |

### 3.5 GROUNDING — 12 codes (4 ✓ static + 7 △ dynamic + 1 guard)

| Code | Severity | Status | Rule | Trigger |
|---|---|---|---|---|
| `GROUNDING.NO_INTENT_TAG`              | WARN | ✓ | [§5.B.1](asset_validator_acceptance.md#5b-static-grounding--status-implemented) | `customData["asset_validator"]["grounded"]` missing/invalid |
| `GROUNDING.FLOATING`                   | FAIL | ✓ | [§5.B.2](asset_validator_acceptance.md#5b-static-grounding--status-implemented) | Static: AABB-bottom > `floating_tolerance_m` above support |
| `GROUNDING.BURIED`                     | FAIL | ✓ | [§5.B.3](asset_validator_acceptance.md#5b-static-grounding--status-implemented) | Static: AABB-bottom > `buried_tolerance_m` below support |
| `GROUNDING.NO_SUPPORT_FOUND`           | FAIL | ✓ | [§5.B.4](asset_validator_acceptance.md#5b-static-grounding--status-implemented) | Static: downward raycast missed within search distance |
| `GROUNDING.NO_GROUND_TAG`              | WARN | △ | [§5.A.1](asset_validator_acceptance.md#5a-dynamic-grounding--status-deferred-to-phase-2) | Reserved for dynamic variant |
| `GROUNDING.AABB_BELOW_SUPPORT`         | FAIL | △ | [§5.A.2](asset_validator_acceptance.md#5a-dynamic-grounding--status-deferred-to-phase-2) | Reserved for dynamic variant |
| `GROUNDING.LINEAR_DRIFT_AFTER_SETTLE`  | FAIL | △ | [§5.A.3](asset_validator_acceptance.md#5a-dynamic-grounding--status-deferred-to-phase-2) | Reserved for dynamic variant |
| `GROUNDING.ANGULAR_DRIFT_AFTER_SETTLE` | FAIL | △ | [§5.A.4](asset_validator_acceptance.md#5a-dynamic-grounding--status-deferred-to-phase-2) | Reserved for dynamic variant |
| `GROUNDING.KINEMATIC_NOT_PINNED`       | FAIL | △ | [§5.A.5](asset_validator_acceptance.md#5a-dynamic-grounding--status-deferred-to-phase-2) | Reserved for dynamic variant |
| `GROUNDING.FLOATING_OBJECT`            | FAIL | △ | [§5.A.6](asset_validator_acceptance.md#5a-dynamic-grounding--status-deferred-to-phase-2) | Reserved for dynamic variant |
| `GROUNDING.SETTLE_BUDGET_EXCEEDED`     | FAIL | △ | [§5.A.7](asset_validator_acceptance.md#5a-dynamic-grounding--status-deferred-to-phase-2) | Reserved for dynamic variant |
| `GROUNDING.NO_INSPECTOR`               | FAIL | ✓ guard | [§7](asset_validator_acceptance.md#7-infrastructure-guard-codes) | `ctx.grounding_inspector is None` |

### 3.6 RESET — 13 codes (12 ✓ + 1 guard)

| Code | Severity | Status | Rule | Trigger |
|---|---|---|---|---|
| `RESET.POSE_TRANSLATION_DRIFT`     | FAIL | ✓ | [§6.1](asset_validator_acceptance.md#6-deterministic-reset-requirements)  | After-reset translation delta vs initial > tolerance |
| `RESET.POSE_ROTATION_DRIFT`        | FAIL | ✓ | [§6.2](asset_validator_acceptance.md#6-deterministic-reset-requirements)  | After-reset quaternion-angle delta vs initial > tolerance |
| `RESET.LINEAR_VELOCITY_DRIFT`      | FAIL | ✓ | [§6.3](asset_validator_acceptance.md#6-deterministic-reset-requirements)  | Residual linear velocity at reset > tolerance |
| `RESET.ANGULAR_VELOCITY_DRIFT`     | FAIL | ✓ | [§6.4](asset_validator_acceptance.md#6-deterministic-reset-requirements)  | Residual angular velocity at reset > tolerance |
| `RESET.DETERMINISM_FLAG_MISSING`   | FAIL | ✓ | [§6.5](asset_validator_acceptance.md#6-deterministic-reset-requirements)  | PhysX `useDeterministicSimulation` not set |
| `RESET.SEED_NOT_FIXED`             | FAIL | ✓ | [§6.6](asset_validator_acceptance.md#6-deterministic-reset-requirements)  | Seeds not configured before the run |
| `RESET.CYCLE_VARIANCE_TRANSLATION` | FAIL | ✓ | [§6.7a](asset_validator_acceptance.md#6-deterministic-reset-requirements) | After-step translation of cycle i ≠ cycle 1 |
| `RESET.CYCLE_VARIANCE_ROTATION`    | FAIL | ✓ | [§6.7b](asset_validator_acceptance.md#6-deterministic-reset-requirements) | After-step rotation of cycle i ≠ cycle 1 |
| `RESET.NON_DETERMINISTIC_AUTHORING`| WARN | ✓ | [§6.8](asset_validator_acceptance.md#6-deterministic-reset-requirements)  | Prim uses a random physics API |
| `RESET.SPAWN_ORDER_MISMATCH`       | FAIL | ✓ | [§6.9](asset_validator_acceptance.md#6-deterministic-reset-requirements)  | Cycle spawn order ≠ initial_spawn_order |
| `RESET.CONTACT_AFTER_RESET`        | FAIL | ✓ | [§6.10](asset_validator_acceptance.md#6-deterministic-reset-requirements) | Residual contact penetration > tolerance at next t=0 |
| `RESET.BODY_SET_MISMATCH`          | FAIL | ✓ | [§6.11](asset_validator_acceptance.md#6-deterministic-reset-requirements) | Body set after reset ≠ initial body set |
| `RESET.NO_SIMULATOR`               | FAIL | ✓ guard | [§7](asset_validator_acceptance.md#7-infrastructure-guard-codes) | `ctx.reset_simulator is None` |

### 3.7 Totals

| Validator           | Codes | Implemented (✓) | Deferred / collapsed (△) |
|---|---:|---:|---:|
| Overlap             |  5 |  3 | 2 |
| Transform           | 15 | 14 (+1 guard) | 0 |
| Collider            | 13 | 12 (+1 guard) | 1 |
| Hierarchy           | 11 |  0 | 11 |
| Grounding (static)  |  4 |  4 | 0 |
| Grounding (dynamic) |  7 |  0 | 7 |
| Grounding guard     |  1 |  1 | 0 |
| Reset               | 13 | 12 (+1 guard) | 0 |
| **Total**           | **69** | **49** | **20** |

> "Implemented" here counts every code emitted by validator code, including the 5 guard codes for missing inspectors / simulator. Acceptance §7 lists the guards explicitly.

### 3.8 Per-code field guarantees (implemented codes only)

Asset-issue codes carry their measurement under stable `metric` keys; threshold values use the corresponding dataclass field names. Guard codes carry no metric/threshold.

| Code | `metric` keys | `threshold` keys | `prim_paths` length |
|---|---|---|---|
| `OVERLAP.PEN_DEPTH_EXCEEDED`              | `penetration_depth_m` | `pen_depth_max_m`     | 2 |
| `OVERLAP.PEN_DEPTH_EXCEEDED_FIT`          | `penetration_depth_m` | `pen_depth_max_fit_m` | 2 |
| `OVERLAP.SELF_INTERSECTION`               | `penetration_depth_m` | (empty)               | 1 |
| `TRANSFORM.NAN_VALUE`                     | `nan_count`           | (empty) | 1 |
| `TRANSFORM.INF_VALUE`                     | `inf_count`           | (empty) | 1 |
| `TRANSFORM.ZERO_SCALE`                    | `scale_{x,y,z}`       | `min_scale_magnitude` | 1 |
| `TRANSFORM.SCALE_OUT_OF_RANGE`            | `scale_{x,y,z}`       | `max_scale_magnitude` | 1 |
| `TRANSFORM.NON_POSITIVE_SCALE`            | `scale_{x,y,z}`       | (empty) | 1 |
| `TRANSFORM.QUATERNION_DENORMAL`           | `quaternion_magnitude` | `quaternion_magnitude_min`, `quaternion_magnitude_max` | 1 |
| `TRANSFORM.ROTATION_NON_ORTHOGONAL`       | `orthogonality_error` | `rotation_orthogonality_eps` | 1 |
| `TRANSFORM.TRANSLATION_OUT_OF_RANGE`      | `translation_magnitude_m` | `max_translation_magnitude_m` | 1 |
| `TRANSFORM.TIME_SAMPLED_ON_STATIC`        | `time_sample_count`   | (empty) | 1 |
| `TRANSFORM.MIXED_OP_ORDER`                | (empty)               | (empty) | 1 |
| `TRANSFORM.XFORMOP_ORDER_INVALID`         | (empty)               | (empty) | 1 |
| `TRANSFORM.CASCADE_INVALID_WORLD`         | (empty)               | (empty) | 1 |
| `TRANSFORM.FLOATING_HEURISTIC`            | `translate_z_m`       | `floating_heuristic_z_m` | 1 |
| `TRANSFORM.OP_VALUE_COUNT_MISMATCH`       | `value_count`, `expected_count` | (empty) | 1 |
| `COLLIDER.NO_RIGID_BODY_ANCESTOR`         | (empty)               | (empty) | 1 |
| `COLLIDER.RIGID_BODY_WITHOUT_COLLIDER`    | (empty)               | (empty) | 1 |
| `COLLIDER.MESH_ON_DYNAMIC`                | (empty)               | (empty) | 2 |
| `COLLIDER.CONVEX_DECOMP_HULL_LIMIT`       | `hull_count`          | `hull_threshold` | 1 |
| `COLLIDER.AABB_MISMATCH`                  | `ratio_{x,y,z}`       | `aabb_ratio_max` | 1 |
| `COLLIDER.MISSING_COLLISION_GROUP`        | (empty)               | (empty) | 1 |
| `COLLIDER.COOKING_FAILED`                 | (empty)               | (empty) | 1 |
| `COLLIDER.MASS_OUT_OF_RANGE`              | `mass_kg`             | `mass_min_kg`, `mass_max_kg` | 1 |
| `COLLIDER.MASS_DENSITY_CONFLICT`          | `mass_kg`, `expected_mass_kg`, `relative_error` | `mass_density_tolerance` | 1 |
| `COLLIDER.DEGENERATE_AABB`                | `min_extent_m`        | `min_aabb_extent_m` | 1 |
| `COLLIDER.EXTREME_ASPECT_RATIO`           | `aspect_ratio`        | `max_aabb_aspect_ratio` | 1 |
| `GROUNDING.NO_INTENT_TAG`                 | (empty)               | (empty) | 1 |
| `GROUNDING.FLOATING`                      | `gap_m`, `aabb_bottom_z_m`, `support_hit_z_m` | `floating_tolerance_m` | 1 |
| `GROUNDING.BURIED`                        | `gap_m`, `aabb_bottom_z_m`, `support_hit_z_m` | `buried_tolerance_m` | 1 |
| `GROUNDING.NO_SUPPORT_FOUND`              | `aabb_bottom_z_m`     | (empty) | 1 |
| `RESET.POSE_TRANSLATION_DRIFT`            | `translation_delta_m`, `cycle_index` | `translation_tolerance_m` | 1 |
| `RESET.POSE_ROTATION_DRIFT`               | `rotation_delta_rad`, `cycle_index`  | `rotation_tolerance_rad`  | 1 |
| `RESET.LINEAR_VELOCITY_DRIFT`             | `linear_velocity_m_per_s`, `cycle_index` | `velocity_tolerance_m_per_s` | 1 |
| `RESET.ANGULAR_VELOCITY_DRIFT`            | `angular_velocity_rad_per_s`, `cycle_index` | `angular_velocity_tolerance_rad_per_s` | 1 |
| `RESET.DETERMINISM_FLAG_MISSING`          | (empty)               | (empty) | 0 |
| `RESET.SEED_NOT_FIXED`                    | (empty)               | (empty) | 0 |
| `RESET.CYCLE_VARIANCE_TRANSLATION`        | `translation_delta_m`, `cycle_index` | `cycle_variance_translation_m` | 1 |
| `RESET.CYCLE_VARIANCE_ROTATION`           | `rotation_delta_rad`,  `cycle_index` | `cycle_variance_rotation_rad`  | 1 |
| `RESET.NON_DETERMINISTIC_AUTHORING`       | (empty)               | (empty) | 1 |
| `RESET.SPAWN_ORDER_MISMATCH`              | `cycle_index`         | (empty) | 0 |
| `RESET.CONTACT_AFTER_RESET`               | `penetration_depth_m`, `cycle_index` | `max_penetration_after_reset_m` | 2 |
| `RESET.BODY_SET_MISMATCH`                 | `missing_count`, `extra_count` | (empty) | 0 |
| `*.NO_STAGE_INSPECTOR` / `NO_COLLIDER_INSPECTOR` / `NO_INSPECTOR` / `NO_SIMULATOR` (guards) | (empty) | (empty) | 0 |

---

## 4. CLI text rendering

Default output of `--reporter text`:

```
Asset:       file:///home/cap2/last/assets/example.usd
Criteria:    .../configs/acceptance_default.yaml (sha256: 7c0a2f…)
Seed:        0
Validators:  hierarchy, transform, collider, overlap
Duration:    4.18 s

[FAIL] OVERLAP.PEN_DEPTH_EXCEEDED            overlap
   prims: /World/A, /World/B
   Unexpected contact between '/World/A' and '/World/B' penetrates 2.000 mm (threshold 1.000 mm).
   metric: penetration_depth_m=0.002
   threshold: pen_depth_max_m=0.001

[WARN] OVERLAP.PEN_DEPTH_EXCEEDED_FIT        overlap
   prims: /World/C, /World/D
   Expected-contact pair '/World/C' <-> '/World/D' penetrates 0.500 mm (fit threshold 0.100 mm).
   metric: penetration_depth_m=0.0005
   threshold: pen_depth_max_fit_m=0.0001

Summary: FAIL=1  WARN=1  INFO=0    status=FAIL
```

Rules:

- Tag column is fixed width (`[FAIL]`, `[WARN]`, `[INFO]`) — 6 chars.
- Code column is 40 chars left-aligned.
- Validator name right-aligned at column 80.
- ANSI colour is enabled only when stdout is a TTY (mirrors `scripts/validate_runtime.sh`).

---

## 5. JUnit XML rendering

For CI integration. One `<testsuite>` per validator; one `<testcase>` per issue.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="asset_validator" tests="2" failures="1" errors="0" time="4.182">
  <testsuite name="overlap" tests="2" failures="1">
    <testcase classname="OVERLAP.PEN_DEPTH_EXCEEDED"
              name="/World/A,/World/B"
              time="0.000">
      <failure type="FAIL"
               message="Unexpected contact ...">
        metric.penetration_depth_m=0.002
        threshold.pen_depth_max_m=0.001
      </failure>
    </testcase>
    <testcase classname="OVERLAP.PEN_DEPTH_EXCEEDED_FIT"
              name="/World/C,/World/D"
              time="0.000">
      <!-- WARN: a non-failing testcase with system-out, no failure tag -->
      <system-out>WARN: Expected-contact pair ...</system-out>
    </testcase>
  </testsuite>
</testsuites>
```

Conventions:

- Severity `FAIL` → `<failure>`; `WARN` → `<system-out>`; `INFO` → `<system-out>` with `INFO: ` prefix.
- `classname` carries the issue code (so CI dashboards can group by it).
- `name` carries the affected prim paths joined by `,`.

---

## 6. Output file layout

Per [docs/storage_policy.md](storage_policy.md), all reports land under the workspace:

```
${WORKSPACE_ROOT}/outputs/asset_validation/<run-id>/
├── report.json         # §2 schema, primary artifact
├── report.txt          # §4 text rendering
├── report.junit.xml    # §5 JUnit (CI consumption)
└── stdout.log          # full stdout of the validator process
```

`<run-id>` defaults to a UTC timestamp `YYYYMMDDTHHMMSSZ` plus an 8-char hash of `(asset_uri + criteria_digest + seed)`. CLI flag `--out-dir` overrides the full path.

---

## 7. Versioning

The `schema_version` field at the report root follows semver:

- **PATCH**: doc-only changes (clarifications, typos).
- **MINOR**: append-only — new optional fields, new issue codes, new validators added.
- **MAJOR**: incompatible — renamed fields, removed codes, changed field types, changed ordering rule.

Consumers must accept any future MINOR version of the same MAJOR; they must reject MAJOR mismatches with a clear error.

Current: **`1.1.0`** (covers v1.1: OverlapValidator, TransformValidator, ColliderValidator, GroundingValidator (static), and DeterministicResetValidator implemented; HierarchyValidator and dynamic-grounding variant deferred to Phase 2 with reserved code namespaces). Bump from `1.0.0` is MINOR because the change is purely additive — all 1.0.0 codes remain valid with the same semantics.
