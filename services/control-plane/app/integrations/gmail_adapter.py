"""Gmail API: create draft only (users.drafts.create)."""

from __future__ import annotations

import base64
import json
from email.message import EmailMessage
from typing import Any

import httpx

from app.schemas.gmail_draft import GmailCreateDraftContract, GmailDraftResult

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
OAUTH_TOKEN = "https://oauth2.googleapis.com/token"


def _truncate(s: str, n: int = 500) -> str:
    t = s.strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _rfc822_bytes(contract: GmailCreateDraftContract) -> bytes:
    msg = EmailMessage()
    msg["To"] = ", ".join(str(x) for x in contract.to)
    if contract.cc:
        msg["Cc"] = ", ".join(str(x) for x in contract.cc)
    if contract.bcc:
        msg["Bcc"] = ", ".join(str(x) for x in contract.bcc)
    msg["Subject"] = contract.subject
    if contract.reply_to_message_id:
        rid = contract.reply_to_message_id.strip()
        if rid:
            msg["In-Reply-To"] = rid
            msg["References"] = rid
    msg.set_content(contract.body or "", subtype="plain", charset="utf-8")
    return msg.as_bytes()


def _encode_raw(rfc: bytes) -> str:
    return base64.urlsafe_b64encode(rfc).decode("ascii").rstrip("=")


async def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> tuple[str | None, str | None]:
    """Return (access_token, error_message)."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(OAUTH_TOKEN, data=data)
    except httpx.HTTPError as e:
        return None, _truncate(str(e))
    try:
        body = r.json() if r.content else {}
    except json.JSONDecodeError:
        body = {}
    if r.status_code // 100 == 2 and isinstance(body, dict):
        at = body.get("access_token")
        if isinstance(at, str) and at.strip():
            return at.strip(), None
    err = ""
    if isinstance(body, dict):
        err = str(body.get("error_description") or body.get("error") or "")
    if not err:
        err = r.text[:400] if r.text else f"HTTP {r.status_code}"
    return None, _truncate(err)


async def create_draft(
    *,
    access_token: str,
    contract: GmailCreateDraftContract,
) -> GmailDraftResult:
    """POST users/me/drafts."""
    rfc = _rfc822_bytes(contract)
    raw = _encode_raw(rfc)
    message: dict[str, Any] = {"raw": raw}
    if contract.thread_id and contract.thread_id.strip():
        message["threadId"] = contract.thread_id.strip()

    url = f"{GMAIL_API}/users/me/drafts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body_json: dict[str, Any] = {"message": message}

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(url, json=body_json, headers=headers)
    except httpx.HTTPError as e:
        return GmailDraftResult(
            success=False,
            subject=contract.subject,
            to_preview=_to_preview(contract),
            error_code="http_error",
            error_message=_truncate(str(e)),
        )

    try:
        data = r.json() if r.content else {}
    except json.JSONDecodeError:
        data = {}

    if r.status_code // 100 == 2 and isinstance(data, dict):
        did = data.get("id")
        mid = None
        tid = None
        inner = data.get("message")
        if isinstance(inner, dict):
            mid = inner.get("id")
            tid = inner.get("threadId")
        snippet = (contract.body or "")[:200].replace("\n", " ").strip() or None
        draft_id = str(did) if did else None
        return GmailDraftResult(
            success=True,
            subject=contract.subject,
            to_preview=_to_preview(contract),
            snippet=snippet,
            draft_id=draft_id,
            message_id=str(mid) if mid else None,
            thread_id=str(tid) if tid else None,
            gmail_url="https://mail.google.com/mail/u/0/#drafts",
        )

    err_msg = ""
    if isinstance(data, dict):
        err_msg = str(data.get("error", {}).get("message") or data.get("message") or "")
    if not err_msg:
        err_msg = r.text[:400] if r.text else f"HTTP {r.status_code}"
    return GmailDraftResult(
        success=False,
        subject=contract.subject,
        to_preview=_to_preview(contract),
        error_code=f"gmail_http_{r.status_code}",
        error_message=_truncate(err_msg),
    )


def _to_preview(contract: GmailCreateDraftContract) -> str:
    if not contract.to:
        return ""
    return ", ".join(str(x) for x in contract.to[:5])
