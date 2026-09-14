"""Persisted YOLO pipeline run history.

The YOLO pipeline runs from the browser and regularly takes over an hour, so
whoever started it is usually away from the machine when a stage fails. The
error toast is long gone by the time they come back, which used to leave no
record at all of where the run stopped. Every stage transition is therefore
written under the project as `data/projects/{script_id}/yolo/runs.json`,
giving a durable answer to "which stage failed, why, and where did the time
go" that survives an AFK return, a reload, or an app restart.

The browser owns the run state and PUTs a full snapshot on each transition.
Storing whole snapshots rather than merging per-stage deltas keeps the writes
idempotent — a retried or out-of-order PUT cannot corrupt the record.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from config import DATA_DIR

logger = logging.getLogger(__name__)

# Only the last few runs are useful; older ones are noise on disk.
MAX_RUNS = 5

SAFE_SCRIPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

YoloStageStatus = Literal["pending", "running", "done", "skipped", "failed", "cancelled"]
YoloRunStatus = Literal["running", "completed", "completed_with_failures", "halted", "cancelled"]


def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO timestamp, returning None rather than raising on junk."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class YoloStageRecord(BaseModel):
    """One stage of a YOLO run — what it was, how long it took, how it ended."""

    MAX_ERROR_CHARS: ClassVar[int] = 1000
    MAX_DETAIL_CHARS: ClassVar[int] = 300

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    status: YoloStageStatus = "pending"
    started_at: str | None = Field(default=None, max_length=64)
    ended_at: str | None = Field(default=None, max_length=64)
    attempts: int = Field(default=0, ge=0, le=100)
    error: str | None = None
    detail: str | None = None

    @field_validator("error")
    @classmethod
    def _truncate_error(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value[: cls.MAX_ERROR_CHARS]

    @field_validator("detail")
    @classmethod
    def _truncate_detail(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value[: cls.MAX_DETAIL_CHARS]

    @property
    def duration_seconds(self) -> float | None:
        """Wall-clock seconds the stage took, or None while it is still open."""
        started = _parse_iso(self.started_at)
        ended = _parse_iso(self.ended_at)
        if started is None or ended is None:
            return None
        # Both ends are written by the same clock in the same format, so either
        # both carry a tz offset or neither does; a mismatch means junk input.
        if (started.tzinfo is None) != (ended.tzinfo is None):
            return None
        return max(0.0, (ended - started).total_seconds())


class YoloRunRecord(BaseModel):
    """A single YOLO run: its stages, in pipeline order, and its outcome."""

    MAX_STAGES: ClassVar[int] = 64

    run_id: str = Field(min_length=1, max_length=64)
    script_id: str = Field(min_length=1, max_length=128)
    started_at: str = Field(min_length=1, max_length=64)
    ended_at: str | None = Field(default=None, max_length=64)
    status: YoloRunStatus = "running"
    stages: list[YoloStageRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _cap_stages(self) -> "YoloRunRecord":
        if len(self.stages) > self.MAX_STAGES:
            raise ValueError(f"a YOLO run cannot have more than {self.MAX_STAGES} stages")
        return self

    @property
    def duration_seconds(self) -> float | None:
        started = _parse_iso(self.started_at)
        ended = _parse_iso(self.ended_at)
        if started is None or ended is None:
            return None
        if (started.tzinfo is None) != (ended.tzinfo is None):
            return None
        return max(0.0, (ended - started).total_seconds())


def validate_script_id(script_id: str) -> str:
    if not isinstance(script_id, str) or not SAFE_SCRIPT_ID_RE.fullmatch(script_id):
        raise ValueError("script_id must be a safe identifier of letters, numbers, underscores, or hyphens")
    return script_id


def _projects_dir() -> Path:
    return DATA_DIR / "projects"


def runs_path(script_id: str) -> Path:
    """Path to a project's YOLO run history, refusing anything outside it."""
    safe_id = validate_script_id(script_id)
    path = _projects_dir() / safe_id / "yolo" / "runs.json"
    try:
        path.resolve().relative_to(_projects_dir().resolve())
    except ValueError as exc:  # pragma: no cover — guarded by the regex above
        raise ValueError("script_id resolved outside the projects directory") from exc
    return path


def load_runs(script_id: str) -> list[YoloRunRecord]:
    """Load a project's run history, newest first. Never raises on bad data."""
    path = runs_path(script_id)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Unreadable YOLO run history for %s; starting a fresh log", script_id)
        return []

    entries = raw.get("runs") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return []

    runs: list[YoloRunRecord] = []
    for entry in entries:
        try:
            runs.append(YoloRunRecord.model_validate(entry))
        except ValueError:
            continue
    return _sorted_newest_first(runs)


def _sorted_newest_first(runs: list[YoloRunRecord]) -> list[YoloRunRecord]:
    return sorted(runs, key=lambda run: (run.started_at, run.run_id), reverse=True)


def save_run(script_id: str, run: YoloRunRecord) -> list[YoloRunRecord]:
    """Upsert one run into the project's history and prune to MAX_RUNS."""
    path = runs_path(script_id)
    existing = [item for item in load_runs(script_id) if item.run_id != run.run_id]
    runs = _sorted_newest_first([run, *existing])[:MAX_RUNS]

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"runs": [item.model_dump(mode="json") for item in runs]}
    # Write through a temp file so an interrupted write cannot leave the
    # history truncated — this file is written dozens of times per run.
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)
    return runs
