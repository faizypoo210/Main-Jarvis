"""Registry summary readiness counts (no database — WorkerRepository mocked)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.worker_registry_service import build_registry_summary


class _FakeRow:
    __slots__ = ("metadata_", "last_heartbeat_at")

    def __init__(self, meta: dict, hb: datetime | None) -> None:
        self.metadata_ = meta
        self.last_heartbeat_at = hb


@pytest.mark.asyncio
async def test_build_registry_summary_counts_ready_state_meta() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        _FakeRow({"ready_state": "ready"}, now),
        _FakeRow({"ready_state": "not_ready"}, now),
        _FakeRow({"ready_state": "degraded"}, now),
        _FakeRow({}, now),
        _FakeRow({"ready_state": " Ready "}, now),
    ]
    with patch(
        "app.services.worker_registry_service.WorkerRepository.list_all",
        new=AsyncMock(return_value=rows),
    ):
        s = await build_registry_summary(AsyncMock(), threshold_minutes=15)

    assert s.registered_total == 5
    assert s.healthy_heartbeat == 5
    assert s.stale_or_absent == 0
    assert s.readiness_ready == 2
    assert s.readiness_not_ready == 1
    assert s.readiness_degraded == 1
