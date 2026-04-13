"""Truthful readiness snapshots for coordinator/executor worker registry metadata (no secrets).

Used by coordinator.py and executor.py when calling POST /workers/register and /workers/heartbeat.
Pure functions are testable without Redis or OpenClaw.
"""

from __future__ import annotations

from typing import Any, Literal

ReadyState = Literal["ready", "not_ready", "degraded"]


def coordinator_readiness_snapshot(
    *,
    machine_label: str,
    control_plane_api_key_configured: bool,
    dashclaw_base_configured: bool,
    dashclaw_api_key_configured: bool,
    redis_ping_ok: bool | None,
    streams: list[str],
    groups: list[str],
    consumer_name: str,
) -> dict[str, Any]:
    """Coordinator needs CP API key, DashClaw URL+key, and a live Redis connection for streams."""
    reasons: list[str] = []
    config_present = (
        control_plane_api_key_configured
        and dashclaw_base_configured
        and dashclaw_api_key_configured
    )
    if not control_plane_api_key_configured:
        reasons.append("CONTROL_PLANE_API_KEY missing")
    if not dashclaw_base_configured:
        reasons.append("DASHCLAW_BASE_URL missing")
    if not dashclaw_api_key_configured:
        reasons.append("DASHCLAW_API_KEY missing")

    dependency_reachable: bool | None
    if redis_ping_ok is None:
        dependency_reachable = None
    else:
        dependency_reachable = redis_ping_ok
        if not redis_ping_ok:
            reasons.append("Redis PING failed")

    if not config_present:
        ready_state: ReadyState = "not_ready"
    elif redis_ping_ok is None:
        ready_state = "degraded"
    elif not redis_ping_ok:
        ready_state = "not_ready"
    else:
        ready_state = "ready"

    reason = "; ".join(reasons) if reasons else "Routing config and Redis OK."

    return {
        "role": "coordinator",
        "machine_label": machine_label[:128],
        "ready_state": ready_state,
        "readiness_reason": reason[:500],
        "config_present": config_present,
        "dependency_reachable": dependency_reachable,
        "streams": streams[:16],
        "groups": groups[:16],
        "consumer": consumer_name[:128],
    }


def executor_readiness_snapshot(
    *,
    machine_label: str,
    control_plane_api_key_configured: bool,
    openclaw_cmd: str,
    openclaw_cmd_exists: bool,
    openclaw_json_exists: bool,
    auth_profiles_configured: bool,
    gateway_model_lane: str | None,
    redis_ping_ok: bool | None,
    stream: str,
    group: str,
    consumer_name: str,
    gateway_health_url: str | None,
    ollama_health_url: str | None,
) -> dict[str, Any]:
    """Executor needs API key, OpenClaw CLI path, and local OpenClaw config files for runs."""
    reasons: list[str] = []
    if not control_plane_api_key_configured:
        reasons.append("CONTROL_PLANE_API_KEY missing")
    if not openclaw_cmd_exists:
        reasons.append("OPENCLAW_CMD path not found")
    if not openclaw_json_exists:
        reasons.append("openclaw.json missing under ~/.openclaw")
    if openclaw_json_exists and not auth_profiles_configured:
        reasons.append("auth-profiles.json absent or empty (cloud lanes may fail)")

    config_present = (
        control_plane_api_key_configured and openclaw_cmd_exists and openclaw_json_exists
    )

    if redis_ping_ok is False:
        reasons.append("Redis PING failed")

    dependency_reachable: bool | None
    if redis_ping_ok is None:
        dependency_reachable = None
    else:
        dependency_reachable = redis_ping_ok

    if not config_present:
        ready_state: ReadyState = "not_ready"
    elif redis_ping_ok is None:
        ready_state = "degraded"
    elif redis_ping_ok is False:
        ready_state = "not_ready"
    elif openclaw_json_exists and not auth_profiles_configured:
        ready_state = "degraded"
    else:
        ready_state = "ready"

    reason = "; ".join(reasons) if reasons else "CLI, config, and execution stream OK."

    out: dict[str, Any] = {
        "role": "executor",
        "machine_label": machine_label[:128],
        "ready_state": ready_state,
        "readiness_reason": reason[:500],
        "config_present": config_present,
        "dependency_reachable": dependency_reachable,
        "openclaw_cmd_basename": openclaw_cmd.split("/")[-1].split("\\")[-1][:128],
        "gateway_model_lane": (gateway_model_lane or "")[:64] or None,
        "stream": stream[:128],
        "group": group[:128],
        "consumer": consumer_name[:128],
    }
    if gateway_health_url:
        out["gateway_health_url"] = gateway_health_url.strip()[:512]
    if ollama_health_url:
        out["ollama_health_url"] = ollama_health_url.strip()[:512]
    return out
