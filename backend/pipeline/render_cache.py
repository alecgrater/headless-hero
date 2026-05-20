"""Cache invalidation helpers for video renders.

Cached MP4s in `data/projects/{id}/renders/` should be re-rendered when any
source asset (image frame, audio clip) has been modified after the MP4 was
written. Without this check, regenerating images leaves stale videos cached
and the YOLO pipeline copies the old MP4s to Downloads.
"""

from pathlib import Path

from config import DATA_DIR


def latest_source_mtime(script_id: str) -> float | None:
    """Return the maximum mtime across all source images and audio for a project.

    Returns None when no source files exist on disk yet.
    """
    project_dir = DATA_DIR / "projects" / script_id
    latest: float | None = None
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

    A render is considered stale (returns False) when any image or audio file
    has been modified after the render was written. Missing renders return
    False; projects with no source files return True (nothing can be stale).
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
