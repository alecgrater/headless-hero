"""Full-frame blink audit and eligibility helpers."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from pydantic import BaseModel, Field
from sqlmodel import Session

from config import DATA_DIR
from models.script import Script, ScriptContent
from pipeline.image_gen import (
    BLINK_CUTOUT_REGISTRATION_VERSION,
    _blink_eye_fill_gradient,
    _sample_blink_face_skin_fill,
)

logger = logging.getLogger(__name__)

BURGER_KING_BLINK_AUDIT_SCRIPT_ID = "9dacedc774514306ae1acb85215449e1"
MEDIA_BACKED_BLINK_MODES = {"full_frame"}

# Conservative safety bounds for a believable detected eye pair (normalized
# image fractions). Tightening these trades blink coverage for never shipping a
# distorted overlay — quality over coverage.
BLINK_EYE_MIN_SIZE = 0.004
BLINK_EYE_MAX_SIZE = 0.14
# Keep equal to the renderer's floor (BLINK_EYE_MIN_SEPARATION in BlinkOverlay.tsx):
# a mismatch marks scenes as blinking that the renderer then refuses to draw.
BLINK_EYE_MIN_SEPARATION = 0.03
BLINK_EYE_MAX_SEPARATION = 0.6
# The renderer hard-caps each closed-eye mark's half-width at eyeDistance*0.22,
# so marks can never cross the nose. This guard only rejects degenerate
# mis-detections where an "eye" is nearly as wide as the gap between the eyes.
BLINK_EYE_MAX_WIDTH_VS_SEPARATION = 0.9
BLINK_FILL_MAX_LUMINANCE_GAP = 45
BLINK_LENS_MAX_VERTICAL_DELTA = 0.02  # = renderer BLINK_EYE_MAX_VERTICAL_DELTA


class FullFrameBlinkDetection(BaseModel):
    status: Literal["passed", "failed"]
    eligible: bool
    reason: str = ""
    anchor: dict[str, object] | None = None
    registration_algorithm_version: str = BLINK_CUTOUT_REGISTRATION_VERSION


class FullFrameBlinkCandidate(BaseModel):
    script_id: str
    scene_id: str
    segment_name: str
    scene_label: str
    visual_mode: str
    image_url: str
    image_path: str
    detection: FullFrameBlinkDetection
    # Approximate start offset of this scene in the long-form timeline, so a
    # designated blink can be cross-referenced against the exported video.
    start_seconds: float = 0.0


class FullFrameBlinkAuditReport(BaseModel):
    id: str
    script_id: str
    title: str
    created_at: str
    candidates: list[FullFrameBlinkCandidate] = Field(default_factory=list)


def detect_full_frame_blink_anchor(image_path: Path) -> FullFrameBlinkDetection:
    if not image_path.exists() or not image_path.is_file():
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="image_missing")
    try:
        with Image.open(image_path) as image:
            rgba = image.convert("RGBA")
            detection_image = _full_frame_detection_image(rgba)
            # Glasses first: it is the stricter test, and on a glasses face the
            # skin/eye-pair path can lock onto something else (it once picked two
            # outlined shirt pockets with buttons under the real face). A glasses
            # hit that fails the quality gate still lets the main path try.
            rejection_reason = "face_landmarks_missing"
            for detect in (_detect_full_frame_glasses_face_anchor_points, _detect_full_frame_main_face_anchor_points):
                detected = detect(detection_image)
                if detected is None:
                    continue
                anchor = _anchor_from_detection(rgba, detected)
                rejection_reason = full_frame_blink_quality_rejection_reason(anchor)
                if not rejection_reason:
                    return FullFrameBlinkDetection(status="passed", eligible=True, anchor=anchor)
    except OSError:
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="image_unreadable")
    return FullFrameBlinkDetection(status="failed", eligible=False, reason=rejection_reason)


def _anchor_from_detection(rgba: Image.Image, detected: dict[str, Any]) -> dict[str, object]:
    skin_fill = _sample_blink_face_skin_fill(rgba, detected)
    return {
        "version": 1,
        "detected": True,
        "coordinate_space": "normalized_image",
        **({"skin_fill": skin_fill} if skin_fill else {}),
        "eye_left": dict(detected["eye_left"]),
        "eye_right": dict(detected["eye_right"]),
        "mouth": dict(detected["mouth"]),
        "brow_left": dict(detected["brow_left"]),
        "brow_right": dict(detected["brow_right"]),
        **({"eye_fill_source": detected["eye_fill_source"]} if "eye_fill_source" in detected else {}),
    }


def full_frame_blink_quality_rejection_reason(anchor: dict[str, object]) -> str:
    """Return a stable reason when an anchor is not safe enough for production blink."""
    required = ("eye_left", "eye_right", "mouth", "brow_left", "brow_right")
    if anchor.get("detected") is not True:
        return "anchor_not_full_frame_safe"
    for key in required:
        point = anchor.get(key)
        if not isinstance(point, dict):
            return "anchor_not_full_frame_safe"
        if not isinstance(point.get("x"), int | float) or not isinstance(point.get("y"), int | float):
            return "anchor_not_full_frame_safe"
    if not isinstance(anchor.get("skin_fill"), str):
        return "anchor_not_full_frame_safe"

    left_eye = anchor["eye_left"]
    right_eye = anchor["eye_right"]
    if not isinstance(left_eye, dict) or not isinstance(right_eye, dict):
        return "anchor_not_full_frame_safe"
    left_width = _anchor_dimension(left_eye, "width")
    right_width = _anchor_dimension(right_eye, "width")
    left_height = _anchor_dimension(left_eye, "height")
    right_height = _anchor_dimension(right_eye, "height")
    if left_width <= 0 or right_width <= 0 or left_height <= 0 or right_height <= 0:
        return "anchor_not_full_frame_safe"

    width_ratio = min(left_width, right_width) / max(left_width, right_width)
    height_ratio = min(left_height, right_height) / max(left_height, right_height)
    if width_ratio < 0.65 or height_ratio < 0.65:
        return "blink_quality_eye_pair_asymmetric"

    left_y = float(left_eye["y"])
    right_y = float(right_eye["y"])
    # Lens anchors place each closed eye exactly on its own detected eye, so a
    # tilted head still reads right; allow the renderer's own limit for them.
    max_vertical_delta = BLINK_LENS_MAX_VERTICAL_DELTA if anchor.get("eye_fill_source") == "lens" else 0.008
    if abs(left_y - right_y) > max_vertical_delta:
        return "blink_quality_eye_pair_misaligned"

    # Conservative absolute eye-size sanity (normalized image fractions). Real
    # eyes occupy a small, bounded fraction of the frame; anything outside this
    # range is a mis-detection that would render as an oversized smear.
    for value in (left_width, right_width, left_height, right_height):
        if value < BLINK_EYE_MIN_SIZE or value > BLINK_EYE_MAX_SIZE:
            return "blink_quality_eye_size_out_of_range"

    separation = abs(float(right_eye["x"]) - float(left_eye["x"]))
    if separation < BLINK_EYE_MIN_SEPARATION or separation > BLINK_EYE_MAX_SEPARATION:
        return "blink_quality_eye_separation_out_of_range"

    # The closed-eye marks are ~1.2x the detected eye width. If an eye is wide
    # relative to the gap between the eyes, the two marks would reach across the
    # nose — suppress rather than ship a bar.
    if max(left_width, right_width) > separation * BLINK_EYE_MAX_WIDTH_VS_SEPARATION:
        return "blink_quality_overlay_would_span_nose"

    # The closed eye is painted with these fills. On a pale face the skin sampler
    # can only find the grey eye edge, and the blink renders as two grey patches.
    # Lens fills are sampled from the lens itself, so a tinted lens is expected
    # to differ from the face.
    if anchor.get("eye_fill_source") != "lens":
        skin_rgb = _hex_rgb(anchor.get("skin_fill"))
        for eye in (left_eye, right_eye):
            fill_rgb = _hex_rgb(eye.get("fill_top"))
            if skin_rgb and fill_rgb and abs(_luminance(fill_rgb) - _luminance(skin_rgb)) > BLINK_FILL_MAX_LUMINANCE_GAP:
                return "blink_quality_fill_mismatch"

    return ""


# --- Closed-eye preview --------------------------------------------------------
# A line-for-line port of blinkBlinkEyeOverlayGeometry (remotion TreatmentRenderer
# .tsx) so the backend can look at the exact closed eye the renderer will draw
# before keeping a blink. Keep the two in step: test_full_frame_blink_preview pins
# the numbers against the TypeScript output for a fixed anchor.
BLINK_EYELID_STROKE = "#2A1712"
BLINK_FALLBACK_SKIN_FILL = "#D9A374"
_BLINK_MAX_ON_SCREEN_ASPECT = 2.4


def _color_distance(first: object, second: object) -> float | None:
    a, b = _hex_rgb(first), _hex_rgb(second)
    if a is None or b is None:
        return None
    return math.dist(a, b)


def blink_closed_eye_geometry(anchor: dict[str, Any], aspect: float = 16 / 9) -> list[dict[str, Any]]:
    """Closed-eye mask and lid per eye, in the renderer's 0–100 viewBox units."""
    left, right = anchor["eye_left"], anchor["eye_right"]
    sizes = []
    for point in (left, right):
        width, height = point.get("width"), point.get("height")
        if not isinstance(width, int | float) or not isinstance(height, int | float) or width <= 0 or height <= 0:
            return []
        sizes.append((width, height))
    left_eye = (left["x"] * 100, left["y"] * 100)
    right_eye = (right["x"] * 100, right["y"] * 100)
    eye_distance = abs(right_eye[0] - left_eye[0])
    if not eye_distance > 0:
        return []
    midpoint_x = (left_eye[0] + right_eye[0]) / 2
    nose_margin = max(eye_distance * 0.1, 1.0)
    safe_aspect = aspect if aspect > 0 else 16 / 9
    skin_fill = anchor.get("skin_fill") if isinstance(anchor.get("skin_fill"), str) else BLINK_FALLBACK_SKIN_FILL
    shapes = []
    for point, (eye_x, eye_y), (width, height), side in (
        (left, left_eye, sizes[0], "left"),
        (right, right_eye, sizes[1], "right"),
    ):
        eye_width, eye_height = width * 100, height * 100
        mask_half_height = max(eye_height * 0.85, eye_height * 0.5 + 0.4)
        mask_half_width = min(
            eye_width * 0.6,
            eye_distance * 0.22,
            (mask_half_height * _BLINK_MAX_ON_SCREEN_ASPECT) / safe_aspect,
        )
        mask_left, mask_right = eye_x - mask_half_width, eye_x + mask_half_width
        if side == "left":
            mask_right = min(mask_right, midpoint_x - nose_margin)
        else:
            mask_left = max(mask_left, midpoint_x + nose_margin)
        mask_width = max(0.0, mask_right - mask_left)
        mask_height = mask_half_height * 2
        side_distance = _color_distance(point.get("fill_left"), point.get("fill_right"))
        vertical_distance = _color_distance(point.get("fill_top"), point.get("fill_bottom"))
        if side_distance is not None and (vertical_distance is None or side_distance >= vertical_distance):
            gradient = ("horizontal", point["fill_left"], point["fill_right"])
        elif vertical_distance is not None:
            gradient = ("vertical", point["fill_top"], point["fill_bottom"])
        else:
            gradient = None
        lid_half_width = max(0.0, min(eye_width * 0.5, eye_distance * 0.22, eye_x - mask_left, mask_right - eye_x))
        shapes.append({
            "mask": {
                "x": mask_left, "y": eye_y - mask_half_height, "width": mask_width, "height": mask_height,
                "rx": min(mask_width, mask_height) / 2, "fill": skin_fill, "gradient": gradient,
            },
            "lid": {
                "start": (eye_x - lid_half_width, eye_y),
                "control": (eye_x, eye_y - mask_half_height * 0.3),
                "end": (eye_x + lid_half_width, eye_y),
                "stroke_width": min(max(eye_height * 0.28, 0.4), 0.9),
            },
        })
    return shapes


def _rounded_box_mask(size: tuple[int, int], box: tuple[float, float, float, float], rx: float, ry: float) -> Image.Image:
    """SVG <rect rx> under preserveAspectRatio="none": corners are ellipses (rx·sx by rx·sy), not circles."""
    from PIL import ImageDraw

    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    x0, y0, x1, y1 = box
    rx, ry = min(rx, (x1 - x0) / 2), min(ry, (y1 - y0) / 2)
    draw.rectangle((x0 + rx, y0, x1 - rx, y1), fill=255)
    draw.rectangle((x0, y0 + ry, x1, y1 - ry), fill=255)
    for cx, cy in ((x0 + rx, y0 + ry), (x1 - rx, y0 + ry), (x0 + rx, y1 - ry), (x1 - rx, y1 - ry)):
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    return mask


def render_closed_eye_frame(image: Image.Image, anchor: dict[str, Any]) -> Image.Image:
    """The image with the renderer's closed-eye overlay drawn on it (2x supersampled, eye region only)."""
    from PIL import ImageDraw

    base = image.convert("RGBA")
    width, height = base.size
    shapes = blink_closed_eye_geometry(anchor, width / height)
    if not shapes:
        return base
    # Work only on the region around the eyes; full-frame 2x layers cost ~16 MB each.
    left = max(0, int(min(sh["mask"]["x"] for sh in shapes) * width / 100) - 8)
    top = max(0, int(min(sh["mask"]["y"] for sh in shapes) * height / 100) - 8)
    right = min(width, int(max(sh["mask"]["x"] + sh["mask"]["width"] for sh in shapes) * width / 100) + 9)
    bottom = min(height, int(max(sh["mask"]["y"] + sh["mask"]["height"] for sh in shapes) * height / 100) + 9)
    scale = 2
    region = ((right - left) * scale, (bottom - top) * scale)
    overlay = Image.new("RGBA", region, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    sx, sy = width * scale / 100, height * scale / 100
    ox, oy = left * scale, top * scale
    lid_rgb = _hex_rgb(BLINK_EYELID_STROKE)
    for shape in shapes:
        mask = shape["mask"]
        box = (mask["x"] * sx - ox, mask["y"] * sy - oy, (mask["x"] + mask["width"]) * sx - ox,
               (mask["y"] + mask["height"]) * sy - oy)
        if box[2] - box[0] < 1 or box[3] - box[1] < 1:
            continue
        shape_mask = _rounded_box_mask(region, box, mask["rx"] * sx, mask["rx"] * sy)
        fill_layer = Image.new("RGBA", region, (0, 0, 0, 0))
        fill_draw = ImageDraw.Draw(fill_layer)
        if mask["gradient"]:
            orientation, start, end = mask["gradient"]
            start_rgb, end_rgb = _hex_rgb(start), _hex_rgb(end)
            span = (box[2] - box[0]) if orientation == "horizontal" else (box[3] - box[1])
            for step in range(int(span) + 1):
                t = step / max(span, 1)
                color = tuple(round(a + (b - a) * t) for a, b in zip(start_rgb, end_rgb)) + (255,)
                if orientation == "horizontal":
                    fill_draw.line([(box[0] + step, box[1]), (box[0] + step, box[3])], fill=color)
                else:
                    fill_draw.line([(box[0], box[1] + step), (box[2], box[1] + step)], fill=color)
        else:
            fill_draw.rectangle(box, fill=_hex_rgb(mask["fill"]) + (255,))
        overlay.paste(fill_layer, (0, 0), shape_mask)
        lid = shape["lid"]
        (x0, y0), (cx, cy), (x1, y1) = lid["start"], lid["control"], lid["end"]
        points = []
        for index in range(25):
            t = index / 24
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1
            points.append((x * sx - ox, y * sy - oy))
        # A near-horizontal stroke in a non-uniformly stretched viewBox is as
        # thick as the vertical scale makes it.
        stroke = max(1, round(lid["stroke_width"] * sy))
        draw.line(points, fill=lid_rgb + (255,), width=stroke, joint="curve")
        for px, py in (points[0], points[-1]):
            draw.ellipse((px - stroke / 2, py - stroke / 2, px + stroke / 2, py + stroke / 2), fill=lid_rgb + (255,))
    patch = overlay.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
    result = base.copy()
    result.alpha_composite(patch, (left, top))
    return result


def _hex_rgb(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return None
    try:
        return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
    except ValueError:
        return None


def build_full_frame_blink_metadata(script_id: str, scene_id: str, image_url: str) -> dict[str, object] | None:
    """Build production full-frame blink metadata using the same detector as Blink Audit.

    Blink is auto-enabled wherever the anchor passes strict safety validation;
    unsafe anchors are silently suppressed (no metadata). There is no deterministic
    coverage gate and no manual review.
    """
    image_path = image_path_from_static_url(image_url)
    if image_path is None:
        return None
    detection = detect_full_frame_blink_anchor(image_path)
    if not detection.eligible or detection.anchor is None:
        return None
    verdict = blink_vision_check(image_path, detection.anchor, script_id=script_id)
    if verdict.passed is False:
        logger.warning(
            "[BLINK] vision check rejected blink scene=%s script=%s: %s", scene_id, script_id, verdict.note
        )
        return None
    logger.info(
        "[BLINK] blink enabled scene=%s script=%s vision_check=%s",
        scene_id, script_id, "passed" if verdict.passed else f"skipped ({verdict.note})",
    )
    return {
        "enabled": True,
        "action": "blink",
        "anchor": detection.anchor,
        "vision_check": "passed" if verdict.passed else "skipped",
    }


class BlinkVisionVerdict(BaseModel):
    passed: bool | None  # None: the check could not run, so the geometric gate alone decides
    note: str = ""


BLINK_VISION_QUESTION = """Image A is a frame from a cartoon. Image B is the same frame with an automatic "closed eyes" overlay drawn on it, used to make the character blink.
Judge ONLY whether Image B is a clean, believable blink. Return only a JSON object:
{"on_the_eyes": true/false (each closed-eye mark sits exactly where an open eye was, inside the glasses if there are any),
 "eyes_hidden": true/false (the open eyes from Image A are no longer visible in Image B),
 "looks_natural": true/false (Image B reads as the same character with eyes closed, in the drawing's own style),
 "visible_patch": true/false (a box, smear, bar, or patch of a different color is visible around the marks),
 "note": "under 15 words"}"""


def _blink_eye_crop_box(anchor: dict[str, Any], width: int, height: int) -> tuple[float, float, float, float]:
    center_x = (anchor["eye_left"]["x"] + anchor["eye_right"]["x"]) / 2 * width
    center_y = (anchor["eye_left"]["y"] + anchor["eye_right"]["y"]) / 2 * height
    separation = max(abs(anchor["eye_right"]["x"] - anchor["eye_left"]["x"]) * width, 8.0)
    return (
        max(0.0, center_x - separation * 1.6),
        max(0.0, center_y - separation * 0.8),
        min(float(width), center_x + separation * 1.6),
        min(float(height), center_y + separation * 0.8),
    )


def blink_vision_check(image_path: Path, anchor: dict[str, Any], *, script_id: str | None = None) -> BlinkVisionVerdict:
    """Show Claude the eyes open and with the renderer's closed-eye overlay; keep the blink only if it passes.

    The geometric gate had no false positives on 106 test images, but loosening
    detection for coverage is exactly where bad blinks would slip in, and a
    picture is the only reliable way to judge "does this look like a blink".
    Runs on the cloud even in Local Mode, like cutout-sheet escalation; with no
    key, or on any failure, it is skipped and the geometric gate alone decides.
    """
    from integrations import vision_client

    if not vision_client.vision_check_available():
        return BlinkVisionVerdict(passed=None, note="no Anthropic key")
    if time.monotonic() < _VISION_BREAKER["open_until"]:
        return BlinkVisionVerdict(passed=None, note="paused after repeated failures")
    cache_path = image_path.with_name(f"{image_path.name}.blinkcheck.json")
    cache_key = _vision_cache_key(image_path, anchor)
    try:
        cached = json.loads(cache_path.read_text())
        if cached.get("key") == cache_key:
            return BlinkVisionVerdict(passed=cached["passed"], note=cached.get("note", ""))
    except (OSError, ValueError, KeyError):
        pass
    try:
        with Image.open(image_path) as image:
            base = image.convert("RGBA")
        closed = render_closed_eye_frame(base, anchor)
        box = _blink_eye_crop_box(anchor, *base.size)
        answer = vision_client.judge_images(
            BLINK_VISION_QUESTION,
            [("Image A:", base.crop(box)), ("Image B:", closed.crop(box))],
            operation="blink_check",
            script_id=script_id,
        )
    except Exception as exc:  # noqa: BLE001 - a failed check must never block image generation
        with _VISION_BREAKER_LOCK:
            _VISION_BREAKER["failures"] += 1
            if _VISION_BREAKER["failures"] >= VISION_BREAKER_FAILURES:
                _VISION_BREAKER["open_until"] = time.monotonic() + VISION_BREAKER_COOLDOWN_SECONDS
                _VISION_BREAKER["failures"] = 0
                logger.warning("[BLINK] vision check paused for %ds after repeated failures", VISION_BREAKER_COOLDOWN_SECONDS)
        logger.warning("[BLINK] vision check unavailable (%s: %s); keeping the geometric decision", type(exc).__name__, exc)
        return BlinkVisionVerdict(passed=None, note=f"check failed: {type(exc).__name__}")
    with _VISION_BREAKER_LOCK:
        _VISION_BREAKER["failures"] = 0
    passed = (
        answer.get("on_the_eyes") is True
        and answer.get("eyes_hidden") is True
        and answer.get("looks_natural") is True
        and answer.get("visible_patch") is False
    )
    verdict = BlinkVisionVerdict(passed=passed, note=str(answer.get("note") or "")[:200])
    try:
        cache_path.write_text(json.dumps({"key": cache_key, "passed": verdict.passed, "note": verdict.note}))
    except OSError:
        pass
    return verdict


# During an outage every scene would wait out its own timeout; after a few
# consecutive failures, skip checks for a while instead.
VISION_BREAKER_FAILURES = 3
VISION_BREAKER_COOLDOWN_SECONDS = 600
_VISION_BREAKER = {"failures": 0, "open_until": 0.0}
_VISION_BREAKER_LOCK = threading.Lock()


def _vision_cache_key(image_path: Path, anchor: dict[str, Any]) -> str:
    """Same image file + same anchor + same question = same verdict, so reruns are free."""
    stat = image_path.stat()
    payload = json.dumps({"mtime": stat.st_mtime_ns, "size": stat.st_size, "anchor": anchor,
                          "question": BLINK_VISION_QUESTION}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _anchor_dimension(point: dict[str, object], key: str) -> float:
    value = point.get(key)
    return float(value) if isinstance(value, int | float) else 0.0


def run_full_frame_blink_audit(
    *,
    session: Session,
    script_id: str = BURGER_KING_BLINK_AUDIT_SCRIPT_ID,
) -> FullFrameBlinkAuditReport:
    script = session.get(Script, script_id)
    if script is None:
        raise FileNotFoundError(f"Script not found: {script_id}")
    content = ScriptContent.model_validate_json(script.script_json)
    report = FullFrameBlinkAuditReport(
        id=f"blink-audit-{uuid.uuid4().hex[:12]}",
        script_id=script.id,
        title=script.topic_title or content.title,
        created_at=datetime.now(timezone.utc).isoformat(),
        candidates=[],
    )
    elapsed = 0.0
    for segment in content.segments:
        for scene in segment.scenes:
            scene_start = elapsed
            duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds
            elapsed += duration
            if scene.is_title_card or scene.visual_mode not in MEDIA_BACKED_BLINK_MODES:
                continue
            image_url = _scene_image_url(script.id, scene.id, scene.image_url)
            image_path = image_path_from_static_url(image_url)
            if image_path is None:
                detection = FullFrameBlinkDetection(status="failed", eligible=False, reason="image_missing")
                resolved_path = ""
            else:
                detection = detect_full_frame_blink_anchor(image_path)
                resolved_path = str(image_path)
            report.candidates.append(
                FullFrameBlinkCandidate(
                    script_id=script.id,
                    scene_id=scene.id,
                    segment_name=segment.name,
                    scene_label=scene.narration[:80],
                    visual_mode=scene.visual_mode,
                    image_url=image_url,
                    image_path=resolved_path,
                    detection=detection,
                    start_seconds=round(scene_start, 2),
                )
            )
    save_blink_audit_report(report)
    return report


def list_blink_audit_reports() -> list[FullFrameBlinkAuditReport]:
    reports = []
    for path in sorted(_audit_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        reports.append(FullFrameBlinkAuditReport.model_validate_json(path.read_text(encoding="utf-8")))
    return reports


def load_blink_audit_report(report_id: str) -> FullFrameBlinkAuditReport:
    path = _audit_report_path(report_id)
    if not path.exists():
        raise FileNotFoundError(report_id)
    return FullFrameBlinkAuditReport.model_validate_json(path.read_text(encoding="utf-8"))


def save_blink_audit_report(report: FullFrameBlinkAuditReport) -> None:
    path = _audit_report_path(report.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def _anchor_is_full_frame_eligible(anchor: dict[str, object]) -> bool:
    return full_frame_blink_quality_rejection_reason(anchor) == ""


def _full_frame_detection_image(image: Image.Image) -> Image.Image:
    max_dimension = 960
    width, height = image.size
    largest_dimension = max(width, height)
    if largest_dimension <= max_dimension:
        return image
    scale = max_dimension / largest_dimension
    resized = image.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.NEAREST,
    )
    return resized.convert("RGBA")


def _detect_full_frame_main_face_anchor_points(image: Image.Image) -> dict[str, dict[str, float]] | None:
    width, height = image.size
    if width <= 0 or height <= 0:
        return None
    components_by_kind = _collect_full_frame_components(image)
    skin_components = components_by_kind["skin"]
    dark_components = components_by_kind["dark"]
    light_eye_components = components_by_kind["light_eye"]
    components = [*skin_components, *dark_components, *light_eye_components]
    face_components = [
        component
        for component in skin_components
        if component["area"] >= max(180, width * height * 0.0012)
        and 0.045 <= component["width"] <= 0.42
        and 0.07 <= component["height"] <= 0.58
        and 0.42 <= component["width"] / max(component["height"], 0.001) <= 1.35
    ]
    ranked_faces = sorted(
        face_components,
        key=lambda component: (
            component["area"],
            -abs(component["cx"] - 0.48),
            -component["cy"],
        ),
        reverse=True,
    )
    if not ranked_faces:
        return None
    return _anchor_for_face_component(image, ranked_faces[0], dark_components, light_eye_components, components)


# --- Glasses faces -----------------------------------------------------------
# Minimal cartoon characters with round glasses defeat the skin/eye-pair path:
# the frame joins both eyes and the hair into one dark shape, the eyes are small
# grey dots behind tinted lenses, and an off-white head merges with pale walls.
# Measured on 76 images of a stick-figure protagonist: the main path made 2
# faces eligible; with this path 31 pass the quality gate, with no false hits.
# It runs first (see detect_full_frame_blink_anchor), and its anchor goes
# through the same full_frame_blink_quality_rejection_reason gate.
GLASSES_LENS_MIN_WIDTH = 0.008
GLASSES_LENS_MAX_WIDTH = 0.14  # close-ups: lenses measured up to ~12% of frame width
GLASSES_RIM_MIN_FRACTION = 0.6
GLASSES_EYE_CONTRAST = 40  # glare on tinted lenses washed eyes out at 55


def _luminance(pixel: tuple[int, ...]) -> float:
    red, green, blue = pixel[:3]
    return 0.299 * red + 0.587 * green + 0.114 * blue


def _is_full_frame_pale_pixel(red: int, green: int, blue: int, alpha: int) -> bool:
    return alpha > 140 and min(red, green, blue) >= 170 and max(red, green, blue) - min(red, green, blue) <= 45


def _collect_pale_and_dark_components(image: Image.Image) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    width, height = image.size
    pixels = image.load()
    pale: set[tuple[int, int]] = set()
    dark: set[tuple[int, int]] = set()
    for y in range(round(height * 0.04), round(height * 0.82)):
        for x in range(round(width * 0.03), round(width * 0.97)):
            red, green, blue, alpha = pixels[x, y]
            if _is_full_frame_pale_pixel(red, green, blue, alpha):
                pale.add((x, y))
            if alpha > 80 and red < 70 and green < 70 and blue < 70:
                dark.add((x, y))
    return (
        _components_from_points(pale, width, height, "pale", min_area=20),
        _components_from_points(dark, width, height, "dark", min_area=8),
    )


def _lens_rim_fraction(image: Image.Image, lens: dict[str, float], *, samples: int = 36, reach: float = 1.9) -> float:
    """Share of rays from the lens center that meet a dark rim within `reach` lens radii.

    Walks outward rather than sampling one circle: a lens highlight splits the
    pale interior, so the detected lens shape can be smaller than the real lens.
    """
    width, height = image.size
    pixels = image.load()
    center_x, center_y = lens["cx"] * width, lens["cy"] * height
    radius = max(lens["width"] * width, lens["height"] * height) / 2
    hits = 0
    for index in range(samples):
        angle = 2 * math.pi * index / samples
        for step in range(int(radius * 0.5), int(radius * reach) + 2):
            x = int(center_x + step * math.cos(angle))
            y = int(center_y + step * math.sin(angle))
            if not (0 <= x < width and 0 <= y < height):
                break
            if _luminance(pixels[x, y]) < 90:
                hits += 1
                break
    return hits / samples


def _eye_inside_lens(image: Image.Image, lens: dict[str, float]) -> dict[str, float] | None:
    """The blob clearly darker than the lens itself — eyes behind tinted glass are grey, not black."""
    width, height = image.size
    pixels = image.load()
    # Only inside the lens oval: the corners of the lens' bounding box lie on the
    # dark rim, which would otherwise pass for an eye in an empty pair of glasses.
    center_x, center_y = lens["cx"] * width, lens["cy"] * height
    radius_x, radius_y = lens["width"] * width * 0.4, lens["height"] * height * 0.4
    inside = [
        (x, y)
        for y in range(int(center_y - radius_y), int(center_y + radius_y) + 1)
        for x in range(int(center_x - radius_x), int(center_x + radius_x) + 1)
        if 0 <= x < width and 0 <= y < height
        and ((x - center_x) / max(radius_x, 1)) ** 2 + ((y - center_y) / max(radius_y, 1)) ** 2 <= 1
    ]
    if not inside:
        return None
    levels = sorted(_luminance(pixels[x, y]) for x, y in inside)
    lens_level = levels[int(len(levels) * 0.7)]
    points = {(x, y) for x, y in inside if _luminance(pixels[x, y]) < lens_level - GLASSES_EYE_CONTRAST}
    blobs = _components_from_points(points, width, height, "eye", min_area=4)
    eye = max(blobs, key=lambda blob: blob["area"], default=None)
    if eye is None:
        return None
    lens_area = lens["width"] * width * lens["height"] * height
    if eye["area"] > lens_area * 0.4 or eye["width"] > lens["width"] * 0.6 or eye["height"] > lens["height"] * 0.6:
        return None
    return eye


def _lens_fill(image: Image.Image, lens: dict[str, float]) -> str | None:
    """Median color of the lens interior, excluding the eye and the rim.

    The closed eye is painted over with this. Sampling the erase-box edges
    instead picked up the eye and frame and left a visible grey patch.
    """
    width, height = image.size
    pixels = image.load()
    x0, x1 = int(lens["left"] * width), int(lens["right"] * width)
    y0, y1 = int(lens["top"] * height), int(lens["bottom"] * height)
    samples = [pixels[x, y][:3] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    if not samples:
        return None
    levels = sorted(_luminance(sample) for sample in samples)
    floor = levels[int(len(levels) * 0.7)] - 20
    bright = [sample for sample in samples if _luminance(sample) >= floor]
    if not bright:
        return None
    channels = [sorted(sample[index] for sample in bright)[len(bright) // 2] for index in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*channels)


def _eyes_share_gaze(
    left_eye: dict[str, float], left_lens: dict[str, float], right_eye: dict[str, float], right_lens: dict[str, float]
) -> bool:
    def offset(eye: dict[str, float], lens: dict[str, float]) -> tuple[float, float]:
        return (eye["cx"] - lens["cx"]) / max(lens["width"], 0.001), (eye["cy"] - lens["cy"]) / max(lens["height"], 0.001)

    (left_dx, left_dy), (right_dx, right_dy) = offset(left_eye, left_lens), offset(right_eye, right_lens)
    return abs(left_dx - right_dx) <= 0.25 and abs(left_dy - right_dy) <= 0.25


def _with_size(eye: dict[str, float], width: float, height: float) -> dict[str, float]:
    return {
        **eye,
        "width": width,
        "height": height,
        "left": eye["cx"] - width / 2,
        "right": eye["cx"] + width / 2,
        "top": eye["cy"] - height / 2,
        "bottom": eye["cy"] + height / 2,
    }


def _clamp_box_to(box: dict[str, float], bounds: dict[str, float]) -> dict[str, float]:
    return {
        "left": round(max(box["left"], bounds["left"]), 4),
        "top": round(max(box["top"], bounds["top"]), 4),
        "right": round(min(box["right"], bounds["right"]), 4),
        "bottom": round(min(box["bottom"], bounds["bottom"]), 4),
    }


def _detect_full_frame_glasses_face_anchor_points(image: Image.Image) -> dict[str, Any] | None:
    width, height = image.size
    if width <= 0 or height <= 0:
        return None
    pale_components, dark_components = _collect_pale_and_dark_components(image)
    aspect = width / height
    lenses = [
        component
        for component in pale_components
        if GLASSES_LENS_MIN_WIDTH <= component["width"] <= GLASSES_LENS_MAX_WIDTH
        and component["area"] >= 30
        and 0.6 <= (component["width"] * aspect) / max(component["height"], 0.001) <= 1.7
    ]
    best: tuple[float, dict, dict, dict, dict, dict] | None = None
    # Rim and eye checks depend on one lens only; compute each once, not per pair.
    rim_cache: dict[int, float] = {}
    eye_cache: dict[int, dict[str, float] | None] = {}

    def rim(lens: dict[str, float]) -> float:
        if id(lens) not in rim_cache:
            rim_cache[id(lens)] = _lens_rim_fraction(image, lens)
        return rim_cache[id(lens)]

    def eye_of(lens: dict[str, float]) -> dict[str, float] | None:
        if id(lens) not in eye_cache:
            eye_cache[id(lens)] = _eye_inside_lens(image, lens)
        return eye_cache[id(lens)]

    for left_lens in lenses:
        for right_lens in lenses:
            if left_lens is right_lens or left_lens["cx"] >= right_lens["cx"]:
                continue
            # A highlight can split one lens' pale interior, so widths match loosely;
            # heights (unaffected by a vertical glare stripe) still match strictly.
            if min(left_lens["width"], right_lens["width"]) / max(left_lens["width"], right_lens["width"]) < 0.55:
                continue
            if min(left_lens["height"], right_lens["height"]) / max(left_lens["height"], right_lens["height"]) < 0.7:
                continue
            lens_width = (left_lens["width"] + right_lens["width"]) / 2
            lens_height = (left_lens["height"] + right_lens["height"]) / 2
            if abs(left_lens["cy"] - right_lens["cy"]) > lens_height * 0.3:
                continue
            gap = right_lens["left"] - left_lens["right"]
            if not lens_width * 0.05 <= gap <= lens_width * 1.2:
                continue
            if rim(left_lens) < GLASSES_RIM_MIN_FRACTION or rim(right_lens) < GLASSES_RIM_MIN_FRACTION:
                continue
            left_eye = eye_of(left_lens)
            right_eye = eye_of(right_lens)
            if left_eye is None or right_eye is None:
                continue
            # Glare on one lens shrinks that eye's blob. Accept a size mismatch only
            # when both eyes sit in the same spot inside their lenses (same gaze);
            # the pair then gets one shared size below.
            if min(left_eye["area"], right_eye["area"]) / max(left_eye["area"], right_eye["area"]) < 0.25:
                continue
            if not _eyes_share_gaze(left_eye, left_lens, right_eye, right_lens):
                continue
            # The pale face has to continue below the glasses, or this is just two
            # framed pale shapes (windows, gauges) that happen to sit side by side.
            span = right_lens["right"] - left_lens["left"]
            faces = [
                component
                for component in pale_components
                if component is not left_lens
                and component is not right_lens
                and component["left"] <= left_lens["cx"]
                and component["right"] >= right_lens["cx"]
                and component["bottom"] >= max(left_lens["bottom"], right_lens["bottom"]) + lens_height * 0.3
                and span * 0.6 <= component["width"] <= span * 3.5
            ]
            # ...and above them: a forehead. Outlined shirt pockets with buttons passed
            # every other check; the collar above them is not pale head.
            foreheads = [
                component
                for component in pale_components
                if component is not left_lens
                and component is not right_lens
                and component["left"] <= right_lens["cx"]
                and component["right"] >= left_lens["cx"]
                and component["top"] <= min(left_lens["top"], right_lens["top"]) - lens_height * 0.2
                and component["bottom"] >= min(left_lens["top"], right_lens["top"]) - lens_height * 0.6
                and component["width"] >= span * 0.4
            ]
            if not faces or not foreheads:
                continue
            face_component = max(faces, key=lambda component: component["area"])
            score = -abs(left_lens["cy"] - right_lens["cy"]) + min(left_eye["area"], right_eye["area"]) / 1000
            if best is None or score > best[0]:
                best = (score, left_lens, right_lens, face_component, left_eye, right_eye)
    if best is None:
        return None
    _score, left_lens, right_lens, face_component, left_eye, right_eye = best
    # Glare only shrinks a blob, so the larger eye is the true size; an average
    # left the real eye's edges uncovered when the blobs differed 2x.
    shared_width = max(left_eye["width"], right_eye["width"])
    shared_height = max(left_eye["height"], right_eye["height"])
    left_eye = _with_size(left_eye, shared_width, shared_height)
    right_eye = _with_size(right_eye, shared_width, shared_height)
    lens_height = (left_lens["height"] + right_lens["height"]) / 2
    face_left = min(face_component["left"], left_lens["left"])
    face_right = max(face_component["right"], right_lens["right"])
    face_top = max(0.0, min(left_lens["top"], right_lens["top"]) - lens_height)
    face_bottom = face_component["bottom"]
    face = {
        "left": face_left,
        "right": face_right,
        "top": face_top,
        "bottom": face_bottom,
        "width": face_right - face_left,
        "height": face_bottom - face_top,
        "cx": (face_left + face_right) / 2,
        "cy": (face_top + face_bottom) / 2,
        "area": face_component["area"],
    }
    eye_y = (left_eye["cy"] + right_eye["cy"]) / 2
    midpoint = (left_eye["cx"] + right_eye["cx"]) / 2
    mouth = _mouth_for_face(face, dark_components, midpoint, eye_y)
    brow_y = max(face_top, eye_y - face["height"] * 0.17)
    eyes = {}
    for key, eye, lens in (("eye_left", left_eye, left_lens), ("eye_right", right_eye, right_lens)):
        # Keep the erase inside the lens so the closed eye never paints over the frame.
        erase_box = _clamp_box_to(_full_frame_eye_erase_box(eye, face), lens)
        # Lens interiors are one flat color, so the closed eye is painted with it
        # directly. _blink_eye_fill_gradient skips pale pixels (it was built to
        # avoid eye whites on skin-toned faces) and returned the grey eye edge.
        lens_fill = _lens_fill(image, lens)
        if lens_fill is None:
            return None
        fill_top = fill_bottom = fill_left = fill_right = lens_fill
        eyes[key] = {
            "x": round(eye["cx"], 4),
            "y": round(eye["cy"], 4),
            "width": round(eye["width"], 4),
            "height": round(eye["height"], 4),
            "erase_box": erase_box,
            "fill_top": fill_top,
            "fill_bottom": fill_bottom,
            "fill_left": fill_left,
            "fill_right": fill_right,
        }
    return {
        **eyes,
        "eye_fill_source": "lens",
        "mouth": {"x": round(mouth["cx"], 4), "y": round(mouth["cy"], 4)},
        "brow_left": {"x": round(left_eye["cx"], 4), "y": round(brow_y, 4)},
        "brow_right": {"x": round(right_eye["cx"], 4), "y": round(brow_y, 4)},
    }


def _collect_full_frame_components(image: Image.Image) -> dict[str, list[dict[str, float]]]:
    width, height = image.size
    pixels = image.load()
    points_by_kind = {
        "skin": set(),
        "dark": set(),
        "light_eye": set(),
    }
    for y in range(round(height * 0.04), round(height * 0.82)):
        for x in range(round(width * 0.03), round(width * 0.97)):
            red, green, blue, alpha = pixels[x, y]
            if _is_full_frame_skin_pixel(red, green, blue, alpha):
                points_by_kind["skin"].add((x, y))
            if alpha > 80 and red < 70 and green < 70 and blue < 70:
                points_by_kind["dark"].add((x, y))
            if _is_full_frame_light_eye_pixel(red, green, blue, alpha):
                points_by_kind["light_eye"].add((x, y))

    return {
        kind: _components_from_points(points, width, height, kind, min_area=60 if kind == "skin" else 8)
        for kind, points in points_by_kind.items()
    }


def _components_from_points(
    points: set[tuple[int, int]],
    width: int,
    height: int,
    kind: str,
    *,
    min_area: int,
) -> list[dict[str, float]]:
    collected: list[dict[str, float]] = []
    seen: set[tuple[int, int]] = set()
    for point in list(points):
        if point in seen:
            continue
        stack = [point]
        seen.add(point)
        xs: list[int] = []
        ys: list[int] = []
        while stack:
            x, y = stack.pop()
            xs.append(x)
            ys.append(y)
            for nx in (x - 1, x, x + 1):
                for ny in (y - 1, y, y + 1):
                    neighbor = (nx, ny)
                    if neighbor != (x, y) and neighbor in points and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        if len(xs) < min_area:
            continue
        left = min(xs)
        top = min(ys)
        right = max(xs)
        bottom = max(ys)
        box_width = right - left + 1
        box_height = bottom - top + 1
        if box_width <= 0 or box_height <= 0:
            continue
        collected.append(
            {
                "kind": kind,
                "area": float(len(xs)),
                "left": left / width,
                "top": top / height,
                "right": right / width,
                "bottom": bottom / height,
                "cx": (sum(xs) / len(xs)) / width,
                "cy": (sum(ys) / len(ys)) / height,
                "width": box_width / width,
                "height": box_height / height,
            }
        )
    return collected


def _is_full_frame_light_eye_pixel(red: int, green: int, blue: int, alpha: int) -> bool:
    if alpha <= 120:
        return False
    channel_max = max(red, green, blue)
    channel_min = min(red, green, blue)
    brightness = (red + green + blue) / 3
    return channel_min > 170 and brightness > 195 and channel_max - channel_min < 22


def _is_full_frame_skin_pixel(red: int, green: int, blue: int, alpha: int) -> bool:
    if alpha < 140:
        return False
    channel_spread = max(red, green, blue) - min(red, green, blue)
    return (
        red >= 145
        and green >= 115
        and blue >= 75
        and red >= green - 25
        and red >= blue + 15
        and green >= blue - 8
        and channel_spread <= 120
    )


def _anchor_for_face_component(
    image: Image.Image,
    face: dict[str, float],
    dark_components: list[dict[str, float]],
    light_eye_components: list[dict[str, float]],
    components: list[dict[str, float]],
) -> dict[str, dict[str, float]] | None:
    face_width = face["width"]
    face_height = face["height"]
    face_left = face["left"]
    face_right = face["right"]
    face_top = face["top"]
    face_bottom = face["bottom"]
    eye_components = [*dark_components, *light_eye_components]
    eye_candidates = [
        component
        for component in eye_components
        if face_left + face_width * 0.14 <= component["cx"] <= face_right - face_width * 0.14
        and face_top + face_height * 0.12 <= component["cy"] <= face_top + face_height * 0.58
        and 0.018 <= component["width"] / max(face_width, 0.001) <= 0.31
        and 0.012 <= component["height"] / max(face_height, 0.001) <= 0.30
        and component["area"] >= 8
    ]
    valid_pairs: list[tuple[float, dict[str, float], dict[str, float], dict[str, float]]] = []
    if face_top < 0.055 or _full_frame_face_has_busy_forehead(face, dark_components):
        return None
    for left_eye in eye_candidates:
        for right_eye in eye_candidates:
            if left_eye is right_eye or left_eye["cx"] >= right_eye["cx"]:
                continue
            if not _full_frame_eye_pair_is_symmetric(left_eye, right_eye):
                continue
            separation = right_eye["cx"] - left_eye["cx"]
            relative_separation = separation / max(face_width, 0.001)
            if relative_separation < 0.22 or relative_separation > 0.58:
                continue
            y_delta = abs(left_eye["cy"] - right_eye["cy"]) / max(face_height, 0.001)
            if y_delta > 0.12:
                continue
            midpoint = (left_eye["cx"] + right_eye["cx"]) / 2
            eye_y = (left_eye["cy"] + right_eye["cy"]) / 2
            relative_eye_y = (eye_y - face_top) / max(face_height, 0.001)
            if relative_eye_y < 0.25 or relative_eye_y > 0.46:
                continue
            if _full_frame_face_has_busy_upper_expression(face, dark_components, left_eye, right_eye, eye_y):
                continue
            mouth = _mouth_for_face(face, dark_components, midpoint, eye_y)
            eye_shape_score = (
                _eye_component_shape_score(left_eye, face)
                + _eye_component_shape_score(right_eye, face)
            )
            score = (
                -abs(midpoint - face["cx"]) * 0.6
                -abs(relative_separation - 0.36) * 0.4
                -abs(relative_eye_y - 0.34) * 1.5
                -y_delta
                + eye_shape_score
                + min(face["area"] / 10000.0, 0.4)
            )
            valid_pairs.append((score, left_eye, right_eye, mouth))
    if not valid_pairs:
        return None
    _score, left_eye, right_eye, mouth = max(valid_pairs, key=lambda pair: pair[0])
    eye_y = (left_eye["cy"] + right_eye["cy"]) / 2
    brow_y = max(face_top, eye_y - face_height * 0.17)
    left_erase_box = _full_frame_eye_erase_box(left_eye, face)
    right_erase_box = _full_frame_eye_erase_box(right_eye, face)
    skin_fill = _sample_blink_face_skin_fill(
        image,
        {
            "eye_left": {"x": left_eye["cx"], "y": left_eye["cy"]},
            "eye_right": {"x": right_eye["cx"], "y": right_eye["cy"]},
            "mouth": {"x": mouth["cx"], "y": mouth["cy"]},
        },
    )
    left_fill_top, left_fill_bottom, left_fill_left, left_fill_right = _blink_eye_fill_gradient(
        left_erase_box,
        image,
        preferred_fill=skin_fill,
    )
    right_fill_top, right_fill_bottom, right_fill_left, right_fill_right = _blink_eye_fill_gradient(
        right_erase_box,
        image,
        preferred_fill=skin_fill,
    )
    return {
        "eye_left": {
            "x": round(left_eye["cx"], 4),
            "y": round(left_eye["cy"], 4),
            "width": round(left_eye["width"], 4),
            "height": round(left_eye["height"], 4),
            "erase_box": left_erase_box,
            "fill_top": left_fill_top,
            "fill_bottom": left_fill_bottom,
            "fill_left": left_fill_left,
            "fill_right": left_fill_right,
        },
        "eye_right": {
            "x": round(right_eye["cx"], 4),
            "y": round(right_eye["cy"], 4),
            "width": round(right_eye["width"], 4),
            "height": round(right_eye["height"], 4),
            "erase_box": right_erase_box,
            "fill_top": right_fill_top,
            "fill_bottom": right_fill_bottom,
            "fill_left": right_fill_left,
            "fill_right": right_fill_right,
        },
        "mouth": {"x": round(mouth["cx"], 4), "y": round(mouth["cy"], 4)},
        "brow_left": {"x": round(left_eye["cx"], 4), "y": round(brow_y, 4)},
        "brow_right": {"x": round(right_eye["cx"], 4), "y": round(brow_y, 4)},
    }


def _full_frame_face_has_busy_forehead(face: dict[str, float], dark_components: list[dict[str, float]]) -> bool:
    face_width = face["width"]
    face_height = face["height"]
    horizontal_marks = 0
    for component in dark_components:
        if not (
            face["left"] <= component["cx"] <= face["right"]
            and face["top"] <= component["cy"] <= face["bottom"]
        ):
            continue
        relative_y = (component["cy"] - face["top"]) / max(face_height, 0.001)
        relative_width = component["width"] / max(face_width, 0.001)
        aspect = component["width"] / max(component["height"], 0.001)
        if relative_y < 0.29 and aspect >= 4.0 and relative_width >= 0.08:
            horizontal_marks += 1
    return horizontal_marks > 2


def _full_frame_face_has_busy_upper_expression(
    face: dict[str, float],
    dark_components: list[dict[str, float]],
    left_eye: dict[str, float],
    right_eye: dict[str, float],
    eye_y: float,
) -> bool:
    face_width = face["width"]
    face_height = face["height"]
    eye_relative_y = (eye_y - face["top"]) / max(face_height, 0.001)
    horizontal_marks = 0
    for component in dark_components:
        if not (
            face["left"] <= component["cx"] <= face["right"]
            and face["top"] <= component["cy"] <= face["bottom"]
        ):
            continue
        relative_y = (component["cy"] - face["top"]) / max(face_height, 0.001)
        if relative_y >= eye_relative_y - 0.06:
            continue
        near_selected_eye = abs(component["cy"] - eye_y) < face_height * 0.08 and (
            abs(component["cx"] - left_eye["cx"]) < face_width * 0.13
            or abs(component["cx"] - right_eye["cx"]) < face_width * 0.13
        )
        if near_selected_eye:
            continue
        relative_width = component["width"] / max(face_width, 0.001)
        aspect = component["width"] / max(component["height"], 0.001)
        if aspect >= 4.0 and relative_width >= 0.08:
            horizontal_marks += 1
    return horizontal_marks > 2


def _full_frame_eye_pair_is_symmetric(left_eye: dict[str, float], right_eye: dict[str, float]) -> bool:
    width_ratio = min(left_eye["width"], right_eye["width"]) / max(left_eye["width"], right_eye["width"], 0.001)
    height_ratio = min(left_eye["height"], right_eye["height"]) / max(left_eye["height"], right_eye["height"], 0.001)
    area_ratio = min(left_eye["area"], right_eye["area"]) / max(left_eye["area"], right_eye["area"], 1.0)
    return width_ratio >= 0.42 and height_ratio >= 0.42 and area_ratio >= 0.22


def _full_frame_eye_erase_box(eye: dict[str, float], face: dict[str, float]) -> dict[str, float]:
    face_width = face["width"]
    face_height = face["height"]
    pad_x = min(max(eye["width"] * 0.45, face_width * 0.025), face_width * 0.08)
    pad_y = min(max(eye["height"] * 0.12, face_height * 0.018), face_height * 0.04)
    left = max(face["left"], eye["left"] - pad_x)
    right = min(face["right"], eye["right"] + pad_x)
    top = max(face["top"], eye["top"] - pad_y)
    bottom = min(face["bottom"], eye["bottom"] + pad_y)
    max_width = face_width * 0.22
    max_height = face_height * 0.18
    if right - left > max_width:
        center_x = eye["cx"]
        left = max(face["left"], center_x - max_width / 2)
        right = min(face["right"], center_x + max_width / 2)
    if bottom - top > max_height:
        center_y = eye["cy"]
        top = max(face["top"], center_y - max_height / 2)
        bottom = min(face["bottom"], center_y + max_height / 2)
    return {
        "left": round(max(0.0, left), 4),
        "top": round(max(0.0, top), 4),
        "right": round(min(1.0, right), 4),
        "bottom": round(min(1.0, bottom), 4),
    }


def _eye_component_shape_score(component: dict[str, float], face: dict[str, float]) -> float:
    size_score = min(component["area"] / max(face["area"] * 0.008, 1.0), 1.0) * 0.12
    if component.get("kind") == "light_eye":
        return 0.10 + size_score
    aspect = component["height"] / max(component["width"], 0.001)
    if aspect < 0.24:
        return -0.18 + size_score
    if aspect >= 0.45:
        return 0.06 + size_score
    return size_score


def _mouth_for_face(
    face: dict[str, float],
    dark_components: list[dict[str, float]],
    midpoint: float,
    eye_y: float,
) -> dict[str, float]:
    face_width = face["width"]
    face_height = face["height"]
    mouth_candidates = [
        component
        for component in dark_components
        if eye_y + face_height * 0.12 <= component["cy"] <= min(face["bottom"], eye_y + face_height * 0.38)
        and abs(component["cx"] - midpoint) <= face_width * 0.20
        and component["width"] <= face_width * 0.36
        and component["height"] <= face_height * 0.18
    ]
    mouth = max(mouth_candidates, key=lambda component: component["area"], default=None)
    if mouth is not None:
        return mouth
    return {
        "area": 0.0,
        "left": midpoint,
        "top": eye_y + face_height * 0.24,
        "right": midpoint,
        "bottom": eye_y + face_height * 0.24,
        "cx": midpoint,
        "cy": min(face["bottom"], eye_y + face_height * 0.24),
        "width": 0.0,
        "height": 0.0,
    }


def _audit_dir() -> Path:
    return DATA_DIR / "test-lab" / "full-frame-blink-audits"


def _audit_report_path(report_id: str) -> Path:
    if not report_id or "/" in report_id or "\\" in report_id:
        raise ValueError("Invalid blink audit report id.")
    return _audit_dir() / f"{report_id}.json"


def _scene_image_url(script_id: str, scene_id: str, image_url: str) -> str:
    return image_url or f"/static/projects/{script_id}/images/{scene_id}.png"


def image_path_from_static_url(image_url: str) -> Path | None:
    prefix = "/static/projects/"
    if not image_url.startswith(prefix):
        return None
    relative = image_url.removeprefix(prefix)
    path = (DATA_DIR / "projects" / relative).resolve()
    projects_dir = (DATA_DIR / "projects").resolve()
    if not path.is_relative_to(projects_dir):
        return None
    return path
