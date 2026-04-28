"""Audio-to-text alignment using faster-whisper for word-level timestamps."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading faster-whisper 'small' model (first use)...")
        _model = WhisperModel("small", device="cpu", compute_type="int8")
        logger.info("faster-whisper model loaded")
    return _model


def align_audio(audio_path: Path, text: str) -> list[dict]:
    """Align audio file against reference text, returning word-level timestamps.

    Returns list of {word, start_ms, end_ms} matching ElevenLabs format.
    Falls back to even distribution if alignment fails.
    """
    words = text.split()
    if not words:
        return []

    try:
        model = _get_model()
        segments, _ = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
            initial_prompt=text,
        )

        timestamps: list[dict] = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    timestamps.append({
                        "word": w.word.strip(),
                        "start_ms": int(w.start * 1000),
                        "end_ms": int(w.end * 1000),
                    })

        if timestamps:
            logger.info("Aligned %d words from audio %s", len(timestamps), audio_path.name)
            return timestamps

        logger.warning("Whisper returned no word timestamps for %s, falling back to even distribution", audio_path.name)
    except Exception as exc:
        logger.exception("Whisper alignment failed for %s: %s", audio_path.name, exc)

    return _even_distribution(words, audio_path)


def _even_distribution(words: list[str], audio_path: Path) -> list[dict]:
    """Distribute words evenly across the audio duration as fallback."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=10,
        )
        duration_ms = int(float(result.stdout.strip()) * 1000)
    except Exception:
        duration_ms = len(words) * 430  # ~140 WPM fallback

    word_duration = duration_ms // len(words) if words else 0
    timestamps: list[dict] = []
    for i, word in enumerate(words):
        start = i * word_duration
        end = (i + 1) * word_duration
        timestamps.append({"word": word, "start_ms": start, "end_ms": end})
    return timestamps
