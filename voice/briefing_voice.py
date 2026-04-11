"""
Voice Mission Briefing + Status Readout v1 — read-only operator truth.

Uses control plane GETs only (missions, approvals/pending, operator/heartbeat, operator/workers,
system/health, operator/activity, optional operator/cost-events). No invented state; short-first TTS.
Ephemeral per-WebSocket focus list + cursor (not persisted).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("jarvis.voice.briefing")

_sessions: dict[int, VoiceBriefingState] = {}


@dataclass
class VoiceBriefingState:
    """Ranked mission ids for next/previous/read-top; ephemeral only."""

    mission_ids: list[str] = field(default_factory=list)
    cursor: int = 0
    last_headline: str | None = None


def get_voice_briefing_state(ws_key: int) -> VoiceBriefingState:
    if ws_key not in _sessions:
        _sessions[ws_key] = VoiceBriefingState()
    return _sessions[ws_key]


def forget_voice_briefing_state(ws_key: int) -> None:
    _sessions.pop(ws_key, None)


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def _short_id(full_id: str) -> str:
    s = str(full_id).replace("-", "")
    return s[:8] if len(s) >= 8 else s


def _mission_rank(m: dict[str, Any]) -> tuple[int, str]:
    """Higher = more important for briefing. Tie-break by updated_at."""
    st = str(m.get("status") or "").lower()
    if st == "failed":
        return (100, str(m.get("updated_at") or ""))
    if st in ("pending", "awaiting_approval"):
        return (80, str(m.get("updated_at") or ""))
    if st in ("in_progress", "running", "active"):
        return (60, str(m.get("updated_at") or ""))
    if st == "complete":
        return (10, str(m.get("updated_at") or ""))
    return (40, str(m.get("updated_at") or ""))


def rank_mission_ids(missions: list[dict[str, Any]], *, limit: int = 12) -> list[str]:
    scored = sorted(missions, key=_mission_rank, reverse=True)
    out: list[str] = []
    for m in scored:
        mid = m.get("id")
        if mid:
            out.append(str(mid))
        if len(out) >= limit:
            break
    return out


def _truncate(s: str, max_len: int = 220) -> str:
    t = " ".join(s.split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


async def _get_json(client: httpx.AsyncClient, url: str) -> Any:
    r = await client.get(url, timeout=25.0)
    r.raise_for_status()
    return r.json()


async def fetch_operator_snapshot(
    client: httpx.AsyncClient, base: str
) -> dict[str, Any]:
    """Parallel GETs; partial failure is recorded in errors."""
    base = base.rstrip("/")
    out: dict[str, Any] = {
        "missions": [],
        "pending_approvals": [],
        "heartbeat": None,
        "workers": None,
        "health": None,
        "activity": None,
        "cost_rollup": None,
        "errors": [],
    }

    async def wrap(name: str, coro: Any) -> tuple[str, Any | None]:
        try:
            return name, await coro
        except Exception as e:
            log.warning("%s: %s", name, e)
            return name, None

    results = await asyncio.gather(
        wrap("missions", _get_json(client, f"{base}/api/v1/missions?limit=120&offset=0")),
        wrap("pending_approvals", _get_json(client, f"{base}/api/v1/approvals/pending")),
        wrap("heartbeat", _get_json(client, f"{base}/api/v1/operator/heartbeat")),
        wrap("workers", _get_json(client, f"{base}/api/v1/operator/workers")),
        wrap("health", _get_json(client, f"{base}/api/v1/system/health")),
        wrap("activity", _get_json(client, f"{base}/api/v1/operator/activity?limit=12")),
        wrap("cost_rollup", _get_json(client, f"{base}/api/v1/operator/cost-events?limit=1&offset=0")),
    )
    for name, val in results:
        if val is None:
            out["errors"].append(name)
            continue
        if name == "missions":
            out["missions"] = val if isinstance(val, list) else []
        elif name == "pending_approvals":
            out["pending_approvals"] = val if isinstance(val, list) else []
        else:
            out[name] = val

    # Cost: one line for unknown-cost attention if rollup available
    cr = out.get("cost_rollup") or {}
    if isinstance(cr, dict) and isinstance(cr.get("rollup"), dict):
        unk = cr["rollup"].get("unknown_count")
        if isinstance(unk, int) and unk > 0:
            out["cost_unknown_hint"] = unk

    return out


def compose_whats_happening(snap: dict[str, Any]) -> str:
    missions = snap.get("missions") or []
    pending = snap.get("pending_approvals") or []
    hb = snap.get("heartbeat") or {}
    wr = snap.get("workers") or {}
    health = snap.get("health") or {}
    errs = snap.get("errors") or []
    cost_u = snap.get("cost_unknown_hint")

    n_m = len(missions)
    n_p = len(pending)
    hb_open = int(hb.get("open_count") or 0)

    parts: list[str] = []
    if errs:
        parts.append(
            "Some operator data did not load; I will only summarize what I have."
        )
    if isinstance(cost_u, int) and cost_u > 0:
        parts.append(
            f"Cost accounting: {cost_u} unknown-cost event{'s' if cost_u != 1 else ''} on file."
        )

    status_bits: list[str] = []
    cp = health.get("control_plane") or {}
    if isinstance(cp, dict) and str(cp.get("status") or "") != "healthy":
        status_bits.append("control plane check is not green")

    wr_reg = wr.get("workers") if isinstance(wr, dict) else None
    if isinstance(wr_reg, list):
        stale = sum(
            1
            for w in wr_reg
            if isinstance(w, dict)
            and str(w.get("status") or "").lower() in ("offline", "stopped", "unknown")
        )
        if stale:
            status_bits.append(f"{stale} worker row(s) look unhealthy or stale")

    if status_bits:
        parts.append("Heads up: " + "; ".join(status_bits) + ".")

    parts.append(
        f"Overview: {n_m} missions on record, {n_p} pending approvals, "
        f"{hb_open} open heartbeat finding{'s' if hb_open != 1 else ''}."
    )

    ranked = rank_mission_ids(missions if isinstance(missions, list) else [], limit=3)
    if ranked:
        top = next((m for m in missions if str(m.get("id")) == ranked[0]), None)
        if isinstance(top, dict):
            parts.append(
                f"Top mission by priority: «{_truncate(str(top.get('title') or 'Untitled'), 80)}», "
                f"status {top.get('status') or 'unknown'}."
            )
    else:
        parts.append("No missions returned.")

    return _truncate(" ".join(parts), 480)


def compose_what_needs_attention(snap: dict[str, Any]) -> str:
    pending = snap.get("pending_approvals") or []
    hb = snap.get("heartbeat") or {}
    missions = snap.get("missions") or []
    findings = hb.get("open_findings") or []

    lines: list[str] = []
    if pending:
        lines.append(
            f"{len(pending)} pending approval{'s' if len(pending) != 1 else ''} need a decision."
        )
    if findings:
        for f in findings[:3]:
            if not isinstance(f, dict):
                continue
            lines.append(
                f"Heartbeat: {f.get('finding_type') or 'finding'} — "
                f"{_truncate(str(f.get('summary') or ''), 100)}"
            )
    failed = [m for m in missions if str(m.get("status") or "").lower() == "failed"]
    if failed:
        t = str(failed[0].get("title") or "Untitled")
        lines.append(f"Failed mission: «{_truncate(t, 80)}».")

    if not lines:
        return "Nothing critical from approvals, heartbeat failures, or failed missions in the snapshot I have."

    return _truncate(" ".join(lines), 480)


def compose_what_am_i_working_on(snap: dict[str, Any]) -> str:
    missions = snap.get("missions") or []
    active = [
        m
        for m in missions
        if str(m.get("status") or "").lower()
        not in ("complete", "failed", "cancelled", "canceled")
    ]
    if not active:
        return "No non-terminal missions in the current list, or data was incomplete."

    ranked = rank_mission_ids(active, limit=5)
    bits: list[str] = []
    for mid in ranked[:5]:
        m = next((x for x in active if str(x.get("id")) == mid), None)
        if not m:
            continue
        bits.append(
            f"«{_truncate(str(m.get('title') or 'Untitled'), 60)}» ({m.get('status')})"
        )
    return _truncate("Active work: " + "; ".join(bits), 480)


def compose_whats_running(snap: dict[str, Any]) -> str:
    missions = snap.get("missions") or []
    wr = snap.get("workers") or {}
    running = [
        m
        for m in missions
        if str(m.get("status") or "").lower() in ("in_progress", "running", "active", "pending")
    ]
    wr_list = wr.get("workers") if isinstance(wr, dict) else []
    healthy = 0
    if isinstance(wr_list, list):
        healthy = sum(
            1
            for w in wr_list
            if isinstance(w, dict)
            and str(w.get("status") or "").lower() == "healthy"
        )
    parts = [
        f"Missions not complete: {len(running)}. "
        f"Workers reporting healthy in registry: {healthy} of {len(wr_list) if isinstance(wr_list, list) else 0}."
    ]
    return _truncate(" ".join(parts), 420)


def compose_whats_blocked(snap: dict[str, Any]) -> str:
    pending = snap.get("pending_approvals") or []
    missions = snap.get("missions") or []
    hb = snap.get("heartbeat") or {}
    findings = hb.get("open_findings") or []

    chunks: list[str] = []
    if pending:
        chunks.append(f"{len(pending)} approvals waiting.")
    failed = [m for m in missions if str(m.get("status") or "").lower() == "failed"]
    if failed:
        chunks.append(
            f"Failed missions: {len(failed)}. First: «{_truncate(str(failed[0].get('title') or ''), 70)}»."
        )
    stall = [f for f in findings if isinstance(f, dict) and "stall" in str(f.get("finding_type") or "").lower()]
    for f in stall[:2]:
        chunks.append(f"Supervision: {_truncate(str(f.get('summary') or ''), 120)}")
    if not chunks:
        return "No obvious blockers in approvals, failed missions, or stall findings from this snapshot."
    return _truncate(" ".join(chunks), 480)


def compose_what_changed_recently(snap: dict[str, Any]) -> str:
    act = snap.get("activity") or {}
    items = act.get("items") or []
    if not items:
        return "No recent activity items returned."
    bits: list[str] = []
    for it in items[:4]:
        if not isinstance(it, dict):
            continue
        bits.append(
            f"{it.get('category') or 'event'}: {_truncate(str(it.get('title') or it.get('summary') or ''), 90)}"
        )
    return _truncate("Recent: " + " · ".join(bits), 480)


async def _fetch_bundle(
    client: httpx.AsyncClient, base: str, mission_id: str
) -> dict[str, Any] | None:
    try:
        return await _get_json(client, f"{base.rstrip('/')}/api/v1/missions/{mission_id}/bundle")
    except Exception as e:
        log.warning("bundle %s: %s", mission_id, e)
        return None


def _speak_mission_bundle(bundle: dict[str, Any]) -> str:
    m = bundle.get("mission") or {}
    title = str(m.get("title") or "Untitled")
    st = str(m.get("status") or "unknown")
    evs = bundle.get("events") or []
    last_ev = ""
    if evs and isinstance(evs[-1], dict):
        last_ev = str(evs[-1].get("event_type") or "")
    appr = bundle.get("approvals") or []
    pend_a = [a for a in appr if isinstance(a, dict) and str(a.get("status")) == "pending"]
    rc = bundle.get("receipts") or []
    last_rc = ""
    if rc and isinstance(rc[-1], dict):
        last_rc = str(rc[-1].get("receipt_type") or "")

    bits = [
        f"Mission «{_truncate(title, 100)}», status {st}.",
    ]
    if pend_a:
        bits.append(f"{len(pend_a)} pending approval(s) on this mission.")
    if last_ev:
        bits.append(f"Latest timeline event type: {last_ev}.")
    if last_rc:
        bits.append(f"Latest receipt type: {last_rc}.")
    return _truncate(" ".join(bits), 500)


# --- Intent regex (avoid overlap with approval_voice: use "my attention" not "my approval") ---

RE_WHATS_HAPPENING = re.compile(
    r"\b(what\s+is\s+happening|what'?s\s+happening|what\s+is\s+going\s+on|"
    r"give\s+me\s+a\s+status|status\s+overview|big\s+picture)\b",
    re.I,
)
RE_NEEDS_ATTENTION = re.compile(
    r"\b(what\s+needs\s+my\s+attention|what\s+should\s+I\s+focus\s+on|"
    r"what\s+is\s+urgent|priorities)\b",
    re.I,
)
RE_WORKING_ON = re.compile(
    r"\b(what\s+am\s+I\s+working\s+on|what\s+are\s+we\s+working\s+on|"
    r"current\s+missions|active\s+missions)\b",
    re.I,
)
RE_WHATS_RUNNING = re.compile(
    r"\b(what'?s\s+running|what\s+is\s+running|what\s+is\s+in\s+progress)\b",
    re.I,
)
RE_WHATS_BLOCKED = re.compile(
    r"\b(what'?s\s+blocked|what\s+is\s+blocked|blockers|what\s+is\s+stuck)\b",
    re.I,
)
RE_READ_TOP_MISSION = re.compile(
    r"\b(read\s+(me\s+)?(the\s+)?top\s+mission|read\s+the\s+focused\s+mission|"
    r"describe\s+the\s+top\s+mission)\b",
    re.I,
)
RE_NEXT_MISSION = re.compile(
    r"\b(next\s+mission|go\s+to\s+the\s+next\s+mission)\b",
    re.I,
)
RE_PREV_MISSION = re.compile(
    r"\b(previous\s+mission|prior\s+mission|back\s+one\s+mission)\b",
    re.I,
)
RE_WHAT_CHANGED = re.compile(
    r"\b(what\s+changed\s+recently|what\s+is\s+new|recent\s+changes)\b",
    re.I,
)


async def try_handle_voice_briefing(
    text: str,
    ws_key: int,
    *,
    control_plane_url: str,
    api_key: str,
) -> str | None:
    """
    Read-only briefing. Return spoken string or None to fall through (commands / approval / Ollama).
    """
    _ = api_key  # reserved; briefing uses public GETs only
    t = _norm(text)
    if not t:
        return None

    st = get_voice_briefing_state(ws_key)
    base = control_plane_url.rstrip("/")

    async with httpx.AsyncClient() as client:
        snap = await fetch_operator_snapshot(client, base)

        missions = snap.get("missions") or []
        if not isinstance(missions, list):
            missions = []

        def _refresh_rank() -> None:
            st.mission_ids = rank_mission_ids(missions, limit=12)
            st.cursor = 0

        if RE_WHATS_HAPPENING.search(t):
            msg = compose_whats_happening(snap)
            st.last_headline = msg
            _refresh_rank()
            return msg

        if RE_NEEDS_ATTENTION.search(t):
            msg = compose_what_needs_attention(snap)
            st.last_headline = msg
            _refresh_rank()
            return msg

        if RE_WORKING_ON.search(t):
            msg = compose_what_am_i_working_on(snap)
            st.last_headline = msg
            _refresh_rank()
            return msg

        if RE_WHATS_RUNNING.search(t):
            msg = compose_whats_running(snap)
            st.last_headline = msg
            _refresh_rank()
            return msg

        if RE_WHATS_BLOCKED.search(t):
            msg = compose_whats_blocked(snap)
            st.last_headline = msg
            _refresh_rank()
            return msg

        if RE_WHAT_CHANGED.search(t):
            msg = compose_what_changed_recently(snap)
            st.last_headline = msg
            return msg

        if RE_READ_TOP_MISSION.search(t):
            if not st.mission_ids:
                _refresh_rank()
            if not st.mission_ids:
                return "There are no missions to read. Try what's happening to refresh context."
            mid = st.mission_ids[st.cursor]
            bundle = await _fetch_bundle(client, base, mid)
            if not bundle:
                return "I could not load that mission bundle from the control plane."
            msg = _speak_mission_bundle(bundle)
            st.last_headline = msg
            return msg

        if RE_NEXT_MISSION.search(t):
            if not st.mission_ids:
                _refresh_rank()
            if not st.mission_ids:
                return "No mission list in focus. Say what's happening first."
            st.cursor = min(st.cursor + 1, len(st.mission_ids) - 1)
            mid = st.mission_ids[st.cursor]
            bundle = await _fetch_bundle(client, base, mid)
            if not bundle:
                return "Could not load that mission."
            msg = f"Mission {_short_id(mid)}. {_speak_mission_bundle(bundle)}"
            st.last_headline = msg
            return msg

        if RE_PREV_MISSION.search(t):
            if not st.mission_ids:
                return "Say what's happening to load missions first."
            st.cursor = max(st.cursor - 1, 0)
            mid = st.mission_ids[st.cursor]
            bundle = await _fetch_bundle(client, base, mid)
            if not bundle:
                return "Could not load that mission."
            msg = f"Mission {_short_id(mid)}. {_speak_mission_bundle(bundle)}"
            st.last_headline = msg
            return msg

    return None
