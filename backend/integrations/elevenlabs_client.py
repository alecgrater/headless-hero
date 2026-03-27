"""Thin wrapper around the ElevenLabs API for text-to-speech."""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

import httpx


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


def _headers() -> Dict[str, str]:
    return {
        "xi-api-key": _get_key(),
        "Accept": "application/json",
    }


def generate_speech(
    text: str,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
) -> bytes:
    """Generate speech audio bytes from text using ElevenLabs TTS.

    Returns raw audio bytes (MP3).
    """
    url = f"{_BASE_URL}/text-to-speech/{voice_id}"

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": _DEFAULT_VOICE_SETTINGS,
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            url,
            json=payload,
            headers={
                "xi-api-key": _get_key(),
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            params={"output_format": output_format},
        )
        response.raise_for_status()
        return response.content


def list_voices() -> List[Dict[str, str]]:
    """List available voices from ElevenLabs.

    Returns list of {voice_id, name, category} dicts.
    """
    url = f"{_BASE_URL}/voices"

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers=_headers())
        response.raise_for_status()
        data = response.json()

    voices = []  # type: List[Dict[str, str]]
    for v in data.get("voices", []):
        voices.append({
            "voice_id": v["voice_id"],
            "name": v["name"],
            "category": v.get("category", ""),
        })
    return voices
