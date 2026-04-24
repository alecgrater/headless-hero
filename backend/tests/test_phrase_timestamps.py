"""Tests for compute_phrase_timestamps in pipeline/voiceover.py."""

from pipeline.voiceover import compute_phrase_timestamps


class TestComputePhraseTimestamps:
    def test_empty_input(self):
        assert compute_phrase_timestamps([]) == []

    def test_single_word(self):
        words = [{"word": "Hello", "start_ms": 100, "end_ms": 400}]
        result = compute_phrase_timestamps(words)
        assert result == [{"start_ms": 100, "end_ms": 400}]

    def test_all_words_in_one_phrase(self):
        words = [
            {"word": "The", "start_ms": 0, "end_ms": 200},
            {"word": "quick", "start_ms": 230, "end_ms": 500},
            {"word": "brown", "start_ms": 530, "end_ms": 800},
            {"word": "fox", "start_ms": 830, "end_ms": 1100},
        ]
        result = compute_phrase_timestamps(words)
        assert len(result) == 1
        assert result[0] == {"start_ms": 0, "end_ms": 1100}

    def test_multi_phrase_split(self):
        words = [
            {"word": "Hello", "start_ms": 0, "end_ms": 300},
            {"word": "world", "start_ms": 340, "end_ms": 700},
            # 800ms gap — should split (well above any reasonable threshold)
            {"word": "How", "start_ms": 1500, "end_ms": 1800},
            {"word": "are", "start_ms": 1840, "end_ms": 2100},
            {"word": "you", "start_ms": 2140, "end_ms": 2400},
        ]
        result = compute_phrase_timestamps(words)
        assert len(result) == 2
        assert result[0] == {"start_ms": 0, "end_ms": 700}
        assert result[1] == {"start_ms": 1500, "end_ms": 2400}

    def test_threshold_clamp_lower_bound(self):
        """When median gap is tiny, threshold clamps to 200ms minimum."""
        words = [
            {"word": "a", "start_ms": 0, "end_ms": 100},
            {"word": "b", "start_ms": 110, "end_ms": 200},  # 10ms gap
            {"word": "c", "start_ms": 210, "end_ms": 300},  # 10ms gap
            # 250ms gap — above the clamped 200ms threshold
            {"word": "d", "start_ms": 550, "end_ms": 650},
        ]
        result = compute_phrase_timestamps(words)
        assert len(result) == 2
        assert result[0]["end_ms"] == 300
        assert result[1]["start_ms"] == 550

    def test_threshold_clamp_upper_bound(self):
        """When median gap is huge, threshold clamps to 800ms maximum."""
        words = [
            {"word": "a", "start_ms": 0, "end_ms": 100},
            {"word": "b", "start_ms": 1100, "end_ms": 1200},  # 1000ms gap
            {"word": "c", "start_ms": 2200, "end_ms": 2300},  # 1000ms gap
            # 700ms gap — below the clamped 800ms threshold, so same phrase
            {"word": "d", "start_ms": 3000, "end_ms": 3100},
        ]
        result = compute_phrase_timestamps(words)
        # median gap = 1000ms, threshold = min(800, 1000*3) = 800ms
        # gaps: 1000 >= 800 (split), 1000 >= 800 (split), 700 < 800 (same phrase)
        assert len(result) == 3
        assert result[0] == {"start_ms": 0, "end_ms": 100}
        assert result[1] == {"start_ms": 1100, "end_ms": 1200}
        assert result[2] == {"start_ms": 2200, "end_ms": 3100}

    def test_two_words_one_phrase(self):
        words = [
            {"word": "Hi", "start_ms": 0, "end_ms": 200},
            {"word": "there", "start_ms": 250, "end_ms": 500},
        ]
        result = compute_phrase_timestamps(words)
        assert len(result) == 1
        assert result[0] == {"start_ms": 0, "end_ms": 500}

    def test_two_words_split(self):
        """Two words with a huge gap should produce two phrases."""
        words = [
            {"word": "Yes", "start_ms": 0, "end_ms": 300},
            {"word": "No", "start_ms": 2000, "end_ms": 2300},
        ]
        result = compute_phrase_timestamps(words)
        # Single gap = 1700ms, median = 1700, threshold = min(800, 5100) = 800
        # 1700 >= 800 → split
        assert len(result) == 2
