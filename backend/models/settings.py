"""App settings key-value store."""

from sqlmodel import Field, SQLModel


class AppSetting(SQLModel, table=True):
    """Key-value pair for persisted app settings (API keys, etc.)."""

    __tablename__ = "app_settings"

    key: str = Field(primary_key=True)
    value: str = Field(default="")
