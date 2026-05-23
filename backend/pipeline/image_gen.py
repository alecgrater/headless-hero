"""Image generation pipeline — connects visual prompts to Google Gemini."""

import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH, VIDEO_HEIGHT, VIDEO_WIDTH
from integrations.image_client import generate_image
from models.script import MainCharacter
from prompts import IMAGE_CHARACTER_IN_SCENE, IMAGE_COMPOSITION_GUIDE, IMAGE_VISUAL_STYLE

logger = logging.getLogger(__name__)

_STYLE_GUIDE = IMAGE_COMPOSITION_GUIDE.template
_VISUAL_STYLE = IMAGE_VISUAL_STYLE.template
_CHARACTER_PROMPT = IMAGE_CHARACTER_IN_SCENE.template

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

    with Session(engine) as session:
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
) -> list[dict]:
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    processed_layers: list[dict] = []
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
                continue

        logger.info("[PANEL_GEN] generating panel scene=%s layer=%s", scene_id, layer_id)
        tmp_path = generate_image(
            composed_prompt,
            width=width,
            height=height,
            reference_image_path=reference_image_path,
            original_prompt=prompt,
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
        logger.info("[PANEL_GEN] complete scene=%s layer=%s", scene_id, layer_id)

    return processed_layers


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
            if character_text:
                parts.append(character_text)
            parts.append(
                f"This is frame {i + 1} of {total_frames} in an animation sequence. "
                f"Using the input image as reference, change ONLY the following: "
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

        if style_reference_path:
            try:
                mtime = int(Path(style_reference_path).stat().st_mtime)
                prompt += f"\n[style_ref:{style_reference_path}:{mtime}]"
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
            style_reference_path=style_reference_path,
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
      - source == "real_photo" → scrape Google Images; fallback to AI
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

        # --- Real photo frames: Google Images scraper ---
        if directive.source == "real_photo" and directive.search_query:
            from integrations.google_image_scraper import scrape_google_image_sync

            # Cache check
            if not force and local_path.exists() and prompt_marker.exists():
                cached = prompt_marker.read_text(encoding="utf-8").strip()
                if cached == directive.search_query:
                    results.append((web_path, directive.search_query, _read_source_metadata(local_path)))
                    prev_frame_path = local_path
                    continue

            scraped = scrape_google_image_sync(
                query=directive.search_query,
                output_path=str(local_path),
                width=VIDEO_WIDTH,
                height=VIDEO_HEIGHT,
            )
            if scraped:
                metadata = {
                    "source_type": "scraped_web_image",
                    "provider": "google_images_scraper",
                    "query": directive.search_query,
                    "reason": "Frame directive requested a real photo",
                    "license_note": "Scraped web image; verify usage rights before publishing.",
                    "fallback": False,
                }
                _write_source_metadata(local_path, metadata)
                prompt_marker.write_text(directive.search_query, encoding="utf-8")
                results.append((web_path, directive.search_query, metadata))
                prev_frame_path = local_path
                continue

            # Fallback to AI generation using search_query as prompt
            logger.info("Google scrape failed for %r, falling back to AI gen", directive.search_query)
            directive_prompt = directive.search_query
        # --- Stock photo frames: Pexels search ---
        elif directive.source == "stock_photo":
            from integrations.pexels_client import search_and_download

            query = directive.search_query or directive.prompt

            # Cache check
            if not force and local_path.exists() and prompt_marker.exists():
                cached = prompt_marker.read_text(encoding="utf-8").strip()
                if cached == query:
                    results.append((web_path, query, _read_source_metadata(local_path)))
                    prev_frame_path = local_path
                    continue

            try:
                tmp = search_and_download(query)
            except Exception:
                logger.error("Pexels search failed for frame %d query %r", i, query, exc_info=True)
                tmp = None

            if tmp:
                shutil.move(tmp, str(local_path))
                metadata = {
                    "source_type": "stock_photo",
                    "provider": "pexels",
                    "query": query,
                    "fallback": False,
                }
                _write_source_metadata(local_path, metadata)
                prompt_marker.write_text(query, encoding="utf-8")
                results.append((web_path, query, metadata))
                prev_frame_path = local_path
                continue

            # Fallback to AI generation using query as prompt
            logger.info("No stock photo for frame %d query %r, falling back to AI gen", i, query)
            directive_prompt = query
        else:
            directive_prompt = directive.prompt

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

        if use_reference:
            # Kontext-optimized: edit instruction referencing the input image
            parts: list[str] = []
            if _VISUAL_STYLE:
                parts.append(_VISUAL_STYLE)
            if character_text:
                parts.append(character_text)
            parts.append(
                f"This is frame {i + 1} of {total_frames} in an animation sequence. "
                f"Using the input image as reference, change ONLY the following: "
                f"{directive_prompt}\n"
                f"Maintain identical style, background, composition, character design, "
                f"and color palette. Only the described action should change."
            )
            prompt = "\n\n".join(parts)
        else:
            # Independent text-to-image (no reference chaining)
            parts: list[str] = []
            if _VISUAL_STYLE:
                parts.append(_VISUAL_STYLE)
            if guide and guide != directive_prompt:
                parts.append(f"Scene context: {guide}\n\nThis specific frame:")
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

        if style_reference_path:
            try:
                mtime = int(Path(style_reference_path).stat().st_mtime)
                prompt += f"\n[style_ref:{style_reference_path}:{mtime}]"
            except OSError:
                pass

        # Cache check
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
            if cached_prompt == prompt:
                results.append((web_path, prompt, _read_source_metadata(local_path)))
                prev_frame_path = local_path
                continue

        # reference_previous wins for animation continuity; otherwise use resolved character ref
        if use_reference:
            ref_path = str(prev_frame_path)
        else:
            ref_path = reference_image_path

        tmp_path = generate_image(
            prompt,
            width=width,
            height=height,
            reference_image_path=ref_path,
            original_prompt=directive_prompt,
            style_reference_path=style_reference_path,
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
        treatment = scene.get("visual_treatment", "full_frame")
        layers = scene.get("visual_layers", []) or []
        if treatment not in {"popup_sequence", "flipflop"} or not layers:
            return result
        layer_dicts = [
            layer.model_dump() if hasattr(layer, "model_dump") else dict(layer)
            for layer in layers
            if isinstance(layer, dict) or hasattr(layer, "model_dump")
        ]
        if not layer_dicts:
            return result
        result["visual_layers"] = generate_visual_layer_panels(
            scene["scene_id"],
            layer_dicts,
            script_id,
            width=width,
            height=height,
            contains_person=bool(scene.get("contains_person", False)),
        )
        return result

    try:
        media_source = scene.get("media_source", "ai")

        # --- Stock photo dispatch ---
        if media_source == "stock_photo":
            logger.info("[PEXELS] scene %s — query: %s", scene["scene_id"], scene.get("visual_prompt", "")[:80])
            frame_directives = scene.get("frame_directives", [])
            if frame_directives:
                # Multi-frame stock photo — use v2 pipeline
                frame_results = generate_scene_frames_v2(
                    scene_id=scene["scene_id"],
                    frame_directives=frame_directives,
                    script_id=script_id,
                    visual_prompt=scene.get("visual_prompt", ""),
                    width=width,
                    height=height,
                    style_guide=style_guide,
                    contains_person=scene.get("contains_person", False),
                )
                frame_urls = [url for url, _, _ in frame_results]
                source_metadata = next((metadata for url, _, metadata in frame_results if url and metadata), None)
                return with_visual_layers({
                    "scene_id": scene["scene_id"],
                    "image_url": next((u for u in frame_urls if u), None),
                    "frame_urls": frame_urls,
                    "prompt_used": frame_results[0][1] if frame_results else None,
                    "visual_source_metadata": source_metadata,
                    "error": None,
                })
            # Single stock photo (no frame_directives)
            from pipeline.stock_photo import generate_stock_photo
            search_query = scene.get("visual_prompt", "")
            image_url = generate_stock_photo(script_id, scene["scene_id"], search_query)
            return with_visual_layers({
                "scene_id": scene["scene_id"],
                "image_url": image_url,
                "prompt_used": search_query,
                "visual_source_metadata": None,
                "error": None,
            })

        # --- Gameplay video dispatch ---
        if media_source == "gameplay_video":
            from pipeline.gameplay import generate_gameplay_clip
            game_name = scene.get("gameplay_game_name", "") or scene.get("gameplay_game_override", "")
            duration = scene.get("audio_duration_seconds", 8.0)
            if not game_name:
                raise RuntimeError("Gameplay scene missing game_name")
            logger.info("[TWITCH] scene %s — game: %s, duration: %.1fs", scene["scene_id"], game_name, float(duration))
            video_url = generate_gameplay_clip(script_id, scene["scene_id"], game_name, float(duration))
            return with_visual_layers({
                "scene_id": scene["scene_id"],
                "image_url": None,
                "video_url": video_url,
                "prompt_used": f"gameplay:{game_name}",
                "visual_source_metadata": None,
                "error": None,
            })

        # --- AI video dispatch ---
        if media_source == "ai_video":
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
                "video_url": video_url,
                "prompt_used": prompt_used,
                "visual_source_metadata": source_metadata,
                "error": None,
            })

        # --- User upload: skip generation ---
        if media_source == "user_upload":
            return with_visual_layers({
                "scene_id": scene["scene_id"],
                "image_url": scene.get("upload_url") or scene.get("image_url"),
                "prompt_used": None,
                "visual_source_metadata": None,
                "error": None,
            })

        # --- AI-generated (default) ---
        logger.info("[GEMINI] scene %s — prompt: %s", scene["scene_id"], scene.get("visual_prompt", "")[:80])
        frame_directives = scene.get("frame_directives", [])
        frame_prompts = scene.get("frame_prompts", [])
        scene_contains_person = scene.get("contains_person", False)

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


def generate_batch(
    scenes: list[dict[str, str]],
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    style_guide: str = "",
) -> list[dict[str, str | None]]:
    """Generate images for a list of scenes with bounded concurrency.

    Each scene dict must have 'scene_id' and 'visual_prompt'.
    Optionally 'frame_prompts' (list[str]) for multi-frame scenes.
    Dispatches based on scene 'media_source': ai (default), ai_video, stock_photo, gameplay_video.
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
