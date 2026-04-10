"""Approval domain: requests and decisions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval
from app.repositories.approval_repo import ApprovalRepository
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._mission_repo = MissionRepository(session)

    async def request_approval(
        self,
        mission_id: UUID,
        action_type: str,
        risk_class: str,
        reason: str | None,
        requested_by: str,
        requested_via: str,
        expires_at: datetime | None = None,
    ) -> Approval:
        mission = await self._mission_repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )

        approval = await ApprovalRepository.create(
            self._session,
            mission_id=mission_id,
            action_type=action_type,
            risk_class=risk_class,
            reason=reason,
            requested_by=requested_by,
            requested_via=requested_via,
            expires_at=expires_at,
        )
        await MissionEventRepository.create(
            self._session,
            mission_id=mission_id,
            event_type="approval_requested",
            payload={"action_type": action_type, "risk_class": risk_class},
        )
        await self._mission_repo.update_status(mission_id, "awaiting_approval")
        return approval

    async def resolve_approval(
        self,
        approval_id: UUID,
        decision: str,
        decided_by: str,
        decided_via: str,
        decision_notes: str | None = None,
    ) -> Approval:
        approval = await ApprovalRepository.get(self._session, approval_id)
        if approval is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval not found",
            )
        if approval.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approval is not in pending status",
            )
        if decision not in ("approved", "denied"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="decision must be approved or denied",
            )

        updated = await ApprovalRepository.update_decision(
            self._session,
            approval_id=approval_id,
            status=decision,
            decided_by=decided_by,
            decided_via=decided_via,
            decision_notes=decision_notes,
        )
        assert updated is not None

        await MissionEventRepository.create(
            self._session,
            mission_id=approval.mission_id,
            event_type="approval_resolved",
            payload={"decision": decision, "decided_by": decided_by},
        )

        if decision == "approved":
            await self._mission_repo.update_status(approval.mission_id, "active")
        else:
            await self._mission_repo.update_status(approval.mission_id, "blocked")

        return updated
