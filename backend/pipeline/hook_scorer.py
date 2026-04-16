"""30-second hook retention scorer — Claude evaluates opening scenes."""

import json
import logging

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import HookScore, Scene

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a YouTube retention analyst. You evaluate the first ~30 seconds of a \
video script (the "hook") on three dimensions that determine whether viewers \
stay or click away.

## Rubric

**Promise (0-100)** — Does the opening set a clear value proposition? The \
viewer should know within seconds what they'll learn or experience. Score 80+ \
if the hook explicitly states or strongly implies the video's payoff. Score \
below 50 if the opening is generic or buries the value.

**Tension (0-100)** — Is there a curiosity gap, conflict, or unanswered \
question? Great hooks create a "wait, really?" moment. Score 80+ for a \
genuine open loop. Score below 50 if the opening is flat or expository.

**Payoff Hint (0-100)** — Does the hook tease a resolution without spoiling \
it? Viewers need confidence the video will deliver, not the answer itself. \
Score 80+ if there's a clear tease. Score below 50 if the opening either \
spoils the conclusion or gives no hint that it's worth watching.

**Overall (0-100)** — Your holistic retention prediction, weighted by how \
these three factors combine. This is NOT a simple average — tension matters \
most for retention.

**Suggestions** — 2-4 concrete, actionable suggestions to improve the hook. \
Each should be a single sentence.

## Output format

Return ONLY valid JSON — no markdown fences, no commentary:

{
  "promise": {"score": <int>, "reasoning": "<1-2 sentences>"},
  "tension": {"score": <int>, "reasoning": "<1-2 sentences>"},
  "payoff_hint": {"score": <int>, "reasoning": "<1-2 sentences>"},
  "overall": <int>,
  "suggestions": ["<suggestion 1>", "<suggestion 2>", ...]
}
"""


def score_hook(
    intro_hook: str,
    hook_scenes: list[Scene],
    video_title: str,
    script_id: str | None = None,
) -> HookScore:
    """Score the first ~30 seconds of a script for viewer retention."""
    scene_texts = []
    for i, scene in enumerate(hook_scenes, 1):
        scene_texts.append(
            f"Scene {i} ({scene.duration_estimate_seconds:.0f}s):\n"
            f"  Narration: {scene.narration}\n"
            f"  Visual: {scene.visual_prompt}"
        )

    user_msg = (
        f"Video title: {video_title}\n\n"
        f"Intro hook text: \"{intro_hook}\"\n\n"
        f"Opening scenes (first ~30 seconds):\n\n"
        + "\n\n".join(scene_texts)
    )

    logger.info("[%s] Scoring hook for %r (%d scenes)", script_id or "no-id", video_title, len(hook_scenes))
    raw = chat(SYSTEM_PROMPT, user_msg, max_tokens=2048, script_id=script_id)
    text = strip_markdown_fences(raw)

    try:
        data = json.loads(text)
        result = HookScore.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("[%s] Failed to parse hook score response: %s\nRaw: %s", script_id or "no-id", exc, text[:500])
        raise RuntimeError(f"Hook scoring returned invalid JSON: {exc}") from exc

    logger.info("[%s] Hook score: overall=%d, promise=%d, tension=%d, payoff=%d",
                script_id or "no-id", result.overall, result.promise.score,
                result.tension.score, result.payoff_hint.score)
    return result
