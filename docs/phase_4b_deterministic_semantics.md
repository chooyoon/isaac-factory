# Phase 4B — Deterministic Execution Semantics (Contract)

Status: **authoritative contract.**
Scope: Isaac Sim / PhysX single-process orchestration determinism. Nothing else.
Predecessor: [docs/phase_4b_orchestration_architecture.md](phase_4b_orchestration_architecture.md) — the architectural shape this contract binds.

This document defines the deterministic execution semantics that **every** Phase 4B implementation step, every future extension, and every code review must obey. It is written as a numbered invariant set so that pull requests, tests, and review comments can cite specific clauses (e.g. *“violates D-SCHED-6 — dict iteration in scheduler path.”*).

The contract is **architecture-level**: it constrains semantics, not signatures. Implementation choices may vary; the invariants may not.

### Reading this document

* **Invariant** clauses (`D-XXX-N`) are normative. Code that violates one is wrong.
* **Rationale** paragraphs explain why a clause exists. They are non-normative but should not be paraphrased away in derivative docs.
* **Non-goals** clauses say what the contract deliberately does *not* cover.
* Conflicts between this document and the architecture doc are resolved in favour of this document, because this document is more recent and more specific.

---

## 0. Glossary

| term | definition |
|---|---|
| **orchestration tick** | One iteration of `ExecutionSession.step()`. Advances at most one `TaskNode` through one of its lifecycle states. |
| **physics tick** | One `world.step()` call. Fixed `physics_dt = 1/60 s`. Strictly nested *inside* a single task's physics loop. |
| **node execution** | The interval from `TaskStarted` to `TaskCompleted` / `TaskFailed` for one `TaskNode`. Contains many physics ticks. |
| **command** | A write to a PhysX-visible target (joint drive target, gripper drive, belt surface velocity, world reset). |
| **trace commit** | Persisting a record into the authoritative event / snapshot stream. Atomic per record. |
| **replay-authoritative state** | State whose value is required to reproduce identical orchestration decisions, commands, validation verdicts, and registry transitions. |
| **derived state** | State recomputed from replay-authoritative state on every run; not stored. |
| **diagnostic state** | State emitted for human/observability use; never read back by orchestration logic. |
| **runtime hash** | `H(isaac_sim_version, physx_version, cell_authoring_schema_version, cell_cfg_content_hash)`. The cross-process determinism boundary. |

---

## 1. Execution Ordering Contract  *(D-EXEC)*

### 1.1 Orchestration tick — fixed 7-phase order

Each call to `ExecutionSession.step()` executes the following phases **in this exact order, with no interleaving**:

```
   ┌─ Phase A ─┐ ┌─ Phase B ─┐ ┌─ Phase C ─┐ ┌─ Phase D ─┐ ┌─ Phase E ─┐ ┌─ Phase F ─┐ ┌─ Phase G ─┐
   │  intake   │ │ scheduler │ │ pre-node  │ │  node     │ │ post-node │ │ validate  │ │  commit   │
   │ (drain    │ │ decision  │ │ checks +  │ │ execution │ │ checks +  │ │ + classify│ │ + emit +  │
   │ operator) │ │           │ │ snapshot  │ │ (physics) │ │ snapshot  │ │           │ │ trace     │
   └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘
```

**D-EXEC-1** — The orchestration-tick phases A → G run sequentially. No phase may be skipped except by the rules below:

* Phase A executes only at node boundaries; within a node, operator commands are not honored.
* Phase D may be **bypassed** (E and F skipped) when Phase C fails — control jumps to Phase G to emit the violation event.
* Phase F may be **bypassed** (G still runs) when Phase E surfaces an executor-error verdict; classification falls through to the existing verdict.

**D-EXEC-2** — No phase may emit events out of its phase. Specifically: scheduler decisions are emitted in Phase B; precondition violations in Phase C; gate violations in Phase F; task completions in Phase G. Any event whose phase-of-origin is ambiguous is a contract violation.

**D-EXEC-3** — A single orchestration tick advances exactly one node by exactly one state transition (see §7). Multiple state transitions per tick are forbidden; this preserves the 1:1 correspondence between orchestration ticks and trace records.

### 1.2 Node execution — fixed 5-phase physics-tick order

Phase D contains the inner physics loop. Each iteration of that loop is a *physics tick* and runs in this exact order:

```
   ┌── 1. command ──┐ ┌── 2. step ──┐ ┌── 3. probe ──┐ ┌── 4. update ──┐ ┌── 5. observe ──┐
   │ joint targets, │ │ world.step()│ │ poses,       │ │ registry      │ │ optional       │
   │ gripper drive, │ │ player.adv. │ │ velocities,  │ │ contact +     │ │ step_observer  │
   │ belt control   │ │             │ │ contacts     │ │ pose updates  │ │ (HUD/trace)    │
   └────────────────┘ └─────────────┘ └──────────────┘ └───────────────┘ └────────────────┘
```

**D-EXEC-4** — A physics tick’s phases (1 → 5) run in fixed order. No phase may be reordered or interleaved with another physics tick. `world.step()` is invoked **exactly once** per physics tick. No double-stepping, no zero-stepping, no conditional re-stepping.

**D-EXEC-5** — Command writes (phase 1) happen **before** `world.step()`. Probes (phase 3) happen **after** `world.step()`. Registry updates (phase 4) happen **after** probes. The observer callback (phase 5), if registered, happens **after** all registry updates.

**D-EXEC-6** — The observer callback is read-only with respect to simulation and registry state. It may not issue commands, may not mutate the registry, may not subscribe to the event bus, and may not emit events. Violation of this clause invalidates trace identity.

### 1.3 Trace commit semantics

**D-EXEC-7** — Trace commit happens in Phase G **after** every other phase-G activity completes. Event emission is part of trace commit. The commit is a single append-only operation per record.

**D-EXEC-8** — A trace commit may not occur before the action it records. Specifically: `TaskCompleted` is committed after `UnifiedValidator` returns PASS; `GateViolated` is committed after `UnifiedValidator` returns a non-PASS verdict; `ObjectStateChanged` is committed after the registry mutation that produced it.

**D-EXEC-9** — Trace commit is non-blocking with respect to ordering: if subscriber dispatch (synchronous, see §3) raises, the recorded event is still committed before the exception propagates as a `SubscriberError` event.

### 1.4 Replay checkpoint semantics

A *replay checkpoint* is a registry snapshot serialized at a specific orchestration moment.

**D-EXEC-10** — Replay checkpoints are taken at exactly three points per node:

1. **`pre_node`** — at end of Phase C, before any command is issued.
2. **`post_node_sim`** — at end of Phase E, after the last physics tick.
3. **`post_node_validate`** — at end of Phase F, capturing any registry mutations driven by the verdict (e.g. fixture occupancy on PASS, registry rollback on FAIL).

**D-EXEC-11** — In addition, a single **`session_initial`** checkpoint is taken before the first orchestration tick of `session.begin()`. No mid-physics-tick checkpoints are permitted.

**D-EXEC-12** — A checkpoint’s identity is `(session_id, node_id, kind)`. Two checkpoints with the same identity within one session is a contract violation.

### 1.5 Non-goals

* Multi-physics-tick atomicity windows. Each physics tick is a unit; commands within one physics tick are not transactional across ticks.
* Per-physics-tick replay checkpoints. The per-tick `step_observer` may *record* tick-rate telemetry, but that telemetry is **diagnostic state** (§5), not replay-authoritative.

---

## 2. Scheduler Determinism Contract  *(D-SCHED)*

### 2.1 Pure-function discipline

**D-SCHED-1** — The scheduler’s next-node decision is a **pure function** of:

```
   (TaskGraph, CellStateRegistry, completed: frozenset, failed: frozenset,
    retry_counts: Mapping[node_id, int])
```

No other inputs are permitted. In particular, the scheduler may not read:

* `time.time()`, `time.monotonic()`, `datetime.now()`, or any wall-clock source;
* environment variables;
* filesystem state;
* the event bus;
* the trace recorder;
* the operator channel (operator commands enter via §1 Phase A, not the scheduler);
* any module-level mutable state.

### 2.2 Canonical DAG traversal

**D-SCHED-2** — Traversal of the `TaskGraph` proceeds in a **canonical, stable order** derived solely from the graph topology and `node_id` lexicographic order.

**D-SCHED-3** — The canonical order is defined as: among all nodes whose parents are all `completed` and whose preconditions all evaluate `True`, select the node minimizing `(priority, node_id)` where `priority` is the node’s integer priority field and `node_id` is its stable string identifier.

**D-SCHED-4** — Ties on `(priority, node_id)` are impossible by construction: `node_id` is required to be unique within a `TaskGraph`. A graph constructed with duplicate `node_id`s is malformed and rejected at `TaskGraph.__init__`.

### 2.3 Stable-iteration requirements

**D-SCHED-5** — Every scheduler-visible iteration over a collection of nodes, edges, predicates, or strategies **must** use either:

* a `tuple` (canonically ordered at construction), or
* a list returned by an explicit `sorted(...)` call with a documented key.

**D-SCHED-6** — Iteration over a Python `dict` (other than via `sorted(d.items(), key=...)`) is forbidden in scheduler-visible paths. The fact that CPython 3.7+ preserves insertion order is **not** a substitute — insertion order itself can leak nondeterminism (e.g. set membership tests).

**D-SCHED-7** — Iteration over a Python `set` or `frozenset` is forbidden in scheduler-visible paths. Use `sorted(...)` to lift sets into a deterministic sequence at every consumption site.

**D-SCHED-8** — The scheduler may not rely on traversal order from any external graph library (`networkx`, `graphlib.TopologicalSorter`, etc.). If such a library is used as a *correctness oracle* (e.g. to detect cycles at graph construction), its output **must** be re-ordered into canonical order before being read by the scheduler.

### 2.4 Random / UUID / clock forbidden during execution

**D-SCHED-9** — Random or pseudo-random number generation during a running session is forbidden **except** via a deterministically-seeded RNG whose seed is derived solely from `(job.seed, node_id, purpose_tag)`.

**D-SCHED-10** — `uuid.uuid4()`, `os.urandom()`, `secrets.*`, and any non-deterministic ID-minting routine are forbidden in scheduler, predicate, executor-binding, event-construction, and trace-commit paths. Identifiers used at runtime must be either:

* statically configured (e.g. `node_id` in the `Job` definition), or
* derived from a seeded RNG per D-SCHED-9.

**D-SCHED-11** — Wall-clock reads in scheduler decisions, predicate evaluation, command emission, validation, or replay-authoritative trace commits are forbidden. Wall-clock reads are permitted **only** for the diagnostic `wall_ns` field on events, which is excluded from replay-identity comparisons (§4.2).

### 2.5 Predicate determinism

**D-SCHED-12** — Predicates (`ObjectAtFixture`, `FixtureEmpty`, `ObjectPoseWithin`, and any future predicate) are **pure functions** of `CellStateRegistry`. They may not touch PhysX, may not consult wall time, may not consult random sources, and may not depend on Python object identity.

**D-SCHED-13** — Predicate evaluation order within a single node’s precondition / postcondition list is preserved as the tuple’s construction order. The list is iterated in index order; evaluation short-circuits on the first `False`.

### 2.6 Non-goals

* Parallel scheduling, anytime scheduling, priority-budget scheduling. Phase 4B ships exactly one scheduler (`TopologicalSequentialScheduler`). Any alternative is a deliberate Phase 4C+ extension that must publish its own conformance to D-SCHED-1 through D-SCHED-13.

---

## 3. EventBus Semantics  *(D-BUS)*

### 3.1 Synchronous dispatch

**D-BUS-1** — All event dispatch is **synchronous**. `EventBus.emit(event)` invokes every subscriber and returns only after the last subscriber returns (or raises). No queue, no batch, no deferral, no thread pool, no asyncio task.

**D-BUS-2** — Asynchronous primitives are forbidden in the event-bus implementation: no `asyncio`, no `threading`, no `concurrent.futures`, no `multiprocessing`, no Twisted/Trio/AnyIO, no callback registration libraries that internally defer.

### 3.2 Monotonic ordering

**D-BUS-3** — Every event carries a `seq: int` field. `seq` is **monotone and gap-free** within one `ExecutionSession`: the *k*-th event committed has `seq = k`, starting from `seq = 0`.

**D-BUS-4** — Two events with the same `seq` within one session is a contract violation. `seq` is assigned at commit time, inside the EventBus, holding a single in-process invariant — never derived from wall time or RNG.

**D-BUS-5** — Events emitted in Phase G of orchestration tick *t* have `seq` values strictly greater than every event emitted in any prior phase or prior tick. Phase ordering (D-EXEC-2) and seq ordering align.

### 3.3 Subscriber topology — frozen at session start

**D-BUS-6** — Subscriber registration **must** complete before `ExecutionSession.begin()` returns. After `begin()` returns, the subscriber list is frozen for the lifetime of the session.

**D-BUS-7** — Runtime subscriber registration after `begin()` is a contract violation. There is no `session.subscribe(...)` API post-begin; any such method, if introduced, must raise.

**D-BUS-8** — Runtime subscriber **un**registration after `begin()` is likewise forbidden. A subscriber that wishes to silence itself must filter inside its own callback, not detach.

*Rationale.* Subscriber topology is part of the replay-authoritative state. A trace recorded with subscriber set *S₁* and replayed against subscriber set *S₂* is, by definition, replaying a different observation graph. The session manifest records the subscriber identities (§6.4), and the replay-identity tool refuses to compare across mismatched subscriber sets.

### 3.4 Deterministic subscriber dispatch

**D-BUS-9** — Subscribers receive each event in **registration order** — the order they were added at session construction.

**D-BUS-10** — Per-subscriber dispatch is non-reentrant: a subscriber may not call `emit()` from inside its own callback. (It may *request* an event to be emitted by another component, but it may not directly re-enter the bus.) Re-entry is a contract violation.

### 3.5 Subscriber-exception handling

**D-BUS-11** — A subscriber that raises during dispatch does **not** halt dispatch to remaining subscribers. The exception is captured and recorded as a `SubscriberError` event (with `seq` immediately following the offending event), and dispatch continues.

**D-BUS-12** — `SubscriberError` events are themselves dispatched to all subscribers in registration order, with one exception suppression: the failing subscriber is not re-invoked with its own `SubscriberError`. This prevents trivial reentry loops.

### 3.6 Non-goals

* Retry / dead-letter / replay of failed subscriber callbacks. A subscriber that fails *records* the failure; recovery is out of scope.
* Priority dispatch. Subscriber order is registration order, full stop.

---

## 4. Replay Identity Model  *(D-REPLAY)*

### 4.1 Layered identity

Replay identity is defined at **four** layers, in increasing strictness:

| layer | what it asserts | scope |
|---|---|---|
| **L1 — Orchestration Identity** | Scheduler decisions match: same sequence of `node_id`s selected, same precondition/postcondition verdicts, same retry/failure-action applications. | Logical |
| **L2 — Command Identity** | The sequence of commands emitted to PhysX (joint targets, gripper, belt, world reset) matches at every physics tick of every node. | Logical |
| **L3 — Trace Identity** | The serialized event log (`events.jsonl`) matches modulo the `wall_ns` field. All `seq`, `ts_step`, `kind`, `payload` fields equal. Per-node `TaskResult` fingerprints match (Phase 4A baseline metrics). Registry snapshots match. | Logical |
| **L4 — Semantic Validation Identity** | All `UnifiedValidator` verdicts match for all nodes. PASS-nodes stay PASS; FAIL-nodes fail with the same `TaskOutcome` and `outcome_detail` modulo numerical formatting tolerances. | Verdict-level |

**D-REPLAY-1** — Strictness ordering: **L1 ⊇ L2 ⊇ L3 ⊇ L4**. L3 implies L4. L2 implies L3 (because trace is a deterministic projection of commands + verdicts). L1 implies L2 (because commands are a deterministic projection of scheduler decisions + executor logic).

### 4.2 Bitwise-identical vs semantically-equivalent replay

**D-REPLAY-2** — **Bitwise-identical replay** requires:

* identical `runtime_hash`,
* identical `(Job, seed, cell_cfg_content_hash)`,
* identical subscriber topology,
* same process or same `(OS, libc, BLAS, PhysX cooking cache)` — i.e. byte-equivalent PhysX state evolution.

When all the above hold, L3 holds byte-for-byte (modulo `wall_ns`) and L4 holds verbatim.

**D-REPLAY-3** — **Semantically-equivalent replay** is the weaker property that holds across different processes / different machines / non-byte-equivalent PhysX states. It asserts:

* L1 holds verbatim.
* L2 holds at the **command-program level** — the sequence of commanded targets per physics tick is identical (because commands are derived from the scheduler-chosen profile + waypoints, not from sim state).
* L4 holds: every node’s `TaskOutcome` matches across replays.
* L3 holds with **numerical tolerance** on `TaskResult` fields: peg pose ≤ 5 mm (Phase 3P-measured bound), motion metrics within their Phase 3O gate headrooms.

**D-REPLAY-4** — Bitwise-identical replay is the strong default within a single process / single TaskExecutor instance. Phase 4A `TestProfilesPreserveDeterminismOnNominal` already establishes this at the per-task layer; Phase 4B extends it to the per-session layer.

### 4.3 Runtime-version drift

**D-REPLAY-5** — The session manifest records `runtime_hash = H(isaac_sim_version, physx_version, schema_version, cell_cfg_hash)`. Any field change yields a new `runtime_hash`.

**D-REPLAY-6** — The replay-identity tool **refuses** to perform L3 comparison across mismatched `runtime_hash`. It may optionally perform L4 (semantic-validation) comparison across mismatched runtime hashes, gated behind an explicit `--allow-runtime-drift` flag, with the understanding that L4 success under drift is a weaker guarantee.

**D-REPLAY-7** — A Phase 4B implementation that observes runtime drift (e.g. via Isaac upgrade) **must** record a `RuntimeDriftDetected` diagnostic event but must **not** silently relax replay assertions.

### 4.4 Identity boundaries

**D-REPLAY-8** — Two sessions sharing the same `(Job, seed)` but produced by different `ExecutionSession` *instances* (even within one process) inherit the Phase 3P determinism story: within-instance bit-identical, cross-instance within tolerance. Phase 4B does not strengthen this boundary; it only inherits it.

**D-REPLAY-9** — The session manifest **must** record subscriber identities (stable type names and constructor argument hashes, where available). L3 replay comparison requires identical subscriber sets; mismatched subscriber sets are compared at L4 only.

---

## 5. ExecutionSession Authority Boundary  *(D-SESS)*

### 5.1 Sole mutable-state authority

**D-SESS-1** — `ExecutionSession` is the **sole entity authorized to hold or mutate** orchestration state during a running session. No other entity may:

* construct or initialize PhysX-backed handles (`Articulation`, `RigidPrim`, `PhysXContactSource`);
* call `world.step()`;
* call `world.reset()`;
* mutate `CellStateRegistry`;
* assign event `seq` values;
* append to the trace.

Subordinate components (`TaskExecutor`, `Scheduler`, `EventBus`, `TraceRecorder`) operate **within** the authority `ExecutionSession` extends to them at construction. They do not own state; they implement behaviour over state the session controls.

**D-SESS-2** — Module-level globals that hold session state are forbidden. State must be reachable via the session instance.

### 5.2 State categorization

Every state element falls into exactly **one** of three categories:

| category | examples | replay role |
|---|---|---|
| **Replay-authoritative** | `seq` counter, `JobState.completed/failed/retry_counts`, `CellStateRegistry` (objects, fixtures, robot, task, contact), `TaskResult` fingerprint fields, subscriber set, `runtime_hash` | Must be reconstructable from the trace. L3 replay verifies every replay-authoritative field. |
| **Derived / transient** | trajectory player phase index, contact-source frame buffers, accumulated motion-metric peaks during a tick loop, intermediate joint-target arrays | Recomputed on every run from the replay-authoritative inputs. Never serialized. |
| **Diagnostic** | `wall_ns` event timestamps, profile timing samples, per-tick HUD payloads, `step_observer` payloads, runtime profiling artifacts | Emitted for human inspection. Never read back into orchestration logic. May be omitted from `--compact` traces. |

**D-SESS-3** — Replay-authoritative state **must** be reconstructable from the trace. If a state element affects replay and is not in the trace, the trace is incomplete and the contract is violated.

**D-SESS-4** — Derived state **must** be recomputable from replay-authoritative inputs. If a piece of derived state cannot be re-derived from a fresh process, it is in the wrong category — either promote it to replay-authoritative (and trace it) or accept it as diagnostic (and forbid orchestration logic from reading it).

**D-SESS-5** — Diagnostic state **may not** be read by scheduler, predicate, command-emission, validation, or trace-commit code paths. Any such read is a contract violation.

### 5.3 Mutation discipline

**D-SESS-6** — Registry mutations occur only in:

* `ExecutionSession.begin()` (initial population), and
* Phase D / Phase G of orchestration ticks (executor’s registry updates + verdict-driven occupancy updates + rollback on failure).

No other point in the codebase may mutate `CellStateRegistry`.

**D-SESS-7** — Subscriber callbacks **may not mutate** `CellStateRegistry`, `JobState`, the event bus, or the trace. They may only request a mutation via emitting an event that a session-owned handler later acts on. Direct mutation from a subscriber is a contract violation.

**D-SESS-8** — Strategy / Profile / Predicate / Job / TaskGraph / TaskNode / Event instances are **frozen** (`@dataclass(frozen=True)`). Mutating any of these post-construction is a contract violation; even `object.__setattr__` workarounds are forbidden.

### 5.4 Non-goals

* Session-level distributed locks, leases, coordinators. There is only one process, by design.
* External persistence stores. The trace is the persistence layer.

---

## 6. TraceRecorder Authority Semantics  *(D-TRACE)*

### 6.1 Authoritative categories

**D-TRACE-1** — `TraceRecorder` is **authoritative** for:

| category | content | identity layer |
|---|---|---|
| **Scheduler decisions** | The `node_id` selected at each Phase B, recorded via `TaskScheduled` events. | L1 |
| **Task transitions** | `TaskStarted`, `TaskCompleted`, `TaskFailed`, `TaskRetried`, `TaskSkipped`, `TaskCascadeSkipped`. | L1, L3 |
| **Event ordering** | The `seq`-ordered append-only `events.jsonl`. | L3 |
| **Command emission ordering** | Implicitly via per-`TaskResult` `n_steps` + per-node-boundary registry snapshots. Per-tick command logs are diagnostic (see §6.2). | L2, L3 |
| **Validation outputs** | `UnifiedValidator` verdicts: `TaskOutcome`, `outcome_detail`. One per node. | L4 |
| **Frame indices** | `ts_step` on each event; `n_steps`, `grasp_close_step`, `lift_end_step`, `place_end_step`, `release_start_step`, `release_end_step` on each `TaskResult`. | L3 |

**D-TRACE-2** — The authoritative trace is **append-only**. Records are never edited, never reordered, never deleted post-commit. Compaction (`--compact` mode) deletes only **non-authoritative artifacts** (§6.2); the authoritative event log, manifest, registry snapshots, and validation reports are retained in every mode.

**D-TRACE-3** — The authoritative trace **may not** be regenerated retroactively. A run that fails to commit a record midway leaves a partial trace; the partial trace is preserved as-is, and the manifest is marked `incomplete = true`. There is no “re-emit” path.

### 6.2 Non-authoritative categories

**D-TRACE-4** — `TraceRecorder` is **not** authoritative for, and may freely discard, regenerate, or omit:

* **Caches** — PhysX cooking caches, IK warm-start caches, asset-load caches. These are filesystem-managed by Isaac Sim / our extension layer; the trace records their hash (via `runtime_hash`) but not their contents.
* **Visualization metadata** — viewport camera poses, HUD overlay snapshots, WebRTC stream metadata, replay-video thumbnails. Recorded as diagnostic events; never read back.
* **Diagnostics** — `wall_ns` timestamps, profile timing samples, per-tick `step_observer` payloads, RAM/VRAM measurements.
* **Profiling artifacts** — `cProfile` dumps, NVIDIA Nsight captures, etlfiles. These live in their own directories alongside the session package; their presence or absence does not affect replay identity at any layer.

**D-TRACE-5** — Diagnostic and visualization records, when written, are placed in clearly-named subdirectories (e.g. `diagnostics/`, `viz/`) **outside** the authoritative path. The replay-identity tool ignores everything outside the authoritative path.

### 6.3 Trace integrity

**D-TRACE-6** — Each authoritative record carries enough self-identifying information that a corrupted prefix can be detected: `seq` field, schema_version field. Mismatched `seq` order or unknown schema_version at replay-load time is a fatal error; the replay tool refuses to compare against a corrupt trace.

**D-TRACE-7** — Trace integrity is verified at session close: the recorder asserts gap-free `seq`, monotonic `ts_step`, exactly one `JobStarted` and one terminal `JobCompleted` or `JobAborted`, and one `TaskScheduled` per `TaskStarted`. Verification failures mark the session manifest `integrity_verified = false`.

### 6.4 Manifest content

**D-TRACE-8** — The session manifest records — at minimum — the fields needed to interpret the trace:

* `session_id`, `started_at_wall` (diagnostic-only), `ended_at_wall` (diagnostic-only);
* `job_id`, `seed`, `cell_cfg_content_hash`, `runtime_hash`;
* `schema_version`;
* `subscriber_set: list[{type_name, args_hash}]` — per D-REPLAY-9;
* `integrity_verified`, `incomplete` flags;
* `n_events`, `n_nodes_scheduled`, `n_nodes_passed`, `n_nodes_failed`, `n_nodes_skipped`.

---

## 7. Multi-Object Lifecycle Semantics  *(D-LIFE)*

### 7.1 Object lifecycle states

**D-LIFE-1** — Every orchestration-managed object passes through a strict subset of the following lifecycle states:

```
                        spawned
                           │
                           ▼
                       registered
                           │
                           ▼
                        settled
                           │
                           ▼
        ┌──────────── available ◄───────────┐
        │                                   │
        ▼                                   │
     reserved                               │
        │                                   │
        ▼                                   │
     attached                               │
        │                                   │
        ▼                                   │
     released ─────────────────────────────┘
        │
        ▼  (only when an object exits the cell — out of phase 4B scope)
     retired
```

| state | meaning | who can transition it |
|---|---|---|
| **spawned** | Object prim exists on the stage; no orchestration view yet. | Cell loader (pre-`session.begin()` only). |
| **registered** | `CellStateRegistry.register_object()` has run; object is visible to predicates. | `ExecutionSession.begin()` (initial pass). |
| **settled** | Initial physics-settle ticks have completed; object pose has stabilized. | `ExecutionSession.begin()` Phase reset. |
| **available** | Object is at a known pose, no task currently holds it. Predicates may target it. | Transition from `settled`, or from `released` after a successful PASS. |
| **reserved** | A scheduler has selected a node whose `task.pick_source.object_id == this_object`. Object is logically committed to that node. | Phase B selection. |
| **attached** | Pads have sustained contact (Phase 4A `grasp_acquired_step` reached); the object is being transported. | Phase D, triggered by executor’s temporal grasp detector. |
| **released** | Executor’s release strategy has fired; the object has been set down at the place target. | Phase D, after `release_end_step`. |
| **retired** | Object has left the cell (Phase 4C+ scope; not transitioned by Phase 4B). | Out of scope. |

### 7.2 Transition determinism

**D-LIFE-2** — Each transition is a **deterministic function** of `(current_state, executor_verdict, scheduler_decision)`. No transition depends on wall time, RNG, or external state.

**D-LIFE-3** — Each transition emits **exactly one** `ObjectStateChanged` event in Phase G. Multiple state transitions for the same object within one orchestration tick are forbidden (this preserves D-EXEC-3).

**D-LIFE-4** — Transition table (only these are legal; all others are contract violations):

```
   spawned    → registered     (session.begin, registration pass)
   registered → settled        (session.begin, settle ticks)
   settled    → available      (session.begin, after Phase Reset)
   available  → reserved       (Phase B, scheduler selection)
   reserved   → attached       (Phase D, grasp_acquired_step reached)
   attached   → released       (Phase D, release_end_step reached)
   released   → available      (Phase G, on PASS verdict)
   reserved   → available      (Phase G, on FAIL verdict before grasp)
   attached   → available      (Phase G, on FAIL verdict after grasp)
                                  — registry rollback restores pre-task snapshot
   released   → retired        (Phase 4C+; out of scope)
```

**D-LIFE-5** — A `reserved` object that finishes a PASS becomes `available` again only after both:

1. registry mutation that records the placement (fixture occupancy), and
2. trace commit of `TaskCompleted` for that node.

This ordering prevents a downstream scheduler from picking up the object in a half-transitioned state.

### 7.3 Fixture lifecycle

**D-LIFE-6** — Fixture states form a binary lifecycle:

```
   empty ◄──────────► occupied(object_id)
```

Transitions:

```
   empty       → occupied(o)   (Phase D, executor verifies peg landed within placement_tolerance_xy_m)
   occupied(o) → empty         (Phase D, executor verifies peg lifted past lift_end_step)
```

**D-LIFE-7** — Each fixture transition emits exactly one `FixtureStateChanged` event in Phase G. A fixture cannot transition between two different `occupied(...)` states without passing through `empty` first.

### 7.4 Reservation conflicts

**D-LIFE-8** — Two nodes may not simultaneously hold an object in `reserved` state. The scheduler is responsible for preventing this; the registry enforces it as an invariant — a second `available → reserved` transition for an object already `reserved` is a contract violation and triggers `JobAborted`.

**D-LIFE-9** — Reservation does not survive failure: a `reserved` or `attached` object whose node fails returns to `available` via registry rollback (per §5.3 D-SESS-6 and the Phase 4B architecture doc’s registry rollback rule).

### 7.5 Non-goals

* Per-object physics-time-of-flight tracking outside `TaskResult.peg_xyz_final` and motion metrics. Object pose during transit is in `step_observer` payloads (diagnostic) — not in the authoritative trace.
* Object spawning / despawning during a running session. All objects must be registered at `session.begin()` and may not be added or removed mid-session.

---

## 8. Forbidden Patterns  *(D-FORBID)*

Each of the following is a **contract violation** in Phase 4B orchestration code (where “code” spans scheduler, predicate, executor binding, event bus, trace recorder, session, registry, operator channel, and any code path they touch transitively):

**D-FORBID-1 — Async execution.** Use of `asyncio`, `async def`, `await`, `asyncio.run`, `loop.run_until_complete`, `asyncio.gather`, `asyncio.create_task`, or any third-party async runtime is forbidden in orchestration code.

**D-FORBID-2 — Concurrent PhysX stepping.** `world.step()` may not be called from any thread other than the thread that owns the `ExecutionSession`. The PhysX scene may not be accessed concurrently from multiple threads.

**D-FORBID-3 — Hidden mutable caches.** Module-level mutable singletons, `functools.lru_cache` decorators on functions whose results affect orchestration decisions, and any cache whose contents survive across sessions are forbidden. Caches that are demonstrably pure (e.g. `lru_cache` on a pure mathematical helper) are permitted only if their cache state cannot leak into replay-authoritative outputs.

**D-FORBID-4 — Runtime graph mutation.** `TaskGraph`, `TaskNode`, `Job`, and their constituents are frozen dataclasses; constructing them is the only legal mutation. Once `session.begin(job)` accepts a job, the job and its graph are immutable for the session’s lifetime.

**D-FORBID-5 — Runtime subscriber mutation.** Per D-BUS-6 / D-BUS-7 / D-BUS-8: no subscribe / unsubscribe / reorder after `begin()`.

**D-FORBID-6 — Wall-clock-dependent behavior.** Per D-SCHED-11: no wall-clock reads except for the diagnostic `wall_ns` field. Code that branches on wall time is forbidden.

**D-FORBID-7 — Nondeterministic iteration.** Per D-SCHED-5 / D-SCHED-6 / D-SCHED-7: no dict / set / frozenset iteration in scheduler-visible paths without an explicit `sorted(...)` lift.

**D-FORBID-8 — Hidden replay dependencies.** Any orchestration decision driven by state not in the replay-authoritative set (§5.2) is forbidden. Examples: branching on `os.environ`, on a file’s mtime, on a network response, on a GPU-driver-version check, on a `numpy.random` global RNG state.

**D-FORBID-9 — Speculative execution.** Running a node and then conditionally discarding its effects based on a later predicate is forbidden. Preconditions are checked **before** Phase D; postconditions are checked **after** and may fail the node but may not retroactively erase the physics that happened.

**D-FORBID-10 — Multi-physics-tick `world.step()`.** Calling `world.step(render=…)` more or less than exactly once per physics tick is forbidden. The `n_steps` field on `TaskResult` must equal the number of physics ticks elapsed during Phase D.

**D-FORBID-11 — Per-tick wall-time pacing.** Sleeping, throttling, or otherwise gating physics ticks on wall time within a node is forbidden. (External operator pacing happens between nodes via the operator channel — Phase A — and never inside Phase D.)

**D-FORBID-12 — Cross-session shared state.** State that persists across `ExecutionSession` instances within one process is forbidden in orchestration code. Each session begins from authored cell-config state.

**D-FORBID-13 — Subscriber-driven mutation.** Per D-SESS-7: subscribers may not mutate registry, job state, the bus, or the trace. They may only emit further events.

**D-FORBID-14 — Late binding of frozen state.** Replacing a frozen dataclass field via `object.__setattr__`, `dataclass.replace` *into* an existing slot, or any reflective bypass is forbidden. `dataclass.replace` to construct a *new* instance (as Phase 4A profiles do) is permitted.

---

## 9. Future Scalability Note  *(D-SCALE)*

### 9.1 Explicit prioritization

Phase 4B intentionally prioritizes the following properties:

* **Determinism** — bit-identical replay within a process, semantic equivalence across processes.
* **Replay reproducibility** — the trace is the source of truth and is sufficient to reconstruct every orchestration decision.
* **Auditability** — every command, every verdict, every state transition is a traceable event.
* **Orchestration trace integrity** — gap-free, append-only, monotone.

over:

* throughput,
* concurrency,
* horizontal scalability,
* aggregate jobs-per-second.

This prioritization is **deliberate and load-bearing**. The Phase 3M / 3N / 3O / 3P validation discipline depends on it. Reversing it would invalidate every validated gate.

**D-SCALE-1** — The orchestration layer is **explicitly single-process, single-threaded with respect to PhysX, and sequential with respect to task execution**. This is a design choice, not a temporary limitation.

### 9.2 Scaling paths — if and when needed

**D-SCALE-2** — Scalability, if pursued in a future phase, must be achieved through **process-level partitioning**, not through introducing concurrency inside the orchestration core.

Permitted future scaling axes:

| axis | approach |
|---|---|
| **Deterministic partitioning** | Decompose a large job into multiple independent sub-jobs whose task graphs are disjoint and whose registry footprints are disjoint. Run each sub-job in its own `ExecutionSession` in its own process. Aggregate session packages downstream. |
| **Isolated execution cells** | A second cell (`cell_02.yaml`, etc.) runs in its own process with its own world / stage / executor / session. No shared state. |
| **Process-level replication** | A perturbation sweep runs N processes in parallel, each with a different seed. Each process’s session is internally sequential and deterministic. Aggregation is offline. |

Forbidden future scaling axes:

| axis | reason |
|---|---|
| **Shared concurrent orchestration** | Multiple sessions sharing a world / stage / executor / registry breaks every invariant in §1, §3, §5. |
| **Threaded scheduler** | Violates D-SCHED-1 (pure-function discipline) and creates ordering races. |
| **Async event bus** | Violates D-BUS-1 / D-BUS-2. |
| **Speculative task execution** | Violates D-FORBID-9. |

**D-SCALE-3** — Future phases that propose any scaling beyond the permitted axes above **must** publish their own deterministic-semantics contract and prove that each invariant in this document is either preserved or explicitly superseded with rationale. Until such a successor contract exists, this contract is binding.

### 9.3 Non-goals (forever)

* Distributed orchestration — there is no “orchestrator cluster.” One job, one process.
* Cloud event-stream architectures — events live in a local `events.jsonl`, not in Kafka / Kinesis / Pub-Sub.
* Generic robotics patterns — this contract binds *this* Isaac Sim cell, not arbitrary robot software.
* Throughput optimization — if throughput becomes a bottleneck, reduce work-per-job or replicate processes; do not parallelize internally.

---

## 10. Conformance & enforcement

**D-CONF-1** — Every Phase 4B implementation step (per §9 of the architecture doc) must publish a conformance note listing which invariants of this contract its diff exercises and which existing tests verify each one.

**D-CONF-2** — A pull request that touches scheduler, event bus, trace recorder, session, registry, or operator-channel code must cite at least one specific invariant ID for each behavioural change.

**D-CONF-3** — A test failure that traces back to a violation of any clause in this document is a contract failure, not a flaky test. The fix is to restore conformance, not to relax the test.

**D-CONF-4** — This document is the contract. Subsequent design notes that contradict it are rejected. Subsequent design notes that *extend* it (e.g. adding a new predicate kind that itself obeys D-SCHED-12) are permitted and become part of the contract on landing.

---

## 11. Open extensions (future contract revisions)

The following are recognized gaps that future revisions will need to address. Listing them here marks them as *known-unspecified*, not *forgotten*:

1. **`OperatorOverride` event commutativity.** The contract specifies operator commands enter only at Phase A; it does not yet specify whether two operator commands in the same Phase A drain are processed in arrival order or in a canonical order. Phase 4B step 11 will close this gap.
2. **Diagnostic-event filtering.** D-TRACE-5 says diagnostic records live outside the authoritative path. It does not specify the exact directory layout. The implementation step that lands diagnostic trace plumbing will pin it.
3. **Cross-cell replay identity.** Out of scope here; deferred to a hypothetical Phase 5+ cross-cell contract.
4. **Failure-action determinism under nested cascades.** When task A fails and tasks B and C both depend on A, the order in which B and C are marked `TaskCascadeSkipped` follows D-SCHED-3. But the contract does not yet specify cascade depth limits or cycle-of-cascades edge cases. Phase 4B step 9 will surface and pin this.

---

**End of deterministic-semantics contract.**

This document binds [docs/phase_4b_orchestration_architecture.md](phase_4b_orchestration_architecture.md) and every Phase 4B implementation step that follows. On adoption, the next architectural artifact is the step-1 implementation note for `EventBus` + event taxonomy, which **must** cite this contract for every dispatch / ordering / subscriber-topology choice it makes.
