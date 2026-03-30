"""SQLite-backed logging handler for the dev dashboard.

Persists log records to a DevLog table and broadcasts them to WebSocket clients.
Uses a background thread with a queue to avoid blocking callers.
"""

import logging
import queue
import threading
import traceback as tb_module
from datetime import datetime, timezone, timedelta

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlmodel import Field, Session, SQLModel, select


class DevLog(SQLModel, table=True):
    __tablename__ = "dev_logs"

    id: int | None = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime, index=True),
    )
    level: str = Field(sa_column=Column(String, index=True))
    logger_name: str = Field(sa_column=Column(String, index=True))
    message: str = Field(sa_column=Column(Text))
    module: str = ""
    func_name: str = ""
    lineno: int = 0
    traceback: str | None = None


# Broadcast queue — routes.py reads from this to push to WebSocket clients
_broadcast_queue: queue.Queue[dict] = queue.Queue(maxsize=10_000)


def get_broadcast_queue() -> queue.Queue[dict]:
    return _broadcast_queue


class SQLiteLogHandler(logging.Handler):
    """Logging handler that persists records to SQLite via a background writer thread."""

    def __init__(self, engine) -> None:
        super().__init__()
        self._engine = engine
        self._queue: queue.Queue[logging.LogRecord | None] = queue.Queue(maxsize=50_000)
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            pass  # drop the log rather than blocking the caller

    def _writer_loop(self) -> None:
        while True:
            record = self._queue.get()
            if record is None:
                break
            try:
                self._persist(record)
            except Exception:
                pass  # never crash the writer thread

    def _persist(self, record: logging.LogRecord) -> None:
        traceback_str = None
        if record.exc_info and record.exc_info[1] is not None:
            traceback_str = "".join(tb_module.format_exception(*record.exc_info))[-2000:]

        entry = DevLog(
            timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
            level=record.levelname,
            logger_name=record.name,
            message=self.format(record) if self.formatter else record.getMessage(),
            module=record.module or "",
            func_name=record.funcName or "",
            lineno=record.lineno or 0,
            traceback=traceback_str,
        )

        with Session(self._engine) as session:
            session.add(entry)
            session.commit()
            session.refresh(entry)

        # Broadcast to WebSocket clients
        broadcast_data = {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat(),
            "level": entry.level,
            "logger_name": entry.logger_name,
            "message": entry.message,
            "module": entry.module,
            "func_name": entry.func_name,
            "lineno": entry.lineno,
            "traceback": entry.traceback,
        }
        try:
            _broadcast_queue.put_nowait(broadcast_data)
        except queue.Full:
            pass


def prune_old_logs(engine, days: int = 7) -> int:
    """Delete logs older than *days*. Returns count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with Session(engine) as session:
        old = session.exec(select(DevLog).where(DevLog.timestamp < cutoff)).all()
        count = len(old)
        for log in old:
            session.delete(log)
        session.commit()
    return count
