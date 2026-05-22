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
        f"Cinematic character reference portrait of {character.name}.\n"
        f"Appearance: {character.appearance}\n"
        f"Personality: {character.vibe}\n\n"
        "Chest-up framing. Centered. Direct lighting from front-left. "
        "Plain neutral light gray background. No props in hands. "
        "Mouth closed, neutral expression. "
        "Photorealistic, cinematic film still aesthetic, shallow depth of field. "
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
    shutil.copyfile(temp_path, target)
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
