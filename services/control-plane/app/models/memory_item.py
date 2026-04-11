"""Durable operator memory — separate from mission aggregate state."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.mission import Mission
    from app.models.mission_event import MissionEvent
    from app.models.receipt import Receipt


class MemoryItem(Base):
    """Long-lived context for operators — not mission logs or chat transcripts."""

    __tablename__ = "memory_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("missions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("receipts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mission_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    dedupe_key: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    mission: Mapped["Mission | None"] = relationship("Mission", foreign_keys=[source_mission_id])
    receipt: Mapped["Receipt | None"] = relationship("Receipt", foreign_keys=[source_receipt_id])
    source_event: Mapped["MissionEvent | None"] = relationship(
        "MissionEvent", foreign_keys=[source_event_id]
    )
