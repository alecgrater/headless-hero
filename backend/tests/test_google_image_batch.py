import base64
from pathlib import Path

import pytest

from integrations import google_image_client


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class _State:
    def __init__(self, name: str):
        self.name = name


class _InlineData:
    def __init__(self, data: bytes):
        self.data = data


class _Part:
    def __init__(self, data: bytes):
        self.inline_data = _InlineData(data)


class _Response:
    def __init__(self, data: bytes, *, use_candidates: bool = False):
        if use_candidates:
            self.candidates = [_Candidate(data)]
            self.parts = []
        else:
            self.parts = [_Part(data)]
            self.candidates = []


class _Content:
    def __init__(self, data: bytes):
        self.parts = [_Part(data)]


class _Candidate:
    def __init__(self, data: bytes):
        self.content = _Content(data)


class _InlineResponse:
    def __init__(self, data: bytes | None = None, error: str | None = None, *, use_candidates: bool = False):
        self.response = _Response(data, use_candidates=use_candidates) if data is not None else None
        self.error = error


class _Dest:
    def __init__(self, responses: list[_InlineResponse]):
        self.inlined_responses = responses


class _BatchJob:
    def __init__(
        self,
        name: str = "batches/test",
        state: str = "JOB_STATE_PENDING",
        responses: list[_InlineResponse] | None = None,
        error: str | None = None,
    ):
        self.name = name
        self.state = _State(state)
        self.dest = _Dest(responses or [])
        self.error = error


class _Batches:
    def __init__(self, terminal_job: _BatchJob):
        self.created_model = ""
        self.created_src = []
        self.created_srcs = []
        self.created_config = {}
        self.create_count = 0
        self._terminal_job = terminal_job
        self._gets = 0

    def create(self, *, model, src, config):
        self.created_model = model
        self.created_src = src
        self.created_srcs.append(src)
        self.created_config = config
        self.create_count += 1
        return _BatchJob()

    def get(self, *, name):
        self._gets += 1
        if self._gets == 1:
            return _BatchJob(name=name, state="JOB_STATE_RUNNING")
        return self._terminal_job


class _Client:
    def __init__(self, terminal_job: _BatchJob):
        self.batches = _Batches(terminal_job)


def test_generate_images_batch_returns_temp_pngs(monkeypatch):
    client = _Client(
        _BatchJob(
            state="JOB_STATE_SUCCEEDED",
            responses=[_InlineResponse(TINY_PNG), _InlineResponse(TINY_PNG)],
        )
    )
    usage_records = []
    monkeypatch.setattr(google_image_client.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(google_image_client, "record_usage", lambda **kwargs: usage_records.append(kwargs))

    results = google_image_client.generate_images_batch(
        client=client,
        requests=[
            google_image_client.GoogleBatchImageRequest(key="scene-a", prompt="a prompt", aspect_ratio="16:9"),
            google_image_client.GoogleBatchImageRequest(key="scene-b", prompt="b prompt", aspect_ratio="16:9"),
        ],
        script_id="script-1",
        poll_interval_seconds=0,
    )

    assert [result.key for result in results] == ["scene-a", "scene-b"]
    assert all(Path(result.image_path).read_bytes() == TINY_PNG for result in results if result.image_path)
    assert client.batches.created_model == google_image_client.DEFAULT_IMAGE_MODEL
    assert client.batches.created_config["display_name"].startswith("headless-hero-images-script-1")
    assert client.batches.created_src[0]["contents"][0]["parts"][0]["text"] == "a prompt"
    assert usage_records[-1]["operation"] == "image_gen_batch"
    assert usage_records[-1]["images"] == 2


def test_generate_images_batch_extracts_candidate_content_parts(monkeypatch):
    client = _Client(
        _BatchJob(
            state="JOB_STATE_SUCCEEDED",
            responses=[_InlineResponse(TINY_PNG, use_candidates=True)],
        )
    )
    monkeypatch.setattr(google_image_client.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(google_image_client, "record_usage", lambda **_kwargs: None)

    results = google_image_client.generate_images_batch(
        client=client,
        requests=[
            google_image_client.GoogleBatchImageRequest(key="scene-a", prompt="a prompt", aspect_ratio="16:9"),
        ],
        poll_interval_seconds=0,
    )

    assert len(results) == 1
    assert results[0].error is None
    assert Path(results[0].image_path or "").read_bytes() == TINY_PNG


def test_generate_images_batch_chunks_inline_requests_under_limit(monkeypatch):
    client = _Client(
        _BatchJob(
            state="JOB_STATE_SUCCEEDED",
            responses=[_InlineResponse(TINY_PNG)],
        )
    )
    monkeypatch.setattr(google_image_client.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(google_image_client, "record_usage", lambda **_kwargs: None)
    monkeypatch.setattr(google_image_client, "BATCH_INLINE_REQUEST_LIMIT_BYTES", 160)

    results = google_image_client.generate_images_batch(
        client=client,
        requests=[
            google_image_client.GoogleBatchImageRequest(key="scene-a", prompt="a prompt" * 10, aspect_ratio="16:9"),
            google_image_client.GoogleBatchImageRequest(key="scene-b", prompt="b prompt" * 10, aspect_ratio="16:9"),
        ],
        poll_interval_seconds=0,
    )

    assert [result.key for result in results] == ["scene-a", "scene-b"]
    assert client.batches.create_count == 2
    assert all(len(src) == 1 for src in client.batches.created_srcs)


def test_generate_images_batch_raises_on_failed_job(monkeypatch):
    client = _Client(_BatchJob(state="JOB_STATE_FAILED", error="quota exhausted"))
    monkeypatch.setattr(google_image_client.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="Google image batch failed"):
        google_image_client.generate_images_batch(
            client=client,
            requests=[
                google_image_client.GoogleBatchImageRequest(key="scene-a", prompt="a prompt", aspect_ratio="16:9"),
            ],
            poll_interval_seconds=0,
        )
