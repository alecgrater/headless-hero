"""Main character reference image generation.

Used when ProjectConfig.eli_enabled is False. Produces a single canonical
reference image for the project's main character and persists it to
data/projects/{script_id}/character/reference.png.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH
from integrations.google_image_client import generate_image
from models.script import MainCharacter
from models.style_preset_character import StylePresetCharacter, StylePresetCharacterResponse
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


def style_preset_character_path(preset_id: str, character_id: str) -> Path:
    return DATA_DIR / "style" / "presets" / preset_id / "characters" / f"{character_id}.png"


def style_preset_character_web_path(preset_id: str, character_id: str) -> str:
    return f"/static/style/presets/{preset_id}/characters/{character_id}.png"


def active_style_preset_character_key(preset_id: str) -> str:
    return f"ACTIVE_STYLE_PRESET_CHARACTER_ID_{preset_id}"


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


def read_active_style_preset_id(session) -> str | None:
    from models.settings import AppSetting

    row = session.get(AppSetting, "ACTIVE_STYLE_PRESET_ID")
    value = (row.value if row else "").strip()
    return value or None


def read_active_style_preset_character_id(session, preset_id: str) -> str | None:
    from models.settings import AppSetting

    row = session.get(AppSetting, active_style_preset_character_key(preset_id))
    value = (row.value if row else "").strip()
    return value or None


def write_active_style_preset_character_id(
    session,
    preset_id: str,
    character_id: str | None,
) -> None:
    _write_app_setting(session, active_style_preset_character_key(preset_id), character_id or "")


def style_preset_image_path(preset_id: str) -> Path:
    return DATA_DIR / "style" / "presets" / f"{preset_id}.png"


def _style_preset_character_response(
    session,
    character: StylePresetCharacter,
) -> StylePresetCharacterResponse:
    active_id = read_active_style_preset_character_id(session, character.style_preset_id)
    return StylePresetCharacterResponse(
        id=character.id,
        style_preset_id=character.style_preset_id,
        name=character.name,
        appearance=character.appearance,
        vibe=character.vibe,
        reference_image_url=character.reference_image_url,
        created_at=character.created_at,
        active=character.id == active_id,
    )


def list_style_preset_characters(session, preset_id: str) -> list[StylePresetCharacterResponse]:
    from sqlmodel import select

    rows = session.exec(
        select(StylePresetCharacter)
        .where(StylePresetCharacter.style_preset_id == preset_id)
        .order_by(StylePresetCharacter.created_at.desc())
    ).all()
    visible = [
        row
        for row in rows
        if style_preset_character_path(row.style_preset_id, row.id).exists()
    ]
    return [_style_preset_character_response(session, row) for row in visible]


def get_active_style_preset_character(
    session,
    preset_id: str,
) -> StylePresetCharacterResponse | None:
    character_id = read_active_style_preset_character_id(session, preset_id)
    if not character_id:
        return None
    row = session.get(StylePresetCharacter, character_id)
    if row is None or row.style_preset_id != preset_id:
        return None
    if not style_preset_character_path(preset_id, character_id).exists():
        return None
    return _style_preset_character_response(session, row)


def select_style_preset_character(session, preset_id: str, character_id: str) -> StylePresetCharacterResponse:
    row = session.get(StylePresetCharacter, character_id)
    if row is None or row.style_preset_id != preset_id:
        raise FileNotFoundError(f"style preset character {character_id} not found")
    if not style_preset_character_path(preset_id, character_id).exists():
        raise FileNotFoundError(f"style preset character image {character_id} not found")
    write_active_style_preset_character_id(session, preset_id, character_id)
    return _style_preset_character_response(session, row)


def build_style_preset_character_prompt(character: MainCharacter) -> str:
    return (
        "CHARACTER REFERENCE REQUIREMENT:\n"
        "Create a canonical reference image for a recurring main character. "
        "The included style preset image is the visual style source of truth. "
        "Match its line weight, proportions, face detail level, color treatment, and overall illustration language.\n\n"
        f"Character: {character.name}.\n"
        f"Appearance: {character.appearance}\n"
        f"Personality: {character.vibe}\n\n"
        "Centered three-quarter full-body character pose on a plain neutral light gray background. "
        "No props in hands. Mouth closed, neutral-friendly expression. "
        "No text, letters, numbers, labels, logos, captions, signs, or written marks anywhere. "
        "Never use photorealism, cinematic film still aesthetics, 3D rendering, realistic lens "
        "effects, gradients, shallow depth of field, or painterly concept art unless the style preset itself clearly uses that treatment. "
        "16:9 aspect ratio."
    )


def _call_style_character_image_generator(
    prompt: str,
    script_id: str,
    style_reference_path: str,
) -> str:
    return generate_image(
        prompt,
        width=IMAGE_WIDTH,
        height=IMAGE_HEIGHT,
        script_id=script_id,
        style_reference_path=style_reference_path,
    )


def create_style_preset_character(
    session,
    *,
    preset_id: str,
    character: MainCharacter,
) -> StylePresetCharacterResponse:
    from models.style_preset import StylePreset

    preset = session.get(StylePreset, preset_id)
    if preset is None:
        raise FileNotFoundError(f"style preset {preset_id} not found")
    preset_image = style_preset_image_path(preset_id)
    if not preset_image.exists():
        raise FileNotFoundError(f"style preset image {preset_id} not found")

    character_id = uuid.uuid4().hex
    prompt = build_style_preset_character_prompt(character)
    temp_path = _call_style_character_image_generator(
        prompt,
        f"style-preset-character-{preset_id}",
        str(preset_image),
    )
    final_path = style_preset_character_path(preset_id, character_id)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(temp_path, final_path)

    row = StylePresetCharacter(
        id=character_id,
        style_preset_id=preset_id,
        name=character.name,
        appearance=character.appearance,
        vibe=character.vibe,
        reference_image_url=style_preset_character_web_path(preset_id, character_id),
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    write_active_style_preset_character_id(session, preset_id, character_id)
    session.flush()
    return _style_preset_character_response(session, row)


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
    """Copy the active preset-scoped character into an Eli-disabled project.

    Project image generation still expects a project-local reference path, so
    this keeps preset-scoped character management canonical while preserving the
    existing render pipeline contract.
    """
    from models.project_config import ProjectConfig, get_project_config
    from models.script import Script, ScriptContent

    cfg = get_project_config(session, script_id)
    if cfg.eli_enabled or not cfg.style_preset_enabled:
        return False

    preset_id = read_active_style_preset_id(session)
    if not preset_id or not style_preset_image_path(preset_id).exists():
        return False

    active_character_id = read_active_style_preset_character_id(session, preset_id)
    if not active_character_id:
        return False

    row = session.get(StylePresetCharacter, active_character_id)
    if row is None or row.style_preset_id != preset_id:
        return False

    source_ref = style_preset_character_path(preset_id, active_character_id)
    if not source_ref.exists():
        return False

    script = session.get(Script, script_id)
    if script is None:
        return False

    character = MainCharacter(name=row.name, appearance=row.appearance, vibe=row.vibe)
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
    shutil.copy2(source_ref, target)
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
    if not cfg.style_preset_enabled:
        return "Style preset is disabled. Enable the style preset before generating Eli-disabled scene images."

    if sync_global_main_character_to_project(session, script_id):
        session.commit()

    script = session.get(Script, script_id)
    if script is None:
        return "Script not found"

    try:
        content = ScriptContent.model_validate_json(script.script_json)
    except Exception:  # noqa: BLE001
        return "Script content is invalid. Save the script before generating images."

    preset_id = read_active_style_preset_id(session)
    if not preset_id or not style_preset_image_path(preset_id).exists():
        return "Active style preset is missing. Open Settings -> Style Presets and select a preset before generating images."
    active_character_id = read_active_style_preset_character_id(session, preset_id)
    if not active_character_id:
        return "Active style preset has no selected character. Open Settings -> Style Presets and generate or select a character before generating images."
    character_row = session.get(StylePresetCharacter, active_character_id)
    if character_row is None or character_row.style_preset_id != preset_id:
        return "Active style preset character is missing. Open Settings -> Style Presets and select a character before generating images."
    if not style_preset_character_path(preset_id, active_character_id).exists():
        return "Active style preset character reference file is missing on disk. Regenerate or select a character before generating images."
    if content.main_character is None:
        return "Main character details are missing. Open Settings -> Style Presets and select a character first."
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
