# Phase 4B — Orchestration Architecture (Proposed)

Status: **proposed, pre-implementation.** Architecture-first per Phase 4B brief.
Predecessors: Phase 3M / 3N / 3O / 3P (validated manipulation cell) + Phase 4A (task abstraction layer). Test surface at entry: **32 / 32 PASS**.

This document defines the orchestration spine before any code is written. It exists so that the implementation phase (steps 1–12 in §9) cannot drift from the determinism, validation, and ownership disciplines established in Phases 3M–4A.

---

## 0. Scope and non-goals

Phase 4B transitions the system from **single-task execution** (Phase 4A — one `TaskExecutor.execute(task)` call per validated cycle) to **deterministic orchestration of multi-task jobs**.

**In scope:**

* Job abstraction (a `Job` is a `TaskGraph` + seed + policy).
* `TaskGraph` (a DAG of `TaskNode`s; nodes are existing Phase 4A `TaskDefinition`s + orchestration metadata).
* A deterministic, sequential `Scheduler` that selects the next runnable node.
* `ExecutionSession`, the single owner of world / executor / registry / event bus / trace recorder for one job.
* A synchronous `EventBus` and event taxonomy.
* `TraceRecorder` + `SessionPackage` (the orchestration-grade replay artifact).
* Multi-object lifecycle semantics on top of the existing `CellStateRegistry`.
* Orchestration-grade replay identity (sequence-level, not just endpoint-level).

**Explicitly out of scope (Phase 4C+):**

* Concurrent / parallel task execution (PhysX in Isaac Sim is single-process; concurrency would break determinism).
* New concrete task kinds (peg-into-hole, multi-peg sort). Phase 4B defines the surface; new kinds are deliberate Phase 4C extensions.
* Online motion planning (the validated `TrajectoryPlayer` + baked waypoint path is preserved).
* Cross-cell deployments (current `CellConfig` remains single-cell — a known Phase 4A architectural debt item).
* Interpolator changes to `TrajectoryPlayer` (Phase 3O deferred this with documented rationale).

**Discipline carried over from Phase 4A:**

* Additive only. No file in [`cell_authoring/trajectory.py`](../isaac_factory/extensions/cell_authoring/cell_authoring/trajectory.py), [`cell_authoring/config.py`](../isaac_factory/extensions/cell_authoring/cell_authoring/config.py), [`configs/cell_01.yaml`](../configs/cell_01.yaml), or any pre-existing test file is modified.
* `UnifiedValidator` remains the single authority for gate logic. Phase 4B job-level checks delegate to it.
* `TaskExecutor` (Phase 4A) remains the only entity that mutates PhysX state. Orchestration sits **above** it.

---

## 1. Core object model

```
                                  ┌─────────────────────────────┐
                                  │      Job (frozen)           │
                                  │  job_id                     │
                                  │  task_graph: TaskGraph      │
                                  │  profile_default            │
                                  │  retry_policy               │
                                  │  failure_policy             │
                                  │  seed                       │
                                  └─────────────┬───────────────┘
                                                │
                                                ▼
                ┌───────────────────────────────────────────────────────┐
                │              TaskGraph (frozen, DAG)                  │
                │   nodes:  Mapping[node_id → TaskNode]                 │
                │   edges:  frozenset[(parent_id, child_id)]            │
                │   acyclicity validated at construction                │
                └───────────────────────────┬───────────────────────────┘
                                            │
                                            ▼
                ┌───────────────────────────────────────────────────────┐
                │                 TaskNode (frozen)                     │
                │   node_id          (stable, used as tiebreaker)       │
                │   task             (Phase 4A TaskDefinition)          │
                │   profile          (TrajectoryProfile, optional)      │
                │   preconditions    tuple[Predicate, ...]              │
                │   postconditions   tuple[Predicate, ...]              │
                │   priority         int    (lower = earlier)           │
                │   failure_action   ABORT_JOB | SKIP_NODE | RETRY      │
                │   retry_budget     int                                │
                └───────────────────────────────────────────────────────┘

                                            ▲    drives
                                            │
                ┌───────────────────────────────────────────────────────┐
                │           ExecutionSession (mutable, owned)           │
                │   session_id, seed, started_at_step                   │
                │                                                       │
                │   world, stage, cell_cfg     ← Isaac handles          │
                │   task_executor: TaskExecutor     (Phase 4A)          │
                │   registry:      CellStateRegistry (Phase 4A)         │
                │                                                       │
                │   scheduler:     Scheduler         (Phase 4B)         │
                │   event_bus:     EventBus          (Phase 4B)         │
                │   trace_recorder: TraceRecorder    (Phase 4B)         │
                │   operator_channel: OperatorChannel (Phase 4B)        │
                │                                                       │
                │   job_state: JobState (current node, completed,       │
                │                        failed, skipped, retry_counts) │
                └───────────────────────────────────────────────────────┘
```

### Ownership boundaries (the load-bearing rule)

| Owner                | Owns                                                                         | Notes |
|---|---|---|
| `ExecutionSession`   | the Isaac `World` + `stage`, the `TaskExecutor`, the registry, the event bus, the trace recorder | Single mutable entity in the whole orchestration stack. |
| `TaskExecutor` (4A)  | `Articulation`, `RigidPrim`, `PhysXContactSource`, `TrajectoryPlayer`        | Created once at `prepare()`, reused across all nodes of a job. **Not recreated per task** — Phase 3P proves persistent handles are the bit-identical path. |
| `CellStateRegistry` (4A) | `ObjectState` / `FixtureState` / `RobotState` / `TaskState` / `ContactState` dicts | Already multi-object via dicts keyed by id. Phase 4B reads + writes it through the executor and event bus. |
| `Job` / `TaskGraph` / `TaskNode` | descriptive data only                                              | Frozen dataclasses. No mutable state, ever. |
| `Scheduler`          | nothing                                                                      | Pure function: `(graph, registry, completed, failed) → next_node_id?`. |
| `EventBus`           | the ordered event log of one session                                         | Synchronous. Holds an in-memory list + dispatches to subscribers. |
| `TraceRecorder`      | the on-disk session artifact                                                 | Write-only-after-the-fact. Never feeds back into scheduling decisions. |
| `OperatorChannel`    | a synchronous between-node command queue                                     | Operator inputs are drained only between nodes; never mid-tick. |

Everything stateful lives in `ExecutionSession` and the Phase 4A components it owns. Nothing else holds simulation handles. This is what makes Phase 4B determinism analysable.

---

## 2. Execution lifecycle

One job runs in three phases:

```
session.begin(job)
    ├── validate job:
    │     ├── task graph is acyclic
    │     ├── every TaskDefinition is realisable by the executor's
    │     │   _realisation_table whitelist (Phase 4A guard reused)
    │     ├── every Predicate references known registry ids
    │     └── retry_budget ≥ 0
    ├── task_executor.prepare()         (idempotent; Phase 4A)
    ├── task_executor.reset(scope=FULL) (authored initial conditions)
    ├── registry.snapshot() → trace as "initial"
    └── event_bus.emit(JobStarted(...))

session.step() → RunStatus
    ├── operator_channel.drain()           ← only at node boundaries
    ├── node_id = scheduler.next_runnable_node(
    │     graph, registry, completed, failed)
    ├── if node_id is None and no in-flight → return COMPLETE
    │
    ├── node = graph.nodes[node_id]
    ├── event_bus.emit(TaskScheduled(node_id))
    │
    ├── for pre in node.preconditions:
    │     if not pre.evaluate(registry):
    │         event_bus.emit(PreconditionViolated(node_id, pre))
    │         apply(node.failure_action)
    │         return IN_PROGRESS
    │
    ├── registry_snapshot_pre = registry.snapshot()
    ├── event_bus.emit(TaskStarted(node_id))
    │
    ├── result = task_executor.execute(
    │     node.task,
    │     profile=node.profile or job.profile_default,
    │     seed=derive_seed(job.seed, node_id),
    │     step_observer=trace_recorder.tick_observer,
    │     reset_scope=ACQUIRED_ONLY)   ← see §6
    │
    ├── trace_recorder.append_task(result)
    │
    ├── # UnifiedValidator already ran inside executor.execute().
    │   # We do NOT re-run gates — we read the verdict.
    ├── if result.outcome != PASS:
    │     event_bus.emit(GateViolated(node_id, result.outcome,
    │                                 result.outcome_detail))
    │     event_bus.emit(TaskFailed(node_id, result))
    │     registry.restore(registry_snapshot_pre)  ← rollback registry only
    │     apply(node.failure_action)
    │     return IN_PROGRESS
    │
    ├── for post in node.postconditions:
    │     if not post.evaluate(registry):
    │         event_bus.emit(PostconditionViolated(node_id, post))
    │         apply(node.failure_action)
    │         return IN_PROGRESS
    │
    ├── completed.add(node_id)
    ├── event_bus.emit(TaskCompleted(node_id, result))
    └── return IN_PROGRESS

session.run_to_completion()
    └── while session.step() is IN_PROGRESS: pass

session.close()
    ├── event_bus.emit(JobCompleted(...) or JobAborted(...))
    ├── trace_recorder.flush()                  ← writes events.jsonl etc.
    ├── session_package.write_dir(...)
    └── task_executor.close()
```

`session.step()` is the **determinism unit**. It advances exactly one node. This mirrors `TaskExecutor.execute()` (which is the determinism unit at the layer below). Composing the two yields one well-defined fixed point per `(Job, seed)`.

---

## 3. Scheduler semantics

The scheduler is a **pure function** of the inputs given to it.

```python
def next_runnable_node(
    graph:      TaskGraph,
    registry:   CellStateRegistry,
    completed:  frozenset[str],
    failed:     frozenset[str],
    *,
    retry_counts: Mapping[str, int],
) -> str | None: ...
```

Ordering rules — applied **strictly in this order**:

1. **Dependency-satisfied filter.** Keep nodes whose every parent is in `completed`.
2. **Precondition filter.** Keep nodes whose every `Predicate.evaluate(registry)` returns `True`.
3. **Retry-eligibility filter.** Drop nodes in `failed` whose `retry_counts[node_id] >= retry_budget`.
4. **Priority + id sort.** Sort by `(node.priority, node.node_id)`. `node_id` is a stable string and always breaks ties.
5. **Return the head**, or `None` if the filtered set is empty.

The scheduler is **sequential** (one node at a time) and **never reads wall time**. The only randomness allowed in scheduling is via a deterministically-derived RNG (`numpy.random.default_rng(job.seed + node_id_hash)`), and only in optional shuffle modes flagged at construction.

Three non-features that future contributors must not add without writing a successor architecture doc:

- **No concurrency.** PhysX in Isaac Sim is single-process; concurrent task execution would corrupt determinism. Multi-arm cells are a separate cell-design problem.
- **No clock-based ordering.** The scheduler must not see `time.time()` or `time.monotonic()` for ordering. (Wall time may be recorded in events for diagnostics; it never feeds decisions.)
- **No global / module-level mutable state in scheduler code.** All inputs are arguments.

### Initial implementation: `TopologicalSequentialScheduler`

The only scheduler shipped in Phase 4B is the topological-sequential one above. Mirrors the Phase 4A `_realisation_table` whitelist pattern — adding a new scheduler kind (priority, budgeted, anytime) is a deliberate extension with its own re-validation.

---

## 4. Event taxonomy

The `EventBus` is **synchronous, in-process, ordered**:

```python
@dataclass(frozen=True)
class Event:
    session_id:  str
    seq:         int             # monotone, the orchestration replay key
    ts_step:     int             # simulation step at which observed
    wall_ns:     int             # diagnostic only; never used for ordering
    kind:        EventKind
    payload:     Mapping[str, Any]  # JSON-serialisable
```

- `seq` is a monotone integer. It increments by exactly one per `emit()`. **This is the replay identity hook.**
- `ts_step` is the simulation step at which the event is logically observed (e.g. the executor's last completed step, or 0 between nodes). Wall time is never used.
- `emit()` dispatches to subscribers **synchronously, in registration order**, before returning. If a subscriber raises, the exception is recorded as a `SubscriberError` event but the orchestrator continues — this preserves determinism even when observers crash.

### Event families

| family               | kinds                                                                               |
|---|---|
| Job lifecycle        | `JobStarted`, `JobCompleted`, `JobAborted`                                          |
| Task lifecycle       | `TaskScheduled`, `TaskStarted`, `TaskCompleted`, `TaskFailed`, `TaskRetried`, `TaskSkipped`, `TaskCascadeSkipped` |
| Validation           | `PreconditionViolated`, `PostconditionViolated`, `GateViolated`                     |
| Registry mutation    | `ObjectStateChanged`, `FixtureStateChanged`, `ContactStateChanged`                  |
| Trace                | `SnapshotTaken`, `TraceFlushed`                                                     |
| Cell                 | `WorldReset(scope=…)`, `BeltStateChanged`, `OperatorOverride`                       |
| Internal             | `SubscriberError`                                                                   |

### What does NOT go through the event bus

- Per-physics-tick telemetry (joint vel, EE pose, contacts). That stays in the Phase 4A `step_observer` callback at the executor layer — bypassing the event bus avoids a 60 Hz × 800-step × 20-node = 960 000-event log per job.
- Per-tick contact resolutions. Already aggregated into `TaskResult` by the executor.

The event bus is a **node-boundary audit trail**, not a tick stream. Tick-rate data lives in per-task `TaskResult`s and (optionally) per-task per-tick `trace.jsonl` files inside each task's ReplayPackage.

---

## 5. Replay / trace model

Phase 4B replay is a **stronger** property than Phase 4A replay:

| dimension                | Phase 4A replay (single task)              | Phase 4B replay (orchestrated job)                                      |
|---|---|---|
| identity unit            | one `TaskResult` + one registry snapshot   | one `events.jsonl` + N `TaskResult`s + per-node registry snapshots      |
| fingerprint              | `peg_xyz_final`, motion metrics            | event-sequence equality + every per-task fingerprint                    |
| bit-identity scope       | within one `TaskExecutor` instance         | within one `ExecutionSession` (which owns one `TaskExecutor` instance)  |
| cross-process tolerance  | ≤ 5 mm peg pose, within 50 mm gate         | inherited from below — same per-task tolerance, plus identical scheduler/event ordering |

### `TraceRecorder` writes three streams

1. **Event stream** — `events.jsonl`. The ordered sequence of `Event`s emitted by the bus. This is the **orchestration replay key**.
2. **Per-task ReplayPackages** — `tasks/<node_id>/`. Reuses Phase 4A `ReplayPackage` unchanged, one directory per node.
3. **Registry snapshots at node boundaries** — `registry/<seq>_<node_id>.json`. Captures full snapshot before and after each node. Diff format is *not* used — full snapshots are cheap, diffs complicate replay verification.

### `SessionPackage` layout

```
sessions/<job_id>_<seed>_<utc_iso>/
├── manifest.json              # job_id, seed, runtime_hash, cell_cfg_hash,
│                              #   isaac_version, physx_version, schema_version
├── job_definition.json        # frozen Job dataclass
├── events.jsonl               # ordered event log
├── tasks/
│   ├── node_0/                # one Phase 4A ReplayPackage per node
│   ├── node_1/
│   └── …
├── registry/
│   ├── 0000_initial.json
│   ├── 0001_pre_node_0.json
│   ├── 0002_post_node_0.json
│   └── …
├── validation/
│   ├── per_task_validation.json   # one ValidationReport per node
│   └── session_report.json        # aggregated across nodes
└── trace.jsonl                    # optional per-tick stream (off by default)
```

### Replay-identity check (separate tool)

`tools/check_session_replay_identity.py` (Phase 4B step 10): given two `SessionPackage` directories, asserts:

1. `manifest.runtime_hash` and `manifest.cell_cfg_hash` match. If not — refuse, do not compare.
2. `events.jsonl` matches **byte-for-byte**, excluding the `wall_ns` field.
3. Every per-task `TaskResult` in `tasks/` matches bit-for-bit on the per-task fingerprint Phase 4A already tests (`peg_xyz_final`, `wrist_3_max_z_m`, `joint_vel_peak_per_joint_rad_s`, `cartesian_path_length_m`, `grasp_acquired_step`).
4. Every `registry/<…>.json` matches byte-for-byte.

This is the orchestration analogue of `TestProfilesPreserveDeterminismOnNominal` from Phase 4A — and explicitly inherits its scope: bit-identical within one `TaskExecutor` instance, within-tolerance across instances.

---

## 6. Lifecycle model — multi-object semantics

Phase 4A registered objects/fixtures via dicts keyed by id (`TestRegistryMultiObjectReadiness` proves this works). Phase 4B formalises the lifecycle.

### Object state lifecycle

```
ObjectState.lifecycle:
    AUTHORED          ← initial pose from CellConfig.parts
       │
       ▼
    IN_TRANSIT        ← TaskExecutor has acquired it (pads_L+R sustained)
       │
       ▼
    PLACED(fixture)   ← TaskExecutor released it within tolerance
       │
       ▼ (next task picks it again)
    IN_TRANSIT → …
```

### Fixture state lifecycle

```
FixtureState.lifecycle:
    EMPTY ←→ OCCUPIED(object_id)
```

Every transition emits a `ObjectStateChanged` or `FixtureStateChanged` event with the (prev, next) pair. These events are reconstructable from the registry snapshots, but emitting them on the bus gives subscribers (HUD, monitors, future planner) a clean reactive interface without polling.

### TaskExecutor.reset_scope — additive change

Today the Phase 4A `TaskExecutor.reset()` teleports **the cell's authored peg** to its authored pose. For a multi-task job where an earlier task placed `Peg_01` on `FixtureA`, calling the same reset before the next task would clobber that placement.

**Resolution:** add an additive `reset_scope` parameter, default preserving Phase 4A behaviour:

```python
class ResetScope(enum.Enum):
    FULL          = "full"           # Phase 4A behaviour: all objects → authored pose
    ACQUIRED_ONLY = "acquired_only"  # only the arm + currently-acquired object
    ARM_ONLY      = "arm_only"       # only the arm; all objects untouched
```

`ExecutionSession.step()` calls `task_executor.reset(scope=ACQUIRED_ONLY)` between nodes. The first task of a job is preceded by a `FULL` reset in `session.begin()`. All 32 Phase 4A tests continue to pass because they exercise the default `FULL` path.

### Predicate surface

Predicates are **pure functions of the registry**. They never touch PhysX.

```python
@dataclass(frozen=True)
class ObjectAtFixture(Predicate):
    object_id:  str
    fixture_id: str

@dataclass(frozen=True)
class FixtureEmpty(Predicate):
    fixture_id: str

@dataclass(frozen=True)
class ObjectPoseWithin(Predicate):
    object_id:    str
    world_pose_m: tuple[float, float, float]
    tolerance_m:  float
```

Phase 4B ships exactly these three. The whitelist discipline from Phase 4A applies — adding a new Predicate kind is a deliberate extension.

### Registry rollback on failure

When a task fails, the registry is restored to the snapshot taken at `TaskStarted`. The simulation world is **not** rolled back — the operator sees the post-failure state (which is diagnostically valuable). Subsequent tasks then either: (a) retry on the post-failure world if retry policy allows, or (b) fail their own preconditions and cascade. This is intentional asymmetry: registry rollback preserves the planner's model; sim non-rollback preserves the diagnostic record.

---

## 7. Determinism guarantees (the contract)

> **Given identical `(Job, seed, cell_cfg, runtime_hash)`, two `ExecutionSession`s within the same process produce:**
>
> 1. **Identical event sequence** — every event in `events.jsonl` matches modulo `wall_ns`.
> 2. **Identical per-task `TaskResult`s** — bit-identical on the Phase 4A fingerprint set.
> 3. **Identical scheduler decisions** — the sequence of node_ids picked matches.
> 4. **Identical registry transitions** — every snapshot matches byte-for-byte.
>
> **Cross-process (fresh `ExecutionSession` in a new process):** results within Phase 3P-measured tolerance (≤ 5 mm peg pose; never breaches a Phase 3M/N/O/P gate). Not bit-identical. Phase 4B does not regress this.

### What gives this property

| mechanism                                    | property it preserves                                |
|---|---|
| Synchronous event bus, no async / threads    | event ordering ↔ replay identity                     |
| Sequential scheduler, no clock, no global RNG | scheduler decisions are pure                         |
| Phase 4A executor reused across all nodes    | per-task bit-identity inherited (Phase 3P + 4A)      |
| `UnifiedValidator` is the only gate logic    | no validation drift                                  |
| `dataclasses.replace`-style profile application | `cell_cfg` is never mutated                       |
| Frozen dataclasses for Job / TaskGraph / TaskNode / Event | no aliasing-based state leaks               |
| TraceRecorder is write-only after-the-fact   | recording cannot influence scheduling                |

### What would break it (forbidden patterns)

- `asyncio`, `threading`, `multiprocessing` in the orchestration layer.
- Wall-clock reads in scheduler, predicate, or event-ordering code paths.
- Iterating an un-ordered `set` where order is observable.
- Hashing on Python object id (`id(x)`) anywhere visible to scheduling.
- Mutating `Job`, `TaskGraph`, `TaskNode`, or `Event` after construction.
- Lazily-evaluated predicates with side effects.
- Subscriber callbacks that mutate the registry directly (they must request a mutation by emitting an event; the executor / session is the only mutator).

---

## 8. Known risk areas & architectural failure modes

Identified before implementation begins:

1. **Scheduler determinism vs. order-sensitivity coverage.** A strict topological order is reproducible but can mask cell-design bugs that appear only under different orderings. **Mitigation:** ship a `--shuffle-seed` flag that produces deterministic-but-non-canonical orderings from a seed, used in stress tests only. Default order remains canonical.

2. **PhysX scene-state accumulation across tasks.** Phase 3P showed test-helper-style fresh handles produce ~mm variation per cycle. **Mitigation:** `ExecutionSession` owns **one** `TaskExecutor` instance reused across every node. `reset_scope=ACQUIRED_ONLY` between nodes (see §6) avoids clobbering placed objects.

3. **Validation gate drift.** Two parallel gate implementations would let one drift. **Mitigation:** job-level checks delegate to `UnifiedValidator`. The executor already does this; Phase 4B reads its verdict rather than re-running gates.

4. **Belt control tied to waypoint names.** Today the executor halts the belt at the `grasp` waypoint and resumes at `lift`. A future task picking from a static tray would still execute this code. **Mitigation:** belt control moves from `_run_cycle` into a per-`PickSource.source_kind` policy (`ConveyorPickPolicy`, `StaticPickPolicy`). This is a Phase 4B step-12 refactor, documented now so it isn't forgotten.

5. **Replay-package storage cost.** 20 tasks × ~1.5 MB / package = ~30 MB / session. 1000-task overnight = ~1.5 GB. Acceptable. **Mitigation if it bites:** `--compact` flag retains only `summary.json` + event log for PASSed tasks, full package only for FAILed tasks.

6. **Event-log growth.** Sync emit means we record everything. ~5 000 events for a 20-min, 1000-task job. Trivial. Not a risk.

7. **TraceRecorder back-pressure.** Synchronous disk writes can stall the simulator. **Mitigation:** intentionally synchronous in v1 (we'd rather stall than miss an event). If it becomes operationally painful, buffer in RAM and flush at task boundary — but only after measuring.

8. **Operator-channel coupling.** The Phase 4A WebRTC session proved operators want to pause / skip / abort live. **Mitigation:** `OperatorChannel` is a synchronous between-node queue; commands NEVER fire mid-tick. Operator inputs become `OperatorOverride` events; absence of input is a no-op, so determinism is preserved when nobody's watching.

9. **Failure cascades.** A failed task's downstream nodes will fail their preconditions. Without distinct event kinds the operator can't tell a real failure from a cascade. **Mitigation:** emit `TaskCascadeSkipped` (distinct from `TaskFailed`) for nodes whose precondition fails due to an upstream failure.

10. **Runtime-version drift.** Cross-process determinism is bounded by PhysX cooking + Isaac Sim version. **Mitigation:** `manifest.runtime_hash` captures `(isaac_sim_version, physx_version, schema_version, cell_cfg_hash)`. The replay-identity tool refuses to compare across mismatched hashes.

11. **Predicate explosion.** Cell designers will want richer predicates than the three shipped. **Mitigation:** the predicate whitelist mirrors the Phase 4A `_realisation_table` discipline — new predicates require a code change + a unit test, not a config knob.

12. **SAFE-profile motion-quality anomaly (Phase 4A carry-over).** SAFE produces *larger* PD overshoots than NOMINAL (16 vs 5 rad/s) despite longer phases. Not blocking Phase 4B architecture, but the orchestration layer must not paper over it — `UnifiedValidator` will continue to flag `MOTION_QUALITY_VIOLATION` per-task, and the per-task verdict propagates up to the session report.

---

## 9. Recommended implementation order

Every step preserves the **32 / 32 PASS** test surface from Phase 4A. New tests are additive.

| step | scope                                                                          | new tests                                                                                                  | regression gate |
|---|---|---|---|
| 1 | Event taxonomy + synchronous `EventBus` + monotone `seq` invariant             | unit (event ordering, subscriber-error handling)                                                            | 32 / 32 unchanged |
| 2 | `TraceRecorder` + `SessionPackage` skeleton (empty job → empty session dir)     | unit (file layout, manifest schema)                                                                         | 32 / 32 unchanged |
| 3 | `Predicate` base + `ObjectAtFixture` / `FixtureEmpty` / `ObjectPoseWithin`     | unit (pure-Python evaluation against a hand-built `CellStateRegistry`)                                      | 32 / 32 unchanged |
| 4 | `TaskGraph` + acyclicity validation + topological sort                          | unit (cycle detection, stable ordering, edge consistency)                                                   | 32 / 32 unchanged |
| 5 | `TopologicalSequentialScheduler` v1                                             | unit (ordering rules 1–5 isolated; clock-independence proof)                                                | 32 / 32 unchanged |
| 6 | `ExecutionSession` wrapping Phase 4A `TaskExecutor`; run the validated cycle as a single-node `Job` | integration: 1-node `Job` PASS + bit-identical to Phase 4A `TestTaskAbstractionEquivalence` baseline | 32 / 32 unchanged + 1 new |
| 7 | Add `reset_scope` to `TaskExecutor.reset()` (additive, default = `FULL`)        | unit (each scope variant preserves correct subset)                                                          | 32 / 32 unchanged |
| 8 | Two-task `Job`: pick-belt→place-A, then pick-A→place-B                         | integration: 2-node job runs, postconditions enforced, registry shows correct lifecycle                     | 32 / 32 + 1 new |
| 9 | Failure handling: precondition violation → cascade-skip; postcondition violation → fail; gate violation → policy-driven | integration (each failure_action variant)                              | 32 / 32 + 3 new |
| 10 | `tools/check_session_replay_identity.py` + CLI                                  | tools-level (same job run twice → byte-equal events log, snapshots, fingerprints)                          | 32 / 32 + 1 new |
| 11 | `OperatorChannel` + `OperatorOverride` event                                   | unit + integration (between-node command intake, mid-tick commands are NOT honored)                         | 32 / 32 + 2 new |
| 12 | Belt-control refactor: move out of `_run_cycle` into `ConveyorPickPolicy`      | unit (policy isolated) + integration (existing cycle unchanged)                                              | 32 / 32 + new policy tests |

After step 12, Phase 4B has a complete orchestration spine and the cell can describe and execute multi-task jobs deterministically. Concrete new task kinds (peg-into-hole, multi-peg sort, vision-driven pick) are Phase 4C scope.

---

## 10. File layout (proposed)

Phase 4B code lives in a **new package** alongside Phase 4A:

```
isaac_factory/extensions/cell_authoring/cell_authoring/
    tasks/                           # Phase 4A — unchanged
        __init__.py
        definitions.py
        profiles.py
        registry.py
        executor.py                  # +reset_scope param (additive)
        validation.py
        replay.py
    orchestration/                   # Phase 4B — new
        __init__.py
        events.py                    # Event, EventKind, EventBus
        predicates.py                # Predicate base + 3 concretes
        graph.py                     # TaskNode, TaskGraph
        job.py                       # Job, retry/failure policies
        scheduler.py                 # TopologicalSequentialScheduler
        session.py                   # ExecutionSession
        trace.py                     # TraceRecorder, SessionPackage
        operator.py                  # OperatorChannel
        policies/
            __init__.py
            conveyor_pick.py         # belt halt/resume policy (step 12)
            static_pick.py

isaac_factory/extensions/asset_validator/tests/unit/
    test_cell_01_phase_4b_*           # one file per step (1, 6, 8, 9, 10, 11, 12)

tools/
    check_session_replay_identity.py # step 10

orchestration/                       # existing empty placeholder at workspace root
    (NOT used — left for cross-cell future scope; Phase 4B lives inside the
     existing cell_authoring extension to keep the import surface stable.)
```

The pre-existing empty [`orchestration/`](../orchestration/) directory at the workspace root is **not** repurposed by this phase — the Phase 4B code lives next to the Phase 4A tasks package, where it can import from `..config`, `..trajectory`, and `..tasks.*` without crossing extension boundaries. The workspace-root `orchestration/` directory stays empty as a marker for a possible future cross-cell orchestration layer (Phase 5+) that would compose multiple cells.

---

## 11. What this document is NOT

* It is not an implementation plan in the sense of "go write this now." Each step in §9 is its own design + review cycle.
* It is not a commitment to specific Python class signatures. The shapes shown are illustrative; the contracts are the §2 lifecycle, the §3 ordering rules, the §4 event taxonomy, the §6 lifecycle model, and the §7 determinism contract.
* It is not a license to touch the Phase 3M–4A validated stack. All Phase 4B work is additive. The single exception — the `reset_scope` parameter on `TaskExecutor.reset()` — is additive with a default that preserves Phase 4A behaviour exactly.

---

## 12. Open questions to resolve before step 1

These are deliberately deferred to the implementation discussion, not pre-decided here:

1. **Predicate serialisation format.** Predicates are dataclasses today (cheap). For replay-identity, do we serialise them as `{"kind": "ObjectAtFixture", "object_id": "...", "fixture_id": "..."}` directly, or via a registered codec table? Recommend the latter for forward-compat.
2. **Retry policy granularity.** Per-node `retry_budget` is enough for now. Do we also need a per-job global budget? Skip until step 9 surfaces a need.
3. **Where event subscribers register.** Constructor argument to `ExecutionSession`, or runtime `session.subscribe(...)`? Recommend constructor — keeps the session immutable after `begin()`.
4. **Event payload schema enforcement.** Free-form `Mapping[str, Any]` for v1 (matches Phase 4A's `metadata` fields); migrate to per-event typed payloads if/when the schema stabilises.
5. **How to express the `derive_seed(job.seed, node_id)` function.** Recommend `hashlib.blake2b(f"{job.seed}:{node_id}".encode(), digest_size=8)` → int. Deterministic, no collisions in practice, no external deps.

---

**End of proposed Phase 4B architecture.**

Predecessor: [Phase 4A — task abstraction](../isaac_factory/extensions/cell_authoring/cell_authoring/tasks/) (32 / 32 PASS).
On approval, step 1 in §9 (`EventBus` + event taxonomy) begins.
