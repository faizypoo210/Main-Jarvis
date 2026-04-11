"""Mission event creation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mission_event import MissionEvent
from app.realtime.emit import queue_mission_event


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_event(
        self,
        *,
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
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        queue_mission_event(self._session, event)
        return event
