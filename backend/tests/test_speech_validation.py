"""Length sanity checks for locally generated speech.

The numbers in test_real_export_failures are measured from the 75-scene export
that exposed the bug: Higgs TTS 3 answered short sentences with its full ~47.75s
generation budget, and the resulting durations went straight into the render as
scene lengths.
"""

import pytest

from pipeline.speech_validation import (
    PLAUSIBLE_SECONDS_PER_WORD,
    SpeechLengthVerdict,
    evaluate_speech_length,
    plausible_speech_seconds,
    spoken_end_seconds,
)


def verdict_for(word_count: int, audio: float, spoken: float) -> SpeechLengthVerdict:
    return evaluate_speech_length(
        word_count=word_count,
        audio_seconds=audio,
        spoken_end_seconds=spoken,
    )


class TestNormalSpeech:
    def test_typical_pace_is_untouched(self):
        # 20 words at the measured ~395 ms/word median.
        assert verdict_for(20, 7.9, 7.8).status == "ok"

    def test_slowest_legitimate_pace_is_untouched(self):
        # "Trophy." — one word, 510 ms, plus a dramatic pause.
        assert verdict_for(1, 2.4, 2.1).status == "ok"

    def test_short_trailing_silence_is_not_trimmed(self):
        # Under the slack threshold: natural decay, not junk.
        assert verdict_for(10, 5.0, 3.8).status == "ok"

    def test_empty_narration_is_ok(self):
        assert verdict_for(0, 47.8, 0.0).status == "ok"

    def test_missing_audio_is_ok(self):
        assert verdict_for(10, 0.0, 0.0).status == "ok"


class TestTrailingJunk:
    def test_trims_to_just_past_the_last_word(self):
        result = verdict_for(15, 47.75, 6.72)
        assert result.status == "trim"
        assert result.trim_to_seconds == pytest.approx(7.07, abs=0.01)

    def test_trim_never_exceeds_the_clip(self):
        result = verdict_for(10, 6.0, 5.9)
        assert result.trim_to_seconds <= 6.0

    def test_trim_reason_names_both_lengths(self):
        result = verdict_for(15, 47.75, 6.72)
        assert "47.8" in result.reason and "6.7" in result.reason

    def test_trimmed_clip_is_judged_on_its_trimmed_length(self):
        # 47.75s of audio would blow the ceiling, but the speech inside it is
        # a normal 6.7s — trimming resolves it, no resample needed.
        assert verdict_for(15, 47.75, 6.72).status == "trim"


class TestRunaway:
    def test_looping_generation_is_a_runaway(self):
        # Alignment spans nearly the whole clip: the engine really did keep
        # talking, so there is no junk tail to cut away.
        assert verdict_for(32, 47.75, 47.72).status == "runaway"

    def test_runaway_when_trimming_still_leaves_too_much(self):
        assert verdict_for(14, 47.75, 43.38).status == "runaway"

    def test_runaway_without_alignment(self):
        # No word timestamps at all — only the ceiling can catch it.
        assert verdict_for(6, 47.75, 0.0).status == "runaway"

    def test_runaway_reason_names_the_ceiling(self):
        result = verdict_for(6, 47.75, 47.7)
        assert "47.8" in result.reason and "ceiling" in result.reason

    def test_runaway_is_not_usable(self):
        assert verdict_for(6, 47.75, 47.7).is_usable is False
        assert verdict_for(20, 7.9, 7.8).is_usable is True


class TestRealExportFailures:
    """Every scene the shipped export got wrong, and every scene it got right."""

    # (scene, words, audio_seconds, alignment_end_seconds, expected status)
    BROKEN = [
        ("scene_002", 14, 47.75, 43.38, "runaway"),
        ("scene_011", 32, 47.75, 47.72, "runaway"),
        ("scene_029", 15, 47.75, 6.72, "trim"),
        ("scene_035", 16, 47.75, 47.70, "runaway"),
        ("scene_042", 11, 10.70, 5.80, "trim"),
        ("scene_059", 6, 47.75, 31.98, "runaway"),
        ("scene_061", 9, 23.20, 2.32, "trim"),
        ("scene_068", 35, 47.75, 31.98, "trim"),
    ]

    @pytest.mark.parametrize("scene,words,audio,spoken,expected", BROKEN)
    def test_every_broken_scene_is_caught(self, scene, words, audio, spoken, expected):
        assert verdict_for(words, audio, spoken).status == expected, scene

    def test_no_broken_scene_survives_as_ok(self):
        statuses = {verdict_for(w, a, s).status for _, w, a, s, _ in self.BROKEN}
        assert "ok" not in statuses

    def test_borderline_scenes_are_left_alone(self):
        # scene_025 and scene_016 are slow but real; resampling them would be a
        # false positive that costs minutes of local generation for nothing.
        assert verdict_for(8, 7.2, 6.6).status == "ok"
        assert verdict_for(26, 25.84, 25.78).status == "ok"


class TestCeiling:
    def test_scales_with_word_count(self):
        assert plausible_speech_seconds(10) < plausible_speech_seconds(20)

    def test_uses_the_configured_rate(self):
        assert plausible_speech_seconds(10) == pytest.approx(10 * PLAUSIBLE_SECONDS_PER_WORD + 3.0)

    def test_zero_words_still_allows_headroom(self):
        assert plausible_speech_seconds(0) > 0


class TestSpokenEnd:
    def test_reads_the_last_word(self):
        assert spoken_end_seconds([{"end_ms": 500}, {"end_ms": 1800}]) == pytest.approx(1.8)

    def test_skips_trailing_zero_entries(self):
        assert spoken_end_seconds([{"end_ms": 1800}, {"end_ms": 0}]) == pytest.approx(1.8)

    def test_empty_alignment_is_zero(self):
        assert spoken_end_seconds([]) == 0.0
        assert spoken_end_seconds(None) == 0.0
