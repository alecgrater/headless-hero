"""Hook refiner — Claude rewrites intro_hook + opening_narration using retention score feedback."""

import json
import logging

from pydantic import BaseModel

from config import parse_json_response
from integrations.claude_client import chat
from models.script import HookScore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a YouTube hook specialist. You receive an intro hook and opening \
narration that have been scored on Promise, Tension, and Payoff Hint. Your \
job is to rewrite them to address the weaknesses identified in the score \
while preserving what already works well.

## Rules

- Keep the same core topic and angle — don't change what the video is about.
- Preserve elements that scored 80+ unless they conflict with improving weaker areas.
- Focus your changes on the lowest-scoring dimensions.
- The intro_hook should be 1-2 punchy sentences — the first words the viewer hears.
- The opening_narration should be 3-4 sentences for the first 2-3 content scenes.
- Write in the same tone and style as the original.
- Be concrete and specific, not vague or generic.

## Output format

Return ONLY valid JSON — no markdown fences, no commentary:

{
  "intro_hook": "<rewritten 1-2 sentence hook>",
  "opening_narration": "<rewritten 3-4 sentence opening narration>"
}
"""


class RefinedHook(BaseModel):
    intro_hook: str
    opening_narration: str


def refine_hook(
    intro_hook: str,
    opening_narration: str,
    hook_score: HookScore,
    video_title: str,
) -> RefinedHook:
    """Rewrite intro_hook + opening_narration to address retention score weaknesses."""
    suggestions_text = "\n".join(f"- {s}" for s in hook_score.suggestions)

    user_msg = (
        f"Video title: {video_title}\n\n"
        f"## Original Hook\n\n"
        f"Intro hook: \"{intro_hook}\"\n\n"
        f"Opening narration: \"{opening_narration}\"\n\n"
        f"## Retention Score\n\n"
        f"Promise: {hook_score.promise.score}/100 — {hook_score.promise.reasoning}\n"
        f"Tension: {hook_score.tension.score}/100 — {hook_score.tension.reasoning}\n"
        f"Payoff Hint: {hook_score.payoff_hint.score}/100 — {hook_score.payoff_hint.reasoning}\n"
        f"Overall: {hook_score.overall}/100\n\n"
        f"## Suggestions to Address\n\n"
        f"{suggestions_text}\n\n"
        f"Rewrite the intro_hook and opening_narration to address these weaknesses."
    )

    logger.info("Refining hook for %r (overall score: %d)", video_title, hook_score.overall)
    raw = chat(SYSTEM_PROMPT, user_msg, max_tokens=1024, json_mode=True, task="hook")

    try:
        data = parse_json_response(raw)
        result = RefinedHook.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse hook refine response: %s\nRaw: %s", exc, raw[:500])
        raise RuntimeError(f"Hook refinement returned invalid JSON: {exc}") from exc

    logger.info("Hook refined for %r", video_title)
    return result
