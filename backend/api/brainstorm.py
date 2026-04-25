"""Brainstorm recommendation endpoints."""

import logging

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from database import get_session
from models.script import Script
from models.trending import TrendingTopic
from pipeline.brainstorm import generate_brainstorm_recommendations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["brainstorm"])


@router.post("/brainstorm/generate")
def generate_brainstorm(session: Session = Depends(get_session)):
    scripts = session.exec(select(Script)).all()
    script_titles = [s.topic_title for s in scripts if s.topic_title]

    trending_stmt = (
        select(TrendingTopic)
        .where(TrendingTopic.status == "new")
        .order_by(TrendingTopic.score.desc())  # type: ignore[union-attr]
        .limit(20)
    )
    topics = session.exec(trending_stmt).all()
    trending_data = [{"title": t.title, "score": t.score} for t in topics]

    recommendations = generate_brainstorm_recommendations(
        script_titles=script_titles,
        trending_topics=trending_data,
    )

    return {
        "recommendations": recommendations,
        "stats": {
            "script_count": len(script_titles),
            "topic_count": len(trending_data),
        },
    }
