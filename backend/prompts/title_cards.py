from . import PromptDef, RetentionMeta, register

def _build_title_card_instructions(allowed_segments_str: str) -> str:
    return f"""\

Composite Title Card System:
- The video uses a composite grid title card showing ALL segments as circles on one image.
- You MUST provide these top-level fields:
  - "card_title": A condensed 2-4 word UPPERCASE title for the card (e.g. "TYPES OF DREAMS")
  - "card_title_highlight_word": One word from card_title to highlight in accent color (e.g. "DREAMS")
  - "card_subtitle": MUST be an empty string. Do NOT create a title-card subtitle, kicker, tagline, secondary promise, or red text phrase.
- Each segment MUST include:
  - "short_name": A punchy 1-3 word UPPERCASE label for the segment (used on thumbnail). Must be 3 words or fewer.
  - "circle_color": A bold, distinct hex color for the circle background (e.g. "#e91e63"). \
Pick thematically appropriate colors — each segment gets a unique color.
  - "title_card_image_prompt": A vivid visual description for the AI-generated circle image. \
Describe a single iconic subject centered on a clean background, matching the brand art style. \
Keep it simple and readable at small sizes (it will be cropped into a circle).
- The first scene of each segment MUST be a title card (is_title_card: true) with a short (2-3s) intro narration.
- Title card intro narration MUST NOT use countdown or ranking labels such as "Number eight", "#8", "8.", \
"No. 8", "Part 8", or "Segment 8"; introduce the concept directly instead.
- Title card scenes MUST have visual_prompt set to "" (empty string) — their visuals come from \
the composite grid card, not individual AI generation.
- Each segment MUST have at least 5 scenes (including the title card).
- Segment count MUST be exactly {allowed_segments_str} for a balanced grid layout."""


TITLE_CARD_INSTRUCTIONS = register(PromptDef(
    name="TITLE_CARD_INSTRUCTIONS",
    domain="SCRIPT",
    purpose="Composite title card system rules appended to script system prompt",
    target_model="claude",
    template="",  # Dynamic — use builder
    builder=_build_title_card_instructions,
    inputs=["allowed_segments_str"],
    retention=RetentionMeta(
        goal="Ensure consistent title card structure for visual quality",
        failure_mode="Missing title cards or inconsistent segment metadata breaks rendering",
        metrics_to_watch=["render_success_rate"],
    ),
))

# -- Script review rubric --
