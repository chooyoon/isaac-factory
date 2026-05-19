# cell_authoring

Programmatic USD authoring for industrial cells, starting with `cell_01`.

**Runtime**: Runtime A (research profile) — conda `env_isaaclab`, Python 3.10,
`usd-core 26.3`, `pyyaml`. No Kit Python, no PhysX, no Isaac Sim imports.

## Quick start

```bash
source scripts/activate_factory_env.sh research
python -m cell_authoring.cli build \
    --config    configs/cell_01.yaml \
    --workspace /home/cap2/last
```

Output: `assets/cells/cell_01.usda` (path declared in the config).

## Phase status

* **Phase 1A (this sprint)**: stage scaffolding, PhysicsScene, dome light, floor.
* **Phase 1B**: class-prim templates (`_StaticProp`, `_DynamicPart`,
  `_RobotLink`, `_BeltSurface`).
* **Phase 1C**: environment props (safety cage, robot pedestal, work fixture,
  conveyor frames).
* **Phase 2+**: parts, machinery, robot — see `docs/sprints/cell_01.md` §5.

## Determinism contract

Same config + same code → byte-identical `.usda` (modulo USD's authoring
banner comment). The Phase A test suite asserts this with two consecutive
builds against the same input.

## Hierarchy convention

```
/World
    /World/PhysicsScene                       UsdPhysics.Scene + physxScene:* custom
    /World/Lights
        /World/Lights/DomeLight               UsdLux.DomeLight
    /World/Environment
        /World/Environment/Floor              Xform (groups visual + collider)
            /World/Environment/Floor/visual   UsdGeom.Cube (Imageable only)
            /World/Environment/Floor/collider UsdGeom.Cube + UsdPhysics.CollisionAPI
```

Detailed reasoning: see `cell_authoring/stage.py` module docstring.
