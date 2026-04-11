"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.realtime.hub import get_hub

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: commit on success, rollback on error."""
    async with async_session_maker() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
            pending_sms = session.info.pop("approval_sms_queue", [])
            pending = session.info.pop("realtime_emit", [])
            if pending_sms:
                from app.services.sms_approval_service import process_approval_sms_queue

                await process_approval_sms_queue([UUID(x) for x in pending_sms])
            if pending:
                hub = get_hub()
                await hub.broadcast_all(pending)
        except Exception:
            await session.rollback()
            raise
