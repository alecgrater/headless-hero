"""FFmpeg command-line argument builder for thumbnail composite utilities."""

import logging
import subprocess

logger = logging.getLogger(__name__)


# Detect drawtext filter availability once at import time
def _has_drawtext() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=5,
        )
        return "drawtext" in result.stdout
    except Exception:
        return False

_DRAWTEXT_AVAILABLE = _has_drawtext()
if not _DRAWTEXT_AVAILABLE:
    logger.warning("FFmpeg drawtext filter not available — text overlays will be skipped. "
                    "Install FFmpeg with libfreetype to enable text overlays.")


def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\u2019")
    text = text.replace(":", "\\:")
    text = text.replace(";", "\\;")
    return text


def build_thumbnail_composite_cmd(
    image_path: str,
    output_path: str,
    title_text: str,
    bar_color: str = "0x9333EA",
    width: int = 1280,
    height: int = 720,
    font_family: str = "",
) -> list[str]:
    """Build FFmpeg command to composite title text + color bar onto a thumbnail image."""
    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"drawbox=x=0:y=ih-80:w=iw:h=80:color=#{bar_color.replace('0x', '')}@0.85:t=fill"
    )

    if _DRAWTEXT_AVAILABLE:
        escaped = _escape_drawtext(title_text)
        font_part = f":font='{font_family}'" if font_family else ""
        filter_complex += (
            f",drawtext=text='{escaped}':fontsize=52:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"borderw=3:bordercolor=black:shadowx=3:shadowy=3:shadowcolor='black@0.7'"
            f"{font_part}"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", image_path,
        "-vf", filter_complex,
        "-frames:v", "1",
        output_path,
    ]

    return cmd
