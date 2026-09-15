import io
import wave
from pathlib import Path

import pytest

from integrations import local_tts_client
from integrations.local_models import REGISTRY


def make_wav(seconds: float, rate: int = 8000) -> bytes:
    """A real silent PCM WAV, so the client's length checks see a parseable header."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


def alignment(*word_end_seconds: float) -> list[dict]:
    starts = [0.0, *word_end_seconds[:-1]]
    return [
        {"word": f"w{index}", "start_ms": int(start * 1000), "end_ms": int(end * 1000)}
        for index, (start, end) in enumerate(zip(starts, word_end_seconds))
    ]


@pytest.fixture
def stub_backend(monkeypatch):
    monkeypatch.setattr(local_tts_client, "ensure_daemon", lambda backend: None)
    monkeypatch.setattr(local_tts_client, "_post_speech", lambda **kwargs: make_wav(1.0))
    monkeypatch.setattr(local_tts_client, "_wav_to_mp3", lambda data, trim=0.0: b"ID3FAKEMP3")
    # Without this every run inserts api_usage rows into the real data/db.sqlite.
    monkeypatch.setattr(local_tts_client, "record_usage", lambda **kwargs: None)
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
        lambda **kwargs: captured.update(kwargs) or make_wav(1.0),
    )
    local_tts_client.generate_speech(text="hi", voice_id="af_heart")
    assert captured["model"] == REGISTRY["kokoro-82m"].weights
    assert captured["voice"] == REGISTRY["kokoro-82m"].default_voice
    assert captured["text"] == "hi"


def test_cloud_voice_id_is_not_forwarded_to_the_local_engine(stub_backend, monkeypatch):
    """ElevenLabs voice ids belong to a different namespace and must not leak."""
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "higgs-tts-3-4b")
    monkeypatch.delenv("LOCAL_VOICE_ID", raising=False)
    captured: dict = {}
    monkeypatch.setattr(
        local_tts_client,
        "_post_speech",
        lambda **kwargs: captured.update(kwargs) or make_wav(1.0),
    )
    local_tts_client.generate_speech(text="hi", voice_id="21m00Tcm4TlvDq8ikWAM")
    assert captured["voice"] == REGISTRY["higgs-tts-3-4b"].default_voice


def test_local_voice_id_override_is_used(stub_backend, monkeypatch):
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")
    monkeypatch.setenv("LOCAL_VOICE_ID", "af_bella")
    captured: dict = {}
    monkeypatch.setattr(
        local_tts_client,
        "_post_speech",
        lambda **kwargs: captured.update(kwargs) or make_wav(1.0),
    )
    local_tts_client.generate_speech(text="hi", voice_id="ignored")
    assert captured["voice"] == "af_bella"


def test_speed_from_voice_settings_is_forwarded(stub_backend, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        local_tts_client,
        "_post_speech",
        lambda **kwargs: captured.update(kwargs) or make_wav(1.0),
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


class TestRunawayGeneration:
    """Higgs answers a short sentence with its full ~47.8s budget often enough
    that one draw is not a sample. See pipeline/speech_validation.py."""

    def five_word_text(self) -> str:
        return "one two three four five"

    def test_trailing_junk_is_trimmed_off(self, stub_backend, monkeypatch):
        trims: list[float] = []
        monkeypatch.setattr(local_tts_client, "_post_speech", lambda **kwargs: make_wav(47.75))
        monkeypatch.setattr(local_tts_client, "align_audio", lambda path, text: alignment(1.0, 2.0, 3.0, 4.0, 4.9))
        monkeypatch.setattr(
            local_tts_client,
            "_wav_to_mp3",
            lambda data, trim=0.0: trims.append(trim) or b"ID3FAKEMP3",
        )
        local_tts_client.generate_speech(text=self.five_word_text(), voice_id="narrator")
        assert trims == [pytest.approx(5.25, abs=0.01)]

    def test_clean_audio_is_not_trimmed(self, stub_backend, monkeypatch):
        trims: list[float] = []
        monkeypatch.setattr(local_tts_client, "_post_speech", lambda **kwargs: make_wav(5.0))
        monkeypatch.setattr(local_tts_client, "align_audio", lambda path, text: alignment(1.0, 2.0, 3.0, 4.0, 4.9))
        monkeypatch.setattr(
            local_tts_client,
            "_wav_to_mp3",
            lambda data, trim=0.0: trims.append(trim) or b"ID3FAKEMP3",
        )
        local_tts_client.generate_speech(text=self.five_word_text(), voice_id="narrator")
        assert trims == [0.0]

    def test_runaway_is_resampled_and_a_good_draw_is_kept(self, stub_backend, monkeypatch):
        # First draw loops for 47.75s; the retry behaves.
        draws = [make_wav(47.75), make_wav(4.0)]
        alignments = [alignment(*[i * 9.5 for i in range(1, 6)]), alignment(1.0, 2.0, 3.0, 3.5, 3.9)]
        monkeypatch.setattr(local_tts_client, "_post_speech", lambda **kwargs: draws.pop(0))
        monkeypatch.setattr(local_tts_client, "align_audio", lambda path, text: alignments.pop(0))
        audio, words = local_tts_client.generate_speech(text=self.five_word_text(), voice_id="narrator")
        assert audio == b"ID3FAKEMP3"
        assert len(words) == 5
        assert draws == []

    def test_persistent_runaway_raises_rather_than_shipping_dead_air(self, stub_backend, monkeypatch):
        calls: list[int] = []

        def always_runaway(**kwargs):
            calls.append(1)
            return make_wav(47.75)

        monkeypatch.setattr(local_tts_client, "_post_speech", always_runaway)
        monkeypatch.setattr(
            local_tts_client,
            "align_audio",
            lambda path, text: alignment(*[i * 9.5 for i in range(1, 6)]),
        )
        with pytest.raises(local_tts_client.LocalSpeechRunawayError, match="all 3 attempts"):
            local_tts_client.generate_speech(text=self.five_word_text(), voice_id="narrator")
        assert len(calls) == local_tts_client.GENERATION_ATTEMPTS

    def test_runaway_error_names_the_remedy(self, stub_backend, monkeypatch):
        monkeypatch.setattr(local_tts_client, "_post_speech", lambda **kwargs: make_wav(47.75))
        monkeypatch.setattr(
            local_tts_client,
            "align_audio",
            lambda path, text: alignment(*[i * 9.5 for i in range(1, 6)]),
        )
        with pytest.raises(local_tts_client.LocalSpeechRunawayError, match="Voice to Cloud"):
            local_tts_client.generate_speech(text=self.five_word_text(), voice_id="narrator")

    def test_unparseable_wav_header_does_not_block_generation(self, stub_backend, monkeypatch):
        """A header quirk must degrade to 'length unknown', not fail the scene."""
        monkeypatch.setattr(local_tts_client, "_post_speech", lambda **kwargs: b"RIFFnotreallyawav")
        audio, _ = local_tts_client.generate_speech(text=self.five_word_text(), voice_id="narrator")
        assert audio == b"ID3FAKEMP3"
