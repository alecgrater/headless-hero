"""Programmatic short-form thumbnail generation.

Creates TikTok-safe 9:16 PNG covers from each segment title-card image. The
center 1:1 crop carries the important title text so profile grids stay useful.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from config import DATA_DIR
from models.script import ScriptContent
from pipeline.export_paths import project_downloads_folder, shortform_filename
from pipeline.formats import resolve_format
from pipeline.short_form_parts import short_form_part_indicator

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None

SHORT_THUMB_WIDTH = 1080
SHORT_THUMB_HEIGHT = 1920
FOCAL_SIZE = 980
IMAGE_TEXT_GAP = 40
PART_LABEL_GAP = 28
COMPOSITION_TOP_BIAS = 30
TEXT_MAX_HEIGHT = 280
TEXT_MAX_WIDTH = 920
MAX_PNG_BYTES = 2 * 1024 * 1024

_BUNDLED_TITLE_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Anton-Regular.ttf"
_BUNDLED_BODY_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "PermanentMarker-Regular.ttf"


def _thumbs_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders" / "short_thumbnails"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _source_image_path(script_id: str, segment_idx: int, content: ScriptContent) -> Path:
    """Resolve the per-segment source image path per the script's format.

    composite-grid (youtube-listicle): images/title_card_{idx}.png
    cinematic-chapters (life-as-a): images/chapter_{idx + 1}.png
    """
    images_dir = DATA_DIR / "projects" / script_id / "images"
    fmt = resolve_format(content.format_id)
    if fmt.title_card_strategy.kind == "cinematic-chapters":
        return images_dir / f"chapter_{segment_idx + 1}.png"
    return images_dir / f"title_card_{segment_idx}.png"


def _web_url(script_id: str, segment_idx: int) -> str:
    return f"/static/projects/{script_id}/renders/short_thumbnails/{segment_idx}.png"


def short_thumbnail_title(content: ScriptContent, segment_idx: int) -> str:
    """Return display text for a short thumbnail: short_name, then full name."""
    segment = content.segments[segment_idx]
    return (segment.short_name or segment.name or f"Short {segment_idx + 1}").strip()


def short_thumbnail_filename(segment_name: str, n: int, total: int) -> str:
    """Build export filename for a segment thumbnail."""
    return shortform_filename("Thumbnail", segment_name, ".png", index=n, total=total)


def _load_font(size: int, *, title: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        str(_BUNDLED_TITLE_FONT if title else _BUNDLED_BODY_FONT),
        "/System/Library/Fonts/Avenir Next Condensed.ttc",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default(size=size)


def _cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _contain_resize(image: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(max_size, Image.Resampling.LANCZOS)
    return copy


def _text_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    stroke_width: int = 0,
) -> tuple[int, int, int, int]:
    return draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)


def _text_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    stroke_width: int = 0,
) -> tuple[int, int]:
    bbox = _text_bbox(draw, text, font, stroke_width)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap_for_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    words = text.upper().split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _text_size(draw, candidate, font, stroke_width=8)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_height: int,
) -> tuple[ImageFont.FreeTypeFont, list[str], int, list[tuple[int, int, int, int]]]:
    for size in range(210, 24, -6):
        font = _load_font(size, title=True)
        lines = _wrap_for_font(draw, text, font, max_width)
        line_gap = max(8, int(size * 0.08))
        bboxes = [_text_bbox(draw, line, font, stroke_width=8) for line in lines]
        heights = [bbox[3] - bbox[1] for bbox in bboxes]
        total_h = sum(heights) + line_gap * (len(lines) - 1)
        widest = max((bbox[2] - bbox[0] for bbox in bboxes), default=0)
        if total_h <= max_height and widest <= max_width:
            return font, lines, line_gap, bboxes
    font = _load_font(24, title=True)
    lines = _wrap_for_font(draw, text, font, max_width)
    bboxes = [_text_bbox(draw, line, font, stroke_width=8) for line in lines]
    return font, lines, 6, bboxes


def _fit_single_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    *,
    start_size: int,
    min_size: int = 28,
    title: bool = True,
    stroke_width: int = 0,
) -> tuple[ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
    for size in range(start_size, min_size - 1, -4):
        font = _load_font(size, title=title)
        bbox = _text_bbox(draw, text, font, stroke_width=stroke_width)
        if bbox[2] - bbox[0] <= max_width:
            return font, bbox
    font = _load_font(min_size, title=title)
    return font, _text_bbox(draw, text, font, stroke_width=stroke_width)


def _save_png_under_limit(image: Image.Image, output_path: Path) -> None:
    rgb = image.convert("RGB")
    rgb.save(output_path, format="PNG", optimize=True, compress_level=9, dpi=(72, 72))
    if output_path.stat().st_size <= MAX_PNG_BYTES:
        return

    # Quantize only when needed. Step down the palette until the PNG fits.
    for colors in (256, 192, 128, 96, 64, 48, 32):
        quantized = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
        quantized.save(output_path, format="PNG", optimize=True, compress_level=9, dpi=(72, 72))
        if output_path.stat().st_size <= MAX_PNG_BYTES:
            return


def generate_short_thumbnail(
    script_id: str,
    segment_idx: int,
    content: ScriptContent,
    on_progress: ProgressCallback = None,
) -> str:
    """Generate one vertical thumbnail and return its web path."""
    if segment_idx < 0 or segment_idx >= len(content.segments):
        raise RuntimeError(f"segment_idx {segment_idx} out of range")

    src_path = _source_image_path(script_id, segment_idx, content)
    if not src_path.exists():
        raise RuntimeError(
            f"Title-card image missing for segment {segment_idx + 1}. Generate title card images first."
        )

    if on_progress:
        on_progress(0.1, "Loading source image...")

    source = Image.open(src_path).convert("RGB")
    background = _cover_resize(source, (SHORT_THUMB_WIDTH, SHORT_THUMB_HEIGHT))
    background = ImageEnhance.Color(background).enhance(0.86)
    background = ImageEnhance.Brightness(background).enhance(0.45)
    background = background.filter(ImageFilter.GaussianBlur(30))
    canvas = background.convert("RGBA")

    if on_progress:
        on_progress(0.35, "Building vertical composition...")

    focal = _contain_resize(source, (FOCAL_SIZE, FOCAL_SIZE))
    focal = ImageEnhance.Color(focal).enhance(1.18)
    focal = ImageEnhance.Contrast(focal).enhance(1.08)

    text = short_thumbnail_title(content, segment_idx)
    part_label = short_form_part_indicator(content, segment_idx)
    measure_draw = ImageDraw.Draw(canvas)
    font, lines, line_gap, line_bboxes = _fit_text(measure_draw, text, TEXT_MAX_WIDTH, TEXT_MAX_HEIGHT)
    heights = [bbox[3] - bbox[1] for bbox in line_bboxes]
    total_text_h = sum(heights) + line_gap * (len(lines) - 1)

    part_font: ImageFont.FreeTypeFont | None = None
    part_bbox: tuple[int, int, int, int] | None = None
    part_h = 0
    if part_label:
        part_font, part_bbox = _fit_single_line(
            measure_draw,
            part_label.upper(),
            TEXT_MAX_WIDTH,
            start_size=76,
            title=True,
            stroke_width=5,
        )
        part_h = part_bbox[3] - part_bbox[1]

    comp_h = focal.height + IMAGE_TEXT_GAP + total_text_h
    if part_label:
        comp_h += part_h + PART_LABEL_GAP
    focal_x = (SHORT_THUMB_WIDTH - focal.width) // 2
    comp_y = (SHORT_THUMB_HEIGHT - comp_h) // 2 - COMPOSITION_TOP_BIAS
    part_y = comp_y if part_label else 0
    focal_y = comp_y + (part_h + PART_LABEL_GAP if part_label else 0)
    text_y = focal_y + focal.height + IMAGE_TEXT_GAP

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (focal_x + 16, focal_y + 20, focal_x + focal.width + 16, focal_y + focal.height + 20),
        radius=44,
        fill=(0, 0, 0, 135),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas = Image.alpha_composite(canvas, shadow)

    mask = Image.new("L", focal.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, focal.width, focal.height), radius=38, fill=255)
    canvas.paste(focal.convert("RGBA"), (focal_x, focal_y), mask)

    if on_progress:
        on_progress(0.65, "Drawing title...")

    draw = ImageDraw.Draw(canvas)

    if part_label and part_font and part_bbox:
        part_text = part_label.upper()
        part_w = part_bbox[2] - part_bbox[0]
        part_x = (SHORT_THUMB_WIDTH - part_w) // 2
        draw.text(
            (part_x - part_bbox[0] + 5, part_y - part_bbox[1] + 7),
            part_text,
            font=part_font,
            fill=(0, 0, 0, 230),
            stroke_width=5,
            stroke_fill=(0, 0, 0, 230),
        )
        draw.text(
            (part_x - part_bbox[0], part_y - part_bbox[1]),
            part_text,
            font=part_font,
            fill=(255, 244, 141, 255),
            stroke_width=5,
            stroke_fill=(23, 9, 0, 255),
        )

    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle(
        (54, text_y - 12, SHORT_THUMB_WIDTH - 54, text_y + total_text_h + 12),
        radius=38,
        fill=(0, 0, 0, 170),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    canvas = Image.alpha_composite(canvas, glow)
    draw = ImageDraw.Draw(canvas)

    y = text_y
    for line, line_h, bbox in zip(lines, heights, line_bboxes):
        line_w = bbox[2] - bbox[0]
        x = (SHORT_THUMB_WIDTH - line_w) // 2
        draw.text(
            (x - bbox[0] + 7, y - bbox[1] + 9),
            line,
            font=font,
            fill=(0, 0, 0, 220),
            stroke_width=8,
            stroke_fill=(0, 0, 0, 220),
        )
        draw.text(
            (x - bbox[0], y - bbox[1]),
            line,
            font=font,
            fill=(255, 236, 120, 255),
            stroke_width=7,
            stroke_fill=(32, 11, 0, 255),
        )
        y += line_h + line_gap

    output_path = _thumbs_dir(script_id) / f"{segment_idx}.png"
    if on_progress:
        on_progress(0.9, "Saving PNG...")
    _save_png_under_limit(canvas, output_path)

    if output_path.stat().st_size > MAX_PNG_BYTES:
        logger.warning("Short thumbnail exceeded 2 MB after optimization: %s", output_path)

    if on_progress:
        on_progress(1.0, "Thumbnail complete")
    return _web_url(script_id, segment_idx)


def generate_all_short_thumbnails(
    script_id: str,
    content: ScriptContent,
    segment_indices: list[int] | None = None,
    on_progress: ProgressCallback = None,
) -> list[str]:
    indices = list(range(len(content.segments))) if segment_indices is None else segment_indices
    total = len(indices)
    results: list[str] = []
    for batch_idx, segment_idx in enumerate(indices):
        def seg_progress(p: float, msg: str, _batch_idx: int = batch_idx, _segment_idx: int = segment_idx) -> None:
            if on_progress:
                global_p = (_batch_idx + p) / max(total, 1)
                on_progress(global_p, f"Thumbnail {_batch_idx + 1}/{total} (segment {_segment_idx + 1}): {msg}")

        results.append(generate_short_thumbnail(script_id, segment_idx, content, seg_progress))
    return results


def existing_short_thumbnail_paths(script_id: str, total: int) -> dict[int, str]:
    base = _thumbs_dir(script_id)
    paths: dict[int, str] = {}
    for idx in range(total):
        path = base / f"{idx}.png"
        if path.is_file():
            paths[idx] = _web_url(script_id, idx)
    return paths


def export_short_thumbnails(
    script_id: str,
    content: ScriptContent,
    project_title: str,
) -> tuple[str, list[str], dict[int, str]]:
    """Generate missing thumbnails, copy all to Downloads, and return paths."""
    missing = [
        idx for idx in range(len(content.segments))
        if not (_thumbs_dir(script_id) / f"{idx}.png").is_file()
    ]
    if missing:
        generate_all_short_thumbnails(script_id, content, missing)

    folder = project_downloads_folder(project_title)

    files: list[str] = []
    paths: dict[int, str] = {}
    total = len(content.segments)
    for idx, segment in enumerate(content.segments):
        src = _thumbs_dir(script_id) / f"{idx}.png"
        if not src.is_file():
            raise RuntimeError(f"Thumbnail missing for segment {idx + 1}")
        filename = short_thumbnail_filename(segment.name, idx + 1, total)
        dest = folder / filename
        shutil.copy2(src, dest)
        files.append(dest.name)
        paths[idx] = str(dest)

    return str(folder), files, paths
