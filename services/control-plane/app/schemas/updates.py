"""Outbox / updates stream schemas (future Redis bridge)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class UpdatesStatus(BaseModel):
    status: str = "ok"
    note: str = "Use GET /api/v1/updates/stream (SSE) for live mission_event and mission snapshots."


class MissionEventRead(BaseModel):
    id: UUID
    mission_id: UUID
    event_type: str
    actor_type: str | None
    actor_id: str | None
    payload: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
