"""Pillow-based composite title card image generation.

Creates a grid layout of circular segment images with bold YouTube-style
typography, gradient fills, glow effects, and drop shadows — designed for
high-CTR thumbnails.
"""

import logging
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from config import DATA_DIR, DEFAULT_ACCENT_COLOR, DEFAULT_SEGMENT_COLORS, VIDEO_HEIGHT, VIDEO_WIDTH

logger = logging.getLogger(__name__)

# Canvas dimensions
CANVAS_W = VIDEO_WIDTH
CANVAS_H = VIDEO_HEIGHT

# Grid layout mappings: segment_count -> (rows, cols)
_GRID_LAYOUTS = {
    8: (2, 4),
    10: (2, 5),
}

# Default bold colors when Claude doesn't provide them
_DEFAULT_COLORS = DEFAULT_SEGMENT_COLORS

# Path to bundled fonts
_BUNDLED_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "PermanentMarker-Regular.ttf"
_BUNDLED_TITLE_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Anton-Regular.ttf"

# --- Style constants ---
_BG_COLOR = (255, 250, 240)  # warm cream (fallback only)
_BG_GRAD_TOP = (26, 5, 51)  # deep purple #1a0533
_BG_GRAD_BOTTOM = (10, 46, 61)  # dark teal #0a2e3d
_VIGNETTE_STRENGTH = 100  # alpha of dark edge overlay
_CENTER_GLOW_RADIUS = 60  # blur radius for center glow
_CIRCLE_BORDER_WIDTH = 8
_CIRCLE_SHADOW_OFFSET = (6, 8)
_CIRCLE_SHADOW_BLUR = 15
_CIRCLE_SHADOW_ALPHA = 90
_BADGE_OVERLAP_PX = 20  # how far badge overlaps bottom of circle
_BADGE_PAD_X = 28
_BADGE_PAD_Y = 12
_BADGE_RADIUS = 20  # corner radius
_BADGE_GLOW_BLUR = 12
_TITLE_SHADOW_OFFSET = (5, 7)
_TITLE_SHADOW_BLUR = 12
_TITLE_SHADOW_ALPHA = 140
_TITLE_EXTRUSION_DEPTH = 5
_TITLE_EXTRUSION_COLOR = (15, 15, 60)
_TITLE_STROKE_WIDTH = 7
_TITLE_STROKE_COLOR = (0, 30, 120)
_TITLE_GRAD_TOP = (255, 230, 0)  # yellow
_TITLE_GRAD_BOTTOM = (255, 140, 0)  # orange
_BURST_COLOR = (255, 245, 180)  # warm yellow glow
_BURST_ALPHA = 100
_COLOR_SATURATION = 1.15
_COLOR_CONTRAST = 1.08
_ELI_SCALE = 0.42                          # fraction of canvas height
_ELI_ROTATION_DEG = 5                      # slight counter-clockwise tilt
_ELI_RIGHT_OVERFLOW = 0.35                 # fraction of eli width allowed to overflow right edge
_ELI_STROKE_WIDTH = 9                      # MaxFilter kernel — crisp outline
_ELI_GLOW_EXPAND = 21                      # MaxFilter kernel for glow spread
_ELI_GLOW_BLUR = 22                        # GaussianBlur radius
_ELI_GLOW_ALPHA = 230                      # glow opacity (punchy)
_ELI_SHADOW_OFFSET = (8, 10)              # drop shadow (dx, dy)
_ELI_SHADOW_BLUR = 14                      # drop shadow blur radius
_ELI_SHADOW_ALPHA = 140                    # drop shadow opacity
# Gradient outline colors (top → bottom): hot magenta → golden orange → electric cyan
_ELI_GRAD_TOP = (255, 50, 180)            # hot magenta/pink
_ELI_GRAD_BOTTOM = (0, 220, 255)          # electric cyan


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


def _load_title_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a bold condensed font for title text (Anton → Impact → fallback)."""
    candidates = [
        str(_BUNDLED_TITLE_FONT),
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
        "/Library/Fonts/Impact.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return _load_font(size, bold=True)


def _darken_hex(hex_color: str, factor: float = 0.5) -> str:
    """Darken a hex color by the given factor (0=black, 1=unchanged)."""
    hex_color = hex_color.lstrip("#")
    r = int(int(hex_color[0:2], 16) * factor)
    g = int(int(hex_color[2:4], 16) * factor)
    b = int(int(hex_color[4:6], 16) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def _draw_warm_background(w: int, h: int) -> Image.Image:
    """Create saturated gradient canvas with center glow and edge vignette."""
    # Vertical gradient from deep purple to dark teal
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    for row in range(h):
        t = row / max(h - 1, 1)
        r = int(_BG_GRAD_TOP[0] + (_BG_GRAD_BOTTOM[0] - _BG_GRAD_TOP[0]) * t)
        g = int(_BG_GRAD_TOP[1] + (_BG_GRAD_BOTTOM[1] - _BG_GRAD_TOP[1]) * t)
        b = int(_BG_GRAD_TOP[2] + (_BG_GRAD_BOTTOM[2] - _BG_GRAD_TOP[2]) * t)
        ImageDraw.Draw(canvas).line([(0, row), (w, row)], fill=(r, g, b, 255))

    # Center glow: white ellipse, blurred, composited at reduced opacity
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    gw, gh = int(w * 0.7), int(h * 0.7)
    gx, gy = (w - gw) // 2, (h - gh) // 2
    glow_draw.ellipse((gx, gy, gx + gw, gy + gh), fill=(255, 255, 255, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(_CENTER_GLOW_RADIUS))
    canvas = Image.alpha_composite(canvas, glow)

    # Edge vignette: dark overlay masked by inverted ellipse
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vmask = Image.new("L", (w, h), _VIGNETTE_STRENGTH)
    vmask_draw = ImageDraw.Draw(vmask)
    margin = 80
    vmask_draw.ellipse((margin, margin, w - margin, h - margin), fill=0)
    vmask = vmask.filter(ImageFilter.GaussianBlur(100))
    vignette = Image.new("RGBA", (w, h), (20, 15, 10, 0))
    vignette.putalpha(vmask)
    canvas = Image.alpha_composite(canvas, vignette)

    return canvas


def _draw_title_burst(canvas: Image.Image, title_y: int, title_h: int) -> Image.Image:
    """Draw radial yellow glow behind title area."""
    w, h = canvas.size
    burst = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    burst_draw = ImageDraw.Draw(burst)
    bw, bh = int(w * 0.8), title_h + 120
    bx = (w - bw) // 2
    by = title_y - 40
    burst_draw.ellipse((bx, by, bx + bw, by + bh), fill=_BURST_COLOR + (_BURST_ALPHA,))
    burst = burst.filter(ImageFilter.GaussianBlur(50))
    return Image.alpha_composite(canvas, burst)


def _draw_circle_shadow(canvas: Image.Image, cx: int, cy: int, radius: int) -> Image.Image:
    """Draw a blurred drop shadow for a circle."""
    w, h = canvas.size
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    ox, oy = _CIRCLE_SHADOW_OFFSET
    sd.ellipse(
        (cx - radius + ox, cy - radius + oy, cx + radius + ox, cy + radius + oy),
        fill=(0, 0, 0, _CIRCLE_SHADOW_ALPHA),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(_CIRCLE_SHADOW_BLUR))
    return Image.alpha_composite(canvas, shadow)


def _draw_label_badge(
    canvas: Image.Image,
    cx: int,
    cy: int,
    radius: int,
    label: str,
    color: str,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    """Draw a dark rounded-rect badge overlapping the bottom of a circle."""
    w, h = canvas.size
    bbox = font.getbbox(label)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    bw = tw + _BADGE_PAD_X * 2
    bh = th + _BADGE_PAD_Y * 2
    bx = cx - bw // 2
    by = cy + radius - _BADGE_OVERLAP_PX

    # Subtle glow behind badge
    glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.rounded_rectangle((bx - 4, by - 4, bx + bw + 4, by + bh + 4), radius=_BADGE_RADIUS + 4, fill=(0, 0, 0, 60))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(_BADGE_GLOW_BLUR))
    canvas = Image.alpha_composite(canvas, glow_layer)

    # Badge background
    badge_fill = _darken_hex(color, 0.25)
    badge_rgb = _hex_to_rgb(badge_fill)
    badge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.rounded_rectangle((bx, by, bx + bw, by + bh), radius=_BADGE_RADIUS, fill=badge_rgb + (230,))
    canvas = Image.alpha_composite(canvas, badge)

    # White text with dark stroke
    text_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    tx = cx - tw // 2
    ty = by + _BADGE_PAD_Y - bbox[1]
    td.text((tx, ty), label, fill=(255, 255, 255, 255), font=font, stroke_width=3, stroke_fill=(0, 0, 0, 255))
    canvas = Image.alpha_composite(canvas, text_layer)

    return canvas


def _draw_3d_title_text(
    canvas: Image.Image,
    title_text: str,
    highlight_word: str,
    accent_color: str,
    y: int = 20,
) -> Image.Image:
    """Render title with 3D extrusion, gradient fill, stroke, and drop shadow."""
    w, h = canvas.size
    font = _load_title_font(140)

    # Split title into segments: before, highlight, after
    highlight = highlight_word.upper() if highlight_word else ""
    segments: list[tuple[str, bool]] = []  # (text, is_highlight)

    if highlight and highlight in title_text:
        parts = title_text.split(highlight, 1)
        if parts[0]:
            segments.append((parts[0], False))
        segments.append((highlight, True))
        if len(parts) > 1 and parts[1]:
            segments.append((parts[1], False))
    else:
        segments.append((title_text, False))

    # Measure total width
    total_w = 0
    seg_widths: list[int] = []
    for text, _ in segments:
        bbox = font.getbbox(text)
        sw = bbox[2] - bbox[0]
        seg_widths.append(sw)
        total_w += sw

    x_start = (w - total_w) // 2

    # Helper to render one segment with full 3D treatment
    def _render_segment(text: str, x: int, is_highlight: bool) -> None:
        nonlocal canvas

        grad_top = _hex_to_rgb(accent_color) if is_highlight else _TITLE_GRAD_TOP
        grad_bottom = (
            tuple(max(0, c - 60) for c in _hex_to_rgb(accent_color))
            if is_highlight
            else _TITLE_GRAD_BOTTOM
        )

        # 1) Drop shadow
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sx, sy = _TITLE_SHADOW_OFFSET
        sd.text((x + sx, y + sy), text, fill=(0, 0, 0, _TITLE_SHADOW_ALPHA), font=font)
        shadow = shadow.filter(ImageFilter.GaussianBlur(_TITLE_SHADOW_BLUR))
        canvas = Image.alpha_composite(canvas, shadow)

        # 2) 3D extrusion (stacked layers offset downward)
        for d in range(_TITLE_EXTRUSION_DEPTH, 0, -1):
            ext = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ed = ImageDraw.Draw(ext)
            ed.text((x, y + d), text, fill=_TITLE_EXTRUSION_COLOR + (255,), font=font)
            canvas = Image.alpha_composite(canvas, ext)

        # 3) Blue stroke
        stroke_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sld = ImageDraw.Draw(stroke_layer)
        sld.text(
            (x, y), text, fill=(0, 0, 0, 0), font=font,
            stroke_width=_TITLE_STROKE_WIDTH, stroke_fill=_TITLE_STROKE_COLOR + (255,),
        )
        canvas = Image.alpha_composite(canvas, stroke_layer)

        # 4) Gradient fill via text mask
        # Create text mask
        text_mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(text_mask)
        md.text((x, y), text, fill=255, font=font)

        # Create vertical gradient
        gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        # Find text bounds for gradient range
        bbox = font.getbbox(text)
        text_top = y + bbox[1]
        text_bottom = y + bbox[3]
        text_height = text_bottom - text_top
        if text_height <= 0:
            text_height = 1

        for row in range(h):
            if row < text_top or row > text_bottom:
                continue
            t = (row - text_top) / text_height
            r = int(grad_top[0] + (grad_bottom[0] - grad_top[0]) * t)
            g = int(grad_top[1] + (grad_bottom[1] - grad_top[1]) * t)
            b = int(grad_top[2] + (grad_bottom[2] - grad_top[2]) * t)
            ImageDraw.Draw(gradient).line([(0, row), (w, row)], fill=(r, g, b, 255))

        # Apply text mask to gradient
        gradient.putalpha(text_mask)
        canvas = Image.alpha_composite(canvas, gradient)

    # Render each segment
    x = x_start
    for i, (text, is_hl) in enumerate(segments):
        _render_segment(text, x, is_hl)
        x += seg_widths[i]

    return canvas


def _boost_colors(img: Image.Image) -> Image.Image:
    """Subtle saturation and contrast boost."""
    rgb = img.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(_COLOR_SATURATION)
    rgb = ImageEnhance.Contrast(rgb).enhance(_COLOR_CONTRAST)
    return rgb


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
        grid_top = 160  # allow title to overlap top circles slightly
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


def _overlay_eli_frame(canvas: Image.Image) -> Image.Image:
    """Composite a random Eli character frame in the top-right corner."""
    try:
        from pipeline.character_frames import get_manifest, FRAMES_DIR

        manifest = get_manifest()
        if not manifest or not manifest.get("frames"):
            return canvas

        frames = manifest["frames"]
        frame = random.choice(frames)

        # Pick a random variant (or base) if variants exist
        variant_count = frame.get("variant_count", 1)
        if variant_count > 1:
            variant_idx = random.randint(0, variant_count)  # 0 = base, 1..N = variants
        else:
            variant_idx = 0

        if variant_idx == 0:
            file_name = frame.get("file_closed", "")
        else:
            # Variant file: e.g. "neutral_standing_closed_v2.png"
            base_name = frame.get("file_closed", "")
            stem = Path(base_name).stem  # e.g. "neutral_standing_closed"
            file_name = f"{stem}_v{variant_idx + 1}.png"

        frame_path = FRAMES_DIR / file_name
        if not frame_path.exists():
            # Fallback to base frame if variant missing
            frame_path = FRAMES_DIR / frame.get("file_closed", "")
            if not frame_path.exists():
                return canvas

        eli_img = Image.open(frame_path).convert("RGBA")

        w, h = canvas.size

        # Scale to 42% of canvas height
        target_h = int(h * _ELI_SCALE)
        scale = target_h / eli_img.height
        target_w = int(eli_img.width * scale)
        eli_img = eli_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Rotate if configured
        if _ELI_ROTATION_DEG:
            eli_img = eli_img.rotate(_ELI_ROTATION_DEG, expand=True, resample=Image.Resampling.BICUBIC)

        # Position: push right so body overflows canvas edge, face stays visible
        overflow_px = int(eli_img.width * _ELI_RIGHT_OVERFLOW)
        paste_x = w - eli_img.width + overflow_px
        paste_y = -int(eli_img.height * 0.08)  # nudge up so top clips off edge

        alpha = eli_img.getchannel("A")

        # --- Drop shadow ---
        shadow_alpha = alpha.filter(ImageFilter.MaxFilter(size=3))
        shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(radius=_ELI_SHADOW_BLUR))
        shadow_alpha = shadow_alpha.point(lambda p: min(p, _ELI_SHADOW_ALPHA))
        shadow_rgba = Image.new("RGBA", eli_img.size, (0, 0, 0, 0))
        shadow_rgba.putalpha(shadow_alpha)
        sx, sy = _ELI_SHADOW_OFFSET

        # --- Outer glow with vertical gradient (magenta → cyan) ---
        glow_expanded = alpha.filter(ImageFilter.MaxFilter(size=_ELI_GLOW_EXPAND))
        glow_mask = glow_expanded.point(lambda p: _ELI_GLOW_ALPHA if p > 0 else 0)
        # Build vertical gradient fill for the glow
        glow_grad = Image.new("RGBA", eli_img.size, (0, 0, 0, 0))
        for row in range(eli_img.height):
            t = row / max(eli_img.height - 1, 1)
            r = int(_ELI_GRAD_TOP[0] + (_ELI_GRAD_BOTTOM[0] - _ELI_GRAD_TOP[0]) * t)
            g = int(_ELI_GRAD_TOP[1] + (_ELI_GRAD_BOTTOM[1] - _ELI_GRAD_TOP[1]) * t)
            b = int(_ELI_GRAD_TOP[2] + (_ELI_GRAD_BOTTOM[2] - _ELI_GRAD_TOP[2]) * t)
            ImageDraw.Draw(glow_grad).line([(0, row), (eli_img.width, row)], fill=(r, g, b, 255))
        glow_grad.putalpha(glow_mask)
        glow_rgba = glow_grad.filter(ImageFilter.GaussianBlur(radius=_ELI_GLOW_BLUR))

        # --- Solid stroke with same gradient (crisp, no blur) ---
        stroke_expanded = alpha.filter(ImageFilter.MaxFilter(size=_ELI_STROKE_WIDTH))
        stroke_mask = stroke_expanded.point(lambda p: 255 if p > 0 else 0)
        stroke_grad = Image.new("RGBA", eli_img.size, (0, 0, 0, 0))
        for row in range(eli_img.height):
            t = row / max(eli_img.height - 1, 1)
            r = int(_ELI_GRAD_TOP[0] + (_ELI_GRAD_BOTTOM[0] - _ELI_GRAD_TOP[0]) * t)
            g = int(_ELI_GRAD_TOP[1] + (_ELI_GRAD_BOTTOM[1] - _ELI_GRAD_TOP[1]) * t)
            b = int(_ELI_GRAD_TOP[2] + (_ELI_GRAD_BOTTOM[2] - _ELI_GRAD_TOP[2]) * t)
            ImageDraw.Draw(stroke_grad).line([(0, row), (eli_img.width, row)], fill=(r, g, b, 255))
        stroke_grad.putalpha(stroke_mask)

        # --- Composite layers back-to-front ---
        eli_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        eli_layer.paste(shadow_rgba, (paste_x + sx, paste_y + sy), shadow_rgba)
        eli_layer.paste(glow_rgba, (paste_x, paste_y), glow_rgba)
        eli_layer.paste(stroke_grad, (paste_x, paste_y), stroke_grad)
        eli_layer.paste(eli_img, (paste_x, paste_y), eli_img)
        return Image.alpha_composite(canvas, eli_layer)

    except Exception as exc:
        logger.debug("Skipping Eli overlay on title card: %s", exc)
        return canvas


def compose_title_card(
    circle_image_paths: list[str],
    segment_names: list[str],
    circle_colors: list[str],
    card_title: str,
    highlight_word: str,
    accent_color: str = DEFAULT_ACCENT_COLOR,
    output_path: str = "",
    include_title: bool = True,
    include_eli: bool = True,
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
        grid_top = 160  # match calculate_grid_layout
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

    # --- Layer 0: Warm background ---
    canvas = _draw_warm_background(CANVAS_W, CANVAS_H)

    # --- Layer 1: Title burst ---
    if include_title:
        canvas = _draw_title_burst(canvas, 20, 120)

    # --- Layer 2: Circle shadows (all drawn before circles) ---
    for i, (cx, cy) in enumerate(positions):
        if i >= count:
            break
        bg_radius = max_radius + _CIRCLE_BORDER_WIDTH // 2
        canvas = _draw_circle_shadow(canvas, cx, cy, bg_radius)

    # --- Layers 3-6: Circles, images, outlines, labels ---
    zoom_targets: dict[int, tuple[int, int, int]] = {}

    for i, (cx, cy) in enumerate(positions):
        if i >= count:
            break

        color = circle_colors[i] if i < len(circle_colors) else _DEFAULT_COLORS[i % len(_DEFAULT_COLORS)]
        border_color = _darken_hex(color, 0.4)
        border_rgb = _hex_to_rgb(border_color)

        # Layer 3: Circle background (thicker border in darkened color)
        bg_radius = max_radius + _CIRCLE_BORDER_WIDTH // 2
        bg_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        bgd = ImageDraw.Draw(bg_layer)
        bgd.ellipse(
            (cx - bg_radius, cy - bg_radius, cx + bg_radius, cy + bg_radius),
            fill=_hex_to_rgb(color) + (255,),
        )
        canvas = Image.alpha_composite(canvas, bg_layer)

        # Layer 4: Circle image
        try:
            img = Image.open(circle_image_paths[i])
            cropped = circle_crop(img, max_radius * 2)
            img_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
            img_layer.paste(cropped, (cx - max_radius, cy - max_radius), cropped)
            canvas = Image.alpha_composite(canvas, img_layer)
        except Exception as exc:
            logger.warning("Failed to load circle image %d (%s), using solid color fallback: %s", i, circle_image_paths[i], exc)
            fill_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
            fd = ImageDraw.Draw(fill_layer)
            fd.ellipse(
                (cx - max_radius, cy - max_radius, cx + max_radius, cy + max_radius),
                fill=_hex_to_rgb(color) + (255,),
            )
            canvas = Image.alpha_composite(canvas, fill_layer)

        # Layer 5: Circle outline (dark border stroke)
        outline_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        od = ImageDraw.Draw(outline_layer)
        od.ellipse(
            (cx - bg_radius, cy - bg_radius, cx + bg_radius, cy + bg_radius),
            outline=border_rgb + (255,),
            width=_CIRCLE_BORDER_WIDTH,
        )
        canvas = Image.alpha_composite(canvas, outline_layer)

        # Layer 6: Label badge — auto-scale to fit cell width
        label = segment_names[i].upper() if i < len(segment_names) else f"SEGMENT {i + 1}"
        max_label_w = int(cell_w - 20)
        label_size = 64
        label_font = _load_font(label_size, bold=True)
        lbox = label_font.getbbox(label)
        lw = lbox[2] - lbox[0]
        # Shrink font until label fits or we hit minimum size
        while lw > max_label_w and label_size > 36:
            label_size -= 2
            label_font = _load_font(label_size, bold=True)
            lbox = label_font.getbbox(label)
            lw = lbox[2] - lbox[0]

        canvas = _draw_label_badge(canvas, cx, cy, max_radius, label, color, label_font)

        zoom_targets[i] = (cx, cy, max_radius)

    # --- Layer 7: Title text ---
    if include_title:
        title_text = card_title.upper()
        canvas = _draw_3d_title_text(canvas, title_text, highlight_word, accent_color, y=20)

    # --- Layer 8: Eli character overlay (top-right corner) ---
    if include_eli:
        canvas = _overlay_eli_frame(canvas)

    # --- Layer 9: Color boost ---
    final = _boost_colors(canvas)

    final.save(output_path, "PNG")
    logger.info("Composite title card saved: %s (%d segments, %dx%d grid, title=%s)", output_path, count, cols, rows, include_title)

    return output_path, zoom_targets
