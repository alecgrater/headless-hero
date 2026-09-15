"""Length sanity checks for locally generated speech.

Cloud TTS returns audio whose length matches the text it was handed. Local
engines do not. Higgs TTS 3 has a hard generation ceiling (~47.8s) and will
spend all of it on a six-word sentence in one of two ways: it finishes the
utterance and then emits noise until the budget runs out, or it loops the
narration until the budget runs out. Both shipped in the same video.

Scene audio duration is the render's timing source of truth, so neither failure
stays inside the audio stage — a six-word scene with 47.8s of audio becomes 47.8
seconds of a frozen frame in the finished MP4. The two cases need different
handling, and forced alignment already tells us which one we have:

  * alignment ends well before the audio does  → trailing junk, trim it off
  * alignment spans audio far longer than the words justify → runaway, resample

Pure functions, no I/O — the caller owns the audio bytes and the retry loop.
"""

from dataclasses import dataclass
from typing import Literal

# Measured narration across a finished 75-scene video runs ~395 ms/word at the
# median and ~510 ms/word for the slowest dramatic single-word beats. 1.1 s/word
# is therefore roughly double the slowest legitimate pace: generous enough that
# normal speech is never resampled, tight enough that a runaway is unambiguous.
PLAUSIBLE_SECONDS_PER_WORD = 1.1

# Flat headroom so very short scenes aren't judged on a razor-thin budget — a
# one-word scene with a long dramatic pause is legitimate.
DURATION_HEADROOM_SECONDS = 3.0

# Trailing audio beyond the last aligned word that we accept as natural decay.
# Real trailing silence on a clean utterance is a few hundred ms; two seconds is
# already generous, and beyond it the tail is junk rather than breathing room.
TRAILING_SILENCE_SLACK_SECONDS = 2.0

# Kept after the last aligned word when trimming, so the final consonant and its
# natural decay survive the cut.
TRAILING_TAIL_SECONDS = 0.35

Status = Literal["ok", "trim", "runaway"]


@dataclass(frozen=True)
class SpeechLengthVerdict:
    """What to do with one generated clip.

    `trim_to_seconds` is meaningful only for `status == "trim"`.
    """

    status: Status
    trim_to_seconds: float = 0.0
    reason: str = ""

    @property
    def is_usable(self) -> bool:
        return self.status != "runaway"


def plausible_speech_seconds(word_count: int) -> float:
    """Longest runtime a clip of `word_count` words can credibly need."""
    if word_count <= 0:
        return DURATION_HEADROOM_SECONDS
    return word_count * PLAUSIBLE_SECONDS_PER_WORD + DURATION_HEADROOM_SECONDS


def evaluate_speech_length(
    *,
    word_count: int,
    audio_seconds: float,
    spoken_end_seconds: float,
) -> SpeechLengthVerdict:
    """Classify a generated clip as usable, trimmable, or a runaway.

    `spoken_end_seconds` is the end of the last aligned word. Pass 0 when
    alignment produced nothing — the trailing-junk case is then undetectable and
    only the runaway ceiling applies.
    """
    if audio_seconds <= 0 or word_count <= 0:
        return SpeechLengthVerdict("ok")

    ceiling = plausible_speech_seconds(word_count)
    effective_seconds = audio_seconds
    trim_to = 0.0

    if spoken_end_seconds > 0 and audio_seconds - spoken_end_seconds > TRAILING_SILENCE_SLACK_SECONDS:
        trim_to = min(spoken_end_seconds + TRAILING_TAIL_SECONDS, audio_seconds)
        effective_seconds = trim_to

    if effective_seconds > ceiling:
        return SpeechLengthVerdict(
            "runaway",
            reason=(
                f"{word_count} words produced {audio_seconds:.1f}s of speech "
                f"(plausible ceiling {ceiling:.1f}s); the engine looped or stalled"
            ),
        )

    if trim_to > 0:
        return SpeechLengthVerdict(
            "trim",
            trim_to_seconds=round(trim_to, 3),
            reason=(
                f"audio ran {audio_seconds:.1f}s but the last aligned word ends at "
                f"{spoken_end_seconds:.1f}s; trimming {audio_seconds - trim_to:.1f}s of trailing junk"
            ),
        )

    return SpeechLengthVerdict("ok")


def spoken_end_seconds(word_timestamps: list[dict]) -> float:
    """End of the last aligned word, in seconds. 0 when there is no alignment."""
    for entry in reversed(word_timestamps or []):
        end_ms = entry.get("end_ms") or 0
        if end_ms > 0:
            return end_ms / 1000
    return 0.0
