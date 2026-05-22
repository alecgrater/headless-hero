"""Endpoints for SEO metadata generation."""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from api.short_form_hooks import ensure_short_form_hook_scene_count
from database import get_session
from models.brand import BrandProfile
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.export_paths import (
    longform_filename,
    project_downloads_folder,
    shortform_filename,
)
from pipeline.seo import (
    SEOMetadata,
    ShortFormSEOMetadata,
    build_short_form_seo_contexts,
    format_timestamp,
    generate_seo,
    generate_short_form_seo,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["seo"])

class GenerateSEORequest(BaseModel):
    script_id: str

class GenerateSEOResponse(BaseModel):
    metadata: SEOMetadata

class GenerateShortFormSEOResponse(BaseModel):
    metadata: ShortFormSEOMetadata

@router.post("/generate", response_model=GenerateSEOResponse)
def generate_seo_metadata(body: GenerateSEORequest, session: Session = Depends(get_session)):
    """Generate SEO metadata for all platforms."""
    t0 = time.monotonic()
    logger.info("Generating SEO metadata for script %s", body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    # Compute cumulative timestamps from scene audio durations
    segments: list[tuple[str, str]] = []
    elapsed = 0.0
    for seg in content.segments:
        segments.append((seg.name, format_timestamp(elapsed)))
        for scene in seg.scenes:
            elapsed += scene.audio_duration_seconds

    # Build brand context for SEO generation
    brand = session.get(BrandProfile, record.brand_id)
    brand_context = ""
    if brand:
        brand_context = brand.name

    metadata = generate_seo(
        video_title=content.title,
        segments=segments,
        video_description=record.topic_description,
        brand_context=brand_context,
        script_id=body.script_id,
    )

    # Persist SEO metadata in the script JSON blob
    content.seo_metadata = metadata.model_dump()
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("SEO metadata generated for script %s", body.script_id)

    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="seo_generation", duration_seconds=duration))
    session.commit()

    return GenerateSEOResponse(metadata=metadata)

@router.post("/generate-shorts", response_model=GenerateShortFormSEOResponse)
def generate_short_form_seo_metadata(body: GenerateSEORequest, session: Session = Depends(get_session)):
    """Generate short-form SEO metadata for every per-segment short in one call."""
    t0 = time.monotonic()
    logger.info("Generating short-form SEO metadata for script %s", body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    content = ensure_short_form_hook_scene_count(session, body.script_id, content, record)
    shorts = build_short_form_seo_contexts(content)
    if not shorts:
        raise HTTPException(status_code=400, detail="Script has no segments")

    brand = session.get(BrandProfile, record.brand_id)
    brand_context = brand.name if brand else ""

    project_title = record.topic_title or content.title or "Untitled"
    metadata = generate_short_form_seo(
        video_title=project_title,
        shorts=shorts,
        video_description=record.topic_description,
        brand_context=brand_context,
        script_id=body.script_id,
    )

    content.short_form_seo_metadata = metadata.model_dump()
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Short-form SEO metadata generated for script %s", body.script_id)

    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="short_form_seo_generation", duration_seconds=duration))
    session.commit()

    return GenerateShortFormSEOResponse(metadata=metadata)


class ExportSEOResponse(BaseModel):
    folder_path: str
    files: list[str]


@router.post("/export-longform", response_model=ExportSEOResponse)
def export_longform_seo(body: GenerateSEORequest, session: Session = Depends(get_session)):
    """Write the long-form SEO markdown file into the project Downloads folder."""
    from pipeline.script_helpers import _format_longform_seo_markdown

    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    if not content.seo_metadata:
        raise HTTPException(status_code=400, detail="Long-form SEO has not been generated yet")

    seo_markdown = _format_longform_seo_markdown(content.seo_metadata)
    if not seo_markdown.strip():
        raise HTTPException(status_code=400, detail="Long-form SEO metadata is empty")

    project_title = record.topic_title or content.title or "Untitled"
    folder = project_downloads_folder(project_title)
    (folder / longform_filename("SEO", project_title, ".txt")).unlink(missing_ok=True)
    dest = folder / longform_filename("SEO", project_title, ".md")
    dest.write_text(seo_markdown, encoding="utf-8")

    logger.info("Exported long-form SEO for script %s to %s", body.script_id, dest)
    return ExportSEOResponse(folder_path=str(folder), files=[dest.name])


@router.post("/export-shorts", response_model=ExportSEOResponse)
def export_short_form_seo(body: GenerateSEORequest, session: Session = Depends(get_session)):
    """Write all short-form SEO markdown files into the project Downloads folder."""
    from pipeline.script_helpers import _format_shortform_seo_markdown

    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    content = ensure_short_form_hook_scene_count(session, body.script_id, content, record)
    if not content.short_form_seo_metadata:
        raise HTTPException(status_code=400, detail="Short-form SEO has not been generated yet")

    short_items = (content.short_form_seo_metadata or {}).get("shorts", [])
    if not short_items:
        raise HTTPException(status_code=400, detail="Short-form SEO metadata is empty")

    project_title = record.topic_title or content.title or "Untitled"
    folder = project_downloads_folder(project_title)

    parsed_indices: list[int] = []
    for item in short_items:
        try:
            parsed_indices.append(int(item.get("index", -1)))
        except (TypeError, ValueError):
            parsed_indices.append(-1)
    uses_one_based_indices = 1 in parsed_indices

    total_segments = len(content.segments)
    written: list[str] = []
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
        written.append(dest.name)

    logger.info("Exported %d short-form SEO files for script %s to %s", len(written), body.script_id, folder)
    return ExportSEOResponse(folder_path=str(folder), files=written)
