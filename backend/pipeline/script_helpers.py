"""Pure-data and filesystem helpers used by api/scripts.py.

Covers the three pure-helper clusters that previously lived inline in
api/scripts.py: SEO markdown formatting, project-export folder discovery
and renaming, and API-usage cost labelling. None of these touch a DB
session or FastAPI types, so they belong in the pipeline layer.
"""

import logging
from pathlib import Path

from models.script import ScriptContent
from pipeline.export_paths import (
    downloads_base,
    has_export_label,
    longform_filename,
    project_downloads_folder,
    shortform_filename,
    shortform_video_filename,
)
from pipeline.seo import strip_short_form_part_suffix

logger = logging.getLogger(__name__)


# --- SEO markdown formatters (also used by api/render.py export_bundle) ---

def _format_longform_seo_markdown(seo: dict) -> str:
    yt = seo.get("youtube", {})
    lines: list[str] = []
    if yt.get("title"):
        lines.extend(["# Title", "", yt["title"], ""])
    if yt.get("description"):
        lines.extend(["# Description", "", yt["description"], ""])
    if yt.get("tags"):
        lines.extend(["# Tags", "", ", ".join(yt["tags"]), ""])
    return "\n".join(lines).strip() + "\n"


def _format_shortform_seo_markdown(item: dict) -> str:
    hashtags = item.get("hashtags") or []
    tags = item.get("tags") or []
    title = strip_short_form_part_suffix(str(item.get("title", "")))
    description = item.get("description", "")
    hashtags_line = " ".join(hashtags)
    tags_line = ", ".join(tags)
    lines = [
        f"# Short {item.get('index', '?')}",
        "",
        "# Youtube",
        "",
        "## Title",
        "",
        title,
        "",
        "## Description",
        "",
        description,
        "",
        "## Hashtags",
        "",
        hashtags_line,
        "",
        "## SEO Tags",
        "",
        tags_line,
        "",
        "# Tiktok / Insta",
        "",
        title,
        "",
        description,
    ]
    if hashtags:
        lines.extend(["", hashtags_line])
    if tags:
        lines.extend(["", tags_line])
    return "\n".join(lines).strip() + "\n"


# --- Project-export folder discovery / rename ---

def _short_item_index(item: dict, fallback_index: int, uses_one_based_indices: bool) -> int:
    try:
        raw = int(item.get("index", -1))
    except (TypeError, ValueError):
        raw = -1
    if uses_one_based_indices and raw >= 1:
        return raw - 1
    if raw >= 0:
        return raw
    return fallback_index


def _refresh_exported_seo_files(project_title: str, content: ScriptContent, folder: Path) -> None:
    """Rewrite exported SEO markdown after title-derived names or titles change."""
    if not folder.is_dir():
        logger.info("Skipped exported SEO refresh because project folder is missing: %s", folder)
        return

    if content.seo_metadata:
        seo_markdown = _format_longform_seo_markdown(content.seo_metadata)
        if seo_markdown.strip():
            (folder / longform_filename("SEO", project_title, ".txt")).unlink(missing_ok=True)
            dest = folder / longform_filename("SEO", project_title, ".md")
            dest.write_text(seo_markdown, encoding="utf-8")
            logger.info("Refreshed exported long-form SEO markdown: %s", dest)
    else:
        logger.info("Skipped exported long-form SEO refresh because metadata is missing")

    short_items = (content.short_form_seo_metadata or {}).get("shorts", [])
    if not isinstance(short_items, list) or not short_items:
        logger.info("Skipped exported short-form SEO refresh because metadata is missing")
        return
    parsed_indices: list[int] = []
    for item in short_items:
        try:
            parsed_indices.append(int(item.get("index", -1)))
        except (AttributeError, TypeError, ValueError):
            parsed_indices.append(-1)
    uses_one_based_indices = 1 in parsed_indices
    total_segments = len(content.segments)
    for item_idx, item in enumerate(short_items):
        if not isinstance(item, dict):
            continue
        segment_idx = _short_item_index(item, item_idx, uses_one_based_indices)
        segment_name = (
            content.segments[segment_idx].name
            if 0 <= segment_idx < total_segments
            else f"Short {item.get('index', '?')}"
        )
        n = (segment_idx + 1) if 0 <= segment_idx < total_segments else (item_idx + 1)
        (folder / shortform_filename("SEO", segment_name, ".txt", index=n, total=total_segments)).unlink(missing_ok=True)
        dest = folder / shortform_filename("SEO", segment_name, ".md", index=n, total=total_segments)
        dest.write_text(
            _format_shortform_seo_markdown(item),
            encoding="utf-8",
        )
        logger.info("Refreshed exported short-form SEO markdown: %s", dest)


def _normalize_exported_longform_filenames(project_title: str, folder: Path) -> None:
    """Retitle long-form export filenames inside a known project folder."""
    if not folder.is_dir():
        logger.info("Skipped long-form export filename normalization because project folder is missing: %s", folder)
        return

    for file in sorted(folder.iterdir(), key=lambda path: path.name):
        if not file.is_file():
            continue
        for asset in ("Video", "Thumbnail", "SEO"):
            if not has_export_label(file.name, "Longform", asset):
                continue
            dest = folder / longform_filename(asset, project_title, file.suffix)
            if file == dest:
                break
            if dest.exists():
                if asset == "SEO":
                    file.unlink()
                    logger.info("Removed stale exported long-form SEO filename after title rename: %s", file)
                else:
                    logger.info("Skipped long-form export filename rename because destination exists: %s", dest)
                break
            file.rename(dest)
            logger.info("Renamed long-form export file %s to %s", file, dest)
            break


def _exports_folder_score(folder: Path, content: ScriptContent) -> int:
    """Score how confidently a project export folder belongs to this script."""
    if not folder.is_dir():
        return 0

    short_asset_score = 0
    total = len(content.segments)
    for idx, segment in enumerate(content.segments):
        n = idx + 1
        if (folder / shortform_video_filename(segment.name, n, total)).is_file():
            short_asset_score += 6
        if (folder / shortform_filename("Thumbnail", segment.name, ".png", index=n, total=total)).is_file():
            short_asset_score += 3
        if (folder / shortform_filename("SEO", segment.name, ".md", index=n, total=total)).is_file():
            short_asset_score += 2

    if short_asset_score == 0:
        return 0

    score = short_asset_score
    for file in folder.iterdir():
        if not file.is_file():
            continue
        if has_export_label(file.name, "Longform", "Video"):
            score += 5
        elif has_export_label(file.name, "Longform", "Thumbnail"):
            score += 3
        elif has_export_label(file.name, "Longform", "SEO"):
            score += 2
    return score


def _find_exports_folder_for_title_rename(old_title: str, new_title: str, content: ScriptContent) -> Path | None:
    """Find existing exports even when a previous title edit left the folder under an older title."""
    old_folder = project_downloads_folder(old_title, create=False)
    if old_folder.is_dir():
        return old_folder

    new_folder = project_downloads_folder(new_title, create=False)
    if new_folder.is_dir() and _exports_folder_score(new_folder, content) > 0:
        return new_folder

    base = downloads_base()
    if not base.is_dir():
        logger.info("Exports base does not exist while searching for title rename folder: %s", base)
        return None

    candidates: list[tuple[int, Path]] = []
    for folder in base.glob("[[]project[]] *"):
        score = _exports_folder_score(folder, content)
        if score > 0:
            candidates.append((score, folder))

    if not candidates:
        logger.info("No content-matching export folder found for title rename from %r to %r", old_title, new_title)
        return None

    candidates.sort(key=lambda item: (item[0], item[1].stat().st_mtime), reverse=True)
    best_score, best_folder = candidates[0]
    logger.info(
        "Discovered export project folder for title rename by matching script assets: %s (score=%d)",
        best_folder,
        best_score,
    )
    return best_folder


# --- API-usage cost labelling ---

def _usage_task_label(service: str, operation: str, metadata_json: str) -> str:
    """Return a human-readable task label for a usage row."""
    import json

    task = ""
    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
            task = str(metadata.get("task") or "")
        except (TypeError, ValueError):
            task = ""

    key = task or operation
    labels = {
        "tts": "Generate Audio",
        "image_gen": "Generate Images",
        "chat": "AI Text Tasks",
        "script": "Write Script",
        "fx": "Generate FX",
        "eli": "Add Eli",
        "title_card": "Title Cards",
        "hook": "Hook Score",
        "seo": "SEO Metadata",
        "media": "Media Analysis",
        "refine": "Scene Refinement",
        "duration": "Duration Fixes",
        "idea": "Ideas",
        "analysis": "Analysis",
        "hook_detect": "Hook Detection",
    }
    if key in labels:
        return labels[key]
    if service == "elevenlabs":
        return "Generate Audio"
    if service in {"google_ai", "replicate"}:
        return "Generate Images"
    return key.replace("_", " ").title() if key else "Other"
