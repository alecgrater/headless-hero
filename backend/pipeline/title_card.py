"""Composite title card generation pipeline.

Generates individual AI circle images per segment, then composites them
into a grid layout title card using Pillow. The composite image is reused
for all title card scenes and as the YouTube thumbnail.
"""

import json
import logging
import os
import shutil
from pathlib import Path

from config import DATA_DIR
from models.script import ScriptContent
from pipeline.image_gen import generate_scene_image
from pipeline.render_jobs import update_job
from pipeline.title_card_composer import compose_title_card

logger = logging.getLogger(__name__)


def ensure_title_card_images(
    script_id: str,
    content: ScriptContent,
    accent_color: str = "#e91e63",
    style_string: str = "",
    force: bool = False,
    job_id: str | None = None,
) -> dict[int, tuple[int, int, int]]:
    """Generate circle images and composite title card for all segments.

    Args:
        script_id: The script ID (used for file paths).
        content: Full script content with segment metadata.
        accent_color: Hex color for title highlight word.
        style_string: Brand style string prepended to image prompts.
        force: If True, regenerate even if composite already exists.

    Returns:
        Dict mapping segment_index -> (center_x, center_y, radius) zoom targets.
    """
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    composite_path = images_dir / "composite_title_card.png"

    notitle_path = images_dir / "composite_title_card_notitle.png"

    # Check if both composites already exist (cache)
    if not force and composite_path.exists() and notitle_path.exists():
        logger.info("Composite title cards already exist, recomputing zoom targets only")
        from pipeline.title_card_composer import calculate_grid_layout
        from pipeline.title_card_composer import CANVAS_H, CANVAS_W

        # Compute zoom targets for the no-title version (used for scene rendering)
        rows, cols, positions = calculate_grid_layout(len(content.segments), include_title=False)
        grid_top = 30
        grid_bottom = CANVAS_H - 40
        grid_left = 80
        grid_right = CANVAS_W - 80
        cell_w = (grid_right - grid_left) / cols
        cell_h = (grid_bottom - grid_top) / rows
        label_space = 30
        max_radius = int(min(cell_w, cell_h - label_space) / 2 - 12)
        zoom_targets = {i: (pos[0], pos[1], max_radius) for i, pos in enumerate(positions) if i < len(content.segments)}

        # Set image_url on title card scenes to no-title version
        web_path = f"/static/projects/{script_id}/images/composite_title_card_notitle.png"
        _set_title_card_urls_and_zoom(content, web_path, zoom_targets)

        return zoom_targets

    # Step 1: Generate individual circle images for each segment
    segment_names = [seg.name for seg in content.segments]
    total_segments = len(content.segments)

    # Report initial progress
    if job_id:
        update_job(job_id, current_step=json.dumps({
            "completed": [],
            "total": total_segments,
            "names": segment_names,
        }))

    circle_paths: list[str] = []
    for idx, seg in enumerate(content.segments):
        circle_filename = f"title_card_{idx}.png"
        circle_path = str(images_dir / circle_filename)

        # Skip if already generated and not forcing
        if not force and os.path.exists(circle_path):
            circle_paths.append(circle_path)
            # Report progress for cached images too
            if job_id:
                completed = list(range(idx + 1))
                update_job(job_id, current_step=json.dumps({
                    "completed": completed,
                    "total": total_segments,
                    "names": segment_names,
                }), progress=(idx + 1) / total_segments)
            continue

        # Use the segment's title_card_image_prompt, fallback to segment name
        prompt = seg.title_card_image_prompt or f"A vivid, colorful illustration representing the concept of {seg.name}. Simple, iconic, centered subject on a clean background."

        try:
            web_url, _ = generate_scene_image(
                scene_id=f"title_card_{idx}",
                visual_prompt=prompt,
                script_id=script_id,
                width=768,
                height=768,  # Square for circle cropping
                force=force,
                style_guide="",
                style_string=style_string,
            )
            circle_paths.append(circle_path)
            logger.info("Generated circle image %d/%d for segment %r", idx + 1, len(content.segments), seg.name)
        except Exception as exc:
            logger.error(
                "Failed to generate circle image for segment %d (%s): %s",
                idx, seg.name, exc,
                exc_info=True,
            )
            circle_paths.append("")  # Placeholder — composer will draw colored circle

        # Report per-segment progress
        if job_id:
            completed = list(range(idx + 1))
            update_job(job_id, current_step=json.dumps({
                "completed": completed,
                "total": total_segments,
                "names": segment_names,
            }), progress=(idx + 1) / total_segments)

    # Step 2: Compose the grid title card (with title — for thumbnail)
    circle_colors = [
        seg.circle_color or _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)]
        for i, seg in enumerate(content.segments)
    ]

    card_title = content.card_title or content.title
    highlight_word = content.card_title_highlight_word or ""

    compose_title_card(
        circle_image_paths=[p for p in circle_paths],
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=accent_color,
        output_path=str(composite_path),
        include_title=True,
    )

    # Step 3: Compose no-title version (for zoom scene rendering — larger circles)
    _, zoom_targets = compose_title_card(
        circle_image_paths=[p for p in circle_paths],
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=accent_color,
        output_path=str(notitle_path),
        include_title=False,
    )

    # Step 4: Copy with-title composite to thumbnail location
    thumbs_dir = DATA_DIR / "projects" / script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(composite_path), str(thumbs_dir / "0.png"))
    logger.info("Copied composite title card to thumbnail: %s", thumbs_dir / "0.png")

    # Step 5: Set image_url on title card scenes to no-title version (for zoom rendering)
    web_path = f"/static/projects/{script_id}/images/composite_title_card_notitle.png"
    _set_title_card_urls_and_zoom(content, web_path, zoom_targets)

    return zoom_targets


def _set_title_card_urls_and_zoom(
    content: ScriptContent,
    web_path: str,
    zoom_targets: dict[int, tuple[int, int, int]],
) -> None:
    """Set image_url and zoom target on all title card scenes."""
    for seg_idx, seg in enumerate(content.segments):
        target = zoom_targets.get(seg_idx)
        for scene in seg.scenes:
            if scene.is_title_card:
                scene.image_url = web_path
                if target:
                    scene.title_card_zoom_target = {
                        "x": target[0],
                        "y": target[1],
                        "radius": target[2],
                    }


# Default circle colors (used when Claude doesn't provide them)
_DEFAULT_COLORS = [
    "#e91e63", "#2196f3", "#4caf50", "#ff9800",
    "#9c27b0", "#00bcd4", "#ff5722", "#8bc34a",
    "#3f51b5", "#cddc39", "#f44336", "#009688",
]
