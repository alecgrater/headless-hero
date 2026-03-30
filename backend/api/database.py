import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, text

# Store the DB in a `data/` directory next to the backend package
_data_dir = Path(os.environ.get("HH_DATA_DIR", os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data")))
_data_dir.mkdir(parents=True, exist_ok=True)
_db_path = _data_dir / "db.sqlite"

engine = create_engine(f"sqlite:///{_db_path}", echo=False)

def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    SQLModel.metadata.create_all(engine)
    # Run lightweight migrations for new columns on existing tables
    _migrate(engine)

def _migrate(engine) -> None:
    """Add columns that may not exist in older databases."""
    migrations = [
        "ALTER TABLE brand_profiles ADD COLUMN content_modifiers TEXT DEFAULT ''",
        "ALTER TABLE scripts ADD COLUMN content_format TEXT DEFAULT 'youtube'",
        "ALTER TABLE scripts ADD COLUMN shortform_platforms TEXT DEFAULT ''",
        "ALTER TABLE brand_profiles ADD COLUMN shortform_voice_settings TEXT DEFAULT ''",
        "ALTER TABLE brand_profiles ADD COLUMN style_string TEXT DEFAULT ''",
    ]
    with Session(engine) as session:
        for sql in migrations:
            try:
                session.exec(text(sql))
                session.commit()
            except Exception:
                session.rollback()

def get_session():
    """FastAPI dependency that yields a DB session."""
    with Session(engine) as session:
        yield session
