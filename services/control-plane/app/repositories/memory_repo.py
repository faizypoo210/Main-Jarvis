"""Memory item persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_item import MemoryItem


class MemoryRepository:
    @staticmethod
    async def create(db: AsyncSession, row: MemoryItem) -> MemoryItem:
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    @staticmethod
    async def get(db: AsyncSession, memory_id: uuid.UUID) -> MemoryItem | None:
        result = await db.execute(select(MemoryItem).where(MemoryItem.id == memory_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def count_filtered(
        db: AsyncSession,
        *,
        memory_type: str | None,
        status: str | None,
        q: str | None,
    ) -> int:
        stmt = select(func.count()).select_from(MemoryItem)
        stmt = MemoryRepository._apply_filters(stmt, memory_type=memory_type, status=status, q=q)
        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)

    @staticmethod
    def _apply_filters(
        stmt: Any,
        *,
        memory_type: str | None,
        status: str | None,
        q: str | None,
    ) -> Any:
        if memory_type is not None:
            stmt = stmt.where(MemoryItem.memory_type == memory_type)
        if status is not None:
            stmt = stmt.where(MemoryItem.status == status)
        if q is not None and str(q).strip():
            needle = f"%{str(q).strip()}%"
            stmt = stmt.where(
                or_(
                    MemoryItem.title.ilike(needle),
                    MemoryItem.summary.ilike(needle),
                    MemoryItem.content.ilike(needle),
                )
            )
        return stmt

    @staticmethod
    async def list_filtered(
        db: AsyncSession,
        *,
        memory_type: str | None,
        status: str | None,
        q: str | None,
        limit: int,
        offset: int,
    ) -> list[MemoryItem]:
        stmt: Select[tuple[MemoryItem]] = select(MemoryItem).order_by(
            MemoryItem.updated_at.desc(),
            MemoryItem.id.desc(),
        )
        stmt = MemoryRepository._apply_filters(stmt, memory_type=memory_type, status=status, q=q)
        stmt = stmt.offset(offset).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count_by_type_and_status(db: AsyncSession) -> tuple[dict[str, int], int, int]:
        r1 = await db.execute(
            select(MemoryItem.memory_type, func.count())
            .group_by(MemoryItem.memory_type)
        )
        by_type = {str(row[0]): int(row[1]) for row in r1.fetchall()}
        r2 = await db.execute(
            select(MemoryItem.status, func.count()).group_by(MemoryItem.status)
        )
        st = {str(row[0]): int(row[1]) for row in r2.fetchall()}
        active = st.get("active", 0)
        archived = st.get("archived", 0)
        return by_type, active, archived
