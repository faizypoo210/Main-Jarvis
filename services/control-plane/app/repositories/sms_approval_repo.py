"""SMS approval token persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval_sms_token import ApprovalSmsToken


class SmsApprovalRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        approval_id: UUID,
        sms_code: str,
        phone_hint: str | None,
    ) -> ApprovalSmsToken:
        row = ApprovalSmsToken(
            approval_id=approval_id,
            sms_code=sms_code.upper(),
            status="pending",
            phone_hint=phone_hint,
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    @staticmethod
    async def get_by_code(
        db: AsyncSession, sms_code: str, *, pending_only: bool = True
    ) -> ApprovalSmsToken | None:
        c = sms_code.strip().upper()
        stmt = select(ApprovalSmsToken).where(ApprovalSmsToken.sms_code == c)
        if pending_only:
            stmt = stmt.where(ApprovalSmsToken.status == "pending")
        r = await db.execute(stmt)
        return r.scalar_one_or_none()

    @staticmethod
    async def get_by_approval_id(db: AsyncSession, approval_id: UUID) -> ApprovalSmsToken | None:
        r = await db.execute(
            select(ApprovalSmsToken).where(ApprovalSmsToken.approval_id == approval_id)
        )
        return r.scalar_one_or_none()

    @staticmethod
    async def mark_sent(db: AsyncSession, token_id: UUID, *, note: str | None) -> None:
        await db.execute(
            update(ApprovalSmsToken)
            .where(ApprovalSmsToken.id == token_id)
            .values(
                last_sent_at=datetime.now(UTC),
                outbound_note=note,
            )
        )

    @staticmethod
    async def mark_inbound(db: AsyncSession, token_id: UUID, *, note: str | None) -> None:
        await db.execute(
            update(ApprovalSmsToken)
            .where(ApprovalSmsToken.id == token_id)
            .values(
                last_inbound_at=datetime.now(UTC),
                inbound_note=note,
            )
        )

    @staticmethod
    async def mark_used(db: AsyncSession, token_id: UUID) -> None:
        await db.execute(
            update(ApprovalSmsToken).where(ApprovalSmsToken.id == token_id).values(status="used")
        )
