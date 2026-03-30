"""Thin wrapper around the ElevenLabs API for text-to-speech."""

import base64
import logging
import os

import httpx

from config import DEFAULT_TTS_MODEL

log = logging.getLogger(__name__)

_BASE_URL = "https://api.elevenlabs.io/v1"

# Default voice settings — natural speech, moderate stability
_DEFAULT_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}

def _get_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set. "
            "Export it in your shell or add it to the app settings."
        )
    return key

def _headers() -> dict[str, str]:
    return {
        "xi-api-key": _get_key(),
        "Accept": "application/json",
    }

def _reconstruct_words(
    characters: list[str],
    start_times: list[float],
    end_times: list[float],
) -> list[dict]:
    """Reconstruct word-level timestamps from character-level alignment data.

    Groups characters between whitespace boundaries into words.
    Returns list of {word, start_ms, end_ms}.
    """
    words: list[dict] = []
    current_chars: list[str] = []
    word_start: float | None = None

    for i, char in enumerate(characters):
        if char.isspace():
            if current_chars and word_start is not None:
                words.append({
                    "word": "".join(current_chars),
                    "start_ms": round(word_start * 1000),
                    "end_ms": round(end_times[i - 1] * 1000),
                })
                current_chars = []
                word_start = None
        else:
            if word_start is None:
                word_start = start_times[i]
            current_chars.append(char)

    # Flush last word
    if current_chars and word_start is not None:
        words.append({
            "word": "".join(current_chars),
            "start_ms": round(word_start * 1000),
            "end_ms": round(end_times[len(characters) - 1] * 1000),
        })

    return words

def generate_speech(
    text: str,
    voice_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    output_format: str = "mp3_44100_128",
    voice_settings: dict | None = None,
) -> tuple[bytes, list[dict]]:
    """Generate speech audio bytes from text using ElevenLabs TTS with timestamps.

    Returns (raw audio bytes MP3, word_timestamps [{word, start_ms, end_ms}]).
    """
    url = f"{_BASE_URL}/text-to-speech/{voice_id}/with-timestamps"

    effective_settings = {**_DEFAULT_VOICE_SETTINGS}
    if voice_settings:
        effective_settings.update(voice_settings)

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": effective_settings,
        "output_format": output_format,
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            url,
            json=payload,
            headers={
                "xi-api-key": _get_key(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

    audio_bytes = base64.b64decode(data["audio_base64"])

    alignment = data.get("alignment", {})
    characters = alignment.get("characters", [])
    char_starts = alignment.get("character_start_times_seconds", [])
    char_ends = alignment.get("character_end_times_seconds", [])

    if characters and char_starts and char_ends:
        word_timestamps = _reconstruct_words(characters, char_starts, char_ends)
    else:
        log.warning("No alignment data returned from ElevenLabs — word timestamps unavailable")
        word_timestamps = []

    return audio_bytes, word_timestamps

def clone_voice(
    name: str,
    audio_files: list[tuple[str, bytes]],
    description: str = "",
) -> str:
    """Clone a voice by uploading audio samples to ElevenLabs.

    Args:
        name: Name for the cloned voice.
        audio_files: list of (filename, file_bytes) tuples.
        description: Optional description for the voice.

    Returns:
        The voice_id of the newly created cloned voice.
    """
    url = f"{_BASE_URL}/voices/add"

    files = [("files", (fname, fbytes, "audio/mpeg")) for fname, fbytes in audio_files]
    data = {"name": name, "description": description}

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            url,
            data=data,
            files=files,
            headers={"xi-api-key": _get_key()},
        )
        response.raise_for_status()
        return response.json()["voice_id"]

def list_voices() -> list[dict[str, str]]:
    """List available voices from ElevenLabs.

    Returns list of {voice_id, name, category} dicts.
    """
    url = f"{_BASE_URL}/voices"

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers=_headers())
        response.raise_for_status()
        data = response.json()

    voices: list[dict[str, str]] = []
    for v in data.get("voices", []):
        voices.append({
            "voice_id": v["voice_id"],
            "name": v["name"],
            "category": v.get("category", ""),
        })
    return voices
