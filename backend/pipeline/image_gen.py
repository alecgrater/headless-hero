"""Image generation pipeline — connects visual prompts to fal.ai Flux."""

import os
import urllib.request
from pathlib import Path

from integrations.fal_client import generate_image

# data/ directory lives two levels above backend/pipeline/
_data_dir = Path(os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

def generate_scene_image(
    scene_id: str,
    visual_prompt: str,
    brand_style: str,
    script_id: str,
    width: int = 1344,
    height: int = 768,
    force: bool = False,
) -> tuple[str, str]:
    """Generate a single scene image and save it locally.

    If the image already exists and force=False, skips regeneration.
    Returns (web-relative path, composed prompt used).
    """
    prompt = f"{brand_style}. {visual_prompt}" if brand_style else visual_prompt

    # Check cache: if image exists and we have a matching prompt marker, skip regen
    images_dir = _data_dir / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    local_path = images_dir / f"{scene_id}.png"
    prompt_marker = images_dir / f"{scene_id}.prompt"
    web_path = f"/static/projects/{script_id}/images/{scene_id}.png"

    if not force and local_path.exists() and prompt_marker.exists():
        cached_prompt = prompt_marker.read_text(encoding="utf-8").strip()
        if cached_prompt == prompt:
            return web_path, prompt

    cdn_url = generate_image(prompt, width=width, height=height)

    # Download to local storage
    urllib.request.urlretrieve(cdn_url, str(local_path))

    # Write prompt marker for cache validation
    prompt_marker.write_text(prompt, encoding="utf-8")

    return web_path, prompt

def generate_batch(
    scenes: list[dict[str, str]],
    brand_style: str,
    script_id: str,
    width: int = 1344,
    height: int = 768,
) -> list[dict[str, str | None]]:
    """Generate images for a list of scenes sequentially.

    Each scene dict must have 'scene_id' and 'visual_prompt'.
    Returns list of {scene_id, image_url, prompt_used, error?}.
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
            )
            results.append({
                "scene_id": scene["scene_id"],
                "image_url": image_url,
                "prompt_used": prompt_used,
                "error": None,
            })
        except Exception as exc:
            results.append({
                "scene_id": scene["scene_id"],
                "image_url": None,
                "prompt_used": None,
                "error": str(exc),
            })
    return results
