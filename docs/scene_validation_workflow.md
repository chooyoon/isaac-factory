# Scene Validation Workflow

**Workspace**: `/home/cap2/last`
**Companion to**: [docs/asset_validator_design.md](asset_validator_design.md), [docs/asset_validator_acceptance.md](asset_validator_acceptance.md), [docs/asset_validator_report_format.md](asset_validator_report_format.md)
**Implements**: [scripts/run_scene_validation.sh](../scripts/run_scene_validation.sh)
**Status**: Authoritative for the **order**, **phasing**, and **failure semantics** of running the asset validators against a scene. Per-validator rules live in the acceptance doc; per-report shape lives in the report-format doc.
**Last revised**: 2026-05-18

This document defines the canonical eight-step workflow for validating one scene against all currently-implemented validators. It is the runtime counterpart to the design doc's architectural section — same components, different angle: the design doc says **what** each part is; this doc says **when** and **why** in what order.

---

## 1. Workflow at a glance

```
        ┌──────────────────────────────────────────────────────┐
        │  1. Load scene                                       │
        │      open USD into anonymous root layer (read-only)  │
        └────────────────────────┬─────────────────────────────┘
                                 ▼
        ┌──────────────────────────────────────────────────────┐  ─┐
        │  2. Validate transforms  → TransformValidator        │   │
        └────────────────────────┬─────────────────────────────┘   │
                                 ▼                                  │  STATIC PHASE
        ┌──────────────────────────────────────────────────────┐   │  (no physics)
        │  3. Validate colliders   → ColliderValidator         │   │
        └────────────────────────┬─────────────────────────────┘   │
                                 ▼                                  │
        ┌──────────────────────────────────────────────────────┐   │
        │  4. Validate grounding   → GroundingValidator        │   │
        │     raycast-based (static geometric)                 │   │
        └────────────────────────┬─────────────────────────────┘  ─┘
                                 │   ── physics-init boundary ──
                                 ▼
        ┌──────────────────────────────────────────────────────┐  ─┐
        │  5. Validate overlap     → OverlapValidator          │   │
        │     1 physics step from settled initial state        │   │
        └────────────────────────┬─────────────────────────────┘   │
                                 ▼                                  │  DYNAMIC PHASE
        ┌──────────────────────────────────────────────────────┐   │
        │  6. Physics settle                                   │   │
        │     N = 60 steps @ 60 Hz (1.0 s)                     │   │
        └────────────────────────┬─────────────────────────────┘   │
                                 ▼                                  │
        ┌──────────────────────────────────────────────────────┐   │
        │  7. Deterministic reset  → DeterministicResetValidator │  │
        │     3 cycles × 100 steps, fixed seed                 │   │
        └────────────────────────┬─────────────────────────────┘  ─┘
                                 ▼
        ┌──────────────────────────────────────────────────────┐
        │  8. Aggregate → PASS / WARN / FAIL                   │
        │     write summary.txt, report.json, junit.xml        │
        └──────────────────────────────────────────────────────┘
```

---

## 2. Ordering rationale

The order is **not** arbitrary. Three principles drive it:

1. **Cheapest first, heaviest last.** Each step's cost in wall time and resources grows down the list. A run that's destined to fail should fail as early as possible.
2. **Static before dynamic.** Steps 2–4 require no physics scene. They run before PhysX is initialized — so a malformed asset that would crash physics initialization is caught and reported, not crashed-on.
3. **Each step's preconditions are met by the previous one.** Overlap needs colliders that cooked successfully (§5 prerequisite is §3). Reset validation needs an asset that survives one settle without divergence (§7 prerequisite is §6). Settle needs physics initialized (§6 prerequisite is §5's init).

| Step | Static / Dynamic | Approx cost (single asset) | Why this position |
|---|---|---|---|
| 1. Load             | n/a     | < 1 s   | Trivial; everything depends on it |
| 2. Transforms       | static  | 1–3 s   | NaN/Inf catches everything else's noise before it spreads |
| 3. Colliders        | static  | 2–5 s   | Catches PhysX schema issues that would otherwise abort step 4's init |
| 4. Grounding        | static  | 1–3 s   | Raycast is geometric; cheap and identifies obviously-wrong staging early |
| 5. Overlap          | dynamic | 5–15 s  | First step needing PhysX; checks t=0 contact state |
| 6. Physics settle   | dynamic | 1–3 s   | Required by step 7's "after_step" snapshot |
| 7. Reset validation | dynamic | 30–90 s | Heaviest by far (3 cycles × 100 steps × full scene); run last so earlier failures surface first |
| 8. Aggregate        | n/a     | < 1 s   | Pure I/O |

---

## 3. Step details

### Step 1 — Load scene

| Aspect | Value |
|---|---|
| Component | `stage_io.open_for_validation` (deferred — see [design doc §5.4](asset_validator_design.md#54-read-only-guarantee)) |
| Input | A USD file path or `omniverse://` URI |
| Action | `Usd.Stage.Open` against an **anonymous root layer** that references the asset. Source file is never written. |
| Failure | If the asset cannot be opened, the workflow aborts here with exit code 1 and an `IO.STAGE_LOAD_FAILED`-style error |
| Read-only invariant | Stage is held in memory only; `Save()` is never called on the source layer |

### Step 2 — Validate transforms

| Aspect | Value |
|---|---|
| Validator | `TransformValidator` (phase = static) |
| Reads | `StageInspector.iter_xformable_prims()` |
| Emits codes | `TRANSFORM.NAN_VALUE`, `TRANSFORM.INF_VALUE`, `TRANSFORM.ZERO_SCALE`, `TRANSFORM.SCALE_OUT_OF_RANGE`, `TRANSFORM.NON_POSITIVE_SCALE`, `TRANSFORM.QUATERNION_DENORMAL`, `TRANSFORM.ROTATION_NON_ORTHOGONAL`, `TRANSFORM.TRANSLATION_OUT_OF_RANGE`, `TRANSFORM.TIME_SAMPLED_ON_STATIC`, `TRANSFORM.MIXED_OP_ORDER`, `TRANSFORM.XFORMOP_ORDER_INVALID`, `TRANSFORM.CASCADE_INVALID_WORLD`, `TRANSFORM.FLOATING_HEURISTIC`, `TRANSFORM.OP_VALUE_COUNT_MISMATCH` |
| Why first | NaN/Inf in any transform op cascades through the world matrix to every descendant. Catching it at step 2 makes the cascade pattern visible before downstream checks misread the same data |

### Step 3 — Validate colliders

| Aspect | Value |
|---|---|
| Validator | `ColliderValidator` (phase = static) |
| Reads | `ColliderInspector.iter_colliders()`, `.iter_rigid_bodies()` |
| Emits codes | `COLLIDER.NO_RIGID_BODY_ANCESTOR`, `COLLIDER.RIGID_BODY_WITHOUT_COLLIDER`, `COLLIDER.MESH_ON_DYNAMIC`, `COLLIDER.CONVEX_DECOMP_HULL_LIMIT`, `COLLIDER.AABB_MISMATCH`, `COLLIDER.MISSING_COLLISION_GROUP`, `COLLIDER.COOKING_FAILED`, `COLLIDER.MASS_OUT_OF_RANGE`, `COLLIDER.MASS_DENSITY_CONFLICT`, `COLLIDER.DEGENERATE_AABB`, `COLLIDER.EXTREME_ASPECT_RATIO` |
| Why second | Validates the schemas PhysX will read at init. A mesh approximation on a dynamic body would cause PhysX to silently fall back to the visual mesh (or refuse to cook); catching it here gives a clear error instead of a confusing physics behaviour later |

### Step 4 — Validate grounding

| Aspect | Value |
|---|---|
| Validator | `GroundingValidator` (phase = static, raycast-based) |
| Reads | `GroundingInspector.iter_grounding_probes()` — pre-computed downward raycasts |
| Emits codes | `GROUNDING.FLOATING`, `GROUNDING.BURIED`, `GROUNDING.NO_SUPPORT_FOUND`, `GROUNDING.NO_INTENT_TAG` |
| Why third | This is the **static** grounding check — geometric, not physics-based. The acceptance doc §5 dynamic check (settle + residual-velocity) is **separate** and currently not implemented. Running the static check before physics init catches obviously-floating placements without paying the physics-init cost. See [GroundingValidator's module docstring](../isaac_factory/extensions/asset_validator/asset_validator/validators/grounding.py) for the distinction |

> **Physics-init boundary** — the line between steps 4 and 5. Crossing it means: the World is created, PhysX cooks all colliders, the scene is loaded into the solver, deterministic flags + seeds are set. From here on, validators consume live physics state.

### Step 5 — Validate overlap

| Aspect | Value |
|---|---|
| Validator | `OverlapValidator` (phase = dynamic) |
| Reads | `ContactSource.query_contacts()` after a single measurement step |
| Procedure | `World.reset()` → step `physics_settle_pre_steps` (default 5) for contact resolution → step 1 measurement frame → query contacts |
| Emits codes | `OVERLAP.PEN_DEPTH_EXCEEDED`, `OVERLAP.PEN_DEPTH_EXCEEDED_FIT`, `OVERLAP.SELF_INTERSECTION` |
| Why fourth | First dynamic check; doesn't yet need a full settle. Catches authoring issues (parts that intersect at their authored pose) cheaply before paying for step 7's multi-cycle cost |

### Step 6 — Physics settle

| Aspect | Value |
|---|---|
| Component | `IsaacWorldAdapter` (deferred) — `world.step(render=False)` × N |
| Default | N = 60 steps @ 60 Hz = 1.0 s |
| Action | Lets gravity and constraints reach steady state. Required by step 7 because reset validation snapshots `after_step` to compare against initial pose — the body needs to have moved *somewhere* during the cycle |
| Emits codes | None directly. Settle failures (NaN positions, exploded constraints) surface as failures in step 7 via `RESET.BODY_SET_MISMATCH` or `RESET.POSE_*_DRIFT` |
| Why sixth | After cheap dynamic check (step 5) but before the multi-cycle heavy check (step 7) |

### Step 7 — Deterministic reset validation

| Aspect | Value |
|---|---|
| Validator | `DeterministicResetValidator` (phase = dynamic) |
| Reads | `ResetSimulator.get_reset_report()` — full multi-cycle report |
| Procedure | 3 cycles × 100 steps × fixed seed; snapshot at initial, after_step, after_reset of each cycle |
| Emits codes | `RESET.POSE_TRANSLATION_DRIFT`, `RESET.POSE_ROTATION_DRIFT`, `RESET.LINEAR_VELOCITY_DRIFT`, `RESET.ANGULAR_VELOCITY_DRIFT`, `RESET.DETERMINISM_FLAG_MISSING`, `RESET.SEED_NOT_FIXED`, `RESET.CYCLE_VARIANCE_TRANSLATION`, `RESET.CYCLE_VARIANCE_ROTATION`, `RESET.NON_DETERMINISTIC_AUTHORING`, `RESET.SPAWN_ORDER_MISMATCH`, `RESET.CONTACT_AFTER_RESET`, `RESET.BODY_SET_MISMATCH` |
| Why last | Heaviest single step (3 cycles × 100 steps × full scene = 300 simulation steps minimum). Running last ensures cheaper failures surface first |

### Step 8 — Aggregate → PASS / WARN / FAIL

| Aspect | Value |
|---|---|
| Component | The runner script's analyzer; in CLI mode, `ValidationReport` aggregation |
| Action | Combine all issues from steps 2–7, sort per [report-format §2.3](asset_validator_report_format.md#23-issue-ordering), compute status per the rule below, write outputs per §5 of this doc |
| Output | `summary.txt`, `report.json`, JUnit XML, individual step logs |

**Overall status rule** (mirrors [report-format §2.2](asset_validator_report_format.md#22-field-reference)):

- `FAIL` if any Issue is severity FAIL, or if step 1 (load) failed.
- `WARN` if no FAIL but at least one Issue is severity WARN.
- `PASS` if no FAIL and no WARN.

---

## 4. Phase boundary semantics

The static / dynamic split (steps 2–4 vs 5–7) determines failure-isolation behaviour.

### `--strict-static` (default on)

If any static-phase validator (steps 2, 3, or 4) emits a FAIL Issue, the dynamic phase **is not run**. Steps 5–7 are recorded as `skipped` in the report with reason `strict-static-fail`. Rationale: a structurally broken asset (NaN transform, mesh-on-dynamic, missing collider) will produce garbage physics results, and the time spent computing those results is wasted.

### `--strict-static=off`

The dynamic phase runs even if static steps reported FAILs. Useful when triaging: the user wants to see the full picture before remediating. Default for `--deep` runs.

### Per-step exit on FAIL

Within a phase, a FAIL in one step **does not** skip subsequent steps of the same phase. All static validators always run when the static phase runs; same for dynamic. This is so an asset with multiple problems gets a complete report on the first pass.

---

## 5. Outputs and artifacts

Per [docs/storage_policy.md §3](storage_policy.md), all outputs land under the workspace:

```
$WORKSPACE_ROOT/outputs/asset_validation/<run-id>/
├── summary.txt                ← human-readable PASS/WARN/FAIL report
├── report.json                ← machine-readable report (schema_version 1.0.0)
├── unit.junit.xml             ← raw pytest JUnit, unit suite
├── unit.log                   ← full stdout/stderr, unit suite
├── scene_integrity.junit.xml  ← raw pytest JUnit, scene_integrity suite
└── scene_integrity.log        ← full stdout/stderr, scene_integrity suite
```

`<run-id>` defaults to `run-<UTC-timestamp>` (e.g., `run-20260518T120000Z`). The runner script's `--out-dir` flag overrides this.

In **CLI mode** (when `asset_validator.cli.validate` ships), the same layout will apply, with the four `*.junit.xml` and `*.log` files replaced by per-step artifacts (`step02_transform.junit.xml`, `step05_overlap.json`, etc.) — same directory shape, same status semantics.

---

## 6. Invocation

### Current — test-suite driven (no CLI yet)

```bash
# 1. Open a fresh shell, activate research profile (policy §4)
source scripts/activate_factory_env.sh research

# 2. Run validation against the workspace's test suites
bash scripts/run_scene_validation.sh

# 3. Inspect outputs
ls outputs/asset_validation/run-<timestamp>/
cat outputs/asset_validation/run-<timestamp>/summary.txt
```

Exit code 0 means PASS or PASS-with-warnings; 1 means FAIL; 2 means an environment problem (no pytest, missing workspace).

### Future — direct CLI

```bash
# Profile B (isaac); requires real adapters / simulator
"$ISAAC_PATH/python.sh" -m asset_validator.cli.validate \
    --asset path/to/scene.usd \
    --validators overlap,transform,collider,grounding,deterministic_reset \
    --reporter text,json,junit \
    --out-dir "$WORKSPACE_ROOT/outputs/asset_validation/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

The CLI will accept the same flags from any profile because all adapter wiring happens inside the entry point.

---

## 7. Performance characteristics

| Step | Single small asset (≤ 100 prims) | Full factory cell (~1000 prims) |
|---|---|---|
| 1. Load          | < 1 s   | 1–3 s   |
| 2. Transforms    | 1–2 s   | 3–8 s   |
| 3. Colliders     | 1–2 s   | 5–15 s  |
| 4. Grounding     | 1 s     | 2–5 s   |
| 5. Overlap       | 3–8 s   | 10–30 s |
| 6. Settle        | 1 s     | 2–5 s   |
| 7. Reset (3×100) | 20–40 s | 60–180 s|
| 8. Aggregate     | < 1 s   | < 1 s   |
| **Total**        | **~ 30–60 s** | **~ 90–250 s** |

The reset step dominates. If you only need static checks, pass `--skip-dynamic` (deferred CLI flag) — saves ~80 % of the budget.

---

## 8. Failure-class quick reference

When `summary.txt` ends in `Overall : FAIL`, the most common root causes by step:

| Step | Most common FAIL | Most common fix |
|---|---|---|
| 2. Transforms | `TRANSFORM.NAN_VALUE` propagated from a parent | Re-author the parent xform; cascade INFOs identify descendants |
| 2. Transforms | `TRANSFORM.QUATERNION_DENORMAL` after authoring an Euler-derived quaternion | Re-normalize before write |
| 3. Colliders | `COLLIDER.MESH_ON_DYNAMIC` | Change approximation to `convexHull` or `convexDecomposition` |
| 3. Colliders | `COLLIDER.COOKING_FAILED` (degenerate mesh) | Clean the input mesh; or fall back to `box` collider |
| 4. Grounding | `GROUNDING.FLOATING` with > 50 mm gap | Wrong AABB origin or wrong support surface placement |
| 4. Grounding | `GROUNDING.NO_SUPPORT_FOUND` | The scene's static floor is missing or out of raycast range |
| 5. Overlap | `OVERLAP.PEN_DEPTH_EXCEEDED` between authored-adjacent parts | Add the pair to `expects_contact` if intentional, or adjust authored pose |
| 7. Reset | `RESET.DETERMINISM_FLAG_MISSING` | Set `physxScene:useDeterministicSimulation = True` |
| 7. Reset | `RESET.POSE_TRANSLATION_DRIFT` only on cycle 2+ | Reset hook isn't actually resetting; check `World.reset()` wiring |

---

## 9. Relationship to other documents

| Document | Role |
|---|---|
| [docs/asset_validator_design.md](asset_validator_design.md)      | What each validator is, what its API surface is, what it depends on |
| [docs/asset_validator_acceptance.md](asset_validator_acceptance.md) | The numeric thresholds and per-rule severities that each step enforces |
| [docs/asset_validator_report_format.md](asset_validator_report_format.md) | The on-disk and on-stream shape of the outputs produced by step 8 |
| [docs/runtime_policy.md](runtime_policy.md)         | Which Python runtime runs which step (dynamic phase lives in Runtime B) |
| [docs/storage_policy.md](storage_policy.md)         | Where outputs land |
| [scripts/run_scene_validation.sh](../scripts/run_scene_validation.sh) | The script that drives this workflow today |
| [scripts/validate_runtime.sh](../scripts/validate_runtime.sh)        | Sibling doctor for the runtime itself; complementary, not overlapping |

---

## 10. Open questions / known gaps

| # | Item | Status |
|---|---|---|
| 1 | `HierarchyValidator` (acceptance §4) is designed but not implemented. When it ships, it will insert between steps 1 and 2 — the cheapest static check first | Deferred |
| 2 | The dynamic-phase **grounding** check (acceptance §5, settle + residual velocity) is not implemented; step 4 today is the static raycast variant only | Deferred |
| 3 | The Pipeline class (design doc §4.4) that actually orchestrates steps 2–8 is not implemented; the runner script drives the workflow through pytest invocations instead | Deferred |
| 4 | Real adapters (`adapters/usd_adapter.py`, `adapters/physx_adapter.py`, `adapters/isaac_world_adapter.py`) are not implemented; all validators currently consume mock inspectors injected by tests | Deferred — gates all dynamic-phase end-to-end runs |
| 5 | `--skip-dynamic`, `--strict-static`, `--seed`, `--criteria`, `--validators` CLI flags exist in the design doc (§4.6) but not in code | Deferred to CLI implementation |
| 6 | Multi-asset / batch validation (validate a directory of `.usd` files in one run) is explicitly out of scope for v1 | Out of scope |
| 7 | The eight-step workflow assumes one asset per run; collections need a separate orchestrator | Out of scope |

These do not block the workflow described here from being **specified** — they constrain only what an actual end-to-end run can do today.
