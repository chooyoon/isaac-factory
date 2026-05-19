from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .severity import Severity


_FrozenDict = tuple[tuple[str, float], ...]


def _freeze(d: Mapping[str, float] | None) -> _FrozenDict | None:
    if d is None:
        return None
    return tuple(sorted((str(k), float(v)) for k, v in d.items()))


@dataclass(frozen=True)
class Issue:
    """Single finding emitted by a validator.

    `metric` and `threshold` are stored as sorted tuples of (key, value) pairs
    so the dataclass stays frozen and hashable. Use :meth:`metric_dict` /
    :meth:`threshold_dict` to round-trip to ``dict``.
    """

    code:       str
    severity:   Severity
    message:    str
    prim_paths: tuple[str, ...]      = ()
    metric:     _FrozenDict | None   = None
    threshold:  _FrozenDict | None   = None
    validator:  str                  = ""

    # ---- constructors ------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        code:       str,
        severity:   Severity,
        message:    str,
        prim_paths: Iterable[str]               = (),
        metric:     Mapping[str, float] | None  = None,
        threshold:  Mapping[str, float] | None  = None,
        validator:  str                         = "",
    ) -> "Issue":
        return cls(
            code=code,
            severity=Severity(severity),
            message=message,
            prim_paths=tuple(prim_paths),
            metric=_freeze(metric),
            threshold=_freeze(threshold),
            validator=validator,
        )

    # ---- accessors ---------------------------------------------------------

    def metric_dict(self) -> dict[str, float]:
        return dict(self.metric or ())

    def threshold_dict(self) -> dict[str, float]:
        return dict(self.threshold or ())

    # ---- serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "code":       self.code,
            "severity":   self.severity.name,
            "message":    self.message,
            "prim_paths": list(self.prim_paths),
            "metric":     self.metric_dict(),
            "threshold":  self.threshold_dict(),
            "validator":  self.validator,
        }

    # ---- ordering ----------------------------------------------------------

    @staticmethod
    def sort_key(issue: "Issue") -> tuple:
        # Highest severity first, then code, then prims, then validator name.
        return (-int(issue.severity), issue.code, issue.prim_paths, issue.validator)
