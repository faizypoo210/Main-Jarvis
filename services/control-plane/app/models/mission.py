"""Mission aggregate root."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.approval import Approval
    from app.models.cost_event import CostEvent
    from app.models.mission_event import MissionEvent
    from app.models.receipt import Receipt


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    surface_origin: Mapped[str | None] = mapped_column(String(256), nullable=True)
    risk_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_stage: Mapped[str | None] = mapped_column(String(256), nullable=True)
    stages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    events: Mapped[list["MissionEvent"]] = relationship(
        "MissionEvent", back_populates="mission", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        "Approval", back_populates="mission", cascade="all, delete-orphan"
    )
    receipts: Mapped[list["Receipt"]] = relationship(
        "Receipt", back_populates="mission"
    )
    cost_events: Mapped[list["CostEvent"]] = relationship(
        "CostEvent", back_populates="mission"
    )
