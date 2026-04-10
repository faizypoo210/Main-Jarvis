"""Mission event persistence."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mission_event import MissionEvent


class MissionEventRepository:
    """Async mission event queries."""

    @staticmethod
    async def create(
        db: AsyncSession,
        mission_id: UUID,
        event_type: str,
        actor_type: str | None = None,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MissionEvent:
        event = MissionEvent(
            mission_id=mission_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )
        db.add(event)
        await db.flush()
        await db.refresh(event)
        return event

    @staticmethod
    async def list_by_mission(db: AsyncSession, mission_id: UUID) -> list[MissionEvent]:
        stmt: Select[tuple[MissionEvent]] = (
            select(MissionEvent)
            .where(MissionEvent.mission_id == mission_id)
            .order_by(MissionEvent.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
