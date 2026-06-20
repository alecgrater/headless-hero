"""Local flip-flop diagnostics for cached Test Lab cutouts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from config import DATA_DIR
from models.script import Scene, ScriptContent, Segment, VisualCanvas, VisualLayer
from pipeline.image_gen import (
    FLIPFLOP_CUTOUT_REGISTRATION_VERSION,
    FlipflopRegistrationError,
    _flipflop_base_cache_valid,
    _flipflop_overlay_anchor_metadata,
    _read_source_metadata,
    _write_source_metadata,
    generate_flipflop_base_cutout,
)
from pipeline.remotion_render import render_full_video

FlipflopDebugAction = Literal["blink", "speaking_mouth", "eye_glance", "eyebrow_raise"]
FLIPFLOP_FIXTURE_SCRIPT_ID = "test-lab-flipflop-fixtures"
FLIPFLOP_FIXTURE_SCENE_ID = "fixture-scene"
FLIPFLOP_FIXTURE_LAYER_ID = "flipflop_fixture_base"
DEFAULT_FIXTURE_PROMPT = (
    "Young fast-food employee character framed chest-up, wearing a plain red polo and red visor cap, "
    "tired but composed expression, looking slightly off-camera. Clean flat 2D illustration, no props, "
    "no counter, no background elements, no logos, no text."
)
DEFAULT_FIXTURE_NARRATION = (
    "You're six hours in. The fryer is screaming, your visor is sliding, and the guy in line three "
    "is asking if the flame-grilled burger comes with cheese."
)

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


class FlipflopFixtureResult(BaseModel):
    asset: FlipflopDebugAsset
    used_external_api: bool
    status: Literal["ready"] = "ready"


class FlipflopFixtureRenderResult(BaseModel):
    asset: FlipflopDebugAsset
    action: FlipflopDebugAction
    render_url: str
    used_external_api: bool = False


def list_flipflop_debug_assets(*, limit: int = 20) -> list[FlipflopDebugAsset]:
    """Return recent saved Test Lab cutouts that can be reprocessed locally."""

    projects_dir = DATA_DIR / "projects"
    patterns = (
        "test-lab-*/flipflop_cutouts/*/base_*.png",
        "test-lab-*/character/cutout.png",
        "test-lab-*/popup_crops/*/anchor_cutout.png",
    )
    candidate_paths: dict[Path, None] = {}
    for pattern in patterns:
        for path in projects_dir.glob(pattern):
            candidate_paths[path] = None
    candidates = sorted(
        (path for path in candidate_paths if _is_reusable_debug_asset(path)),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    return [_asset_from_path(path) for path in candidates[:limit]]


def create_flipflop_fixture_asset(
    *,
    visual_prompt: str = DEFAULT_FIXTURE_PROMPT,
    narration: str = DEFAULT_FIXTURE_NARRATION,
    force: bool = False,
) -> FlipflopFixtureResult:
    """Create or reuse the stable flip-flop fixture base cutout."""

    fixture_path = _fixture_asset_path()
    cache_valid = fixture_path.exists() and _flipflop_base_cache_valid(fixture_path)
    used_external_api = bool(force or not cache_valid)
    if used_external_api:
        generate_flipflop_base_cutout(
            scene_id=FLIPFLOP_FIXTURE_SCENE_ID,
            layers=[
                {
                    "id": FLIPFLOP_FIXTURE_LAYER_ID,
                    "type": "image",
                    "asset_kind": "cutout",
                    "prompt": (visual_prompt or DEFAULT_FIXTURE_PROMPT).strip(),
                    "placement": "center",
                    "enter_at_seconds": 0.0,
                    "animation": "none",
                    "contains_person": True,
                }
            ],
            script_id=FLIPFLOP_FIXTURE_SCRIPT_ID,
            scene_prompt=(visual_prompt or DEFAULT_FIXTURE_PROMPT).strip(),
            scene_narration=(narration or DEFAULT_FIXTURE_NARRATION).strip(),
            force=force,
            contains_person=True,
        )
        if not fixture_path.exists():
            raise FileNotFoundError("Flip-flop fixture generation did not create the expected base cutout.")

    return FlipflopFixtureResult(
        asset=_asset_from_path(fixture_path),
        used_external_api=used_external_api,
    )


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


def render_flipflop_fixture_preview(
    *,
    asset_id: str,
    action: FlipflopDebugAction = "blink",
) -> FlipflopFixtureRenderResult:
    """Render a real Remotion preview from a saved fixture asset without provider calls."""

    asset_path = _path_for_asset_id(asset_id)
    asset = _asset_from_path(asset_path)
    scene = Scene(
        id=FLIPFLOP_FIXTURE_SCENE_ID,
        narration=DEFAULT_FIXTURE_NARRATION,
        visual_prompt=DEFAULT_FIXTURE_PROMPT,
        duration_estimate_seconds=4.0,
        contains_person=True,
        visual_mode="flipflop",
        flipflop_action=action,
        renderer_context="shop",
        visual_layers=[
            VisualLayer(
                id=FLIPFLOP_FIXTURE_LAYER_ID,
                type="image",
                asset_kind="cutout",
                image_url=asset.asset_url,
                placement="center",
                enter_at_seconds=0.0,
                animation="none",
                visual_source_metadata=asset.source_metadata,
            )
        ],
    )
    content = ScriptContent(
        title="Flip-flop Fixture",
        format_id="youtube-listicle",
        visual_canvas=VisualCanvas(background_color="#1f1f1f"),
        segment_timer_enabled=False,
        subtitle_highlight_enabled=False,
        segments=[
            Segment(
                name="Fixture",
                scenes=[scene],
            )
        ],
    )
    render_url = render_full_video(
        script_id=asset.script_id,
        content=content,
        title="",
        speed=1.0,
        brand={},
    )
    return FlipflopFixtureRenderResult(
        asset=asset,
        action=action,
        render_url=render_url,
        used_external_api=False,
    )


def _asset_from_path(path: Path) -> FlipflopDebugAsset:
    path = path.resolve()
    relative = path.relative_to((DATA_DIR / "projects").resolve())
    parts = relative.parts
    script_id = parts[0] if len(parts) > 0 else ""
    scene_id = _scene_id_for_debug_asset(relative)
    created = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    source_metadata = _current_or_repaired_source_metadata(path)
    return FlipflopDebugAsset(
        asset_id=relative.as_posix(),
        asset_url=_web_url_for_project_path(path),
        script_id=script_id,
        scene_id=scene_id,
        filename=path.name,
        created_at=created,
        source_metadata=source_metadata,
    )


def _current_or_repaired_source_metadata(path: Path) -> dict[str, object]:
    metadata = _read_source_metadata(path) or {}
    if not metadata.get("source_type"):
        metadata = {**metadata, "source_type": _source_type_for_debug_asset(path)}
    anchor = metadata.get("flipflop_overlay_anchor")
    if (
        metadata.get("registration_algorithm_version") == FLIPFLOP_CUTOUT_REGISTRATION_VERSION
        and isinstance(anchor, dict)
        and anchor.get("detected") is True
        and isinstance(anchor.get("skin_fill"), str)
    ):
        return metadata
    try:
        with Image.open(path) as image:
            repaired_anchor = _flipflop_overlay_anchor_metadata(image.convert("RGBA"), require_detected=True)
    except OSError:
        return metadata
    except Exception as exc:
        if exc.__class__.__name__ != "FlipflopRegistrationError":
            raise
        return metadata

    repaired = {
        **metadata,
        "registration_algorithm_version": FLIPFLOP_CUTOUT_REGISTRATION_VERSION,
        "flipflop_overlay_anchor": repaired_anchor,
    }
    _write_source_metadata(path, repaired)
    return repaired


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
        not relative.parts
        or not relative.parts[0].startswith("test-lab-")
        or path.suffix.lower() != ".png"
        or not _is_allowed_debug_asset(relative)
        or not _is_reusable_debug_asset(path)
    ):
        raise ValueError(
            "Selected file is not a cached Test Lab flip-flop base cutout or saved Test Lab character cutout."
        )
    return path


def _is_allowed_debug_asset(relative: Path) -> bool:
    parts = relative.parts
    if len(parts) >= 4 and parts[1] == "flipflop_cutouts" and parts[-1].startswith("base_"):
        return True
    if len(parts) == 3 and parts[1] == "character" and parts[2] == "cutout.png":
        return True
    if len(parts) == 4 and parts[1] == "popup_crops" and parts[3] == "anchor_cutout.png":
        return True
    return False


def _is_reusable_debug_asset(path: Path) -> bool:
    relative = path.resolve().relative_to((DATA_DIR / "projects").resolve())
    if not _is_allowed_debug_asset(relative):
        return False
    parts = relative.parts
    if len(parts) == 4 and parts[1] == "popup_crops" and parts[3] == "anchor_cutout.png":
        if not _has_transparent_background(path):
            return False
    return _has_detectable_flipflop_anchor(path)


def _has_detectable_flipflop_anchor(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            _flipflop_overlay_anchor_metadata(image.convert("RGBA"), require_detected=True)
    except OSError:
        return False
    except FlipflopRegistrationError:
        return False
    return True


def _has_transparent_background(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            if image.mode != "RGBA":
                image = image.convert("RGBA")
            alpha = image.getchannel("A")
            extrema = alpha.getextrema()
    except OSError:
        return False
    return bool(extrema and extrema[0] < 245)


def _scene_id_for_debug_asset(relative: Path) -> str:
    parts = relative.parts
    if len(parts) >= 4 and parts[1] in {"flipflop_cutouts", "popup_crops"}:
        return parts[2]
    if len(parts) >= 3 and parts[1] == "character":
        return "character"
    return ""


def _source_type_for_debug_asset(path: Path) -> str:
    relative = path.resolve().relative_to((DATA_DIR / "projects").resolve())
    parts = relative.parts
    if len(parts) >= 3 and parts[1] == "character":
        return "character_cutout"
    if len(parts) >= 4 and parts[1] == "popup_crops":
        return "popup_anchor_cutout"
    return "flipflop_base_cutout"


def _fixture_asset_path() -> Path:
    return (
        DATA_DIR
        / "projects"
        / FLIPFLOP_FIXTURE_SCRIPT_ID
        / "flipflop_cutouts"
        / FLIPFLOP_FIXTURE_SCENE_ID
        / "base_flipflop_fixture_base.png"
    )


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
