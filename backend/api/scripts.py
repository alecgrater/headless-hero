"""Endpoints for AI-powered script generation."""

import json
import logging
import os
import shutil
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
    GenerateScriptResponse,
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
from pipeline.audio_split import split_scene_audio
from pipeline.hook_scorer import score_hook
from pipeline.media_analyzer import analyze_media_sources, apply_assignments
from pipeline.export_paths import (
    downloads_base,
    has_export_label,
    longform_filename,
    project_downloads_folder,
    rename_project_exports,
    shortform_filename,
    shortform_video_filename,
)
from pipeline.seo import retitle_short_form_seo_metadata
from prompts import CHARACTER_SPEC_MD, IMAGE_VISUAL_STYLE

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _short_item_index(item: dict, fallback_index: int, uses_one_based_indices: bool) -> int:
    try:
        raw = int(item.get("index", -1))
    except (TypeError, ValueError):
        raw = -1
    if uses_one_based_indices and raw >= 1:
        return raw - 1
    if raw >= 0:
        return raw
    return fallback_index


def _refresh_exported_seo_files(project_title: str, content: ScriptContent, folder: Path) -> None:
    """Rewrite exported SEO markdown after title-derived names or titles change."""
    if not folder.is_dir():
        logger.info("Skipped exported SEO refresh because project folder is missing: %s", folder)
        return

    from api.render import _format_longform_seo_markdown, _format_shortform_seo_markdown

    if content.seo_metadata:
        seo_markdown = _format_longform_seo_markdown(content.seo_metadata)
        if seo_markdown.strip():
            (folder / longform_filename("SEO", project_title, ".txt")).unlink(missing_ok=True)
            dest = folder / longform_filename("SEO", project_title, ".md")
            dest.write_text(seo_markdown, encoding="utf-8")
            logger.info("Refreshed exported long-form SEO markdown: %s", dest)
    else:
        logger.info("Skipped exported long-form SEO refresh because metadata is missing")

    short_items = (content.short_form_seo_metadata or {}).get("shorts", [])
    if not isinstance(short_items, list) or not short_items:
        logger.info("Skipped exported short-form SEO refresh because metadata is missing")
        return
    parsed_indices: list[int] = []
    for item in short_items:
        try:
            parsed_indices.append(int(item.get("index", -1)))
        except (AttributeError, TypeError, ValueError):
            parsed_indices.append(-1)
    uses_one_based_indices = 1 in parsed_indices
    total_segments = len(content.segments)
    for item_idx, item in enumerate(short_items):
        if not isinstance(item, dict):
            continue
        segment_idx = _short_item_index(item, item_idx, uses_one_based_indices)
        segment_name = (
            content.segments[segment_idx].name
            if 0 <= segment_idx < total_segments
            else f"Short {item.get('index', '?')}"
        )
        n = (segment_idx + 1) if 0 <= segment_idx < total_segments else (item_idx + 1)
        (folder / shortform_filename("SEO", segment_name, ".txt", index=n, total=total_segments)).unlink(missing_ok=True)
        dest = folder / shortform_filename("SEO", segment_name, ".md", index=n, total=total_segments)
        dest.write_text(
            _format_shortform_seo_markdown(item),
            encoding="utf-8",
        )
        logger.info("Refreshed exported short-form SEO markdown: %s", dest)


def _normalize_exported_longform_filenames(project_title: str, folder: Path) -> None:
    """Retitle long-form export filenames inside a known project folder."""
    if not folder.is_dir():
        logger.info("Skipped long-form export filename normalization because project folder is missing: %s", folder)
        return

    for file in sorted(folder.iterdir(), key=lambda path: path.name):
        if not file.is_file():
            continue
        for asset in ("Video", "Thumbnail", "SEO"):
            if not has_export_label(file.name, "Longform", asset):
                continue
            dest = folder / longform_filename(asset, project_title, file.suffix)
            if file == dest:
                break
            if dest.exists():
                if asset == "SEO":
                    file.unlink()
                    logger.info("Removed stale exported long-form SEO filename after title rename: %s", file)
                else:
                    logger.info("Skipped long-form export filename rename because destination exists: %s", dest)
                break
            file.rename(dest)
            logger.info("Renamed long-form export file %s to %s", file, dest)
            break


def _exports_folder_score(folder: Path, content: ScriptContent) -> int:
    """Score how confidently a project export folder belongs to this script."""
    if not folder.is_dir():
        return 0

    short_asset_score = 0
    total = len(content.segments)
    for idx, segment in enumerate(content.segments):
        n = idx + 1
        if (folder / shortform_video_filename(segment.name, n, total)).is_file():
            short_asset_score += 6
        if (folder / shortform_filename("Thumbnail", segment.name, ".png", index=n, total=total)).is_file():
            short_asset_score += 3
        if (folder / shortform_filename("SEO", segment.name, ".md", index=n, total=total)).is_file():
            short_asset_score += 2

    if short_asset_score == 0:
        return 0

    score = short_asset_score
    for file in folder.iterdir():
        if not file.is_file():
            continue
        if has_export_label(file.name, "Longform", "Video"):
            score += 5
        elif has_export_label(file.name, "Longform", "Thumbnail"):
            score += 3
        elif has_export_label(file.name, "Longform", "SEO"):
            score += 2
    return score


def _find_exports_folder_for_title_rename(old_title: str, new_title: str, content: ScriptContent) -> Path | None:
    """Find existing exports even when a previous title edit left the folder under an older title."""
    old_folder = project_downloads_folder(old_title, create=False)
    if old_folder.is_dir():
        return old_folder

    new_folder = project_downloads_folder(new_title, create=False)
    if new_folder.is_dir() and _exports_folder_score(new_folder, content) > 0:
        return new_folder

    base = downloads_base()
    if not base.is_dir():
        logger.info("Exports base does not exist while searching for title rename folder: %s", base)
        return None

    candidates: list[tuple[int, Path]] = []
    for folder in base.glob("[[]project[]] *"):
        score = _exports_folder_score(folder, content)
        if score > 0:
            candidates.append((score, folder))

    if not candidates:
        logger.info("No content-matching export folder found for title rename from %r to %r", old_title, new_title)
        return None

    candidates.sort(key=lambda item: (item[0], item[1].stat().st_mtime), reverse=True)
    best_score, best_folder = candidates[0]
    logger.info(
        "Discovered export project folder for title rename by matching script assets: %s (score=%d)",
        best_folder,
        best_score,
    )
    return best_folder


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
        status=status,
        hook_score_overall=content.hook_score.get("overall") if isinstance(content.hook_score, dict) else None,
        upload_tracking=upload_tracking,
    )


@router.get("", response_model=list[ScriptSummary])
def list_scripts(session: Session = Depends(get_session)):
    statement = select(Script).order_by(Script.created_at.desc())  # type: ignore[arg-type]
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

    # Dedup: if an identical script was created in the last 60 seconds, return it as a completed job
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    existing = session.exec(
        select(Script)
        .where(Script.brand_id == brand_id, Script.topic_title == body.topic, Script.created_at >= cutoff)
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
        if existing_eli_enabled == body.eli_enabled:
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
    animated_scene_count = body.animated_scene_count
    model = body.model
    segmented = body.segmented
    cold_open_text = body.cold_open_text
    gameplay_enabled = body.gameplay_enabled
    stock_photo_enabled = body.stock_photo_enabled
    eli_enabled = body.eli_enabled
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
            brand_context=brand_context,
            animated_scene_count=animated_scene_count,
            brand=brand_dict,
            model=model,
            segmented=segmented,
            cold_open_text=cold_open_text,
            progress_callback=_progress,
            gameplay_enabled=gameplay_enabled,
            stock_photo_enabled=stock_photo_enabled,
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
                bg_session, script_id, eli_enabled=eli_enabled
            )
            bg_session.commit()

            if not eli_enabled and script_content.main_character is not None:
                from pipeline.main_character import generate_character_reference
                from models.project_config import update_project_config

                logger.info(
                    "Generating main character reference for script_id=%s", script_id
                )
                try:
                    web_path = generate_character_reference(
                        script_id=script_id,
                        character=script_content.main_character,
                    )
                    update_project_config(
                        bg_session,
                        script_id,
                        main_character_reference_url=web_path,
                    )
                    bg_session.commit()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Main character reference generation failed: %s", exc)
                    # Non-fatal: project still works, scenes will just lack the reference.

        logger.info("Script generated: %s (%d segments) in %.1fs", script_id, len(script_content.segments), duration)

        if gameplay_enabled or stock_photo_enabled or (ai_video_enabled and animated_scene_count > 0):
            try:
                update_job(job_id, current_step="Analyzing media sources...")
                assignments = analyze_media_sources(
                    script_content,
                    gameplay_enabled=gameplay_enabled,
                    stock_photo_enabled=stock_photo_enabled,
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
                logger.info("Media sources assigned for %s", script_id)
            except Exception:
                logger.exception("Media source analysis failed for %s — keeping default AI routing", script_id)

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


@router.put("/{script_id}", response_model=ScriptRead)
def update_script(script_id: str, body: UpdateScriptRequest, session: Session = Depends(get_session)):
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = body.script.model_copy(update={"title": record.topic_title or body.script.title})
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    session.refresh(record)
    mark_render_inputs_changed(script_id)

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


def _usage_task_label(service: str, operation: str, metadata_json: str) -> str:
    """Return a human-readable task label for a usage row."""
    task = ""
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
            task = str(metadata.get("task") or "")
        except (TypeError, ValueError):
            task = ""

    key = task or operation
    labels = {
        "tts": "Generate Audio",
        "image_gen": "Generate Images",
        "chat": "AI Text Tasks",
        "script": "Write Script",
        "fx": "Generate FX",
        "eli": "Add Eli",
        "title_card": "Title Cards",
        "hook": "Hook Score",
        "seo": "SEO Metadata",
        "media": "Media Analysis",
        "refine": "Scene Refinement",
        "duration": "Duration Fixes",
        "idea": "Ideas",
        "analysis": "Analysis",
        "hook_detect": "Hook Detection",
    }
    if key in labels:
        return labels[key]
    if service == "elevenlabs":
        return "Generate Audio"
    if service in {"google_ai", "replicate"}:
        return "Generate Images"
    return key.replace("_", " ").title() if key else "Other"


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
