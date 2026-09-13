"""Test-session isolation from the developer's real app state.

`TestClient(app)` runs the real FastAPI lifespan, and that lifespan reaches for
the developer's actual `data/` directory: it copies every saved setting into
`os.environ`, prunes rows out of `dev_logs`, installs a log handler that writes
more in, and — since identity snapshots — rewrites `data/identity.json` whenever
a test exercises a style preset or settings endpoint. Nothing in the suite asked
for any of that, and all of it leaks across tests or into tracked files.

Local Models Mode made it concrete: turning Local Mode on in Settings writes
`LOCAL_MODELS_ENABLED=true`, which then routed later routing and thumbnail
tests to the local providers and failed twelve of them on a machine where
nothing was actually broken.

`HH_DATA_DIR` is set at module scope rather than in a fixture because
`config.DATA_DIR` resolves it at import time, and pytest loads this file before
any backend module.

Three fixtures, all autouse:

* **Environment.** Snapshot/restore `os.environ` per test, and strip every
  `api.settings.ALLOWED_KEYS` name from the copy the test sees. Snapshotting
  alone is not enough — a setting exported in the developer's *shell* reaches
  the suite without ever going through the lifespan.
* **Database.** Point the lifespan's *settings and dev-log* engine at an empty
  in-memory database, so the suite reads defaults and never prunes or writes the
  developer's `dev_logs`. `init_db()` and `ensure_default_brand()` still run
  against a file engine — but that file now lives in the throwaway data
  directory, so tests still supply their own engine via the `get_session`
  override and nothing touches real state.
* **Local-model arena.** `pipeline.local_runtime` holds process-global state and
  its `_unload` sends a real "free your models" POST to whichever daemon is
  running. Reset the state around every test and make `_unload` inert; a test
  run must never evict a model out of the developer's live ComfyUI.
"""

import os
import tempfile

# Must precede every backend import below — config.DATA_DIR is read at import.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="headless-hero-tests-")
os.environ["HH_DATA_DIR"] = _TEST_DATA_DIR

import pytest  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import SQLModel, create_engine  # noqa: E402

import models.settings  # noqa: F401, E402  -- registers app_settings on SQLModel.metadata
import dev.log_handler  # noqa: F401, E402  -- registers dev_logs on SQLModel.metadata

# One empty database for the whole session; it only ever has to be readable.
# StaticPool + check_same_thread: a default in-memory SQLite engine hands every
# connection its own blank database, so tables created here would be invisible
# to the lifespan's session.
_EMPTY_DB_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(_EMPTY_DB_ENGINE)


@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    """Give the throwaway file database the full schema.

    Some tests reach the module-level engine rather than an injected one and
    previously borrowed the developer's populated db.sqlite for its tables.
    Importing the app first registers every SQLModel table, so the schema is
    complete even when a single test file runs on its own.
    """
    import api  # noqa: F401 -- registers all tables
    from database import init_db

    init_db()


@pytest.fixture(autouse=True)
def _isolate_environment():
    from api.settings import ALLOWED_KEYS

    snapshot = dict(os.environ)
    for key in ALLOWED_KEYS:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)


@pytest.fixture(autouse=True)
def _isolate_database(monkeypatch):
    # Only the name the lifespan reads. Repointing `database.engine` itself
    # breaks the many modules that bound it at import time and leaves tests
    # querying an empty database they never seeded.
    import api

    monkeypatch.setattr(api, "_db_engine", _EMPTY_DB_ENGINE)


@pytest.fixture(autouse=True)
def _silence_dev_log_handler(monkeypatch):
    """Stop the lifespan from installing a real SQLite log writer per test.

    `lifespan` builds a `SQLiteLogHandler` — each with its own writer thread —
    and adds it to the root logger without ever removing it. Across the suite
    that accumulates hundreds of live threads all writing through the single
    connection a StaticPool in-memory engine hands out, which segfaults inside
    the SQLite C extension partway through a full run. Nothing under test
    asserts on dev-log persistence.
    """
    import logging

    import api

    class _InertLogHandler(logging.Handler):
        def __init__(self, engine) -> None:
            super().__init__()

        def emit(self, record: logging.LogRecord) -> None:
            pass

    monkeypatch.setattr(api, "SQLiteLogHandler", _InertLogHandler)


@pytest.fixture(autouse=True)
def _isolate_local_runtime(monkeypatch):
    from pipeline import local_runtime

    # A test that wants to assert on unloading re-patches this itself; its
    # monkeypatch is applied after ours and wins.
    monkeypatch.setattr(local_runtime, "_unload", lambda modality: None)
    local_runtime.reset_for_testing()
    try:
        yield
    finally:
        local_runtime.reset_for_testing()
