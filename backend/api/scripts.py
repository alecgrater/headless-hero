"""Endpoints for AI-powered script generation."""

import json
import logging
import os
import shutil
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from api.short_form_hooks import ensure_short_form_hook_scene_count
from database import get_default_brand_id, get_session, engine
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.project_config import ProjectConfig
from models.script import (
    GenerateScriptRequest,
    HookScore,
    RefineSceneRequest,
    RefineSceneResponse,
    Scene,
    Script,
    ScriptContent,
    ScriptRead,
    ScriptSummary,
    UploadTracking,
    UpdateScriptRequest,
    UpdateScriptTitleRequest,
)
from models.publish import PublishRecord
from pipeline.refine import refine_scene
from pipeline.render_cache import mark_render_inputs_changed
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job
from pipeline.formats import resolve_format
from pipeline.scriptwriter import generate_script
from pipeline.script_rating import rate_script
from pipeline.audio_split import split_scene_audio
from pipeline.hook_scorer import score_hook
from pipeline.media_analyzer import analyze_media_sources, apply_assignments
from pipeline.export_paths import project_downloads_folder, rename_project_exports
from pipeline.script_helpers import (
    _find_exports_folder_for_title_rename,
    _normalize_exported_longform_filenames,
    _refresh_exported_seo_files,
    _usage_task_label,
)
from pipeline.seo import retitle_short_form_seo_metadata
from prompts import CHARACTER_SPEC_MD, IMAGE_VISUAL_STYLE

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _collect_hook_scenes(content: ScriptContent, max_scenes: int = 5, max_seconds: float = 30.0) -> list[Scene]:
    """Collect first non-title-card scenes up to max_scenes or max_seconds."""
    scenes: list[Scene] = []
    total = 0.0
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.is_title_card:
                continue
            scenes.append(scene)
            total += scene.duration_estimate_seconds
            if len(scenes) >= max_scenes or total >= max_seconds:
                return scenes
    return scenes

_VISUAL_STYLE = IMAGE_VISUAL_STYLE.template
_CHARACTER = CHARACTER_SPEC_MD.template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


def _sync_remote_profile_input_async(reason: str) -> None:
    """Upload the remote profile input snapshot after script-library changes."""

    def _sync() -> None:
        try:
            from api.trending import _upload_content_profile_input

            status = _upload_content_profile_input()
            if status.status == "uploaded":
                logger.info("Remote profile input synced after %s", reason)
            elif status.status == "warning":
                logger.warning("Remote profile input sync after %s failed: %s", reason, status.message)
            else:
                logger.info("Remote profile input sync after %s skipped: %s", reason, status.message)
        except Exception:
            logger.exception("Remote profile input sync after %s crashed", reason)

    threading.Thread(
        target=_sync,
        name=f"remote-profile-input-sync-{reason}",
        daemon=True,
    ).start()


def _build_upload_tracking(session: Session, script_id: str) -> UploadTracking:
    """Derive aggregate upload tracking from publish history and manual toggles."""
    stmt = select(PublishRecord).where(
        PublishRecord.script_id == script_id,
    )
    records = session.exec(stmt).all()

    field_map = {
        ("long_form", "youtube"): "longform_youtube",
        ("short_form", "youtube"): "shortform_youtube",
        ("short_form", "instagram"): "shortform_instagram",
        ("short_form", "tiktok"): "shortform_tiktok",
    }
    latest: dict[str, tuple[datetime, bool]] = {}

    for r in records:
        field = field_map.get((r.asset_kind, r.platform))
        if not field:
            continue

        value: bool | None = None
        if r.upload_batch_id == "manual" and r.status == "not_uploaded":
            value = False
        elif r.status in ("published", "scheduled"):
            value = True

        if value is None:
            continue

        changed_at = r.updated_at or r.created_at
        current = latest.get(field)
        if current is None or changed_at >= current[0]:
            latest[field] = (changed_at, value)

    tracking = UploadTracking()
    for field, (_, value) in latest.items():
        setattr(tracking, field, value)
    return tracking


def _build_summary(record: Script, session: Session | None = None) -> ScriptSummary:
    """Build a ScriptSummary from a Script record."""
    content = ScriptContent.model_validate(json.loads(record.script_json))
    scenes = content.all_scenes()
    image_count = sum(1 for s in scenes if s.image_url)
    audio_count = sum(1 for s in scenes if s.audio_url)

    renders_dir = DATA_DIR / "projects" / record.id / "renders"
    has_renders = renders_dir.exists() and any(renders_dir.iterdir())

    # Prefer the active long-form thumbnail, then format-specific source
    # thumbnails, and finally fall back to the first scene image.
    thumbnail_url = ""
    thumbnail_candidates = [
        (
            DATA_DIR / "projects" / record.id / "renders" / "thumbnails" / "0.png",
            f"/static/projects/{record.id}/renders/thumbnails/0.png",
        ),
        (
            DATA_DIR / "projects" / record.id / "images" / "cinematic_thumbnail.png",
            f"/static/projects/{record.id}/images/cinematic_thumbnail.png",
        ),
        (
            DATA_DIR / "projects" / record.id / "images" / "composite_title_card.png",
            f"/static/projects/{record.id}/images/composite_title_card.png",
        ),
    ]
    for path, url in thumbnail_candidates:
        if path.exists():
            thumbnail_url = url
            break
    if not thumbnail_url:
        for s in scenes:
            if s.image_url:
                thumbnail_url = s.image_url
                break

    # Derive status
    if has_renders:
        status = "exported"
    elif audio_count > 0:
        status = "audio"
    elif image_count > 0:
        status = "images"
    else:
        status = "script"

    upload_tracking = _build_upload_tracking(session, record.id) if session else UploadTracking()
    return ScriptSummary(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        created_at=record.created_at,
        segment_count=len(content.segments),
        scene_count=len(scenes),
        image_count=image_count,
        audio_count=audio_count,
        has_renders=has_renders,
        thumbnail_url=thumbnail_url,
        format_id=content.format_id,
        status=status,
        hook_score_overall=content.hook_score.get("overall") if isinstance(content.hook_score, dict) else None,
        script_rating_overall=content.script_rating.overall if content.script_rating else None,
        upload_tracking=upload_tracking,
    )


@router.get("", response_model=list[ScriptSummary])
def list_scripts(session: Session = Depends(get_session)):
    statement = (
        select(Script)
        .where(Script.is_test_lab == False)  # noqa: E712
        .order_by(Script.created_at.desc())  # type: ignore[arg-type]
    )
    records = session.exec(statement).all()
    return [_build_summary(r, session) for r in records]


class SetUploadTrackingRequest(BaseModel):
    longform_youtube: bool | None = None
    shortform_youtube: bool | None = None
    shortform_instagram: bool | None = None
    shortform_tiktok: bool | None = None


class ScriptExportsFolderResponse(BaseModel):
    folder_path: str


@router.post("/{script_id}/exports-folder", response_model=ScriptExportsFolderResponse)
def ensure_script_exports_folder(script_id: str, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    title = record.topic_title or content.title or "Untitled"
    source_folder = _find_exports_folder_for_title_rename(title, title, content)
    folder = (
        rename_project_exports(title, title, source_folder=source_folder)
        if source_folder
        else project_downloads_folder(title, create=True)
    )
    _normalize_exported_longform_filenames(title, folder)
    _refresh_exported_seo_files(title, content, folder)
    return ScriptExportsFolderResponse(folder_path=str(folder))


@router.get("/{script_id}/upload-tracking", response_model=UploadTracking)
def get_upload_tracking(script_id: str, session: Session = Depends(get_session)):
    """Return derived upload tracking for a script (from PublishRecord + manual overrides)."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")
    return _build_upload_tracking(session, script_id)


@router.post("/{script_id}/upload-tracking", response_model=UploadTracking)
def set_upload_tracking(
    script_id: str,
    body: SetUploadTrackingRequest,
    session: Session = Depends(get_session),
):
    """Manually set upload tracking flags by inserting synthetic PublishRecord rows."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    from database import get_default_brand_id

    brand_id = get_default_brand_id(session)
    now = datetime.now(timezone.utc)

    def _set_flag(asset_kind: str, platform: str, value: bool):
        """Toggle aggregate tracking without deleting real upload history."""
        stmt = select(PublishRecord).where(
            PublishRecord.script_id == script_id,
            PublishRecord.asset_kind == asset_kind,
            PublishRecord.platform == platform,
            PublishRecord.upload_batch_id == "manual",
        )
        existing = session.exec(stmt).all()
        for r in existing:
            session.delete(r)

        session.add(
            PublishRecord(
                script_id=script_id,
                brand_id=brand_id,
                platform=platform,
                asset_kind=asset_kind,
                status="published" if value else "not_uploaded",
                upload_batch_id="manual",
                published_at=now if value else None,
                updated_at=now,
            )
        )

    field_map = {
        "longform_youtube": ("long_form", "youtube"),
        "shortform_youtube": ("short_form", "youtube"),
        "shortform_instagram": ("short_form", "instagram"),
        "shortform_tiktok": ("short_form", "tiktok"),
    }
    for field, (asset_kind, platform) in field_map.items():
        val = getattr(body, field)
        if val is not None:
            _set_flag(asset_kind, platform, val)

    session.commit()
    return _build_upload_tracking(session, script_id)


@router.delete("/{script_id}")
def delete_script(script_id: str, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    # Clean up associated ProjectConfig row first (no FK cascade configured).
    existing_cfg = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if existing_cfg:
        session.delete(existing_cfg)

    session.delete(record)
    session.commit()
    _sync_remote_profile_input_async("script_deleted")

    # Clean up project files
    project_dir = DATA_DIR / "projects" / script_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

    logger.info("Deleted script %s", script_id)
    return {"ok": True}


class GenerateJobResponse(BaseModel):
    job_id: str


@router.post("/generate", response_model=GenerateJobResponse)
def generate(body: GenerateScriptRequest, session: Session = Depends(get_session)):
    # Auto-resolve brand_id from default brand
    brand_id = body.brand_id or get_default_brand_id(session)
    brand = session.get(BrandProfile, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    fmt = resolve_format(body.format_id)

    logger.info("Script generation requested: topic=%r, brand_id=%s, format_id=%s", body.topic, brand_id, fmt.id)

    from models.settings import AppSetting

    if body.eli_enabled is not None:
        resolved_eli_enabled = body.eli_enabled
    else:
        eli_setting = session.get(AppSetting, "ELI_ENABLED_DEFAULT")
        resolved_eli_enabled = (eli_setting.value if eli_setting else "false").lower() == "true"

    # Dedup: if an identical script was created in the last 60 seconds, return it as a completed job
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    existing = session.exec(
        select(Script)
        .where(
            Script.brand_id == brand_id,
            Script.topic_title == body.topic,
            Script.created_at >= cutoff,
            Script.is_test_lab == False,  # noqa: E712
        )
        .order_by(Script.created_at.desc())  # type: ignore[arg-type]
    ).first()
    if existing:
        # If the existing script has a different eli_enabled mode than the
        # incoming request, skip the dedup so we don't return a script with
        # the wrong character configuration.
        existing_cfg = session.exec(
            select(ProjectConfig).where(ProjectConfig.script_id == existing.id)
        ).first()
        existing_eli_enabled = existing_cfg.eli_enabled if existing_cfg else True
        if existing_eli_enabled == resolved_eli_enabled:
            # Create an already-completed job pointing to the existing script
            job = create_job()
            update_job(job.id, status="completed", progress=1.0, current_step="Complete", output_urls=[existing.id])
            return GenerateJobResponse(job_id=job.id)

    # Build brand context string with universal style + character
    parts = [brand.name]
    if _VISUAL_STYLE:
        parts.append(f"Visual Style:\n{_VISUAL_STYLE}")
    if _CHARACTER:
        parts.append(f"Character:\n{_CHARACTER}")
    brand_context = "\n\n".join(parts)

    brand_dict = {
        "name": brand.name,
    }

    # Capture request params for the background thread
    topic = body.topic
    description = body.description
    creator_guidance = body.creator_guidance
    animated_scene_count = body.animated_scene_count
    model = body.model
    segmented = body.segmented
    cold_open_text = body.cold_open_text
    eli_enabled = resolved_eli_enabled
    # Resolve style_preset_enabled: use explicit value, else fall back to AppSettings
    if body.style_preset_enabled is not None:
        style_preset_enabled = body.style_preset_enabled
    else:
        style_setting = session.get(AppSetting, "STYLE_PRESET_ENABLED_DEFAULT")
        style_preset_enabled = (style_setting.value if style_setting else "true").lower() == "true"
    ai_video_enabled = os.environ.get("AI_VIDEO_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    try:
        ai_video_scenes_per_segment = int(os.environ.get("AI_VIDEO_SCENES_PER_SEGMENT", "2"))
    except ValueError:
        ai_video_scenes_per_segment = 2
    ai_video_scenes_per_segment = max(0, min(ai_video_scenes_per_segment, 5))
    format_id = fmt.id
    supports_hook_scoring = fmt.supports_hook_scoring

    job = create_job()
    job_id = job.id
    script_id = uuid.uuid4().hex

    def _run_generation() -> list[str]:
        def _progress(segment: int, total: int, name: str) -> None:
            update_job(job_id, current_step=json.dumps({
                "segment": segment,
                "total": total,
                "name": name,
            }))

        logger.info("Background script gen started: job=%s, topic=%r", job_id, topic)
        t0 = time.monotonic()
        script_content = generate_script(
            topic=topic,
            description=description,
            creator_guidance=creator_guidance,
            brand_context=brand_context,
            animated_scene_count=animated_scene_count,
            brand=brand_dict,
            model=model,
            segmented=segmented,
            cold_open_text=cold_open_text,
            progress_callback=_progress,
            script_id=script_id,
            format_id=format_id,
            eli_enabled=eli_enabled,
        )
        script_content.ai_video_enabled = ai_video_enabled
        duration = time.monotonic() - t0

        # Persist to SQLite using a fresh session (background thread)
        from sqlmodel import Session as SqlSession
        with SqlSession(engine) as bg_session:
            bg_session.add(GenerationDuration(operation_type="script_generation_youtube", duration_seconds=duration))
            record = Script(
                id=script_id,
                brand_id=brand_id,
                format_id=format_id,
                topic_title=topic,
                topic_description=description,
                script_json=script_content.model_dump_json(),
            )
            bg_session.add(record)
            bg_session.commit()
            bg_session.refresh(record)

            from models.project_config import get_or_create_project_config

            get_or_create_project_config(
                bg_session, script_id, eli_enabled=eli_enabled, style_preset_enabled=style_preset_enabled
            )
            bg_session.commit()

        logger.info("Script generated: %s (%d segments) in %.1fs", script_id, len(script_content.segments), duration)

        try:
            update_job(job_id, current_step="Rating script...")
            t_rating = time.monotonic()
            script_content.script_rating = rate_script(script_content, script_id=script_id)
            with SqlSession(engine) as rating_session:
                record_rating = rating_session.get(Script, script_id)
                if record_rating:
                    record_rating.script_json = script_content.model_dump_json()
                    rating_session.add(record_rating)
                rating_session.add(GenerationDuration(operation_type="script_rating", duration_seconds=time.monotonic() - t_rating))
                rating_session.commit()
            logger.info("Script rated for %s: overall=%.1f", script_id, script_content.script_rating.overall)
        except Exception:
            logger.exception("Script rating failed for %s — script saved without rating", script_id)

        if ai_video_enabled and animated_scene_count > 0:
            try:
                update_job(job_id, current_step="Analyzing visual modes...")
                assignments = analyze_media_sources(
                    script_content,
                    gameplay_enabled=False,
                    stock_photo_enabled=False,
                    ai_video_enabled=ai_video_enabled,
                    animated_scene_count=animated_scene_count,
                    ai_video_scenes_per_segment=ai_video_scenes_per_segment,
                    script_id=script_id,
                )
                apply_assignments(script_content, assignments)
                with SqlSession(engine) as media_session:
                    record_media = media_session.get(Script, script_id)
                    if record_media:
                        record_media.script_json = script_content.model_dump_json()
                        media_session.add(record_media)
                        media_session.commit()
                logger.info("Visual modes assigned for %s", script_id)
            except Exception:
                logger.exception("Visual mode analysis failed for %s — keeping default AI routing", script_id)

        # Auto-score the hook on the final generated script
        try:
            hook_scenes = _collect_hook_scenes(script_content)

            if supports_hook_scoring and hook_scenes:
                update_job(job_id, current_step="Scoring hook...")
                t_hook = time.monotonic()
                hook_result = score_hook(script_content.intro_hook, hook_scenes, script_content.title, script_id)
                script_content.hook_score = hook_result.model_dump()
                with SqlSession(engine) as bg_session2:
                    record2 = bg_session2.get(Script, script_id)
                    if record2:
                        record2.script_json = script_content.model_dump_json()
                        bg_session2.add(record2)
                    bg_session2.add(GenerationDuration(operation_type="hook_score", duration_seconds=time.monotonic() - t_hook))
                    bg_session2.commit()
                logger.info("Hook scored for %s: overall=%d", script_id, hook_result.overall)
            elif not supports_hook_scoring:
                logger.info("Skipping hook scoring for format %s", format_id)
        except Exception:
            logger.exception("Hook scoring failed for %s — script saved without score", script_id)

        try:
            update_job(job_id, current_step="Detecting short-form hook...")
            with SqlSession(engine) as hook_session:
                record_hook = hook_session.get(Script, script_id)
                if record_hook:
                    script_content = ensure_short_form_hook_scene_count(
                        hook_session,
                        script_id,
                        script_content,
                        record_hook,
                    )
        except Exception:
            logger.exception("Hook scene detection failed for %s — short-form render will retry later", script_id)

        _sync_remote_profile_input_async("script_generated")
        return [script_id]

    run_in_background(job_id, _run_generation)
    return GenerateJobResponse(job_id=job_id)


@router.get("/generate-status/{job_id}")
def generate_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    # If completed, include script_id for convenience
    if job.status == "completed" and job.output_urls:
        result["script_id"] = job.output_urls[0]
    return result


def _script_rating_signature(content: ScriptContent) -> dict:
    """Return the text/story fields that make a saved script rating valid."""
    return {
        "title": content.title,
        "intro_hook": content.intro_hook,
        "outro_cta": content.outro_cta,
        "card_title": content.card_title,
        "card_subtitle": content.card_subtitle,
        "segments": [
            {
                "name": segment.name,
                "short_name": segment.short_name,
                "scenes": [
                    {
                        "id": scene.id,
                        "is_title_card": scene.is_title_card,
                        "narration": scene.narration,
                        "visual_prompt": scene.visual_prompt,
                        "caption_text": scene.caption_text,
                        "caption_emphasis": scene.caption_emphasis,
                    }
                    for scene in segment.scenes
                ],
            }
            for segment in content.segments
        ],
    }


@router.put("/{script_id}", response_model=ScriptRead)
def update_script(script_id: str, body: UpdateScriptRequest, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = body.script.model_copy(update={"title": record.topic_title or body.script.title})
    prev_content: ScriptContent | None = None

    # Clear legacy hidden TTS text when narration is edited.
    try:
        prev_content = ScriptContent.model_validate(json.loads(record.script_json))
        prev_narration = {sc.id: sc.narration for seg in prev_content.segments for sc in seg.scenes}
        for seg in content.segments:
            for sc in seg.scenes:
                if prev_narration.get(sc.id) != sc.narration:
                    sc.tts_narration = ""
    except Exception:
        logger.exception("Failed to clear legacy tts_narration on edited scenes; continuing")

    if prev_content is not None:
        if _script_rating_signature(prev_content) != _script_rating_signature(content):
            content.script_rating = None
        elif prev_content.script_rating is not None:
            content.script_rating = prev_content.script_rating

    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    session.refresh(record)
    mark_render_inputs_changed(script_id)
    _sync_remote_profile_input_async("script_updated")

    logger.info("Updated script %s", script_id)
    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=content,
        created_at=record.created_at,
    )

@router.put("/{script_id}/title", response_model=ScriptRead)
def update_script_title(
    script_id: str,
    body: UpdateScriptTitleRequest,
    session: Session = Depends(get_session),
):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be blank")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    old_title = record.topic_title or content.title or "Untitled"
    logger.info("Updating script title for %s from %r to %r", script_id, old_title, title)
    content.title = title
    if content.seo_metadata:
        youtube = content.seo_metadata.get("youtube")
        if isinstance(youtube, dict) and str(youtube.get("title", "")).strip() == old_title.strip():
            youtube["title"] = title
            logger.info("Retitled stored long-form SEO title for script %s", script_id)
        else:
            logger.info("Kept stored long-form SEO title for script %s because it was custom", script_id)
    else:
        logger.info("No stored long-form SEO metadata to retitle for script %s", script_id)
    short_count = len((content.short_form_seo_metadata or {}).get("shorts", []))
    content.short_form_seo_metadata = retitle_short_form_seo_metadata(
        content.short_form_seo_metadata,
        title,
        content,
    )
    if short_count:
        logger.info("Retitled stored short-form SEO titles for %d shorts in script %s", short_count, script_id)
    else:
        logger.info("No stored short-form SEO metadata to retitle for script %s", script_id)
    source_folder = _find_exports_folder_for_title_rename(old_title, title, content)
    folder = rename_project_exports(old_title, title, source_folder=source_folder)
    _normalize_exported_longform_filenames(title, folder)
    _refresh_exported_seo_files(title, content, folder)
    record.topic_title = title
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    session.refresh(record)
    mark_render_inputs_changed(script_id)
    _sync_remote_profile_input_async("script_title_updated")

    logger.info("Updated script title %s and persisted title rename actions", script_id)
    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=content,
        created_at=record.created_at,
    )

@router.get("/{script_id}", response_model=ScriptRead)
def get_script(script_id: str, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=ScriptContent.model_validate(json.loads(record.script_json)),
        created_at=record.created_at,
    )


class ScriptCostResponse(BaseModel):
    script_id: str
    total_cost: float
    breakdown: list[dict]


@router.get("/{script_id}/cost", response_model=ScriptCostResponse)
def get_script_cost(script_id: str, session: Session = Depends(get_session)):
    """Return the total estimated cost for a script based on API usage records."""
    from models.api_usage import ApiUsage

    rows = session.exec(select(ApiUsage).where(ApiUsage.script_id == script_id)).all()
    grouped = defaultdict(lambda: {
        "task": "",
        "service": "",
        "operation": "",
        "model": "",
        "call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "characters": 0,
        "images": 0,
        "total_cost": 0.0,
    })

    for row in rows:
        task = _usage_task_label(row.service, row.operation, row.metadata_json)
        key = (task, row.service, row.operation, row.model)
        item = grouped[key]
        item["task"] = task
        item["service"] = row.service
        item["operation"] = row.operation
        item["model"] = row.model
        item["call_count"] += 1
        item["input_tokens"] += row.input_tokens
        item["output_tokens"] += row.output_tokens
        item["characters"] += row.characters
        item["images"] += row.images
        item["total_cost"] += row.cost_estimate

    breakdown = sorted(grouped.values(), key=lambda item: item["total_cost"], reverse=True)
    for item in breakdown:
        item["total_cost"] = round(float(item["total_cost"]), 4)

    total_cost = round(sum(item["total_cost"] for item in breakdown), 4)
    return ScriptCostResponse(script_id=script_id, total_cost=total_cost, breakdown=breakdown)


@router.post("/{script_id}/refine-scene", response_model=RefineSceneResponse)
def refine_scene_endpoint(
    script_id: str,
    body: RefineSceneRequest,
    session: Session = Depends(get_session),
):
    t0 = time.monotonic()
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    script_content = ScriptContent.model_validate(json.loads(record.script_json))

    if body.segment_index < 0 or body.segment_index >= len(script_content.segments):
        raise HTTPException(status_code=400, detail="Invalid segment index")

    segment = script_content.segments[body.segment_index]
    if not any(s.id == body.scene_id for s in segment.scenes):
        raise HTTPException(status_code=400, detail="Scene not found in segment")

    logger.info("Refining scene %s in script %s", body.scene_id, script_id)
    refined = refine_scene(script_content, body.segment_index, body.scene_id)

    session.add(GenerationDuration(operation_type="scene_refinement", duration_seconds=time.monotonic() - t0))
    session.commit()

    return RefineSceneResponse(scene=refined)


class SplitSceneRequest(BaseModel):
    scene_id: str
    split_time_ms: int


@router.post("/{script_id}/split-scene", response_model=ScriptRead)
def split_scene_endpoint(
    script_id: str,
    body: SplitSceneRequest,
    session: Session = Depends(get_session),
):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    script_content = ScriptContent.model_validate(json.loads(record.script_json))

    # Find the scene and its segment
    target_seg_idx = None
    target_scene_idx = None
    target_scene = None
    for si, seg in enumerate(script_content.segments):
        for sci, sc in enumerate(seg.scenes):
            if sc.id == body.scene_id:
                target_seg_idx = si
                target_scene_idx = sci
                target_scene = sc
                break
        if target_scene is not None:
            break

    if target_scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")

    if not target_scene.audio_url:
        raise HTTPException(status_code=422, detail="Scene has no audio to split")

    # Perform the split
    scene_dict = target_scene.model_dump()
    scene_a, scene_b = split_scene_audio(script_id, scene_dict, body.split_time_ms)

    # Splice into the segment: replace original with [A, B]
    segment = script_content.segments[target_seg_idx]
    new_scenes = list(segment.scenes)
    new_scenes[target_scene_idx:target_scene_idx + 1] = [
        Scene.model_validate(scene_a),
        Scene.model_validate(scene_b),
    ]
    segment.scenes = new_scenes

    # Persist
    record.script_json = script_content.model_dump_json()
    session.add(record)
    session.commit()
    session.refresh(record)
    _sync_remote_profile_input_async("script_split")

    logger.info("Split scene %s in script %s at %dms", body.scene_id, script_id, body.split_time_ms)

    return ScriptRead(
        id=record.id,
        brand_id=record.brand_id,
        topic_title=record.topic_title,
        topic_description=record.topic_description,
        script=script_content,
        created_at=record.created_at,
    )


class HookScoreResponse(BaseModel):
    hook_score: HookScore


@router.post("/{script_id}/hook-score", response_model=HookScoreResponse)
def hook_score_endpoint(script_id: str, session: Session = Depends(get_session)):
    t0 = time.monotonic()
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    hook_scenes = _collect_hook_scenes(content)

    if not hook_scenes:
        raise HTTPException(status_code=422, detail="No scorable scenes found")

    result = score_hook(content.intro_hook, hook_scenes, content.title, script_id)

    # Persist
    content.hook_score = result.model_dump()
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    session.add(GenerationDuration(operation_type="hook_score", duration_seconds=time.monotonic() - t0))
    session.commit()

    return {"hook_score": result.model_dump()}
