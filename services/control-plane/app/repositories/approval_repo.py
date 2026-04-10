"""Approval persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval


class ApprovalRepository:
    """Async approval queries."""

    @staticmethod
    async def create(
        db: AsyncSession,
        mission_id: UUID,
        action_type: str,
        risk_class: str,
        reason: str | None,
        requested_by: str,
        requested_via: str,
        expires_at: datetime | None = None,
    ) -> Approval:
        approval = Approval(
            mission_id=mission_id,
            action_type=action_type,
            risk_class=risk_class,
            reason=reason,
            status="pending",
            requested_by=requested_by,
            requested_via=requested_via,
            expires_at=expires_at,
        )
        db.add(approval)
        await db.flush()
        await db.refresh(approval)
        return approval

    @staticmethod
    async def get(db: AsyncSession, approval_id: UUID) -> Approval | None:
        result = await db.execute(select(Approval).where(Approval.id == approval_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_pending(db: AsyncSession, limit: int = 50) -> list[Approval]:
        stmt: Select[tuple[Approval]] = (
            select(Approval)
            .where(Approval.status == "pending")
            .order_by(Approval.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_decision(
        db: AsyncSession,
        approval_id: UUID,
        status: str,
        decided_by: str,
        decided_via: str,
        decision_notes: str | None = None,
    ) -> Approval | None:
        approval = await ApprovalRepository.get(db, approval_id)
        if approval is None:
            return None
        approval.status = status
        approval.decided_by = decided_by
        approval.decided_via = decided_via
        approval.decision_notes = decision_notes
        approval.decided_at = datetime.now(UTC)
        await db.flush()
        await db.refresh(approval)
        return approval
