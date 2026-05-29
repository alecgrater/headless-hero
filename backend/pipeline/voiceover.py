"""Voiceover pipeline — connects narration text to ElevenLabs TTS."""

import logging
import os
import re
import statistics
import struct
from concurrent.futures import ThreadPoolExecutor

from config import DATA_DIR, DEFAULT_TTS_MODEL
from integrations.elevenlabs_client import generate_speech

logger = logging.getLogger(__name__)

_TITLE_CARD_LEVEL_PREFIX_RE = re.compile(
    r"^level\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b[\s,.:;!?\-—–]*",
    re.IGNORECASE,
)
_LEVEL_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_V3_SAFE_AUDIO_TAGS = {"[serious]", "[thoughtful]", "[curious]", "[confident]", "[reflective]"}
_AUDIO_TAG_WORD_RE = re.compile(r"^\[[^\]]+\][,.;:!?]*$")


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using %.2f", name, raw, default)
        return default
    if value < minimum or value > maximum:
        logger.warning("Out-of-range %s=%r; using %.2f", name, raw, default)
        return default
    return value


def resolve_tts_model_and_settings(
    model_id: str | None,
    voice_settings: dict | None,
) -> tuple[str, dict | None]:
    """Resolve explicit request overrides or saved ElevenLabs TTS defaults."""
    if model_id:
        return model_id, voice_settings

    resolved_model = (os.environ.get("ELEVENLABS_TTS_MODEL") or DEFAULT_TTS_MODEL).strip() or DEFAULT_TTS_MODEL
    resolved_settings = {
        "stability": _env_float("ELEVENLABS_STABILITY", 0.5, 0.0, 1.0),
        "style": _env_float("ELEVENLABS_STYLE", 0.0, 0.0, 1.0),
        "speed": _env_float("ELEVENLABS_SPEED", 1.0, 0.7, 1.2),
    }
    return resolved_model, resolved_settings


def select_v3_audio_tag(narration: str) -> str:
    """Choose a conservative Eleven v3 delivery tag from narration cues."""
    text = narration.lower()
    serious_terms = (
        "dark",
        "burned",
        "collapsed",
        "collapse",
        "failed",
        "death",
        "war",
        "danger",
        "worse",
        "crisis",
    )
    curious_terms = ("why", "how", "what if", "strangest", "mystery", "question", "?")
    confident_terms = ("that is", "this is", "here's", "the truth", "the answer", "the point")
    reflective_terms = ("generation by generation", "slowly", "quiet", "normal", "remember", "sometimes")

    if any(term in text for term in serious_terms):
        return "[serious]"
    if any(term in text for term in curious_terms):
        return "[curious]"
    if any(term in text for term in confident_terms):
        return "[confident]"
    if any(term in text for term in reflective_terms):
        return "[reflective]"
    return "[thoughtful]"


def add_v3_audio_tags(narration: str) -> str:
    """Add a light hidden Eleven v3 direction tag without changing subtitles."""
    text = narration.strip()
    if not text or text.startswith("["):
        return narration
    tag = select_v3_audio_tag(text)
    if tag not in _V3_SAFE_AUDIO_TAGS:
        tag = "[thoughtful]"
    return f"{tag} {text}"


def prepare_tts_text(
    narration: str,
    *,
    model_id: str,
    is_title_card: bool = False,
    level_number: int | None = None,
) -> str:
    """Prepare hidden TTS-only text while keeping stored narration untouched."""
    text = narration
    if is_title_card and level_number is not None:
        return frame_title_card_for_tts(narration, level_number)
    if model_id == "eleven_v3":
        text = add_v3_audio_tags(text)
    return text


def strip_tts_audio_tag_words(word_timestamps: list[dict]) -> list[dict]:
    """Remove inline audio tags from display-facing word timestamps."""
    cleaned: list[dict] = []
    for word in word_timestamps:
        value = str(word.get("word", ""))
        if _AUDIO_TAG_WORD_RE.match(value.strip()):
            continue
        cleaned.append(word)
    return cleaned

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

def frame_title_card_for_tts(narration: str, level_number: int) -> str:
    """Wrap a title card scene's narration with 'Level N — ' framing for TTS only.

    Bare titles like 'Confidence' get voiced as awkward fragments — adding a
    framing prefix and terminal period gives ElevenLabs heading-style intonation.
    The script's stored narration is unchanged; only the TTS input is reframed.
    """
    cleaned = narration.strip().rstrip(".!?,;:—-").strip()
    if not cleaned:
        return narration
    match = _TITLE_CARD_LEVEL_PREFIX_RE.match(cleaned)
    if match:
        label = match.group(1).lower()
        parsed_level = int(label) if label.isdigit() else _LEVEL_WORDS[label]
        if parsed_level == level_number:
            return f"{cleaned}."
    return f"Level {level_number} — {cleaned}."


def compute_phrase_timestamps(word_timestamps: list[dict]) -> list[dict]:
    """Group word timestamps into phrase-level intervals for smooth mouth animation.

    Uses an adaptive threshold: median inter-word gap × 3, clamped [200ms, 800ms].
    """
    if not word_timestamps:
        return []
    if len(word_timestamps) == 1:
        return [{"start_ms": word_timestamps[0]["start_ms"], "end_ms": word_timestamps[0]["end_ms"]}]

    gaps = []
    for i in range(len(word_timestamps) - 1):
        gap = word_timestamps[i + 1]["start_ms"] - word_timestamps[i]["end_ms"]
        gaps.append(gap)

    median_gap = statistics.median(gaps) if gaps else 0
    threshold = max(200, min(800, median_gap * 3))

    phrases: list[dict] = []
    phrase_start = word_timestamps[0]["start_ms"]
    phrase_end = word_timestamps[0]["end_ms"]

    for i in range(len(word_timestamps) - 1):
        gap = word_timestamps[i + 1]["start_ms"] - word_timestamps[i]["end_ms"]
        if gap >= threshold:
            phrases.append({"start_ms": phrase_start, "end_ms": phrase_end})
            phrase_start = word_timestamps[i + 1]["start_ms"]
        phrase_end = word_timestamps[i + 1]["end_ms"]

    phrases.append({"start_ms": phrase_start, "end_ms": phrase_end})
    return phrases


def generate_scene_audio(
    scene_id: str,
    narration: str,
    voice_id: str,
    script_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> tuple[str, float, list[dict], list[dict]]:
    """Generate TTS audio for a single scene and save locally.

    Returns (web-relative path, duration in seconds, word_timestamps, phrase_timestamps).
    """
    logger.info("Generating audio for scene %s (script=%s, voice=%s, model=%s, chars=%d)", scene_id, script_id, voice_id, model_id, len(narration))
    audio_bytes, word_timestamps = generate_speech(
        text=narration,
        voice_id=voice_id,
        model_id=model_id,
        voice_settings=voice_settings,
        script_id=script_id,
    )
    word_timestamps = strip_tts_audio_tag_words(word_timestamps)

    # Save to local storage
    audio_dir = DATA_DIR / "projects" / script_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    local_path = audio_dir / f"{scene_id}.mp3"
    local_path.write_bytes(audio_bytes)

    # Prefer ElevenLabs-reported duration (last word end_ms) as it's more accurate
    # than MP3 frame parsing. Fall back to MP3 parsing if timestamps are unavailable.
    if word_timestamps:
        last_end_ms = word_timestamps[-1].get("end_ms", 0)
        if last_end_ms > 0:
            duration = round(last_end_ms / 1000, 3)
            logger.info(
                "Audio generated for scene %s: %.3fs duration (from ElevenLabs timestamps)",
                scene_id, duration,
            )
        else:
            duration = _mp3_duration_seconds(audio_bytes)
            logger.info(
                "Audio generated for scene %s: %.2fs duration (from MP3 frames, timestamps had no end_ms)",
                scene_id, duration,
            )
    else:
        duration = _mp3_duration_seconds(audio_bytes)
        logger.info(
            "Audio generated for scene %s: %.2fs duration (from MP3 frames, no timestamps)",
            scene_id, duration,
        )

    web_path = f"/static/projects/{script_id}/audio/{scene_id}.mp3"
    phrase_timestamps = compute_phrase_timestamps(word_timestamps) if word_timestamps else []
    return web_path, duration, word_timestamps, phrase_timestamps

def _generate_one_audio(
    scene: dict[str, str],
    voice_id: str,
    script_id: str,
    model_id: str,
    voice_settings: dict | None,
) -> dict:
    try:
        audio_url, duration, word_timestamps, phrase_timestamps = generate_scene_audio(
            scene_id=scene["scene_id"],
            narration=scene["narration"],
            voice_id=voice_id,
            script_id=script_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )
        return {
            "scene_id": scene["scene_id"],
            "audio_url": audio_url,
            "duration_seconds": duration,
            "word_timestamps": word_timestamps,
            "phrase_timestamps": phrase_timestamps,
            "error": None,
        }
    except Exception as exc:
        logger.exception("Audio generation failed for scene %s", scene["scene_id"])
        return {
            "scene_id": scene["scene_id"],
            "audio_url": None,
            "duration_seconds": None,
            "error": str(exc),
        }


def generate_batch_audio(
    scenes: list[dict[str, str]],
    voice_id: str,
    script_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> list[dict[str, str | None]]:
    """Generate TTS audio for a list of scenes with bounded concurrency.

    Each scene dict must have 'scene_id' and 'narration'.
    Returns list of {scene_id, audio_url, duration_seconds, error?} preserving
    input order. Concurrency is tunable via HH_TTS_CONCURRENCY (default 4).
    """
    try:
        max_workers = max(1, int(os.environ.get("HH_TTS_CONCURRENCY", "4")))
    except ValueError:
        max_workers = 4
    max_workers = min(max_workers, max(1, len(scenes)))

    logger.info(
        "Starting batch audio generation for %d scenes (script=%s, voice=%s, max_workers=%d)",
        len(scenes), script_id, voice_id, max_workers,
    )
    results: list[dict | None] = [None] * len(scenes)
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tts") as pool:
        futures = {
            pool.submit(_generate_one_audio, scene, voice_id, script_id, model_id, voice_settings): idx
            for idx, scene in enumerate(scenes)
        }
        for fut in futures:
            idx = futures[fut]
            results[idx] = fut.result()

    final_results: list[dict] = [r for r in results if r is not None]
    succeeded = sum(1 for r in final_results if r["error"] is None)
    logger.info("Batch audio complete: %d/%d succeeded (script %s)", succeeded, len(scenes), script_id)
    return final_results
