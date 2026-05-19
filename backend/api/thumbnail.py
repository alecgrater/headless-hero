"""Endpoints for thumbnail generation."""

import json
import logging
import os
import shutil
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR, DEFAULT_ACCENT_COLOR, DEFAULT_SEGMENT_COLORS
from database import get_session
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.thumbnail import get_composite_thumbnail, _cache_bust, gemini_enhance_thumbnail
from pipeline.title_card_composer import compose_title_card

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/thumbnail", tags=["thumbnail"])


def _setting_enabled(value: str | None, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


class RecompositeThumbnailRequest(BaseModel):
    script_id: str


class ThumbnailConceptResult(BaseModel):
    idx: int
    title_text: str
    visual_description: str
    image_url: str | None = None
    error: str | None = None


class GenerateThumbnailResponse(BaseModel):
    concepts: list[ThumbnailConceptResult]


@router.get("/{script_id}", response_model=GenerateThumbnailResponse)
def get_existing_thumbnails(script_id: str, session: Session = Depends(get_session)):
    """Return pre-existing thumbnail for a script."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    concepts: list[ThumbnailConceptResult] = []
    url = get_composite_thumbnail(script_id)
    if url:
        concepts.append(ThumbnailConceptResult(idx=0, title_text="", visual_description="Title card thumbnail", image_url=url))
    return GenerateThumbnailResponse(concepts=concepts)


@router.post("/recomposite", response_model=GenerateThumbnailResponse)
def recomposite_thumbnail(body: RecompositeThumbnailRequest, session: Session = Depends(get_session)):
    """Re-run compositing on existing circle images, then enhance with Gemini."""
    t0 = time.monotonic()
    logger.info("Recompositing thumbnail for script %s", body.script_id)
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    images_dir = DATA_DIR / "projects" / body.script_id / "images"

    # Collect existing circle images
    circle_paths: list[str] = []
    for idx in range(len(content.segments)):
        circle_path = images_dir / f"title_card_{idx}.png"
        if not circle_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Circle image missing for segment {idx}. Generate title card images first.",
            )
        circle_paths.append(str(circle_path))

    # Build compositing inputs
    segment_names = [seg.short_name or " ".join(seg.name.split()[:3]) for seg in content.segments]
    circle_colors = [
        seg.circle_color or DEFAULT_SEGMENT_COLORS[i % len(DEFAULT_SEGMENT_COLORS)]
        for i, seg in enumerate(content.segments)
    ]
    card_title = content.card_title or content.title
    highlight_word = content.card_title_highlight_word or ""
    card_subtitle = content.card_subtitle or ""

    thumbs_dir = DATA_DIR / "projects" / body.script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    # Generate base composite (no Eli — Gemini places Eli bursting out of one
    # randomly-chosen segment circle as a portal effect for maximum CTR)
    output_path = str(images_dir / "composite_title_card.png")
    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=DEFAULT_ACCENT_COLOR,
        output_path=output_path,
        include_title=True,
        include_eli=False,
        card_subtitle=card_subtitle,
    )

    # Also generate no-title variant for video zoom scenes (stays Pillow-only)
    notitle_path = str(images_dir / "composite_title_card_notitle.png")
    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=DEFAULT_ACCENT_COLOR,
        output_path=notitle_path,
        include_title=False,
        include_eli=False,
        card_subtitle=card_subtitle,
    )

    # Gemini enhancement — transforms the base into a CTR-optimized thumbnail
    base_path = str(images_dir / "composite_title_card_base.png")
    enhanced_path = gemini_enhance_thumbnail(
        base_image_path=base_path,
        video_title=card_title,
        script_id=body.script_id,
        include_arrow=_setting_enabled(os.environ.get("LONGFORM_THUMBNAIL_ARROW_ENABLED"), default=True),
    )

    # If Gemini succeeded, use the enhanced version as the final thumbnail
    if enhanced_path:
        shutil.copy2(enhanced_path, output_path)
        logger.info("Using Gemini-enhanced thumbnail")

    # Copy to renders/thumbnails for export
    thumb_dest = thumbs_dir / "0.png"
    shutil.copy2(output_path, str(thumb_dest))
    url = f"/static/projects/{body.script_id}/renders/thumbnails/0.png"
    url = _cache_bust(url, str(thumb_dest))

    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="thumbnail_generation", duration_seconds=duration))
    session.commit()

    return GenerateThumbnailResponse(
        concepts=[ThumbnailConceptResult(idx=0, title_text=card_title, visual_description="Gemini-enhanced title card", image_url=url)]
    )
