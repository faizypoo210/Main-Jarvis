"""Mission queries."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.schemas.approvals import ApprovalRead
from app.schemas.missions import (
    MissionBundleRead,
    MissionEventCreate,
    MissionRead,
    MissionStatusUpdate,
)
from app.schemas.receipts import ReceiptRead
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


@router.post("/{mission_id}/status", response_model=MissionRead)
async def post_mission_status(
    mission_id: UUID,
    body: MissionStatusUpdate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> MissionRead:
    svc = MissionService(session)
    return await svc.update_mission_status(mission_id, body.status)


@router.get("/{mission_id}/events", response_model=list[MissionEventRead])
async def list_mission_events(
    mission_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[MissionEventRead]:
    svc = MissionService(session)
    return await svc.list_mission_events(mission_id)


@router.post("/{mission_id}/events", response_model=MissionEventRead)
async def post_mission_event(
    mission_id: UUID,
    body: MissionEventCreate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> MissionEventRead:
    """Append a mission event (workers: coordinator, etc.)."""
    svc = MissionService(session)
    return await svc.create_mission_event(mission_id, body)


@router.get("/{mission_id}/approvals", response_model=list[ApprovalRead])
async def list_mission_approvals(
    mission_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ApprovalRead]:
    svc = MissionService(session)
    return await svc.list_mission_approvals(mission_id)


@router.get("/{mission_id}/receipts", response_model=list[ReceiptRead])
async def list_mission_receipts(
    mission_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ReceiptRead]:
    svc = MissionService(session)
    return await svc.list_mission_receipts(mission_id)


@router.get("/{mission_id}/bundle", response_model=MissionBundleRead)
async def get_mission_bundle(
    mission_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> MissionBundleRead:
    svc = MissionService(session)
    return await svc.get_mission_bundle(mission_id)


@router.get("/{mission_id}", response_model=MissionRead)
async def get_mission(
    mission_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> MissionRead:
    svc = MissionService(session)
    return await svc.get_mission(mission_id)
