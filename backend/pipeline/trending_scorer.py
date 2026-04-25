"""Trending topic scoring, deduplication, Claude format-fit, and background job runner."""

import json
import logging
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from thefuzz import fuzz

from config import strip_markdown_fences
from integrations.claude_client import chat
from prompts import FORMAT_FIT_SYSTEM

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background job tracking (mirrors render_jobs.py pattern)
# ---------------------------------------------------------------------------

class TrendingRefreshJob:
    __slots__ = ("id", "status", "progress", "error", "result_count", "sources_status")

    def __init__(self, job_id: str) -> None:
        self.id = job_id
        self.status = "pending"  # pending | running | completed | failed
        self.progress = 0.0
        self.error: str | None = None
        self.result_count = 0
        self.sources_status: dict[str, str] = {
            "youtube": "pending",
            "google_trends": "pending",
            "reddit": "pending",
            "news": "pending",
            "hackernews": "pending",
            "wikipedia": "pending",
            "stackexchange": "pending",
        }

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "progress": round(self.progress, 2),
            "sources": dict(self.sources_status),
            "result_count": self.result_count,
            "error": self.error,
        }


_jobs: dict[str, TrendingRefreshJob] = {}
_lock = threading.Lock()


def create_refresh_job() -> TrendingRefreshJob:
    job = TrendingRefreshJob(uuid.uuid4().hex[:12])
    with _lock:
        _jobs[job.id] = job
    return job


def get_refresh_job(job_id: str) -> TrendingRefreshJob | None:
    with _lock:
        return _jobs.get(job_id)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _deduplicate(topics: list[dict]) -> list[dict]:
    """Merge topics with similar titles using fuzzy matching (ratio >= 85)."""
    if not topics:
        return []

    merged: list[dict] = []
    used = [False] * len(topics)

    for i, topic_a in enumerate(topics):
        if used[i]:
            continue
        group = [topic_a]
        used[i] = True

        for j in range(i + 1, len(topics)):
            if used[j]:
                continue
            if fuzz.ratio(topic_a["title"].lower(), topics[j]["title"].lower()) >= 85:
                group.append(topics[j])
                used[j] = True

        # Merge group: combine sources, keep best scores
        sources = set()
        best_search_velocity = 0.0
        best_competitor_rate = 0.0
        best_reddit_engagement = 0.0
        is_breakout = False
        raw_data_combined: dict[str, list] = {}

        for t in group:
            sources.add(t["source"])
            best_search_velocity = max(best_search_velocity, t.get("search_velocity", 0.0))
            best_competitor_rate = max(best_competitor_rate, t.get("competitor_view_rate", 0.0))
            best_reddit_engagement = max(best_reddit_engagement, t.get("reddit_engagement", 0.0))
            is_breakout = is_breakout or t.get("is_breakout", False)
            src = t["source"]
            if src not in raw_data_combined:
                raw_data_combined[src] = []
            raw_data_combined[src].append(t.get("raw_data", {}))

        # Use the title from the item with the highest individual score
        best_title = max(group, key=lambda t: (
            t.get("search_velocity", 0) +
            t.get("competitor_view_rate", 0) +
            t.get("reddit_engagement", 0)
        ))["title"]

        merged.append({
            "title": best_title,
            "source": ",".join(sorted(sources)),
            "search_velocity": best_search_velocity,
            "competitor_view_rate": best_competitor_rate,
            "reddit_engagement": best_reddit_engagement,
            "is_breakout": is_breakout,
            "raw_data": raw_data_combined,
        })

    logger.info("Deduplication: %d → %d topics", len(topics), len(merged))
    return merged


# ---------------------------------------------------------------------------
# Claude format-fit scoring
# ---------------------------------------------------------------------------


def _score_format_fit(topics: list[dict]) -> dict[str, dict]:
    """Batch-evaluate format fit via Claude. Returns {title: {score, rationale}}."""
    if not topics:
        return {}

    # Batch in groups of 20
    results: dict[str, dict] = {}
    batch_size = 20

    for i in range(0, len(topics), batch_size):
        batch = topics[i:i + batch_size]
        titles_list = [{"title": t["title"]} for t in batch]

        try:
            user_message = f"Rate these {len(batch)} topics:\n{json.dumps(titles_list)}"
            raw = chat(FORMAT_FIT_SYSTEM.template, user_message, max_tokens=2048)
            text = strip_markdown_fences(raw)
            scored = json.loads(text)
            for item in scored:
                title = item.get("title", "")
                results[title] = {
                    "score": float(item.get("score", 50)),
                    "rationale": item.get("rationale", ""),
                }
        except Exception:
            logger.warning("Format-fit scoring failed for batch %d", i // batch_size, exc_info=True)
            for t in batch:
                results[t["title"]] = {"score": 50.0, "rationale": "Scoring unavailable"}

    return results


# ---------------------------------------------------------------------------
# Evidence snippet builder
# ---------------------------------------------------------------------------

def _build_evidence(topic: dict, format_fit: dict) -> str:
    """Build a human-readable evidence snippet."""
    parts = []
    sv = topic.get("search_velocity", 0)
    cr = topic.get("competitor_view_rate", 0)
    re_ = topic.get("reddit_engagement", 0)

    if sv > 0:
        raw = topic.get("raw_data", {})
        gt_data = raw.get("google_trends", [{}])
        rise_pct = None
        if isinstance(gt_data, list):
            for d in gt_data:
                if isinstance(d, dict) and "rise_percentage" in d:
                    rise_pct = d["rise_percentage"]
                    break
        if rise_pct:
            parts.append(f"↑ {rise_pct:.0f}% on Google Trends")
        else:
            parts.append(f"Search velocity: {sv:.0f}/100")

    if cr > 0:
        parts.append(f"Competitor velocity: {cr:.0f}/100")

    if re_ > 0:
        reddit_data = topic.get("raw_data", {}).get("reddit", [])
        if isinstance(reddit_data, list) and reddit_data:
            total_upvotes = sum(d.get("upvotes", 0) for d in reddit_data if isinstance(d, dict))
            parts.append(f"{len(reddit_data)} Reddit posts ({total_upvotes:,} upvotes)")
        else:
            parts.append(f"Reddit engagement: {re_:.0f}/100")

    fit_score = format_fit.get("score", 0)
    if fit_score > 0:
        parts.append(f"Format fit: {fit_score:.0f}/100")

    return " · ".join(parts) if parts else "No trend signals"


# ---------------------------------------------------------------------------
# Final scoring
# ---------------------------------------------------------------------------

def _calculate_final_score(
    topic: dict,
    format_fit_score: float,
    is_saturated: bool,
) -> tuple[float, bool]:
    """Calculate final score and first-mover status. Returns (score, is_first_mover)."""
    sv = topic.get("search_velocity", 0.0)
    cr = topic.get("competitor_view_rate", 0.0)
    re_ = topic.get("reddit_engagement", 0.0)

    score = (
        sv * 0.35 +
        cr * 0.30 +
        re_ * 0.20 +
        format_fit_score * 0.15
    )

    # Saturation penalty
    if is_saturated:
        score -= 15

    # First mover bonus: trending on Reddit/Trends but NOT saturated on YouTube
    has_trend_signal = sv > 30 or re_ > 30
    is_first_mover = has_trend_signal and not is_saturated
    if is_first_mover:
        score += 10

    return max(0, min(100, score)), is_first_mover


# ---------------------------------------------------------------------------
# Main refresh pipeline
# ---------------------------------------------------------------------------

def _run_refresh(job: TrendingRefreshJob) -> None:
    """Fetch from all sources, deduplicate, score, and persist."""
    from pipeline.trending_youtube import fetch_youtube_topics, check_saturation, _get_youtube_client
    from pipeline.trending_reddit import fetch_reddit_topics
    from pipeline.trending_pytrends import fetch_google_trends_topics
    from pipeline.trending_news import fetch_news_topics
    from pipeline.trending_hackernews import fetch_hackernews_topics
    from pipeline.trending_wikipedia import fetch_wikipedia_topics
    from pipeline.trending_stackexchange import fetch_stackexchange_topics

    job.status = "running"
    all_topics: list[dict] = []
    source_count = 7
    completed = 0

    # Fetch from all 7 sources in parallel
    fetchers = {
        "youtube": fetch_youtube_topics,
        "reddit": fetch_reddit_topics,
        "google_trends": fetch_google_trends_topics,
        "news": fetch_news_topics,
        "hackernews": fetch_hackernews_topics,
        "wikipedia": fetch_wikipedia_topics,
        "stackexchange": fetch_stackexchange_topics,
    }

    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {}
        for name, fn in fetchers.items():
            job.sources_status[name] = "running"
            futures[executor.submit(fn)] = name

        for future in as_completed(futures):
            name = futures[future]
            try:
                results = future.result()
                all_topics.extend(results)
                job.sources_status[name] = "done"
            except Exception:
                logger.warning("Source %s failed", name, exc_info=True)
                job.sources_status[name] = "failed"
            completed += 1
            job.progress = completed / (source_count + 2)  # +2 for dedup and scoring steps

    if not all_topics:
        job.status = "completed"
        job.progress = 1.0
        job.result_count = 0
        return

    # Deduplicate
    merged = _deduplicate(all_topics)
    job.progress = (source_count + 1) / (source_count + 2)

    # Format-fit scoring via Claude
    format_fits = _score_format_fit(merged)

    # Saturation checking (sample top candidates, not all)
    youtube = _get_youtube_client()
    saturation_cache: dict[str, bool] = {}
    if youtube:
        # Only check top 20 by preliminary score
        prelim_scored = sorted(merged, key=lambda t: (
            t.get("search_velocity", 0) * 0.35 +
            t.get("competitor_view_rate", 0) * 0.30 +
            t.get("reddit_engagement", 0) * 0.20
        ), reverse=True)[:20]
        for t in prelim_scored:
            saturation_cache[t["title"]] = check_saturation(youtube, t["title"])

    # Calculate final scores and build DB records
    from database import engine
    from models.trending import TrendingTopic
    from sqlmodel import Session, select

    records: list[TrendingTopic] = []
    for topic in merged:
        fit = format_fits.get(topic["title"], {"score": 50.0, "rationale": ""})
        is_saturated = saturation_cache.get(topic["title"], False)
        final_score, is_first_mover = _calculate_final_score(topic, fit["score"], is_saturated)
        evidence = _build_evidence(topic, fit)

        score_breakdown = {
            "search_velocity": topic.get("search_velocity", 0.0),
            "competitor_view_rate": topic.get("competitor_view_rate", 0.0),
            "reddit_engagement": topic.get("reddit_engagement", 0.0),
            "format_fit": fit["score"],
        }

        records.append(TrendingTopic(
            title=topic["title"],
            source=topic["source"],
            score=final_score,
            score_breakdown=json.dumps(score_breakdown),
            format_fit_rationale=fit.get("rationale", ""),
            raw_data=json.dumps(topic.get("raw_data", {})),
            is_breakout=topic.get("is_breakout", False),
            is_first_mover=is_first_mover,
            evidence_snippet=evidence,
        ))

    # Sort by score descending, keep top 50
    records.sort(key=lambda r: r.score, reverse=True)
    records = records[:50]

    # Persist: clear old topics, insert new batch
    with Session(engine) as session:
        old = session.exec(select(TrendingTopic)).all()
        for o in old:
            session.delete(o)
        for r in records:
            session.add(r)
        session.commit()

    job.result_count = len(records)
    job.progress = 1.0
    job.status = "completed"
    logger.info("Trending refresh complete: %d topics scored and saved", len(records))


def run_refresh_sync() -> int:
    """Run a trending refresh synchronously. Returns topic count."""
    job = create_refresh_job()
    _run_refresh(job)
    if job.status == "failed":
        raise RuntimeError(f"Trending refresh failed: {job.error}")
    return job.result_count


def start_refresh() -> TrendingRefreshJob:
    """Start a background trending topic refresh job."""
    job = create_refresh_job()

    def _wrapper():
        try:
            _run_refresh(job)
        except Exception:
            logger.exception("Trending refresh job %s failed", job.id)
            job.status = "failed"
            job.error = traceback.format_exc()[-1000:]

    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()
    return job
