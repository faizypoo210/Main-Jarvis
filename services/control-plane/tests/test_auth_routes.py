"""HTTP-level auth for protected routes (PostgreSQL required)."""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

from app.core.config import clear_settings_cache

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("_alembic_upgrade_session", "_clean_db"),
]


@pytest.mark.asyncio
async def test_post_commands_401_without_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTROL_PLANE_AUTH_MODE", "api_key")
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "server-secret")
    clear_settings_cache()
    r = await client.post(
        "/api/v1/commands",
        json={"text": "t", "source": "api"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_post_commands_401_wrong_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTROL_PLANE_AUTH_MODE", "api_key")
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "server-secret")
    clear_settings_cache()
    r = await client.post(
        "/api/v1/commands",
        json={"text": "t", "source": "api"},
        headers={"x-api-key": "wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_post_commands_200_with_valid_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, api_headers: dict[str, str]
) -> None:
    monkeypatch.setenv("CONTROL_PLANE_AUTH_MODE", "api_key")
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", os.environ["CONTROL_PLANE_API_KEY"])
    clear_settings_cache()
    r = await client.post(
        "/api/v1/commands",
        json={"text": "auth route ok", "source": "api", "context": {"skip_runtime_publish": True}},
        headers=api_headers,
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_local_trusted_allows_post_without_header(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CONTROL_PLANE_AUTH_MODE", "local_trusted")
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "")
    clear_settings_cache()
    r = await client.post(
        "/api/v1/commands",
        json={"text": "local trusted", "source": "api", "context": {"skip_runtime_publish": True}},
    )
    assert r.status_code == 200, r.text
