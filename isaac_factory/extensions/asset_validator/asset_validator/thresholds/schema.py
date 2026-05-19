from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OverlapThresholds:
    """See docs/asset_validator_acceptance.md §1."""

    pen_depth_max_m:           float = 1.0e-3   # 1.0 mm (rule 1.1)
    pen_depth_max_fit_m:       float = 1.0e-4   # 0.1 mm (rule 1.2)
    convergence_max_steps:     int   = 5        # rule 1.4 (not enforced in v1)
    physics_settle_pre_steps:  int   = 5        # internal warmup before measurement


@dataclass(frozen=True)
class TransformThresholds:
    """See docs/asset_validator_acceptance.md §2.

    Field names mirror the acceptance-doc threshold names where possible so
    the YAML mirror (when written) maps 1:1.
    """

    # Rule 2.3
    min_scale_magnitude:        float = 1.0e-3
    # Rule 2.4
    max_scale_magnitude:        float = 1.0e+3
    # Rule 2.6
    quaternion_magnitude_min:   float = 0.999
    quaternion_magnitude_max:   float = 1.001
    # Rule 2.7
    rotation_orthogonality_eps: float = 1.0e-4
    # Rule 2.8
    max_translation_magnitude_m: float = 1.0e+6

    # Heuristic: flag prims whose local translate.z exceeds this height.
    # NOT a substitute for GroundingValidator — set to None to disable.
    # Default is intentionally permissive (100 m): catches obviously-floating
    # placements without false-positives on legitimate overhead structures.
    floating_heuristic_z_m: float | None = 100.0


@dataclass(frozen=True)
class ColliderThresholds:
    """See docs/asset_validator_acceptance.md §3."""

    # §3.3 — approximations allowed on dynamic (non-kinematic) rigid bodies.
    dynamic_allowed_approximations: tuple[str, ...] = (
        "box", "sphere", "capsule", "cylinder",
        "convexHull", "convexDecomposition",
    )
    # §3.4 — convex decomposition hull count thresholds.
    convex_decomp_hull_warn:  int   = 32
    convex_decomp_hull_fail:  int   = 64
    # §3.5 — max ratio of collider AABB extent to visual AABB extent per axis.
    aabb_ratio_max:           float = 1.10
    # §3.9 — rigid body mass sanity bounds.
    mass_min_kg:              float = 1.0e-3
    mass_max_kg:              float = 1.0e+5
    # §3.10 — mass vs density*volume agreement.
    mass_density_tolerance:   float = 0.10
    # Stability heuristics (user-requested "unstable collider geometry").
    # min_aabb_extent_m: colliders with any axis thinner than this can
    # generate unstable contacts in PhysX.
    min_aabb_extent_m:        float = 1.0e-4   # 0.1 mm
    # max_aabb_aspect_ratio: longest-axis / shortest-axis above this is
    # likely sliver geometry (cooking instability + contact jitter).
    max_aabb_aspect_ratio:    float = 1000.0


@dataclass(frozen=True)
class GroundingThresholds:
    """See docs/asset_validator_acceptance.md §5.

    Defaults mirror §5 where applicable, with separate tolerances for the
    floating and buried sides of the gap (the acceptance doc collapses
    these into a single AABB-to-support distance; this validator reports
    them as distinct codes per the user's pipeline).
    """

    # Object's AABB-bottom may sit at most this far ABOVE the support.
    floating_tolerance_m:  float = 5.0e-3   # 5 mm (acceptance §5.2 ground_tolerance)
    # Object's AABB-bottom may sit at most this far BELOW the support
    # (i.e. penetration into the support surface).
    buried_tolerance_m:    float = 5.0e-3   # 5 mm; mirrors floating for symmetry


@dataclass(frozen=True)
class DeterministicResetThresholds:
    """See docs/asset_validator_acceptance.md §6."""

    # §6.1 / 6.2 — pose drift after reset vs initial.
    translation_tolerance_m: float = 1.0e-5
    rotation_tolerance_rad:  float = 1.0e-4
    # §6.3 / 6.4 — velocity at reset must be zero within tolerance.
    velocity_tolerance_m_per_s:           float = 1.0e-6
    angular_velocity_tolerance_rad_per_s: float = 1.0e-6
    # §6.7 — inter-cycle pose match (after_step of cycle i vs cycle 1).
    cycle_variance_translation_m: float = 1.0e-5
    cycle_variance_rotation_rad:  float = 1.0e-4
    # User: "no overlap after reset". Max penetration depth tolerated in
    # the residual contact-pair list reported by the simulator at t=0
    # of the next cycle.
    max_penetration_after_reset_m: float = 1.0e-6
    # §6.5 / 6.6 — make these mandatory by default.
    require_determinism_flag: bool = True
    require_seed:             bool = True


@dataclass(frozen=True)
class AcceptanceCriteria:
    """Root threshold container.

    New thresholds are appended as later validators are implemented; existing
    fields are not renamed or removed (semver-stable surface).
    """

    overlap:            OverlapThresholds            = field(default_factory=OverlapThresholds)
    transform:          TransformThresholds          = field(default_factory=TransformThresholds)
    collider:           ColliderThresholds           = field(default_factory=ColliderThresholds)
    grounding:          GroundingThresholds          = field(default_factory=GroundingThresholds)
    deterministic_reset: DeterministicResetThresholds = field(default_factory=DeterministicResetThresholds)
