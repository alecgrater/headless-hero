"""Tests that media_source properly routes to different providers.

Mocks external APIs (Pexels, Twitch, Gemini) at the integration layer and
verifies that generate_batch correctly dispatches based on media_source.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.image_gen import generate_batch, generate_scene_image


@pytest.fixture(autouse=True)
def tmp_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("pipeline.image_gen.DATA_DIR", tmp_path)
    monkeypatch.setattr("config.DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def mock_pexels():
    with patch("pipeline.stock_photo.search_and_download") as mock:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(b"\xff\xd8\xff" + b"\x00" * 100)
        tmp.close()
        mock.return_value = tmp.name
        yield mock


@pytest.fixture
def mock_twitch():
    with patch("pipeline.gameplay.lookup_game") as mock_lookup, \
         patch("pipeline.gameplay.search_clips") as mock_clips, \
         patch("pipeline.gameplay.search_vods") as mock_vods, \
         patch("pipeline.gameplay.download_clip") as mock_dl_clip, \
         patch("pipeline.gameplay.download_vod_segment") as mock_dl, \
         patch("pipeline.gameplay.detect_facecam") as mock_facecam:
        mock_lookup.return_value = {"id": "12345", "name": "Minecraft"}
        mock_clips.return_value = [{"url": "https://clips.twitch.tv/fake", "id": "c1"}]
        mock_vods.return_value = [{"url": "https://twitch.tv/videos/fake", "id": "v1"}]
        mock_facecam.return_value = False

        def _fake_download_clip(url, output_path):
            Path(output_path).write_bytes(b"\x00" * 100)

        def _fake_download_vod(url, duration, output_path):
            Path(output_path).write_bytes(b"\x00" * 100)

        mock_dl_clip.side_effect = _fake_download_clip
        mock_dl.side_effect = _fake_download_vod
        yield {
            "lookup_game": mock_lookup,
            "search_clips": mock_clips,
            "search_vods": mock_vods,
            "download_clip": mock_dl_clip,
            "download_vod_segment": mock_dl,
            "detect_facecam": mock_facecam,
        }


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


class TestMediaSourceDispatch:
    """Verify that media_source controls which provider is called."""

    def test_ai_source_calls_gemini(self, mock_gemini, mock_pexels, tmp_data_dir):
        scenes = [{
            "scene_id": "scene_ai_1",
            "visual_prompt": "A glowing brain made of circuits",
            "media_source": "ai",
        }]
        results = generate_batch(scenes, script_id="test-script-1")

        assert mock_gemini.called, "AI source should call generate_image (Gemini)"
        assert not mock_pexels.called, "AI source should NOT call Pexels"
        assert results[0]["error"] is None
        assert results[0]["image_url"] is not None

    def test_stock_photo_calls_pexels(self, mock_gemini, mock_pexels, tmp_data_dir):
        scenes = [{
            "scene_id": "scene_stock_1",
            "visual_prompt": "Golden Gate Bridge at sunset",
            "media_source": "stock_photo",
        }]
        results = generate_batch(scenes, script_id="test-script-2")

        assert mock_pexels.called, "stock_photo source should call Pexels"
        assert not mock_gemini.called, "stock_photo source should NOT call Gemini"
        assert results[0]["error"] is None
        assert results[0]["image_url"] is not None

    def test_gameplay_calls_twitch(self, mock_gemini, mock_pexels, mock_twitch, tmp_data_dir):
        scenes = [{
            "scene_id": "scene_gameplay_1",
            "visual_prompt": "Minecraft building montage",
            "media_source": "gameplay_video",
            "gameplay_game_name": "Minecraft",
            "audio_duration_seconds": 5.0,
        }]
        results = generate_batch(scenes, script_id="test-script-3")

        assert mock_twitch["lookup_game"].called, "gameplay source should call Twitch lookup"
        assert mock_twitch["search_clips"].called, "gameplay source should search clips"
        assert not mock_gemini.called, "gameplay source should NOT call Gemini"
        assert not mock_pexels.called, "gameplay source should NOT call Pexels"
        assert results[0]["error"] is None
        assert results[0]["video_url"] is not None

    def test_ai_video_generates_anchor_image_then_runway_video(self, mock_gemini, mock_pexels, tmp_data_dir):
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
        assert not mock_pexels.called, "AI video should NOT call Pexels"
        assert results[0]["error"] is None
        assert results[0]["image_url"] is None
        assert results[0]["video_url"] == "/static/projects/test-script-video/videos/scene_ai_video_1.mp4"

    def test_default_source_is_ai(self, mock_gemini, mock_pexels, tmp_data_dir):
        scenes = [{
            "scene_id": "scene_default_1",
            "visual_prompt": "Abstract concept of time",
        }]
        results = generate_batch(scenes, script_id="test-script-4")

        assert mock_gemini.called, "Default (no media_source) should call Gemini"
        assert not mock_pexels.called, "Default should NOT call Pexels"

    def test_mixed_sources_route_correctly(self, mock_gemini, mock_pexels, mock_twitch, tmp_data_dir):
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

        assert mock_gemini.call_count == 1, f"Expected 1 Gemini call, got {mock_gemini.call_count}"
        assert mock_pexels.call_count == 1, f"Expected 1 Pexels call, got {mock_pexels.call_count}"
        assert mock_twitch["lookup_game"].call_count == 1, "Expected 1 Twitch lookup"

        assert results[0]["image_url"] is not None
        assert results[1]["image_url"] is not None
        assert results[2]["video_url"] is not None

        for r in results:
            assert r["error"] is None

    def test_stock_photo_without_api_key_errors(self, mock_gemini, tmp_data_dir):
        with patch("pipeline.stock_photo.search_and_download", side_effect=RuntimeError("PEXELS_API_KEY not configured")):
            scenes = [{
                "scene_id": "scene_nokey_1",
                "visual_prompt": "Mountain landscape",
                "media_source": "stock_photo",
            }]
            results = generate_batch(scenes, script_id="test-script-6")

            assert results[0]["error"] is not None
            assert "PEXELS_API_KEY" in results[0]["error"]
            assert not mock_gemini.called, "Should NOT silently fall back to AI when stock_photo requested"

    def test_gameplay_without_game_name_errors(self, mock_gemini, mock_twitch, tmp_data_dir):
        scenes = [{
            "scene_id": "scene_nogame_1",
            "visual_prompt": "Some gameplay footage",
            "media_source": "gameplay_video",
            "gameplay_game_name": "",
            "audio_duration_seconds": 5.0,
        }]
        results = generate_batch(scenes, script_id="test-script-7")

        assert results[0]["error"] is not None
        assert "game_name" in results[0]["error"].lower() or "game" in results[0]["error"].lower()
        assert not mock_gemini.called, "Should NOT silently fall back to AI when gameplay requested"


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
