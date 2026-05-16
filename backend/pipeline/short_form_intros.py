"""Short-form intro voiceover pipeline.

Generates per-segment intro voiceovers ("{stripped video title} — {segment name}")
via ElevenLabs and persists ShortIntro metadata into ScriptContent.short_intros.
"""

import logging
import re
from pathlib import Path

from config import DATA_DIR, DEFAULT_TTS_MODEL
from integrations.elevenlabs_client import generate_speech
from models.script import ScriptContent, ShortIntro
from pipeline.voiceover import _mp3_duration_seconds

logger = logging.getLogger(__name__)


def strip_leading_number(title: str) -> str:
    """Strip leading digit(s) followed by whitespace from a title.

    Examples:
        "8 Unsolved Crimes ..." -> "Unsolved Crimes ..."
        "How to Train Your Dragon" -> "How to Train Your Dragon"
        "8Track Memories" -> "8Track Memories"  (no following whitespace)
    """
    return re.sub(r"^\d+\s+", "", title)


def build_display_text(video_title: str, segment_name: str) -> str:
    """Build the display string spoken by Eli and rendered on the title card.

    Format: "{stripped video title} — {segment name}"
    The em-dash (U+2014) is the spoken/visual handoff between the two zones.
    """
    return f"{strip_leading_number(video_title)} — {segment_name}"


def is_stale(existing: ShortIntro, expected_display_text: str) -> bool:
    """Return True if a stored intro's display text no longer matches what would be generated."""
    return existing.display_text != expected_display_text


def _intro_audio_path(script_id: str, segment_idx: int) -> Path:
    """Filesystem path for a short-form intro audio file."""
    audio_dir = DATA_DIR / "projects" / script_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir / f"short_intro_{segment_idx}.mp3"


def generate_short_intro(
    script_id: str,
    segment_idx: int,
    display_text: str,
    voice_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> ShortIntro:
    """Generate a single intro voiceover via ElevenLabs and persist the MP3.

    Returns a fully populated ShortIntro (caller is responsible for writing it
    into ScriptContent.short_intros).
    """
    logger.info(
        "Generating short intro for script %s, segment %d (voice=%s, text=%r)",
        script_id, segment_idx, voice_id, display_text,
    )
    audio_bytes, word_timestamps = generate_speech(
        text=display_text,
        voice_id=voice_id,
        model_id=model_id,
        voice_settings=voice_settings,
        script_id=script_id,
    )

    audio_path = _intro_audio_path(script_id, segment_idx)
    audio_path.write_bytes(audio_bytes)

    if word_timestamps and word_timestamps[-1].get("end_ms", 0) > 0:
        duration = round(word_timestamps[-1]["end_ms"] / 1000, 3)
    else:
        duration = _mp3_duration_seconds(audio_bytes)

    web_url = f"/static/projects/{script_id}/audio/short_intro_{segment_idx}.mp3"
    return ShortIntro(
        segment_idx=segment_idx,
        display_text=display_text,
        audio_url=web_url,
        duration_seconds=duration,
        word_timestamps=word_timestamps or [],
    )


def generate_short_intros(
    script_id: str,
    content: ScriptContent,
    voice_id: str,
    force: bool = False,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
    on_progress=None,  # callable(idx, total, display_text) -> None
) -> list[ShortIntro]:
    """Generate intros for every segment in `content`.

    If `force` is False, skips segments whose existing ShortIntro is non-stale
    (display_text matches the current title/segment_name combination).
    Returns the full list of ShortIntros in segment order.
    """
    existing_map: dict[int, ShortIntro] = {}
    if content.short_intros:
        existing_map = {intro.segment_idx: intro for intro in content.short_intros}

    results: list[ShortIntro] = []
    total = len(content.segments)
    for idx, seg in enumerate(content.segments):
        display_text = build_display_text(content.title, seg.name)

        if on_progress:
            on_progress(idx, total, display_text)

        existing = existing_map.get(idx)
        if not force and existing and not is_stale(existing, display_text):
            logger.info("Short intro for segment %d is up-to-date — skipping", idx)
            results.append(existing)
            continue

        intro = generate_short_intro(
            script_id=script_id,
            segment_idx=idx,
            display_text=display_text,
            voice_id=voice_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )
        results.append(intro)

    return results
