"""POST /api/v1/intake integration tests."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("_alembic_upgrade_session", "_clean_db"),
]


@pytest.mark.asyncio
async def test_intake_mission_request_creates_mission(
    client: AsyncClient, api_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/api/v1/intake",
        json={
            "source_surface": "api",
            "text": "pytest intake mission via unified path",
            "context": {
                "rehearsal_mode": "synthetic_api_only",
                "skip_runtime_publish": True,
            },
        },
        headers=api_headers,
    )
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    assert data["outcome"] == "mission_created"
    assert data["interpretation"]["intent_type"] == "mission_request"
    assert data["reply"]["kind"] == "mission_created"
    mid = UUID(data["reply"]["mission_id"])
    assert str(mid)

    mr = await client.get(f"/api/v1/missions/{mid}")
    assert mr.status_code == 200


@pytest.mark.asyncio
async def test_intake_status_query_returns_snapshot(
    client: AsyncClient, api_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/api/v1/intake",
        json={"source_surface": "api", "text": "list missions status"},
        headers=api_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["outcome"] == "status_reply"
    assert data["interpretation"]["intent_type"] == "status_query"
    assert data["reply"]["kind"] == "status_snapshot"


@pytest.mark.asyncio
async def test_intake_status_query_what_is_going_on_regression(
    client: AsyncClient, api_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/api/v1/intake",
        json={"source_surface": "api", "text": "What is going on right now?"},
        headers=api_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["outcome"] == "status_reply"
    assert data["interpretation"]["intent_type"] == "status_query"
    assert data["reply"]["kind"] == "status_snapshot"


@pytest.mark.asyncio
async def test_intake_requires_api_key(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/intake",
        json={"source_surface": "api", "text": "hello"},
    )
    assert r.status_code == 401
