# Asset Validator — Acceptance Criteria

**Companion to**: [docs/asset_validator_design.md](asset_validator_design.md)
**Status**: Synchronized with implementation as of 2026-05-18 (audit remediation pass). Proposed numeric defaults are unchanged from the initial draft; threshold values are still subject to revision once `06_ACCEPTANCE_CRITERIA.md` (not on host) becomes available.
**Authority**: This document is the **single source of truth for threshold values** and the **public registry of issue codes**. The machine-readable mirror at [`isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml`](../isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml) **must** match this doc; a unit test (`tests/unit/test_acceptance_docs_in_sync.py`, deferred) will assert equality.
**Last revised**: 2026-05-18

This document defines, for each validation category, the numeric thresholds and structural rules an asset must satisfy to pass. Every Issue raised by the validator must cite a rule from this document; conversely, every code emitted by the validator must appear here. Code names match the `CODE_*` constants in the validator modules.

**Implementation status legend** (added per audit remediation):

| Symbol | Meaning |
|---|---|
| **✓ implemented** | The validator emits this code; numeric threshold is the runtime default. |
| **△ deferred** | Documented for future implementation. Reserved code name; not emitted yet. |
| **⊖ collapsed** | The condition is captured by another rule's emit; no separate code. |

---

## 0. Conventions

- **Units**: meters (m), kilograms (kg), seconds (s), radians (rad). All numerical thresholds are SI unless explicitly noted.
- **Coordinate system**: Z-up, right-handed (USD default, Isaac Sim convention).
- **Time base**: physics_dt = 1/60 s (60 Hz), unless an asset overrides via custom metadata.
- **Severity**: `INFO` (advisory), `WARN` (degraded but usable), `FAIL` (must be fixed). Thresholds below specify the boundary between severities.
- **Tagging convention**: assets may declare expectations via `customData["asset_validator"]` on the defaultPrim — e.g., `{"grounded": true, "expects_contact": ["/World/AssemblyFrame"]}`.

Each row in the threshold tables below is a single rule, identified by an issue code (e.g., `OVERLAP.PEN_DEPTH_EXCEEDED`). Codes are **stable** — CI gates and Sprint Contracts reference them.

---

## 1. Overlap thresholds

Detected by `OverlapValidator` (dynamic phase) using PhysX contact reports after one settled physics step from the asset's initial pose.

| # | Issue code | Rule | Threshold | Severity | Status |
|---|---|---|---|---|---|
| 1.1 | `OVERLAP.PEN_DEPTH_EXCEEDED` | Maximum penetration depth between any two non-touching bodies at rest | ≤ 1.0 mm (1.0 × 10⁻³ m) | `FAIL` | ✓ |
| 1.2 | `OVERLAP.PEN_DEPTH_EXCEEDED_FIT` | Penetration depth between bodies tagged as `expects_contact` (e.g., snap-fit, press-fit) | ≤ 0.1 mm | `WARN` | ✓ |
| 1.3 | `OVERLAP.UNEXPECTED_CONTACT` | Contact between two bodies that are not in `expects_contact` for either side | 0 contact pairs allowed | `FAIL` | ⊖ subsumed by 1.1 (any non-fit pair above threshold triggers `PEN_DEPTH_EXCEEDED`); code reserved |
| 1.4 | `OVERLAP.CONVERGENCE_FAILURE` | Initial-state contact resolution must converge within N physics steps | N ≤ 5 steps | `FAIL` | △ requires multi-step measurement; `convergence_max_steps` threshold wired through but not yet enforced |
| 1.5 | `OVERLAP.SELF_INTERSECTION` | A single rigid body's collider self-intersecting with its own mesh (cooking artifact) | 0 self-contacts allowed | `FAIL` | ✓ |

### Procedure

1. World.reset() → physics step ×`physics_settle_pre_steps` (default 5) with all dynamic bodies disabled.
2. Re-enable physics, step 1 frame.
3. Query `PxContactManager` for all contact pairs and per-pair `depth_max`.
4. Classify each pair against `expects_contact` tags.

### Inputs the validator may rely on

- `customData["asset_validator"]["expects_contact"]: list[str]` on the defaultPrim — Sdf paths of allowed contact partners.

---

## 2. Invalid transform rules

Detected by `TransformValidator` (static phase) via `pxr.UsdGeom.XformCommonAPI` and direct `xformOpOrder` inspection.

| # | Issue code | Rule | Threshold | Severity | Status |
|---|---|---|---|---|---|
| 2.1  | `TRANSFORM.NAN_VALUE` | No NaN in any translation, rotation, or scale component | 0 NaN values | `FAIL` | ✓ |
| 2.2  | `TRANSFORM.INF_VALUE` | No Inf or -Inf in any transform value | 0 Inf values | `FAIL` | ✓ |
| 2.3  | `TRANSFORM.ZERO_SCALE` | No axis with scale magnitude < ε | `\|scale_axis\| ≥ 1.0 × 10⁻³` | `FAIL` | ✓ |
| 2.4  | `TRANSFORM.SCALE_OUT_OF_RANGE` | Scale magnitude on any axis within sanity bounds | `\|scale_axis\| ∈ [1.0 × 10⁻³, 1.0 × 10⁺³]` | `FAIL` | ✓ |
| 2.5  | `TRANSFORM.NON_POSITIVE_SCALE` | Negative scale only allowed with explicit mirror metadata | `scale > 0` unless `customData["mirror"]: true` | `WARN` (escalate to `FAIL` if collider present) | ✓ |
| 2.6  | `TRANSFORM.QUATERNION_DENORMAL` | Quaternion magnitude must be near unit | `\|q\| ∈ [0.999, 1.001]` | `FAIL` | ✓ |
| 2.7  | `TRANSFORM.ROTATION_NON_ORTHOGONAL` | If transform is given as a 3×3 / 4×4 matrix, rotation submatrix must be orthogonal | Frobenius norm of `RᵀR − I` ≤ 1.0 × 10⁻⁴ | `FAIL` | ✓ |
| 2.8  | `TRANSFORM.TRANSLATION_OUT_OF_RANGE` | Translation magnitude within plausible scene bounds | `\|t\| ≤ 1.0 × 10⁶ m` | `WARN` | ✓ |
| 2.9  | `TRANSFORM.TIME_SAMPLED_ON_STATIC` | Static asset must not have time-sampled `xformOp:*` values | 0 time samples on default-static prims | `WARN` | ✓ |
| 2.10 | `TRANSFORM.MIXED_OP_ORDER` | Within one prim, all `xformOpOrder` ops must be from the same authoring style (no mix of `xformOp:transform` with separate translate/rotate/scale) | single-style only | `WARN` | ✓ |
| 2.11 | `TRANSFORM.XFORMOP_ORDER_INVALID` | `xformOpOrder` references an op that is not present on the prim (hierarchy corruption) | 0 unresolved op names | `FAIL` | ✓ |
| 2.12 | `TRANSFORM.CASCADE_INVALID_WORLD` | Descendant of a prim that failed a transform rule has an unreliable world matrix | per-descendant marker | `INFO` | ✓ |
| 2.13 | `TRANSFORM.FLOATING_HEURISTIC` | Local `translate.z` above the floating-heuristic threshold (static, geometric) | `z ≤ 100 m` (configurable; `None`/`0` disables) | `WARN` | ✓ |
| 2.14 | `TRANSFORM.OP_VALUE_COUNT_MISMATCH` | xformOp's value array has the wrong length for its op type | translate/scale=3, rotate_quat=4, transform_matrix=16, … | `FAIL` | ✓ |

> Note: rule 2.13 is a **static heuristic** complementing the dynamic-grounding check in §5.A (deferred). It catches obviously-airborne placements at the transform layer without needing physics.

---

## 3. Collider requirements

Detected by `ColliderValidator` (static phase) via `pxr.UsdPhysics` schema inspection + PhysX cooking pre-flight.

| # | Issue code | Rule | Threshold / requirement | Severity | Status |
|---|---|---|---|---|---|
| 3.1  | `COLLIDER.NO_RIGID_BODY_ANCESTOR` | Every prim with `CollisionAPI` must have either a `RigidBodyAPI` ancestor or `customData["static_collider"]: true` | enforced | `FAIL` | ✓ |
| 3.2  | `COLLIDER.RIGID_BODY_WITHOUT_COLLIDER` | Every prim with `RigidBodyAPI` must have at least one descendant with `CollisionAPI` | ≥ 1 collider descendant | `FAIL` | ✓ |
| 3.3  | `COLLIDER.MESH_ON_DYNAMIC` | Dynamic rigid bodies must use primitive / convex hull / convex decomposition colliders — not raw triangle mesh | approximation in `{box, sphere, capsule, cylinder, convexHull, convexDecomposition}` | `FAIL` | ✓ |
| 3.4  | `COLLIDER.CONVEX_DECOMP_HULL_LIMIT` | Convex decomposition output bounded for cook time and runtime | ≤ 64 hulls (warn at 32) | `WARN` at 32, `FAIL` at 64 | ✓ |
| 3.5  | `COLLIDER.AABB_MISMATCH` | Collider AABB extent must not exceed the visual mesh AABB by more than 10 % per axis | ratio ≤ 1.10 per axis | `WARN` | ✓ |
| 3.6  | `COLLIDER.MISSING_COLLISION_GROUP` | Every CollisionAPI must specify a non-default collision group | `physxCollision:filterGroup` set explicitly | `WARN` | ✓ |
| 3.7  | `COLLIDER.COOKING_FAILED` | PhysX cooking must succeed at stage load (no errors in `omni.physx` log) | 0 cooking errors | `FAIL` | ✓ |
| 3.8  | `COLLIDER.STATIC_MISSING_KINEMATIC_FLAG` | Static colliders (no RigidBody ancestor) must be flagged kinematic or marked `customData["static_collider"]: true` | enforced | `WARN` | ⊖ collapsed into §3.1 (same condition, FAIL severity wins); code reserved |
| 3.9  | `COLLIDER.MASS_OUT_OF_RANGE` | Rigid body mass within sanity bounds | mass ∈ [1.0 × 10⁻³, 1.0 × 10⁵] kg | `WARN` | ✓ |
| 3.10 | `COLLIDER.MASS_DENSITY_CONFLICT` | If both `mass` and `density` are authored on the same body, they must be consistent | density × volume ≈ mass within ±10 % | `WARN` | ✓ |
| 3.11 | `COLLIDER.DEGENERATE_AABB` | Collider AABB has at least one axis below stability minimum (paper-thin geometry produces unstable contacts) | min axis extent ≥ 1.0 × 10⁻⁴ m (0.1 mm) | `WARN` | ✓ |
| 3.12 | `COLLIDER.EXTREME_ASPECT_RATIO` | Collider AABB max-axis / min-axis ratio above stability cap (sliver geometry causes cook + contact jitter) | ≤ 1000.0 | `WARN` | ✓ |

> Note: §3.11 and §3.12 are **stability heuristics** added to address the user-requested "unstable collider geometry" class. Codes precede the rule numbers in code; the rule numbers exist in this doc only.
> `COLLIDER.AABB_MISMATCH` (§3.5) was previously documented as `COLLIDER.COLLIDER_AABB_MISMATCH`; **renamed 2026-05-18** to match the validator's `CODE_AABB_MISMATCH` constant.

---

## 4. Hierarchy rules — **STATUS: DEFERRED TO PHASE 2**

`HierarchyValidator` is **not yet implemented**. The codes below are reserved for the deferred implementation. Once shipped, the validator slots into the workflow between scene-load and `TransformValidator` per [scene_validation_workflow.md §10 item 1](scene_validation_workflow.md).

Until then, certain hierarchy-corruption conditions are surfaced by the implemented validators:

- **xformOpOrder corruption** → `TRANSFORM.XFORMOP_ORDER_INVALID` (§2.11)
- **Orphan collider** → `COLLIDER.NO_RIGID_BODY_ANCESTOR` (§3.1)
- **Rigid body without collider** → `COLLIDER.RIGID_BODY_WITHOUT_COLLIDER` (§3.2)
- **Transform cascade from invalid parent** → `TRANSFORM.CASCADE_INVALID_WORLD` (§2.12)

Planned codes (all `△ deferred`):

| # | Issue code | Rule | Threshold / requirement | Severity |
|---|---|---|---|---|
| 4.1  | `HIERARCHY.MAX_DEPTH_EXCEEDED` | Maximum prim depth from stage root | ≤ 12 (warn at 10) | `WARN` at 10, `FAIL` at 12 |
| 4.2  | `HIERARCHY.MAX_CHILDREN_EXCEEDED` | Maximum children per Xform | ≤ 200 (warn at 100) | `WARN` at 100, `FAIL` at 200 |
| 4.3  | `HIERARCHY.MISSING_DEFAULT_PRIM` | Stage must declare a resolvable `defaultPrim` | enforced | `FAIL` |
| 4.4  | `HIERARCHY.NESTED_RIGID_BODY` | A `RigidBodyAPI` prim must not have an ancestor also carrying `RigidBodyAPI` | 0 nested rigid bodies | `FAIL` |
| 4.5  | `HIERARCHY.MULTIPLE_ARTICULATION_ROOTS` | Each articulation chain has exactly one `ArticulationRootAPI` | exactly 1 per chain | `FAIL` |
| 4.6  | `HIERARCHY.ORPHAN_COLLIDER` | A `CollisionAPI` prim must have either a `RigidBodyAPI` ancestor or be explicitly tagged static | enforced | `FAIL` |
| 4.7  | `HIERARCHY.UNRESOLVED_REFERENCE` | All `references` / `payloads` must resolve at stage load | 0 unresolved | `FAIL` |
| 4.8  | `HIERARCHY.PURPOSE_GUIDE_WITH_PHYSICS` | A prim with `purpose=guide` or `purpose=proxy` must not carry physics schemas | enforced | `FAIL` |
| 4.9  | `HIERARCHY.INSTANCEABLE_PROTOTYPE_INVALID` | Instanceable prims must point to a prototype that is itself a sane Xform subtree | enforced | `FAIL` |
| 4.10 | `HIERARCHY.NON_XFORM_PARENT_FOR_RIGID_BODY` | `RigidBodyAPI` may only be applied to an Xformable | enforced | `FAIL` |
| 4.11 | `HIERARCHY.SCHEMA_ON_INACTIVE_PRIM` | Physics schemas on inactive (`active=false`) prims are misleading | 0 such cases | `WARN` |

---

## 5. Grounding rules

Grounding is split into two variants. The **static raycast variant** (§5.B) is implemented today; the **dynamic settle variant** (§5.A) is deferred to Phase 2 alongside other dynamic-phase work.

### 5.A Dynamic grounding — **STATUS: DEFERRED TO PHASE 2**

Detected by a future dynamic implementation of `GroundingValidator` by stepping physics for a settle duration and measuring AABB position drift + residual velocity.

| # | Issue code | Rule | Threshold / requirement | Severity | Status |
|---|---|---|---|---|---|
| 5.A.1 | `GROUNDING.NO_GROUND_TAG` | Assets must declare grounding intent via `customData["asset_validator"]["grounded"]` ∈ `{true, false, "kinematic"}` | declaration required | `WARN` | △ |
| 5.A.2 | `GROUNDING.AABB_BELOW_SUPPORT` | For `grounded=true` assets, AABB lowest point must be within tolerance of the nearest support surface beneath it after settle | distance ≤ 5.0 mm | `FAIL` | △ |
| 5.A.3 | `GROUNDING.LINEAR_DRIFT_AFTER_SETTLE` | After settle (default 60 steps = 1 s @ 60 Hz), residual linear velocity for `grounded=true` bodies | `\|v\|₂ ≤ 1.0 mm/s` | `FAIL` | △ |
| 5.A.4 | `GROUNDING.ANGULAR_DRIFT_AFTER_SETTLE` | After settle, residual angular velocity | `\|ω\|₂ ≤ 0.5 °/s ≈ 8.7 × 10⁻³ rad/s` | `FAIL` | △ |
| 5.A.5 | `GROUNDING.KINEMATIC_NOT_PINNED` | `grounded="kinematic"` assets must show zero linear and angular velocity at all times | `\|v\|₂ = 0` and `\|ω\|₂ = 0` | `FAIL` | △ |
| 5.A.6 | `GROUNDING.FLOATING_OBJECT` | `grounded=true` and no static surface found within `floating_search_distance` below | search distance ≤ 10 m | `FAIL` | △ |
| 5.A.7 | `GROUNDING.SETTLE_BUDGET_EXCEEDED` | Settle process diverges (velocity growing) within budget | velocity must monotonically decrease across last 10 steps | `FAIL` | △ |

**Tunable parameters** (deferred):

| Parameter | Default |
|---|---|
| `settle_steps` | 60 (= 1.0 s at 60 Hz) |
| `ground_tolerance_m` | 5.0 × 10⁻³ |
| `max_linear_drift_m_per_s` | 1.0 × 10⁻³ |
| `max_angular_drift_rad_per_s` | 8.7 × 10⁻³ |
| `floating_search_distance_m` | 10.0 |

### 5.B Static grounding — **STATUS: IMPLEMENTED**

Detected by `GroundingValidator` (static, raycast-based) — consumes pre-computed downward-raycast results from a `GroundingInspector`. Workflow per [scene_validation_workflow.md §3 step 4](scene_validation_workflow.md).

| # | Issue code | Rule | Threshold / requirement | Severity | Status |
|---|---|---|---|---|---|
| 5.B.1 | `GROUNDING.NO_INTENT_TAG` | `customData["asset_validator"]["grounded"]` is absent or invalid (defaults to `"true"` for checks) | declaration required | `WARN` | ✓ |
| 5.B.2 | `GROUNDING.FLOATING` | Object's AABB-bottom sits more than `floating_tolerance_m` ABOVE the support surface | ≤ 5.0 mm | `FAIL` | ✓ |
| 5.B.3 | `GROUNDING.BURIED` | Object's AABB-bottom sits more than `buried_tolerance_m` BELOW the support surface (penetration) | ≤ 5.0 mm | `FAIL` | ✓ |
| 5.B.4 | `GROUNDING.NO_SUPPORT_FOUND` | Downward raycast from the object found no support within the inspector's search distance | enforced | `FAIL` | ✓ |

**Tunable parameters** (implemented):

| Parameter | Default |
|---|---|
| `floating_tolerance_m` | 5.0 × 10⁻³ |
| `buried_tolerance_m`   | 5.0 × 10⁻³ |

---

## 6. Deterministic reset requirements

Detected by `DeterministicResetValidator` (dynamic phase) by snapshotting body states, stepping physics, calling `World.reset()`, and comparing.

| # | Issue code | Rule | Threshold | Severity | Status |
|---|---|---|---|---|---|
| 6.1  | `RESET.POSE_TRANSLATION_DRIFT` | After reset, every dynamic body must return to its initial translation within tolerance | `‖Δt‖₂ ≤ 1.0 × 10⁻⁵ m` | `FAIL` | ✓ |
| 6.2  | `RESET.POSE_ROTATION_DRIFT` | After reset, rotation must return to initial within tolerance | quaternion-angle delta ≤ 1.0 × 10⁻⁴ rad | `FAIL` | ✓ |
| 6.3  | `RESET.LINEAR_VELOCITY_DRIFT` | Linear velocity at reset must be zero | `‖v‖₂ ≤ 1.0 × 10⁻⁶ m/s` | `FAIL` | ✓ |
| 6.4  | `RESET.ANGULAR_VELOCITY_DRIFT` | Angular velocity at reset must be zero | `‖ω‖₂ ≤ 1.0 × 10⁻⁶ rad/s` | `FAIL` | ✓ |
| 6.5  | `RESET.DETERMINISM_FLAG_MISSING` | Scene must have `useDeterministicSimulation = True` | enforced | `FAIL` | ✓ |
| 6.6  | `RESET.SEED_NOT_FIXED` | Seeds for NumPy, Python `random`, PhysX solver, and (if loaded) Warp must be set before each cycle | enforced | `FAIL` | ✓ |
| 6.7a | `RESET.CYCLE_VARIANCE_TRANSLATION` | After-step translation of cycle i must match cycle 1 | `‖Δt‖₂ ≤ 1.0 × 10⁻⁵ m` | `FAIL` | ✓ |
| 6.7b | `RESET.CYCLE_VARIANCE_ROTATION`    | After-step rotation of cycle i must match cycle 1    | quaternion-angle delta ≤ 1.0 × 10⁻⁴ rad | `FAIL` | ✓ |
| 6.8  | `RESET.NON_DETERMINISTIC_AUTHORING` | Asset must not use random initializers (`physxRigidBody:randomizedSeed`, etc.) | enforced | `WARN` | ✓ |
| 6.9  | `RESET.SPAWN_ORDER_MISMATCH` | Each cycle's spawn order must match `initial_spawn_order` | identical sequences | `FAIL` | ✓ |
| 6.10 | `RESET.CONTACT_AFTER_RESET` | After reset, no residual contact-pair penetration above tolerance | ≤ 1.0 × 10⁻⁶ m | `FAIL` | ✓ |
| 6.11 | `RESET.BODY_SET_MISMATCH` | After reset, the set of dynamic bodies must match the initial snapshot (no missing, no extra) | exact match | `FAIL` | ✓ |

> Rule 6.7 was a single code (`RESET.CYCLE_VARIANCE`) in the initial draft; **split 2026-05-18** into `_TRANSLATION` + `_ROTATION` to match the validator's two emit sites.

### Procedure

```
1. Set seeds (NumPy, Python random, PhysX solver, Warp if loaded).
2. World.reset().
3. Snapshot S₀ = {(prim_path, t, q, v, ω) for every dynamic body}.
4. For cycle in [1..3]:
     a. Step physics N = 100 frames.
     b. Snapshot Sₙ.
     c. World.reset().
     d. Snapshot S_reset.
     e. For each body, compute deltas vs S₀ → check rules 6.1–6.4.
     f. Compare Sₙ_cycle_i vs Sₙ_cycle_1 → check rules 6.7a / 6.7b.
     g. Compare cycle.spawn_order vs S₀.spawn_order → check rule 6.9.
     h. Compare cycle.contact_pairs_after_reset → check rule 6.10.
     i. Compare body-set of S_reset vs S₀ → check rule 6.11.
```

### Tunable parameters

| Parameter | Default |
|---|---|
| `steps_per_cycle` | 100 |
| `n_cycles`        | 3 |
| `seed`            | 0 (CLI-overridable) |
| `translation_tolerance_m`              | 1.0 × 10⁻⁵ |
| `rotation_tolerance_rad`               | 1.0 × 10⁻⁴ |
| `velocity_tolerance_m_per_s`           | 1.0 × 10⁻⁶ |
| `angular_velocity_tolerance_rad_per_s` | 1.0 × 10⁻⁶ |
| `cycle_variance_translation_m`         | 1.0 × 10⁻⁵ |
| `cycle_variance_rotation_rad`          | 1.0 × 10⁻⁴ |
| `max_penetration_after_reset_m`        | 1.0 × 10⁻⁶ |
| `require_determinism_flag`             | true |
| `require_seed`                         | true |

---

## 7. Infrastructure guard codes

These are emitted only when a validator's required dependency is missing from `ValidationContext` — they signal misconfiguration, not asset issues. All `FAIL` severity, all implemented (✓).

| Code | Validator | Trigger |
|---|---|---|
| `OVERLAP.…` | `OverlapValidator` | (none; missing ContactSource raises `AttributeError` — guard not yet emitted) |
| `TRANSFORM.NO_STAGE_INSPECTOR` | `TransformValidator` | `ctx.stage_inspector is None` |
| `COLLIDER.NO_COLLIDER_INSPECTOR` | `ColliderValidator` | `ctx.collider_inspector is None` |
| `GROUNDING.NO_INSPECTOR` | `GroundingValidator` | `ctx.grounding_inspector is None` |
| `RESET.NO_SIMULATOR` | `DeterministicResetValidator` | `ctx.reset_simulator is None` |

These codes do **not** indicate problems with the asset under test; they indicate the pipeline / adapter wiring is incomplete. CI gates may treat them differently from asset-level FAILs.

---

## 8. Severity escalation rules

Beyond per-rule severities, the report aggregator applies these escalation rules:

| Rule | Result |
|---|---|
| ≥ 3 distinct `WARN`s in the same validator class | escalate to `FAIL` for that validator class |
| Any `FAIL` in static phase + `--strict-static` (default true) | skip dynamic phase, overall report = `FAIL` |
| ≥ 1 `FAIL` total | overall report = `FAIL`, CLI exit code `1` |
| Only `WARN`s, no `FAIL`s | overall report = `WARN`, CLI exit code `0` (unless `--fail-on warn`) |
| Only `INFO`s | overall report = `INFO`, CLI exit code `0` |

---

## 9. Per-asset overrides

An asset MAY declare exception metadata on its defaultPrim:

```usda
customData = {
    dictionary asset_validator = {
        bool grounded = true
        token[] expects_contact = ["/World/AssemblyFrame", "/World/ConveyorBelt"]
        dictionary thresholds = {
            double pen_depth_max_m = 0.0005     # tighter than the default 0.001
        }
        token[] allowed_issue_codes = ["TRANSFORM.NON_POSITIVE_SCALE"]   # explicit waiver
    }
}
```

Rules:

1. **Loosening** a threshold (e.g., setting a larger penetration depth) is permitted only via `allowed_issue_codes` waivers — never by overriding the numeric threshold upward.
2. **Tightening** a threshold via `thresholds` is always permitted.
3. Every waiver code must be accompanied by a `# WAIVER:` comment in the USD file naming the engineering ticket and review date.
4. A unit test (`tests/regression/test_waivers_documented.py`, deferred) parses all assets in `tests/fixtures/` and `assets/` and asserts every waiver has a comment.

---

## 10. Versioning

This document is versioned with the validator extension. The header carries a `Last revised` date; the YAML mirror has a `schema_version` field. Breaking changes to thresholds (tightening, renaming codes) bump the minor version of the validator extension and trigger a workspace-wide re-validation gate.

**Code-stability invariants** (across revisions):

- An emitted code's **name** is permanent. Codes are reserved on retirement, not reused for another meaning.
- A code's **severity** may move up (WARN → FAIL) only with a major-version bump.
- A code's **numeric threshold** may change at minor version (subject to §9 §1 loosening rule).
- A code's **status** (✓ implemented / △ deferred / ⊖ collapsed) may change at any revision; the change is recorded in this doc.

---

## 11. Assumptions and gaps to revisit

Same caveat as the design doc: the source rules document (`06_ACCEPTANCE_CRITERIA.md`) is **not present on this host**, so every numeric value above is a **proposed default** based on:

- Standard PhysX tolerances (penetration depth, velocity zeros).
- Common USD asset-QA practice (hierarchy depth/breadth limits).
- The host's known hardware envelope (RTX 5090, 60 Hz physics dt).
- Conservative bias — when uncertain, set tighter thresholds; users can loosen via §9 waivers.

When the real source doc surfaces:

1. Diff its numeric values against §1–§6 here.
2. Where they disagree, the source doc wins; update both this file and the YAML mirror at [`isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml`](../isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml).
3. The deferred `tests/unit/test_acceptance_docs_in_sync.py` check will guarantee the YAML doesn't silently drift.
4. Sprint Contracts that referenced specific issue codes remain valid — codes are stable; only numeric values may move.

---

## 12. Quick-reference card

For Sprint Contract authors and reviewers:

| Validator | Top-level question it answers | Status |
|---|---|---|
| **OverlapValidator** | "Are any bodies passing through each other at rest?" | ✓ implemented |
| **TransformValidator** | "Are there any nonsense numbers or degenerate transforms?" | ✓ implemented |
| **ColliderValidator** | "Does every body that should physically interact have a sane collider?" | ✓ implemented |
| **HierarchyValidator** | "Is the prim tree shaped the way PhysX and USD expect?" | △ deferred to Phase 2 |
| **GroundingValidator** | "Do things that should sit on the floor actually sit on the floor?" | ✓ implemented (static); △ dynamic deferred |
| **DeterministicResetValidator** | "If I reset, do I get back exactly the state I started with — every time?" | ✓ implemented |

A run with overall status `PASS` (no `FAIL`s) is the prerequisite for any asset entering `assets/` from `cache/`, `outputs/`, or external sources.
