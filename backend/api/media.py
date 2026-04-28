"""Media upload endpoint for user-provided images and videos."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR
from database import get_session
from models.script import Script, ScriptContent
from pipeline.media_analyzer import analyze_media_sources, apply_assignments, MediaAssignment
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])

ALLOWED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_VIDEO_TYPES = {".mp4", ".mov", ".webm"}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES


class UploadResponse(BaseModel):
    url: str
    media_type: str


@router.post("/upload", response_model=UploadResponse)
async def upload_scene_media(
    script_id: str = Form(...),
    scene_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload an image or video file for a scene."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    uploads_dir = DATA_DIR / "projects" / script_id / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = uploads_dir / f"{scene_id}{ext}"

    content = await file.read()
    dest.write_bytes(content)

    media_type = "video" if ext in ALLOWED_VIDEO_TYPES else "image"
    url = f"/static/projects/{script_id}/uploads/{scene_id}{ext}"

    logger.info("Uploaded %s for scene %s: %s (%d bytes)", media_type, scene_id, dest, len(content))
    return UploadResponse(url=url, media_type=media_type)


class MediaAssignmentResponse(BaseModel):
    scene_id: str
    media_source: str
    game_name: str | None = None
    search_query: str | None = None
    reasoning: str = ""


class AnalyzeResponse(BaseModel):
    job_id: str


class ApplyRequest(BaseModel):
    assignments: list[MediaAssignmentResponse]


class ApplyResponse(BaseModel):
    ok: bool


@router.post("/analyze/{script_id}", response_model=AnalyzeResponse)
def analyze_media(script_id: str, session: Session = Depends(get_session)):
    """Trigger media source analysis for a script. Runs as a background job."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    gameplay_enabled = True
    stock_photo_enabled = True

    job = create_job()
    job_id = job.id

    def _run_analysis() -> list[str]:
        update_job(job_id, current_step="Analyzing script for media sources...")

        from database import engine
        from sqlmodel import Session as SqlSession
        with SqlSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if not rec:
                raise RuntimeError(f"Script {script_id} not found during background analysis")
            fresh_content = ScriptContent.model_validate(json.loads(rec.script_json))

        assignments = analyze_media_sources(
            fresh_content,
            gameplay_enabled=gameplay_enabled,
            stock_photo_enabled=stock_photo_enabled,
            script_id=script_id,
        )

        with SqlSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if not rec:
                raise RuntimeError(f"Script {script_id} deleted during media analysis")
            final_content = ScriptContent.model_validate(json.loads(rec.script_json))
            apply_assignments(final_content, assignments)
            rec.script_json = final_content.model_dump_json()
            bg_session.add(rec)
            bg_session.commit()

        result_data = json.dumps([{
            "scene_id": a.scene_id,
            "media_source": a.media_source,
            "game_name": a.game_name,
            "search_query": a.search_query,
            "reasoning": a.reasoning,
        } for a in assignments])

        update_job(job_id, output_data=result_data)
        return [script_id]

    run_in_background(job_id, _run_analysis)
    return AnalyzeResponse(job_id=job_id)


@router.get("/analyze/status/{job_id}")
def analyze_status(job_id: str):
    """Poll the status of a media analysis job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    if job.status == "completed" and job.output_data:
        raw = json.loads(job.output_data)
        summary: dict[str, int] = {}
        for a in raw:
            src = a["media_source"]
            summary[src] = summary.get(src, 0) + 1
        result["assignments"] = raw
        result["summary"] = summary
    return result


@router.post("/apply/{script_id}", response_model=ApplyResponse)
def apply_media(body: ApplyRequest, script_id: str, session: Session = Depends(get_session)):
    """Apply user-edited media assignments to the script."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    assignments = [
        MediaAssignment(
            scene_id=a.scene_id,
            media_source=a.media_source,
            game_name=a.game_name,
            search_query=a.search_query,
            reasoning=a.reasoning,
        )
        for a in body.assignments
    ]

    apply_assignments(content, assignments)

    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Applied %d media assignments to script %s", len(assignments), script_id)
    return ApplyResponse(ok=True)
