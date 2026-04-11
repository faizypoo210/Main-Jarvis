"""Approvals API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.repositories.approval_repo import ApprovalRepository
from app.schemas.approval_bundle import ApprovalBundleResponse
from app.schemas.approvals import ApprovalCreate, ApprovalDecision, ApprovalRead
from app.services.approval_review_packet import build_approval_bundle
from app.services.approval_service import ApprovalService

router = APIRouter()


@router.post("", response_model=ApprovalRead)
async def create_approval(
    body: ApprovalCreate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> ApprovalRead:
    svc = ApprovalService(session)
    approval = await svc.request_approval(
        mission_id=body.mission_id,
        action_type=body.action_type,
        risk_class=body.risk_class,
        reason=body.reason,
        requested_by=body.requested_by,
        requested_via=body.requested_via,
        expires_at=body.expires_at,
        command_text=body.command_text,
        dashclaw_decision_id=body.dashclaw_decision_id,
    )
    return ApprovalRead.model_validate(approval)


@router.get("/pending", response_model=list[ApprovalRead])
async def list_pending_approvals(
    session: AsyncSession = Depends(get_db),
) -> list[ApprovalRead]:
    rows = await ApprovalRepository.get_pending(session)
    return [ApprovalRead.model_validate(a) for a in rows]


@router.get("/{approval_id}/bundle", response_model=ApprovalBundleResponse)
async def get_approval_bundle(
    approval_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> ApprovalBundleResponse:
    """Approval Review Packets v1 — inspectable bundle (no secrets)."""
    bundle = await build_approval_bundle(session, approval_id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    return bundle


@router.post("/{approval_id}/decision", response_model=ApprovalRead)
async def decide_approval(
    approval_id: UUID,
    body: ApprovalDecision,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> ApprovalRead:
    svc = ApprovalService(session)
    approval = await svc.resolve_approval(
        approval_id=approval_id,
        decision=body.decision,
        decided_by=body.decided_by,
        decided_via=body.decided_via,
        decision_notes=body.decision_notes,
    )
    return ApprovalRead.model_validate(approval)
