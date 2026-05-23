"""Thumbnail pipeline — composite title card lookup.

When the title_cards modifier is active and a composite title card exists,
it is used directly as the thumbnail.
"""

import json
import logging
import os
import random
import re
import shutil
import threading
from hashlib import sha256
from pathlib import Path
from typing import Literal

from config import DATA_DIR
from prompts import IMAGE_CTR_EXPRESSION_GUIDANCE

logger = logging.getLogger(__name__)

_LONGFORM_THUMB_RE = re.compile(r"^(\d+)\.png$")
_LONGFORM_THUMB_LOCKS: dict[str, threading.Lock] = {}
_LONGFORM_THUMB_LOCKS_GUARD = threading.Lock()
_EARLY_LIFE_AS_A_THUMBNAIL_LABELS = tuple(f"{months} months in" for months in range(3, 9))
_LATE_LIFE_AS_A_THUMBNAIL_LABELS = tuple(f"{years} years in" for years in range(8, 16))
_LEVEL_LABEL_RE = re.compile(r"^LEVEL [1-9]\d?$")

ThumbnailLabelStyle = Literal["time_periods", "levels"]
DEFAULT_THUMBNAIL_LABEL_STYLE: ThumbnailLabelStyle = "time_periods"


def _longform_thumbnail_lock(script_id: str) -> threading.Lock:
    with _LONGFORM_THUMB_LOCKS_GUARD:
        lock = _LONGFORM_THUMB_LOCKS.get(script_id)
        if lock is None:
            lock = threading.Lock()
            _LONGFORM_THUMB_LOCKS[script_id] = lock
        return lock


def _pick_time_period_thumbnail_labels() -> tuple[str, str]:
    """Pick early/late time-period labels for a life-as-a split thumbnail."""
    return (
        random.choice(_EARLY_LIFE_AS_A_THUMBNAIL_LABELS),
        random.choice(_LATE_LIFE_AS_A_THUMBNAIL_LABELS),
    )


def _pick_level_thumbnail_labels(n_levels: int) -> tuple[str, str]:
    """Pick a (left, right) ``LEVEL X`` / ``LEVEL Y`` label pair.

    left ∈ {1, 2}, right ∈ {n_levels-1, n_levels}, ensuring left < right.
    """
    assert n_levels >= 2, f"_pick_level_thumbnail_labels requires n_levels >= 2, got {n_levels}"
    left_candidates = [n for n in (1, 2) if n < n_levels]
    right_candidates = [n for n in (n_levels - 1, n_levels) if n > 1]
    left = random.choice(left_candidates)
    right_choices = [n for n in right_candidates if n > left]
    if not right_choices:
        right_choices = right_candidates
    right = random.choice(right_choices)
    if left >= right:
        left, right = 1, n_levels
    return (f"LEVEL {left}", f"LEVEL {right}")


def _pick_life_as_a_thumbnail_labels(
    style: ThumbnailLabelStyle = DEFAULT_THUMBNAIL_LABEL_STYLE,
    n_levels: int | None = None,
) -> tuple[str, str]:
    """Pick split-progression labels for the active style.

    For ``"time_periods"``, returns lowercase ``"X months in"`` / ``"Y years in"``.
    For ``"levels"``, returns ``"LEVEL X"`` / ``"LEVEL Y"`` based on ``n_levels``.
    """
    if style == "levels":
        if n_levels is None:
            raise ValueError("n_levels is required for style='levels'")
        return _pick_level_thumbnail_labels(n_levels)
    return _pick_time_period_thumbnail_labels()


def _write_life_as_a_thumbnail_label_sidecar(
    path: Path,
    style: ThumbnailLabelStyle,
    left_label: str,
    right_label: str,
) -> None:
    """Persist the chosen labels (with their style) next to the thumbnail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "style": style,
        "left_label": left_label,
        "right_label": right_label,
    }))


def _read_life_as_a_thumbnail_label_sidecar(
    path: Path,
) -> tuple[ThumbnailLabelStyle, str, str] | None:
    """Read persisted labels. Returns ``(style, left, right)`` or None.

    Falls back to ``style="time_periods"`` for back-compat sidecars without
    a style field. Rejects legacy ``{"left_level": …}`` schemas.
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    left = data.get("left_label")
    right = data.get("right_label")
    if not isinstance(left, str) or not isinstance(right, str):
        return None
    style = data.get("style")
    if style not in ("time_periods", "levels"):
        # Back-compat: infer time_periods from label shape.
        if (
            left in _EARLY_LIFE_AS_A_THUMBNAIL_LABELS
            and right in _LATE_LIFE_AS_A_THUMBNAIL_LABELS
        ):
            return ("time_periods", left, right)
        return None
    if style == "time_periods":
        if left not in _EARLY_LIFE_AS_A_THUMBNAIL_LABELS:
            return None
        if right not in _LATE_LIFE_AS_A_THUMBNAIL_LABELS:
            return None
        return ("time_periods", left, right)
    # style == "levels"
    if not _LEVEL_LABEL_RE.match(left) or not _LEVEL_LABEL_RE.match(right):
        return None
    return ("levels", left, right)


def enhance_split_progression(
    clean_image_path: Path,
    output_path: Path,
    left_label: str,
    right_label: str,
    script_id: str | None = None,
    force: bool = False,
    style: ThumbnailLabelStyle | None = None,
) -> Path:
    """Transform a single iconic life-as-a thumbnail into a split-progression thumbnail.

    Sends the clean image to Gemini with the SPLIT_PROGRESSION_PROMPT (with
    {left_label} / {right_label} substituted) and writes the result to output_path.

    Caches by mtime plus prompt/label fingerprint: re-runs if output is missing,
    source is newer, prompt or labels changed, style changed, or force=True.
    On Gemini failure, falls back to copying the clean image to output_path.
    """
    from integrations.google_image_client import transform_with_references
    from prompts import SPLIT_PROGRESSION_PROMPT

    prompt = SPLIT_PROGRESSION_PROMPT.template.format(
        left_label=left_label,
        right_label=right_label,
    )
    cache_metadata_path = output_path.with_suffix(f"{output_path.suffix}.cache.json")
    prompt_hash = sha256(prompt.encode("utf-8")).hexdigest()

    # mtime cache check
    if not force and output_path.exists():
        try:
            cache_metadata = json.loads(cache_metadata_path.read_text())
            cache_matches = (
                cache_metadata.get("prompt_hash") == prompt_hash
                and cache_metadata.get("left_label") == left_label
                and cache_metadata.get("right_label") == right_label
                and cache_metadata.get("style") == style
            )
            if (
                cache_matches
                and output_path.stat().st_mtime >= clean_image_path.stat().st_mtime
            ):
                logger.info(
                    "[%s] split-progression cache hit: %s",
                    script_id or "no-id", output_path,
                )
                return output_path
        except (OSError, json.JSONDecodeError):
            pass  # Fall through and regenerate

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_metadata_path.unlink(missing_ok=True)

    try:
        result_path = transform_with_references(
            prompt=prompt,
            image_paths=[str(clean_image_path)],
            script_id=script_id,
        )
        shutil.copy2(result_path, str(output_path))
        cache_metadata_path.write_text(json.dumps({
            "prompt_hash": prompt_hash,
            "left_label": left_label,
            "right_label": right_label,
            "style": style,
        }))
        logger.info(
            "[%s] split-progression thumbnail written: %s (%s / %s)",
            script_id or "no-id", output_path, left_label, right_label,
        )
        return output_path
    except Exception as exc:
        logger.warning(
            "[%s] split-progression Gemini call failed (%s); falling back to clean image",
            script_id or "no-id", exc,
        )
        shutil.copy2(str(clean_image_path), str(output_path))
        return output_path


def _cache_bust(url: str, file_path: str) -> str:
    """Append file mtime as query param to bust browser cache."""
    try:
        mtime = int(os.path.getmtime(file_path))
        return f"{url}?t={mtime}"
    except OSError:
        return url


def _longform_thumbnails_dir(script_id: str) -> Path:
    thumbs_dir = DATA_DIR / "projects" / script_id / "renders" / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    return thumbs_dir


def _next_longform_thumbnail_path(script_id: str) -> Path:
    thumbs_dir = _longform_thumbnails_dir(script_id)
    highest = 0
    for file in thumbs_dir.iterdir():
        match = _LONGFORM_THUMB_RE.match(file.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return thumbs_dir / f"{highest + 1}.png"


def archive_current_longform_thumbnail(script_id: str) -> Path | None:
    """Save the current active long-form thumbnail as a numbered variant.

    ``0.png`` remains the active thumbnail used by exports and upload helpers.
    Before regeneration replaces it, copy the previous current image to the
    next numbered sibling so users can compare versions in the UI.
    """
    with _longform_thumbnail_lock(script_id):
        current = _longform_thumbnails_dir(script_id) / "0.png"
        if not current.is_file():
            return None
        archived = _next_longform_thumbnail_path(script_id)
        shutil.copy2(str(current), str(archived))
        return archived


def replace_active_longform_thumbnail(
    script_id: str,
    source: Path,
    archive_existing: bool = True,
) -> str:
    """Optionally archive the active thumbnail, then replace it atomically per script."""
    with _longform_thumbnail_lock(script_id):
        thumbs_dir = _longform_thumbnails_dir(script_id)
        thumb_path = thumbs_dir / "0.png"
        if archive_existing and thumb_path.is_file():
            archived = _next_longform_thumbnail_path(script_id)
            shutil.copy2(str(thumb_path), str(archived))
        shutil.copy2(str(source), str(thumb_path))
    url = f"/static/projects/{script_id}/renders/thumbnails/0.png"
    return _cache_bust(url, str(thumb_path))


def write_active_longform_thumbnail(script_id: str, source: Path) -> str:
    """Copy ``source`` to the active long-form thumbnail slot and return its URL."""
    return replace_active_longform_thumbnail(script_id, source, archive_existing=False)


def promote_longform_thumbnail(script_id: str, idx: int) -> str:
    """Make ``idx.png`` the active thumbnail (``0.png``).

    Archives the current 0.png to the next free slot, then renames
    ``idx.png`` → ``0.png``. Returns the cache-busted URL of the new active.
    Raises FileNotFoundError if idx.png does not exist.
    Raises ValueError if idx == 0.
    """
    if idx == 0:
        raise ValueError("idx 0 is already active")
    with _longform_thumbnail_lock(script_id):
        thumbs_dir = _longform_thumbnails_dir(script_id)
        target = thumbs_dir / f"{idx}.png"
        active = thumbs_dir / "0.png"
        if not target.is_file():
            raise FileNotFoundError(f"thumbnail variant {idx} not found")
        if active.is_file():
            archived = _next_longform_thumbnail_path(script_id)
            shutil.move(str(active), str(archived))
        shutil.move(str(target), str(active))
    return _cache_bust(
        f"/static/projects/{script_id}/renders/thumbnails/0.png",
        str(active),
    )


def list_longform_thumbnails(script_id: str) -> list[tuple[int, str]]:
    """Return saved long-form thumbnail variants as ``(idx, cache-busted URL)``.

    The active thumbnail (0.png) is returned first. Older archived variants are
    returned newest-first by numeric filename.
    """
    thumbs_dir = DATA_DIR / "projects" / script_id / "renders" / "thumbnails"
    if not thumbs_dir.is_dir():
        return []

    found: list[tuple[int, Path]] = []
    for file in thumbs_dir.iterdir():
        match = _LONGFORM_THUMB_RE.match(file.name)
        if match and file.is_file():
            found.append((int(match.group(1)), file))

    found.sort(key=lambda item: (item[0] != 0, -item[0] if item[0] != 0 else 0))
    return [
        (
            idx,
            _cache_bust(f"/static/projects/{script_id}/renders/thumbnails/{idx}.png", str(path)),
        )
        for idx, path in found
    ]


def get_composite_thumbnail(script_id: str) -> str | None:
    """Return a web path for the script's primary thumbnail, if one exists.

    Tries cinematic_thumbnail.png (life-as-a / cinematic-chapters) first, then
    falls back to composite_title_card.png (youtube-listicle / composite-grid).
    The two files are mutually exclusive on disk per format, so trying both is
    safe and keeps callers format-agnostic.
    """
    images_dir = DATA_DIR / "projects" / script_id / "images"
    candidates = [
        images_dir / "cinematic_thumbnail.png",
        images_dir / "composite_title_card.png",
    ]
    for source in candidates:
        if source.exists():
            return write_active_longform_thumbnail(script_id, source)
    return None


def get_composite_thumbnail_no_eli(script_id: str) -> str | None:
    """Check if a no-Eli composite title card exists and return its web path if so."""
    composite = DATA_DIR / "projects" / script_id / "images" / "composite_title_card_no_eli.png"
    if composite.exists():
        thumbs_dir = DATA_DIR / "projects" / script_id / "renders" / "thumbnails"
        thumbs_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumbs_dir / "0_no_eli.png"
        shutil.copy2(str(composite), str(thumb_path))
        url = f"/static/projects/{script_id}/renders/thumbnails/0_no_eli.png"
        return _cache_bust(url, str(thumb_path))
    return None


THUMBNAIL_REFERENCES_DIR = DATA_DIR / "character" / "thumbnail_references"

# CTR expression tier guidance for Gemini prompt
_CTR_EXPRESSION_GUIDANCE = IMAGE_CTR_EXPRESSION_GUIDANCE.template


def gemini_enhance_thumbnail(
    base_image_path: str,
    video_title: str,
    script_id: str | None = None,
) -> str | None:
    """Enhance a base title card composite using Gemini with reference thumbnails.

    Sends the base image + a reference thumbnail + a random Eli character frame
    to Gemini, which chooses ONE segment circle and replaces it with Eli bursting
    out as a portal. All other segment circles must be preserved exactly.

    Args:
        base_image_path: Path to the base Pillow-generated composite.
        video_title: The video title (provides context for expression selection).
        script_id: Optional script ID for usage tracking.

    Returns:
        Path to the enhanced image, or None if enhancement can't be performed
        (no references uploaded, no character frames, etc.).
    """
    logger.info("[%s] Starting Gemini thumbnail enhancement for %r", script_id or "no-id", video_title)

    from integrations.google_image_client import transform_with_references
    from pipeline.character_frames import get_manifest, FRAMES_DIR

    # Check for reference thumbnails
    ref_dir = THUMBNAIL_REFERENCES_DIR
    if not ref_dir.exists():
        logger.info("No thumbnail references directory — skipping enhancement")
        return None

    ref_files = [
        f for f in ref_dir.iterdir()
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    ]
    if not ref_files:
        logger.info("No thumbnail references uploaded — skipping enhancement")
        return None

    logger.info("[%s] Found %d thumbnail references", script_id or "no-id", len(ref_files))

    # Pick a random reference thumbnail
    ref_path = str(random.choice(ref_files))
    logger.info("Using thumbnail reference: %s", ref_path)

    # Pick a random Eli character frame
    eli_frame_path = None
    try:
        manifest = get_manifest()
        if manifest and manifest.get("frames"):
            # Prefer thumbnail frames with open mouth
            thumbnail_frames = manifest.get("thumbnail_frames", [])
            frames = thumbnail_frames if thumbnail_frames else manifest["frames"]
            frame = random.choice(frames)
            mouth_key = "file_open" if thumbnail_frames else "file_closed"
            file_name = frame.get(mouth_key, "")
            if file_name:
                candidate = FRAMES_DIR / file_name
                if candidate.exists():
                    eli_frame_path = str(candidate)
                    logger.info("[%s] Selected Eli frame for thumbnail: %s", script_id or "no-id", file_name)
    except Exception as exc:
        logger.debug("Could not load Eli frame for thumbnail: %s", exc)

    # Build image list: base image first, then reference, then Eli frame
    image_paths = [base_image_path, ref_path]
    if eli_frame_path:
        image_paths.append(eli_frame_path)

    # Build prompt
    character_instruction = ""
    if eli_frame_path:
        character_instruction = (
            "CHARACTER INSERTION:\n"
            "The third image is a character. Choose ONE segment circle AT RANDOM (you pick which one) "
            "and turn it into a portal with this character BURSTING OUT of it. "
            "The character should be MUCH larger than the circle — the circle acts as "
            "a portal he is emerging from. His head and upper body should extend dramatically past the "
            "circle boundary (about 60-75% overflow), with the circle sitting around his waist/hips area. "
            "His hands should grip the circle edge as if climbing out of it. "
            "Add a glowing blue plasma vortex effect inside and around the portal circle.\n\n"
            "PORTAL ALIGNMENT — CRITICAL:\n"
            "The portal circle MUST be drawn at the EXACT same center pixel coordinates and EXACT "
            "same radius as the original segment circle you are replacing. It must snap PERFECTLY "
            "onto the grid cell — do NOT shift it left, right, up, or down even by a few pixels. "
            "Do NOT draw the portal between two circles or overlapping into adjacent cells. "
            "The portal boundary and the original circle boundary must be pixel-aligned.\n\n"
            "Keep the segment label badge beneath the portal circle readable.\n"
            "Do NOT add any arrow, pointer, caret, callout line, or direction marker anywhere in the image.\n\n"
            f"{_CTR_EXPRESSION_GUIDANCE}\n\n"
        )

    prompt = (
        "You are a YouTube thumbnail optimizer. You have been given:\n"
        "1. A base title card image with a grid of circular segment thumbnails, each with a label badge below it.\n"
        "2. A reference thumbnail showing the target visual style.\n"
        f"{'3. A character image to insert into the title card.' if eli_frame_path else ''}\n\n"
        "Your task:\n"
        "- Study the reference thumbnail's visual style (circle borders, glow effects, "
        "character positioning, title treatment).\n"
        f"{character_instruction}"
        "- Apply the reference thumbnail's circle border styling (glowing magical borders) "
        "to ALL circles in the image.\n"
        "- You may enhance the existing main title's style, but you must preserve its exact wording. "
        "Do not add any secondary headline, subtitle, kicker, tagline, badge text, or red promise phrase.\n"
        "- TITLE MUST FIT IN FRAME — NO CUTOFF: Every letter of the title must be fully visible inside "
        "the image. Do NOT let the first letter clip past the left edge or the last letter clip past the "
        "right edge. Keep at least a 30px margin between the first/last letter and the frame edge. If your "
        "styling would push the title past the edges, scale the title DOWN until every letter fits — never "
        "scale it up beyond what fits in the frame. It is a hard failure to crop any letter of the title.\n"
        f'- The video title is: "{video_title}".\n'
        "- Optimize everything for maximum YouTube CTR.\n\n"
        "CRITICAL RULES — violations are bugs:\n"
        "- TEXT LOCK: The only allowed text is text already present in the base image: the main title "
        "and the existing segment label badges. Do NOT create new words anywhere else.\n"
        "- Do NOT copy any text from the reference thumbnail. Use its lighting, contrast, borders, "
        "composition energy, and character treatment only.\n"
        "- Do NOT add title subtitles or taglines such as 'DEBUNKED FOREVER', 'EXPLAINED', "
        "'THE TRUTH', 'SHOCKING FACTS', or any similar invented phrase.\n"
        "- You MAY replace EXACTLY ONE segment circle (the one you chose) with the character portal. "
        "Every OTHER segment circle must be preserved EXACTLY as in the base image — "
        "same interior image, same label text, same position. Do NOT redraw them from memory.\n"
        "- DO NOT duplicate any segment's image or label into another cell. Every segment label "
        "must stay unique. If you find yourself repeating a label (e.g. 'BOY IN THE BOX' twice), stop and correct it.\n"
        "- DO NOT leave any segment blank, faded, or missing.\n"
        "- DO NOT invent extra segments or add/remove circles — the grid size must match the input exactly.\n"
        "- DO NOT add a second copy of the character anywhere else in the image.\n\n"
        "- DO NOT add any arrow, pointer, caret, callout line, or direction marker anywhere in the image.\n\n"
        "Return the modified image."
    )

    try:
        result_path = transform_with_references(
            prompt=prompt,
            image_paths=image_paths,
            script_id=script_id,
        )
        logger.info("Gemini thumbnail enhancement complete: %s", result_path)
        return result_path
    except Exception as exc:
        logger.warning("Gemini thumbnail enhancement failed, using base image: %s", exc)
        return None
