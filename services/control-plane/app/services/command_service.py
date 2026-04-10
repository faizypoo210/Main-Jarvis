"""Command intake — always creates mission + mission_event."""

from __future__ import annotations

import json

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.mission import Mission
from app.repositories.mission_repo import MissionRepository
from app.schemas.commands import CommandCreate, CommandResponse
from app.services.event_service import EventService

STREAM_COMMANDS = "jarvis.commands"

log = get_logger(__name__)


async def _publish_jarvis_command(
    mission_id: str,
    text: str,
    created_by: str,
) -> None:
    settings = get_settings()
    url = settings.REDIS_URL or "redis://localhost:6379"
    payload = {
        "mission_id": mission_id,
        "text": text,
        "created_by": created_by,
    }
    r: Redis | None = None
    try:
        r = Redis.from_url(url, decode_responses=False)
        await r.xadd(STREAM_COMMANDS, {"data": json.dumps(payload)})
    except Exception as e:
        log.warning("redis jarvis.commands publish failed: %s", e)
    finally:
        if r is not None:
            await r.close()


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

        await self._session.commit()

        await _publish_jarvis_command(
            str(mission.id),
            data.text,
            data.source,
        )

        return CommandResponse(
            mission_id=mission.id,
            mission_status=mission.status,
            message="Mission created and recorded.",
        )
