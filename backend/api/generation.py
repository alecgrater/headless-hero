"""Endpoints for generation time estimates."""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select

from database import get_session
from models.generation_duration import GenerationDuration, GenerationEstimateResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generation", tags=["generation"])


@router.get("/estimate", response_model=GenerationEstimateResponse)
def get_estimate(
    operation_type: str = Query(..., description="Operation type to estimate"),
    scene_count: int | None = Query(None, description="Scale estimate by scene count"),
    session: Session = Depends(get_session),
):
    logger.info("Fetching generation estimate for %s (scene_count=%s)", operation_type, scene_count)

    if scene_count and scene_count > 0:
        rows_with_scenes = select(
            func.avg(GenerationDuration.duration_seconds / GenerationDuration.scene_count),
            func.count(GenerationDuration.id),
        ).where(
            GenerationDuration.operation_type == operation_type,
            GenerationDuration.scene_count.is_not(None),
            GenerationDuration.scene_count > 0,
        )
        result = session.exec(rows_with_scenes).one()
        per_scene_avg, per_scene_count = result
        if per_scene_avg is not None and per_scene_count > 0:
            scaled = round(per_scene_avg * scene_count, 1)
            return GenerationEstimateResponse(
                operation_type=operation_type,
                average_seconds=scaled,
                sample_count=per_scene_count,
            )

    statement = select(
        func.avg(GenerationDuration.duration_seconds),
        func.count(GenerationDuration.id),
    ).where(GenerationDuration.operation_type == operation_type)

    result = session.exec(statement).one()
    avg_seconds, count = result

    return GenerationEstimateResponse(
        operation_type=operation_type,
        average_seconds=round(avg_seconds, 1) if avg_seconds is not None else None,
        sample_count=count,
    )


class RecordDurationRequest(BaseModel):
    operation_type: str
    duration_seconds: float
    scene_count: int | None = None


class RecordDurationResponse(BaseModel):
    recorded: bool


@router.post("/record-duration", response_model=RecordDurationResponse)
def record_duration(body: RecordDurationRequest, session: Session = Depends(get_session)):
    """Record a generation duration from the frontend (for frontend-driven batch operations)."""
    logger.info("Recording duration: %s = %.1fs (scenes=%s)", body.operation_type, body.duration_seconds, body.scene_count)
    record = GenerationDuration(
        operation_type=body.operation_type,
        duration_seconds=body.duration_seconds,
        scene_count=body.scene_count,
    )
    session.add(record)
    session.commit()
    return RecordDurationResponse(recorded=True)
