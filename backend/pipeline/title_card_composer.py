"""Pillow-based composite title card image generation.

Creates a grid layout of circular segment images with a title overlay,
inspired by "Everything Professor" style YouTube thumbnails.
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Canvas dimensions
CANVAS_W = 1920
CANVAS_H = 1080

# Grid layout mappings: segment_count -> (rows, cols)
_GRID_LAYOUTS = {
    6: (2, 3),
    8: (2, 4),
    10: (2, 5),
    12: (3, 4),
}

# Default bold colors when Claude doesn't provide them
_DEFAULT_COLORS = [
    "#e91e63", "#2196f3", "#4caf50", "#ff9800",
    "#9c27b0", "#00bcd4", "#ff5722", "#8bc34a",
    "#3f51b5", "#cddc39", "#f44336", "#009688",
]


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load a system font, falling back to default if unavailable."""
    # Try common bold system fonts
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
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
) -> tuple[int, int, list[tuple[int, int]]]:
    """Calculate grid positions for segment circles.

    Returns: (rows, cols, list of (center_x, center_y) for each cell)
    """
    rows, cols = _GRID_LAYOUTS.get(segment_count, (2, max(3, (segment_count + 1) // 2)))

    # Title takes top ~15% of canvas, grid fills the rest
    title_height = 140
    grid_top = title_height + 20
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

    Returns:
        (output_path, zoom_targets) where zoom_targets maps
        segment_index -> (center_x, center_y, radius).
    """
    count = len(circle_image_paths)
    rows, cols, positions = calculate_grid_layout(count)

    # Calculate circle radius from grid cell size
    title_height = 140
    grid_top = title_height + 20
    grid_bottom = CANVAS_H - 40
    grid_left = 80
    grid_right = CANVAS_W - 80
    cell_w = (grid_right - grid_left) / cols
    cell_h = (grid_bottom - grid_top) / rows
    # Leave room for label text below circle
    label_space = 30
    max_radius = int(min(cell_w, cell_h - label_space) / 2 - 12)

    # Create white canvas
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    draw = ImageDraw.Draw(canvas)

    # --- Render title text ---
    title_font = _load_font(64, bold=True)
    title_text = card_title.upper()
    highlight = highlight_word.upper() if highlight_word else ""

    if highlight and highlight in title_text:
        # Split title around highlight word and render segments
        parts = title_text.split(highlight, 1)
        before, after = parts[0], parts[1] if len(parts) > 1 else ""

        # Measure total width to center
        before_bbox = title_font.getbbox(before) if before else (0, 0, 0, 0)
        hl_bbox = title_font.getbbox(highlight)
        after_bbox = title_font.getbbox(after) if after else (0, 0, 0, 0)
        total_w = (before_bbox[2] - before_bbox[0]) + (hl_bbox[2] - hl_bbox[0]) + (after_bbox[2] - after_bbox[0])
        x = (CANVAS_W - total_w) // 2
        y = 40

        if before:
            draw.text((x, y), before, fill="#222222", font=title_font)
            x += before_bbox[2] - before_bbox[0]
        draw.text((x, y), highlight, fill=accent_color, font=title_font)
        x += hl_bbox[2] - hl_bbox[0]
        if after:
            draw.text((x, y), after, fill="#222222", font=title_font)
    else:
        # No highlight — center the full title
        bbox = title_font.getbbox(title_text)
        tw = bbox[2] - bbox[0]
        draw.text(((CANVAS_W - tw) // 2, 40), title_text, fill="#222222", font=title_font)

    # --- Place circles ---
    label_font = _load_font(20, bold=True)
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
        except Exception:
            logger.warning("Failed to load circle image %d: %s", i, circle_image_paths[i])
            # Draw a placeholder circle with the color
            draw.ellipse(
                (cx - max_radius, cy - max_radius, cx + max_radius, cy + max_radius),
                fill=color,
            )

        # Draw segment label below circle
        label = segment_names[i].upper() if i < len(segment_names) else f"SEGMENT {i + 1}"
        # Truncate long labels
        if len(label) > 18:
            label = label[:16] + "..."
        lbox = label_font.getbbox(label)
        lw = lbox[2] - lbox[0]
        draw.text(
            (cx - lw // 2, cy + max_radius + 10),
            label,
            fill="#333333",
            font=label_font,
        )

        zoom_targets[i] = (cx, cy, max_radius)

    canvas.save(output_path, "PNG")
    logger.info("Composite title card saved: %s (%d segments, %dx%d grid)", output_path, count, cols, rows)

    return output_path, zoom_targets
