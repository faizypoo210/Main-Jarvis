"""Approval Review Packet v1 — bundle for operator inspection (no secrets)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.approvals import ApprovalRead
from app.schemas.missions import MissionRead


class PacketField(BaseModel):
    """Single human-readable row for drill-down."""

    label: str
    value: str


class ApprovalReviewPacket(BaseModel):
    """Normalized review surface — not a raw JSON dump."""

    kind: str = Field(
        ...,
        description="typed | generic | parse_error — how command_text was interpreted",
    )
    action_type: str
    headline: str
    subheadline: str | None = None
    action_kind: str | None = Field(None, description="Short category e.g. github_issue, gmail_draft")
    operator_effect: str | None = Field(None, description="What happens if approved")
    target_summary: str | None = None
    identity_bearing: bool | None = Field(
        None,
        description="True when risk_class red or action touches external identity",
    )
    fields: list[PacketField] = Field(default_factory=list)
    brief_summary: str = Field(..., description="One short paragraph for UI")
    spoken_summary: str = Field(
        ...,
        description="Plain language, suitable for future voice readout",
    )
    preflight_summary: str | None = None
    preflight_available: bool = False
    parse_ok: bool = True
    parse_note: str | None = None


class ApprovalContextBlock(BaseModel):
    """Decision context — direct from approval + mission rows."""

    requested_by: str
    requested_via: str
    risk_class: str
    created_at: datetime
    age_seconds: float = Field(..., description="Seconds since approval created (UTC)")
    mission_id: UUID
    mission_title: str | None = None
    mission_status: str | None = None
    mission_link: str | None = Field(
        None,
        description="Relative Command Center path e.g. /missions/{id} (client resolves origin)",
    )
    identity_bearing: bool = Field(
        ...,
        description="True when external identity-bearing action (typically risk red)",
    )
    reason_line: str | None = None


class MissionEventSnippet(BaseModel):
    id: UUID
    event_type: str
    created_at: datetime
    summary: str = Field("", description="Compact, non-sensitive one-liner")


class ReceiptSnippet(BaseModel):
    id: UUID
    receipt_type: str
    created_at: datetime
    summary: str | None = None


class BundleDataQuality(BaseModel):
    direct_from_store: list[str] = Field(default_factory=list)
    derived: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ApprovalBundleResponse(BaseModel):
    generated_at: datetime
    approval: ApprovalRead
    mission: MissionRead | None = None
    context: ApprovalContextBlock
    packet: ApprovalReviewPacket
    recent_events: list[MissionEventSnippet] = Field(default_factory=list)
    related_receipts: list[ReceiptSnippet] = Field(default_factory=list)
    data_quality: BundleDataQuality
    notes: list[str] = Field(
        default_factory=list,
        description="Short operator-facing notes (e.g. parse caveats); not a substitute for packet fields",
    )
