"""Mission schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MissionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: str | None = None
    status: str = Field(default="pending")
    priority: str = Field(default="normal")
    created_by: str
    surface_origin: str | None = None
    risk_class: str | None = None
    current_stage: str | None = None
    summary: str | None = None


class MissionRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: str
    priority: str
    created_by: str
    surface_origin: str | None
    risk_class: str | None
    current_stage: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
