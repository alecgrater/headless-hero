"""Test-session isolation from the developer's real app state.

`TestClient(app)` runs the real FastAPI lifespan, and that lifespan reaches for
the developer's actual `data/db.sqlite`: it copies every saved setting into
`os.environ`, prunes rows out of `dev_logs`, and installs a log handler that
writes more in. Nothing in the suite asked for any of that, and all three leak
across tests.

Local Models Mode made it concrete: turning Local Mode on in Settings writes
`LOCAL_MODELS_ENABLED=true`, which then routed later routing and thumbnail
tests to the local providers and failed twelve of them on a machine where
nothing was actually broken.

Three fixtures, all autouse:

* **Environment.** Snapshot/restore `os.environ` per test, and strip every
  `api.settings.ALLOWED_KEYS` name from the copy the test sees. Snapshotting
  alone is not enough — a setting exported in the developer's *shell* reaches
  the suite without ever going through the lifespan.
* **Database.** Point the lifespan's *settings and dev-log* engine at an empty
  in-memory database, so the suite reads defaults and never prunes or writes the
  developer's `dev_logs`. `init_db()` and `ensure_default_brand()` still run
  against the real file — both are idempotent `CREATE TABLE IF NOT EXISTS` /
  "insert one row if absent" calls — so this is not full database isolation, and
  tests still supply their own engine via the `get_session` override.
* **Local-model arena.** `pipeline.local_runtime` holds process-global state and
  its `_unload` sends a real "free your models" POST to whichever daemon is
  running. Reset the state around every test and make `_unload` inert; a test
  run must never evict a model out of the developer's live ComfyUI.
"""

import os

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import models.settings  # noqa: F401  -- registers app_settings on SQLModel.metadata
import dev.log_handler  # noqa: F401  -- registers dev_logs on SQLModel.metadata

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
