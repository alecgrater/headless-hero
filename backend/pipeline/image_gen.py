"""Image generation pipeline — connects visual prompts to Google Gemini."""

import logging
import shutil
from pathlib import Path

from config import DATA_DIR
from integrations.image_client import generate_image

logger = logging.getLogger(__name__)

# data/ directory lives two levels above backend/pipeline/

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "image_gen_guide.md"
_STYLE_GUIDE = _GUIDE_PATH.read_text() if _GUIDE_PATH.exists() else ""


def generate_scene_image(
    scene_id: str,
    visual_prompt: str,
    script_id: str,
    width: int = 1344,
    height: int = 768,
    force: bool = False,
    variant: str = "a",
    style_guide: str = "",
    seed: int | None = None,
    style_string: str = "",
) -> tuple[str, str]:
    """Generate a single scene image and save it locally.

    If the image already exists and force=False, skips regeneration.
    variant="a" uses {scene_id}.png, variant="b" uses {scene_id}_b.png.
    style_guide overrides the default _STYLE_GUIDE if provided.
    Returns (web-relative path, composed prompt used).
    """
    guide = style_guide if style_guide else _STYLE_GUIDE

    # Build prompt: style_string (verbatim) → guide → visual prompt
    parts: list[str] = []
    if style_string:
        parts.append(style_string)
    if guide:
        parts.append(guide)
    parts.append(visual_prompt)
    prompt = "\n\n".join(parts)

    # Check cache: if image exists and we have a matching prompt marker, skip regen
    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    suffix = "_b" if variant == "b" else ""
    filename = f"{scene_id}{suffix}.png"
    local_path = images_dir / filename
    prompt_marker = images_dir / f"{scene_id}{suffix}.prompt"
    web_path = f"/static/projects/{script_id}/images/{filename}"

    if not force and local_path.exists() and prompt_marker.exists():
        cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
        if cached_prompt == prompt:
            logger.info("Image cache hit for scene %s (variant=%s)", scene_id, variant)
            return web_path, prompt

    logger.info("Generating image for scene %s (variant=%s)", scene_id, variant)
    tmp_path = generate_image(prompt, width=width, height=height, seed=seed)

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
    width: int = 1344,
    height: int = 768,
    force: bool = False,
    style_guide: str = "",
    seed: int | None = None,
    style_string: str = "",
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
            if style_string:
                parts.append(style_string)
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
            if style_string:
                parts.append(style_string)
            if guide:
                parts.append(guide)

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

        # Cache check
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
            if cached_prompt == prompt:
                results.append((web_path, prompt))
                prev_frame_path = local_path
                continue

        tmp_path = generate_image(
            prompt,
            width=width,
            height=height,
            seed=seed,
            reference_image_path=str(prev_frame_path) if use_reference else None,
        )
        shutil.move(tmp_path, str(local_path))
        prompt_marker.write_text(prompt, encoding="utf-8")
        results.append((web_path, prompt))
        prev_frame_path = local_path

    return results

def generate_batch(
    scenes: list[dict[str, str]],
    script_id: str,
    width: int = 1344,
    height: int = 768,
    style_guide: str = "",
    style_string: str = "",
) -> list[dict[str, str | None]]:
    """Generate images for a list of scenes sequentially.

    Each scene dict must have 'scene_id' and 'visual_prompt'.
    Optionally 'is_animated' (bool) and 'visual_prompt_b' (str) for A/B scenes.
    Optionally 'frame_prompts' (list[str]) and 'frame_seed' (int|None) for multi-frame scenes.
    Returns list of {scene_id, image_url, prompt_used, image_url_b?, frame_urls?, error?}.
    """
    results: list[dict[str, str]] | None = []
    logger.info("Starting batch image generation for %s scenes (script %s)", len(scenes), script_id)
    for scene in scenes:
        try:
            frame_prompts = scene.get("frame_prompts", [])

            # Multi-frame path
            if frame_prompts:
                frame_results = generate_scene_frames(
                    scene_id=scene["scene_id"],
                    frame_prompts=frame_prompts,
                    script_id=script_id,
                    visual_prompt=scene.get("visual_prompt", ""),
                    width=width,
                    height=height,
                    style_guide=style_guide,
                    seed=scene.get("frame_seed"),
                    style_string=style_string,
                )
                frame_urls = [url for url, _ in frame_results]
                # Use first frame as the primary image_url for backward compat
                results.append({
                    "scene_id": scene["scene_id"],
                    "image_url": frame_urls[0] if frame_urls else None,
                    "image_url_b": None,
                    "frame_urls": frame_urls,
                    "prompt_used": frame_results[0][1] if frame_results else None,
                    "error": None,
                })
                continue

            # Legacy single/A-B path
            image_url, prompt_used = generate_scene_image(
                scene_id=scene["scene_id"],
                visual_prompt=scene["visual_prompt"],
                script_id=script_id,
                width=width,
                height=height,
                style_guide=style_guide,
                style_string=style_string,
            )
            image_url_b = None
            if scene.get("is_animated") and scene.get("visual_prompt_b"):
                image_url_b, _ = generate_scene_image(
                    scene_id=scene["scene_id"],
                    visual_prompt=scene["visual_prompt_b"],
                    script_id=script_id,
                    width=width,
                    height=height,
                    variant="b",
                    style_guide=style_guide,
                    style_string=style_string,
                )
            results.append({
                "scene_id": scene["scene_id"],
                "image_url": image_url,
                "image_url_b": image_url_b,
                "prompt_used": prompt_used,
                "error": None,
            })
        except Exception as exc:
            logger.error("Image generation failed for scene %s: %s", scene["scene_id"], exc, exc_info=True)
            results.append({
                "scene_id": scene["scene_id"],
                "image_url": None,
                "image_url_b": None,
                "prompt_used": None,
                "error": str(exc),
            })
    logger.info("Batch image generation complete: %s/%s succeeded",
                sum(1 for r in results if r.get("error") is None), len(scenes))
    return results
