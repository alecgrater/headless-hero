"""Endpoints for video rendering and export."""

import json
import logging
import shutil
import threading
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR, FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from api.short_form_hooks import ensure_short_form_hook_scene_count
from database import get_default_brand_id, get_session
from api._helpers import find_scene_in_content
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.render_jobs import RenderJob, create_job, estimate_render_time, get_job, is_cancelled, run_in_background, update_job
from pipeline.remotion_render import render_full_video
from pipeline.export_paths import (
    copy_to_project_downloads,
    has_export_label,
    longform_filename,
    project_downloads_folder,
    shortform_filename,
    shortform_video_filename,
)

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
    elapsed_seconds: float | None = None

class RenderEstimateResponse(BaseModel):
    estimated_seconds: float

class ExportBundleRequest(BaseModel):
    script_id: str

class ExportBundleResponse(BaseModel):
    folder_path: str
    files: list[str]

class RenderedLongformResponse(BaseModel):
    rendered: bool
    path: str | None = None
    url: str | None = None

class ExportTestRequest(BaseModel):
    script_id: str
    regen_images: bool = False
    regen_audio: bool = False
    regen_fx: bool = False
    regen_eli: bool = False

class RenderScenePreviewRequest(BaseModel):
    script_id: str
    scene_id: str

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


def _format_longform_seo_markdown(seo: dict) -> str:
    yt = seo.get("youtube", {})
    lines: list[str] = []
    if yt.get("title"):
        lines.extend(["# Title", "", yt["title"], ""])
    if yt.get("description"):
        lines.extend(["# Description", "", yt["description"], ""])
    if yt.get("tags"):
        lines.extend(["# Tags", "", ", ".join(yt["tags"]), ""])
    return "\n".join(lines).strip() + "\n"


def _format_shortform_seo_markdown(item: dict) -> str:
    hashtags = item.get("hashtags") or []
    tags = item.get("tags") or []
    title = item.get("title", "")
    description = item.get("description", "")
    hashtags_line = " ".join(hashtags)
    tags_line = ", ".join(tags)
    lines = [
        f"# Short {item.get('index', '?')}",
        "",
        "# Youtube",
        "",
        "## Title",
        "",
        title,
        "",
        "## Description",
        "",
        description,
        "",
        "## Hashtags",
        "",
        hashtags_line,
        "",
        "## SEO Tags",
        "",
        tags_line,
        "",
        "# Tiktok / Insta",
        "",
        title,
        "",
        description,
    ]
    if hashtags:
        lines.extend(["", hashtags_line])
    if tags:
        lines.extend(["", tags_line])
    return "\n".join(lines).strip() + "\n"


def _find_rendered_longform(script_id: str, project_title: str) -> tuple[str | None, str | None]:
    """Return an existing long-form render path and optional web URL."""
    renders_dir = DATA_DIR / "projects" / script_id / "renders"
    if renders_dir.exists():
        candidates = sorted(
            renders_dir.glob("full_youtube*.mp4"),
            key=lambda path: (path.name != "full_youtube.mp4", path.name),
        )
        for mp4 in candidates:
            if mp4.is_file():
                return str(mp4), f"/static/projects/{script_id}/renders/{mp4.name}"

    folder = project_downloads_folder(project_title, create=False)
    exported = folder / longform_filename("Video", project_title, ".mp4")
    if exported.is_file():
        return str(exported), None
    if folder.is_dir():
        exported_videos = sorted(
            (
                path
                for path in folder.glob("*.mp4")
                if path.is_file() and has_export_label(path.name, "Longform", "Video")
            ),
            key=lambda path: path.name,
        )
        if exported_videos:
            return str(exported_videos[0]), None

    return None, None

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
    project_title: str
    title: str
    total_segments: int
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
    if ctx.regen_audio:
        phase_weights["audio"] = 25
    if ctx.regen_images:
        phase_weights["images"] = 18
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
    for phase_name in ["audio", "images", "persist", "fx", "eli", "render", "copy"]:
        if phase_name in phase_weights:
            start = cursor
            span = phase_weights[phase_name] / total_weight
            cursor += span
            phase_ranges[phase_name] = (start, start + span)

    ctx.phase_ranges = phase_ranges


def _check_cancelled(job_id: str) -> None:
    """Raise RuntimeError if the job has been cancelled."""
    if is_cancelled(job_id):
        raise RuntimeError("Job cancelled")


def _phase_images(ctx: ExportContext) -> None:
    """Phase 3: Generate images for all scenes (skips title cards)."""
    from pipeline.image_gen import generate_scene_image

    non_tc = [sc for sc in ctx.scenes if not sc.get("is_title_card")]
    scene_count = len(non_tc)
    logger.info("[%s] Phase: images — generating %d scene images", ctx.script_id, scene_count)
    for i, sc_info in enumerate(non_tc):
        _check_cancelled(ctx.job.id)
        p = _phase_progress(ctx, "images", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating image ({i+1}/{scene_count})...")
        sid = sc_info["scene_id"]
        logger.info("[%s] Generating image for scene %s (%d/%d)", ctx.script_id, sid, i + 1, scene_count)
        image_url, _, _ = generate_scene_image(sid, sc_info["visual_prompt"], ctx.script_id, force=True)
        sc_info["_image_url"] = image_url
        sc_info["_frame_urls"] = None
    logger.info("[%s] Phase: images — complete (%d scenes)", ctx.script_id, scene_count)


def _phase_audio(ctx: ExportContext) -> None:
    """Phase 2: Generate audio for all scenes."""
    from pipeline.voiceover import generate_scene_audio

    scene_count = len(ctx.scenes)
    logger.info("[%s] Phase: audio — generating %d scene audio clips (voice %s)", ctx.script_id, scene_count, ctx.voice_id)
    for i, sc_info in enumerate(ctx.scenes):
        _check_cancelled(ctx.job.id)
        p = _phase_progress(ctx, "audio", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating audio ({i+1}/{scene_count})...")
        logger.info("[%s] Generating audio for scene %s (%d/%d)", ctx.script_id, sc_info["scene_id"], i + 1, scene_count)
        audio_url, audio_duration, word_timestamps, phrase_timestamps = generate_scene_audio(
            sc_info["scene_id"], sc_info["narration"], ctx.voice_id, ctx.script_id,
        )
        sc_info["_audio_url"] = audio_url
        sc_info["_audio_duration"] = audio_duration
        sc_info["_word_timestamps"] = word_timestamps
        sc_info["_phrase_timestamps"] = phrase_timestamps
    logger.info("[%s] Phase: audio — complete (%d scenes)", ctx.script_id, scene_count)


def _phase_persist(ctx: ExportContext) -> None:
    """Phase 4: Persist regenerated assets to DB in a single write."""
    logger.info("[%s] Phase: persist — saving %d scene assets to DB", ctx.script_id, len(ctx.scenes))
    update_job(ctx.job.id, progress=_phase_progress(ctx, "persist", 0), current_step="Saving scene data...")

    from database import engine
    with Session(engine) as session:
        record = session.get(Script, ctx.script_id)
        if not record:
            return
        content = ScriptContent.model_validate(json.loads(record.script_json))
        scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}

        for sc_info in ctx.scenes:
            sc = scene_map.get(sc_info["scene_id"])
            if not sc:
                continue
            # Fill in missing fields from existing data if not regenerated
            if "_image_url" not in sc_info:
                sc_info["_image_url"] = sc.image_url
                sc_info["_frame_urls"] = sc.frame_urls
            if "_audio_url" not in sc_info:
                sc_info["_audio_url"] = sc.audio_url
                sc_info["_audio_duration"] = sc.audio_duration_seconds
                sc_info["_word_timestamps"] = sc.word_timestamps
                sc_info["_phrase_timestamps"] = sc.phrase_timestamps

            if sc_info.get("_image_url"):
                sc.image_url = sc_info["_image_url"]
            if sc_info.get("_frame_urls"):
                sc.frame_urls = sc_info["_frame_urls"]
            sc.audio_url = sc_info.get("_audio_url", sc.audio_url)
            sc.audio_duration_seconds = sc_info.get("_audio_duration", sc.audio_duration_seconds)
            sc.word_timestamps = sc_info.get("_word_timestamps", sc.word_timestamps)
            sc.phrase_timestamps = sc_info.get("_phrase_timestamps", sc.phrase_timestamps)

        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()


def _phase_fx(ctx: ExportContext) -> None:
    """Phase 5: Generate FX for all scenes (skips title cards), persist in a single write."""
    from pipeline.fx_generator import generate_scene_fx

    non_tc = [sc for sc in ctx.scenes if not sc.get("is_title_card")]
    scene_count = len(non_tc)
    logger.info("[%s] Phase: fx — generating FX for %d scenes", ctx.script_id, scene_count)

    # Generate FX for each scene, collecting results
    content_now = _reload_content(ctx.script_id)
    fx_updates: dict[str, dict] = {}
    for i, sc_info in enumerate(non_tc):
        _check_cancelled(ctx.job.id)
        p = _phase_progress(ctx, "fx", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating FX ({i+1}/{scene_count})...")
        scene_now = find_scene_in_content(content_now, sc_info["scene_id"])
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
            fx_updates[sc_info["scene_id"]] = fx_result["fx"]
        except Exception as e:
            logger.warning("Failed FX for scene %s: %s", sc_info["scene_id"], e)

    # Persist all FX in a single DB write
    if fx_updates:
        from database import engine
        with Session(engine) as session:
            record = session.get(Script, ctx.script_id)
            if record:
                content = ScriptContent.model_validate(json.loads(record.script_json))
                scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}
                for scene_id, fx in fx_updates.items():
                    sc = scene_map.get(scene_id)
                    if sc:
                        sc.fx = fx
                record.script_json = content.model_dump_json()
                session.add(record)
                session.commit()


def _phase_eli(ctx: ExportContext) -> None:
    """Phase 6: Generate Eli pose selection for all scenes (skips title cards)."""
    try:
        from pipeline.eli_animator import generate_scene_eli
    except ImportError:
        logger.warning("eli_animator module not found — skipping Eli phase")
        return

    non_tc = [sc for sc in ctx.scenes if not sc.get("is_title_card")]
    scene_count = len(non_tc)
    logger.info("[%s] Phase: eli — generating Eli poses for %d scenes", ctx.script_id, scene_count)

    content_now = _reload_content(ctx.script_id)
    eli_updates: dict[str, dict] = {}
    previous_corner: str | None = None
    for i, sc_info in enumerate(non_tc):
        _check_cancelled(ctx.job.id)
        p = _phase_progress(ctx, "eli", i / scene_count)
        update_job(ctx.job.id, progress=p, current_step=f"Generating Eli ({i+1}/{scene_count})...")
        scene_now = find_scene_in_content(content_now, sc_info["scene_id"])
        if scene_now.contains_person:
            continue
        try:
            eli_result = generate_scene_eli(
                scene_now.narration,
                previous_corner=previous_corner,
                script_id=ctx.script_id,
            )
            eli_updates[sc_info["scene_id"]] = eli_result
            previous_corner = eli_result.get("corner")
        except Exception as e:
            logger.warning("Failed Eli for scene %s: %s", sc_info["scene_id"], e)

    # Persist all Eli overlays in a single DB write
    if eli_updates:
        from database import engine
        with Session(engine) as session:
            record = session.get(Script, ctx.script_id)
            if record:
                content = ScriptContent.model_validate(json.loads(record.script_json))
                scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}
                for scene_id, eli_overlay in eli_updates.items():
                    sc = scene_map.get(scene_id)
                    if sc:
                        sc.eli_overlay = eli_overlay
                record.script_json = content.model_dump_json()
                session.add(record)
                session.commit()


def _phase_render(ctx: ExportContext) -> None:
    """Render only the first segment via Remotion (always runs). Sets ctx.video_url.

    Creates a filtered ScriptContent containing only the first segment, so
    render_full_video produces a short clip instead of the entire video.
    Uses timer-based progress instead of Remotion's sparse on_progress callbacks.
    """
    render_start, render_end = ctx.phase_ranges["render"]
    update_job(ctx.job.id, progress=render_start, current_step="Rendering first segment...")
    content_now = _reload_content(ctx.script_id)

    # Filter to first segment only
    first_seg_content = content_now.model_copy(update={"segments": content_now.segments[:1]})
    render_scene_count = sum(len(s.scenes) for s in first_seg_content.segments)

    logger.info("[%s] Phase: render — starting Remotion render (first segment, %d scenes)", ctx.script_id, render_scene_count)
    estimated = estimate_render_time(render_scene_count)
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
        _check_cancelled(ctx.job.id)
        ctx.video_url = render_full_video(
            script_id=ctx.script_id,
            content=first_seg_content,
            on_progress=None,
            cancel_check=lambda: _check_cancelled(ctx.job.id),
            title="",  # Don't copy to Downloads inside render_full_video — _phase_copy handles it
            speed=1.25,
            brand=ctx.brand_dict,
        )
    finally:
        stop_timer.set()
        timer.join(timeout=2)

    _check_cancelled(ctx.job.id)
    update_job(ctx.job.id, progress=render_end)
    logger.info("[%s] Phase: render — Remotion complete (first segment), output: %s", ctx.script_id, ctx.video_url)


def _phase_copy_to_downloads(ctx: ExportContext) -> None:
    """Phase 8: Copy rendered video to Downloads folder (always runs)."""
    logger.info("[%s] Phase: copy — copying to Downloads", ctx.script_id)
    update_job(ctx.job.id, progress=ctx.phase_ranges["copy"][0], current_step="Copying to Downloads...")
    projects_prefix = "/static/projects/"
    if ctx.video_url.startswith(projects_prefix):
        relative = ctx.video_url[len(projects_prefix):]
        src_path = str(DATA_DIR / "projects" / relative)
    else:
        src_path = ctx.video_url

    dest_name = shortform_video_filename(ctx.seg_name, 1, ctx.total_segments)
    dest_path = copy_to_project_downloads(ctx.project_title, src_path, dest_name)
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
        _check_cancelled(job.id)
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
            _check_cancelled(job.id)
            if p >= 0.4 and not timer_started.is_set():
                # Remotion render phase starting — switch to timer
                timer_started.set()
                timer.start()
                return
            if timer_started.is_set():
                if p >= 0.9:
                    # Post-processing phase (e.g. FFmpeg speed) — stop timer, show real step
                    stop_timer.set()
                    update_job(job.id, progress=p, current_step=msg)
                    return
                return  # Timer handles progress from here
            update_job(job.id, progress=p, current_step=msg)

        try:
            result = render_full_video(
                script_id=body.script_id,
                content=content,
                width=body.width,
                height=body.height,
                on_progress=on_progress,
                cancel_check=lambda: _check_cancelled(job.id),
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
    job_dict = job.to_dict()
    return RenderStatusResponse(**job_dict)

@router.get("/estimate", response_model=RenderEstimateResponse)
def render_estimate(
    scene_count: int = Query(..., ge=1),
    total_audio_duration: float = Query(0.0, ge=0),
):
    """Estimate render time based on scene count and historical averages."""
    estimated = estimate_render_time(scene_count, total_audio_duration)
    return RenderEstimateResponse(estimated_seconds=estimated)


@router.get("/rendered-longform", response_model=RenderedLongformResponse)
def rendered_longform(script_id: str, session: Session = Depends(get_session)):
    """Return whether a long-form video already exists in cache or export folder."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    project_title = record.topic_title or "Untitled"
    path, url = _find_rendered_longform(script_id, project_title)
    return RenderedLongformResponse(
        rendered=path is not None,
        path=path,
        url=url,
    )


class ExportThumbnailRequest(BaseModel):
    script_id: str


class ExportThumbnailResponse(BaseModel):
    folder_path: str
    file: str


@router.post("/export-thumbnail", response_model=ExportThumbnailResponse)
def export_thumbnail(body: ExportThumbnailRequest, session: Session = Depends(get_session)):
    """Copy the composite long-form thumbnail PNG into the project Downloads folder."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    project_title = record.topic_title or "Untitled"
    thumb_src = DATA_DIR / "projects" / body.script_id / "renders" / "thumbnails" / "0.png"
    if not thumb_src.is_file():
        raise HTTPException(
            status_code=400,
            detail="Long-form thumbnail has not been generated yet",
        )

    folder = project_downloads_folder(project_title)
    dest = folder / longform_filename("Thumbnail", project_title, ".png")
    shutil.copy2(str(thumb_src), str(dest))
    logger.info("Exported long-form thumbnail for script %s to %s", body.script_id, dest)
    return ExportThumbnailResponse(folder_path=str(folder), file=dest.name)


@router.post("/export-bundle", response_model=ExportBundleResponse)
def export_bundle(body: ExportBundleRequest, session: Session = Depends(get_session)):
    """Bundle video, thumbnail, and SEO into the project Downloads folder."""
    t0 = time.monotonic()
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    content = ensure_short_form_hook_scene_count(session, body.script_id, content, record)
    project_title = record.topic_title or "Untitled"
    folder = project_downloads_folder(project_title)

    renders_dir = DATA_DIR / "projects" / body.script_id / "renders"
    copied_files: list[str] = []
    (folder / longform_filename("Audio", project_title, ".mp3")).unlink(missing_ok=True)

    # Video — copy cached render, or acknowledge an already exported file.
    longform_path, _url = _find_rendered_longform(body.script_id, project_title)
    if longform_path:
        dest = folder / longform_filename("Video", project_title, ".mp4")
        if str(dest) != longform_path:
            shutil.copy2(longform_path, dest)
        copied_files.append(dest.name)

    # Thumbnail — auto-generate if missing
    thumb_src = renders_dir / "thumbnails" / "0.png"
    if not thumb_src.exists():
        try:
            from pipeline.thumbnail import get_composite_thumbnail
            get_composite_thumbnail(body.script_id)
        except Exception:
            logger.warning("Auto-generate thumbnail failed", exc_info=True)
    if thumb_src.exists():
        dest = folder / longform_filename("Thumbnail", project_title, ".png")
        shutil.copy2(str(thumb_src), dest)
        copied_files.append(dest.name)

    # SEO — auto-generate if missing
    if not content.seo_metadata:
        try:
            from pipeline.seo import generate_seo, format_timestamp

            segments: list[tuple[str, str]] = []
            elapsed = 0.0
            for seg in content.segments:
                segments.append((seg.name, format_timestamp(elapsed)))
                for scene in seg.scenes:
                    elapsed += scene.audio_duration_seconds

            brand = session.get(BrandProfile, record.brand_id)
            brand_context = brand.name if brand else ""

            metadata = generate_seo(
                video_title=content.title,
                segments=segments,
                video_description=record.topic_description,
                brand_context=brand_context,
                script_id=body.script_id,
            )
            content.seo_metadata = metadata.model_dump()
            record.script_json = content.model_dump_json()
            session.add(record)
            session.commit()
        except Exception:
            logger.warning("Auto-generate SEO failed", exc_info=True)

    if content.seo_metadata:
        seo_markdown = _format_longform_seo_markdown(content.seo_metadata)
        if seo_markdown.strip():
            (folder / longform_filename("SEO", project_title, ".txt")).unlink(missing_ok=True)
            dest = folder / longform_filename("SEO", project_title, ".md")
            dest.write_text(seo_markdown, encoding="utf-8")
            copied_files.append(dest.name)

    # Short-form SEO — auto-generate all shorts in one additional call if missing
    if not content.short_form_seo_metadata:
        try:
            from pipeline.seo import build_short_form_seo_contexts, generate_short_form_seo

            brand = session.get(BrandProfile, record.brand_id)
            brand_context = brand.name if brand else ""

            short_metadata = generate_short_form_seo(
                video_title=project_title,
                shorts=build_short_form_seo_contexts(content),
                video_description=record.topic_description,
                brand_context=brand_context,
                script_id=body.script_id,
            )
            content.short_form_seo_metadata = short_metadata.model_dump()
            record.script_json = content.model_dump_json()
            session.add(record)
            session.commit()
        except Exception:
            logger.warning("Auto-generate short-form SEO failed", exc_info=True)

    if content.short_form_seo_metadata:
        short_seo = content.short_form_seo_metadata
        short_items = short_seo.get("shorts", [])
        parsed_indices: list[int] = []
        for item in short_items:
            try:
                parsed_indices.append(int(item.get("index", -1)))
            except (TypeError, ValueError):
                parsed_indices.append(-1)
        uses_one_based_indices = 1 in parsed_indices
        total_segments = len(content.segments)
        for item_idx, item in enumerate(short_items):
            raw_index = item.get("index", "?")
            parsed_index = parsed_indices[item_idx]
            segment_idx = (
                parsed_index - 1 if uses_one_based_indices and parsed_index >= 0
                else parsed_index if parsed_index >= 0
                else item_idx
            )
            segment_name = (
                content.segments[segment_idx].name
                if 0 <= segment_idx < len(content.segments)
                else f"Short {raw_index}"
            )
            n = (segment_idx + 1) if 0 <= segment_idx < total_segments else (item_idx + 1)
            (folder / shortform_filename("SEO", segment_name, ".txt", index=n, total=total_segments)).unlink(missing_ok=True)
            dest = folder / shortform_filename("SEO", segment_name, ".md", index=n, total=total_segments)
            dest.write_text(_format_shortform_seo_markdown(item), encoding="utf-8")
            copied_files.append(dest.name)

    logger.info("Export bundle created at %s with %d files: %s", folder, len(copied_files), copied_files)

    session.add(GenerationDuration(operation_type="export_bundle", duration_seconds=time.monotonic() - t0))
    session.commit()

    return ExportBundleResponse(folder_path=str(folder), files=copied_files)


@router.post("/export-test", response_model=RenderJobResponse)
def start_export_test(body: ExportTestRequest, session: Session = Depends(get_session)):
    """Run the full pipeline (audio → image → FX → Eli → render) for the first segment."""
    content = _load_content(session, body.script_id)
    brand_dict = _load_brand(session, body.script_id)
    record = session.get(Script, body.script_id)
    project_title = record.topic_title if record and record.topic_title else content.title or "Untitled"

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

    # Collect all scenes in first segment for processing (including title cards)
    scenes_to_process: list[dict] = []
    global_idx = 0
    total_scenes = sum(len(seg.scenes) for seg in content.segments)
    for sci, scene in enumerate(first_seg.scenes):
        scenes_to_process.append({
            "scene_id": scene.id,
            "narration": scene.narration or "",
            "visual_prompt": scene.visual_prompt or "",
            "sc_idx": sci,
            "global_idx": global_idx,
            "is_title_card": scene.is_title_card,
        })
        global_idx += 1

    if not any(not sc["is_title_card"] for sc in scenes_to_process):
        raise HTTPException(status_code=400, detail="No non-title-card scenes in first segment")

    content_scene_count = sum(1 for sc in scenes_to_process if not sc["is_title_card"])
    regen_flags = [k for k, v in {"audio": body.regen_audio, "images": body.regen_images,
                                   "eli": body.regen_eli, "fx": body.regen_fx}.items() if v]
    logger.info("Starting export test for script %s, segment %r (%d scenes + %d title cards, regen: %s)",
                body.script_id, seg_name, content_scene_count,
                len(scenes_to_process) - content_scene_count,
                ", ".join(regen_flags) or "render only")
    job = create_job(scene_count=content_scene_count)
    job.estimated_seconds = estimate_render_time(content_scene_count)

    ctx = ExportContext(
        script_id=body.script_id,
        job=job,
        scenes=scenes_to_process,
        seg_name=seg_name,
        total_scenes=total_scenes,
        voice_id=voice_id,
        brand_dict=brand_dict,
        project_title=project_title,
        title=title,
        total_segments=len(content.segments),
        regen_images=body.regen_images,
        regen_audio=body.regen_audio,
        regen_fx=body.regen_fx,
        regen_eli=body.regen_eli,
    )

    def do_export_test():
        _build_phase_ranges(ctx)

        if ctx.regen_audio:
            _check_cancelled(ctx.job.id)
            _phase_audio(ctx)
        if ctx.regen_images:
            _check_cancelled(ctx.job.id)
            _phase_images(ctx)
        if ctx.regen_images or ctx.regen_audio:
            _check_cancelled(ctx.job.id)
            _phase_persist(ctx)
        if ctx.regen_fx:
            _check_cancelled(ctx.job.id)
            _phase_fx(ctx)
        if ctx.regen_eli:
            _check_cancelled(ctx.job.id)
            _phase_eli(ctx)

        _check_cancelled(ctx.job.id)
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


@router.post("/preview-scene", response_model=RenderJobResponse)
def start_scene_preview(body: RenderScenePreviewRequest, session: Session = Depends(get_session)):
    """Render a single scene as a standalone video clip."""
    content = _load_content(session, body.script_id)
    brand_dict = _load_brand(session, body.script_id)

    try:
        scene = find_scene_in_content(content, body.scene_id)
    except RuntimeError:
        raise HTTPException(status_code=404, detail="Scene not found")

    from models.script import Segment
    single_scene_content = content.model_copy(update={
        "segments": [Segment(name="preview", scenes=[scene])]
    })

    job = create_job(scene_count=1)
    job.estimated_seconds = estimate_render_time(1)

    def do_render():
        render_start = 0.0
        render_end = 1.0
        estimated = estimate_render_time(1)
        stop_timer = threading.Event()

        def _timer_updater():
            start = time.monotonic()
            while not stop_timer.is_set():
                elapsed = time.monotonic() - start
                frac = min(0.95, elapsed / estimated) if estimated > 0 else 0.5
                progress = render_start + frac * (render_end - render_start)
                update_job(job.id, progress=progress, current_step="Rendering scene preview...")
                stop_timer.wait(1.0)

        timer = threading.Thread(target=_timer_updater, daemon=True)
        timer.start()

        try:
            video_url = render_full_video(
                script_id=body.script_id,
                content=single_scene_content,
                on_progress=None,
                title="",
                brand=brand_dict,
            )
        finally:
            stop_timer.set()
            timer.join(timeout=2)

        return video_url

    run_in_background(job.id, do_render)
    return RenderJobResponse(job_id=job.id)
