"""Worker registry — register + heartbeat (API key)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.schemas.workers import WorkerHeartbeatRequest, WorkerRead, WorkerRegisterRequest
from app.services.worker_registry_service import heartbeat_worker, register_worker

router = APIRouter()


@router.post(
    "/workers/register",
    response_model=WorkerRead,
    summary="Register or refresh a worker row (idempotent upsert)",
)
async def workers_register(
    body: WorkerRegisterRequest,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> WorkerRead:
    row = await register_worker(session, body)
    await session.commit()
    return row


@router.post(
    "/workers/heartbeat",
    response_model=WorkerRead,
    summary="Worker heartbeat — updates last_heartbeat_at and status",
)
async def workers_heartbeat(
    body: WorkerHeartbeatRequest,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> WorkerRead:
    row = await heartbeat_worker(session, body)
    await session.commit()
    return row
