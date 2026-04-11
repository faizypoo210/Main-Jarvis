"""Gmail draft creation — approval-gated; does not send mail."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.gmail_adapter import (
    _reply_recipient,
    create_draft,
    create_reply_draft,
    get_message_metadata,
    refresh_access_token,
    send_draft,
)
from app.models.approval import Approval
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository
from app.schemas.gmail_draft import (
    GmailCreateDraftContract,
    GmailCreateDraftRequest,
    GmailCreateReplyDraftContract,
    GmailCreateReplyDraftRequest,
    GmailDraftResult,
    GmailReplyDraftResult,
    GmailSendDraftContract,
    GmailSendDraftRequest,
    GmailSendDraftResult,
)
from app.services.receipt_service import ReceiptService

log = get_logger(__name__)

ACTION_TYPE = "gmail_create_draft"
ACTION_TYPE_SEND = "gmail_send_draft"
ACTION_TYPE_REPLY = "gmail_create_reply_draft"
RISK_CLASS = "red"


def human_reason(contract: GmailCreateDraftContract) -> str:
    first = str(contract.to[0]) if contract.to else "recipient"
    return f"Create Gmail draft to {first}: {contract.subject}"


def contract_to_command_text(contract: GmailCreateDraftContract) -> str:
    return contract.model_dump_json()


async def resolve_gmail_access_token() -> tuple[str | None, str | None]:
    """Return (access_token, error_message)."""
    settings = get_settings()
    direct = (settings.JARVIS_GMAIL_ACCESS_TOKEN or "").strip()
    if direct:
        return direct, None
    rt = (settings.JARVIS_GMAIL_REFRESH_TOKEN or "").strip()
    cid = (settings.JARVIS_GMAIL_CLIENT_ID or "").strip()
    csec = (settings.JARVIS_GMAIL_CLIENT_SECRET or "").strip()
    if rt and cid and csec:
        return await refresh_access_token(
            client_id=cid, client_secret=csec, refresh_token=rt
        )
    return None, (
        "Gmail is not configured: set JARVIS_GMAIL_ACCESS_TOKEN, or "
        "JARVIS_GMAIL_REFRESH_TOKEN with JARVIS_GMAIL_CLIENT_ID and JARVIS_GMAIL_CLIENT_SECRET "
        "(see docs/INTEGRATIONS_GMAIL.md). Tokens are machine-local on the control plane host."
    )


async def submit_create_draft_request(
    session: AsyncSession,
    *,
    mission_id: UUID,
    body: GmailCreateDraftRequest,
) -> Approval:
    from fastapi import HTTPException, status

    from app.services.approval_service import ApprovalService

    contract = GmailCreateDraftContract.model_validate(
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

    to_preview = ", ".join(str(x) for x in contract.to[:3])
    safe_payload: dict[str, Any] = {
        "provider": contract.provider,
        "action": contract.action,
        "to_preview": to_preview,
        "subject": contract.subject,
        "approval_id": str(approval.id),
    }
    if contract.source_mission_id:
        safe_payload["source_mission_id"] = str(contract.source_mission_id)

    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_requested",
        actor_type="system",
        actor_id="gmail_draft_workflow",
        payload=safe_payload,
    )

    await session.refresh(approval)
    return approval


async def execute_gmail_draft_after_approval(
    session: AsyncSession,
    approval: Approval,
) -> None:
    receipts = ReceiptService(session)
    missions = MissionRepository(session)
    mid = approval.mission_id
    raw = (approval.command_text or "").strip()

    if not raw:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            None,
            GmailDraftResult(
                success=False,
                subject="",
                to_preview="",
                error_code="missing_contract",
                error_message="Approval had no structured command_text payload.",
            ),
        )
        await session.commit()
        return

    try:
        contract = GmailCreateDraftContract.model_validate_json(raw)
    except Exception as e:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            None,
            GmailDraftResult(
                success=False,
                subject="",
                to_preview="",
                error_code="invalid_contract",
                error_message=str(e)[:500],
            ),
        )
        await session.commit()
        return

    token, err = await resolve_gmail_access_token()
    if not token:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            contract,
            GmailDraftResult(
                success=False,
                subject=contract.subject,
                to_preview=_preview_to(contract),
                error_code="missing_gmail_auth",
                error_message=err or "Gmail auth not configured.",
            ),
        )
        await session.commit()
        return

    result = await create_draft(access_token=token, contract=contract)
    if result.success:
        await _success_path(session, receipts, missions, mid, contract, result)
    else:
        await _failure_path(session, receipts, missions, mid, contract, result)
    await session.commit()


def _preview_to(contract: GmailCreateDraftContract) -> str:
    return ", ".join(str(x) for x in contract.to[:5])


def _receipt_payload(result: GmailDraftResult) -> dict[str, Any]:
    d: dict[str, Any] = result.model_dump()
    d["gmail"] = {
        "draft_id": result.draft_id,
        "message_id": result.message_id,
        "thread_id": result.thread_id,
        "subject": result.subject,
        "to_preview": result.to_preview,
        "snippet": result.snippet,
        "gmail_url": result.gmail_url,
    }
    return d


async def _success_path(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GmailCreateDraftContract,
    result: GmailDraftResult,
) -> None:
    payload = _receipt_payload(result)
    summary = f"Draft saved for {result.to_preview}" + (
        f" (id {result.draft_id})" if result.draft_id else ""
    )
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="gmail_draft_created",
        source="gmail_integration",
        payload=payload,
        summary=summary,
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_executed",
        actor_type="system",
        actor_id="gmail_integration",
        payload={
            "provider": "gmail",
            "action": "create_draft",
            "draft_id": result.draft_id,
            "subject": result.subject,
            "to_preview": result.to_preview,
            "gmail_url": result.gmail_url,
            "message_id": result.message_id,
        },
    )
    await missions.update_status(mission_id, "complete")
    log.info("gmail draft created mission_id=%s draft_id=%s", mission_id, result.draft_id)


async def _failure_path(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GmailCreateDraftContract | None,
    result: GmailDraftResult,
) -> None:
    payload = _receipt_payload(result)
    summary = result.error_message or "Gmail draft creation failed"
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="gmail_draft_failed",
        source="gmail_integration",
        payload=payload,
        summary=f"{summary} ({result.error_code or 'error'})",
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_failed",
        actor_type="system",
        actor_id="gmail_integration",
        payload={
            "provider": "gmail",
            "action": "create_draft",
            "subject": result.subject or (contract.subject if contract else ""),
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    )
    await missions.update_status(mission_id, "failed")
    log.warning("gmail draft failed mission_id=%s code=%s", mission_id, result.error_code)


def human_reason_send(contract: GmailSendDraftContract) -> str:
    base = f"Send Gmail draft {contract.draft_id}"
    if contract.to_preview and contract.to_preview.strip():
        base = f"{base} to {contract.to_preview.strip()}"
    if contract.subject and contract.subject.strip():
        base = f"{base}: {contract.subject.strip()}"
    return base


def contract_send_to_command_text(contract: GmailSendDraftContract) -> str:
    return contract.model_dump_json()


async def submit_send_draft_request(
    session: AsyncSession,
    *,
    mission_id: UUID,
    body: GmailSendDraftRequest,
) -> Approval:
    from fastapi import HTTPException, status

    from app.services.approval_service import ApprovalService

    contract = GmailSendDraftContract.model_validate(
        body.model_dump(exclude={"requested_by", "requested_via"})
    )
    missions = MissionRepository(session)
    mission = await missions.get_by_id(mission_id)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")

    svc = ApprovalService(session)
    approval = await svc.request_approval(
        mission_id=mission_id,
        action_type=ACTION_TYPE_SEND,
        risk_class=RISK_CLASS,
        reason=human_reason_send(contract),
        requested_by=body.requested_by,
        requested_via=body.requested_via,
        command_text=contract_send_to_command_text(contract),
    )

    safe_payload: dict[str, Any] = {
        "provider": contract.provider,
        "action": contract.action,
        "draft_id": contract.draft_id,
        "subject": contract.subject or "",
        "to_preview": contract.to_preview or "",
        "approval_id": str(approval.id),
    }
    if contract.source_mission_id:
        safe_payload["source_mission_id"] = str(contract.source_mission_id)

    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_requested",
        actor_type="system",
        actor_id="gmail_send_draft_workflow",
        payload=safe_payload,
    )

    await session.refresh(approval)
    return approval


async def execute_gmail_send_draft_after_approval(
    session: AsyncSession,
    approval: Approval,
) -> None:
    receipts = ReceiptService(session)
    missions = MissionRepository(session)
    mid = approval.mission_id
    raw = (approval.command_text or "").strip()

    if not raw:
        await _failure_path_send(
            session,
            receipts,
            missions,
            mid,
            None,
            GmailSendDraftResult(
                success=False,
                error_code="missing_contract",
                error_message="Approval had no structured command_text payload.",
            ),
        )
        await session.commit()
        return

    try:
        contract = GmailSendDraftContract.model_validate_json(raw)
    except Exception as e:
        await _failure_path_send(
            session,
            receipts,
            missions,
            mid,
            None,
            GmailSendDraftResult(
                success=False,
                error_code="invalid_contract",
                error_message=str(e)[:500],
            ),
        )
        await session.commit()
        return

    token, err = await resolve_gmail_access_token()
    if not token:
        await _failure_path_send(
            session,
            receipts,
            missions,
            mid,
            contract,
            GmailSendDraftResult(
                success=False,
                draft_id=contract.draft_id,
                subject=contract.subject or "",
                to_preview=contract.to_preview or "",
                error_code="missing_gmail_auth",
                error_message=err or "Gmail auth not configured.",
            ),
        )
        await session.commit()
        return

    result = await send_draft(
        access_token=token,
        draft_id=contract.draft_id,
        display_subject=contract.subject or "",
        display_to_preview=contract.to_preview or "",
    )
    if result.success:
        await _success_path_send(session, receipts, missions, mid, contract, result)
    else:
        await _failure_path_send(session, receipts, missions, mid, contract, result)
    await session.commit()


def _receipt_payload_send(result: GmailSendDraftResult) -> dict[str, Any]:
    d: dict[str, Any] = result.model_dump()
    d["gmail"] = {
        "operation": "send_draft",
        "draft_id": result.draft_id,
        "message_id": result.message_id,
        "thread_id": result.thread_id,
        "subject": result.subject,
        "to_preview": result.to_preview,
        "snippet": result.snippet,
        "gmail_url": result.gmail_url,
    }
    return d


async def _success_path_send(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GmailSendDraftContract,
    result: GmailSendDraftResult,
) -> None:
    payload = _receipt_payload_send(result)
    summary = f"Draft {result.draft_id} sent" + (
        f" (message {result.message_id})" if result.message_id else ""
    )
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="gmail_draft_sent",
        source="gmail_integration",
        payload=payload,
        summary=summary,
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_executed",
        actor_type="system",
        actor_id="gmail_integration",
        payload={
            "provider": "gmail",
            "action": "send_draft",
            "draft_id": result.draft_id,
            "message_id": result.message_id,
            "thread_id": result.thread_id,
            "subject": result.subject,
            "to_preview": result.to_preview,
            "gmail_url": result.gmail_url,
        },
    )
    await missions.update_status(mission_id, "complete")
    log.info(
        "gmail draft sent mission_id=%s draft_id=%s message_id=%s",
        mission_id,
        result.draft_id,
        result.message_id,
    )


async def _failure_path_send(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GmailSendDraftContract | None,
    result: GmailSendDraftResult,
) -> None:
    payload = _receipt_payload_send(result)
    summary = result.error_message or "Gmail draft send failed"
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="gmail_draft_send_failed",
        source="gmail_integration",
        payload=payload,
        summary=f"{summary} ({result.error_code or 'error'})",
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_failed",
        actor_type="system",
        actor_id="gmail_integration",
        payload={
            "provider": "gmail",
            "action": "send_draft",
            "draft_id": result.draft_id or (contract.draft_id if contract else ""),
            "subject": result.subject or (contract.subject if contract else "") or "",
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    )
    await missions.update_status(mission_id, "failed")
    log.warning("gmail send draft failed mission_id=%s code=%s", mission_id, result.error_code)


def human_reason_reply(contract: GmailCreateReplyDraftContract, meta: dict[str, str]) -> str:
    tp = _reply_recipient(meta.get("from", ""), meta.get("to", ""), meta.get("reply_to", ""))
    if not tp and contract.to_preview:
        tp = contract.to_preview.strip()
    if not tp:
        tp = "recipient"
    subj = (contract.subject or meta.get("subject") or "").strip() or "thread"
    return f"Create Gmail reply draft to {tp}: {subj[:120]}"


def contract_reply_to_command_text(contract: GmailCreateReplyDraftContract) -> str:
    return contract.model_dump_json()


async def submit_create_reply_draft_request(
    session: AsyncSession,
    *,
    mission_id: UUID,
    body: GmailCreateReplyDraftRequest,
) -> Approval:
    from fastapi import HTTPException, status

    from app.services.approval_service import ApprovalService

    contract = GmailCreateReplyDraftContract.model_validate(
        body.model_dump(exclude={"requested_by", "requested_via"})
    )
    missions = MissionRepository(session)
    mission = await missions.get_by_id(mission_id)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")

    token, err = await resolve_gmail_access_token()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=err or "Gmail is not configured.",
        )

    meta = await get_message_metadata(
        access_token=token, message_id=contract.reply_to_message_id.strip()
    )
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail message not found or inaccessible (check reply_to_message_id and auth).",
        )

    hint = (contract.thread_id or "").strip()
    api_tid = (meta.get("thread_id") or "").strip()
    if hint and api_tid and hint != api_tid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id does not match the message's thread.",
        )

    svc = ApprovalService(session)
    approval = await svc.request_approval(
        mission_id=mission_id,
        action_type=ACTION_TYPE_REPLY,
        risk_class=RISK_CLASS,
        reason=human_reason_reply(contract, meta),
        requested_by=body.requested_by,
        requested_via=body.requested_via,
        command_text=contract_reply_to_command_text(contract),
    )

    to_pv = _reply_recipient(meta.get("from", ""), meta.get("to", ""), meta.get("reply_to", ""))
    if not to_pv and contract.to_preview:
        to_pv = contract.to_preview.strip()

    safe_payload: dict[str, Any] = {
        "provider": contract.provider,
        "action": contract.action,
        "reply_to_message_id": contract.reply_to_message_id,
        "thread_id": api_tid or hint,
        "subject_preview": (meta.get("subject") or "")[:200],
        "to_preview": to_pv,
        "snippet_preview": (meta.get("snippet") or "")[:300],
        "approval_id": str(approval.id),
    }
    if contract.source_mission_id:
        safe_payload["source_mission_id"] = str(contract.source_mission_id)

    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_requested",
        actor_type="system",
        actor_id="gmail_reply_draft_workflow",
        payload=safe_payload,
    )

    await session.refresh(approval)
    return approval


async def execute_gmail_reply_draft_after_approval(
    session: AsyncSession,
    approval: Approval,
) -> None:
    receipts = ReceiptService(session)
    missions = MissionRepository(session)
    mid = approval.mission_id
    raw = (approval.command_text or "").strip()

    if not raw:
        await _failure_path_reply(
            session,
            receipts,
            missions,
            mid,
            None,
            GmailReplyDraftResult(
                success=False,
                reply_to_message_id="",
                error_code="missing_contract",
                error_message="Approval had no structured command_text payload.",
            ),
        )
        await session.commit()
        return

    try:
        contract = GmailCreateReplyDraftContract.model_validate_json(raw)
    except Exception as e:
        await _failure_path_reply(
            session,
            receipts,
            missions,
            mid,
            None,
            GmailReplyDraftResult(
                success=False,
                reply_to_message_id="",
                error_code="invalid_contract",
                error_message=str(e)[:500],
            ),
        )
        await session.commit()
        return

    token, err = await resolve_gmail_access_token()
    if not token:
        await _failure_path_reply(
            session,
            receipts,
            missions,
            mid,
            contract,
            GmailReplyDraftResult(
                success=False,
                reply_to_message_id=contract.reply_to_message_id,
                error_code="missing_gmail_auth",
                error_message=err or "Gmail auth not configured.",
            ),
        )
        await session.commit()
        return

    result = await create_reply_draft(access_token=token, contract=contract)
    if result.success:
        await _success_path_reply(session, receipts, missions, mid, contract, result)
    else:
        await _failure_path_reply(session, receipts, missions, mid, contract, result)
    await session.commit()


def _receipt_payload_reply(result: GmailReplyDraftResult) -> dict[str, Any]:
    d: dict[str, Any] = result.model_dump()
    d["gmail"] = {
        "operation": "create_reply_draft",
        "reply_to_message_id": result.reply_to_message_id,
        "draft_id": result.draft_id,
        "message_id": result.message_id,
        "thread_id": result.thread_id,
        "subject": result.subject,
        "to_preview": result.to_preview,
        "snippet": result.snippet,
        "gmail_url": result.gmail_url,
    }
    return d


async def _success_path_reply(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GmailCreateReplyDraftContract,
    result: GmailReplyDraftResult,
) -> None:
    payload = _receipt_payload_reply(result)
    summary = f"Reply draft for thread" + (
        f" (draft {result.draft_id})" if result.draft_id else ""
    )
    if result.to_preview:
        summary = f"Reply draft to {result.to_preview}" + (
            f" (id {result.draft_id})" if result.draft_id else ""
        )
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="gmail_reply_draft_created",
        source="gmail_integration",
        payload=payload,
        summary=summary,
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_executed",
        actor_type="system",
        actor_id="gmail_integration",
        payload={
            "provider": "gmail",
            "action": "create_reply_draft",
            "reply_to_message_id": result.reply_to_message_id,
            "draft_id": result.draft_id,
            "message_id": result.message_id,
            "thread_id": result.thread_id,
            "subject": result.subject,
            "to_preview": result.to_preview,
            "gmail_url": result.gmail_url,
        },
    )
    await missions.update_status(mission_id, "complete")
    log.info(
        "gmail reply draft created mission_id=%s draft_id=%s reply_to=%s",
        mission_id,
        result.draft_id,
        result.reply_to_message_id,
    )


async def _failure_path_reply(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GmailCreateReplyDraftContract | None,
    result: GmailReplyDraftResult,
) -> None:
    payload = _receipt_payload_reply(result)
    summary = result.error_message or "Gmail reply draft creation failed"
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="gmail_reply_draft_failed",
        source="gmail_integration",
        payload=payload,
        summary=f"{summary} ({result.error_code or 'error'})",
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_failed",
        actor_type="system",
        actor_id="gmail_integration",
        payload={
            "provider": "gmail",
            "action": "create_reply_draft",
            "reply_to_message_id": result.reply_to_message_id
            or (contract.reply_to_message_id if contract else ""),
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    )
    await missions.update_status(mission_id, "failed")
    log.warning("gmail reply draft failed mission_id=%s code=%s", mission_id, result.error_code)
