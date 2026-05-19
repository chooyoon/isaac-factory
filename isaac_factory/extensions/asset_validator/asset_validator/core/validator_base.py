from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from .context import ValidationContext
from .issue   import Issue
from ..thresholds.schema import AcceptanceCriteria


class Validator(ABC):
    """Abstract base for all validators.

    Concrete validators set the two class-level attributes and implement
    :meth:`run`. The Pipeline (not implemented in this turn) is responsible
    for selecting and ordering validators by phase.
    """

    name:  ClassVar[str]
    phase: ClassVar[Literal["static", "dynamic"]]

    def __init__(self, criteria: AcceptanceCriteria) -> None:
        self.criteria = criteria

    @abstractmethod
    def run(self, ctx: ValidationContext) -> list[Issue]: ...
