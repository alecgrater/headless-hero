"""Endpoints for thumbnail generation."""

import json
import logging
import shutil
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from config import DATA_DIR, DEFAULT_ACCENT_COLOR, DEFAULT_SEGMENT_COLORS
from database import get_session
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.thumbnail import (
    get_composite_thumbnail,
    list_longform_thumbnails,
    gemini_enhance_thumbnail,
    replace_active_longform_thumbnail,
)
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
    """Return pre-existing thumbnail for a script."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    concepts: list[ThumbnailConceptResult] = []
    saved = list_longform_thumbnails(script_id)
    if not saved:
        get_composite_thumbnail(script_id)
        saved = list_longform_thumbnails(script_id)
    for idx, url in saved:
        label = "Current thumbnail" if idx == 0 else f"Saved thumbnail {idx}"
        concepts.append(ThumbnailConceptResult(idx=idx, title_text=label, visual_description="Long-form thumbnail", image_url=url))
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

    from pipeline.formats import resolve_format
    fmt = resolve_format(content.format_id)
    if fmt.title_card_strategy.kind != "composite-grid":
        raise HTTPException(
            status_code=400,
            detail=f"Recomposite is only available for composite-grid formats. This script uses {fmt.id!r}.",
        )

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
    )

    # If Gemini succeeded, use the enhanced version as the final thumbnail
    if enhanced_path:
        shutil.copy2(enhanced_path, output_path)
        logger.info("Using Gemini-enhanced thumbnail")

    # Copy to renders/thumbnails for export
    url = replace_active_longform_thumbnail(body.script_id, images_dir / "composite_title_card.png")

    duration = time.monotonic() - t0
    session.add(GenerationDuration(operation_type="thumbnail_generation", duration_seconds=duration))
    session.commit()

    concepts = [
        ThumbnailConceptResult(idx=idx, title_text=("Current thumbnail" if idx == 0 else f"Saved thumbnail {idx}"), visual_description="Gemini-enhanced title card", image_url=thumb_url)
        for idx, thumb_url in list_longform_thumbnails(body.script_id)
    ]
    if not concepts:
        concepts = [ThumbnailConceptResult(idx=0, title_text=card_title, visual_description="Gemini-enhanced title card", image_url=url)]
    return GenerateThumbnailResponse(concepts=concepts)


class RegenerateSplitProgressionRequest(BaseModel):
    script_id: str


@router.post("/regenerate-split-progression", response_model=GenerateThumbnailResponse)
def regenerate_split_progression(
    body: RegenerateSplitProgressionRequest,
    session: Session = Depends(get_session),
):
    """Re-roll the level pair and re-run the split-progression Gemini call only.

    Does NOT regenerate chapter images or the cinematic clean image. Reuses both.
    Used by the Timeline/Modal "Regenerate Thumbnail" button for life-as-a projects.
    """
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    from pipeline.formats import resolve_format
    fmt = resolve_format(content.format_id)
    if fmt.title_card_strategy.kind != "cinematic-chapters":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Split-progression regeneration is only available for cinematic-chapters "
                f"formats. This script uses {content.format_id!r}."
            ),
        )

    from pipeline.formats.title_cards.cinematic_chapters import _thumbnail_paths
    from pipeline.thumbnail import (
        _pick_level_pair,
        _write_level_pair_sidecar,
        enhance_split_progression,
    )

    clean_path, final_path, sidecar_path = _thumbnail_paths(body.script_id)
    if not clean_path.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                "Cinematic clean image is missing. Run title card generation first."
            ),
        )

    n_levels = len(content.levels) if content.levels else 0
    if n_levels < 2:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Need at least 2 levels for a split-progression thumbnail; got {n_levels}."
            ),
        )

    # Always re-roll on explicit regenerate (overwrites sidecar).
    left_level, right_level = _pick_level_pair(n_levels)
    _write_level_pair_sidecar(sidecar_path, left_level, right_level)

    # Force-regenerate the final thumbnail via Gemini.
    enhance_split_progression(
        clean_image_path=clean_path,
        output_path=final_path,
        left_level=left_level,
        right_level=right_level,
        script_id=body.script_id,
        force=True,
    )

    if not final_path.exists():
        # Defensive — enhance_split_progression always writes final_path (with fallback to clean copy).
        raise HTTPException(status_code=500, detail="Thumbnail file missing after regeneration")
    replace_active_longform_thumbnail(body.script_id, final_path)

    return GenerateThumbnailResponse(
        concepts=[
            ThumbnailConceptResult(
                idx=idx,
                title_text=("Current thumbnail" if idx == 0 else f"Saved thumbnail {idx}"),
                visual_description="Split-progression thumbnail",
                image_url=url,
            )
            for idx, url in list_longform_thumbnails(body.script_id)
        ]
    )
