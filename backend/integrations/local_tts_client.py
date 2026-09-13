"""Local text-to-speech through an mlx-audio server.

Returns exactly what elevenlabs_client.generate_speech returns — MP3 bytes and
word-level timestamps — so pipeline.voiceover and everything downstream are
unchanged. mlx-audio emits WAV and no timestamps, so this module transcodes
with ffmpeg and reuses the faster-whisper aligner the project already ships.
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from integrations.local_models import active_model, local_voice_id
from integrations.usage_tracker import record_usage
from pipeline.audio_alignment import align_audio
from pipeline.local_runtime import daemon_url, ensure_daemon, hold

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 600.0


def _post_speech(*, model: str, voice: str, text: str, speed: float, timeout: float) -> bytes:
    """Call the mlx-audio OpenAI-compatible speech endpoint and return WAV bytes."""
    response = httpx.post(
        f"{daemon_url('mlx-audio')}/v1/audio/speech",
        json={
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": "wav",
            "speed": speed,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.content


def _wav_to_mp3(wav_bytes: bytes) -> bytes:
    """Transcode WAV to MP3 with ffmpeg, matching the ElevenLabs output format."""
    process = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "wav", "-i", "pipe:0",
            "-codec:a", "libmp3lame", "-b:a", "128k", "-ar", "44100",
            "-f", "mp3", "pipe:1",
        ],
        input=wav_bytes,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed to transcode local TTS audio: {process.stderr.decode(errors='replace')[:400]}"
        )
    return process.stdout


def generate_speech(
    text: str,
    voice_id: str,
    model_id: str = "",
    output_format: str = "mp3_44100_128",
    voice_settings: dict | None = None,
    script_id: str | None = None,
) -> tuple[bytes, list[dict]]:
    """Generate speech locally and return (MP3 bytes, word_timestamps).

    model_id and output_format exist for signature parity with the ElevenLabs
    client. The local engine is chosen by LOCAL_VOICE_MODEL, and output is
    always MP3 44.1 kHz 128 kbps.
    """
    ensure_daemon("mlx-audio")
    clean_text = (text or "").strip()
    if not clean_text:
        return b"", []

    model = active_model("voice")
    # voice_id arrives from the ElevenLabs voice picker and belongs to a
    # different namespace entirely, so it is deliberately not forwarded. The
    # local voice comes from LOCAL_VOICE_ID or the model's default.
    local_voice = local_voice_id()
    speed = float((voice_settings or {}).get("speed", 1.0))
    timeout = float(os.environ.get("LOCAL_TTS_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))

    if voice_id and voice_id != local_voice:
        logger.debug(
            "Ignoring cloud voice id %r for local TTS; using %r on %s",
            voice_id, local_voice, model.id,
        )

    logger.info(
        "Calling local TTS model=%s voice=%s chars=%d",
        model.id, local_voice, len(clean_text),
    )
    started = time.monotonic()

    with hold("voice"):
        wav_bytes = _post_speech(
            model=model.weights,
            voice=local_voice,
            text=clean_text,
            speed=speed,
            timeout=timeout,
        )

    mp3_bytes = _wav_to_mp3(wav_bytes)

    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.write(wav_bytes)
    handle.close()
    wav_path = Path(handle.name)
    try:
        word_timestamps = align_audio(wav_path, clean_text)
    finally:
        wav_path.unlink(missing_ok=True)

    if not word_timestamps:
        logger.warning("Local alignment produced no word timestamps for a %d-char scene", len(clean_text))

    elapsed = time.monotonic() - started
    record_usage(
        service="local_voice",
        operation="tts",
        model=model.id,
        characters=len(clean_text),
        cost_estimate=0.0,
        script_id=script_id,
    )
    logger.info(
        "Local TTS complete in %.1fs — %d bytes MP3, %d words (model=%s)",
        elapsed, len(mp3_bytes), len(word_timestamps), model.id,
    )
    return mp3_bytes, word_timestamps
