"""Mission queries."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.approval_repo import ApprovalRepository
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository
from app.repositories.receipt_repo import ReceiptRepository
from app.schemas.approvals import ApprovalRead
from app.schemas.missions import MissionBundleRead, MissionRead
from app.schemas.receipts import ReceiptRead
from app.schemas.updates import MissionEventRead


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
