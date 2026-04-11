"""Application settings from environment variables.

TRUTH_SOURCE: .env keys documented in services/control-plane/.env.example; required for boot.
MACHINE_CONFIG_REQUIRED: DATABASE_URL, SECRET_KEY, and optional CONTROL_PLANE_API_KEY on the host.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Control plane configuration."""

    DATABASE_URL: str
    REDIS_URL: str | None = None
    SERVICE_NAME: str = "jarvis-control-plane"
    SECRET_KEY: str
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    CONTROL_PLANE_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
