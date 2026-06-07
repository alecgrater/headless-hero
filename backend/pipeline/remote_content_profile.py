"""Analyze uploaded content-profile input snapshots for GitHub Actions."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import parse_json_response
from integrations.llm_client import chat
from pipeline.discovery_seed import build_discovery_seed
from prompts import PROFILE_SYSTEM

REMOTE_CONTENT_PROFILE_PATH = (
    Path(__file__).resolve().parents[2] / "frontend" / "public" / "discovery" / "content-profile.json"
)

_STOPWORDS = frozenset(
    "the a an and or but in on at to for of is it this that with from by as are was were "
    "be been being have has had do does did will would could should may might shall can "
    "not no nor so if then than too very just about also how what when where which who "
    "whom why each every all both few more most other some such many much own same "
    "into over after before between through during without again further once here there "
    "their its our your my his her we they them us you he she me him i".split()
)


def _clean_words(text: str) -> list[str]:
    words: list[str] = []
    for word in re.split(r"\s+", text.lower()):
        cleaned = word.strip(".,!?;:\"'()-")
        if cleaned and cleaned not in _STOPWORDS and len(cleaned) > 2:
            words.append(cleaned)
    return words


def _parse_profile_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_remote_content_profile(path: Path | str = REMOTE_CONTENT_PROFILE_PATH) -> dict[str, Any] | None:
    """Read the Actions-generated public content profile artifact when available."""
    profile_path = Path(path)
    if not profile_path.exists():
        return None
    try:
        payload = json.loads(profile_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        script_count = int(payload.get("script_count") or 0)
        avg_segment_count = float(payload.get("avg_segment_count") or 0.0)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(avg_segment_count):
        return None
    if script_count <= 0:
        return None
    required = {
        "common_topics": list,
        "typical_keywords": list,
        "narration_style": str,
        "visual_approach": str,
        "audience_profile": str,
        "analyzed_at": str,
    }
    for key, expected_type in required.items():
        if not isinstance(payload.get(key), expected_type):
            return None
    return {
        "script_count": script_count,
        "common_topics": payload["common_topics"],
        "narration_style": payload["narration_style"],
        "visual_approach": payload["visual_approach"],
        "typical_keywords": payload["typical_keywords"],
        "audience_profile": payload["audience_profile"],
        "avg_segment_count": avg_segment_count,
        "analyzed_at": payload["analyzed_at"],
        "is_stale": bool(payload.get("is_stale", False)),
    }


def choose_freshest_profile(
    local: dict[str, Any] | None,
    remote: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Prefer the newer valid profile, allowing Actions to refresh the app profile."""
    if not local:
        return remote
    if not remote:
        return local
    local_at = _parse_profile_datetime(local.get("analyzed_at"))
    remote_at = _parse_profile_datetime(remote.get("analyzed_at"))
    if remote_at and (local_at is None or remote_at > local_at):
        return remote
    return local


def _extract_snapshot_features(snapshot: dict[str, Any]) -> dict[str, Any]:
    titles: list[str] = []
    segment_names: list[str] = []
    narration_samples: list[str] = []
    visual_modes: Counter[str] = Counter()
    word_counter: Counter[str] = Counter()
    total_segments = 0
    scripts = [script for script in snapshot.get("scripts", []) if isinstance(script, dict)]

    for script in scripts:
        title = script.get("title")
        if isinstance(title, str) and title.strip():
            titles.append(title.strip())
        segments = [segment for segment in script.get("segments", []) if isinstance(segment, dict)]
        total_segments += len(segments)
        for segment in segments:
            name = segment.get("name")
            if isinstance(name, str) and name.strip():
                segment_names.append(name.strip())
            for scene in segment.get("scenes", []):
                if not isinstance(scene, dict):
                    continue
                mode = scene.get("visual_mode")
                if isinstance(mode, str) and mode:
                    visual_modes[mode] += 1
                narration = scene.get("narration")
                if isinstance(narration, str) and narration.strip():
                    narration_samples.append(narration.strip())
                    word_counter.update(_clean_words(narration))

    avg_segments = total_segments / max(1, len(scripts))
    return {
        "titles": titles,
        "segment_names": segment_names[:50],
        "narration_samples": narration_samples[:20],
        "top_words": [word for word, _ in word_counter.most_common(50)],
        "visual_modes": dict(visual_modes.most_common()),
        "avg_segment_count": round(avg_segments, 1),
        "script_count": len(scripts),
    }


def analyze_content_profile_snapshot(
    snapshot: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a ContentProfileRead-shaped profile from an uploaded snapshot."""
    features = _extract_snapshot_features(snapshot)
    user_msg = json.dumps(
        {
            "titles": features["titles"],
            "segment_names": features["segment_names"],
            "narration_excerpts": [n[:300] for n in features["narration_samples"][:15]],
            "frequent_words": features["top_words"][:30],
            "visual_modes": features["visual_modes"],
            "script_count": features["script_count"],
            "avg_segments_per_video": features["avg_segment_count"],
        },
        indent=2,
    )
    raw = chat(
        PROFILE_SYSTEM.template,
        f"Analyze this creator's content library from a remote JSON snapshot:\n{user_msg}",
        max_tokens=1024,
        json_mode=True,
        task="analysis",
    )
    result = parse_json_response(raw)
    if not isinstance(result, dict):
        raise ValueError("Remote content profile analysis returned non-object JSON")
    analyzed_at = now or datetime.now(timezone.utc)
    return {
        "script_count": features["script_count"],
        "common_topics": result.get("common_topics", []),
        "narration_style": result.get("narration_style", ""),
        "visual_approach": result.get("visual_approach", ""),
        "typical_keywords": result.get("typical_keywords", []),
        "audience_profile": result.get("audience_profile", ""),
        "avg_segment_count": features["avg_segment_count"],
        "analyzed_at": analyzed_at.isoformat(),
        "is_stale": False,
    }


def build_remote_profile_artifacts(snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the public profile and sanitized discovery seed artifacts."""
    profile = analyze_content_profile_snapshot(snapshot)
    seed = build_discovery_seed(profile)
    return profile, seed
