# Asset Validator — Design Specification

**Target path**: `isaac_factory/extensions/asset_validator/`
**Runtime**: Profile B (`isaac`) — Isaac Sim 5.0 Kit Python 3.11
**Status**: Design only. **No code in this turn.** Implementation deferred.
**Last revised**: 2026-05-18

This document specifies the architecture, module layout, dependency graph, public API, validation pipeline, and testing strategy for the workspace-local asset validator extension. The validator's purpose is to catch broken or unsafe USD assets before they reach a simulation run.

---

## 0. Source documents — status

The user named three input documents — `02_ENGINEERING_RULES.md`, `04_SUBSYSTEMS.md`, `06_ACCEPTANCE_CRITERIA.md` — none of which exist anywhere under `/home/cap2/`. This design therefore relies on:

- The [runtime](runtime_policy.md), [validation](runtime_validation.md), and [storage](storage_policy.md) policies in this workspace.
- The reference-only `factory/` project's harness conventions (Sprint Contracts, G1–G6 gates) — **consulted as prior art, not copied**, per [[feedback-no-legacy-auto-adoption]].
- Standard NVIDIA Isaac Sim 5 / USD / PhysX best practices.
- The companion [docs/asset_validator_acceptance.md](asset_validator_acceptance.md), drafted in the same turn as this spec.

**Assumptions in lieu of the missing source docs** — flag and override any that conflict with the real engineering rules when they surface:

| # | Assumption | Reason it matters |
|---|---|---|
| A1 | All assets are authored in **meters / kilograms / seconds**, Z-up, right-handed (USD default, Isaac Sim convention). | Drives bounds and tolerance numerics in §6 (overlap distance, drift velocity). |
| A2 | A "valid asset" is a USD layer (`.usd`/`.usda`/`.usdc`) referenced into a stage; the validator runs against either a file or a live `Usd.Stage`. | Determines the entry-point API shape. |
| A3 | Physics validation uses `omni.physx` + `isaacsim.core.api.World`, not raw PxScene. | Determines adapter layer (`adapters/`). |
| A4 | The validator must be **non-destructive**: it may open and step a stage but must not save mutations back to source files. | Drives §5 read-only guarantee. |
| A5 | Acceptance thresholds are **configurable**, with defaults from [docs/asset_validator_acceptance.md](asset_validator_acceptance.md). | Drives `thresholds/` module shape. |
| A6 | The validator is callable from (a) a CLI under Profile B, (b) other Python scripts in `isaac_factory/`, (c) optionally a Kit UI panel. | Drives three-pronged entry points. |
| A7 | Validation failures must produce **machine-readable** output for CI gates (JSON + JUnit XML). | Drives `reporters/`. |

---

## 1. Architecture overview

The validator is a **layered pure-Python package** that runs inside Isaac Sim Kit Python (Runtime B per [runtime_policy.md §2](runtime_policy.md#2-runtime-separation-rules)). It is structured as a Kit extension folder so it can later expose a UI panel, but the core is usable as a plain `import` from any `isaac_factory/` script.

```
            ┌─────────────────────────────────────────────────┐
            │                CLI / Kit UI panel               │
            └────────────────────────┬────────────────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │       Pipeline             │
                       │  (orchestrates phases)     │
                       └──┬─────────────┬──────────┘
                          │             │
              ┌───────────▼──┐    ┌─────▼────────┐
              │  Validators  │    │  Reporters   │
              │  (6 checks)  │    │ (json/text/  │
              │              │    │  junit)      │
              └─┬────┬──┬────┘    └──────┬───────┘
                │    │  │                │
   ┌────────────▼┐ ┌─▼──▼─────┐ ┌────────▼──────┐
   │  Thresholds │ │ Adapters │ │   Core types  │
   │  (config)   │ │ (USD,    │ │ (Report,Issue,│
   │             │ │  PhysX,  │ │  Severity,    │
   │             │ │  World)  │ │  Context)     │
   └─────────────┘ └────┬─────┘ └───────┬───────┘
                        │               │
                        └───────┬───────┘
                                │
                          ┌─────▼─────┐
                          │   Utils   │
                          │ (pure-py) │
                          └───────────┘
```

### Layer boundaries

| Layer | May import | May NOT import |
|---|---|---|
| `utils/`     | stdlib, `numpy` | `pxr`, `omni`, anything else in the project |
| `core/`      | `utils/`, stdlib, `numpy` | `pxr`, `omni`, `isaacsim` |
| `thresholds/`| `core/`, stdlib, `pyyaml` | `pxr`, `omni` |
| `adapters/`  | `core/`, `utils/`, `pxr`, `omni.usd`, `omni.physx`, `isaacsim.core.api` | other validator modules |
| `validators/`| `core/`, `thresholds/`, `adapters/`, `utils/` | `reporters/`, `cli/`, `ui/` |
| `reporters/` | `core/`, stdlib | `validators/`, `adapters/` |
| `cli/`       | all of the above | — |
| `ui/`        | `core/`, `omni.ui` | `validators/` directly (goes through Pipeline) |

The bottom three layers (`utils/`, `core/`, `thresholds/`) are **Isaac-free** and can be unit-tested in Runtime A (`research` profile) via `usd-core` only — no Kit needed. Everything above must run in Runtime B.

---

## 2. Module layout

```
isaac_factory/extensions/asset_validator/
├── README.md                          # quick-start + invocation examples
├── CHANGELOG.md
├── pyproject.toml                     # standalone-import packaging metadata
├── config/
│   └── extension.toml                 # Kit extension manifest (optional load)
├── data/
│   └── icons/                         # for Kit UI panel
├── configs/
│   └── acceptance_default.yaml        # mirrors docs/asset_validator_acceptance.md
│
├── asset_validator/                   # the Python package
│   ├── __init__.py                    # public API re-exports (see §4)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── severity.py                # Severity enum: INFO | WARN | FAIL
│   │   ├── issue.py                   # @dataclass Issue
│   │   ├── report.py                  # ValidationReport + aggregation
│   │   ├── context.py                 # ValidationContext (stage, config, world handle)
│   │   ├── validator_base.py          # abstract Validator base class
│   │   └── pipeline.py                # Pipeline orchestrator (phase selection, retries)
│   │
│   ├── thresholds/
│   │   ├── __init__.py
│   │   ├── schema.py                  # AcceptanceCriteria dataclass tree
│   │   └── loader.py                  # YAML/JSON load, env override, validation
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── stage_io.py                # open USD file, isolate to scratch stage
│   │   ├── usd_adapter.py             # pure-USD queries (no physics)
│   │   ├── physx_adapter.py           # PhysX contact reports, scene queries
│   │   └── isaac_world_adapter.py     # isaacsim.core.api.World lifecycle wrapper
│   │
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── overlap.py                 # OverlapValidator           (dynamic)
│   │   ├── collider.py                # ColliderValidator          (static)
│   │   ├── transform.py               # TransformValidator         (static)
│   │   ├── grounding.py               # GroundingValidator         (dynamic)
│   │   ├── hierarchy.py               # HierarchyValidator         (static) — △ DEFERRED PHASE 2
│   │   └── deterministic_reset.py     # DeterministicResetValidator (dynamic)
│   │
│   ├── reporters/
│   │   ├── __init__.py
│   │   ├── base.py                    # Reporter ABC
│   │   ├── text_reporter.py           # human-readable report → stdout / file
│   │   ├── json_reporter.py           # machine-readable JSON
│   │   └── junit_reporter.py          # JUnit XML for CI
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── usd_traversal.py           # depth-first walks, prim filters
│   │   ├── transform_math.py          # quaternion/matrix helpers (numpy)
│   │   └── logging.py                 # structured-logging wrapper
│   │
│   └── ui/                            # optional Kit panel (post-MVP)
│       ├── __init__.py
│       └── window.py
│
├── cli/
│   ├── __init__.py
│   └── validate.py                    # CLI entrypoint: python.sh -m cli.validate
│
└── tests/
    ├── conftest.py                    # fixture discovery, profile gating
    ├── fixtures/
    │   ├── README.md                  # fixture catalog
    │   ├── good_asset.usda            # passes all checks
    │   ├── overlap_pair.usda
    │   ├── nan_transform.usda
    │   ├── neg_scale.usda
    │   ├── orphan_collider.usda
    │   ├── unbounded_mesh_collider.usda
    │   ├── nested_rigid_body.usda
    │   ├── deep_hierarchy.usda
    │   ├── floating_object.usda
    │   ├── unresolved_reference.usda
    │   └── non_deterministic_seed.usda
    ├── unit/                          # L1: pure-python, no Isaac
    │   ├── test_severity.py
    │   ├── test_issue.py
    │   ├── test_report_aggregation.py
    │   ├── test_thresholds_load.py
    │   └── test_pipeline_phase_order.py
    ├── usd_only/                      # L2: usd-core, no Kit, no PhysX
    │   ├── test_hierarchy.py
    │   ├── test_transform.py
    │   └── test_collider_static.py
    ├── kit/                           # L3: requires Kit + PhysX
    │   ├── test_overlap.py
    │   ├── test_grounding.py
    │   ├── test_deterministic_reset.py
    │   └── test_pipeline_end_to_end.py
    └── regression/                    # L4: golden + bad assets
        ├── test_golden_pass.py
        └── test_known_failures.py
```

---

## 3. Dependency graph

### 3.1 Internal (intra-package)

```
cli.validate ───────────────┐
                            ▼
                        Pipeline ─────┐
                            │         │
              ┌─────────────┼─────────┘
              ▼             ▼
        validators/*   reporters/*
              │
   ┌──────────┼────────────┐
   ▼          ▼            ▼
adapters/  thresholds/   core/*
   │                       │
   └───────────┬───────────┘
               ▼
            utils/*
```

Compile-time rule: **no cycles**. Any new module must not introduce a back-edge. A `tests/unit/test_import_graph.py` test enforces this with `importlib` + DAG check.

### 3.2 External (third-party + Isaac stack)

| Package | Required by | Source | Runtime |
|---|---|---|---|
| `numpy` | `utils/`, validators, core | conda env / Kit bundled | A + B |
| `pyyaml` | `thresholds/loader.py` | conda env / Kit bundled | A + B |
| `pxr` | `adapters/usd_adapter.py`, `stage_io.py`, validators | bundled in Isaac extscache (B) OR `usd-core` (A, L1/L2 tests only) | A (static) + B (full) |
| `omni.usd` | `adapters/stage_io.py` | Isaac Sim extensions | B only |
| `omni.physx` | `adapters/physx_adapter.py`, `OverlapValidator`, `DeterministicResetValidator` | Isaac Sim extensions | B only |
| `isaacsim.core.api` | `adapters/isaac_world_adapter.py` | Isaac Sim | B only |
| `omni.ui` | `ui/window.py` (optional) | Isaac Sim | B only |
| `pytest` | `tests/` | conda env / Kit bundled | A + B |

**No dependency on**: `torch`, `isaaclab`, `rclpy`, `ros2*`, `gym*`, `stable_baselines3`. The validator is a single-runtime tool by design.

---

## 4. Public API

Exported from `asset_validator/__init__.py`:

```python
# Core types
from .core.severity        import Severity              # IntEnum: INFO=0, WARN=1, FAIL=2
from .core.issue           import Issue
from .core.report          import ValidationReport
from .core.context         import ValidationContext
from .core.validator_base  import Validator
from .core.pipeline        import Pipeline

# Configuration
from .thresholds.schema    import AcceptanceCriteria
from .thresholds.loader    import load_criteria          # (path: str | Path) -> AcceptanceCriteria

# Concrete validators
from .validators.overlap              import OverlapValidator
from .validators.collider             import ColliderValidator
from .validators.transform            import TransformValidator
from .validators.grounding            import GroundingValidator
from .validators.hierarchy            import HierarchyValidator  # △ DEFERRED PHASE 2
from .validators.deterministic_reset  import DeterministicResetValidator

# Reporters
from .reporters.text_reporter   import TextReporter
from .reporters.json_reporter   import JsonReporter
from .reporters.junit_reporter  import JunitReporter

# Convenience entrypoint
from .api import run_validation
```

### 4.1 `Issue`

```python
@dataclass(frozen=True)
class Issue:
    code:        str            # stable identifier, e.g. "OVERLAP.PEN_DEPTH_EXCEEDED"
    severity:    Severity
    message:     str            # human-readable
    prim_paths:  tuple[str, ...]  # affected USD prims (Sdf paths)
    metric:      dict[str, float] | None = None   # raw measurements
    threshold:   dict[str, float] | None = None   # what was expected
    validator:   str = ""       # which validator emitted this
```

Issue **codes are namespaced** (`OVERLAP.*`, `COLLIDER.*`, `TRANSFORM.*`, `GROUNDING.*`, `HIERARCHY.*`, `RESET.*`) and stable across versions — they appear in CI gates and Sprint Contracts.

### 4.2 `ValidationReport`

```python
class ValidationReport:
    issues:           list[Issue]
    validators_run:   list[str]
    duration_seconds: float
    asset_uri:        str
    started_at:       datetime
    criteria:         AcceptanceCriteria   # what we measured against

    def status(self) -> Severity: ...      # max severity across issues
    def by_severity(self, s: Severity) -> list[Issue]: ...
    def by_validator(self, name: str) -> list[Issue]: ...
    def to_dict(self) -> dict: ...
    def passed(self) -> bool: ...          # True iff no FAILs
```

### 4.3 `Validator` base

```python
class Validator(ABC):
    name:  ClassVar[str]                   # e.g. "overlap"
    phase: ClassVar[Literal["static", "dynamic"]]

    def __init__(self, criteria: AcceptanceCriteria): ...

    @abstractmethod
    def run(self, ctx: ValidationContext) -> list[Issue]: ...
```

### 4.4 `Pipeline`

```python
class Pipeline:
    def __init__(
        self,
        validators: list[Validator],
        criteria:   AcceptanceCriteria,
        *,
        skip_dynamic: bool = False,
        seed:         int  = 0,
    ): ...

    def run(self, stage_or_uri: Usd.Stage | str) -> ValidationReport: ...
```

### 4.5 `run_validation` (convenience)

```python
def run_validation(
    asset:     str | Path | Usd.Stage,
    criteria:  AcceptanceCriteria | str | Path | None = None,
    validators: list[str] | None = None,    # subset by name; default = all six
    reporters:  list[Reporter] | None = None,
    out_dir:    Path | None = None,         # default: $WORKSPACE_ROOT/outputs/asset_validation/<ts>/
) -> ValidationReport:
    ...
```

### 4.6 CLI

```
python.sh -m asset_validator.cli.validate \
    --asset path/to/asset.usd \
    [--criteria path/to/acceptance.yaml] \
    [--validators overlap,collider,transform,grounding,hierarchy,reset] \
    [--out-dir outputs/asset_validation/run42] \
    [--reporter text,json,junit] \
    [--seed 0] \
    [--skip-dynamic] \
    [--fail-on warn]            # default: fail-on fail
```

Exit codes mirror [scripts/validate_runtime.sh](../scripts/validate_runtime.sh): `0` clean, `0` with WARN (unless `--fail-on warn`), `1` on FAIL, `2` on bad argument.

---

## 5. Validation pipeline

### 5.1 Phases

| Phase | Validators | Stage state | Cost |
|---|---|---|---|
| **0. Setup** | — | Resolve URI → open stage in isolated `Sdf.Layer.CreateAnonymous` sublayer; never mutate source file | fast |
| **1. Static** | hierarchy, transform, collider | Stage loaded, **no physics** | fast (1–5 s) |
| **2. Dynamic-init** | — | `isaacsim.core.api.World` created with `physics_dt=1/60`, deterministic flags set; `World.reset()` called | medium (5–10 s) |
| **3. Dynamic** | overlap, grounding, deterministic_reset | Physics steps under controlled seed | slow (10–60 s, depends on settle/reset cycles) |
| **4. Aggregate** | — | Combine issues; escalate per criteria | fast |
| **5. Report** | — | Write reporter outputs to `outputs/asset_validation/<ts>/` | fast |

### 5.2 Sequencing rules

1. **Static phase runs first**. If any static validator emits a FAIL and `--strict-static` is set (default true), the pipeline **skips the dynamic phase** — no point physics-simulating a structurally broken asset.
2. **Dynamic-init failures** (e.g., PhysX cooking errors) are reported as `COLLIDER.COOKING_FAILED` issues and abort the dynamic phase with FAIL.
3. **Random seed is fixed at Setup** and re-applied before each dynamic validator. NumPy, `torch` (if present), and PhysX's solver seed are all set. Default seed = 0; CLI `--seed` overrides.
4. **Single-pass execution**. Validators are not reordered or repeated within a run; cross-validator dependencies are forbidden. Shared state lives in `ValidationContext`, populated once at Setup.

### 5.3 Per-validator one-line summary

| Validator | Phase | What it measures | Acceptance ref | Status |
|---|---|---|---|---|
| `HierarchyValidator`       | static  | prim depth/breadth, articulation roots, schema parentage | [acceptance §4](asset_validator_acceptance.md#4-hierarchy-rules--status-deferred-to-phase-2) | **△ deferred to Phase 2** |
| `TransformValidator`       | static  | NaN/Inf, scale bounds, quaternion normalization, orthogonality, cascade, static floating-heuristic | [acceptance §2](asset_validator_acceptance.md#2-invalid-transform-rules) | ✓ implemented |
| `ColliderValidator`        | static  | RigidBody↔Collision pairing, collider type, cooking success, stability heuristics | [acceptance §3](asset_validator_acceptance.md#3-collider-requirements) | ✓ implemented |
| `OverlapValidator`         | dynamic | contact pairs + penetration depth after 1 physics step | [acceptance §1](asset_validator_acceptance.md#1-overlap-thresholds) | ✓ implemented |
| `GroundingValidator` (static)  | static  | raycast-based gap + buried/floating/no-support detection | [acceptance §5.B](asset_validator_acceptance.md#5b-static-grounding--status-implemented) | ✓ implemented |
| `GroundingValidator` (dynamic) | dynamic | AABB vs support distance after settle; drift velocity | [acceptance §5.A](asset_validator_acceptance.md#5a-dynamic-grounding--status-deferred-to-phase-2) | **△ deferred to Phase 2** |
| `DeterministicResetValidator` | dynamic | pose delta after step + reset cycles + spawn order + residual contacts | [acceptance §6](asset_validator_acceptance.md#6-deterministic-reset-requirements) | ✓ implemented |

### 5.4 Read-only guarantee

- `stage_io.open_for_validation()` opens with `Usd.Stage.Open(..., Usd.Stage.LoadAll)` against an **anonymous root layer** that references the asset; the source layer is never `Save()`-ed.
- Dynamic-phase mutations (PhysX state, applied forces) happen on the in-memory stage only.
- No code path writes to the asset URI. Only `outputs/asset_validation/<ts>/` is written.
- A `tests/unit/test_no_save_calls.py` test grep-asserts that the source tree contains no `.Save(` calls on USD layers (whitelist for tests' own fixture authoring).

---

## 6. Configuration flow

```
docs/asset_validator_acceptance.md  ──(authoritative human-readable thresholds)
            │
            │   manually kept in sync
            ▼
configs/acceptance_default.yaml     ──(machine-readable mirror, shipped with extension)
            │
            ▼
load_criteria(path) ──► AcceptanceCriteria  (dataclass tree, validated)
            │
            ▼
Pipeline(criteria=…) ──► Validator(criteria=…) ──► Issue.threshold = relevant subset
```

Per-asset overrides are allowed via CLI `--criteria custom.yaml`. CI gates can pin a specific criteria version.

A test (`tests/unit/test_acceptance_docs_in_sync.py`) parses both the markdown table in §1–§6 of the acceptance doc and the YAML defaults, and asserts every threshold appears in both with the same value.

---

## 7. Testing strategy

### 7.1 Four-tier test pyramid

| Tier | Runtime | Speed | What it covers | When it runs |
|---|---|---|---|---|
| **L1 — unit**       | A (`research`)            | <30 s total | pure-python: severity ordering, report aggregation, threshold loading, pipeline phase selection, import-graph DAG | every PR (pre-commit hook) |
| **L2 — usd-only**   | A (`research`, `usd-core`) | <60 s total | static validators against synthetic `.usda` fixtures; no Kit, no PhysX | every PR |
| **L3 — kit**        | B (`isaac`, full Kit Python) | 3–10 min | dynamic validators end-to-end, real PhysX, real World | nightly + on-demand |
| **L4 — regression** | B                          | 5–20 min  | golden assets that must always PASS; bad assets that must FAIL with named codes | nightly + before release |

### 7.2 Fixture catalogue

Each fixture is a small synthetic `.usda` checked into `tests/fixtures/` (text, version-controllable). The fixture name maps 1:1 to the issue code it should produce.

| Fixture | Expected outcome |
|---|---|
| `good_asset.usda`              | PASS on all six validators |
| `overlap_pair.usda`            | `OVERLAP.PEN_DEPTH_EXCEEDED` FAIL |
| `nan_transform.usda`           | `TRANSFORM.NAN_VALUE` FAIL |
| `neg_scale.usda`               | `TRANSFORM.NON_POSITIVE_SCALE` FAIL or WARN per criteria |
| `orphan_collider.usda`         | `COLLIDER.NO_RIGID_BODY_ANCESTOR` FAIL |
| `unbounded_mesh_collider.usda` | `COLLIDER.NON_CONVEX_MESH_ON_DYNAMIC` FAIL |
| `nested_rigid_body.usda`       | `HIERARCHY.NESTED_RIGID_BODY` FAIL |
| `deep_hierarchy.usda`          | `HIERARCHY.MAX_DEPTH_EXCEEDED` WARN |
| `floating_object.usda`         | `GROUNDING.DRIFT_AFTER_SETTLE` FAIL |
| `unresolved_reference.usda`    | `HIERARCHY.UNRESOLVED_REFERENCE` FAIL |
| `non_deterministic_seed.usda`  | `RESET.POSE_DRIFT_EXCEEDED` FAIL |

### 7.3 Determinism gate for the tests themselves

The dynamic-validator tests must themselves be deterministic. The L3 test runner:

1. Sets PhysX `useDeterministicSimulation = True`.
2. Fixes `numpy.random.seed(0)` and Python `random.seed(0)`.
3. Pins the physics_dt and substep counts.
4. Re-runs each test 3× in a row; if outputs differ, the test is failed regardless of the assertion result (`tests/kit/conftest.py: pytest_runtest_call` wrapper).

### 7.4 Coverage targets

| Module | Line coverage | Branch coverage |
|---|---|---|
| `core/`        | ≥ 90 % | ≥ 80 % |
| `validators/`  | ≥ 85 % | ≥ 75 % |
| `thresholds/`  | ≥ 95 % | ≥ 85 % |
| `adapters/`    | ≥ 70 % | — (Isaac-bound, hard to mock) |
| `reporters/`   | ≥ 80 % | — |
| `cli/`         | smoke only | smoke only |

### 7.5 CI integration

- **Pre-commit hook**: L1 + L2 (fast).
- **PR check**: L1 + L2 + lint + import-graph DAG + acceptance-docs-in-sync.
- **Nightly job**: L3 + L4, JUnit XML uploaded for trend analysis.
- **Release gate**: full pyramid + manual review of any new fixture.

Tests live alongside the extension at `isaac_factory/extensions/asset_validator/tests/`. The workspace-level `tests/` directory (per the 12 canonical dirs) holds **integration tests that exercise the validator against real `factory/` assets** as a separate concern.

---

## 8. Out of scope (for this design)

To keep the MVP tight, the following are explicitly **not** in v1 and would be follow-up designs:

1. **Material / shader validation** — broken MDL paths, missing textures, OmniPBR vs UsdPreviewSurface mismatch. Belongs in a sibling `material_validator` extension.
2. **Animation / time-sampled data validation** — sample-rate checks, missing keyframes. Static-asset validator only for v1.
3. **Articulation joint-limit validation** — implied by collider + transform checks but a thorough joint validator is a separate concern.
4. **Repair mode** — the validator only diagnoses. Auto-fixing live on a separate `asset_repair` tool that consumes a `ValidationReport`.
5. **Distributed validation** — parallel validation of many assets. v1 is single-asset, single-process.
6. **Live-stage incremental validation** — re-running checks on a changed prim only. v1 always validates the full stage.
7. **Replicator-time validation** — checking outputs during SDG. Out of scope; SDG QA is a separate pipeline.

---

## 9. Open questions

These need answers from the real source docs (when available) or from the user before implementation begins:

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | Does an asset that passes all six validators receive a signed "validated" badge metadata that downstream consumers can check? | No badge in v1 |
| Q2 | Should the validator support **asset libraries** (validate every USD in a directory) or only single assets? | Single asset in v1; bash loop for libraries |
| Q3 | Is there an established issue-code namespace already in use (e.g., from `factory/.dev/harness/`)? | Use the namespaces in this doc |
| Q4 | Must the validator hook into a Sprint Contract gate (G1–G6 in `factory/` precedent)? | Treat the validator's status as a project-level gate; integration TBD |
| Q5 | What's the policy on **third-party USD assets** (e.g., NVIDIA's sample factory assets) that may not meet our acceptance criteria? | Validate with `--criteria third_party.yaml` (looser) |
| Q6 | Should reports be persisted to a central artifact store, or is the workspace `outputs/` sufficient? | `outputs/` only, per [storage_policy.md](storage_policy.md) |

---

## 10. Relation to other documents

| Document | Role |
|---|---|
| [docs/asset_validator_acceptance.md](asset_validator_acceptance.md) | The authoritative threshold values — single source of truth for §6 numerics |
| [docs/runtime_policy.md](runtime_policy.md) | Determines this extension runs in Runtime B; constrains its imports |
| [docs/runtime_validation.md](runtime_validation.md) | Sibling doctor for the runtime itself; complementary, not overlapping |
| [docs/storage_policy.md](storage_policy.md) | Determines where reports land (`outputs/asset_validation/`), where caches go (`cache/`) |
| `02_ENGINEERING_RULES.md`, `04_SUBSYSTEMS.md`, `06_ACCEPTANCE_CRITERIA.md` | **Not found on host** — this design is provisional pending those inputs |
