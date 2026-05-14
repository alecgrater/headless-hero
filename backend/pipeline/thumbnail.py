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
    """Enhance a base title card composite using Gemini with reference thumbnails.

    Sends the base image + a reference thumbnail + a random Eli character frame
    to Gemini, which chooses ONE segment circle and replaces it with Eli bursting
    out as a portal. All other segment circles must be preserved exactly.

    Args:
        base_image_path: Path to the base Pillow-generated composite.
        video_title: The video title (provides context for expression selection).
        script_id: Optional script ID for usage tracking.

    Returns:
        Path to the enhanced image, or None if enhancement can't be performed
        (no references uploaded, no character frames, etc.).
    """
    logger.info("[%s] Starting Gemini thumbnail enhancement for %r", script_id or "no-id", video_title)

    from integrations.google_image_client import transform_with_references
    from pipeline.character_frames import get_manifest, FRAMES_DIR

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

    # Pick a random reference thumbnail
    ref_path = str(random.choice(ref_files))
    logger.info("Using thumbnail reference: %s", ref_path)

    # Pick a random Eli character frame
    eli_frame_path = None
    try:
        manifest = get_manifest()
        if manifest and manifest.get("frames"):
            # Prefer thumbnail frames with open mouth
            thumbnail_frames = manifest.get("thumbnail_frames", [])
            frames = thumbnail_frames if thumbnail_frames else manifest["frames"]
            frame = random.choice(frames)
            mouth_key = "file_open" if thumbnail_frames else "file_closed"
            file_name = frame.get(mouth_key, "")
            if file_name:
                candidate = FRAMES_DIR / file_name
                if candidate.exists():
                    eli_frame_path = str(candidate)
                    logger.info("[%s] Selected Eli frame for thumbnail: %s", script_id or "no-id", file_name)
    except Exception as exc:
        logger.debug("Could not load Eli frame for thumbnail: %s", exc)

    # Build image list: base image first, then reference, then Eli frame
    image_paths = [base_image_path, ref_path]
    if eli_frame_path:
        image_paths.append(eli_frame_path)

    # Build prompt
    character_instruction = ""
    if eli_frame_path:
        character_instruction = (
            "CHARACTER INSERTION:\n"
            "The third image is a character. Choose ONE segment circle AT RANDOM (you pick which one) "
            "and turn it into a portal with this character BURSTING OUT of it. "
            "The character should be MUCH larger than the circle — the circle acts as "
            "a portal he is emerging from. His head and upper body should extend dramatically past the "
            "circle boundary (about 60-75%% overflow), with the circle sitting around his waist/hips area. "
            "His hands should grip the circle edge as if climbing out of it. "
            "Add a glowing blue plasma vortex effect inside and around the portal circle.\n\n"
            "PORTAL ALIGNMENT — CRITICAL:\n"
            "The portal circle MUST be drawn at the EXACT same center pixel coordinates and EXACT "
            "same radius as the original segment circle you are replacing. It must snap PERFECTLY "
            "onto the grid cell — do NOT shift it left, right, up, or down even by a few pixels. "
            "Do NOT draw the portal between two circles or overlapping into adjacent cells. "
            "The portal boundary and the original circle boundary must be pixel-aligned.\n\n"
            "Keep the segment label badge beneath the portal circle readable.\n"
            "Add a small, eye-catching arrow (curved or straight) pointing at the portal circle, "
            "to draw the viewer's eye there.\n\n"
            f"{_CTR_EXPRESSION_GUIDANCE}\n\n"
        )

    prompt = (
        "You are a YouTube thumbnail optimizer. You have been given:\n"
        "1. A base title card image with a grid of circular segment thumbnails, each with a label badge below it.\n"
        "2. A reference thumbnail showing the target visual style.\n"
        f"{'3. A character image to insert into the title card.' if eli_frame_path else ''}\n\n"
        "Your task:\n"
        "- Study the reference thumbnail's visual style (circle borders, glow effects, "
        "character positioning, title treatment).\n"
        f"{character_instruction}"
        "- Apply the reference thumbnail's circle border styling (glowing magical borders) "
        "to ALL circles in the image.\n"
        "- Make the title text SIGNIFICANTLY LARGER — it should dominate the top of the thumbnail. "
        "Keep it punchy, bold, and attention-grabbing, matching the reference thumbnail's title treatment.\n"
        f'- The video title is: "{video_title}".\n'
        "- Optimize everything for maximum YouTube CTR.\n\n"
        "CRITICAL RULES — violations are bugs:\n"
        "- You MAY replace EXACTLY ONE segment circle (the one you chose) with the character portal. "
        "Every OTHER segment circle must be preserved EXACTLY as in the base image — "
        "same interior image, same label text, same position. Do NOT redraw them from memory.\n"
        "- DO NOT duplicate any segment's image or label into another cell. Every segment label "
        "must stay unique. If you find yourself repeating a label (e.g. 'BOY IN THE BOX' twice), stop and correct it.\n"
        "- DO NOT leave any segment blank, faded, or missing.\n"
        "- DO NOT invent extra segments or add/remove circles — the grid size must match the input exactly.\n"
        "- DO NOT add a second copy of the character anywhere else in the image.\n\n"
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
