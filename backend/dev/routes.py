"""Dev dashboard API routes, WebSocket log streaming, and HTML serving."""

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlmodel import Session, func, select, col

from api.database import engine
from dev.log_handler import DevLog, get_broadcast_queue
from models.api_usage import ApiUsage
from pipeline import render_jobs

logger = logging.getLogger(__name__)

# --- File Explorer ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

IGNORED_NAMES = {
    ".git", "node_modules", "__pycache__", ".venv", "data", "dist", "out",
    ".vite", ".DS_Store", ".env", ".env.local",
}


def _safe_resolve(path_str: str) -> Path:
    """Resolve a path against PROJECT_ROOT, rejecting traversal attempts."""
    resolved = (PROJECT_ROOT / path_str).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    return resolved


# Markdown index cache
_md_index_cache: dict | None = None
_md_index_ts: float = 0

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


# --- API Usage Tracking ---

@router.get("/api/usage/summary")
async def usage_summary(days: int = Query(default=30, le=365)):
    """Aggregate usage stats per service over the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with Session(engine) as session:
        # Per-service totals
        rows = session.exec(
            select(
                ApiUsage.service,
                func.count().label("call_count"),
                func.sum(ApiUsage.input_tokens).label("total_input_tokens"),
                func.sum(ApiUsage.output_tokens).label("total_output_tokens"),
                func.sum(ApiUsage.characters).label("total_characters"),
                func.sum(ApiUsage.images).label("total_images"),
                func.sum(ApiUsage.cost_estimate).label("total_cost"),
            )
            .where(ApiUsage.created_at >= cutoff)
            .group_by(ApiUsage.service)
        ).all()

        services = []
        grand_total = 0.0
        for row in rows:
            cost = row.total_cost or 0.0
            grand_total += cost
            services.append({
                "service": row.service,
                "call_count": row.call_count,
                "total_input_tokens": row.total_input_tokens or 0,
                "total_output_tokens": row.total_output_tokens or 0,
                "total_characters": row.total_characters or 0,
                "total_images": row.total_images or 0,
                "total_cost": round(cost, 4),
            })

        # Per-day cost breakdown (for chart)
        daily_rows = session.exec(
            select(
                func.date(ApiUsage.created_at).label("day"),
                ApiUsage.service,
                func.sum(ApiUsage.cost_estimate).label("cost"),
                func.count().label("calls"),
            )
            .where(ApiUsage.created_at >= cutoff)
            .group_by(func.date(ApiUsage.created_at), ApiUsage.service)
            .order_by(func.date(ApiUsage.created_at))
        ).all()

        daily = []
        for row in daily_rows:
            daily.append({
                "day": str(row.day),
                "service": row.service,
                "cost": round(row.cost or 0.0, 4),
                "calls": row.calls,
            })

        # Per-operation breakdown
        op_rows = session.exec(
            select(
                ApiUsage.service,
                ApiUsage.operation,
                ApiUsage.model,
                func.count().label("call_count"),
                func.sum(ApiUsage.cost_estimate).label("total_cost"),
            )
            .where(ApiUsage.created_at >= cutoff)
            .group_by(ApiUsage.service, ApiUsage.operation, ApiUsage.model)
            .order_by(func.sum(ApiUsage.cost_estimate).desc())
        ).all()

        operations = []
        for row in op_rows:
            operations.append({
                "service": row.service,
                "operation": row.operation,
                "model": row.model,
                "call_count": row.call_count,
                "total_cost": round(row.total_cost or 0.0, 4),
            })

    return {
        "days": days,
        "grand_total_cost": round(grand_total, 4),
        "services": services,
        "daily": daily,
        "operations": operations,
    }


@router.get("/api/usage/recent")
async def usage_recent(limit: int = Query(default=100, le=500)):
    """Return recent API usage events for the call log table."""
    with Session(engine) as session:
        rows = session.exec(
            select(ApiUsage)
            .order_by(col(ApiUsage.created_at).desc())
            .limit(limit)
        ).all()

    return [
        {
            "id": r.id,
            "service": r.service,
            "operation": r.operation,
            "model": r.model,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "characters": r.characters,
            "images": r.images,
            "cost_estimate": round(r.cost_estimate, 6),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# --- File Explorer ---

@router.get("/api/files/tree")
async def files_tree(path: str = ""):
    """List directory contents (dirs first, then files, alphabetical)."""
    resolved = _safe_resolve(path)
    if not resolved.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    rel = resolved.relative_to(PROJECT_ROOT)
    parent = str(rel.parent) if str(rel) != "." else None

    entries = []
    try:
        for item in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name in IGNORED_NAMES:
                continue
            if item.is_dir():
                try:
                    child_count = sum(1 for c in item.iterdir() if c.name not in IGNORED_NAMES)
                except PermissionError:
                    child_count = 0
                entries.append({
                    "name": item.name,
                    "type": "dir",
                    "child_count": child_count,
                })
            else:
                try:
                    size = item.stat().st_size
                except OSError:
                    size = 0
                entries.append({
                    "name": item.name,
                    "type": "file",
                    "size": size,
                    "ext": item.suffix.lstrip(".") if item.suffix else "",
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {
        "path": str(rel),
        "parent": parent,
        "entries": entries,
    }


@router.get("/api/files/read")
async def files_read(path: str):
    """Read a single file's contents."""
    resolved = _safe_resolve(path)
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    size = resolved.stat().st_size
    if size > 500_000:
        raise HTTPException(status_code=413, detail="File too large (>500KB)")

    name = resolved.name
    ext = resolved.suffix.lstrip(".") if resolved.suffix else ""
    is_markdown = ext in ("md", "mdx")

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "path": str(resolved.relative_to(PROJECT_ROOT)),
            "name": name,
            "ext": ext,
            "size": size,
            "content": None,
            "is_markdown": False,
            "is_binary": True,
        }

    return {
        "path": str(resolved.relative_to(PROJECT_ROOT)),
        "name": name,
        "ext": ext,
        "size": size,
        "content": content,
        "is_markdown": is_markdown,
        "is_binary": False,
    }


@router.get("/api/files/markdown-index")
async def files_markdown_index():
    """Discover all .md files in repo (cached 30s)."""
    global _md_index_cache, _md_index_ts

    now = time.time()
    if _md_index_cache is not None and (now - _md_index_ts) < 30:
        return _md_index_cache

    files = []
    for md_path in sorted(PROJECT_ROOT.rglob("*.md")):
        # Skip ignored directories
        parts = md_path.relative_to(PROJECT_ROOT).parts
        if any(p in IGNORED_NAMES for p in parts):
            continue
        rel = md_path.relative_to(PROJECT_ROOT)
        files.append({
            "path": str(rel),
            "name": md_path.name,
            "dir": str(rel.parent) if str(rel.parent) != "." else "",
        })

    _md_index_cache = {"files": files}
    _md_index_ts = now
    return _md_index_cache
