"""Mission timeline events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.mission import Mission


class MissionEvent(Base):
    __tablename__ = "mission_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("missions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    mission: Mapped["Mission"] = relationship("Mission", back_populates="events")
