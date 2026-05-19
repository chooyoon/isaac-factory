# Runtime B Bootstrap

**Purpose**: how to verify Runtime B (Isaac Sim Kit Python) is reachable from this workspace and that the omni.* modules the Phase 1.B PhysX adapters will need are importable.
**Companion to**: [runtime_b.md](runtime_b.md), [physx_runtime_constraints.md](physx_runtime_constraints.md), [runtime_policy.md §4](runtime_policy.md#4-activation-order)
**Last revised**: 2026-05-18

This is the operational manual for the **bootstrap probe** shipped this turn — `tools/runtime_b_validation.py` + `tools/physx_runtime_probe.py`. The probe is read-only, runs in seconds (static mode) or tens of seconds (--probe mode), and produces a PASS/WARN/FAIL report matching the format of `scripts/validate_runtime.sh`.

---

## 1. When to run the probe

| Situation | Mode |
|---|---|
| Verifying that Isaac Sim 5.0 is installed where the policy expects | default (static) |
| Before requesting a Phase 1.B adapter implementation | `--probe` |
| After upgrading Isaac Sim, conda env, or NVIDIA driver | `--probe` |
| Triaging an "it worked yesterday" Kit-Python issue | `--probe` |
| In CI as a gate for any Runtime B work | `--probe` |
| Verifying SimulationApp can boot end-to-end (not yet supported) | `--deep` (reserved, not implemented in this scaffold) |

---

## 2. Running it

### 2.1 Default (static) mode

```bash
python isaac_factory/extensions/asset_validator/tools/runtime_b_validation.py
```

Runs in any Python ≥ 3.10. Uses `subprocess` for one Kit-Python `--version` call (fast). No Kit boot. Typical wall time: < 1 second.

Static checks performed:

| Check | What it verifies |
|---|---|
| Isaac Sim directory present | `/home/cap2/isaac-sim-5.0.0/` exists |
| Launchers present | `python.sh`, `isaac-sim.sh`, `kit/python/bin/python3` |
| Kit Python version | `kit/python/bin/python3 --version` reports 3.11.x |
| extscache layout | `omni.physx*`, `omni.usd.libs-*`, `isaacsim.core.api`, `isaacsim.ros2.bridge/jazzy` present |
| Probe script present | `tools/physx_runtime_probe.py` is on disk |
| Adapter scaffolds present | `physx_contact_source.py`, `physx_collider_inspector.py`, `physx_reset_simulator.py` |

### 2.2 `--probe` (subprocess import-probe)

```bash
python isaac_factory/extensions/asset_validator/tools/runtime_b_validation.py --probe
```

Adds one subprocess invocation: `$ISAAC_PATH/python.sh tools/physx_runtime_probe.py`. The probe script:

1. Reports Kit Python's version.
2. Tries to `import` each of: `pxr.Usd`, `pxr.UsdGeom`, `pxr.UsdPhysics`, `omni.usd`, `omni.physx`, `omni.physx.scripts`, `isaacsim.core.api`.
3. Tries three trivial pxr operations: create an in-memory stage, traverse it, define a `UsdGeom.Cube` prim.
4. Emits a JSON object to stdout.

The outer validator parses the JSON, classifies each import / capability as PASS / WARN / FAIL, and prints the summary.

Typical wall time: **10–30 s** (first invocation may JIT shaders). 60 s timeout.

### 2.3 `--deep` (reserved)

```bash
python isaac_factory/extensions/asset_validator/tools/runtime_b_validation.py --deep
```

Reserved for a future revision that boots `isaacsim.SimulationApp()` and runs a single physics step. Not implemented in this scaffold — booting Kit has GPU/license/network dependencies that don't fit a preparation pass. Returns a WARN to signal the gap.

---

## 3. Reading the output

Same format as `scripts/validate_runtime.sh`:

```
Runtime B bootstrap validator
workspace : /home/cap2/last
isaac path: /home/cap2/isaac-sim-5.0.0

── Isaac Sim install ──
  [PASS] Isaac Sim directory present: /home/cap2/isaac-sim-5.0.0
  [PASS] launcher present: python.sh
  ...

── Kit Python interpreter ──
  [PASS] Kit Python: Python 3.11.13

── PhysX extensions in extscache ──
  [PASS] extension present: omni.physx
  ...

──────────────────────────────────────────────────────────
 Runtime B validation summary
──────────────────────────────────────────────────────────
pass=N  warn=N  fail=N

FAIL
  • <if any>

result: PASS | PASS with warnings | FAIL
```

Exit code: `0` if no FAILs (WARNs allowed), `1` if any FAIL.

---

## 4. Common failures and what they mean

### `[FAIL] Isaac Sim directory missing`

Isaac Sim is not installed at the canonical path. Fix: install Isaac Sim 5.0 at `/home/cap2/isaac-sim-5.0.0/` per [runtime_policy.md §1](runtime_policy.md). All policies, scripts, and adapter code assume this path.

### `[FAIL] launcher missing: python.sh`

Isaac Sim install is corrupted or incomplete. Re-run the Omniverse Launcher install.

### `[WARN] unexpected Kit Python major.minor`

Kit Python is not 3.11.x. The Phase 1.B adapters target 3.11 specifically because that's what Isaac Sim 5.0 ships with. Skew here means a major Isaac Sim version upgrade has happened and the adapter targets need to be re-validated.

### `[WARN] extension not found in extscache: omni.physx`

PhysX extensions not present where expected. Could mean:
- Isaac Sim install with a non-default extension set.
- A custom build that re-locates extensions.

Workaround: most extensions also live under `$ISAAC_PATH/exts/`; the probe checks both locations.

### `[FAIL] probe produced no parsable JSON output`

`./python.sh` ran but didn't produce the expected JSON. Likely Kit emitted an error before the script ran. Re-run with the raw output:

```bash
$ISAAC_PATH/python.sh isaac_factory/extensions/asset_validator/tools/physx_runtime_probe.py
```

The last JSON object in the stdout is the report; everything before is Kit's startup noise.

### `[FAIL] Kit Python probe timed out (60s)`

Cooking, license check, or first-run shader JIT didn't finish in 60 s. Re-run; second invocation is usually < 5 s after caches warm up. If repeatedly times out, the `--probe` workload may be hitting an external dependency (Omniverse Hub auth, license server).

### `[FAIL] import omni.physx failed`

This is the central Phase 1.B blocker. Likely causes:

| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError: No module named 'omni'` | `python.sh` didn't set up paths; running `kit/python/bin/python3` directly instead |
| `ImportError: libcarb.so: cannot open` | `LD_LIBRARY_PATH` not set; either run via `python.sh` or set it manually |
| `RuntimeError: Failed to load Kit extension 'omni.physx'` | Extension cache corrupted; clear `$ISAAC_PATH/kit/cache/` and retry |

---

## 5. What success looks like

For a healthy install, `--probe` should produce:

```
── Isaac Sim install ──           : 4 PASS, 0 WARN, 0 FAIL
── Kit Python interpreter ──      : 1 PASS, 0 WARN, 0 FAIL
── PhysX extensions in extscache  : 6 PASS
── Probe script self-check ──     : 1 PASS
── PhysX adapter scaffolds ──     : 3 PASS
── Kit Python import probe ──     : Kit Python 3.11.13 + 7 imports PASS + 3 capabilities PASS

pass=25  warn=0  fail=0
result: PASS
```

Any FAIL blocks Phase 1.B adapter implementation work — the adapter can't be tested if its runtime isn't reachable.

---

## 6. After the probe passes

The next steps (each gated on an explicit user request — not auto-implemented):

1. **`PhysXContactSource`** — smallest PhysX adapter; least risk. Wires `OverlapValidator` to a real PhysX scene.
2. **`PhysXColliderInspector`** — adds cooking-error capture. Required for `COLLIDER.COOKING_FAILED`.
3. **`PhysXResetSimulator`** — heaviest; multi-cycle physics. Required for full `DeterministicResetValidator` end-to-end.

Each lands as a single PR — same shape as the two Phase 1 USD adapters that already shipped (see [grounding_validator.md](grounding_validator.md), [transform_validator.md](transform_validator.md)).

---

## 7. Constraints honored by the probe

- **Read-only.** Writes nothing to disk; exports nothing into the parent shell. The subprocess call to `python.sh` is contained.
- **No SimulationApp boot.** `--deep` is reserved but not implemented — the probe never instantiates `isaacsim.SimulationApp()`, so it doesn't load license, doesn't touch GPU beyond `nvidia-smi`, and doesn't open network sockets.
- **60-second hard timeout** on the subprocess. Failed probes don't hang the parent.
- **No new dependencies.** Only stdlib + `subprocess.run` from the outer; only `pxr` + `omni` (best-effort) inside the inner probe.

---

## 8. Cross-references

| Document | Role |
|---|---|
| [docs/runtime_b.md](runtime_b.md)                           | What Runtime B is and which validators depend on it |
| [docs/physx_runtime_constraints.md](physx_runtime_constraints.md) | What every Phase 1.B PhysX adapter must respect |
| [docs/runtime_policy.md](runtime_policy.md) §1, §4, §7      | Workspace runtime stack, activation, prohibitions |
| [docs/scene_validation_workflow.md](scene_validation_workflow.md) | Where Runtime B fits in the 8-step workflow |
| [scripts/validate_runtime.sh](../scripts/validate_runtime.sh) | Sibling host-level doctor (any profile) |
| [scripts/activate_factory_env.sh](../scripts/activate_factory_env.sh) | Profile dispatcher; `isaac` profile is the precondition for `--probe` |
