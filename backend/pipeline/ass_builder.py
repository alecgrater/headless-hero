"""ASS (Advanced SubStation Alpha) subtitle generator for modern animated subtitles.

Replaces drawtext-based subtitle rendering with ASS files that support:
- Word-by-word karaoke highlighting (\kf tags)
- Pop/bounce scale animations (\t transitions)
- Smooth fade in/out (\fad)
- Rounded-pill look via border blur (\be)
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Phrase:
    """A group of words displayed as a single subtitle line."""

    words: list[dict]  # [{word, start_ms, end_ms}, ...]
    start_ms: int = 0
    end_ms: int = 0
    text: str = ""

    def __post_init__(self) -> None:
        if self.words:
            self.start_ms = self.words[0]["start_ms"]
            self.end_ms = self.words[-1]["end_ms"]
            self.text = " ".join(w["word"] for w in self.words)


def _rgb_to_ass_color(hex_color: str) -> str:
    """Convert #RRGGBB to ASS &H00BBGGRR& format."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "00FFFF"  # fallback cyan
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"&H00{b:02X}{g:02X}{r:02X}&"


def _ms_to_ass_time(ms: int) -> str:
    """Convert milliseconds to ASS time format H:MM:SS.CC (centiseconds)."""
    if ms < 0:
        ms = 0
    total_cs = ms // 10
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    """Escape special characters for ASS dialogue text.

    ASS uses { } for override tags, so literal braces must be escaped.
    Backslashes that aren't part of override tags need escaping too.
    """
    # Replace literal braces with fullwidth equivalents (ASS has no proper escape)
    text = text.replace("{", "\uFF5B").replace("}", "\uFF5D")
    return text


def _group_into_phrases(
    word_timestamps: list[dict],
    max_words: int = 5,
    gap_threshold_ms: int = 300,
) -> list[Phrase]:
    """Group words into natural phrases for subtitle display.

    Break on:
    - Timing gaps > gap_threshold_ms between consecutive words
    - Punctuation boundaries (.,!?;:)
    - max_words limit
    """
    if not word_timestamps:
        return []

    phrases: list[Phrase] = []
    current_words: list[dict] = []

    for i, wt in enumerate(word_timestamps):
        current_words.append(wt)

        is_last = i == len(word_timestamps) - 1
        at_max = len(current_words) >= max_words

        # Check for timing gap to next word
        has_gap = False
        if not is_last:
            next_start = word_timestamps[i + 1]["start_ms"]
            this_end = wt["end_ms"]
            has_gap = (next_start - this_end) > gap_threshold_ms

        # Check for punctuation at end of word
        word_text = wt.get("word", "")
        has_punct = bool(re.search(r"[.!?;:]$", word_text))

        if is_last or at_max or has_gap or has_punct:
            phrases.append(Phrase(words=current_words))
            current_words = []

    return phrases


def _build_dialogue_line(
    phrase: Phrase,
    accent_color_ass: str,
    style_name: str = "Default",
) -> str:
    """Build an ASS Dialogue line with karaoke highlighting and pop animation.

    Uses:
    - \\kf{cs} for smooth word-by-word color fill (accent color sweeps each word)
    - \\t(0,150,\\fscx105\\fscy105)\\t(150,300,\\fscx100\\fscy100) for pop-in bounce
    - \\fad(100,100) for smooth fade in/out
    """
    start = _ms_to_ass_time(phrase.start_ms)
    end = _ms_to_ass_time(phrase.end_ms)

    # Build karaoke tags: \kf{duration_cs} before each word
    # \kf fills from secondary color to primary over duration
    parts: list[str] = []

    # Pop-in bounce + fade as prefix override
    parts.append(r"{\fad(100,100)\t(0,150,\fscx105\fscy105)\t(150,300,\fscx100\fscy100)}")

    for wt in phrase.words:
        word_text = _escape_ass_text(wt.get("word", "")).upper()
        duration_ms = wt["end_ms"] - wt["start_ms"]
        duration_cs = max(1, duration_ms // 10)  # centiseconds, min 1

        parts.append(rf"{{\kf{duration_cs}}}{word_text}")

    text = "".join(parts)

    # ASS Dialogue format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    return f"Dialogue: 0,{start},{end},{style_name},,0,0,0,,{text}"


def generate_ass_subtitles(
    word_timestamps: list[dict],
    duration: float,
    width: int,
    height: int,
    accent_color: str = "#00FFFF",
    mode: str = "landscape",
    output_path: str | None = None,
    font_name: str = "",
) -> str | None:
    """Generate an ASS subtitle file from word timestamps.

    Args:
        word_timestamps: List of {word, start_ms, end_ms} dicts from ElevenLabs TTS.
        duration: Total scene duration in seconds.
        width: Video width in pixels.
        height: Video height in pixels.
        accent_color: Hex color for karaoke highlight (e.g. "#00FFFF").
        mode: "landscape" (1920x1080) or "portrait" (1080x1920).
        output_path: Where to write the .ass file. If None, returns content as string.

    Returns:
        Path to the written .ass file, or None if no timestamps.
    """
    if not word_timestamps:
        return None

    phrases = _group_into_phrases(word_timestamps)
    if not phrases:
        return None

    accent_ass = _rgb_to_ass_color(accent_color)
    white_ass = "&H00FFFFFF&"
    black_ass = "&H00000000&"
    shadow_ass = "&H80000000&"  # 50% transparent black

    # Style parameters by mode
    if mode == "portrait":
        fontsize = 72
        alignment = 5  # \an5 = center screen
        margin_v = 0
    else:
        fontsize = 68
        alignment = 2  # \an2 = bottom center
        margin_v = 60

    # Use brand font if provided, otherwise fall back to Arial Black
    ass_font = font_name if font_name else "Arial Black"

    # Build ASS file content
    lines: list[str] = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        # Primary = white (final color after karaoke sweep)
        # Secondary = accent color (karaoke fill color that sweeps across)
        f"Style: Default,{ass_font},{fontsize},{white_ass},{accent_ass},{black_ass},{shadow_ass},"
        f"-1,0,0,0,100,100,0,0,1,4,2,{alignment},20,20,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for phrase in phrases:
        dialogue = _build_dialogue_line(phrase, accent_ass)
        lines.append(dialogue)

    content = "\n".join(lines) + "\n"

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(content, encoding="utf-8")
        return output_path
    else:
        return content


def generate_ass_for_scene(
    word_timestamps: list[dict],
    duration: float,
    width: int,
    height: int,
    accent_color: str,
    mode: str,
    renders_dir: str,
    scene_id: str,
    speed: float = 1.0,
    font_name: str = "",
) -> str | None:
    """Convenience wrapper: generate ASS for a scene, adjusting for speed, saving to renders dir.

    Returns path to .ass file, or None if no timestamps.
    """
    if not word_timestamps:
        return None

    # Adjust timestamps for speed
    if speed != 1.0 and speed > 0:
        adjusted = []
        for wt in word_timestamps:
            adjusted.append({
                "word": wt["word"],
                "start_ms": int(wt["start_ms"] / speed),
                "end_ms": int(wt["end_ms"] / speed),
            })
        word_timestamps = adjusted

    subdir = "autoedit_scenes"
    ass_path = str(Path(renders_dir) / subdir / f"{scene_id}.ass")

    return generate_ass_subtitles(
        word_timestamps=word_timestamps,
        duration=duration / speed if speed != 1.0 else duration,
        width=width,
        height=height,
        accent_color=accent_color,
        mode=mode,
        output_path=ass_path,
        font_name=font_name,
    )
