"""Trending topic discovery endpoints."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session, get_default_brand_id
from models.script import Script
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


class ContentProfileRead(BaseModel):
    script_count: int
    common_topics: list[str]
    narration_style: str
    visual_approach: str
    typical_keywords: list[str]
    audience_profile: str
    avg_segment_count: float
    analyzed_at: str
    is_stale: bool


class SmartIdea(BaseModel):
    title: str
    description: str
    segments_est: int
    keywords: list[str]
    trending_source: str
    style_match_score: float | None = None
    reasoning: str
    angle: str
    signals: list[str] = []


class SmartIdeasResponse(BaseModel):
    ideas: list[SmartIdea]
    profile_used: bool
    trending_topics_used: int


class SmartIdeasRequest(BaseModel):
    count: int = 10


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/refresh")
async def refresh_trending():
    """Start a background trending topic refresh job."""
    logger.info("Starting trending topic refresh")
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
    logger.info("Generating ideas from trending topic %r (topic_id=%s)", topic.title, body.topic_id)
    ideas = generate_ideas(niche=enriched_niche, count=5)

    # Mark topic as used
    topic.status = "used"
    session.add(topic)
    session.commit()

    return {
        "ideas": [idea.model_dump() for idea in ideas],
        "niche": topic.title,
    }


# ---------------------------------------------------------------------------
# Content profile endpoints
# ---------------------------------------------------------------------------

@router.get("/content-profile", response_model=ContentProfileRead | None)
async def get_content_profile():
    """Return cached content profile with staleness flag. No Claude call."""
    from pipeline.content_profile import get_cached_profile
    profile = get_cached_profile()
    if not profile:
        return None
    return ContentProfileRead(**profile)


@router.post("/content-profile/refresh", response_model=ContentProfileRead)
async def refresh_content_profile():
    """Force-regenerate content profile via Claude. Returns updated profile."""
    from pipeline.content_profile import analyze_content_profile
    profile = analyze_content_profile()
    if not profile:
        raise HTTPException(status_code=422, detail="No scripts found to analyze")
    return ContentProfileRead(**profile)


# ---------------------------------------------------------------------------
# Smart ideas endpoint
# ---------------------------------------------------------------------------

@router.post("/smart-ideas", response_model=SmartIdeasResponse)
async def generate_smart_ideas(
    body: SmartIdeasRequest,
    session: Session = Depends(get_session),
):
    """Generate video ideas combining trending topics with optional content profile."""
    from pipeline.content_profile import get_cached_profile, analyze_content_profile
    from pipeline.smart_ideation import generate_smart_ideas as _generate

    # Try to load profile — but don't require it
    profile = None
    script_titles: list[str] = []

    cached = get_cached_profile()
    if cached and cached.get("script_count", 0) >= 3:
        if cached.get("is_stale"):
            profile = analyze_content_profile() or None
        else:
            profile = cached
    else:
        # No profile or not enough scripts — fall back to titles
        scripts = session.exec(select(Script)).all()
        script_titles = [s.topic_title for s in scripts if s.topic_title]

    # Load top trending topics
    stmt = select(TrendingTopic).where(
        TrendingTopic.status == "new"
    ).order_by(TrendingTopic.score.desc()).limit(20)
    topics = session.exec(stmt).all()

    trending_data = [
        {
            "title": t.title,
            "source": t.source,
            "score": t.score,
            "evidence": t.evidence_snippet,
            "is_breakout": t.is_breakout,
        }
        for t in topics
    ]

    ideas = _generate(
        trending_topics=trending_data,
        count=body.count,
        profile=profile,
        script_titles=script_titles if not profile else None,
    )

    return SmartIdeasResponse(
        ideas=[SmartIdea(**idea) for idea in ideas],
        profile_used=profile is not None,
        trending_topics_used=len(trending_data),
    )
