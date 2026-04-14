"""Endpoints for thumbnail generation."""

import json
import logging
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR, DEFAULT_ACCENT_COLOR, DEFAULT_SEGMENT_COLORS
from database import get_session
from models.script import Script, ScriptContent
from pipeline.thumbnail import get_composite_thumbnail
from pipeline.title_card_composer import compose_title_card

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/thumbnail", tags=["thumbnail"])


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
    """Return any pre-existing thumbnails on disk (e.g. from title card generation)."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    composite_url = get_composite_thumbnail(script_id)
    if composite_url:
        return GenerateThumbnailResponse(concepts=[ThumbnailConceptResult(
            idx=0,
            title_text=content.card_title or content.title,
            visual_description="Composite grid title card (auto-generated from segments)",
            image_url=composite_url,
        )])
    return GenerateThumbnailResponse(concepts=[])


@router.post("/recomposite", response_model=GenerateThumbnailResponse)
def recomposite_thumbnail(body: RecompositeThumbnailRequest, session: Session = Depends(get_session)):
    """Re-run compositing on existing circle images (no AI generation).

    Reapplies gradient background, circle layout, label badges, 3D title text,
    Eli overlay, and color boost using existing segment circle images on disk.
    """
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

    # Build compositing inputs (same as Steps 2-5 of ensure_title_card_images)
    segment_names = [seg.short_name or " ".join(seg.name.split()[:3]) for seg in content.segments]
    circle_colors = [
        seg.circle_color or DEFAULT_SEGMENT_COLORS[i % len(DEFAULT_SEGMENT_COLORS)]
        for i, seg in enumerate(content.segments)
    ]
    card_title = content.card_title or content.title
    highlight_word = content.card_title_highlight_word or ""

    composite_path = images_dir / "composite_title_card.png"
    notitle_path = images_dir / "composite_title_card_notitle.png"

    # Compose with-title version (for thumbnail)
    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=DEFAULT_ACCENT_COLOR,
        output_path=str(composite_path),
        include_title=True,
    )

    # Compose no-title version (for scene rendering)
    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=DEFAULT_ACCENT_COLOR,
        output_path=str(notitle_path),
        include_title=False,
    )

    # Copy with-title composite to thumbnail location
    thumbs_dir = DATA_DIR / "projects" / body.script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(composite_path), str(thumbs_dir / "0.png"))

    thumbnail_url = f"/static/projects/{body.script_id}/renders/thumbnails/0.png"
    logger.info("Recomposited thumbnail for script %s", body.script_id)

    return GenerateThumbnailResponse(concepts=[ThumbnailConceptResult(
        idx=0,
        title_text=card_title,
        visual_description="Composite grid title card (recomposited from existing segments)",
        image_url=thumbnail_url,
    )])
