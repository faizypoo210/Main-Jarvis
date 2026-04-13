"""Pydantic contract checks for operator JSON shapes (no ASGI, no database I/O)."""

from __future__ import annotations

import pytest

from app.schemas.system import SystemHealthResponse

pytestmark = pytest.mark.unit


def test_system_health_response_accepts_worker_registry_readiness_counts() -> None:
    """Regression: worker_registry must include readiness aggregates from WorkerRegistrySummary."""
    payload = {
        "checked_at": "2026-04-01T12:00:00.000000Z",
        "control_plane": {
            "status": "healthy",
            "detail": "API responding",
            "probe_source": "control_plane_local",
        },
        "postgres": {"status": "healthy", "detail": None, "probe_source": "control_plane_local"},
        "redis": {"status": "healthy", "detail": "PING ok", "probe_source": "control_plane_local"},
        "openclaw_gateway": {
            "status": "unknown",
            "detail": None,
            "probe_source": "unknown",
        },
        "ollama": {"status": "unknown", "detail": None, "probe_source": "unknown"},
        "worker_registry": {
            "registered_total": 2,
            "healthy_heartbeat": 1,
            "stale_or_absent": 1,
            "threshold_minutes": 15.0,
            "readiness_ready": 1,
            "readiness_not_ready": 0,
            "readiness_degraded": 1,
        },
    }
    model = SystemHealthResponse.model_validate(payload)
    assert model.worker_registry.readiness_ready == 1
    assert model.worker_registry.readiness_degraded == 1
