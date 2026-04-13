"""SSE byte stream with periodic comment heartbeats (idle-safe for proxies/browsers)."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from typing import Any

from app.realtime.hub import RealtimeHub

_DEFAULT_KEEPALIVE = 20.0


def sse_keepalive_interval_sec() -> float:
    raw = os.environ.get("SSE_KEEPALIVE_SEC", "").strip()
    if not raw:
        return _DEFAULT_KEEPALIVE
    try:
        v = float(raw)
        return max(5.0, min(120.0, v))
    except ValueError:
        return _DEFAULT_KEEPALIVE


async def sse_mission_updates_stream(
    hub: RealtimeHub, *, keepalive_sec: float | None = None
) -> AsyncIterator[str]:
    """Yield SSE lines: initial retry, then data frames or `: keepalive` comments on idle."""
    interval = keepalive_sec if keepalive_sec is not None else sse_keepalive_interval_sec()
    bridge: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)

    async def pump() -> None:
        async for msg in hub.subscribe():
            await bridge.put(msg)

    # Start pump before the first yield so hub subscription is live before any client
    # bytes (avoids a race where broadcasts between retry and the first bridge wait are lost).
    pump_task = asyncio.create_task(pump())
    await asyncio.sleep(0)
    try:
        yield "retry: 5000\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(bridge.get(), timeout=interval)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
            else:
                yield f"data: {json.dumps(msg)}\n\n"
    finally:
        pump_task.cancel()
        try:
            await pump_task
        except asyncio.CancelledError:
            pass
