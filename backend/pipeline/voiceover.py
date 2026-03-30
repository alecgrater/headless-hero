"""Voiceover pipeline — connects narration text to ElevenLabs TTS."""

import logging
import struct

from config import DATA_DIR, DEFAULT_TTS_MODEL
from integrations.elevenlabs_client import generate_speech

logger = logging.getLogger(__name__)

def _mp3_duration_seconds(data: bytes) -> float:
    """Estimate MP3 duration from raw bytes using frame headers.

    Falls back to a rough byte-rate estimate if no valid frames found.
    """
    # Try to find MP3 frames and sum their durations
    bitrate_table = {
        # MPEG1 Layer3 bitrate index -> kbps
        1: 32, 2: 40, 3: 48, 4: 56, 5: 64, 6: 80, 7: 96,
        8: 112, 9: 128, 10: 160, 11: 192, 12: 224, 13: 256, 14: 320,
    }
    sample_rate_table = {0: 44100, 1: 48000, 2: 32000}

    total_frames = 0
    samples_per_frame = 1152  # MPEG1 Layer3
    sample_rate = 44100
    i = 0

    while i < len(data) - 4:
        # Look for frame sync (0xFF followed by 0xE0+ mask)
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            header = struct.unpack(">I", data[i : i + 4])[0]
            bitrate_idx = (header >> 12) & 0xF
            sr_idx = (header >> 10) & 0x3
            padding = (header >> 9) & 0x1

            if bitrate_idx in bitrate_table and sr_idx in sample_rate_table:
                bitrate = bitrate_table[bitrate_idx] * 1000
                sample_rate = sample_rate_table[sr_idx]
                frame_size = (samples_per_frame * bitrate // (8 * sample_rate)) + padding
                if frame_size > 0:
                    total_frames += 1
                    i += frame_size
                    continue
        i += 1

    if total_frames > 0:
        return round(total_frames * samples_per_frame / sample_rate, 2)

    # Fallback: assume 128kbps
    return round(len(data) / (128 * 1000 / 8), 2)

def generate_scene_audio(
    scene_id: str,
    narration: str,
    voice_id: str,
    script_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> tuple[str, float, list[dict]]:
    """Generate TTS audio for a single scene and save locally.

    Returns (web-relative path, duration in seconds, word_timestamps).
    """
    logger.info("Generating audio for scene %s (voice=%s, model=%s)", scene_id, voice_id, model_id)
    audio_bytes, word_timestamps = generate_speech(
        text=narration,
        voice_id=voice_id,
        model_id=model_id,
        voice_settings=voice_settings,
    )

    # Save to local storage
    audio_dir = DATA_DIR / "projects" / script_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    local_path = audio_dir / f"{scene_id}.mp3"
    local_path.write_bytes(audio_bytes)

    duration = _mp3_duration_seconds(audio_bytes)
    web_path = f"/static/projects/{script_id}/audio/{scene_id}.mp3"
    logger.info("Audio generated for scene %s: %.2fs duration", scene_id, duration)
    return web_path, duration, word_timestamps

def generate_batch_audio(
    scenes: list[dict[str, str]],
    voice_id: str,
    script_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> list[dict[str, str | None]]:
    """Generate TTS audio for a list of scenes sequentially.

    Each scene dict must have 'scene_id' and 'narration'.
    Returns list of {scene_id, audio_url, duration_seconds, error?}.
    """
    results: list[dict] = []
    logger.info("Starting batch audio generation for %s scenes (script %s)", len(scenes), script_id)
    for scene in scenes:
        try:
            audio_url, duration, word_timestamps = generate_scene_audio(
                scene_id=scene["scene_id"],
                narration=scene["narration"],
                voice_id=voice_id,
                script_id=script_id,
                model_id=model_id,
                voice_settings=voice_settings,
            )
            results.append({
                "scene_id": scene["scene_id"],
                "audio_url": audio_url,
                "duration_seconds": duration,
                "word_timestamps": word_timestamps,
                "error": None,
            })
        except Exception as exc:
            logger.exception("Audio generation failed for scene %s", scene["scene_id"])
            results.append({
                "scene_id": scene["scene_id"],
                "audio_url": None,
                "duration_seconds": None,
                "error": str(exc),
            })
    return results
