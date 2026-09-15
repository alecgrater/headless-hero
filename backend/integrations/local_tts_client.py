"""Local text-to-speech through an mlx-audio server.

Returns exactly what elevenlabs_client.generate_speech returns — MP3 bytes and
word-level timestamps — so pipeline.voiceover and everything downstream are
unchanged. mlx-audio emits WAV and no timestamps, so this module transcodes
with ffmpeg and reuses the faster-whisper aligner the project already ships.
"""

import io
import logging
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import httpx

from integrations.local_models import active_model, local_voice_id
from integrations.usage_tracker import record_usage
from pipeline.audio_alignment import align_audio
from pipeline.fallback_observability import record_fallback
from pipeline.local_runtime import daemon_url, ensure_daemon, env_timeout, hold
from pipeline.speech_validation import evaluate_speech_length, spoken_end_seconds

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 600.0

# Higgs TTS 3 answers a short sentence with its full ~47.8s generation budget
# often enough that one attempt is not a sample. Three keeps a bad draw from
# costing the scene without turning a genuinely stuck model into a long stall.
GENERATION_ATTEMPTS = 3


class LocalSpeechRunawayError(RuntimeError):
    """The local engine could not produce audio matching the narration length."""


def _post_speech(*, model: str, voice: str, text: str, speed: float, timeout: float) -> bytes:
    """Call the mlx-audio OpenAI-compatible speech endpoint and return WAV bytes.

    trust_env=False because mlx-audio listens on loopback — an ambient
    corporate proxy setting must not be asked to relay 127.0.0.1 traffic.
    """
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
        trust_env=False,
    )
    response.raise_for_status()
    return response.content


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    """Duration of PCM WAV bytes, or 0 when the header can't be parsed.

    A zero here degrades to "length unknown", which disables the trailing-junk
    check but leaves generation working — never a hard failure on a header quirk.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as handle:
            rate = handle.getframerate()
            if rate <= 0:
                return 0.0
            return handle.getnframes() / float(rate)
    except (wave.Error, EOFError) as exc:
        logger.warning("Could not read local TTS WAV header (%s); skipping length checks", exc)
        return 0.0


def _wav_to_mp3(wav_bytes: bytes, trim_to_seconds: float = 0.0) -> bytes:
    """Transcode WAV to MP3 with ffmpeg, matching the ElevenLabs output format.

    `trim_to_seconds` caps the output length; 0 keeps the whole clip.
    """
    duration_args = ["-t", f"{trim_to_seconds:.3f}"] if trim_to_seconds > 0 else []
    process = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "wav", "-i", "pipe:0",
            *duration_args,
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


def _synthesize_once(
    *,
    model_weights: str,
    voice: str,
    text: str,
    speed: float,
    timeout: float,
) -> tuple[bytes, list[dict], float]:
    """One synthesis attempt: returns (WAV bytes, word_timestamps, audio_seconds)."""
    with hold("voice"):
        wav_bytes = _post_speech(
            model=model_weights,
            voice=voice,
            text=text,
            speed=speed,
            timeout=timeout,
        )

    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.write(wav_bytes)
    handle.close()
    wav_path = Path(handle.name)
    try:
        word_timestamps = align_audio(wav_path, text)
    finally:
        wav_path.unlink(missing_ok=True)

    return wav_bytes, word_timestamps, _wav_duration_seconds(wav_bytes)


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

    Raises LocalSpeechRunawayError when every attempt produced audio far longer
    than the narration justifies. Raising is deliberate: the alternatives are
    shipping dead air (invisible until someone watches the export) or silently
    finishing the scene on the cloud voice, which would change voices mid-video.
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
    timeout = env_timeout("LOCAL_TTS_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    word_count = len(clean_text.split())

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
    last_reason = ""

    for attempt in range(1, GENERATION_ATTEMPTS + 1):
        wav_bytes, word_timestamps, audio_seconds = _synthesize_once(
            model_weights=model.weights,
            voice=local_voice,
            text=clean_text,
            speed=speed,
            timeout=timeout,
        )

        if not word_timestamps:
            logger.warning("Local alignment produced no word timestamps for a %d-char scene", len(clean_text))

        verdict = evaluate_speech_length(
            word_count=word_count,
            audio_seconds=audio_seconds,
            spoken_end_seconds=spoken_end_seconds(word_timestamps),
        )

        if verdict.status == "runaway":
            last_reason = verdict.reason
            record_fallback(
                category="voiceover",
                event="local_tts_runaway_generation",
                reason=verdict.reason,
                to_value=f"attempt_{attempt}_of_{GENERATION_ATTEMPTS}",
                severity="warn" if attempt < GENERATION_ATTEMPTS else "error",
                script_id=script_id,
                metadata={"model": model.id, "word_count": word_count, "audio_seconds": round(audio_seconds, 2)},
                logger=logger,
            )
            continue

        if verdict.status == "trim":
            record_fallback(
                category="voiceover",
                event="local_tts_trailing_audio_trimmed",
                reason=verdict.reason,
                to_value=f"{verdict.trim_to_seconds:.2f}s",
                severity="warn",
                script_id=script_id,
                metadata={"model": model.id, "word_count": word_count, "audio_seconds": round(audio_seconds, 2)},
                logger=logger,
            )

        mp3_bytes = _wav_to_mp3(wav_bytes, verdict.trim_to_seconds)

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
            "Local TTS complete in %.1fs — %d bytes MP3, %d words, %s (model=%s, attempt %d)",
            elapsed, len(mp3_bytes), len(word_timestamps), verdict.status, model.id, attempt,
        )
        return mp3_bytes, word_timestamps

    raise LocalSpeechRunawayError(
        f"Local TTS ({model.id}) returned unusable audio on all {GENERATION_ATTEMPTS} attempts: "
        f"{last_reason}. Regenerate this scene, or set Settings → Local Models → Voice to Cloud."
    )
