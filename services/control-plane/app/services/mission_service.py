"""Mission queries."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.approval_repo import ApprovalRepository
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository
from app.repositories.receipt_repo import ReceiptRepository
from app.schemas.approvals import ApprovalRead
from app.schemas.missions import (
    MissionBundleRead,
    MissionEventCreate,
    MissionRead,
    MissionStagesPatchBody,
    MissionStatusUpdate,
    _validate_stage_items,
)
from app.schemas.receipts import ReceiptRead
from app.schemas.updates import MissionEventRead
from app.services.mission_planner import plan_mission


class MissionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MissionRepository(session)

    async def list_missions(
        self,
        *,
        status: str | None,
        created_by: str | None,
        limit: int,
        offset: int,
    ) -> list[MissionRead]:
        rows = await self._repo.list_missions(
            status=status,
            created_by=created_by,
            limit=limit,
            offset=offset,
        )
        return [MissionRead.model_validate(m) for m in rows]

    async def get_mission(self, mission_id: UUID) -> MissionRead:
        mission = await self._repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        return MissionRead.model_validate(mission)

    async def update_mission_stages(
        self, mission_id: UUID, body: MissionStagesPatchBody
    ) -> MissionRead:
        normalized = _validate_stage_items(body.stages)
        if body.stages and not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No valid stages in payload",
            )
        to_store: list[dict[str, Any]] | None = normalized if normalized else None
        mission = await self._repo.update_stages(mission_id, to_store)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        return MissionRead.model_validate(mission)

    async def plan_and_save_stages(self, mission_id: UUID, command: str) -> list[dict[str, Any]]:
        cmd = (command or "").strip()
        if not cmd:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="command query parameter is required",
            )
        mission = await self._repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        planned = await plan_mission(cmd, str(mission_id))
        normalized = _validate_stage_items(planned)
        if not normalized:
            normalized = _validate_stage_items(
                [{"id": "stage-1", "title": cmd, "status": "pending"}]
            )
        updated = await self._repo.update_stages(mission_id, normalized)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        return normalized

    async def list_mission_events(self, mission_id: UUID) -> list[MissionEventRead]:
        mission = await self._repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        rows = await MissionEventRepository.list_by_mission(self._session, mission_id)
        return [MissionEventRead.model_validate(e) for e in rows]

    async def list_mission_approvals(self, mission_id: UUID) -> list[ApprovalRead]:
        mission = await self._repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        rows = await ApprovalRepository.list_by_mission(self._session, mission_id)
        return [ApprovalRead.model_validate(a) for a in rows]

    async def list_mission_receipts(self, mission_id: UUID) -> list[ReceiptRead]:
        mission = await self._repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        rows = await ReceiptRepository.list_by_mission(self._session, mission_id)
        return [ReceiptRead.model_validate(r) for r in rows]

    async def get_mission_bundle(self, mission_id: UUID) -> MissionBundleRead:
        mission = await self._repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        events = await MissionEventRepository.list_by_mission(self._session, mission_id)
        approvals = await ApprovalRepository.list_by_mission(self._session, mission_id)
        receipts = await ReceiptRepository.list_by_mission(self._session, mission_id)
        return MissionBundleRead(
            mission=MissionRead.model_validate(mission),
            events=[MissionEventRead.model_validate(e) for e in events],
            approvals=[ApprovalRead.model_validate(a) for a in approvals],
            receipts=[ReceiptRead.model_validate(r) for r in receipts],
        )

    async def update_mission_status(self, mission_id: UUID, status: str) -> MissionRead:
        mission = await self._repo.update_status(mission_id, status)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        return MissionRead.model_validate(mission)

    async def create_mission_event(
        self,
        mission_id: UUID,
        body: MissionEventCreate,
    ) -> MissionEventRead:
        mission = await self._repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )
        event = await MissionEventRepository.create(
            self._session,
            mission_id=mission_id,
            event_type=body.event_type,
            actor_type=body.actor_type,
            actor_id=body.actor_id,
            payload=body.payload,
        )
        return MissionEventRead.model_validate(event)
