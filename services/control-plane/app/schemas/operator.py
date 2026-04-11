"""Operator-facing aggregates from control-plane truth (missions, receipts, events)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LaneCount(BaseModel):
    lane: str
    count: int


class DailyReceiptCount(BaseModel):
    day: str = Field(..., description="UTC date YYYY-MM-DD")
    count: int


class MissionStatusCount(BaseModel):
    status: str
    count: int


class OperatorUsageResponse(BaseModel):
    """Activity and execution usage — not exact cloud spend."""

    generated_at: str
    missions_total: int
    missions_by_status: list[MissionStatusCount]
    receipts_total: int
    receipts_by_type: dict[str, int]
    openclaw_execution_receipts: int
    openclaw_success: int
    openclaw_failure: int
    openclaw_success_unknown: int
    lane_distribution: list[LaneCount]
    receipts_by_day_utc: list[DailyReceiptCount]
    last_mission_event_at: str | None = None
    last_receipt_at: str | None = None
    last_openclaw_execution_at: str | None = None


class ActivitySummary(BaseModel):
    """Counts over a recent UTC window (stored mission_events)."""

    window_hours: int = Field(168, description="Default 7 days.")
    total_in_window: int
    approvals_in_window: int
    execution_in_window: int
    attention_in_window: int


class OperatorActivityItem(BaseModel):
    id: str
    occurred_at: str
    kind: str
    category: str
    title: str
    summary: str
    status: str
    mission_id: str
    mission_title: str
    actor_label: str | None = None
    risk_class: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class OperatorActivityResponse(BaseModel):
    generated_at: str
    summary: ActivitySummary
    items: list[OperatorActivityItem]
    next_before: str | None = Field(
        default=None,
        description="Pass as `before` to fetch the next older page (ISO-8601 UTC).",
    )
