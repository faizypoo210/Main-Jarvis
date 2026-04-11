"""Heartbeat finding persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heartbeat_finding import HeartbeatFinding


class HeartbeatFindingRepository:
    @staticmethod
    async def get_by_dedupe_key(db: AsyncSession, dedupe_key: str) -> HeartbeatFinding | None:
        result = await db.execute(
            select(HeartbeatFinding).where(HeartbeatFinding.dedupe_key == dedupe_key)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_open(db: AsyncSession) -> list[HeartbeatFinding]:
        stmt: Select[tuple[HeartbeatFinding]] = (
            select(HeartbeatFinding)
            .where(HeartbeatFinding.status == "open")
            .order_by(HeartbeatFinding.last_seen_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_resolved_cost_findings_recent(
        db: AsyncSession,
        *,
        limit: int = 8,
    ) -> list[HeartbeatFinding]:
        stmt = (
            select(HeartbeatFinding)
            .where(
                and_(
                    HeartbeatFinding.status == "resolved",
                    HeartbeatFinding.resolved_at.isnot(None),
                    HeartbeatFinding.finding_type.op("~")("^cost_"),
                )
            )
            .order_by(HeartbeatFinding.resolved_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_open_recent(
        db: AsyncSession,
        *,
        limit: int,
        before: datetime | None,
    ) -> list[HeartbeatFinding]:
        stmt = select(HeartbeatFinding).where(HeartbeatFinding.status == "open")
        if before is not None:
            stmt = stmt.where(HeartbeatFinding.last_seen_at < before)
        stmt = stmt.order_by(HeartbeatFinding.last_seen_at.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def save(db: AsyncSession, row: HeartbeatFinding) -> HeartbeatFinding:
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row
