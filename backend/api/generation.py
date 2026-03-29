"""Endpoints for generation time estimates."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from api.database import get_session
from models.generation_duration import GenerationDuration, GenerationEstimateResponse

ALLOWED_OPERATION_TYPES = {"idea_generation", "script_generation_youtube", "script_generation_shortform"}

router = APIRouter(prefix="/api/generation", tags=["generation"])


@router.get("/estimate", response_model=GenerationEstimateResponse)
def get_estimate(
    operation_type: str = Query(..., description="Operation type to estimate"),
    session: Session = Depends(get_session),
):
    if operation_type not in ALLOWED_OPERATION_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid operation_type. Must be one of: {', '.join(sorted(ALLOWED_OPERATION_TYPES))}")

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
