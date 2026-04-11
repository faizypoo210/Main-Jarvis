"""Receipt schemas.

TRUTH_SOURCE: POST /api/v1/receipts (executors and golden-path scripts use the same shape).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReceiptCreate(BaseModel):
    mission_id: UUID | None = None
    receipt_type: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None


class ReceiptRead(BaseModel):
    id: UUID
    mission_id: UUID | None
    receipt_type: str
    source: str
    payload: dict[str, Any]
    summary: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
