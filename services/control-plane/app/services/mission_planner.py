"""Mission decomposition via local Ollama (planner prompt)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

_PLANNER_SYSTEM = (
    "You are a mission planner for Jarvis. Break the following command into 2-5 clear, sequential, "
    "actionable stages. Each stage must be a concrete action. Reply ONLY with a JSON array. "
    "Each item must have: id (short slug), title (action phrase), status ('pending'). "
    "No explanation, no markdown, just the JSON array."
)


def _first_json_array(text: str) -> list[Any] | None:
    s = (text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, list) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", s)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, list) else None
    except json.JSONDecodeError:
        return None


def _normalize_planned_item(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    sid = raw.get("id")
    title = raw.get("title")
    st = raw.get("status", "pending")
    if not isinstance(sid, str) or not sid.strip():
        return None
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(st, str) or st not in ("pending", "active", "complete", "failed"):
        st = "pending"
    return {"id": sid.strip(), "title": title.strip(), "status": st}


async def plan_mission(command: str, mission_id: str) -> list[dict[str, Any]]:
    """Return validated stage dicts; ``mission_id`` is for logging only."""
    _ = mission_id
    cmd = (command or "").strip()
    if not cmd:
        return [{"id": "stage-1", "title": "(empty command)", "status": "pending"}]

    settings = get_settings()
    base = (settings.OLLAMA_BASE_URL or "").strip().rstrip("/")
    model = (settings.JARVIS_LOCAL_MODEL or "").strip()
    if not base or not model:
        log.warning("mission_planner: missing OLLAMA_BASE_URL or JARVIS_LOCAL_MODEL")
        return [{"id": "stage-1", "title": cmd, "status": "pending"}]

    url = f"{base}/api/generate"
    body = {
        "model": model,
        "prompt": cmd,
        "system": _PLANNER_SYSTEM,
        "stream": False,
        "think": False,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            r = await client.post(url, json=body)
    except Exception as e:
        log.warning("mission_planner: ollama request failed: %s", e)
        return [{"id": "stage-1", "title": cmd, "status": "pending"}]

    if r.status_code >= 400:
        log.warning("mission_planner: ollama HTTP %s", r.status_code)
        return [{"id": "stage-1", "title": cmd, "status": "pending"}]

    try:
        data = r.json()
    except Exception as e:
        log.warning("mission_planner: invalid JSON response: %s", e)
        return [{"id": "stage-1", "title": cmd, "status": "pending"}]

    if not isinstance(data, dict):
        return [{"id": "stage-1", "title": cmd, "status": "pending"}]

    text = data.get("response")
    if not isinstance(text, str):
        return [{"id": "stage-1", "title": cmd, "status": "pending"}]

    arr = _first_json_array(text)
    if not arr:
        return [{"id": "stage-1", "title": cmd, "status": "pending"}]

    out: list[dict[str, Any]] = []
    for item in arr:
        norm = _normalize_planned_item(item)
        if norm:
            out.append(norm)

    if not out:
        return [{"id": "stage-1", "title": cmd, "status": "pending"}]
    return out


async def is_complex(command: str) -> bool:
    """True when the command looks like a multi-step mission (heuristic)."""
    words = (command or "").strip().split()
    if len(words) <= 6:
        return False
    low = (command or "").strip().lower()
    if low.startswith("open http") or low.startswith("open www"):
        return False
    for prefix in ("what", "who", "how many", "list", "show"):
        if low.startswith(prefix):
            return False
    return True
