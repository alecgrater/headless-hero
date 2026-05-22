"""Tests for title card script post-processing."""

from pathlib import Path

from models.script import Scene, ScriptContent, Segment
from pipeline.modifiers.title_cards import enforce_title_cards_and_min_scenes
from pipeline import thumbnail, title_card, title_card_composer


def test_title_card_narration_drops_leading_countdown_label():
    content = ScriptContent(
        title="Corporate Scandals",
        segments=[
            Segment(
                name="Wells Fargo's fake accounts machine",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="Number eight. Wells Fargo's fake accounts machine.",
                        visual_prompt="placeholder",
                        is_title_card=True,
                    ),
                ],
            ),
        ],
    )

    updated = enforce_title_cards_and_min_scenes(content)

    assert updated.segments[0].scenes[0].narration == "Wells Fargo's fake accounts machine."


def test_title_card_narration_keeps_intrinsic_numbers():
    content = ScriptContent(
        title="History of 3M",
        segments=[
            Segment(
                name="The 3M origin story",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="The 3M origin story starts in a mine.",
                        visual_prompt="placeholder",
                        is_title_card=True,
                    ),
                ],
            ),
        ],
    )

    updated = enforce_title_cards_and_min_scenes(content)

    assert updated.segments[0].scenes[0].narration == "The 3M origin story starts in a mine."


def test_title_card_subtitle_is_cleared():
    content = ScriptContent(
        title="Common Myths",
        card_subtitle="DEBUNKED FOREVER",
        segments=[
            Segment(
                name="Night vision",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="Night vision.",
                        visual_prompt="placeholder",
                        is_title_card=True,
                    ),
                ],
            ),
        ],
    )

    updated = enforce_title_cards_and_min_scenes(content)

    assert updated.card_subtitle == ""


def test_composer_ignores_legacy_card_subtitle(tmp_path, monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("subtitle text should not be drawn on title cards")

    monkeypatch.setattr(title_card_composer, "_draw_subtitle_text", fail_if_called)

    output_path = tmp_path / "card.png"
    title_card_composer.compose_title_card(
        circle_image_paths=[""],
        segment_names=["Night Vision"],
        circle_colors=["#1e90ff"],
        card_title="COMMON MYTHS",
        highlight_word="MYTHS",
        output_path=str(output_path),
        card_subtitle="DEBUNKED FOREVER",
    )

    assert output_path.is_file()


def test_title_card_generation_archives_previous_active_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(title_card, "DATA_DIR", tmp_path)
    monkeypatch.setattr(thumbnail, "DATA_DIR", tmp_path)

    script_id = "script-title-card"
    images_dir = tmp_path / "projects" / script_id / "images"
    thumbs_dir = tmp_path / "projects" / script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    active_path = thumbs_dir / "0.png"
    active_path.write_bytes(b"old active thumbnail")

    def fake_generate_scene_image(scene_id: str, **_kwargs):
        out = images_dir / f"{scene_id}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"circle")
        return (f"/static/projects/{script_id}/images/{scene_id}.png", None, None)

    def fake_compose_title_card(**kwargs):
        output_path = kwargs["output_path"]
        content = b"with title" if kwargs.get("include_title", True) else b"without title"
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(content)
        return (output_path, {0: (100, 100, 50)})

    monkeypatch.setattr(title_card, "generate_scene_image", fake_generate_scene_image)
    monkeypatch.setattr(title_card, "compose_title_card", fake_compose_title_card)
    monkeypatch.setattr(thumbnail, "gemini_enhance_thumbnail", lambda **_kwargs: None)

    content = ScriptContent(
        title="Corporate Scandals",
        segments=[
            Segment(
                name="Night Vision",
                scenes=[Scene(id="scene_001", narration="Night Vision.", visual_prompt="placeholder", is_title_card=True)],
            ),
        ],
    )

    title_card.ensure_title_card_images(script_id, content, force=True)

    assert (thumbs_dir / "1.png").read_bytes() == b"old active thumbnail"
    assert active_path.read_bytes() == b"with title"
