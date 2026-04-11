"""Fan-out hub for Server-Sent Events — single source: post-commit payloads from sessions."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from app.core.logging import get_logger

log = get_logger(__name__)


class RealtimeHub:
    """Broadcast JSON-serializable dicts to all connected SSE clients."""

    def __init__(self) -> None:
        self._subs: list[asyncio.Queue[dict[str, Any] | None]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=512)
        async with self._lock:
            self._subs.append(q)
        try:
            while True:
                msg = await q.get()
                if msg is None:
                    break
                yield msg
        finally:
            async with self._lock:
                if q in self._subs:
                    self._subs.remove(q)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                try:
                    _ = q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(message)
                except asyncio.QueueFull:
                    log.warning("realtime subscriber queue still full after drop")

    async def broadcast_all(self, messages: list[dict[str, Any]]) -> None:
        for m in messages:
            await self.broadcast(m)


_hub: RealtimeHub | None = None


def get_hub() -> RealtimeHub:
    global _hub
    if _hub is None:
        _hub = RealtimeHub()
    return _hub
