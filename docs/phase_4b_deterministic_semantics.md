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

### 1.5 Sub-Phase-E interruption surface  *(Step 10 Direction A extension)*

This subsection extends §1.1's Phase E semantics to admit a strictly executor-internal interruption surface introduced by Step 10 Direction A. It carves out the surface *without* relaxing any orchestration-visible D-EXEC clause. From the orchestration tick's perspective (D-EXEC-1..-3), Phase E remains a single atomic call. The interruption surface lives entirely inside the executor.

**D-EXEC-13** — During Phase E, the executor MAY consult a session-supplied **interruption predicate** at deterministic **segment boundaries** internal to `execute()`. A *segment boundary* is the discrete state in which **all** of the following hold simultaneously:

1. The most recent `world.step()` for the current `execute()` invocation has returned.
2. The registry's last-tick canonical-pose write for that step has been committed (D-CONT-1).
3. The executor holds no in-flight PhysX command (joint targets, gripper drive, belt control all settled).
4. The robot is at a documented trajectory-segment terminus — an author-declared boundary such as approach / grasp / lift / transport / place / release / retract — NOT mid-segment, NOT between physics ticks within a segment.
5. Object D-LIFE state is well-defined (no in-transition state).

Consulting the predicate at any other point is **FORBIDDEN**. The boundary set is determined by the trajectory author at trajectory construction; the executor MUST NOT invent new boundaries at runtime.

The predicate is a **pure function** of its `segment_tick: int` argument and a closure over session-provided authoritative state captured **at `execute()` invocation entry**. Permitted closure inputs are restricted to the authoritative-state whitelist:

* the snapshot of pending `OperatorEnvelope` instances at `execute()` entry (D-FAULT-9);
* the session's `_orchestration_tick` at `execute()` entry (`base_tick`);
* the active `TaskDefinition.tick_budget_ticks` (D-FAULT-12);
* the active `TaskDefinition.task_id` (read-only identifier).

Closure over PhysX state (D-CONT-2 forbidden inputs), wall-clock sources, random sources, the executor's internal state, the session's mutable runtime fields, or any non-authoritative observational projection is **FORBIDDEN**. The predicate MUST NOT emit events, log, mutate any captured object, or perform I/O.

If the predicate returns `True` at a legal segment boundary, the executor MUST:

* perform NO further `world.step()` invocations within this `execute()` call;
* perform NO further PhysX commands within this `execute()` call;
* return a `TaskResult` whose `outcome` is `TaskOutcome.EXECUTION_INTERRUPTED` (D-FAULT-1b);
* populate `ticks_consumed` with the cumulative count of `world.step()` invocations performed up to and including the most recent settled boundary (D-FAULT-12c).

If the predicate returns `False` at every boundary the executor consults, `execute()` runs to trajectory completion exactly as in the Phase 4A baseline; `outcome` is the normal validator verdict and `EXECUTION_INTERRUPTED` is **NOT** produced.

**D-EXEC-13a** — Phase E remains **atomic from the orchestration perspective**. D-FAULT-6a is preserved: the session calls `executor.execute(task, ...)` once, observes a single `TaskResult` return, and proceeds to Phase F/G. The session MUST NOT, during a single Phase E:

* interleave Phase A envelope drains;
* dispatch the EventBus;
* emit events;
* take boundary snapshots (D-EXEC-10's three checkpoints are exhaustive);
* observe `segment_tick` values or per-segment events.

Sub-Phase-E interruption is **executor-internal**. From every D-EXEC-1..-12 perspective, Phase E is one atomic call; the predicate-consultation surface is not an orchestration phenomenon, not a phase reordering, not a new event-emission point, and not a new mutation path.

**D-EXEC-13b** — `segment_tick` (the predicate's integer argument) is the count of segment boundaries completed strictly before the predicate call within the current `execute()` invocation: `segment_tick = 0` before any segment runs, `segment_tick = N` after `N` segments complete. `segment_tick` is **executor-deterministic**: for identical inputs and identical trajectory, every cycle produces an identical sequence of `segment_tick` values at identical predicate-consultation sites.

The forensic fields `interrupted_at_segment_index: int | None` and `interrupted_at_segment_name: str | None` on `TaskResult` are **observational, not authoritative**. They MUST be derivable from `ticks_consumed` plus the trajectory's static segment-tick map and MUST NOT enter the per-task fingerprint (D-FAULT-10). Duplicating their state into authoritative continuity would double-bind replay-identity to the same underlying fact, a violation of D-CONT-7a's projection-purity discipline.

**D-EXEC-13c** — The interruption predicate is **session-constructed only**. Construction of an interruption predicate outside the session — by the executor, by trajectory authors, by external callers, by validator code, by registry code — is **FORBIDDEN**. This preserves single-emitter discipline (D-FAULT-2) for the interruption surface: the session is the sole authority that selects which envelopes and which budget shape the predicate's `True`-condition.

The executor consumes the predicate as an opaque callable: it MUST NOT introspect the predicate's closure, MUST NOT re-derive its inputs, and MUST NOT replace the predicate with an alternative mid-`execute()`. Predicate substitution mid-execute, predicate composition by the executor, or predicate state-carrying across `execute()` invocations are all **FORBIDDEN**.

**D-EXEC-13d** — Sub-Phase-E interruption is **not** speculative: the executor MUST act on the predicate's first `True` return at a legal boundary by terminating the `execute()` call. Continuing past a `True` return — even with the intent of "checking again later" or "trying to reach a more convenient boundary" — is **FORBIDDEN**. There is no soft-interruption, no retry-the-predicate, no defer-until-next-segment semantic.

*Rationale.* The interruption surface is, by construction, a **deterministic observational consequence** of orchestration truth, not an independent control authority. The predicate reads only authoritative state captured at execute-entry; the executor honors the predicate at deterministic boundaries; the session classifies the result post-Phase-E (D-FAULT-3b). Across this boundary, no authority is widened, no mutation path is added, no event ordering is relaxed. Phase E remains atomic from orchestration's perspective. Sub-Phase-E is an executor-internal mechanism for honoring a session-supplied predicate, nothing more.

### 1.6 Non-goals

* Multi-physics-tick atomicity windows. Each physics tick is a unit; commands within one physics tick are not transactional across ticks.
* Per-physics-tick replay checkpoints. The per-tick `step_observer` may *record* tick-rate telemetry, but that telemetry is **diagnostic state** (§5), not replay-authoritative.
* Per-physics-tick interruption granularity. The predicate is consulted at **segment** boundaries only (D-EXEC-13 condition 4); per-step predicate consultation is **FORBIDDEN**.
* Sub-segment interruption ("interrupt 30% of the way through grasp"). Interruption eligibility exists only at the boundaries D-EXEC-13 enumerates.
* Async cancellation, signal-driven interruption, or thread-based interruption. The predicate is synchronously consulted by the executor in the same thread as `world.step()`.

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

### 2.7 D-SCHED-14 — Orchestration-Decision Input Whitelist Closure

**D-SCHED-14** — The input sets of the orchestration-decision pure functions are constitutionally **closed** — no additional input may be admitted without explicit amendment of the cited governing clause:

* scheduler input set: `(graph, registry, completed, failed, retry_counts)` (D-SCHED-1);
* predicate input set: `registry` (D-SCHED-12);
* registry-mutation entry points: `ExecutionSession.begin()` and Phase D / Phase G of orchestration ticks (D-SESS-6);
* executor predicate closure capture set: `(envelope snapshot, base_tick, tick_budget_ticks, task_id)` at execute-entry (D-EXEC-13c).

Widening any of these sets without explicit amendment of the cited governing clause is **FORBIDDEN**.

**Citations.**
* Anchor: D-SCHED-1, D-SCHED-12, D-SESS-6, D-EXEC-13c

*Note.* This clause asserts framework Theorem T9 (Orchestration-Decision Input Whitelist Closure) per `docs/phase_4b_step11_closure_verification.md` §5. T9 captures the closure property of the orchestration-decision input-whitelist set: each input set is uniquely fixed by an existing governing clause; no additional input may be admitted without weakening at least one existing clause. T9 is normative-strengthening (making the implicit closure of D-SCHED-1 + D-SCHED-12 + D-SESS-6 + D-EXEC-13c explicit), not normative-additive — it forecloses the addition of new orchestration-decision inputs (e.g., observer surfaces, transport-layer state, hardware-sensor reads outside D-CONT-5a's PhysX projection) without explicit clause amendment.

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

### 4.5 D-REPLAY-10 — Scheduled-Injection Replay Primitive

**D-REPLAY-10** — A replay tool **MAY** reconstruct a session's `pending_operator_envelopes` content from the authoritative trace via a **scheduled-injection** primitive: for each `OperatorAbortRequested` / `OperatorPauseRequested` / `OperatorResumeRequested` event, reconstruct an `OperatorEnvelope` from payload `(kind, requested_at_tick, reason)` with `envelope_id` content-addressed per D-FAULT-9; associate each envelope with the event's `ts_step` as its scheduled drain tick; at each Phase A, inject envelopes whose scheduled drain tick equals the current `orchestration_tick` into `_pending_envelopes` before the canonical-order drain. The pre-queue primitive (envelopes passed to `pending_operator_envelopes` at `session.begin()`) is the special case where each envelope's scheduled drain tick equals its `requested_at_tick`.

Scheduled-injection is a **replay-tool reconstruction algorithm**, not a substrate-runtime obligation. The production `ExecutionSession` is unchanged: production envelope intake remains live channel pull and pre-queue per the existing D-FAULT-9 contract.

**Citations.**
* Anchor: D-REPLAY-1, D-REPLAY-2, D-TRACE-2, D-FAULT-9

*Note.* This clause asserts framework refinement R1 to Lemma L4 (Replay-Reconstruction From Trace Alone) per `docs/phase_4b_step11_admissibility_framework.md` §C.4 and `docs/phase_4b_step11_f58_paused_analysis.md` §J.2. R1 extends L4's reconstruction primitive from "pre-queue only" to "scheduled-injection," resolving the late-arrival case where an envelope's Phase A drain tick differs from its `requested_at_tick`. D-REPLAY-10 is normative-strengthening (making explicit the replay-tool reconstruction primitive that the trace + D-FAULT-9 content-addressing already enable), not normative-additive — it introduces no new production-runtime semantics, no new ingress surfaces, and no new authority quanta; `orchestration_tick` remains the authority quantum (D-SCHED-11 preserved); transport-independence (framework Theorem T5) is preserved (the replay tool reads only the trace). The extraction plan §4.2 row 6 reference to "L4 framework label" is materialized in this Note section to preserve V9 framework-ref confinement; the Citations Reference subsection is intentionally omitted to avoid V17 ambiguity with the contract's local "L4" label (§4.1 Semantic Validation Identity layer, an unrelated concept).

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
4. **Failure-action determinism under nested cascades.** Pinned in §13 D-FAULT (D-FAULT-3, D-FAULT-3a, D-FAULT-4, D-FAULT-7) — sibling-tolerant default with explicit `FailureAction.ABORT_COHORT` / `ABORT_JOB` escalation; cascade emission iterates `graph.canonical_order`; emission is idempotent at the transition.

---

## 12. Inter-Node Continuity Contract  *(D-CONT)*

### 12.0 Scope

This section binds **Step 8 onward** — the first runtime moment at which the deterministic-execution contract crosses a node boundary with retained state. Up to Step 7, the contract concerned one node's execution and one session's bookkeeping. From Step 8 forward, the contract concerns what authority survives the inter-node gap and what does not.

Step 8 deliberately does not prove orchestration capability. Step 8 proves: **deterministic retained-state handoff with contamination-resistant replay-authoritative continuity semantics.** The two-node test job (pick-belt → place-FixtureA, then pick-FixtureA → place-FixtureB) is a validation vehicle. The deliverable is the authority discipline catalogued below.

Subsequent implementation steps (9 retry/cascade, 10 replay-identity tool, 11 operator channel, 12 conveyor-policy refactor) MUST cite this section for every cross-node assumption they make.

### 12.1 Authoritative vs Observational State

The Phase 4B runtime distinguishes three orthogonal state populations:

| population | example fields | authority? | replay-identity participation |
|---|---|---|---|
| **Authoritative continuity** | object D-LIFE state, fixture occupancy, canonical object pose, session orchestration sets, event-ordering metadata | yes | yes — explicitly enumerated by D-CONT-1 |
| **Observational projection** (registry mirrors of live simulator state) | per-tick joint velocities, contact flags, wrist pose, gripper drive target | no | no — incidentally survive the boundary, MUST NOT be relied on |
| **Diagnostic** | `wall_clock_s`, `joint_vel_peak_rad_s`, `cartesian_path_length_m`, `wall_ns` | no | no — emitted for human inspection, excluded from all L3 comparisons |

Four principles bind the partition; each is normative.

* **Simulator state is NOT orchestration authority.** PhysX scene values are read by the executor as observational probes (D-EXEC-5 phase 3); they enter the registry only as observational projection. Orchestration may not infer authority from "the simulator happened to leave it there."

* **Registry state is NOT authoritative by default.** The `CellStateRegistry` is a convenience aggregator. Membership in the registry does not imply replay authority. Authority is conferred explicitly and only by D-CONT-1.

* **Observational projection does NOT imply replay authority.** The executor's per-tick `update_object_pose`, `update_contact_state`, `update_robot_pose` writes mirror live physics into the registry. They are observational. Only the *last-tick* canonical object pose is promoted to authoritative by D-CONT-1; intermediate per-tick writes are not promoted by anything.

* **Only explicitly enumerated D-CONT state participates in replay identity.** A field not named in D-CONT-1 does not participate in L3 replay identity (D-REPLAY-1). The boundary snapshot serializer (D-CONT-6) enforces this allowlist mechanically.

*Rationale.* The Phase 4A `CellStateRegistry` was authored before Step 8 made the registry replay-authoritative in part. Without an explicit partition, every future contributor would naturally assume "if it's in the registry, it matters." That inference is wrong, frequent, and load-bearing for the determinism contract. D-CONT-7 turns it into a contract violation.

### 12.2 D-CONT-1 — Authoritative continuity enumeration

**D-CONT-1** — Authoritative retained continuity across node boundaries is **strictly limited to**:

* **object ownership** — the D-LIFE state of each managed object (D-LIFE-1);
* **fixture occupancy** — the D-LIFE-6 binary state of each managed fixture;
* **canonical object pose** — the final per-tick `update_object_pose` write the outgoing node made to the registry for each registered object;
* **session orchestration sets** — `_completed`, `_failed`, `_skipped`, `_retry_counts`, `_node_runtime` (D-SESS-1; `_skipped` added by D-FAULT-4a);
* **deterministic event-ordering metadata** — `seq`, `orchestration_tick`, source `node_id`, snapshot `kind` (D-BUS-3, D-EXEC-12).

This list is the complete authoritative continuity set for Phase 4B. Anything not in this list is, by D-CONT-1, not authoritative. Expansion of this set is a contract revision, not an implementation detail. The Step 9 expansion (`_skipped` and the per-node `_cascade_emitted` / `_blocked_emission_key` fields of `_node_runtime`) is normatively pinned by D-FAULT-4a and D-FAULT-7; the corresponding `BOUNDARY_SNAPSHOT_SCHEMA_VERSION` bump from 1 to 2 is governed by D-CONT-6b.

### 12.3 D-CONT-2 — Non-authoritative state forbidden as continuity input

**D-CONT-2** — The following are non-authoritative continuity inputs. None may be read by predicates, scheduler decisions, registry writes, validator gates, or replay-identity assertions:

| forbidden continuity input | reason |
|---|---|
| rigid-body linear velocity | residual dynamic state; non-portable across PhysX versions |
| rigid-body angular velocity | same |
| contact manifold persistence | solver-internal warm-start data; not stable across solver iterations |
| solver warm-start cache | implementation-defined; opaque |
| articulation stabilization state | numerical convergence artifact, not a logical property |
| sleep/wake state of any rigid body | PhysX-internal optimization, not orchestration semantics |
| latent PhysX solver residuals | non-deterministic across runtime versions by definition |
| per-tick aggregate metrics computed inside a node (motion peaks, accelerations, EE speeds) | bounded to per-node verdicts only; no cross-node meaning |

A predicate or replay-identity comparator that wants to read any of the above is the wrong predicate or comparator. A future requirement that seems to require any of the above means the architecture is wrong, not the contract.

### 12.4 D-CONT-3 — Boundary PhysX-quiescence

**D-CONT-3** — Between the outgoing node's Phase-G snapshot commit and the incoming node's Phase-B precondition evaluation, exactly **zero** `world.step()` calls occur. The interval is PhysX-quiescent.

Commands issued during the interval (belt-velocity restoration, registry writes, event emissions) are non-stepping operations: they queue PhysX-visible writes for the incoming node's first physics tick but do not themselves advance the simulator clock. Forbidden between phases:

* `world.step(...)`;
* `world.play()` followed by an implicit step;
* `kit.update()` if it can drive a step;
* any other simulator-advancing primitive.

*Rationale.* A single idle `world.step()` between nodes permits passive settling drift — gravity nudging objects, sleeping joints ticking toward solver-resolved rest. That drift is deterministic in one run but diverges across PhysX versions, BLAS implementations, and compile flags. Forbidding the step removes the channel.

### 12.5 D-CONT-4 — `ResetScope.ACQUIRED_ONLY` semantics

**D-CONT-4** — `ResetScope.ACQUIRED_ONLY` means **selective authoritative persistence of ownership-closed retained state only**.

It is NOT:

* arbitrary simulator persistence;
* residual dynamic continuity preservation;
* emergent PhysX-history authority;
* "whatever happens to survive `world.step()` not being called" as a feature.

The reset implementation is required to:

* preserve canonical object pose for objects whose D-LIFE state at boundary entry is `available` or `released` and which are ownership-closed (no pending reservation conflict);
* preserve fixture occupancy in the registry;
* explicitly drain or zero everything in the D-CONT-2 forbidden list whose drain is itself a non-stepping operation (e.g. `registry.contact = ContactState()`, `contact_source.query_contacts()` to flush);
* re-issue **no** PhysX teleport commands (no `set_joint_positions`, no `set_world_poses`, no `set_linear_velocities`).

Anything `ACQUIRED_ONLY` does not enumerate is not persisted in the contract sense. If the implementation happens to leave it in place because no code touched it, that is incidental and may not be relied on.

### 12.6 D-CONT-5 — Occupancy mutation authority

**D-CONT-5** — `mark_fixture_occupied` and `mark_fixture_empty` are callable **only** from `ExecutionSession`, **only** in Phase G of an orchestration tick, conditioned on:

1. the outgoing executor's `TaskResult` has `outcome == TaskOutcome.PASS`;
2. the task definition declares a fixture transition (`task.pick_source.fixture_id` for `mark_fixture_empty`; `task.place_target.fixture_id` for `mark_fixture_occupied`);
3. the executor's `TaskResult` carries objective placement/release evidence (final pose, lift-off step, placement offset) within the task definition's declared tolerances.

The executor **emits evidence**. The `UnifiedValidator` **confirms the verdict**. The session **commits the registry transition**. Three distinct authorities, one mutation point.

A direct registry write from inside `TaskExecutor._run_cycle` to `mark_fixture_*` is a contract violation, even if the resulting registry state would be equivalent. The discipline is positional, not consequential.

#### 12.6.1 D-CONT-5a — Observational mirroring corollary

**D-CONT-5a** — `TaskExecutor` may mirror continuous-valued physics state into the registry per tick (pose, joint velocities, contact-flag snapshot) as an observational projection (D-EXEC-5 phases 3–4). It may NOT perform categorical lifecycle state transitions (fixture occupancy, D-LIFE state changes). Lifecycle transitions are Phase-G, session-owned, verdict-conditioned.

*Rationale.* Per-tick mirroring populates the registry with values needed by per-tick observers and by the final-tick canonical pose. Lifecycle transitions are categorical decisions about replay-authoritative state — they belong with the single orchestration authority (D-SESS-1), not with a subordinate executor.

### 12.7 D-CONT-6 — Boundary snapshot canonicality

A **boundary snapshot** is the serialized artifact captured at the `pre_node` and `post_node` checkpoints of every orchestration tick (D-EXEC-10). Once written, its canonical-JSON hash is replay-authoritative and participates in every L3 replay-identity comparison (D-REPLAY-1).

The boundary snapshot serializer is **not** "registry serialization." It is a **replay-authoritative canonicalization boundary** — the precise interface at which the runtime's open-world state is projected down to a closed-world replay identity. Modifying it modifies the contract.

#### 12.7.1 Allowlist-only serialization

**D-CONT-6** — Boundary snapshot serialization is **allowlist-only**. Snapshots are constructed by explicit enumeration of authoritative fields, never by filtering a full state dump.

**Forbidden implementation pattern — blacklist filtering of a full dump.** Any future field added to the source mapping leaks into the snapshot until someone remembers to delete it.

```python
# FORBIDDEN — serialization-by-subtraction.
snapshot = registry.to_dict()
del snapshot["velocity"]
del snapshot["contact_manifold"]
# A new registry field added next quarter silently lands in the snapshot
# and silently joins the replay-identity hash. The contract is breached
# without a single test failing.
```

**Required implementation pattern — serialization-by-enumeration.** Adding a field to the source mapping has no effect on the snapshot unless the allowlist is updated, which is a deliberate, reviewable contract revision.

```python
# REQUIRED — explicit enumeration from D-CONT-1.
snapshot = {
    "schema_version": BOUNDARY_SNAPSHOT_SCHEMA_VERSION,
    "kind":           kind,           # "pre_node" | "post_node"
    "node_id":        node_id,
    "seq":            seq,
    "objects": {
        oid: {
            "pose_m":      [float(x), float(y), float(z)],
            "dlife_state": dlife_state,
        }
        for oid, (pose, dlife_state) in sorted(authoritative_objects.items())
    },
    "fixtures": {
        fid: {"occupied_by": occupied_by}
        for fid, occupied_by in sorted(authoritative_fixtures.items())
    },
    "session": {
        "completed":    sorted(session_completed),
        "failed":       sorted(session_failed),
        "skipped":      sorted(session_skipped),   # D-FAULT-4a (schema_version=2)
        "retry_counts": [
            [nid, session_retry_counts.get(nid, 0)]
            for nid in sorted(session_retry_counts)
        ],
    },
}
```

Iteration over any mapping during snapshot serialization uses `sorted(keys)`. Canonical-JSON encoding uses `sort_keys=True`, `ensure_ascii=True`, `allow_nan=False`, separators=(`","`, `":"`) — identical to the `canonical_dumps` helper in [`orchestration/package.py`](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/package.py).

**Allowed snapshot content:**

* object D-LIFE state, per `object_id` (D-CONT-1);
* fixture occupancy, per `fixture_id` (D-CONT-1, D-CONT-5);
* canonical object pose (last-tick `update_object_pose` value), per `object_id` (D-CONT-1);
* session orchestration sets (`_completed`, `_failed`, `_skipped`, `_retry_counts`, `_node_runtime`); `_skipped` and the per-node idempotency fields are mandatory from `BOUNDARY_SNAPSHOT_SCHEMA_VERSION = 2` onward (D-FAULT-4a, D-FAULT-7);
* deterministic event-ordering metadata (`seq`, `orchestration_tick`, source `node_id`, snapshot `kind`);
* `schema_version` constant per snapshot kind (D-TRACE-6; current value `2` post-Step-9 per D-FAULT-4a).

**Forbidden snapshot content** (this list is normative):

* rigid-body linear velocity (D-CONT-2);
* rigid-body angular velocity (D-CONT-2);
* contact manifold cache state (D-CONT-2);
* sleep/wake state (D-CONT-2);
* solver warm-start / convergence residuals (D-CONT-2);
* articulation stabilization state (D-CONT-2);
* runtime diagnostics (`wall_ns`, `wall_clock_s`, profile timings) (D-TRACE-4);
* per-tick aggregate metrics (motion peaks, accelerations, EE speeds, joint vel peaks) (D-CONT-2);
* derived motion-quality aggregates;
* transient executor-local measurements (probe intermediates, `prev_jvel`, contact-tick scratch state) (D-SESS-4);
* any timestamp not derivable from `seq` + `orchestration_tick` (D-SCHED-11);
* observational-only registry mirrors not explicitly enumerated in D-CONT-1 (e.g. `RobotState.joint_velocities_rad_s`, intermediate `ContactState` flags) (D-CONT-7);
* any field whose presence-or-absence in a future PhysX/Isaac version could differ.

#### 12.7.2 D-CONT-6a — Snapshot identity rule

**D-CONT-6a** — Two boundary snapshots have **equal identity** if and only if their canonical-JSON encodings are byte-equal. A snapshot may not carry equality-relevant data outside its canonical-JSON form. Sidecar files, diagnostic JSON, and metadata sibling artifacts are forbidden from contributing to snapshot identity even when they sit in the same `sessions/<sid>/registry/` directory.

#### 12.7.3 D-CONT-6b — Forward-compatibility

**D-CONT-6b** — Snapshot `schema_version` is mandatory. A snapshot read at replay time whose `schema_version` differs from the comparator's expected version is **refused**, not coerced. There is no automatic forward migration of snapshots. Cites D-TRACE-6.

#### 12.7.4 D-CONT-6c — Snapshot projection purity

**D-CONT-6c** — The `boundary_snapshot(...)` projector MUST be:

* **pure-function** — no instance state, no class state;
* **side-effect free** — no I/O, no event emission, no registry mutation, no logging that influences identity;
* **deterministic** — identical authoritative inputs produce identical outputs;
* **allowlist-only** — fields are enumerated explicitly (D-CONT-6);
* **independent of runtime clocks** — no wall-clock reads (D-SCHED-11);
* **independent of simulator-private state** — no PhysX queries, no scene reads, no live handle dereferences;
* **independent of incidental registry fields** — fields not in the D-CONT-1 allowlist are not read, not iterated, not even probed for existence.

Two calls with identical authoritative inputs MUST produce byte-identical canonical-JSON output. A unit test asserting this property is required by every implementation of the projector.

*Rationale.* `boundary_snapshot` is the choke point at which open-world simulator state becomes closed-world replay identity. Any impurity in the projector — a wall-clock read, a hash dependent on Python object id, a `dict.items()` call on an unsorted map — silently couples replay identity to runtime-environmental variables. The projector's purity is not an optimization; it is the contract.

### 12.8 D-CONT-7 — Observational projection discipline

**D-CONT-7** — A registry field written by per-tick observational projection is replay-authoritative if and only if it is **explicitly enumerated** by D-CONT-1. Every other registry field written by the executor is observational only.

**Presence inside the registry does not imply continuity authority.** Membership in the `CellStateRegistry` confers no authority on its own. Authority is conferred explicitly and only by D-CONT-1.

Registry-field classification for Phase 4B:

| registry field | written by | authoritative under D-CONT-1? |
|---|---|---|
| `objects[oid].pose_m` | per-tick observational projection | **yes** at last-tick value only; intermediate per-tick values are observational |
| `objects[oid].yaw_rad` | per-tick observational projection | **yes** at last-tick value (mirrors `pose_m`) |
| `objects[oid].contact_with` | per-tick observational projection | **no** — observational only |
| `objects[oid].metadata` | (free-form scratchpad) | **no** — diagnostic |
| `fixtures[fid].occupied_by` | session-committed in Phase G (D-CONT-5) | **yes** |
| `fixtures[fid].metadata` | (free-form scratchpad) | **no** — diagnostic |
| `robots[rid].joint_positions_rad` | per-tick observational projection | **no** — observational only |
| `robots[rid].joint_velocities_rad_s` | per-tick observational projection | **no** — observational only (also D-CONT-2 forbidden) |
| `robots[rid].wrist_3_xyz` | per-tick observational projection | **no** — observational only |
| `robots[rid].gripper_state` | per-tick observational projection | **no** — observational only |
| `robots[rid].gripper_drive_target` | per-tick observational projection | **no** — observational only |
| `task.step`, `task.phase`, `task.task_id`, `task.started_at_step` | per-tick / lifecycle transition | **no** — diagnostic |
| `contact.*` (all flags + `pad_pen_max_mm`) | per-tick observational projection | **no** — the only authoritative claim about contact at a boundary is "`ContactState()` zeroed" (D-CONT-4) |
| `metrics` (free-form scratchpad) | per-tick observational projection | **no** — diagnostic |

**Consequence for snapshot construction.** The boundary snapshot serializer is **not** `registry.snapshot()` — that method emits every registry field, observational and authoritative alike. Step 8 introduces a separate `boundary_snapshot(...)` projector that emits only the D-CONT-1 allowed set. The full `registry.snapshot()` remains available for diagnostics; its output never enters a replay-identity hash.

#### 12.8.1 D-CONT-7a — Forward discipline

**D-CONT-7a** — A future contributor who adds a new registry-write site MUST classify it on landing as either:

* **authoritative** — in which case D-CONT-1 is amended in the same patch and the `boundary_snapshot` allowlist is extended, with a fingerprint-version bump (D-TRACE-6) and a forward-compat plan; or
* **observational/diagnostic** — in which case it is excluded from `boundary_snapshot` and the field's docstring states "observational projection only, not authoritative continuity state."

A write site with unclassified status is a contract violation. Pull-request review for any patch touching [`tasks/registry.py`](../isaac_factory/extensions/cell_authoring/cell_authoring/tasks/registry.py), [`tasks/executor.py`](../isaac_factory/extensions/cell_authoring/cell_authoring/tasks/executor.py), or [`orchestration/session.py`](../isaac_factory/extensions/cell_authoring/cell_authoring/orchestration/session.py) MUST cite each registry-write classification.

### 12.9 Contributor discipline — field classification on landing

The architecture is now **replay-authority-driven** rather than convenience-state-driven. Every field added to a replay-touching surface must be classified at the time of landing, in the same patch that introduces it. Unclassified fields are contract violations regardless of intent.

Replay-touching surfaces requiring classification on every field addition:

| surface | classification required |
|---|---|
| `CellStateRegistry` field | authoritative (with D-CONT-1 amendment) or observational/diagnostic (with exclusion confirmation) |
| `TaskResult` field | authoritative-evidence (input to D-CONT-5 commit) or observational/diagnostic |
| event payload field | replay-authoritative (enters `events.jsonl` identity) or diagnostic (`wall_ns`-class) |
| boundary snapshot schema field | authoritative-only (a snapshot field is by construction authoritative; D-CONT-6b governs forward-compat bumps) |
| `Predicate` configuration field | replay-authoritative (enters predicate fingerprint) — predicates are pure functions of D-CONT-1 state, no other classification permitted |

Classification lives in the field's docstring or its containing dataclass docstring. A reviewer's first job on a Phase 4B+ patch is to verify every new field is classified. A reviewer's second job is to verify the classification matches the field's use sites.

*Rationale.* Phase 4A landed with implicit classification — "if I wrote it down, someone will figure out what it means later." Step 8 makes classification explicit because replay identity now depends on it. The contributor-discipline note is the human-process complement to D-CONT-7a's mechanical rule.

### 12.10 Preserved architectural constraints

This contract section explicitly preserves and does NOT relax the following architectural constraints from §1–§9:

* **No new top-level orchestration phase.** Boundary continuity is embedded in the outgoing node's Phase G and the incoming node's Phase B/C. The D-EXEC-1 7-phase order is unchanged. Preserves D-EXEC-3.

* **No replay-recovery machinery.** A failed boundary precondition stalls the session deterministically. There is no recovery path (D-FORBID-9).

* **No retry semantics.** `_retry_counts` is plumbed but unconsumed in Step 8. Step 9 explicitly **defers** retry semantics further (D-FAULT-8b) — re-attempt in Step 9 is expressed only via explicit recovery nodes (D-FAULT-8). `_retry_counts` remains plumbed-but-unused; retry semantics return only under a dedicated future contract.

* **No async orchestration.** D-FORBID-1, D-FORBID-2. Synchronous, single-process, single-threaded with respect to PhysX, sequential with respect to task execution (D-SCALE-1).

* **No speculative state handling.** D-FORBID-9. Boundary snapshots record what happened; they do not record what might happen.

* **ExecutionSession remains the single orchestration authority.** D-SESS-1. D-CONT-5 strengthens this by moving fixture-occupancy mutation from the subordinate executor up to the session.

* **Replay-authoritative surfaces remain minimal and explicitly enumerated.** D-CONT-1 defines the set. Expansion is a contract revision, not an implementation detail.

### 12.11 Step 8 scope restatement

Step 8 is **not** about orchestration power. The two-node test job is a validation vehicle for the boundary contract, not a feature deliverable.

Step 8 is proving:

> **Deterministic retained-state handoff with contamination-resistant replay-authoritative continuity semantics, under selective authoritative persistence semantics (D-CONT-4) and allowlist-only canonicalization (D-CONT-6).**

The load-bearing assertions are:

1. The `boundary_snapshot(...)` projector is pure, allowlist-only, deterministic (D-CONT-6, D-CONT-6c).
2. The boundary interval is PhysX-quiescent (D-CONT-3).
3. Fixture-occupancy authority lives only in `ExecutionSession.step()` Phase G (D-CONT-5).
4. The forbidden non-authoritative state (D-CONT-2) does not influence snapshot hashes (D-CONT-6 contamination test).
5. The Phase 4A 32/32 regression surface is preserved.

If the two-node exercise passes but the contamination test in (4) fails, Step 8 has not landed.

---

## 13. Deterministic Failure Semantics Contract  *(D-FAULT)*

### 13.0 Scope

This section binds **Step 9 onward** — the first runtime moment at which the deterministic-execution contract acknowledges failure as a first-class participant in orchestration. Up to Step 8, the contract enforced what authority survives a successful boundary handoff. From Step 9 forward, the contract enforces what authority survives an **unsuccessful** transition: failed verdicts, aborted execution, exceeded budgets, broken invariants, and replay-integrity refusals.

Step 9 does not introduce a second orchestration system. It extends the existing single orchestration authority (D-SESS-1) to acknowledge failure deterministically. Every failure is an explicit transition. Every transition is append-only. Every transition is replay-authoritative.

Subsequent implementation steps (10 replay-identity tooling extension, 11 operator channel ingress, 12 conveyor refactor, and any future Phase 4C revision) MUST cite this section for every failure-path assumption they make.

### 13.1 D-FAULT-1 — Orchestration-level failure taxonomy

**D-FAULT-1** — Failure at the orchestration level is **strictly enumerated** as exactly one of the following eight classes:

| class | origin authority | emitted via |
|---|---|---|
| `NODE_EXECUTION_FAILURE` | `UnifiedValidator` inside `TaskExecutor.execute()` | `NodeExecutionCompleted` with `passed=False` and inner `TaskOutcome` |
| `PRECONDITION_FAILURE` | scheduler (D-SCHED-13) | `NodeBlocked` with `status="blocked_by_precondition"` or `"blocked_by_predicate_error"` |
| `AUTHORITY_VIOLATION` | `ExecutionSession` postcondition check at Phase G | `AuthorityViolationDetected` |
| `CONTINUITY_VALIDATION_FAILURE` | `ExecutionSession` boundary-snapshot postcondition at Phase G | `ContinuityValidationFailed` |
| `TIMEOUT_FAILURE` | `ExecutionSession` post-Phase-E tick-budget check (D-FAULT-12) | `NodeTimeoutTripped` |
| `OPERATOR_ABORT` | `OperatorAbortRequested` envelope drained at Phase A | `SessionAborting` / `SessionAborted` |
| `INFRASTRUCTURE_DEGRADATION` | out-of-band detector (launch harness) | sidecar artifact (D-FAULT-13); **NOT** in `events.jsonl` |
| `REPLAY_INTEGRITY_FAILURE` | replay-identity comparator tool | comparator exit code + replay audit artifact (D-FAULT-11); **NOT** in any session's `events.jsonl` |

Expansion of this list is a contract revision, not an implementation detail. A failure mode not in this list is, by D-FAULT-1, not a recognized failure mode.

#### 13.1.1 D-FAULT-1a — Inner sub-classification

**D-FAULT-1a** — The `NODE_EXECUTION_FAILURE` class is sub-classified by `TaskOutcome` (Phase 4A enum, currently 8 non-PASS values). Sub-classification of any other orchestration-level class via `TaskOutcome` is **FORBIDDEN**; `TaskOutcome` is a per-task validator verdict and its mutation authority remains with Phase 4A's `UnifiedValidator`.

*Rationale.* Two-tier taxonomy preserves the Mutation Authority Matrix: orchestration-level classes are session-owned; per-task sub-classification is validator-owned. Conflating the two would breach D-SESS-1.

#### 13.1.2 D-FAULT-1b — Executor-reported interruption sub-classifier  *(Step 10 Direction A)*

**D-FAULT-1b** — `TaskOutcome.EXECUTION_INTERRUPTED` is the **executor-reported, mechanically-neutral** outcome value indicating that `TaskExecutor.execute()` stopped at a deterministic segment boundary in response to a session-supplied interruption predicate (D-EXEC-13). It is a sub-classifier of `NODE_EXECUTION_FAILURE` per D-FAULT-1a; it MUST NOT be promoted to a top-level D-FAULT-1 class, and it MUST NOT be emitted by any authority other than `TaskExecutor.execute()`.

The value is deliberately neutral: it describes only the **mechanical event** ("the executor returned early at a deterministic boundary") and carries no commitment to **why** the executor returned early. The session combines this outcome with its envelope-queue snapshot at `execute()` entry, the resulting `ticks_consumed`, and `tick_budget_ticks` to assign the orchestration-level failure class per D-FAULT-3b. The executor MUST NOT classify the interruption cause; that authority remains with the session per D-FAULT-2.

A `TaskResult` carrying `outcome == EXECUTION_INTERRUPTED` MUST satisfy:

* `ticks_consumed >= 0` and `ticks_consumed` equals the cumulative settled-boundary `world.step()` count (D-FAULT-12c);
* `interrupted_at_segment_index: int` is populated and is the index (0-based) of the segment boundary at which the predicate returned `True`;
* `interrupted_at_segment_name: str` is populated and is the author-declared name of that boundary;
* `passed == False` on the corresponding `NodeExecutionCompleted` event.

`interrupted_at_segment_index` and `interrupted_at_segment_name` are **observational** per D-EXEC-13b and MUST NOT enter the per-task fingerprint (D-FAULT-10). Only `ticks_consumed` and the `EXECUTION_INTERRUPTED` outcome enter the fingerprint.

*Rationale.* Two-layer authority preserves D-FAULT-1a's layering: executor reports a mechanical verdict, session interprets it. Conflating mechanical interruption (an executor concern) with orchestration-level classification (a session concern) would re-introduce the hidden-authority anti-pattern D-FAULT-15 #16 was specifically introduced to prevent. The neutral-surface design keeps the D-FAULT-1 enumeration immutable while admitting a new executor-internal mechanical surface; the eight-class D-FAULT-1 taxonomy does NOT expand.

### 13.2 D-FAULT-2 — Origin authority and emission discipline

**D-FAULT-2** — Each failure class has exactly **one** origin authority (per D-FAULT-1 table). The same class **MUST NOT** be emitted by any authority not listed for it. A would-be second emitter is a contract violation per D-CONT-7a.

*Rationale.* Single-emitter discipline is the failure-path analogue of D-CONT-5's single-mutator discipline. Multiple emitters of the same class allow drift across paths.

### 13.3 D-FAULT-3 — Propagation rules

**D-FAULT-3** — A failure-class emission propagates per the following table:

| emitted class | downstream effect |
|---|---|
| `NODE_EXECUTION_FAILURE` | failed node added to `_failed`; descendants per `FailureAction` (D-FAULT-3a) |
| `PRECONDITION_FAILURE` | node remains pending; no state mutation; descendants stay `blocked_by_parents` |
| `AUTHORITY_VIOLATION` | session → `FAILED` immediately; remaining pending nodes cascade-skipped uniformly; **FailureAction is overridden** |
| `CONTINUITY_VALIDATION_FAILURE` | session → `FAILED` immediately; same as `AUTHORITY_VIOLATION` |
| `TIMEOUT_FAILURE` | failed node added to `_failed`; descendants per `FailureAction` (D-FAULT-3a) |
| `OPERATOR_ABORT` | session → `ABORTING` → `ABORTED`; remaining pending nodes cascade-skipped uniformly; **FailureAction is overridden** |
| `INFRASTRUCTURE_DEGRADATION` | session presumed dead; no further propagation possible in-session |
| `REPLAY_INTEGRITY_FAILURE` | n/a in-session; comparator exits non-zero |

Terminal `SessionState` values introduced by D-FAULT-3 are `ABORTING` (transient, entered at the abort drain), `ABORTED` (terminal, operator-initiated), and `FAILED` (terminal, validator/scheduler/authority-violation/timeout/continuity-validation initiated). `ABORTED` and `FAILED` are byte-distinguishable terminal states; `RECOVERING` is **FORBIDDEN** as a `SessionState` value (D-FAULT-15 #18).

#### 13.3.1 D-FAULT-3a — `FailureAction` enumeration

**D-FAULT-3a** — `FailureAction` is a per-edge enumeration on `TaskGraph`, immutable after `graph.build()`. Permitted values:

| value | meaning |
|---|---|
| `SKIP_NODE` (default) | descendants of failed node cascade-skipped; siblings unaffected |
| `ABORT_COHORT` | descendants AND all fan-out siblings of the failure point cascade-skipped |
| `ABORT_JOB` | session → `FAILED`; all remaining pending nodes cascade-skipped uniformly |

Sibling-tolerant default (D-FAULT-3a `SKIP_NODE`). Sibling-strict requires explicit `ABORT_COHORT` declaration per-edge. Live mutation of `FailureAction` after `graph.build()` is **FORBIDDEN** (D-SCHED-8 frozen-graph invariant).

#### 13.3.2 D-FAULT-3b — Session classification of `EXECUTION_INTERRUPTED`  *(Step 10 Direction A)*

**D-FAULT-3b** — When `TaskExecutor.execute()` returns a `TaskResult` with `outcome == TaskOutcome.EXECUTION_INTERRUPTED` (D-FAULT-1b), the session MUST classify the orchestration-level failure class at **end of Phase E**, **before** Phase F/G, as a **pure function** of the following authoritative inputs:

* `envelope_snapshot_at_execute_entry`: the tuple of `OperatorEnvelope` instances pending at `execute()` invocation entry (canonical-ordered per D-FAULT-9);
* `base_tick`: the session's `_orchestration_tick` at `execute()` invocation entry (D-EXEC-12 metadata);
* `result.ticks_consumed`: the executor-reported settled-boundary `world.step()` count (D-FAULT-12c);
* `task.tick_budget_ticks`: the per-task tick budget (D-FAULT-12).

Classification proceeds by evaluating the following rows **in declared order**; the first matching row applies and is the assigned orchestration-level class:

| # | condition | orchestration-level class | propagation |
|---|---|---|---|
| 1 | an `OperatorEnvelope` with `kind == "abort"` and `requested_at_tick ≤ base_tick + result.ticks_consumed` exists in `envelope_snapshot_at_execute_entry` | `OPERATOR_ABORT` | per D-FAULT-3 row 6 (session → `ABORTING` → `ABORTED`; cascade-skip uniformly) |
| 2 | `result.ticks_consumed > task.tick_budget_ticks` | `TIMEOUT_FAILURE` | per D-FAULT-3 row 5 (failed node added to `_failed`; descendants per `FailureAction`) |
| 3 | otherwise | `NODE_EXECUTION_FAILURE` (interpreted: "predicate-driven stop with no recognized cause") | per D-FAULT-3 row 1 |

The classification is **declared, not best-fit**: the first matching row applies. The ordering encodes architectural priority — operator intent (envelope) outranks budget exhaustion outranks unattributed mechanical interruption. Multi-cause interruptions (envelope eligible **and** budget exceeded at the same boundary) deterministically resolve to row 1 (`OPERATOR_ABORT`); no soft-handling, no implicit composition, no joint classification.

The session MUST:

* perform the classification as a pure function of the four inputs above; consultation of wall-clock sources, PhysX state, observational projections, or session-side mutable state during classification is **FORBIDDEN**;
* emit the corresponding ingress event(s) at the classification site as part of post-Phase-E handling:
  * for row 1 — `OperatorAbortRequested` (deferred from Phase A drain since the envelope was retained as eligible-but-undrained at execute-entry), followed by `SessionAborting`;
  * for row 2 — `NodeTimeoutTripped`;
  * for row 3 — no additional ingress event; `NodeExecutionCompleted` with `passed=False` and `outcome=EXECUTION_INTERRUPTED` is the sole transition record;
* propagate per the matching row in D-FAULT-3 (cascade, abort, or fail);
* skip Phase G occupancy commit (`outcome != PASS`, D-CONT-5 unchanged);
* leave retained state (D-LIFE, fixture occupancy, canonical pose) at its last-tick truth per D-FAULT-5 / D-FAULT-5b — the contradiction is preserved verbatim until an explicit recovery node (D-FAULT-8) resolves it.

Row 3 (`NODE_EXECUTION_FAILURE` from an unattributed interruption) SHOULD be rare in practice: it indicates the predicate returned `True` despite no eligible envelope and no budget violation, which is consistent with a contract-violation in predicate construction. A pure-Python contract test (Step 10 Phase 3) asserts that legitimate predicate constructions cannot reach row 3.

*Rationale.* `EXECUTION_INTERRUPTED` is mechanically neutral (D-FAULT-1b). Classification must be deterministic, single-authority, and pure-function over authoritative inputs; an ordered, declared rule preserves replay-authority. Multi-cause resolution is by declared priority rather than evidence-weighing; evidence-weighing would re-introduce the "soft failure" anti-pattern D-FAULT-15 #3 forbids. The classification is a session-side analogue of D-FAULT-2's single-emitter discipline: one authority, one rule, one classification per `EXECUTION_INTERRUPTED` return.

### 13.4 D-FAULT-4 — `TaskCascadeSkipped` distinct from `NodeFailed`

**D-FAULT-4** — A node whose pending state is resolved by **cascade** (descendant of a `failed` node, or skipped under `ABORT_COHORT` / `ABORT_JOB`) **MUST** be recorded via a distinct `TaskCascadeSkipped` event, **never** via `NodeFailed`. The `_skipped` set is distinct from the `_failed` set in `SessionRuntimeSnapshot`.

*Rationale.* An operator inspecting the trace must distinguish nodes that genuinely failed (their executor ran and produced a non-PASS verdict) from nodes that were skipped (their executor never ran). Conflating them obscures forensic provenance.

#### 13.4.1 D-FAULT-4a — `_skipped` enters authoritative continuity

**D-FAULT-4a** — The `_skipped: frozenset[str]` set is added to the authoritative continuity enumeration defined by D-CONT-1. The boundary snapshot schema is extended (D-CONT-6) to include `_skipped` alongside `_completed`, `_failed`, `_retry_counts`. `BOUNDARY_SNAPSHOT_SCHEMA_VERSION` increments from 1 to 2 at Step 9 Phase 4 (runtime wiring) landing. Mismatched-version replays are refused per D-CONT-6b.

*Rationale.* `_skipped` participates in continuity (recovery preconditions consult it). It is therefore authoritative per D-CONT-1's definition and MUST appear in the boundary snapshot.

### 13.5 D-FAULT-5 — Retained-state mutation on failure

**D-FAULT-5** — Retained-state mutation on failure is **FORBIDDEN** except as explicitly enumerated by D-CONT-5 (occupancy mutation on PASS). Specifically:

* implicit rollback of canonical object pose: **FORBIDDEN**;
* implicit clearing of fixture occupancy on failed pick: **FORBIDDEN**;
* implicit release of D-LIFE `attached` state on failed transport: **FORBIDDEN**;
* implicit reset of any `NodeRuntimeState` field outside the session's documented transition table: **FORBIDDEN**.

The post-failure boundary snapshot **MUST** reflect the last-tick truth of all authoritative fields. Recovery topology resolves contradictions explicitly.

```python
# FORBIDDEN — implicit rollback to "clean" the snapshot.
if task_result.outcome != TaskOutcome.PASS:
    registry.update_object_pose(peg, pre_failure_pose)   # LIE
    registry.mark_fixture_empty(fixture_a)                # WRONG AUTHORITY
```

```python
# REQUIRED — failure preserves last-tick truth.
if task_result.outcome != TaskOutcome.PASS:
    # No mutation. The session records `_failed.add(node_id)` and emits
    # NodeExecutionCompleted with passed=False. Post-G snapshot serializes
    # the actual canonical pose, the actual fixture occupancy.
    pass
```

#### 13.5.1 D-FAULT-5a — Pose-on-FAIL semantic

**D-FAULT-5a** — The canonical object pose at the post-failure boundary is the **last-tick `update_object_pose` write** the failing node made (D-CONT-1 definition, unchanged). Frozen-pre-failure semantics (snapshot lies about reality) are **FORBIDDEN**. Dual-snapshot semantics (two truths in one snapshot) are **FORBIDDEN**.

#### 13.5.2 D-FAULT-5b — Fixture occupancy on FAIL

**D-FAULT-5b** — Fixture occupancy is **NOT** mutated on failure (D-CONT-5 already requires PASS for mutation). A failed pick from an occupied fixture leaves occupancy unchanged; a failed place at an empty fixture leaves occupancy unchanged. The resulting contradiction between occupancy and canonical pose is **REQUIRED** to be preserved verbatim in the post-failure boundary snapshot.

*Rationale.* Contradictions are forensic truth. The architectural rule forbids silent healing. Recovery nodes (declared in graph topology) resolve contradictions explicitly via subsequent transitions.

### 13.6 D-FAULT-6 — Abort/cancellation boundary phase

**D-FAULT-6** — Operator abort enters orchestration **only at Phase A** of an orchestration tick. The `OperatorAbortRequested` envelope is drained at Phase A; if accepted, the session transitions `RUNNING` → `ABORTING` before any Phase B scheduling. Abort ingress at any other phase is **FORBIDDEN**.

Specifically:

* mid-Phase-E (mid-`execute()`) interrupt is **FORBIDDEN**;
* between-`world.step()` interrupt inside Phase E is **FORBIDDEN**;
* method-as-ingress (e.g. `ExecutionSession.request_abort()`) is **FORBIDDEN**;
* multiple ingress paths for the same abort are **FORBIDDEN**.

#### 13.6.1 D-FAULT-6a — Phase E atomicity

**D-FAULT-6a** — Phase E is **atomic** from the orchestration perspective. The executor runs its declared trajectory to completion (or to executor-internal exception). The session does not interrupt mid-step on budget exhaustion, abort request, or any other condition. Mid-step interrupt would break D-EXEC-2 (no event out of phase) and D-CONT-3 (boundary quiescence).

#### 13.6.2 D-FAULT-6b — N-Interior-Phase-E Ingress Cannot Acquire In-Tick Authority

**D-FAULT-6b** — Within a single orchestration tick `K_N` executing node `N`'s Phase D–E, an `OperatorEnvelope` whose channel-arrival wall-clock instant lies strictly inside (start of `N`'s Phase D execute-entry, end of `N`'s Phase E) MUST NOT influence `N`'s interruption predicate, MUST NOT be drained mid-Phase-E, and MUST NOT terminate `N`'s `execute()` via any orchestration-observable mechanism. The earliest `orchestration_tick` at which such an envelope MAY acquire orchestration authority is `K_N + 1` (Phase A of the next `session.step`).

**Citations.**
* Anchor: D-FAULT-6, D-EXEC-13a, D-EXEC-13c, D-FAULT-15 row 27
* Reference: D-FAULT-15 row 5

*Note.* This clause asserts framework Theorem T2 (N2-only-Interruption Impossibility) per `docs/phase_4b_step11_admissibility_framework.md` §B.2. The embedded T1 explanation (Tick Non-Commensurability) is a separate C-2 note authored in Wave 6; it provides the wall-clock-to-orchestration-tick non-commensurability reasoning that underlies this clause's "earliest authority = `K_N + 1`" assertion. T2 is normative-strengthening (making implicit D-FAULT-6 + D-EXEC-13a + D-EXEC-13c + D-FAULT-15 row 27 discipline explicit), not normative-additive.

#### 13.6.3 D-FAULT-6c — Phase-A-Only Ingress Observability

**D-FAULT-6c** — Within a single `session.step(K)` invocation, the session's only observation surface for ingress events is **Phase A**. Sub-Phase pulled observation at Phases B, C, D, E, F, or G, and `pull-at-end-of-Phase-G` observation, are **FORBIDDEN**. Every ingress observation MUST correspond to exactly one (`session_id`, `orchestration_tick`) pair, with `orchestration_tick` value equal to `K` (the value the tick holds throughout the entire `session.step(K)` call).

**Citations.**
* Anchor: D-EXEC-1, D-EXEC-2, D-FAULT-6

*Note.* This clause asserts framework Theorem T3 (Phase-A-Only Ingress Observability) per `docs/phase_4b_step11_admissibility_framework.md` §B.3. The framework's derivation hypotheses are D-EXEC-1 (7-phase order; no sub-phases), D-EXEC-2 (events out of phase forbidden), D-EXEC-13a (Phase E atomic), and D-FAULT-15 row 27 (mid-execute envelope drain forbidden); framework Theorem T1 (Tick Non-Commensurability) provides the wall-clock-to-orchestration-tick non-commensurability reasoning that underlies "`orchestration_tick` value at observation = `K`". T3 is normative-strengthening (making implicit D-EXEC-1 + D-EXEC-2 + D-FAULT-6 + D-EXEC-13a + D-FAULT-15 row 27 discipline explicit), not normative-additive — it forecloses the post-Phase-A pull, pre-Phase-E pull, and pre-Phase-G pull design temptations.

### 13.7 D-FAULT-7 — Idempotent cancellation

**D-FAULT-7** — Cancellation is idempotent at the **transition**, not the envelope:

* a node cascade-skipped twice (e.g. two failed parents) **MUST** emit exactly one `TaskCascadeSkipped` event;
* an `OperatorAbortRequested` envelope arriving while the session is already in `ABORTING` or `ABORTED` **MUST** be recorded in the trace (as an envelope ingress event) but **MUST NOT** trigger a second state transition;
* a `NodeBlocked` event for a given node fires at most once per blocking-episode, where an episode begins when the node transitions to blocked and ends when it un-blocks (parent completes, predicate succeeds) or transitions to terminal.

The session **MUST** maintain per-node idempotency tracking in `NodeRuntimeState`:

* `_cascade_emitted: bool` (set on `TaskCascadeSkipped` emission);
* `_blocked_emission_key: str | None` (set on `NodeBlocked` emission; cleared on un-block).

These fields are authoritative (D-FAULT-4a extends D-CONT-1 to include them via `_node_runtime`).

### 13.8 D-FAULT-8 — Recovery as explicit graph topology

**D-FAULT-8** — Recovery from any failure class is **exclusively** expressed as graph topology: a `TaskNode` whose `metadata["recovery_of"] == "<failed_node_id>"`, reachable via a graph edge from the failure point. Implicit recovery — any runtime code path that re-attempts work without an explicit graph node — is **FORBIDDEN**.

A recovery node:

* is a normal `TaskNode` from the scheduler's perspective (D-SCHED-2/-3 canonical-order applies);
* carries `metadata["recovery_of"]: str | None` (None for non-recovery nodes);
* on entry, emits a `RecoveryNodeEntered` event whose payload includes `recovers_from_node_id` and `recovers_from_outcome` (extracted from the failed node's `TaskResult`).

#### 13.8.1 D-FAULT-8a — Topology-derived recovery inference forbidden

**D-FAULT-8a** — Inferring "recovery node" status from graph topology alone (e.g. "any node downstream of a failure-edge is a recovery node") is **FORBIDDEN**. The `metadata["recovery_of"]` field is the **only** authoritative source. Topology-derived inference is a hidden authority.

#### 13.8.2 D-FAULT-8b — No retry in Step 9

**D-FAULT-8b** — Retry of the same `TaskNode` (re-execution of the same `task_ref` with the same node_id) is **FORBIDDEN** in Step 9. The `retry_counts` parameter on `TopologicalSequentialScheduler.next_runnable_node(...)` remains plumbed-but-unused (Step 5 forward-compat). Re-attempt is expressed via a distinct recovery node (different `node_id`).

*Rationale.* Retry semantics are the largest source of implicit orchestration in industrial systems. Step 9 prefers graph-explicit recovery; retry returns under a dedicated future contract.

### 13.9 D-FAULT-9 — Operator envelope schema

**D-FAULT-9** — Operator commands enter orchestration via `OperatorEnvelope`, a frozen dataclass with the following schema (canonical-JSON serializable, stable across versions):

```python
@dataclass(frozen=True, slots=True)
class OperatorEnvelope:
    kind:               str          # "abort" (Step 9); Step 11 adds "pause"|"resume"|"manual_advance"
    requested_at_tick:  int          # earliest orchestration_tick at which Phase A drains this envelope
    reason:             str          # short, operator-supplied; participates in fingerprint
    envelope_id:        str          # deterministic UUID-equivalent (e.g. blake2b digest of (kind, tick, reason, sequence_within_pending))
```

Envelopes are passed to `ExecutionSession.__init__` via `pending_operator_envelopes: tuple[OperatorEnvelope, ...]`. The tuple is sorted by `(requested_at_tick, envelope_id)` for canonical ordering. Live-channel ingress (Step 11) **MUST** preserve this schema and the canonical-ordering discipline.

#### 13.9.1 D-FAULT-9a — Step 9 supports only `kind="abort"`

**D-FAULT-9a** — In Step 9, the only permitted `OperatorEnvelope.kind` value is `"abort"`. Other kinds (`pause`, `resume`, `manual_advance`) are reserved for Step 11; an envelope with an unrecognized kind **MUST** be rejected at session construction with `ExecutionSessionError`.

#### 13.9.2 D-FAULT-9b — PAUSED Constitutional Admissibility

**D-FAULT-9b** — A `SessionState` value `PAUSED` is constitutionally admissible IF AND ONLY IF all five of the following properties hold conjunctively:

1. **Phase-A-governed transitions.** Both transitions into and out of `PAUSED` (`RUNNING` → `PAUSED` via `pause` envelope; `PAUSED` → `RUNNING` via `resume` envelope; `PAUSED` → `ABORTING` via `abort` envelope) **MUST** occur exclusively at Phase A drain. No other phase, and no other authority, **MAY** transition into or out of `PAUSED`.
2. **Phase B–G structural skip.** During `PAUSED`, each `session.step()` invocation runs Phase A normally and structurally **MUST** skip Phases B through G. No scheduler call, no predicate construction, no executor invocation, no boundary snapshot, no registry mutation, and no Phase G commit **MAY** occur.
3. **`orchestration_tick` continuity.** `_orchestration_tick` **MUST** advance by exactly 1 at the end of every `session.step()` invocation regardless of `session_state`, including during `PAUSED`. `PAUSED` **MUST NOT** freeze, gate, or otherwise interfere with tick advancement.
4. **No wall-clock observation.** The substrate **MUST** make zero wall-clock observations during `PAUSED`. The wall-clock duration of any `PAUSED` interval **MUST** be determined entirely by the caller's cadence in invoking `session.step()` (per D-INGRESS-9).
5. **Single-emitter discipline preserved.** Only `ExecutionSession.step()`, processing a drained envelope at Phase A, **MAY** transition into or out of `PAUSED`. No method-as-ingress, no callback, no timer, and no second-emitter pathway **MAY** introduce or remove `PAUSED`.

Admittance of `PAUSED` without ALL of properties 1–5 holding conjunctively is **FORBIDDEN**.

**Citations.**
* Anchor: D-FAULT-6c, D-INGRESS-9, D-FAULT-6a, D-FAULT-2, D-FAULT-9
* Reference: D-FAULT-15 row 18, D-FAULT-7

*Note.* This clause asserts framework Theorem T6 (PAUSED Constitutional Admissibility) per `docs/phase_4b_step11_f58_paused_analysis.md` §M.1. T6's five conjunctive properties jointly close framework Threat 7 (PAUSED-as-wall-clock-wait) per F58 §O. The clause depends on existing-clause anchors: D-FAULT-6c (Phase-A-only ingress observation surface, Wave 1) bounds the property 1 transition surface; D-INGRESS-9 (Caller-Driven PAUSED Cadence, Wave 2) provides the property 4 caller-cadence discipline (D-INGRESS-9 itself becomes binding upon this clause's admission of `PAUSED`); D-FAULT-6a (Phase E atomicity) is preserved by property 2's structural skip; D-FAULT-2 (single-origin authority) is preserved by property 5's single-emitter discipline; D-FAULT-9 (envelope schema) provides the `pause` / `resume` envelope kinds enumerated in property 1. D-FAULT-9b is normative-strengthening (making explicit the conjunctive five-property admissibility surface that the cited anchors jointly imply); it is not normative-additive — it introduces no new authority surface, no new wall-clock observation pathway, no autonomous progression mechanism, no scheduler-state widening, and no replay-nondeterminism. The reference to D-FAULT-15 row 18 (`RECOVERING` as a `SessionState` value FORBIDDEN) provides the SessionState-additions discipline context; D-FAULT-7 (idempotent cancellation) provides the existing transition-not-envelope idempotency context that T6's property 1 inherits for the `pause` / `resume` / `abort` transition idempotency surface.

#### 13.9.3 D-FAULT-9c — Override Admissibility Boundary

**D-FAULT-9c** — No `OperatorEnvelope.kind` value **MAY** admit an effect outside the orchestration-decision whitelist of (`session_state` transition at Phase A drain) plus (forensic event recording in `events.jsonl`). Any envelope-kind semantic that would acquire decision-making authority beyond this two-element whitelist — including but not limited to: scheduler input extension beyond D-SCHED-14's closed input sets; predicate input extension beyond D-SCHED-12's closure; executor predicate-closure extension beyond D-EXEC-13c's session-constructed-only discipline; registry mutation outside D-SESS-6's enumerated entry points; direct runtime mutation; autonomous progression; wall-clock advancement; method-as-ingress (per D-FAULT-15 row 16) — is **FORBIDDEN**.

**Override statement.** D-FAULT-9c overrides D-FAULT-9a's reservation of `manual_advance` (along with `pause` and `resume`) for Step 11. D-FAULT-9a's reservation language is preserved verbatim for historical citation continuity; this clause supersedes the `manual_advance`-specific portion of that reservation by establishing the general T7 override boundary that forecloses the entire class of orchestration-decision-authority-widening envelope semantics. As a bounded example of the general foreclosure, `manual_advance` is constitutionally INADMISSIBLE: no semantic for `manual_advance` distinct from existing envelope kinds (`abort`, `pause`, `resume`) exists under the substrate's authority-singularity discipline; the reserved name has empty admissible content. The reservation of `pause` and `resume` is separately admitted via D-FAULT-9b's PAUSED Constitutional Admissibility.

**Citations.**
* Anchor: D-SCHED-14, D-FAULT-2, D-FAULT-9a, D-FAULT-9, D-FAULT-9b
* Reference: D-FAULT-15 row 16, D-SCHED-1, D-SCHED-12, D-EXEC-13c, D-SESS-6

*Note.* This clause asserts framework Theorem T7 (Manual-Advance Constitutional Incompatibility, reformulated here as the general Override Admissibility Boundary) per `docs/phase_4b_step11_f59_manual_advance_analysis.md` §5.1. T7's foreclosure surface is the general envelope-kind-effect boundary: no envelope kind admits an effect outside Lemma 2.2's whitelist (`session_state` transition + forensic event) without violating at least one of D-SCHED-1, D-SCHED-12, D-SESS-6, D-EXEC-13c, D-CONT-5a, D-FAULT-2, D-FAULT-6a, D-FAULT-8, D-FAULT-14, D-FAULT-15 rows #2/#5/#8/#15/#16/#27/#29, T1, T2, T3, or D6. D-FAULT-9c restates T7 as a normative contract clause with the general-boundary-first / `manual_advance`-as-bounded-example structure per extraction plan §6.A row 4 mitigation guidance. The anchor citations bound D-FAULT-9c's normative scope: D-SCHED-14 (input whitelist closure) is the dominant constitutional surface T7 protects; D-FAULT-2 (single-origin authority) is the underlying authority-singularity discipline; D-FAULT-9a (existing reserved-kind language) is the text this clause overrides via additive supersession; D-FAULT-9 (envelope schema) bounds the namespace within which T7 operates; D-FAULT-9b (PAUSED admissibility, Wave 3 AAU 1) is the sibling clause that admits `pause` and `resume` — the only envelope-kind expansions T7 does NOT forbid. D-FAULT-9c is normative-strengthening (making explicit the general envelope-kind-effect boundary that the cited anchors jointly imply); it is not normative-additive — it introduces no new authority surface, no autonomous progression mechanism, no scheduler-state widening beyond D-SCHED-14, no replay-nondeterminism, no implicit control-flow pathway. The reference to D-FAULT-15 row 16 (method-as-ingress anti-pattern) provides the existing method-as-ingress foreclosure context; D-SCHED-1 + D-SCHED-12 + D-EXEC-13c + D-SESS-6 are the four constitutional surfaces whose collective closure (formalized by D-SCHED-14) D-FAULT-9c protects from envelope-kind widening. Future envelope-kind proposals must demonstrate non-entry into the whitelist; per F59 §5.2, D-FAULT-9a's reservation of `manual_advance` is recommended for Option A (drop) in any future hygiene wave, but Step 12 preserves D-FAULT-9a's reservation language verbatim per additive-only discipline.

### 13.10 D-FAULT-10 — Failure-event canonical-JSON fingerprinting

**D-FAULT-10** — Every failure-related event (`NodeExecutionCompleted` with `passed=False`, `NodeBlocked`, `TaskCascadeSkipped`, `NodeTimeoutTripped`, `AuthorityViolationDetected`, `ContinuityValidationFailed`, `OperatorAbortRequested`, `SessionAborting`, `SessionAborted`, `SessionFailed`, `RecoveryNodeEntered`) **MUST** be canonical-JSON serialized via `canonical_dumps` (D-TRACE-8). Float fields in failure payloads (e.g. evidence in `TaskOutcome` sub-classification) **MUST** originate from a deterministic PhysX read or deterministic arithmetic on PhysX reads; computed intermediates that introduce float-repr instability are **FORBIDDEN**.

### 13.11 D-FAULT-11 — Replay-integrity failure handling

**D-FAULT-11** — `REPLAY_INTEGRITY_FAILURE` is a **meta-failure** detected by the replay-identity comparator tool (`tools/check_session_replay_identity.py`). It is **NOT** an in-session event:

* it **MUST NOT** be appended to any session's `events.jsonl`;
* it is recorded only via the comparator's exit code (non-zero) and an audit artifact at a comparator-defined location (e.g. `replay_audit/<timestamp>_<pkg_a>_vs_<pkg_b>.json`);
* a session that subsequently fails replay does NOT become retroactively `FAILED` — its own `events.jsonl` remains unchanged.

#### 13.11.1 D-FAULT-11a — Replay-tolerance creep forbidden

**D-FAULT-11a** — The comparator **MUST** apply strict byte-equality (no numerical tolerance, no field-level fuzziness, no "approximately equal" replay). A future PR introducing replay tolerance is rejected at review under this clause and D-REPLAY-1.

### 13.12 D-FAULT-12 — Tick-budget enforcement

**D-FAULT-12** — Task-level timeout is enforced as a **tick budget**, never as wall-clock time:

* every `TaskDefinition` declares `tick_budget_ticks: int`;
* the executor reports `ticks_consumed: int` in `TaskResult`;
* the session evaluates `ticks_consumed > tick_budget_ticks` post-Phase-E and, if true, sets `TIMEOUT_FAILURE`;
* the budget enforcement happens at the per-`world.step()` count granularity, post-execution, not at sub-phase granularity.

Wall-clock based timeout is **FORBIDDEN**. Watchdog threads are **FORBIDDEN**. Asynchronous timeout mutation is **FORBIDDEN**.

#### 13.12.1 D-FAULT-12a — Phase E atomicity preserved on timeout

**D-FAULT-12a** — Timeout detection is **post-Phase-E**. The session evaluates `ticks_consumed > tick_budget_ticks` **after** `execute()` returns, regardless of whether the executor ran to trajectory completion or returned early via D-EXEC-13 sub-Phase-E interruption. Mid-Phase-E **orchestration-observable** budget interrupt — the session interrupting the executor mid-`execute()`, the session polling the executor for budget violation during `execute()`, or any wall-clock-driven session-side watchdog — is **FORBIDDEN** (D-FAULT-6a, D-EXEC-13a).

Sub-Phase-E budget-aware predicate consultation per D-EXEC-13 is permitted and is **not** a violation of this clause: it is executor-internal, the session observes only the post-Phase-E `TaskResult`, and `ticks_consumed > tick_budget_ticks` is detected at the same post-Phase-E classification site (D-FAULT-3b row 2) regardless of whether `execute()` returned early or ran to completion.

#### 13.12.2 D-FAULT-12b — Margin requirement

**D-FAULT-12b** — Trajectory authoring **MUST** produce `tick_budget_ticks` values with a documented margin over the trajectory's declared tick length. A pure-Python test asserts `tick_budget_ticks >= trajectory_length_ticks + MARGIN_TICKS` for every registered task. Tight budgets that exceed-by-one in one run and finish-by-one in another are a divergence vector.

#### 13.12.3 D-FAULT-12c — `ticks_consumed` ontology  *(Step 10 Direction A)*

**D-FAULT-12c** — `ticks_consumed: int` on `TaskResult` is REQUIRED to be a **non-negative integer count** of deterministic `world.step()` invocations that the executor performed during the most recent `execute()` call. The field is **wall-clock-independent by construction** and is produced by counting step invocations at their site.

Specifically:

* `ticks_consumed == 0` iff zero `world.step()` invocations were issued during the call (boundary-0 interrupt per D-EXEC-13, or empty trajectory);
* for a `TaskResult` whose `outcome` is **not** `EXECUTION_INTERRUPTED` and whose underlying trajectory ran to completion: `ticks_consumed == sum_of_segment_tick_lengths` for the executed trajectory;
* for a `TaskResult` whose `outcome == EXECUTION_INTERRUPTED`: `ticks_consumed == sum_of_segment_tick_lengths` for the segments that completed strictly before the boundary at which the predicate returned `True` (cumulative settled-boundary count; the interrupted segment contributes zero, because by D-EXEC-13 the predicate is consulted **at** boundaries, not during segment execution).

`ticks_consumed` is **authoritative-evidence** per D-CONT-1 family and enters:

* `TaskResult` (Phase 4A field, populated per this clause from Step 10 Phase 4 forward);
* `task_result_fingerprint` (D-FAULT-10 canonical-JSON, `sort_keys=True`, stable across Python versions);
* `NodeExecutionCompleted` event payload (via the fingerprint);
* therefore the replay-identity byte-equality surface enforced by `tools/check_session_replay_identity.py` (D-FAULT-11a).

Two replays of identical inputs MUST produce **bit-identical** `ticks_consumed` values. Divergence is a `REPLAY_INTEGRITY_FAILURE` per D-FAULT-11; the comparator surfaces it as a byte-level diff in `events.jsonl` without any new comparator-tool change.

The following derivations of `ticks_consumed` are **FORBIDDEN**:

* derivation from `time.time()`, `time.monotonic()`, `time.perf_counter()`, `datetime.now()`, or any duration-based wall-clock source;
* derivation from a rate × duration calculation;
* rounding or approximation ("≈ N ticks") under D-FAULT-11a;
* derivation from PhysX-internal simulation-time queries (these are D-CONT-2 forbidden inputs as continuity authority);
* substitution of `trajectory.declared_length_ticks` for actual settled-boundary count (the field is a counter, not a specification).

`interrupted_at_segment_index` and `interrupted_at_segment_name` (D-FAULT-1b, D-EXEC-13b) are **observational** projections derivable from `ticks_consumed` plus the trajectory's static segment-tick map; they MUST NOT enter the fingerprint and MUST NOT be re-derived as inputs to `ticks_consumed`.

*Rationale.* `ticks_consumed` is the load-bearing input to D-FAULT-3b's classification rule and the load-bearing field for D-FAULT-12 budget enforcement. It must be wall-clock-independent and bit-exact, or the entire interruption surface loses replay-authority. D-FAULT-12c closes the gap left by the Phase 4A executor (which today does not populate the field); Step 10 Phase 4 lands the runtime population, Step 10 Phase 7 the comparator-level confirmation.

### 13.13 D-FAULT-13 — Infrastructure-degradation provenance

**D-FAULT-13** — `INFRASTRUCTURE_DEGRADATION` is detected out-of-band (Kit subprocess exit, PhysX exception, simulation_app death). The session **MUST NOT** emit an infrastructure-degradation event (the session is dead by hypothesis). The launch harness **MUST** write a sidecar artifact at `<session_package>/infrastructure_degradation.json` with the schema:

```json
{
  "schema_version": 1,
  "detected_by": "launch_harness",
  "detected_at_wall_ns": <int>,
  "last_seen_seq": <int|null>,
  "exit_signal": <str|null>,
  "exit_code": <int|null>,
  "reason": "<short str>"
}
```

`detected_at_wall_ns` is the **only** legitimate wall-clock use in the entire system (the deterministic clock has stopped). The replay-identity comparator **MUST** treat sidecar presence as **REPLAY-INVALID** (a distinct verdict from "divergent" — explicitly unreplayable).

### 13.14 D-FAULT-14 — No implicit secondary orchestration system

**D-FAULT-14** — Failure handling **MUST NOT** become an implicit secondary orchestration system. Specifically:

* every failure transition is one append to `events.jsonl`;
* every state mutation on failure is justified by exactly one D-FAULT clause;
* recovery is graph topology, never runtime behaviour (D-FAULT-8);
* abort is envelope-driven, never method-driven (D-FAULT-9);
* timeout is tick-budgeted, never wall-clock (D-FAULT-12);
* infrastructure degradation is sidecar, never session-emitted (D-FAULT-13).

A code path that "cleans up" on failure without an emitted event is a contract violation under this clause.

### 13.15 D-FAULT-15 — Forbidden anti-patterns (failure-path scope)

**D-FAULT-15** — In addition to D-FORBID-1..-14, the following patterns are **FORBIDDEN** in any code that participates in failure handling:

| # | forbidden pattern | cites |
|---|---|---|
| 1 | implicit rollback of retained state on failure | D-FAULT-5 |
| 2 | implicit retry without an explicit recovery node | D-FAULT-8, D-FAULT-8b |
| 3 | "transient failure" or "soft failure" suppression | D-FAULT-13 (no warnings) |
| 4 | "approximately equal" replay tolerance for failure traces | D-FAULT-11a |
| 5 | **orchestration-observable** mid-Phase-E interrupt (abort, timeout, anything) — session-side interruption of the executor during `execute()`, session-side polling of executor state during `execute()`, or any session-observable mid-execute event | D-FAULT-6, D-FAULT-6a, D-EXEC-13a |
| 6 | operator intervention bypassing the OperatorEnvelope schema | D-FAULT-9 |
| 7 | failure-driven cleanup of D-LIFE state outside Phase G | D-FAULT-5, D-CONT-5a |
| 8 | "recovery completed silently" without a `RecoveryNodeEntered` event | D-FAULT-8 |
| 9 | cascade-skip emission iterating an unordered set | D-FAULT-4, D-SCHED-3 |
| 10 | wall-clock timeout budget (per-tick or per-step) | D-FAULT-12, D-FAULT-12c |
| 11 | failure trace mutation of a prior event | D-TRACE-2 (Step 9 explicitly cites) |
| 12 | cross-session retained-state continuity for recovery | D-FORBID, D-FAULT-8 |
| 13 | live-mutating `FailureAction` after `graph.build()` | D-FAULT-3a, D-SCHED-8 |
| 14 | severity tiers ("warning", "minor failure", etc.) | D-FAULT-13 |
| 15 | topology-derived recovery inference | D-FAULT-8a |
| 16 | `ExecutionSession.request_abort()` or any method-as-ingress | D-FAULT-6, D-FAULT-9 |
| 17 | inserting infrastructure-degradation events into `events.jsonl` | D-FAULT-13 |
| 18 | `RECOVERING` as a `SessionState` value | D-FAULT-3 |
| 19 | promoting `TaskOutcome.EXECUTION_INTERRUPTED` to a top-level D-FAULT-1 class | D-FAULT-1, D-FAULT-1b |
| 20 | interruption predicate constructed outside `ExecutionSession` (in the executor, in trajectory authors, in external callers) | D-EXEC-13c, D-FAULT-2 |
| 21 | interruption predicate consultation at a non-segment-boundary point (mid-step, mid-PhysX-command, between physics ticks of the same segment) | D-EXEC-13 condition 4 |
| 22 | interruption predicate with side-effects, I/O, logging, mutation of captured state, wall-clock reads, random reads, or closure over PhysX state | D-EXEC-13, D-CONT-2 |
| 23 | speculative interruption — continuing `execute()` past a predicate `True` return at a legal boundary | D-EXEC-13d |
| 24 | wall-clock-derived `ticks_consumed` (any duration-based derivation, any rate × time calculation, any rounding) | D-FAULT-12c |
| 25 | promotion of `interrupted_at_segment_*` forensic fields into the per-task fingerprint | D-EXEC-13b, D-FAULT-10 |
| 26 | executor-side classification of interruption cause (executor inferring "this is an OPERATOR_ABORT" vs "this is a TIMEOUT_FAILURE" and reporting different outcomes) | D-FAULT-1b, D-FAULT-3b |
| 27 | session-side mid-`execute()` envelope drain (Phase A drain interleaved with Phase E) | D-FAULT-6, D-EXEC-13a |
| 28 | async cancellation channel, signal handler, thread-based interrupt, or any non-synchronous interruption mechanism into the executor | D-EXEC-13, §1.6 non-goals |
| 29 | adaptive interruption (predicate mutating mid-`execute()`, predicate substitution, predicate composition by the executor) | D-EXEC-13c |
| 30 | live-channel interruption ingress during `execute()` (envelopes arriving mid-execute and influencing the predicate) | D-EXEC-13 (closure captured at execute-entry only) — Step 11 territory |
| 31 | live-channel callback registration (any API by which the channel notifies the session of envelope arrival outside Phase A pull) | D-FAULT-15 #16, D-FORBID-1 |
| 32 | sub-tick channel pull (pulls at Phase B/C/D/E/F/G) | D-EXEC-1, D-EXEC-2 |

### 13.16 Step 9 scope restatement

Step 9 is **not** about failure tolerance. The deliberately-failing 2-node test job is a validation vehicle for the failure-semantics contract, not a feature deliverable.

Step 9 is proving:

> **Deterministic failure semantics with contamination-resistant replay-authoritative failure traces, under explicit graph-topology recovery (D-FAULT-8), tick-budget timeout enforcement (D-FAULT-12), envelope-as-event abort ingress (D-FAULT-9), and contradiction-preserving retained-state posture (D-FAULT-5).**

The load-bearing assertions are:

1. Every failure class in D-FAULT-1 has exactly one origin authority (D-FAULT-2).
2. Failure transitions never mutate retained state beyond what D-CONT-5 permits on PASS (D-FAULT-5, D-FAULT-5a, D-FAULT-5b).
3. Abort enters only at Phase A; Phase E is atomic (D-FAULT-6, D-FAULT-6a, D-FAULT-12a).
4. Cancellation is idempotent at the transition (D-FAULT-7).
5. Recovery is graph topology, never runtime behaviour (D-FAULT-8, D-FAULT-8a, D-FAULT-8b, D-FAULT-14).
6. Failure traces are byte-identical across multiple sessions that terminate at the same `(SessionState, seq, terminator_reason)` triple (D-FAULT-10, D-FAULT-11, D-FAULT-11a).
7. The Phase 4A 32/32 regression surface and Step 8 D-CONT contamination tests remain preserved.

If the deliberately-failing exercise passes but any of these load-bearing assertions does not hold, Step 9 has not landed.

### 13.17 Step 10 Direction A scope extension  *(contract freeze + empirical validation closed 2026-05-21)*

**Empirical validation status (2026-05-21):** Direction A is architecturally CLOSED. All four deferred-from-Step-9 scenarios (C/D/E/F) PASS on real Isaac Sim 5.0 PhysX with 12/12 cycles bytewise replay-identical under the validated `--reopen-stage-between-cycles` launcher isolation policy. The four clauses below (D-EXEC-13 a/b/c/d, D-FAULT-1b, D-FAULT-3b, D-FAULT-12c) passed under direct empirical pressure without weakening. See [`docs/phase_4b_step10_direction_a_analysis.md`](phase_4b_step10_direction_a_analysis.md) §P and [`docs/phase_4b_step10_p6_isaac_acceptance.md`](phase_4b_step10_p6_isaac_acceptance.md) §J/§K for closure record. The stage-reopen isolation requirement is a **launcher-level / test-infrastructure** policy for cross-cycle PhysX articulation-state isolation, NOT a contract limitation.

Step 10 Direction A extends the deterministic failure semantics with **executor-internal interruption surfaces** without expanding orchestration authority. The five immovable substrate posture clauses are restated explicitly under Step 10:

1. **Replay-authoritative truth.** `ticks_consumed` (D-FAULT-12c) is integer-counted, wall-clock-independent, and enters the per-task fingerprint (D-FAULT-10). `TaskOutcome.EXECUTION_INTERRUPTED` enters the fingerprint as a sub-classifier of `NODE_EXECUTION_FAILURE` (D-FAULT-1b). Observational forensics (`interrupted_at_segment_*`) do NOT enter the fingerprint (D-EXEC-13b).
2. **D-FAULT-1 enumeration is immutable.** No new top-level failure class is introduced. `EXECUTION_INTERRUPTED` is mechanically neutral and is classified post-Phase-E into one of the existing eight D-FAULT-1 classes per D-FAULT-3b's declared-order rule.
3. **Phase E remains atomic from the orchestration perspective.** D-FAULT-6a is preserved. The sub-Phase-E interruption surface is executor-internal (D-EXEC-13a) and invisible to D-EXEC-1..-12.
4. **Phase-A-only abort ingress.** D-FAULT-6 stands. Envelopes drained at Phase A; `OperatorAbortRequested` for a deferred (eligible-but-undrained) envelope is emitted by the session at the post-Phase-E classification site per D-FAULT-3b, NOT by the executor.
5. **Contradiction preservation on FAIL.** D-FAULT-5 / -5a / -5b stand; occupancy-mutation authority remains exclusively at Phase G on PASS (D-CONT-5). Mid-execute interrupt produces the same retained-state posture as full-execute FAIL: last-tick canonical truth, no occupancy mutation (D-CONT-5), no D-LIFE cleanup, no implicit rollback.

The Step 10 Direction A contract surface comprises four normative clauses:

| clause | scope | location |
|---|---|---|
| D-EXEC-13 (a–d) | sub-Phase-E interruption surface: segment boundaries, predicate purity, single-emitter discipline, no-speculation | §1.5 |
| D-FAULT-1b | `EXECUTION_INTERRUPTED` as executor-reported neutral outcome | §13.1.2 |
| D-FAULT-3b | session classification of `EXECUTION_INTERRUPTED` into orchestration-level class | §13.3.2 |
| D-FAULT-12c | `ticks_consumed` ontology and replay-authority | §13.12.3 |

Step 10 Direction A is **execution-adapter evolution only**: the orchestration substrate (D-CONT-1..-7a, D-FAULT-1..-15 modulo the additions above, D-EXEC-1..-12, D-SCHED, D-SESS, D-TRACE, D-BUS, D-REPLAY, D-FORBID, D-SCALE, D-CONF) is **frozen**. No D-FAULT clause is weakened; D-FAULT-15 row 5 is **strengthened** by an "orchestration-observable" qualification that makes the orchestration-observable interrupt prohibition more precise without admitting any new orchestration-observable surface. Twelve new D-FAULT-15 rows (19–30) explicitly enumerate Step 10-specific anti-patterns.

Step 10 Direction A is **NOT**:

* a new orchestration authority — the executor never gains mutation authority beyond PhysX scene;
* a new event taxonomy — no new event types are added;
* a new failure class — the D-FAULT-1 eight-class enumeration is unchanged;
* a new envelope schema — D-FAULT-9 stands;
* a recovery mechanism — D-FAULT-8 graph-explicit recovery remains the sole recovery path; Direction A only makes the deferred Step 9 scenarios C–F empirically reachable on PhysX;
* a live-ingress channel — envelopes are captured by closure at `execute()` entry only (Step 11 territory for live ingress);
* a pause/resume mechanism — D-FAULT-15 #18 forbids `RECOVERING`; Direction F (deferred indefinitely) addresses pause/resume separately;
* a cross-cell mechanism — Direction C (deferred) territory.

The load-bearing assertions Step 10 Direction A must satisfy at landing:

1. Every `TaskResult` with `outcome == EXECUTION_INTERRUPTED` carries a non-negative integer `ticks_consumed` produced by counting `world.step()` invocations at their site (D-FAULT-12c).
2. Every `EXECUTION_INTERRUPTED` return is classified by the session **before** Phase F/G into exactly one of `OPERATOR_ABORT` / `TIMEOUT_FAILURE` / `NODE_EXECUTION_FAILURE` per D-FAULT-3b's declared-order rule.
3. The interruption predicate is constructed only by the session, is pure, and closes only over the D-EXEC-13 whitelist of authoritative state captured at `execute()` entry.
4. The executor consults the predicate only at the segment boundaries enumerated by D-EXEC-13 conditions 1–5; per-step predicate consultation is FORBIDDEN.
5. Phase E remains atomic from the orchestration perspective per D-FAULT-6a and D-EXEC-13a: no session-side mid-execute mutation, no mid-execute envelope drain, no mid-execute event emission, no mid-execute boundary snapshot.
6. `EXECUTION_INTERRUPTED` (D-FAULT-1b) and `ticks_consumed` (D-FAULT-12c) enter the per-task fingerprint per D-FAULT-10; `interrupted_at_segment_*` do NOT enter the fingerprint per D-EXEC-13b; replay-identity byte-equality is preserved per D-FAULT-11a across multiple cycles of any deterministic interruption scenario.
7. The Step 8 Phase 6 comparator (`tools/check_session_replay_identity.py`) requires no changes; replay-identity divergence of `ticks_consumed` or `EXECUTION_INTERRUPTED` surfaces as ordinary `events.jsonl` byte-level divergence.
8. The Phase 4A 32/32 regression surface and the Step 8 + Step 9 D-CONT + D-FAULT regression suites remain preserved.

If Step 10 Direction A lands but any of these load-bearing assertions does not hold, Step 10 Direction A has not landed.

---

## 14. Live Ingress Admissibility Contract  *(D-INGRESS)*

### 14.1 Scope

This section codifies the constitutional admissibility surface for **live operator ingress**: the channel-based pathway by which `OperatorEnvelope` instances (D-FAULT-9) enter an `ExecutionSession` at runtime, in addition to the pre-queue pathway already governed by `pending_operator_envelopes` at `session.begin()`.

The clauses D-INGRESS-1 through D-INGRESS-9 are **conjunctive admissibility conditions**: live ingress is constitutionally compatible with the substrate IF AND ONLY IF all nine disciplines hold. Each discipline closes one or more identified threat surfaces from the Step 11 framework (per `docs/phase_4b_step11_admissibility_framework.md` §G + `docs/phase_4b_step11_f58_paused_analysis.md` §N).

D-INGRESS clauses bind the **substrate's view of the channel**, not the transport layer or the channel's internal implementation. The transport may use any push, pull, queue, or pub-sub mechanism; the substrate observes the channel exclusively through the Phase-A pull surface enumerated below.

### 14.2 D-INGRESS-1 — Channel Opacity

**D-INGRESS-1** — The channel is a **passive store**. It produces no observable behavior to the orchestration substrate except through the session's Phase-A pull. The channel **MUST NOT** emit events, **MUST NOT** register subscribers, **MUST NOT** expose a state-machine to orchestration, and **MUST NOT** observe session state.

**Citations.**
* Anchor: D-FAULT-9, D-BUS-1

*Note.* This clause asserts framework Discipline D1 (Channel Opacity) per `docs/phase_4b_step11_admissibility_framework.md` §G.1. D1 closes Step 11 framework Threats 1 (channel-as-second-emitter), 5 (cross-session channel state observation), and 8 (per-session lifecycle bleed). D-INGRESS-1 is normative-strengthening (making explicit the channel's passive-store property that D-FAULT-9 envelope-schema discipline + D-BUS-1 synchronous-dispatch discipline already imply), not normative-additive.

### 14.3 D-INGRESS-3 — Strict Atomic Snapshot

**D-INGRESS-3** — The channel pull **MUST** be an atomic operation that simultaneously (a) captures the channel's current buffer contents as a deterministic return value and (b) clears the channel's buffer. New arrivals after the snapshot **MUST** be invisible to the current `session.step()` invocation; they become eligible for the next session.step()'s Phase-A pull.

**Citations.**
* Anchor: D-FAULT-9, D-FAULT-6

*Note.* This clause asserts framework Discipline D3 (Strict Atomic Snapshot) per `docs/phase_4b_step11_admissibility_framework.md` §G.1. D3 closes Step 11 framework Threat 2 (hidden-race specifics at the pull boundary). The atomicity requirement constrains the observation, not the implementation mechanism (lock, CAS, lock-free queue with snapshot semantics, etc., are all admissible). D-INGRESS-3 is normative-strengthening (making explicit the snapshot atomicity property required by D-FAULT-6's Phase-A ingress entry surface), not normative-additive.

### 14.4 D-INGRESS-2 — Phase-A-Only Pull

**D-INGRESS-2** — The session **MUST** pull the channel exactly once per `session.step()` invocation, at the start of Phase A, before the existing `_drain_phase_a_envelopes` step. **No** sub-phase pull, **no** Phase B/C/D/E/F/G pull, and **no** post-Phase-G pull is admissible.

**Citations.**
* Anchor: D-FAULT-6, D-FAULT-6c, D-EXEC-1

*Note.* This clause asserts framework Discipline D2 (Phase-A-Only Pull) per `docs/phase_4b_step11_admissibility_framework.md` §G.1. D2 closes Step 11 framework Threats 2 (sub-phase observation), 3 (Phase-E pull), and 6 (post-execute pull). D-INGRESS-2 is constitutionally aligned with D-FAULT-6c (Phase-A-Only Ingress Observability, Wave 1) — D-FAULT-6c bounds the observation surface for ingress events to Phase A; D-INGRESS-2 bounds the pull mechanism for the channel to Phase A. The two clauses are complementary: D-FAULT-6c is the foreclosure on observation surfaces; D-INGRESS-2 is the foreclosure on pull invocations. D-INGRESS-2 is normative-strengthening, not normative-additive.

### 14.5 D-INGRESS-4 — Canonical-Order Discipline

**D-INGRESS-4** — After the Phase-A pull, the merged `_pending_envelopes` set **MUST** be canonical-ordered by `(requested_at_tick, envelope_id)`. The drain **MUST** iterate this canonical order. Transport-layer arrival order, buffer storage order, and channel internal order **MUST NOT** influence drain order.

**Citations.**
* Anchor: D-FAULT-9, D-SCHED-1

*Note.* This clause asserts framework Discipline D4 (Canonical-Order Discipline) per `docs/phase_4b_step11_admissibility_framework.md` §G.1. D4 closes Step 11 framework Threat 4 (transport-layer ordering authority over drain order). The canonical-order key `(requested_at_tick, envelope_id)` derives from D-FAULT-9's envelope schema (`requested_at_tick` field; content-addressed `envelope_id`). D-INGRESS-4 is normative-strengthening (making explicit the canonical-order discipline that D-FAULT-9 + D-SCHED-1's pure-function input set already imply), not normative-additive — it does NOT introduce transport-authority and does NOT introduce wall-clock-arrival authority.

### 14.6 D-INGRESS-5 — Pull-Only Direction

**D-INGRESS-5** — **No** callback, **no** notification, **no** signal, **no** asynchronous task, and **no** event **MAY** flow from the channel into the session except via the session's Phase-A pull. The session **MUST** always be the initiator of the observation surface; the channel **MUST NOT** initiate communication with the session.

**Citations.**
* Anchor: D-FAULT-9, D-BUS-2

*Note.* This clause asserts framework Discipline D5 (Pull-Only Direction) per `docs/phase_4b_step11_admissibility_framework.md` §G.1. D5 closes Step 11 framework Threat 1 explicitly (preventing the channel from becoming a second authoritative emitter alongside the session). The Pull-Only Direction reinforces D-BUS-2's prohibition on asynchronous primitives in the event-bus implementation. D-INGRESS-5 is normative-strengthening, not normative-additive.

### 14.7 D-INGRESS-6 — Predicate Closure Stability

**D-INGRESS-6** — The execute-entry predicate **MUST** close over `_pending_envelopes` as Phase A left it. **No** subsequent mutation of `_pending_envelopes` (e.g. a second pull, a callback-injected envelope, a sub-phase observation) **MAY** occur within the same `session.step()` invocation. The predicate **MUST** be constructed by the session (per D-EXEC-13c) and consumed opaquely by the executor (per D-EXEC-13d).

**Citations.**
* Anchor: D-EXEC-13c, D-EXEC-13d, D-FAULT-9

*Note.* This clause asserts framework Discipline D6 (Predicate Closure Stability) per `docs/phase_4b_step11_admissibility_framework.md` §G.1. D6 closes Step 11 framework Threat 6 (predicate input variance within a single tick). D-INGRESS-6 is constitutionally aligned with D-EXEC-13c (predicate session-constructed only) + D-EXEC-13d (predicate opaque to executor) — D-INGRESS-6 extends these to assert the closure's *input stability* across the Phase-A-to-execute-entry interval. D-INGRESS-6 is normative-strengthening, not normative-additive.

### 14.8 D-INGRESS-7 — Per-Session Channel Lifecycle

**D-INGRESS-7** — The channel **MUST** be constructed at or before `session.begin()` and **MUST** be torn down at `session.close()`. Channel state **MUST NOT** survive into subsequent sessions in the same process. The transport layer **MAY** persist across sessions; the substrate's view of the channel **MUST NOT**.

**Citations.**
* Anchor: D-FAULT-9, D-CONT-1

*Note.* This clause asserts framework Discipline D7 (Per-Session Channel Lifecycle) per `docs/phase_4b_step11_admissibility_framework.md` §G.1. D7 closes Step 11 framework Threat 8 (cross-session channel state observation). The constitutional invariant is that channel state is a session-scoped resource; the transport layer's persistence is out-of-substrate. D-INGRESS-7 is normative-strengthening (making explicit the session-scoped lifecycle property that D-FAULT-9's session-bound envelope schema + D-CONT-1's session-scoped authoritative state discipline already imply), not normative-additive.

### 14.9 D-INGRESS-8 — Diagnostic Boundary

**D-INGRESS-8** — Wall-clock arrival timestamps, transport identifiers, connection state, and any other non-authoritative channel metadata are **diagnostic only**, subject to three conjunctive sub-rules:

* **D-INGRESS-8a (on-event-not-envelope):** Diagnostic metadata **MAY** be recorded on `OperatorAbortRequested` / `OperatorPauseRequested` / `OperatorResumeRequested` events as an explicitly diagnostic payload field, subject to D-SESS-5. Diagnostic metadata **MUST NOT** enter the `OperatorEnvelope` schema (D-FAULT-9).
* **D-INGRESS-8b (not-read-by-orchestration):** Orchestration logic — scheduler decisions (D-SCHED-1), predicate evaluation (D-SCHED-12), command emission (D-EXEC), validation, or replay-authoritative trace commits (D-TRACE-1) — **MUST NOT** read diagnostic metadata. Diagnostic metadata is non-authoritative.
* **D-INGRESS-8c (not-in-fingerprint):** Diagnostic metadata **MUST NOT** enter the per-task fingerprint (D-FAULT-10), the canonical-drain order (D-SCHED), the predicate closure (D-EXEC-13), or any authoritative continuity surface (D-CONT-1). Diagnostic metadata **MUST NOT** influence replay-identity comparisons (D-REPLAY-1 through D-REPLAY-9).

Diagnostic metadata **MAY** be omitted entirely.

**Citations.**
* Anchor: D-FAULT-9, D-SESS-5, D-FAULT-10, D-SCHED-11

*Note.* This clause asserts framework Discipline D8 (Diagnostic Boundary) per `docs/phase_4b_step11_admissibility_framework.md` §G.1. D8 closes Step 11 framework Threat 3 (partial) and Threat 7 (partial) via the diagnostic-field discipline. The three sub-rules (D-INGRESS-8a/b/c) jointly prevent diagnostic metadata from acquiring orchestration authority through any indirect pathway. D-INGRESS-8 is normative-strengthening (making explicit the diagnostic-authoritative separation that D-SESS-5 + D-SCHED-11 + D-FAULT-10 already imply), not normative-additive — it does NOT introduce wall-clock authority and does NOT introduce transport authority.

### 14.10 D-INGRESS-9 — Caller-Driven PAUSED Cadence

**D-INGRESS-9** — During the `PAUSED` session state, the substrate **MUST NOT** make wall-clock observations and **MUST NOT** consume wall-clock duration internally. The wall-clock duration of any PAUSED interval **MUST** be determined entirely by the cadence at which the caller invokes `session.step()`. The substrate **MUST** count only `orchestration_tick` values; the substrate **MUST NOT** measure, gate on, or observe wall-clock duration during PAUSED. D-INGRESS-9 applies conditionally on `PAUSED` being an admitted session state; when `PAUSED` is constitutionally admitted, this discipline becomes binding without modification of this clause.

**Citations.**
* Anchor: D-SCHED-11, D-FAULT-9, D-FAULT-9a

*Note.* This clause asserts framework Discipline D9 (Caller-Driven PAUSED Cadence) per `docs/phase_4b_step11_f58_paused_analysis.md` §N.1. D9 closes Step 11 framework Threat 7 (PAUSED-as-wall-clock-wait) by forbidding the substrate from observing wall-clock during PAUSED. The substrate's wall-clock foreclosure (D-SCHED-11) is already in force pre-Step-12 and remains the controlling constitutional discipline for non-PAUSED contexts; D-INGRESS-9 extends the same foreclosure surface specifically into the PAUSED state. D-INGRESS-9 is normative-strengthening (making explicit the PAUSED-specific wall-clock foreclosure that D-SCHED-11 already implies for the PAUSED state), not normative-additive — it does NOT introduce autonomous progression, does NOT introduce wall-clock authority, and does NOT introduce scheduler-state mutation outside of caller-driven `session.step()` invocations.

### 14.11 Step 11 scope restatement

The nine D-INGRESS clauses jointly assert the Step 11 framework's verdict: **live operator ingress is constitutionally compatible with the Phase 4B substrate IF AND ONLY IF D-INGRESS-1 through D-INGRESS-9 all hold.** This restatement is non-normative; the constitutional binding is on the per-clause statements above.

Per Step 11 framework §G.2 (sufficiency claim) + §G.3 (necessity claim): D1–D9 are both sufficient (admitting the channel mechanism without weakening any existing clause) and necessary (removing any single Di reopens at least one threat). Per `docs/phase_4b_step11_closure_verification.md` §7.1: no additional threat surface beyond the eight Step 11 threats + the F58-introduced Threat 7 requires a new discipline; D1–D9 are minimal and complete.

The §14 D-INGRESS family is the constitutional landing surface for live ingress. Subsequent waves of Step 12 codification may cite §14 from §13 D-FAULT extensions and from D-FAULT-15 row extensions where ingress-related foreclosures intersect with failure-family semantics; the specific cross-section citation graph is the next-wave authoring concern and is not pre-bound here.

---

**End of deterministic-semantics contract.**

This document binds [docs/phase_4b_orchestration_architecture.md](phase_4b_orchestration_architecture.md) and every Phase 4B implementation step that follows. On adoption, the next architectural artifact is the step-1 implementation note for `EventBus` + event taxonomy, which **must** cite this contract for every dispatch / ordering / subscriber-topology choice it makes. Sections §12 (D-CONT) and §13 (D-FAULT) extend the contract for inter-node continuity (Step 8) and deterministic failure semantics (Step 9) respectively; every subsequent step MUST cite both families for any cross-node or failure-path behaviour. Section §1.5 (D-EXEC-13 sub-Phase-E interruption surface) and the D-FAULT-1b / D-FAULT-3b / D-FAULT-12c clauses (Step 10 Direction A contract freeze, §13.17) extend the contract for deterministic executor interruption surfaces; every subsequent step that touches the executor MUST cite §1.5 and §13.17 for any segment-boundary, predicate-consumption, `ticks_consumed`, or `EXECUTION_INTERRUPTED` behaviour.
