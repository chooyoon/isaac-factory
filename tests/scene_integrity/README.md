# tests/scene_integrity/

Scene-level integration tests for `isaac_factory/extensions/asset_validator/`.

## Purpose

Each test in this directory composes a **representative multi-prim scene**
(workbench + parts, assembly chain, conveyor, etc.) and asserts the
validator's behaviour at the scene level — which Issue codes fire, which
prims are correctly isolated, that ordering and severity are deterministic.

These tests complement — they do not replace — the per-validator unit tests
under `isaac_factory/extensions/asset_validator/tests/unit/`, which cover
every edge case of every threshold in isolation.

## Files

| File | Validator under test |
|---|---|
| [test_overlap_scenes.py](test_overlap_scenes.py)     | `OverlapValidator` |
| [test_transform_scenes.py](test_transform_scenes.py) | `TransformValidator` |
| [test_collider_scenes.py](test_collider_scenes.py)   | `ColliderValidator` |
| [test_grounding_scenes.py](test_grounding_scenes.py) | `GroundingValidator` |
| [test_reset_scenes.py](test_reset_scenes.py)         | `DeterministicResetValidator` |

## Runtime

All tests are **pure Python** — no pxr, no omni, no isaacsim. They use the
same in-memory mock inspectors that the extension's unit tests use.

Run in the `research` profile (conda `env_isaaclab`, Python 3.10):

```bash
source scripts/activate_factory_env.sh research
python -m pytest tests/scene_integrity/ -v
```

## What "scene-level" means

A scene-level test typically:

1. Builds 3–8 prims (rigid bodies + colliders, or xformable prims with
   varied transforms) representing a small slice of a real factory cell.
2. Runs one validator against the resulting mock inspector.
3. Asserts: (a) the expected set of Issue codes is present; (b) prim
   paths in each Issue point at the right offenders; (c) severity
   ordering matches policy; (d) clean prims produce no spurious issues.

This is the same level of coverage that future regression tests against
real `.usda` fixtures (in `isaac_factory/extensions/asset_validator/tests/regression/`)
will provide, with the simulator/inspector adapter doing the heavy lifting
once it exists.
