"""
Voice Approval Readout + Resolution v1 — narrow, high-trust control-plane integration.

TRUTH_SOURCE: uses GET /api/v1/approvals/pending and GET /api/v1/approvals/{id}/bundle;
POST /api/v1/approvals/{id}/decision with decided_via=voice. Ephemeral state only (per WebSocket).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("jarvis.voice.approval")

# Ephemeral per-connection state (not mission truth)
_sessions: dict[int, VoiceApprovalState] = {}


@dataclass
class VoiceApprovalState:
    """Lightweight focus for one voice WebSocket connection."""

    queue_ids: list[str] = field(default_factory=list)
    cursor: int = 0
    last_spoken: str | None = None


def get_voice_approval_state(ws_key: int) -> VoiceApprovalState:
    if ws_key not in _sessions:
        _sessions[ws_key] = VoiceApprovalState()
    return _sessions[ws_key]


def forget_voice_approval_state(ws_key: int) -> None:
    _sessions.pop(ws_key, None)


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def _short_id(full_id: str) -> str:
    s = str(full_id).replace("-", "")
    return s[:8] if len(s) >= 8 else s


def _find_id_by_token(pending: list[dict[str, Any]], token: str) -> str | None:
    t = re.sub(r"[^a-f0-9]", "", token.lower())
    if len(t) < 4:
        return None
    for row in pending:
        aid = str(row.get("id", ""))
        compact = aid.replace("-", "").lower()
        if compact.startswith(t) or t in compact:
            return aid
    return None


def _spoken_from_bundle(data: dict[str, Any]) -> str:
    packet = data.get("packet") or {}
    ctx = data.get("context") or {}
    if packet.get("spoken_summary"):
        line = str(packet["spoken_summary"]).strip()
    else:
        parts: list[str] = []
        if packet.get("headline"):
            parts.append(str(packet["headline"]).strip())
        if packet.get("brief_summary"):
            parts.append(str(packet["brief_summary"]).strip())
        line = " ".join(parts) if parts else "Approval details could not be summarized."
    extras: list[str] = []
    rc = ctx.get("risk_class") or packet.get("risk_class")
    if rc:
        extras.append(f"Risk class: {rc}.")
    if ctx.get("mission_title"):
        extras.append(f"Mission: {ctx['mission_title']}.")
    if packet.get("operator_effect"):
        extras.append(str(packet["operator_effect"]).strip())
    if extras:
        line = line + " " + " ".join(extras)
    return line.strip()


def _queue_summary_lines(pending: list[dict[str, Any]], max_items: int = 5) -> str:
    if not pending:
        return "No pending approvals."
    n = len(pending)
    lines: list[str] = [f"You have {n} pending approval{'s' if n != 1 else ''}."]
    for i, row in enumerate(pending[:max_items]):
        aid = str(row.get("id", ""))
        at = row.get("action_type") or "unknown action"
        risk = row.get("risk_class") or "unknown"
        lines.append(
            f"Number {i + 1}: {at}, risk {risk}, id {_short_id(aid)}."
        )
    if n > max_items:
        lines.append(f"Plus {n - max_items} more.")
    return " ".join(lines)


RE_WHAT_NEEDS = re.compile(
    r"\b(what\s+needs\s+my\s+approval|what\s+needs\s+approval|what(\s+is|\s+are)\s+pending|"
    r"pending\s+approvals?|list\s+(my\s+)?approvals?|what\s+approvals?)\b",
    re.I,
)
RE_READ_NEXT = re.compile(
    r"\b(read\s+(me\s+)?(the\s+)?next\s+approval|read\s+(the\s+)?approval|"
    r"read\s+full\s+approval|tell\s+me\s+about\s+(this|the)\s+approval)\b",
    re.I,
)
RE_READ_AGAIN = re.compile(
    r"\b(read\s+that\s+again|repeat\s+(that|it|the\s+approval)|say\s+that\s+again)\b",
    re.I,
)
RE_APPROVE_IT = re.compile(
    r"^(approve\s+it|approve\s+this)(\s*[.!]?)?$",
    re.I,
)
RE_DENY_IT = re.compile(
    r"^(deny\s+it|deny\s+this|reject\s+it|deny\s+that)(\s*[.!]?)?$",
    re.I,
)
RE_APPROVE_ID = re.compile(
    r"\bapprove\s+(?:approval\s+)?([a-f0-9-]{4,40})\b",
    re.I,
)
RE_DENY_ID = re.compile(r"\bdeny\s+(?:approval\s+)?([a-f0-9-]{4,40})\b", re.I)
RE_BARE_APPROVE_DENY = re.compile(r"^(approve|deny|reject)(\s*[.!]?)?$", re.I)
RE_NEXT = re.compile(r"\b(next\s+approval|go\s+to\s+next)\b", re.I)
RE_PREV = re.compile(r"\b(previous|prior|back)\s+approval\b", re.I)
RE_BARE_YES_NO = re.compile(r"^(yes|no|yeah|nope|nah|yep)(\s*[.!]?)?$", re.I)
RE_BARE_DO = re.compile(
    r"^(do\s+it|send\s+it|merge\s+it|go\s+ahead|okay\s+go|ok\s+go)(\s*[.!]?)?$", re.I
)


async def _get_pending(client: httpx.AsyncClient, base: str) -> list[dict[str, Any]]:
    r = await client.get(f"{base}/api/v1/approvals/pending", timeout=20.0)
    r.raise_for_status()
    body = r.json()
    return list(body) if isinstance(body, list) else []


async def _get_bundle(
    client: httpx.AsyncClient, base: str, approval_id: str
) -> dict[str, Any]:
    r = await client.get(
        f"{base}/api/v1/approvals/{approval_id}/bundle",
        timeout=20.0,
    )
    r.raise_for_status()
    return r.json()


async def _post_decision(
    client: httpx.AsyncClient,
    base: str,
    approval_id: str,
    decision: str,
    api_key: str,
) -> None:
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    body = {
        "decision": decision,
        "decided_by": "operator",
        "decided_via": "voice",
        "decision_notes": None,
    }
    r = await client.post(
        f"{base}/api/v1/approvals/{approval_id}/decision",
        json=body,
        headers=headers,
        timeout=25.0,
    )
    r.raise_for_status()


async def try_handle_voice_approval(
    text: str,
    ws_key: int,
    *,
    control_plane_url: str,
    api_key: str,
) -> str | None:
    """
    If this utterance is handled by the approval flow, return the exact string to speak.
    Return None to fall through to normal command → Ollama path.
    """
    t = _norm(text)
    if not t:
        return None

    st = get_voice_approval_state(ws_key)

    # Reject ambiguous short confirmations (never approve/deny by voice without explicit phrasing)
    if RE_BARE_YES_NO.match(t) or RE_BARE_DO.match(t):
        return (
            "I did not act on that. To approve or deny, say approve it or deny it "
            "after you have heard an approval. Say what needs my approval to list pending items."
        )

    if RE_BARE_APPROVE_DENY.match(t):
        return (
            "Say approve it or deny it when an approval is in focus, "
            "or say approve approval followed by the short id."
        )

    base = control_plane_url.rstrip("/")

    async with httpx.AsyncClient() as client:
        # --- Explicit id (no focus required) ---
        m_aid = RE_APPROVE_ID.search(t)
        m_did = RE_DENY_ID.search(t)
        if m_aid and not RE_APPROVE_IT.match(t):
            token = m_aid.group(1)
            try:
                pending = await _get_pending(client, base)
            except Exception as e:
                log.warning("pending fetch: %s", e)
                return "I could not reach the control plane for approvals."
            target = _find_id_by_token(pending, token)
            if not target:
                return f"No pending approval matches id {token}. Check the list with: what needs my approval."
            if not api_key.strip():
                return "Control plane API key is not configured; I cannot submit that decision."
            try:
                bundle = await _get_bundle(client, base, target)
                spoken = _spoken_from_bundle(bundle)
                await _post_decision(client, base, target, "approved", api_key)
            except Exception as e:
                log.warning("approve by id: %s", e)
                return "That approval decision failed. Check the control plane or try again."
            st.queue_ids = [str(x.get("id")) for x in pending if x.get("id")]
            try:
                st.cursor = st.queue_ids.index(target)
            except ValueError:
                st.cursor = 0
            msg = (
                f"Recorded approve for approval {_short_id(target)}. "
                f"You asked to approve: {spoken}"
            )
            st.last_spoken = msg
            return msg

        elif m_did and not RE_DENY_IT.match(t):
            token = m_did.group(1)
            try:
                pending = await _get_pending(client, base)
            except Exception as e:
                log.warning("pending fetch: %s", e)
                return "I could not reach the control plane for approvals."
            target = _find_id_by_token(pending, token)
            if not target:
                return f"No pending approval matches id {token}."
            if not api_key.strip():
                return "Control plane API key is not configured; I cannot submit that decision."
            try:
                bundle = await _get_bundle(client, base, target)
                spoken = _spoken_from_bundle(bundle)
                await _post_decision(client, base, target, "denied", api_key)
            except Exception as e:
                log.warning("deny by id: %s", e)
                return "That denial failed. Check the control plane or try again."
            msg = (
                f"Recorded deny for approval {_short_id(target)}. "
                f"That was: {spoken}"
            )
            st.last_spoken = msg
            return msg

        # --- List / queue ---
        if RE_WHAT_NEEDS.search(t):
            try:
                pending = await _get_pending(client, base)
            except Exception as e:
                log.warning("pending: %s", e)
                return "I could not load pending approvals from the control plane."
            st.queue_ids = [str(x.get("id")) for x in pending if x.get("id")]
            st.cursor = 0
            summary = _queue_summary_lines(pending)
            if not pending:
                st.last_spoken = summary
                return summary
            tail = (
                " The first approval is focused. Say read the next approval for full details, "
                "or say next approval to move in the queue."
            )
            out = summary + tail
            st.last_spoken = out
            return out

        # --- Read focused / next ---
        if RE_READ_NEXT.search(t):
            try:
                pending = await _get_pending(client, base)
            except Exception as e:
                log.warning("pending: %s", e)
                return "I could not load approvals."
            st.queue_ids = [str(x.get("id")) for x in pending if x.get("id")]
            if not st.queue_ids:
                return "There are no pending approvals."
            if st.cursor >= len(st.queue_ids):
                st.cursor = 0
            aid = st.queue_ids[st.cursor]
            try:
                bundle = await _get_bundle(client, base, aid)
            except Exception as e:
                log.warning("bundle: %s", e)
                return "I could not load that approval bundle."
            spoken = _spoken_from_bundle(bundle)
            intro = f"Approval {_short_id(aid)}. "
            out = intro + spoken
            st.last_spoken = out
            return out

        if RE_READ_AGAIN.search(t):
            if st.last_spoken:
                return st.last_spoken
            return "There is nothing to repeat yet. Say what needs my approval first."

        if RE_NEXT.search(t):
            if not st.queue_ids:
                try:
                    pending = await _get_pending(client, base)
                except Exception:
                    return "I could not load the approval queue."
                st.queue_ids = [str(x.get("id")) for x in pending if x.get("id")]
            if not st.queue_ids:
                return "No pending approvals."
            st.cursor = min(st.cursor + 1, len(st.queue_ids) - 1)
            aid = st.queue_ids[st.cursor]
            try:
                bundle = await _get_bundle(client, base, aid)
            except Exception:
                return "Could not load that approval."
            spoken = _spoken_from_bundle(bundle)
            out = f"Now focused on approval {_short_id(aid)}. {spoken}"
            st.last_spoken = out
            return out

        if RE_PREV.search(t):
            if not st.queue_ids:
                return "Say what needs my approval to load the queue first."
            st.cursor = max(st.cursor - 1, 0)
            aid = st.queue_ids[st.cursor]
            try:
                bundle = await _get_bundle(client, base, aid)
            except Exception:
                return "Could not load that approval."
            spoken = _spoken_from_bundle(bundle)
            out = f"Now focused on approval {_short_id(aid)}. {spoken}"
            st.last_spoken = out
            return out

        # --- Approve / deny focused (explicit phrasing only) ---
        if RE_APPROVE_IT.match(t):
            fid = (
                st.queue_ids[st.cursor]
                if st.queue_ids and 0 <= st.cursor < len(st.queue_ids)
                else None
            )
            if not fid:
                return (
                    "There is no approval in focus. Say what needs my approval, "
                    "then read the next approval before approving."
                )
            if not api_key.strip():
                return "API key is not set; I cannot submit an approval decision."
            try:
                bundle = await _get_bundle(client, base, fid)
                spoken = _spoken_from_bundle(bundle)
                await _post_decision(client, base, fid, "approved", api_key)
            except Exception as e:
                log.warning("approve it: %s", e)
                return "The approval failed. Check the control plane."
            msg = (
                f"Approved. You authorized: {_short_id(fid)}. "
                f"Summary was: {spoken}"
            )
            st.last_spoken = msg
            # Refresh queue after decision
            try:
                pending = await _get_pending(client, base)
                st.queue_ids = [str(x.get("id")) for x in pending if x.get("id")]
                st.cursor = 0
            except Exception:
                pass
            return msg

        if RE_DENY_IT.match(t):
            fid = (
                st.queue_ids[st.cursor]
                if st.queue_ids and 0 <= st.cursor < len(st.queue_ids)
                else None
            )
            if not fid:
                return (
                    "There is no approval in focus. Say what needs my approval first, "
                    "then read the next approval."
                )
            if not api_key.strip():
                return "API key is not set; I cannot submit a denial."
            try:
                bundle = await _get_bundle(client, base, fid)
                spoken = _spoken_from_bundle(bundle)
                await _post_decision(client, base, fid, "denied", api_key)
            except Exception as e:
                log.warning("deny it: %s", e)
                return "The denial failed. Check the control plane."
            msg = f"Denied. That was: {spoken}"
            st.last_spoken = msg
            try:
                pending = await _get_pending(client, base)
                st.queue_ids = [str(x.get("id")) for x in pending if x.get("id")]
                st.cursor = 0
            except Exception:
                pass
            return msg

    return None
