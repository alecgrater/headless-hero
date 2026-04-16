"""Cold open A/B variant generation — uses Claude to produce 3 hook styles with scoring."""

import json
import logging
import os

from config import DEFAULT_CLAUDE_MODEL, strip_markdown_fences
from integrations.claude_client import chat
from models.cold_open import ColdOpenResult, ColdOpenScores, ColdOpenVariant
from pipeline.scriptwriter import BASE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_COLD_OPEN_ADDENDUM = """\

You are now generating 3 COLD OPEN VARIANTS for an upcoming video script.
YouTube retention lives and dies in the first 10 seconds. Each variant uses a
different hook technique from the Payoff Promise toolkit.

Generate exactly 3 variants:

1. **"Cold Open"** style — staccato subject statement. Drop the viewer straight
   into the topic with a punchy, declarative opening. No preamble.

2. **"Universality Anchor"** style — personal connection first. Start with a
   relatable experience or feeling the viewer has had, then pivot to the topic.

3. **"Rapid Pivot"** style — common belief → myth-bust. State something most
   people assume is true, then immediately challenge it.

For each variant produce:
- `intro_hook`: 1-2 sentences — the very first words the viewer hears
- `opening_narration`: 3-4 sentences for the first 2-3 content scenes that
  flow naturally from the hook

Then SCORE each variant on three dimensions (0-100):
- `tension`: How much unresolved curiosity does the opening create?
- `specificity`: How concrete and vivid are the details (vs. vague/generic)?
- `drop_rate_risk`: How likely is the viewer to click away in the first 10s?
  (lower is better for the video, but score the RISK — 100 = very likely to lose them)

Include a short `reasoning` string explaining the scores.

Return valid JSON with this exact structure:
{
  "variants": [
    {
      "id": "cold_open",
      "style": "Cold Open",
      "intro_hook": "...",
      "opening_narration": "...",
      "scores": {
        "tension": 85,
        "specificity": 70,
        "drop_rate_risk": 20,
        "reasoning": "..."
      }
    },
    {
      "id": "universality_anchor",
      "style": "Universality Anchor",
      "intro_hook": "...",
      "opening_narration": "...",
      "scores": {
        "tension": 75,
        "specificity": 80,
        "drop_rate_risk": 15,
        "reasoning": "..."
      }
    },
    {
      "id": "rapid_pivot",
      "style": "Rapid Pivot",
      "intro_hook": "...",
      "opening_narration": "...",
      "scores": {
        "tension": 90,
        "specificity": 65,
        "drop_rate_risk": 25,
        "reasoning": "..."
      }
    }
  ]
}

Return ONLY valid JSON — no markdown fences, no commentary outside the JSON.
"""


def generate_cold_opens(
    topic: str,
    description: str = "",
    brand_context: str = "",
    model: str | None = None,
) -> ColdOpenResult:
    """Generate 3 cold open variants with Claude scoring.

    Returns a ColdOpenResult with computed overall scores and winner_id.
    """
    resolved_model = model or os.environ.get("SCRIPT_MODEL", DEFAULT_CLAUDE_MODEL)

    system_prompt = BASE_SYSTEM_PROMPT + _COLD_OPEN_ADDENDUM

    user_parts = [f'Generate 3 cold open variants for the video topic: "{topic}"']
    if description:
        user_parts.append(f"Angle/description: {description}")
    if brand_context:
        user_parts.append(f"Brand context: {brand_context}")

    user_message = "\n".join(user_parts)

    logger.info("Generating cold open variants for topic=%r (model=%s)", topic, resolved_model)

    raw = chat(
        system_prompt,
        user_message,
        model=resolved_model,
        max_tokens=4096,
        timeout=120.0,
    )

    text = strip_markdown_fences(raw)
    data = json.loads(text)

    # Parse variants and compute overall scores
    variants: list[ColdOpenVariant] = []
    for v in data.get("variants", []):
        scores_data = v.get("scores", {})
        scores = ColdOpenScores(
            tension=scores_data.get("tension", 50),
            specificity=scores_data.get("specificity", 50),
            drop_rate_risk=scores_data.get("drop_rate_risk", 50),
            reasoning=scores_data.get("reasoning", ""),
        )
        scores.overall = round(
            (scores.tension + scores.specificity + (100 - scores.drop_rate_risk)) / 3, 1
        )
        variants.append(ColdOpenVariant(
            id=v.get("id", ""),
            style=v.get("style", ""),
            intro_hook=v.get("intro_hook", ""),
            opening_narration=v.get("opening_narration", ""),
            scores=scores,
        ))

    # Determine winner (highest overall)
    winner_id = ""
    if variants:
        winner = max(variants, key=lambda v: v.scores.overall)
        winner_id = winner.id

    result = ColdOpenResult(variants=variants, winner_id=winner_id)

    logger.info(
        "Cold open variants generated: %d variants, winner=%s (scores: %s)",
        len(variants),
        winner_id,
        ", ".join(f"{v.id}={v.scores.overall}" for v in variants),
    )

    return result
