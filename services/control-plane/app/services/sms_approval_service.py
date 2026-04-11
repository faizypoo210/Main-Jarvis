"""SMS approval notification (Twilio outbound) + explicit APPROVE/DENY/READ inbound handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from typing import Any
from uuid import UUID
from xml.sax.saxutils import escape

import httpx
from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import async_session_maker
from app.core.logging import get_logger
from app.repositories.approval_repo import ApprovalRepository
from app.repositories.sms_approval_repo import SmsApprovalRepository
from app.services.approval_review_packet import build_approval_bundle
from app.services.approval_service import ApprovalService

log = get_logger(__name__)

_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I

RE_SMS_COMMAND = re.compile(
    r"^\s*(APPROVE|DENY|READ)\s+([A-Z0-9]{4,12})\s*$",
    re.I,
)


def maybe_queue_sms_notification(session: AsyncSession, approval_id: UUID) -> None:
    """After approval row exists; queue post-commit outbound SMS if configured."""
    s = get_settings()
    if not s.JARVIS_SMS_APPROVALS_ENABLED:
        return
    if not (
        s.JARVIS_TWILIO_ACCOUNT_SID
        and s.JARVIS_TWILIO_AUTH_TOKEN
        and s.JARVIS_TWILIO_FROM_NUMBER
        and s.JARVIS_APPROVAL_SMS_TO_E164
    ):
        log.info("sms approval: enabled but Twilio/to not fully configured; skipping queue")
        return
    session.info.setdefault("approval_sms_queue", []).append(str(approval_id))


def _gen_sms_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def _phone_hint(e164: str) -> str:
    d = "".join(c for c in e164 if c.isdigit())
    return d[-4:] if len(d) >= 4 else ""


def _compact_sms_lines(
    *,
    sms_code: str,
    risk_class: str,
    headline: str,
    brief: str,
    mission_title: str | None,
) -> str:
    h = (headline or "Approval request").strip()
    b = (brief or "").strip()
    mt = (mission_title or "").strip()
    r = (risk_class or "").strip()
    # Short-first; total target under ~300 chars for single segment where possible
    parts = [
        f"Jarvis [{sms_code}] risk {r}.",
        h[:140] + ("…" if len(h) > 140 else ""),
    ]
    if mt:
        parts.append(f"Mission: {mt[:80]}{'…' if len(mt) > 80 else ''}")
    if b and b != h:
        parts.append(b[:120] + ("…" if len(b) > 120 else ""))
    parts.append(f"Reply: APPROVE {sms_code} or DENY {sms_code}. READ {sms_code} for more.")
    return " ".join(p for p in parts if p).strip()


async def send_operator_sms(body: str) -> tuple[bool, str]:
    """Send outbound SMS to the configured operator number (Twilio). Used by approval reminders."""
    s = get_settings()
    to_e164 = (s.JARVIS_APPROVAL_SMS_TO_E164 or "").strip()
    if not to_e164:
        return False, "JARVIS_APPROVAL_SMS_TO_E164 not set"
    return await _twilio_send_message(to_e164=to_e164, body=body)


async def _twilio_send_message(*, to_e164: str, body: str) -> tuple[bool, str]:
    s = get_settings()
    sid = s.JARVIS_TWILIO_ACCOUNT_SID
    token = s.JARVIS_TWILIO_AUTH_TOKEN
    from_n = s.JARVIS_TWILIO_FROM_NUMBER
    if not sid or not token or not from_n:
        return False, "twilio not configured"
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                url,
                data={"To": to_e164, "From": from_n, "Body": body[:1600]},
                auth=(sid, token),
            )
            if r.status_code >= 400:
                return False, f"HTTP {r.status_code}: {(r.text or '')[:200]}"
            return True, "sent"
    except Exception as e:
        log.warning("twilio send: %s", e)
        return False, str(e)[:200]


async def _send_notification_for_approval(session: AsyncSession, approval_id: UUID) -> None:
    s = get_settings()
    approval = await ApprovalRepository.get(session, approval_id)
    if approval is None or approval.status != "pending":
        return

    existing = await SmsApprovalRepository.get_by_approval_id(session, approval_id)
    if existing is not None:
        return

    bundle = await build_approval_bundle(session, approval_id)
    packet = bundle.packet if bundle else None
    ctx = bundle.context if bundle else None
    headline = str(packet.headline if packet else "") or approval.action_type
    brief = str(packet.brief_summary if packet else "") or (approval.reason or "")[:200]
    mission_title = str(ctx.mission_title if ctx and ctx.mission_title else "") or None

    to_e164 = s.JARVIS_APPROVAL_SMS_TO_E164.strip()
    row = None
    for _attempt in range(10):
        code = _gen_sms_code()
        try:
            row = await SmsApprovalRepository.create(
                session,
                approval_id=approval_id,
                sms_code=code,
                phone_hint=_phone_hint(to_e164),
            )
            await session.flush()
            break
        except IntegrityError:
            await session.rollback()
    if row is None:
        log.warning("sms approval: could not allocate unique code for %s", approval_id)
        return

    text = _compact_sms_lines(
        sms_code=row.sms_code,
        risk_class=approval.risk_class,
        headline=headline,
        brief=brief,
        mission_title=mission_title,
    )
    ok, note = await _twilio_send_message(to_e164=to_e164, body=text)
    await SmsApprovalRepository.mark_sent(session, row.id, note=f"{'ok' if ok else 'error'}: {note}")
    if not ok:
        log.warning("sms approval outbound failed approval_id=%s note=%s", approval_id, note)


async def process_approval_sms_queue(approval_ids: list[UUID]) -> None:
    """Run after DB commit for new approvals."""
    if not approval_ids:
        return
    s = get_settings()
    if not s.JARVIS_SMS_APPROVALS_ENABLED:
        return
    if not (
        s.JARVIS_TWILIO_ACCOUNT_SID
        and s.JARVIS_TWILIO_AUTH_TOKEN
        and s.JARVIS_TWILIO_FROM_NUMBER
        and s.JARVIS_APPROVAL_SMS_TO_E164
    ):
        return

    for aid in approval_ids:
        async with async_session_maker() as session:
            try:
                await _send_notification_for_approval(session, aid)
                await session.commit()
            except Exception as e:
                log.warning("process_approval_sms_queue approval_id=%s: %s", aid, e)
                await session.rollback()


def validate_twilio_signature(
    public_url: str,
    post_params: dict[str, Any],
    signature: str | None,
    auth_token: str,
) -> bool:
    """https://www.twilio.com/docs/usage/security#validating-requests"""
    if not signature or not auth_token:
        return False
    url = public_url.rstrip("/")
    s = url + "".join(f"{k}{v}" for k, v in sorted(post_params.items()))
    digest = hmac.new(auth_token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    try:
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def _normalize_from(raw: str) -> str:
    return "".join(raw.split())


def _from_allowed(incoming: str, expected: str) -> bool:
    return _normalize_from(incoming) == _normalize_from(expected)


def _twiml_message(text: str) -> str:
    body = escape(text, {"'": "&apos;", '"': "&quot;"})
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{body}</Message></Response>'


def _twiml_empty() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


async def handle_twilio_inbound(request: Request, session: AsyncSession) -> str:
    """
    Parse Twilio webhook; return TwiML XML. No vague approvals — APPROVE/DENY/READ + code only.
    """
    s = get_settings()
    form = await request.form()
    params: dict[str, str] = {str(k): str(v) for k, v in form.items()}
    body_raw = (params.get("Body") or "").strip()
    from_raw = params.get("From") or ""
    sig = request.headers.get("X-Twilio-Signature")

    public_url = (s.JARVIS_TWILIO_WEBHOOK_BASE_URL or "").strip()
    if not public_url:
        return _twiml_message("SMS webhook base URL is not configured on the server (JARVIS_TWILIO_WEBHOOK_BASE_URL).")

    if not s.JARVIS_TWILIO_INBOUND_SKIP_SIGNATURE_VALIDATION:
        if not validate_twilio_signature(public_url, params, sig, s.JARVIS_TWILIO_AUTH_TOKEN):
            return _twiml_message("Unauthorized: invalid Twilio signature.")
    elif not s.JARVIS_TWILIO_AUTH_TOKEN:
        return _twiml_message("Twilio auth token is not configured.")

    exp = s.JARVIS_APPROVAL_SMS_TO_E164.strip()
    if not exp or not _from_allowed(from_raw, exp):
        log.warning("sms inbound: rejected From=%s (expected configured operator number)", from_raw)
        return _twiml_message("This number is not authorized to submit approval decisions.")

    m = RE_SMS_COMMAND.match(body_raw)
    if not m:
        return _twiml_message(
            "Send APPROVE, DENY, or READ followed by your six-character code. "
            "Example: APPROVE ABC12X. I do not accept yes, ok, or send it."
        )

    verb = m.group(1).upper()
    code = m.group(2).upper()

    token = await SmsApprovalRepository.get_by_code(session, code)
    if token is None:
        return _twiml_message("Unknown or expired code. Check the SMS Jarvis sent you.")

    approval = await ApprovalRepository.get(session, token.approval_id)
    if approval is None:
        return _twiml_message("That approval no longer exists.")

    await SmsApprovalRepository.mark_inbound(session, token.id, note=f"{verb} {code}")

    if approval.status != "pending":
        await session.commit()
        return _twiml_message("That approval is no longer pending.")

    if verb == "READ":
        bundle = await build_approval_bundle(session, approval.id)
        if bundle and bundle.packet:
            p = bundle.packet
            line = str(p.spoken_summary).strip() if p.spoken_summary else f"{p.headline}. {p.brief_summary}"
        else:
            line = f"{approval.action_type}. {approval.reason or 'No extra detail.'}"
        await SmsApprovalRepository.mark_inbound(session, token.id, note=f"{verb} {code}")
        await session.commit()
        return _twiml_message(line[:1500])

    decided_by = s.JARVIS_TWILIO_INBOUND_DECIDED_BY.strip() or "sms_operator"
    decision = "approved" if verb == "APPROVE" else "denied"
    await SmsApprovalRepository.mark_inbound(session, token.id, note=f"{verb} {code}")
    await session.flush()
    svc = ApprovalService(session)
    try:
        await svc.resolve_approval(
            approval.id,
            decision=decision,
            decided_by=decided_by,
            decided_via="sms",
            decision_notes=f"sms:{code}",
        )
    except HTTPException as e:
        await session.rollback()
        return _twiml_message(str(e.detail) if e.detail else "Request failed.")

    async with async_session_maker() as s2:
        await SmsApprovalRepository.mark_used(s2, token.id)
        await s2.commit()
    return _twiml_message(f"Recorded {decision} for code {code}. Mission truth is updated in Jarvis.")
