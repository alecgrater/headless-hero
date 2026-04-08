"""Endpoints for Eli character frame library management."""

import logging
import threading
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.character_frames import (
    clear_all_frames,
    generate_frame_library,
    generate_reference_candidates,
    get_manifest,
    get_reference_candidates,
    get_selected_reference,
    regenerate_frame,
    select_reference,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/character", tags=["character"])

# In-memory job tracking (same pattern as render_jobs.py)
_jobs: dict[str, dict] = {}


class GenerateFramesRequest(BaseModel):
    reference_path: str | None = None


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


class SelectReferenceRequest(BaseModel):
    filename: str


class SelectReferenceResponse(BaseModel):
    selected: str
    path: str


class ReferencesResponse(BaseModel):
    references: list[str]
    selected: str | None


@router.post("/generate-references", response_model=GenerateFramesResponse)
def start_generate_references():
    """Trigger background generation of reference candidate images."""
    for job in _jobs.values():
        if job["status"] == "running" and job.get("type") == "references":
            raise HTTPException(status_code=409, detail="Reference generation already in progress")

    job_id = uuid.uuid4().hex[:8]
    _jobs[job_id] = {
        "type": "references",
        "status": "running",
        "completed": 0,
        "total": 15,
        "current_label": "Starting...",
        "error": None,
    }

    def run():
        def on_progress(completed: int, total: int, label: str):
            _jobs[job_id]["completed"] = completed
            _jobs[job_id]["total"] = total
            _jobs[job_id]["current_label"] = label

        try:
            generate_reference_candidates(count=15, on_progress=on_progress)
            _jobs[job_id]["status"] = "completed"
        except Exception as e:
            logger.error("Reference generation failed", exc_info=True)
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    return GenerateFramesResponse(job_id=job_id)


@router.get("/references", response_model=ReferencesResponse)
def get_references():
    """Return list of reference candidate filenames and which is selected."""
    return ReferencesResponse(
        references=get_reference_candidates(),
        selected=get_selected_reference(),
    )


@router.post("/select-reference", response_model=SelectReferenceResponse)
def select_reference_endpoint(body: SelectReferenceRequest):
    """Select a reference candidate as the canonical reference."""
    try:
        path = select_reference(body.filename)
        return SelectReferenceResponse(selected=body.filename, path=path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/generate-frames", response_model=GenerateFramesResponse)
def start_generate_frames(body: GenerateFramesRequest | None = None):
    """Trigger background generation of the full Eli frame library."""
    # Check if already running
    for job in _jobs.values():
        if job["status"] == "running" and job.get("type") == "frames":
            raise HTTPException(status_code=409, detail="Frame generation already in progress")

    job_id = uuid.uuid4().hex[:8]
    _jobs[job_id] = {
        "type": "frames",
        "status": "running",
        "completed": 0,
        "total": 0,
        "current_label": "",
        "error": None,
    }

    reference_path = body.reference_path if body else None

    def run():
        def on_progress(completed: int, total: int, label: str):
            _jobs[job_id]["completed"] = completed
            _jobs[job_id]["total"] = total
            _jobs[job_id]["current_label"] = label

        try:
            generate_frame_library(reference_path=reference_path, on_progress=on_progress)
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
    return JobStatusResponse(**{k: v for k, v in job.items() if k != "type"})


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


@router.delete("/clear-all", status_code=200)
def clear_all():
    """Delete all frames, references, manifest, and selection metadata."""
    return clear_all_frames()
