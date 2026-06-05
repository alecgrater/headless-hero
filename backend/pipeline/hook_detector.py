"""AI-based hook detection for short-form export.

Identifies how many leading scenes of segment 0 are hook teasers (vs. actual
segment content). Used to skip those scenes when rendering short #1.
"""

import json
import logging
import re

from config import strip_markdown_fences
from integrations.llm_client import chat
from models.script import ScriptContent
from pipeline.fallback_observability import record_fallback

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You analyze the opening of a long-form educational/listicle video and identify how many opening scenes are "hook teasers" rather than substantive content for the first segment.

A "hook teaser" scene:
- Foreshadows multiple upcoming segments (e.g., "you'll learn about X, Y, and Z")
- Promises a payoff that won't be delivered until later in the video
- Asks a rhetorical question the rest of the VIDEO answers (not just the first segment)
- References the video title or the count of segments ("8 things you didn't know...")
- Provides cold-open shock/tension that bridges into the segment content

A substantive scene for the first segment:
- Discusses the first segment's specific topic directly
- Introduces facts, examples, or context that belong to the first segment specifically
- Does NOT reference other segments

Return a JSON object: {"hook_scene_count": <integer 0-5>, "reasoning": "<one sentence>"}

If the first segment opens directly with substantive content (no hook), return 0. The hook is typically 1-3 scenes but can be 0 (rare) or up to 5 (unusual)."""


def _build_user_message(content: ScriptContent) -> str:
    if not content.segments:
        return "EMPTY SCRIPT"
    first_seg = content.segments[0]
    seg_name = first_seg.name
    title = content.title
    intro_hook = content.intro_hook or ""

    # Take up to the first 6 scenes — gives the model enough context
    # without flooding it. Hook is almost always within the first 3-4.
    scenes_to_show = [sc for sc in first_seg.scenes if not sc.is_title_card][:6]

    lines: list[str] = [
        f'Video title: "{title}"',
        f'First segment name: "{seg_name}"',
    ]
    if intro_hook:
        lines.append(f'Intro hook text (from script outline): "{intro_hook}"')
    lines.append("")
    lines.append("Opening scenes of segment 1:")
    for i, sc in enumerate(scenes_to_show):
        narration = (sc.narration or "").strip()
        lines.append(f"\nScene {i + 1}:\n{narration}")
    lines.append("")
    lines.append("How many of these opening scenes are hook teasers (vs. substantive first-segment content)?")
    lines.append('Return JSON: {"hook_scene_count": <int 0-5>, "reasoning": "<short>"}')
    return "\n".join(lines)


def _normalize_text(value: str) -> str:
    """Normalize narration for conservative exact-ish hook matching."""
    return re.sub(r"\s+", " ", value).strip().lower()


def _fallback_hook_scene_count(content: ScriptContent) -> int:
    """Detect an obvious first hook scene without an LLM.

    This catches the common cold-open path where scene 1 is the outline's
    intro_hook verbatim. The LLM can still identify longer teaser runs.
    """
    if not content.intro_hook or not content.segments:
        return 0

    scenes = [sc for sc in content.segments[0].scenes if not sc.is_title_card]
    if len(scenes) <= 1:
        return 0

    intro = _normalize_text(content.intro_hook)
    first = _normalize_text(scenes[0].narration or "")
    if not intro or not first:
        return 0
    if first.startswith(intro) or intro.startswith(first):
        return 1
    return 0


def detect_hook_scene_count(content: ScriptContent, script_id: str | None = None) -> int:
    """Detect how many leading scenes of segment 0 are hook teasers.

    Returns an integer in [0, 5]. Falls back to 0 if the LLM call fails or
    returns an invalid value (i.e., don't skip anything when uncertain).
    """
    if not content.segments or not content.segments[0].scenes:
        return 0

    first_seg = content.segments[0]
    non_title_scene_count = sum(1 for sc in first_seg.scenes if not sc.is_title_card)
    if non_title_scene_count == 0:
        return 0

    fallback_count = _fallback_hook_scene_count(content)
    user_message = _build_user_message(content)

    try:
        response = chat(
            system=_SYSTEM_PROMPT,
            user_message=user_message,
            task="hook_detect",
            json_mode=True,
            max_tokens=512,
            script_id=script_id,
        )
    except Exception:
        logger.exception("Hook detection LLM call failed — defaulting to fallback count %d", fallback_count)
        record_fallback(
            category="hook_detection",
            event="hook_detection_llm_fallback",
            reason="Hook detection LLM call failed",
            to_value="deterministic_count",
            script_id=script_id,
            severity="warn",
            metadata={"fallback_count": fallback_count},
            logger=logger,
        )
        return fallback_count

    try:
        cleaned = strip_markdown_fences(response)
        data = json.loads(cleaned)
        raw_count = data.get("hook_scene_count", 0)
        count = int(raw_count)
    except (ValueError, TypeError, json.JSONDecodeError):
        logger.warning(
            "Hook detector returned non-JSON or non-int: %r — defaulting to fallback count %d",
            response,
            fallback_count,
        )
        record_fallback(
            category="hook_detection",
            event="hook_detection_parse_fallback",
            reason="Hook detector returned non-JSON or non-int",
            to_value="deterministic_count",
            script_id=script_id,
            severity="warn",
            metadata={"fallback_count": fallback_count},
            logger=logger,
        )
        return fallback_count

    # Clamp to a sane range and cap at the number of available scenes minus 1
    # so short #1 always has at least one content scene to render.
    count = max(0, min(count, 5))
    count = min(count, max(0, non_title_scene_count - 1))
    count = max(count, fallback_count)

    reasoning = data.get("reasoning", "")
    logger.info(
        "Hook detection: %d leading scenes flagged as hook for script %s (reasoning: %s)",
        count, script_id or "unknown", reasoning,
    )
    return count
