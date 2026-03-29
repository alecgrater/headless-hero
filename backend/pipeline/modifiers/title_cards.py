"""Title cards content modifier.

Injects title card instructions into script generation prompts,
enforces title card constraints post-generation, and generates
programmatic title card images before rendering.
"""

import logging

from models.script import Scene, ScriptContent, TextOverlayConfig
from pipeline.modifiers.base import ContentModifier, ModifierMeta

logger = logging.getLogger(__name__)

# Instructions that were previously hardcoded in scriptwriter.SYSTEM_PROMPT lines 50-56
_TITLE_CARD_PROMPT_INSTRUCTIONS = """\

- The first scene of each segment MUST be a title card (is_title_card: true) \
with the segment name as text_overlay and a short (2-3s) intro line.
- Title card scenes MUST have visual_prompt set to "" (empty string) — their \
visuals are generated programmatically from brand colors, not by AI image gen.
- Title card scenes MUST have text_overlay_config with style "title_card", \
position "center", and animation "fade_in".
- Each segment MUST have at least 5 scenes (including the title card)."""

_TITLE_CARD_SHORTFORM_PROMPT_INSTRUCTIONS = """\

- You may include at most ONE title card (is_title_card: true) at the very \
start of the video. If included, it should be 2 seconds max.
- Title card scenes MUST have visual_prompt set to "" (empty string).
- Title card scenes MUST have text_overlay_config with style "title_card", \
position "center", and animation "fade_in"."""


class TitleCardsModifier(ContentModifier):
    meta = ModifierMeta(
        id="title_cards",
        name="Programmatic Title Cards",
        description="Auto-generate branded title card slides at the start of each segment.",
        icon="🎬",
    )

    def modify_script_prompt(self, system_prompt: str, user_message: str) -> tuple[str, str]:
        # Use lighter instructions for shortform (detected by system prompt content)
        if "short-form" in system_prompt.lower() or "shortform" in system_prompt.lower():
            return system_prompt + _TITLE_CARD_SHORTFORM_PROMPT_INSTRUCTIONS, user_message
        return system_prompt + _TITLE_CARD_PROMPT_INSTRUCTIONS, user_message

    def modify_script_post(self, content: ScriptContent, brand: dict) -> ScriptContent:
        if content.format == "shortform":
            return _enforce_shortform_title_cards(content)
        return _enforce_title_cards_and_min_scenes(content)

    def modify_scene_pre_render(self, scene: Scene, script_id: str, brand: dict) -> Scene:
        if not scene.is_title_card:
            return scene

        # Only generate if image doesn't already exist
        from pathlib import Path

        images_dir = Path("data/projects") / script_id / "images"
        image_path = images_dir / f"{scene.id}.png"
        if image_path.exists():
            return scene

        # Extract brand colors
        primary, secondary = "#1a1a2e", "#16213e"
        color_palette = brand.get("color_palette", "")
        if color_palette:
            colors = [c.strip() for c in color_palette.split(",") if c.strip()]
            if len(colors) >= 1:
                primary = colors[0]
            if len(colors) >= 2:
                secondary = colors[1]

        from pipeline.title_card import ensure_title_card_images
        from models.script import Segment

        # Wrap in a minimal segment for the existing function
        dummy_seg = Segment(name="", scenes=[scene])
        ensure_title_card_images(script_id, [dummy_seg], primary, secondary, font_family=brand.get("font", ""))

        return scene


def _enforce_title_cards_and_min_scenes(content: ScriptContent) -> ScriptContent:
    """Post-process script to ensure title card consistency and minimum scene counts.

    - Ensures first scene of every segment is is_title_card: true
    - Clears visual_prompt on all title cards (programmatic generation)
    - Sets text_overlay to segment name if empty
    - Sets text_overlay_config to title_card defaults if missing
    - Logs warning if segment has fewer than 5 scenes
    """
    scene_counter = 0
    for seg in content.segments:
        for sc in seg.scenes:
            num = int(sc.id.replace("scene_", "")) if sc.id.startswith("scene_") else 0
            scene_counter = max(scene_counter, num)

    for seg in content.segments:
        # Ensure first scene is a title card
        if not seg.scenes or not seg.scenes[0].is_title_card:
            scene_counter += 1
            title_scene = Scene(
                id=f"scene_{scene_counter:03d}",
                narration=f"Welcome to {seg.name}.",
                visual_prompt="",
                text_overlay=seg.name,
                duration_estimate_seconds=3.0,
                is_title_card=True,
                text_overlay_config=TextOverlayConfig(
                    position="center",
                    style="title_card",
                    animation="fade_in",
                ),
            )
            seg.scenes.insert(0, title_scene)

        # Enforce title card properties on all title cards in this segment
        for sc in seg.scenes:
            if sc.is_title_card:
                sc.visual_prompt = ""
                sc.visual_prompt_b = ""
                sc.is_animated = False
                if not sc.text_overlay:
                    sc.text_overlay = seg.name
                if not sc.text_overlay_config or sc.text_overlay_config.style != "title_card":
                    sc.text_overlay_config = TextOverlayConfig(
                        position="center",
                        style="title_card",
                        animation="fade_in",
                    )

        if len(seg.scenes) < 5:
            logger.warning(
                "Segment %r has only %d scenes (minimum recommended: 5)",
                seg.name,
                len(seg.scenes),
            )

    return content


def _enforce_shortform_title_cards(content: ScriptContent) -> ScriptContent:
    """For shortform: allow at most one title card (the very first scene), remove extras."""
    found_first = False
    for seg in content.segments:
        to_remove: list[int] = []
        for i, sc in enumerate(seg.scenes):
            if sc.is_title_card:
                if found_first:
                    # Remove extra title cards
                    to_remove.append(i)
                else:
                    found_first = True
                    # Enforce title card properties
                    sc.visual_prompt = ""
                    sc.visual_prompt_b = ""
                    sc.is_animated = False
                    if not sc.text_overlay_config or sc.text_overlay_config.style != "title_card":
                        sc.text_overlay_config = TextOverlayConfig(
                            position="center",
                            style="title_card",
                            animation="fade_in",
                        )
        for idx in reversed(to_remove):
            seg.scenes.pop(idx)

    return content
