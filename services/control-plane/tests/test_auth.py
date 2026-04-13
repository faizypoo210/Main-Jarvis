"""Control plane auth mode and startup validation (no DB)."""

from __future__ import annotations

import pytest

from app.core.auth import assert_auth_config_for_startup, require_api_key
from app.core.config import Settings


def test_startup_fails_api_key_mode_without_key() -> None:
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://u@localhost:5432/db",
        SECRET_KEY="x",
        CONTROL_PLANE_AUTH_MODE="api_key",
        CONTROL_PLANE_API_KEY="",
    )
    with pytest.raises(RuntimeError, match="CONTROL_PLANE_AUTH_MODE=api_key"):
        assert_auth_config_for_startup(s, testing=False)


def test_startup_allows_local_trusted_with_empty_key() -> None:
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://u@localhost:5432/db",
        SECRET_KEY="x",
        CONTROL_PLANE_AUTH_MODE="local_trusted",
        CONTROL_PLANE_API_KEY="",
    )
    assert_auth_config_for_startup(s, testing=False)


def test_startup_skipped_when_testing_flag() -> None:
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://u@localhost:5432/db",
        SECRET_KEY="x",
        CONTROL_PLANE_AUTH_MODE="api_key",
        CONTROL_PLANE_API_KEY="",
    )
    assert_auth_config_for_startup(s, testing=True)


@pytest.mark.asyncio
async def test_require_api_key_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    monkeypatch.setenv("CONTROL_PLANE_AUTH_MODE", "api_key")
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "good")
    from app.core.config import clear_settings_cache

    clear_settings_cache()
    try:
        with pytest.raises(HTTPException) as ei:
            await require_api_key(x_api_key="bad")
        assert ei.value.status_code == 401
    finally:
        clear_settings_cache()
