"""Receipt domain: record execution receipts and timeline events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt import Receipt
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository
from app.repositories.receipt_repo import ReceiptRepository
from app.services.memory_service import try_promote_from_receipt


class ReceiptService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._mission_repo = MissionRepository(session)

    async def record_receipt(
        self,
        mission_id: UUID | None,
        receipt_type: str,
        source: str,
        payload: dict[str, Any],
        summary: str | None = None,
    ) -> Receipt:
        if mission_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="mission_id is required to record a receipt with a mission event",
            )
        mission = await self._mission_repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )

        receipt = await ReceiptRepository.create(
            self._session,
            mission_id=mission_id,
            receipt_type=receipt_type,
            source=source,
            payload=payload,
            summary=summary,
        )
        # Always include summary key so clients avoid fragile None/omit branching.
        ev_payload: dict[str, Any] = {
            "receipt_type": receipt_type,
            "source": source,
            "summary": summary if summary is not None else "",
        }
        em = payload.get("execution_meta")
        if isinstance(em, dict):
            ev_payload["execution_meta"] = em
        await MissionEventRepository.create(
            self._session,
            mission_id=mission_id,
            event_type="receipt_recorded",
            payload=ev_payload,
        )
        await try_promote_from_receipt(self._session, receipt, mission_id)
        return receipt
