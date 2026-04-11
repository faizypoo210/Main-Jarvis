"""Operator memory — durable context (v1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.schemas.memory import (
    MemoryCountsResponse,
    MemoryCreate,
    MemoryItemRead,
    MemoryListResponse,
    MemoryPatch,
    MissionMemoryPromote,
)
from app.services.memory_service import MemoryService

router = APIRouter()


@router.get("/operator/memory/counts", response_model=MemoryCountsResponse)
async def memory_counts(
    session: AsyncSession = Depends(get_db),
) -> MemoryCountsResponse:
    svc = MemoryService(session)
    return await svc.counts()


@router.get("/operator/memory", response_model=MemoryListResponse)
async def list_memory(
    session: AsyncSession = Depends(get_db),
    memory_type: str | None = Query(None),
    status: str | None = Query(None, pattern="^(active|archived)$"),
    q: str | None = Query(None, description="Search title/summary/content (substring)."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> MemoryListResponse:
    svc = MemoryService(session)
    return await svc.list_memory(
        memory_type=memory_type,
        status=status,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/operator/memory/{memory_id}", response_model=MemoryItemRead)
async def get_memory(
    memory_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> MemoryItemRead:
    svc = MemoryService(session)
    return await svc.get(memory_id)


@router.post("/operator/memory", response_model=MemoryItemRead)
async def create_memory(
    body: MemoryCreate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> MemoryItemRead:
    svc = MemoryService(session)
    return await svc.create_manual(body)


@router.patch("/operator/memory/{memory_id}", response_model=MemoryItemRead)
async def patch_memory(
    memory_id: UUID,
    body: MemoryPatch,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> MemoryItemRead:
    svc = MemoryService(session)
    return await svc.patch(memory_id, body)


@router.post("/operator/memory/promote-from-mission", response_model=MemoryItemRead)
async def promote_memory_from_mission(
    body: MissionMemoryPromote,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> MemoryItemRead:
    """Explicit promotion tied to a mission (operator-initiated; not automatic on mission status)."""
    svc = MemoryService(session)
    return await svc.promote_from_mission(body)
