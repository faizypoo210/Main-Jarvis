"""Operator system health: compact probes (no secrets)."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import engine, get_db
from app.repositories.worker_repo import WorkerRepository
from app.schemas.system import ComponentHealth, SystemHealthResponse
from app.services.system_execution_health import (
    PROBE_CONTROL_PLANE_LOCAL,
    ollama_health,
    openclaw_gateway_health,
)
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


def _worker_stale_threshold_minutes() -> float:
    raw = os.environ.get("HEARTBEAT_WORKER_STALE_MINUTES", "").strip()
    if not raw:
        return 15.0
    try:
        return float(raw)
    except ValueError:
        return 15.0


@router.get("/system/health", response_model=SystemHealthResponse)
async def system_health(
    session: AsyncSession = Depends(get_db),
) -> SystemHealthResponse:
    """Aggregated health for Command Center operator surfaces."""
    settings = get_settings()
    checked = _utc_now_iso()

    threshold = _worker_stale_threshold_minutes()
    worker_registry = await build_registry_summary(
        session, threshold_minutes=threshold
    )

    workers = await WorkerRepository.list_all(session)

    postgres = await _check_postgres()
    redis_url = settings.REDIS_URL or "redis://localhost:6379"
    redis = await _check_redis(redis_url)

    gateway = await openclaw_gateway_health(
        configured_gateway_url=settings.JARVIS_HEALTH_OPENCLAW_GATEWAY_URL,
        workers=workers,
    )
    ollama = await ollama_health(
        configured_ollama_url=settings.JARVIS_HEALTH_OLLAMA_URL,
        workers=workers,
    )

    return SystemHealthResponse(
        checked_at=checked,
        control_plane=ComponentHealth(
            status="healthy",
            detail="API responding",
            probe_source=PROBE_CONTROL_PLANE_LOCAL,
        ),
        postgres=ComponentHealth(
            status=postgres.status,
            detail=postgres.detail,
            probe_source=PROBE_CONTROL_PLANE_LOCAL,
        ),
        redis=ComponentHealth(
            status=redis.status,
            detail=redis.detail,
            probe_source=PROBE_CONTROL_PLANE_LOCAL,
        ),
        openclaw_gateway=gateway,
        ollama=ollama,
        worker_registry=worker_registry,
    )
