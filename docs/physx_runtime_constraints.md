# PhysX Runtime Constraints

**Scope**: Constraints that apply to **every PhysX-backed adapter under Runtime B**. Captured up front so Phase 1.B implementations can be written against a single contract.
**Companion to**: [runtime_b.md](runtime_b.md), [runtime_b_bootstrap.md](runtime_b_bootstrap.md), [asset_validator_acceptance.md §6](asset_validator_acceptance.md#6-deterministic-reset-requirements)
**Last revised**: 2026-05-18

PhysX is fast and accurate but has sharp edges — particularly around determinism, cooking, and contact reports. This doc lists the constraints that any Phase 1.B adapter **must** respect.

---

## 1. Determinism

The `DeterministicResetValidator` (and the per-cycle invariants it checks) is meaningless without strict determinism. Phase 1.B adapters must:

1. **Set the determinism flag at scene creation**, not after.
   ```python
   physx_scene.SetFlag(omni.physx.PxSceneFlag.eENABLE_DETERMINISTIC_SIMULATION, True)
   # must precede the first step; setting it later produces silent drift
   ```
2. **Fix every RNG seed before any physics step.** Order matters:
   1. Python `random.seed(s)`
   2. `numpy.random.seed(s)`
   3. PhysX solver seed (via `omni.physx` API)
   4. Warp seed (if Warp is loaded — `warp.rand_init(s)`)
3. **Pin `physics_dt`.** 1/60 s by default (60 Hz). Variable timestep breaks reproducibility.
4. **Pin substep count** if the engine exposes it. Acceptance §0 assumes a fixed dt; substep-adaptive solvers would invalidate the §6 thresholds.
5. **Disable all sources of timing-dependent ordering.** No `threading.Timer`, no `asyncio.sleep()` in adapter code; queue work synchronously.

Violation symptoms: `RESET.POSE_TRANSLATION_DRIFT` appearing on cycle 2 but not cycle 1, or `RESET.CYCLE_VARIANCE_*` firing on different bodies between runs.

---

## 2. Cooking

PhysX **cooks** collider geometry (mesh → BVH, convex hull → projected support function) at stage load. Cooking failures are the only signal that produces `COLLIDER.COOKING_FAILED` (§3.7 of the acceptance doc) — they cannot be inferred from USD alone.

Constraints:

1. **Cook synchronously during stage load.** Asynchronous cooking introduces timing-dependent ordering of error reports.
2. **Capture every cooking error from `omni.log` during the scoped cook window.** Use `omni.log.Channel("omni.physx.cooking").set_callback(...)` or equivalent. Unsubscribe immediately after; otherwise unrelated runtime warnings leak into the report.
3. **Map cooking errors to the originating prim path.** PhysX's error text usually includes the path, but parsing is fragile — prefer reading the PxRigidActor/PxShape user data, which `omni.physx` attaches to each cooked actor.
4. **Don't cook twice.** `World.reset()` rebuilds the scene but cooking should be a one-time cost amortised across all cycles.

---

## 3. Contact reports

Required by `OverlapValidator` and (indirectly) the `RESET.CONTACT_AFTER_RESET` check.

1. **Subscribe to contact reports before the first step.** Subscriptions added mid-step miss the events for that step.
2. **Use the `eNOTIFY_TOUCH_FOUND | eNOTIFY_TOUCH_PERSISTS` event mask.** TOUCH_LOST alone won't surface penetrations; PERSISTS alone misses first-frame penetrations.
3. **Drain the buffer per step.** Between steps, the buffer's order is well-defined; across steps it is not. The adapter must consume + reset per step.
4. **Deduplicate by prim-path pair.** A single contact pair can produce multiple events per step (one per overlapping shape pair). Take the max penetration depth.
5. **Canonicalise prim path ordering.** `ContactPair.create(a, b, depth)` already does this — the adapter just needs to feed it the raw paths.

---

## 4. Scene queries

`omni.physx` provides ray/sphere/box scene queries. For the deferred dynamic-grounding variant (acceptance §5.A), these would replace the USD-AABB raycast.

Constraints:

1. **Scene queries must run after at least one step.** Queries on a freshly-loaded but unstepped scene return stale data.
2. **Use the closest-hit variant unless you specifically want all hits.** Multi-hit queries are slower and need filtering anyway.
3. **Filter via collision groups.** A raycast doesn't know about "support" semantics; use `physxCollision:filterGroup` to scope the query.
4. **Don't trust raycast normals from triangle meshes.** Use the cooked actor's `PxShape` normal where possible.

---

## 5. World lifecycle

`isaacsim.core.api.World` is the canonical wrapper around `omni.physx`. Phase 1.B adapters must coordinate with it carefully.

1. **One `World` per process.** Constructing a second World silently inherits the first's PhysX scene; behaviour is undefined.
2. **`world.reset()` is destructive.** It rebuilds the scene from the stage. Any in-flight contact subscriptions are dropped — re-subscribe after every reset.
3. **`world.stop()` then `world.play()` is NOT equivalent to `world.reset()`.** Stop/play preserves PhysX state; reset re-cooks.
4. **Time-step ownership is the adapter's, not the World's.** Call `world.step(render=False)` from the adapter, don't rely on auto-stepping.
5. **Always close the World before the script exits.** PhysX has thread pools and shared memory regions that need clean shutdown; `world.close()` (or implicit `__del__`) is required to avoid leaking GPU buffers.

---

## 6. Threading and async

Kit's main loop is event-driven and uses `omni.kit.async_engine` for coroutines. Phase 1.B adapters live inside that loop.

1. **Run physics steps synchronously from the main thread.** Off-thread `world.step()` triggers race conditions in `omni.physx`.
2. **Avoid `asyncio.sleep(0)` between steps.** It yields to other Kit subsystems which may modify the scene mid-cycle.
3. **Capture contact reports synchronously inside the step callback.** Buffering and consuming async violates §3 (drain per step).

---

## 7. Memory and GPU

PhysX 5 (bundled with Isaac Sim 5) uses GPU dynamics by default. This is faster but has constraints:

1. **GPU dynamics requires a CUDA-capable device.** The host's RTX 5090 satisfies this; in headless environments without a GPU, fall back to CPU dynamics via `PxSceneDesc.flags.SCENE_FLAG_DISABLE_GPU_DYNAMICS`.
2. **Maximum body count on GPU is finite.** Default is ~1024; large factory scenes may exceed it. Adapters should query `PxScene.getNbActors()` after load and warn if approaching the limit.
3. **GPU memory is not freed until World.close().** Long-running validation that loads many stages must close the World between assets.

---

## 8. Error reporting

PhysX errors arrive through `omni.log`. Adapters must:

1. **Subscribe to `omni.log.Channel("omni.physx")` and child channels** for the duration of the validation run.
2. **Treat any ERROR-level log as a FAIL** (with the affected prim path if recoverable).
3. **Treat WARN-level logs as advisory** — propagate to the report at INFO severity if they're scoped to the asset.
4. **Unsubscribe in `finally`** — a long-lived subscription leaks across Phase 1.B adapter invocations and produces cross-run noise.

---

## 9. Read-only stage constraint

This is a workspace-wide rule (per [asset_validator_design.md §5.4](asset_validator_design.md#54-read-only-guarantee)) but worth re-stating in PhysX context:

1. **Open the stage against an anonymous root layer** that references the asset. Never `Save()` the source layer.
2. **PhysX may write back to the stage** via `PxRigidActor::setGlobalPose` etc. when stepping. These writes go to the in-memory composed stage, not the source asset.
3. **Validator's view of the stage is post-step** — that's the intent. Adapters need not snapshot pre-step state unless the validator's contract specifically requires it (it does for `DeterministicResetValidator.initial_state`).

---

## 10. Quick reference — adapter contracts

| Adapter | Setup hook | Per-step hook | Per-cycle hook |
|---|---|---|---|
| `PhysXContactSource`       | seed + flag + contact subscribe         | step + drain contact buffer        | n/a |
| `PhysXColliderInspector`   | cook + capture cooking errors + walk schemas | n/a (static, post-cook)        | n/a |
| `PhysXResetSimulator`      | seed + flag + snapshot initial          | step × N                           | reset + re-subscribe contacts + snapshot |

All three share: deterministic seed handling, one-World invariant, synchronous physics steps, clean teardown.

---

## 11. Phase 1.B implementation order recommendation

When the user requests Phase 1.B implementations, the suggested order is:

1. **`PhysXContactSource`** — smallest PhysX surface (one scene, one step, one buffer drain). Easiest to validate against existing OverlapValidator unit tests by feeding the existing fixture format.
2. **`PhysXColliderInspector`** — requires omni.log subscription. Validates cooking-error flow, which is the highest-risk part.
3. **`PhysXResetSimulator`** — most complex. Builds on the determinism + contact subscriptions from (1) and (2). Defers gracefully if (1) is shaky.

Each can ship independently. The validator + Protocol contracts don't change.
