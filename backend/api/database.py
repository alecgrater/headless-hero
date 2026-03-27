import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# Store the DB in a `data/` directory next to the backend package
_data_dir = Path(os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
_data_dir.mkdir(parents=True, exist_ok=True)
_db_path = _data_dir / "db.sqlite"

engine = create_engine(f"sqlite:///{_db_path}", echo=False)

def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    SQLModel.metadata.create_all(engine)

def get_session():
    """FastAPI dependency that yields a DB session."""
    with Session(engine) as session:
        yield session
