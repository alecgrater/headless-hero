"""Image generation pipeline — connects visual prompts to Google Gemini."""

import json
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH, VIDEO_HEIGHT, VIDEO_WIDTH
from integrations.image_client import generate_image
from models.script import MainCharacter
from pipeline.asset_vault import VaultKind, save_vault_image
from pipeline.character_assets import process_character_asset_bundle
from pipeline.cutout_chroma import key_out_background, save_keyed_trimmed_cutout as save_shared_keyed_trimmed_cutout
from pipeline.fallback_observability import record_fallback
from pipeline.render_jobs import UserFacingJobError
from pipeline.visual_treatments import flipflop_cutout_prompt
from prompts import IMAGE_CHARACTER_IN_SCENE, IMAGE_COMPOSITION_GUIDE, IMAGE_VISUAL_STYLE

logger = logging.getLogger(__name__)

FLIPFLOP_CUTOUT_REGISTRATION_VERSION = "alpha-mask-registration-v4"
FLIPFLOP_SCALE_CORRECTION_MIN = 0.92
FLIPFLOP_SCALE_CORRECTION_MAX = 1.08
FLIPFLOP_ASPECT_RATIO_TOLERANCE = 0.12
FLIPFLOP_FINAL_SIZE_TOLERANCE_PX = 2
_STYLE_GUIDE = IMAGE_COMPOSITION_GUIDE.template
_VISUAL_STYLE = IMAGE_VISUAL_STYLE.template
_CHARACTER_PROMPT = IMAGE_CHARACTER_IN_SCENE.template


class FlipflopRegistrationError(UserFacingJobError):
    """Raised when generated flipflop states cannot be safely aligned."""


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
        prompt = _flipflop_micro_animation_prompt(prompt, index) if visual_treatment == "flipflop" else prompt
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
        if visual_treatment == "flipflop" and previous_panel_path is not None:
            reference_image_path = str(previous_panel_path)
            try:
                mtime = int(previous_panel_path.stat().st_mtime)
                composed_prompt += f"\n[flipflop_ref:{previous_panel_path}:{mtime}]"
            except OSError:
                pass

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
                "provider": os.environ.get("IMAGE_PROVIDER", "google"),
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


def _flipflop_micro_animation_prompt(prompt: str, index: int) -> str:
    base = prompt.strip()
    if index <= 0:
        return "\n".join(
            [
                "Flip-flop micro-animation State A.",
                "Create the first frame of a two-frame animation from this scene.",
                "Use the same character, same camera angle, same framing, same background, and same composition that State B should preserve.",
                "Show the character in the initial pose: controlled, readable, and just before the expression or gesture changes.",
                "Keep the pose natural and not exaggerated.",
                "",
                "Base scene prompt:",
                base,
            ]
        ).strip()
    return "\n".join(
        [
            "Flip-flop micro-animation State B.",
            "Create the second frame of the same two-frame animation.",
            "Use the reference image as the source of truth for the same exact composition, character identity, camera angle, framing, background, lighting, and style.",
            "Only make a small pose/expression progression: slightly change the mouth, eyes, head angle, or hand gesture so it feels like the next moment in the same action.",
            "Do not change the outfit, setting, props, camera angle, or overall layout.",
            "",
            "Base scene prompt:",
            base,
        ]
    ).strip()


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


def _flipflop_state_sheet_fingerprint(prompt: str) -> str:
    return json.dumps(
        {
            "prompt": prompt,
            "registration_algorithm_version": FLIPFLOP_CUTOUT_REGISTRATION_VERSION,
        },
        sort_keys=True,
    )


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


def generate_flipflop_cutouts(
    *,
    scene_id: str,
    layers: list[dict],
    script_id: str,
    scene_prompt: str,
    scene_narration: str = "",
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
    contains_person: bool = False,
) -> list[dict]:
    """Generate transparent state cutouts for renderer-owned flip-flop scenes."""

    layers = _normalize_flipflop_generation_layers(
        scene_id=scene_id,
        layers=layers,
        scene_prompt=scene_prompt,
        scene_narration=scene_narration,
    )
    output_dir = DATA_DIR / "projects" / script_id / "flipflop_cutouts" / scene_id
    output_dir.mkdir(parents=True, exist_ok=True)
    processed_layers: list[dict] = []
    cutout_entries: list[dict] = []
    state_entries: list[dict] = []
    image_index = 0
    for layer in layers:
        if not isinstance(layer, dict):
            processed_layers.append(layer)
            continue
        if layer.get("type", "image") != "image":
            processed_layers.append(layer)
            continue

        next_layer = dict(layer)
        layer_id = str(next_layer.get("id") or f"{scene_id}_state_{image_index + 1}")
        next_layer["id"] = layer_id
        prompt = str(next_layer.get("prompt") or scene_prompt or "").strip()
        if not prompt:
            logger.info("[FLIPFLOP_CUTOUT] skipped empty prompt scene=%s layer=%s", scene_id, layer_id)
            processed_layers.append(next_layer)
            continue

        image_index += 1
        filename = f"state_{image_index:02d}_{_slug(layer_id)}.png"
        local_path = output_dir / filename
        raw_path = output_dir / f"raw_{filename}"
        prompt_marker = output_dir / f"{filename}.prompt"
        web_path = f"/static/projects/{script_id}/flipflop_cutouts/{scene_id}/{filename}"
        next_layer["asset_kind"] = "cutout"
        next_layer["image_url"] = web_path
        processed_layers.append(next_layer)
        state_entries.append(
            {
                "raw_path": raw_path,
                "local_path": local_path,
                "prompt_marker": prompt_marker,
                "prompt": prompt,
                "metadata": {
                    "source_type": "flipflop_cutout",
                    "provider": os.environ.get("IMAGE_PROVIDER", "google"),
                    "fallback": False,
                },
                "layer": next_layer,
                "contains_person": bool(next_layer.get("contains_person", contains_person)),
            }
        )

    cutout_entries.extend(
        _generate_flipflop_state_sheet(
            scene_id=scene_id,
            state_entries=state_entries,
            scene_prompt=scene_prompt,
            script_id=script_id,
            output_dir=output_dir,
            width=width,
            height=height,
            force=force,
        )
    )
    _recrop_flipflop_cutouts_to_shared_bbox(cutout_entries, script_id=script_id, scene_id=scene_id)
    return processed_layers


def _generate_flipflop_state_sheet(
    *,
    scene_id: str,
    state_entries: list[dict],
    scene_prompt: str,
    script_id: str,
    output_dir: Path,
    width: int,
    height: int,
    force: bool,
) -> list[dict]:
    if len(state_entries) < 2:
        return []

    states = state_entries[:2]
    source_prompt = _compose_flipflop_state_sheet_source_prompt(
        state_a_prompt=str(states[0]["prompt"]),
        state_b_prompt=str(states[1]["prompt"]),
        scene_prompt=scene_prompt,
    )
    composed_prompt, reference_image_path, style_reference_path = _compose_cutout_prompt_context(
        visual_prompt=source_prompt,
        script_id=script_id,
        contains_person=any(bool(entry.get("contains_person")) for entry in states),
    )
    prompt_marker = output_dir / "state_sheet.prompt"
    prompt_fingerprint = _flipflop_state_sheet_fingerprint(composed_prompt)
    sheet_path = output_dir / "state_sheet.png"
    cache_valid = (
        not force
        and prompt_marker.exists()
        and prompt_marker.read_text(encoding="utf-8") == prompt_fingerprint
        and sheet_path.exists()
        and all(Path(entry["local_path"]).exists() and Path(entry["raw_path"]).exists() for entry in states)
        and all(_flipflop_registration_cache_valid(Path(entry["local_path"])) for entry in states)
    )

    if cache_valid:
        logger.info("[FLIPFLOP_CUTOUT] state sheet cache hit scene=%s", scene_id)
        for entry in states:
            source_metadata = _read_source_metadata(Path(entry["local_path"])) or entry["metadata"]
            entry["metadata"] = source_metadata
            entry["layer"]["visual_source_metadata"] = source_metadata
        return states

    logger.info("[FLIPFLOP_CUTOUT] generating shared state sheet scene=%s", scene_id)
    generated_path = Path(
        generate_image(
            composed_prompt,
            width=width,
            height=height,
            reference_image_path=reference_image_path,
            style_reference_path=style_reference_path,
            original_prompt=source_prompt,
            script_id=script_id,
        )
    )
    if generated_path.resolve() != sheet_path.resolve():
        shutil.copyfile(generated_path, sheet_path)

    with Image.open(sheet_path) as sheet:
        source = sheet.convert("RGBA")
        cell_width = source.width // 2
        crops = [
            source.crop((0, 0, cell_width, source.height)),
            source.crop((cell_width, 0, source.width, source.height)),
        ]
        for entry, crop in zip(states, crops, strict=True):
            raw_path = Path(entry["raw_path"])
            local_path = Path(entry["local_path"])
            crop.save(raw_path)
            trim_box = save_shared_keyed_trimmed_cutout(crop, local_path)
            source_metadata = {**entry["metadata"], "trim_box": trim_box}
            _write_source_metadata(local_path, source_metadata)
            entry["metadata"] = source_metadata
            entry["layer"]["visual_source_metadata"] = source_metadata
            Path(entry["prompt_marker"]).write_text(prompt_fingerprint, encoding="utf-8")
            save_vault_image(kind="item", label=f"Flip-flop {entry['layer']['id']}", source_path=local_path)

    prompt_marker.write_text(prompt_fingerprint, encoding="utf-8")
    return states


def _flipflop_registration_cache_valid(path: Path) -> bool:
    metadata = _read_source_metadata(path)
    return bool(
        metadata
        and metadata.get("registration_algorithm_version") == FLIPFLOP_CUTOUT_REGISTRATION_VERSION
        and isinstance(metadata.get("trim_box"), list)
        and isinstance(metadata.get("virtual_trim_box"), list)
        and isinstance(metadata.get("registration_box"), list)
        and isinstance(metadata.get("scale_factor"), int | float)
    )


def _normalize_flipflop_generation_layers(
    *,
    scene_id: str,
    layers: list[dict],
    scene_prompt: str,
    scene_narration: str,
) -> list[dict]:
    image_layers = [
        dict(layer)
        for layer in layers
        if isinstance(layer, dict) and layer.get("type", "image") == "image"
    ]
    other_layers = [
        layer
        for layer in layers
        if not (isinstance(layer, dict) and layer.get("type", "image") == "image")
    ]
    state_layers = [
        layer
        for layer in image_layers
        if layer.get("asset_kind") != "full_frame"
        and layer.get("asset_kind") != "panel"
        and not str(layer.get("id") or "").endswith("_background")
    ]
    normalized: list[dict] = []

    for index, layer in enumerate(state_layers[:2]):
        state_layer = dict(layer)
        state_layer["asset_kind"] = "cutout"
        state_layer["placement"] = state_layer.get("placement") or "center"
        state_layer["enter_at_seconds"] = state_layer.get("enter_at_seconds") or 0.0
        state_layer["animation"] = state_layer.get("animation") or "none"
        normalized.append(state_layer)

    while len([layer for layer in normalized if layer.get("asset_kind") == "cutout"]) < 2:
        state_index = len([layer for layer in normalized if layer.get("asset_kind") == "cutout"])
        focus = "state A" if state_index == 0 else "state B"
        normalized.append(
            {
                "id": f"{scene_id}_state_{'a' if state_index == 0 else 'b'}",
                "type": "image",
                "asset_kind": "cutout",
                "prompt": flipflop_cutout_prompt(scene_prompt, scene_narration, focus),
                "placement": "center",
                "enter_at_seconds": 0.0,
                "animation": "none",
            }
        )

    return normalized + other_layers


def _recrop_flipflop_cutouts_to_shared_bbox(
    entries: list[dict],
    *,
    script_id: str | None = None,
    scene_id: str | None = None,
    padding: int = 24,
    tolerance: int = 70,
) -> None:
    if len(entries) < 2:
        return

    keyed_entries = []
    for entry in entries:
        raw_path = Path(entry["raw_path"])
        if not raw_path.exists():
            return
        with Image.open(raw_path) as source:
            keyed = key_out_background(source.convert("RGBA"), tolerance=tolerance)
        bbox = keyed.getbbox()
        if bbox is None:
            return
        keyed_entries.append((entry, keyed, list(bbox)))

    if not keyed_entries:
        return

    target_box = keyed_entries[0][2]
    target_width = max(1, target_box[2] - target_box[0])
    target_height = max(1, target_box[3] - target_box[1])
    target_aspect_ratio = target_width / target_height
    prepared_subjects: list[tuple[dict, Image.Image, list[int], float, tuple[float, float], tuple[int, int]]] = []
    shifted_boxes: list[list[int]] = []

    for entry, keyed, bbox in keyed_entries:
        subject_width = max(1, bbox[2] - bbox[0])
        subject_height = max(1, bbox[3] - bbox[1])
        scale_factor = min(target_width / subject_width, target_height / subject_height)
        subject = keyed.crop(tuple(bbox))
        subject_aspect_ratio = subject_width / subject_height
        scale_is_safe = FLIPFLOP_SCALE_CORRECTION_MIN <= scale_factor <= FLIPFLOP_SCALE_CORRECTION_MAX
        aspect_is_safe = (
            abs(subject_aspect_ratio - target_aspect_ratio) / max(target_aspect_ratio, 0.001)
            <= FLIPFLOP_ASPECT_RATIO_TOLERANCE
        )
        if prepared_subjects and (not scale_is_safe or not aspect_is_safe):
            raise FlipflopRegistrationError(
                "Flipflop State A/B cutouts could not be aligned: generated states differ too much in scale or aspect ratio. Regenerate the scene or use full_frame."
            )
        if scale_factor != 1.0:
            scaled_size = (
                max(1, round(subject.width * scale_factor)),
                max(1, round(subject.height * scale_factor)),
            )
            subject = subject.resize(scaled_size, Image.Resampling.LANCZOS)
        final_bbox = subject.getbbox()
        final_width = max(0, final_bbox[2] - final_bbox[0]) if final_bbox else 0
        final_height = max(0, final_bbox[3] - final_bbox[1]) if final_bbox else 0
        final_size_is_safe = (
            abs(final_width - target_width) <= FLIPFLOP_FINAL_SIZE_TOLERANCE_PX
            and abs(final_height - target_height) <= FLIPFLOP_FINAL_SIZE_TOLERANCE_PX
        )
        if prepared_subjects and not final_size_is_safe:
            raise FlipflopRegistrationError(
                "Flipflop State A/B cutouts could not be aligned: final registered state sizes still differ. Regenerate the scene or use full_frame."
            )
        anchor = _alpha_anchor(subject)
        if not prepared_subjects:
            target_anchor = anchor
        shift = _bounded_alpha_anchor_shift(target_anchor, anchor, max_shift=padding)
        shifted_box = [
            shift[0],
            shift[1],
            subject.width + shift[0],
            subject.height + shift[1],
        ]
        prepared_subjects.append((entry, subject, bbox, scale_factor, anchor, shift))
        shifted_boxes.append(shifted_box)

    virtual_trim_box = [
        min(box[0] for box in shifted_boxes) - padding,
        min(box[1] for box in shifted_boxes) - padding,
        max(box[2] for box in shifted_boxes) + padding,
        max(box[3] for box in shifted_boxes) + padding,
    ]

    for entry, subject, bbox, scale_factor, anchor, shift in prepared_subjects:
        local_path = Path(entry["local_path"])
        registered = _translated_alpha_crop(subject, shift=shift, crop_box=virtual_trim_box)
        registered.save(local_path)
        source_metadata = {
            **entry["metadata"],
            "trim_box": [0, 0, registered.width, registered.height],
            "virtual_trim_box": virtual_trim_box,
            "registration_box": bbox,
            "scaled_registration_box": [0, 0, subject.width, subject.height],
            "scale_factor": round(scale_factor, 4),
            "registration_algorithm_version": FLIPFLOP_CUTOUT_REGISTRATION_VERSION,
            "alpha_anchor": [round(anchor[0], 2), round(anchor[1], 2)],
            "alpha_anchor_shift": [shift[0], shift[1]],
        }
        _write_source_metadata(local_path, source_metadata)
        entry["layer"]["visual_source_metadata"] = source_metadata


def _translated_alpha_crop(
    image: Image.Image,
    *,
    shift: tuple[int, int],
    crop_box: list[int],
) -> Image.Image:
    left, top, right, bottom = crop_box
    output = Image.new("RGBA", (max(1, right - left), max(1, bottom - top)), (0, 0, 0, 0))
    source_left = max(0, left - shift[0])
    source_top = max(0, top - shift[1])
    source_right = min(image.width, right - shift[0])
    source_bottom = min(image.height, bottom - shift[1])
    if source_left >= source_right or source_top >= source_bottom:
        return output

    crop = image.crop((source_left, source_top, source_right, source_bottom))
    output.alpha_composite(
        crop,
        dest=(source_left + shift[0] - left, source_top + shift[1] - top),
    )
    return output


def _alpha_anchor(image: Image.Image) -> tuple[float, float]:
    alpha = image.convert("RGBA").getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return (image.width / 2, image.height / 2)
    left, top, right, bottom = bbox
    upper_bottom = top + max(1, round((bottom - top) * 0.62))
    total = 0
    weighted_x = 0
    weighted_y = 0
    pixels = alpha.load()
    for y in range(top, upper_bottom):
        for x in range(left, right):
            value = pixels[x, y]
            if value <= 0:
                continue
            total += value
            weighted_x += x * value
            weighted_y += y * value
    if total == 0:
        return ((left + right) / 2, (top + bottom) / 2)
    return (weighted_x / total, weighted_y / total)


def _bounded_alpha_anchor_shift(
    target_anchor: tuple[float, float],
    anchor: tuple[float, float],
    *,
    max_shift: int,
) -> tuple[int, int]:
    raw_x = round(target_anchor[0] - anchor[0])
    raw_y = round(target_anchor[1] - anchor[1])
    return (
        max(-max_shift, min(max_shift, raw_x)),
        max(-max_shift, min(max_shift, raw_y)),
    )


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


def _compose_flipflop_cutout_source_prompt(layer_prompt: str, scene_prompt: str) -> str:
    return "\n".join(
        [
            "Generate one isolated flip-flop animation state cutout.",
            "Use a solid flat chroma key background across the entire image.",
            "Use bright green (#00FF00) unless the subject contains green, then use bright magenta (#FF00FF).",
            "Keep exactly one clear closed-silhouette subject suitable for automatic chroma-key trimming.",
            "For flip-flop pairs, preserve an identical pixel footprint, subject bounding box, camera distance, and canvas position across every state.",
            "No zoom, no tighter crop, no wider crop, no resizing, no rotation, and no subject translation between states.",
            "No full background scene, scenery, split-screen, decorative border, picture frame, mat, white margin, inset panel, UI chrome, caption box, poster edge, speech bubble, labels, or text.",
            "",
            "Layer direction:",
            layer_prompt.strip(),
            "",
            "Scene context for identity and style only:",
            scene_prompt.strip(),
        ]
    ).strip()


def _compose_flipflop_state_sheet_source_prompt(*, state_a_prompt: str, state_b_prompt: str, scene_prompt: str) -> str:
    return "\n".join(
        [
            "Generate a two-cell contact sheet of isolated flip-flop animation state cutouts.",
            "The output image must contain exactly two equal-width vertical cells: LEFT CELL is State A, RIGHT CELL is State B.",
            "Both cells must use the same solid flat chroma key background across the entire cell.",
            "Use bright green (#00FF00) unless the subject contains green, then use bright magenta (#FF00FF).",
            "Each cell contains exactly one clear closed-silhouette human or character subject suitable for automatic chroma-key trimming.",
            "Make State A and State B look like traced animation cels of the same drawing.",
            "Preserve identical identity, body proportions, camera distance, crop, canvas position, identical pixel footprint, and subject bounding box in both cells.",
            "No zoom, no tighter crop, no wider crop, no resizing, no rotation, and no subject translation between cells.",
            "The ONLY visual difference between the two cells is the named flip-flop micro-action described in the state directions.",
            "No full background scene, scenery, props, split-screen board, decorative border, picture frame, mat, white margin, inset panel, UI chrome, caption box, poster edge, speech bubble, labels, or text.",
            "",
            "LEFT CELL / State A direction:",
            state_a_prompt.strip(),
            "",
            "RIGHT CELL / State B direction:",
            state_b_prompt.strip(),
            "",
            "Scene context for identity and style only:",
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
                    from_value=os.environ.get("IMAGE_PROVIDER", "google"),
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
            from_value=os.environ.get("IMAGE_PROVIDER", "google"),
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
        "provider": os.environ.get("IMAGE_PROVIDER", "google"),
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
            "provider": os.environ.get("IMAGE_PROVIDER", "google"),
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
            "provider": os.environ.get("IMAGE_PROVIDER", "google"),
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
        treatment = visual_mode if visual_mode in {"popup_sequence", "flipflop", "comparison_board", "stat_card"} else "full_frame"
        layers = scene.get("visual_layers", []) or []
        if treatment not in {"popup_sequence", "flipflop", "comparison_board", "stat_card"}:
            return result
        if not layers and treatment != "flipflop":
            return result
        layer_dicts = [
            layer.model_dump() if hasattr(layer, "model_dump") else dict(layer)
            for layer in layers
            if isinstance(layer, dict) or hasattr(layer, "model_dump")
        ]
        if not layer_dicts and treatment != "flipflop":
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
        elif treatment == "flipflop":
            result["visual_layers"] = generate_flipflop_cutouts(
                scene_id=scene["scene_id"],
                layers=layer_dicts,
                script_id=script_id,
                scene_prompt=str(scene.get("visual_prompt") or ""),
                scene_narration=str(scene.get("narration") or ""),
                width=width,
                height=height,
                contains_person=bool(scene.get("contains_person", False)),
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
        treatment = visual_mode if visual_mode in {"popup_sequence", "flipflop", "comparison_board", "stat_card"} else "full_frame"

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
