"""Thin wrapper around the Runway API for image-to-video generation."""

import base64
import json
import logging
import mimetypes
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from integrations.usage_tracker import RUNWAY_GEN4_TURBO_PER_SECOND, record_usage

logger = logging.getLogger(__name__)

RUNWAY_API_BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_API_VERSION = "2024-11-06"
RUNWAY_MODEL = "gen4_turbo"
RUNWAY_IMAGE_DATA_URI_LIMIT_BYTES = 5 * 1024 * 1024


def _require_secret() -> str:
    secret = os.environ.get("RUNWAYML_API_SECRET") or os.environ.get("RUNWAY_API_KEY")
    if not secret:
        raise RuntimeError(
            "RUNWAYML_API_SECRET is not set. Add it in Settings -> API Keys "
            "or export it in your shell."
        )
    return secret


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_require_secret()}",
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_API_VERSION,
    }


def ratio_for_dimensions(width: int, height: int) -> str:
    ratio = width / max(height, 1)
    options = [
        (1280 / 720, "1280:720"),
        (720 / 1280, "720:1280"),
        (1104 / 832, "1104:832"),
        (832 / 1104, "832:1104"),
        (960 / 960, "960:960"),
        (1584 / 672, "1584:672"),
    ]
    return min(options, key=lambda item: abs(item[0] - ratio))[1]


def duration_for_scene(duration_seconds: float) -> int:
    return 10 if duration_seconds > 6.5 else 5


def _image_to_data_uri(image_path: str) -> str:
    """Return a Runway-compatible image data URI, compressing if needed."""
    path = Path(image_path)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = path.read_bytes()
    if len(base64.b64encode(data)) <= RUNWAY_IMAGE_DATA_URI_LIMIT_BYTES:
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    with Image.open(path) as img:
        rgb = img.convert("RGB")
        for quality in (92, 85, 78, 70, 62, 54, 46):
            fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            try:
                rgb.save(tmp_path, format="JPEG", quality=quality, optimize=True)
                compressed = Path(tmp_path).read_bytes()
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            encoded = base64.b64encode(compressed)
            if len(encoded) <= RUNWAY_IMAGE_DATA_URI_LIMIT_BYTES:
                logger.info(
                    "Compressed Runway prompt image to JPEG quality=%d (%.2fMB encoded)",
                    quality,
                    len(encoded) / 1024 / 1024,
                )
                return f"data:image/jpeg;base64,{encoded.decode('ascii')}"

    raise RuntimeError("Prompt image is too large for Runway data URI upload after compression.")


def _extract_output_url(task: dict[str, Any]) -> str:
    output = task.get("output")
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("url", "uri"):
                value = first.get(key)
                if isinstance(value, str):
                    return value
    raise RuntimeError(f"Runway task completed without a video URL: {task}")


def _poll_task(client: httpx.Client, task_id: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"{RUNWAY_API_BASE}/tasks/{task_id}", headers=_headers())
        response.raise_for_status()
        task = response.json()
        status = str(task.get("status", "")).lower()
        if status in {"succeeded", "success", "completed", "complete"}:
            return task
        if status in {"failed", "failure", "cancelled", "canceled"}:
            raise RuntimeError(f"Runway task {task_id} failed: {task}")
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for Runway task {task_id}")


def generate_video_from_image(
    *,
    image_path: str,
    prompt: str,
    output_path: Path,
    width: int,
    height: int,
    scene_duration_seconds: float,
    script_id: str | None = None,
) -> dict[str, object]:
    """Generate a Runway Gen-4 Turbo video from an image and save it locally."""
    duration = duration_for_scene(scene_duration_seconds)
    ratio = ratio_for_dimensions(width, height)
    payload = {
        "model": RUNWAY_MODEL,
        "promptImage": _image_to_data_uri(image_path),
        "promptText": prompt,
        "ratio": ratio,
        "duration": duration,
    }

    timeout = float(os.environ.get("RUNWAY_TIMEOUT_SECONDS", "900"))
    logger.info("Starting Runway image-to-video task (model=%s, ratio=%s, duration=%ss)", RUNWAY_MODEL, ratio, duration)
    with httpx.Client(timeout=120.0) as client:
        response = client.post(f"{RUNWAY_API_BASE}/image_to_video", headers=_headers(), json=payload)
        response.raise_for_status()
        created = response.json()
        task_id = created.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"Runway did not return a task id: {created}")
        task = _poll_task(client, task_id, timeout_seconds=timeout)
        video_url = _extract_output_url(task)
        download = client.get(video_url, follow_redirects=True)
        download.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(download.content)
    os.chmod(output_path, 0o644)

    cost_estimate = duration * RUNWAY_GEN4_TURBO_PER_SECOND
    metadata = {
        "source_type": "ai_generated_video",
        "provider": "runway",
        "model": RUNWAY_MODEL,
        "task_id": task_id,
        "duration_seconds": duration,
        "ratio": ratio,
        "prompt": prompt,
        "cost_estimate": cost_estimate,
        "fallback": False,
    }
    output_path.with_suffix(".source.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    record_usage(
        service="runway",
        operation="image_to_video",
        model=RUNWAY_MODEL,
        cost_estimate=cost_estimate,
        metadata_json=json.dumps({"task_id": task_id, "duration_seconds": duration, "ratio": ratio}),
        script_id=script_id,
    )
    return metadata
