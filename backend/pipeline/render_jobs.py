"""In-memory background render job tracking.

Single-user Electron app, so a simple dict with a threading lock is sufficient.
Jobs run in daemon threads and are polled via job_id.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional


class RenderJob:
    """Tracks the state of a background render task."""

    __slots__ = ("id", "status", "progress", "current_step", "output_urls", "error")

    def __init__(self, job_id: str) -> None:
        self.id = job_id
        self.status = "pending"  # pending | running | completed | failed
        self.progress = 0.0  # 0.0 – 1.0
        self.current_step = ""
        self.output_urls = []  # type: List[str]
        self.error = None  # type: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "current_step": self.current_step,
            "output_urls": self.output_urls,
            "error": self.error,
        }


_jobs = {}  # type: Dict[str, RenderJob]
_lock = threading.Lock()


def create_job() -> RenderJob:
    """Create a new pending render job and return it."""
    job = RenderJob(uuid.uuid4().hex[:12])
    with _lock:
        _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Optional[RenderJob]:
    """Look up a job by ID. Returns None if not found."""
    with _lock:
        return _jobs.get(job_id)


def update_job(
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    current_step: Optional[str] = None,
    output_urls: Optional[List[str]] = None,
    error: Optional[str] = None,
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
        except Exception:
            update_job(job_id, status="failed", error=traceback.format_exc()[-1000:])

    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()
