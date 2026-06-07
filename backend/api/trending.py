"""Trending topic discovery endpoints."""

import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from database import engine, get_session, get_default_brand_id
from integrations.github_contents import upload_json_file
from models.script import Script
from models.settings import AppSetting
from models.trending import TrendingTopic
from pipeline.content_profile_snapshot import build_content_profile_input_snapshot
from pipeline.discovery_seed import build_discovery_seed
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job
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


class SeedUploadStatus(BaseModel):
    status: str
    message: str
    commit_sha: str | None = None


class ContentProfileRefreshResponse(ContentProfileRead):
    profile_input_upload: SeedUploadStatus
    seed_upload: SeedUploadStatus


class SmartIdea(BaseModel):
    category: str = "Other"
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
    categories: list[str] = []
    profile_used: bool
    trending_topics_used: int
    refresh_triggered: bool = False
    refresh_job_id: str | None = None
    trending_age_hours: float | None = None


class SmartIdeasRequest(BaseModel):
    count: int = Field(default=40, ge=1, le=100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_setting_or_env(key: str) -> str:
    with Session(engine) as session:
        setting = session.get(AppSetting, key)
        if setting and setting.value:
            return setting.value
    return os.environ.get(key, "")


def _missing_token_status(message: str) -> SeedUploadStatus:
    return SeedUploadStatus(status="skipped", message=message)


def _upload_json_artifact(
    *,
    token: str,
    path: str,
    content: dict,
    message: str,
    success_message: str,
    warning_context: str,
) -> SeedUploadStatus:
    try:
        result = upload_json_file(
            token=token,
            path=path,
            content=content,
            message=message,
        )
    except Exception as exc:
        logger.warning("%s upload failed", warning_context, exc_info=True)
        return SeedUploadStatus(status="warning", message=str(exc))
    logger.info("%s uploaded to GitHub commit %s", warning_context, result.get("commit_sha"))
    return SeedUploadStatus(
        status="uploaded",
        message=success_message,
        commit_sha=result.get("commit_sha") or None,
    )


def _upload_content_profile_input(token: str | None = None) -> SeedUploadStatus:
    token = token if token is not None else _get_setting_or_env("GITHUB_CONTENTS_TOKEN").strip()
    if not token:
        return _missing_token_status(
            message="GitHub Contents Token is not configured, so remote discovery refresh was not triggered.",
        )
    try:
        snapshot = build_content_profile_input_snapshot()
    except Exception as exc:
        logger.warning("Content profile input snapshot build failed", exc_info=True)
        return SeedUploadStatus(status="warning", message=str(exc))
    return _upload_json_artifact(
        token=token,
        path="discovery/content-profile-input.json",
        content=snapshot,
        message="Update remote content profile input",
        success_message="Content profile input uploaded; GitHub Actions can refresh the profile on schedule.",
        warning_context="Content profile input",
    )


def _upload_discovery_seed(profile: dict, token: str | None = None) -> SeedUploadStatus:
    token = token if token is not None else _get_setting_or_env("GITHUB_CONTENTS_TOKEN").strip()
    if not token:
        return _missing_token_status(
            message="GitHub Contents Token is not configured, so remote discovery refresh was not triggered.",
        )
    seed = build_discovery_seed(profile)
    return _upload_json_artifact(
        token=token,
        path="discovery/content-profile-seed.json",
        content=seed,
        message="Update discovery content profile seed",
        success_message="Discovery seed uploaded; GitHub Actions will refresh whitespace results.",
        warning_context="Discovery seed",
    )


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
    """Return cached content profile with staleness flag. No LLM call."""
    from pipeline.content_profile import get_cached_profile
    profile = get_cached_profile()
    if not profile:
        return None
    return ContentProfileRead(**profile)


@router.post("/content-profile/refresh", response_model=ContentProfileRefreshResponse)
async def refresh_content_profile():
    """Force-regenerate content profile via the routed LLM provider. Returns updated profile."""
    from pipeline.content_profile import analyze_content_profile
    profile = analyze_content_profile()
    if not profile:
        raise HTTPException(status_code=422, detail="No scripts found to analyze")
    token = _get_setting_or_env("GITHUB_CONTENTS_TOKEN").strip()
    profile_input_status = _upload_content_profile_input(token)
    seed_upload_status = _upload_discovery_seed(profile, token)
    return ContentProfileRefreshResponse(
        **profile,
        profile_input_upload=profile_input_status,
        seed_upload=seed_upload_status,
    )


# ---------------------------------------------------------------------------
# Smart ideas endpoint
# ---------------------------------------------------------------------------

@router.post("/smart-ideas")
async def generate_smart_ideas(
    body: SmartIdeasRequest,
    session: Session = Depends(get_session),
):
    """Start background job to generate video ideas combining trending topics with optional content profile."""
    from pipeline.content_profile import get_cached_profile

    # Check trending topic age — trigger background refresh if stale, but don't block
    latest = session.exec(
        select(TrendingTopic).order_by(TrendingTopic.fetched_at.desc()).limit(1)
    ).first()

    refresh_triggered = False
    refresh_job_id: str | None = None
    trending_age_hours: float | None = None

    if latest:
        age = datetime.now(timezone.utc) - latest.fetched_at.replace(tzinfo=timezone.utc)
        trending_age_hours = round(age.total_seconds() / 3600, 1)

    needs_refresh = latest is None or (trending_age_hours is not None and trending_age_hours > 24)
    if needs_refresh:
        logger.info("Trending topics stale or missing — starting background refresh")
        refresh_job = start_refresh()
        refresh_triggered = True
        refresh_job_id = refresh_job.id

    # Gather inputs synchronously (fast DB reads)
    scripts = session.exec(select(Script)).all()
    script_titles = [s.topic_title for s in scripts if s.topic_title]

    profile = None
    cached = get_cached_profile()
    if cached and cached.get("script_count", 0) >= 3:
        profile = {k: v for k, v in cached.items() if k != "is_stale"} if cached.get("is_stale") else cached

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

    # Start background job for the slow LLM call
    job = create_job()
    count = body.count

    def _run() -> list[str]:
        from pipeline.content_profile import analyze_content_profile
        from pipeline.smart_ideation import generate_smart_ideas as _generate

        update_job(job.id, current_step="Generating ideas...")

        actual_profile = profile
        if cached and cached.get("is_stale") and cached.get("script_count", 0) >= 3:
            try:
                actual_profile = analyze_content_profile() or None
            except Exception:
                logger.warning("Content profile refresh failed — proceeding without it")

        ideas = _generate(
            trending_topics=trending_data,
            count=count,
            profile=actual_profile,
            script_titles=script_titles or None,
        )

        seen_categories: list[str] = []
        for idea in ideas:
            cat = idea.get("category", "Other")
            if cat not in seen_categories:
                seen_categories.append(cat)

        result = SmartIdeasResponse(
            ideas=[SmartIdea(**idea) for idea in ideas],
            categories=seen_categories,
            profile_used=actual_profile is not None,
            trending_topics_used=len(trending_data),
            refresh_triggered=refresh_triggered,
            refresh_job_id=refresh_job_id,
            trending_age_hours=trending_age_hours,
        )
        update_job(job.id, output_data=result.model_dump_json())
        return []

    run_in_background(job.id, _run)

    return {
        "job_id": job.id,
        "refresh_triggered": refresh_triggered,
        "refresh_job_id": refresh_job_id,
        "trending_age_hours": trending_age_hours,
    }


@router.get("/smart-ideas-status/{job_id}")
async def smart_ideas_status(job_id: str):
    """Get status of a smart ideas generation job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()
