"""Tests for SQLite schema upgrades."""

import sqlite3


def test_init_db_adds_cutout_url_to_existing_style_preset_characters_table(
    tmp_path,
    monkeypatch,
):
    import database
    from models.api_usage import ApiUsage  # noqa: F401
    from models.brand import BrandProfile  # noqa: F401
    from models.generation_duration import GenerationDuration  # noqa: F401
    from models.idea import Idea  # noqa: F401
    from models.publish import PublishRecord  # noqa: F401
    from models.script import Script  # noqa: F401
    from models.settings import AppSetting  # noqa: F401

    db_path = tmp_path / "upgrade.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE style_preset_characters (
                id TEXT PRIMARY KEY,
                style_preset_id TEXT,
                name TEXT DEFAULT '',
                appearance TEXT DEFAULT '',
                vibe TEXT DEFAULT '',
                reference_image_url TEXT DEFAULT '',
                created_at TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(database, "_db_path", db_path)
    monkeypatch.setattr(
        database,
        "engine",
        database.create_engine(f"sqlite:///{db_path}", echo=False),
    )

    database.init_db()

    conn = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(style_preset_characters)")}
    finally:
        conn.close()

    assert "cutout_image_url" in columns
