"""Mission schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.approvals import ApprovalRead
from app.schemas.receipts import ReceiptRead
from app.schemas.updates import MissionEventRead


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


class MissionStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=64)


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


class MissionBundleRead(BaseModel):
    """Single response for mission detail first paint (mission + timeline + approvals + receipts)."""

    mission: MissionRead
    events: list[MissionEventRead]
    approvals: list[ApprovalRead]
    receipts: list[ReceiptRead]
