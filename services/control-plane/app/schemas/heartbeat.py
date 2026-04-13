"""Heartbeat API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HeartbeatFindingRead(BaseModel):
    id: UUID
    finding_type: str
    severity: str
    summary: str
    dedupe_key: str
    mission_id: UUID | None = None
    approval_id: UUID | None = None
    worker_id: UUID | None = None
    integration_id: UUID | None = None
    service_component: str | None = None
    provenance_note: str | None = None
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class HeartbeatOperatorResponse(BaseModel):
    """Open findings + compact counts for operator surfaces."""

    generated_at: str
    open_count: int
    by_severity: dict[str, int]
    by_type: dict[str, int]
    open_findings: list[HeartbeatFindingRead]
    operator_note: str | None = Field(
        default=None,
        description="Non-fatal hint when the snapshot could not be loaded (e.g. DB schema drift).",
    )


class HeartbeatRunResponse(BaseModel):
    evaluated_at: str
    open_count: int
    resolved_this_run: int
    upserted: int
