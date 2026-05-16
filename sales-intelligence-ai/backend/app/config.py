from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[PROJECT_ROOT / ".env", BACKEND_DIR / ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./sales_intelligence.db"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    COMAX_REPORTS_DIR: Path = PROJECT_ROOT / "data" / "comax_reports"
    IMPORTED_DIR: Path = PROJECT_ROOT / "data" / "imported"
    FAILED_DIR: Path = PROJECT_ROOT / "data" / "failed"
    ARCHIVE_DIR: Path = PROJECT_ROOT / "data" / "archive"
    SAMPLE_DIR: Path = PROJECT_ROOT / "data" / "sample"
    REPORTS_DIR: Path = PROJECT_ROOT / "reports"
    EXPORTS_DIR: Path = PROJECT_ROOT / "exports"
    LOGS_DIR: Path = PROJECT_ROOT / "logs"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    WATCHER_INTERVAL_SECONDS: int = 60
    WATCHER_ENABLED: bool = True

    DATA_SOURCE: str = "file"  # "file" | "comax_api"

    COMAX_API_BASE_URL: str = ""
    COMAX_API_KEY: str = ""
    COMAX_API_USER: str = ""
    COMAX_API_PASSWORD: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    def ensure_dirs(self) -> None:
        for d in [
            self.COMAX_REPORTS_DIR,
            self.IMPORTED_DIR,
            self.FAILED_DIR,
            self.ARCHIVE_DIR,
            self.SAMPLE_DIR,
            self.REPORTS_DIR,
            self.REPORTS_DIR / "jpg",
            self.REPORTS_DIR / "png",
            self.REPORTS_DIR / "pdf",
            self.EXPORTS_DIR,
            self.LOGS_DIR,
        ]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
