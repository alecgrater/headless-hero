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
_CTR_EXPRESSION_GUIDANCE = """
Choose the character's expression/pose based on the video title and topic, using one of these CTR-optimized tiers:

1. Pattern Interrupt (High Surprise) — for shocking/unexpected content:
   - Gasped Breath: mouth slightly open, eyes wide, eyebrows raised
   - Wince/Cringe: one eye squinting, mouth pulled to side
   - Wide-Eyed Hyper-Focus: leaning into camera, dilated pupils

2. Negative Tension (Anxiety & Concern) — for warning/cautionary content:
   - Forehead Furrow: brows pinched, hand on chin/forehead
   - Tears/Red Eyes: glistening eyes, empathy-driving
   - Secretive "Shush": finger to lips, eyes darting

3. Action-Oriented (Excitement & Joy) — for travel, tech, challenge content:
   - Mid-Laugh: genuine squinty-eyed laugh
   - "Look at This" Gaze: looking with wonder at the subject
   - Exertion/Struggle: teeth grit, brow sweating

Pick the tier and specific expression that best matches the video title/topic.
"""


def gemini_enhance_thumbnail(
    base_image_path: str,
    video_title: str,
    script_id: str | None = None,
) -> str | None:
    """Enhance a base title card composite using Gemini with reference thumbnails.

    Sends the base image + a random reference thumbnail + a random Eli character
    frame to Gemini, which transforms the image for higher CTR.

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
            "The third image is a character to insert into the title card. "
            "Choose one of the segment circles at random and replace its image with "
            "this character popping out of that circle, matching how the character "
            "appears in the reference thumbnail (head extending past the circle, "
            "hands gripping the edge, emerging from a glowing blue plasma vortex). "
            "Keep the segment label badge beneath the chosen circle readable.\n\n"
            f"{_CTR_EXPRESSION_GUIDANCE}\n"
        )

    prompt = (
        "You are a YouTube thumbnail optimizer. You have been given:\n"
        "1. A base title card image with circular segment thumbnails arranged in a grid\n"
        "2. A reference thumbnail showing the target visual style\n"
        f"{'3. A character image to insert into the title card' if eli_frame_path else ''}\n\n"
        "Your task:\n"
        "- Study the reference thumbnail's visual style (circle borders, glow effects, "
        "character positioning, title treatment)\n"
        f"{character_instruction}"
        "- Apply the reference thumbnail's circle border styling (glowing magical borders) "
        "to ALL circles in the image\n"
        "- Update the title text styling to be more punchy, bold, and attention-grabbing, "
        "matching the reference thumbnail's title treatment\n"
        f'- The video title is: "{video_title}"\n'
        "- Optimize everything for maximum YouTube CTR\n\n"
        "Keep the segment label badges readable. Keep the overall layout and grid intact. "
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
