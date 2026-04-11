"""Operator-facing cost guardrail snapshot (env thresholds + window metrics + cost-type heartbeat rows)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.heartbeat import HeartbeatFindingRead


class CostGuardrailBreachActive(BaseModel):
    direct_spend_high: bool = False
    estimated_spend_high: bool = False
    unknown_spike: bool = False
    provider_concentration: bool = False


class CostGuardrailConfigRead(BaseModel):
    """Explicit env-backed thresholds; 0 disables that check."""

    window_hours: float
    direct_usd_threshold: float = Field(
        ...,
        description="0 = disabled. Rolling sum of direct USD in window must exceed this to open finding.",
    )
    estimated_usd_threshold: float
    unknown_count_threshold: float
    provider_concentration_pct_threshold: float
    min_events_for_concentration: int


class OperatorCostGuardrailsResponse(BaseModel):
    generated_at: str
    config: CostGuardrailConfigRead
    metrics: dict[str, Any] = Field(
        ...,
        description="Window rollups from cost_events (same window as guardrail evaluation).",
    )
    breach_active: CostGuardrailBreachActive = Field(
        default_factory=CostGuardrailBreachActive,
        description="Whether each guardrail would emit a candidate this instant (for UI badges).",
    )
    open_cost_findings: list[HeartbeatFindingRead]
    recent_resolved_cost_findings: list[HeartbeatFindingRead] = Field(
        default_factory=list,
        description="Latest resolved cost_* findings (newest first, capped).",
    )
