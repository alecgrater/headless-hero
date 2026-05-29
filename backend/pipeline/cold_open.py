"""Cold open A/B variant generation — uses the routed LLM provider to produce 3 hook styles with scoring."""

import json
import logging
from config import strip_markdown_fences
from integrations.llm_client import chat
from models.cold_open import ColdOpenResult, ColdOpenScores, ColdOpenVariant
from prompts import LIFE_AS_A_COLD_OPEN_ADDENDUM, compose_script_system_prompt


DEFAULT_SCORE_LABELS = {
    "tension": "Tension",
    "specificity": "Specificity",
    "drop_rate_risk": "Drop Risk",
}

LIFE_AS_A_SCORE_LABELS = {
    "tension": "Stakes",
    "specificity": "Immersion",
    "drop_rate_risk": "Drop Risk",
}

logger = logging.getLogger(__name__)


def generate_cold_opens(
    topic: str,
    description: str = "",
    brand_context: str = "",
    model: str | None = None,
    format_id: str = "youtube-listicle",
) -> ColdOpenResult:
    """Generate 3 cold open variants with routed LLM scoring.

    Returns a ColdOpenResult with computed overall scores and winner_id.
    """
    resolved_model = model

    if format_id == "life-as-a":
        system_prompt = LIFE_AS_A_COLD_OPEN_ADDENDUM.template
        score_labels = LIFE_AS_A_SCORE_LABELS
        heading = "Choose Your Opening"
        description_text = "3 long-form opening styles scored on stakes, immersion, and drop-rate risk. Pick the one that fits this life path."
    else:
        system_prompt = compose_script_system_prompt(cold_open=True)
        score_labels = DEFAULT_SCORE_LABELS
        heading = "Choose Your Cold Open"
        description_text = "3 hook styles scored on tension, specificity, and drop-rate risk. Pick the one that fits your video."

    user_parts = [f'Generate 3 opening variants for the video topic: "{topic}"']
    if description:
        user_parts.append(f"Angle/description: {description}")
    if brand_context:
        user_parts.append(f"Brand context: {brand_context}")

    user_message = "\n".join(user_parts)

    logger.info("Generating cold open variants for topic=%r (model=%s)", topic, resolved_model or "configured")

    raw = chat(
        system_prompt,
        user_message,
        model=resolved_model,
        max_tokens=4096,
        timeout=120.0,
        json_mode=True,
        task="script",
    )

    text = strip_markdown_fences(raw)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Some providers append commentary after the JSON object; extract just the JSON.
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

    result = ColdOpenResult(
        variants=variants,
        winner_id=winner_id,
        score_labels=score_labels,
        heading=heading,
        description=description_text,
    )

    logger.info(
        "Cold open variants generated: %d variants, winner=%s (scores: %s)",
        len(variants),
        winner_id,
        ", ".join(f"{v.id}={v.scores.overall}" for v in variants),
    )

    return result
