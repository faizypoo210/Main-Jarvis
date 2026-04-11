"""Approval domain: requests and decisions."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories.approval_repo import ApprovalRepository
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository

STREAM_EXECUTION = "jarvis.execution"

log = get_logger(__name__)

_JARVIS_ROOT = Path(__file__).resolve().parents[4]
if str(_JARVIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_JARVIS_ROOT))
from shared.routing import decide_route  # noqa: E402


async def _publish_execution_resume(
    mission_id: str,
    command: str,
    approval_id: str,
) -> None:
    settings = get_settings()
    url = settings.REDIS_URL or "redis://localhost:6379"
    route = decide_route(text=command, context={}, risk_class=None)
    routing = route.to_execution_dict()
    routing["approval_sensitive"] = True
    rs = str(routing.get("reason_summary") or "").strip()
    routing["reason_summary"] = (
        f"{rs} Resumed after approval." if rs else "Resumed after approval."
    )
    payload = {
        "mission_id": mission_id,
        "command": command,
        "approval_id": approval_id,
        "resumed": True,
        "routing": routing,
    }
    r: Redis | None = None
    try:
        r = Redis.from_url(url, decode_responses=False)
        await r.xadd(STREAM_EXECUTION, {"data": json.dumps(payload)})
    except Exception as e:
        log.warning("redis execution publish failed: %s", e)
    finally:
        if r is not None:
            await r.close()


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._mission_repo = MissionRepository(session)

    async def request_approval(
        self,
        mission_id: UUID,
        action_type: str,
        risk_class: str,
        reason: str | None,
        requested_by: str,
        requested_via: str,
        expires_at: datetime | None = None,
        *,
        command_text: str | None = None,
        dashclaw_decision_id: str | None = None,
    ) -> Approval:
        mission = await self._mission_repo.get_by_id(mission_id)
        if mission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found",
            )

        approval = await ApprovalRepository.create(
            self._session,
            mission_id=mission_id,
            action_type=action_type,
            risk_class=risk_class,
            reason=reason,
            requested_by=requested_by,
            requested_via=requested_via,
            expires_at=expires_at,
            command_text=command_text,
            dashclaw_decision_id=dashclaw_decision_id,
        )
        await MissionEventRepository.create(
            self._session,
            mission_id=mission_id,
            event_type="approval_requested",
            payload={
                "approval_id": str(approval.id),
                "mission_id": str(mission_id),
                "action_type": action_type,
                "risk_class": risk_class,
                "reason": reason,
                "status": approval.status,
            },
        )
        await self._mission_repo.update_status(mission_id, "awaiting_approval")
        from app.services.sms_approval_service import maybe_queue_sms_notification

        maybe_queue_sms_notification(self._session, approval.id)
        return approval

    async def resolve_approval(
        self,
        approval_id: UUID,
        decision: str,
        decided_by: str,
        decided_via: str,
        decision_notes: str | None = None,
    ) -> Approval:
        approval = await ApprovalRepository.get(self._session, approval_id)
        if approval is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval not found",
            )
        if approval.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approval is not in pending status",
            )
        if decision not in ("approved", "denied"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="decision must be approved or denied",
            )

        updated = await ApprovalRepository.update_decision(
            self._session,
            approval_id=approval_id,
            status=decision,
            decided_by=decided_by,
            decided_via=decided_via,
            decision_notes=decision_notes,
        )
        assert updated is not None

        mid = updated.mission_id
        aid = updated.id
        cmd_text = (updated.command_text or "").strip()

        decided_at_iso = updated.decided_at.isoformat() if updated.decided_at else None
        await MissionEventRepository.create(
            self._session,
            mission_id=mid,
            event_type="approval_resolved",
            payload={
                "approval_id": str(aid),
                "mission_id": str(mid),
                "decision": decision,
                "decided_by": decided_by,
                "decided_via": decided_via,
                **({"decided_at": decided_at_iso} if decided_at_iso else {}),
            },
        )

        if decision == "approved":
            await self._mission_repo.update_status(mid, "active")
        else:
            await self._mission_repo.update_status(mid, "blocked")

        await self._session.commit()

        if decision == "approved":
            if updated.action_type == "github_create_issue":
                from app.services.github_issue_workflow import execute_github_issue_after_approval

                await execute_github_issue_after_approval(self._session, updated)
            elif updated.action_type == "github_create_pull_request":
                from app.services.github_pr_workflow import execute_github_pr_after_approval

                await execute_github_pr_after_approval(self._session, updated)
            elif updated.action_type == "github_merge_pull_request":
                from app.services.github_pr_merge_workflow import execute_github_pr_merge_after_approval

                await execute_github_pr_merge_after_approval(self._session, updated)
            elif updated.action_type == "gmail_create_draft":
                from app.services.gmail_draft_workflow import execute_gmail_draft_after_approval

                await execute_gmail_draft_after_approval(self._session, updated)
            elif updated.action_type == "gmail_send_draft":
                from app.services.gmail_draft_workflow import execute_gmail_send_draft_after_approval

                await execute_gmail_send_draft_after_approval(self._session, updated)
            elif updated.action_type == "gmail_create_reply_draft":
                from app.services.gmail_draft_workflow import execute_gmail_reply_draft_after_approval

                await execute_gmail_reply_draft_after_approval(self._session, updated)
            else:
                await _publish_execution_resume(str(mid), cmd_text, str(aid))

        return updated
