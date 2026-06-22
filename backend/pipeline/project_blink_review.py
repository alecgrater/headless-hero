"""Project-scoped Blink Review state and render/export validation."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from models.script import Scene, Script, ScriptContent
from pipeline import full_frame_blink

BLINK_REVIEW_ENABLED_KEY = "FULL_FRAME_BLINK_REVIEW_ENABLED"
BlinkReviewStatus = Literal["unreviewed", "enabled", "disabled"]


class BlinkReviewCandidate(BaseModel):
    scene_id: str
    scene_label: str
    image_url: str
    eligible: bool
    reason: str = ""
    anchor: dict[str, object] | None = None
    fingerprint: str = ""
    review_status: BlinkReviewStatus | Literal["rejected"] = "rejected"
    enabled: bool = False


class BlinkReviewSummary(BaseModel):
    script_id: str
    candidates: list[BlinkReviewCandidate] = Field(default_factory=list)
    eligible_count: int = 0
    unreviewed_count: int = 0
    enabled_count: int = 0
    disabled_count: int = 0
    complete: bool = True
    review_enabled: bool = True


class BlinkReviewRequiredError(RuntimeError):
    def __init__(self, summary: BlinkReviewSummary):
        self.summary = summary
        super().__init__(
            "Blink Review must be completed before rendering/exporting: "
            f"{summary.unreviewed_count} eligible scene(s) still need review."
        )


def project_blink_review_enabled() -> bool:
    value = os.getenv(BLINK_REVIEW_ENABLED_KEY, "true")
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def blink_metadata_fingerprint(image_url: str, anchor: dict[str, object]) -> str:
    payload = json.dumps({"image_url": image_url, "anchor": anchor}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_unreviewed_full_frame_blink_metadata(script_id: str, scene_id: str, image_url: str) -> dict[str, object] | None:
    if not project_blink_review_enabled():
        return None
    image_path = full_frame_blink.image_path_from_static_url(image_url)
    if image_path is None:
        return None
    detection = full_frame_blink.detect_full_frame_blink_anchor(image_path)
    if not detection.eligible or detection.anchor is None:
        return None
    return {
        "enabled": False,
        "action": "blink",
        "fingerprint": blink_metadata_fingerprint(image_url, detection.anchor),
        "anchor": detection.anchor,
        "review": {"status": "unreviewed"},
    }


def refresh_project_blink_review(content: ScriptContent, script_id: str) -> BlinkReviewSummary:
    if not project_blink_review_enabled():
        _clear_all_blink_metadata(content)
        return BlinkReviewSummary(script_id=script_id, complete=True, review_enabled=False)
    candidates: list[BlinkReviewCandidate] = []
    for scene in content.all_scenes():
        candidate = _refresh_scene(script_id, scene)
        if candidate is not None:
            candidates.append(candidate)
    return _summary(script_id, candidates)


def set_project_blink_review_decision(
    content: ScriptContent,
    script_id: str,
    scene_id: str,
    status: Literal["enabled", "disabled"],
) -> BlinkReviewSummary:
    if not project_blink_review_enabled():
        _clear_all_blink_metadata(content)
        raise ValueError("Blink Review is disabled.")
    scene = next((item for item in content.all_scenes() if item.id == scene_id), None)
    if scene is None:
        raise ValueError(f"Scene not found: {scene_id}")
    blink = _blink_metadata(scene)
    review = blink.get("review") if blink and isinstance(blink.get("review"), dict) else {}
    if not blink or not _blink_metadata_matches_scene(scene, blink):
        refresh_project_blink_review(content, script_id)
        scene = next((item for item in content.all_scenes() if item.id == scene_id), None)
        blink = _blink_metadata(scene) if scene else None
        review = blink.get("review") if blink and isinstance(blink.get("review"), dict) else {}
    if not blink or review.get("status") == "rejected":
        raise ValueError(f"Scene is not eligible for blink review: {scene_id}")
    blink["enabled"] = status == "enabled"
    blink["review"] = {"status": status, "reviewed_at": datetime.now(timezone.utc).isoformat()}
    scene.visual_source_metadata = {**(scene.visual_source_metadata or {}), "full_frame_blink": blink}
    return _summary_from_metadata(content, script_id)


def validate_project_blink_review_complete(content: ScriptContent, script_id: str) -> BlinkReviewSummary:
    summary = refresh_project_blink_review(content, script_id)
    if not summary.complete:
        raise BlinkReviewRequiredError(summary)
    return summary


def ensure_project_blink_review_complete_for_script(record: Script) -> None:
    if not project_blink_review_enabled():
        return
    content = ScriptContent.model_validate_json(record.script_json)
    validate_project_blink_review_complete(content, record.id)


def _refresh_scene(script_id: str, scene: Scene) -> BlinkReviewCandidate | None:
    if scene.is_title_card or scene.visual_mode not in full_frame_blink.MEDIA_BACKED_BLINK_MODES:
        _clear_scene_blink(scene)
        return None
    image_url = scene.image_url or ""
    if not image_url:
        _clear_scene_blink(scene)
        return None
    image_path = full_frame_blink.image_path_from_static_url(image_url)
    if image_path is None:
        _clear_scene_blink(scene)
        return None
    detection = full_frame_blink.detect_full_frame_blink_anchor(image_path)
    if not detection.eligible or detection.anchor is None:
        _set_scene_blink(
            scene,
            {
                "enabled": False,
                "action": "blink",
                "anchor": None,
                "fingerprint": "",
                "review": {"status": "rejected"},
                "reason": detection.reason,
            },
        )
        return BlinkReviewCandidate(
            scene_id=scene.id,
            scene_label=scene.narration[:120],
            image_url=image_url,
            eligible=False,
            reason=detection.reason,
            review_status="rejected",
        )
    fingerprint = blink_metadata_fingerprint(image_url, detection.anchor)
    existing = _blink_metadata(scene)
    existing_review = existing.get("review", {}) if existing and existing.get("fingerprint") == fingerprint else {}
    if not isinstance(existing_review, dict):
        existing_review = {}
    review_status = existing_review.get("status") if existing_review.get("status") in {"enabled", "disabled"} else "unreviewed"
    blink = {
        "enabled": review_status == "enabled",
        "action": "blink",
        "fingerprint": fingerprint,
        "anchor": detection.anchor,
        "review": {
            "status": review_status,
            **({"reviewed_at": existing_review.get("reviewed_at")} if existing_review.get("reviewed_at") else {}),
        },
    }
    _set_scene_blink(scene, blink)
    return BlinkReviewCandidate(
        scene_id=scene.id,
        scene_label=scene.narration[:120],
        image_url=image_url,
        eligible=True,
        anchor=detection.anchor,
        fingerprint=fingerprint,
        review_status=review_status,
        enabled=review_status == "enabled",
    )


def _summary(script_id: str, candidates: list[BlinkReviewCandidate]) -> BlinkReviewSummary:
    eligible = [item for item in candidates if item.eligible]
    unreviewed = [item for item in eligible if item.review_status == "unreviewed"]
    enabled = [item for item in eligible if item.review_status == "enabled"]
    disabled = [item for item in eligible if item.review_status == "disabled"]
    return BlinkReviewSummary(
        script_id=script_id,
        candidates=candidates,
        eligible_count=len(eligible),
        unreviewed_count=len(unreviewed),
        enabled_count=len(enabled),
        disabled_count=len(disabled),
        complete=len(unreviewed) == 0,
        review_enabled=True,
    )


def _summary_from_metadata(content: ScriptContent, script_id: str) -> BlinkReviewSummary:
    candidates = []
    for scene in content.all_scenes():
        candidate = _candidate_from_scene_metadata(scene)
        if candidate is not None:
            candidates.append(candidate)
    return _summary(script_id, candidates)


def _candidate_from_scene_metadata(scene: Scene) -> BlinkReviewCandidate | None:
    if scene.is_title_card or scene.visual_mode not in full_frame_blink.MEDIA_BACKED_BLINK_MODES:
        return None
    blink = _blink_metadata(scene)
    if not blink:
        return None
    review = blink.get("review") if isinstance(blink.get("review"), dict) else {}
    review_status = review.get("status")
    if review_status == "rejected":
        return BlinkReviewCandidate(
            scene_id=scene.id,
            scene_label=scene.narration[:120],
            image_url=scene.image_url or "",
            eligible=False,
            reason=str(blink.get("reason") or ""),
            review_status="rejected",
        )
    if review_status not in {"unreviewed", "enabled", "disabled"}:
        return None
    anchor = blink.get("anchor")
    return BlinkReviewCandidate(
        scene_id=scene.id,
        scene_label=scene.narration[:120],
        image_url=scene.image_url or "",
        eligible=True,
        anchor=anchor if isinstance(anchor, dict) else None,
        fingerprint=str(blink.get("fingerprint") or ""),
        review_status=review_status,
        enabled=review_status == "enabled",
    )


def _blink_metadata(scene: Scene) -> dict[str, object] | None:
    metadata = scene.visual_source_metadata or {}
    blink = metadata.get("full_frame_blink")
    return blink if isinstance(blink, dict) else None


def _blink_metadata_matches_scene(scene: Scene, blink: dict[str, object]) -> bool:
    if scene.is_title_card or scene.visual_mode not in full_frame_blink.MEDIA_BACKED_BLINK_MODES:
        return False
    anchor = blink.get("anchor")
    if not isinstance(anchor, dict):
        return False
    fingerprint = blink.get("fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        return False
    return fingerprint == blink_metadata_fingerprint(scene.image_url or "", anchor)


def _set_scene_blink(scene: Scene, blink: dict[str, object]) -> None:
    scene.visual_source_metadata = {**(scene.visual_source_metadata or {}), "full_frame_blink": blink}


def _clear_scene_blink(scene: Scene) -> None:
    metadata = dict(scene.visual_source_metadata or {})
    metadata.pop("full_frame_blink", None)
    scene.visual_source_metadata = metadata or None


def _clear_all_blink_metadata(content: ScriptContent) -> None:
    for scene in content.all_scenes():
        _clear_scene_blink(scene)
