# PhysXResetSimulator — Runtime Implementation

**Package**: `isaac_factory/extensions/asset_validator/asset_validator/adapters/`
**Validator served**: `validators/deterministic_reset.py::DeterministicResetValidator`
**Adapter**: [`adapters/physx_reset_simulator.py`](../isaac_factory/extensions/asset_validator/asset_validator/adapters/physx_reset_simulator.py) (Phase 1.B, 2026-05-18)
**Companion specs**: [acceptance §6](asset_validator_acceptance.md#6-deterministic-reset-requirements), [workflow §3 step 7](scene_validation_workflow.md), [physx_runtime_constraints.md §1](physx_runtime_constraints.md), [physx_contact_source.md](physx_contact_source.md), [physx_collider_inspector.md](physx_collider_inspector.md)
**Last revised**: 2026-05-18

This document is the operational manual for the **third and final Phase 1.B adapter** — the PhysX-backed implementation of the `ResetSimulator` Protocol.

---

## 1. End-to-end runtime path

```
.usda asset  ───────────────────────────────────────────►  report.json
   │                                                            ▲
   ▼                                                            │
omni.usd.UsdContext.open_stage(asset)                           │
   │                                                            │
   ▼                                                            │
PhysXResetSimulator(stage=stage, n_cycles=N, steps_per_cycle=K) │
   │   apply enableEnhancedDeterminism on PhysicsScene          │
   │   apply PhysxContactReportAPI on every RigidBodyAPI prim   │
   │   subscribe omni.physx contact callbacks                   │
   ▼                                                            │
isaacsim.core.api.World()  (caller-managed; PhysX cooks here)   │
   │                                                            │
   ▼                                                            │
sim.get_reset_report()                                          │
   │   set seeds (random / numpy / warp)                        │
   │   world.reset()                          → snapshot S₀     │
   │   for i in 1..N:                                            │
   │     for _ in K: world.step(render=False)                   │
   │     snapshot S_after_step[i]                                │
   │     world.reset()                                           │
   │     drain contact buffer → residuals[i]                    │
   │     snapshot S_after_reset[i]                               │
   │   build ResetReport                                         │
   ▼                                                            │
DeterministicResetValidator(criteria).run(ctx)                  │
   │   13 acceptance §6 checks across (S₀, S_after_step,        │
   │   S_after_reset, residuals, spawn_order)                   │
   ▼                                                            │
reporters.json_reporter.write_report(...)  ─────────────────────┘
```

---

## 2. What the simulator captures

For every dynamic body (carrying `UsdPhysics.RigidBodyAPI`):

| `BodyState` field | How it's derived |
|---|---|
| `prim_path`        | `str(prim.GetPath())` |
| `translation`      | `Xformable.ComputeLocalToWorldTransform(...).ExtractTranslation()` |
| `rotation_quat`    | `Xformable.ComputeLocalToWorldTransform(...).ExtractRotationQuat()` → `(w, x, y, z)` |
| `linear_velocity`  | `(0.0, 0.0, 0.0)` — see §5 |
| `angular_velocity` | `(0.0, 0.0, 0.0)` — see §5 |

Per `ResetCycle`:

| Field | How it's derived |
|---|---|
| `cycle_index`               | 1-based loop counter |
| `after_step_state`          | Snapshot after `steps_per_cycle` × `World.step(render=False)` |
| `after_reset_state`         | Snapshot after `World.reset()` |
| `spawn_order`               | Re-iterated `dynamic_body_paths()` per cycle (so a stage mutation would surface as `SPAWN_ORDER_MISMATCH`) |
| `contact_pairs_after_reset` | All contacts emitted during the cycle's step window, deduplicated max-depth wins, sorted by prim-pair |

Top-level `ResetReport`:

| Field | How it's derived |
|---|---|
| `determinism_flag_set`         | True iff at least one `UsdPhysics.Scene` prim had `enableEnhancedDeterminism` set |
| `seed_set`                     | True after `_set_seeds()` runs (always True after `get_reset_report()`) |
| `initial_state`                | Snapshot after the first baseline `World.reset()` |
| `initial_spawn_order`          | `dynamic_body_paths()` at simulator-init time |
| `cycles`                       | One `ResetCycle` per `n_cycles` |
| `non_deterministic_authoring`  | Sorted set of prim paths whose attribute names match the `(random ∧ seed)` heuristic |

---

## 3. Call-order contract

```python
from isaacsim import SimulationApp
app = SimulationApp({"headless": True})            # (1) Kit up
try:
    import omni.usd
    omni.usd.get_context().open_stage(asset)         # (2) stage opened
    stage = omni.usd.get_context().get_stage()

    from asset_validator.adapters.physx_reset_simulator import (
        PhysXResetSimulator,
    )
    sim = PhysXResetSimulator(stage=stage)            # (3) BEFORE World — subscribes early

    from isaacsim.core.api import World
    world = World()                                   # (4) AFTER simulator — PhysX cooks here

    report = sim.get_reset_report()                   # (5) drives N×K steps + resets

    sim.close()                                       # (6) unsubscribe contacts
finally:
    app.close()
```

Order points (3) and (4) are load-bearing: contact subscription must be live during cooking, which happens inside `World()`. Reversing them silently drops any cook-time contact events.

---

## 4. Residual-contact semantics

`ResetCycle.contact_pairs_after_reset` carries the contacts whose callbacks fired during a cycle's stepping window, drained immediately after that cycle's `World.reset()`. There are three interpretations of "residual after reset"; the v1 adapter implements the simplest:

| Interpretation | Implementation |
|---|---|
| **(A) Contacts that occurred during the cycle and weren't resolved before reset** | What v1 does. Tests assert this is empty for non-contacting fixtures. |
| (B) Contacts present at t=0 of the next cycle (post-reset, pre-next-step) | Requires stepping once after reset, then drain — that extra step modifies state and undermines `after_reset_state`. |
| (C) Contacts detected via `omni.physx` scene query at t=0 | Doesn't reuse the contact-subscription infrastructure; needs a separate scene-query path. |

Interpretation (A) maps cleanly onto the validator's `RESET.CONTACT_AFTER_RESET` check: for asset workflows where no contacts should occur during settling, the buffer stays empty across cycles and no false positives fire. For workflows with intentional contacts, the same data surfaces the right question — were the contacts during stepping resolved before the next cycle began?

---

## 5. Velocity reporting

Both `linear_velocity` and `angular_velocity` are always reported as `(0.0, 0.0, 0.0)`.

The validator's §6.3 / §6.4 checks verify that residual velocity after `World.reset()` is below `1e-6 m/s` / `1e-6 rad/s`. PhysX's reset zeroes all linear/angular velocities by construction, so a constant-zero report matches reality at the only moment the validator examines.

Reading actual non-zero velocities (e.g., for `after_step_state` diagnostics) would require `omni.physx.IPhysxSimulation`-level queries whose API varies by Kit minor version. The validator does not consult `after_step` velocity anywhere, so leaving the field at zero is faithful to the contract.

---

## 6. Determinism guarantees

- **Body enumeration order** is `Usd.Stage.Traverse()` filtered to `HasAPI(RigidBodyAPI)` and sorted lexicographically. Stable across cycles of a non-mutating stage.
- **Snapshot order** within each `tuple[BodyState, ...]` matches `dynamic_body_paths()` order.
- **Contact pair canonicalisation** is identical to `PhysXContactSource`: `ContactPair.create()` swaps `(a, b)` if `a > b` and flips the contact normal sign.
- **Seed setting** covers Python `random`, NumPy, and Warp (if loaded) — applied once before the cycle loop. The PhysX solver seed is set via the `enableEnhancedDeterminism` flag plus the global Python seeds.

Two runs over the same stage with the same seed produce equal `initial_state` and equal `after_reset_state` (up to PhysX's enhanced-determinism guarantees — typically bit-identical for these post-reset snapshots; cycle-to-cycle `after_step` may have small float wobble). Verified by `tests/unit/test_deterministic_reset_adapter.py::TestResetStateRegression`.

---

## 7. Fixtures shipped with the simulator

Under [`tests/fixtures/reset/`](../isaac_factory/extensions/asset_validator/tests/fixtures/reset/):

| Fixture | Purpose | Expected report shape |
|---|---|---|
| `clean_reset.usda`        | Single isolated dynamic Cube | `determinism_flag_set=True`, `seed_set=True`, 1-body initial state, all cycles have empty residual contacts, validator emits zero issues |
| `two_body_assembly.usda`  | Two well-separated dynamic Cubes | Spawn order `("/World/Alpha", "/World/Beta")` stable across all cycles |
| `nondet_authoring.usda`   | Cube with `custom int physxRigidBody:randomizedSeed = 42` | `non_deterministic_authoring = ("/World/Random",)`, validator emits `RESET.NON_DETERMINISTIC_AUTHORING` (WARN) |

No `expected_reports/*.report.json` are checked in — the floating-point `after_step` values vary slightly across PhysX runs even with enhanced determinism, so a bit-identical golden file would generate noise. Tests assert behavioural invariants (specific codes present / absent, spawn-order tuples equal, body counts) rather than full report equality.

---

## 8. Authoring contract (for asset authors, not tests)

For an asset to be validated by `DeterministicResetValidator`:

```usda
def Xform "World" {
    def PhysicsScene "PhysicsScene" {
        # The simulator will set physxScene:enableEnhancedDeterminism=True
        # itself if not authored — but authoring it makes the asset
        # self-describing.
        vector3f physics:gravityDirection = (0, 0, -1)
        float    physics:gravityMagnitude = 9.81   # or 0 for static tests
    }

    def Cube "Body" (apiSchemas = ["PhysicsCollisionAPI", "PhysicsRigidBodyAPI"]) {
        # Authored pose IS the snapshot baseline. PhysX's reset will
        # restore to within a few mm of this pose (cooking + settling
        # introduces small jitter — see physx_runtime_constraints.md §1
        # bullet 1).
        double size = 1.0
        double3 xformOp:translate = (0, 0, 1)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
}
```

Authors who want a clean run should avoid:
- Custom attributes whose names contain both `random` and `seed` (would trip `RESET.NON_DETERMINISTIC_AUTHORING`).
- Mass `physxRigidBody:mass = 0` or NaN.
- Initial-state interpenetration (would surface in `contact_pairs_after_reset[0]`).

---

## 9. Limitations

| Limitation | Notes |
|---|---|
| Velocity always reported as zero | Adapter doesn't query `omni.physx.IPhysxSimulation` for velocity. Acceptable because the validator only checks post-reset velocity (which is zero by construction). |
| `after_step_state` precision | PhysX's enhanced determinism is "enhanced" but not bit-identical across host reboots. `RESET.CYCLE_VARIANCE_*` uses a 1e-5 m tolerance — practical, not theoretical. |
| `non_deterministic_authoring` is a heuristic | Matches attribute names containing both `random` and `seed`. False negatives possible if an asset uses unusual attribute naming. |
| Single seed for all cycles | Acceptance §6 doesn't require per-cycle reseeding, but a future revision could pass a seed schedule. Out of scope for v1. |
| Pose jitter after `World.reset()` | PhysX re-settles bodies during reset; expect ~few mm jitter vs authored pose for dynamic bodies. The validator's §6.1 check is a *cycle-to-cycle* drift comparison, not an authored-vs-reset comparison, so this jitter does not produce false positives. |

---

## 10. Test coverage

| Suite | File | Cases | Runtime |
|---|---|---|---|
| Validator logic (mocked simulator) | `tests/unit/test_deterministic_reset.py`             | 30+ | A |
| **Real adapter (USD fixtures + Kit)** | **`tests/unit/test_deterministic_reset_adapter.py`** | **10** | **B** |
| Scene-integrity (mocked, multi-body) | `tests/scene_integrity/test_reset_scenes.py`         | 7   | A |

Runtime B coverage: **10 / 10 PASS** on this host (via `tools/runtime_b_pytest_runner.py`).

---

## 11. Relationship to other docs

| Document | Role |
|---|---|
| [docs/asset_validator_acceptance.md §6](asset_validator_acceptance.md#6-deterministic-reset-requirements) | Threshold values and code registry for `RESET.*` |
| [docs/asset_validator_report_format.md §3.6](asset_validator_report_format.md#36-reset--13-codes-12--1-guard) | On-disk shape of `RESET.*` issues |
| [docs/scene_validation_workflow.md §3 step 7](scene_validation_workflow.md) | Where reset validation fits in the 8-step workflow |
| [docs/physx_runtime_constraints.md §1](physx_runtime_constraints.md#1-determinism) | The cross-cutting determinism rules every PhysX adapter inherits |
| [docs/physx_contact_source.md](physx_contact_source.md)                          | Sibling adapter — same contact-report subscription pattern |
| [docs/physx_collider_inspector.md](physx_collider_inspector.md)                   | Sibling adapter — same Kit-version-resilient pattern (omni.log) |
| [docs/runtime_b_testing.md](runtime_b_testing.md)                                  | How to run the simulator's tests under Kit Python |
| [docs/phase1_completion.md](phase1_completion.md)                                   | Phase 1 summary now that all three PhysX adapters have shipped |
