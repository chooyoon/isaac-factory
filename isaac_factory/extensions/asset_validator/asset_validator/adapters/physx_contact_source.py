"""PhysX-backed `ContactSource` — real implementation (Phase 1.B).

Replaces the Phase 1.A scaffold. Exposes contacts captured by
``omni.physx``'s contact-report callback as the
:class:`~asset_validator.core.contact.ContactPair` records the
:class:`~asset_validator.OverlapValidator` consumes.

Runtime: **B** (Isaac Sim Kit Python 3.11). Requires
:class:`isaacsim.SimulationApp` to be running BEFORE this adapter is
constructed — the caller owns SimulationApp's lifecycle (per the
"no SimulationApp abstraction layer" constraint).

Usage outline::

    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True})
    try:
        from isaacsim.core.api import World
        from asset_validator.adapters.physx_contact_source import PhysXContactSource

        import omni.usd
        omni.usd.get_context().open_stage("/path/to/asset.usd")
        world = World()
        source = PhysXContactSource(stage=world.stage)
        source.setup(seed=0)
        for _ in range(5):
            source.step()
        contacts = source.query_contacts()
    finally:
        app.close()

Module imports are guarded so the file loads in Runtime A too; the
:meth:`__init__` raises with a bootstrap hint if PhysX isn't reachable.
"""

from __future__ import annotations

import random
from typing import Any, Iterable, Sequence

# All Kit-side imports are guarded — module loads in Runtime A for IDE /
# design-doc reference. Instantiation fails loudly outside Runtime B.
try:
    from pxr import PhysxSchema, PhysicsSchemaTools, Sdf, Usd, UsdPhysics  # type: ignore
    _HAS_PXR = True
except ImportError:                                            # pragma: no cover
    _HAS_PXR = False

try:
    import omni.physx                                          # noqa: F401
    from omni.physx import get_physx_simulation_interface
    _HAS_OMNI_PHYSX = True
except ImportError:
    _HAS_OMNI_PHYSX = False

try:
    from isaacsim.core.api import World                        # type: ignore
    _HAS_ISAACSIM = True
except ImportError:
    _HAS_ISAACSIM = False

from ..core.contact import ContactPair


_BOOTSTRAP_HINT = (
    "PhysXContactSource requires Isaac Sim Kit Python (Runtime B). "
    "Bootstrap via:\n"
    "    from isaacsim import SimulationApp\n"
    "    app = SimulationApp({'headless': True})\n"
    "before constructing PhysXContactSource. See docs/runtime_b_bootstrap.md."
)


class PhysXContactSource:
    """Real ContactSource backed by isaacsim.core.api.World + omni.physx contact reports.

    Lifecycle (caller-driven):

      1. SimulationApp created
      2. PhysXContactSource(stage=...)  — applies ContactReportAPI, subscribes
      3. setup(seed=N)                  — seeds RNGs + resets world
      4. step()  × M                    — advances physics by M ticks; events accrue
      5. query_contacts()               — drains the per-pair maxima and returns sorted
      6. close()  or  __exit__          — unsubscribes from the contact-report callback
    """

    name = "physx_contact_source"
    runtime = "B"

    def __init__(
        self,
        stage,
        *,
        physics_dt: float = 1.0 / 60.0,
        deterministic: bool = True,
    ):
        if not _HAS_OMNI_PHYSX:
            raise RuntimeError(_BOOTSTRAP_HINT)
        if not _HAS_PXR:
            raise RuntimeError(
                "pxr unavailable — Kit Python should have it bundled. "
                "See docs/runtime_b.md for the environment expectations."
            )

        if not isinstance(stage, Usd.Stage):
            raise TypeError(
                f"PhysXContactSource(stage=...) requires a pxr.Usd.Stage; "
                f"got {type(stage).__name__}"
            )

        self._stage = stage
        self._physics_dt = physics_dt
        self._deterministic = deterministic

        # Captured raw events between query_contacts() calls.
        # Each entry: {"a": str, "b": str, "separation": float, "normal": tuple[float,float,float]}
        self._captured: list[dict[str, Any]] = []
        self._sub = None

        # Enable per-prim contact reports on every dynamic rigid body.
        self._apply_contact_report_api()

        # If the user authored a UsdPhysics.Scene, set the determinism flag now.
        if self._deterministic:
            self._enable_scene_determinism()

        # Subscribe before the first physics step so we never miss events.
        self._sub = get_physx_simulation_interface().subscribe_contact_report_events(
            self._on_contact_event
        )

    # ===================================================== Protocol API ==

    def setup(self, *, seed: int) -> None:
        """Seed RNGs + reset the (caller's) World so cooking is fresh."""
        random.seed(int(seed))
        try:
            import numpy as np                                  # type: ignore
            np.random.seed(int(seed))
        except ImportError:                                      # pragma: no cover
            pass

        # If a World exists, reset it to (a) re-cook with the latest
        # ContactReportAPIs we applied, (b) clear any prior simulation state.
        if _HAS_ISAACSIM:
            inst = World.instance()
            if inst is not None:
                inst.reset()

        # Drop any contacts captured during cooking — they don't belong to
        # the measurement window.
        self._captured.clear()

    def step(self) -> None:
        """Advance the World by one physics_dt."""
        if not _HAS_ISAACSIM:
            raise RuntimeError(_BOOTSTRAP_HINT)
        inst = World.instance()
        if inst is None:
            raise RuntimeError(
                "No isaacsim.core.api.World instance. Construct one before "
                "calling PhysXContactSource.step(); see docs/physx_contact_source.md §3."
            )
        inst.step(render=False)

    def query_contacts(self) -> Sequence[ContactPair]:
        """Drain the captured-event buffer into deduplicated ContactPair records.

        Multiple contact-data points per pair (one per touching feature) are
        collapsed to the **maximum** penetration depth observed. The chosen
        contact's normal is also surfaced. Output is sorted by
        (prim_a, prim_b) for deterministic downstream comparison.
        """
        by_pair: dict[frozenset, ContactPair] = {}
        for evt in self._captured:
            depth = max(0.0, -float(evt["separation"]))
            pair = ContactPair.create(
                evt["a"],
                evt["b"],
                penetration_depth=depth,
                contact_normal=evt["normal"],
            )
            key = frozenset({pair.prim_a, pair.prim_b})
            existing = by_pair.get(key)
            if existing is None or pair.penetration_depth > existing.penetration_depth:
                by_pair[key] = pair
        self._captured.clear()
        return sorted(by_pair.values(), key=lambda p: (p.prim_a, p.prim_b))

    def close(self) -> None:
        """Unsubscribe from the PhysX contact-report callback."""
        if self._sub is not None:
            # Newer Kit returns a Subscription with .unsubscribe();
            # older returns a SubscriptionId. Be defensive.
            try:
                self._sub.unsubscribe()
            except AttributeError:                              # pragma: no cover
                # Fallback for older API surfaces.
                try:
                    get_physx_simulation_interface().unsubscribe_contact_report_events(
                        self._sub
                    )
                except Exception:                               # pragma: no cover
                    pass
            self._sub = None

    def __enter__(self) -> "PhysXContactSource":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):                                          # pragma: no cover
        # Best-effort; explicit close() preferred.
        try:
            self.close()
        except Exception:
            pass

    # ===================================================== internal ==

    def _apply_contact_report_api(self) -> None:
        """Enable contact reports on every dynamic rigid body in the stage.

        Without this, PhysX fires no events even though the simulation
        runs — `PhysxContactReportAPI` is opt-in per prim.
        """
        for prim in self._stage.Traverse():
            if not prim.IsActive():
                continue
            if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                continue
            if not PhysxSchema.PhysxContactReportAPI.Get(self._stage, prim.GetPath()):
                PhysxSchema.PhysxContactReportAPI.Apply(prim)

    def _enable_scene_determinism(self) -> None:
        """Set `enableEnhancedDeterminism` on every UsdPhysics.Scene prim.

        No-op if the asset doesn't define a scene — the caller's World()
        creates a default scene without this flag, which is fine for
        non-determinism-sensitive use; the OverlapValidator does not
        require strict determinism (that's DeterministicResetValidator).
        """
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

    def _on_contact_event(self, headers, data) -> None:
        """Subscriber callback. Runs synchronously inside `World.step()`.

        ``headers`` is a Vt.Array of ContactEventHeader; ``data`` is a flat
        array of ContactData indexed by ``header.contact_data_offset``.
        """
        for h in headers:
            try:
                path_a = str(PhysicsSchemaTools.intToSdfPath(h.actor0))
                path_b = str(PhysicsSchemaTools.intToSdfPath(h.actor1))
            except Exception:                                   # pragma: no cover
                # Defensive — unresolvable handles skipped silently.
                continue

            n = int(h.num_contact_data)
            base = int(h.contact_data_offset)
            for i in range(n):
                d = data[base + i]
                normal_obj = d.normal
                # carb.Float3 exposes .x/.y/.z; coerce to plain floats.
                normal = (float(normal_obj.x), float(normal_obj.y), float(normal_obj.z))
                self._captured.append({
                    "a":          path_a,
                    "b":          path_b,
                    "separation": float(d.separation),
                    "normal":     normal,
                })
