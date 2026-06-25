from pathlib import Path

import httpx

from integrations import fal_video_client


class _JsonResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.content = b""
        self.request = httpx.Request("GET", "https://queue.fal.run/test")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=self.request, response=httpx.Response(self.status_code))


class _BytesResponse:
    status_code = 200
    content = b"video-bytes"

    def json(self):
        return {}

    def raise_for_status(self):
        return None


def _input_image(tmp_path: Path) -> Path:
    path = tmp_path / "anchor.png"
    path.write_bytes(b"png")
    return path


def _run_fal_generation(monkeypatch, tmp_path: Path, fake_client):
    monkeypatch.setenv("FAL_API_KEY", "fal-test-key")
    monkeypatch.setattr(fal_video_client.httpx, "Client", lambda timeout: fake_client)
    monkeypatch.setattr(fal_video_client, "record_usage", lambda **_kwargs: None)
    monkeypatch.setattr(fal_video_client.time, "sleep", lambda _seconds: None)

    return fal_video_client.generate_video_from_image(
        image_path=str(_input_image(tmp_path)),
        prompt="subtle motion",
        output_path=tmp_path / "scene.mp4",
        width=1920,
        height=1080,
        scene_duration_seconds=5.0,
        script_id="script-1",
    )


def test_fal_generation_uses_queue_urls_returned_by_submit(monkeypatch, tmp_path):
    calls: list[tuple[str, str]] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, **_kwargs):
            calls.append(("POST", url))
            return _JsonResponse({
                "request_id": "request-1",
                "status_url": "https://queue.fal.run/custom/status-url",
                "response_url": "https://queue.fal.run/custom/response-url",
            })

        def get(self, url, **_kwargs):
            calls.append(("GET", url))
            if url == "https://queue.fal.run/custom/status-url":
                return _JsonResponse({"status": "COMPLETED"})
            if url == "https://queue.fal.run/custom/response-url":
                return _JsonResponse({"video": {"url": "https://v3.fal.media/video.mp4"}})
            if url == "https://v3.fal.media/video.mp4":
                return _BytesResponse()
            raise AssertionError(f"unexpected GET {url}")

    metadata = _run_fal_generation(monkeypatch, tmp_path, FakeClient())

    assert metadata["provider"] == "fal"
    assert (tmp_path / "scene.mp4").read_bytes() == b"video-bytes"
    assert ("GET", "https://queue.fal.run/custom/status-url") in calls
    assert ("GET", "https://queue.fal.run/custom/response-url") in calls


def test_fal_status_polling_retries_without_logs_after_405(monkeypatch, tmp_path):
    status_calls: list[dict] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, **_kwargs):
            return _JsonResponse({
                "request_id": "request-2",
                "status_url": "https://queue.fal.run/custom/status-url",
                "response_url": "https://queue.fal.run/custom/response-url",
            })

        def get(self, url, **kwargs):
            if url == "https://queue.fal.run/custom/status-url":
                status_calls.append(kwargs)
                if kwargs.get("params") == {"logs": "1"}:
                    return _JsonResponse({"detail": "Method Not Allowed"}, status_code=405)
                return _JsonResponse({"status": "COMPLETED", "response_url": "https://queue.fal.run/custom/response-url"})
            if url == "https://queue.fal.run/custom/response-url":
                return _JsonResponse({"video": {"url": "https://v3.fal.media/video.mp4"}})
            if url == "https://v3.fal.media/video.mp4":
                return _BytesResponse()
            raise AssertionError(f"unexpected GET {url}")

    _run_fal_generation(monkeypatch, tmp_path, FakeClient())

    assert status_calls[0]["params"] == {"logs": "1"}
    assert "params" not in status_calls[1]


def test_frames_for_duration_clamps_and_biases_long():
    # +1 frame bias keeps the clip just past the narration.
    assert fal_video_client._frames_for_duration(5.0) == 81  # ceil(80)+1
    assert fal_video_client._frames_for_duration(8.0) == 129  # ceil(128)+1
    # Floor at fal's minimum.
    assert fal_video_client._frames_for_duration(0.1) == fal_video_client.FAL_MIN_FRAMES
    assert fal_video_client._frames_for_duration(0.0) == fal_video_client.FAL_MIN_FRAMES
    # Ceiling at fal's maximum (anything over ~10s).
    assert fal_video_client._frames_for_duration(15.36) == fal_video_client.FAL_MAX_FRAMES
    assert fal_video_client._frames_for_duration(999.0) == fal_video_client.FAL_MAX_FRAMES


def test_model_supports_frame_count_only_for_non_turbo():
    assert fal_video_client._model_supports_frame_count("fal-ai/wan/v2.2-a14b/image-to-video") is True
    assert fal_video_client._model_supports_frame_count("fal-ai/wan/v2.2-a14b/image-to-video/turbo") is False
    assert fal_video_client._model_supports_frame_count("fal-ai/wan/v2.2-a14b/image-to-video/turbo/") is False


class _PayloadCaptureClient:
    def __init__(self, captured: dict):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def post(self, url, **kwargs):
        self._captured.update(kwargs.get("json", {}))
        return _JsonResponse({
            "request_id": "request-payload",
            "status_url": "https://queue.fal.run/custom/status-url",
            "response_url": "https://queue.fal.run/custom/response-url",
        })

    def get(self, url, **_kwargs):
        if url == "https://queue.fal.run/custom/status-url":
            return _JsonResponse({"status": "COMPLETED"})
        if url == "https://queue.fal.run/custom/response-url":
            return _JsonResponse({"video": {"url": "https://v3.fal.media/video.mp4", "duration": 8.06}})
        if url == "https://v3.fal.media/video.mp4":
            return _BytesResponse()
        raise AssertionError(f"unexpected GET {url}")


def test_non_turbo_payload_sizes_frames_and_records_actual_duration(monkeypatch, tmp_path):
    captured: dict = {}
    monkeypatch.delenv("FAL_VIDEO_MODEL", raising=False)  # use non-turbo default
    metadata = _run_fal_generation_with_duration(
        monkeypatch, tmp_path, _PayloadCaptureClient(captured), scene_duration_seconds=8.0,
    )

    assert captured["num_frames"] == 129
    assert captured["frames_per_second"] == fal_video_client.FAL_VIDEO_FPS
    assert captured["interpolator_model"] == "none"
    # Metadata reflects the clip fal actually returned, not the requested scene length.
    assert metadata["duration_seconds"] == 8.06


def test_turbo_payload_omits_frame_count(monkeypatch, tmp_path):
    captured: dict = {}
    monkeypatch.setenv("FAL_VIDEO_MODEL", "fal-ai/wan/v2.2-a14b/image-to-video/turbo")
    _run_fal_generation_with_duration(
        monkeypatch, tmp_path, _PayloadCaptureClient(captured), scene_duration_seconds=8.0,
    )

    assert "num_frames" not in captured
    assert "frames_per_second" not in captured
    assert "interpolator_model" not in captured


def _run_fal_generation_with_duration(monkeypatch, tmp_path: Path, fake_client, *, scene_duration_seconds: float):
    monkeypatch.setenv("FAL_API_KEY", "fal-test-key")
    monkeypatch.setattr(fal_video_client.httpx, "Client", lambda timeout: fake_client)
    monkeypatch.setattr(fal_video_client, "record_usage", lambda **_kwargs: None)
    monkeypatch.setattr(fal_video_client.time, "sleep", lambda _seconds: None)
    return fal_video_client.generate_video_from_image(
        image_path=str(_input_image(tmp_path)),
        prompt="subtle motion",
        output_path=tmp_path / "scene.mp4",
        width=1920,
        height=1080,
        scene_duration_seconds=scene_duration_seconds,
        script_id="script-1",
    )
