"""JARVIS executor worker: consume jarvis.execution, classify intent with Ollama, act, publish jarvis.receipts.

Reads the same Redis execution stream as the legacy OpenClaw executor (consumer group jarvis-executor)
but publishes results to jarvis.receipts for the coordinator to process. Does not call OpenClaw.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import webbrowser
from typing import Any
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from redis.asyncio import Redis
from redis.exceptions import ResponseError

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
# Local Ollama classifier: JARVIS_LOCAL_MODEL is canonical; OLLAMA_MODEL remains a deprecated alias.
OLLAMA_MODEL = (
    os.getenv("JARVIS_LOCAL_MODEL", "").strip()
    or os.getenv("OLLAMA_MODEL", "").strip()
    or "qwen3.5:4b"
)
JARVIS_CLOUD_MODEL = os.getenv("JARVIS_CLOUD_MODEL")
OLLAMA_TIMEOUT_SEC = float(os.getenv("OLLAMA_TIMEOUT_SEC", "120"))

STREAM_EXECUTION = "jarvis.execution"
STREAM_RECEIPTS = "jarvis.receipts"
GROUP_EXECUTOR = "jarvis-executor"
CONSUMER_NAME = "jarvis-worker-1"

log = logging.getLogger("jarvis.executor.worker")
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)
sys.stdout.reconfigure(line_buffering=True)

CLASSIFIER_SYSTEM = """You classify operator commands for a local assistant.
Respond with a single JSON object only (no markdown), using this schema:
{"intent":"open_url"|"unknown","url":string|null,"reason":string|null}
Rules:
- intent "open_url" only if the user clearly wants to open a web page and you can extract one http(s) URL from the command.
- Put the full URL in "url" (include https:// if the user omitted the scheme but clearly meant a hostname, e.g. example.com -> https://example.com).
- Otherwise intent "unknown" with a short reason."""


def _decode_fields(raw: dict[Any, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in raw.items():
        ks = k.decode() if isinstance(k, bytes) else str(k)
        vs = v.decode() if isinstance(v, bytes) else (v if isinstance(v, str) else str(v))
        out[ks] = vs
    return out


def _parse_data(fields: dict[str, str]) -> dict[str, Any]:
    raw = fields.get("data") or fields.get("payload")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    if "mission_id" in fields:
        return dict(fields)
    return {}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    s = text.strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _normalize_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", u):
        if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", u):
            u = "https://" + u
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return u


async def _ensure_group(redis: Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def classify_intent(
    client: httpx.AsyncClient,
    command_text: str,
) -> dict[str, Any]:
    """Call Ollama /api/chat with JSON format; return parsed intent dict or error."""
    url = f"{OLLAMA_URL}/api/chat"
    body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": CLASSIFIER_SYSTEM},
            {"role": "user", "content": command_text},
        ],
    }
    r = await client.post(url, json=body, timeout=OLLAMA_TIMEOUT_SEC)
    r.raise_for_status()
    payload = r.json()
    msg = (payload.get("message") or {}) if isinstance(payload, dict) else {}
    content = msg.get("content") if isinstance(msg, dict) else None
    if not isinstance(content, str):
        return {"intent": "unknown", "url": None, "reason": "empty_model_response"}
    parsed = _extract_json_object(content)
    if not parsed:
        return {"intent": "unknown", "url": None, "reason": "unparseable_model_json"}
    return parsed


async def handle_execution(
    redis: Redis,
    http: httpx.AsyncClient,
    msg_id: bytes,
    fields: dict[Any, Any],
) -> None:
    f = _decode_fields(fields)
    data = _parse_data(f)
    mission_id = str(data.get("mission_id") or "").strip()
    command_text = (data.get("command") or data.get("text") or "").strip()

    log.info(
        json.dumps(
            {
                "worker": "execution_received",
                "mission_id": mission_id,
                "command_preview": command_text[:200],
            },
            default=str,
        )
    )

    if not mission_id:
        log.warning(json.dumps({"error": "execution_missing_mission_id"}))
        await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
        return

    try:
        intent_obj = await classify_intent(http, command_text)
    except Exception as e:
        log.warning(json.dumps({"ollama": "classify_failed", "detail": str(e)}))
        await redis.xadd(
            STREAM_RECEIPTS,
            {
                "data": json.dumps(
                    {
                        "mission_id": mission_id,
                        "status": "failed",
                        "summary": f"Ollama classification failed: {e}",
                        "evidence": {"stage": "ollama", "error": str(e)},
                    },
                    default=str,
                )
            },
        )
        await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
        return

    intent = str(intent_obj.get("intent") or "unknown").strip().lower()
    raw_url = intent_obj.get("url")
    reason = intent_obj.get("reason")
    url = _normalize_url(raw_url if isinstance(raw_url, str) else None)

    evidence: dict[str, Any] = {
        "intent": intent,
        "ollama_model": OLLAMA_MODEL,
        "classifier_output": intent_obj,
    }

    if intent == "open_url" and url:
        try:
            opened = await asyncio.to_thread(webbrowser.open, url)
            summary = (
                f"Opened URL in default browser: {url}"
                if opened
                else f"webbrowser.open returned false for {url}"
            )
            status = "complete" if opened else "failed"
            evidence["url"] = url
            evidence["webbrowser_open"] = bool(opened)
            log.info(json.dumps({"worker": "open_url", "mission_id": mission_id, "url": url, "opened": opened}))
        except Exception as e:
            status = "failed"
            summary = f"Failed to open URL: {e}"
            evidence["error"] = str(e)
            log.warning(json.dumps({"worker": "open_url_error", "detail": str(e)}))
    else:
        status = "complete" if intent == "unknown" else "failed"
        if intent == "open_url" and not url:
            summary = "Model chose open_url but no valid http(s) URL was produced."
            status = "failed"
        else:
            r = reason if isinstance(reason, str) else None
            summary = (r.strip() if r else "No URL action for this command.")[:500]

        log.info(
            json.dumps(
                {
                    "worker": "no_browser_action",
                    "mission_id": mission_id,
                    "intent": intent,
                    "summary": summary[:200],
                },
                default=str,
            )
        )

    receipt_body = {
        "mission_id": mission_id,
        "status": status,
        "summary": summary,
        "evidence": evidence,
    }
    await redis.xadd(STREAM_RECEIPTS, {"data": json.dumps(receipt_body, default=str)})
    log.info(json.dumps({"worker": "receipt_published", "mission_id": mission_id, "status": status}))
    await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)


async def _warmup_ollama() -> None:
    url = f"{OLLAMA_URL}/api/chat"
    body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": "hi"}],
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=body, timeout=OLLAMA_TIMEOUT_SEC)
            r.raise_for_status()
            log.info(json.dumps({"ollama": "warmup_ok", "model": OLLAMA_MODEL}))
    except Exception as e:
        log.warning(json.dumps({"ollama": "warmup_failed", "detail": str(e)}))


async def _run_loop(redis: Redis) -> None:
    timeout = httpx.Timeout(OLLAMA_TIMEOUT_SEC + 10.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        while True:
            try:
                out = await redis.xreadgroup(
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
                        await handle_execution(redis, http, msg_id, raw_fields)
                    except Exception as e:
                        log.error(json.dumps({"error": "handle_execution", "detail": str(e)}))
                        f = _decode_fields(raw_fields)
                        data = _parse_data(f)
                        mid = str(data.get("mission_id") or "").strip()
                        if mid:
                            await redis.xadd(
                                STREAM_RECEIPTS,
                                {
                                    "data": json.dumps(
                                        {
                                            "mission_id": mid,
                                            "status": "failed",
                                            "summary": f"Executor worker internal error: {e}",
                                            "evidence": {"error": str(e)},
                                        },
                                        default=str,
                                    )
                                },
                            )
                        try:
                            await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
                        except Exception as ack_e:
                            log.warning(json.dumps({"error": "xack_fail", "detail": str(ack_e)}))


async def _main() -> None:
    log.info("Local model: %s", OLLAMA_MODEL)
    log.info(
        "Cloud model: %s",
        JARVIS_CLOUD_MODEL.strip() if (JARVIS_CLOUD_MODEL or "").strip() else "(unset)",
    )
    log.info(
        json.dumps(
            {
                "worker": "starting",
                "ollama_url": OLLAMA_URL,
                "ollama_model": OLLAMA_MODEL,
                "redis": REDIS_URL.split("@")[-1],
            },
            default=str,
        )
    )
    redis = Redis.from_url(REDIS_URL, decode_responses=False)
    try:
        await _ensure_group(redis, STREAM_EXECUTION, GROUP_EXECUTOR)
        await _warmup_ollama()
        await _run_loop(redis)
    finally:
        await redis.close()


if __name__ == "__main__":
    asyncio.run(_main())
