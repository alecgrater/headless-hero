import logging

from sqlmodel import Session, SQLModel, create_engine, text

from config import DATA_DIR

logger = logging.getLogger(__name__)

# Store the DB in a `data/` directory next to the backend package
DATA_DIR.mkdir(parents=True, exist_ok=True)
_db_path = DATA_DIR / "db.sqlite"

engine = create_engine(f"sqlite:///{_db_path}", echo=False)

def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    logger.info("Initializing database")
    SQLModel.metadata.create_all(engine)
    # Run lightweight migrations for new columns on existing tables
    _migrate(engine)
    logger.info("Database ready")

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
                name = sql.split("ADD COLUMN")[1].strip().split()[0] if "ADD COLUMN" in sql else sql[:40]
                logger.info("Applied migration: %s", name)
            except Exception:
                session.rollback()

def get_session():
    """FastAPI dependency that yields a DB session."""
    with Session(engine) as session:
        yield session
