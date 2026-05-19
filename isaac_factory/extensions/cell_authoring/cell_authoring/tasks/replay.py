"""Phase 4A — ReplayPackage.

Standard portable artifact that bundles everything needed to review
or re-validate one task execution offline. Contents:

    summary.json        — TaskResult + ValidationReport + metadata
    task_definition.json — the TaskDefinition + profile id + seed
    cell_config.snapshot.yaml — copy of the cell config used
    registry_snapshot.json — CellStateRegistry at completion
    trace.jsonl (optional)  — per-tick telemetry, if provided
    video.mp4 (optional)    — replay video, if provided

The package is written as a directory by default; ``.write_tar()`` can
be used to produce a single .tar.gz for distribution. Determinism is
preserved — same TaskResult + same trace produces same package bytes
(modulo a header timestamp).
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import CellConfig
from .definitions import PickPlaceTask, TaskDefinition, TaskResult
from .profiles import TrajectoryProfile
from .validation import ValidationReport


class ReplayPackage:
    """Build + write a replay package directory (optionally tar it)."""

    def __init__(self,
                 *,
                 task:    TaskDefinition,
                 result:  TaskResult,
                 cell_cfg: CellConfig,
                 profile: TrajectoryProfile,
                 seed:    int,
                 validation_report: ValidationReport | None = None,
                 trace:   list[dict[str, Any]] | None = None,
                 video_path: Path | None = None) -> None:
        self.task    = task
        self.result  = result
        self.cell_cfg = cell_cfg
        self.profile = profile
        self.seed    = seed
        self.validation_report = validation_report
        self.trace   = trace
        self.video_path = video_path

    # ───────────── serialisers ─────────────
    def _task_to_dict(self) -> dict[str, Any]:
        """Convert a frozen-dataclass task into a plain dict (recursively
        handles strategy / source / target frozen dataclasses)."""
        def _conv(o):
            if dataclasses.is_dataclass(o) and not isinstance(o, type):
                return {k: _conv(v) for k, v in dataclasses.asdict(o).items()}
            if isinstance(o, (tuple, list)):
                return [_conv(x) for x in o]
            if isinstance(o, dict):
                return {k: _conv(v) for k, v in o.items()}
            return o
        return _conv(self.task)

    def _cell_cfg_to_yaml_str(self) -> str:
        """Read the on-disk cell config YAML rather than re-serialising
        the dataclass (the on-disk form is canonical)."""
        # We don't store the config path on the CellConfig dataclass.
        # The author's contract: the cell config is always loaded from
        # configs/cell_01.yaml relative to the workspace, so we read
        # that file as the snapshot.
        from pathlib import Path as _P
        ws = _P(__file__).resolve().parents[5]
        cfg_path = ws / "configs" / "cell_01.yaml"
        if cfg_path.is_file():
            return cfg_path.read_text()
        return f"# cell config snapshot unavailable: {cfg_path} not found"

    # ───────────── writer ─────────────
    def write_dir(self, out_dir: Path) -> Path:
        """Write the package to a directory. Returns the directory path."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # summary.json
        summary = {
            "package_kind":      "phase_4a_replay",
            "package_version":   "1.0.0",
            "created_at_utc":    datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "task_id":           self.task.task_id,
            "task_kind":         self.task.task_kind,
            "profile":           self.profile.value,
            "seed":              self.seed,
            "task_result":       self.result.to_dict(),
            "validation_report": self.validation_report.to_dict() if self.validation_report else None,
        }
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        # task_definition.json
        (out_dir / "task_definition.json").write_text(
            json.dumps(self._task_to_dict(), indent=2))

        # cell_config.snapshot.yaml
        (out_dir / "cell_config.snapshot.yaml").write_text(self._cell_cfg_to_yaml_str())

        # registry snapshot
        if self.result.registry_snapshot is not None:
            (out_dir / "registry_snapshot.json").write_text(
                json.dumps(self.result.registry_snapshot, indent=2, default=str))

        # trace.jsonl
        if self.trace is not None:
            with (out_dir / "trace.jsonl").open("w") as fh:
                for r in self.trace:
                    fh.write(json.dumps(r, default=str) + "\n")

        # video.mp4 — copy if provided
        if self.video_path is not None and self.video_path.is_file():
            shutil.copy2(self.video_path, out_dir / "video.mp4")

        return out_dir

    def write_tar(self, out_dir: Path, tar_path: Path | None = None) -> Path:
        """Write a tar.gz of the package. Returns the tar path."""
        pkg_dir = self.write_dir(out_dir)
        tar_path = tar_path or pkg_dir.with_suffix(".tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(pkg_dir, arcname=pkg_dir.name)
        return tar_path
