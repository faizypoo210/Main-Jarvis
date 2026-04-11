"""Operator-facing cost event reads — honest labels (direct / estimated / unknown / not_applicable)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CostEventRead(BaseModel):
    id: UUID
    mission_id: UUID | None
    source_kind: str
    source_receipt_id: UUID | None
    provider: str | None
    operation: str | None
    amount: Decimal | None
    currency: str | None
    cost_status: str
    usage_tokens_input: int | None
    usage_tokens_output: int | None
    usage_units: dict[str, Any] | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CostEventRollup(BaseModel):
    """Totals over the filtered set (same filters as `events`)."""

    direct_total_usd: Decimal = Field(
        default=Decimal("0"),
        description="Sum of amount where cost_status=direct and currency=USD.",
    )
    estimated_total_usd: Decimal = Field(
        default=Decimal("0"),
        description="Sum of amount where cost_status=estimated and currency=USD.",
    )
    unknown_count: int = 0
    not_applicable_count: int = 0
    events_total: int = 0


class OperatorCostEventsResponse(BaseModel):
    generated_at: str
    rollup: CostEventRollup
    provider_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Event counts by provider key (includes null as 'unset').",
    )
    events: list[CostEventRead]
