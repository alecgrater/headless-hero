"""Content profile analysis pipeline — builds a style profile from existing scripts."""

import json
import logging
from collections import Counter
from datetime import datetime, timezone

from sqlmodel import Session, select

from config import strip_markdown_fences
from database import engine
from integrations.claude_client import chat
from models.content_profile import ContentProfile
from models.script import Script, ScriptContent

logger = logging.getLogger(__name__)

# Common English stopwords to filter from keyword extraction
_STOPWORDS = frozenset(
    "the a an and or but in on at to for of is it this that with from by as are was were "
    "be been being have has had do does did will would could should may might shall can "
    "not no nor so if then than too very just about also how what when where which who "
    "whom why each every all both few more most other some such many much own same "
    "into over after before between through during without again further once here there "
    "their its our your my his her we they them us you he she me him i".split()
)

PROFILE_SYSTEM_PROMPT = """\
You are analyzing a YouTube creator's content library to build a style profile.
You will receive titles, segment names, and narration excerpts from their existing videos.

Synthesize a JSON profile with these fields:
- common_topics: list of up to 10 recurring subject areas (e.g. "cognitive psychology", "space exploration")
- narration_style: 1-2 sentences describing the writing voice (e.g. "conversational and curiosity-driven, uses rhetorical questions")
- visual_approach: 1-2 sentences about their visual storytelling (e.g. "heavy use of infographics, prefers abstract imagery over photos")
- typical_keywords: list of up to 20 characteristic words/phrases from their content
- audience_profile: 1-2 sentences about their likely audience (e.g. "curious adults interested in science, likely 25-45")

Return ONLY valid JSON — no markdown fences, no commentary.
"""


def _extract_features(scripts: list[ScriptContent]) -> dict:
    """Pure Python feature extraction from script content."""
    titles: list[str] = []
    segment_names: list[str] = []
    narration_samples: list[str] = []
    word_counter: Counter = Counter()
    total_segments = 0

    for script in scripts:
        titles.append(script.title)
        for seg in script.segments:
            segment_names.append(seg.name)
            total_segments += 1
            for scene in seg.scenes:
                if scene.narration:
                    narration_samples.append(scene.narration)
                    words = scene.narration.lower().split()
                    for w in words:
                        cleaned = w.strip(".,!?;:\"'()-")
                        if cleaned and cleaned not in _STOPWORDS and len(cleaned) > 2:
                            word_counter[cleaned] += 1

    avg_segments = total_segments / max(1, len(scripts))
    top_words = [w for w, _ in word_counter.most_common(50)]

    return {
        "titles": titles,
        "segment_names": segment_names[:50],
        "narration_samples": narration_samples[:20],  # Cap to avoid huge prompts
        "top_words": top_words,
        "avg_segment_count": round(avg_segments, 1),
        "script_count": len(scripts),
    }


def _load_scripts() -> list[ScriptContent]:
    """Load all scripts from DB and parse their JSON content."""
    with Session(engine) as session:
        scripts = session.exec(select(Script)).all()
        parsed = []
        for s in scripts:
            try:
                content = ScriptContent.model_validate(json.loads(s.script_json))
                parsed.append(content)
            except Exception:
                logger.debug("Skipping unparseable script %s", s.id)
        return parsed


def analyze_content_profile() -> dict:
    """Build a content profile from all existing scripts and persist it."""
    scripts = _load_scripts()
    if not scripts:
        return {}

    features = _extract_features(scripts)

    # Build Claude prompt with extracted features
    user_msg = json.dumps({
        "titles": features["titles"],
        "segment_names": features["segment_names"],
        "narration_excerpts": [n[:300] for n in features["narration_samples"][:15]],
        "frequent_words": features["top_words"][:30],
        "script_count": features["script_count"],
        "avg_segments_per_video": features["avg_segment_count"],
    }, indent=2)

    logger.info("Analyzing content profile for %d scripts via Claude", features["script_count"])
    raw = chat(
        PROFILE_SYSTEM_PROMPT,
        f"Analyze this creator's content library:\n{user_msg}",
        max_tokens=1024,
    )
    result = json.loads(strip_markdown_fences(raw))

    # Persist: upsert pattern (delete old, insert new)
    profile_data = {
        "script_count": features["script_count"],
        "common_topics": json.dumps(result.get("common_topics", [])),
        "narration_style": result.get("narration_style", ""),
        "visual_approach": result.get("visual_approach", ""),
        "typical_keywords": json.dumps(result.get("typical_keywords", [])),
        "audience_profile": result.get("audience_profile", ""),
        "avg_segment_count": features["avg_segment_count"],
        "analyzed_at": datetime.now(timezone.utc),
    }

    with Session(engine) as session:
        old = session.exec(select(ContentProfile)).all()
        for o in old:
            session.delete(o)
        session.add(ContentProfile(**profile_data))
        session.commit()

    logger.info("Content profile saved (%d topics, %d keywords)",
                len(result.get("common_topics", [])), len(result.get("typical_keywords", [])))

    return _format_profile(profile_data)


def get_cached_profile() -> dict | None:
    """Return the cached content profile with staleness check, or None if not yet analyzed."""
    with Session(engine) as session:
        profile = session.exec(select(ContentProfile)).first()
        if not profile:
            return None

        # Check staleness: compare script count
        from sqlmodel import func
        current_count = session.exec(select(func.count(Script.id))).one()

        data = {
            "script_count": profile.script_count,
            "common_topics": json.loads(profile.common_topics),
            "narration_style": profile.narration_style,
            "visual_approach": profile.visual_approach,
            "typical_keywords": json.loads(profile.typical_keywords),
            "audience_profile": profile.audience_profile,
            "avg_segment_count": profile.avg_segment_count,
            "analyzed_at": profile.analyzed_at.isoformat(),
            "is_stale": current_count != profile.script_count,
        }
        return data


def _format_profile(data: dict) -> dict:
    """Format profile data for API response."""
    return {
        "script_count": data["script_count"],
        "common_topics": json.loads(data["common_topics"]) if isinstance(data["common_topics"], str) else data["common_topics"],
        "narration_style": data["narration_style"],
        "visual_approach": data["visual_approach"],
        "typical_keywords": json.loads(data["typical_keywords"]) if isinstance(data["typical_keywords"], str) else data["typical_keywords"],
        "audience_profile": data["audience_profile"],
        "avg_segment_count": data["avg_segment_count"],
        "analyzed_at": data["analyzed_at"].isoformat() if isinstance(data["analyzed_at"], datetime) else data["analyzed_at"],
        "is_stale": False,
    }
