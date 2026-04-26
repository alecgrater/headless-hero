"""Image generation pipeline — connects visual prompts to Google Gemini."""

import hashlib
import logging
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH, VIDEO_HEIGHT, VIDEO_WIDTH
from integrations.image_client import generate_image
from integrations.google_image_scraper import scrape_google_image_sync
from prompts import IMAGE_CHARACTER_IN_SCENE, IMAGE_COMPOSITION_GUIDE, IMAGE_VISUAL_STYLE

logger = logging.getLogger(__name__)

_STYLE_GUIDE = IMAGE_COMPOSITION_GUIDE.template
_VISUAL_STYLE = IMAGE_VISUAL_STYLE.template
_CHARACTER_PROMPT = IMAGE_CHARACTER_IN_SCENE.template

# --- Character reference helpers ---

_char_ref_cache: dict[str, str] = {}  # mtime -> hash


def _get_character_reference() -> str | None:
    """Return path to selected character reference image, or None."""
    from pipeline.character_frames import SELECTED_REFERENCE_PATH
    if SELECTED_REFERENCE_PATH.exists():
        return str(SELECTED_REFERENCE_PATH)
    return None


def _character_ref_hash() -> str:
    """Short hash of the character reference image for cache invalidation."""
    from pipeline.character_frames import SELECTED_REFERENCE_PATH
    if not SELECTED_REFERENCE_PATH.exists():
        return ""
    mtime = str(SELECTED_REFERENCE_PATH.stat().st_mtime)
    if mtime in _char_ref_cache:
        return _char_ref_cache[mtime]
    with open(SELECTED_REFERENCE_PATH, "rb") as f:
        h = hashlib.md5(f.read(4096)).hexdigest()[:8]
    _char_ref_cache.clear()
    _char_ref_cache[mtime] = h
    return h


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


def generate_scene_image(
    scene_id: str,
    visual_prompt: str,
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    force: bool = False,
    style_guide: str = "",
    contains_person: bool = False,
) -> tuple[str, str]:
    """Generate a single scene image and save it locally.

    If the image already exists and force=False, skips regeneration.
    style_guide overrides the default _STYLE_GUIDE if provided.
    When contains_person is True, injects Eli character reference + prompt.
    Returns (web-relative path, composed prompt used).
    """
    guide = style_guide if style_guide else _STYLE_GUIDE

    # Build prompt: universal style → guide → character → visual prompt
    parts: list[str] = []
    if _VISUAL_STYLE:
        parts.append(_VISUAL_STYLE)
    if guide:
        parts.append(guide)
    if contains_person and _CHARACTER_PROMPT:
        parts.append(_CHARACTER_PROMPT)
    parts.append(visual_prompt)
    prompt = "\n\n".join(parts)

    # Append character ref hash for cache invalidation
    if contains_person:
        ref_hash = _character_ref_hash()
        if ref_hash:
            prompt += f"\n[char_ref:{ref_hash}]"

    # Resolve character reference image
    reference_image_path = _get_character_reference() if contains_person else None

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
            return web_path, prompt

    logger.info("Generating image for scene %s (contains_person=%s)", scene_id, contains_person)
    try:
        tmp_path = generate_image(
            prompt, width=width, height=height,
            original_prompt=visual_prompt,
            reference_image_path=reference_image_path,
            script_id=script_id,
        )
    except Exception:
        logger.error("All image generation failed for scene %s, trying direct scraper fallback", scene_id)
        scraped = scrape_google_image_sync(
            query=visual_prompt[:120],
            output_path=str(local_path),
            width=width,
            height=height,
        )
        if scraped:
            logger.warning("Using scraped web image for scene %s", scene_id)
            prompt_marker.write_text(prompt, encoding="utf-8")
            return web_path, prompt

        logger.error("Scraper also failed for scene %s, creating placeholder", scene_id)
        _create_placeholder_image(local_path, width, height, f"Image generation failed:\n{visual_prompt[:80]}")
        prompt_marker.write_text(prompt, encoding="utf-8")
        return web_path, prompt

    # Move generated image to local storage
    shutil.move(tmp_path, str(local_path))

    # Write prompt marker for cache validation
    prompt_marker.write_text(prompt, encoding="utf-8")

    return web_path, prompt


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
) -> list[tuple[str, str]]:
    """Generate multiple frames for a scene and save them locally.

    Each frame is saved as {scene_id}_f{i}.png with a cache file {scene_id}_f{i}.prompt.
    visual_prompt is the scene's anchor description used to enforce cross-frame consistency.
    Returns list of (web_path, composed_prompt) tuples.
    """
    guide = style_guide if style_guide else _STYLE_GUIDE
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    total_frames = len(frame_prompts)
    logger.info("Generating %s frames for scene %s", total_frames, scene_id)
    results: list[tuple[str, str]] = []
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
            if contains_person and _CHARACTER_PROMPT:
                parts.append(_CHARACTER_PROMPT)
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
            if contains_person and _CHARACTER_PROMPT:
                parts.append(_CHARACTER_PROMPT)

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

        # Append character ref hash for cache invalidation
        if contains_person:
            ref_hash = _character_ref_hash()
            if ref_hash:
                prompt += f"\n[char_ref:{ref_hash}]"

        # Cache check
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
            if cached_prompt == prompt:
                results.append((web_path, prompt))
                prev_frame_path = local_path
                continue

        # Frame 0 with person: use character reference; frames 1+: use prev frame for continuity
        if use_reference:
            ref_path = str(prev_frame_path)
        elif contains_person:
            ref_path = _get_character_reference()
        else:
            ref_path = None

        tmp_path = generate_image(
            prompt,
            width=width,
            height=height,
            reference_image_path=ref_path,
            original_prompt=full_frame_description,
            script_id=script_id,
        )
        shutil.move(tmp_path, str(local_path))
        prompt_marker.write_text(prompt, encoding="utf-8")
        results.append((web_path, prompt))
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
) -> list[tuple[str, str]]:
    """Generate frames using the Visual Beat System's per-frame directives.

    Dispatches per-directive based on source and reference_previous:
      - source == "subtitle" → skip generation, return ("", prompt)
      - source == "real_photo" → scrape Google Images; fallback to AI
      - source == "ai_generated" + reference_previous → Gemini image-to-image
      - source == "ai_generated" + !reference_previous → Gemini text-to-image (independent)

    Returns list of (web_path, prompt) tuples. Empty string web_path for subtitle frames.
    """
    from models.script import FrameDirective as FrameDirectiveModel

    guide = style_guide if style_guide else _STYLE_GUIDE
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    total_frames = len(frame_directives)
    logger.info("Generating %d frames (v2) for scene %s", total_frames, scene_id)
    results: list[tuple[str, str]] = []
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
            results.append(("", directive.prompt))
            # Don't update prev_frame_path — subtitles can't be references
            continue

        # --- Real photo frames: Google Images scraper ---
        if directive.source == "real_photo" and directive.search_query:
            from integrations.google_image_scraper import scrape_google_image_sync

            # Cache check
            if not force and local_path.exists() and prompt_marker.exists():
                cached = prompt_marker.read_text(encoding="utf-8").strip()
                if cached == directive.search_query:
                    results.append((web_path, directive.search_query))
                    prev_frame_path = local_path
                    continue

            scraped = scrape_google_image_sync(
                query=directive.search_query,
                output_path=str(local_path),
                width=VIDEO_WIDTH,
                height=VIDEO_HEIGHT,
            )
            if scraped:
                prompt_marker.write_text(directive.search_query, encoding="utf-8")
                results.append((web_path, directive.search_query))
                prev_frame_path = local_path
                continue

            # Fallback to AI generation using search_query as prompt
            logger.info("Google scrape failed for %r, falling back to AI gen", directive.search_query)
            directive_prompt = directive.search_query
        else:
            directive_prompt = directive.prompt

        # --- AI-generated frames ---
        # Per-frame contains_person: check directive first, fall back to scene-level
        frame_has_person = directive.contains_person or contains_person

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
            if frame_has_person and _CHARACTER_PROMPT:
                parts.append(_CHARACTER_PROMPT)
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
            if frame_has_person and _CHARACTER_PROMPT:
                parts.append(_CHARACTER_PROMPT)
            parts.append(directive_prompt)
            prompt = "\n\n".join(parts)

        # Append character ref hash for cache invalidation
        if frame_has_person:
            ref_hash = _character_ref_hash()
            if ref_hash:
                prompt += f"\n[char_ref:{ref_hash}]"

        # Cache check
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
            if cached_prompt == prompt:
                results.append((web_path, prompt))
                prev_frame_path = local_path
                continue

        # reference_previous wins for animation continuity; otherwise use character ref
        if use_reference:
            ref_path = str(prev_frame_path)
        elif frame_has_person:
            ref_path = _get_character_reference()
        else:
            ref_path = None

        tmp_path = generate_image(
            prompt,
            width=width,
            height=height,
            reference_image_path=ref_path,
            original_prompt=directive_prompt,
            script_id=script_id,
        )
        shutil.move(tmp_path, str(local_path))
        prompt_marker.write_text(prompt, encoding="utf-8")
        results.append((web_path, prompt))
        prev_frame_path = local_path

    return results


def generate_batch(
    scenes: list[dict[str, str]],
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    style_guide: str = "",
) -> list[dict[str, str | None]]:
    """Generate images for a list of scenes sequentially.

    Each scene dict must have 'scene_id' and 'visual_prompt'.
    Optionally 'frame_prompts' (list[str]) for multi-frame scenes.
    Dispatches based on scene 'media_source': ai (default), stock_photo, gameplay_video.
    Returns list of {scene_id, image_url, prompt_used, frame_urls?, video_url?, error?}.
    """
    results: list[dict[str, str]] | None = []
    logger.info("Starting batch image generation for %s scenes (script %s)", len(scenes), script_id)
    for scene in scenes:
        try:
            media_source = scene.get("media_source", "ai")

            # --- Stock photo dispatch ---
            if media_source == "stock_photo":
                from pipeline.stock_photo import generate_stock_photo
                search_query = scene.get("visual_prompt", "")
                image_url = generate_stock_photo(script_id, scene["scene_id"], search_query)
                results.append({
                    "scene_id": scene["scene_id"],
                    "image_url": image_url,
                    "prompt_used": search_query,
                    "error": None,
                })
                continue

            # --- Gameplay video dispatch ---
            if media_source == "gameplay_video":
                from pipeline.gameplay import generate_gameplay_clip
                game_name = scene.get("gameplay_game_name", "") or scene.get("gameplay_game_override", "")
                duration = scene.get("audio_duration_seconds", 8.0)
                if not game_name:
                    raise RuntimeError("Gameplay scene missing game_name")
                video_url = generate_gameplay_clip(script_id, scene["scene_id"], game_name, float(duration))
                results.append({
                    "scene_id": scene["scene_id"],
                    "image_url": None,
                    "video_url": video_url,
                    "prompt_used": f"gameplay:{game_name}",
                    "error": None,
                })
                continue

            # --- User upload: skip generation ---
            if media_source == "user_upload":
                results.append({
                    "scene_id": scene["scene_id"],
                    "image_url": scene.get("upload_url") or scene.get("image_url"),
                    "prompt_used": None,
                    "error": None,
                })
                continue

            # --- AI-generated (default) ---
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
                frame_urls = [url for url, _ in frame_results]
                results.append({
                    "scene_id": scene["scene_id"],
                    "image_url": next((u for u in frame_urls if u), None),
                    "frame_urls": frame_urls,
                    "prompt_used": frame_results[0][1] if frame_results else None,
                    "error": None,
                })
                continue

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
                frame_urls = [url for url, _ in frame_results]
                results.append({
                    "scene_id": scene["scene_id"],
                    "image_url": frame_urls[0] if frame_urls else None,
                    "frame_urls": frame_urls,
                    "prompt_used": frame_results[0][1] if frame_results else None,
                    "error": None,
                })
                continue

            # Single-image path
            image_url, prompt_used = generate_scene_image(
                scene_id=scene["scene_id"],
                visual_prompt=scene["visual_prompt"],
                script_id=script_id,
                width=width,
                height=height,
                style_guide=style_guide,
                contains_person=scene_contains_person,
            )
            results.append({
                "scene_id": scene["scene_id"],
                "image_url": image_url,
                "prompt_used": prompt_used,
                "error": None,
            })
        except Exception as exc:
            logger.error("Image generation failed for scene %s: %s", scene["scene_id"], exc, exc_info=True)
            results.append({
                "scene_id": scene["scene_id"],
                "image_url": None,
                "prompt_used": None,
                "error": str(exc),
            })
    logger.info("Batch image generation complete: %s/%s succeeded",
                sum(1 for r in results if r.get("error") is None), len(scenes))
    return results
