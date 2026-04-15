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
from pipeline.thumbnail import get_composite_thumbnail, get_composite_thumbnail_no_eli, _cache_bust
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
    card_title = content.card_title or content.title

    concepts: list[ThumbnailConceptResult] = []

    composite_url = get_composite_thumbnail(script_id)
    if composite_url:
        concepts.append(ThumbnailConceptResult(
            idx=0,
            title_text=f"{card_title} (with Eli)",
            visual_description="Composite grid title card with Eli overlay",
            image_url=composite_url,
        ))

    no_eli_url = get_composite_thumbnail_no_eli(script_id)
    if no_eli_url:
        concepts.append(ThumbnailConceptResult(
            idx=1,
            title_text=f"{card_title} (without Eli)",
            visual_description="Composite grid title card without Eli overlay",
            image_url=no_eli_url,
        ))

    return GenerateThumbnailResponse(concepts=concepts)


@router.post("/recomposite", response_model=GenerateThumbnailResponse)
def recomposite_thumbnail(body: RecompositeThumbnailRequest, session: Session = Depends(get_session)):
    """Re-run compositing on existing circle images (no AI generation).

    Always generates both with-Eli and without-Eli variants so both are
    visible and downloadable in the UI.
    """
    logger.info("Recompositing thumbnails for script %s", body.script_id)
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

    thumbs_dir = DATA_DIR / "projects" / body.script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    concepts: list[ThumbnailConceptResult] = []

    # --- With-Eli variant ---
    composite_path = images_dir / "composite_title_card.png"
    notitle_path = images_dir / "composite_title_card_notitle.png"

    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=DEFAULT_ACCENT_COLOR,
        output_path=str(composite_path),
        include_title=True,
        include_eli=True,
    )
    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=DEFAULT_ACCENT_COLOR,
        output_path=str(notitle_path),
        include_title=False,
        include_eli=True,
    )
    shutil.copy2(str(composite_path), str(thumbs_dir / "0.png"))
    url_0 = f"/static/projects/{body.script_id}/renders/thumbnails/0.png"
    concepts.append(ThumbnailConceptResult(
        idx=0,
        title_text=f"{card_title} (with Eli)",
        visual_description="Composite grid title card with Eli overlay",
        image_url=_cache_bust(url_0, str(thumbs_dir / "0.png")),
    ))

    # --- Without-Eli variant ---
    composite_no_eli_path = images_dir / "composite_title_card_no_eli.png"

    compose_title_card(
        circle_image_paths=circle_paths,
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=DEFAULT_ACCENT_COLOR,
        output_path=str(composite_no_eli_path),
        include_title=True,
        include_eli=False,
    )
    shutil.copy2(str(composite_no_eli_path), str(thumbs_dir / "0_no_eli.png"))
    url_1 = f"/static/projects/{body.script_id}/renders/thumbnails/0_no_eli.png"
    concepts.append(ThumbnailConceptResult(
        idx=1,
        title_text=f"{card_title} (without Eli)",
        visual_description="Composite grid title card without Eli overlay",
        image_url=_cache_bust(url_1, str(thumbs_dir / "0_no_eli.png")),
    ))

    logger.info("Recomposited both thumbnail variants for script %s", body.script_id)
    return GenerateThumbnailResponse(concepts=concepts)
