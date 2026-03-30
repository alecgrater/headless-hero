"""Programmatic title card image generation via FFmpeg.

Generates solid-color PNG images with centered segment name text,
ensuring all title cards have identical visual treatment.
"""

import logging
import subprocess
from pathlib import Path

from pipeline.ffmpeg_builder import build_title_card_image_cmd

logger = logging.getLogger(__name__)


def ensure_title_card_images(
    script_id: str,
    segments: list,
    color_primary: str = "#1a1a2e",
    color_secondary: str = "#16213e",
    width: int = 1920,
    height: int = 1080,
    font_family: str = "",
    force: bool = False,
) -> list[str]:
    """Generate title card PNG images for all title card scenes that lack them.

    Args:
        script_id: The script ID (used for file paths).
        segments: List of Segment objects from ScriptContent.
        color_primary: Primary brand color (hex) for background.
        color_secondary: Secondary brand color (hex), reserved for future use.
        width: Image width in pixels.
        height: Image height in pixels.
        font_family: Brand font family name.
        force: If True, regenerate even if image already exists.

    Returns:
        List of scene IDs that got new images generated.
    """
    images_dir = Path("data/projects") / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []

    for seg in segments:
        for scene in seg.scenes:
            if not scene.is_title_card:
                continue

            image_path = images_dir / f"{scene.id}.png"
            if image_path.exists() and not force:
                continue
            if force and image_path.exists():
                image_path.unlink()

            title_text = scene.text_overlay or seg.name
            cmd = build_title_card_image_cmd(
                output_path=str(image_path),
                title_text=title_text,
                color_primary=color_primary,
                color_secondary=color_secondary,
                width=width,
                height=height,
                font_family=font_family,
            )

            logger.info("Generating title card for scene %s: %s", scene.id, title_text)
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    logger.error("FFmpeg title card failed for %s: %s", scene.id, result.stderr)
                    continue
                # Set image_url so the rest of the pipeline can find it
                scene.image_url = f"/static/projects/{script_id}/images/{scene.id}.png"
                generated.append(scene.id)
            except subprocess.TimeoutExpired:
                logger.error("FFmpeg title card timed out for %s", scene.id)

    if generated:
        logger.info("Generated %d title card image(s): %s", len(generated), generated)

    return generated
