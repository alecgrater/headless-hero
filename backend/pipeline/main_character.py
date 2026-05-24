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

GLOBAL_MAIN_CHARACTER_NAME_KEY = "GLOBAL_MAIN_CHARACTER_NAME"
GLOBAL_MAIN_CHARACTER_APPEARANCE_KEY = "GLOBAL_MAIN_CHARACTER_APPEARANCE"
GLOBAL_MAIN_CHARACTER_VIBE_KEY = "GLOBAL_MAIN_CHARACTER_VIBE"
GLOBAL_MAIN_CHARACTER_REFERENCE_URL_KEY = "GLOBAL_MAIN_CHARACTER_REFERENCE_URL"


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


def global_character_reference_path() -> Path:
    """Absolute path to the active global main character reference image."""
    return DATA_DIR / "character" / "main" / "reference.png"


def global_character_reference_web_path() -> str:
    return "/static/character/main/reference.png"


def global_character_reference_variants_dir() -> Path:
    return DATA_DIR / "character" / "main" / "references"


def global_character_reference_active_marker() -> Path:
    return DATA_DIR / "character" / "main" / "active_reference.txt"


def _reference_variant_path(script_id: str, idx: int) -> Path:
    return character_reference_variants_dir(script_id) / f"{idx}.png"


def _reference_variant_web_path(script_id: str, idx: int) -> str:
    return f"/static/projects/{script_id}/character/references/{idx}.png"


def _global_reference_variant_path(idx: int) -> Path:
    return global_character_reference_variants_dir() / f"{idx}.png"


def _global_reference_variant_web_path(idx: int) -> str:
    return f"/static/character/main/references/{idx}.png"


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


def _next_global_reference_variant_path() -> tuple[int, Path]:
    variants_dir = global_character_reference_variants_dir()
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


def _read_global_active_reference_idx() -> int | None:
    marker = global_character_reference_active_marker()
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


def list_global_character_reference_variants() -> list[dict[str, object]]:
    """Return saved global main character candidates, newest first."""
    variants_dir = global_character_reference_variants_dir()
    active_idx = _read_global_active_reference_idx()
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
                "image_url": _global_reference_variant_web_path(idx),
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


def select_global_character_reference_variant(*, idx: int) -> str:
    """Promote a saved global reference candidate to the active global reference."""
    variant_path = _global_reference_variant_path(idx)
    if not variant_path.exists():
        raise FileNotFoundError(f"global main character reference variant {idx} not found")

    target = global_character_reference_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(variant_path, target)
    global_character_reference_active_marker().write_text(str(idx), encoding="utf-8")
    return global_character_reference_web_path()


def read_global_main_character(session) -> MainCharacter | None:
    """Load the global main character details from AppSettings."""
    from models.settings import AppSetting

    name_row = session.get(AppSetting, GLOBAL_MAIN_CHARACTER_NAME_KEY)
    appearance_row = session.get(AppSetting, GLOBAL_MAIN_CHARACTER_APPEARANCE_KEY)
    vibe_row = session.get(AppSetting, GLOBAL_MAIN_CHARACTER_VIBE_KEY)
    name = (name_row.value if name_row else "").strip()
    appearance = (appearance_row.value if appearance_row else "").strip()
    vibe = (vibe_row.value if vibe_row else "").strip()
    if not name and not appearance and not vibe:
        return None
    return MainCharacter(name=name, appearance=appearance, vibe=vibe)


def _write_app_setting(session, key: str, value: str) -> None:
    from models.settings import AppSetting

    row = session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
    else:
        row.value = value
    session.add(row)


def read_global_main_character_reference_url(session) -> str | None:
    from models.settings import AppSetting

    row = session.get(AppSetting, GLOBAL_MAIN_CHARACTER_REFERENCE_URL_KEY)
    value = (row.value if row else "").strip()
    return value or None


def write_global_main_character_reference_url(session, reference_url: str | None) -> None:
    _write_app_setting(session, GLOBAL_MAIN_CHARACTER_REFERENCE_URL_KEY, reference_url or "")


def write_global_main_character(session, character: MainCharacter) -> bool:
    """Persist global character details. Returns True when details changed."""
    previous = read_global_main_character(session)
    changed = previous != character
    _write_app_setting(session, GLOBAL_MAIN_CHARACTER_NAME_KEY, character.name)
    _write_app_setting(session, GLOBAL_MAIN_CHARACTER_APPEARANCE_KEY, character.appearance)
    _write_app_setting(session, GLOBAL_MAIN_CHARACTER_VIBE_KEY, character.vibe)
    if changed:
        write_global_main_character_reference_url(session, None)
        active = global_character_reference_path()
        marker = global_character_reference_active_marker()
        if active.exists():
            active.unlink()
        if marker.exists():
            marker.unlink()
    return changed


def generate_global_character_reference(*, character: MainCharacter, force: bool = False) -> str:
    """Generate and select a global main character reference candidate."""
    target = global_character_reference_path()
    if target.exists() and not force and not list_global_character_reference_variants():
        return global_character_reference_web_path()

    target.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_reference_prompt(character)
    logger.info("Generating global main character reference")
    temp_path = _call_image_generator(prompt, "global-main-character")
    idx, variant_path = _next_global_reference_variant_path()
    shutil.move(temp_path, variant_path)
    return select_global_character_reference_variant(idx=idx)


def sync_global_main_character_to_project(session, script_id: str) -> bool:
    """Copy the active global main character into an Eli-disabled project.

    Project image generation still expects a project-local reference path, so
    this keeps global character management canonical while preserving the
    existing render pipeline contract.
    """
    from models.project_config import ProjectConfig, get_project_config
    from models.script import Script, ScriptContent

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled:
        return False

    character = read_global_main_character(session)
    global_url = read_global_main_character_reference_url(session)
    global_ref = global_character_reference_path()
    if character is None or not global_url or not global_ref.exists():
        return False

    script = session.get(Script, script_id)
    if script is None:
        return False

    content = ScriptContent.model_validate_json(script.script_json)
    changed = content.main_character != character
    content.main_character = character
    script.script_json = content.model_dump_json()
    session.add(script)

    if session.get(ProjectConfig, script_id) is None:
        session.add(cfg)
    target = character_reference_path(script_id)
    reference_missing = not target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(global_ref, target)
    if reference_missing or cfg.main_character_reference_url != character_reference_web_path(script_id):
        changed = True
    cfg.main_character_reference_url = character_reference_web_path(script_id)
    session.add(cfg)
    return changed


def missing_character_reference_reason(session, script_id: str) -> str | None:
    """Return why an Eli-disabled project cannot generate images yet, if blocked."""
    from models.project_config import get_project_config
    from models.script import Script, ScriptContent

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled:
        return None

    if sync_global_main_character_to_project(session, script_id):
        session.commit()

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
