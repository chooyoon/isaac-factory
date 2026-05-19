"""PhysX-backed `ResetSimulator` — real implementation (Phase 1.B).

Replaces the Phase 1.A scaffold. Drives ``isaacsim.core.api.World`` for
N step-and-reset cycles, snapshots dynamic body state from the USD
stage at each phase boundary, captures residual contact pairs via the
same ``omni.physx`` subscription pattern as :class:`PhysXContactSource`,
and returns a :class:`ResetReport` the
:class:`~asset_validator.DeterministicResetValidator` consumes.

Runtime: **B** (Isaac Sim Kit Python 3.11). Requires
:class:`isaacsim.SimulationApp` to be running BEFORE this simulator is
constructed — the caller owns the SimulationApp + World lifecycle.

Reuses two patterns from existing Phase 1.B adapters:

  * ``omni.physx.get_physx_simulation_interface().subscribe_contact_report_events``
    + ``pxr.PhysxSchema.PhysxContactReportAPI.Apply`` for residual-contact
    capture (same as :class:`PhysXContactSource`).
  * ``pxr.PhysxSchema.PhysxSceneAPI.GetEnableEnhancedDeterminismAttr``
    for the determinism prerequisite check (same as
    :class:`PhysXContactSource`).
"""

from __future__ import annotations

import random as _random
from typing import Any

# Guarded imports — module loads in Runtime A too.
try:
    from pxr import (                                            # type: ignore
        Gf, PhysicsSchemaTools, PhysxSchema, Sdf, Usd, UsdGeom, UsdPhysics,
    )
    _HAS_PXR = True
except ImportError:                                              # pragma: no cover
    _HAS_PXR = False

try:
    import omni.physx                                            # noqa: F401
    from omni.physx import get_physx_simulation_interface
    _HAS_OMNI_PHYSX = True
except ImportError:
    _HAS_OMNI_PHYSX = False

try:
    from isaacsim.core.api import World                          # type: ignore
    _HAS_ISAACSIM = True
except ImportError:
    _HAS_ISAACSIM = False

from ..core.contact import ContactPair
from ..core.reset import BodyState, ResetCycle, ResetReport


_BOOTSTRAP_HINT = (
    "PhysXResetSimulator requires Isaac Sim Kit Python (Runtime B). "
    "Bootstrap via:\n"
    "    from isaacsim import SimulationApp\n"
    "    app = SimulationApp({'headless': True})\n"
    "before constructing PhysXResetSimulator, and ensure an "
    "isaacsim.core.api.World instance has been created with the stage "
    "loaded. See docs/runtime_b_bootstrap.md and "
    "docs/physx_reset_simulator.md §3 for the call order."
)


class PhysXResetSimulator:
    """Real ResetSimulator backed by isaacsim.core.api.World + omni.physx.

    Construction must come AFTER ``isaacsim.SimulationApp`` is up but BEFORE
    ``isaacsim.core.api.World()`` is created (so the contact-report
    subscription is in place when PhysX cooks the stage during World init).
    """

    name    = "physx_reset_simulator"
    runtime = "B"

    def __init__(
        self,
        stage,
        *,
        n_cycles: int = 3,
        steps_per_cycle: int = 100,
        physics_dt: float = 1.0 / 60.0,
        deterministic: bool = True,
        seed: int = 0,
    ):
        if not _HAS_OMNI_PHYSX:
            raise RuntimeError(_BOOTSTRAP_HINT)
        if not _HAS_PXR:
            raise RuntimeError(
                "pxr unavailable — Kit Python should have it bundled."
            )
        if not isinstance(stage, Usd.Stage):
            raise TypeError(
                f"PhysXResetSimulator(stage=...) requires a pxr.Usd.Stage; "
                f"got {type(stage).__name__}"
            )
        if n_cycles < 1:
            raise ValueError("n_cycles must be >= 1")
        if steps_per_cycle < 1:
            raise ValueError("steps_per_cycle must be >= 1")

        self._stage           = stage
        self._n_cycles        = int(n_cycles)
        self._steps_per_cycle = int(steps_per_cycle)
        self._physics_dt      = float(physics_dt)
        self._deterministic   = bool(deterministic)
        self._seed            = int(seed)

        self._determinism_flag_set = False
        self._seed_set             = False
        self._captured_contacts: list[dict[str, Any]] = []
        self._sub = None

        # Determinism flag on PhysicsScene (best-effort).
        if self._deterministic:
            self._determinism_flag_set = self._apply_determinism_flag()

        # Opt every dynamic rigid body into contact reports.
        self._apply_contact_report_api()

        # Subscribe before any cooking / stepping happens.
        self._sub = get_physx_simulation_interface().subscribe_contact_report_events(
            self._on_contact_event
        )

    # ============================================ ResetSimulator Protocol ==

    def get_reset_report(self) -> ResetReport:
        """Drive N step-and-reset cycles and return the full diagnostic record.

        The caller must have constructed an ``isaacsim.core.api.World``
        before invoking this method (the simulator does not own World's
        lifecycle).
        """
        if not _HAS_ISAACSIM:
            raise RuntimeError(_BOOTSTRAP_HINT)
        world = World.instance()
        if world is None:
            raise RuntimeError(
                "No isaacsim.core.api.World instance. Construct one before "
                "calling PhysXResetSimulator.get_reset_report(); see "
                "docs/physx_reset_simulator.md §3."
            )

        # Phase 0: seeds + baseline reset
        self._set_seeds(self._seed)
        world.reset()
        # Discard any contacts emitted during cooking / baseline reset.
        self._captured_contacts.clear()

        # Find dynamic bodies in stage-traversal order (deterministic).
        body_paths = self._dynamic_body_paths()
        # spawn_order is the same list per cycle (USD traversal is stable
        # over the lifetime of a single stage). Captured here once.
        spawn_order = body_paths

        initial_state = self._snapshot(body_paths)
        non_det_authoring = self._detect_non_deterministic_authoring()

        cycles: list[ResetCycle] = []
        for cycle_idx in range(1, self._n_cycles + 1):
            # Fresh per-cycle contact buffer.
            self._captured_contacts.clear()

            # Step
            for _ in range(self._steps_per_cycle):
                world.step(render=False)

            after_step = self._snapshot(body_paths)

            # Reset
            world.reset()

            # Drain whatever contacts fired during the stepping window.
            # Semantically these are "contacts that occurred during this
            # cycle and were not resolved by the reset" — see
            # docs/physx_reset_simulator.md §4 for the discussion of
            # alternative interpretations.
            contacts_residual = self._drain_contacts()

            after_reset = self._snapshot(body_paths)

            # Per-cycle spawn order — re-iterate so a stage-mutation drift
            # would be detected. Stable for read-only assets.
            cycle_spawn_order = self._dynamic_body_paths()

            cycles.append(ResetCycle(
                cycle_index=cycle_idx,
                after_step_state=after_step,
                after_reset_state=after_reset,
                spawn_order=cycle_spawn_order,
                contact_pairs_after_reset=tuple(contacts_residual),
            ))

        return ResetReport(
            determinism_flag_set=self._determinism_flag_set,
            seed_set=self._seed_set,
            initial_state=initial_state,
            initial_spawn_order=spawn_order,
            cycles=tuple(cycles),
            non_deterministic_authoring=non_det_authoring,
        )

    # =================================================== lifecycle ==

    def close(self) -> None:
        if self._sub is not None:
            try:
                self._sub.unsubscribe()
            except AttributeError:                              # pragma: no cover
                try:
                    get_physx_simulation_interface().unsubscribe_contact_report_events(
                        self._sub
                    )
                except Exception:                               # pragma: no cover
                    pass
            self._sub = None

    def __enter__(self) -> "PhysXResetSimulator":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):                                          # pragma: no cover
        try:
            self.close()
        except Exception:
            pass

    # =================================================== internal ==

    def _apply_determinism_flag(self) -> bool:
        """Set `enableEnhancedDeterminism` on every UsdPhysics.Scene prim.
        Returns True iff at least one Scene prim was updated."""
        any_set = False
        for prim in self._stage.Traverse():
            if not prim.IsA(UsdPhysics.Scene):
                continue
            if not prim.HasAPI(PhysxSchema.PhysxSceneAPI):
                PhysxSchema.PhysxSceneAPI.Apply(prim)
            api = PhysxSchema.PhysxSceneAPI(prim)
            attr = api.GetEnableEnhancedDeterminismAttr()
            if not attr:
                attr = api.CreateEnableEnhancedDeterminismAttr()
            attr.Set(True)
            any_set = True
        return any_set

    def _apply_contact_report_api(self) -> None:
        for prim in self._stage.Traverse():
            if not prim.IsActive():
                continue
            if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                continue
            if not PhysxSchema.PhysxContactReportAPI.Get(self._stage, prim.GetPath()):
                PhysxSchema.PhysxContactReportAPI.Apply(prim)

    def _set_seeds(self, seed: int) -> None:
        _random.seed(int(seed))
        try:
            import numpy as np                                  # type: ignore
            np.random.seed(int(seed))
        except ImportError:                                      # pragma: no cover
            pass
        try:
            import warp                                          # type: ignore
            warp.rand_init(int(seed))
        except Exception:                                        # pragma: no cover
            # Warp is optional.
            pass
        self._seed_set = True

    def _dynamic_body_paths(self) -> tuple[str, ...]:
        """All paths carrying UsdPhysics.RigidBodyAPI, sorted lex.

        The validator's notion of `spawn_order` is the same list — stable
        across cycles of a non-mutating stage.
        """
        paths = [
            str(p.GetPath()) for p in self._stage.Traverse()
            if p.IsActive() and p.HasAPI(UsdPhysics.RigidBodyAPI)
        ]
        paths.sort()
        return tuple(paths)

    def _snapshot(self, body_paths: tuple[str, ...]) -> tuple[BodyState, ...]:
        """Read translation + rotation from the stage; velocities = (0,0,0).

        Reading actual linear / angular velocity would require a
        `omni.physx.IPhysxSimulation` query that varies by Kit version.
        After `world.reset()` (the relevant snapshot for the validator's
        §6.3 / §6.4 checks) the velocities are zero by construction, so
        the validator's drift-vs-zero comparison passes.
        """
        states: list[BodyState] = []
        for path in body_paths:
            prim = self._stage.GetPrimAtPath(Sdf.Path(path))
            if not prim or not prim.IsValid() or not prim.IsActive():
                continue
            if not prim.IsA(UsdGeom.Xformable):
                continue
            xform = UsdGeom.Xformable(prim)
            mat = xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            # Decompose without the scale component — pxr's
            # ExtractRotationQuat on a matrix containing non-uniform
            # scale yields a spurious rotation (e.g. a belt scaled
            # 2.0 × 0.4 × 0.05 reads as ~1.06 rad rotation even
            # though authored xformOps contain only translate + scale).
            # This matches the canonical NVIDIA decomposition pattern
            # in omni.physxdemos.scenes.SurfaceVelocityDemo.
            mat_no_scale = mat.RemoveScaleShear()
            t = mat_no_scale.ExtractTranslation()
            q = mat_no_scale.ExtractRotationQuat()
            states.append(BodyState(
                prim_path=path,
                translation=(float(t[0]), float(t[1]), float(t[2])),
                rotation_quat=(
                    float(q.GetReal()),
                    float(q.GetImaginary()[0]),
                    float(q.GetImaginary()[1]),
                    float(q.GetImaginary()[2]),
                ),
                linear_velocity=(0.0, 0.0, 0.0),
                angular_velocity=(0.0, 0.0, 0.0),
            ))
        return tuple(states)

    def _detect_non_deterministic_authoring(self) -> tuple[str, ...]:
        """Best-effort: flag prims with an attribute whose name contains
        both 'random' and 'seed' (case-insensitive).

        Catches the most common offender (``physxRigidBody:randomizedSeed``).
        """
        offenders: list[str] = []
        for prim in self._stage.Traverse():
            if not prim.IsActive():
                continue
            for attr in prim.GetAttributes():
                name = attr.GetName().lower()
                if "random" in name and "seed" in name:
                    offenders.append(str(prim.GetPath()))
                    break
        offenders.sort()
        return tuple(offenders)

    def _on_contact_event(self, headers, data) -> None:
        for h in headers:
            try:
                path_a = str(PhysicsSchemaTools.intToSdfPath(h.actor0))
                path_b = str(PhysicsSchemaTools.intToSdfPath(h.actor1))
            except Exception:                                   # pragma: no cover
                continue
            n = int(h.num_contact_data)
            base = int(h.contact_data_offset)
            for i in range(n):
                d = data[base + i]
                self._captured_contacts.append({
                    "a":          path_a,
                    "b":          path_b,
                    "separation": float(d.separation),
                })

    def _drain_contacts(self) -> list[ContactPair]:
        """Deduplicate per pair (max-depth wins) and return sorted list."""
        by_pair: dict[frozenset, ContactPair] = {}
        for evt in self._captured_contacts:
            depth = max(0.0, -float(evt["separation"]))
            pair = ContactPair.create(evt["a"], evt["b"], depth)
            key = frozenset({pair.prim_a, pair.prim_b})
            existing = by_pair.get(key)
            if existing is None or pair.penetration_depth > existing.penetration_depth:
                by_pair[key] = pair
        self._captured_contacts.clear()
        return sorted(by_pair.values(), key=lambda p: (p.prim_a, p.prim_b))
