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
    ai_provider: str = "fixture"
    ai_model_profiles_json: str = (
        '{"analysis-default":{"model":"fixture://analysis","label":"Fixture analysis",'
        '"structured_output_mode":"native_schema"},'
        '"analysis-json":{"model":"fixture://analysis","label":"Fixture JSON object",'
        '"structured_output_mode":"json_object"},'
        '"judge-default":{"model":"fixture://judge","label":"Fixture judge",'
        '"structured_output_mode":"native_schema"}}'
    )
    ai_default_analysis_profile: str = "analysis-default"
    ai_default_judge_profile: str = "judge-default"
    ai_prompt_root: Path = Path("app/prompts")
    ai_max_context_bytes: int = 512 * 1024
    ai_max_measurement_points: int = 200
    ai_max_total_points: int = 2000
    ai_max_output_tokens: int = 4000
    ai_timeout_seconds: float = 45.0
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
