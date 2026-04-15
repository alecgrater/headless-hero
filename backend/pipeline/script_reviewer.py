"""Script quality reviewer — evaluates scripts against 5 craft skillsets via Gemini."""

import json
import logging

from pydantic import BaseModel

from config import strip_markdown_fences
from models.script import ScriptContent

logger = logging.getLogger(__name__)

REVIEW_RUBRIC = """\
You are a script quality reviewer for educational YouTube videos.
Evaluate the script narration against these 5 craft skillsets.
For each, return pass or fail with a one-sentence explanation.

1. Payoff Promise: Does the opening deliver a surprising insight in the first \
segment? Does it partially deliver value before asking for viewer commitment? \
Or does it use a generic intro that promises without giving?

2. Mosaic Structure: Are there open loops that create tension? Do threads weave \
together across segments? Or is it a flat A→B→C progression that reads like a list?

3. Steel-Manning: When claims are made, does the script acknowledge the strongest \
counterarguments before dismantling them? Or does it bulldoze past opposing views?

4. Concrete Before Abstract: Do big claims follow specific, human-scale examples? \
Are there vivid, sensory scenarios the viewer can picture? Or are claims stated \
abstractly first with examples tacked on?

5. Callback Economy: Are there planted details that recur with new meaning later \
in the script? Or is it a flat sequence of unconnected facts with no callbacks?

IMPORTANT: Be rigorous but fair. A skillset passes if the script makes a genuine \
attempt, even if imperfect. It fails only if the skillset is clearly absent or \
poorly executed. A script can pass overall with 3/5 skillsets passing.

Return ONLY valid JSON with this exact structure:
{
  "overall_pass": true,
  "skillsets": {
    "payoff_promise": {"pass": true, "critique": "The opening immediately delivers..."},
    "mosaic_structure": {"pass": false, "critique": "The script follows a flat list..."},
    "steel_manning": {"pass": true, "critique": "Claims acknowledge complexity..."},
    "concrete_before_abstract": {"pass": true, "critique": "Each major point is grounded..."},
    "callback_economy": {"pass": false, "critique": "No details recur later..."}
  }
}

Set overall_pass to true if 3 or more skillsets pass. Set it to false otherwise.
"""


class SkillsetResult(BaseModel):
    """Pass/fail result for a single skillset."""

    passed: bool
    critique: str


class ReviewResult(BaseModel):
    """Structured result from script quality review."""

    overall_pass: bool
    payoff_promise: SkillsetResult
    mosaic_structure: SkillsetResult
    steel_manning: SkillsetResult
    concrete_before_abstract: SkillsetResult
    callback_economy: SkillsetResult

    def critique_summary(self) -> str:
        """Return a formatted summary of failed skillsets for injection into retry prompt."""
        failed = []
        for name, result in [
            ("Payoff Promise", self.payoff_promise),
            ("Mosaic Structure", self.mosaic_structure),
            ("Steel-Manning", self.steel_manning),
            ("Concrete Before Abstract", self.concrete_before_abstract),
            ("Callback Economy", self.callback_economy),
        ]:
            if not result.passed:
                failed.append(f"- {name}: {result.critique}")
        return "\n".join(failed)

    def pass_count(self) -> int:
        """Return the number of passing skillsets."""
        return sum(
            1
            for r in [
                self.payoff_promise,
                self.mosaic_structure,
                self.steel_manning,
                self.concrete_before_abstract,
                self.callback_economy,
            ]
            if r.passed
        )


def _extract_narration(content: ScriptContent) -> str:
    """Extract all narration text from a script, ordered by segment/scene."""
    lines: list[str] = []
    for seg in content.segments:
        lines.append(f"--- {seg.name} ---")
        for scene in seg.scenes:
            if scene.narration and not scene.is_title_card:
                lines.append(scene.narration)
    return "\n\n".join(lines)


def review_script(content: ScriptContent) -> ReviewResult:
    """Review a script against the 5 craft skillsets using Gemini.

    If Gemini fails for any reason, returns a passing result so generation
    is not blocked by reviewer outages.
    """
    from integrations.google_text_client import generate_text

    narration = _extract_narration(content)
    user_message = (
        f"Review the following educational YouTube script narration:\n\n"
        f"{narration}"
    )

    try:
        raw = generate_text(
            system_prompt=REVIEW_RUBRIC,
            user_message=user_message,
        )
    except Exception:
        logger.warning(
            "Gemini review call failed — accepting script without review",
            exc_info=True,
        )
        return _passing_result()

    try:
        text = strip_markdown_fences(raw)
        data = json.loads(text)
        return _parse_review(data)
    except Exception:
        logger.warning(
            "Failed to parse Gemini review response — accepting script",
            exc_info=True,
        )
        return _passing_result()


def _parse_review(data: dict) -> ReviewResult:
    """Parse raw JSON from Gemini into a ReviewResult."""
    skillsets = data.get("skillsets", {})

    def _get(key: str) -> SkillsetResult:
        entry = skillsets.get(key, {})
        return SkillsetResult(
            passed=entry.get("pass", True),
            critique=entry.get("critique", ""),
        )

    return ReviewResult(
        overall_pass=data.get("overall_pass", True),
        payoff_promise=_get("payoff_promise"),
        mosaic_structure=_get("mosaic_structure"),
        steel_manning=_get("steel_manning"),
        concrete_before_abstract=_get("concrete_before_abstract"),
        callback_economy=_get("callback_economy"),
    )


def _passing_result() -> ReviewResult:
    """Return a default passing result (used when Gemini is unavailable)."""
    ok = SkillsetResult(passed=True, critique="Review skipped")
    return ReviewResult(
        overall_pass=True,
        payoff_promise=ok,
        mosaic_structure=ok,
        steel_manning=ok,
        concrete_before_abstract=ok,
        callback_economy=ok,
    )
