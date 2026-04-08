"""Endpoints for video rendering and export."""

import json
import logging
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR
from database import get_default_brand_id, get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.render_jobs import create_job, estimate_render_time, get_job, run_in_background, update_job
from pipeline.remotion_render import (
    _sanitize_filename,
    render_full_video,
    render_scene_preview,
)
from pipeline.video_render import export_full_audio

logger = logging.getLogger(__name__)

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

class ExportTestRequest(BaseModel):
    script_id: str

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
    """Load brand dict for a script. Modifier IDs always empty (title_cards handled separately)."""
    record = session.get(Script, script_id)
    if not record:
        return {}, []
    brand = session.get(BrandProfile, record.brand_id)
    if not brand:
        return {}, []

    brand_dict = {
        "name": brand.name,
    }

    return brand_dict, []

# --- Endpoints ---

@router.post("/preview-scene", response_model=PreviewSceneResponse)
def preview_scene(body: PreviewSceneRequest, session: Session = Depends(get_session)):
    """Render a single scene to MP4 via Remotion (synchronous)."""
    content = _load_content(session, body.script_id)
    brand_dict, modifier_ids = _load_brand_and_modifiers(session, body.script_id)
    scene = _find_scene(content, body.scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    logger.info("Rendering scene preview: scene %s in script %s", body.scene_id, body.script_id)
    video_url = render_scene_preview(
        scene, body.script_id, body.width, body.height,
        modifier_ids=modifier_ids, brand=brand_dict,
    )
    return PreviewSceneResponse(video_url=video_url)

@router.post("/full", response_model=RenderJobResponse)
def start_full_render(body: RenderFullRequest, session: Session = Depends(get_session)):
    """Start a full YouTube video render via Remotion in the background."""
    content = _load_content(session, body.script_id)
    brand_dict, modifier_ids = _load_brand_and_modifiers(session, body.script_id)
    scene_count = _count_scenes(content)
    audio_dur = _total_audio_duration(content)
    job = create_job(scene_count=scene_count, total_audio_duration=audio_dur)

    logger.info("Starting full render for script %s (%d scenes, %.1fs audio)", body.script_id, scene_count, audio_dur)

    speed = max(0.5, min(3.0, body.speed))

    def do_render():
        def on_progress(p: float, msg: str):
            update_job(job.id, progress=p, current_step=msg)

        return render_full_video(
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
    logger.info("Exporting full audio for script %s", body.script_id)
    audio_url = export_full_audio(body.script_id, content, title=body.title)
    logger.info("Audio export complete for script %s: %s", body.script_id, audio_url)
    return ExportAudioResponse(audio_url=audio_url)


@router.post("/export-test", response_model=RenderJobResponse)
def start_export_test(body: ExportTestRequest, session: Session = Depends(get_session)):
    """Run the full pipeline (image → audio → FX → Eli → render) for scene 1 only."""
    content = _load_content(session, body.script_id)
    brand_dict, modifier_ids = _load_brand_and_modifiers(session, body.script_id)

    # Resolve voice_id from the default brand
    brand_id = get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand or not brand.voice_id:
        raise HTTPException(status_code=400, detail="No voice configured — set a voice in Settings first")
    voice_id = brand.voice_id

    # Find the first non-title-card scene
    target_scene = None
    target_seg_idx = -1
    target_sc_idx = -1
    global_idx = 0
    total_scenes = sum(len(seg.scenes) for seg in content.segments)

    for si, seg in enumerate(content.segments):
        for sci, scene in enumerate(seg.scenes):
            if not scene.is_title_card:
                target_scene = scene
                target_seg_idx = si
                target_sc_idx = sci
                break
            global_idx += 1
        if target_scene:
            break

    if not target_scene:
        raise HTTPException(status_code=400, detail="No non-title-card scene found")

    # Capture what we need for the background thread (session won't be available)
    script_id = body.script_id
    scene_id = target_scene.id
    scene_narration = target_scene.narration or ""
    scene_visual_prompt = target_scene.visual_prompt or ""
    scene_frame_prompts = target_scene.frame_prompts or []
    scene_media_type = target_scene.media_type or "ai_generated"
    seg_name = content.segments[target_seg_idx].name
    title = content.segments[0].scenes[0].text_overlay or "Untitled" if content.segments else "Untitled"

    job = create_job(scene_count=1)

    def do_export_test():
        from pipeline.eli_animator import generate_scene_eli
        from pipeline.fx_generator import generate_scene_fx
        from pipeline.image_gen import generate_scene_frames, generate_scene_image
        from pipeline.title_card import ensure_title_card_images
        from pipeline.voiceover import generate_scene_audio

        # Step 1: Title cards
        update_job(job.id, progress=0.05, current_step="Generating title card...")
        content_for_tc = _reload_content(script_id)
        ensure_title_card_images(script_id, content_for_tc, force=True, job_id=job.id)

        # Step 2: Image
        update_job(job.id, progress=0.15, current_step="Generating image...")
        if scene_frame_prompts and len(scene_frame_prompts) > 1:
            results = generate_scene_frames(scene_id, scene_frame_prompts, script_id, visual_prompt=scene_visual_prompt, force=True)
            frame_urls = [r[0] for r in results]
            image_url = frame_urls[0] if frame_urls else None
        else:
            image_url, _ = generate_scene_image(scene_id, scene_visual_prompt, script_id, force=True)
            frame_urls = None

        # Step 3: Audio
        update_job(job.id, progress=0.35, current_step="Generating audio...")
        audio_url, audio_duration, word_timestamps = generate_scene_audio(
            scene_id, scene_narration, voice_id, script_id,
        )

        # Step 4: Persist to DB so FX/Eli/render pick up the new data
        update_job(job.id, progress=0.45, current_step="Saving scene data...")
        _persist_scene_assets(
            script_id, scene_id,
            image_url=image_url,
            frame_urls=frame_urls,
            audio_url=audio_url,
            audio_duration=audio_duration,
            word_timestamps=word_timestamps,
        )

        # Step 5: FX
        update_job(job.id, progress=0.55, current_step="Generating FX...")
        content_now = _reload_content(script_id)
        scene_now = _find_scene_in_content(content_now, scene_id)
        duration = scene_now.audio_duration_seconds or scene_now.duration_estimate_seconds
        scene_data = {
            "id": scene_id,
            "segment": seg_name,
            "segment_index": target_seg_idx,
            "scene_index_in_segment": target_sc_idx,
            "global_index": global_idx,
            "is_first_scene": global_idx == 0,
            "is_last_scene": global_idx == total_scenes - 1,
            "is_first_in_segment": target_sc_idx == 0,
            "is_title_card": False,
            "media_type": scene_media_type,
            "narration": scene_now.narration,
            "duration_seconds": duration,
            "duration_frames": int(duration * 30),
            "has_multiple_frames": bool(scene_now.frame_urls and len(scene_now.frame_urls) > 1),
        }
        if scene_now.word_timestamps:
            scene_data["word_timestamps"] = scene_now.word_timestamps
        fx_result = generate_scene_fx(scene_data)
        _persist_scene_fx(script_id, scene_id, fx_result["fx"])

        # Step 6: Eli
        update_job(job.id, progress=0.65, current_step="Generating Eli animation...")
        content_now = _reload_content(script_id)
        scene_now = _find_scene_in_content(content_now, scene_id)
        duration = scene_now.audio_duration_seconds or scene_now.duration_estimate_seconds
        eli_scene_data = {
            "id": scene_id,
            "segment": seg_name,
            "segment_index": target_seg_idx,
            "scene_index_in_segment": target_sc_idx,
            "global_index": global_idx,
            "is_title_card": False,
            "narration": scene_now.narration,
            "duration_seconds": duration,
            "duration_frames": int(duration * 30),
        }
        if scene_now.word_timestamps:
            eli_scene_data["word_timestamps"] = scene_now.word_timestamps
        eli_result = generate_scene_eli(eli_scene_data)
        _persist_scene_eli(script_id, scene_id, eli_result["eli_overlay"])

        # Step 7: Render scene preview
        update_job(job.id, progress=0.75, current_step="Rendering video...")
        content_now = _reload_content(script_id)
        scene_now = _find_scene_in_content(content_now, scene_id)
        video_url = render_scene_preview(scene_now, script_id, modifier_ids=modifier_ids, brand=brand_dict)

        # Step 8: Copy to Downloads
        update_job(job.id, progress=0.95, current_step="Copying to Downloads...")
        src_path = str(DATA_DIR / "projects" / video_url.lstrip("/static/projects/"))
        # video_url is like /static/projects/{script_id}/renders/scenes/{scene_id}.mp4
        # We need the actual filesystem path
        projects_prefix = "/static/projects/"
        if video_url.startswith(projects_prefix):
            relative = video_url[len(projects_prefix):]
            src_path = str(DATA_DIR / "projects" / relative)
        else:
            src_path = video_url

        downloads_dir = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
        safe_title = _sanitize_filename(title)
        dest_path = Path(downloads_dir) / f"TEST_SCENE_1_{safe_title}.mp4"
        shutil.copy2(src_path, dest_path)
        logger.info("Export test copied to: %s", dest_path)

        return video_url

    run_in_background(job.id, do_export_test)
    return RenderJobResponse(job_id=job.id)


# --- Export test helpers (DB access from background threads) ---

def _reload_content(script_id: str) -> ScriptContent:
    """Load fresh ScriptContent from DB (for use in background threads)."""
    from database import engine
    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            raise RuntimeError(f"Script {script_id} not found")
        return ScriptContent.model_validate(json.loads(record.script_json))


def _find_scene_in_content(content: ScriptContent, scene_id: str):
    """Find a scene by ID across all segments."""
    for seg in content.segments:
        for sc in seg.scenes:
            if sc.id == scene_id:
                return sc
    raise RuntimeError(f"Scene {scene_id} not found in content")


def _persist_scene_assets(
    script_id: str,
    scene_id: str,
    *,
    image_url: str | None,
    frame_urls: list[str] | None,
    audio_url: str,
    audio_duration: float,
    word_timestamps: list[dict],
) -> None:
    """Update a scene's media fields in the DB."""
    from database import engine
    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            return
        content = ScriptContent.model_validate(json.loads(record.script_json))
        for seg in content.segments:
            for sc in seg.scenes:
                if sc.id == scene_id:
                    if image_url:
                        sc.image_url = image_url
                    if frame_urls:
                        sc.frame_urls = frame_urls
                    sc.audio_url = audio_url
                    sc.audio_duration_seconds = audio_duration
                    sc.word_timestamps = word_timestamps
                    break
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


def _persist_scene_fx(script_id: str, scene_id: str, fx: dict) -> None:
    """Update a scene's FX in the DB."""
    from database import engine
    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            return
        content = ScriptContent.model_validate(json.loads(record.script_json))
        for seg in content.segments:
            for sc in seg.scenes:
                if sc.id == scene_id:
                    sc.fx = fx
                    break
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


def _persist_scene_eli(script_id: str, scene_id: str, eli_overlay: dict) -> None:
    """Update a scene's Eli overlay in the DB."""
    from database import engine
    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            return
        content = ScriptContent.model_validate(json.loads(record.script_json))
        for seg in content.segments:
            for sc in seg.scenes:
                if sc.id == scene_id:
                    sc.eli_overlay = eli_overlay
                    break
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()
