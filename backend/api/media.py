"""Media upload endpoint for user-provided images and videos."""

import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR
from database import get_session
from models.script import Script, ScriptContent
from pipeline.media_analyzer import analyze_media_sources, apply_assignments, MediaAssignment, is_ai_video_eligible
from pipeline.render_jobs import UserFacingJobError, create_job, get_job, run_in_background, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media", tags=["media"])

ALLOWED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_VIDEO_TYPES = {".mp4", ".mov", ".webm"}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES
UPLOAD_CHUNK_SIZE = 1024 * 1024


def _ai_video_scenes_per_segment() -> int:
    try:
        value = int(os.environ.get("AI_VIDEO_SCENES_PER_SEGMENT", "2"))
    except ValueError:
        return 2
    return max(0, min(value, 5))


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
    raise HTTPException(status_code=410, detail="Scene media uploads have been removed")
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
    temp_dest = uploads_dir / f".{scene_id}.{uuid.uuid4().hex}.tmp"

    bytes_written = 0
    try:
        with temp_dest.open("wb") as out:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                out.write(chunk)
                bytes_written += len(chunk)
        temp_dest.replace(dest)
    except BaseException:
        temp_dest.unlink(missing_ok=True)
        raise

    media_type = "video" if ext in ALLOWED_VIDEO_TYPES else "image"
    url = f"/static/projects/{script_id}/uploads/{scene_id}{ext}"

    logger.info("Uploaded %s for scene %s: %s (%d bytes)", media_type, scene_id, dest, bytes_written)
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


def media_analysis_source_flags(script_json: dict) -> tuple[bool, bool, bool]:
    """Return enabled media sources. Gameplay and stock-photo routing are removed."""
    return (
        False,
        False,
        script_json.get("ai_video_enabled", False),
    )


def preserve_media_analysis_source_flags(
    content: ScriptContent,
    script_json: dict,
    gameplay_enabled: bool,
    stock_photo_enabled: bool,
    ai_video_enabled: bool,
) -> None:
    """Persist source flags while keeping removed source types disabled."""
    content.gameplay_enabled = False
    content.stock_photo_enabled = False
    if "ai_video_enabled" not in script_json:
        content.ai_video_enabled = ai_video_enabled


def normalize_media_assignments_for_sources(
    assignments: list[MediaAssignment],
    *,
    script_content: ScriptContent | None = None,
    gameplay_enabled: bool,
    stock_photo_enabled: bool,
    ai_video_enabled: bool,
) -> list[MediaAssignment]:
    """Coerce assignments to AI when disabled or invalid for the latest script."""
    normalized: list[MediaAssignment] = []
    scenes_by_id = {
        scene.id: scene
        for scene in script_content.all_scenes()
    } if script_content is not None else {}
    require_eli_scene_for_ai_video = script_content is not None and script_content.format_id == "life-as-a"
    life_as_a_role = ""
    if require_eli_scene_for_ai_video and script_content is not None:
        from pipeline.formats.life_as_a import life_as_a_role as resolve_life_as_a_role

        life_as_a_role = resolve_life_as_a_role(script_content)

    for assignment in assignments:
        if (
            assignment.media_source == "gameplay_video"
        ) or (
            assignment.media_source == "stock_photo"
        ) or (
            assignment.media_source == "ai_video" and not ai_video_enabled
        ):
            normalized.append(MediaAssignment(
                scene_id=assignment.scene_id,
                media_source="ai",
                game_name=None,
                search_query=None,
                reasoning="Media source disabled before analysis completed.",
            ))
        elif assignment.media_source == "ai_video" and script_content is not None:
            scene = scenes_by_id.get(assignment.scene_id)
            if scene is None or not is_ai_video_eligible(
                scene,
                current_source=scene.media_source if scene is not None else "ai",
                require_eli_scene=require_eli_scene_for_ai_video,
                life_as_a_role=life_as_a_role,
                enforce_duration_cap=False,
            ):
                normalized.append(MediaAssignment(
                    scene_id=assignment.scene_id,
                    media_source="ai",
                    game_name=None,
                    search_query=None,
                    reasoning="AI video assignment no longer fits the latest scene timing, media source, or content.",
                ))
                logger.info(
                    "[MEDIA_ANALYSIS] downgraded ai_video scene %s; reason=latest scene is ineligible",
                    assignment.scene_id,
                )
            else:
                normalized.append(assignment)
        else:
            normalized.append(assignment)
    return normalized


def missing_voiceover_scene_ids(content: ScriptContent) -> list[str]:
    """Return scene ids that do not have generated voiceover duration yet."""
    return [
        scene.id
        for scene in content.all_scenes()
        if scene.audio_duration_seconds <= 0
    ]


def media_analysis_voiceover_required_message(missing_count: int) -> str:
    """Build the user-facing media analysis voiceover gate message."""
    return (
        "Generate voiceover before media analysis. "
        f"{missing_count} scene(s) are missing audio duration timing."
    )


def require_media_analysis_voiceover(content: ScriptContent) -> None:
    """Raise a user-facing job error when media analysis lacks voiceover timing."""
    missing_voiceover = missing_voiceover_scene_ids(content)
    if missing_voiceover:
        logger.info(
            "[MEDIA_ANALYSIS] blocked; reason=missing voiceover durations count=%d",
            len(missing_voiceover),
        )
        raise UserFacingJobError(
            media_analysis_voiceover_required_message(len(missing_voiceover))
        )


@router.post("/analyze/{script_id}", response_model=AnalyzeResponse)
def analyze_media(script_id: str, session: Session = Depends(get_session)):
    """Trigger media source analysis for a script. Runs as a background job."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    missing_voiceover = missing_voiceover_scene_ids(content)
    if missing_voiceover:
        logger.info(
            "[MEDIA_ANALYSIS] blocked; reason=missing voiceover durations count=%d",
            len(missing_voiceover),
        )
        raise HTTPException(
            status_code=409,
            detail=media_analysis_voiceover_required_message(len(missing_voiceover)),
        )

    job = create_job()
    job_id = job.id

    def _run_analysis() -> list[str]:
        update_job(job_id, current_step="Validating media analysis against voiceover durations...")

        from database import engine
        from sqlmodel import Session as SqlSession
        with SqlSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if not rec:
                raise RuntimeError(f"Script {script_id} not found during background analysis")
            fresh_raw = json.loads(rec.script_json)
            fresh_content = ScriptContent.model_validate(fresh_raw)
            require_media_analysis_voiceover(fresh_content)

        gameplay_enabled, stock_photo_enabled, ai_video_enabled = media_analysis_source_flags(fresh_raw)

        if gameplay_enabled or stock_photo_enabled or ai_video_enabled:
            update_job(job_id, current_step="Analyzing script for media sources...")
            assignments = analyze_media_sources(
                fresh_content,
                gameplay_enabled=gameplay_enabled,
                stock_photo_enabled=stock_photo_enabled,
                ai_video_enabled=ai_video_enabled,
                animated_scene_count=5,
                ai_video_scenes_per_segment=_ai_video_scenes_per_segment(),
                script_id=script_id,
            )
        else:
            assignments = [
                MediaAssignment(
                    scene_id=scene.id,
                    media_source="ai",
                    game_name=None,
                    search_query=None,
                    reasoning="Gameplay, stock photo, and AI video routing are disabled for this script.",
                )
                for scene in fresh_content.all_scenes()
            ]

        with SqlSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if not rec:
                raise RuntimeError(f"Script {script_id} deleted during media analysis")
            final_raw = json.loads(rec.script_json)
            final_content = ScriptContent.model_validate(final_raw)
            update_job(job_id, current_step="Validating media analysis against voiceover durations...")
            require_media_analysis_voiceover(final_content)
            final_gameplay_enabled, final_stock_photo_enabled, final_ai_video_enabled = media_analysis_source_flags(final_raw)
            update_job(job_id, current_step="Downgrading stale AI video assignments...")
            final_assignments = normalize_media_assignments_for_sources(
                assignments,
                script_content=final_content,
                gameplay_enabled=final_gameplay_enabled,
                stock_photo_enabled=final_stock_photo_enabled,
                ai_video_enabled=final_ai_video_enabled,
            )
            apply_assignments(final_content, final_assignments)
            preserve_media_analysis_source_flags(
                final_content,
                script_json=final_raw,
                gameplay_enabled=gameplay_enabled,
                stock_photo_enabled=stock_photo_enabled,
                ai_video_enabled=ai_video_enabled,
            )
            rec.script_json = final_content.model_dump_json()
            bg_session.add(rec)
            bg_session.commit()

        result_data = json.dumps([{
            "scene_id": a.scene_id,
            "media_source": a.media_source,
            "game_name": a.game_name,
            "search_query": a.search_query,
            "reasoning": a.reasoning,
        } for a in final_assignments])

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
