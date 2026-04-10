"""Mission queries."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.missions import MissionRead
from app.schemas.updates import MissionEventRead
from app.services.mission_service import MissionService

router = APIRouter()


@router.get("", response_model=list[MissionRead])
async def list_missions(
    status: str | None = Query(None),
    created_by: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[MissionRead]:
    svc = MissionService(session)
    return await svc.list_missions(
        status=status,
        created_by=created_by,
        limit=limit,
        offset=offset,
    )


@router.get("/{mission_id}/events", response_model=list[MissionEventRead])
async def list_mission_events(
    mission_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[MissionEventRead]:
    svc = MissionService(session)
    return await svc.list_mission_events(mission_id)


@router.get("/{mission_id}", response_model=MissionRead)
async def get_mission(
    mission_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> MissionRead:
    svc = MissionService(session)
    return await svc.get_mission(mission_id)
