"""Tests for title card script post-processing."""

from models.script import Scene, ScriptContent, Segment
from pipeline.modifiers.title_cards import enforce_title_cards_and_min_scenes
from pipeline import title_card_composer


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
