"""
Application configuration via environment variables (pydantic-settings).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All app config is driven by env vars (or .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — default to SQLite for local dev
    DATABASE_URL: str = "sqlite:///./dev.db"

    # Google Gemini
    GEMINI_API_KEY: str = ""
    MODEL_NAME: str = "gemini-3.5-flash-lite"

    # CORS — comma-separated origins
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Upload limits
    MAX_UPLOAD_MB: int = 10
    MAX_PDF_PAGES: int = 6
    MAX_TEXT_CHARS: int = 20000

    # Rate limiting
    RATE_LIMIT_PER_HOUR: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
