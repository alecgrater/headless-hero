"""Dev dashboard API routes, WebSocket log streaming, and HTML serving."""

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import inspect, text
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


# --- Database Inspector ---

_SENSITIVE_COLUMNS = {"access_token", "refresh_token", "value"}
_SENSITIVE_TABLES = {"platform_credentials", "app_settings"}


@router.get("/api/db/tables")
async def db_tables():
    """Return all table names with row counts and column info."""
    inspector_obj = inspect(engine)
    tables = inspector_obj.get_table_names()
    result = []
    with engine.connect() as conn:
        for table_name in sorted(tables):
            columns = [
                {"name": c["name"], "type": str(c["type"])}
                for c in inspector_obj.get_columns(table_name)
            ]
            row_count = conn.execute(
                text(f"SELECT COUNT(*) FROM [{table_name}]")
            ).scalar()
            result.append({
                "name": table_name,
                "row_count": row_count,
                "columns": columns,
            })
    return result


@router.get("/api/db/tables/{table_name}")
async def db_table_rows(
    table_name: str,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
):
    """Paginated row browser for a specific table."""
    inspector_obj = inspect(engine)
    valid_tables = inspector_obj.get_table_names()
    if table_name not in valid_tables:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    columns = [c["name"] for c in inspector_obj.get_columns(table_name)]
    should_redact = table_name in _SENSITIVE_TABLES

    with engine.connect() as conn:
        row_count = conn.execute(
            text(f"SELECT COUNT(*) FROM [{table_name}]")
        ).scalar()
        rows_raw = conn.execute(
            text(f"SELECT * FROM [{table_name}] LIMIT :lim OFFSET :off"),
            {"lim": limit, "off": offset},
        ).fetchall()

    rows = []
    for row in rows_raw:
        row_dict = dict(zip(columns, row))
        if should_redact:
            for col_name in _SENSITIVE_COLUMNS:
                if col_name in row_dict and row_dict[col_name]:
                    val = str(row_dict[col_name])
                    row_dict[col_name] = "••••••••" + val[-4:] if len(val) > 4 else "••••••••"
        rows.append(row_dict)

    return {
        "table": table_name,
        "columns": columns,
        "row_count": row_count,
        "rows": rows,
        "limit": limit,
        "offset": offset,
    }


class DbQueryRequest(BaseModel):
    sql: str
    limit: int = 200


@router.post("/api/db/query")
async def db_query(req: DbQueryRequest):
    """Execute a read-only SQL query."""
    sql_stripped = req.sql.strip()
    first_keyword = sql_stripped.split()[0].upper() if sql_stripped else ""
    allowed = {"SELECT", "PRAGMA", "EXPLAIN", "WITH"}
    if first_keyword not in allowed:
        return {
            "error": f"Only {', '.join(sorted(allowed))} queries are allowed. Got: {first_keyword}",
            "columns": [],
            "rows": [],
        }

    limit = min(req.limit, 500)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_stripped))
            columns = list(result.keys()) if result.returns_rows else []
            rows_raw = result.fetchmany(limit) if result.returns_rows else []
            rows = [dict(zip(columns, row)) for row in rows_raw]
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"error": str(e), "columns": [], "rows": []}
