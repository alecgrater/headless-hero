"""Tests for ElevenLabs voiceover model/settings and hidden TTS text."""

from api.settings import ALLOWED_KEYS, _DEFAULTS, _PLAINTEXT_KEYS
from pipeline.voiceover import (
    prepare_tts_text,
    resolve_tts_model_and_settings,
    strip_tts_audio_tag_words,
)


def test_elevenlabs_tts_settings_are_allowed_plaintext_and_defaulted():
    expected_defaults = {
        "ELEVENLABS_TTS_MODEL": "eleven_multilingual_v2",
        "ELEVENLABS_STABILITY": "0.5",
        "ELEVENLABS_STYLE": "0.0",
        "ELEVENLABS_SPEED": "1.0",
    }

    for key, default in expected_defaults.items():
        assert key in ALLOWED_KEYS
        assert key in _PLAINTEXT_KEYS
        assert _DEFAULTS[key] == default


def test_resolve_tts_model_and_settings_uses_saved_defaults(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_TTS_MODEL", "eleven_v3")
    monkeypatch.setenv("ELEVENLABS_STABILITY", "0.35")
    monkeypatch.setenv("ELEVENLABS_STYLE", "0.25")
    monkeypatch.setenv("ELEVENLABS_SPEED", "0.95")

    model_id, voice_settings = resolve_tts_model_and_settings(None, None)

    assert model_id == "eleven_v3"
    assert voice_settings == {
        "stability": 0.35,
        "style": 0.25,
        "speed": 0.95,
    }


def test_resolve_tts_model_and_settings_preserves_explicit_overrides(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_TTS_MODEL", "eleven_v3")
    monkeypatch.setenv("ELEVENLABS_STABILITY", "0.35")
    monkeypatch.setenv("ELEVENLABS_STYLE", "0.25")
    monkeypatch.setenv("ELEVENLABS_SPEED", "0.95")

    model_id, voice_settings = resolve_tts_model_and_settings(
        "eleven_turbo_v2_5",
        {"stability": 0.7, "similarity_boost": 0.8},
    )

    assert model_id == "eleven_turbo_v2_5"
    assert voice_settings == {"stability": 0.7, "similarity_boost": 0.8}


def test_prepare_tts_text_adds_v3_tags_without_touching_v2_text():
    narration = "The first lock failed. Then the whole vault opened."

    assert prepare_tts_text(narration, model_id="eleven_multilingual_v2") == narration

    tagged = prepare_tts_text(narration, model_id="eleven_v3")

    assert tagged.startswith("[curious] ")
    assert narration in tagged


def test_prepare_tts_text_keeps_title_card_level_framing_without_v3_tags():
    text = prepare_tts_text(
        "Confidence",
        model_id="eleven_v3",
        is_title_card=True,
        level_number=2,
    )

    assert text == "Level 2 — Confidence."


def test_strip_tts_audio_tag_words_removes_tags_from_display_timestamps():
    words = [
        {"word": "[curious]", "start_ms": 0, "end_ms": 100},
        {"word": "The", "start_ms": 120, "end_ms": 180},
        {"word": "vault", "start_ms": 190, "end_ms": 350},
        {"word": "[pause]", "start_ms": 360, "end_ms": 400},
        {"word": "opened.", "start_ms": 420, "end_ms": 650},
    ]

    assert strip_tts_audio_tag_words(words) == [
        {"word": "The", "start_ms": 120, "end_ms": 180},
        {"word": "vault", "start_ms": 190, "end_ms": 350},
        {"word": "opened.", "start_ms": 420, "end_ms": 650},
    ]
