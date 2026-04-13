"""Trending topic discovery endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session, get_default_brand_id
from models.trending import TrendingTopic
from pipeline.trending_scorer import start_refresh, get_refresh_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trending", tags=["trending"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class UpdateStatusRequest(BaseModel):
    status: str  # "dismissed" | "used"


class GenerateIdeasRequest(BaseModel):
    topic_id: str


class TrendingTopicRead(BaseModel):
    id: str
    title: str
    source: str
    score: float
    score_breakdown: dict
    format_fit_rationale: str
    fetched_at: str
    status: str
    is_breakout: bool
    is_first_mover: bool
    evidence_snippet: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/refresh")
async def refresh_trending():
    """Start a background trending topic refresh job."""
    job = start_refresh()
    return {"job_id": job.id}


@router.get("/refresh-status/{job_id}")
async def refresh_status(job_id: str):
    """Get status of a trending refresh job."""
    job = get_refresh_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.get("/topics", response_model=list[TrendingTopicRead])
async def get_topics(
    status: str | None = None,
    session: Session = Depends(get_session),
):
    """Get trending topics, sorted by score descending."""
    stmt = select(TrendingTopic)
    if status:
        stmt = stmt.where(TrendingTopic.status == status)
    stmt = stmt.order_by(TrendingTopic.score.desc())
    topics = session.exec(stmt).all()

    return [
        TrendingTopicRead(
            id=t.id,
            title=t.title,
            source=t.source,
            score=round(t.score, 1),
            score_breakdown=json.loads(t.score_breakdown) if t.score_breakdown else {},
            format_fit_rationale=t.format_fit_rationale,
            fetched_at=t.fetched_at.isoformat(),
            status=t.status,
            is_breakout=t.is_breakout,
            is_first_mover=t.is_first_mover,
            evidence_snippet=t.evidence_snippet,
        )
        for t in topics
    ]


@router.patch("/topics/{topic_id}/status")
async def update_topic_status(
    topic_id: str,
    body: UpdateStatusRequest,
    session: Session = Depends(get_session),
):
    """Update a topic's status (dismiss or mark as used)."""
    topic = session.get(TrendingTopic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if body.status not in ("dismissed", "used"):
        raise HTTPException(status_code=422, detail="Status must be 'dismissed' or 'used'")
    topic.status = body.status
    session.add(topic)
    session.commit()
    return {"status": "ok"}


@router.post("/generate-ideas")
async def generate_ideas_from_topic(
    body: GenerateIdeasRequest,
    session: Session = Depends(get_session),
):
    """Generate video ideas from a trending topic, then mark it as used."""
    topic = session.get(TrendingTopic, body.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Build enriched niche string with context
    niche_parts = [topic.title]
    if topic.evidence_snippet:
        niche_parts.append(f"(Trending context: {topic.evidence_snippet})")
    if topic.format_fit_rationale:
        niche_parts.append(f"(Format fit: {topic.format_fit_rationale})")
    enriched_niche = " ".join(niche_parts)

    # Generate ideas using existing pipeline
    from pipeline.ideation import generate_ideas

    brand_id = get_default_brand_id(session)
    ideas = generate_ideas(niche=enriched_niche, count=5)

    # Mark topic as used
    topic.status = "used"
    session.add(topic)
    session.commit()

    return {
        "ideas": [idea.model_dump() for idea in ideas],
        "niche": topic.title,
    }
