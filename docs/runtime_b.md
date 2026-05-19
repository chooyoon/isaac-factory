# Runtime B — Isaac Sim Kit Python

**Workspace**: `/home/cap2/last`
**Runtime canonical path**: `/home/cap2/isaac-sim-5.0.0` (Isaac Sim 5.0.0-rc.45)
**Kit Python**: `kit/python/bin/python3` (Python 3.11.13)
**Companion docs**: [runtime_policy.md §2](runtime_policy.md), [physx_runtime_constraints.md](physx_runtime_constraints.md), [runtime_b_bootstrap.md](runtime_b_bootstrap.md), [asset_validator_design.md](asset_validator_design.md)
**Last revised**: 2026-05-18

This document is the conceptual reference for Runtime B — the Isaac Sim Kit Python environment that hosts every validator runtime that needs PhysX. It complements `runtime_policy.md` (which is policy) with **what Runtime B actually contains** and **what work belongs there**.

---

## 1. What Runtime B is

A single Python 3.11.13 interpreter bundled with Isaac Sim 5.0 at `/home/cap2/isaac-sim-5.0.0/kit/python/`. It is launched via:

- `./python.sh <script.py>` — runs a Python script with Kit's sys.path set up so `pxr.*`, `omni.*`, and `isaacsim.*` import cleanly. **Does not boot the Kit application** unless the script explicitly calls `isaacsim.SimulationApp()`.
- `./isaac-sim.sh` — boots the Kit application interactively.
- `python.sh -c "..."` — one-liner mode; useful for probes.

Runtime B is one of three Python runtimes on this host. The other two (Runtime A — conda `env_isaaclab`; Runtime C — system Python 3.12 for ROS 2) are described in [runtime_policy.md §2](runtime_policy.md#2-runtime-separation-rules). They are never combined in a single process.

### Why Runtime B is required for some validators

Three of the five implemented validators have abstract Protocol dependencies that can *in principle* be satisfied by either USD-only or PhysX-backed adapters. In practice, two of them have signals that **only** PhysX produces:

| Validator | Dependency | Signal that needs PhysX |
|---|---|---|
| `OverlapValidator`            | `ContactSource`     | per-pair penetration depth at runtime (USD-only AABB tests can't measure this) |
| `ColliderValidator`           | `ColliderInspector` | `COLLIDER.COOKING_FAILED` — only emitted in `omni.physx`'s cooking log |
| `DeterministicResetValidator` | `ResetSimulator`    | actual physics step-and-reset cycle; needs `useDeterministicSimulation` PhysX flag + `isaacsim.core.api.World` |

The other two validators (`TransformValidator`, `GroundingValidator (static)`) are USD-only and run under Runtime A without any PhysX dependency. See [grounding_validator.md](grounding_validator.md) and [transform_validator.md](transform_validator.md).

---

## 2. What Runtime B contains

Snapshot of the Isaac Sim 5.0 install at `/home/cap2/isaac-sim-5.0.0/`:

| Subtree | Size | Role |
|---|---|---|
| `kit/python/`          | bundled Python 3.11.13 with `pxr` already on sys.path |
| `kit/cache/`           | 2.3 G | Kit launcher cache (regenerable) |
| `extscache/omni.usd.libs-*` | bundled `pxr` (cp311 build) — see runtime_policy.md §6 |
| `extscache/omni.physx-*`    | PhysX bindings, scene, contact reports, cooking |
| `extscache/omni.physx.commands-*`, `omni.physx.cooking-*` | PhysX support extensions |
| `exts/isaacsim.core.api/`   | `World`, `RigidBody`, `Articulation` wrappers |
| `exts/isaacsim.ros2.bridge/jazzy/` | bundled ROS 2 bridge for B → C transports |

The `python.sh` launcher prepends the right `extscache` paths to `sys.path` and `LD_LIBRARY_PATH` so Kit-Python imports resolve correctly. Doing the equivalent manually requires reading the launcher's logic — it's much easier to invoke `python.sh` directly.

---

## 3. Runtime separation invariants (recap from runtime_policy.md)

Runtime B is **mutually exclusive** with Runtimes A and C in a single shell. Crossing these boundaries is prohibited per [runtime_policy.md §7](runtime_policy.md#7-prohibited-mixed-runtime-imports):

| Prohibition | Why |
|---|---|
| **P3** — importing `omni.*` from anything other than Kit Python | `omni.kit.app` requires the Kit runtime context |
| **P5** — mixing conda `site-packages` with Kit's `sys.path` | NumPy / protobuf ABI clash |
| **P7** — sourcing `/opt/ros/jazzy/setup.bash` before launching Kit | system `librcl*` shadows the bundled bridge |

Cross-runtime communication is by ROS 2 topics/services, external IPC, or file handoff — never by shared imports.

---

## 4. Phase 1.B adapter scaffolding (this turn)

Phase 1.B is the work of implementing PhysX-backed adapters under Runtime B. The validator + Protocol layer was finalized in Phase 0; Phase 1 then shipped two USD-only adapters (under Runtime A). This turn ships **scaffolds** for the three remaining adapters that need Runtime B:

| Scaffold | Path | Protocol |
|---|---|---|
| `PhysXContactSource`       | [`asset_validator/adapters/physx_contact_source.py`](../isaac_factory/extensions/asset_validator/asset_validator/adapters/physx_contact_source.py) | `ContactSource` (overlap) |
| `PhysXColliderInspector`   | [`asset_validator/adapters/physx_collider_inspector.py`](../isaac_factory/extensions/asset_validator/asset_validator/adapters/physx_collider_inspector.py) | `ColliderInspector` (collider) |
| `PhysXResetSimulator`      | [`asset_validator/adapters/physx_reset_simulator.py`](../isaac_factory/extensions/asset_validator/asset_validator/adapters/physx_reset_simulator.py) | `ResetSimulator` (reset) |

Each scaffold:
- Imports its Protocol from `core/`.
- Guards `pxr`/`omni`/`isaacsim` imports with `try/except` so the module loads in Runtime A for type checking and design review.
- Raises `RuntimeError(_BOOTSTRAP_HINT)` from `__init__` when `omni.physx` isn't importable — failing **at construction**, not at first method call.
- All Protocol methods raise `NotImplementedError("Phase 1.B scaffold — …")` with a one-line description of what the method **will** do when filled in.

This pattern preserves the workspace's "one runtime per process" invariant while giving downstream consumers (tests, design docs, future Pipeline class) a place to import the adapter types from.

---

## 5. Implementation backlog (Phase 1.B)

What each PhysX adapter will need to do when filled in, ordered roughly by complexity / risk:

### 5.1 `PhysXContactSource` — least PhysX surface area

1. Construct an `isaacsim.core.api.World` bound to the input stage.
2. Set deterministic flags on the scene's `PxScene`.
3. On `setup(seed=…)`: configure PhysX solver seed, NumPy seed, Python `random` seed, Warp seed (if Warp is loaded).
4. On `step()`: call `world.step(render=False)` once.
5. On `query_contacts()`: drain the `PxContactReportCallback` event buffer, deduplicate by canonicalised prim-path pair, compute per-pair max penetration via `Gf.Vec3d(separation).GetLength()`, return `tuple[ContactPair, ...]`.

Risk: PhysX contact report wiring under `omni.physx` requires a callback subscribe API that has churned across Isaac Sim minor versions. Targeting 5.0 specifically.

### 5.2 `PhysXColliderInspector` — heaviest USD walk

1. Open or load the stage into a `World`.
2. Walk every prim with `UsdPhysicsCollisionAPI`; compute world AABB via `UsdGeom.BBoxCache`; classify approximation; capture `physxCollision:filterGroup`.
3. Walk every prim with `UsdPhysicsRigidBodyAPI` / `ArticulationRootAPI`; extract mass / density / kinematic flag.
4. Resolve `rigid_body_path` per collider (closest ancestor RigidBody) — single pass via prim-path prefix matching.
5. Subscribe to `omni.physx` cooking callbacks during stage load; map each cooking error to its target prim path; populate `ColliderInfo.cooking_error`.
6. Emit `ColliderInfo` + `RigidBodyInfo` iterables.

Risk: cooking errors are surfaced via `omni.log.Channel` — capturing only the asset's errors (filtering out unrelated noise) needs careful subscription scoping.

### 5.3 `PhysXResetSimulator` — most fragile

1. Set seeds, then `World.reset()` and snapshot S₀.
2. For 3 cycles: step 100 frames, snapshot S_after_step; `World.reset()`; snapshot S_after_reset.
3. After each cycle's reset, drain residual contact reports → `contact_pairs_after_reset`.
4. Capture spawn order from `world.scene.get_object_names()` per cycle (USD prim creation order via traversal).
5. Detect non-deterministic authoring via `UsdPhysics` schema introspection (`physxRigidBody:randomizedSeed` etc).
6. Assemble the full `ResetReport`.

Risk: PhysX determinism flag must be set on the scene **before** the first step; setting it after produces silently divergent runs. Tests need to verify the order rigorously.

### 5.4 Hierarchy + dynamic-grounding adapters

These are Phase 2 items, called out for visibility but not part of Phase 1.B. See [scene_validation_workflow.md §10](scene_validation_workflow.md) items 1 + 2.

---

## 6. How to verify Runtime B is reachable

Use the bootstrap probe shipped this turn:

```bash
# Static checks only (any Python, < 1 s):
python isaac_factory/extensions/asset_validator/tools/runtime_b_validation.py

# Add subprocess import-probe via $ISAAC_PATH/python.sh (10–30 s):
python isaac_factory/extensions/asset_validator/tools/runtime_b_validation.py --probe
```

See [runtime_b_bootstrap.md](runtime_b_bootstrap.md) for the full bootstrap procedure and expected output.

---

## 7. Status

As of 2026-05-18:

- **Runtime A adapters shipped**: `UsdGroundingInspector`, `UsdStageInspector` (Phase 1, two prior turns)
- **Runtime B scaffolds shipped**: `PhysXContactSource`, `PhysXColliderInspector`, `PhysXResetSimulator` (this turn)
- **Bootstrap probe shipped**: `tools/runtime_b_validation.py`, `tools/physx_runtime_probe.py` (this turn)
- **Runtime B real implementations**: deferred — each is a separate per-component request

No validator code has been touched in this turn; the Phase 0 logic remains the contract every Runtime B adapter will satisfy.
