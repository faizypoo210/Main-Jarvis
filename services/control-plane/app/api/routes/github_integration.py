"""Governed GitHub integration — create issue workflow only."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.schemas.approvals import ApprovalRead
from app.schemas.github_issue import GitHubCreateIssueRequest
from app.services.github_issue_workflow import submit_create_issue_request

router = APIRouter()


@router.post(
    "/{mission_id}/integrations/github/create-issue",
    response_model=ApprovalRead,
    summary="Request GitHub issue creation (approval-gated)",
)
async def request_github_create_issue(
    mission_id: UUID,
    body: GitHubCreateIssueRequest,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> ApprovalRead:
    approval = await submit_create_issue_request(session, mission_id=mission_id, body=body)
    return ApprovalRead.model_validate(approval)
