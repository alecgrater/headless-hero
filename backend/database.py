import logging

from sqlmodel import Session, SQLModel, create_engine

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
    logger.info("Database ready")

def get_session():
    """FastAPI dependency that yields a DB session."""
    with Session(engine) as session:
        yield session
