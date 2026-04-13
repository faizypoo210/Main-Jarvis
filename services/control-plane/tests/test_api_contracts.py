"""High-value API contract tests — PostgreSQL required (see docs/TESTING.md)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.api.routes import system as system_routes
from app.schemas.system import ComponentHealth


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("service") == "jarvis-control-plane"
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_post_commands_creates_mission_and_created_event(
    client: AsyncClient, api_headers: dict[str, str]
) -> None:
    """Golden path: API-key command intake → mission + `created` event (Redis skipped)."""
    payload = {
        "text": "pytest contract mission",
        "source": "api",
        "context": {
            "rehearsal_mode": "synthetic_api_only",
            "skip_runtime_publish": True,
        },
    }
    r = await client.post("/api/v1/commands", json=payload, headers=api_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("message")
    mid = UUID(data["mission_id"])
    assert data.get("mission_status") == "pending"

    mr = await client.get(f"/api/v1/missions/{mid}")
    assert mr.status_code == 200
    mission = mr.json()
    assert mission["id"] == str(mid)
    assert mission["status"] == "pending"

    er = await client.get(f"/api/v1/missions/{mid}/events")
    assert er.status_code == 200
    events: list[dict[str, Any]] = er.json()
    types = {e["event_type"] for e in events}
    assert "created" in types
    created = next(e for e in events if e["event_type"] == "created")
    assert created.get("payload") and "text" in created["payload"]

    br = await client.get(f"/api/v1/missions/{mid}/bundle")
    assert br.status_code == 200
    bundle = br.json()
    assert bundle.get("mission") and bundle["mission"]["id"] == str(mid)


@pytest.mark.asyncio
async def test_github_create_issue_pending_approval_bundle_and_inbox(
    client: AsyncClient, api_headers: dict[str, str]
) -> None:
    """Governed GitHub route creates pending approval + events; bundle is structured."""
    cmd = await client.post(
        "/api/v1/commands",
        json={
            "text": "mission for github governed request",
            "source": "api",
            "context": {
                "rehearsal_mode": "synthetic_api_only",
                "skip_runtime_publish": True,
            },
        },
        headers=api_headers,
    )
    assert cmd.status_code == 200
    mission_id = UUID(cmd.json()["mission_id"])

    gh = await client.post(
        f"/api/v1/missions/{mission_id}/integrations/github/create-issue",
        json={
            "repo": "test-owner/test-repo",
            "title": "Contract test issue",
            "body": "",
            "requested_by": "pytest",
            "requested_via": "command_center",
        },
        headers=api_headers,
    )
    assert gh.status_code == 200, gh.text
    approval = gh.json()
    approval_id = UUID(approval["id"])
    assert approval["status"] == "pending"
    assert approval["action_type"] == "github_create_issue"

    mer = await client.get(f"/api/v1/missions/{mission_id}/events")
    assert mer.status_code == 200
    ev = mer.json()
    et = {e["event_type"] for e in ev}
    assert "approval_requested" in et
    assert "integration_action_requested" in et

    mr = await client.get(f"/api/v1/missions/{mission_id}")
    assert mr.json().get("status") == "awaiting_approval"

    bundle_r = await client.get(f"/api/v1/approvals/{approval_id}/bundle")
    assert bundle_r.status_code == 200
    b = bundle_r.json()
    assert b.get("generated_at")
    assert b["approval"]["id"] == str(approval_id)
    assert b["packet"]["action_type"] == "github_create_issue"
    assert b["packet"]["kind"] == "typed"
    assert "spoken_summary" in b["packet"]
    assert b["context"]["requested_via"] == "command_center"
    assert b["context"]["identity_bearing"] is True

    inbox = await client.get("/api/v1/operator/inbox")
    assert inbox.status_code == 200
    ib = inbox.json()
    assert "generated_at" in ib
    assert "counts" in ib and isinstance(ib["counts"], dict)
    for k in ("urgent", "attention", "info", "total_visible"):
        assert k in ib["counts"]
    assert isinstance(ib["items"], list)
    keys = {item["item_key"] for item in ib["items"]}
    assert f"approval:{approval_id}" in keys
    assert ib["counts"].get("approvals_pending", 0) >= 1


@pytest.mark.asyncio
async def test_post_receipt_round_trip(
    client: AsyncClient, api_headers: dict[str, str]
) -> None:
    """Receipts API persists and links to mission list."""
    cmd = await client.post(
        "/api/v1/commands",
        json={
            "text": "mission for receipt",
            "source": "api",
            "context": {
                "rehearsal_mode": "synthetic_api_only",
                "skip_runtime_publish": True,
            },
        },
        headers=api_headers,
    )
    assert cmd.status_code == 200
    mission_id = cmd.json()["mission_id"]

    rec = await client.post(
        "/api/v1/receipts",
        json={
            "mission_id": mission_id,
            "receipt_type": "pytest_contract",
            "source": "pytest",
            "payload": {"note": "contract test"},
            "summary": "pytest receipt summary",
        },
        headers=api_headers,
    )
    assert rec.status_code == 200
    row = rec.json()
    rid = row["id"]
    assert row["receipt_type"] == "pytest_contract"
    assert row["mission_id"] == mission_id

    one = await client.get(f"/api/v1/receipts/{rid}")
    assert one.status_code == 200
    assert one.json()["id"] == rid

    lst = await client.get(f"/api/v1/missions/{mission_id}/receipts")
    assert lst.status_code == 200
    ids = {r["id"] for r in lst.json()}
    assert rid in ids


@pytest.mark.asyncio
async def test_command_intake_dispatch_failure_is_durable_truth(
    client: AsyncClient, api_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redis publish failure must not look like a healthy pending runtime mission."""

    from app.services import command_service as cs

    async def fake_publish(*args: object, **kwargs: object) -> cs.JarvisCommandPublishResult:
        return cs.JarvisCommandPublishResult(
            ok=False,
            error_detail="connection refused",
            error_class="ConnectionError",
        )

    monkeypatch.setattr(cs, "_publish_jarvis_command", fake_publish)

    r = await client.post(
        "/api/v1/commands",
        json={"text": "pytest dispatch failure", "source": "api"},
        headers=api_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mission_status"] == "failed"
    assert "dispatch" in data["message"].lower()
    mid = UUID(data["mission_id"])

    er = await client.get(f"/api/v1/missions/{mid}/events")
    assert er.status_code == 200
    events: list[dict[str, Any]] = er.json()
    types = {e["event_type"] for e in events}
    assert "created" in types
    assert "runtime_dispatch_failed" in types
    assert "mission_status_changed" in types

    mr = await client.get(f"/api/v1/missions/{mid}")
    assert mr.status_code == 200
    assert mr.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_api_v1_system_health_includes_worker_registry(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: handler must define worker registry (DB-backed summary); never reference undefined locals."""

    async def _fake_postgres() -> ComponentHealth:
        return ComponentHealth(status="healthy", detail=None)

    async def _fake_redis(_url: str) -> ComponentHealth:
        return ComponentHealth(status="healthy", detail="PING ok")

    async def _fake_probe_http(_url: str) -> ComponentHealth:
        return ComponentHealth(status="healthy", detail="HTTP 200")

    async def _fake_probe_http_chain(_urls: list[str]) -> ComponentHealth:
        return ComponentHealth(status="healthy", detail="HTTP 200")

    monkeypatch.setattr(system_routes, "_check_postgres", _fake_postgres)
    monkeypatch.setattr(system_routes, "_check_redis", _fake_redis)
    monkeypatch.setattr(system_routes, "_probe_http", _fake_probe_http)
    monkeypatch.setattr(system_routes, "_probe_http_chain", _fake_probe_http_chain)

    r = await client.get("/api/v1/system/health")
    assert r.status_code == 200, r.text
    body = r.json()
    wr = body["worker_registry"]
    assert "registered_total" in wr
    assert "healthy_heartbeat" in wr
    assert "stale_or_absent" in wr
    assert "threshold_minutes" in wr
    assert body["control_plane"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_api_v1_approvals_pending_is_list(client: AsyncClient) -> None:
    r = await client.get("/api/v1/approvals/pending")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
