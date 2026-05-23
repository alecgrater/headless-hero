"""Integration tests for the rewritten CinematicChaptersStrategy.prepare_thumbnail."""
import json
import os

import pytest
from PIL import Image

from models.script import LevelMeta, MainCharacter, Scene, ScriptContent, Segment
from pipeline.formats.title_cards.cinematic_chapters import (
    CINEMATIC_CHAPTERS,
    _thumbnail_paths,
    _chapter_image_path,
)


def _make_content(n_levels: int) -> ScriptContent:
    levels = [
        LevelMeta(
            number=i + 1,
            descriptor=f"stage{i + 1}",
            image_prompt="" if i == 0 else f"chapter prompt {i + 1}",
        )
        for i in range(n_levels)
    ]
    segments = [
        Segment(name=f"Level {i + 1}, the stage{i + 1}", scenes=[
            Scene(id=f"chapter_{i+1:02d}", narration="x", visual_prompt="[ESTABLISHING] x",
                  duration_estimate_seconds=4.0, is_title_card=True, visual_beat="static"),
            Scene(id=f"s_{i+1}_a", narration="x", visual_prompt="[ESTABLISHING] x",
                  duration_estimate_seconds=10.0, is_title_card=False, visual_beat="static"),
        ])
        for i in range(n_levels)
    ]
    return ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        cinematic_thumbnail_prompt="iconic test image",
        levels=levels,
        segments=segments,
    )


@pytest.fixture
def patched_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR for the strategy and its helpers to tmp_path."""
    monkeypatch.setattr("pipeline.formats.title_cards.cinematic_chapters.DATA_DIR", tmp_path)
    monkeypatch.setattr(
        "pipeline.formats.title_cards.cinematic_chapters._eli_enabled_for_project",
        lambda script_id: True,
    )
    monkeypatch.setattr("pipeline.thumbnail.DATA_DIR", tmp_path)
    monkeypatch.setattr("pipeline.thumbnail._resolve_thumbnail_style_ref", lambda script_id: None)
    return tmp_path


@pytest.fixture
def fake_image_gen(monkeypatch):
    """Replace generate_scene_image with a stub that writes a dummy PNG."""
    import pipeline.formats.title_cards.cinematic_chapters as cinematic_module
    calls: list[tuple[str, str]] = []

    def fake_generate(scene_id: str, visual_prompt: str, script_id: str, force: bool = False, **_kwargs) -> str:
        calls.append((scene_id, visual_prompt))
        # Use the patched DATA_DIR via the module reference
        from pipeline.formats.title_cards.cinematic_chapters import DATA_DIR
        out = DATA_DIR / "projects" / script_id / "images" / f"{scene_id}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 32), (123, 45, 67)).save(out)
        return str(out)

    monkeypatch.setattr(cinematic_module, "generate_scene_image", fake_generate)
    return calls


@pytest.fixture
def fake_gemini_transform(monkeypatch, tmp_path):
    """Stub transform_with_references to write a marker PNG."""
    transform_calls: list[dict] = []

    def fake_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        transform_calls.append({"prompt": prompt, "image_paths": image_paths, "script_id": script_id})
        out = tmp_path / "gemini_out.png"
        Image.new("RGB", (32, 32), (200, 200, 200)).save(out)
        return str(out)

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", fake_transform)
    return transform_calls


def test_prepare_thumbnail_generates_clean_chapter1_and_split(
    patched_data_dir, fake_image_gen, fake_gemini_transform,
):
    script_id = "test-1"
    content = _make_content(n_levels=4)

    CINEMATIC_CHAPTERS.prepare_thumbnail(
        script_id=script_id,
        content=content,
        accent_color="#ff0066",
        force=False,
    )

    clean_path, final_path, sidecar_path = _thumbnail_paths(script_id)

    # Clean cinematic image was generated
    assert clean_path.exists()
    assert any(scene_id == "cinematic_thumbnail_clean" for scene_id, _ in fake_image_gen)

    # Chapter 1 was COPIED (not generated)
    chapter_1 = _chapter_image_path(script_id, 1)
    assert chapter_1.exists()
    assert chapter_1.read_bytes() == clean_path.read_bytes()
    assert not any(scene_id == "chapter_1" for scene_id, _ in fake_image_gen)

    # Chapters 2..4 WERE generated
    for n in (2, 3, 4):
        assert _chapter_image_path(script_id, n).exists()
        assert any(scene_id == f"chapter_{n}" for scene_id, _ in fake_image_gen)

    # Split-progression Gemini call ran with the clean image
    assert len(fake_gemini_transform) == 1
    call = fake_gemini_transform[0]
    assert call["image_paths"] == [str(clean_path)]
    assert "months in" in call["prompt"]
    assert "years in" in call["prompt"]
    # No "LEVEL N" labels are substituted into the prompt (only in the casing example).
    import re as _re
    substituted_levels = [m for m in _re.findall(r"LEVEL \d+", call["prompt"]) if m != "LEVEL X"]
    assert substituted_levels == []

    # Sidecar reflects the default style (time_periods) for fresh runs.
    sidecar_data = json.loads(sidecar_path.read_text())
    assert sidecar_data.get("style") == "time_periods"

    # Final thumbnail and sidecar both exist
    assert final_path.exists()
    assert sidecar_path.exists()


def test_prepare_thumbnail_caches_time_labels_across_runs(
    patched_data_dir, fake_image_gen, fake_gemini_transform,
):
    script_id = "test-2"
    content = _make_content(n_levels=5)

    CINEMATIC_CHAPTERS.prepare_thumbnail(script_id=script_id, content=content, accent_color="#ff0066")
    _, _, sidecar_path = _thumbnail_paths(script_id)
    import json
    first_labels = json.loads(sidecar_path.read_text())

    # Second run without force should reuse the same labels (sidecar unchanged)
    CINEMATIC_CHAPTERS.prepare_thumbnail(script_id=script_id, content=content, accent_color="#ff0066")
    second_labels = json.loads(sidecar_path.read_text())
    assert first_labels == second_labels
    assert "left_label" in first_labels
    assert "right_label" in first_labels


def test_prepare_thumbnail_regenerates_when_legacy_level_sidecar_exists(
    patched_data_dir, monkeypatch, fake_gemini_transform,
):
    script_id = "test-legacy-sidecar"
    content = _make_content(n_levels=4)
    clean_path, final_path, sidecar_path = _thumbnail_paths(script_id)
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (123, 45, 67)).save(clean_path)
    Image.new("RGB", (32, 32), (99, 99, 99)).save(final_path)
    sidecar_path.write_text(json.dumps({"left_level": 1, "right_level": 4}))

    newer_mtime = clean_path.stat().st_mtime + 10
    os.utime(final_path, (newer_mtime, newer_mtime))

    import pipeline.formats.title_cards.cinematic_chapters as cinematic_module

    def cached_generate(
        scene_id: str,
        visual_prompt: str,
        script_id: str,
        force: bool = False,
        **_kwargs,
    ) -> str:
        del visual_prompt, force
        out = patched_data_dir / "projects" / script_id / "images" / f"{scene_id}.png"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (32, 32), (123, 45, 67)).save(out)
        return str(out)

    monkeypatch.setattr(cinematic_module, "generate_scene_image", cached_generate)

    CINEMATIC_CHAPTERS.prepare_thumbnail(
        script_id=script_id,
        content=content,
        accent_color="#ff0066",
    )

    assert len(fake_gemini_transform) == 1
    sidecar_data = json.loads(sidecar_path.read_text())
    assert "left_label" in sidecar_data
    assert "right_label" in sidecar_data


def test_prepare_thumbnail_falls_back_when_one_level(
    patched_data_dir, fake_image_gen, fake_gemini_transform,
):
    script_id = "test-3"
    content = _make_content(n_levels=1)

    CINEMATIC_CHAPTERS.prepare_thumbnail(script_id=script_id, content=content, accent_color="#ff0066")

    clean_path, final_path, sidecar_path = _thumbnail_paths(script_id)
    # Final exists and equals clean (no Gemini enhancement performed)
    assert final_path.exists()
    assert final_path.read_bytes() == clean_path.read_bytes()
    # No sidecar written (no pair to record)
    assert not sidecar_path.exists()
    # No Gemini transform call happened
    assert len(fake_gemini_transform) == 0


def test_prepare_thumbnail_uses_main_character_prompt_only_when_eli_disabled(
    patched_data_dir, fake_image_gen, fake_gemini_transform, monkeypatch,
):
    import pipeline.formats.title_cards.cinematic_chapters as cinematic_module

    content = _make_content(n_levels=2)
    content.main_character = MainCharacter(
        name="Maya",
        appearance="short black hair and a blue uniform",
        vibe="focused",
    )

    monkeypatch.setattr(cinematic_module, "_eli_enabled_for_project", lambda script_id: True)

    CINEMATIC_CHAPTERS.prepare_thumbnail(
        script_id="eli-on",
        content=content,
        accent_color="#ff0066",
        force=True,
    )

    eli_on_prompts = [prompt for _, prompt in fake_image_gen]
    assert eli_on_prompts
    assert all("Maya is the visually dominant main subject" not in prompt for prompt in eli_on_prompts)

    fake_image_gen.clear()
    fake_gemini_transform.clear()
    monkeypatch.setattr(cinematic_module, "_eli_enabled_for_project", lambda script_id: False)

    CINEMATIC_CHAPTERS.prepare_thumbnail(
        script_id="eli-off",
        content=content,
        accent_color="#ff0066",
        force=True,
    )

    eli_off_prompts = [prompt for _, prompt in fake_image_gen]
    assert eli_off_prompts
    assert all("Maya is the visually dominant main subject" in prompt for prompt in eli_off_prompts)
