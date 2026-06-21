from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from models.script import Script, ScriptContent
from pipeline import project_blink_review

router = APIRouter(prefix="/api/blink-review", tags=["blink-review"])


class UpdateBlinkReviewDecisionRequest(BaseModel):
    status: Literal["enabled", "disabled"]


def _load_content(session: Session, script_id: str) -> tuple[Script, ScriptContent]:
    record = session.get(Script, script_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Script not found")
    return record, ScriptContent.model_validate_json(record.script_json)


@router.get("/{script_id}")
def get_blink_review(script_id: str, session: Session = Depends(get_session)):
    record, content = _load_content(session, script_id)
    summary = project_blink_review.refresh_project_blink_review(content, script_id)
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    return summary.model_dump(mode="json")


@router.post("/{script_id}/scenes/{scene_id}")
def update_blink_review_decision(
    script_id: str,
    scene_id: str,
    request: UpdateBlinkReviewDecisionRequest,
    session: Session = Depends(get_session),
):
    record, content = _load_content(session, script_id)
    try:
        summary = project_blink_review.set_project_blink_review_decision(content, script_id, scene_id, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()
    return summary.model_dump(mode="json")
