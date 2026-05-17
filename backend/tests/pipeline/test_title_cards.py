"""Tests for title card script post-processing."""

from models.script import Scene, ScriptContent, Segment
from pipeline.modifiers.title_cards import enforce_title_cards_and_min_scenes


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
