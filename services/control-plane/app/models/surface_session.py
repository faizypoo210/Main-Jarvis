"""Surface (voice, UI, SMS) session state."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SurfaceSession(Base):
    __tablename__ = "surface_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    surface_type: Mapped[str] = mapped_column(String(32), nullable=False)
    user_identity: Mapped[str | None] = mapped_column(String(512), nullable=True)
    trust_level: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    session_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
