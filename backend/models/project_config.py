from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, select


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectConfig(SQLModel, table=True):
    """Per-project configuration. One row per script.

    Missing rows are treated as the default (Eli enabled) so projects created
    before this feature shipped continue to behave identically.
    """

    __tablename__ = "project_config"

    script_id: str = Field(primary_key=True, foreign_key="scripts.id")
    eli_enabled: bool = Field(default=True)
    main_character_reference_url: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


def get_project_config(session: Session, script_id: str) -> ProjectConfig:
    """Return the persisted ProjectConfig or a synthetic default for missing rows."""
    row = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if row is not None:
        return row
    return ProjectConfig(script_id=script_id, eli_enabled=True)


def get_or_create_project_config(
    session: Session, script_id: str, *, eli_enabled: bool
) -> ProjectConfig:
    """Insert a config row if missing, else return the existing row unchanged."""
    existing = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if existing is not None:
        return existing
    row = ProjectConfig(script_id=script_id, eli_enabled=eli_enabled)
    session.add(row)
    return row


def update_project_config(
    session: Session,
    script_id: str,
    *,
    main_character_reference_url: str | None = None,
) -> ProjectConfig:
    """Update mutable fields on an existing ProjectConfig. Raises if missing."""
    row = session.exec(
        select(ProjectConfig).where(ProjectConfig.script_id == script_id)
    ).first()
    if row is None:
        raise ValueError(f"ProjectConfig not found for script_id={script_id}")
    if main_character_reference_url is not None:
        row.main_character_reference_url = main_character_reference_url
    row.updated_at = _utcnow()
    session.add(row)
    return row
