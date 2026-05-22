"""Endpoints for video rendering and export."""

import json
import logging
import shutil
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR, VIDEO_HEIGHT, VIDEO_WIDTH
from api.short_form_hooks import ensure_short_form_hook_scene_count
from database import get_default_brand_id, get_session
from pipeline.script_utils import find_scene_in_content
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.render_jobs import create_job, estimate_render_time, get_job, run_in_background, update_job
from pipeline.remotion_render import render_full_video
from pipeline.render_cache import is_render_up_to_date
from pipeline.render_phases import (
    ExportContext,
    _build_phase_ranges,
    _check_cancelled,
    _phase_audio,
    _phase_copy_to_downloads,
    _phase_eli,
    _phase_fx,
    _phase_images,
    _phase_persist,
    _phase_render,
)
from pipeline.export_paths import (
    has_export_label,
    longform_filename,
    project_downloads_folder,
    shortform_filename,
)
from pipeline.script_helpers import _format_longform_seo_markdown, _format_shortform_seo_markdown

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


def _find_rendered_longform(script_id: str, project_title: str) -> tuple[str | None, str | None]:
    """Return an existing long-form render path and optional web URL.

    Stale renders (older than any source image/audio file) are ignored so the
    caller will re-render when assets have been regenerated.
    """
    renders_dir = DATA_DIR / "projects" / script_id / "renders"
    if renders_dir.exists():
        candidates = sorted(
            renders_dir.glob("full_youtube*.mp4"),
            key=lambda path: (path.name != "full_youtube.mp4", path.name),
        )
        for mp4 in candidates:
            if mp4.is_file() and is_render_up_to_date(mp4, script_id):
                return str(mp4), f"/static/projects/{script_id}/renders/{mp4.name}"

    folder = project_downloads_folder(project_title, create=False)
    exported = folder / longform_filename("Video", project_title, ".mp4")
    if exported.is_file() and is_render_up_to_date(exported, script_id):
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
        for video in exported_videos:
            if is_render_up_to_date(video, script_id):
                return str(video), None

    return None, None

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
            _check_cancelled(job.id)
            video_url = render_full_video(
                script_id=body.script_id,
                content=single_scene_content,
                on_progress=None,
                cancel_check=lambda: _check_cancelled(job.id),
                title="",
                brand=brand_dict,
            )
        finally:
            stop_timer.set()
            timer.join(timeout=2)

        _check_cancelled(job.id)
        return video_url

    run_in_background(job.id, do_render)
    return RenderJobResponse(job_id=job.id)
