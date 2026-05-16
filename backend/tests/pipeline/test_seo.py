"""Tests for SEO helper behavior."""

from models.script import Scene, ScriptContent, Segment
from pipeline.seo import build_short_form_seo_contexts


def _scene(scene_id: str, narration: str, duration: float, is_title_card: bool = False) -> Scene:
    return Scene(
        id=scene_id,
        narration=narration,
        visual_prompt="",
        audio_duration_seconds=duration,
        is_title_card=is_title_card,
    )


class TestBuildShortFormSeoContexts:
    def test_builds_one_context_per_segment(self):
        content = ScriptContent(
            title="Test",
            segments=[
                Segment(
                    name="First",
                    scenes=[
                        _scene("title-1", "", 1.0, True),
                        _scene("scene-1", "First narration.", 3.0),
                    ],
                ),
                Segment(
                    name="Second",
                    scenes=[
                        _scene("title-2", "", 1.0, True),
                        _scene("scene-2", "Second narration.", 4.0),
                    ],
                ),
            ],
        )

        shorts = build_short_form_seo_contexts(content)

        assert [short["index"] for short in shorts] == [1, 2]
        assert shorts[0]["total"] == 2
        assert shorts[0]["segment_name"] == "First"
        assert shorts[0]["transcript"] == "First narration."
        assert shorts[1]["transcript"] == "Second narration."

    def test_short_one_skips_hook_scenes_like_renderer(self):
        content = ScriptContent(
            title="Test",
            hook_scene_count=2,
            segments=[
                Segment(
                    name="First",
                    scenes=[
                        _scene("title-1", "", 1.0, True),
                        _scene("hook-1", "Hook one.", 2.0),
                        _scene("hook-2", "Hook two.", 2.0),
                        _scene("body-1", "Body scene.", 5.0),
                    ],
                ),
            ],
        )

        shorts = build_short_form_seo_contexts(content)

        assert shorts[0]["transcript"] == "Body scene."
        assert shorts[0]["duration_seconds"] == 6.0
