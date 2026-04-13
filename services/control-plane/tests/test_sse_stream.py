"""Unit tests for SSE mission stream (keepalive + data frames; no DB)."""

from __future__ import annotations

import asyncio

import pytest

from app.realtime.hub import RealtimeHub
from app.realtime.sse_stream import sse_mission_updates_stream


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sse_emits_retry_then_keepalive_without_mission_traffic() -> None:
    hub = RealtimeHub()
    gen = sse_mission_updates_stream(hub, keepalive_sec=0.05)
    assert (await gen.__anext__()).startswith("retry:")
    assert (await asyncio.wait_for(gen.__anext__(), timeout=0.3)) == ": keepalive\n\n"
    await gen.aclose()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sse_emits_data_when_hub_broadcasts() -> None:
    hub = RealtimeHub()
    gen = sse_mission_updates_stream(hub, keepalive_sec=300.0)
    assert (await gen.__anext__()).startswith("retry:")
    await hub.broadcast({"type": "mission", "mission": {"id": "m1", "title": "t"}})
    out = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert out.startswith("data: ")
    assert "m1" in out
    await gen.aclose()
