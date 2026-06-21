"""Full-frame blink audit and eligibility helpers."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

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

BURGER_KING_BLINK_AUDIT_SCRIPT_ID = "9dacedc774514306ae1acb85215449e1"
MEDIA_BACKED_BLINK_MODES = {"full_frame", "multi_frame", "continuous", "captions"}


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
    blink_enabled: bool = False


class FullFrameBlinkAuditReport(BaseModel):
    id: str
    script_id: str
    title: str
    created_at: str
    candidates: list[FullFrameBlinkCandidate] = Field(default_factory=list)


def deterministic_blink_enabled(script_id: str, scene_id: str) -> bool:
    digest = hashlib.sha256(f"{script_id}:{scene_id}".encode("utf-8")).digest()
    return digest[0] < 128


def detect_full_frame_blink_anchor(image_path: Path) -> FullFrameBlinkDetection:
    if not image_path.exists() or not image_path.is_file():
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="image_missing")
    try:
        with Image.open(image_path) as image:
            rgba = image.convert("RGBA")
            detected = _detect_full_frame_main_face_anchor_points(_full_frame_detection_image(rgba))
            if detected is None:
                return FullFrameBlinkDetection(status="failed", eligible=False, reason="face_landmarks_missing")
            skin_fill = _sample_blink_face_skin_fill(rgba, detected)
            anchor = {
                "version": 1,
                "detected": True,
                "coordinate_space": "normalized_image",
                **({"skin_fill": skin_fill} if skin_fill else {}),
                "eye_left": dict(detected["eye_left"]),
                "eye_right": dict(detected["eye_right"]),
                "mouth": dict(detected["mouth"]),
                "brow_left": dict(detected["brow_left"]),
                "brow_right": dict(detected["brow_right"]),
            }
    except OSError:
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="image_unreadable")
    if not _anchor_is_full_frame_eligible(anchor):
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="anchor_not_full_frame_safe")
    return FullFrameBlinkDetection(status="passed", eligible=True, anchor=anchor)


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
    for segment in content.segments:
        for scene in segment.scenes:
            if scene.is_title_card or scene.visual_mode not in MEDIA_BACKED_BLINK_MODES:
                continue
            image_url = _scene_image_url(script.id, scene.id, scene.image_url)
            image_path = _image_path_from_url(image_url)
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
                    blink_enabled=detection.eligible and deterministic_blink_enabled(script.id, scene.id),
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
    required = ("eye_left", "eye_right", "mouth", "brow_left", "brow_right")
    if anchor.get("detected") is not True:
        return False
    for key in required:
        point = anchor.get(key)
        if not isinstance(point, dict):
            return False
        if not isinstance(point.get("x"), int | float) or not isinstance(point.get("y"), int | float):
            return False
    return isinstance(anchor.get("skin_fill"), str)


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
    max_width = face_width * 0.46
    max_height = face_height * 0.36
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


def _image_path_from_url(image_url: str) -> Path | None:
    prefix = "/static/projects/"
    if not image_url.startswith(prefix):
        return None
    relative = image_url.removeprefix(prefix)
    path = (DATA_DIR / "projects" / relative).resolve()
    projects_dir = (DATA_DIR / "projects").resolve()
    if not path.is_relative_to(projects_dir):
        return None
    return path
