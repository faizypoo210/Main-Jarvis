"""JARVIS Event Coordinator: Redis Streams router, DashClaw guard/outcomes, control plane status."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from redis.asyncio import Redis
from redis.exceptions import ResponseError

load_dotenv()

# Control plane (Jarvis API). Override via .env: CONTROL_PLANE_URL=http://localhost:8001
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8001")

# Mission status values (control plane missions)
ST_ACTIVE = "active"
ST_COMPLETE = "complete"
ST_FAILED = "failed"

STREAM_COMMANDS = "jarvis.commands"
STREAM_EXECUTION = "jarvis.execution"
STREAM_RECEIPTS = "jarvis.receipts"
STREAM_UPDATES = "jarvis.updates"

GROUP_COMMANDS = "jarvis-coordinator-commands"
GROUP_RECEIPTS = "jarvis-coordinator-receipts"
CONSUMER_NAME = f"coordinator-{os.getpid()}"

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

DASHCLAW_BASE_URL = os.environ.get("DASHCLAW_BASE_URL", "").rstrip("/")
DASHCLAW_API_KEY = os.environ.get("DASHCLAW_API_KEY", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("jarvis.coordinator")


async def post_to_control_plane(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST JSON to the control plane. Logs only; never raises."""
    base = CONTROL_PLANE_URL.rstrip("/")
    p = path if path.startswith("/") else f"/{path}"
    url = f"{base}{p}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            out = r.json()
            if not isinstance(out, dict):
                log.warning(
                    json.dumps(
                        {
                            "control_plane": "unexpected_response",
                            "path": path,
                            "detail": "response was not a JSON object",
                        }
                    )
                )
                return None
            log.info(
                json.dumps(
                    {
                        "control_plane": "ok",
                        "path": path,
                        "status_code": r.status_code,
                    }
                )
            )
            return out
    except Exception as e:
        log.warning(
            json.dumps(
                {
                    "control_plane": "fail",
                    "path": path,
                    "detail": str(e),
                }
            )
        )
        return None


def _normalize_risk_class(risk: str | None) -> str:
    if not risk:
        return "amber"
    r = risk.strip().lower()
    if r in ("green", "amber", "red"):
        return r
    return "amber"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _log_event(
    *,
    stream: str,
    event_type: str,
    mission_id: str,
    decision: str,
) -> None:
    payload = {
        "timestamp": _now_iso(),
        "stream": stream,
        "event_type": event_type,
        "mission_id": mission_id,
        "decision": decision,
    }
    log.info(json.dumps(payload, default=str))


def _decode_fields(raw: dict[Any, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in raw.items():
        ks = k.decode() if isinstance(k, bytes) else str(k)
        vs = v.decode() if isinstance(v, bytes) else (v if isinstance(v, str) else str(v))
        out[ks] = vs
    return out


def _parse_json_field(fields: dict[str, str], key: str) -> dict[str, Any]:
    raw = fields.get(key) or fields.get("payload") or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


async def _ensure_group(redis: Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


class Coordinator:
    def __init__(self) -> None:
        if not DASHCLAW_BASE_URL or not DASHCLAW_API_KEY:
            raise RuntimeError("DASHCLAW_BASE_URL and DASHCLAW_API_KEY are required.")

        self._redis: Redis | None = None
        self._dash_headers = {
            "x-api-key": DASHCLAW_API_KEY,
            "Content-Type": "application/json",
        }

    async def connect(self) -> None:
        self._redis = Redis.from_url(REDIS_URL, decode_responses=False)
        assert self._redis is not None
        await _ensure_group(self._redis, STREAM_COMMANDS, GROUP_COMMANDS)
        await _ensure_group(self._redis, STREAM_RECEIPTS, GROUP_RECEIPTS)

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    async def handle_command(self, redis: Redis, msg_id: bytes, fields: dict[Any, Any]) -> None:
        f = _decode_fields(fields)
        data = _parse_json_field(f, "data")
        text = (data.get("text") or data.get("command") or "").strip()
        mission_id = str(data.get("mission_id") or "").strip()

        if not mission_id:
            log.warning(
                json.dumps(
                    {
                        "error": "command_missing_mission_id",
                        "detail": "Redis command payload must include mission_id from control plane",
                    }
                )
            )
            await redis.xack(STREAM_COMMANDS, GROUP_COMMANDS, msg_id)
            return

        try:
            uuid.UUID(mission_id)
        except ValueError:
            log.warning(
                json.dumps(
                    {
                        "error": "command_invalid_mission_id",
                        "mission_id": mission_id,
                        "detail": "mission_id must be a UUID from the control plane",
                    }
                )
            )
            await redis.xack(STREAM_COMMANDS, GROUP_COMMANDS, msg_id)
            return

        async with httpx.AsyncClient(timeout=60.0) as client:
            _log_event(
                stream=STREAM_COMMANDS,
                event_type="command_received",
                mission_id=mission_id,
                decision="pending",
            )

            guard_body = {
                "mission_id": mission_id,
                "action_type": "command",
                "command": text,
                "context": data.get("context") or {},
            }
            gr = await client.post(
                f"{DASHCLAW_BASE_URL}/api/guard",
                headers=self._dash_headers,
                json=guard_body,
            )
            gr.raise_for_status()
            guard = gr.json()
            decision_raw = (guard.get("decision") or "").strip().lower()
            if decision_raw in ("allow", "approved"):
                decision = "allow"
            elif decision_raw in ("requires_approval", "approval", "review"):
                decision = "requires_approval"
            elif decision_raw in ("deny", "denied", "reject"):
                decision = "deny"
            else:
                decision = "requires_approval"

            risk = guard.get("risk_level")
            risk_s = str(risk).strip() if risk is not None else None
            risk_class = _normalize_risk_class(risk_s)
            dashclaw_decision_id = guard.get("decision_id") or guard.get("id")
            dashclaw_decision_id_s = (
                str(dashclaw_decision_id).strip() if dashclaw_decision_id is not None else None
            )
            action_type = (text[:128] if text else "(empty)") or "(empty)"

            if decision == "allow":
                await post_to_control_plane(
                    f"/api/v1/missions/{mission_id}/status",
                    {"status": ST_ACTIVE},
                )
                exec_payload = {
                    "mission_id": mission_id,
                    "command": text,
                    "dashclaw_decision": decision,
                }
                await redis.xadd(
                    STREAM_EXECUTION,
                    {"data": json.dumps(exec_payload, default=str)},
                )
                _log_event(
                    stream=STREAM_EXECUTION,
                    event_type="execution_publish",
                    mission_id=mission_id,
                    decision=decision,
                )

            elif decision == "requires_approval":
                approval_body: dict[str, Any] = {
                    "mission_id": mission_id,
                    "action_type": action_type,
                    "risk_class": risk_class,
                    "reason": guard.get("message"),
                    "command_text": text,
                    "requested_by": os.environ.get("JARVIS_OPERATOR") or "coordinator",
                    "requested_via": "system",
                }
                if dashclaw_decision_id_s:
                    approval_body["dashclaw_decision_id"] = dashclaw_decision_id_s
                ap_resp = await post_to_control_plane("/api/v1/approvals", approval_body)
                approval_id_str: str | None = None
                if ap_resp is not None:
                    aid = ap_resp.get("id")
                    if aid is not None:
                        approval_id_str = str(aid)
                up: dict[str, Any] = {
                    "type": "approval_required",
                    "mission_id": mission_id,
                    "message": guard.get("message") or "Approval required before execution.",
                    "command": text,
                }
                if approval_id_str:
                    up["approval_id"] = approval_id_str
                await redis.xadd(STREAM_UPDATES, {"data": json.dumps(up, default=str)})
                _log_event(
                    stream=STREAM_UPDATES,
                    event_type="approval_request",
                    mission_id=mission_id,
                    decision=decision,
                )

            else:
                await post_to_control_plane(
                    f"/api/v1/missions/{mission_id}/status",
                    {"status": ST_FAILED},
                )
                _log_event(
                    stream=STREAM_COMMANDS,
                    event_type="command_denied",
                    mission_id=mission_id,
                    decision="deny",
                )

        await redis.xack(STREAM_COMMANDS, GROUP_COMMANDS, msg_id)

    async def handle_receipt(self, redis: Redis, msg_id: bytes, fields: dict[Any, Any]) -> None:
        f = _decode_fields(fields)
        data = _parse_json_field(f, "data")
        mission_id = str(data.get("mission_id") or "").strip()
        if not mission_id:
            await redis.xack(STREAM_RECEIPTS, GROUP_RECEIPTS, msg_id)
            return

        status_raw = (data.get("status") or data.get("outcome") or "").strip().lower()
        summary = data.get("summary") or data.get("message") or ""

        async with httpx.AsyncClient(timeout=60.0) as client:
            ok = status_raw in ("complete", "success", "done", "ok")
            outcome_body = {
                "mission_id": mission_id,
                "outcome": "success" if ok else "failure",
                "evidence": data.get("evidence") or data,
                "summary": summary,
            }
            or_post = await client.post(
                f"{DASHCLAW_BASE_URL}/api/outcomes",
                headers=self._dash_headers,
                json=outcome_body,
            )
            or_post.raise_for_status()

            if ok:
                await post_to_control_plane(
                    f"/api/v1/missions/{mission_id}/status",
                    {"status": ST_COMPLETE},
                )
                decision = "complete"
            else:
                await post_to_control_plane(
                    f"/api/v1/missions/{mission_id}/status",
                    {"status": ST_FAILED},
                )
                decision = "failed"

            up = {
                "type": "receipt_summary",
                "mission_id": mission_id,
                "status": decision,
                "summary": summary,
            }
            await redis.xadd(STREAM_UPDATES, {"data": json.dumps(up, default=str)})

            _log_event(
                stream=STREAM_RECEIPTS,
                event_type="receipt_processed",
                mission_id=mission_id,
                decision=decision,
            )

            summ: str | None = None
            if summary is not None:
                s = str(summary).strip()
                if s:
                    summ = s[:500] if len(s) > 500 else s
            await post_to_control_plane(
                "/api/v1/receipts",
                {
                    "mission_id": mission_id,
                    "receipt_type": "agent_output",
                    "source": "coordinator",
                    "payload": data,
                    "summary": summ,
                },
            )

        await redis.xack(STREAM_RECEIPTS, GROUP_RECEIPTS, msg_id)

    async def _poll_stream(
        self,
        redis: Redis,
        stream: str,
        group: str,
        label: str,
        handler: Callable[[Redis, bytes, dict[Any, Any]], Awaitable[None]],
    ) -> None:
        while True:
            try:
                out = await redis.xreadgroup(
                    group,
                    CONSUMER_NAME,
                    {stream: ">"},
                    count=10,
                    block=5000,
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error(json.dumps({"error": f"{label}_loop", "detail": str(e)}))
                await asyncio.sleep(2)
                continue
            if not out:
                continue
            for _s, messages in out:
                for msg_id, fields in messages:
                    try:
                        await handler(redis, msg_id, fields)
                    except Exception as e:
                        log.error(json.dumps({"error": f"{label}_handle", "detail": str(e)}))


async def _main() -> None:
    c = Coordinator()
    await c.connect()
    assert c._redis is not None
    r = c._redis
    try:
        await asyncio.gather(
            c._poll_stream(r, STREAM_COMMANDS, GROUP_COMMANDS, "commands", c.handle_command),
            c._poll_stream(r, STREAM_RECEIPTS, GROUP_RECEIPTS, "receipts", c.handle_receipt),
        )
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(_main())
