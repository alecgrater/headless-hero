"""Tests that media_source properly routes to supported visual providers."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.image_gen import generate_batch, generate_scene_frames_v2, generate_scene_image
from pipeline import media_analyzer
from api._helpers import update_scene
from models.script import Script, ScriptContent, Scene, Segment


@pytest.fixture(autouse=True)
def tmp_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("pipeline.image_gen.DATA_DIR", tmp_path)
    monkeypatch.setattr("pipeline.video_gen.DATA_DIR", tmp_path)
    monkeypatch.setattr("config.DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def mock_gemini():
    with patch("pipeline.image_gen.generate_image") as mock:
        def _fake_generate(prompt, width, height, **kwargs):
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(b"\x89PNG" + b"\x00" * 100)
            tmp.close()
            return tmp.name
        mock.side_effect = _fake_generate
        yield mock


def test_update_scene_can_clear_mutually_exclusive_visual_fields(tmp_data_dir):
    engine = create_engine(f"sqlite:///{tmp_data_dir / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    content = ScriptContent(
        title="Visual field clearing",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_1",
                        narration="A line.",
                        visual_prompt="A prompt",
                        image_url="/old.png",
                        frame_urls=["/old-frame.png"],
                        video_url="/old.mp4",
                    ),
                ],
            ),
        ],
    )
    with Session(engine) as session:
        session.add(Script(id="script-clear", brand_id="brand", script_json=content.model_dump_json()))
        session.commit()
        update_scene(
            session,
            "script-clear",
            "scene_1",
            image_url="",
            frame_urls=[],
            video_url="/new.mp4",
        )
        updated = ScriptContent.model_validate_json(session.get(Script, "script-clear").script_json)

    scene = updated.segments[0].scenes[0]
    assert scene.image_url == ""
    assert scene.frame_urls == []
    assert scene.video_url == "/new.mp4"


class TestMediaSourceDispatch:
    """Verify that media_source controls which provider is called."""

    def test_ai_source_calls_gemini(self, mock_gemini, tmp_data_dir):
        scenes = [{
            "scene_id": "scene_ai_1",
            "visual_prompt": "A glowing brain made of circuits",
            "media_source": "ai",
        }]
        results = generate_batch(scenes, script_id="test-script-1")

        assert mock_gemini.called, "AI source should call generate_image (Gemini)"
        assert results[0]["error"] is None
        assert results[0]["image_url"] is not None

    def test_ai_video_provider_runway_calls_runway_client(self, monkeypatch, mock_gemini, tmp_data_dir):
        monkeypatch.setenv("AI_VIDEO_PROVIDER", "runway")

        def _fake_video(**kwargs):
            Path(kwargs["output_path"]).write_bytes(b"\x00" * 100)
            return {
                "source_type": "ai_generated_video",
                "provider": "runway",
                "model": "gen4_turbo",
            }

        with patch("integrations.runway_video_client.generate_video_from_image", side_effect=_fake_video) as mock_runway:
            scenes = [{
                "scene_id": "scene_ai_video_1",
                "visual_prompt": "A character points at a thought bubble",
                "media_source": "ai_video",
                "audio_duration_seconds": 5.0,
            }]
            results = generate_batch(scenes, script_id="test-script-video")

        assert mock_gemini.called, "AI video should create a styled anchor image first"
        assert mock_runway.called, "AI video should call Runway image-to-video"
        assert results[0]["error"] is None
        assert results[0]["image_url"] is None
        assert results[0]["video_url"] == "/static/projects/test-script-video/videos/scene_ai_video_1.mp4"

    def test_video_visual_mode_routes_to_ai_video_generation(self, monkeypatch, mock_gemini, tmp_data_dir):
        monkeypatch.setenv("AI_VIDEO_PROVIDER", "runway")

        def _fake_video(**kwargs):
            Path(kwargs["output_path"]).write_bytes(b"\x00" * 100)
            return {
                "source_type": "ai_generated_video",
                "provider": "runway",
                "model": "gen4_turbo",
            }

        with patch("integrations.runway_video_client.generate_video_from_image", side_effect=_fake_video) as mock_runway:
            scenes = [{
                "scene_id": "scene_visual_mode_video",
                "visual_prompt": "A character points at a thought bubble",
                "visual_mode": "video",
                "audio_duration_seconds": 5.0,
            }]
            results = generate_batch(scenes, script_id="test-script-visual-mode-video")

        assert mock_gemini.called
        assert mock_runway.called
        assert results[0]["error"] is None
        assert results[0]["image_url"] is None
        assert results[0]["video_url"] == "/static/projects/test-script-visual-mode-video/videos/scene_visual_mode_video.mp4"

    def test_ai_video_provider_fal_calls_fal_client(self, monkeypatch, mock_gemini, tmp_data_dir):
        monkeypatch.setenv("AI_VIDEO_PROVIDER", "fal")

        def _fake_video(**kwargs):
            Path(kwargs["output_path"]).write_bytes(b"\x00" * 100)
            return {
                "source_type": "ai_generated_video",
                "provider": "fal",
                "model": "fal-ai/wan/v2.2-a14b/image-to-video/turbo",
            }

        with patch("integrations.runway_video_client.generate_video_from_image") as mock_runway, \
             patch("integrations.fal_video_client.generate_video_from_image", side_effect=_fake_video) as mock_fal:
            scenes = [{
                "scene_id": "scene_ai_video_fal",
                "visual_prompt": "A character points at a thought bubble",
                "media_source": "ai_video",
                "audio_duration_seconds": 5.0,
            }]
            results = generate_batch(scenes, script_id="test-script-video-fal")

        assert mock_gemini.called, "AI video should create a styled anchor image first"
        assert mock_fal.called, "AI video should call Fal image-to-video"
        assert not mock_runway.called, "Fal provider should not call Runway"
        assert results[0]["error"] is None
        assert results[0]["image_url"] is None
        assert results[0]["video_url"] == "/static/projects/test-script-video-fal/videos/scene_ai_video_fal.mp4"

    def test_ai_video_cache_key_changes_when_provider_or_model_changes(self, monkeypatch, mock_gemini, tmp_data_dir):
        scene = {
            "scene_id": "scene_ai_video_cache",
            "visual_prompt": "A character points at a thought bubble",
            "media_source": "ai_video",
            "audio_duration_seconds": 5.0,
        }

        def _fake_runway(**kwargs):
            Path(kwargs["output_path"]).write_bytes(b"runway")
            return {
                "source_type": "ai_generated_video",
                "provider": "runway",
                "model": "gen4_turbo",
            }

        def _fake_fal(**kwargs):
            Path(kwargs["output_path"]).write_bytes(b"fal")
            return {
                "source_type": "ai_generated_video",
                "provider": "fal",
                "model": "fal-ai/wan/v2.2-a14b/image-to-video/turbo",
            }

        monkeypatch.setenv("AI_VIDEO_PROVIDER", "runway")
        with patch("integrations.runway_video_client.generate_video_from_image", side_effect=_fake_runway) as mock_runway:
            first = generate_batch([scene], script_id="test-script-video-cache")

        monkeypatch.setenv("AI_VIDEO_PROVIDER", "fal")
        with patch("integrations.fal_video_client.generate_video_from_image", side_effect=_fake_fal) as mock_fal:
            second = generate_batch([scene], script_id="test-script-video-cache")

        monkeypatch.setenv("FAL_VIDEO_MODEL", "fal-ai/wan/custom-test-model")
        with patch("integrations.fal_video_client.generate_video_from_image", side_effect=_fake_fal) as mock_fal_model:
            third = generate_batch([scene], script_id="test-script-video-cache")

        assert first[0]["error"] is None
        assert second[0]["error"] is None
        assert third[0]["error"] is None
        assert mock_runway.call_count == 1
        assert mock_fal.call_count == 1
        assert mock_fal_model.call_count == 1

    def test_ai_video_does_not_animate_placeholder_anchor(self, monkeypatch, tmp_data_dir):
        monkeypatch.setenv("IMAGE_SCRAPER_FALLBACK_ENABLED", "false")
        monkeypatch.setenv("AI_VIDEO_PROVIDER", "runway")
        with patch("pipeline.image_gen.generate_image", side_effect=RuntimeError("Gemini blocked")), \
             patch("integrations.runway_video_client.generate_video_from_image") as mock_runway:
            scenes = [{
                "scene_id": "scene_ai_video_placeholder",
                "visual_prompt": "A character points at a thought bubble",
                "media_source": "ai_video",
                "audio_duration_seconds": 5.0,
            }]
            results = generate_batch(scenes, script_id="test-script-video-placeholder")

        assert not mock_runway.called
        assert results[0]["error"] is not None
        assert "Refusing to animate non-AI anchor image" in results[0]["error"]

    def test_default_source_is_ai(self, mock_gemini, tmp_data_dir):
        scenes = [{
            "scene_id": "scene_default_1",
            "visual_prompt": "Abstract concept of time",
        }]
        results = generate_batch(scenes, script_id="test-script-4")

        assert mock_gemini.called, "Default (no media_source) should call Gemini"

    def test_removed_sources_fall_back_to_ai_generation(self, mock_gemini, tmp_data_dir):
        scenes = [
            {
                "scene_id": "scene_mix_ai",
                "visual_prompt": "Neural network diagram",
                "media_source": "ai",
            },
            {
                "scene_id": "scene_mix_stock",
                "visual_prompt": "New York City skyline",
                "media_source": "stock_photo",
            },
            {
                "scene_id": "scene_mix_gameplay",
                "visual_prompt": "Fortnite battle",
                "media_source": "gameplay_video",
                "gameplay_game_name": "Fortnite",
                "audio_duration_seconds": 6.0,
            },
        ]
        results = generate_batch(scenes, script_id="test-script-5")

        assert mock_gemini.call_count == 3, f"Expected 3 Gemini calls, got {mock_gemini.call_count}"

        assert results[0]["image_url"] is not None
        assert results[1]["image_url"] is not None
        assert results[2]["image_url"] is not None

        for r in results:
            assert r["error"] is None


class TestImageFallbackBehavior:
    """Verify scraped web-image fallback is opt-in."""

    def test_ai_failure_uses_placeholder_when_scraper_fallback_disabled(self, monkeypatch, tmp_data_dir):
        monkeypatch.setenv("IMAGE_SCRAPER_FALLBACK_ENABLED", "false")

        with patch("pipeline.image_gen.generate_image", side_effect=RuntimeError("Gemini blocked")) as mock_generate, \
             patch("integrations.google_image_scraper.scrape_google_image_sync") as mock_scrape:
            image_url, _prompt, metadata = generate_scene_image(
                scene_id="scene_placeholder_1",
                visual_prompt="A clean educational diagram",
                script_id="test-script-placeholder",
            )

        assert mock_generate.called
        assert not mock_scrape.called
        assert image_url.endswith("/scene_placeholder_1.png")
        assert metadata is not None
        assert metadata["source_type"] == "placeholder"
        assert metadata["fallback"] is True
        assert (tmp_data_dir / "projects" / "test-script-placeholder" / "images" / "scene_placeholder_1.png").exists()

    def test_ai_failure_uses_scraper_only_when_enabled(self, monkeypatch, tmp_data_dir):
        monkeypatch.setenv("IMAGE_SCRAPER_FALLBACK_ENABLED", "true")

        def _fake_scrape(query, output_path, width, height):
            Path(output_path).write_bytes(b"\x89PNG" + b"\x00" * 100)
            return output_path

        with patch("pipeline.image_gen.generate_image", side_effect=RuntimeError("Gemini blocked")), \
             patch("integrations.google_image_scraper.scrape_google_image_sync", side_effect=_fake_scrape) as mock_scrape:
            _image_url, _prompt, metadata = generate_scene_image(
                scene_id="scene_scraped_1",
                visual_prompt="A real photo of an old computer lab",
                script_id="test-script-scraped",
            )

        assert mock_scrape.called
        assert metadata is not None
        assert metadata["source_type"] == "scraped_web_image"
        assert metadata["provider"] == "google_images_scraper"
        assert metadata["fallback"] is True


def test_real_photo_frame_directives_are_generated_as_ai(monkeypatch, mock_gemini, tmp_data_dir):
    with patch("integrations.google_image_scraper.scrape_google_image_sync") as mock_scrape:
        results = generate_scene_frames_v2(
            scene_id="scene_real_photo_removed",
            frame_directives=[
                {
                    "prompt": "A courthouse exterior in the house illustration style",
                    "source": "real_photo",
                    "search_query": "courthouse exterior",
                    "transition": "cut",
                    "reference_previous": False,
                    "contains_person": False,
                }
            ],
            script_id="test-script-real-photo-removed",
        )

    assert mock_gemini.called
    assert not mock_scrape.called
    assert results[0][0].endswith("/scene_real_photo_removed_f0.png")
    assert results[0][2] is not None
    assert results[0][2]["source_type"] == "ai_generated"


def test_media_analyzer_maps_legacy_quick_cuts_mode_to_multi_frame(monkeypatch):
    content = ScriptContent(
        title="Media modes",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="Three independent details snap into view.",
                        visual_prompt="Three separate visual details",
                        visual_mode="multi_frame",
                    )
                ],
            )
        ],
    )
    monkeypatch.setattr(
        media_analyzer,
        "chat",
        lambda **_kwargs: (
            '[{"scene_id":"scene_001","media_source":"ai","visual_mode":"full_frame",'
            '"reasoning":"Validator leaves planned mode alone."}]'
        ),
    )

    assignments = media_analyzer.analyze_media_sources(content, script_id="script-multi-frame")
    media_analyzer.apply_assignments(content, assignments)

    assert assignments[0].visual_mode == "multi_frame"
    assert content.all_scenes()[0].visual_mode == "multi_frame"
    assert content.all_scenes()[0].visual_treatment == "full_frame"


def test_media_analyzer_preserves_continuous_mode(monkeypatch):
    content = ScriptContent(
        title="Media modes",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="The crack slowly spreads across the glass.",
                        visual_prompt="A crack growing across glass",
                        visual_mode="continuous",
                    )
                ],
            )
        ],
    )
    monkeypatch.setattr(
        media_analyzer,
        "chat",
        lambda **_kwargs: (
            '[{"scene_id":"scene_001","media_source":"ai","visual_mode":"full_frame",'
            '"reasoning":"Validator leaves planned mode alone."}]'
        ),
    )

    assignments = media_analyzer.analyze_media_sources(content, script_id="script-continuous")
    media_analyzer.apply_assignments(content, assignments)

    assert assignments[0].visual_mode == "continuous"
    assert content.all_scenes()[0].visual_mode == "continuous"
    assert content.all_scenes()[0].visual_treatment == "full_frame"


def test_media_analyzer_apply_assignments_clears_stale_layers_for_non_layered_mode():
    stale_layer = {"id": "stale_panel", "prompt": "Old popup"}
    content = ScriptContent(
        title="Media modes",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="A regular full-frame scene.",
                        visual_prompt="A full-frame image",
                        visual_mode="popup_sequence",
                        visual_layers=[stale_layer],
                    )
                ],
            )
        ],
    )

    media_analyzer.apply_assignments(
        content,
        [
            media_analyzer.MediaAssignment(
                scene_id="scene_001",
                media_source="ai",
                game_name=None,
                search_query=None,
                reasoning="Use normal AI image.",
                visual_mode="full_frame",
            )
        ],
    )

    scene = content.all_scenes()[0]
    assert scene.visual_mode == "full_frame"
    assert scene.visual_treatment == "full_frame"
    assert scene.visual_layers == []
