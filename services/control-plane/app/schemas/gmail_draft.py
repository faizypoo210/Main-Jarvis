"""Gmail draft creation contract — governed workflow only (no send, no inbox)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.approvals import ApprovalSurface


class GmailCreateDraftContract(BaseModel):
    """Structured payload for gmail_create_draft approvals."""

    provider: Literal["gmail"] = "gmail"
    action: Literal["create_draft"] = "create_draft"
    to: list[EmailStr] = Field(..., min_length=1, max_length=50)
    subject: str = Field(..., min_length=1, max_length=998)
    body: str = Field("", max_length=1024 * 1024)
    cc: list[EmailStr] = Field(default_factory=list, max_length=30)
    bcc: list[EmailStr] = Field(default_factory=list, max_length=30)
    reply_to_message_id: str | None = Field(
        None,
        max_length=512,
        description="Optional RFC Message-ID / Gmail id hint for In-Reply-To (best-effort; no send).",
    )
    thread_id: str | None = Field(
        None,
        max_length=128,
        description="Optional Gmail threadId when drafting in an existing thread.",
    )
    source_mission_id: UUID | None = None

    @field_validator("to", "cc", "bcc", mode="before")
    @classmethod
    def normalize_lists(cls, v: object) -> object:
        if v is None:
            return []
        return v


class GmailCreateDraftRequest(GmailCreateDraftContract):
    """POST body: draft fields plus who requested approval."""

    requested_by: str = Field(..., min_length=1, max_length=256)
    requested_via: ApprovalSurface


class GmailDraftResult(BaseModel):
    """Safe fields for receipts (no tokens)."""

    success: bool
    provider: Literal["gmail"] = "gmail"
    action: Literal["create_draft"] = "create_draft"
    draft_id: str | None = None
    message_id: str | None = None
    thread_id: str | None = None
    subject: str = ""
    to_preview: str = ""
    snippet: str | None = None
    gmail_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class GmailSendDraftContract(BaseModel):
    """Structured payload for gmail_send_draft — send an existing draft only."""

    provider: Literal["gmail"] = "gmail"
    action: Literal["send_draft"] = "send_draft"
    draft_id: str = Field(..., min_length=1, max_length=256)
    message_id: str | None = Field(None, max_length=256, description="Optional Gmail message id hint (audit)")
    thread_id: str | None = Field(None, max_length=128)
    subject: str | None = Field(None, max_length=998, description="Display only; not verified against Gmail")
    to_preview: str | None = Field(None, max_length=512, description="Display only for approval copy")
    source_mission_id: UUID | None = None


class GmailSendDraftRequest(GmailSendDraftContract):
    """POST body: send-draft plus who requested approval."""

    requested_by: str = Field(..., min_length=1, max_length=256)
    requested_via: ApprovalSurface


class GmailSendDraftResult(BaseModel):
    """Safe fields after drafts.send (no tokens)."""

    success: bool
    provider: Literal["gmail"] = "gmail"
    action: Literal["send_draft"] = "send_draft"
    draft_id: str = ""
    message_id: str | None = None
    thread_id: str | None = None
    subject: str = ""
    to_preview: str = ""
    snippet: str | None = None
    gmail_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
