"""Queue canonical mission/event snapshots for broadcast after successful DB commit."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mission import Mission
from app.models.mission_event import MissionEvent
from app.schemas.missions import MissionRead
from app.schemas.updates import MissionEventRead

_REALTIME_KEY = "realtime_emit"


def queue_mission_event(session: AsyncSession, event: MissionEvent) -> None:
    read = MissionEventRead.model_validate(event)
    session.info.setdefault(_REALTIME_KEY, []).append(
        {"type": "mission_event", "event": read.model_dump(mode="json")}
    )


def queue_mission_snapshot(session: AsyncSession, mission: Mission) -> None:
    read = MissionRead.model_validate(mission)
    session.info.setdefault(_REALTIME_KEY, []).append(
        {"type": "mission", "mission": read.model_dump(mode="json")}
    )
