"""Approval reminder / escalation row queries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval_reminder import ApprovalReminder


class ApprovalReminderRepository:
    @staticmethod
    async def get_by_dedupe_key(
        db: AsyncSession, dedupe_key: str
    ) -> ApprovalReminder | None:
        r = await db.execute(
            select(ApprovalReminder).where(ApprovalReminder.dedupe_key == dedupe_key)
        )
        return r.scalar_one_or_none()

    @staticmethod
    async def count_reminder_rows(db: AsyncSession, approval_id: UUID) -> int:
        r = await db.execute(
            select(func.count())
            .select_from(ApprovalReminder)
            .where(
                ApprovalReminder.approval_id == approval_id,
                ApprovalReminder.notification_type == "reminder",
            )
        )
        return int(r.scalar_one() or 0)

    @staticmethod
    async def last_reminder_attempt_at(
        db: AsyncSession, approval_id: UUID
    ) -> datetime | None:
        r = await db.execute(
            select(func.max(ApprovalReminder.last_attempt_at))
            .where(
                ApprovalReminder.approval_id == approval_id,
                ApprovalReminder.notification_type == "reminder",
            )
        )
        return r.scalar_one_or_none()

    @staticmethod
    async def has_escalation_row(db: AsyncSession, approval_id: UUID) -> bool:
        r = await db.execute(
            select(func.count())
            .select_from(ApprovalReminder)
            .where(
                ApprovalReminder.approval_id == approval_id,
                ApprovalReminder.notification_type == "escalation",
            )
        )
        return int(r.scalar_one() or 0) > 0

    @staticmethod
    async def aggregate_for_approval(db: AsyncSession, approval_id: UUID) -> dict:
        r_rem = await db.execute(
            select(func.count())
            .select_from(ApprovalReminder)
            .where(
                ApprovalReminder.approval_id == approval_id,
                ApprovalReminder.notification_type == "reminder",
                ApprovalReminder.status == "sent",
            )
        )
        r_esc = await db.execute(
            select(func.count())
            .select_from(ApprovalReminder)
            .where(
                ApprovalReminder.approval_id == approval_id,
                ApprovalReminder.notification_type == "escalation",
                ApprovalReminder.status == "sent",
            )
        )
        r_lr = await db.execute(
            select(func.max(ApprovalReminder.sent_at)).where(
                ApprovalReminder.approval_id == approval_id,
                ApprovalReminder.notification_type == "reminder",
                ApprovalReminder.status == "sent",
                ApprovalReminder.sent_at.isnot(None),
            )
        )
        r_le = await db.execute(
            select(func.max(ApprovalReminder.sent_at)).where(
                ApprovalReminder.approval_id == approval_id,
                ApprovalReminder.notification_type == "escalation",
                ApprovalReminder.status == "sent",
                ApprovalReminder.sent_at.isnot(None),
            )
        )
        r_la = await db.execute(
            select(func.max(ApprovalReminder.last_attempt_at)).where(
                ApprovalReminder.approval_id == approval_id,
            )
        )
        return {
            "reminder_sent_count": int(r_rem.scalar_one() or 0),
            "escalation_sent": int(r_esc.scalar_one() or 0) > 0,
            "last_reminder_at": r_lr.scalar_one_or_none(),
            "last_escalation_at": r_le.scalar_one_or_none(),
            "last_attempt_at": r_la.scalar_one_or_none(),
        }

    @staticmethod
    async def latest_row(db: AsyncSession, approval_id: UUID) -> ApprovalReminder | None:
        r = await db.execute(
            select(ApprovalReminder)
            .where(ApprovalReminder.approval_id == approval_id)
            .order_by(ApprovalReminder.created_at.desc())
            .limit(1)
        )
        return r.scalar_one_or_none()
