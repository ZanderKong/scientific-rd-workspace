from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Scientific R&D Workspace API"
    database_url: str = "postgresql+psycopg://scientific:scientific@localhost:5432/scientific_rd"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    storage_root: Path = Path("../data/uploads")
    max_upload_bytes: int = 25 * 1024 * 1024
    max_import_bytes: int = 10 * 1024 * 1024
    max_import_rows: int = 10000
    max_import_columns: int = 100
    import_preview_rows: int = 20
    max_xlsx_expanded_bytes: int = 50 * 1024 * 1024
    max_xlsx_archive_entries: int = 200
    mcp_bearer_token: str | None = None
    storage_backend_default: str = "local"
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_force_path_style: bool = False
    storage_image_to_s3: bool = False
    storage_large_file_threshold: int | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
