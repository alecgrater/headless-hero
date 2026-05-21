"""AI video generation pipeline for scene visuals."""

import hashlib
import json
import logging
import os
from pathlib import Path

from config import DATA_DIR, IMAGE_HEIGHT, IMAGE_WIDTH
from pipeline.image_gen import generate_scene_image

logger = logging.getLogger(__name__)


_NEGATIVE_MOTION_GUIDANCE = (
    "No text, letters, captions, subtitles, logos, watermarks, new characters, "
    "new objects, heavy camera shake, photorealism, 3D rendering, style change, "
    "warped faces, distorted hands, flicker, or sudden cuts."
)


def _build_animation_prompt(visual_prompt: str) -> str:
    prompt = visual_prompt.strip()
    return (
        "Animate this as a polished educational explainer shot in the same flat 2D cartoon style "
        "as the reference image. Preserve the exact composition, subject identities, colors, clean "
        "line art, and lighting from the source frame. Use subtle natural motion that supports the "
        f"scene: {prompt}. Add a calm, slow documentary push-in with gentle parallax where appropriate. "
        "Keep the motion restrained and readable for narration. "
        f"{_NEGATIVE_MOTION_GUIDANCE}"
    )


def _prompt_marker_path(video_path: Path) -> Path:
    return video_path.with_suffix(".prompt")


def _metadata_path(video_path: Path) -> Path:
    return video_path.with_suffix(".source.json")


def _read_metadata(video_path: Path) -> dict[str, object] | None:
    path = _metadata_path(video_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid video source metadata at %s", path)
        return None


def _source_image_path(script_id: str, scene_id: str, image_url: str) -> Path:
    filename = image_url.rsplit("/", 1)[-1] if image_url else f"{scene_id}.png"
    return DATA_DIR / "projects" / script_id / "images" / filename


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_marker(
    *,
    prompt: str,
    image_path: Path,
    image_metadata: dict[str, object] | None,
    width: int,
    height: int,
    scene_duration_seconds: float,
) -> str:
    from integrations.runway_video_client import RUNWAY_MODEL, duration_for_scene, ratio_for_dimensions

    contract = {
        "prompt": prompt,
        "provider": "runway",
        "model": RUNWAY_MODEL,
        "runway_duration_seconds": duration_for_scene(scene_duration_seconds),
        "ratio": ratio_for_dimensions(width, height),
        "width": width,
        "height": height,
        "anchor_image_hash": _file_hash(image_path),
        "anchor_source_type": (image_metadata or {}).get("source_type"),
        "anchor_provider": (image_metadata or {}).get("provider"),
        "image_provider_setting": os.environ.get("IMAGE_PROVIDER", "google"),
    }
    return hashlib.sha256(json.dumps(contract, sort_keys=True).encode("utf-8")).hexdigest()


def generate_scene_video(
    *,
    scene_id: str,
    visual_prompt: str,
    script_id: str,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
    scene_duration_seconds: float = 5.0,
    force: bool = False,
    contains_person: bool = False,
) -> tuple[str, str, dict[str, object] | None]:
    """Generate one anchor image, animate it with Runway, and save the MP4 locally."""
    videos_dir = DATA_DIR / "projects" / script_id / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    video_path = videos_dir / f"{scene_id}.mp4"
    web_path = f"/static/projects/{script_id}/videos/{scene_id}.mp4"
    prompt = _build_animation_prompt(visual_prompt)

    image_url, _image_prompt, image_metadata = generate_scene_image(
        scene_id=scene_id,
        visual_prompt=visual_prompt,
        script_id=script_id,
        width=width,
        height=height,
        force=force,
        contains_person=contains_person,
    )
    if image_metadata is None:
        logger.info("Regenerating AI video anchor for scene %s because cached image lacks source metadata", scene_id)
        image_url, _image_prompt, image_metadata = generate_scene_image(
            scene_id=scene_id,
            visual_prompt=visual_prompt,
            script_id=script_id,
            width=width,
            height=height,
            force=True,
            contains_person=contains_person,
        )
    if not image_metadata or image_metadata.get("source_type") != "ai_generated":
        raise RuntimeError(
            "Refusing to animate non-AI anchor image "
            f"for scene {scene_id}: {(image_metadata or {}).get('source_type')}"
        )
    image_path = _source_image_path(script_id, scene_id, image_url)
    if not image_path.exists():
        raise RuntimeError(f"AI video anchor image was not found: {image_path}")

    marker_hash = _cache_marker(
        prompt=prompt,
        image_path=image_path,
        image_metadata=image_metadata,
        width=width,
        height=height,
        scene_duration_seconds=scene_duration_seconds,
    )
    marker = _prompt_marker_path(video_path)
    if not force and video_path.exists() and marker.exists() and marker.read_text(encoding="utf-8").strip() == marker_hash:
        logger.info("AI video cache hit for scene %s", scene_id)
        return web_path, prompt, _read_metadata(video_path)

    from integrations.runway_video_client import generate_video_from_image

    metadata = generate_video_from_image(
        image_path=str(image_path),
        prompt=prompt,
        output_path=video_path,
        width=width,
        height=height,
        scene_duration_seconds=scene_duration_seconds,
        script_id=script_id,
    )
    marker.write_text(marker_hash, encoding="utf-8")
    return web_path, prompt, metadata
