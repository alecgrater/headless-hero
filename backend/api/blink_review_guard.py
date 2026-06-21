"""Shared API guard for project Blink Review completion."""

from fastapi import HTTPException

from models.script import Script
from pipeline.project_blink_review import BlinkReviewRequiredError, ensure_project_blink_review_complete_for_script


def require_blink_review_complete_for_script(record: Script) -> None:
    try:
        ensure_project_blink_review_complete_for_script(record)
    except BlinkReviewRequiredError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
            headers={"X-Headless-Hero-Error-Code": "blink_review_required"},
        ) from exc
