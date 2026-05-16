"""Tests for short_form_render helpers."""

from pipeline.short_form_render import _short_filename, strip_leading_number


class TestShortFilename:
    def test_basic_format(self):
        assert _short_filename("My Project", 1, 8) == "[short form 1∕8] My Project.mp4"

    def test_handles_special_chars(self):
        # sanitize_filename strips < > : " / \ | ? *
        result = _short_filename("My/Project: Test", 5, 8)
        assert result == "[short form 5∕8] MyProject Test.mp4"

    def test_last_of_8(self):
        assert _short_filename("Foo", 8, 8) == "[short form 8∕8] Foo.mp4"

    def test_non_8_total(self):
        assert _short_filename("Bar", 2, 6) == "[short form 2∕6] Bar.mp4"

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
