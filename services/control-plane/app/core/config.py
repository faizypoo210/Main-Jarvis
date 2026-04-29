"""Application settings from environment variables.

TRUTH_SOURCE: .env keys documented in services/control-plane/.env.example; required for boot.
MACHINE_CONFIG_REQUIRED: DATABASE_URL, SECRET_KEY, CONTROL_PLANE_AUTH_MODE, and (for api_key mode) CONTROL_PLANE_API_KEY.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ControlPlaneAuthMode(StrEnum):
    """How protected routes enforce write access."""

    API_KEY = "api_key"
    LOCAL_TRUSTED = "local_trusted"


class Settings(BaseSettings):
    """Control plane configuration."""

    DATABASE_URL: str
    REDIS_URL: str | None = None
    SERVICE_NAME: str = "jarvis-control-plane"
    SECRET_KEY: str
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    # api_key: require CONTROL_PLANE_API_KEY; local_trusted: explicit insecure local dev (no key enforcement).
    CONTROL_PLANE_AUTH_MODE: ControlPlaneAuthMode = ControlPlaneAuthMode.API_KEY
    CONTROL_PLANE_API_KEY: str = ""
    # Optional HTTP probes for GET /api/v1/system/health (empty = do not assume localhost execution truth).
    JARVIS_HEALTH_OPENCLAW_GATEWAY_URL: str = ""
    JARVIS_HEALTH_OLLAMA_URL: str = ""
    # Optional: base URL for the OpenClaw gateway (e.g. set in .env — see .env.example)
    JARVIS_OPENCLAW_GATEWAY_URL: str = ""
    JARVIS_LOCAL_MODEL: str = ""
    JARVIS_CLOUD_MODEL: str = ""
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    # GitHub REST (governed create-issue workflow only). Machine-local secret; never logged.
    JARVIS_GITHUB_TOKEN: str = ""
    # Gmail API (governed create-draft only). Use access token and/or OAuth refresh — see INTEGRATIONS_GMAIL.md.
    JARVIS_GMAIL_ACCESS_TOKEN: str = ""
    JARVIS_GMAIL_REFRESH_TOKEN: str = ""
    JARVIS_GMAIL_CLIENT_ID: str = ""
    JARVIS_GMAIL_CLIENT_SECRET: str = ""
    # SMS approval v1 (Twilio): outbound notify + inbound APPROVE/DENY/READ <code>
    JARVIS_SMS_APPROVALS_ENABLED: bool = False
    JARVIS_TWILIO_ACCOUNT_SID: str = ""
    JARVIS_TWILIO_AUTH_TOKEN: str = ""
    JARVIS_TWILIO_FROM_NUMBER: str = ""
    JARVIS_APPROVAL_SMS_TO_E164: str = ""
    JARVIS_TWILIO_WEBHOOK_BASE_URL: str = ""
    JARVIS_TWILIO_INBOUND_SKIP_SIGNATURE_VALIDATION: bool = False
    JARVIS_TWILIO_INBOUND_DECIDED_BY: str = "sms_operator"
    # Approval reminders + escalation v1 (heartbeat; persisted in approval_reminders)
    APPROVAL_REMINDERS_ENABLED: bool = False
    APPROVAL_REMINDER_FIRST_MINUTES: int = 60
    APPROVAL_REMINDER_REPEAT_MINUTES: int = 120
    APPROVAL_ESCALATION_MINUTES: int = 360
    APPROVAL_REMINDER_MAX_ATTEMPTS: int = 3
    APPROVAL_REMINDER_SMS_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
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
