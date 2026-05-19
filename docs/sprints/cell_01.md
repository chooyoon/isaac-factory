# Sprint Contract — Cell 01

**Workspace**: `/home/cap2/last`
**Scope**: First industrial assembly cell — single-robot peg-into-housing on tray with conveyor in-feed / out-feed.
**Started**: 2026-05-18
**Status**: Phase 1A in progress.

This is the binding engineering contract for the cell-01 build. It is the single source of truth for what is in-scope, what is out-of-scope, what counts as "done", and the constraints that must not be relaxed for convenience.

---

## 1. Goals

1. Stand up the first **production-shape** industrial cell in Isaac Sim 5.0, validator-clean across all five Phase-1 validators.
2. Exercise the full A↔B↔C runtime topology end-to-end with a real workload (not a fixture).
3. Establish the conventions every subsequent cell will follow: modular USD composition, instanceable parts, deterministic physics, ROS-ready I/O.

## 2. Out of scope (explicitly)

- Multiple robots, multiple cells, mobile bases.
- Vision / sensors / cameras (beyond what the bridge publishes by default).
- Force/torque control loops; assembly is friction- and gravity-driven plus position trajectories.
- Mid-cycle prim add/remove (no procedural spawn in cycle).
- Parent-swap or runtime `FixedJoint` attach during pick (deferred to a later sprint with explicit determinism analysis).
- GUI-authored USD as primary source. GUI is inspection-only.
- Copying structure from `factory/`, `peg_in_hole_2026/`, or any other sibling tree.

## 3. Hard constraints

These are non-negotiable. A PR that weakens any of them is rejected without review.

- **No teleportation** of dynamic bodies. Motion is via friction, articulation joints, or kinematic surface velocity only.
- **No fake physics**. No per-frame pose overrides on rigid bodies. No "skip physics this frame" branches.
- **No triangle-mesh dynamic colliders**. Approximations must be in `ColliderThresholds.dynamic_allowed_approximations` (box, sphere, capsule, cylinder, convexHull, convexDecomposition).
- **No overlapping geometry** above thresholds: 1 mm for non-fit pairs, 0.1 mm for `expects_contact` fit pairs.
- **Deterministic by construction**. `physxScene:enableEnhancedDeterminism = True`, fixed `physics_dt = 1/60 s`, seeded RNGs, sorted prim iteration.
- **Reset reproducibility is mandatory**. `DeterministicResetValidator` must pass with default tolerances across ≥3 cycles.
- **Runtime separation preserved**. No cross-runtime imports. Bridge is the only B↔C transport.
- **Validator guarantees never weakened** for convenience. If a validator fails, we fix the scene, not the validator.

## 4. Decision log (input — user-confirmed before sprint start)

| # | Decision |
|---|---|
| 1 | Cell scope: single-robot peg-into-housing on tray with conveyor in/out. Architecture scalable toward multi-cell. |
| 2 | Robot: UR10e. Use Isaac Sim native asset; no custom URDF import pipeline. |
| 3 | Conveyor: `PhysxSurfaceVelocityAPI` + friction-based transport. No teleporting, no snap, no fake attach. |
| 4 | Authoring: programmatic `usd-core` in Runtime A. GUI is inspection-only. Generated USD must be deterministic, reviewable, diff-friendly. |
| 5 | Sprint contract location: `docs/sprints/cell_01.md` (this file). |

## 5. Phase plan (with exit gates)

Each phase exits only when the listed validators are green on the as-built stage.

### Phase 1 — Foundation
- **1A** Scaffolding, cell config, USD authoring primitives, first runnable cell stage (PhysicsScene + lights + floor), Runtime-A validator driver. **Exit**: TransformValidator + GroundingValidator (static) → 0 FAIL, 0 WARN on `assets/cells/cell_01.usda`.
- **1B** USD class-prim templates (`_StaticProp`, `_DynamicPart`, `_RobotLink`, `_BeltSurface`); materials (steel / ABS / rubber). **Exit**: class prims load via reference resolution; validators still green.
- **1C** Environment + fixtures: safety cage, robot pedestal, work fixture, conveyor frames (frames only, no belt surface yet). **Exit**: validators green; fixture count matches cell config.

### Phase 2 — Conveyor + consumables
- **2A** `machinery/conveyor_2m.usda` with kinematic belt surface + `PhysxSurfaceVelocityAPI`. **Exit**: validators green; belt approximation is `boundingCube`.
- **2B** Parts (peg, housing) and tray as `_DynamicPart` references with convex hull/decomp colliders. **Exit**: validators green at rest state; hull count ≤ 24 on housing.
- **2C** Runtime-B validator driver; merged A+B JSON report. **Exit**: all 5 validators → 0 FAIL combined; `criteria_digest` matches across A and B reports.

### Phase 3 — UR10e + pick/place cycle
- **3A** UR10e from Isaac Sim's bundled library, pedestal-mounted. **Exit**: articulation root validated; all 5 validators clean.
- **3B** Headless deterministic cycle: ingest → pick → place → out-feed. **Exit**: identical end-state across 3 reset cycles; reset validator clean.
- **3C** Per-cycle JSONL telemetry, fsync'd. **Exit**: telemetry survives Kit fast-shutdown.

### Phase 4 — ROS 2 wiring
- **4A** `cell_msgs/`. **Exit**: `colcon build` clean.
- **4B** Bridge enabled in cell-runner; `/cell_01/{joint_states,tick,conveyor/*/state}` published. **Exit**: topics visible from a `ros` shell.
- **4C** `cell_bringup/` + `cell_monitor`. **Exit**: 60 s headless run with no deadline-miss alarms.

## 6. Acceptance gates (sprint completion)

All of the following must hold:

1. `OverlapValidator` → 0 issues (FAIL or WARN) on the as-built rest state.
2. `TransformValidator` → 0 FAIL, 0 WARN.
3. `ColliderValidator` → 0 FAIL, 0 WARN; hull budget respected.
4. `GroundingValidator (static)` → 0 FAIL, 0 WARN; every static prop sits within ±5 mm of its authored support.
5. `DeterministicResetValidator` → PASS over 3 cycles with default tolerances; seed recorded.
6. 60 s headless cycle completes with no deadline-miss alarms on `/cell_01/tick`.
7. Merged JSON report under `outputs/cell_validation/<run-id>/` has a stable `criteria_digest`; two consecutive runs hash-match (excluding `started_at`, `duration_seconds`, `asset_uri`).
8. The cell builds reproducibly from `configs/cell_01.yaml` — same config → byte-identical `.usda` (modulo USD's timestamp comment, which we strip in the reporter).

## 7. Conventions inherited from Phase 1 (must not drift)

- Single `UsdPhysics.Scene` at `/World/PhysicsScene` with `physxScene:enableEnhancedDeterminism=True`.
- `customData.static_collider = true` on every collision-only environment prop.
- `customData["asset_validator"]["grounded"]` ∈ `{"true","false","kinematic"}` on every grounding candidate.
- Per-prim layout: `/visual` (Imageable only) sibling of `/collider` (CollisionAPI only).
- Sorted iteration in every authoring helper that emits prims.
- All randomness seeded from `runtime.seed` in `configs/cell_01.yaml`.

## 8. References

- [docs/runtime_policy.md](../runtime_policy.md) — runtime separation
- [docs/phase1_completion.md](../phase1_completion.md) — what the validators cover
- [docs/asset_validator_acceptance.md](../asset_validator_acceptance.md) — acceptance codes and thresholds
- [docs/scene_validation_workflow.md](../scene_validation_workflow.md) — 8-step pipeline
- [configs/cell_01.yaml](../../configs/cell_01.yaml) — cell config (sprint-scoped)
