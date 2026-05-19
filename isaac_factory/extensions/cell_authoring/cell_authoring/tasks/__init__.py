"""cell_authoring.tasks — Phase 4A task abstraction layer.

A thin, additive layer over the validated Phase 3M/N/O/P manipulation
stack. The existing TrajectoryPlayer, config schema, and cell_01.yaml
are intentionally NOT modified — this package wraps them and exposes
composable Task / Profile / Executor / Validator / Replay abstractions.

The validated pick-and-place trajectory is the reference task; running
it through the new abstractions must produce results identical to
the validated harness output.

Public API:
  Tasks            — TaskDefinition, PickPlaceTask, TaskResult, TaskOutcome
  Sources/targets  — PickSource, PlaceTarget
  Strategies       — GraspStrategy, TransportStrategy, ReleaseStrategy
  Profiles         — TrajectoryProfile (SAFE / NOMINAL / AGGRESSIVE)
  Execution        — TaskExecutor
  State            — CellStateRegistry
  Validation       — UnifiedValidator, ValidationReport
  Replay           — ReplayPackage
"""

from .definitions import (
    TaskDefinition,
    TaskOutcome,
    TaskResult,
    PickPlaceTask,
    PickSource,
    PlaceTarget,
    GraspStrategy,
    TransportStrategy,
    ReleaseStrategy,
    PrismaticClampGrasp,
    JointSpaceLerpTransport,
    OpenJawRelease,
)
from .profiles import (
    TrajectoryProfile,
    ProfileSpec,
    apply_profile_to_trajectory,
)
from .registry import (
    CellStateRegistry,
    ObjectState,
    FixtureState,
    RobotState,
    TaskState,
    ContactState,
    RegistryStateError,
)
from .executor import TaskExecutor
from .validation import UnifiedValidator, ValidationReport
from .replay import ReplayPackage


__all__ = [
    "TaskDefinition",
    "TaskOutcome",
    "TaskResult",
    "PickPlaceTask",
    "PickSource",
    "PlaceTarget",
    "GraspStrategy",
    "TransportStrategy",
    "ReleaseStrategy",
    "PrismaticClampGrasp",
    "JointSpaceLerpTransport",
    "OpenJawRelease",
    "TrajectoryProfile",
    "ProfileSpec",
    "apply_profile_to_trajectory",
    "CellStateRegistry",
    "ObjectState",
    "FixtureState",
    "RobotState",
    "TaskState",
    "ContactState",
    "RegistryStateError",
    "TaskExecutor",
    "UnifiedValidator",
    "ValidationReport",
    "ReplayPackage",
]
