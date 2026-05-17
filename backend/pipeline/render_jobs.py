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


class UserFacingJobError(RuntimeError):
    """Error whose message is safe to show directly in job status UI."""


class RenderJob:
    """Tracks the state of a background render task."""

    __slots__ = ("id", "status", "progress", "current_step", "output_urls", "output_data", "error",
                 "scene_count", "total_audio_duration", "duration_seconds", "estimated_seconds",
                 "_start_time", "_cancel_event")

    def __init__(self, job_id: str) -> None:
        self.id = job_id
        self.status = "pending"  # pending | running | completed | failed | cancelled
        self.progress = 0.0  # 0.0 – 1.0
        self.current_step = ""
        self.output_urls: list[str] = []
        self.output_data: str | None = None  # arbitrary JSON payload for non-URL results
        self.error: str | None = None
        self.scene_count: int = 0
        self.total_audio_duration: float = 0.0
        self.duration_seconds: float | None = None
        self.estimated_seconds: float | None = None
        self._start_time: float | None = None
        self._cancel_event: threading.Event = threading.Event()

    def to_dict(self) -> dict[str, Any]:
        elapsed = None
        if self._start_time is not None:
            elapsed = round(time.monotonic() - self._start_time, 1)
        return {
            "job_id": self.id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "current_step": self.current_step,
            "output_urls": self.output_urls,
            "output_data": self.output_data,
            "error": self.error,
            "estimated_seconds": self.estimated_seconds,
            "elapsed_seconds": elapsed,
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
    logger.info("Created render job %s (scene_count=%d)", job.id, scene_count)
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
    output_data: str | None = None,
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
        if output_data is not None:
            job.output_data = output_data
        if error is not None:
            job.error = error

def cancel_job(job_id: str) -> bool:
    """Signal a job to cancel. Returns True if found."""
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return False
        job._cancel_event.set()
        if job.status in ("pending", "running"):
            job.status = "cancelled"
            job.current_step = "Cancelled"
            logger.info("Job %s cancelled", job_id)
        return True


def cancel_all_jobs() -> int:
    """Cancel all pending/running jobs. Returns count cancelled."""
    count = 0
    with _lock:
        for job in _jobs.values():
            if job.status in ("pending", "running"):
                job._cancel_event.set()
                job.status = "cancelled"
                job.current_step = "Cancelled"
                count += 1
    if count:
        logger.info("Cancelled %d render job(s)", count)
    return count


def is_cancelled(job_id: str) -> bool:
    """Check if a job has been cancelled."""
    with _lock:
        job = _jobs.get(job_id)
        return job._cancel_event.is_set() if job else False


def run_in_background(
    job_id: str,
    target: Callable[[], Any],
) -> None:
    """Run *target* in a daemon thread, updating the job on completion/failure."""

    def _wrapper() -> None:
        logger.info("Background thread started for job %s", job_id)
        with _lock:
            job = _jobs.get(job_id)
            if job:
                job._start_time = time.monotonic()
        # Check cancellation before starting
        if is_cancelled(job_id):
            logger.info("Job %s cancelled before start", job_id)
            return
        update_job(job_id, status="running")
        try:
            result = target()
            # Check cancellation after completion
            if is_cancelled(job_id):
                logger.info("Job %s cancelled during execution", job_id)
                return
            # target should return a list of output URLs (or a single string)
            if isinstance(result, str):
                urls = [result]
            elif isinstance(result, list):
                urls = result
            else:
                urls = []
            update_job(job_id, status="completed", progress=1.0, current_step="Complete", output_urls=urls)
            # Log success with elapsed time
            with _lock:
                j = _jobs.get(job_id)
                elapsed = round(time.monotonic() - j._start_time, 1) if j and j._start_time else None
            logger.info("Render job %s completed in %.1fs", job_id, elapsed or 0.0)
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
                        _persist_render_duration(job.scene_count, job.duration_seconds)
        except UserFacingJobError as exc:
            if is_cancelled(job_id):
                logger.info("Job %s cancelled (exception during teardown)", job_id)
                return
            logger.warning("Render job %s failed with user-facing error: %s", job_id, exc)
            update_job(job_id, status="failed", error=str(exc))
        except Exception:
            if is_cancelled(job_id):
                logger.info("Job %s cancelled (exception during teardown)", job_id)
                return
            logger.exception("Render job %s failed", job_id)
            update_job(job_id, status="failed", error=traceback.format_exc()[-1000:])

    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()

def _persist_render_duration(scene_count: int, duration_seconds: float) -> None:
    """Write a render duration record to the database."""
    try:
        from database import engine
        from models.generation_duration import GenerationDuration
        from sqlmodel import Session

        with Session(engine) as session:
            record = GenerationDuration(
                operation_type="video_render",
                duration_seconds=duration_seconds,
                scene_count=scene_count,
            )
            session.add(record)
            session.commit()
    except Exception:
        logger.warning("Failed to persist render duration to DB", exc_info=True)


def estimate_render_time(scene_count: int, total_audio_duration: float = 0.0) -> float:
    """Estimate render duration in seconds based on historical data.

    Returns estimated seconds. Uses average seconds-per-scene from completed jobs
    (in-memory first, then DB), falling back to a default if no history exists.
    """
    # Try in-memory history first
    with _lock:
        history = list(_completed_history)

    if history:
        total_scenes = sum(h["scene_count"] for h in history)
        total_duration = sum(h["duration_seconds"] for h in history)
        if total_scenes > 0:
            estimate = round((total_duration / total_scenes) * scene_count, 1)
            logger.info("Render estimate for %d scenes: %.1fs (source=in-memory, %d historical jobs)", scene_count, estimate, len(history))
            return estimate

    # Fall back to DB history
    try:
        from database import engine
        from sqlmodel import Session, select, func
        from models.generation_duration import GenerationDuration

        with Session(engine) as session:
            stmt = select(
                func.sum(GenerationDuration.duration_seconds),
                func.sum(GenerationDuration.scene_count),
            ).where(
                GenerationDuration.operation_type == "video_render",
                GenerationDuration.scene_count.is_not(None),
            )
            result = session.exec(stmt).one()
            total_duration, total_scenes = result
            if total_duration and total_scenes and total_scenes > 0:
                estimate = round((total_duration / total_scenes) * scene_count, 1)
                logger.info("Render estimate for %d scenes: %.1fs (source=database)", scene_count, estimate)
                return estimate
    except Exception:
        logger.warning("Failed to query render duration history from DB", exc_info=True)

    estimate = round(_DEFAULT_SECONDS_PER_SCENE * scene_count, 1)
    logger.info("Render estimate for %d scenes: %.1fs (source=default, %.1fs/scene)", scene_count, estimate, _DEFAULT_SECONDS_PER_SCENE)
    return estimate
