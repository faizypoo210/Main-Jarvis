"""Gmail API: create draft (drafts.create) and send draft (drafts.send)."""

from __future__ import annotations

import base64
import json
import re
from email.message import EmailMessage
from typing import Any

import httpx

from app.schemas.gmail_draft import (
    GmailCreateDraftContract,
    GmailCreateReplyDraftContract,
    GmailDraftResult,
    GmailReplyDraftResult,
    GmailSendDraftResult,
)

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
OAUTH_TOKEN = "https://oauth2.googleapis.com/token"


def _truncate(s: str, n: int = 500) -> str:
    t = s.strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _first_email_address(header_value: str) -> str:
    if not header_value or not str(header_value).strip():
        return ""
    m = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", str(header_value))
    return m.group(0) if m else ""


def _reply_recipient(from_hdr: str, to_hdr: str, reply_to_hdr: str) -> str:
    """Choose a single reply To: Reply-To, else From, else first address in To."""
    a = _first_email_address(reply_to_hdr)
    if a:
        return a
    a = _first_email_address(from_hdr)
    if a:
        return a
    return _first_email_address(to_hdr)


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


async def send_draft(
    *,
    access_token: str,
    draft_id: str,
    display_subject: str = "",
    display_to_preview: str = "",
) -> GmailSendDraftResult:
    """POST users/me/drafts/send with draft id only."""
    did = draft_id.strip()
    if not did:
        return GmailSendDraftResult(
            success=False,
            draft_id="",
            subject=display_subject,
            to_preview=display_to_preview,
            error_code="invalid_draft_id",
            error_message="draft_id is required.",
        )

    url = f"{GMAIL_API}/users/me/drafts/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body_json = {"id": did}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, json=body_json, headers=headers)
    except httpx.HTTPError as e:
        return GmailSendDraftResult(
            success=False,
            draft_id=did,
            subject=display_subject,
            to_preview=display_to_preview,
            error_code="http_error",
            error_message=_truncate(str(e)),
        )

    try:
        data = r.json() if r.content else {}
    except json.JSONDecodeError:
        data = {}

    if r.status_code // 100 == 2 and isinstance(data, dict):
        mid = data.get("id")
        tid = data.get("threadId")
        snip = data.get("snippet")
        if isinstance(snip, str):
            snip = snip[:300] if len(snip) > 300 else snip
        thread = str(tid) if tid else None
        gurl = (
            f"https://mail.google.com/mail/u/0/#inbox/{thread}"
            if thread
            else "https://mail.google.com/mail/u/0/#sent"
        )
        return GmailSendDraftResult(
            success=True,
            draft_id=did,
            message_id=str(mid) if mid else None,
            thread_id=thread,
            subject=display_subject,
            to_preview=display_to_preview,
            snippet=str(snip) if snip else None,
            gmail_url=gurl,
        )

    err_msg = ""
    if isinstance(data, dict):
        err_msg = str(data.get("error", {}).get("message") or data.get("message") or "")
    if not err_msg:
        err_msg = r.text[:400] if r.text else f"HTTP {r.status_code}"
    return GmailSendDraftResult(
        success=False,
        draft_id=did,
        subject=display_subject,
        to_preview=display_to_preview,
        error_code=f"gmail_http_{r.status_code}",
        error_message=_truncate(err_msg),
    )


async def get_message_metadata(
    *,
    access_token: str,
    message_id: str,
) -> dict[str, str] | None:
    """GET users/me/messages/{id} (metadata). Safe subset for approvals — no raw body."""
    mid = message_id.strip()
    if not mid:
        return None
    url = f"{GMAIL_API}/users/me/messages/{mid}"
    params = [
        ("format", "metadata"),
        ("metadataHeaders", "Subject"),
        ("metadataHeaders", "From"),
        ("metadataHeaders", "To"),
        ("metadataHeaders", "Message-ID"),
        ("metadataHeaders", "Reply-To"),
    ]
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError:
        return None
    if r.status_code == 404:
        return None
    if r.status_code // 100 != 2:
        return None
    try:
        data = r.json() if r.content else {}
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    tid = data.get("threadId")
    snippet = str(data.get("snippet") or "")[:500]
    hdrs: dict[str, str] = {}
    payload = data.get("payload") or {}
    for h in payload.get("headers") or []:
        if isinstance(h, dict) and h.get("name"):
            hdrs[str(h["name"]).lower()] = str(h.get("value") or "")
    subject = _truncate(hdrs.get("subject", ""), 500)
    return {
        "thread_id": str(tid) if tid else "",
        "snippet": snippet,
        "subject": subject,
        "from": hdrs.get("from", ""),
        "to": hdrs.get("to", ""),
        "rfc_message_id": hdrs.get("message-id", "").strip(),
        "reply_to": hdrs.get("reply-to", ""),
    }


async def create_reply_draft(
    *,
    access_token: str,
    contract: GmailCreateReplyDraftContract,
) -> GmailReplyDraftResult:
    """Resolve reply recipient from thread message; drafts.create with In-Reply-To."""
    meta = await get_message_metadata(
        access_token=access_token, message_id=contract.reply_to_message_id.strip()
    )
    if not meta:
        return GmailReplyDraftResult(
            success=False,
            reply_to_message_id=contract.reply_to_message_id,
            error_code="message_not_found",
            error_message="Could not load the message to reply to.",
        )

    rfc_mid = meta["rfc_message_id"]
    if not rfc_mid:
        return GmailReplyDraftResult(
            success=False,
            reply_to_message_id=contract.reply_to_message_id,
            error_code="missing_rfc_message_id",
            error_message="Source message has no Message-ID header.",
        )

    to_addr = _reply_recipient(meta["from"], meta["to"], meta["reply_to"])
    if not to_addr:
        return GmailReplyDraftResult(
            success=False,
            reply_to_message_id=contract.reply_to_message_id,
            error_code="no_reply_recipient",
            error_message="Could not determine a recipient from From / To / Reply-To headers.",
        )

    orig_subj = meta["subject"] or "(no subject)"
    if contract.subject and contract.subject.strip():
        subj = contract.subject.strip()
    else:
        subj = orig_subj if orig_subj.lower().startswith("re:") else f"Re: {orig_subj}"

    thread = (contract.thread_id or meta["thread_id"] or "").strip()

    inner = GmailCreateDraftContract(
        to=[to_addr],  # type: ignore[list-item]
        subject=subj,
        body=contract.body,
        cc=contract.cc,
        bcc=contract.bcc,
        reply_to_message_id=rfc_mid,
        thread_id=thread if thread else None,
        source_mission_id=contract.source_mission_id,
    )

    result = await create_draft(access_token=access_token, contract=inner)
    return GmailReplyDraftResult(
        success=result.success,
        reply_to_message_id=contract.reply_to_message_id,
        draft_id=result.draft_id,
        message_id=result.message_id,
        thread_id=result.thread_id or (thread if thread else None),
        subject=result.subject or subj,
        to_preview=result.to_preview or to_addr,
        snippet=result.snippet,
        gmail_url=result.gmail_url,
        error_code=result.error_code,
        error_message=result.error_message,
    )
