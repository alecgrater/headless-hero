"""Tests for short_form_render helpers."""

from models.script import Scene, ScriptContent, Segment
from pipeline import short_form_render
from pipeline.hook_detector import detect_hook_scene_count
from pipeline.short_form_render import _short_filename, is_short_render_current, render_short_segment, strip_leading_number


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
        short_form_render._write_short_render_metadata("script-1", 0, content)

        assert is_short_render_current("script-1", 0, content) is True

    def test_malformed_metadata_marks_first_short_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(short_form_render, "DATA_DIR", tmp_path)
        content = ScriptContent(
            title="Test",
            hook_scene_count=1,
            segments=[Segment(name="First", scenes=[_scene("title", "First.", True), _scene("body", "Body.")])],
        )
        metadata_path = tmp_path / "projects" / "script-1" / "renders" / "shorts" / "0.json"
        metadata_path.parent.mkdir(parents=True)
        metadata_path.write_text('{"segment_idx": 0, "hook_scene_count": "bad"}', encoding="utf-8")

        assert is_short_render_current("script-1", 0, content) is False

    def test_requires_subtitle_metadata_for_other_shorts_and_no_hook_skip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(short_form_render, "DATA_DIR", tmp_path)
        content = ScriptContent(
            title="Test",
            hook_scene_count=0,
            segments=[Segment(name="First", scenes=[_scene("title", "First.", True), _scene("body", "Body.")])],
        )

        assert is_short_render_current("script-1", 0, content) is False

        short_form_render._write_short_render_metadata("script-1", 0, content)

        assert is_short_render_current("script-1", 0, content) is True
        content.segments[0].scenes[1].subtitle_style = "burst"
        assert is_short_render_current("script-1", 0, content) is False

    def test_life_as_a_requires_matching_part_indicator_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setattr(short_form_render, "DATA_DIR", tmp_path)
        content = ScriptContent(
            title="Test",
            format_id="life-as-a",
            segments=[
                Segment(name="First", scenes=[_scene("title", "First.", True), _scene("body", "Body.")]),
                Segment(name="Second", scenes=[_scene("title", "Second.", True), _scene("body", "Body.")]),
            ],
        )

        assert is_short_render_current("script-1", 1, content) is False

        short_form_render._write_short_render_metadata("script-1", 1, content)

        assert is_short_render_current("script-1", 1, content) is True


class TestLifeAsAPartIndicator:
    def test_render_props_include_part_indicator_for_life_as_a(self, tmp_path, monkeypatch):
        monkeypatch.setattr(short_form_render, "DATA_DIR", tmp_path)
        captured_props: dict = {}

        def fake_run_remotion(*, props_path, output_path, **_kwargs):
            import json

            captured_props.update(json.loads(props_path.read_text(encoding="utf-8")))
            output_path.write_bytes(b"raw")

        def fake_reencode(raw_output, output_path):
            output_path.write_bytes(raw_output.read_bytes())
            return True

        monkeypatch.setattr(short_form_render, "_run_remotion", fake_run_remotion)
        monkeypatch.setattr(short_form_render, "_verify_video", lambda _path: True)
        monkeypatch.setattr(short_form_render, "_reencode_h264", fake_reencode)
        monkeypatch.setattr(short_form_render, "_copy_to_downloads", lambda *_args: str(tmp_path / "out.mp4"))

        content = ScriptContent(
            title="Your Life As A Guard On Death Row",
            format_id="life-as-a",
            segments=[
                Segment(name="Level 1, intake", scenes=[_scene("title-1", "", True), _scene("body-1", "Body.")]),
                Segment(name="Level 2, detail", scenes=[_scene("title-2", "", True), _scene("body-2", "Body.")]),
                Segment(name="Level 3, the weight", scenes=[_scene("title-3", "", True), _scene("body-3", "Body.")]),
            ],
        )

        render_short_segment("script-1", 2, content, "Project")

        assert captured_props["part_indicator"] == "Part 3/3"

    def test_render_props_include_visual_canvas(self, tmp_path, monkeypatch):
        monkeypatch.setattr(short_form_render, "DATA_DIR", tmp_path)
        captured_props: dict = {}

        def fake_run_remotion(*, props_path, output_path, **_kwargs):
            import json

            captured_props.update(json.loads(props_path.read_text(encoding="utf-8")))
            output_path.write_bytes(b"raw")

        def fake_reencode(raw_output, output_path):
            output_path.write_bytes(raw_output.read_bytes())
            return True

        monkeypatch.setattr(short_form_render, "_run_remotion", fake_run_remotion)
        monkeypatch.setattr(short_form_render, "_verify_video", lambda _path: True)
        monkeypatch.setattr(short_form_render, "_reencode_h264", fake_reencode)
        monkeypatch.setattr(short_form_render, "_copy_to_downloads", lambda *_args: str(tmp_path / "out.mp4"))

        content = ScriptContent(
            title="Canvas Test",
            visual_canvas={"background_color": "#ABCDEF"},
            segments=[
                Segment(name="Segment", scenes=[_scene("title-1", "", True), _scene("body-1", "Body.")]),
            ],
        )

        render_short_segment("script-1", 0, content, "Project")

        assert captured_props["visual_canvas"]["background_color"] == "#ABCDEF"
