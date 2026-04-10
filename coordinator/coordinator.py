"""JARVIS Event Coordinator: Redis Streams, local SQLite missions, DashClaw guard/outcomes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import sys
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from redis.asyncio import Redis
from redis.exceptions import ResponseError

load_dotenv()

# Control plane (Jarvis API). Override via .env: CONTROL_PLANE_URL=http://localhost:8001
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8001")

# Mission status values (missions table)
ST_PENDING = "pending"
ST_ACTIVE = "active"
ST_AWAITING_APPROVAL = "awaiting_approval"
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
MISSIONS_DB_PATH = Path(__file__).resolve().parent / "missions.db"

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


def _control_plane_command_source(data: dict[str, Any]) -> str:
    """Map incoming command metadata to control plane CommandCreate.source (voice|command_center|sms|api)."""
    raw = str(data.get("surface_origin") or data.get("source") or "").strip().lower()
    if raw in ("voice", "command_center", "sms", "api"):
        return raw
    # Coordinator path / unknown surfaces: use api (control plane does not accept "coordinator" as source)
    return "api"


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


def _init_db_sync(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS missions (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            created_by TEXT,
            decision TEXT,
            risk_level TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()


class Coordinator:
    def __init__(self) -> None:
        if not DASHCLAW_BASE_URL or not DASHCLAW_API_KEY:
            raise RuntimeError("DASHCLAW_BASE_URL and DASHCLAW_API_KEY are required.")

        self._redis: Redis | None = None
        self._conn: sqlite3.Connection | None = None
        self._db_lock = asyncio.Lock()
        self._cp_mission_by_local: dict[str, str] = {}
        self._dash_headers = {
            "x-api-key": DASHCLAW_API_KEY,
            "Content-Type": "application/json",
        }

    async def connect(self) -> None:
        self._redis = Redis.from_url(REDIS_URL, decode_responses=False)
        assert self._redis is not None
        await _ensure_group(self._redis, STREAM_COMMANDS, GROUP_COMMANDS)
        await _ensure_group(self._redis, STREAM_RECEIPTS, GROUP_RECEIPTS)

        def _open_and_init() -> sqlite3.Connection:
            MISSIONS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(MISSIONS_DB_PATH, check_same_thread=False)
            _init_db_sync(c)
            return c

        self._conn = await asyncio.to_thread(_open_and_init)
        assert self._conn is not None

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
        if self._conn:

            def _close(c: sqlite3.Connection) -> None:
                c.close()

            await asyncio.to_thread(_close, self._conn)
            self._conn = None

    async def _db_run(self, fn: Callable[..., Any], *args: Any) -> Any:
        async with self._db_lock:
            return await asyncio.to_thread(fn, *args)

    def _insert_mission(
        self,
        mission_id: str,
        title: str,
        created_by: str,
        status: str = ST_PENDING,
    ) -> None:
        assert self._conn is not None
        now = _now_iso()
        self._conn.execute(
            """
            INSERT INTO missions (id, title, status, created_by, decision, risk_level, created_at, updated_at)
            VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (mission_id, title, status, created_by, now, now),
        )
        self._conn.commit()

    def _ensure_mission_row(
        self,
        mission_id: str,
        title: str,
        created_by: str,
    ) -> None:
        assert self._conn is not None
        cur = self._conn.execute("SELECT id FROM missions WHERE id = ?", (mission_id,))
        if cur.fetchone() is None:
            self._insert_mission(mission_id, title, created_by, ST_PENDING)

    def _update_mission(
        self,
        mission_id: str,
        *,
        status: str | None = None,
        decision: str | None = None,
        risk_level: str | None = None,
    ) -> None:
        assert self._conn is not None
        now = _now_iso()
        parts: list[str] = ["updated_at = ?"]
        vals: list[Any] = [now]
        if status is not None:
            parts.append("status = ?")
            vals.append(status)
        if decision is not None:
            parts.append("decision = ?")
            vals.append(decision)
        if risk_level is not None:
            parts.append("risk_level = ?")
            vals.append(risk_level)
        vals.append(mission_id)
        sql = f"UPDATE missions SET {', '.join(parts)} WHERE id = ?"
        self._conn.execute(sql, vals)
        self._conn.commit()

    async def handle_command(self, redis: Redis, msg_id: bytes, fields: dict[Any, Any]) -> None:
        f = _decode_fields(fields)
        data = _parse_json_field(f, "data")
        text = (data.get("text") or data.get("command") or "").strip()
        mission_id = str(data.get("mission_id") or "").strip()
        created_by = str(data.get("created_by") or os.environ.get("JARVIS_OPERATOR") or "").strip()

        title = f"JARVIS: {(text[:200] or '(empty command)').replace(chr(10), ' ')}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            if not mission_id:
                mission_id = str(uuid.uuid4())

            def _prepare() -> None:
                assert self._conn is not None
                self._ensure_mission_row(mission_id, title, created_by)

            await self._db_run(_prepare)

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

            if decision == "allow":

                def _allow() -> None:
                    self._update_mission(
                        mission_id,
                        status=ST_ACTIVE,
                        decision=decision,
                        risk_level=risk_s,
                    )

                await self._db_run(_allow)
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

                def _approval() -> None:
                    self._update_mission(
                        mission_id,
                        status=ST_AWAITING_APPROVAL,
                        decision=decision,
                        risk_level=risk_s,
                    )

                await self._db_run(_approval)
                up = {
                    "type": "approval_required",
                    "mission_id": mission_id,
                    "message": guard.get("message") or "Approval required before execution.",
                    "command": text,
                }
                await redis.xadd(STREAM_UPDATES, {"data": json.dumps(up, default=str)})
                _log_event(
                    stream=STREAM_UPDATES,
                    event_type="approval_request",
                    mission_id=mission_id,
                    decision=decision,
                )

            else:

                def _deny() -> None:
                    self._update_mission(
                        mission_id,
                        status=ST_FAILED,
                        decision="deny",
                        risk_level=risk_s,
                    )

                await self._db_run(_deny)
                _log_event(
                    stream=STREAM_COMMANDS,
                    event_type="command_denied",
                    mission_id=mission_id,
                    decision="deny",
                )

        cmd_text = (text or "").strip() or "(empty command)"
        cp_source = _control_plane_command_source(data)
        cp_resp = await post_to_control_plane(
            "/api/v1/commands",
            {"text": cmd_text, "source": cp_source},
        )
        if cp_resp is not None:
            cp_mid = cp_resp.get("mission_id")
            if cp_mid is not None:
                self._cp_mission_by_local[str(mission_id)] = str(cp_mid)
                log.info(
                    json.dumps(
                        {
                            "control_plane_mission_id": str(cp_mid),
                            "local_mission_id": mission_id,
                        }
                    )
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

                def _done() -> None:
                    self._update_mission(mission_id, status=ST_COMPLETE, decision="complete")

                await self._db_run(_done)
                decision = "complete"
            else:

                def _fail() -> None:
                    self._update_mission(mission_id, status=ST_FAILED, decision="failed")

                await self._db_run(_fail)
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

            cp_mid = self._cp_mission_by_local.get(mission_id)
            if cp_mid:
                summ: str | None = None
                if summary is not None:
                    s = str(summary).strip()
                    if s:
                        summ = s[:500] if len(s) > 500 else s
                await post_to_control_plane(
                    "/api/v1/receipts",
                    {
                        "mission_id": cp_mid,
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
