"""Thumbnail pipeline — composite title card lookup.

When the title_cards modifier is active and a composite title card exists,
it is used directly as the thumbnail.
"""

import logging
import os
import random
import shutil
from pathlib import Path

from config import DATA_DIR
from prompts import IMAGE_CTR_EXPRESSION_GUIDANCE

logger = logging.getLogger(__name__)


def _cache_bust(url: str, file_path: str) -> str:
    """Append file mtime as query param to bust browser cache."""
    try:
        mtime = int(os.path.getmtime(file_path))
        return f"{url}?t={mtime}"
    except OSError:
        return url


def get_composite_thumbnail(script_id: str) -> str | None:
    """Check if a composite title card exists and return its web path if so."""
    composite = DATA_DIR / "projects" / script_id / "images" / "composite_title_card.png"
    if composite.exists():
        # Copy to thumbnail location
        thumbs_dir = DATA_DIR / "projects" / script_id / "renders" / "thumbnails"
        thumbs_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumbs_dir / "0.png"
        shutil.copy2(str(composite), str(thumb_path))
        url = f"/static/projects/{script_id}/renders/thumbnails/0.png"
        return _cache_bust(url, str(thumb_path))
    return None


def get_composite_thumbnail_no_eli(script_id: str) -> str | None:
    """Check if a no-Eli composite title card exists and return its web path if so."""
    composite = DATA_DIR / "projects" / script_id / "images" / "composite_title_card_no_eli.png"
    if composite.exists():
        thumbs_dir = DATA_DIR / "projects" / script_id / "renders" / "thumbnails"
        thumbs_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumbs_dir / "0_no_eli.png"
        shutil.copy2(str(composite), str(thumb_path))
        url = f"/static/projects/{script_id}/renders/thumbnails/0_no_eli.png"
        return _cache_bust(url, str(thumb_path))
    return None


THUMBNAIL_REFERENCES_DIR = DATA_DIR / "character" / "thumbnail_references"

# CTR expression tier guidance for Gemini prompt
_CTR_EXPRESSION_GUIDANCE = IMAGE_CTR_EXPRESSION_GUIDANCE.template


def gemini_enhance_thumbnail(
    base_image_path: str,
    video_title: str,
    script_id: str | None = None,
) -> str | None:
    """Enhance a base title card composite using Gemini with a reference thumbnail.

    The base composite already has the character (Eli) placed deterministically
    in the top-right corner by the Pillow composer. Gemini is only asked to
    enhance styling (circle borders, title treatment) and must NOT reposition
    the character or replace any segment circle.

    Args:
        base_image_path: Path to the base Pillow-generated composite.
        video_title: The video title (provides context for expression selection).
        script_id: Optional script ID for usage tracking.

    Returns:
        Path to the enhanced image, or None if enhancement can't be performed.
    """
    logger.info("[%s] Starting Gemini thumbnail enhancement for %r", script_id or "no-id", video_title)

    from integrations.google_image_client import transform_with_references

    # Check for reference thumbnails
    ref_dir = THUMBNAIL_REFERENCES_DIR
    if not ref_dir.exists():
        logger.info("No thumbnail references directory — skipping enhancement")
        return None

    ref_files = [
        f for f in ref_dir.iterdir()
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    ]
    if not ref_files:
        logger.info("No thumbnail references uploaded — skipping enhancement")
        return None

    logger.info("[%s] Found %d thumbnail references", script_id or "no-id", len(ref_files))

    # Pick a random reference thumbnail for style guidance only
    ref_path = str(random.choice(ref_files))
    logger.info("Using thumbnail reference: %s", ref_path)

    # Two images: base composite (already has Eli top-right) + style reference
    image_paths = [base_image_path, ref_path]

    prompt = (
        "You are a YouTube thumbnail stylist. You have been given:\n"
        "1. A base title card image — it already contains the final layout: a title, "
        "a grid of segment circles with labels, and a character in the top-right corner.\n"
        "2. A reference thumbnail showing the target visual style.\n\n"
        "Your task — STYLE ENHANCEMENT ONLY:\n"
        "- Apply the reference thumbnail's circle border styling (glowing magical borders) "
        "to ALL segment circles in the base image.\n"
        "- Make the title text SIGNIFICANTLY LARGER — it should dominate the top of the thumbnail. "
        "Keep it punchy, bold, and attention-grabbing, matching the reference thumbnail's title treatment.\n"
        f'- The video title is: "{video_title}".\n'
        "- Optimize everything for maximum YouTube CTR (saturation, contrast, drama).\n\n"
        "STRICT RULES — violations are bugs:\n"
        "- DO NOT move, duplicate, remove, redraw, or reposition the character. "
        "Keep him in the exact top-right corner position he already occupies.\n"
        "- DO NOT replace ANY segment circle with the character or any other element. "
        "Every one of the segment circles must remain intact with its original image and label.\n"
        "- DO NOT duplicate any circle's image or label into another cell. "
        "Every segment label must stay unique and in its original position.\n"
        "- DO NOT add a second copy of the character anywhere.\n"
        "- DO NOT insert a 'portal' or 'vortex' effect inside any segment circle.\n\n"
        "Keep the segment label badges readable. Keep the overall grid layout intact. "
        f"{_CTR_EXPRESSION_GUIDANCE}\n\n"
        "Return the modified image."
    )

    try:
        result_path = transform_with_references(
            prompt=prompt,
            image_paths=image_paths,
            script_id=script_id,
        )
        logger.info("Gemini thumbnail enhancement complete: %s", result_path)
        return result_path
    except Exception as exc:
        logger.warning("Gemini thumbnail enhancement failed, using base image: %s", exc)
        return None
