"""Composite title card generation pipeline.

Generates individual AI circle images per segment, then composites them
into a grid layout title card using Pillow. The composite image is reused
for all title card scenes and as the YouTube thumbnail.
"""

import logging
import os
import shutil
from pathlib import Path

from models.script import ScriptContent
from pipeline.image_gen import generate_scene_image
from pipeline.title_card_composer import compose_title_card

logger = logging.getLogger(__name__)

_data_dir = Path(os.environ.get("HH_DATA_DIR", os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data")))


def ensure_title_card_images(
    script_id: str,
    content: ScriptContent,
    accent_color: str = "#e91e63",
    style_string: str = "",
    force: bool = False,
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
    images_dir = _data_dir / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    composite_path = images_dir / "composite_title_card.png"

    # Check if composite already exists (cache)
    if not force and composite_path.exists():
        logger.info("Composite title card already exists, recomputing zoom targets only")
        from pipeline.title_card_composer import calculate_grid_layout
        _, _, positions = calculate_grid_layout(len(content.segments))
        # Recompute zoom targets from grid layout
        from pipeline.title_card_composer import CANVAS_H, CANVAS_W
        title_height = 140
        grid_top = title_height + 20
        grid_bottom = CANVAS_H - 40
        grid_left = 80
        grid_right = CANVAS_W - 80
        rows, cols, _ = calculate_grid_layout(len(content.segments))
        cell_w = (grid_right - grid_left) / cols
        cell_h = (grid_bottom - grid_top) / rows
        label_space = 30
        max_radius = int(min(cell_w, cell_h - label_space) / 2 - 12)
        zoom_targets = {i: (pos[0], pos[1], max_radius) for i, pos in enumerate(positions) if i < len(content.segments)}

        # Set image_url on all title card scenes
        web_path = f"/static/projects/{script_id}/images/composite_title_card.png"
        _set_title_card_urls_and_zoom(content, web_path, zoom_targets)

        return zoom_targets

    # Step 1: Generate individual circle images for each segment
    circle_paths: list[str] = []
    for idx, seg in enumerate(content.segments):
        circle_filename = f"title_card_{idx}.png"
        circle_path = str(images_dir / circle_filename)

        # Skip if already generated and not forcing
        if not force and os.path.exists(circle_path):
            circle_paths.append(circle_path)
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
        except Exception:
            logger.error("Failed to generate circle image for segment %d (%s)", idx, seg.name, exc_info=True)
            circle_paths.append("")  # Placeholder — composer will draw colored circle

    # Step 2: Compose the grid title card
    segment_names = [seg.name for seg in content.segments]
    circle_colors = [
        seg.circle_color or _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)]
        for i, seg in enumerate(content.segments)
    ]

    card_title = content.card_title or content.title
    highlight_word = content.card_title_highlight_word or ""

    _, zoom_targets = compose_title_card(
        circle_image_paths=[p for p in circle_paths],
        segment_names=segment_names,
        circle_colors=circle_colors,
        card_title=card_title,
        highlight_word=highlight_word,
        accent_color=accent_color,
        output_path=str(composite_path),
    )

    # Step 3: Copy composite to thumbnail location
    thumbs_dir = _data_dir / "projects" / script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(composite_path), str(thumbs_dir / "0.png"))
    logger.info("Copied composite title card to thumbnail: %s", thumbs_dir / "0.png")

    # Step 4: Set image_url on all title card scenes and store zoom targets
    web_path = f"/static/projects/{script_id}/images/composite_title_card.png"
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
