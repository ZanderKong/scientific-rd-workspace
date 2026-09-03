from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Scientific R&D Workspace API"
    database_url: str = "postgresql+psycopg://scientific:scientific@localhost:5432/scientific_rd"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    storage_root: Path = Path("../data/uploads")
    max_upload_bytes: int = 25 * 1024 * 1024
    max_import_bytes: int = 10 * 1024 * 1024
    max_import_rows: int = 10000
    max_import_columns: int = 100
    import_preview_rows: int = 20
    max_xlsx_expanded_bytes: int = 50 * 1024 * 1024
    max_xlsx_archive_entries: int = 200


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
