"""Operator system health: compact probes (no secrets)."""

from __future__ import annotations

import asyncio
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import engine, get_db
from app.schemas.system import ComponentHealth, SystemHealthResponse
from app.schemas.workers import WorkerRegistrySummary
from app.services.worker_registry_service import build_registry_summary

router = APIRouter()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


async def _check_postgres() -> ComponentHealth:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return ComponentHealth(status="healthy", detail=None)
    except Exception as e:
        return ComponentHealth(status="offline", detail=str(e)[:200])


async def _check_redis(url: str) -> ComponentHealth:
    r = Redis.from_url(url, decode_responses=True)
    try:
        await asyncio.wait_for(r.ping(), timeout=2.0)
        return ComponentHealth(status="healthy", detail="PING ok")
    except Exception as e:
        return ComponentHealth(status="offline", detail=str(e)[:200])
    finally:
        await r.close()


def _http_probe_sync(url: str, timeout: float = 2.0) -> ComponentHealth:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            if isinstance(code, int) and code < 500:
                return ComponentHealth(status="healthy", detail=f"HTTP {code}")
            return ComponentHealth(status="degraded", detail=f"HTTP {code}")
    except urllib.error.HTTPError as e:
        if e.code < 500:
            return ComponentHealth(status="healthy", detail=f"HTTP {e.code}")
        return ComponentHealth(status="degraded", detail=f"HTTP {e.code}")
    except Exception as e:
        return ComponentHealth(status="offline", detail=str(e)[:200])


async def _probe_http(url: str) -> ComponentHealth:
    return await asyncio.to_thread(_http_probe_sync, url)


def _worker_stale_threshold_minutes() -> float:
    raw = os.environ.get("HEARTBEAT_WORKER_STALE_MINUTES", "").strip()
    if not raw:
        return 15.0
    try:
        return float(raw)
    except ValueError:
        return 15.0


async def _probe_http_chain(urls: list[str]) -> ComponentHealth:
    last = ComponentHealth(status="unknown", detail="no probe URLs")
    for u in urls:
        if not u.strip():
            continue
        h = await _probe_http(u.strip())
        if h.status in ("healthy", "degraded"):
            return h
        last = h
    return last


@router.get("/system/health", response_model=SystemHealthResponse)
async def system_health() -> SystemHealthResponse:
    """Aggregated health for Command Center operator surfaces."""
    settings = get_settings()
    checked = _utc_now_iso()

    postgres = await _check_postgres()
    redis_url = settings.REDIS_URL or "redis://localhost:6379"
    redis = await _check_redis(redis_url)

    gw_urls = [
        settings.JARVIS_HEALTH_OPENCLAW_GATEWAY_URL.strip(),
        "http://127.0.0.1:18789/",
    ]
    # Dedupe while preserving order
    seen: set[str] = set()
    gw_urls_unique: list[str] = []
    for u in gw_urls:
        if u and u not in seen:
            seen.add(u)
            gw_urls_unique.append(u)
    gateway = await _probe_http_chain(gw_urls_unique)

    ollama = await _probe_http(settings.JARVIS_HEALTH_OLLAMA_URL.strip())

    return SystemHealthResponse(
        checked_at=checked,
        control_plane=ComponentHealth(
            status="healthy",
            detail="API responding",
        ),
        postgres=postgres,
        redis=redis,
        openclaw_gateway=gateway,
        ollama=ollama,
        worker_registry=wr,
    )
