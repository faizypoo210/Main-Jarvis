"""Command intake — always creates mission + mission_event."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.mission_repo import MissionRepository
from app.schemas.commands import CommandCreate, CommandResponse
from app.services.event_service import EventService
from app.models.mission import Mission


class CommandService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._missions = MissionRepository(session)
        self._events = EventService(session)

    async def intake(self, data: CommandCreate) -> CommandResponse:
        raw = data.text.strip()
        title = raw[:512] if len(raw) <= 512 else raw[:509] + "..."
        if not title:
            title = "(empty command)"

        mission = Mission(
            title=title,
            description=None,
            status="pending",
            priority="normal",
            created_by=data.source,
            surface_origin=data.source,
            risk_class=None,
            current_stage=None,
            summary=None,
        )
        await self._missions.create(mission)

        payload: dict[str, object] = {"text": data.text}
        if data.context is not None:
            payload["context"] = data.context
        if data.surface_session_id is not None:
            payload["surface_session_id"] = str(data.surface_session_id)

        await self._events.record_event(
            mission_id=mission.id,
            event_type="created",
            actor_type="surface",
            actor_id=data.source,
            payload=payload,
        )

        return CommandResponse(
            mission_id=mission.id,
            mission_status=mission.status,
            message="Mission created and recorded.",
        )
