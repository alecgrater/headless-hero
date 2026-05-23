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


def character_reference_variants_dir(script_id: str) -> Path:
    """Directory containing generated reference candidates for a script."""
    return DATA_DIR / "projects" / script_id / "character" / "references"


def character_reference_active_marker(script_id: str) -> Path:
    """File storing the active variant index, when one has been selected."""
    return DATA_DIR / "projects" / script_id / "character" / "active_reference.txt"


def _reference_variant_path(script_id: str, idx: int) -> Path:
    return character_reference_variants_dir(script_id) / f"{idx}.png"


def _reference_variant_web_path(script_id: str, idx: int) -> str:
    return f"/static/projects/{script_id}/character/references/{idx}.png"


def _next_reference_variant_path(script_id: str) -> tuple[int, Path]:
    variants_dir = character_reference_variants_dir(script_id)
    variants_dir.mkdir(parents=True, exist_ok=True)
    existing = [
        int(path.stem)
        for path in variants_dir.glob("*.png")
        if path.stem.isdigit()
    ]
    idx = max(existing, default=0) + 1
    return idx, variants_dir / f"{idx}.png"


def _read_active_reference_idx(script_id: str) -> int | None:
    marker = character_reference_active_marker(script_id)
    if not marker.exists():
        return None
    try:
        return int(marker.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def list_character_reference_variants(script_id: str) -> list[dict[str, object]]:
    """Return saved reference candidates, newest first, with active metadata."""
    variants_dir = character_reference_variants_dir(script_id)
    active_idx = _read_active_reference_idx(script_id)
    if not variants_dir.exists():
        return []
    variants: list[dict[str, object]] = []
    for path in variants_dir.glob("*.png"):
        if not path.stem.isdigit():
            continue
        idx = int(path.stem)
        variants.append(
            {
                "idx": idx,
                "image_url": _reference_variant_web_path(script_id, idx),
                "active": idx == active_idx,
            }
        )
    return sorted(variants, key=lambda item: int(item["idx"]), reverse=True)


def select_character_reference_variant(*, script_id: str, idx: int) -> str:
    """Promote a saved reference candidate to the canonical active reference."""
    variant_path = _reference_variant_path(script_id, idx)
    if not variant_path.exists():
        raise FileNotFoundError(f"main character reference variant {idx} not found")

    target = character_reference_path(script_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(variant_path, target)
    character_reference_active_marker(script_id).write_text(str(idx), encoding="utf-8")
    return character_reference_web_path(script_id)


def missing_character_reference_reason(session, script_id: str) -> str | None:
    """Return why an Eli-disabled project cannot generate images yet, if blocked."""
    from models.project_config import get_project_config
    from models.script import Script, ScriptContent

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled:
        return None

    script = session.get(Script, script_id)
    if script is None:
        return "Script not found"

    try:
        content = ScriptContent.model_validate_json(script.script_json)
    except Exception:  # noqa: BLE001
        return "Script content is invalid. Save the script before generating images."

    if content.main_character is None:
        return "Main character details are missing. Open the Main Character panel and save the character first."
    if not cfg.main_character_reference_url:
        return "Main character reference image is missing. Generate and select a reference before generating images."
    if not character_reference_path(script_id).exists():
        return "Main character reference file is missing on disk. Regenerate or select a reference before generating images."
    return None


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
    """Generate a reference candidate, select it, and persist the canonical copy.

    Returns the web-relative path (suitable for ProjectConfig.main_character_reference_url).
    Skips regeneration if the canonical file already exists and no variant list has
    been created yet, preserving legacy projects unless force=True.
    """
    target = character_reference_path(script_id)
    if target.exists() and not force and not list_character_reference_variants(script_id):
        logger.info("Reusing existing main character reference at %s", target)
        return character_reference_web_path(script_id)

    target.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_reference_prompt(character)
    logger.info("Generating main character reference for script_id=%s", script_id)
    temp_path = _call_image_generator(prompt, script_id)
    idx, variant_path = _next_reference_variant_path(script_id)
    shutil.move(temp_path, variant_path)
    select_character_reference_variant(script_id=script_id, idx=idx)
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
