"""Endpoints for video rendering and export."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.script import Script, ScriptContent
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job
from pipeline.video_render import (
    export_full_audio,
    render_all_segments,
    render_full_video,
    render_scene_video,
)

router = APIRouter(prefix="/api/render", tags=["render"])

# --- Request / Response schemas ---

class PreviewSceneRequest(BaseModel):
    script_id: str
    scene_id: str
    width: int = 1920
    height: int = 1080

class PreviewSceneResponse(BaseModel):
    video_url: str

class RenderFullRequest(BaseModel):
    script_id: str
    width: int = 1920
    height: int = 1080
    fade_out: float = 0.3

class RenderSegmentsRequest(BaseModel):
    script_id: str
    width: int = 1080
    height: int = 1920

class RenderJobResponse(BaseModel):
    job_id: str

class RenderStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    current_step: str
    output_urls: list[str]
    error: str | None = None

class ExportAudioRequest(BaseModel):
    script_id: str

class ExportAudioResponse(BaseModel):
    audio_url: str

# --- Helpers ---

def _load_content(session: Session, script_id: str) -> ScriptContent:
    """Load and parse ScriptContent from the database."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    return ScriptContent.model_validate(json.loads(record.script_json))

def _find_scene(content: ScriptContent, scene_id: str):
    """Find a scene by ID across all segments."""
    for seg in content.segments:
        for sc in seg.scenes:
            if sc.id == scene_id:
                return sc
    return None

# --- Endpoints ---

@router.post("/preview-scene", response_model=PreviewSceneResponse)
def preview_scene(body: PreviewSceneRequest, session: Session = Depends(get_session)):
    """Render a single scene to MP4 (synchronous — typically 2-5s)."""
    content = _load_content(session, body.script_id)
    scene = _find_scene(content, body.scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    video_url = render_scene_video(scene, body.script_id, body.width, body.height)
    return PreviewSceneResponse(video_url=video_url)

@router.post("/full", response_model=RenderJobResponse)
def start_full_render(body: RenderFullRequest, session: Session = Depends(get_session)):
    """Start a full YouTube video render in the background."""
    content = _load_content(session, body.script_id)
    job = create_job()

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        return render_full_video(
            script_id=body.script_id,
            content=content,
            width=body.width,
            height=body.height,
            fade_out=body.fade_out,
            on_progress=on_progress,
        )

    run_in_background(job.id, do_render)
    return RenderJobResponse(job_id=job.id)

@router.post("/segments", response_model=RenderJobResponse)
def start_segments_render(body: RenderSegmentsRequest, session: Session = Depends(get_session)):
    """Start TikTok 9:16 segment renders in the background."""
    content = _load_content(session, body.script_id)
    job = create_job()

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        return render_all_segments(
            script_id=body.script_id,
            content=content,
            width=body.width,
            height=body.height,
            on_progress=on_progress,
        )

    run_in_background(job.id, do_render)
    return RenderJobResponse(job_id=job.id)

@router.get("/status/{job_id}", response_model=RenderStatusResponse)
def render_status(job_id: str):
    """Poll the progress of a background render job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    d = job.to_dict()
    return RenderStatusResponse(**d)

@router.post("/export-audio", response_model=ExportAudioResponse)
def export_audio(body: ExportAudioRequest, session: Session = Depends(get_session)):
    """Concatenate all scene audio into a single MP3 (synchronous)."""
    content = _load_content(session, body.script_id)
    audio_url = export_full_audio(body.script_id, content)
    return ExportAudioResponse(audio_url=audio_url)
