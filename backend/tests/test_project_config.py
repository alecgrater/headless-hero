from sqlmodel import Session, SQLModel, create_engine
from models.project_config import ProjectConfig, get_or_create_project_config, get_project_config


def _make_engine():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return engine


def test_get_project_config_missing_returns_default():
    """Legacy projects with no row return a default with eli_enabled=True."""
    engine = _make_engine()
    with Session(engine) as session:
        cfg = get_project_config(session, "missing-script")
    assert cfg.eli_enabled is True
    assert cfg.script_id == "missing-script"
    assert cfg.main_character_reference_url is None


def test_get_or_create_project_config_persists_row():
    engine = _make_engine()
    with Session(engine) as session:
        cfg = get_or_create_project_config(session, "abc", eli_enabled=False)
        session.commit()
    with Session(engine) as session:
        loaded = get_project_config(session, "abc")
    assert loaded.eli_enabled is False
    assert loaded.script_id == "abc"


def test_get_or_create_idempotent():
    engine = _make_engine()
    with Session(engine) as session:
        get_or_create_project_config(session, "abc", eli_enabled=False)
        session.commit()
    with Session(engine) as session:
        # Calling again does not overwrite
        cfg = get_or_create_project_config(session, "abc", eli_enabled=True)
        session.commit()
    with Session(engine) as session:
        loaded = get_project_config(session, "abc")
    assert loaded.eli_enabled is False
