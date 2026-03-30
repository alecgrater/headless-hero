"""Image generation pipeline — connects visual prompts to Google Gemini."""

import os
import shutil
from pathlib import Path

from integrations.image_client import generate_image

# data/ directory lives two levels above backend/pipeline/
_data_dir = Path(os.environ.get("HH_DATA_DIR", os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data")))

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
    images_dir = _data_dir / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    suffix = "_b" if variant == "b" else ""
    filename = f"{scene_id}{suffix}.png"
    local_path = images_dir / filename
    prompt_marker = images_dir / f"{scene_id}{suffix}.prompt"
    web_path = f"/static/projects/{script_id}/images/{filename}"

    if not force and local_path.exists() and prompt_marker.exists():
        cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
        if cached_prompt == prompt:
            return web_path, prompt

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
    images_dir = _data_dir / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    total_frames = len(frame_prompts)
    results: list[tuple[str, str]] = []

    for i, frame_prompt in enumerate(frame_prompts):
        # Build continuity-aware prompt:
        # style_string → guide → continuity preamble → frame instruction
        parts: list[str] = []
        if style_string:
            parts.append(style_string)
        if guide:
            parts.append(guide)

        # Add continuity preamble when we have a visual_prompt anchor
        if visual_prompt and total_frames > 1:
            continuity = (
                f"ANIMATION SEQUENCE: This is frame {i + 1} of {total_frames} "
                f"in an animation sequence.\n"
                f"BASE SCENE: {visual_prompt}\n"
                f"ALL frames must have IDENTICAL style, character design, "
                f"background, composition, and color palette. "
                f"Only the specific action/pose described below should differ "
                f"from the base scene.\n\n"
                f"FRAME INSTRUCTION: {frame_prompt}"
            )
            parts.append(continuity)
        else:
            parts.append(frame_prompt)

        prompt = "\n\n".join(parts)

        filename = f"{scene_id}_f{i}.png"
        local_path = images_dir / filename
        prompt_marker = images_dir / f"{scene_id}_f{i}.prompt"
        web_path = f"/static/projects/{script_id}/images/{filename}"

        # Cache check
        if not force and local_path.exists() and prompt_marker.exists():
            cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
            if cached_prompt == prompt:
                results.append((web_path, prompt))
                continue

        tmp_path = generate_image(prompt, width=width, height=height, seed=seed)
        shutil.move(tmp_path, str(local_path))
        prompt_marker.write_text(prompt, encoding="utf-8")
        results.append((web_path, prompt))

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
            results.append({
                "scene_id": scene["scene_id"],
                "image_url": None,
                "image_url_b": None,
                "prompt_used": None,
                "error": str(exc),
            })
    return results
