from __future__ import annotations

from dataclasses import dataclass, field

from .collider  import ColliderInspector
from .contact   import ContactSource
from .grounding import GroundingInspector
from .reset     import ResetSimulator
from .stage     import StageInspector
from ..thresholds.schema import AcceptanceCriteria


@dataclass(frozen=True)
class ValidationContext:
    """State shared with validators during a single pipeline run.

    All inspector handles are optional so that a validator needing only one
    of them can be exercised without the others. Each validator is
    responsible for checking that its own required handles are present and
    emitting a clear FAIL Issue if not.
    """

    asset_uri:              str
    criteria:               AcceptanceCriteria
    contact_source:         ContactSource | None        = None
    stage_inspector:        StageInspector | None       = None
    collider_inspector:     ColliderInspector | None    = None
    grounding_inspector:    GroundingInspector | None   = None
    reset_simulator:        ResetSimulator | None       = None
    allowed_contact_pairs:  frozenset[frozenset[str]]   = field(default_factory=frozenset)
    seed:                   int                         = 0
