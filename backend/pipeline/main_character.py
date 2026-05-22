"""Main character reference image generation.

Used when ProjectConfig.eli_enabled is False. Produces a single canonical
reference image for the project's main character and persists it to
data/projects/{script_id}/character/reference.png.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.google_image_client import generate_image
from models.script import MainCharacter
from prompts import IMAGE_VISUAL_STYLE

logger = logging.getLogger(__name__)


def character_reference_path(script_id: str) -> Path:
    """Absolute path to the persisted reference image for a script."""
    return DATA_DIR / "projects" / script_id / "character" / "reference.png"


def character_reference_web_path(script_id: str) -> str:
    """The /static path the frontend uses to load the reference."""
    return f"/static/projects/{script_id}/character/reference.png"


def build_reference_prompt(character: MainCharacter) -> str:
    """Compose the Gemini prompt for the canonical reference image."""
    return (
        f"{IMAGE_VISUAL_STYLE.template}\n\n"
        "CHARACTER REFERENCE REQUIREMENT:\n"
        "Create a canonical reference image for a recurring topic-specific main character. "
        "This image will be reused as the visual identity anchor for later scene images, "
        "so the art style must match the existing Headless Hero videos exactly.\n\n"
        f"Character: {character.name}.\n"
        f"Appearance: {character.appearance}\n"
        f"Personality: {character.vibe}\n\n"
        "Draw the character as a polished flat 2D cartoon illustration with clean medium-thick "
        "outlines, saturated colors, simple expressive features, flat fills, and one subtle "
        "shadow tone per major shape. The character may be completely different from Eli, but "
        "must look like they belong in the exact same illustrated world as every other Headless "
        "Hero video.\n\n"
        "Centered three-quarter full-body character pose on a plain neutral light gray background. "
        "No props in hands. Mouth closed, neutral-friendly expression. "
        "No text, letters, numbers, labels, logos, captions, signs, or written marks anywhere. "
        "Never use photorealism, cinematic film still aesthetics, 3D rendering, realistic lens "
        "effects, gradients, shallow depth of field, or painterly concept art. "
        "16:9 aspect ratio."
    )


def _call_image_generator(prompt: str, script_id: str) -> str:
    """Wrapper around generate_image() so tests can patch a single seam."""
    return generate_image(
        prompt=prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        script_id=script_id,
    )


def generate_character_reference(
    *, script_id: str, character: MainCharacter, force: bool = False
) -> str:
    """Generate the canonical reference image and persist it.

    Returns the web-relative path (suitable for ProjectConfig.main_character_reference_url).
    Skips regeneration if the file already exists and force is False.
    """
    target = character_reference_path(script_id)
    if target.exists() and not force:
        logger.info("Reusing existing main character reference at %s", target)
        return character_reference_web_path(script_id)

    target.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_reference_prompt(character)
    logger.info("Generating main character reference for script_id=%s", script_id)
    temp_path = _call_image_generator(prompt, script_id)
    shutil.move(temp_path, target)
    return character_reference_web_path(script_id)


def invalidate_dependent_scene_caches(script_id: str) -> int:
    """Delete .prompt marker files for scenes whose images depend on the character.

    Called when the user edits the character description or regenerates the
    reference image. Returns the number of markers deleted.
    """
    images_dir = DATA_DIR / "projects" / script_id / "images"
    if not images_dir.exists():
        return 0
    deleted = 0
    for marker in images_dir.glob("*.prompt"):
        marker.unlink()
        deleted += 1
    return deleted
