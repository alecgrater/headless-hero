"""Tests for short_form_intros pipeline helpers."""

import pytest

from pipeline.short_form_intros import build_display_text, strip_leading_number


class TestStripLeadingNumber:
    def test_strips_single_digit_and_space(self):
        assert strip_leading_number("8 Unsolved Crimes") == "Unsolved Crimes"

    def test_strips_multi_digit_and_space(self):
        assert strip_leading_number("123 Things to Know") == "Things to Know"

    def test_no_leading_number_unchanged(self):
        assert strip_leading_number("How to Train Your Dragon") == "How to Train Your Dragon"

    def test_digit_without_space_unchanged(self):
        assert strip_leading_number("8Track Memories") == "8Track Memories"

    def test_empty_string(self):
        assert strip_leading_number("") == ""

    def test_only_a_number(self):
        # "8" with no following space is left alone (no whitespace match)
        assert strip_leading_number("8") == "8"

    def test_multiple_leading_whitespace(self):
        # Regex requires \s+ after digits, so multiple spaces also collapse
        assert strip_leading_number("8   Spaced Out") == "Spaced Out"


class TestBuildDisplayText:
    def test_combines_stripped_title_and_segment_with_em_dash(self):
        result = build_display_text(
            video_title="8 Unsolved Crimes That Still Baffle Detectives to This Day",
            segment_name="The Isdal Woman",
        )
        assert result == "Unsolved Crimes That Still Baffle Detectives to This Day — The Isdal Woman"

    def test_title_without_leading_number_passes_through(self):
        result = build_display_text(
            video_title="How to Train Your Dragon",
            segment_name="Toothless",
        )
        assert result == "How to Train Your Dragon — Toothless"

    def test_empty_segment_name_still_emits_em_dash(self):
        # Edge case: segment_name should never be empty in practice but be defensive
        result = build_display_text(video_title="8 Foo", segment_name="")
        assert result == "Foo — "
