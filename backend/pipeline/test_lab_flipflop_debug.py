"""Local flip-flop diagnostics for cached Test Lab cutouts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from config import DATA_DIR
from pipeline.image_gen import (
    FLIPFLOP_CUTOUT_REGISTRATION_VERSION,
    FlipflopRegistrationError,
    _flipflop_overlay_anchor_metadata,
    _read_source_metadata,
)

FlipflopDebugAction = Literal["blink", "speaking_mouth", "eye_glance", "eyebrow_raise"]

_ACTION_LABELS: dict[str, str] = {
    "blink": "Blink",
    "speaking_mouth": "Speaking mouth",
    "eye_glance": "Eye glance",
    "eyebrow_raise": "Eyebrow raise",
}


class FlipflopDebugAsset(BaseModel):
    asset_id: str
    asset_url: str
    script_id: str
    scene_id: str
    filename: str
    created_at: str
    source_metadata: dict[str, object] = Field(default_factory=dict)


class FlipflopDebugResult(BaseModel):
    asset: FlipflopDebugAsset
    action: FlipflopDebugAction
    used_external_api: bool = False
    registration_algorithm_version: str
    anchor: dict[str, object] | None = None
    debug_url: str | None = None
    status: Literal["passed", "failed"]
    error: str | None = None


def list_flipflop_debug_assets(*, limit: int = 20) -> list[FlipflopDebugAsset]:
    """Return recent cached flip-flop base cutouts that can be reprocessed locally."""

    projects_dir = DATA_DIR / "projects"
    candidates = sorted(
        projects_dir.glob("test-lab-*/flipflop_cutouts/*/base_*.png"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    return [_asset_from_path(path) for path in candidates[:limit]]


def analyze_flipflop_debug_asset(
    *,
    asset_id: str,
    action: FlipflopDebugAction = "blink",
) -> FlipflopDebugResult:
    """Run current overlay anchor detection against an existing PNG and save a visual proof image."""

    asset_path = _path_for_asset_id(asset_id)
    asset = _asset_from_path(asset_path)
    anchor: dict[str, object] | None = None
    error: str | None = None
    with Image.open(asset_path) as image:
        rgba = image.convert("RGBA")
        try:
            anchor = _flipflop_overlay_anchor_metadata(rgba, require_detected=True)
            status: Literal["passed", "failed"] = "passed"
        except FlipflopRegistrationError as exc:
            status = "failed"
            error = str(exc)
        debug_path = _debug_path(asset_path, action)
        _save_debug_overlay(rgba, debug_path, anchor=anchor, action=action, error=error)

    return FlipflopDebugResult(
        asset=asset,
        action=action,
        used_external_api=False,
        registration_algorithm_version=FLIPFLOP_CUTOUT_REGISTRATION_VERSION,
        anchor=anchor,
        debug_url=_web_url_for_project_path(debug_path),
        status=status,
        error=error,
    )


def _asset_from_path(path: Path) -> FlipflopDebugAsset:
    path = path.resolve()
    relative = path.relative_to((DATA_DIR / "projects").resolve())
    parts = relative.parts
    script_id = parts[0] if len(parts) > 0 else ""
    scene_id = parts[2] if len(parts) > 2 else ""
    created = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    return FlipflopDebugAsset(
        asset_id=relative.as_posix(),
        asset_url=_web_url_for_project_path(path),
        script_id=script_id,
        scene_id=scene_id,
        filename=path.name,
        created_at=created,
        source_metadata=_read_source_metadata(path) or {},
    )


def _path_for_asset_id(asset_id: str) -> Path:
    if not asset_id or asset_id.startswith("/") or "\\" in asset_id:
        raise ValueError("Select a cached flip-flop asset to debug.")
    projects_dir = (DATA_DIR / "projects").resolve()
    path = (projects_dir / asset_id).resolve()
    if not path.is_relative_to(projects_dir):
        raise ValueError("Flip-flop debug asset must live under the project data directory.")
    if not path.exists() or not path.is_file():
        raise ValueError("Selected flip-flop debug asset does not exist.")
    relative = path.relative_to(projects_dir)
    if (
        len(relative.parts) < 4
        or not relative.parts[0].startswith("test-lab-")
        or relative.parts[1] != "flipflop_cutouts"
        or not path.name.startswith("base_")
        or path.suffix.lower() != ".png"
    ):
        raise ValueError("Selected file is not a cached Test Lab flip-flop base cutout.")
    return path


def _debug_path(asset_path: Path, action: str) -> Path:
    return asset_path.with_name(f"debug_{asset_path.stem}_{action}.png")


def _web_url_for_project_path(path: Path) -> str:
    relative = path.resolve().relative_to((DATA_DIR / "projects").resolve())
    return f"/static/projects/{relative.as_posix()}"


def _save_debug_overlay(
    image: Image.Image,
    output_path: Path,
    *,
    anchor: dict[str, object] | None,
    action: str,
    error: str | None,
) -> None:
    width, height = image.size
    background = Image.new("RGBA", image.size, (35, 35, 35, 255))
    background.alpha_composite(image)
    draw = ImageDraw.Draw(background)

    draw.rectangle((0, 0, width - 1, height - 1), outline=(150, 110, 255, 255), width=3)
    draw.text((16, 14), f"Flip-flop debug: {_ACTION_LABELS.get(action, action)}", fill=(245, 245, 245, 255))
    draw.text((16, 34), f"Version: {FLIPFLOP_CUTOUT_REGISTRATION_VERSION}", fill=(190, 190, 190, 255))

    if anchor is None:
        draw.text((16, 58), error or "No detected anchor.", fill=(255, 120, 120, 255))
        background.save(output_path)
        return

    points = _anchor_points(anchor, width=width, height=height)
    for label, color in (
        ("eye_left", (80, 180, 255, 255)),
        ("eye_right", (80, 180, 255, 255)),
        ("mouth", (255, 110, 110, 255)),
        ("brow_left", (255, 220, 90, 255)),
        ("brow_right", (255, 220, 90, 255)),
    ):
        point = points.get(label)
        if point is None:
            continue
        x, y = point
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), outline=color, width=3)
        draw.line((x - 12, y, x + 12, y), fill=color, width=2)
        draw.line((x, y - 12, x, y + 12), fill=color, width=2)
        draw.text((x + 10, y - 8), label.replace("_", " "), fill=color)

    _draw_action_overlay(draw, points, action)
    background.save(output_path)


def _anchor_points(anchor: dict[str, object], *, width: int, height: int) -> dict[str, tuple[float, float]]:
    points: dict[str, tuple[float, float]] = {}
    for label in ("eye_left", "eye_right", "mouth", "brow_left", "brow_right"):
        raw = anchor.get(label)
        if not isinstance(raw, dict):
            continue
        x = raw.get("x")
        y = raw.get("y")
        if isinstance(x, int | float) and isinstance(y, int | float):
            points[label] = (float(x) * width, float(y) * height)
    return points


def _draw_action_overlay(
    draw: ImageDraw.ImageDraw,
    points: dict[str, tuple[float, float]],
    action: str,
) -> None:
    if action == "blink":
        for label in ("eye_left", "eye_right"):
            point = points.get(label)
            if point is None:
                continue
            x, y = point
            draw.arc((x - 42, y - 18, x + 42, y + 18), start=200, end=340, fill=(255, 60, 210, 255), width=7)
        return

    if action == "speaking_mouth":
        point = points.get("mouth")
        if point is None:
            return
        x, y = point
        draw.ellipse((x - 45, y - 24, x + 45, y + 24), fill=(244, 190, 145, 180), outline=(255, 60, 210, 255), width=5)
        draw.ellipse((x - 16, y - 22, x + 16, y + 24), fill=(75, 24, 20, 230), outline=(20, 20, 20, 255), width=3)
        return

    if action == "eye_glance":
        for label in ("eye_left", "eye_right"):
            point = points.get(label)
            if point is None:
                continue
            x, y = point
            draw.ellipse((x - 28, y - 24, x + 5, y + 24), fill=(255, 60, 210, 180), outline=(20, 20, 20, 255), width=3)
        return

    if action == "eyebrow_raise":
        for label in ("brow_left", "brow_right"):
            point = points.get(label)
            if point is None:
                continue
            x, y = point
            draw.arc((x - 48, y - 24, x + 48, y + 20), start=200, end=340, fill=(255, 60, 210, 255), width=7)
