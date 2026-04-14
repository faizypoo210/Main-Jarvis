"""Unified control-plane intake for free-form voice (POST /api/v1/intake).

TRUTH_SOURCE: ``IntakeResponse`` JSON from ``services/control-plane/app/schemas/intake.py``.
Voice speaks ``reply.message``; mission subscription uses ``reply.mission_id`` when
``outcome == mission_created``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

log = logging.getLogger("jarvis.voice.intake")


@dataclass
class VoiceIntakeResult:
    """Result of a voice intake call (success or honest failure)."""

    ok: bool
    http_status: int | None = None
    error_message: str | None = None
    outcome: str | None = None
    message: str = ""
    mission_id: str | None = None
    reply_kind: str | None = None
    raw: dict[str, Any] | None = None


def _str_mission_id(value: Any) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def parse_intake_response(data: dict[str, Any]) -> VoiceIntakeResult:
    """Map control-plane ``IntakeResponse`` JSON to a voice result."""
    reply = data.get("reply")
    if not isinstance(reply, dict):
        reply = {}
    outcome = data.get("outcome")
    if outcome is not None:
        outcome = str(outcome).strip()
    msg = str(reply.get("message") or "").strip()
    kind = reply.get("kind")
    reply_kind = str(kind).strip() if kind is not None else None
    mid = _str_mission_id(reply.get("mission_id"))
    return VoiceIntakeResult(
        ok=True,
        http_status=200,
        outcome=outcome,
        message=msg,
        mission_id=mid,
        reply_kind=reply_kind,
        raw=data,
    )


def friendly_intake_failure(http_status: int | None, detail: str | None) -> str:
    """User-facing line when the control plane cannot complete intake."""
    d = (detail or "").strip()
    if d and len(d) < 400:
        return f"The control plane could not complete that request: {d}"
    return (
        "I could not reach the Jarvis control plane or it rejected the request. "
        "Check that the service is running and the API key is configured."
    )


async def post_voice_intake(
    client: httpx.AsyncClient,
    *,
    control_plane_url: str,
    api_key: str,
    text: str,
    surface_session_id: str | None,
    thread_mission_id: str | None,
    extra_context: dict[str, Any] | None = None,
) -> VoiceIntakeResult:
    """POST ``/api/v1/intake`` with voice defaults and optional session/mission context."""
    url = f"{control_plane_url.rstrip('/')}/api/v1/intake"
    body: dict[str, Any] = {"source_surface": "voice", "text": text}
    if surface_session_id:
        try:
            body["surface_session_id"] = str(UUID(surface_session_id.strip()))
        except ValueError:
            log.warning("voice intake: invalid surface_session_id; omitting")
    if thread_mission_id and str(thread_mission_id).strip():
        try:
            body["mission_id"] = str(UUID(str(thread_mission_id).strip()))
        except ValueError:
            log.warning("voice intake: invalid thread_mission_id; omitting")
    ctx: dict[str, Any] = {"voice": True}
    if extra_context:
        ctx.update(extra_context)
    body["context"] = ctx

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    try:
        r = await client.post(url, json=body, headers=headers)
    except httpx.RequestError as e:
        log.warning("voice intake request failed: %s", e)
        return VoiceIntakeResult(
            ok=False,
            error_message=friendly_intake_failure(None, str(e)),
        )

    if r.status_code != 200:
        detail: str | None = None
        try:
            j = r.json()
            detail = j.get("detail")
            if isinstance(detail, list):
                detail = " ".join(str(x) for x in detail[:3])
            elif detail is not None:
                detail = str(detail)
        except Exception:
            detail = (r.text or "")[:300] or None
        log.warning(
            "voice intake HTTP %s: %s",
            r.status_code,
            detail or r.reason_phrase,
        )
        return VoiceIntakeResult(
            ok=False,
            http_status=r.status_code,
            error_message=friendly_intake_failure(r.status_code, detail),
        )

    try:
        data = r.json()
    except Exception as e:
        log.warning("voice intake: invalid JSON: %s", e)
        return VoiceIntakeResult(
            ok=False,
            http_status=r.status_code,
            error_message=friendly_intake_failure(r.status_code, "invalid response"),
        )

    if not isinstance(data, dict):
        return VoiceIntakeResult(
            ok=False,
            http_status=r.status_code,
            error_message=friendly_intake_failure(r.status_code, None),
        )

    out = parse_intake_response(data)
    out.http_status = r.status_code
    if not out.message:
        out.message = out.outcome or "Done."
    return out
