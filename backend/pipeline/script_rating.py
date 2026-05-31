"""Full-script quality rating for generated scripts."""

import json
import logging
from typing import Any

from config import parse_json_response
from integrations.llm_client import _resolve_model, _resolve_provider, chat
from models.script import ScriptContent, ScriptRating, ScriptRatingCategory, ScriptRatingCriterion
from pipeline.formats import resolve_format

logger = logging.getLogger(__name__)

VERSION = "2026-05-25"

CATEGORY_SPECS: dict[str, dict[str, Any]] = {
    "viewer_retention": {
        "label": "Viewer Retention",
        "weight": 0.30,
        "criteria": ["hook_strength", "curiosity_gaps", "pacing_variance"],
    },
    "narrative_quality": {
        "label": "Narrative Quality",
        "weight": 0.15,
        "criteria": ["coherence", "throughline"],
    },
    "script_craft": {
        "label": "Script Craft",
        "weight": 0.25,
        "criteria": ["sentence_variety", "specificity", "redundancy", "word_economy"],
    },
    "audience_fit": {
        "label": "Audience Fit",
        "weight": 0.20,
        "criteria": ["assumed_knowledge_level", "relatability", "tone_consistency", "emotional_range"],
    },
    "seo_alignment": {
        "label": "SEO Alignment",
        "weight": 0.10,
        "criteria": ["title_hook_match", "search_intent_match", "rewatch_value"],
    },
}

SYSTEM_PROMPT = """\
You are a rigorous YouTube script analyst working in a fresh session with no \
memory of how this script was generated. Judge the script against the standard \
of top-performing videos in its declared format, not against average uploads.

Score every criterion from 1 to 10, where 10 means publish-ready for a strong \
channel and 5 means ordinary but meaningfully flawed. Be honest and do not \
inflate scores because the script is coherent.

Return ONLY valid JSON. Do not include markdown fences or commentary outside JSON.

Use this exact shape:
{
  "viewer_retention": {
    "criteria": {
      "hook_strength": {"score": 8, "note": "short note"},
      "curiosity_gaps": {"score": 7, "note": "short note"},
      "pacing_variance": {"score": 7, "note": "short note"}
    },
    "explanation": "One short paragraph explaining what works and what to fix."
  },
  "narrative_quality": {
    "criteria": {
      "coherence": {"score": 7, "note": "short note"},
      "throughline": {"score": 6, "note": "short note"}
    },
    "explanation": "One short paragraph explaining what works and what to fix."
  },
  "script_craft": {
    "criteria": {
      "sentence_variety": {"score": 8, "note": "short note"},
      "specificity": {"score": 9, "note": "short note"},
      "redundancy": {"score": 7, "note": "short note"},
      "word_economy": {"score": 8, "note": "short note"}
    },
    "explanation": "One short paragraph explaining what works and what to fix."
  },
  "audience_fit": {
    "criteria": {
      "assumed_knowledge_level": {"score": 8, "note": "short note"},
      "relatability": {"score": 7, "note": "short note"},
      "tone_consistency": {"score": 8, "note": "short note"},
      "emotional_range": {"score": 7, "note": "short note"}
    },
    "explanation": "One short paragraph explaining what works and what to fix."
  },
  "seo_alignment": {
    "criteria": {
      "title_hook_match": {"score": 7, "note": "short note"},
      "search_intent_match": {"score": 6, "note": "short note"},
      "rewatch_value": {"score": 7, "note": "short note"}
    },
    "explanation": "One short paragraph explaining what works and what to fix."
  }
}
"""

FORMAT_RATING_ADDENDA: dict[str, str] = {
    "youtube-listicle": """\

Format context: `youtube-listicle`.
Reward high-retention educational/listicle craft: strong payoff promises, open loops,
clean standalone segments, concrete examples, efficient pacing, and satisfying
micro-payoffs. Penalize generic facts, weak segment tension, recap/CTA narration,
and flat list progression.
""",
    "life-as-a": """\

Format context: `life-as-a`.
This is not a listicle. Reward second-person present-tense immersion, literary
observational voice, concrete sensory anchors, time progression markers, recurring
named characters, callbacks with shifted meaning, gradual level transitions, and a
specific earned closing image. Do not penalize the script for avoiding staccato
explainer cadence, punchline mic-drops, explicit cliffhangers, or list-style
standalone topic resolution when the level still closes cleanly on its own moment.
Penalize any drift into greetings, listicle cadence, announced level changes,
abstraction without lived detail, or moralized wrap-up.
""",
}


def _rating_system_prompt(content: ScriptContent) -> str:
    fmt = resolve_format(content.format_id)
    return SYSTEM_PROMPT + FORMAT_RATING_ADDENDA.get(
        fmt.id,
        (
            f"\n\nFormat context: `{fmt.id}` ({fmt.display_name}). Judge the script "
            "against this format's declared structure and notes, while still applying "
            "the JSON rubric exactly.\n"
        ),
    )


def _round_score(value: float) -> float:
    return round(value + 1e-9, 1)


def _script_payload(content: ScriptContent) -> str:
    lines = [
        f"Title: {content.title}",
        f"Intro hook: {content.intro_hook or '(none)'}",
        f"Format: {content.format_id}",
        "",
        "Script:",
    ]
    for segment_index, segment in enumerate(content.segments, 1):
        lines.append(f"\nSegment {segment_index}: {segment.name}")
        for scene_index, scene in enumerate(segment.scenes, 1):
            if scene.is_title_card:
                continue
            lines.append(f"Scene {scene_index}: {scene.narration}")
            if scene.visual_prompt:
                lines.append(f"Visual: {scene.visual_prompt}")
    return "\n".join(lines)


def _category_from_data(category_key: str, data: dict[str, Any]) -> tuple[ScriptRatingCategory, float]:
    spec = CATEGORY_SPECS[category_key]
    raw_category = data.get(category_key)
    if not isinstance(raw_category, dict):
        raise ValueError(f"Missing category: {category_key}")
    raw_criteria = raw_category.get("criteria")
    if not isinstance(raw_criteria, dict):
        raise ValueError(f"Missing criteria for {category_key}")

    criteria: dict[str, ScriptRatingCriterion] = {}
    for criterion_key in spec["criteria"]:
        raw_criterion = raw_criteria.get(criterion_key)
        if not isinstance(raw_criterion, dict):
            raise ValueError(f"Missing criterion: {category_key}.{criterion_key}")
        criteria[criterion_key] = ScriptRatingCriterion.model_validate(raw_criterion)

    average = _round_score(sum(item.score for item in criteria.values()) / len(criteria))
    category = ScriptRatingCategory(
        average=average,
        explanation=str(raw_category.get("explanation", "")).strip(),
        criteria=criteria,
    )
    return category, average * float(spec["weight"])


def parse_script_rating_response(raw: str, *, model: str) -> ScriptRating:
    """Parse, validate, and recompute a script rating response."""
    parsed = parse_json_response(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Script rating response must be a JSON object")

    categories: dict[str, ScriptRatingCategory] = {}
    weighted_total = 0.0
    for category_key in CATEGORY_SPECS:
        category, weighted = _category_from_data(category_key, parsed)
        categories[category_key] = category
        weighted_total += weighted

    return ScriptRating(
        viewer_retention=categories["viewer_retention"],
        narrative_quality=categories["narrative_quality"],
        script_craft=categories["script_craft"],
        audience_fit=categories["audience_fit"],
        seo_alignment=categories["seo_alignment"],
        overall=_round_score(weighted_total),
        model=model,
        version=VERSION,
    )


def rate_script(content: ScriptContent, *, script_id: str | None = None) -> ScriptRating:
    """Rate a full script in one fresh LLM call."""
    provider = _resolve_provider("script_rating")
    model = _resolve_model(provider, "script_rating", None)
    logger.info("[%s] Rating script %r with %s/%s", script_id or "no-id", content.title, provider, model)

    raw = chat(
        _rating_system_prompt(content),
        _script_payload(content),
        max_tokens=4096,
        timeout=300.0,
        script_id=script_id,
        json_mode=True,
        task="script_rating",
    )

    try:
        rating = parse_script_rating_response(raw, model=model)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("[%s] Failed to parse script rating response: %s", script_id or "no-id", exc)
        raise RuntimeError(f"Script rating returned invalid JSON: {exc}") from exc

    logger.info("[%s] Script rating complete: overall=%.1f", script_id or "no-id", rating.overall)
    return rating
