"""Endpoints for Eli character frame library management."""

import logging
import threading
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.character_frames import (
    generate_frame_library,
    get_manifest,
    regenerate_frame,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/character", tags=["character"])

# In-memory job tracking (same pattern as render_jobs.py)
_jobs: dict[str, dict] = {}


class GenerateFramesResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    status: str  # "running" | "completed" | "failed"
    completed: int
    total: int
    current_label: str
    error: str | None = None


class RegenerateFrameRequest(BaseModel):
    frame_id: str


@router.post("/generate-frames", response_model=GenerateFramesResponse)
def start_generate_frames():
    """Trigger background generation of the full Eli frame library."""
    # Check if already running
    for job in _jobs.values():
        if job["status"] == "running":
            raise HTTPException(status_code=409, detail="Frame generation already in progress")

    job_id = uuid.uuid4().hex[:8]
    _jobs[job_id] = {
        "status": "running",
        "completed": 0,
        "total": 0,
        "current_label": "",
        "error": None,
    }

    def run():
        def on_progress(completed: int, total: int, label: str):
            _jobs[job_id]["completed"] = completed
            _jobs[job_id]["total"] = total
            _jobs[job_id]["current_label"] = label

        try:
            generate_frame_library(on_progress=on_progress)
            _jobs[job_id]["status"] = "completed"
        except Exception as e:
            logger.error("Frame generation failed", exc_info=True)
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    return GenerateFramesResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """Poll generation job progress."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job)


@router.get("/frames")
def get_frames():
    """Return the frame manifest (or empty dict if not generated)."""
    manifest = get_manifest()
    return manifest or {"frames": [], "canonical_frame": None, "generated_at": None}


@router.post("/regenerate-frame")
def regenerate_single_frame(body: RegenerateFrameRequest):
    """Regenerate a single frame (both mouth states)."""
    try:
        result = regenerate_frame(body.frame_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
