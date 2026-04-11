"""Approval reminder + escalation v1 — heartbeat-driven, deduped, SMS when configured."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.approval_reminder import ApprovalReminder
from app.repositories.approval_reminder_repo import ApprovalReminderRepository
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.sms_approval_repo import SmsApprovalRepository
from app.services.approval_review_packet import build_approval_bundle
from app.services.sms_approval_service import send_operator_sms


def _dedupe_escalation(approval_id: UUID) -> str:
    return f"escalation:{approval_id}"


def _dedupe_reminder(approval_id: UUID, slot: int) -> str:
    return f"reminder:{approval_id}:{slot}"


def _compact_reminder_body(
    *,
    notification_type: str,
    sms_code: str,
    risk_class: str,
    headline: str,
) -> str:
    tag = "REMINDER" if notification_type == "reminder" else "ESCALATION"
    h = (headline or "Approval request").strip()
    if len(h) > 120:
        h = h[:119] + "…"
    r = (risk_class or "").strip()
    return (
        f"Jarvis {tag} [{sms_code}] risk {r}. {h} "
        f"Reply APPROVE {sms_code} or DENY {sms_code}. READ {sms_code} for more."
    )


async def _record_mission_event(
    session: AsyncSession,
    *,
    mission_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type=event_type,
        actor_type="system",
        actor_id="approval_reminders",
        payload=payload,
    )


async def _persist_reminder_row(
    session: AsyncSession,
    *,
    approval_id: UUID,
    channel: str,
    notification_type: str,
    status: str,
    dedupe_key: str,
    notes: str | None,
    error_note: str | None,
    sent_at: datetime | None,
    last_attempt_at: datetime,
) -> None:
    row = ApprovalReminder(
        id=uuid.uuid4(),
        approval_id=approval_id,
        channel=channel,
        notification_type=notification_type,
        status=status,
        dedupe_key=dedupe_key,
        attempt_count=1,
        sent_at=sent_at,
        last_attempt_at=last_attempt_at,
        notes=notes,
        error_note=error_note,
    )
    session.add(row)
    await session.flush()


async def _try_sms_delivery(
    session: AsyncSession,
    *,
    approval_id: UUID,
    mission_id: UUID,
    notification_type: str,
    dedupe_key: str,
    now: datetime,
) -> None:
    """Insert one reminder row; SMS if configured + token exists. Skipped rows have no mission_event (low-noise)."""
    if await ApprovalReminderRepository.get_by_dedupe_key(session, dedupe_key):
        return

    s = get_settings()
    bundle = await build_approval_bundle(session, approval_id)
    headline = ""
    if bundle and bundle.packet:
        headline = str(bundle.packet.headline or "")
    approval_row = bundle.approval if bundle else None
    risk = str(approval_row.risk_class) if approval_row else ""

    token = await SmsApprovalRepository.get_by_approval_id(session, approval_id)
    sms_config_ok = bool(
        s.APPROVAL_REMINDER_SMS_ENABLED
        and s.JARVIS_SMS_APPROVALS_ENABLED
        and s.JARVIS_TWILIO_ACCOUNT_SID
        and s.JARVIS_TWILIO_AUTH_TOKEN
        and s.JARVIS_TWILIO_FROM_NUMBER
        and (s.JARVIS_APPROVAL_SMS_TO_E164 or "").strip()
    )

    if not sms_config_ok:
        await _persist_reminder_row(
            session,
            approval_id=approval_id,
            channel="sms",
            notification_type=notification_type,
            status="skipped",
            dedupe_key=dedupe_key,
            notes="SMS reminder delivery not configured or disabled for this environment.",
            error_note=None,
            sent_at=None,
            last_attempt_at=now,
        )
        return

    if token is None:
        await _persist_reminder_row(
            session,
            approval_id=approval_id,
            channel="sms",
            notification_type=notification_type,
            status="skipped",
            dedupe_key=dedupe_key,
            notes="No approval SMS token yet (initial SMS not sent for this approval).",
            error_note=None,
            sent_at=None,
            last_attempt_at=now,
        )
        return

    body = _compact_reminder_body(
        notification_type=notification_type,
        sms_code=token.sms_code,
        risk_class=risk,
        headline=headline,
    )
    ok, note = await send_operator_sms(body)
    if ok:
        await _persist_reminder_row(
            session,
            approval_id=approval_id,
            channel="sms",
            notification_type=notification_type,
            status="sent",
            dedupe_key=dedupe_key,
            notes="twilio",
            error_note=None,
            sent_at=now,
            last_attempt_at=now,
        )
        if notification_type == "reminder":
            await _record_mission_event(
                session,
                mission_id=mission_id,
                event_type="approval_reminder_sent",
                payload={
                    "approval_id": str(approval_id),
                    "notification_type": notification_type,
                    "channel": "sms",
                    "status": "sent",
                    "dedupe_key": dedupe_key,
                },
            )
        else:
            await _record_mission_event(
                session,
                mission_id=mission_id,
                event_type="approval_escalated",
                payload={
                    "approval_id": str(approval_id),
                    "notification_type": notification_type,
                    "channel": "sms",
                    "status": "sent",
                    "dedupe_key": dedupe_key,
                },
            )
    else:
        await _persist_reminder_row(
            session,
            approval_id=approval_id,
            channel="sms",
            notification_type=notification_type,
            status="failed",
            dedupe_key=dedupe_key,
            notes=None,
            error_note=note[:2000],
            sent_at=None,
            last_attempt_at=now,
        )
        await _record_mission_event(
            session,
            mission_id=mission_id,
            event_type="approval_reminder_failed",
            payload={
                "approval_id": str(approval_id),
                "notification_type": notification_type,
                "channel": "sms",
                "status": "failed",
                "dedupe_key": dedupe_key,
                "error_note": note[:500],
            },
        )


def _age_minutes(created_at: datetime, now: datetime) -> float:
    c = created_at
    if c.tzinfo is None:
        c = c.replace(tzinfo=UTC)
    return (now - c).total_seconds() / 60.0


async def run_approval_reminder_cycle(session: AsyncSession) -> dict[str, Any]:
    """Evaluate pending approvals once; at most one outbound attempt per approval."""
    s = get_settings()
    if not s.APPROVAL_REMINDERS_ENABLED:
        return {"enabled": False, "processed": 0}

    now = datetime.now(UTC)
    first_m = s.APPROVAL_REMINDER_FIRST_MINUTES
    repeat_m = s.APPROVAL_REMINDER_REPEAT_MINUTES
    esc_m = s.APPROVAL_ESCALATION_MINUTES
    max_attempts = s.APPROVAL_REMINDER_MAX_ATTEMPTS

    r = await session.execute(
        text(
            """
            SELECT id, mission_id, created_at
            FROM approvals
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 500
            """
        )
    )
    rows = r.mappings().all()
    processed = 0

    for row in rows:
        aid = row["id"]
        mid = row["mission_id"]
        created_at = row["created_at"]
        age = _age_minutes(created_at, now)

        esc_key = _dedupe_escalation(aid)
        has_esc = await ApprovalReminderRepository.has_escalation_row(session, aid)
        esc_due = age >= esc_m and not has_esc

        if esc_due:
            await _try_sms_delivery(
                session,
                approval_id=aid,
                mission_id=mid,
                notification_type="escalation",
                dedupe_key=esc_key,
                now=now,
            )
            processed += 1
            continue

        n_rem = await ApprovalReminderRepository.count_reminder_rows(session, aid)
        if n_rem >= max_attempts:
            continue

        last_att = await ApprovalReminderRepository.last_reminder_attempt_at(session, aid)
        if n_rem == 0:
            reminder_due = age >= first_m
        else:
            if last_att is None:
                reminder_due = age >= first_m
            else:
                la = last_att
                if la.tzinfo is None:
                    la = la.replace(tzinfo=UTC)
                reminder_due = now >= la + timedelta(minutes=repeat_m)

        if not reminder_due:
            continue

        slot = n_rem + 1
        rkey = _dedupe_reminder(aid, slot)
        await _try_sms_delivery(
            session,
            approval_id=aid,
            mission_id=mid,
            notification_type="reminder",
            dedupe_key=rkey,
            now=now,
        )
        processed += 1

    return {"enabled": True, "processed": processed, "pending_scanned": len(rows)}
