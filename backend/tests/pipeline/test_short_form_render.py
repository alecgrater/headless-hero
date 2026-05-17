"""Tests for short_form_render helpers."""

from pipeline.short_form_render import _short_filename, strip_leading_number


class TestShortFilename:
    def test_basic_format_uses_segment_name_and_index_total(self):
        assert _short_filename("Design the Default", 1, 8) == (
            "[Shortform 1∕8] [Video] - Design the Default.mp4"
        )

    def test_handles_special_chars_in_segment_name(self):
        # sanitize_filename strips < > : " / \ | ? *
        result = _short_filename('Bad/Segment: "Test"', 1, 8)
        assert result == "[Shortform 1∕8] [Video] - BadSegment Test.mp4"
        assert "/" not in result, f"Filename must not contain POSIX path separator: {result!r}"

    def test_uses_unicode_division_slash(self):
        # POSIX reserves U+002F (/) as a path separator. The visible-but-safe
        # substitute is U+2215 (∕), the Unicode division slash.
        result = _short_filename("X", 3, 8)
        assert "/" not in result, f"Filename must not contain POSIX path separator: {result!r}"
        assert "∕" in result


class TestStripLeadingNumber:
    def test_strips_single_digit_and_space(self):
        assert strip_leading_number("8 Unsolved Crimes") == "Unsolved Crimes"

    def test_strips_multi_digit_and_space(self):
        assert strip_leading_number("100 Things You Didn't Know") == "Things You Didn't Know"

    def test_no_change_when_no_leading_digits(self):
        assert strip_leading_number("How to Train Your Dragon") == "How to Train Your Dragon"

    def test_no_change_when_digits_not_followed_by_whitespace(self):
        assert strip_leading_number("8Track Memories") == "8Track Memories"

    def test_strips_with_multiple_whitespace(self):
        assert strip_leading_number("8  Two Spaces") == "Two Spaces"

    def test_empty_string(self):
        assert strip_leading_number("") == ""
