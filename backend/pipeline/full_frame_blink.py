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
    BlinkRegistrationError,
    _blink_overlay_anchor_metadata,
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
            anchor = _blink_overlay_anchor_metadata(image.convert("RGBA"), require_detected=True)
    except OSError:
        return FullFrameBlinkDetection(status="failed", eligible=False, reason="image_unreadable")
    except BlinkRegistrationError as exc:
        return FullFrameBlinkDetection(status="failed", eligible=False, reason=_stable_detection_reason(str(exc)))
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


def _stable_detection_reason(message: str) -> str:
    text = message.casefold()
    if "facial landmarks" in text:
        return "face_landmarks_missing"
    if "no visible subject" in text:
        return "subject_missing"
    if "centered chest-up" in text:
        return "face_framing_unsafe"
    return "detector_rejected"


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
