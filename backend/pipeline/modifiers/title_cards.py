"""Title cards pipeline — composite grid cards with zoom animation.

Provides title card prompt instructions, post-processing enforcement,
and pre-render image generation as standalone functions (always active).
"""

import logging

from models.script import Scene, ScriptContent

logger = logging.getLogger(__name__)

# Default circle colors when Claude doesn't provide them
DEFAULT_COLORS = [
    "#e91e63", "#2196f3", "#4caf50", "#ff9800",
    "#9c27b0", "#00bcd4", "#ff5722", "#8bc34a",
    "#3f51b5", "#cddc39", "#f44336", "#009688",
]

TITLE_CARD_PROMPT_INSTRUCTIONS = """\

Composite Title Card System:
- The video uses a composite grid title card showing ALL segments as circles on one image.
- You MUST provide these top-level fields:
  - "card_title": A condensed 2-4 word UPPERCASE title for the card (e.g. "TYPES OF DREAMS")
  - "card_title_highlight_word": One word from card_title to highlight in accent color (e.g. "DREAMS")
- Each segment MUST include:
  - "circle_color": A bold, distinct hex color for the circle background (e.g. "#e91e63"). \
Pick thematically appropriate colors — each segment gets a unique color.
  - "title_card_image_prompt": A vivid visual description for the AI-generated circle image. \
Describe a single iconic subject centered on a clean background, matching the brand art style. \
Keep it simple and readable at small sizes (it will be cropped into a circle).
- The first scene of each segment MUST be a title card (is_title_card: true) with a short (2-3s) intro narration.
- Title card scenes MUST have visual_prompt set to "" (empty string) — their visuals come from \
the composite grid card, not individual AI generation.
- Each segment MUST have at least 5 scenes (including the title card).
- Segment count MUST be exactly 6, 8, 10, or 12 for balanced grid layouts."""


def prepare_title_card_scene(scene: Scene, script_id: str, brand: dict) -> Scene:
    """Prepare a title card scene for rendering — generate composite image if needed.

    Called directly from the render pipeline (always active, not a modifier).
    """
    if not scene.is_title_card:
        return scene

    from config import DATA_DIR

    composite_path = DATA_DIR / "projects" / script_id / "images" / "composite_title_card.png"
    notitle_path = DATA_DIR / "projects" / script_id / "images" / "composite_title_card_notitle.png"

    if notitle_path.exists():
        if not scene.image_url:
            scene.image_url = f"/static/projects/{script_id}/images/composite_title_card_notitle.png"
        return scene

    if composite_path.exists():
        if not scene.image_url:
            scene.image_url = f"/static/projects/{script_id}/images/composite_title_card.png"
        return scene

    # Composite not generated yet — generate it now (fallback for single-scene preview)
    from pipeline.title_card import ensure_title_card_images

    import json
    from sqlmodel import Session, select
    from models.script import Script
    from database import engine

    with Session(engine) as session:
        stmt = select(Script).where(Script.id == script_id)
        record = session.exec(stmt).first()
        if record:
            full_content = ScriptContent.model_validate(json.loads(record.script_json))
            ensure_title_card_images(
                script_id=script_id,
                content=full_content,
                accent_color="#e91e63",
            )
            notitle_web = f"/static/projects/{script_id}/images/composite_title_card_notitle.png"
            title_web = f"/static/projects/{script_id}/images/composite_title_card.png"
            notitle_local = DATA_DIR / "projects" / script_id / "images" / "composite_title_card_notitle.png"
            scene.image_url = notitle_web if notitle_local.exists() else title_web

    return scene


def enforce_title_cards_and_min_scenes(content: ScriptContent) -> ScriptContent:
    """Post-process script to ensure title card consistency and composite card fields."""
    # Enforce card_title and highlight_word
    if not content.card_title:
        # Derive from title — take first 4 words, uppercase
        words = content.title.upper().split()[:4]
        content.card_title = " ".join(words)
        logger.info("Derived card_title from title: %s", content.card_title)

    if not content.card_title_highlight_word:
        # Use last word of card_title as highlight
        words = content.card_title.split()
        content.card_title_highlight_word = words[-1] if words else ""
        logger.info("Derived highlight word: %s", content.card_title_highlight_word)

    # Enforce even segment count (warn if odd)
    seg_count = len(content.segments)
    if seg_count % 2 != 0:
        logger.warning("Odd segment count (%d) — grid layout may be unbalanced", seg_count)

    scene_counter = 0
    for seg in content.segments:
        for sc in seg.scenes:
            num = int(sc.id.replace("scene_", "")) if sc.id.startswith("scene_") else 0
            scene_counter = max(scene_counter, num)

    for seg_idx, seg in enumerate(content.segments):
        # Enforce circle_color
        if not seg.circle_color:
            seg.circle_color = DEFAULT_COLORS[seg_idx % len(DEFAULT_COLORS)]
            logger.info("Assigned default circle_color %s to segment %r", seg.circle_color, seg.name)

        # Enforce title_card_image_prompt
        if not seg.title_card_image_prompt:
            seg.title_card_image_prompt = (
                f"A vivid, colorful illustration representing the concept of {seg.name}. "
                f"Simple, iconic, centered subject on a clean background."
            )
            logger.info("Derived title_card_image_prompt for segment %r", seg.name)

        # Ensure first scene is a title card
        if not seg.scenes or not seg.scenes[0].is_title_card:
            scene_counter += 1
            title_scene = Scene(
                id=f"scene_{scene_counter:03d}",
                narration=f"Welcome to {seg.name}.",
                visual_prompt="",
                duration_estimate_seconds=3.0,
                is_title_card=True,
            )
            seg.scenes.insert(0, title_scene)

        # Enforce title card properties on all title cards in this segment
        for sc in seg.scenes:
            if sc.is_title_card:
                sc.visual_prompt = ""

        if len(seg.scenes) < 5:
            logger.warning(
                "Segment %r has only %d scenes (minimum recommended: 5)",
                seg.name,
                len(seg.scenes),
            )

    return content
