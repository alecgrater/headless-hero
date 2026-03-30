"""In-memory background render job tracking.

Single-user Electron app, so a simple dict with a threading lock is sufficient.
Jobs run in daemon threads and are polled via job_id.
"""

import logging
import threading
import time
import traceback
import uuid
from typing import Any, Callable

logger = logging.getLogger(__name__)

class RenderJob:
    """Tracks the state of a background render task."""

    __slots__ = ("id", "status", "progress", "current_step", "output_urls", "error",
                 "scene_count", "total_audio_duration", "duration_seconds", "_start_time")

    def __init__(self, job_id: str) -> None:
        self.id = job_id
        self.status = "pending"  # pending | running | completed | failed
        self.progress = 0.0  # 0.0 – 1.0
        self.current_step = ""
        self.output_urls: list[str] = []
        self.error: str | None = None
        self.scene_count: int = 0
        self.total_audio_duration: float = 0.0
        self.duration_seconds: float | None = None
        self._start_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "current_step": self.current_step,
            "output_urls": self.output_urls,
            "error": self.error,
        }

_jobs: dict[str, RenderJob] = {}
_lock = threading.Lock()

# History of completed render durations for estimation
_completed_history: list[dict[str, float]] = []  # [{scene_count, duration_seconds}]
_DEFAULT_SECONDS_PER_SCENE = 5.0

def create_job(*, scene_count: int = 0, total_audio_duration: float = 0.0) -> RenderJob:
    """Create a new pending render job and return it."""
    job = RenderJob(uuid.uuid4().hex[:12])
    job.scene_count = scene_count
    job.total_audio_duration = total_audio_duration
    with _lock:
        _jobs[job.id] = job
    return job

def get_job(job_id: str) -> RenderJob | None:
    """Look up a job by ID. Returns None if not found."""
    with _lock:
        return _jobs.get(job_id)

def update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    current_step: str | None = None,
    output_urls: list[str] | None = None,
    error: str | None = None,
) -> None:
    """Thread-safe update of job fields."""
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if current_step is not None:
            job.current_step = current_step
        if output_urls is not None:
            job.output_urls = output_urls
        if error is not None:
            job.error = error

def run_in_background(
    job_id: str,
    target: Callable[[], Any],
) -> None:
    """Run *target* in a daemon thread, updating the job on completion/failure."""

    def _wrapper() -> None:
        with _lock:
            job = _jobs.get(job_id)
            if job:
                job._start_time = time.monotonic()
        update_job(job_id, status="running")
        try:
            result = target()
            # target should return a list of output URLs (or a single string)
            if isinstance(result, str):
                urls = [result]
            elif isinstance(result, list):
                urls = result
            else:
                urls = []
            update_job(job_id, status="completed", progress=1.0, current_step="Complete", output_urls=urls)
            # Record duration for estimation
            with _lock:
                job = _jobs.get(job_id)
                if job and job._start_time is not None:
                    job.duration_seconds = time.monotonic() - job._start_time
                    if job.scene_count > 0:
                        _completed_history.append({
                            "scene_count": job.scene_count,
                            "duration_seconds": job.duration_seconds,
                        })
        except Exception:
            logger.exception("Render job %s failed", job_id)
            update_job(job_id, status="failed", error=traceback.format_exc()[-1000:])

    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()

def estimate_render_time(scene_count: int, total_audio_duration: float = 0.0) -> float:
    """Estimate render duration in seconds based on historical data.

    Returns estimated seconds. Uses average seconds-per-scene from completed jobs,
    falling back to a default if no history exists.
    """
    with _lock:
        history = list(_completed_history)

    if history:
        total_scenes = sum(h["scene_count"] for h in history)
        total_duration = sum(h["duration_seconds"] for h in history)
        if total_scenes > 0:
            secs_per_scene = total_duration / total_scenes
        else:
            secs_per_scene = _DEFAULT_SECONDS_PER_SCENE
    else:
        secs_per_scene = _DEFAULT_SECONDS_PER_SCENE

    return round(secs_per_scene * scene_count, 1)
