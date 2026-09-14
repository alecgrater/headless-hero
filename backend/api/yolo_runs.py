"""YOLO run history endpoints.

The browser drives the YOLO pipeline and owns its run state; these endpoints
give it a durable home so a run that failed while nobody was watching can still
be explained after the fact. See `pipeline.yolo_runs` for the storage rules.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_session
from models.script import Script
from pipeline.yolo_runs import YoloRunRecord, load_runs, save_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/yolo", tags=["yolo"])


class YoloRunLogLine(BaseModel):
    """The one dev-dashboard line this transition should emit."""

    level: Literal["info", "warning", "error"] = "info"
    message: str = Field(min_length=1, max_length=500)


class SaveYoloRunRequest(BaseModel):
    run: YoloRunRecord
    log: YoloRunLogLine | None = None


class SaveYoloRunResponse(BaseModel):
    run: YoloRunRecord


class YoloRunListResponse(BaseModel):
    runs: list[YoloRunRecord]


def _require_script(script_id: str, session: Session) -> Script:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")
    return script


@router.get("/runs/{script_id}", response_model=YoloRunListResponse)
def list_yolo_runs(script_id: str, session: Session = Depends(get_session)) -> YoloRunListResponse:
    _require_script(script_id, session)
    try:
        return YoloRunListResponse(runs=load_runs(script_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/runs/{script_id}", response_model=SaveYoloRunResponse)
def save_yolo_run(
    script_id: str,
    request: SaveYoloRunRequest,
    session: Session = Depends(get_session),
) -> SaveYoloRunResponse:
    _require_script(script_id, session)
    if request.run.script_id != script_id:
        raise HTTPException(status_code=400, detail="run.script_id does not match the path script_id")

    try:
        save_run(script_id, request.run)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not save YOLO run history: {exc}") from exc

    if request.log is not None:
        log_at = {
            "info": logger.info,
            "warning": logger.warning,
            "error": logger.error,
        }[request.log.level]
        log_at("YOLO [%s] %s", script_id, request.log.message)

    return SaveYoloRunResponse(run=request.run)
