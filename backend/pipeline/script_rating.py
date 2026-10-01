"""Full-script quality review for generated scripts.

The rater is the judge that was calibrated in the 2026-09-30 script investigation:
on scripts with known and planted defects it found 35 of 38, with 98% of its quotes
verbatim, and scored flawed scripts 4-5 and fixed ones 7. The category scorecard it
replaced rated everything ~7 and did not move when four obvious defects were planted.
The prompt below is that judge's prompt verbatim — re-measure before rewording it.
"""

import json
import logging
import re

from config import parse_json_response
from integrations.llm_client import _resolve_model, _resolve_provider, chat
from models.script import ScriptContent, ScriptRating, ScriptRatingProblem, ScriptRatingScores
from pipeline.formats import resolve_format

logger = logging.getLogger(__name__)

VERSION = "2026-09-30"

FORMAT_NOTES: dict[str, str] = {
    "youtube-listicle": (
        "Educational listicle (8 segments). Each segment must ALSO work as a standalone YouTube Short: it may not "
        "tease the next segment, refer to other segments, or recap the whole video. Punchy rhythm and short "
        "sentences are the intended style; judge whether they work, not whether they exist."),
    "life-as-a": (
        "Literary 'Your Life As A…' video: second person ('you'), present tense, contemplative and observational. "
        "Levels are chapters of one continuous life. Recurring characters and callbacks across levels are intended, "
        "but each person is introduced once and stays consistent; the protagonist is never named. Chapter cards "
        "contain only a short descriptor ('The new hire.')."),
}

JUDGE_SYSTEM = (
    "You are a demanding script editor for a YouTube channel. You read narration that will be voiced as ONE "
    "continuous voiceover — scene breaks are invisible to the listener — and you find concrete problems. You quote "
    "the narration exactly. You never invent problems to look thorough: if a category has no real problem, return "
    "an empty list. Return only a JSON object."
)

JUDGE_TASK = """Format: {fmt_note}
{excerpt_note}
Find problems in these categories:
1. continuity_errors — contradicting facts (ages, numbers, names, dates, timeline), a person introduced as new after already being introduced, one character given different details.
2. unintroduced_references — a person, term, place or thing referred to as if already known but never introduced earlier in the narration{listicle_scope}.
3. bumpy_transitions — a line that does not follow from the line before: non sequitur, missing step, abrupt jump.
4. ai_tells — lines that sound machine-written: a sentence or sentence pattern reused from earlier, formula constructions leaned on repeatedly, empty profundity, stacked em-dashes, filler rhetorical questions.
5. read_aloud_problems — hard to say or follow aloud: tangled or overlong sentences, choppy runs of fragments that stall the pace, lines that describe an image or camera instead of narrating.
6. standalone_violations — {standalone_rule}
7. voice_violations — breaks of the format's voice{voice_rule}.

Each problem: {{"scene": "scene id", "quote": "exact words from the narration, 3-25 words", "problem": "under 20 words", "severity": "major" or "minor"}}.
Then score 1-10 (10 = a strong human writer would ship it, 5 = noticeably flawed): flow, clarity, human_sounding, continuity, format_fit, overall.

Return JSON: {{"continuity_errors": [], "unintroduced_references": [], "bumpy_transitions": [], "ai_tells": [], "read_aloud_problems": [], "standalone_violations": [], "voice_violations": [], "scores": {{"flow": 0, "clarity": 0, "human_sounding": 0, "continuity": 0, "format_fit": 0, "overall": 0}}, "worst_problem": "one sentence"}}

TITLE: {title}
NARRATION:
{narration}"""

CATEGORIES: tuple[str, ...] = (
    "continuity_errors", "unintroduced_references", "bumpy_transitions", "ai_tells",
    "read_aloud_problems", "standalone_violations", "voice_violations",
)

SCORE_KEYS = ("flow", "clarity", "human_sounding", "continuity", "format_fit")


def _narration_payload(content: ScriptContent) -> str:
    """The narration exactly as the calibrated judge saw it: one line per scene, by segment."""
    lines: list[str] = []
    for segment in content.segments:
        lines.append(f"\n##  {segment.name}".rstrip())
        for scene in segment.scenes:
            tag = " (chapter/title card)" if scene.is_title_card else ""
            lines.append(f"{scene.id}{tag}: {scene.narration}")
    return "\n".join(lines).strip()


def _review_prompt(content: ScriptContent) -> str:
    fmt = resolve_format(content.format_id)
    listicle = fmt.segments_stand_alone
    fmt_note = FORMAT_NOTES.get(fmt.id) or f"{fmt.display_name}: {fmt.short_description}"
    return JUDGE_TASK.format(
        fmt_note=fmt_note, excerpt_note="",
        listicle_scope=" (for this listicle: earlier in the SAME segment, since each segment may be watched alone)" if listicle else "",
        standalone_rule=("a segment ending on a tease of another segment, references to other segments, whole-video recaps, channel CTAs."
                         if listicle else "always an empty list for this format."),
        voice_rule=(": greetings, dry academic tone" if listicle else
                    ": not second person or present tense, naming the protagonist, listicle cadence or mic-drops, moralizing"),
        title=content.title, narration=_narration_payload(content))


def _norm(text: str) -> str:
    text = text.lower().replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"[\u2014\u2013-]", " ", text)
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_script_rating_response(raw: str, *, narration: str, model: str) -> ScriptRating:
    """Validate a review and keep only problems whose quote really is in the narration."""
    parsed = parse_json_response(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Script rating response must be a JSON object")
    raw_scores = parsed.get("scores")
    if not isinstance(raw_scores, dict) or not isinstance(raw_scores.get("overall"), (int, float)):
        raise ValueError("Script rating response is missing scores")
    # Round rather than reject a fractional sub-score ("flow": 6.5); overall stays as given.
    scores = ScriptRatingScores.model_validate({
        key: round(value) if isinstance(value, float) else value
        for key in SCORE_KEYS
        for value in [raw_scores.get(key)]
    })

    haystack = _norm(narration)
    problems: list[ScriptRatingProblem] = []
    dropped = 0
    for category in CATEGORIES:
        for item in parsed.get(category) or []:
            if not isinstance(item, dict) or not str(item.get("quote", "")).strip():
                continue
            if _norm(str(item["quote"])) not in haystack:
                dropped += 1  # a paraphrase or invented line is not evidence
                continue
            problems.append(ScriptRatingProblem(
                category=category,
                scene=str(item.get("scene", "")),
                quote=str(item["quote"]).strip(),
                problem=str(item.get("problem", "")).strip(),
                severity="major" if item.get("severity") == "major" else "minor",
            ))
    if dropped:
        logger.warning("Script rating: dropped %d problem(s) whose quote is not in the narration", dropped)
    problems.sort(key=lambda p: p.severity != "major")
    return ScriptRating(
        overall=float(raw_scores["overall"]),
        scores=scores,
        problems=problems,
        worst_problem=str(parsed.get("worst_problem") or "").strip(),
        model=model,
        version=VERSION,
    )


def rate_script(content: ScriptContent, *, script_id: str | None = None) -> ScriptRating:
    """Review a full script in one fresh LLM call."""
    provider = _resolve_provider("script_rating")
    model = _resolve_model(provider, "script_rating", None)
    logger.info("[%s] Rating script %r with %s/%s", script_id or "no-id", content.title, provider, model)

    raw = chat(
        JUDGE_SYSTEM,
        _review_prompt(content),
        max_tokens=16000,
        timeout=300.0,
        script_id=script_id,
        json_mode=True,
        task="script_rating",
    )

    try:
        narration = " ".join(scene.narration for scene in content.all_scenes())
        rating = parse_script_rating_response(raw, narration=narration, model=model)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("[%s] Failed to parse script rating response: %s", script_id or "no-id", exc)
        raise RuntimeError(f"Script rating returned invalid JSON: {exc}") from exc

    majors = sum(problem.severity == "major" for problem in rating.problems)
    logger.info("[%s] Script rating complete: overall=%.1f, %d problems (%d major)",
                script_id or "no-id", rating.overall, len(rating.problems), majors)
    return rating
