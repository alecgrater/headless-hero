"""Endpoints for video rendering and export."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.render_jobs import create_job, estimate_render_time, get_job, run_in_background, update_job
from pipeline.shortform_render import render_shortform_video
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
    title: str = ""
    speed: float = 1.0

class RenderSegmentsRequest(BaseModel):
    script_id: str
    width: int = 1080
    height: int = 1920
    title: str = ""
    speed: float = 1.0

class RenderShortformRequest(BaseModel):
    script_id: str
    title: str = ""
    speed: float = 1.0

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
    title: str = ""

class ExportAudioResponse(BaseModel):
    audio_url: str

class RenderEstimateResponse(BaseModel):
    estimated_seconds: float

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

def _count_scenes(content: ScriptContent) -> int:
    """Count total scenes across all segments."""
    return sum(len(seg.scenes) for seg in content.segments)

def _total_audio_duration(content: ScriptContent) -> float:
    """Sum audio durations across all scenes."""
    total = 0.0
    for seg in content.segments:
        for sc in seg.scenes:
            if sc.audio_duration_seconds:
                total += sc.audio_duration_seconds
    return total

def _load_brand_and_modifiers(session: Session, script_id: str) -> tuple[dict, list[str]]:
    """Load brand dict and modifier IDs for a script."""
    record = session.get(Script, script_id)
    if not record:
        return {}, ["title_cards"]
    brand = session.get(BrandProfile, record.brand_id)
    if not brand:
        return {}, ["title_cards"]

    brand_dict = {
        "name": brand.name,
        "art_style": brand.art_style,
        "color_palette": brand.color_palette,
        "font": brand.font,
    }

    modifier_ids: list[str] = []
    try:
        parsed = json.loads(brand.content_modifiers) if brand.content_modifiers else []
        modifier_ids = parsed if isinstance(parsed, list) else []
    except Exception:
        pass
    if not modifier_ids:
        modifier_ids = ["title_cards"]

    return brand_dict, modifier_ids

# --- Endpoints ---

@router.post("/preview-scene", response_model=PreviewSceneResponse)
def preview_scene(body: PreviewSceneRequest, session: Session = Depends(get_session)):
    """Render a single scene to MP4 (synchronous — typically 2-5s)."""
    content = _load_content(session, body.script_id)
    brand_dict, modifier_ids = _load_brand_and_modifiers(session, body.script_id)
    scene = _find_scene(content, body.scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    video_url = render_scene_video(
        scene, body.script_id, body.width, body.height,
        modifier_ids=modifier_ids, brand=brand_dict,
    )
    return PreviewSceneResponse(video_url=video_url)

@router.post("/full", response_model=RenderJobResponse)
def start_full_render(body: RenderFullRequest, session: Session = Depends(get_session)):
    """Start a full YouTube video render in the background."""
    content = _load_content(session, body.script_id)
    brand_dict, modifier_ids = _load_brand_and_modifiers(session, body.script_id)
    scene_count = _count_scenes(content)
    audio_dur = _total_audio_duration(content)
    job = create_job(scene_count=scene_count, total_audio_duration=audio_dur)

    speed = max(0.5, min(3.0, body.speed))

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
            title=body.title,
            speed=speed,
            modifier_ids=modifier_ids,
            brand=brand_dict,
        )

    run_in_background(job.id, do_render)
    return RenderJobResponse(job_id=job.id)

@router.post("/segments", response_model=RenderJobResponse)
def start_segments_render(body: RenderSegmentsRequest, session: Session = Depends(get_session)):
    """Start TikTok 9:16 segment renders in the background."""
    content = _load_content(session, body.script_id)
    brand_dict, modifier_ids = _load_brand_and_modifiers(session, body.script_id)
    scene_count = _count_scenes(content)
    audio_dur = _total_audio_duration(content)
    job = create_job(scene_count=scene_count, total_audio_duration=audio_dur)

    speed = max(0.5, min(3.0, body.speed))

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        return render_all_segments(
            script_id=body.script_id,
            content=content,
            width=body.width,
            height=body.height,
            on_progress=on_progress,
            title=body.title,
            speed=speed,
            modifier_ids=modifier_ids,
            brand=brand_dict,
        )

    run_in_background(job.id, do_render)
    return RenderJobResponse(job_id=job.id)

@router.post("/shortform", response_model=RenderJobResponse)
def start_shortform_render(body: RenderShortformRequest, session: Session = Depends(get_session)):
    """Start a short-form 1080x1920 render in the background."""
    content = _load_content(session, body.script_id)
    brand_dict, modifier_ids = _load_brand_and_modifiers(session, body.script_id)
    scene_count = _count_scenes(content)
    audio_dur = _total_audio_duration(content)
    job = create_job(scene_count=scene_count, total_audio_duration=audio_dur)

    speed = max(0.5, min(3.0, body.speed))

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        return render_shortform_video(
            script_id=body.script_id,
            content=content,
            on_progress=on_progress,
            title=body.title,
            speed=speed,
            modifier_ids=modifier_ids,
            brand=brand_dict,
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

@router.get("/estimate", response_model=RenderEstimateResponse)
def render_estimate(
    scene_count: int = Query(..., ge=1),
    total_audio_duration: float = Query(0.0, ge=0),
):
    """Estimate render time based on scene count and historical averages."""
    estimated = estimate_render_time(scene_count, total_audio_duration)
    return RenderEstimateResponse(estimated_seconds=estimated)

@router.post("/export-audio", response_model=ExportAudioResponse)
def export_audio(body: ExportAudioRequest, session: Session = Depends(get_session)):
    """Concatenate all scene audio into a single MP3 (synchronous)."""
    content = _load_content(session, body.script_id)
    audio_url = export_full_audio(body.script_id, content, title=body.title)
    return ExportAudioResponse(audio_url=audio_url)
