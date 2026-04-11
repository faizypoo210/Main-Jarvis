"""Gmail integration — create draft workflow only."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.schemas.approvals import ApprovalRead
from app.schemas.gmail_draft import GmailCreateDraftRequest
from app.services.gmail_draft_workflow import submit_create_draft_request

router = APIRouter()


@router.post(
    "/{mission_id}/integrations/gmail/create-draft",
    response_model=ApprovalRead,
    summary="Request Gmail draft creation (approval-gated; does not send)",
)
async def request_gmail_create_draft(
    mission_id: UUID,
    body: GmailCreateDraftRequest,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> ApprovalRead:
    approval = await submit_create_draft_request(session, mission_id=mission_id, body=body)
    return ApprovalRead.model_validate(approval)
