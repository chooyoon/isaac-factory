# PhysXColliderInspector — Runtime Implementation

**Package**: `isaac_factory/extensions/asset_validator/asset_validator/adapters/`
**Validator served**: `validators/collider.py::ColliderValidator`
**Adapter**: [`adapters/physx_collider_inspector.py`](../isaac_factory/extensions/asset_validator/asset_validator/adapters/physx_collider_inspector.py) (Phase 1.B, 2026-05-18)
**Companion specs**: [acceptance §3](asset_validator_acceptance.md#3-collider-requirements), [workflow §3 step 3](scene_validation_workflow.md), [physx_runtime_constraints.md §2](physx_runtime_constraints.md), [physx_contact_source.md](physx_contact_source.md)
**Last revised**: 2026-05-18

This document is the operational manual for the second Phase 1.B adapter — the PhysX-backed implementation of the `ColliderInspector` Protocol.

---

## 1. End-to-end runtime path

```
.usda asset  ───────────────────────────────────────────────►  report.json
   │                                                              ▲
   ▼                                                              │
omni.usd.UsdContext.open_stage(asset)                             │
   │                                                              │
   ▼                                                              │
isaacsim.core.api.World()  (caller-managed; bootstraps PhysX)     │
   │                                                              │
   ▼                                                              │
PhysXColliderInspector(stage=stage)                               │
   │   subscribe omni.log (best-effort) for cooking errors        │
   │   walk UsdPhysics.CollisionAPI / RigidBodyAPI prims           │
   │   classify approximation, compute world AABBs, attach        │
   │     closest-RB-ancestor and cooking-error (if matched)        │
   │   yield ColliderInfo / RigidBodyInfo records                 │
   ▼                                                              │
ColliderValidator(criteria).run(ValidationContext(...))           │
   │   emits Issue records per acceptance §3 codes                 │
   ▼                                                              │
reporters.json_reporter.write_report(...)  ─────────────────────┘
```

Like the other PhysX adapters, no `omni.ui`, no orchestration, no rendering. Optional `pxr.UsdPhysics`, `pxr.PhysxSchema`, and `omni.log` imports are best-effort: the module loads in Runtime A, instantiation raises with the bootstrap hint if `omni.physx` isn't reachable.

---

## 2. What the adapter extracts

For every active prim carrying `UsdPhysics.CollisionAPI`:

| Field on `ColliderInfo` | How it's derived |
|---|---|
| `path`                | `str(prim.GetPath())` |
| `approximation`       | See §3 — primitive type → token, else `MeshCollisionAPI` schema, else PhysxSchema convex hull / decomposition flags |
| `rigid_body_path`     | Closest `UsdPhysics.RigidBodyAPI` ancestor, or `prim.path` itself if RB is on the same prim, or `None` |
| `collider_aabb_min`, `collider_aabb_max` | `UsdGeom.BBoxCache.ComputeWorldBound(prim).ComputeAlignedRange()` |
| `visual_aabb_min`, `visual_aabb_max` | Same as collider AABB in v1 — accurate for primitives, conservative for meshes |
| `convex_decomposition_hull_count` | `None` in v1 — actual count requires post-cook PhysX query (deferred) |
| `cooking_error`       | First buffered `omni.log` message containing the prim's Sdf path (best-effort) |
| `collision_group`     | `physxCollision:filterGroup` attribute if authored, else `None` |
| `custom_data`         | Frozen tuple — propagates `static_collider` bool + any `asset_validator.*` scalar keys |

For every active prim carrying `UsdPhysics.RigidBodyAPI` or `UsdPhysics.ArticulationRootAPI`:

| Field on `RigidBodyInfo` | How it's derived |
|---|---|
| `path`                | `str(prim.GetPath())` |
| `is_kinematic`        | `UsdPhysics.RigidBodyAPI.GetKinematicEnabledAttr()` value, if authored |
| `is_articulation_root`| `prim.HasAPI(UsdPhysics.ArticulationRootAPI)` |
| `mass`                | `UsdPhysics.MassAPI.GetMassAttr()` value, if authored |
| `density`             | `UsdPhysics.MassAPI.GetDensityAttr()` value, if authored |
| `volume_m3`           | Closed-form for `Cube` (`size³`) and `Sphere` (`4/3 π r³`); `None` otherwise |
| `custom_data`         | Same frozen-tuple shape as for colliders |

---

## 3. Approximation classification

Used by the validator's `MESH_ON_DYNAMIC` check (acceptance §3.3) to decide whether a dynamic body's collision shape sits inside the allowed set `{box, sphere, capsule, cylinder, convexHull, convexDecomposition}`.

```
prim.GetTypeName() == "Cube"     ─►  "box"
prim.GetTypeName() == "Sphere"   ─►  "sphere"
prim.GetTypeName() == "Capsule"  ─►  "capsule"
prim.GetTypeName() == "Cylinder" ─►  "cylinder"

prim.HasAPI(PhysxSchema.PhysxConvexHullCollisionAPI)          ─►  "convexHull"
prim.HasAPI(PhysxSchema.PhysxConvexDecompositionCollisionAPI) ─►  "convexDecomposition"

prim.HasAPI(UsdPhysics.MeshCollisionAPI):
    GetApproximationAttr().Get()   ─►  e.g. "convexHull", "boundingCube", "sdf", "none"
    (default if unauthored)        ─►  "none"

prim.GetTypeName() == "Mesh"     ─►  "none"  (catch-all)

else                              ─►  "unknown"
```

The `"none"` and `"unknown"` cases both fall outside `dynamic_allowed_approximations`, so any dynamic rigid body whose collider lands there fires `COLLIDER.MESH_ON_DYNAMIC`.

---

## 4. Authoring contract

A clean factory-cell asset typically contains:

```usda
def Xform "World" {
    def PhysicsScene "PhysicsScene" { ... }

    # Static collider (no RB ancestor needed because of customData flag)
    def Cube "Floor" (
        apiSchemas = ["PhysicsCollisionAPI"]
        customData = { bool static_collider = true }
    ) { double size = 1.0; ... }

    # Dynamic body — RB and collider on the same prim
    def Cube "Box" (apiSchemas = ["PhysicsCollisionAPI", "PhysicsRigidBodyAPI"]) {
        double size = 1.0; ...
    }
}
```

For composite assets (separate Xform for the rigid body + Cube/Mesh children for collision shapes), `rigid_body_path` resolution walks parents until it finds an `RigidBodyAPI`-bearing prim. If none is found and the collider has no `customData.static_collider = true`, `COLLIDER.NO_RIGID_BODY_ANCESTOR` fires.

---

## 5. Cooking-error capture

PhysX cooks rigid-body collision shapes the first time a `World` is created (or whenever `World.reset()` is called). Cook failures get logged to `omni.log` channel `omni.physx.cooking` (and adjacent channels) at error / fatal level. They are the **only** signal for `COLLIDER.COOKING_FAILED` (acceptance §3.7).

The adapter subscribes to `omni.log` at construction:

```python
log = omni.log.get_log()
self._log_handle = log.add_log_message_consumer(self._on_log_message)
```

Different Kit versions expose this under different method names — the adapter tries `add_log_message_consumer` then `add_message_consumer`. If both fail, subscription silently degrades to "no capture" and `cooking_error` is `None` for every collider.

When buffering captured messages, anything containing the substring `"cook"` or a `"physx" + ("error" \| "fail")` combination is recorded. At iter-time, the inspector matches a message to a collider by **substring-matching the prim's Sdf path inside the buffered message text**. This is a heuristic — PhysX cooking log messages typically include the path, but the format isn't a stable contract across Kit versions.

**Honest scope:**

| Behaviour | Outcome |
|---|---|
| Cook succeeds | No buffered messages → `cooking_error = None` |
| Cook fails on a specific shape and the log mentions that shape's path | `cooking_error` = first matching message (truncated to 200 chars) |
| Cook fails but the log doesn't mention the prim path | `cooking_error = None` for that prim. The error is in `_cooking_messages` but unattributed. |
| `omni.log` API surface differs from what we know | Subscription fails silently; same effect as "no cook failures" |

In practice on Isaac Sim 5.0 with the fixtures in this repository, cooking always succeeds. The capture path exists for production assets that exercise edge cases.

---

## 6. Determinism

- Prims are enumerated via `Usd.Stage.Traverse()` then sorted by Sdf path lexicographically before yielding.
- `iter_colliders()` and `iter_rigid_bodies()` are independent walks — each is stable.
- Custom data is frozen as a sorted tuple of `(key, value)` pairs so `ColliderInfo` and `RigidBodyInfo` remain hashable.
- The cooking-message buffer is FIFO; the first matching message wins for each prim.

Two runs over the same stage produce **bit-identical** collider record sequences. Verified by `tests/unit/test_collider_adapter.py::TestDeterminism`.

---

## 7. Fixtures shipped with the runtime

Under [`tests/fixtures/collider/`](../isaac_factory/extensions/asset_validator/tests/fixtures/collider/):

| Fixture | Expected ColliderValidator outcome (asset-level codes only — `MISSING_COLLISION_GROUP` warnings always fire because filter groups are intentionally not authored on these fixtures) |
|---|---|
| `clean_collider_assembly.usda` | No structural failures (floor static + dynamic box) |
| `orphan_collider.usda`         | `COLLIDER.NO_RIGID_BODY_ANCESTOR` on `/World/Loose` |
| `rb_without_collider.usda`     | `COLLIDER.RIGID_BODY_WITHOUT_COLLIDER` on `/World/EmptyRB` |
| `mesh_on_dynamic.usda`         | `COLLIDER.MESH_ON_DYNAMIC` on `/World/TriMesh` (approximation = `"none"`) |
| `degenerate_aabb.usda`         | `COLLIDER.DEGENERATE_AABB` on `/World/Paper` (Z extent ≈ 10 µm) |

No `expected_reports/*.report.json` are generated for these fixtures: `MISSING_COLLISION_GROUP` is order-stable but `cooking_error` capture is non-deterministic across Kit versions. The test suite asserts behavioural invariants (specific codes present / absent) rather than bit-identical JSON.

---

## 8. Programmatic usage

End-to-end run inside Kit Python:

```python
from isaacsim import SimulationApp
app = SimulationApp({"headless": True})
try:
    import omni.usd
    from isaacsim.core.api import World
    from asset_validator import (
        AcceptanceCriteria, ColliderValidator, ValidationContext,
        load_criteria, write_report,
    )
    from asset_validator.adapters.physx_collider_inspector import (
        PhysXColliderInspector,
    )

    criteria = load_criteria(
        "isaac_factory/extensions/asset_validator/configs/acceptance_default.yaml"
    )

    omni.usd.get_context().open_stage("path/to/asset.usd")
    stage = omni.usd.get_context().get_stage()

    # Construct inspector BEFORE World so cooking-log subscription is
    # in place when PhysX cooks during World init.
    with PhysXColliderInspector(stage=stage) as inspector:
        world = World()
        world.reset()  # forces a cook pass

        ctx = ValidationContext(
            asset_uri="file:///path/to/asset.usd",
            criteria=criteria,
            collider_inspector=inspector,
        )
        issues = ColliderValidator(criteria).run(ctx)

    write_report(
        issues,
        "outputs/asset_validation/run-001/report.json",
        asset_uri=ctx.asset_uri,
        validators_run=["collider"],
        duration_seconds=0.0,
        criteria=criteria,
    )
finally:
    app.close()
```

---

## 9. Limitations

| Limitation | Notes |
|---|---|
| `convex_decomposition_hull_count` is always `None` in v1 | Actual hull count requires a post-cook PhysX query that I haven't wired in. Hull-count limit checks (acceptance §3.4) won't fire for any prim. |
| `visual_aabb` = `collider_aabb` | Accurate for primitives (Cube, Sphere, Capsule, Cylinder). For mesh-with-convex-hull approximation the cooked convex hull's AABB can differ from the source mesh's; the validator's §3.5 `AABB_MISMATCH` check is therefore tolerant by construction. |
| `cooking_error` attribution is heuristic | Path-substring matching in log text. False negatives (cooked-but-error-not-attributed) are possible. False positives are unlikely because Sdf paths are unique. |
| `omni.log` subscription is best-effort | If the Kit version's API surface differs from the two method names we try, capture silently degrades. The validator never falsely fires `COOKING_FAILED` as a result; the worst case is missing a real failure. |
| Only the primitive types `Cube`, `Sphere`, `Capsule`, `Cylinder` get a closed-form `volume_m3` | Mesh and `Cone` volumes need PhysX (cooked geometry) — left as `None`. `MASS_DENSITY_CONFLICT` (acceptance §3.10) skips gracefully when volume is `None`. |

---

## 10. Test coverage summary

| Suite | File | Cases | Runtime |
|---|---|---|---|
| Validator logic (mocked inspector) | `tests/unit/test_collider.py` | 30+ | A |
| **Real adapter (USD fixtures)** | **`tests/unit/test_collider_adapter.py`** | **9** | **B** |
| Scene-integrity (mocked, multi-prim) | `tests/scene_integrity/test_collider_scenes.py` | 7 | A |

Runtime B coverage: **9 / 9 PASS** on this host (verified via `tools/runtime_b_pytest_runner.py`).

---

## 11. Relationship to other docs

| Document | Role |
|---|---|
| [docs/asset_validator_acceptance.md §3](asset_validator_acceptance.md#3-collider-requirements)             | Threshold values and code registry for `COLLIDER.*` |
| [docs/asset_validator_report_format.md §3.3](asset_validator_report_format.md#33-collider--13-codes-12--1-guard) | On-disk shape of `COLLIDER.*` issues |
| [docs/scene_validation_workflow.md §3 step 3](scene_validation_workflow.md) | Where collider validation fits in the 8-step workflow |
| [docs/physx_runtime_constraints.md §2](physx_runtime_constraints.md)                                       | Cooking-error handling contract |
| [docs/physx_contact_source.md](physx_contact_source.md)                                                    | Sibling Phase 1.B adapter — same scaffolding pattern |
| [docs/runtime_b_testing.md](runtime_b_testing.md)                                                          | How to run the adapter's tests under Kit Python |
| [docs/runtime_b.md §5.2](runtime_b.md)                                                                     | Where this adapter sat on the implementation backlog before it shipped |
