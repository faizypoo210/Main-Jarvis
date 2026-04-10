"""Receipt persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt import Receipt


class ReceiptRepository:
    """Async receipt queries."""

    @staticmethod
    async def create(
        db: AsyncSession,
        mission_id: UUID | None,
        receipt_type: str,
        source: str,
        payload: dict,
        summary: str | None = None,
    ) -> Receipt:
        receipt = Receipt(
            mission_id=mission_id,
            receipt_type=receipt_type,
            source=source,
            payload=payload,
            summary=summary,
        )
        db.add(receipt)
        await db.flush()
        await db.refresh(receipt)
        return receipt

    @staticmethod
    async def get(db: AsyncSession, receipt_id: UUID) -> Receipt | None:
        result = await db.execute(select(Receipt).where(Receipt.id == receipt_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_mission(db: AsyncSession, mission_id: UUID) -> list[Receipt]:
        stmt: Select[tuple[Receipt]] = (
            select(Receipt)
            .where(Receipt.mission_id == mission_id)
            .order_by(Receipt.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
