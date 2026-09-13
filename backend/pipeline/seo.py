"""SEO metadata generation pipeline — uses the routed LLM provider for YouTube metadata."""

import json
import logging
import re

from pydantic import BaseModel

from config import strip_markdown_fences
from integrations.llm_client import chat
from integrations.local_models import active_model, attribution_for, modality_source
from models.script import ScriptContent
from prompts import SEO_SYSTEM, SHORT_FORM_SEO_SYSTEM

logger = logging.getLogger(__name__)

_PART_SUFFIX_RE = re.compile(r"\s*\(Part\s+[^)]*\)\s*$", re.IGNORECASE)

class YouTubeSEO(BaseModel):
    title: str
    description: str
    tags: list[str]

class SEOMetadata(BaseModel):
    youtube: YouTubeSEO

class ShortFormSEO(BaseModel):
    index: int
    title: str
    description: str
    hashtags: list[str]
    tags: list[str]

class ShortFormSEOMetadata(BaseModel):
    shorts: list[ShortFormSEO]


def format_timestamp(total_seconds: float) -> str:
    """Format seconds as M:SS (or H:MM:SS if >= 1 hour)."""
    total = int(total_seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def _trim_tags(tags: list[str], max_chars: int = 500) -> list[str]:
    """Trim comma-joined tags to fit platform limits."""
    trimmed: list[str] = []
    total_len = 0
    for tag in tags:
        clean = tag.strip()
        if not clean:
            continue
        separator_len = 2 if trimmed else 0
        if total_len + separator_len + len(clean) >= max_chars:
            break
        trimmed.append(clean)
        total_len += separator_len + len(clean)
    return trimmed

def _normalize_hashtags(hashtags: list[str]) -> list[str]:
    """Normalize hashtags for short-form captions."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in hashtags:
        tag = raw.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        tag = tag.replace(" ", "")
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)
    return normalized[:10]

def _split_list_text(value: str) -> list[str]:
    """Split comma/newline text into clean list items."""
    return [
        item.strip()
        for item in value.replace("\n", ",").split(",")
        if item.strip()
    ]

def _normalize_short_form_seo_data(data: dict, requested_shorts: list[dict]) -> dict:
    """Coerce common LLM response drift before strict schema validation."""
    raw_shorts = data.get("shorts")
    if not isinstance(raw_shorts, list):
        return data

    for position, item in enumerate(raw_shorts):
        if not isinstance(item, dict):
            continue

        if "index" not in item and position < len(requested_shorts):
            item["index"] = requested_shorts[position]["index"]

        if isinstance(item.get("tags"), str):
            item["tags"] = _split_list_text(item["tags"])
        elif item.get("tags") is None:
            item["tags"] = []

        if isinstance(item.get("hashtags"), str):
            item["hashtags"] = _split_list_text(item["hashtags"].replace(" #", ",#"))
        elif item.get("hashtags") is None:
            item["hashtags"] = []

    return data

def _validate_short_indices(result: ShortFormSEOMetadata, shorts: list[dict]) -> None:
    """Require exactly one metadata item for each requested short."""
    expected = sorted(int(short["index"]) for short in shorts)
    returned = sorted(short.index for short in result.shorts)
    if expected != returned:
        raise RuntimeError(
            "Short-form SEO generation returned indices "
            f"{returned}; expected exactly {expected}"
        )

def _short_form_title(project_title: str, segment_title: str) -> str:
    """Build the deterministic upload title for a short-form segment."""
    clean_project_title = strip_short_form_part_suffix(project_title.strip()) or "Untitled"
    clean_segment_title = strip_short_form_part_suffix(segment_title.strip()) or "Untitled"
    return f"{clean_project_title} - {clean_segment_title}"


def strip_short_form_part_suffix(title: str) -> str:
    """Remove legacy visible Part N/M suffixes from upload titles."""
    return _PART_SUFFIX_RE.sub("", title).strip()


def retitle_short_form_seo_metadata(metadata: dict | None, project_title: str, content: ScriptContent) -> dict | None:
    """Update stored short-form upload titles after the project title changes."""
    if not metadata:
        return metadata
    items = metadata.get("shorts")
    if not isinstance(items, list):
        return metadata

    parsed_indices: list[int] = []
    for item in items:
        try:
            parsed_indices.append(int(item.get("index", -1)))
        except (AttributeError, TypeError, ValueError):
            parsed_indices.append(-1)
    uses_one_based_indices = 1 in parsed_indices

    updated = dict(metadata)
    updated_items: list[dict] = []
    for item_idx, item in enumerate(items):
        if not isinstance(item, dict):
            updated_items.append(item)
            continue
        parsed_index = parsed_indices[item_idx]
        segment_idx = (
            parsed_index - 1 if uses_one_based_indices and parsed_index >= 1
            else parsed_index if parsed_index >= 0
            else item_idx
        )
        if 0 <= segment_idx < len(content.segments):
            item = dict(item)
            item["title"] = _short_form_title(project_title, content.segments[segment_idx].name)
        updated_items.append(item)
    updated["shorts"] = updated_items
    return updated

def build_short_form_seo_contexts(content: ScriptContent) -> list[dict]:
    """Build one transcript summary per rendered short."""
    shorts: list[dict] = []
    total = len(content.segments)
    for segment_idx, segment in enumerate(content.segments):
        scenes = list(segment.scenes)
        if segment_idx == 0 and content.hook_scene_count:
            skip = min(content.hook_scene_count, max(0, len(scenes) - 2))
            if skip > 0:
                scenes = [scenes[0]] + scenes[1 + skip:]

        narration_parts = [
            scene.narration.strip()
            for scene in scenes
            if not scene.is_title_card and scene.narration.strip()
        ]
        duration_seconds = sum(scene.audio_duration_seconds for scene in scenes)
        transcript = " ".join(narration_parts)
        shorts.append({
            "index": segment_idx + 1,
            "total": total,
            "segment_name": segment.name,
            "duration_seconds": round(duration_seconds, 1),
            "transcript": transcript[:2500],
        })
    return shorts

def required_voice_attribution(voice_engine: str = "") -> str:
    """The licence credit required by the engine that voiced this project.

    Higgs TTS 3 permits monetized video under a Creator Use Grant only when the
    work credits Boson AI, so the credit is a property of the model rather than
    a user preference. There is deliberately no setting to disable this.

    `voice_engine` is the value persisted on a scene when its audio was
    generated (e.g. "local:higgs-tts-3-4b"). It is authoritative, because the
    credit has to follow the engine that actually produced the audio — flipping
    Voice back to Cloud afterwards must not drop the credit from Higgs audio,
    and flipping it to Local must not add one to ElevenLabs audio. Falls back to
    the active mode only when a project has no recorded engine.
    """
    if voice_engine:
        local_prefix = "local:"
        if not voice_engine.startswith(local_prefix):
            return ""
        return attribution_for(voice_engine[len(local_prefix):])
    if modality_source("voice") != "local":
        return ""
    return attribution_for(active_model("voice").id)


def voice_engine_for_content(content: "ScriptContent | None") -> str:
    """The TTS engine recorded on a project's scenes, or "" when unknown.

    A project voiced across an engine switch is treated as needing every credit
    its scenes earned, so the first attribution-requiring engine wins.
    """
    if content is None:
        return ""
    engines = [
        (scene.voice_engine or "")
        for scene in content.all_scenes()
        if getattr(scene, "voice_engine", "")
    ]
    for engine in engines:
        if required_voice_attribution(engine):
            return engine
    return engines[0] if engines else ""


def apply_voice_attribution(description: str, voice_engine: str = "") -> str:
    """Append the required voice credit to a description, idempotently."""
    credit = required_voice_attribution(voice_engine)
    if not credit or credit in description:
        return description
    if not description:
        return credit
    return f"{description}\n\n{credit}"


def generate_seo(
    video_title: str,
    segments: list[tuple[str, str]],
    video_description: str = "",
    brand_context: str = "",
    script_id: str | None = None,
    voice_engine: str = "",
) -> SEOMetadata:
    """Generate SEO metadata for YouTube via the routed LLM provider.

    segments: list of (name, timestamp) tuples, e.g. [("Intro", "0:00"), ("Caffeine", "1:23")].
    """
    segment_list = "\n".join(f"- {ts} {name}" for name, ts in segments)
    user_msg = (
        f"Generate SEO metadata for this video:\n\n"
        f"Title: {video_title}\n"
        f"Segments:\n{segment_list}"
    )
    if video_description:
        user_msg += f"\n\nAdditional context: {video_description}"
    if brand_context:
        user_msg += f"\n\nBrand: {brand_context}"

    logger.info("[%s] Generating SEO metadata for %r (%d segments)", script_id or "no-id", video_title, len(segments))
    raw = chat(SEO_SYSTEM.template, user_msg, max_tokens=4096, script_id=script_id, json_mode=True, task="seo")
    text = strip_markdown_fences(raw)

    data = json.loads(text)
    yt_data = data.get("youtube", {})
    if isinstance(yt_data.get("tags"), str):
        yt_data["tags"] = [t.strip() for t in yt_data["tags"].split(",") if t.strip()]
    result = SEOMetadata.model_validate(data)
    yt = result.youtube

    yt.tags = _trim_tags(yt.tags)
    yt.description = apply_voice_attribution(yt.description, voice_engine)
    total_len = len(", ".join(yt.tags))

    logger.info("[%s] SEO metadata generated for %r (title=%d chars, %d tags, %d tag chars)", script_id or "no-id", video_title, len(yt.title), len(yt.tags), total_len)
    return result

def generate_short_form_seo(
    video_title: str,
    shorts: list[dict],
    video_description: str = "",
    brand_context: str = "",
    script_id: str | None = None,
    voice_engine: str = "",
) -> ShortFormSEOMetadata:
    """Generate one short-form SEO metadata set per rendered short."""
    user_msg = (
        f"Generate short-form metadata for every short from this long-form video.\n\n"
        f"Long-form title: {video_title}\n"
        f"Use each provided segment_name only for context. The final title field will be set by the app as "
        f"\"{{project title}} - {{segment title}}\".\n"
        f"Shorts JSON:\n{json.dumps(shorts, ensure_ascii=False, indent=2)}"
    )
    if video_description:
        user_msg += f"\n\nAdditional context: {video_description}"
    if brand_context:
        user_msg += f"\n\nBrand: {brand_context}"

    logger.info(
        "[%s] Generating short-form SEO metadata for %r (%d shorts)",
        script_id or "no-id",
        video_title,
        len(shorts),
    )
    raw = chat(
        SHORT_FORM_SEO_SYSTEM.template,
        user_msg,
        max_tokens=8192,
        script_id=script_id,
        json_mode=True,
        task="short_form_seo",
    )
    text = strip_markdown_fences(raw)
    data = json.loads(text)
    data = _normalize_short_form_seo_data(data, shorts)
    result = ShortFormSEOMetadata.model_validate(data)
    _validate_short_indices(result, shorts)

    segment_titles_by_index = {
        int(short["index"]): str(short.get("segment_name") or "").strip()
        for short in shorts
    }
    for short in result.shorts:
        short.title = _short_form_title(
            video_title,
            segment_titles_by_index.get(short.index, short.title),
        )
        short.tags = _trim_tags(short.tags)
        short.hashtags = _normalize_hashtags(short.hashtags)
        # Shorts are published independently, so each one has to carry the
        # voice model's required credit on its own.
        short.description = apply_voice_attribution(short.description, voice_engine)
    result.shorts.sort(key=lambda short: short.index)

    logger.info(
        "[%s] Short-form SEO metadata generated for %d shorts",
        script_id or "no-id",
        len(result.shorts),
    )
    return result
