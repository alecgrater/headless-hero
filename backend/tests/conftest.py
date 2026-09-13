"""Test-session isolation from the developer's real app state.

Two leaks, one cause: `TestClient(app)` runs the real FastAPI lifespan, and
that lifespan calls `api.settings.load_keys_into_env` against the developer's
actual `data/db.sqlite`.

1. Every saved setting is copied into `os.environ` and stays there for the rest
   of the session, so a test's result depends on what ran before it.
2. Inside the test that booted the client, the app behaves as the developer's
   Settings screen is configured.

Local Models Mode made both concrete: turning Local Mode on in Settings writes
`LOCAL_MODELS_ENABLED=true`, which then routed later routing and thumbnail
tests to the local providers and failed twelve of them on a machine where
nothing was actually broken.

So: snapshot/restore `os.environ` per test, and point the lifespan's settings
load at an empty database. Defaults still get applied — that is what the
routing tests expect — but no saved user setting reaches the suite.
"""

import os

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import models.settings  # noqa: F401  -- registers app_settings on SQLModel.metadata

# One empty database for the whole session; it only ever has to be readable.
# StaticPool + check_same_thread: a default in-memory SQLite engine hands every
# connection its own blank database, so the tables created here would not be
# visible to the lifespan's session.
_EMPTY_SETTINGS_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(_EMPTY_SETTINGS_ENGINE)


@pytest.fixture(autouse=True)
def _isolate_app_state(monkeypatch):
    import api.settings as settings_module

    real_load = settings_module.load_keys_into_env

    def load_defaults_only(_session) -> None:
        with Session(_EMPTY_SETTINGS_ENGINE) as session:
            real_load(session)

    monkeypatch.setattr(settings_module, "load_keys_into_env", load_defaults_only)

    snapshot = dict(os.environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)
