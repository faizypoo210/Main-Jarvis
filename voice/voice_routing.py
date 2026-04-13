"""Mission ↔ voice WebSocket subscription index (inspectable, no secrets).

Used by server.py to route `jarvis.updates` and TTS only to connections that
subscribed to the relevant mission_id(s).
"""

from __future__ import annotations


class MissionSubscriptionIndex:
    """Maps connection keys to subscribed mission UUID strings.

    Connection keys are typically ``id(websocket)`` from the voice server.
    """

    def __init__(self) -> None:
        self._by_ws: dict[int, set[str]] = {}

    def add_connection(self, ws_key: int, mission_ids: set[str]) -> None:
        clean = {str(m).strip() for m in mission_ids if str(m).strip()}
        self._by_ws[ws_key] = clean

    def add_mission(self, ws_key: int, mission_id: str) -> None:
        mid = str(mission_id).strip()
        if not mid:
            return
        if ws_key not in self._by_ws:
            self._by_ws[ws_key] = set()
        self._by_ws[ws_key].add(mid)

    def remove_connection(self, ws_key: int) -> None:
        self._by_ws.pop(ws_key, None)

    def connection_keys_for_mission(self, mission_id: str) -> list[int]:
        mid = str(mission_id).strip()
        if not mid:
            return []
        return sorted(k for k, mids in self._by_ws.items() if mid in mids)

    def snapshot_mission_count(self, ws_key: int) -> int:
        return len(self._by_ws.get(ws_key, ()))
