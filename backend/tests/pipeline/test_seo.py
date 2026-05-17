"""Tests for SEO helper behavior."""

from models.script import Scene, ScriptContent, Segment
import pytest

from pipeline.seo import (
    ShortFormSEO,
    ShortFormSEOMetadata,
    _normalize_short_form_seo_data,
    _short_form_title,
    _validate_short_indices,
    build_short_form_seo_contexts,
    generate_short_form_seo,
)


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


class TestValidateShortIndices:
    def test_accepts_exact_indices(self):
        result = ShortFormSEOMetadata(
            shorts=[
                ShortFormSEO(index=2, title="Two", description="", hashtags=[], tags=[]),
                ShortFormSEO(index=1, title="One", description="", hashtags=[], tags=[]),
            ],
        )

        _validate_short_indices(result, [{"index": 1}, {"index": 2}])

    def test_rejects_missing_or_duplicate_indices(self):
        result = ShortFormSEOMetadata(
            shorts=[
                ShortFormSEO(index=1, title="One", description="", hashtags=[], tags=[]),
                ShortFormSEO(index=1, title="Duplicate", description="", hashtags=[], tags=[]),
            ],
        )

        with pytest.raises(RuntimeError, match="expected exactly"):
            _validate_short_indices(result, [{"index": 1}, {"index": 2}])


class TestShortFormTitles:
    def test_builds_project_title_segment_title(self):
        assert _short_form_title("Project", "Segment") == "Project: Segment"

    def test_generated_short_titles_are_deterministic(self, monkeypatch):
        def fake_chat(*args, **kwargs):
            return """
            {
              "shorts": [
                {
                  "index": 1,
                  "title": "Model Made This",
                  "description": "First short.",
                  "hashtags": ["#First"],
                  "tags": ["first"]
                },
                {
                  "index": 2,
                  "title": "Model Made That",
                  "description": "Second short.",
                  "hashtags": ["#Second"],
                  "tags": ["second"]
                }
              ]
            }
            """

        monkeypatch.setattr("pipeline.seo.chat", fake_chat)

        result = generate_short_form_seo(
            video_title="Project Title",
            shorts=[
                {"index": 1, "segment_name": "Segment One", "transcript": ""},
                {"index": 2, "segment_name": "Segment Two", "transcript": ""},
            ],
        )

        assert [short.title for short in result.shorts] == [
            "Project Title: Segment One",
            "Project Title: Segment Two",
        ]


class TestNormalizeShortFormSeoData:
    def test_fills_missing_indices_and_splits_string_lists(self):
        data = {
            "shorts": [
                {
                    "title": "One",
                    "description": "",
                    "hashtags": "#Psychology #Marketing",
                    "tags": "psychology, marketing tricks, consumer behavior",
                },
                {
                    "title": "Two",
                    "description": "",
                    "tags": "anchoring\nsales tactics",
                },
            ],
        }

        normalized = _normalize_short_form_seo_data(data, [{"index": 1}, {"index": 2}])

        assert normalized["shorts"][0]["index"] == 1
        assert normalized["shorts"][0]["hashtags"] == ["#Psychology", "#Marketing"]
        assert normalized["shorts"][0]["tags"] == ["psychology", "marketing tricks", "consumer behavior"]
        assert normalized["shorts"][1]["index"] == 2
        assert normalized["shorts"][1]["hashtags"] == []
        assert normalized["shorts"][1]["tags"] == ["anchoring", "sales tactics"]
