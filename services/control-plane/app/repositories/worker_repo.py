"""Worker registry persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.worker import Worker


class WorkerRepository:
    @staticmethod
    async def get_by_type_instance(
        session: AsyncSession, *, worker_type: str, instance_id: str
    ) -> Worker | None:
        r = await session.execute(
            select(Worker).where(
                Worker.worker_type == worker_type,
                Worker.instance_id == instance_id,
            )
        )
        return r.scalar_one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession) -> list[Worker]:
        r = await session.execute(
            select(Worker).order_by(Worker.worker_type, Worker.instance_id)
        )
        return list(r.scalars().all())
