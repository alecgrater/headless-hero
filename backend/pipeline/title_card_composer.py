"""Pillow-based composite title card image generation.

Creates a grid layout of circular segment images with a title overlay,
inspired by "Everything Professor" style YouTube thumbnails.
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import VIDEO_HEIGHT, VIDEO_WIDTH

logger = logging.getLogger(__name__)

# Canvas dimensions
CANVAS_W = VIDEO_WIDTH
CANVAS_H = VIDEO_HEIGHT

# Grid layout mappings: segment_count -> (rows, cols)
_GRID_LAYOUTS = {
    6: (2, 3),
    8: (2, 4),
}

# Default bold colors when Claude doesn't provide them
_DEFAULT_COLORS = [
    "#e91e63", "#2196f3", "#4caf50", "#ff9800",
    "#9c27b0", "#00bcd4", "#ff5722", "#8bc34a",
    "#3f51b5", "#cddc39", "#f44336", "#009688",
]

# Path to bundled marker font
_BUNDLED_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "PermanentMarker-Regular.ttf"


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load a hand-drawn marker font, falling back to system fonts."""
    # Prefer bundled Permanent Marker, then system MarkerFelt, then fallbacks
    candidates = [
        str(_BUNDLED_FONT),
        "/System/Library/Fonts/MarkerFelt.ttc",
        "/System/Library/Fonts/Chalkduster.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default(size=size)


def circle_crop(img: Image.Image, size: int) -> Image.Image:
    """Resize and apply a circular alpha mask to an image."""
    img = img.resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    img.putalpha(mask)
    return img


def calculate_grid_layout(
    segment_count: int,
    include_title: bool = True,
) -> tuple[int, int, list[tuple[int, int]]]:
    """Calculate grid positions for segment circles.

    Args:
        segment_count: Number of segments to lay out.
        include_title: If True, reserve space for title text at top.
            If False, use the full canvas for larger circles.

    Returns: (rows, cols, list of (center_x, center_y) for each cell)
    """
    rows, cols = _GRID_LAYOUTS.get(segment_count, (2, max(3, (segment_count + 1) // 2)))

    if include_title:
        grid_top = 130  # allow title to overlap top circles slightly
    else:
        grid_top = 30  # near top of canvas
    grid_bottom = CANVAS_H - 40
    grid_left = 80
    grid_right = CANVAS_W - 80

    grid_w = grid_right - grid_left
    grid_h = grid_bottom - grid_top

    cell_w = grid_w / cols
    cell_h = grid_h / rows

    positions: list[tuple[int, int]] = []
    for r in range(rows):
        for c in range(cols):
            cx = int(grid_left + cell_w * c + cell_w / 2)
            cy = int(grid_top + cell_h * r + cell_h / 2)
            positions.append((cx, cy))

    return rows, cols, positions


def compose_title_card(
    circle_image_paths: list[str],
    segment_names: list[str],
    circle_colors: list[str],
    card_title: str,
    highlight_word: str,
    accent_color: str = "#e91e63",
    output_path: str = "",
    include_title: bool = True,
) -> tuple[str, dict[int, tuple[int, int, int]]]:
    """Compose a grid title card image with circular segment thumbnails.

    Args:
        circle_image_paths: Paths to individual segment circle images.
        segment_names: Display names for each segment.
        circle_colors: Hex background colors for each circle.
        card_title: The title text (e.g. "TYPES OF DREAMS").
        highlight_word: Word to render in accent color.
        accent_color: Hex color for the highlighted word.
        output_path: Where to save the composite PNG.
        include_title: If True, render title text at top. If False, skip title
            and use the extra space for larger circles.

    Returns:
        (output_path, zoom_targets) where zoom_targets maps
        segment_index -> (center_x, center_y, radius).
    """
    count = len(circle_image_paths)
    rows, cols, positions = calculate_grid_layout(count, include_title=include_title)

    # Calculate circle radius from grid cell size
    if include_title:
        grid_top = 130  # match calculate_grid_layout
    else:
        grid_top = 30
    grid_bottom = CANVAS_H - 40
    grid_left = 80
    grid_right = CANVAS_W - 80
    cell_w = (grid_right - grid_left) / cols
    cell_h = (grid_bottom - grid_top) / rows
    # Leave room for label text below circle
    label_space = 50
    max_radius = int(min(cell_w, cell_h - label_space) / 2 - 12)

    # Create white canvas
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    draw = ImageDraw.Draw(canvas)

    # --- Place circles ---
    zoom_targets: dict[int, tuple[int, int, int]] = {}

    for i, (cx, cy) in enumerate(positions):
        if i >= count:
            break

        color = circle_colors[i] if i < len(circle_colors) else _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)]

        # Draw colored circle background (slightly larger than image for border effect)
        bg_radius = max_radius + 6
        draw.ellipse(
            (cx - bg_radius, cy - bg_radius, cx + bg_radius, cy + bg_radius),
            fill=color,
        )

        # Load and circle-crop the segment image
        try:
            img = Image.open(circle_image_paths[i])
            cropped = circle_crop(img, max_radius * 2)
            canvas.paste(cropped, (cx - max_radius, cy - max_radius), cropped)
        except Exception as exc:
            logger.warning("Failed to load circle image %d (%s), using solid color fallback: %s", i, circle_image_paths[i], exc)
            # Draw a placeholder circle with the color
            draw.ellipse(
                (cx - max_radius, cy - max_radius, cx + max_radius, cy + max_radius),
                fill=color,
            )

        # Draw dark circle outline
        outline_width = 4
        draw.ellipse(
            (cx - bg_radius, cy - bg_radius, cx + bg_radius, cy + bg_radius),
            outline="#1a1a1a",
            width=outline_width,
        )

        # Draw segment label below circle — auto-scale to fit cell width
        label = segment_names[i].upper() if i < len(segment_names) else f"SEGMENT {i + 1}"
        max_label_w = int(cell_w - 20)
        label_size = 40
        label_font = _load_font(label_size, bold=True)
        lbox = label_font.getbbox(label)
        lw = lbox[2] - lbox[0]
        # Shrink font until label fits or we hit minimum size
        while lw > max_label_w and label_size > 22:
            label_size -= 2
            label_font = _load_font(label_size, bold=True)
            lbox = label_font.getbbox(label)
            lw = lbox[2] - lbox[0]

        draw.text(
            (cx - lw // 2, cy + max_radius + 10),
            label,
            fill="#333333",
            font=label_font,
        )

        zoom_targets[i] = (cx, cy, max_radius)

    # --- Render title text AFTER circles so it overlaps them ---
    if include_title:
        title_font = _load_font(110, bold=True)
        title_text = card_title.upper()
        highlight = highlight_word.upper() if highlight_word else ""
        shadow_offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2), (-3, 0), (3, 0), (0, -3), (0, 3)]

        def _draw_title_segment(x: int, y: int, text: str, fill: str) -> None:
            """Draw text with a dark outline for readability over circles."""
            for ox, oy in shadow_offsets:
                draw.text((x + ox, y + oy), text, fill="#000000", font=title_font)
            draw.text((x, y), text, fill=fill, font=title_font)

        if highlight and highlight in title_text:
            parts = title_text.split(highlight, 1)
            before, after = parts[0], parts[1] if len(parts) > 1 else ""

            before_bbox = title_font.getbbox(before) if before else (0, 0, 0, 0)
            hl_bbox = title_font.getbbox(highlight)
            after_bbox = title_font.getbbox(after) if after else (0, 0, 0, 0)
            total_w = (before_bbox[2] - before_bbox[0]) + (hl_bbox[2] - hl_bbox[0]) + (after_bbox[2] - after_bbox[0])
            x = (CANVAS_W - total_w) // 2
            y = 20

            if before:
                _draw_title_segment(x, y, before, "#ffffff")
                x += before_bbox[2] - before_bbox[0]
            _draw_title_segment(x, y, highlight, accent_color)
            x += hl_bbox[2] - hl_bbox[0]
            if after:
                _draw_title_segment(x, y, after, "#ffffff")
        else:
            bbox = title_font.getbbox(title_text)
            tw = bbox[2] - bbox[0]
            _draw_title_segment((CANVAS_W - tw) // 2, 20, title_text, "#ffffff")

    canvas.save(output_path, "PNG")
    logger.info("Composite title card saved: %s (%d segments, %dx%d grid, title=%s)", output_path, count, cols, rows, include_title)

    return output_path, zoom_targets
