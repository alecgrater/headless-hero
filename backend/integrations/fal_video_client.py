"""Thin wrapper around the Fal.ai queue API for image-to-video generation."""

import base64
import json
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import httpx

from integrations.usage_tracker import FAL_WAN_22_TURBO_PER_VIDEO_BY_RESOLUTION, record_usage

logger = logging.getLogger(__name__)

FAL_QUEUE_BASE = "https://queue.fal.run"
FAL_DEFAULT_VIDEO_MODEL = "fal-ai/wan/v2.2-a14b/image-to-video/turbo"
FAL_DEFAULT_RESOLUTION = "720p"


def model_name() -> str:
    return os.environ.get("FAL_VIDEO_MODEL", FAL_DEFAULT_VIDEO_MODEL).strip() or FAL_DEFAULT_VIDEO_MODEL


def _require_key() -> str:
    key = os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY")
    if not key:
        raise RuntimeError(
            "FAL_API_KEY is not set. Add it in Settings -> API Keys "
            "or export it in your shell."
        )
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Key {_require_key()}",
        "Content-Type": "application/json",
    }


def aspect_ratio_for_dimensions(width: int, height: int) -> str:
    ratio = width / max(height, 1)
    options = [
        (16 / 9, "16:9"),
        (9 / 16, "9:16"),
        (1, "1:1"),
    ]
    return min(options, key=lambda item: abs(item[0] - ratio))[1]


def resolution() -> str:
    value = os.environ.get("FAL_VIDEO_RESOLUTION", FAL_DEFAULT_RESOLUTION).strip().lower()
    if value not in {"480p", "580p", "720p"}:
        logger.warning("Invalid FAL_VIDEO_RESOLUTION=%r; using %s", value, FAL_DEFAULT_RESOLUTION)
        return FAL_DEFAULT_RESOLUTION
    return value


def _image_to_data_uri(image_path: str) -> str:
    path = Path(image_path)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _poll_request(client: httpx.Client, request_id: str, timeout_seconds: float, status_url: str) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    include_logs = True
    while time.monotonic() < deadline:
        response = client.get(
            status_url,
            headers=_headers(),
            params={"logs": "1"} if include_logs else None,
        )
        if response.status_code == 405 and include_logs:
            logger.warning("Fal status endpoint rejected logs polling for request %s; retrying without logs", request_id)
            include_logs = False
            response = client.get(status_url, headers=_headers())
        response.raise_for_status()
        status = response.json()
        status_name = str(status.get("status", "")).upper()
        if status_name == "COMPLETED":
            if status.get("error"):
                raise RuntimeError(f"Fal request {request_id} failed: {status}")
            return status
        if status_name in {"FAILED", "ERROR", "CANCELLED", "CANCELED"}:
            raise RuntimeError(f"Fal request {request_id} failed: {status}")
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for Fal request {request_id}")


def _extract_video_url(result: dict[str, Any]) -> str:
    video = result.get("video")
    if isinstance(video, dict):
        url = video.get("url")
        if isinstance(url, str) and url:
            return url
    if isinstance(video, str) and video:
        return video
    raise RuntimeError(f"Fal request completed without a video URL: {result}")


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
    """Generate a Fal Wan image-to-video clip from an image and save it locally."""
    model = model_name()
    ratio = aspect_ratio_for_dimensions(width, height)
    res = resolution()
    payload = {
        "image_url": _image_to_data_uri(image_path),
        "prompt": prompt,
        "resolution": res,
        "aspect_ratio": ratio,
        "enable_safety_checker": True,
        "enable_output_safety_checker": False,
        "enable_prompt_expansion": False,
        "acceleration": "regular",
        "video_quality": "high",
        "video_write_mode": "balanced",
    }

    timeout = float(os.environ.get("FAL_TIMEOUT_SECONDS", "900"))
    logger.info("Starting Fal image-to-video task (model=%s, ratio=%s, resolution=%s)", model, ratio, res)
    with httpx.Client(timeout=120.0) as client:
        response = client.post(f"{FAL_QUEUE_BASE}/{model}", headers=_headers(), json=payload)
        response.raise_for_status()
        created = response.json()
        request_id = created.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise RuntimeError(f"Fal did not return a request id: {created}")
        status_url = created.get("status_url")
        if not isinstance(status_url, str) or not status_url:
            status_url = f"{FAL_QUEUE_BASE}/{model}/requests/{request_id}/status"
        result_url = created.get("response_url") or created.get("result_url")
        if not isinstance(result_url, str) or not result_url:
            result_url = f"{FAL_QUEUE_BASE}/{model}/requests/{request_id}/response"
        status = _poll_request(client, request_id, timeout_seconds=timeout, status_url=status_url)
        status_result_url = status.get("response_url")
        if isinstance(status_result_url, str) and status_result_url:
            result_url = status_result_url
        result_response = client.get(result_url, headers=_headers())
        result_response.raise_for_status()
        result = result_response.json()
        video_url = _extract_video_url(result)
        download = client.get(video_url, follow_redirects=True)
        download.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(download.content)
    os.chmod(output_path, 0o644)

    cost_estimate = FAL_WAN_22_TURBO_PER_VIDEO_BY_RESOLUTION.get(res, 0.0)
    metadata = {
        "source_type": "ai_generated_video",
        "provider": "fal",
        "model": model,
        "request_id": request_id,
        "duration_seconds": scene_duration_seconds,
        "ratio": ratio,
        "resolution": res,
        "prompt": prompt,
        "cost_estimate": cost_estimate,
        "fallback": False,
    }
    output_path.with_suffix(".source.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    record_usage(
        service="fal",
        operation="image_to_video",
        model=model,
        cost_estimate=cost_estimate,
        metadata_json=json.dumps({"request_id": request_id, "resolution": res, "ratio": ratio}),
        script_id=script_id,
    )
    return metadata
