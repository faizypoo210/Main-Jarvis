"""HTTP helpers for POST /workers/register and /workers/heartbeat (control plane API key).

Workers call these with httpx; control plane stores direct truth in ``workers`` table.
"""

from __future__ import annotations

import os
import socket
from typing import Any

import httpx

_DEFAULT_INTERVAL = 60.0


def control_plane_base_url() -> str:
    return os.environ.get("CONTROL_PLANE_URL", "http://localhost:8001").rstrip("/")


def api_key() -> str:
    return os.environ.get("CONTROL_PLANE_API_KEY", "").strip()


def default_instance_id() -> str:
    return (
        os.environ.get("JARVIS_WORKER_INSTANCE_ID", "").strip()
        or socket.gethostname()
        or "default"
    )


def heartbeat_interval_sec() -> float:
    raw = os.environ.get("JARVIS_WORKER_HEARTBEAT_INTERVAL_SEC", "").strip()
    if not raw:
        return _DEFAULT_INTERVAL
    try:
        return max(15.0, float(raw))
    except ValueError:
        return _DEFAULT_INTERVAL


async def register_worker(
    *,
    worker_type: str,
    name: str,
    meta: dict[str, Any] | None = None,
    instance_id: str | None = None,
    host: str | None = None,
    version: str | None = None,
) -> bool:
    key = api_key()
    if not key:
        return False
    base = control_plane_base_url()
    iid = instance_id or default_instance_id()
    payload: dict[str, Any] = {
        "worker_type": worker_type,
        "instance_id": iid,
        "name": name,
        "status": "healthy",
        "meta": meta or {},
    }
    if host:
        payload["host"] = host[:256]
    if version:
        payload["version"] = version[:128]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{base}/api/v1/workers/register",
                json=payload,
                headers={"x-api-key": key, "Content-Type": "application/json"},
            )
            r.raise_for_status()
        return True
    except Exception:
        return False


async def heartbeat_worker(
    *,
    worker_type: str,
    status: str = "healthy",
    meta: dict[str, Any] | None = None,
    instance_id: str | None = None,
    last_error: str | None = None,
) -> bool:
    key = api_key()
    if not key:
        return False
    base = control_plane_base_url()
    iid = instance_id or default_instance_id()
    payload: dict[str, Any] = {
        "worker_type": worker_type,
        "instance_id": iid,
        "status": status,
        "meta": meta or {},
    }
    if last_error:
        payload["last_error"] = last_error[:2048]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{base}/api/v1/workers/heartbeat",
                json=payload,
                headers={"x-api-key": key, "Content-Type": "application/json"},
            )
            r.raise_for_status()
        return True
    except Exception:
        return False
