"""Image generation pipeline — connects visual prompts to Google Gemini."""

import os
import shutil
from pathlib import Path

from integrations.image_client import generate_image

# data/ directory lives two levels above backend/pipeline/
_data_dir = Path(os.environ.get("HH_DATA_DIR", os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data")))

_GUIDE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "image_gen_guide.md"
_STYLE_GUIDE = _GUIDE_PATH.read_text() if _GUIDE_PATH.exists() else ""

def _format_color_palette(color_palette: str) -> str:
    """Turn a comma-separated hex string into a readable palette description."""
    if not color_palette or not color_palette.strip():
        return ""
    colors = [c.strip() for c in color_palette.split(",") if c.strip()]
    if not colors:
        return ""
    return f"Brand color palette (use these colors prominently): {', '.join(colors)}"


def generate_scene_image(
    scene_id: str,
    visual_prompt: str,
    brand_style: str,
    script_id: str,
    width: int = 1344,
    height: int = 768,
    force: bool = False,
    variant: str = "a",
    style_guide: str = "",
    color_palette: str = "",
    font: str = "",
) -> tuple[str, str]:
    """Generate a single scene image and save it locally.

    If the image already exists and force=False, skips regeneration.
    variant="a" uses {scene_id}.png, variant="b" uses {scene_id}_b.png.
    style_guide overrides the default _STYLE_GUIDE if provided.
    Returns (web-relative path, composed prompt used).
    """
    guide = style_guide if style_guide else _STYLE_GUIDE

    # Build prompt: guide → brand style → color palette → font → visual prompt
    parts: list[str] = []
    if guide:
        parts.append(guide)
    if brand_style:
        parts.append(f"Brand art style: {brand_style}")
    palette_desc = _format_color_palette(color_palette)
    if palette_desc:
        parts.append(palette_desc)
    if font:
        parts.append(f"Brand typography: {font}")
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

    tmp_path = generate_image(prompt, width=width, height=height)

    # Move generated image to local storage
    shutil.move(tmp_path, str(local_path))

    # Write prompt marker for cache validation
    prompt_marker.write_text(prompt, encoding="utf-8")

    return web_path, prompt

def generate_batch(
    scenes: list[dict[str, str]],
    brand_style: str,
    script_id: str,
    width: int = 1344,
    height: int = 768,
    style_guide: str = "",
    color_palette: str = "",
    font: str = "",
) -> list[dict[str, str | None]]:
    """Generate images for a list of scenes sequentially.

    Each scene dict must have 'scene_id' and 'visual_prompt'.
    Optionally 'is_animated' (bool) and 'visual_prompt_b' (str) for A/B scenes.
    Returns list of {scene_id, image_url, prompt_used, image_url_b?, error?}.
    """
    results: list[dict[str, str]] | None = []
    for scene in scenes:
        try:
            image_url, prompt_used = generate_scene_image(
                scene_id=scene["scene_id"],
                visual_prompt=scene["visual_prompt"],
                brand_style=brand_style,
                script_id=script_id,
                width=width,
                height=height,
                style_guide=style_guide,
                color_palette=color_palette,
                font=font,
            )
            image_url_b = None
            if scene.get("is_animated") and scene.get("visual_prompt_b"):
                image_url_b, _ = generate_scene_image(
                    scene_id=scene["scene_id"],
                    visual_prompt=scene["visual_prompt_b"],
                    brand_style=brand_style,
                    script_id=script_id,
                    width=width,
                    height=height,
                    variant="b",
                    style_guide=style_guide,
                    color_palette=color_palette,
                    font=font,
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
