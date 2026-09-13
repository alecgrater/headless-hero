from pathlib import Path

import pytest

from integrations import local_tts_client
from integrations.local_models import REGISTRY


@pytest.fixture
def stub_backend(monkeypatch):
    monkeypatch.setattr(local_tts_client, "ensure_daemon", lambda backend: None)
    monkeypatch.setattr(local_tts_client, "_post_speech", lambda **kwargs: b"RIFFFAKEWAVDATA")
    monkeypatch.setattr(local_tts_client, "_wav_to_mp3", lambda data: b"ID3FAKEMP3")
    monkeypatch.setattr(
        local_tts_client,
        "align_audio",
        lambda path, text: [
            {"word": "hello", "start_ms": 0, "end_ms": 400},
            {"word": "world", "start_ms": 400, "end_ms": 900},
        ],
    )


def test_returns_mp3_bytes_and_word_timestamps(stub_backend):
    audio, words = local_tts_client.generate_speech(text="hello world", voice_id="narrator")
    assert audio == b"ID3FAKEMP3"
    assert [w["word"] for w in words] == ["hello", "world"]
    assert words[-1]["end_ms"] == 900


def test_word_timestamps_match_elevenlabs_key_shape(stub_backend):
    _, words = local_tts_client.generate_speech(text="hello world", voice_id="narrator")
    for word in words:
        assert set(word) == {"word", "start_ms", "end_ms"}


def test_request_carries_the_active_voice_model(stub_backend, monkeypatch):
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    captured: dict = {}
    monkeypatch.setattr(
        local_tts_client,
        "_post_speech",
        lambda **kwargs: captured.update(kwargs) or b"RIFFFAKEWAVDATA",
    )
    local_tts_client.generate_speech(text="hi", voice_id="af_heart")
    assert captured["model"] == REGISTRY["kokoro-82m"].weights
    assert captured["voice"] == "af_heart"
    assert captured["text"] == "hi"


def test_speed_from_voice_settings_is_forwarded(stub_backend, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        local_tts_client,
        "_post_speech",
        lambda **kwargs: captured.update(kwargs) or b"RIFFFAKEWAVDATA",
    )
    local_tts_client.generate_speech(text="hi", voice_id="narrator", voice_settings={"speed": 1.15})
    assert captured["speed"] == 1.15


def test_empty_text_returns_empty_result(stub_backend):
    audio, words = local_tts_client.generate_speech(text="   ", voice_id="narrator")
    assert audio == b""
    assert words == []


def test_alignment_failure_degrades_to_empty_timestamps(stub_backend, monkeypatch):
    monkeypatch.setattr(local_tts_client, "align_audio", lambda path, text: [])
    audio, words = local_tts_client.generate_speech(text="hello world", voice_id="narrator")
    assert audio == b"ID3FAKEMP3"
    assert words == []


def test_temp_wav_is_cleaned_up(stub_backend, monkeypatch):
    seen: list[Path] = []

    def spy(path, text):
        seen.append(Path(path))
        assert Path(path).exists()
        return []

    monkeypatch.setattr(local_tts_client, "align_audio", spy)
    local_tts_client.generate_speech(text="hello", voice_id="narrator")
    assert seen and not seen[0].exists()


def test_temp_wav_is_cleaned_up_even_when_alignment_raises(stub_backend, monkeypatch):
    seen: list[Path] = []

    def boom(path, text):
        seen.append(Path(path))
        raise RuntimeError("whisper died")

    monkeypatch.setattr(local_tts_client, "align_audio", boom)
    with pytest.raises(RuntimeError, match="whisper died"):
        local_tts_client.generate_speech(text="hello", voice_id="narrator")
    assert seen and not seen[0].exists()


def test_missing_daemon_raises_actionable_error(monkeypatch):
    def boom(backend):
        raise RuntimeError("mlx-audio daemon is not responding")

    monkeypatch.setattr(local_tts_client, "ensure_daemon", boom)
    with pytest.raises(RuntimeError, match="not responding"):
        local_tts_client.generate_speech(text="hi", voice_id="narrator")


def test_signature_matches_the_elevenlabs_client():
    import inspect

    from integrations import elevenlabs_client

    local_params = list(inspect.signature(local_tts_client.generate_speech).parameters)
    cloud_params = list(inspect.signature(elevenlabs_client.generate_speech).parameters)
    assert local_params == cloud_params
