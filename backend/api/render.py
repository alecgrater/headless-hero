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
)
from pipeline.video_render import export_full_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/render", tags=["render"])

# --- Request / Response schemas ---

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
    regen_title_cards: bool = False
    regen_images: bool = False
    regen_audio: bool = False
    regen_fx: bool = False
    regen_eli: bool = False

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

def _load_brand(session: Session, script_id: str) -> dict:
    """Load brand dict for a script."""
    record = session.get(Script, script_id)
    if not record:
        return {}
    brand = session.get(BrandProfile, record.brand_id)
    if not brand:
        return {}

    return {
        "name": brand.name,
    }

# --- Endpoints ---

@router.post("/full", response_model=RenderJobResponse)
def start_full_render(body: RenderFullRequest, session: Session = Depends(get_session)):
    """Start a full YouTube video render via Remotion in the background."""
    content = _load_content(session, body.script_id)
    brand_dict = _load_brand(session, body.script_id)
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
    """Run the full pipeline (image → audio → FX → Eli → render) for the first segment."""
    content = _load_content(session, body.script_id)
    brand_dict = _load_brand(session, body.script_id)

    # Resolve voice_id from the default brand
    brand_id = get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand or not brand.voice_id:
        raise HTTPException(status_code=400, detail="No voice configured — set a voice in Settings first")
    voice_id = brand.voice_id

    if not content.segments:
        raise HTTPException(status_code=400, detail="Script has no segments")

    first_seg = content.segments[0]
    title = first_seg.scenes[0].text_overlay or "Untitled" if first_seg.scenes else "Untitled"
    seg_name = first_seg.name

    # Collect non-title-card scenes in first segment for processing
    scenes_to_process: list[dict] = []
    global_idx = 0
    total_scenes = sum(len(seg.scenes) for seg in content.segments)
    for sci, scene in enumerate(first_seg.scenes):
        if not scene.is_title_card:
            scenes_to_process.append({
                "scene_id": scene.id,
                "narration": scene.narration or "",
                "visual_prompt": scene.visual_prompt or "",
                "frame_prompts": scene.frame_prompts or [],
                "sc_idx": sci,
                "global_idx": global_idx,
            })
        global_idx += 1

    if not scenes_to_process:
        raise HTTPException(status_code=400, detail="No non-title-card scenes in first segment")

    script_id = body.script_id
    scene_count = len(scenes_to_process)
    job = create_job(scene_count=scene_count)

    # Capture regen flags
    regen_title_cards = body.regen_title_cards
    regen_images = body.regen_images
    regen_audio = body.regen_audio
    regen_fx = body.regen_fx
    regen_eli = body.regen_eli

    def do_export_test():
        from pipeline.eli_animator import generate_scene_eli
        from pipeline.fx_generator import generate_scene_fx
        from pipeline.image_gen import generate_scene_frames, generate_scene_image
        from pipeline.title_card import ensure_title_card_images
        from pipeline.voiceover import generate_scene_audio

        # Build dynamic progress ranges from weights of active phases
        phase_weights = {}
        if regen_title_cards:
            phase_weights["title_cards"] = 2
        if regen_images:
            phase_weights["images"] = 18
        if regen_audio:
            phase_weights["audio"] = 25
        if regen_images or regen_audio:
            phase_weights["persist"] = 2
        if regen_fx:
            phase_weights["fx"] = 15
        if regen_eli:
            phase_weights["eli"] = 12
        phase_weights["render"] = 23
        phase_weights["copy"] = 3

        total_weight = sum(phase_weights.values())
        phase_ranges: dict[str, tuple[float, float]] = {}
        cursor = 0.0
        for phase_name in ["title_cards", "images", "audio", "persist", "fx", "eli", "render", "copy"]:
            if phase_name in phase_weights:
                start = cursor
                span = phase_weights[phase_name] / total_weight
                cursor += span
                phase_ranges[phase_name] = (start, start + span)

        def phase_progress(phase: str, frac: float) -> float:
            """Map a 0-1 fraction within a phase to the global progress range."""
            start, end = phase_ranges[phase]
            return start + frac * (end - start)

        # Phase 1: Title cards
        if regen_title_cards:
            update_job(job.id, progress=phase_progress("title_cards", 0), current_step="Generating title card...")
            content_for_tc = _reload_content(script_id)
            ensure_title_card_images(script_id, content_for_tc, force=True, job_id=job.id)

        # Phase 2: Images for all scenes
        if regen_images:
            for i, sc_info in enumerate(scenes_to_process):
                p = phase_progress("images", i / scene_count)
                update_job(job.id, progress=p, current_step=f"Generating image ({i+1}/{scene_count})...")
                sid = sc_info["scene_id"]
                if sc_info["frame_prompts"] and len(sc_info["frame_prompts"]) > 1:
                    results = generate_scene_frames(sid, sc_info["frame_prompts"], script_id, visual_prompt=sc_info["visual_prompt"], force=True)
                    frame_urls = [r[0] for r in results]
                    image_url = frame_urls[0] if frame_urls else None
                else:
                    image_url, _ = generate_scene_image(sid, sc_info["visual_prompt"], script_id, force=True)
                    frame_urls = None
                sc_info["_image_url"] = image_url
                sc_info["_frame_urls"] = frame_urls

        # Phase 3: Audio for all scenes
        if regen_audio:
            for i, sc_info in enumerate(scenes_to_process):
                p = phase_progress("audio", i / scene_count)
                update_job(job.id, progress=p, current_step=f"Generating audio ({i+1}/{scene_count})...")
                audio_url, audio_duration, word_timestamps = generate_scene_audio(
                    sc_info["scene_id"], sc_info["narration"], voice_id, script_id,
                )
                sc_info["_audio_url"] = audio_url
                sc_info["_audio_duration"] = audio_duration
                sc_info["_word_timestamps"] = word_timestamps

        # Phase 4: Persist regenerated assets to DB
        if regen_images or regen_audio:
            update_job(job.id, progress=phase_progress("persist", 0), current_step="Saving scene data...")
            for sc_info in scenes_to_process:
                # Load existing data for fields we didn't regenerate
                if not regen_images or not regen_audio:
                    content_now = _reload_content(script_id)
                    scene_now = _find_scene_in_content(content_now, sc_info["scene_id"])
                    if "_image_url" not in sc_info:
                        sc_info["_image_url"] = scene_now.image_url
                        sc_info["_frame_urls"] = scene_now.frame_urls
                    if "_audio_url" not in sc_info:
                        sc_info["_audio_url"] = scene_now.audio_url
                        sc_info["_audio_duration"] = scene_now.audio_duration_seconds
                        sc_info["_word_timestamps"] = scene_now.word_timestamps
                _persist_scene_assets(
                    script_id, sc_info["scene_id"],
                    image_url=sc_info["_image_url"],
                    frame_urls=sc_info["_frame_urls"],
                    audio_url=sc_info["_audio_url"],
                    audio_duration=sc_info["_audio_duration"],
                    word_timestamps=sc_info["_word_timestamps"],
                )

        # Phase 5: FX for all scenes
        if regen_fx:
            for i, sc_info in enumerate(scenes_to_process):
                p = phase_progress("fx", i / scene_count)
                update_job(job.id, progress=p, current_step=f"Generating FX ({i+1}/{scene_count})...")
                content_now = _reload_content(script_id)
                scene_now = _find_scene_in_content(content_now, sc_info["scene_id"])
                duration = scene_now.audio_duration_seconds or scene_now.duration_estimate_seconds
                scene_data = {
                    "id": sc_info["scene_id"],
                    "segment": seg_name,
                    "segment_index": 0,
                    "scene_index_in_segment": sc_info["sc_idx"],
                    "global_index": sc_info["global_idx"],
                    "is_first_scene": sc_info["global_idx"] == 0,
                    "is_last_scene": sc_info["global_idx"] == total_scenes - 1,
                    "is_first_in_segment": sc_info["sc_idx"] == 0,
                    "is_title_card": False,
                    "narration": scene_now.narration,
                    "duration_seconds": duration,
                    "duration_frames": int(duration * 30),
                    "has_multiple_frames": bool(scene_now.frame_urls and len(scene_now.frame_urls) > 1),
                }
                if scene_now.word_timestamps:
                    scene_data["word_timestamps"] = scene_now.word_timestamps
                try:
                    fx_result = generate_scene_fx(scene_data)
                    _persist_scene_fx(script_id, sc_info["scene_id"], fx_result["fx"])
                except Exception as e:
                    logger.warning("Failed FX for scene %s: %s", sc_info["scene_id"], e)

        # Phase 6: Eli for all scenes
        if regen_eli:
            for i, sc_info in enumerate(scenes_to_process):
                p = phase_progress("eli", i / scene_count)
                update_job(job.id, progress=p, current_step=f"Generating Eli ({i+1}/{scene_count})...")
                content_now = _reload_content(script_id)
                scene_now = _find_scene_in_content(content_now, sc_info["scene_id"])
                duration = scene_now.audio_duration_seconds or scene_now.duration_estimate_seconds
                eli_scene_data = {
                    "id": sc_info["scene_id"],
                    "segment": seg_name,
                    "segment_index": 0,
                    "scene_index_in_segment": sc_info["sc_idx"],
                    "global_index": sc_info["global_idx"],
                    "is_title_card": False,
                    "narration": scene_now.narration,
                    "duration_seconds": duration,
                    "duration_frames": int(duration * 30),
                }
                if scene_now.word_timestamps:
                    eli_scene_data["word_timestamps"] = scene_now.word_timestamps
                try:
                    eli_result = generate_scene_eli(eli_scene_data)
                    _persist_scene_eli(script_id, sc_info["scene_id"], eli_result["eli_overlay"])
                except Exception as e:
                    logger.warning("Failed Eli for scene %s: %s", sc_info["scene_id"], e)

        # Phase 7: Render full video (always runs)
        render_start, render_end = phase_ranges["render"]
        update_job(job.id, progress=render_start, current_step="Rendering full video...")
        content_now = _reload_content(script_id)

        def on_render_progress(p: float, msg: str):
            update_job(job.id, progress=render_start + p * (render_end - render_start), current_step=msg)

        video_url = render_full_video(
            script_id=script_id,
            content=content_now,
            on_progress=on_render_progress,
            title=title,
            speed=1.25,
            brand=brand_dict,
        )

        # Phase 8: Copy to Downloads (always runs)
        update_job(job.id, progress=phase_ranges["copy"][0], current_step="Copying to Downloads...")
        projects_prefix = "/static/projects/"
        if video_url.startswith(projects_prefix):
            relative = video_url[len(projects_prefix):]
            src_path = str(DATA_DIR / "projects" / relative)
        else:
            src_path = video_url

        downloads_dir = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
        safe_title = _sanitize_filename(title)
        dest_path = Path(downloads_dir) / f"TEST_{safe_title}.mp4"
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
