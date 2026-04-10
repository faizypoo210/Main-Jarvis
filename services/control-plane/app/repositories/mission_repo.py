"""Mission persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mission import Mission


class MissionRepository:
    """Async mission queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, mission: Mission) -> Mission:
        self._session.add(mission)
        await self._session.flush()
        await self._session.refresh(mission)
        return mission

    async def get_by_id(self, mission_id: UUID) -> Mission | None:
        result = await self._session.execute(
            select(Mission).where(Mission.id == mission_id)
        )
        return result.scalar_one_or_none()

    async def list_missions(
        self,
        *,
        status: str | None = None,
        created_by: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Mission]:
        stmt: Select[tuple[Mission]] = select(Mission).order_by(Mission.created_at.desc())
        if status is not None:
            stmt = stmt.where(Mission.status == status)
        if created_by is not None:
            stmt = stmt.where(Mission.created_by == created_by)
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, mission_id: UUID, status: str) -> Mission | None:
        mission = await self.get_by_id(mission_id)
        if mission is None:
            return None
        mission.status = status
        await self._session.flush()
        await self._session.refresh(mission)
        return mission
