"""JARVIS executor worker: consume jarvis.execution, call OpenClaw, record receipts, broadcast updates."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

import aiohttp
from dotenv import load_dotenv
from redis.asyncio import Redis
from redis.exceptions import ResponseError

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8001").rstrip("/")

STREAM_EXECUTION = "jarvis.execution"
STREAM_UPDATES = "jarvis.updates"
GROUP_EXECUTOR = "jarvis-executor"
CONSUMER_NAME = "executor-1"

FALLBACK_ERROR = (
    "I encountered an issue executing that. Please check system logs."
)

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)
sys.stdout.reconfigure(line_buffering=True)
log = logging.getLogger("jarvis.executor")


def _decode_fields(raw: dict[Any, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in raw.items():
        ks = k.decode() if isinstance(k, bytes) else str(k)
        vs = v.decode() if isinstance(v, bytes) else (v if isinstance(v, str) else str(v))
        out[ks] = vs
    return out


def _parse_data(fields: dict[str, str]) -> dict[str, Any]:
    # Try nested JSON in data or payload field first
    raw = fields.get("data") or fields.get("payload")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    # Fall back to flat fields (mission_id, command, etc. as top-level keys)
    if "mission_id" in fields:
        return dict(fields)

    return {}


async def _ensure_group(redis: Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def _post_control_plane(
    session: aiohttp.ClientSession,
    path: str,
    payload: dict[str, Any],
) -> None:
    url = f"{CONTROL_PLANE_URL}{path if path.startswith('/') else '/' + path}"
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status >= 400:
                body = await resp.text()
                log.warning(
                    json.dumps(
                        {
                            "control_plane": "http_error",
                            "path": path,
                            "status": resp.status,
                            "body": body[:500],
                        }
                    )
                )
    except Exception as e:
        log.warning(
            json.dumps(
                {"control_plane": "fail", "path": path, "detail": str(e)}
            )
        )


async def _call_openclaw(
    session: aiohttp.ClientSession,
    command_text: str,
    _session_id: str,
) -> tuple[str, bool]:
    try:
        proc = await asyncio.create_subprocess_exec(
            r"C:\Users\faizt\AppData\Roaming\npm\openclaw.cmd",
            "agent",
            "--agent",
            "main",
            "--message",
            command_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            log.warning(json.dumps({"openclaw": "timeout"}))
            return FALLBACK_ERROR, False

        output = stdout.decode("utf-8", errors="replace").strip()

        # Strip the openclaw banner lines (start with emoji or known prefixes)
        lines = output.splitlines()
        clean_lines = []
        skip_prefixes = ("🦞", "Config warnings", "╭", "╰", "│", "◇", "◆")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if any(stripped.startswith(p) for p in skip_prefixes):
                continue
            clean_lines.append(stripped)

        reply = "\n".join(clean_lines).strip()

        if not reply:
            log.warning(
                json.dumps(
                    {
                        "openclaw": "empty_response",
                        "raw": output[:300],
                    }
                )
            )
            return FALLBACK_ERROR, False

        return reply, True

    except Exception as e:
        log.warning(json.dumps({"openclaw": "fail", "detail": str(e)}))
        return FALLBACK_ERROR, False


async def _xadd_updates(
    redis: Redis,
    *,
    mission_id: str,
    message: str,
    status: str,
) -> None:
    try:
        payload = {
            "type": "mission_update",
            "mission_id": mission_id,
            "message": message,
            "status": status,
        }
        await redis.xadd(STREAM_UPDATES, {"data": json.dumps(payload)})
    except Exception as e:
        log.warning(json.dumps({"redis_updates": "fail", "detail": str(e)}))


async def handle_execution(
    redis: Redis,
    session: aiohttp.ClientSession,
    msg_id: bytes,
    fields: dict[Any, Any],
) -> None:
    f = _decode_fields(fields)
    data = _parse_data(f)
    mission_id = str(data.get("mission_id") or "").strip()
    command_text = (data.get("command") or data.get("text") or "").strip()
    print(f"EXECUTOR: processing mission_id={mission_id} command={command_text!r}", flush=True)

    if not mission_id:
        log.warning(
            json.dumps({"error": "execution_missing_mission_id", "detail": str(data)[:300]})
        )
        await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
        return

    reply_text, ok = await _call_openclaw(session, command_text, mission_id)

    await _post_control_plane(
        session,
        "/api/v1/receipts",
        {
            "mission_id": mission_id,
            "receipt_type": "openclaw_execution",
            "source": "executor",
            "payload": {
                "action": command_text,
                "result": reply_text,
                "success": ok,
            },
            "summary": reply_text,
        },
    )

    final_status = "complete" if ok else "failed"
    await _post_control_plane(
        session,
        f"/api/v1/missions/{mission_id}/status",
        {"status": final_status},
    )

    await _xadd_updates(
        redis,
        mission_id=mission_id,
        message=reply_text,
        status=final_status,
    )

    await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)


class ExecutorWorker:
    def __init__(self) -> None:
        self._redis: Redis | None = None

    async def connect(self) -> None:
        self._redis = Redis.from_url(REDIS_URL, decode_responses=False)
        assert self._redis is not None
        await _ensure_group(self._redis, STREAM_EXECUTION, GROUP_EXECUTOR)

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    async def run(self) -> None:
        assert self._redis is not None
        r = self._redis
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            while True:
                try:
                    out = await r.xreadgroup(
                        GROUP_EXECUTOR,
                        CONSUMER_NAME,
                        {STREAM_EXECUTION: ">"},
                        count=10,
                        block=5000,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.error(json.dumps({"error": "read_loop", "detail": str(e)}))
                    await asyncio.sleep(2)
                    continue
                if not out:
                    continue
                for _s, messages in out:
                    for msg_id, raw_fields in messages:
                        try:
                            await handle_execution(r, http, msg_id, raw_fields)
                        except Exception as e:
                            log.error(
                                json.dumps(
                                    {"error": "handle_execution", "detail": str(e)}
                                )
                            )
                            try:
                                await r.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
                            except Exception as ack_e:
                                log.warning(
                                    json.dumps(
                                        {"error": "xack_after_fail", "detail": str(ack_e)}
                                    )
                                )


async def _main() -> None:
    w = ExecutorWorker()
    await w.connect()
    try:
        await w.run()
    finally:
        await w.close()


if __name__ == "__main__":
    asyncio.run(_main())
