from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ContactPair:
    """A single contact between two USD prims, with measured penetration.

    `prim_a` is always lexicographically <= `prim_b` when constructed via
    :meth:`create`. Penetration depth is in meters; positive means overlap,
    zero means touching without overlap.

    `contact_normal` is the unit-length world-space contact normal pointing
    from ``prim_a`` to ``prim_b``. ``None`` when the source doesn't supply it
    (e.g., mock test data). Added 2026-05-18 to surface PhysX-extracted
    normals; backward-compatible (default ``None``, no equality changes for
    pre-existing pairs).
    """

    prim_a:             str
    prim_b:             str
    penetration_depth:  float
    contact_normal:     tuple[float, float, float] | None = None

    @classmethod
    def create(
        cls,
        prim_x: str,
        prim_y: str,
        penetration_depth: float,
        *,
        contact_normal: tuple[float, float, float] | None = None,
    ) -> "ContactPair":
        """Canonicalise prim ordering. If A↔B swap, flip the normal."""
        if prim_x <= prim_y:
            return cls(
                prim_a=prim_x, prim_b=prim_y,
                penetration_depth=float(penetration_depth),
                contact_normal=contact_normal,
            )
        flipped: tuple[float, float, float] | None = None
        if contact_normal is not None:
            flipped = (-contact_normal[0], -contact_normal[1], -contact_normal[2])
        return cls(
            prim_a=prim_y, prim_b=prim_x,
            penetration_depth=float(penetration_depth),
            contact_normal=flipped,
        )

    @property
    def is_self_contact(self) -> bool:
        return self.prim_a == self.prim_b


class ContactSource(Protocol):
    """Protocol for anything that can produce contact pairs for a stage.

    The real implementation lives in `adapters/physx_adapter.py` (deferred);
    tests provide an in-memory mock. The validator depends only on this
    interface, so it can run without Kit.
    """

    def setup(self, *, seed: int) -> None:
        """Initialize the underlying physics scene with a fixed seed."""

    def step(self) -> None:
        """Advance physics by one dt."""

    def query_contacts(self) -> Sequence[ContactPair]:
        """Return contacts present at the current step."""
