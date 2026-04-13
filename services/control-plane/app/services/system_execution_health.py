"""Execution-plane vs control-plane-local health probing (no secrets).

OpenClaw gateway and Ollama often run off the control-plane host. This module
never treats implicit localhost as authoritative execution truth without labeling.
"""

from __future__ import annotations

import asyncio
import urllib.error
import urllib.request
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.schemas.system import ComponentHealth

if TYPE_CHECKING:
    from app.models.worker import Worker

# Stored on ComponentHealth.probe_source for operator UI / API consumers.
PROBE_CONTROL_PLANE_LOCAL = "control_plane_local"
PROBE_CONFIGURED_REMOTE = "configured_remote"
PROBE_WORKER_REGISTRY = "worker_registry_inference"
PROBE_UNKNOWN = "unknown"


def _local_hostname(h: str | None) -> bool:
    if not h:
        return False
    hl = h.lower().strip()
    return hl in ("localhost", "127.0.0.1", "::1") or hl.startswith("127.")


def probe_source_for_url(url: str) -> str:
    """Classify a configured URL: localhost-ish → control_plane_local, else remote."""
    try:
        host = urlparse(url).hostname
    except Exception:
        return PROBE_CONFIGURED_REMOTE
    return PROBE_CONTROL_PLANE_LOCAL if _local_hostname(host) else PROBE_CONFIGURED_REMOTE


def gather_gateway_urls(
    configured_url: str,
    workers: list[Worker],
) -> list[tuple[str, str]]:
    """Ordered probe candidates: (url, probe_source_label). Deduped."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    u = (configured_url or "").strip()
    if u:
        out.append((u, probe_source_for_url(u)))
        seen.add(u)
    for w in workers:
        if (w.worker_type or "").strip().lower() not in ("executor", "coordinator"):
            continue
        md = getattr(w, "metadata_", None)
        if not isinstance(md, dict):
            continue
        for key in (
            "gateway_health_url",
            "openclaw_gateway_health_url",
            "execution_gateway_url",
        ):
            raw = md.get(key)
            if isinstance(raw, str) and raw.strip():
                url = raw.strip()
                if url not in seen:
                    out.append((url, PROBE_WORKER_REGISTRY))
                    seen.add(url)
    return out


def gather_ollama_urls(
    configured_url: str,
    workers: list[Worker],
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    u = (configured_url or "").strip()
    if u:
        out.append((u, probe_source_for_url(u)))
        seen.add(u)
    for w in workers:
        if (w.worker_type or "").strip().lower() not in ("executor", "coordinator"):
            continue
        md = getattr(w, "metadata_", None)
        if not isinstance(md, dict):
            continue
        raw = md.get("ollama_health_url")
        if isinstance(raw, str) and raw.strip():
            url = raw.strip()
            if url not in seen:
                out.append((url, PROBE_WORKER_REGISTRY))
                seen.add(url)
    return out


def _http_probe_sync(url: str, timeout: float = 2.0) -> ComponentHealth:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            if isinstance(code, int) and code < 500:
                return ComponentHealth(status="healthy", detail=f"HTTP {code}")
            return ComponentHealth(status="degraded", detail=f"HTTP {code}")
    except urllib.error.HTTPError as e:
        if e.code < 500:
            return ComponentHealth(status="healthy", detail=f"HTTP {e.code}")
        return ComponentHealth(status="degraded", detail=f"HTTP {e.code}")
    except Exception as e:
        return ComponentHealth(status="offline", detail=str(e)[:200])


async def _probe_http(url: str) -> ComponentHealth:
    return await asyncio.to_thread(_http_probe_sync, url)


async def probe_url_chain_labeled(
    candidates: list[tuple[str, str]],
) -> ComponentHealth:
    """Try URLs in order; first healthy/degraded wins. If none, return last failure or unknown."""
    if not candidates:
        return ComponentHealth(
            status="unknown",
            detail=(
                "Execution-plane target not configured: set JARVIS_HEALTH_OPENCLAW_GATEWAY_URL "
                "and/or register workers with metadata gateway_health_url."
            ),
            probe_source=PROBE_UNKNOWN,
        )
    last: ComponentHealth | None = None
    for url, source in candidates:
        h = await _probe_http(url)
        last = ComponentHealth(
            status=h.status,
            detail=_format_probe_detail(h.detail, source, url),
            probe_source=source,
        )
        if h.status in ("healthy", "degraded"):
            return last
    assert last is not None
    return last


def _format_probe_detail(
    probe_detail: str | None, source: str, url: str, max_len: int = 320
) -> str:
    safe_url = url[:96] + ("…" if len(url) > 96 else "")
    base = probe_detail or "probe"
    line = f"{base} · scope={source} · url={safe_url}"
    return line if len(line) <= max_len else line[: max_len - 1] + "…"


async def openclaw_gateway_health(
    *,
    configured_gateway_url: str,
    workers: list[Worker],
) -> ComponentHealth:
    cands = gather_gateway_urls(configured_gateway_url, workers)
    return await probe_url_chain_labeled(cands)


async def ollama_health(
    *,
    configured_ollama_url: str,
    workers: list[Worker],
) -> ComponentHealth:
    cands = gather_ollama_urls(configured_ollama_url, workers)
    if not cands:
        return ComponentHealth(
            status="unknown",
            detail=(
                "Ollama/LLM endpoint not probed: set JARVIS_HEALTH_OLLAMA_URL "
                "and/or worker metadata ollama_health_url."
            ),
            probe_source=PROBE_UNKNOWN,
        )
    return await probe_url_chain_labeled(cands)
