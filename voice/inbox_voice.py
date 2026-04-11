"""
Voice Inbox Triage v1 — read-only summary + explicit triage phrases only.

TRUTH_SOURCE: GET /api/v1/operator/inbox; POST .../acknowledge|snooze|dismiss with x-api-key.
Ephemeral per-WebSocket state only (not control plane). Does not resolve approvals — use approval_voice.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger("jarvis.voice.inbox")

_sessions: dict[int, VoiceInboxState] = {}


@dataclass
class VoiceInboxState:
    """Focused inbox queue for one WebSocket — keys align with GET /operator/inbox items."""

    item_keys: list[str] = field(default_factory=list)
    items_cache: list[dict[str, Any]] = field(default_factory=list)
    cursor: int = 0
    last_spoken: str | None = None


def get_voice_inbox_state(ws_key: int) -> VoiceInboxState:
    if ws_key not in _sessions:
        _sessions[ws_key] = VoiceInboxState()
    return _sessions[ws_key]


def forget_voice_inbox_state(ws_key: int) -> None:
    _sessions.pop(ws_key, None)


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def _truncate(s: str, max_len: int = 320) -> str:
    t = " ".join(s.split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


async def _get_inbox(
    client: httpx.AsyncClient,
    base: str,
    api_key: str,
    *,
    status: str = "open",
    limit: int = 120,
) -> dict[str, Any]:
    base = base.rstrip("/")
    url = f"{base}/api/v1/operator/inbox"
    headers = {"x-api-key": api_key or ""}
    r = await client.get(
        url,
        params={"status": status, "limit": limit},
        headers=headers,
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def _sync_state_from_payload(st: VoiceInboxState, data: dict[str, Any]) -> None:
    items = data.get("items") or []
    if not isinstance(items, list):
        items = []
    st.items_cache = [x for x in items if isinstance(x, dict)]
    st.item_keys = [str(x.get("item_key") or "") for x in st.items_cache if x.get("item_key")]
    if st.cursor >= len(st.item_keys):
        st.cursor = max(0, len(st.item_keys) - 1)


def _handoff_sentence(it: dict[str, Any]) -> str:
    sk = str(it.get("source_kind") or "")
    if sk == "approval":
        return "This is an approval item. Review it in Approvals, or use the approval voice flow to hear details and approve or deny — I will not decide from the inbox."
    if sk == "heartbeat":
        ft = str(it.get("meta", {}).get("finding_type") or "")
        if ft.startswith("cost_"):
            return "This is a cost guardrail signal. Open Cost and Usage for numbers."
        if ft == "stale_worker":
            return "This relates to workers. Check the Workers page."
        if "system_degraded" in ft or (it.get("meta") or {}).get("service_component"):
            return "This is a system health signal. Open System Health."
        return "This is a supervision finding from heartbeat. See Activity or the linked surface."
    if sk == "integration_failure":
        return "This is a failed governed integration step. Open the mission timeline."
    if sk == "mission_failure":
        return "This mission is in a terminal failed or blocked state. Open the mission for details."
    return "Use Command Center to follow the link for this item."


def _speak_one_item(it: dict[str, Any]) -> str:
    head = str(it.get("headline") or "Inbox item").strip()
    summ = _truncate(str(it.get("summary") or ""), 280)
    sev = str(it.get("severity") or "")
    core = f"{head}. {summ}".strip()
    if sev:
        core = f"Severity {sev}. {core}"
    return _truncate(f"{core} {_handoff_sentence(it)}", 900)


def _summary_speech(data: dict[str, Any]) -> str:
    c = data.get("counts") or {}
    items = data.get("items") or []
    if not isinstance(items, list):
        items = []
    urgent = int(c.get("urgent") or 0)
    att = int(c.get("attention") or 0)
    tot = int(c.get("total_visible") or 0)
    parts = [
        f"Inbox summary. Urgent: {urgent}. Attention: {att}. Open items: {tot}.",
    ]
    if items:
        top = items[0]
        if isinstance(top, dict):
            parts.append(f"Top item: {_truncate(str(top.get('headline') or ''), 160)}")
    else:
        parts.append("Nothing in the open inbox right now.")
    return _truncate(" ".join(parts), 700)


# --- Strict intents (no vague okay/got it/later) ---

RE_WHATS_IN_INBOX = re.compile(
    r"\b(what'?s\s+in\s+my\s+inbox|what\s+is\s+in\s+my\s+inbox|what'?s\s+in\s+the\s+inbox|"
    r"inbox\s+summary|tell\s+me\s+about\s+my\s+inbox)\b",
    re.I,
)
RE_READ_TOP_INBOX = re.compile(
    r"\b(read\s+me\s+(the\s+)?top\s+inbox\s+item|read\s+the\s+top\s+inbox\s+item)\b",
    re.I,
)
RE_NEXT_INBOX = re.compile(
    r"\b(next\s+inbox\s+item|next\s+item\s+in\s+the\s+inbox)\b",
    re.I,
)
RE_PREV_INBOX = re.compile(
    r"\b(previous\s+inbox\s+item|prior\s+inbox\s+item|back\s+one\s+inbox\s+item)\b",
    re.I,
)

RE_ACK = re.compile(r"^(please\s+)?acknowledge\s+it[\s.!]*$", re.I)
RE_SNOOZE_1H = re.compile(r"^(please\s+)?snooze\s+it\s+for\s+one\s+hour[\s.!]*$", re.I)
RE_SNOOZE_4H = re.compile(r"^(please\s+)?snooze\s+it\s+for\s+four\s+hours[\s.!]*$", re.I)
RE_DISMISS = re.compile(r"^(please\s+)?dismiss\s+it[\s.!]*$", re.I)

RE_WHAT_KIND = re.compile(
    r"\b(what\s+kind\s+of\s+item\s+is\s+this|what\s+is\s+this\s+inbox\s+item)\b",
    re.I,
)
RE_OPEN_APPROVAL = re.compile(
    r"\b(open\s+the\s+approval|go\s+to\s+approvals)\b",
    re.I,
)
RE_OPEN_MISSION = re.compile(r"\b(open\s+the\s+mission)\b", re.I)


async def _post_inbox_action(
    client: httpx.AsyncClient,
    base: str,
    api_key: str,
    item_key: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> None:
    base = base.rstrip("/")
    enc = quote(item_key, safe="")
    url = f"{base}/api/v1/operator/inbox/{enc}/{path}"
    headers = {"x-api-key": api_key or "", "Content-Type": "application/json"}
    r = await client.post(url, headers=headers, json=json_body or {}, timeout=30.0)
    r.raise_for_status()


def _require_focus(st: VoiceInboxState) -> dict[str, Any] | None:
    if not st.item_keys or not st.items_cache:
        return None
    if st.cursor < 0 or st.cursor >= len(st.items_cache):
        return None
    cur = st.items_cache[st.cursor]
    return cur if isinstance(cur, dict) else None


async def try_handle_voice_inbox(
    text: str,
    ws_key: int,
    *,
    control_plane_url: str,
    api_key: str,
) -> str | None:
    """
    Inbox readout + triage. Return spoken string or None to fall through.
    Requires CONTROL_PLANE_API_KEY for POST triage; GET inbox works without key if server allows.
    """
    t = _norm(text)
    if not t:
        return None

    st = get_voice_inbox_state(ws_key)
    base = control_plane_url.rstrip("/")

    async with httpx.AsyncClient() as client:
        # --- Read-only intents (refresh queue) ---
        if RE_WHATS_IN_INBOX.search(t):
            try:
                data = await _get_inbox(client, base, api_key)
            except Exception as e:
                log.warning("inbox GET failed: %s", e)
                return "I could not load the operator inbox from the control plane."
            _sync_state_from_payload(st, data)
            st.cursor = 0
            msg = _summary_speech(data)
            st.last_spoken = msg
            return msg

        if RE_READ_TOP_INBOX.search(t):
            try:
                data = await _get_inbox(client, base, api_key)
            except Exception as e:
                log.warning("inbox GET failed: %s", e)
                return "I could not load the operator inbox."
            _sync_state_from_payload(st, data)
            st.cursor = 0
            if not st.items_cache:
                msg = "Your open inbox is empty."
                st.last_spoken = msg
                return msg
            it = st.items_cache[0]
            msg = _speak_one_item(it)
            st.last_spoken = msg
            return msg

        if RE_NEXT_INBOX.search(t):
            try:
                data = await _get_inbox(client, base, api_key)
            except Exception as e:
                log.warning("inbox GET failed: %s", e)
                return "I could not refresh the inbox."
            _sync_state_from_payload(st, data)
            if not st.item_keys:
                return "There are no inbox items. Say what's in my inbox first."
            st.cursor = min(st.cursor + 1, len(st.item_keys) - 1)
            it = st.items_cache[st.cursor]
            msg = f"Inbox item {st.cursor + 1} of {len(st.item_keys)}. {_speak_one_item(it)}"
            st.last_spoken = msg
            return msg

        if RE_PREV_INBOX.search(t):
            try:
                data = await _get_inbox(client, base, api_key)
            except Exception as e:
                log.warning("inbox GET failed: %s", e)
                return "I could not refresh the inbox."
            _sync_state_from_payload(st, data)
            if not st.item_keys:
                return "There are no inbox items. Say what's in my inbox first."
            st.cursor = max(st.cursor - 1, 0)
            it = st.items_cache[st.cursor]
            msg = f"Inbox item {st.cursor + 1} of {len(st.item_keys)}. {_speak_one_item(it)}"
            st.last_spoken = msg
            return msg

        # --- Context questions (need focus + fresh data) ---
        if RE_WHAT_KIND.search(t) or RE_OPEN_APPROVAL.search(t) or RE_OPEN_MISSION.search(t):
            try:
                data = await _get_inbox(client, base, api_key)
            except Exception as e:
                log.warning("inbox GET failed: %s", e)
                return "I could not refresh the inbox."
            _sync_state_from_payload(st, data)
            focused = _require_focus(st)
            if focused is None:
                return (
                    "There is no focused inbox item. Say what's in my inbox or read me the top inbox item first."
                )
            # Re-align cursor to same item_key if still present
            key = str(focused.get("item_key") or "")
            new_keys = [str(x.get("item_key")) for x in st.items_cache if x.get("item_key")]
            if key and key in new_keys:
                st.cursor = new_keys.index(key)
                focused = st.items_cache[st.cursor]
            else:
                return "That inbox item is no longer open. Say what's in my inbox to refresh."

            if RE_WHAT_KIND.search(t):
                sk = str(focused.get("source_kind") or "unknown")
                msg = f"This is a {sk} item. {_handoff_sentence(focused)}"
                st.last_spoken = msg
                return msg
            if RE_OPEN_APPROVAL.search(t):
                if str(focused.get("source_kind")) != "approval":
                    return "The focused item is not an approval. Ask what kind of item this is."
                msg = "Open Approvals in Command Center to review. I am not opening screens from voice in this pass."
                st.last_spoken = msg
                return msg
            if RE_OPEN_MISSION.search(t):
                if not focused.get("mission_id"):
                    return "This item does not have a single mission link. Check the summary for where to go."
                msg = "Open Missions in Command Center and select the mission from this item's link. I am not opening screens from voice in this pass."
                st.last_spoken = msg
                return msg

        # --- Triage (explicit phrases only; require API key and focus) ---
        if not api_key.strip():
            if RE_ACK.match(t) or RE_SNOOZE_1H.match(t) or RE_SNOOZE_4H.match(t) or RE_DISMISS.match(t):
                return "Inbox triage needs a control plane API key on the voice server. I cannot acknowledge or snooze yet."

        if RE_ACK.match(t) or RE_SNOOZE_1H.match(t) or RE_SNOOZE_4H.match(t) or RE_DISMISS.match(t):
            try:
                data = await _get_inbox(client, base, api_key)
            except Exception as e:
                log.warning("inbox GET failed: %s", e)
                return "I could not refresh the inbox before acting."
            _sync_state_from_payload(st, data)
            focused = _require_focus(st)
            if focused is None:
                return (
                    "There is no focused inbox item. Say read me the top inbox item or what's in my inbox first."
                )
            item_key = str(focused.get("item_key") or "")
            new_keys = st.item_keys
            if item_key not in new_keys:
                return "That inbox item is no longer open. Say what's in my inbox to refresh the queue."

            try:
                if RE_ACK.match(t):
                    await _post_inbox_action(client, base, api_key, item_key, "acknowledge")
                    msg = "Acknowledged. It will stay out of your default open inbox until the underlying issue changes."
                elif RE_SNOOZE_1H.match(t):
                    await _post_inbox_action(client, base, api_key, item_key, "snooze", json_body={"minutes": 60})
                    msg = "Snoozed for one hour."
                elif RE_SNOOZE_4H.match(t):
                    await _post_inbox_action(client, base, api_key, item_key, "snooze", json_body={"minutes": 240})
                    msg = "Snoozed for four hours."
                else:
                    await _post_inbox_action(client, base, api_key, item_key, "dismiss")
                    msg = "Dismissed for this inbox view."
            except Exception as e:
                log.warning("inbox triage POST failed: %s", e)
                return "I could not apply that inbox action. Check the control plane and try again."

            st.last_spoken = msg
            # Refresh queue after mutation
            try:
                data2 = await _get_inbox(client, base, api_key)
                _sync_state_from_payload(st, data2)
                st.cursor = min(st.cursor, max(0, len(st.item_keys) - 1))
            except Exception:
                pass
            return msg

    return None
