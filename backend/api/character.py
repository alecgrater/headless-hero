"""Endpoints for Eli character frame library management."""

import logging
import threading
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.character_frames import (
    FRAMES_DIR,
    clear_all_frames,
    count_existing_variant_frames,
    count_missing_frames,
    count_total_variant_frames,
    generate_frame_library,
    generate_frame_variants,
    generate_missing_frames,
    generate_reference_candidates,
    generate_variants,
    get_manifest,
    get_reference_candidates,
    get_selected_reference,
    regenerate_frame,
    reprocess_backgrounds,
    select_reference,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/character", tags=["character"])

# In-memory job tracking (same pattern as render_jobs.py)
_jobs: dict[str, dict] = {}


def _start_background_job(
    job_type: str,
    target_fn,
    *,
    conflict_msg: str = "Job already in progress",
    initial_total: int = 0,
    initial_label: str = "Starting...",
    target_kwargs: dict | None = None,
) -> str:
    """Create a tracked background job and run target_fn in a daemon thread.

    target_fn is called with an on_progress(completed, total, label) callback
    plus any additional target_kwargs.
    """
    for job in _jobs.values():
        if job["status"] == "running" and job.get("type") == job_type:
            raise HTTPException(status_code=409, detail=conflict_msg)

    job_id = uuid.uuid4().hex[:8]
    _jobs[job_id] = {
        "type": job_type,
        "status": "running",
        "completed": 0,
        "total": initial_total,
        "current_label": initial_label,
        "error": None,
    }

    def run():
        def on_progress(completed: int, total: int, label: str):
            _jobs[job_id]["completed"] = completed
            _jobs[job_id]["total"] = total
            _jobs[job_id]["current_label"] = label

        try:
            kwargs = target_kwargs or {}
            target_fn(on_progress=on_progress, **kwargs)
            _jobs[job_id]["status"] = "completed"
        except Exception as e:
            logger.error("%s job failed", job_type, exc_info=True)
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)

    threading.Thread(target=run, daemon=True).start()
    return job_id


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
    job_id = _start_background_job(
        "references",
        generate_reference_candidates,
        conflict_msg="Reference generation already in progress",
        initial_total=15,
        target_kwargs={"count": 15},
    )
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
    reference_path = body.reference_path if body else None
    job_id = _start_background_job(
        "frames",
        generate_frame_library,
        conflict_msg="Frame generation already in progress",
        target_kwargs={"reference_path": reference_path},
    )
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
    """Return the frame manifest with variant entries expanded."""
    manifest = get_manifest()
    result = manifest or {"frames": [], "canonical_frame": None, "generated_at": None}

    # Expand variant entries into the frames list so the UI can display them
    expanded_frames = []
    for frame in result.get("frames", []):
        expanded_frames.append(frame)
        vc = frame.get("variant_count", 1)
        if vc <= 1:
            continue
        base_id = frame["id"]
        for v in range(2, vc + 1):
            closed_file = f"{base_id}_v{v}_closed.png"
            open_file = f"{base_id}_v{v}_open.png"
            if (FRAMES_DIR / closed_file).exists() and (FRAMES_DIR / open_file).exists():
                expanded_frames.append({
                    "id": f"{base_id}_v{v}",
                    "file_closed": closed_file,
                    "file_open": open_file,
                    "expression": frame["expression"],
                    "pose": frame["pose"],
                    "gesture": frame["gesture"],
                    "variant_count": 1,
                    "variant_of": base_id,
                    "variant_num": v,
                })
    result["frames"] = expanded_frames

    result["missing_count"] = count_missing_frames()
    result["existing_variant_count"] = count_existing_variant_frames()
    result["total_variant_count"] = count_total_variant_frames()
    return result


@router.post("/generate-missing", response_model=GenerateFramesResponse)
def start_generate_missing():
    """Trigger background generation of only missing frames."""
    job_id = _start_background_job(
        "frames",
        generate_missing_frames,
        conflict_msg="Frame generation already in progress",
    )
    return GenerateFramesResponse(job_id=job_id)


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


@router.post("/generate-variants", response_model=GenerateFramesResponse)
def start_generate_variants():
    """Trigger background generation of body micro-variants for all frames that need them."""
    job_id = _start_background_job(
        "variants",
        generate_variants,
        conflict_msg="Variant generation already in progress",
    )
    return GenerateFramesResponse(job_id=job_id)


@router.post("/reprocess-backgrounds", response_model=GenerateFramesResponse)
def start_reprocess_backgrounds():
    """Trigger background reprocessing of frames with green backgrounds."""
    job_id = _start_background_job(
        "reprocess",
        reprocess_backgrounds,
        conflict_msg="Background reprocessing already in progress",
    )
    return GenerateFramesResponse(job_id=job_id)


@router.delete("/clear-all", status_code=200)
def clear_all():
    """Delete all frames, references, manifest, and selection metadata."""
    return clear_all_frames()
