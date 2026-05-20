"""Cache invalidation helpers for video renders.

Cached MP4s in `data/projects/{id}/renders/` should be re-rendered when any
source asset (image frame, audio clip) has been modified after the MP4 was
written. Without this check, regenerating images leaves stale videos cached
and the YOLO pipeline copies the old MP4s to Downloads.

Source assets that live as files on disk (images, audio) are detected by
walking those directories. Source data that lives only in the script_json
DB blob (FX, Eli keyframes, transitions, micro-timeline) does not bump any
file mtime, so callers that mutate those fields must call
`mark_render_inputs_changed(script_id)` to record the change. The marker
file's mtime is included in `latest_source_mtime`.
"""

import logging
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

_MARKER_FILENAME = ".render_inputs_mtime"


def _marker_path(script_id: str) -> Path:
    return DATA_DIR / "projects" / script_id / _MARKER_FILENAME


def mark_render_inputs_changed(script_id: str) -> None:
    """Record that script-blob render inputs (FX, Eli, transitions, etc.) changed.

    Touches a marker file whose mtime is included in `latest_source_mtime`,
    so cached MP4s older than the change are treated as stale.

    Failures (read-only filesystem, etc.) are logged and swallowed so the
    surrounding HTTP/job handler can still report success — a missed
    invalidation is preferable to a 500 after a successful DB commit.
    """
    marker = _marker_path(script_id)
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError as exc:
        logger.warning("Failed to mark render inputs changed for %s: %s", script_id, exc)


def latest_source_mtime(script_id: str) -> float | None:
    """Return the maximum mtime across all source images, audio, and the
    script-blob change marker for a project.

    Returns None when no source files or marker exist on disk yet.
    """
    project_dir = DATA_DIR / "projects" / script_id
    latest: float | None = None

    marker = _marker_path(script_id)
    if marker.is_file():
        try:
            latest = marker.stat().st_mtime
        except OSError:
            pass

    for sub in ("images", "audio"):
        directory = project_dir / sub
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            if not entry.is_file():
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if latest is None or mtime > latest:
                latest = mtime
    return latest


def is_render_up_to_date(render_path: Path, script_id: str) -> bool:
    """Return True if the rendered MP4 is at least as new as every source asset.

    A render is considered stale (returns False) when any image, audio file,
    or script-blob change marker has been modified after the render was
    written. Missing renders return False; projects with no source files
    return True (nothing can be stale).
    """
    if not render_path.is_file():
        return False
    try:
        render_mtime = render_path.stat().st_mtime
    except OSError:
        return False
    source_mtime = latest_source_mtime(script_id)
    if source_mtime is None:
        return True
    return render_mtime >= source_mtime
