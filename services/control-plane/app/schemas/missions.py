"""Mission schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import Any

from pydantic import BaseModel, Field, field_validator

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


_STAGE_STATUSES = frozenset({"pending", "active", "complete", "failed"})


def _validate_stage_items(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in stages:
        if not isinstance(raw, dict):
            continue
        sid = raw.get("id")
        title = raw.get("title")
        st = raw.get("status", "pending")
        if not isinstance(sid, str) or not sid.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(st, str) or st not in _STAGE_STATUSES:
            st = "pending"
        out.append({"id": sid.strip(), "title": title.strip(), "status": st})
    return out


class MissionUpdate(BaseModel):
    stages: list[dict[str, Any]] | None = None


class MissionStagesPatchBody(BaseModel):
    """PATCH /missions/{id}/stages — replace mission stage list."""

    stages: list[dict[str, Any]]

    @field_validator("stages", mode="before")
    @classmethod
    def _coerce_stages(cls, v: Any) -> list[dict[str, Any]]:
        if not isinstance(v, list):
            return []
        return [x for x in v if isinstance(x, dict)]


class MissionPlanResponse(BaseModel):
    stages: list[dict[str, Any]]


class MissionEventCreate(BaseModel):
    """Append-only mission event (workers use API key; event_type must be allowed)."""

    event_type: str = Field(..., min_length=1, max_length=128)
    payload: dict[str, Any] | None = None
    actor_type: str | None = Field(default="system", max_length=64)
    actor_id: str | None = Field(default=None, max_length=256)


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
    stages: list[dict[str, Any]] | None = None
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
