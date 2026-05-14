"""Cold open A/B variant generation — uses Claude to produce 3 hook styles with scoring."""

import json
import logging
import os

from config import DEFAULT_CLAUDE_MODEL, strip_markdown_fences
from integrations.claude_client import chat
from models.cold_open import ColdOpenResult, ColdOpenScores, ColdOpenVariant
from prompts import compose_script_system_prompt

logger = logging.getLogger(__name__)


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

    system_prompt = compose_script_system_prompt(cold_open=True)

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
        json_mode=True,
    )

    text = strip_markdown_fences(raw)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Claude sometimes appends commentary after the JSON object — extract just the JSON
        decoder = json.JSONDecoder()
        try:
            data, _ = decoder.raw_decode(text.lstrip())
        except json.JSONDecodeError as e2:
            raise RuntimeError(f"Cold open generation returned invalid JSON: {e2}") from e2

    # Parse variants and compute overall scores
    variants: list[ColdOpenVariant] = []
    for v in data.get("variants", []):
        scores_data = v.get("scores", {})
        tension = scores_data.get("tension")
        specificity = scores_data.get("specificity")
        drop_rate_risk = scores_data.get("drop_rate_risk")

        if tension is None or specificity is None or drop_rate_risk is None:
            logger.warning(
                "Variant %s missing score fields (tension=%r, specificity=%r, drop_rate_risk=%r), raw scores: %r",
                v.get("id", "?"), tension, specificity, drop_rate_risk, scores_data,
            )

        scores = ColdOpenScores(
            tension=tension if tension is not None else 50,
            specificity=specificity if specificity is not None else 50,
            drop_rate_risk=drop_rate_risk if drop_rate_risk is not None else 50,
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
