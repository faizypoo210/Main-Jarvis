"""Unit tests for machine-aware execution health URL gathering (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.system_execution_health import (
    PROBE_CONFIGURED_REMOTE,
    PROBE_CONTROL_PLANE_LOCAL,
    PROBE_UNKNOWN,
    PROBE_WORKER_REGISTRY,
    gather_gateway_urls,
    gather_ollama_urls,
    ollama_health,
    openclaw_gateway_health,
    probe_source_for_url,
)


def test_probe_source_for_url_localhost_vs_remote() -> None:
    assert probe_source_for_url("http://127.0.0.1:18789/health") == PROBE_CONTROL_PLANE_LOCAL
    assert probe_source_for_url("http://localhost:11434/api/tags") == PROBE_CONTROL_PLANE_LOCAL
    assert probe_source_for_url("http://exec-host.internal:18789/health") == PROBE_CONFIGURED_REMOTE


def test_gather_gateway_prefers_config_then_worker() -> None:
    w = SimpleNamespace(
        worker_type="executor",
        metadata_={"gateway_health_url": "http://worker-host/health"},
    )
    c = gather_gateway_urls("http://cp-configured/gw", [w])
    assert [u for u, _ in c] == [
        "http://cp-configured/gw",
        "http://worker-host/health",
    ]
    assert c[0][1] == PROBE_CONFIGURED_REMOTE
    assert c[1][1] == PROBE_WORKER_REGISTRY


def test_gather_gateway_dedupes_same_url() -> None:
    u = "http://shared.example/health"
    w = SimpleNamespace(worker_type="executor", metadata_={"gateway_health_url": u})
    c = gather_gateway_urls(u, [w])
    assert len(c) == 1
    assert c[0][1] == PROBE_CONFIGURED_REMOTE


def test_gather_gateway_skips_non_executor_workers() -> None:
    w = SimpleNamespace(worker_type="other", metadata_={"gateway_health_url": "http://x/h"})
    assert gather_gateway_urls("", [w]) == []


def test_gather_ollama_worker_metadata() -> None:
    w = SimpleNamespace(worker_type="coordinator", metadata_={"ollama_health_url": "http://w/ollama"})
    c = gather_ollama_urls("", [w])
    assert c == [("http://w/ollama", PROBE_WORKER_REGISTRY)]


@pytest.mark.asyncio
async def test_openclaw_gateway_health_unknown_without_targets() -> None:
    h = await openclaw_gateway_health(configured_gateway_url="", workers=[])
    assert h.status == "unknown"
    assert h.probe_source == PROBE_UNKNOWN
    assert "execution-plane" in (h.detail or "").lower()
    assert "gateway_health_url" in (h.detail or "").lower()


@pytest.mark.asyncio
async def test_ollama_health_unknown_without_targets() -> None:
    h = await ollama_health(configured_ollama_url="", workers=[])
    assert h.status == "unknown"
    assert h.probe_source == PROBE_UNKNOWN
