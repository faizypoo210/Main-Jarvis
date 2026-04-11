"""Heartbeat supervision — run cycle + operator snapshot."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.schemas.heartbeat import HeartbeatOperatorResponse, HeartbeatRunResponse
from app.services.heartbeat_service import build_operator_snapshot, run_heartbeat_cycle

router = APIRouter()


@router.get("/operator/heartbeat", response_model=HeartbeatOperatorResponse)
async def operator_heartbeat(
    session: AsyncSession = Depends(get_db),
) -> HeartbeatOperatorResponse:
    """Open heartbeat findings and counts (quiet when nothing is open)."""
    return await build_operator_snapshot(session)


@router.post("/heartbeat/run", response_model=HeartbeatRunResponse)
async def heartbeat_run(
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> HeartbeatRunResponse:
    """Evaluate supervision rules and sync findings (heartbeat worker)."""
    return await run_heartbeat_cycle(session)
