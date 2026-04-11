"""Approval schemas.

TRUTH_SOURCE: canonical HTTP contract for POST /api/v1/approvals and decision payloads.
Scripts must stay aligned: scripts/lib/ApprovalPayloadContract.ps1, coordinator approval branches.

Parity notes (keep in sync when changing fields or enums):
- `requested_via` / `decided_via`: same closed set as `ApprovalSurface` (mirrored in PowerShell
  `Get-ApprovalRequestedViaAllowedSet`).
- `risk_class`: stored as string; operator scripts validate green|amber|red locally before POST.
  The API does not enforce an enum so coordinator/DashClaw can evolve labels without breaking HTTP.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from uuid import UUID

from pydantic import BaseModel, Field

# Single source for approval surface strings (coordinator + Command Center + operator scripts).
ApprovalSurface = Literal["voice", "command_center", "system", "sms"]


class ApprovalCreate(BaseModel):
    mission_id: UUID
    action_type: str
    risk_class: str = Field(
        ...,
        description="Risk class: green, amber, or red",
    )
    reason: str | None = None
    command_text: str | None = None
    dashclaw_decision_id: str | None = None
    requested_by: str
    requested_via: ApprovalSurface = Field(
        ...,
        description="Must be one of: voice | command_center | system | sms (see ApprovalSurface).",
    )
    expires_at: datetime | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["approved", "denied"]
    decided_by: str
    decided_via: ApprovalSurface = Field(
        ...,
        description="Must be one of: voice | command_center | system | sms (see ApprovalSurface).",
    )
    decision_notes: str | None = None


class ApprovalRead(BaseModel):
    id: UUID
    mission_id: UUID
    action_type: str
    risk_class: str
    reason: str | None
    command_text: str | None
    dashclaw_decision_id: str | None
    status: str
    requested_by: str
    requested_via: str
    decided_by: str | None
    decided_via: str | None
    decision_notes: str | None
    created_at: datetime
    decided_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}
