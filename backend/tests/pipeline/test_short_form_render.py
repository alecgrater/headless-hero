"""Tests for short_form_render helpers."""

from models.script import Scene, ScriptContent, Segment
from pipeline import short_form_render
from pipeline.hook_detector import detect_hook_scene_count
from pipeline.short_form_render import _short_filename, is_short_render_current, strip_leading_number


def _scene(scene_id: str, narration: str, is_title_card: bool = False) -> Scene:
    return Scene(
        id=scene_id,
        narration=narration,
        visual_prompt="",
        is_title_card=is_title_card,
    )


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


class TestHookDetectionFallback:
    def test_detects_verbatim_intro_hook_when_llm_fails(self, monkeypatch):
        def fail_chat(*args, **kwargs):
            raise RuntimeError("offline")

        monkeypatch.setattr("pipeline.hook_detector.chat", fail_chat)
        content = ScriptContent(
            title="Test",
            intro_hook="This is the full-video hook.",
            segments=[
                Segment(
                    name="First",
                    scenes=[
                        _scene("title", "First.", True),
                        _scene("hook", "This is the full-video hook."),
                        _scene("body", "This is actual first-segment content."),
                    ],
                ),
            ],
        )

        assert detect_hook_scene_count(content) == 1


class TestShortRenderCurrent:
    def test_requires_matching_metadata_when_first_short_skips_hooks(self, tmp_path, monkeypatch):
        monkeypatch.setattr(short_form_render, "DATA_DIR", tmp_path)
        content = ScriptContent(
            title="Test",
            hook_scene_count=1,
            segments=[Segment(name="First", scenes=[_scene("title", "First.", True), _scene("body", "Body.")])],
        )

        assert is_short_render_current("script-1", 0, content) is False

        metadata_path = tmp_path / "projects" / "script-1" / "renders" / "shorts" / "0.json"
        metadata_path.write_text('{"segment_idx": 0, "hook_scene_count": 1}', encoding="utf-8")

        assert is_short_render_current("script-1", 0, content) is True

    def test_unchanged_for_other_shorts_and_no_hook_skip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(short_form_render, "DATA_DIR", tmp_path)
        content = ScriptContent(
            title="Test",
            hook_scene_count=0,
            segments=[Segment(name="First", scenes=[_scene("title", "First.", True), _scene("body", "Body.")])],
        )

        assert is_short_render_current("script-1", 0, content) is True
        content.hook_scene_count = 2
        assert is_short_render_current("script-1", 1, content) is True
