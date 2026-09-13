"""Endpoints for generation time estimates."""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select

from database import get_session
from models.generation_duration import (
    LOCAL_BASELINE_SECONDS,
    GenerationDuration,
    GenerationEstimateResponse,
    engine_for_operation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generation", tags=["generation"])


@router.get("/estimate", response_model=GenerationEstimateResponse)
def get_estimate(
    operation_type: str = Query(..., description="Operation type to estimate"),
    scene_count: int | None = Query(None, description="Scale estimate by scene count"),
    session: Session = Depends(get_session),
):
    engine = engine_for_operation(operation_type)
    logger.info(
        "Fetching generation estimate for %s (scene_count=%s, engine=%s)",
        operation_type, scene_count, engine or "any",
    )

    # Only this engine's samples. A two-minute Claude script and a
    # ninety-five-minute local one average into an ETA that is wrong for both,
    # and the pooled average never converges because it depends on how often
    # the user switches. An engine-independent operation has engine == "" and
    # pools across every row, as before.
    def _scoped(statement):
        statement = statement.where(GenerationDuration.operation_type == operation_type)
        if engine:
            statement = statement.where(GenerationDuration.engine == engine)
        return statement

    if scene_count and scene_count > 0:
        rows_with_scenes = _scoped(select(
            func.avg(GenerationDuration.duration_seconds / GenerationDuration.scene_count),
            func.count(GenerationDuration.id),
        )).where(
            GenerationDuration.scene_count.is_not(None),
            GenerationDuration.scene_count > 0,
        )
        per_scene_avg, per_scene_count = session.exec(rows_with_scenes).one()
        if per_scene_avg is not None and per_scene_count > 0:
            return GenerationEstimateResponse(
                operation_type=operation_type,
                average_seconds=round(per_scene_avg * scene_count, 1),
                sample_count=per_scene_count,
                engine=engine,
            )

    avg_seconds, count = session.exec(_scoped(select(
        func.avg(GenerationDuration.duration_seconds),
        func.count(GenerationDuration.id),
    ))).one()

    if avg_seconds is not None and count > 0:
        return GenerationEstimateResponse(
            operation_type=operation_type,
            average_seconds=round(avg_seconds, 1),
            sample_count=count,
            engine=engine,
        )

    # No sample for this engine yet. For a local engine that is the *first* run,
    # and it is the one where the user most needs a number — an unannounced
    # ninety-minute wait is the worst case. Fall back to the published baseline
    # rather than to the cloud average, which would be wrong by more than an
    # order of magnitude in the dangerous direction.
    if engine.startswith("local:") or engine.startswith("ollama:"):
        baseline = LOCAL_BASELINE_SECONDS.get(operation_type)
        if baseline is not None:
            return GenerationEstimateResponse(
                operation_type=operation_type,
                average_seconds=baseline,
                sample_count=0,
                engine=engine,
                source="baseline",
            )

    # Last resort: the cross-engine average. Reached by an install upgrading
    # into engine scoping, whose entire history predates the column and is
    # therefore of an unknown configuration. Better a labelled approximation
    # than silently dropping to an indeterminate bar for every operation until
    # each has been run once again.
    pooled_avg, pooled_count = session.exec(select(
        func.avg(GenerationDuration.duration_seconds),
        func.count(GenerationDuration.id),
    ).where(GenerationDuration.operation_type == operation_type)).one()
    if pooled_avg is not None and pooled_count > 0:
        return GenerationEstimateResponse(
            operation_type=operation_type,
            average_seconds=round(pooled_avg, 1),
            sample_count=pooled_count,
            engine=engine,
            source="pooled",
        )

    return GenerationEstimateResponse(
        operation_type=operation_type,
        average_seconds=None,
        sample_count=0,
        engine=engine,
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
