"""JARVIS executor worker: consume jarvis.execution, call OpenClaw, record receipts, broadcast updates.

TRUTH_SOURCE: posts execution receipts via control plane POST /api/v1/receipts (see app/schemas/receipts.py).
MACHINE_CONFIG_REQUIRED: OPENCLAW_CMD, valid %USERPROFILE%\\.openclaw\\ config for gateway auth and models.
UPSTREAM_DEPENDENCY: OpenClaw CLI + gateway behavior; executor does not embed provider secrets.

OpenClaw invocation: up to two attempts with backoff on a small set of transient failures; receipts
include structured diagnostics (error_class, attempt_count, exit_code, stderr excerpt) without secrets.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
from dotenv import load_dotenv
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from shared.lane_truth import MISSION_EXECUTION_PATH_OPENCLAW, build_lane_truth_block
from shared.worker_readiness import executor_readiness_snapshot
from shared.worker_registry_client import (
    default_instance_id,
    heartbeat_interval_sec,
    heartbeat_worker,
    register_worker,
)

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "").strip()
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "").strip().rstrip("/")
OPENCLAW_CMD = os.getenv(
    "OPENCLAW_CMD",
    str(Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"),
)

STREAM_EXECUTION = "jarvis.execution"
STREAM_UPDATES = "jarvis.updates"
GROUP_EXECUTOR = "jarvis-executor"
CONSUMER_NAME = "executor-1"

FALLBACK_ERROR = (
    "I encountered an issue executing that. Please check system logs."
)

OPENCLAW_MAX_ATTEMPTS = 2
OPENCLAW_RETRY_BACKOFF_SEC = 5.0
OPENCLAW_COMMUNICATE_TIMEOUT_SEC = 120

# Stable set for receipts and logs (extend only with care — downstream may key on these strings).
ERROR_CLASS_OK = "ok"
ERROR_CLASS_TIMEOUT = "timeout"
ERROR_CLASS_EMPTY_OUTPUT = "empty_output"
ERROR_CLASS_LAUNCH_ERROR = "launch_error"
ERROR_CLASS_NONZERO_EXIT = "nonzero_exit"
ERROR_CLASS_AUTH_OR_CONFIG = "auth_or_config_error"
ERROR_CLASS_UNKNOWN = "unknown"

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)
sys.stdout.reconfigure(line_buffering=True)
log = logging.getLogger("jarvis.executor")

OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
AUTH_PROFILES_JSON = (
    Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
)


def _load_openclaw_json() -> dict[str, Any] | None:
    if not OPENCLAW_JSON.is_file():
        return None
    try:
        return json.loads(OPENCLAW_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _default_gateway_model(cfg: dict[str, Any] | None) -> str | None:
    if not cfg:
        return None
    try:
        lst = cfg.get("agents", {}).get("list", [])
        for a in lst:
            if a.get("default") is True:
                m = a.get("model")
                if m:
                    return str(m).strip()
    except (TypeError, AttributeError):
        pass
    return None


def _lane_from_gateway_model(model: str | None) -> str:
    """OpenClaw-routed local Ollama vs cloud/other (no secret data)."""
    if not model:
        return "gateway"
    if str(model).strip().lower().startswith("ollama/"):
        return "local"
    return "gateway"


def _cloud_model_id() -> str:
    """OpenClaw ``--model`` for cloud lane; must be set explicitly for gateway runs."""
    val = os.getenv("JARVIS_CLOUD_MODEL", "").strip()
    if not val:
        raise ValueError(
            "JARVIS_CLOUD_MODEL env var is not set. "
            "Set it in executor/.env before using gateway lane."
        )
    return val


def _requested_lane_from_data(data: dict[str, Any]) -> str:
    raw = data.get("routing")
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("requested_lane") or "").strip()


def _resolved_openclaw_model_lane(
    raw_routing: dict[str, Any] | None,
    gateway_fallback: str,
) -> str:
    """Receipt lane label: routing.requested_lane when set, else gateway-model heuristic."""
    if not isinstance(raw_routing, dict):
        return gateway_fallback
    req = str(raw_routing.get("requested_lane") or "").strip().lower()
    if req == "gateway":
        return "gateway"
    if req == "local_fast":
        return "local"
    return gateway_fallback


def _local_model_from_gateway(model: str | None, lane: str) -> str | None:
    if lane != "local" or not model:
        return None
    s = str(model).strip()
    if s.lower().startswith("ollama/"):
        return s.split("/", 1)[1].strip() if "/" in s else s
    return s


def _auth_profiles_appear_configured() -> bool:
    """True if auth-profiles.json exists and parses to a non-empty object (no token values logged)."""
    if not AUTH_PROFILES_JSON.is_file():
        return False
    try:
        if AUTH_PROFILES_JSON.stat().st_size < 3:
            return False
        data = json.loads(AUTH_PROFILES_JSON.read_text(encoding="utf-8"))
        return isinstance(data, dict) and len(data) > 0
    except (OSError, json.JSONDecodeError):
        return False


_ROUTING_KEYS = frozenset(
    {
        "requested_lane",
        "actual_lane",
        "fallback_applied",
        "reason_code",
        "fallback_reason_code",
        "reason_summary",
        "requires_tools",
        "requires_long_running_execution",
        "approval_sensitive",
    }
)


def _build_execution_meta(
    data: dict[str, Any],
    *,
    gateway_model: str | None,
) -> dict[str, Any]:
    oml_fb = _lane_from_gateway_model(gateway_model)
    raw_routing = data.get("routing") if isinstance(data.get("routing"), dict) else None
    oml = _resolved_openclaw_model_lane(raw_routing, oml_fb)
    resumed = bool(data.get("resumed")) or bool(data.get("approval_id"))
    meta: dict[str, Any] = {
        # Resolved lane for receipts (routing.requested_lane when present; else config heuristic).
        "lane": oml,
        "openclaw_model_lane": oml,
        "gateway_model": gateway_model,
        "local_model": _local_model_from_gateway(gateway_model, oml_fb),
        "resumed_from_approval": resumed,
        "mission_execution_path": MISSION_EXECUTION_PATH_OPENCLAW,
    }
    if oml == "gateway":
        meta["auth_profiles_present"] = _auth_profiles_appear_configured()
    routing_subset: dict[str, Any] = {}
    if isinstance(raw_routing, dict):
        routing_subset = {k: raw_routing[k] for k in _ROUTING_KEYS if k in raw_routing}
        if routing_subset:
            meta["routing"] = routing_subset
    meta["lane_truth"] = build_lane_truth_block(
        routing=raw_routing,
        openclaw_model_lane=oml_fb,
    )
    return meta


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


def _executor_normalize_stages(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        title = item.get("title")
        if not isinstance(sid, str) or not sid.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        st = item.get("status", "pending")
        if not isinstance(st, str):
            st = "pending"
        if st not in ("pending", "active", "complete", "failed"):
            st = "pending"
        out.append({"id": sid.strip(), "title": title.strip(), "status": st})
    return out


def _executor_command_is_complex(command: str) -> bool:
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


async def _get_control_plane_json(
    session: aiohttp.ClientSession,
    path: str,
) -> Any | None:
    url = f"{CONTROL_PLANE_URL}{path if path.startswith('/') else '/' + path}"
    headers = {"x-api-key": os.getenv("CONTROL_PLANE_API_KEY", "")}
    req_timeout = aiohttp.ClientTimeout(total=150.0)
    try:
        async with session.get(url, headers=headers, timeout=req_timeout) as resp:
            if resp.status >= 400:
                body = await resp.text()
                log.warning(
                    json.dumps(
                        {
                            "control_plane": "get_http_error",
                            "path": path,
                            "status": resp.status,
                            "body": body[:500],
                        }
                    )
                )
                return None
            try:
                return await resp.json()
            except Exception as e:
                log.warning(
                    json.dumps(
                        {"control_plane": "get_json_error", "path": path, "detail": str(e)}
                    )
                )
                return None
    except Exception as e:
        log.warning(
            json.dumps({"control_plane": "get_fail", "path": path, "detail": str(e)})
        )
        return None


async def _ensure_group(redis: Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def _sanitize_error_excerpt(text: str, max_len: int = 400) -> str:
    """Truncate stderr/exception text for receipts; redact obvious secret patterns."""
    if not text:
        return ""
    s = text.strip()
    s = re.sub(r"(?i)(Bearer\s+)(\S+)", r"\1[REDACTED]", s)
    s = re.sub(r"(?i)(api[_-]?key\s*[:=]\s*)(\S+)", r"\1[REDACTED]", s)
    s = re.sub(r"(?i)(x-api-key\s*[:=]\s*)(\S+)", r"\1[REDACTED]", s)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _stderr_suggests_auth_or_config(stderr: str) -> bool:
    low = stderr.lower()
    return any(
        needle in low
        for needle in (
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "invalid credential",
            "authentication",
            "not authenticated",
            "api key",
            "invalid token",
            "credential",
        )
    )


def _failure_summary_for_user(error_class: str) -> str:
    """User-visible failure line when classification is reliable enough to avoid a generic fallback."""
    if error_class == ERROR_CLASS_TIMEOUT:
        return (
            "Execution timed out waiting for the agent. If this persists, try again or check "
            "gateway load."
        )
    if error_class == ERROR_CLASS_EMPTY_OUTPUT:
        return (
            "The agent returned no usable output. Check OpenClaw/gateway configuration and "
            "credentials."
        )
    if error_class == ERROR_CLASS_AUTH_OR_CONFIG:
        return (
            "Execution failed due to an authentication or configuration problem. Check OpenClaw "
            "auth profiles and gateway settings."
        )
    if error_class == ERROR_CLASS_LAUNCH_ERROR:
        return (
            "Could not start the OpenClaw CLI. Verify OPENCLAW_CMD and that the CLI is installed."
        )
    if error_class == ERROR_CLASS_NONZERO_EXIT:
        return "The agent process exited with an error. Check executor logs for details."
    return FALLBACK_ERROR


@dataclass
class _OpenClawAttemptResult:
    ok: bool
    reply_text: str
    error_class: str
    exit_code: int | None
    stderr_excerpt: str
    retryable: bool


def _classify_empty_or_stderr(
    *,
    stderr: str,
    returncode: int | None,
) -> str:
    if _stderr_suggests_auth_or_config(stderr):
        return ERROR_CLASS_AUTH_OR_CONFIG
    if returncode is not None and returncode != 0:
        return ERROR_CLASS_NONZERO_EXIT
    return ERROR_CLASS_EMPTY_OUTPUT


async def _call_openclaw_once(
    session: aiohttp.ClientSession,
    command_text: str,
    requested_lane: str,
) -> _OpenClawAttemptResult:
    """Single subprocess invocation; no retries."""
    del session  # reserved for future (e.g. correlated HTTP); CLI path does not use it today.
    proc: asyncio.subprocess.Process | None = None
    argv: list[str] = [
        OPENCLAW_CMD,
        "agent",
        "--agent",
        "main",
        "--message",
        command_text,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        detail = _sanitize_error_excerpt(str(e))
        log.warning(
            json.dumps(
                {
                    "openclaw": "launch_failed",
                    "error_class": ERROR_CLASS_LAUNCH_ERROR,
                    "detail": detail,
                }
            )
        )
        return _OpenClawAttemptResult(
            ok=False,
            reply_text=FALLBACK_ERROR,
            error_class=ERROR_CLASS_LAUNCH_ERROR,
            exit_code=None,
            stderr_excerpt=detail,
            retryable=False,
        )
    except OSError as e:
        detail = _sanitize_error_excerpt(str(e))
        errno = getattr(e, "errno", None)
        transient = errno in (11, 35, 10035)  # EAGAIN / EWOULDBLOCK (POSIX / Win)
        log.warning(
            json.dumps(
                {
                    "openclaw": "launch_failed",
                    "error_class": ERROR_CLASS_LAUNCH_ERROR,
                    "errno": errno,
                    "detail": detail,
                }
            )
        )
        return _OpenClawAttemptResult(
            ok=False,
            reply_text=FALLBACK_ERROR,
            error_class=ERROR_CLASS_LAUNCH_ERROR,
            exit_code=None,
            stderr_excerpt=detail,
            retryable=transient,
        )

    assert proc is not None
    try:
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=OPENCLAW_COMMUNICATE_TIMEOUT_SEC
            )
        except asyncio.TimeoutError:
            timed_out = True
            proc.kill()
            await proc.communicate()
            log.warning(
                json.dumps(
                    {
                        "openclaw": "timeout",
                        "error_class": ERROR_CLASS_TIMEOUT,
                        "communicate_timeout_sec": OPENCLAW_COMMUNICATE_TIMEOUT_SEC,
                    }
                )
            )
            return _OpenClawAttemptResult(
                ok=False,
                reply_text=FALLBACK_ERROR,
                error_class=ERROR_CLASS_TIMEOUT,
                exit_code=None,
                stderr_excerpt="",
                retryable=True,
            )
    except Exception as e:
        detail = _sanitize_error_excerpt(str(e))
        log.warning(
            json.dumps(
                {
                    "openclaw": "communicate_failed",
                    "error_class": ERROR_CLASS_UNKNOWN,
                    "detail": detail,
                }
            )
        )
        return _OpenClawAttemptResult(
            ok=False,
            reply_text=FALLBACK_ERROR,
            error_class=ERROR_CLASS_UNKNOWN,
            exit_code=None,
            stderr_excerpt=detail,
            retryable=False,
        )

    stderr_raw = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""
    stderr_excerpt = _sanitize_error_excerpt(stderr_raw)
    output = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""

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
    exit_code = proc.returncode

    if reply:
        # Semantics preserved: non-empty cleaned stdout counts as success regardless of exit code.
        return _OpenClawAttemptResult(
            ok=True,
            reply_text=reply,
            error_class=ERROR_CLASS_OK,
            exit_code=exit_code,
            stderr_excerpt=stderr_excerpt if stderr_excerpt else "",
            retryable=False,
        )

    ec = _classify_empty_or_stderr(stderr=stderr_raw, returncode=exit_code)
    log.warning(
        json.dumps(
            {
                "openclaw": "empty_or_failed",
                "error_class": ec,
                "exit_code": exit_code,
                "stderr_excerpt": stderr_excerpt[:300],
            }
        )
    )
    return _OpenClawAttemptResult(
        ok=False,
        reply_text=FALLBACK_ERROR,
        error_class=ec,
        exit_code=exit_code,
        stderr_excerpt=stderr_excerpt,
        retryable=ec in (ERROR_CLASS_TIMEOUT, ERROR_CLASS_EMPTY_OUTPUT),
    )


async def _call_openclaw(
    session: aiohttp.ClientSession,
    command_text: str,
    _session_id: str,
    requested_lane: str,
) -> tuple[str, bool, dict[str, Any]]:
    """Run OpenClaw with bounded retries; returns (reply text, success, receipt diagnostics)."""
    del _session_id
    last: _OpenClawAttemptResult | None = None
    attempts_used = 0
    for attempt in range(1, OPENCLAW_MAX_ATTEMPTS + 1):
        attempts_used = attempt
        log.info(
            json.dumps(
                {
                    "openclaw": "attempt",
                    "attempt": attempt,
                    "max_attempts": OPENCLAW_MAX_ATTEMPTS,
                }
            )
        )
        last = await _call_openclaw_once(session, command_text, requested_lane)
        if last.ok:
            meta = {
                "attempt_count": attempts_used,
                "error_class": ERROR_CLASS_OK,
                "exit_code": last.exit_code,
                "stderr_excerpt": last.stderr_excerpt or "",
                "final_success": True,
            }
            return last.reply_text, True, meta
        if attempt < OPENCLAW_MAX_ATTEMPTS and last.retryable:
            log.warning(
                json.dumps(
                    {
                        "openclaw": "retry_scheduled",
                        "after_sec": OPENCLAW_RETRY_BACKOFF_SEC,
                        "error_class": last.error_class,
                        "attempt": attempt,
                    }
                )
            )
            await asyncio.sleep(OPENCLAW_RETRY_BACKOFF_SEC)
            continue
        break

    assert last is not None
    user_msg = _failure_summary_for_user(last.error_class)
    meta = {
        "attempt_count": attempts_used,
        "error_class": last.error_class,
        "exit_code": last.exit_code,
        "stderr_excerpt": last.stderr_excerpt,
        "final_success": False,
    }
    return user_msg, False, meta


async def _post_control_plane(
    session: aiohttp.ClientSession,
    path: str,
    payload: dict[str, Any],
) -> bool:
    """POST JSON to control plane. Returns True only on HTTP 2xx."""
    url = f"{CONTROL_PLANE_URL}{path if path.startswith('/') else '/' + path}"
    headers = {"x-api-key": os.getenv("CONTROL_PLANE_API_KEY", "")}
    try:
        async with session.post(url, json=payload, headers=headers) as resp:
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
                return False
            return True
    except Exception as e:
        log.warning(
            json.dumps(
                {"control_plane": "fail", "path": path, "detail": str(e)}
            )
        )
        return False


async def _post_mission_event(
    session: aiohttp.ClientSession,
    mission_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Append a mission event via control plane (API key). Returns True on HTTP 2xx."""
    return await _post_control_plane(
        session,
        f"/api/v1/missions/{mission_id}/events",
        {
            "event_type": event_type,
            "payload": payload or {},
            "actor_type": "system",
            "actor_id": "executor",
        },
    )


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


async def _finish_unexpected_execution_failure(
    session: aiohttp.ClientSession,
    redis: Redis,
    msg_id: bytes,
    raw_fields: dict[Any, Any],
    exc: BaseException,
) -> None:
    """Durable failure path for unexpected errors in handle_execution.

    XACK only after control plane acknowledges receipt + status, or when the message
    is poison (no mission_id) and we intentionally drop it to avoid a stuck loop.
    """
    f = _decode_fields(raw_fields)
    data = _parse_data(f)
    mission_id = str(data.get("mission_id") or "").strip()
    err_type = type(exc).__name__
    detail = _sanitize_error_excerpt(str(exc))

    if not mission_id:
        log.warning(
            json.dumps(
                {
                    "executor": "unexpected_failure_poison_message",
                    "error_type": err_type,
                    "detail": detail,
                    "action": "xack_no_mission_id",
                }
            )
        )
        try:
            await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
        except Exception as ack_e:
            log.warning(
                json.dumps({"error": "xack_poison_fail", "detail": str(ack_e)})
            )
        return

    log.error(
        json.dumps(
            {
                "executor": "unexpected_failure",
                "mission_id": mission_id,
                "error_type": err_type,
                "detail": detail,
            }
        )
    )

    receipt_payload: dict[str, Any] = {
        "success": False,
        "error_class": "executor_internal_error",
        "error_type": err_type,
        "detail": detail,
    }

    receipt_ok = await _post_control_plane(
        session,
        "/api/v1/receipts",
        {
            "mission_id": mission_id,
            "receipt_type": "executor_internal_failure",
            "source": "executor",
            "payload": receipt_payload,
            "summary": "Executor stopped unexpectedly before recording a normal receipt.",
        },
    )
    status_ok = await _post_control_plane(
        session,
        f"/api/v1/missions/{mission_id}/status",
        {"status": "failed"},
    )

    if receipt_ok and status_ok:
        await _xadd_updates(
            redis,
            mission_id=mission_id,
            message="Executor encountered an internal error before completing.",
            status="failed",
        )
        try:
            await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
        except Exception as ack_e:
            log.warning(
                json.dumps({"error": "xack_after_durable_fail", "detail": str(ack_e)})
            )
        return

    log.error(
        json.dumps(
            {
                "executor": "durable_failure_not_recorded_not_xacking",
                "mission_id": mission_id,
                "receipt_ok": receipt_ok,
                "status_ok": status_ok,
            }
        )
    )


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

    started_ok = await _post_mission_event(
        session,
        mission_id,
        "execution_started",
        {"stream": STREAM_EXECUTION},
    )
    if not started_ok:
        log.error(
            json.dumps(
                {
                    "executor": "execution_started_write_failed_not_xacking",
                    "mission_id": mission_id,
                }
            )
        )
        return

    requested_lane = _requested_lane_from_data(data)

    stages_to_run: list[dict[str, Any]] = []
    mission_json = await _get_control_plane_json(session, f"/api/v1/missions/{mission_id}")
    if isinstance(mission_json, dict):
        raw_stages = mission_json.get("stages")
        if isinstance(raw_stages, list) and len(raw_stages) > 0:
            stages_to_run = _executor_normalize_stages(raw_stages)

    if not stages_to_run:
        if _executor_command_is_complex(command_text):
            plan_path = f"/api/v1/missions/{mission_id}/plan?command={quote(command_text, safe='')}"
            plan_json = await _get_control_plane_json(session, plan_path)
            if isinstance(plan_json, dict):
                ps = plan_json.get("stages")
                if isinstance(ps, list) and len(ps) > 0:
                    stages_to_run = _executor_normalize_stages(ps)
            if not stages_to_run:
                log.warning(
                    json.dumps(
                        {
                            "executor": "plan_fetch_failed_or_empty_fallback_single",
                            "mission_id": mission_id,
                        }
                    )
                )

    cfg = _load_openclaw_json()
    gateway_model = _default_gateway_model(cfg)
    if not gateway_model:
        gateway_model = os.getenv("JARVIS_OPENCLAW_GATEWAY_MODEL", "").strip() or None

    if stages_to_run:
        stage_replies: list[str] = []
        for stage in stages_to_run:
            if stage.get("status") not in ("pending", "active"):
                continue
            sid = str(stage.get("id", ""))
            title = str(stage.get("title", ""))
            await _post_mission_event(
                session,
                mission_id,
                "stage_started",
                {"stage_id": sid, "title": title},
            )
            reply_text, ok, oc_meta = await _call_openclaw(
                session, title, mission_id, requested_lane
            )
            execution_meta = _build_execution_meta(data, gateway_model=gateway_model)
            execution_meta["stage_id"] = sid

            receipt_payload: dict[str, Any] = {
                "action": title,
                "result": reply_text,
                "success": ok,
                "execution_meta": execution_meta,
                "attempt_count": oc_meta["attempt_count"],
                "error_class": oc_meta["error_class"],
                "exit_code": oc_meta["exit_code"],
                "stderr_excerpt": oc_meta["stderr_excerpt"],
                "final_success": oc_meta["final_success"],
            }

            receipt_ok = await _post_control_plane(
                session,
                "/api/v1/receipts",
                {
                    "mission_id": mission_id,
                    "receipt_type": "openclaw_execution",
                    "source": "executor",
                    "payload": receipt_payload,
                    "summary": reply_text,
                },
            )
            if not receipt_ok:
                log.error(
                    json.dumps(
                        {
                            "executor": "stage_receipt_write_failed_not_xacking",
                            "mission_id": mission_id,
                            "stage_id": sid,
                        }
                    )
                )
                return

            if ok:
                await _post_mission_event(
                    session,
                    mission_id,
                    "stage_completed",
                    {"stage_id": sid},
                )
                stage_replies.append(reply_text)
            else:
                await _post_mission_event(
                    session,
                    mission_id,
                    "stage_failed",
                    {"stage_id": sid},
                )
                status_ok = await _post_control_plane(
                    session,
                    f"/api/v1/missions/{mission_id}/status",
                    {"status": "failed"},
                )
                if not status_ok:
                    log.error(
                        json.dumps(
                            {
                                "executor": "stage_fail_status_write_failed_not_xacking",
                                "mission_id": mission_id,
                            }
                        )
                    )
                    return
                await _post_mission_event(
                    session,
                    mission_id,
                    "execution_failed",
                    {"success": False},
                )
                await _xadd_updates(
                    redis,
                    mission_id=mission_id,
                    message=reply_text,
                    status="failed",
                )
                await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
                return

        final_status = "complete"
        status_ok = await _post_control_plane(
            session,
            f"/api/v1/missions/{mission_id}/status",
            {"status": final_status},
        )
        if not status_ok:
            log.error(
                json.dumps(
                    {
                        "executor": "stages_complete_status_write_failed_not_xacking",
                        "mission_id": mission_id,
                    }
                )
            )
            return

        term_ok = await _post_mission_event(
            session,
            mission_id,
            "execution_completed",
            {"success": True},
        )
        if not term_ok:
            log.warning(
                json.dumps(
                    {
                        "executor": "terminal_lifecycle_event_failed",
                        "mission_id": mission_id,
                        "event_type": "execution_completed",
                    }
                )
            )

        summary_text = "\n\n".join(stage_replies) if stage_replies else ""
        await _xadd_updates(
            redis,
            mission_id=mission_id,
            message=summary_text,
            status=final_status,
        )
        await redis.xack(STREAM_EXECUTION, GROUP_EXECUTOR, msg_id)
        return

    reply_text, ok, oc_meta = await _call_openclaw(
        session, command_text, mission_id, requested_lane
    )

    execution_meta = _build_execution_meta(data, gateway_model=gateway_model)

    receipt_payload: dict[str, Any] = {
        "action": command_text,
        "result": reply_text,
        "success": ok,
        "execution_meta": execution_meta,
        "attempt_count": oc_meta["attempt_count"],
        "error_class": oc_meta["error_class"],
        "exit_code": oc_meta["exit_code"],
        "stderr_excerpt": oc_meta["stderr_excerpt"],
        "final_success": oc_meta["final_success"],
    }

    receipt_ok = await _post_control_plane(
        session,
        "/api/v1/receipts",
        {
            "mission_id": mission_id,
            "receipt_type": "openclaw_execution",
            "source": "executor",
            "payload": receipt_payload,
            "summary": reply_text,
        },
    )

    final_status = "complete" if ok else "failed"
    status_ok = await _post_control_plane(
        session,
        f"/api/v1/missions/{mission_id}/status",
        {"status": final_status},
    )

    if not receipt_ok or not status_ok:
        log.error(
            json.dumps(
                {
                    "executor": "normal_path_durable_write_failed_not_xacking",
                    "mission_id": mission_id,
                    "receipt_ok": receipt_ok,
                    "status_ok": status_ok,
                }
            )
        )
        return

    term_type = "execution_completed" if ok else "execution_failed"
    term_ok = await _post_mission_event(
        session,
        mission_id,
        term_type,
        {"success": ok},
    )
    if not term_ok:
        log.warning(
            json.dumps(
                {
                    "executor": "terminal_lifecycle_event_failed",
                    "mission_id": mission_id,
                    "event_type": term_type,
                }
            )
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
        iid = default_instance_id()

        async def _executor_heartbeat_loop() -> None:
            if not os.getenv("CONTROL_PLANE_API_KEY", "").strip():
                return
            ml = os.getenv("JARVIS_WORKER_MACHINE_LABEL", "").strip() or iid
            _gw = os.getenv("JARVIS_GATEWAY_HEALTH_URL", "").strip()
            _oll = os.getenv("JARVIS_OLLAMA_HEALTH_URL", "").strip()

            cmd_path = Path(OPENCLAW_CMD)

            async def _build_readiness_meta() -> dict[str, object]:
                ping_ok: bool | None = None
                try:
                    ping_ok = bool(await r.ping())
                except Exception:
                    ping_ok = False
                cfg = _load_openclaw_json()
                lane = _lane_from_gateway_model(_default_gateway_model(cfg))
                cmd_exists = cmd_path.is_file() or cmd_path.is_symlink()
                return executor_readiness_snapshot(
                    machine_label=ml,
                    control_plane_api_key_configured=True,
                    openclaw_cmd=OPENCLAW_CMD,
                    openclaw_cmd_exists=cmd_exists,
                    openclaw_json_exists=OPENCLAW_JSON.is_file(),
                    auth_profiles_configured=_auth_profiles_appear_configured(),
                    gateway_model_lane=lane,
                    redis_ping_ok=ping_ok,
                    stream=STREAM_EXECUTION,
                    group=GROUP_EXECUTOR,
                    consumer_name=CONSUMER_NAME,
                    gateway_health_url=_gw or None,
                    ollama_health_url=_oll or None,
                )

            reg = await _build_readiness_meta()
            await register_worker(
                worker_type="executor",
                name=f"Executor ({iid})",
                meta={**reg, "pid": os.getpid()},
                instance_id=iid,
            )
            while True:
                await asyncio.sleep(heartbeat_interval_sec())
                hb_meta = await _build_readiness_meta()
                await heartbeat_worker(
                    worker_type="executor",
                    meta={**hb_meta, "pid": os.getpid()},
                    instance_id=iid,
                )

        async def _read_loop() -> None:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as http:
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
                                await _finish_unexpected_execution_failure(
                                    http, r, msg_id, raw_fields, e
                                )

        tasks: list[asyncio.Task[None]] = [
            asyncio.create_task(_read_loop()),
        ]
        if os.getenv("CONTROL_PLANE_API_KEY", "").strip():
            tasks.append(asyncio.create_task(_executor_heartbeat_loop()))
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                try:
                    await t
                except asyncio.CancelledError:
                    pass


async def _main() -> None:
    if not CONTROL_PLANE_URL:
        raise RuntimeError("CONTROL_PLANE_URL env var is required")
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL env var is required")
    w = ExecutorWorker()
    await w.connect()
    try:
        await w.run()
    finally:
        await w.close()


if __name__ == "__main__":
    asyncio.run(_main())
