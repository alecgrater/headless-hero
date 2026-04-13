"""Endpoints for video rendering and export."""

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR, FPS, VIDEO_HEIGHT, VIDEO_WIDTH, sanitize_filename
from database import get_default_brand_id, get_session
from models.brand import BrandProfile
from models.script import Script, ScriptContent
from pipeline.render_jobs import RenderJob, create_job, estimate_render_time, get_job, run_in_background, update_job
from pipeline.remotion_render import render_full_video
from pipeline.video_render import export_full_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/render", tags=["render"])

# --- Request / Response schemas ---

class RenderFullRequest(BaseModel):
    script_id: str
    width: int = VIDEO_WIDTH
    height: int = VIDEO_HEIGHT
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
    estimated_seconds: float | None = None

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

# --- ExportContext dataclass ---

@dataclass
class ExportContext:
    script_id: str
    job: RenderJob
    scenes: list[dict]
    seg_name: str
    total_scenes: int
    voice_id: str
    brand_dict: dict
    title: str
    regen_title_cards: bool
    regen_images: bool
    regen_audio: bool
    regen_fx: bool
    regen_eli: bool
    phase_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    video_url: str = ""

# --- Phase helpers ---

def _phase_progress(ctx: ExportContext, phase_name: str, frac: float) -> float:
    """Map a 0-1 fraction within a phase to the global progress range."""
    start, end = ctx.phase_ranges[phase_name]
    return start + frac * (end - start)


def _build_phase_ranges(ctx: ExportContext) -> None:
    """Compute phase_weights and set ctx.phase_ranges."""
    phase_weights: dict[str, int] = {}
    if ctx.regen_title_cards:
        phase_weights["title_cards"] = 2
    if ctx.regen_images:
        phase_weights["images"] = 18
    if ctx.regen_audio:
        phase_weights["audio"] = 25
    if ctx.regen_images or ctx.regen_audio:
        phase_weights["persist"] = 2
    if ctx.regen_fx:
        phase_weights["fx"] = 15
    if ctx.regen_eli:
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

    ctx.phase_ranges = phase_ranges


def _phase_title_cards(ctx: ExportContext) -> None:
    """Phase 1: Generate title card images."""
    from pipeline.title_card import ensure_title_card_images

    update_job(ctx.job.id, progress=_phase_progress(ctx, "title_cards", 0), current_step="Generating title card...")
    content_for_tc = _reload_content(ctx.script_id)
    ensure_title_card_images(ctx.script_id, content_for_tc, force=True, job_id=ctx.job.id)


def _phase_images(ctx: ExportContext) -> None:
    """Phase 2: Generate images for all scenes."""
    from pipeline.image_gen import generate_scene_frames, generate_scene_image

    scene_count = len(ctx.scenes)
    for i, sc_info in enumerate(ctx.scenes):
        p = _phase_progress(ctx, "images", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating image ({i+1}/{scene_count})...")
        sid = sc_info["scene_id"]
        if sc_info["frame_prompts"] and len(sc_info["frame_prompts"]) > 1:
            results = generate_scene_frames(sid, sc_info["frame_prompts"], ctx.script_id, visual_prompt=sc_info["visual_prompt"], force=True)
            frame_urls = [r[0] for r in results]
            image_url = frame_urls[0] if frame_urls else None
        else:
            image_url, _ = generate_scene_image(sid, sc_info["visual_prompt"], ctx.script_id, force=True)
            frame_urls = None
        sc_info["_image_url"] = image_url
        sc_info["_frame_urls"] = frame_urls


def _phase_audio(ctx: ExportContext) -> None:
    """Phase 3: Generate audio for all scenes."""
    from pipeline.voiceover import generate_scene_audio

    scene_count = len(ctx.scenes)
    for i, sc_info in enumerate(ctx.scenes):
        p = _phase_progress(ctx, "audio", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating audio ({i+1}/{scene_count})...")
        audio_url, audio_duration, word_timestamps = generate_scene_audio(
            sc_info["scene_id"], sc_info["narration"], ctx.voice_id, ctx.script_id,
        )
        sc_info["_audio_url"] = audio_url
        sc_info["_audio_duration"] = audio_duration
        sc_info["_word_timestamps"] = word_timestamps


def _phase_persist(ctx: ExportContext) -> None:
    """Phase 4: Persist regenerated assets to DB."""
    update_job(ctx.job.id, progress=_phase_progress(ctx, "persist", 0), current_step="Saving scene data...")
    for sc_info in ctx.scenes:
        # Load existing data for fields we didn't regenerate
        if not ctx.regen_images or not ctx.regen_audio:
            content_now = _reload_content(ctx.script_id)
            scene_now = _find_scene_in_content(content_now, sc_info["scene_id"])
            if "_image_url" not in sc_info:
                sc_info["_image_url"] = scene_now.image_url
                sc_info["_frame_urls"] = scene_now.frame_urls
            if "_audio_url" not in sc_info:
                sc_info["_audio_url"] = scene_now.audio_url
                sc_info["_audio_duration"] = scene_now.audio_duration_seconds
                sc_info["_word_timestamps"] = scene_now.word_timestamps
        _persist_scene_assets(
            ctx.script_id, sc_info["scene_id"],
            image_url=sc_info["_image_url"],
            frame_urls=sc_info["_frame_urls"],
            audio_url=sc_info["_audio_url"],
            audio_duration=sc_info["_audio_duration"],
            word_timestamps=sc_info["_word_timestamps"],
        )


def _phase_fx(ctx: ExportContext) -> None:
    """Phase 5: Generate FX for all scenes."""
    from pipeline.fx_generator import generate_scene_fx

    scene_count = len(ctx.scenes)
    for i, sc_info in enumerate(ctx.scenes):
        p = _phase_progress(ctx, "fx", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating FX ({i+1}/{scene_count})...")
        content_now = _reload_content(ctx.script_id)
        scene_now = _find_scene_in_content(content_now, sc_info["scene_id"])
        duration = scene_now.audio_duration_seconds or scene_now.duration_estimate_seconds
        scene_data = {
            "id": sc_info["scene_id"],
            "segment": ctx.seg_name,
            "segment_index": 0,
            "scene_index_in_segment": sc_info["sc_idx"],
            "global_index": sc_info["global_idx"],
            "is_first_scene": sc_info["global_idx"] == 0,
            "is_last_scene": sc_info["global_idx"] == ctx.total_scenes - 1,
            "is_first_in_segment": sc_info["sc_idx"] == 0,
            "is_title_card": False,
            "narration": scene_now.narration,
            "duration_seconds": duration,
            "duration_frames": int(duration * FPS),
            "has_multiple_frames": bool(scene_now.frame_urls and len(scene_now.frame_urls) > 1),
        }
        if scene_now.word_timestamps:
            scene_data["word_timestamps"] = scene_now.word_timestamps
        try:
            fx_result = generate_scene_fx(scene_data)
            _persist_scene_fx(ctx.script_id, sc_info["scene_id"], fx_result["fx"])
        except Exception as e:
            logger.warning("Failed FX for scene %s: %s", sc_info["scene_id"], e)


def _phase_eli(ctx: ExportContext) -> None:
    """Phase 6: Generate Eli animation for all scenes."""
    from pipeline.eli_animator import generate_scene_eli

    scene_count = len(ctx.scenes)
    for i, sc_info in enumerate(ctx.scenes):
        p = _phase_progress(ctx, "eli", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating Eli ({i+1}/{scene_count})...")
        content_now = _reload_content(ctx.script_id)
        scene_now = _find_scene_in_content(content_now, sc_info["scene_id"])
        duration = scene_now.audio_duration_seconds or scene_now.duration_estimate_seconds
        eli_scene_data = {
            "id": sc_info["scene_id"],
            "segment": ctx.seg_name,
            "segment_index": 0,
            "scene_index_in_segment": sc_info["sc_idx"],
            "global_index": sc_info["global_idx"],
            "is_title_card": False,
            "narration": scene_now.narration,
            "duration_seconds": duration,
            "duration_frames": int(duration * FPS),
        }
        if scene_now.word_timestamps:
            eli_scene_data["word_timestamps"] = scene_now.word_timestamps
        try:
            eli_result = generate_scene_eli(eli_scene_data)
            _persist_scene_eli(ctx.script_id, sc_info["scene_id"], eli_result["eli_overlay"])
        except Exception as e:
            logger.warning("Failed Eli for scene %s: %s", sc_info["scene_id"], e)


def _phase_render(ctx: ExportContext) -> None:
    """Phase 7: Render full video via Remotion (always runs). Sets ctx.video_url.

    Uses timer-based progress instead of Remotion's sparse on_progress callbacks,
    so the progress bar moves smoothly during the long render subprocess.
    """
    render_start, render_end = ctx.phase_ranges["render"]
    update_job(ctx.job.id, progress=render_start, current_step="Rendering full video...")
    content_now = _reload_content(ctx.script_id)

    estimated = estimate_render_time(ctx.job.scene_count)
    stop_timer = threading.Event()

    def _timer_updater():
        start = time.monotonic()
        while not stop_timer.is_set():
            elapsed = time.monotonic() - start
            frac = min(0.95, elapsed / estimated) if estimated > 0 else 0.5
            progress = render_start + frac * (render_end - render_start)
            update_job(ctx.job.id, progress=progress)
            stop_timer.wait(1.0)

    timer = threading.Thread(target=_timer_updater, daemon=True)
    timer.start()

    try:
        ctx.video_url = render_full_video(
            script_id=ctx.script_id,
            content=content_now,
            on_progress=None,
            title=ctx.title,
            speed=1.25,
            brand=ctx.brand_dict,
        )
    finally:
        stop_timer.set()
        timer.join(timeout=2)

    update_job(ctx.job.id, progress=render_end)


def _phase_copy_to_downloads(ctx: ExportContext) -> None:
    """Phase 8: Copy rendered video to Downloads folder (always runs)."""
    update_job(ctx.job.id, progress=ctx.phase_ranges["copy"][0], current_step="Copying to Downloads...")
    projects_prefix = "/static/projects/"
    if ctx.video_url.startswith(projects_prefix):
        relative = ctx.video_url[len(projects_prefix):]
        src_path = str(DATA_DIR / "projects" / relative)
    else:
        src_path = ctx.video_url

    downloads_dir = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
    safe_title = sanitize_filename(ctx.title)
    dest_path = Path(downloads_dir) / f"TEST_{safe_title}.mp4"
    shutil.copy2(src_path, dest_path)
    logger.info("Export test copied to: %s", dest_path)


# --- Endpoints ---

@router.post("/full", response_model=RenderJobResponse)
def start_full_render(body: RenderFullRequest, session: Session = Depends(get_session)):
    """Start a full YouTube video render via Remotion in the background."""
    content = _load_content(session, body.script_id)
    brand_dict = _load_brand(session, body.script_id)
    scene_count = _count_scenes(content)
    audio_dur = _total_audio_duration(content)
    job = create_job(scene_count=scene_count, total_audio_duration=audio_dur)
    job.estimated_seconds = estimate_render_time(scene_count, audio_dur)

    logger.info("Starting full render for script %s (%d scenes, %.1fs audio)", body.script_id, scene_count, audio_dur)

    speed = max(0.5, min(3.0, body.speed))

    def do_render():
        # render_full_video calls on_progress at these points:
        #   0..0.3 — preparing scenes
        #   0.4 — "Rendering video with Remotion..." (right before subprocess.run)
        #   1.0 — "Complete"
        # We use timer-based progress for the 0.4→1.0 Remotion phase.

        estimated = estimate_render_time(scene_count, audio_dur)
        stop_timer = threading.Event()
        timer_started = threading.Event()

        def _timer_updater():
            start = time.monotonic()
            while not stop_timer.is_set():
                elapsed = time.monotonic() - start
                frac = min(0.95, elapsed / estimated) if estimated > 0 else 0.5
                progress = 0.4 + frac * 0.6
                update_job(job.id, progress=progress, current_step="Rendering full video...")
                stop_timer.wait(1.0)

        timer = threading.Thread(target=_timer_updater, daemon=True)

        def on_progress(p: float, msg: str):
            if p >= 0.4 and not timer_started.is_set():
                # Remotion render phase starting — switch to timer
                timer_started.set()
                timer.start()
                return
            if timer_started.is_set():
                return  # Timer handles progress from here
            update_job(job.id, progress=p, current_step=msg)

        try:
            result = render_full_video(
                script_id=body.script_id,
                content=content,
                width=body.width,
                height=body.height,
                on_progress=on_progress,
                title=body.title,
                speed=speed,
                brand=brand_dict,
            )
        finally:
            stop_timer.set()
            if timer.is_alive():
                timer.join(timeout=2)

        return result

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
    title = first_seg.name if first_seg.scenes else "Untitled"
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

    scene_count = len(scenes_to_process)
    job = create_job(scene_count=scene_count)
    job.estimated_seconds = estimate_render_time(scene_count)

    ctx = ExportContext(
        script_id=body.script_id,
        job=job,
        scenes=scenes_to_process,
        seg_name=seg_name,
        total_scenes=total_scenes,
        voice_id=voice_id,
        brand_dict=brand_dict,
        title=title,
        regen_title_cards=body.regen_title_cards,
        regen_images=body.regen_images,
        regen_audio=body.regen_audio,
        regen_fx=body.regen_fx,
        regen_eli=body.regen_eli,
    )

    def do_export_test():
        _build_phase_ranges(ctx)

        if ctx.regen_title_cards:
            _phase_title_cards(ctx)
        if ctx.regen_images:
            _phase_images(ctx)
        if ctx.regen_audio:
            _phase_audio(ctx)
        if ctx.regen_images or ctx.regen_audio:
            _phase_persist(ctx)
        if ctx.regen_fx:
            _phase_fx(ctx)
        if ctx.regen_eli:
            _phase_eli(ctx)

        _phase_render(ctx)
        _phase_copy_to_downloads(ctx)

        return ctx.video_url

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


def _persist_scene_update(script_id: str, scene_id: str, updater) -> None:
    """Load a script from DB, find scene by ID, apply updater(scene), and save back."""
    from database import engine
    with Session(engine) as session:
        record = session.get(Script, script_id)
        if not record:
            return
        content = ScriptContent.model_validate(json.loads(record.script_json))
        for seg in content.segments:
            for sc in seg.scenes:
                if sc.id == scene_id:
                    updater(sc)
                    break
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


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
    def update(sc):
        if image_url:
            sc.image_url = image_url
        if frame_urls:
            sc.frame_urls = frame_urls
        sc.audio_url = audio_url
        sc.audio_duration_seconds = audio_duration
        sc.word_timestamps = word_timestamps
    _persist_scene_update(script_id, scene_id, update)


def _persist_scene_fx(script_id: str, scene_id: str, fx: dict) -> None:
    """Update a scene's FX in the DB."""
    _persist_scene_update(script_id, scene_id, lambda sc: setattr(sc, "fx", fx))


def _persist_scene_eli(script_id: str, scene_id: str, eli_overlay: dict) -> None:
    """Update a scene's Eli overlay in the DB."""
    _persist_scene_update(script_id, scene_id, lambda sc: setattr(sc, "eli_overlay", eli_overlay))
