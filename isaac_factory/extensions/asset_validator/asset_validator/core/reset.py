"""Deterministic-reset data model.

The validator consumes a complete simulation report — produced offline by
the real adapter (deferred) or fabricated by tests. The data captures
multi-cycle reset behaviour described in
docs/asset_validator_acceptance.md §6:

  initial_state    – snapshot at t=0 (before any stepping)
  cycles[i]
    .after_step    – snapshot after `steps_per_cycle` physics steps
    .after_reset   – snapshot after World.reset() that follows
    .spawn_order   – order in which dynamic bodies were instantiated
    .contact_pairs_after_reset – any residual contacts at t=0 of the next cycle

The validator does not run physics itself; the simulator (real adapter or
test mock) is responsible for executing the cycles with fixed seeds and
returning this report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .contact import ContactPair


@dataclass(frozen=True)
class BodyState:
    """Pose + velocity of one dynamic rigid body at a moment in time."""

    prim_path:        str
    translation:      tuple[float, float, float]
    rotation_quat:    tuple[float, float, float, float]   # (w, x, y, z)
    linear_velocity:  tuple[float, float, float] = (0.0, 0.0, 0.0)
    angular_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class ResetCycle:
    """One step-and-reset cycle's observations."""

    cycle_index:               int                              # 1-based
    after_step_state:          tuple[BodyState, ...]            # post stepping
    after_reset_state:         tuple[BodyState, ...]            # post reset
    spawn_order:               tuple[str, ...]                  # prim paths in spawn order this cycle
    contact_pairs_after_reset: tuple[ContactPair, ...] = ()     # residual contacts at next t=0


@dataclass(frozen=True)
class ResetReport:
    """Full output of a deterministic-reset validation run."""

    determinism_flag_set:        bool                                 # PhysX useDeterministicSimulation
    seed_set:                    bool                                 # seeds configured before run
    initial_state:               tuple[BodyState, ...]                # at t=0
    initial_spawn_order:         tuple[str, ...]                      # ground-truth ordering
    cycles:                      tuple[ResetCycle, ...]               # length = n_cycles
    non_deterministic_authoring: tuple[str, ...]                = ()  # prim paths using random APIs


class ResetSimulator(Protocol):
    """Anything that can run + report a deterministic-reset validation cycle."""

    def get_reset_report(self) -> ResetReport: ...
