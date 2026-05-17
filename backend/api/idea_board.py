"""Idea board CRUD + cold-open hook generation endpoints."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlmodel import Session, col, func, select

from database import get_session
from models.idea import VALID_SOURCES, VALID_STATUSES, Idea
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ideas"])


def _hook_refinement_enabled() -> bool:
    return os.environ.get("HOOK_REFINEMENT_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


class CreateIdeaRequest(BaseModel):
    text: str
    rank: int = 50
    source: str = "manual"
    description: str = ""
    category: str = ""

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}")
        return v


class UpdateIdeaRequest(BaseModel):
    text: str | None = None
    rank: int | None = None
    status: str | None = None
    description: str | None = None
    category: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class SelectColdOpenRequest(BaseModel):
    index: int


def _start_cold_open_generation(idea_id: str) -> str:
    """Start a background job to generate cold opens for an idea."""
    job = create_job()

    def _run() -> list[str]:
        from database import engine
        from sqlmodel import Session as SyncSession

        with SyncSession(engine) as session:
            idea = session.get(Idea, idea_id)
            if not idea:
                raise RuntimeError(f"Idea {idea_id} not found")

            topic = idea.text
            description = idea.description
            idea.cold_open_status = "generating"
            idea.cold_open_job_id = job.id
            session.add(idea)
            session.commit()

        update_job(job.id, current_step="Generating cold opens...")

        from pipeline.cold_open import generate_cold_opens

        result = generate_cold_opens(
            topic=topic,
            description=description,
        )

        with SyncSession(engine) as session:
            idea = session.get(Idea, idea_id)
            if not idea:
                raise RuntimeError(f"Idea {idea_id} not found after generation")
            idea.cold_open_variants_json = result.model_dump_json()
            idea.cold_open_status = "ready"
            session.add(idea)
            session.commit()

        return []

    def _run_with_failure_handling() -> list[str]:
        try:
            return _run()
        except Exception:
            from database import engine
            from sqlmodel import Session as SyncSession

            with SyncSession(engine) as session:
                idea = session.get(Idea, idea_id)
                if idea:
                    idea.cold_open_status = "failed"
                    session.add(idea)
                    session.commit()
            raise

    run_in_background(job.id, _run_with_failure_handling)
    return job.id


def _start_hook_scoring(idea_id: str, variant_index: int) -> str:
    """Start a background job to score and optionally refine a selected cold open."""
    job = create_job()

    def _run() -> list[str]:
        from database import engine
        from sqlmodel import Session as SyncSession

        with SyncSession(engine) as session:
            idea = session.get(Idea, idea_id)
            if not idea:
                raise RuntimeError(f"Idea {idea_id} not found")

            from models.cold_open import ColdOpenResult

            cold_open_result = ColdOpenResult.model_validate_json(idea.cold_open_variants_json)
            if variant_index < 0 or variant_index >= len(cold_open_result.variants):
                raise ValueError(f"Invalid variant index {variant_index}")

            variant = cold_open_result.variants[variant_index]
            video_title = idea.text

            idea.cold_open_status = "refining"
            session.add(idea)
            session.commit()

        update_job(job.id, current_step="Scoring hook...")

        from pipeline.hook_scorer import score_hook

        hook_score = score_hook(
            intro_hook=variant.intro_hook,
            hook_scenes=[],
            video_title=video_title,
            narration_text=variant.opening_narration,
        )

        selected_hook_json = variant.model_dump_json(
            include={"intro_hook", "opening_narration"},
        )
        if _hook_refinement_enabled():
            update_job(job.id, current_step="Refining hook...")

            from pipeline.hook_refiner import refine_hook

            refined = refine_hook(
                intro_hook=variant.intro_hook,
                opening_narration=variant.opening_narration,
                hook_score=hook_score,
                video_title=video_title,
            )
            selected_hook_json = refined.model_dump_json()

        with SyncSession(engine) as session:
            idea = session.get(Idea, idea_id)
            if not idea:
                raise RuntimeError(f"Idea {idea_id} not found after scoring")
            idea.selected_hook_json = selected_hook_json
            idea.hook_score = hook_score.overall
            idea.hook_score_json = hook_score.model_dump_json()
            idea.cold_open_status = "scored"
            session.add(idea)
            session.commit()

        return []

    def _run_with_failure_handling() -> list[str]:
        try:
            return _run()
        except Exception:
            from database import engine
            from sqlmodel import Session as SyncSession

            with SyncSession(engine) as session:
                idea = session.get(Idea, idea_id)
                if idea:
                    idea.cold_open_status = "failed"
                    session.add(idea)
                    session.commit()
            raise

    run_in_background(job.id, _run_with_failure_handling)
    return job.id


@router.get("/idea-board")
def list_ideas(
    sort: str = Query("hook_score", pattern="^(hook_score|rank|newest)$"),
    category: str | None = Query(None),
    status: str | None = Query(None),
    session: Session = Depends(get_session),
) -> list[Idea]:
    stmt = select(Idea)
    if category:
        stmt = stmt.where(Idea.category == category)
    if status:
        stmt = stmt.where(Idea.status == status)

    if sort == "hook_score":
        stmt = stmt.order_by(
            col(Idea.hook_score).is_(None).asc(),
            col(Idea.hook_score).desc(),
            col(Idea.rank).desc(),
        )
    elif sort == "rank":
        stmt = stmt.order_by(col(Idea.rank).desc(), col(Idea.created_at).desc())
    else:
        stmt = stmt.order_by(col(Idea.created_at).desc())

    return list(session.exec(stmt).all())


@router.get("/idea-board/counts")
def idea_counts(session: Session = Depends(get_session)) -> dict[str, int]:
    rows = session.exec(
        select(Idea.status, func.count()).group_by(Idea.status)
    ).all()
    counts = {s: 0 for s in VALID_STATUSES}
    for status, count in rows:
        counts[status] = count
    return counts


@router.get("/idea-board/categories")
def idea_categories(session: Session = Depends(get_session)) -> list[str]:
    rows = session.exec(
        select(Idea.category).where(Idea.category != "").distinct()
    ).all()
    return sorted(rows)


@router.post("/idea-board", status_code=201)
def create_idea(body: CreateIdeaRequest, session: Session = Depends(get_session)) -> Idea:
    idea = Idea(
        text=body.text,
        rank=body.rank,
        source=body.source,
        description=body.description,
        category=body.category,
    )
    session.add(idea)
    session.commit()
    session.refresh(idea)

    _start_cold_open_generation(idea.id)

    session.refresh(idea)
    return idea


@router.put("/idea-board/{idea_id}")
def update_idea(idea_id: str, body: UpdateIdeaRequest, session: Session = Depends(get_session)) -> Idea:
    idea = session.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    if body.text is not None:
        idea.text = body.text
    if body.rank is not None:
        idea.rank = body.rank
    if body.status is not None:
        idea.status = body.status
    if body.description is not None:
        idea.description = body.description
    if body.category is not None:
        idea.category = body.category
    session.add(idea)
    session.commit()
    session.refresh(idea)
    return idea


@router.delete("/idea-board/{idea_id}", status_code=204)
def delete_idea(idea_id: str, session: Session = Depends(get_session)) -> None:
    idea = session.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    session.delete(idea)
    session.commit()


@router.get("/idea-board/{idea_id}/cold-open-status")
def cold_open_status(idea_id: str, session: Session = Depends(get_session)) -> dict:
    idea = session.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    result: dict = {
        "cold_open_status": idea.cold_open_status,
        "hook_score": idea.hook_score,
    }

    if idea.cold_open_variants_json:
        result["cold_open_variants_json"] = idea.cold_open_variants_json
    if idea.selected_hook_json:
        result["selected_hook_json"] = idea.selected_hook_json
    if idea.hook_score_json:
        result["hook_score_json"] = idea.hook_score_json

    if idea.cold_open_job_id:
        job = get_job(idea.cold_open_job_id)
        if job:
            result["job_status"] = job.status
            result["job_error"] = job.error

    return result


@router.post("/idea-board/{idea_id}/select-cold-open")
def select_cold_open(
    idea_id: str,
    body: SelectColdOpenRequest,
    session: Session = Depends(get_session),
) -> dict:
    idea = session.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    if idea.cold_open_status not in ("ready", "scored", "failed"):
        raise HTTPException(status_code=400, detail=f"Cannot select cold open in status '{idea.cold_open_status}'")

    job_id = _start_hook_scoring(idea_id, body.index)
    return {"job_id": job_id, "cold_open_status": "refining"}


@router.post("/idea-board/{idea_id}/retry-cold-open")
def retry_cold_open(idea_id: str, session: Session = Depends(get_session)) -> dict:
    idea = session.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    idea.cold_open_status = "pending"
    idea.cold_open_variants_json = ""
    idea.selected_hook_json = ""
    idea.hook_score = None
    idea.hook_score_json = ""
    session.add(idea)
    session.commit()

    job_id = _start_cold_open_generation(idea_id)
    return {"job_id": job_id, "cold_open_status": "generating"}
