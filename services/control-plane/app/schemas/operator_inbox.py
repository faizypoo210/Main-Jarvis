"""Operator Inbox v1 — derived actionable queue + light operator state."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OperatorInboxItemRead(BaseModel):
    item_key: str
    source_kind: str = Field(
        ...,
        description="approval | heartbeat | integration_failure | mission_failure",
    )
    inbox_group: str = Field(
        ...,
        description="approvals | system | cost | failures — for tabs/filters",
    )
    severity: str = Field(..., description="urgent | attention | info")
    status: str = Field(
        ...,
        description="open | acknowledged | snoozed | dismissed (derived + state)",
    )
    headline: str
    summary: str
    action_label: str
    mission_id: UUID | None = None
    approval_id: UUID | None = None
    related_href: str
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None
    snoozed_until: datetime | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class OperatorInboxCounts(BaseModel):
    urgent: int = 0
    attention: int = 0
    info: int = 0
    approvals_pending: int = 0
    heartbeat_open: int = 0
    cost_alerts: int = 0
    total_visible: int = 0


class OperatorInboxResponse(BaseModel):
    generated_at: str
    counts: OperatorInboxCounts
    items: list[OperatorInboxItemRead]


class OperatorInboxAckResponse(BaseModel):
    ok: bool = True
    item_key: str


class OperatorInboxSnoozeBody(BaseModel):
    minutes: int = Field(
        0,
        ge=0,
        le=10080,
        description="Snooze duration; 0 clears snooze for this item_key.",
    )


class OperatorInboxDismissResponse(BaseModel):
    ok: bool = True
    item_key: str
