"""Persistence for operator inbox ack/snooze/dismiss (keyed by item_key)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operator_inbox_state import OperatorInboxState


class OperatorInboxStateRepository:
    @staticmethod
    async def get(db: AsyncSession, item_key: str) -> OperatorInboxState | None:
        r = await db.execute(select(OperatorInboxState).where(OperatorInboxState.item_key == item_key))
        return r.scalar_one_or_none()

    @staticmethod
    async def get_many(db: AsyncSession, item_keys: list[str]) -> dict[str, OperatorInboxState]:
        if not item_keys:
            return {}
        r = await db.execute(select(OperatorInboxState).where(OperatorInboxState.item_key.in_(item_keys)))
        rows = r.scalars().all()
        return {x.item_key: x for x in rows}

    @staticmethod
    async def upsert_acknowledge(db: AsyncSession, item_key: str) -> None:
        now = datetime.now(UTC)
        row = await OperatorInboxStateRepository.get(db, item_key)
        if row is None:
            db.add(
                OperatorInboxState(
                    item_key=item_key,
                    acknowledged_at=now,
                    snoozed_until=None,
                    updated_at=now,
                )
            )
        else:
            row.acknowledged_at = now
            row.snoozed_until = None
            row.updated_at = now
        await db.flush()

    @staticmethod
    async def upsert_snooze(db: AsyncSession, item_key: str, *, minutes: int) -> None:
        now = datetime.now(UTC)
        until: datetime | None = None if minutes <= 0 else now + timedelta(minutes=minutes)
        row = await OperatorInboxStateRepository.get(db, item_key)
        if row is None:
            db.add(
                OperatorInboxState(
                    item_key=item_key,
                    acknowledged_at=None,
                    snoozed_until=until,
                    updated_at=now,
                )
            )
        else:
            row.snoozed_until = until
            row.updated_at = now
        await db.flush()

    @staticmethod
    async def upsert_dismiss(db: AsyncSession, item_key: str) -> None:
        now = datetime.now(UTC)
        row = await OperatorInboxStateRepository.get(db, item_key)
        if row is None:
            db.add(
                OperatorInboxState(
                    item_key=item_key,
                    acknowledged_at=None,
                    snoozed_until=None,
                    dismissed_at=now,
                    updated_at=now,
                )
            )
        else:
            row.dismissed_at = now
            row.updated_at = now
        await db.flush()
