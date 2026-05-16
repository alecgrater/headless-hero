"""Tests for short_form_render helpers."""

from pipeline.short_form_render import _short_filename


class TestShortFilename:
    def test_basic_format(self):
        assert _short_filename("My Project", 1, 8) == "[short form 1/8] My Project.mp4"

    def test_handles_special_chars(self):
        # sanitize_filename strips < > : " / \ | ? *
        result = _short_filename("My/Project: Test", 5, 8)
        assert result == "[short form 5/8] MyProject Test.mp4"

    def test_last_of_8(self):
        assert _short_filename("Foo", 8, 8) == "[short form 8/8] Foo.mp4"

    def test_non_8_total(self):
        assert _short_filename("Bar", 2, 6) == "[short form 2/6] Bar.mp4"
