import logging

from sqlmodel import Session, SQLModel, create_engine, select

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
    _migrate_add_eli_position()
    _migrate_script_model_default()
    logger.info("Database ready")

def ensure_default_brand() -> None:
    """Ensure exactly one default brand exists. Create if missing."""
    from models.brand import BrandProfile

    with Session(engine) as session:
        existing = session.exec(select(BrandProfile)).first()
        if not existing:
            brand = BrandProfile(name="Headless Hero")
            session.add(brand)
            session.commit()
            logger.info("Created default brand: %s", brand.id)
        else:
            logger.info("Default brand exists: %s", existing.id)

def get_default_brand_id(session: Session) -> str:
    """Return the single default brand's ID."""
    from models.brand import BrandProfile

    brand = session.exec(select(BrandProfile)).first()
    if not brand:
        raise RuntimeError("No default brand found — ensure_default_brand() must run first")
    return brand.id

def get_session():
    """FastAPI dependency that yields a DB session."""
    with Session(engine) as session:
        yield session


def _migrate_add_eli_position() -> None:
    """Add eli_position_json column to brand_profiles if missing."""
    import sqlite3

    conn = sqlite3.connect(str(_db_path))
    try:
        cursor = conn.execute("PRAGMA table_info(brand_profiles)")
        columns = {row[1] for row in cursor.fetchall()}
        if "eli_position_json" not in columns:
            conn.execute("ALTER TABLE brand_profiles ADD COLUMN eli_position_json TEXT DEFAULT ''")
            conn.commit()
            logger.info("Migrated: added eli_position_json to brand_profiles")
    finally:
        conn.close()


def _migrate_script_model_default() -> None:
    """Clear stale SCRIPT_MODEL if it's the old Sonnet default so the new Opus default takes effect."""
    from models.settings import AppSetting

    with Session(engine) as session:
        setting = session.get(AppSetting, "SCRIPT_MODEL")
        if setting and setting.value == "claude-sonnet-4-20250514":
            session.delete(setting)
            session.commit()
            logger.info("Migrated: cleared stale SCRIPT_MODEL default (was claude-sonnet-4)")
