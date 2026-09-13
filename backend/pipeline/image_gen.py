"""Image generation pipeline — connects visual prompts to Google Gemini."""

import json
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw, ImageFont

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH, VIDEO_HEIGHT, VIDEO_WIDTH
from integrations.google_image_client import GoogleBatchImageRequest
from integrations.image_client import generate_image, generate_images_batch, provider_fingerprint
from models.script import MainCharacter
from pipeline.asset_vault import VaultKind, save_vault_image
from pipeline.character_assets import process_character_asset_bundle
from pipeline.cutout_chroma import key_out_background, save_keyed_trimmed_cutout as save_shared_keyed_trimmed_cutout
from pipeline.fallback_observability import record_fallback
from pipeline.render_jobs import UserFacingJobError
from prompts import IMAGE_CHARACTER_IN_SCENE, IMAGE_COMPOSITION_GUIDE, IMAGE_VISUAL_STYLE

logger = logging.getLogger(__name__)

BLINK_CUTOUT_REGISTRATION_VERSION = "alpha-mask-registration-v29"
_STYLE_GUIDE = IMAGE_COMPOSITION_GUIDE.template
_VISUAL_STYLE = IMAGE_VISUAL_STYLE.template
_CHARACTER_PROMPT = IMAGE_CHARACTER_IN_SCENE.template
_CAPTION_TEXT_PROMPT_LEAK_RE = re.compile(
    r"\b(?:caption text|clean sans-serif|words in|text on a dark background|readable caption text)\b",
    re.IGNORECASE,
)


class CaptionPromptLeakError(UserFacingJobError):
    """Raised when renderer-owned caption text is sent to image generation."""


_SEQUENCE_CONSISTENCY_PROMPT = """\
Multi-image sequence consistency:
- These images belong to the same scene sequence and must look like adjacent shots from one cohesive explainer video.
- Keep the same flat 2D cartoon house style, line weight, color palette, character proportions, camera language, and rendering simplicity across every image.
- Output a full-bleed 16:9 illustration only. No decorative border, picture frame, mat, white margin, inset panel, UI chrome, caption box, or poster edge.
- Do not draw literal frames around the image. The word "sequence" refers only to multiple generated images, not a physical frame or border.
"""
_FULL_BLEED_IMAGE_GUARD = """\
Image boundary rules:
- Output one full-bleed 16:9 illustration that fills the entire canvas edge to edge.
- No decorative border, picture frame, mat, white margin, inset panel, UI chrome, caption box, poster edge, or floating card.
- Do not draw a literal frame around the image; any mentions of scenes, frames, panels, states, or sequences are production terms only.
"""


def _contains_caption_text_prompt_leak(scene: dict[str, object]) -> bool:
    prompt_parts = [str(scene.get("visual_prompt") or "")]
    for directive in scene.get("frame_directives") or []:
        if isinstance(directive, dict):
            prompt_parts.append(str(directive.get("prompt") or ""))
        elif hasattr(directive, "prompt"):
            prompt_parts.append(str(getattr(directive, "prompt") or ""))
    return any(_CAPTION_TEXT_PROMPT_LEAK_RE.search(part) for part in prompt_parts)


def _raise_for_caption_text_prompt_leak(prompt_parts: list[str], *, scene_id: str) -> None:
    if any(_CAPTION_TEXT_PROMPT_LEAK_RE.search(part or "") for part in prompt_parts):
        raise CaptionPromptLeakError(
            "Scene visual prompt requests renderer-owned caption text; "
            "use visual_mode='captions' with caption_text/caption_emphasis instead. "
            f"scene_id={scene_id}"
        )


def _closest_aspect_ratio(width: int, height: int) -> str:
    ratio = width / height
    options = [
        (1 / 1, "1:1"),
        (3 / 4, "3:4"),
        (4 / 3, "4:3"),
        (9 / 16, "9:16"),
        (16 / 9, "16:9"),
    ]
    return min(options, key=lambda option: abs(option[0] - ratio))[1]

# --- Character reference helpers ---


def _eli_reference_path() -> str | None:
    """Path to Eli's selected reference, or None if not present."""
    p = DATA_DIR / "character" / "frames" / "selected_reference.png"
    return str(p) if p.exists() else None


def _project_character_reference_path(script_id: str) -> str | None:
    p = DATA_DIR / "projects" / script_id / "character" / "reference.png"
    return str(p) if p.exists() else None


# --- Style preset helpers ---


def _read_app_setting(key: str) -> str:
    """Read a setting value from AppSettings; empty string if missing."""
    from sqlmodel import Session
    from database import engine
    from models.settings import AppSetting

    with Session(engine) as session:
        row = session.get(AppSetting, key)
        return row.value if row else ""


def _active_style_preset_path() -> str | None:
    """Return path to the active style preset image, or None if unset/missing."""
    preset_id = _read_app_setting("ACTIVE_STYLE_PRESET_ID").strip()
    if not preset_id:
        return None
    p = DATA_DIR / "style" / "presets" / f"{preset_id}.png"
    return str(p) if p.exists() else None


def _resolve_style_preset(
    *,
    eli_enabled: bool,
    project_style_enabled: bool,
) -> str | None:
    """Return the active style preset path or None.

    Returns None when:
      - Eli is enabled (style preset never applies to Eli videos)
      - The project's style_preset_enabled toggle is False
      - No preset is active or the active preset's image file is missing
    """
    if eli_enabled or not project_style_enabled:
        return None
    return _active_style_preset_path()


def _serialize_main_character(char: MainCharacter) -> str:
    return (
        f'The primary/main person in this image MUST be "{char.name}" - the project-specific recurring main character. '
        "A reference image of this character is included. The character MUST match this reference exactly: "
        "same face, hair, body type, proportions, clothing cues, distinguishing features, and flat 2D cartoon style. "
        "If the prompt depicts the protagonist, role character, or visible main person, make this character the "
        "visually dominant subject. Other people may appear only as secondary characters and must be visually distinct. "
        f"Appearance: {char.appearance}. "
        f"Vibe: {char.vibe}."
    )


def _load_project_style_enabled(script_id: str) -> bool:
    """Read the project's style_preset_enabled flag, defaulting to True if missing."""
    from sqlmodel import Session
    from database import engine
    from models.project_config import get_project_config

    with Session(engine) as session:
        cfg = get_project_config(session, script_id)
    return cfg.style_preset_enabled


def _load_project_character_context(
    script_id: str,
) -> tuple[bool, str | None, MainCharacter | None]:
    """Load (eli_enabled, main_character_reference_url, main_character) for a script.

    Reads ProjectConfig and ScriptContent from the DB. Returns sane defaults
    (eli_enabled=True, no main_character) if the script row is missing or invalid.
    """
    from sqlmodel import Session
    from database import engine
    from models.project_config import get_project_config
    from models.script import Script, ScriptContent
    from pipeline.main_character import sync_global_main_character_to_project

    with Session(engine) as session:
        if sync_global_main_character_to_project(session, script_id):
            session.commit()
        cfg = get_project_config(session, script_id)
        script_row = session.get(Script, script_id)

    main_character_obj: MainCharacter | None = None
    if script_row is not None:
        try:
            content = ScriptContent.model_validate_json(script_row.script_json)
            main_character_obj = content.main_character
        except Exception:  # noqa: BLE001
            main_character_obj = None

    return cfg.eli_enabled, cfg.main_character_reference_url, main_character_obj


def _project_character_missing_reason(
    *,
    script_id: str,
    main_character_reference_url: str | None,
    main_character: MainCharacter | None,
) -> str | None:
    """Return a human-readable missing-reference reason, or None when ready."""
    if not _load_project_style_enabled(script_id):
        return "Style preset is disabled. Enable the style preset before generating Eli-disabled scene images."
    if main_character is None:
        return "Main character details are missing. Open the Main Character panel and save the character first."
    if not main_character_reference_url:
        return "Main character reference image is missing. Generate the main character reference before generating scene images."
    if _project_character_reference_path(script_id) is None:
        return "Main character reference file is missing on disk. Regenerate the main character reference before generating scene images."
    return None


def _ensure_project_character_reference_ready(
    *,
    script_id: str,
    eli_enabled: bool,
    main_character_reference_url: str | None,
    main_character: MainCharacter | None,
) -> None:
    """Block project image generation when Eli is off but no canonical character exists."""
    if eli_enabled:
        return
    reason = _project_character_missing_reason(
        script_id=script_id,
        main_character_reference_url=main_character_reference_url,
        main_character=main_character,
    )
    if reason:
        raise RuntimeError(reason)


def _resolve_character_reference(
    *,
    script_id: str,
    contains_person: bool,
    eli_enabled: bool,
    main_character_reference_url: str | None,
    main_character: MainCharacter | None,
) -> tuple[str | None, str]:
    """Return (reference_image_path, character_prompt_text) for image gen.

    eli_enabled=True   -> Eli's reference + _CHARACTER_PROMPT (existing behavior).
    eli_enabled=False  -> project main character reference + serialized description.
    contains_person=False always returns (None, "").
    """
    if not contains_person:
        return None, ""

    if eli_enabled:
        return _eli_reference_path(), (_CHARACTER_PROMPT or "")

    _ensure_project_character_reference_ready(
        script_id=script_id,
        eli_enabled=eli_enabled,
        main_character_reference_url=main_character_reference_url,
        main_character=main_character,
    )

    ref = _project_character_reference_path(script_id)
    if ref is None:
        raise RuntimeError(
            "Main character reference file is missing on disk. Regenerate the main character reference before generating scene images."
        )
    return ref, _serialize_main_character(main_character)


def _create_placeholder_image(path: Path, width: int, height: int, text: str) -> None:
    """Create a solid-color placeholder image with error text."""
    img = Image.new("RGB", (width, height), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)
    # Wrap text to fit
    wrapped = text[:120]
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except (OSError, IOError):
        font = ImageFont.load_default()
    draw.text((width // 2, height // 2), wrapped, fill=(180, 180, 200), font=font, anchor="mm")
    img.save(str(path))


def _setting_enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _source_metadata_path(image_path: Path) -> Path:
    return image_path.with_suffix(".source.json")


def _write_source_metadata(image_path: Path, metadata: dict[str, object]) -> None:
    _source_metadata_path(image_path).write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _read_source_metadata(image_path: Path) -> dict[str, object] | None:
    path = _source_metadata_path(image_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid image source metadata at %s", path)
        return None


def _move_generated_image(tmp_path: str, local_path: Path, metadata: dict[str, object]) -> dict[str, object]:
    tmp_source_path = _source_metadata_path(Path(tmp_path))
    shutil.move(tmp_path, str(local_path))
    if tmp_source_path.exists():
        shutil.move(str(tmp_source_path), str(_source_metadata_path(local_path)))
    else:
        _write_source_metadata(local_path, metadata)
    return _read_source_metadata(local_path) or metadata


def _safe_image_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)


def visual_layer_image_filename(scene_id: str, layer_id: str) -> str:
    return f"{_safe_image_id(scene_id)}_layer_{_safe_image_id(layer_id)}.png"


def _compose_image_prompt_context(
    *,
    visual_prompt: str,
    script_id: str,
    style_guide: str = "",
    contains_person: bool = False,
) -> tuple[str, str | None, str | None]:
    guide = style_guide if style_guide else _STYLE_GUIDE

    eli_enabled, main_character_url, main_character_obj = _load_project_character_context(script_id)
    _ensure_project_character_reference_ready(
        script_id=script_id,
        eli_enabled=eli_enabled,
        main_character_reference_url=main_character_url,
        main_character=main_character_obj,
    )

    project_style_enabled = _load_project_style_enabled(script_id)
    style_reference_path = _resolve_style_preset(
        eli_enabled=eli_enabled,
        project_style_enabled=project_style_enabled,
    )

    reference_image_path, character_text = _resolve_character_reference(
        script_id=script_id,
        contains_person=contains_person,
        eli_enabled=eli_enabled,
        main_character_reference_url=main_character_url,
        main_character=main_character_obj,
    )

    parts: list[str] = []
    if _VISUAL_STYLE:
        parts.append(_VISUAL_STYLE)
    parts.append(_FULL_BLEED_IMAGE_GUARD)
    if guide:
        parts.append(guide)
    if character_text:
        parts.append(character_text)
    parts.append(visual_prompt)
    prompt = "\n\n".join(parts)

    if reference_image_path:
        try:
            mtime = int(Path(reference_image_path).stat().st_mtime)
            prompt += f"\n[char_ref:{reference_image_path}:{mtime}]"
        except OSError:
            pass

    if style_reference_path:
        try:
            mtime = int(Path(style_reference_path).stat().st_mtime)
            prompt += f"\n[style_ref:{style_reference_path}:{mtime}]"
        except OSError:
            pass

    return prompt, reference_image_path, style_reference_path


def _compose_cutout_prompt_context(
    *,
    visual_prompt: str,
    script_id: str,
    style_guide: str = "",
    contains_person: bool = False,
) -> tuple[str, str | None, str | None]:
    guide = style_guide if style_guide else _STYLE_GUIDE

    eli_enabled, main_character_url, main_character_obj = _load_project_character_context(script_id)
    _ensure_project_character_reference_ready(
        script_id=script_id,
        eli_enabled=eli_enabled,
        main_character_reference_url=main_character_url,
        main_character=main_character_obj,
    )

    project_style_enabled = _load_project_style_enabled(script_id)
    style_reference_path = _resolve_style_preset(
        eli_enabled=eli_enabled,
        project_style_enabled=project_style_enabled,
    )

    reference_image_path, character_text = _resolve_character_reference(
        script_id=script_id,
        contains_person=contains_person,
        eli_enabled=eli_enabled,
        main_character_reference_url=main_character_url,
        main_character=main_character_obj,
    )

    parts: list[str] = []
    if _VISUAL_STYLE:
        parts.append(_VISUAL_STYLE)
    if guide:
        parts.append(guide)
    if character_text:
        parts.append(character_text)
    parts.append(visual_prompt)
    prompt = "\n\n".join(parts)

    if reference_image_path:
        try:
            mtime = int(Path(reference_image_path).stat().st_mtime)
            prompt += f"\n[char_ref:{reference_image_path}:{mtime}]"
        except OSError:
            pass

    if style_reference_path:
        try:
            mtime = int(Path(style_reference_path).stat().st_mtime)
            prompt += f"\n[style_ref:{style_reference_path}:{mtime}]"
        except OSError:
            pass

    return prompt, reference_image_path, style_reference_path


def generate_visual_layer_panels(
    scene_id: str,
    layers: list[dict],
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
    contains_person: bool = False,
    visual_treatment: str = "",
) -> list[dict]:
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    processed_layers: list[dict] = []
    previous_panel_path: Path | None = None
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            processed_layers.append(layer)
            continue
        if layer.get("type", "image") != "image" or layer.get("asset_kind", "panel") != "panel":
            processed_layers.append(layer)
            continue

        prompt = (layer.get("prompt") or "").strip()
        layer_id = layer.get("id") or f"{scene_id}_layer_{index}"
        if not prompt:
            logger.info("[PANEL_GEN] skipped empty prompt scene=%s layer=%s", scene_id, layer_id)
            processed_layers.append(layer)
            continue

        prompt = _sanitize_layer_prompt_for_full_bleed(prompt)
        original_prompt = prompt
        filename = visual_layer_image_filename(scene_id, str(layer_id))
        local_path = images_dir / filename
        prompt_marker = images_dir / f"{filename}.prompt"
        web_path = f"/static/projects/{script_id}/images/{filename}"
        layer_contains_person = bool(layer.get("contains_person", contains_person))
        composed_prompt, reference_image_path, style_reference_path = _compose_image_prompt_context(
            visual_prompt=prompt,
            script_id=script_id,
            contains_person=layer_contains_person,
        )

        next_layer = dict(layer)
        next_layer["id"] = layer_id
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8")
            if cached_prompt == composed_prompt:
                logger.info("[PANEL_GEN] cache hit scene=%s layer=%s", scene_id, layer_id)
                next_layer["image_url"] = web_path
                source_metadata = _read_source_metadata(local_path)
                if source_metadata:
                    next_layer["visual_source_metadata"] = source_metadata
                processed_layers.append(next_layer)
                previous_panel_path = local_path
                continue

        logger.info("[PANEL_GEN] generating panel scene=%s layer=%s", scene_id, layer_id)
        tmp_path = generate_image(
            composed_prompt,
            width=width,
            height=height,
            reference_image_path=reference_image_path,
            original_prompt=original_prompt,
            style_reference_path=style_reference_path,
            script_id=script_id,
        )
        metadata = _move_generated_image(
            tmp_path,
            local_path,
            {
                "source_type": "visual_layer_panel",
                "provider": provider_fingerprint(),
                "fallback": False,
            },
        )
        prompt_marker.write_text(composed_prompt, encoding="utf-8")
        next_layer["image_url"] = web_path
        next_layer["visual_source_metadata"] = metadata
        processed_layers.append(next_layer)
        previous_panel_path = local_path
        logger.info("[PANEL_GEN] complete scene=%s layer=%s", scene_id, layer_id)

    return processed_layers


def _sanitize_layer_prompt_for_full_bleed(prompt: str) -> str:
    cleaned = prompt.strip()
    cleaned = re.sub(
        r"\bsmall\s+framed\s+Headless\s+Hero\s+cartoon\s+panel\s*(?:for\s+[^:]+)?[:,]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bThe\s+panel\s+sits\s+on\s+a\s+flat\s+static\s+color\s+background,\s+not\s+a\s+full\s+video\s+background\.?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bPopup item cutout prompt(?:\s+for\s+[^:]+)?:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:small\s+)?framed\s+panel\s*(?:for\s+[^:]+)?[:,]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bNo text in image\.?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;-")
    return cleaned or prompt.strip()


def generate_popup_sequence_cutouts(
    *,
    scene_id: str,
    layers: list[dict],
    script_id: str,
    scene_prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
    contains_person: bool = False,
) -> list[dict]:
    """Generate one character anchor plus cropped popup item cutouts for a popup sequence."""

    image_layers = [
        dict(layer)
        for layer in layers
        if isinstance(layer, dict) and layer.get("type", "image") == "image"
    ]
    if not image_layers:
        return layers

    output_dir = DATA_DIR / "projects" / script_id / "popup_crops" / scene_id
    output_dir.mkdir(parents=True, exist_ok=True)

    labels = [_popup_item_label(layer, index) for index, layer in enumerate(image_layers)]
    (
        anchor_reference_path,
        anchor_style_reference_path,
        anchor_character_text,
        anchor_fallback_reason,
    ) = _resolve_popup_anchor_generation_context(
        script_id=script_id,
        contains_person=contains_person,
    )
    if anchor_fallback_reason:
        anchor_prompt = f"transparent protagonist fallback: {anchor_fallback_reason}"
    else:
        anchor_prompt = _compose_popup_anchor_prompt(
            scene_prompt,
            contains_person=contains_person,
            character_context=anchor_character_text,
        )
    item_prompt = _compose_popup_item_sheet_prompt(scene_prompt, labels)
    prompt_marker = output_dir / "popup_sequence.prompt"
    prompt_fingerprint = json.dumps(
        {
            "anchor_prompt": anchor_prompt,
            "anchor_fallback_reason": anchor_fallback_reason,
            "item_prompt": item_prompt,
            "anchor_reference": _reference_fingerprint(anchor_reference_path),
            "anchor_style_reference": _reference_fingerprint(anchor_style_reference_path),
            "labels": labels,
            "layers": [
                {
                    "id": layer.get("id"),
                    "prompt": layer.get("prompt"),
                    "placement": layer.get("placement"),
                    "enter_at_seconds": layer.get("enter_at_seconds"),
                    "animation": layer.get("animation"),
                }
                for layer in image_layers
            ],
        },
        sort_keys=True,
    )

    anchor_cutout_path = output_dir / "anchor_cutout.png"
    item_paths = [output_dir / f"crop_{index + 2:02d}_{_slug(label)}.png" for index, label in enumerate(labels)]
    cache_valid = (
        not force
        and prompt_marker.exists()
        and prompt_marker.read_text(encoding="utf-8") == prompt_fingerprint
        and anchor_cutout_path.exists()
        and all(path.exists() for path in item_paths)
    )

    if not cache_valid:
        logger.info(
            "[POPUP_CROP] generating popup cutouts scene=%s items=%d protagonist_anchor=%s",
            scene_id,
            len(labels),
            bool(anchor_reference_path),
        )
        if anchor_fallback_reason:
            logger.warning(
                "[POPUP_CROP] protagonist_anchor.unavailable scene=%s reason=%s; using transparent anchor fallback",
                scene_id,
                anchor_fallback_reason,
            )
            record_fallback(
                category="image_generation",
                event="popup_anchor_transparent_fallback",
                reason=anchor_fallback_reason,
                to_value="transparent_anchor",
                script_id=script_id,
                scene_id=scene_id,
                severity="warn",
                logger=logger,
            )
            _create_transparent_popup_anchor_cutout(output_dir=output_dir)
        else:
            try:
                _generate_popup_anchor_cutout(
                    anchor_prompt=anchor_prompt,
                    output_dir=output_dir,
                    width=width,
                    height=height,
                    script_id=script_id,
                    reference_image_path=anchor_reference_path,
                    style_reference_path=anchor_style_reference_path,
                )
            except Exception:
                if not anchor_reference_path:
                    raise
                logger.warning(
                    "[POPUP_CROP] protagonist_anchor.generation_failed scene=%s; falling back to reference cutout",
                    scene_id,
                    exc_info=True,
                )
                _create_popup_anchor_cutout_from_reference(
                    reference_image_path=anchor_reference_path,
                    output_dir=output_dir,
                )
        _generate_popup_item_cutouts(
            item_prompt=item_prompt,
            labels=labels,
            output_dir=output_dir,
            width=width,
            height=height,
            script_id=script_id,
        )
        prompt_marker.write_text(prompt_fingerprint, encoding="utf-8")
    else:
        logger.info("[POPUP_CROP] cache hit scene=%s", scene_id)

    web_base = f"/static/projects/{script_id}/popup_crops/{scene_id}"
    processed_layers = [
        {
            "id": f"{scene_id}_anchor",
            "type": "image",
            "asset_kind": "cutout",
            "image_url": f"{web_base}/anchor_cutout.png",
            "prompt": scene_prompt,
            "placement": "center",
            "enter_at_seconds": 0.0,
            "animation": "none",
        }
    ]
    for index, layer in enumerate(image_layers):
        next_layer = dict(layer)
        next_layer["asset_kind"] = "cutout"
        next_layer["image_url"] = f"{web_base}/{item_paths[index].name}"
        next_layer["placement"] = _popup_cutout_placement(str(next_layer.get("placement") or ""), index, len(image_layers))
        next_layer["animation"] = next_layer.get("animation") or "pop_in"
        processed_layers.append(next_layer)
    return processed_layers


def _reference_fingerprint(path: str | None) -> dict[str, object] | None:
    if not path:
        return None
    try:
        return {"path": path, "mtime": int(Path(path).stat().st_mtime)}
    except OSError:
        return {"path": path, "mtime": None}


def _resolve_popup_anchor_generation_context(
    *,
    script_id: str,
    contains_person: bool,
) -> tuple[str | None, str | None, str, str | None]:
    if not contains_person:
        return None, None, "", None

    eli_enabled, main_character_url, main_character_obj = _load_project_character_context(script_id)
    try:
        reference_image_path, character_text = _resolve_character_reference(
            script_id=script_id,
            contains_person=True,
            eli_enabled=eli_enabled,
            main_character_reference_url=main_character_url,
            main_character=main_character_obj,
        )
    except RuntimeError as exc:
        return None, None, "", str(exc)

    if not reference_image_path:
        protagonist = "Eli" if eli_enabled else "the configured main character"
        return None, None, "", f"{protagonist} reference image is missing"

    style_reference_path = _resolve_style_preset(
        eli_enabled=eli_enabled,
        project_style_enabled=_load_project_style_enabled(script_id),
    )
    logger.info(
        "[POPUP_CROP] protagonist_anchor.ready script=%s source=%s",
        script_id,
        "eli" if eli_enabled else "main_character",
    )
    return reference_image_path, style_reference_path, character_text, None


def generate_comparison_board_cutouts(
    *,
    scene_id: str,
    layers: list[dict],
    script_id: str,
    scene_prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
) -> list[dict]:
    """Generate transparent subject cutouts for renderer-owned comparison boards."""

    image_layers = [
        dict(layer)
        for layer in layers
        if isinstance(layer, dict) and layer.get("type", "image") == "image"
    ][:3]
    if len(image_layers) < 2:
        return layers

    output_dir = DATA_DIR / "projects" / script_id / "comparison_boards" / scene_id
    output_dir.mkdir(parents=True, exist_ok=True)

    labels = [_comparison_subject_label(layer, index) for index, layer in enumerate(image_layers)]
    item_prompt = _compose_comparison_subject_sheet_prompt(scene_prompt, labels)
    prompt_marker = output_dir / "comparison_board.prompt"
    prompt_fingerprint = json.dumps(
        {
            "item_prompt": item_prompt,
            "labels": labels,
            "layers": [
                {
                    "id": layer.get("id"),
                    "prompt": layer.get("prompt"),
                    "placement": layer.get("placement"),
                    "enter_at_seconds": layer.get("enter_at_seconds"),
                    "animation": layer.get("animation"),
                }
                for layer in image_layers
            ],
        },
        sort_keys=True,
    )
    item_paths = [output_dir / f"subject_{index + 1:02d}_{_slug(label)}.png" for index, label in enumerate(labels)]
    cache_valid = (
        not force
        and prompt_marker.exists()
        and prompt_marker.read_text(encoding="utf-8") == prompt_fingerprint
        and all(path.exists() for path in item_paths)
    )

    if not cache_valid:
        logger.info("[COMPARISON_BOARD] generating cutouts scene=%s subjects=%d", scene_id, len(labels))
        _generate_comparison_subject_cutouts(
            item_prompt=item_prompt,
            labels=labels,
            output_dir=output_dir,
            width=width,
            height=height,
            script_id=script_id,
        )
        prompt_marker.write_text(prompt_fingerprint, encoding="utf-8")
    else:
        logger.info("[COMPARISON_BOARD] cache hit scene=%s", scene_id)

    web_base = f"/static/projects/{script_id}/comparison_boards/{scene_id}"
    processed_layers = []
    for index, layer in enumerate(image_layers):
        next_layer = dict(layer)
        next_layer["asset_kind"] = "cutout"
        next_layer["image_url"] = f"{web_base}/{item_paths[index].name}"
        next_layer["placement"] = _comparison_cutout_placement(str(next_layer.get("placement") or ""), index, len(image_layers))
        next_layer["animation"] = next_layer.get("animation") or "pop_in"
        processed_layers.append(next_layer)
    return processed_layers


def _sample_blink_face_skin_fill(image: Image.Image, detected: dict[str, dict[str, float]]) -> str | None:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    left_eye = detected.get("eye_left")
    right_eye = detected.get("eye_right")
    mouth = detected.get("mouth")
    if not left_eye or not right_eye:
        return None
    eye_distance = max(1, abs(right_eye["x"] - left_eye["x"]) * width)
    center_x = round(((left_eye["x"] + right_eye["x"]) / 2) * width)
    eye_y = ((left_eye["y"] + right_eye["y"]) / 2) * height
    mouth_y = (mouth["y"] * height) if mouth else eye_y + eye_distance
    center_y = round(min(mouth_y - eye_distance * 0.25, eye_y + eye_distance * 0.35))
    radius_x = max(8, round(eye_distance * 0.24))
    radius_y = max(6, round(eye_distance * 0.18))
    pixels = rgba.load()
    reds: list[int] = []
    greens: list[int] = []
    blues: list[int] = []
    for y in range(max(0, center_y - radius_y), min(height, center_y + radius_y + 1)):
        for x in range(max(0, center_x - radius_x), min(width, center_x + radius_x + 1)):
            dx = (x - center_x) / radius_x
            dy = (y - center_y) / radius_y
            if dx * dx + dy * dy > 1:
                continue
            red, green, blue, alpha = pixels[x, y]
            if alpha < 160:
                continue
            if red < 45 and green < 45 and blue < 45:
                continue
            if red > 245 and green > 245 and blue > 245:
                continue
            reds.append(red)
            greens.append(green)
            blues.append(blue)
    if not reds:
        return None
    return f"#{round(median(reds)):02x}{round(median(greens)):02x}{round(median(blues)):02x}"


def _minimalist_eye_pair_has_face_region(
    image: Image.Image,
    left_eye: dict[str, float],
    right_eye: dict[str, float],
) -> bool:
    width, height = image.size
    pixels = image.load()
    eye_y = (left_eye["cy"] + right_eye["cy"]) / 2
    separation = right_eye["cx"] - left_eye["cx"]
    left = max(0, round((left_eye["cx"] - separation * 0.55) * width))
    right = min(width, round((right_eye["cx"] + separation * 0.55) * width))
    top = max(0, round((eye_y - separation * 0.50) * height))
    bottom = min(height, round((eye_y + separation * 0.90) * height))
    if right <= left or bottom <= top:
        return False

    sampled = 0
    face_like = 0
    dark = 0
    for y in range(top, bottom):
        for x in range(left, right):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 160:
                continue
            sampled += 1
            if red < 55 and green < 55 and blue < 55:
                dark += 1
                continue
            channel_spread = max(red, green, blue) - min(red, green, blue)
            if red >= 150 and green >= 125 and blue >= 90 and channel_spread <= 80:
                face_like += 1
    if sampled < 120:
        return False
    return face_like / sampled >= 0.45 and dark / sampled <= 0.20


def _blink_eye_fill_gradient(
    erase_box: dict[str, float],
    image: Image.Image,
    *,
    preferred_fill: str | None = None,
) -> tuple[str, str, str, str]:
    width, height = image.size
    pixels = image.load()
    left = max(0, round(erase_box["left"] * width))
    right = min(width - 1, round(erase_box["right"] * width))
    top = max(0, round(erase_box["top"] * height))
    bottom = min(height - 1, round(erase_box["bottom"] * height))
    if right <= left or bottom <= top:
        return "#d9a374", "#d9a374", "#d9a374", "#d9a374"

    box_height = bottom - top + 1
    box_width = right - left + 1
    band_height = max(2, round(box_height * 0.28))
    band_width = max(2, round(box_width * 0.28))
    preferred_rgb = _hex_to_rgb(preferred_fill)
    top_color = _median_skin_color_in_box(
        pixels,
        left,
        top,
        right,
        min(bottom, top + band_height),
        preferred_rgb=preferred_rgb,
    )
    bottom_color = _median_skin_color_in_box(
        pixels,
        left,
        max(top, bottom - band_height),
        right,
        bottom,
        preferred_rgb=preferred_rgb,
    )
    left_color = _median_skin_color_in_box(
        pixels,
        left,
        top,
        min(right, left + band_width),
        bottom,
        preferred_rgb=preferred_rgb,
    )
    right_color = _median_skin_color_in_box(
        pixels,
        max(left, right - band_width),
        top,
        right,
        bottom,
        preferred_rgb=preferred_rgb,
    )
    colors = [top_color, bottom_color, left_color, right_color]
    fallback = preferred_fill or next((color for color in colors if color is not None), "#d9a374")
    if top_color is None:
        top_color = fallback
    if bottom_color is None:
        bottom_color = fallback
    if left_color is None:
        left_color = fallback
    if right_color is None:
        right_color = fallback
    return top_color, bottom_color, left_color, right_color


def _median_skin_color_in_box(
    pixels,
    left: int,
    top: int,
    right: int,
    bottom: int,
    *,
    preferred_rgb: tuple[int, int, int] | None = None,
) -> str | None:
    reds: list[int] = []
    greens: list[int] = []
    blues: list[int] = []
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 140:
                continue
            channel_max = max(red, green, blue)
            channel_min = min(red, green, blue)
            brightness = (red + green + blue) / 3
            if channel_max < 28:
                continue
            if channel_min > 115 and brightness > 160 and channel_max - channel_min < 75:
                continue
            if preferred_rgb is not None:
                red_delta = abs(red - preferred_rgb[0])
                green_delta = abs(green - preferred_rgb[1])
                blue_delta = abs(blue - preferred_rgb[2])
                if max(red_delta, green_delta, blue_delta) > 95 or red_delta + green_delta + blue_delta > 210:
                    continue
            reds.append(red)
            greens.append(green)
            blues.append(blue)
    if not reds:
        return None
    return f"#{round(median(reds)):02x}{round(median(greens)):02x}{round(median(blues)):02x}"


def _hex_to_rgb(color: str | None) -> tuple[int, int, int] | None:
    if not color or not color.startswith("#") or len(color) != 7:
        return None
    try:
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    except ValueError:
        return None


def generate_stat_card_cutout(
    *,
    scene_id: str,
    layers: list[dict],
    script_id: str,
    scene_prompt: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
) -> list[dict]:
    """Generate one transparent supporting icon cutout for a stat_card scene.

    Returns the input ``layers`` unchanged when no usable image layer is supplied.
    """

    image_layers = [
        dict(layer)
        for layer in layers
        if isinstance(layer, dict) and layer.get("type", "image") == "image"
    ]
    if not image_layers:
        return layers

    target_layer = image_layers[0]
    icon_prompt = str(target_layer.get("prompt") or scene_prompt or "").strip()
    if not icon_prompt:
        return layers

    output_dir = DATA_DIR / "projects" / script_id / "stat_cards" / scene_id
    output_dir.mkdir(parents=True, exist_ok=True)

    composed_prompt = _compose_stat_card_icon_prompt(icon_prompt)
    prompt_marker = output_dir / "stat_card.prompt"
    prompt_fingerprint = json.dumps(
        {
            "icon_prompt": composed_prompt,
            "width": width,
            "height": height,
            "layer": {
                "id": target_layer.get("id"),
                "prompt": target_layer.get("prompt"),
                "placement": target_layer.get("placement"),
                "animation": target_layer.get("animation"),
            },
        },
        sort_keys=True,
    )

    cutout_path = output_dir / "icon_cutout.png"
    cache_valid = (
        not force
        and prompt_marker.exists()
        and prompt_marker.read_text(encoding="utf-8") == prompt_fingerprint
        and cutout_path.exists()
    )

    if not cache_valid:
        logger.info("[STAT_CARD] generating icon cutout scene=%s", scene_id)
        generated_path = Path(generate_image(composed_prompt, width=width, height=height, script_id=script_id))
        sheet_path = output_dir / "icon_source.png"
        if generated_path.resolve() != sheet_path.resolve():
            shutil.copyfile(generated_path, sheet_path)
        with Image.open(sheet_path) as image:
            source = image.convert("RGBA")
            _save_keyed_trimmed_cutout(source, cutout_path)
        save_vault_image(kind="item", label="Stat card icon", source_path=cutout_path)
        prompt_marker.write_text(prompt_fingerprint, encoding="utf-8")
    else:
        logger.info("[STAT_CARD] cache hit scene=%s", scene_id)

    web_base = f"/static/projects/{script_id}/stat_cards/{scene_id}"
    processed = dict(target_layer)
    processed["asset_kind"] = "cutout"
    processed["image_url"] = f"{web_base}/icon_cutout.png"
    processed["placement"] = str(processed.get("placement") or "center")
    processed["animation"] = processed.get("animation") or "pop_in"
    return [processed]


def _compose_stat_card_icon_prompt(icon_prompt: str) -> str:
    return "\n".join(
        [
            "Generate a single small supporting icon as a clean cartoon illustration for programmatic chroma keying.",
            "",
            f"Icon subject: {icon_prompt.strip()}",
            "",
            "Layout:",
            "- One isolated subject centered in the frame",
            "- Generous empty margin around the subject so automatic trimming does not clip it",
            "- No multiple subjects, no contact sheet, no grid",
            "",
            "Background:",
            "- Solid flat chroma key background filling the entire image",
            "- Use bright green (#00FF00) unless the subject contains green, in which case use bright magenta (#FF00FF)",
            "- The chroma color must NOT appear anywhere within the subject",
            "",
            "Rendering rules:",
            "- Crisp closed silhouette with no soft glow, feathering, or semi-transparent color bleed into the chroma background",
            "- No drop shadows, glows, or effects extending outside the subject boundary",
            "- No frames, borders, mats, picture frames, panels, posters, labels, captions, arrows, or text",
            "- Match the project's flat 2D cartoon house style",
        ]
    ).strip()


def _generate_popup_anchor_cutout(
    *,
    anchor_prompt: str,
    output_dir: Path,
    width: int,
    height: int,
    script_id: str,
    reference_image_path: str | None = None,
    style_reference_path: str | None = None,
    vault_kind: VaultKind = "character",
    vault_label: str = "Popup sequence anchor",
) -> None:
    generated_path = Path(
        generate_image(
            anchor_prompt,
            width=width,
            height=height,
            reference_image_path=reference_image_path,
            style_reference_path=style_reference_path,
            original_prompt=anchor_prompt,
            script_id=script_id,
        )
    )
    source_path = output_dir / "anchor_source.png"
    if generated_path.resolve() != source_path.resolve():
        shutil.copyfile(generated_path, source_path)

    result = process_character_asset_bundle(
        source_path,
        output_dir,
        reference_filename="anchor_source.png",
        cutout_filename="anchor_cutout.png",
        metadata_filename="anchor_metadata.json",
    )
    save_vault_image(kind=vault_kind, label=vault_label, source_path=result.cutout_path)


def _create_popup_anchor_cutout_from_reference(
    *,
    reference_image_path: str,
    output_dir: Path,
) -> None:
    source_path = output_dir / "anchor_source.png"
    if Path(reference_image_path).resolve() != source_path.resolve():
        shutil.copyfile(reference_image_path, source_path)
    result = process_character_asset_bundle(
        source_path,
        output_dir,
        reference_filename="anchor_source.png",
        cutout_filename="anchor_cutout.png",
        metadata_filename="anchor_metadata.json",
    )
    save_vault_image(kind="character", label="Popup sequence anchor fallback", source_path=result.cutout_path)


def _create_transparent_popup_anchor_cutout(*, output_dir: Path) -> None:
    source_path = output_dir / "anchor_source.png"
    cutout_path = output_dir / "anchor_cutout.png"
    Image.new("RGBA", (8, 8), color=(0, 0, 0, 0)).save(source_path)
    Image.new("RGBA", (8, 8), color=(0, 0, 0, 0)).save(cutout_path)


def _generate_popup_item_cutouts(
    *,
    item_prompt: str,
    labels: list[str],
    output_dir: Path,
    width: int,
    height: int,
    script_id: str,
) -> None:
    generated_path = Path(generate_image(item_prompt, width=width, height=height, script_id=script_id))
    sheet_path = output_dir / "item_sheet.png"
    if generated_path.resolve() != sheet_path.resolve():
        shutil.copyfile(generated_path, sheet_path)

    with Image.open(sheet_path) as image:
        source = image.convert("RGBA")
        cell_width = source.width // len(labels)
        for index, label in enumerate(labels):
            left = index * cell_width
            right = source.width if index == len(labels) - 1 else (index + 1) * cell_width
            crop = source.crop((left, 0, right, source.height))
            raw_path = output_dir / f"raw_crop_{index + 2:02d}_{_slug(label)}.png"
            crop.save(raw_path)
            output_path = output_dir / f"crop_{index + 2:02d}_{_slug(label)}.png"
            _save_keyed_trimmed_cutout(crop, output_path)
            save_vault_image(kind="item", label=label, source_path=output_path)


def _generate_comparison_subject_cutouts(
    *,
    item_prompt: str,
    labels: list[str],
    output_dir: Path,
    width: int,
    height: int,
    script_id: str,
) -> None:
    generated_path = Path(generate_image(item_prompt, width=width, height=height, script_id=script_id))
    sheet_path = output_dir / "subject_sheet.png"
    if generated_path.resolve() != sheet_path.resolve():
        shutil.copyfile(generated_path, sheet_path)

    with Image.open(sheet_path) as image:
        source = image.convert("RGBA")
        cell_width = source.width // len(labels)
        for index, label in enumerate(labels):
            left = index * cell_width
            right = source.width if index == len(labels) - 1 else (index + 1) * cell_width
            crop = source.crop((left, 0, right, source.height))
            raw_path = output_dir / f"raw_subject_{index + 1:02d}_{_slug(label)}.png"
            crop.save(raw_path)
            output_path = output_dir / f"subject_{index + 1:02d}_{_slug(label)}.png"
            _save_keyed_trimmed_cutout(crop, output_path)
            save_vault_image(kind="item", label=label, source_path=output_path)


def _compose_popup_anchor_prompt(
    scene_prompt: str,
    *,
    contains_person: bool,
    character_context: str = "",
) -> str:
    if character_context:
        subject_line = (
            "Create one large isolated full-body cutout of the active recurring protagonist standing upright."
        )
    else:
        subject_line = (
            "Create one large isolated full-body cutout of the scene's main character/person standing upright."
            if contains_person
            else "Create one large isolated full-body cutout of the scene's main subject standing upright."
        )
    parts = [
        subject_line,
        "The subject should be detailed, expressive, centered, visually dominant, and shown in a clean neutral standing pose.",
        "Use a flat chroma background color that does not appear anywhere in the subject, preferably bright green unless the subject contains green.",
        "No popup items, no secondary icons, no speech bubbles, no text, no labels, no frames, no full background scene.",
        "No sitting.",
        "No desks, no phones, no notification bubbles, no props, and no environment.",
        "Leave a little empty margin around the full subject so automatic trimming does not clip the pose.",
    ]
    if character_context:
        parts.extend(
            [
                "Use the included character reference as the source of truth for the anchor identity.",
                "The popup anchor must preserve the active protagonist exactly; do not invent a new anonymous host or substitute character.",
                character_context,
            ]
        )
    parts.extend(
        [
            "Use the scene direction only for character identity and visual style; ignore its action, environment, props, and popup items.",
            "",
            "Character/style context:",
            scene_prompt.strip(),
        ]
    )
    return "\n".join(parts).strip()


def _compose_popup_item_sheet_prompt(scene_prompt: str, labels: list[str]) -> str:
    item_lines = [f"{index}. {label}" for index, label in enumerate(labels, start=1)]
    return "\n".join(
        [
            "You are generating a contact sheet for automatic programmatic cropping.",
            "",
            f"Generate exactly {len(labels)} cartoon popup item(s) arranged in a single row,",
            "evenly spaced, left to right in this exact order:",
            *item_lines,
            "",
            "Layout rules:",
            "- Each item occupies an equal-width vertical slot",
            "- Items are horizontally centered within their slot",
            "- Items fill no more than 70% of their slot width, leaving clear margins on both sides",
            "- All items are the same visual scale relative to their slot",
            "- Single row only; do not stack or wrap items",
            "",
            "Background:",
            "- Solid flat chroma key background across the entire image",
            "- Use bright green (#00FF00) unless any item contains green, in which case use bright magenta (#FF00FF)",
            "- The chroma color must not appear anywhere within any item",
            "",
            "Item rendering:",
            "- Each item is fully self-contained with no overlap into adjacent slots",
            "- Crisp closed silhouettes with no soft glow, feathering, or semi-transparent color bleed into the chroma background",
            "- No drop shadows, glows, or effects that extend outside the item boundary",
            "- No frames, borders, labels, captions, arrows, or text",
            "- No background scenes, environments, or context behind items",
            "- No main character or human figures",
            "",
            "Scene context for style only:",
            scene_prompt.strip(),
        ]
    ).strip()


def _compose_comparison_subject_sheet_prompt(scene_prompt: str, labels: list[str]) -> str:
    item_lines = [f"{index}. {label}" for index, label in enumerate(labels, start=1)]
    return "\n".join(
        [
            "You are generating a contact sheet for automatic programmatic cropping.",
            "",
            f"Generate exactly {len(labels)} comparison subject cutout(s) arranged in a single row,",
            "evenly spaced, left to right in this exact order:",
            *item_lines,
            "",
            "Layout rules:",
            "- Each subject occupies an equal-width vertical slot",
            "- Subjects are horizontally centered within their slot",
            "- Subjects fill no more than 78% of their slot width, leaving clear margins",
            "- Single row only; do not stack or wrap subjects",
            "- Do not create a split-screen board; the renderer owns all board layout, dividers, labels, arrows, and stat chips",
            "",
            "Background:",
            "- Solid flat chroma key background across the entire image",
            "- Use bright green (#00FF00) unless a subject contains green, in which case use bright magenta (#FF00FF)",
            "- The chroma color must not appear anywhere within any subject",
            "",
            "Subject rendering:",
            "- Each subject is fully self-contained with no overlap into adjacent slots",
            "- Crisp closed silhouettes with no soft glow, feathering, or semi-transparent color bleed into the chroma background",
            "- No drop shadows, glows, or effects that extend outside the subject boundary",
            "- No frames, borders, labels, captions, arrows, badges, stat chips, or text",
            "- No background scenes, environments, or context behind subjects",
            "",
            "Scene context for style only:",
            scene_prompt.strip(),
        ]
    ).strip()


def _comparison_subject_label(layer: dict, index: int) -> str:
    prompt = str(layer.get("prompt") or "").strip()
    match = re.search(r"\bfor\s+(.+?):", prompt, flags=re.IGNORECASE)
    if match:
        return _clean_popup_label(match.group(1))
    prompt = re.sub(r"Comparison board transparent cutout(?:\s+for\s+[^:]+)?:\s*", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"\bNo text in image\.?", "", prompt, flags=re.IGNORECASE)
    prompt = prompt.split(".", 1)[0]
    return _clean_popup_label(prompt) or f"comparison subject {index + 1}"


def _comparison_cutout_placement(placement: str, index: int, total: int) -> str:
    normalized = placement.replace("_", "-")
    if normalized in {"left", "center", "right"}:
        return normalized
    defaults = {
        2: ["left", "right"],
        3: ["left", "center", "right"],
    }
    return defaults.get(total, defaults[2])[min(index, len(defaults.get(total, defaults[2])) - 1)]


def _popup_item_label(layer: dict, index: int) -> str:
    prompt = str(layer.get("prompt") or "").strip()
    match = re.search(r"\bfor\s+(.+?):", prompt, flags=re.IGNORECASE)
    if match:
        return _clean_popup_label(match.group(1))
    prompt = re.sub(r"small framed Headless Hero cartoon panel[:,]?\s*", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"Popup item cutout prompt(?:\s+for\s+[^:]+)?:\s*", "", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"\bNo text in image\.?", "", prompt, flags=re.IGNORECASE)
    prompt = prompt.split(".", 1)[0]
    return _clean_popup_label(prompt) or f"popup item {index + 1}"


def _clean_popup_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" .,:;-"))


def _popup_cutout_placement(placement: str, index: int, total: int) -> str:
    normalized = placement.replace("_", "-")
    if normalized == "center" and total == 3:
        return "top"
    if normalized:
        return normalized
    defaults = {
        1: ["top"],
        2: ["left", "right"],
        3: ["left", "top", "right"],
        4: ["top-left", "top-right", "bottom-left", "bottom-right"],
    }
    return defaults.get(total, defaults[3])[min(index, len(defaults.get(total, defaults[3])) - 1)]


def _save_keyed_trimmed_cutout(image: Image.Image, output_path: Path, *, padding: int = 24) -> list[int]:
    keyed = _key_out_background(image.convert("RGBA"))
    bbox = keyed.getbbox()
    if bbox is None:
        keyed.save(output_path)
        return [0, 0, keyed.width, keyed.height]

    left, top, right, bottom = bbox
    padded = [
        max(0, left - padding),
        max(0, top - padding),
        min(keyed.width, right + padding),
        min(keyed.height, bottom + padding),
    ]
    keyed.crop(tuple(padded)).save(output_path)
    return padded


def _key_out_background(image: Image.Image, *, tolerance: int = 70) -> Image.Image:
    bg = _sample_background_rgb(image)
    data = bytearray(image.tobytes())
    for index in range(0, len(data), 4):
        red, green, blue, alpha = data[index:index + 4]
        distance = ((red - bg[0]) ** 2 + (green - bg[1]) ** 2 + (blue - bg[2]) ** 2) ** 0.5
        if distance <= tolerance:
            data[index + 3] = 0
        else:
            data[index + 3] = alpha
    return Image.frombytes("RGBA", image.size, bytes(data))


def _sample_background_rgb(image: Image.Image) -> tuple[int, int, int]:
    corner_size = max(1, min(image.width, image.height, 24))
    corners = [
        image.crop((0, 0, corner_size, corner_size)),
        image.crop((image.width - corner_size, 0, image.width, corner_size)),
        image.crop((0, image.height - corner_size, corner_size, image.height)),
        image.crop((image.width - corner_size, image.height - corner_size, image.width, image.height)),
    ]
    samples = []
    for corner in corners:
        data = corner.convert("RGB").tobytes()
        samples.extend((data[index], data[index + 1], data[index + 2]) for index in range(0, len(data), 3))
    red = round(sum(pixel[0] for pixel in samples) / len(samples))
    green = round(sum(pixel[1] for pixel in samples) / len(samples))
    blue = round(sum(pixel[2] for pixel in samples) / len(samples))
    return red, green, blue


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug or "crop"


def generate_scene_image(
    scene_id: str,
    visual_prompt: str,
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
    style_guide: str = "",
    contains_person: bool = False,
) -> tuple[str, str, dict[str, object] | None]:
    """Generate a single scene image and save it locally.

    If the image already exists and force=False, skips regeneration.
    style_guide overrides the default _STYLE_GUIDE if provided.
    When contains_person is True, injects Eli character reference + prompt.
    Returns (web-relative path, composed prompt used, source metadata).
    """
    _raise_for_caption_text_prompt_leak([visual_prompt], scene_id=scene_id)
    prompt, reference_image_path, style_reference_path = _compose_image_prompt_context(
        visual_prompt=visual_prompt,
        script_id=script_id,
        style_guide=style_guide,
        contains_person=contains_person,
    )

    # Check cache: if image exists and we have a matching prompt marker, skip regen
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    suffix = ""
    filename = f"{scene_id}.png"
    local_path = images_dir / filename
    prompt_marker = images_dir / f"{scene_id}.prompt"
    web_path = f"/static/projects/{script_id}/images/{filename}"

    if not force and local_path.exists() and prompt_marker.exists():
        cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
        if cached_prompt == prompt:
            logger.info("Image cache hit for scene %s", scene_id)
            return web_path, prompt, _read_source_metadata(local_path)

    logger.info("Generating image for scene %s (contains_person=%s)", scene_id, contains_person)
    try:
        tmp_path = generate_image(
            prompt, width=width, height=height,
            original_prompt=visual_prompt,
            reference_image_path=reference_image_path,
            style_reference_path=style_reference_path,
            script_id=script_id,
        )
    except Exception:
        scraper_fallback_enabled = _setting_enabled(os.environ.get("IMAGE_SCRAPER_FALLBACK_ENABLED"))
        if scraper_fallback_enabled:
            from integrations.google_image_scraper import scrape_google_image_sync

            logger.error("Image generation failed for scene %s, using opt-in scraper fallback", scene_id)
            search_query = visual_prompt[:120]
            scraped = scrape_google_image_sync(
                query=search_query,
                output_path=str(local_path),
                width=width,
                height=height,
            )
            if scraped:
                logger.warning("Using scraped web image for scene %s", scene_id)
                record_fallback(
                    category="image_generation",
                    event="scraped_image_fallback_used",
                    reason="AI image generation failed after retries",
                    from_value=provider_fingerprint(),
                    to_value="scraped_web_image",
                    script_id=script_id,
                    scene_id=scene_id,
                    severity="fail",
                    metadata={"provider": "google_images_scraper", "source_type": "scraped_web_image"},
                    logger=logger,
                )
                metadata = {
                    "source_type": "scraped_web_image",
                    "provider": "google_images_scraper",
                    "query": search_query,
                    "reason": "AI image generation failed after retries",
                    "license_note": "Scraped web image; verify usage rights before publishing.",
                    "opt_in_setting": "IMAGE_SCRAPER_FALLBACK_ENABLED",
                    "fallback": True,
                }
                _write_source_metadata(local_path, metadata)
                prompt_marker.write_text(prompt, encoding="utf-8")
                return web_path, prompt, metadata

            logger.error("Opt-in scraper fallback also failed for scene %s, creating placeholder", scene_id)
        else:
            logger.error("Image generation failed for scene %s; scraper fallback is disabled", scene_id)

        _create_placeholder_image(local_path, width, height, f"Image generation failed:\n{visual_prompt[:80]}")
        record_fallback(
            category="image_generation",
            event="image_placeholder_created",
            reason="AI image generation failed and scraped web-image fallback is disabled or unavailable",
            from_value=provider_fingerprint(),
            to_value="local_placeholder",
            script_id=script_id,
            scene_id=scene_id,
            severity="fail",
            metadata={"source_type": "placeholder"},
            logger=logger,
        )
        metadata = {
            "source_type": "placeholder",
            "provider": "local_placeholder",
            "reason": "AI image generation failed and scraped web-image fallback is disabled or unavailable",
            "fallback": True,
        }
        _write_source_metadata(local_path, metadata)
        prompt_marker.write_text(prompt, encoding="utf-8")
        return web_path, prompt, metadata

    metadata = _move_generated_image(tmp_path, local_path, {
        "source_type": "ai_generated",
        "provider": provider_fingerprint(),
        "fallback": False,
    })

    # Write prompt marker for cache validation
    prompt_marker.write_text(prompt, encoding="utf-8")

    return web_path, prompt, metadata


def generate_scene_frames(
    scene_id: str,
    frame_prompts: list[str],
    script_id: str,
    visual_prompt: str = "",
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
    style_guide: str = "",
    contains_person: bool = False,
) -> list[tuple[str, str, dict[str, object] | None]]:
    """Generate multiple frames for a scene and save them locally.

    Each frame is saved as {scene_id}_f{i}.png with a cache file {scene_id}_f{i}.prompt.
    visual_prompt is the scene's anchor description used to enforce cross-frame consistency.
    Returns list of (web_path, composed_prompt, source metadata) tuples.
    """
    _raise_for_caption_text_prompt_leak([visual_prompt, *frame_prompts], scene_id=scene_id)
    guide = style_guide if style_guide else _STYLE_GUIDE
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    eli_enabled, main_character_url, main_character_obj = _load_project_character_context(script_id)
    _ensure_project_character_reference_ready(
        script_id=script_id,
        eli_enabled=eli_enabled,
        main_character_reference_url=main_character_url,
        main_character=main_character_obj,
    )
    reference_image_path, character_text = _resolve_character_reference(
        script_id=script_id,
        contains_person=contains_person,
        eli_enabled=eli_enabled,
        main_character_reference_url=main_character_url,
        main_character=main_character_obj,
    )

    project_style_enabled = _load_project_style_enabled(script_id)
    style_reference_path = _resolve_style_preset(
        eli_enabled=eli_enabled,
        project_style_enabled=project_style_enabled,
    )

    total_frames = len(frame_prompts)
    logger.info("Generating %s frames for scene %s", total_frames, scene_id)
    results: list[tuple[str, str, dict[str, object] | None]] = []
    prev_frame_path: Path | None = None

    for i, frame_prompt in enumerate(frame_prompts):
        filename = f"{scene_id}_f{i}.png"
        local_path = images_dir / filename
        prompt_marker = images_dir / f"{scene_id}_f{i}.prompt"
        web_path = f"/static/projects/{script_id}/images/{filename}"

        # Determine if we can chain from the previous frame
        use_reference = (
            i > 0
            and prev_frame_path is not None
            and prev_frame_path.exists()
        )

        # Build the full frame description by combining the anchor visual_prompt
        # with the brief delta frame_prompt (new scriptwriter format).
        # If frame_prompt already contains the full scene (legacy verbatim format),
        # this still works correctly — we simply concatenate.
        if visual_prompt and frame_prompt and not frame_prompt.startswith(visual_prompt[:40]):
            full_frame_description = f"{visual_prompt} — Frame variation: {frame_prompt}"
        else:
            full_frame_description = frame_prompt

        # Build prompt: different strategy for text-only vs reference-based
        if use_reference:
            # Kontext-optimized: edit instruction referencing the input image
            parts: list[str] = []
            if _VISUAL_STYLE:
                parts.append(_VISUAL_STYLE)
            parts.append(_FULL_BLEED_IMAGE_GUARD)
            if character_text:
                parts.append(character_text)
            if visual_prompt.strip():
                parts.append(f"Shared scene brief for the whole continuous sequence:\n{visual_prompt.strip()}")
            parts.append(
                f"This is frame {i + 1} of {total_frames} in an animation sequence. "
                f"Using the input image as the previous frame reference, progress the scene by changing ONLY the following: "
                f"{frame_prompt}\n"
                f"Maintain identical style, background, composition, character design, "
                f"and color palette. Only the described action should change."
            )
            prompt = "\n\n".join(parts)
        else:
            # First frame or no reference: full text-to-image prompt
            parts: list[str] = []
            if _VISUAL_STYLE:
                parts.append(_VISUAL_STYLE)
            parts.append(_FULL_BLEED_IMAGE_GUARD)
            if guide:
                parts.append(guide)
            if character_text:
                parts.append(character_text)

            if visual_prompt and total_frames > 1:
                continuity = (
                    f"ANIMATION SEQUENCE: This is frame {i + 1} of {total_frames} "
                    f"in an animation sequence.\n"
                    f"BASE SCENE: {visual_prompt}\n"
                    f"ALL frames must have IDENTICAL style, character design, "
                    f"background, composition, and color palette. "
                    f"Only the specific action/pose described below should differ "
                    f"from the base scene.\n\n"
                    f"FRAME INSTRUCTION: {full_frame_description}"
                )
                parts.append(continuity)
            else:
                parts.append(full_frame_description)

            prompt = "\n\n".join(parts)

        # Append reference path + mtime for cache invalidation when reference changes
        if reference_image_path:
            try:
                mtime = int(Path(reference_image_path).stat().st_mtime)
                prompt += f"\n[char_ref:{reference_image_path}:{mtime}]"
            except OSError:
                pass

        effective_style_reference_path = None if use_reference else style_reference_path
        if effective_style_reference_path:
            try:
                mtime = int(Path(effective_style_reference_path).stat().st_mtime)
                prompt += f"\n[style_ref:{effective_style_reference_path}:{mtime}]"
            except OSError:
                pass

        if use_reference:
            try:
                mtime = prev_frame_path.stat().st_mtime_ns if prev_frame_path else 0
                prompt += f"\n[reference_previous:{prev_frame_path}:{mtime}]"
            except OSError:
                pass

        # Cache check
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
            if cached_prompt == prompt:
                results.append((web_path, prompt, _read_source_metadata(local_path)))
                prev_frame_path = local_path
                continue

        # Frame 0 with person: use resolved character reference; frames 1+: use prev frame for continuity
        if use_reference:
            ref_path = str(prev_frame_path)
        else:
            ref_path = reference_image_path

        tmp_path = generate_image(
            prompt,
            width=width,
            height=height,
            reference_image_path=ref_path,
            original_prompt=full_frame_description,
            style_reference_path=effective_style_reference_path,
            script_id=script_id,
        )
        metadata = _move_generated_image(tmp_path, local_path, {
            "source_type": "ai_generated",
            "provider": provider_fingerprint(),
            "fallback": False,
        })
        prompt_marker.write_text(prompt, encoding="utf-8")
        results.append((web_path, prompt, metadata))
        prev_frame_path = local_path

    return results


def generate_scene_frames_v2(
    scene_id: str,
    frame_directives: list[dict],
    script_id: str,
    visual_prompt: str = "",
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
    style_guide: str = "",
    contains_person: bool = False,
) -> list[tuple[str, str, dict[str, object] | None]]:
    """Generate frames using the Visual Beat System's per-frame directives.

    Dispatches per-directive based on source and reference_previous:
      - source == "subtitle" → skip generation, return ("", prompt)
      - source == "ai_generated" + reference_previous → Gemini image-to-image
      - source == "ai_generated" + !reference_previous → Gemini text-to-image (independent)

    Returns list of (web_path, prompt, source metadata) tuples. Empty string web_path for subtitle frames.
    """
    from models.script import FrameDirective as FrameDirectiveModel

    prompt_parts = [visual_prompt]
    for directive in frame_directives:
        if isinstance(directive, dict):
            prompt_parts.append(str(directive.get("prompt") or ""))
            prompt_parts.append(str(directive.get("search_query") or ""))
        elif hasattr(directive, "prompt"):
            prompt_parts.append(str(getattr(directive, "prompt") or ""))
            prompt_parts.append(str(getattr(directive, "search_query", "") or ""))
    _raise_for_caption_text_prompt_leak(prompt_parts, scene_id=scene_id)

    guide = style_guide if style_guide else _STYLE_GUIDE
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    eli_enabled, main_character_url, main_character_obj = _load_project_character_context(script_id)
    _ensure_project_character_reference_ready(
        script_id=script_id,
        eli_enabled=eli_enabled,
        main_character_reference_url=main_character_url,
        main_character=main_character_obj,
    )

    project_style_enabled = _load_project_style_enabled(script_id)
    style_reference_path = _resolve_style_preset(
        eli_enabled=eli_enabled,
        project_style_enabled=project_style_enabled,
    )

    total_frames = len(frame_directives)
    logger.info("Generating %d frames (v2) for scene %s", total_frames, scene_id)
    results: list[tuple[str, str, dict[str, object] | None]] = []
    prev_frame_path: Path | None = None

    for i, raw_directive in enumerate(frame_directives):
        # Validate directive
        directive = FrameDirectiveModel.model_validate(raw_directive)

        filename = f"{scene_id}_f{i}.png"
        local_path = images_dir / filename
        prompt_marker = images_dir / f"{scene_id}_f{i}.prompt"
        web_path = f"/static/projects/{script_id}/images/{filename}"

        # --- Subtitle frames: no image generation ---
        if directive.source == "subtitle":
            results.append(("", directive.prompt, None))
            # Don't update prev_frame_path — subtitles can't be references
            continue

        directive_prompt = directive.prompt or directive.search_query

        # --- AI-generated frames ---
        # Per-frame contains_person: check directive first, fall back to scene-level
        frame_has_person = directive.contains_person or contains_person

        # Resolve character reference for this frame's person flag.
        reference_image_path, character_text = _resolve_character_reference(
            script_id=script_id,
            contains_person=frame_has_person,
            eli_enabled=eli_enabled,
            main_character_reference_url=main_character_url,
            main_character=main_character_obj,
        )

        use_reference = (
            directive.reference_previous
            and prev_frame_path is not None
            and prev_frame_path.exists()
        )
        use_style_anchor = (
            not directive.reference_previous
            and total_frames > 1
            and prev_frame_path is not None
            and prev_frame_path.exists()
        )

        if use_reference:
            # Kontext-optimized: edit instruction referencing the input image
            parts: list[str] = []
            if _VISUAL_STYLE:
                parts.append(_VISUAL_STYLE)
            parts.append(_FULL_BLEED_IMAGE_GUARD)
            if character_text:
                parts.append(character_text)
            if visual_prompt.strip():
                parts.append(f"Shared scene brief for the whole continuous sequence:\n{visual_prompt.strip()}")
            parts.append(
                f"This is image {i + 1} of {total_frames} in an animation sequence. "
                f"Using the input image as the previous frame reference, progress the scene by changing ONLY the following: "
                f"{directive_prompt}\n"
                f"Maintain identical style, background, composition, character design, "
                f"and color palette. Only the described action should change."
            )
            prompt = "\n\n".join(parts)
        else:
            # Independent sequence images may change subject/composition, but use
            # the previous generated image as a visual style anchor when present.
            parts: list[str] = []
            if _VISUAL_STYLE:
                parts.append(_VISUAL_STYLE)
            parts.append(_FULL_BLEED_IMAGE_GUARD)
            if total_frames > 1:
                parts.append(_SEQUENCE_CONSISTENCY_PROMPT)
                if visual_prompt.strip():
                    parts.append(f"Shared scene brief for the whole sequence:\n{visual_prompt.strip()}")
            if use_style_anchor:
                parts.append(
                    "Use the input image as a visual style anchor only: match its line weight, flat-color rendering, "
                    "palette discipline, character proportions, and overall cartoon finish. "
                    "Do not copy its exact subject or layout; create the new requested image content below."
                )
            if guide and guide != directive_prompt:
                parts.append(f"Scene context: {guide}\n\nThis specific image:")
            if character_text:
                parts.append(character_text)
            parts.append(directive_prompt)
            prompt = "\n\n".join(parts)

        # Append reference path + mtime for cache invalidation when reference changes
        if reference_image_path:
            try:
                mtime = int(Path(reference_image_path).stat().st_mtime)
                prompt += f"\n[char_ref:{reference_image_path}:{mtime}]"
            except OSError:
                pass

        effective_style_reference_path = (
            None if (use_reference or use_style_anchor) else style_reference_path
        )
        if effective_style_reference_path:
            try:
                mtime = int(Path(effective_style_reference_path).stat().st_mtime)
                prompt += f"\n[style_ref:{effective_style_reference_path}:{mtime}]"
            except OSError:
                pass

        if use_reference or use_style_anchor:
            try:
                anchor_kind = "reference_previous" if use_reference else "style_anchor"
                mtime = prev_frame_path.stat().st_mtime_ns if prev_frame_path else 0
                prompt += f"\n[{anchor_kind}:{prev_frame_path}:{mtime}]"
            except OSError:
                pass

        # Cache check
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
            if cached_prompt == prompt:
                results.append((web_path, prompt, _read_source_metadata(local_path)))
                prev_frame_path = local_path
                continue

        # reference_previous wins for animation continuity; independent sequence
        # images may still use the previous output as a style-only anchor.
        if use_reference:
            ref_path = str(prev_frame_path)
        elif use_style_anchor:
            ref_path = str(prev_frame_path)
        else:
            ref_path = reference_image_path

        tmp_path = generate_image(
            prompt,
            width=width,
            height=height,
            reference_image_path=ref_path,
            original_prompt=directive_prompt,
            style_reference_path=effective_style_reference_path,
            script_id=script_id,
        )
        metadata = _move_generated_image(tmp_path, local_path, {
            "source_type": "ai_generated",
            "provider": provider_fingerprint(),
            "fallback": False,
        })
        prompt_marker.write_text(prompt, encoding="utf-8")
        results.append((web_path, prompt, metadata))
        prev_frame_path = local_path

    return results


def _generate_one_scene(
    scene: dict[str, str],
    script_id: str,
    width: int,
    height: int,
    style_guide: str,
) -> dict[str, str | None]:
    """Generate visuals for a single scene; mirrors the original per-scene branches.

    Returns the same shape the batch loop used to append. Errors are captured
    in the returned dict so a parallel worker pool can keep going.
    """
    def with_visual_layers(result: dict[str, object]) -> dict[str, object]:
        if scene.get("visual_mode") == "captions":
            return result
        visual_mode = str(scene.get("visual_mode") or scene.get("visual_treatment") or "full_frame")
        treatment = visual_mode if visual_mode in {"popup_sequence", "comparison_board", "stat_card"} else "full_frame"
        layers = scene.get("visual_layers", []) or []
        if treatment not in {"popup_sequence", "comparison_board", "stat_card"}:
            return result
        if not layers:
            return result
        layer_dicts = [
            layer.model_dump() if hasattr(layer, "model_dump") else dict(layer)
            for layer in layers
            if isinstance(layer, dict) or hasattr(layer, "model_dump")
        ]
        if not layer_dicts:
            return result
        if treatment == "popup_sequence":
            result["visual_layers"] = generate_popup_sequence_cutouts(
                scene_id=scene["scene_id"],
                layers=layer_dicts,
                script_id=script_id,
                scene_prompt=str(scene.get("visual_prompt") or ""),
                width=width,
                height=height,
                contains_person=bool(scene.get("contains_person", False)),
            )
        elif treatment == "comparison_board":
            result["visual_layers"] = generate_comparison_board_cutouts(
                scene_id=scene["scene_id"],
                layers=layer_dicts,
                script_id=script_id,
                scene_prompt=str(scene.get("visual_prompt") or ""),
                width=width,
                height=height,
            )
        elif treatment == "stat_card":
            result["visual_layers"] = generate_stat_card_cutout(
                scene_id=scene["scene_id"],
                layers=layer_dicts,
                script_id=script_id,
                scene_prompt=str(scene.get("visual_prompt") or ""),
                width=width,
                height=height,
            )
        else:
            result["visual_layers"] = generate_visual_layer_panels(
                scene["scene_id"],
                layer_dicts,
                script_id,
                width=width,
                height=height,
                contains_person=bool(scene.get("contains_person", False)),
                visual_treatment=treatment,
            )
        return result

    try:
        if _contains_caption_text_prompt_leak(scene):
            raise RuntimeError(
                "Scene visual prompt requests renderer-owned caption text; "
                "use visual_mode='captions' with caption_text/caption_emphasis instead."
            )

        visual_mode = scene.get("visual_mode") or ("video" if scene.get("media_source") == "ai_video" else scene.get("visual_treatment", "full_frame"))

        # --- AI video dispatch ---
        if visual_mode == "video":
            from pipeline.video_gen import generate_scene_video

            duration = float(scene.get("audio_duration_seconds", 5.0) or 5.0)
            logger.info("[AI_VIDEO] scene %s — prompt: %s", scene["scene_id"], scene.get("visual_prompt", "")[:80])
            video_url, prompt_used, source_metadata = generate_scene_video(
                scene_id=scene["scene_id"],
                visual_prompt=scene.get("visual_prompt", ""),
                script_id=script_id,
                width=width,
                height=height,
                scene_duration_seconds=duration,
                contains_person=scene.get("contains_person", False),
            )
            return with_visual_layers({
                "scene_id": scene["scene_id"],
                "image_url": None,
                "frame_urls": [],
                "video_url": video_url,
                "prompt_used": prompt_used,
                "visual_source_metadata": source_metadata,
                "error": None,
            })

        if visual_mode == "captions" and not str(scene.get("visual_prompt") or "").strip():
            logger.info("[CAPTIONS] scene %s - text-only caption, skipping image generation", scene["scene_id"])
            return {
                "scene_id": scene["scene_id"],
                "image_url": None,
                "frame_urls": [],
                "video_url": "",
                "prompt_used": None,
                "visual_source_metadata": None,
                "error": None,
            }

        # --- AI-generated (default) ---
        logger.info("[GEMINI] scene %s — prompt: %s", scene["scene_id"], scene.get("visual_prompt", "")[:80])
        frame_directives = scene.get("frame_directives", [])
        frame_prompts = scene.get("frame_prompts", [])
        scene_contains_person = scene.get("contains_person", False)
        treatment = visual_mode if visual_mode in {"popup_sequence", "comparison_board", "stat_card"} else "full_frame"

        if treatment != "full_frame":
            return with_visual_layers({
                "scene_id": scene["scene_id"],
                "image_url": None,
                "frame_urls": [],
                "video_url": "",
                "prompt_used": None,
                "visual_source_metadata": None,
                "error": None,
            })

        # Visual Beat System v2 path: per-frame directives
        if frame_directives:
            frame_results = generate_scene_frames_v2(
                scene_id=scene["scene_id"],
                frame_directives=frame_directives,
                script_id=script_id,
                visual_prompt=scene.get("visual_prompt", ""),
                width=width,
                height=height,
                style_guide=style_guide,
                contains_person=scene_contains_person,
            )
            frame_urls = [url for url, _, _ in frame_results]
            source_metadata = next((metadata for url, _, metadata in frame_results if url and metadata), None)
            return with_visual_layers({
                "scene_id": scene["scene_id"],
                "image_url": next((u for u in frame_urls if u), None),
                "frame_urls": frame_urls,
                "video_url": "",
                "prompt_used": frame_results[0][1] if frame_results else None,
                "visual_source_metadata": source_metadata,
                "error": None,
            })

        # Legacy multi-frame path
        if frame_prompts:
            frame_results = generate_scene_frames(
                scene_id=scene["scene_id"],
                frame_prompts=frame_prompts,
                script_id=script_id,
                visual_prompt=scene.get("visual_prompt", ""),
                width=width,
                height=height,
                style_guide=style_guide,
                contains_person=scene_contains_person,
            )
            frame_urls = [url for url, _, _ in frame_results]
            source_metadata = next((metadata for url, _, metadata in frame_results if url and metadata), None)
            return with_visual_layers({
                "scene_id": scene["scene_id"],
                "image_url": frame_urls[0] if frame_urls else None,
                "frame_urls": frame_urls,
                "video_url": "",
                "prompt_used": frame_results[0][1] if frame_results else None,
                "visual_source_metadata": source_metadata,
                "error": None,
            })

        # Single-image path
        image_url, prompt_used, source_metadata = generate_scene_image(
            scene_id=scene["scene_id"],
            visual_prompt=scene["visual_prompt"],
            script_id=script_id,
            width=width,
            height=height,
            style_guide=style_guide,
            contains_person=scene_contains_person,
        )
        return with_visual_layers({
            "scene_id": scene["scene_id"],
            "image_url": image_url,
            "frame_urls": [],
            "video_url": "",
            "prompt_used": prompt_used,
            "visual_source_metadata": source_metadata,
            "error": None,
        })
    except Exception as exc:
        logger.error("Image generation failed for scene %s: %s", scene["scene_id"], exc, exc_info=True)
        return {
            "scene_id": scene["scene_id"],
            "image_url": None,
            "prompt_used": None,
            "error": str(exc),
        }


def generate_scene_visual(
    scene: dict[str, str],
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    style_guide: str = "",
) -> dict[str, str | None]:
    """Generate visuals for a single scene."""
    return _generate_one_scene(scene, script_id, width, height, style_guide)


def _google_batch_visual_mode(scene: dict[str, object]) -> str:
    return str(
        scene.get("visual_mode")
        or ("video" if scene.get("media_source") == "ai_video" else scene.get("visual_treatment", "full_frame"))
        or "full_frame"
    )


def _is_google_batch_eligible(scene: dict[str, object]) -> bool:
    visual_mode = _google_batch_visual_mode(scene)
    if visual_mode == "captions" and not str(scene.get("visual_prompt") or "").strip():
        return False
    if visual_mode not in {"full_frame", "captions"}:
        return False
    if scene.get("frame_prompts"):
        return False
    frame_directives = scene.get("frame_directives") or []
    if frame_directives:
        return False
    return bool(str(scene.get("visual_prompt") or "").strip())


def _prepare_google_batch_scene(
    scene: dict[str, object],
    script_id: str,
    width: int,
    height: int,
    style_guide: str,
) -> tuple[GoogleBatchImageRequest | None, dict[str, object] | None, Path | None, Path | None]:
    scene_id = str(scene["scene_id"])
    visual_prompt = str(scene.get("visual_prompt") or "")
    _raise_for_caption_text_prompt_leak([visual_prompt], scene_id=scene_id)
    prompt, reference_image_path, style_reference_path = _compose_image_prompt_context(
        visual_prompt=visual_prompt,
        script_id=script_id,
        style_guide=style_guide,
        contains_person=bool(scene.get("contains_person", False)),
    )
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    local_path = images_dir / f"{scene_id}.png"
    prompt_marker = images_dir / f"{scene_id}.prompt"
    web_path = f"/static/projects/{script_id}/images/{scene_id}.png"

    if local_path.exists() and prompt_marker.exists():
        cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
        if cached_prompt == prompt:
            logger.info("Image cache hit for Google batch scene %s", scene_id)
            return None, {
                "scene_id": scene_id,
                "image_url": web_path,
                "frame_urls": [],
                "video_url": "",
                "prompt_used": prompt,
                "visual_source_metadata": _read_source_metadata(local_path),
                "error": None,
            }, None, None

    request = GoogleBatchImageRequest(
        key=scene_id,
        prompt=prompt,
        aspect_ratio=_closest_aspect_ratio(width, height),
        reference_image_path=reference_image_path,
        style_reference_path=style_reference_path,
    )
    return request, None, local_path, prompt_marker


def generate_batch_with_google_batch(
    scenes: list[dict[str, object]],
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    style_guide: str = "",
) -> list[dict[str, object]]:
    """Generate full-project images using Google Batch for eligible independent images."""
    results_by_scene: dict[str, dict[str, object]] = {}
    standard_scenes: list[dict[str, object]] = []
    batch_requests: list[GoogleBatchImageRequest] = []
    output_paths: dict[str, tuple[Path, Path, str]] = {}

    for scene in scenes:
        scene_id = str(scene["scene_id"])
        if not _is_google_batch_eligible(scene):
            standard_scenes.append(scene)
            continue
        try:
            request, cached_result, local_path, prompt_marker = _prepare_google_batch_scene(
                scene, script_id, width, height, style_guide
            )
        except Exception as exc:
            logger.error("Google batch planning failed for scene %s: %s", scene_id, exc, exc_info=True)
            results_by_scene[scene_id] = {
                "scene_id": scene_id,
                "image_url": None,
                "prompt_used": None,
                "error": str(exc),
            }
            continue
        if cached_result is not None:
            results_by_scene[scene_id] = cached_result
            continue
        if request and local_path and prompt_marker:
            batch_requests.append(request)
            output_paths[scene_id] = (
                local_path,
                prompt_marker,
                f"/static/projects/{script_id}/images/{scene_id}.png",
            )

    logger.info(
        "Google image batch plan for script %s: %d eligible, %d standard",
        script_id, len(batch_requests), len(standard_scenes),
    )
    if batch_requests:
        batch_results = generate_images_batch(requests=batch_requests, script_id=script_id)
        for batch_result in batch_results:
            local_path, prompt_marker, web_path = output_paths[batch_result.key]
            prompt = next(request.prompt for request in batch_requests if request.key == batch_result.key)
            if batch_result.error or not batch_result.image_path:
                results_by_scene[batch_result.key] = {
                    "scene_id": batch_result.key,
                    "image_url": None,
                    "prompt_used": prompt,
                    "error": batch_result.error or "Google Batch returned no image",
                }
                continue
            metadata = _move_generated_image(batch_result.image_path, local_path, {
                "source_type": "ai_generated",
                "provider": provider_fingerprint(),
                "batch": True,
                "fallback": False,
            })
            prompt_marker.write_text(prompt, encoding="utf-8")
            results_by_scene[batch_result.key] = {
                "scene_id": batch_result.key,
                "image_url": web_path,
                "frame_urls": [],
                "video_url": "",
                "prompt_used": prompt,
                "visual_source_metadata": metadata,
                "error": None,
            }

    for result in generate_batch(
        standard_scenes,
        script_id=script_id,
        width=width,
        height=height,
        style_guide=style_guide,
    ) if standard_scenes else []:
        results_by_scene[str(result["scene_id"])] = result

    return [
        results_by_scene.get(str(scene["scene_id"]), {
            "scene_id": str(scene["scene_id"]),
            "image_url": None,
            "prompt_used": None,
            "error": "Scene was not processed",
        })
        for scene in scenes
    ]


def generate_batch(
    scenes: list[dict[str, str]],
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    style_guide: str = "",
) -> list[dict[str, str | None]]:
    """Generate images for a list of scenes with bounded concurrency.

    Each scene dict must have 'scene_id', 'visual_prompt', and canonical 'visual_mode'.
    Optionally 'frame_prompts' (list[str]) for multi-frame scenes.
    Returns list of {scene_id, image_url, prompt_used, frame_urls?, video_url?, error?}
    in the same order as the input scenes.

    Concurrency is tunable via HH_IMAGE_GEN_CONCURRENCY (default 4).
    """
    try:
        max_workers = max(1, int(os.environ.get("HH_IMAGE_GEN_CONCURRENCY", "4")))
    except ValueError:
        max_workers = 4
    # Don't spin up more workers than scenes.
    max_workers = min(max_workers, max(1, len(scenes)))

    logger.info(
        "Starting batch image generation for %s scenes (script %s, max_workers=%d)",
        len(scenes), script_id, max_workers,
    )

    results: list[dict[str, str | None] | None] = [None] * len(scenes)
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="img-gen") as pool:
        futures = {
            pool.submit(_generate_one_scene, scene, script_id, width, height, style_guide): idx
            for idx, scene in enumerate(scenes)
        }
        for fut in futures:
            idx = futures[fut]
            results[idx] = fut.result()

    final_results: list[dict[str, str | None]] = [r for r in results if r is not None]
    logger.info("Batch image generation complete: %s/%s succeeded",
                sum(1 for r in final_results if r.get("error") is None), len(scenes))
    return final_results
