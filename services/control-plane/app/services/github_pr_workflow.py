"""Governed GitHub draft PR creation: approval-gated, receipt-backed."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.github_adapter import create_pull_request
from app.models.approval import Approval
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository
from app.schemas.github_pr import (
    GitHubCreatePullRequestContract,
    GitHubCreatePullRequestRequest,
    GitHubPullRequestResult,
)
from app.services.receipt_service import ReceiptService

log = get_logger(__name__)

ACTION_TYPE = "github_create_pull_request"
RISK_CLASS = "red"


def human_reason(contract: GitHubCreatePullRequestContract) -> str:
    kind = "draft PR" if contract.draft else "PR"
    return (
        f"Create GitHub {kind} in {contract.repo} from {contract.head} into {contract.base}: {contract.title}"
    )


def contract_to_command_text(contract: GitHubCreatePullRequestContract) -> str:
    return contract.model_dump_json()


async def submit_create_pull_request(
    session: AsyncSession,
    *,
    mission_id: UUID,
    body: GitHubCreatePullRequestRequest,
) -> Approval:
    from fastapi import HTTPException, status

    from app.services.approval_service import ApprovalService

    contract = GitHubCreatePullRequestContract.model_validate(
        body.model_dump(exclude={"requested_by", "requested_via"})
    )
    missions = MissionRepository(session)
    mission = await missions.get_by_id(mission_id)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")

    svc = ApprovalService(session)
    approval = await svc.request_approval(
        mission_id=mission_id,
        action_type=ACTION_TYPE,
        risk_class=RISK_CLASS,
        reason=human_reason(contract),
        requested_by=body.requested_by,
        requested_via=body.requested_via,
        command_text=contract_to_command_text(contract),
    )

    safe_payload: dict[str, Any] = {
        "provider": contract.provider,
        "action": contract.action,
        "repo": contract.repo,
        "base": contract.base,
        "head": contract.head,
        "title": contract.title,
        "draft": contract.draft,
        "approval_id": str(approval.id),
    }
    if contract.source_mission_id:
        safe_payload["source_mission_id"] = str(contract.source_mission_id)

    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_requested",
        actor_type="system",
        actor_id="github_pr_workflow",
        payload=safe_payload,
    )

    await session.refresh(approval)
    return approval


async def execute_github_pr_after_approval(
    session: AsyncSession,
    approval: Approval,
) -> None:
    settings = get_settings()
    token = (settings.JARVIS_GITHUB_TOKEN or "").strip()
    mid = approval.mission_id
    raw = (approval.command_text or "").strip()

    receipts = ReceiptService(session)
    missions = MissionRepository(session)

    if not raw:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            None,
            GitHubPullRequestResult(
                success=False,
                repo="",
                base="",
                head="",
                title="",
                error_code="missing_contract",
                error_message="Approval had no structured command_text payload.",
            ),
        )
        await session.commit()
        return

    try:
        contract = GitHubCreatePullRequestContract.model_validate_json(raw)
    except Exception as e:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            None,
            GitHubPullRequestResult(
                success=False,
                repo="",
                base="",
                head="",
                title="",
                error_code="invalid_contract",
                error_message=str(e)[:500],
            ),
        )
        await session.commit()
        return

    if not token:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            contract,
            GitHubPullRequestResult(
                success=False,
                repo=contract.repo,
                base=contract.base,
                head=contract.head,
                title=contract.title,
                error_code="missing_token",
                error_message=(
                    "JARVIS_GITHUB_TOKEN is not set on the control plane. "
                    "Set a GitHub PAT with pull requests:write (or repo scope) for the target repository."
                ),
            ),
        )
        await session.commit()
        return

    result = await create_pull_request(token=token, contract=contract)
    if result.success:
        await _success_path(session, receipts, missions, mid, contract, result)
    else:
        await _failure_path(session, receipts, missions, mid, contract, result)
    await session.commit()


def _receipt_payload(result: GitHubPullRequestResult) -> dict[str, Any]:
    d: dict[str, Any] = result.model_dump()
    d["github"] = {
        "repo": result.repo,
        "title": result.title,
        "pr_number": result.pr_number,
        "html_url": result.html_url,
        "base": result.base,
        "head": result.head,
        "draft": result.draft,
    }
    return d


async def _success_path(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GitHubCreatePullRequestContract,
    result: GitHubPullRequestResult,
) -> None:
    payload = _receipt_payload(result)
    summary = (
        f"PR #{result.pr_number} in {result.repo}"
        if result.pr_number is not None
        else f"PR created in {result.repo}"
    )
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="github_pull_request_created",
        source="github_integration",
        payload=payload,
        summary=summary,
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_executed",
        actor_type="system",
        actor_id="github_integration",
        payload={
            "provider": "github",
            "action": "create_pull_request",
            "repo": result.repo,
            "base": result.base,
            "head": result.head,
            "pr_number": result.pr_number,
            "html_url": result.html_url,
            "title": result.title,
            "draft": result.draft,
        },
    )
    await missions.update_status(mission_id, "complete")
    log.info(
        "github pr created mission_id=%s repo=%s number=%s",
        mission_id,
        result.repo,
        result.pr_number,
    )


async def _failure_path(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GitHubCreatePullRequestContract | None,
    result: GitHubPullRequestResult,
) -> None:
    payload = _receipt_payload(result)
    repo = result.repo or (contract.repo if contract else "")
    title = result.title or (contract.title if contract else "")
    summary = result.error_message or "GitHub pull request creation failed"
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="github_pull_request_failed",
        source="github_integration",
        payload=payload,
        summary=f"{summary} ({result.error_code or 'error'})",
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_failed",
        actor_type="system",
        actor_id="github_integration",
        payload={
            "provider": "github",
            "action": "create_pull_request",
            "repo": repo,
            "base": result.base or (contract.base if contract else ""),
            "head": result.head or (contract.head if contract else ""),
            "title": title,
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    )
    await missions.update_status(mission_id, "failed")
    log.warning(
        "github pr failed mission_id=%s code=%s",
        mission_id,
        result.error_code,
    )
