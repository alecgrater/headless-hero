"""Dev dashboard API routes, WebSocket log streaming, and HTML serving."""

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlmodel import Session, func, select, col

from api.database import engine
from dev.log_handler import DevLog, get_broadcast_queue
from pipeline import render_jobs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev", tags=["dev"])

_DASHBOARD_HTML = Path(__file__).parent / "dashboard.html"

# --- Connected WebSocket clients ---
_ws_clients: set[WebSocket] = set()
_ws_lock = threading.Lock()


@router.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(_DASHBOARD_HTML.read_text())


@router.get("/api/logs")
async def get_logs(
    level: str | None = None,
    logger_name: str | None = None,
    search: str | None = None,
    since: str | None = None,
    limit: int = Query(default=200, le=2000),
    offset: int = 0,
):
    stmt = select(DevLog).order_by(col(DevLog.id).desc())

    if level:
        levels = _level_and_above(level)
        stmt = stmt.where(col(DevLog.level).in_(levels))
    if logger_name:
        stmt = stmt.where(DevLog.logger_name == logger_name)
    if search:
        stmt = stmt.where(col(DevLog.message).contains(search))
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            stmt = stmt.where(DevLog.timestamp >= since_dt)
        except ValueError:
            pass

    stmt = stmt.offset(offset).limit(limit)

    with Session(engine) as session:
        logs = session.exec(stmt).all()

    return [_log_to_dict(log) for log in logs]


@router.get("/api/logs/stats")
async def log_stats():
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_1h = now - timedelta(hours=1)

    with Session(engine) as session:
        # By level
        level_rows = session.exec(
            select(DevLog.level, func.count()).where(DevLog.timestamp >= last_24h).group_by(DevLog.level)
        ).all()
        by_level = {row[0]: row[1] for row in level_rows}

        # By module
        mod_rows = session.exec(
            select(DevLog.logger_name, func.count())
            .where(DevLog.timestamp >= last_24h)
            .group_by(DevLog.logger_name)
            .order_by(func.count().desc())
            .limit(20)
        ).all()
        by_module = {row[0]: row[1] for row in mod_rows}

        # Top messages (group by first 120 chars of message)
        top_rows = session.exec(
            select(func.substr(DevLog.message, 1, 120), func.count())
            .where(DevLog.timestamp >= last_24h)
            .group_by(func.substr(DevLog.message, 1, 120))
            .order_by(func.count().desc())
            .limit(10)
        ).all()
        top_messages = [{"message": row[0], "count": row[1]} for row in top_rows]

        # Recent new — messages that first appeared in last hour
        # Get message prefixes from last hour
        recent_prefixes = session.exec(
            select(func.substr(DevLog.message, 1, 120)).distinct()
            .where(DevLog.timestamp >= last_1h)
            .limit(100)
        ).all()
        # Check which ones don't exist before last hour
        recent_new = []
        for (prefix,) in recent_prefixes if recent_prefixes else []:
            older = session.exec(
                select(func.count())
                .select_from(DevLog)
                .where(DevLog.timestamp < last_1h)
                .where(func.substr(DevLog.message, 1, 120) == prefix)
            ).one()
            if older == 0:
                recent_new.append(prefix)
            if len(recent_new) >= 10:
                break

    return {
        "by_level": by_level,
        "by_module": by_module,
        "top_messages": top_messages,
        "recent_new": recent_new,
    }


@router.get("/api/logs/modules")
async def log_modules():
    """Return distinct logger names for filter dropdown."""
    with Session(engine) as session:
        rows = session.exec(select(DevLog.logger_name).distinct().limit(100)).all()
    return sorted(set(r for r in rows if r))


@router.get("/api/jobs")
async def get_jobs():
    jobs = []
    with render_jobs._lock:
        for job in render_jobs._jobs.values():
            d = job.to_dict()
            d["scene_count"] = job.scene_count
            d["duration_seconds"] = job.duration_seconds
            d["start_time"] = job._start_time
            jobs.append(d)
    return jobs


@router.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    with _ws_lock:
        _ws_clients.add(ws)
    try:
        bq = get_broadcast_queue()
        while True:
            # Check for new broadcast items
            try:
                data = await asyncio.get_event_loop().run_in_executor(None, lambda: bq.get(timeout=0.5))
                # Send to this client
                await ws.send_text(json.dumps(data))
                # Drain any queued items
                while not bq.empty():
                    try:
                        extra = bq.get_nowait()
                        await ws.send_text(json.dumps(extra))
                    except Exception:
                        break
            except Exception:
                # Timeout or empty — check if client still connected by receiving
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=0.01)
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        with _ws_lock:
            _ws_clients.discard(ws)


def _log_to_dict(log: DevLog) -> dict:
    return {
        "id": log.id,
        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        "level": log.level,
        "logger_name": log.logger_name,
        "message": log.message,
        "module": log.module,
        "func_name": log.func_name,
        "lineno": log.lineno,
        "traceback": log.traceback,
    }


def _level_and_above(level: str) -> list[str]:
    """Return the given level and all more severe levels."""
    order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    level = level.upper()
    if level in order:
        idx = order.index(level)
        return order[idx:]
    return [level]
