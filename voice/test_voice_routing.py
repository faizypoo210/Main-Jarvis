"""Unit tests for MissionSubscriptionIndex (no network, no FastAPI).

Run from repo root: python voice/test_voice_routing.py
Or from voice/: python test_voice_routing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from voice_routing import MissionSubscriptionIndex


def test_connection_and_missions() -> None:
    idx = MissionSubscriptionIndex()
    m1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    m2 = "11111111-bbbb-cccc-dddd-eeeeeeeeeeee"
    idx.add_connection(1, {m1})
    idx.add_mission(1, m2)
    assert idx.snapshot_mission_count(1) == 2
    assert idx.connection_keys_for_mission(m1) == [1]
    assert idx.connection_keys_for_mission(m2) == [1]
    assert idx.connection_keys_for_mission("deadbeef-dead-beef-dead-beefdeadbeef") == []


def test_two_connections_same_mission() -> None:
    idx = MissionSubscriptionIndex()
    mid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    idx.add_connection(10, {mid})
    idx.add_connection(20, {mid})
    assert len(idx.connection_keys_for_mission(mid)) == 2


def test_remove_connection() -> None:
    idx = MissionSubscriptionIndex()
    mid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    idx.add_connection(1, {mid})
    idx.remove_connection(1)
    assert idx.connection_keys_for_mission(mid) == []


def main() -> None:
    test_connection_and_missions()
    test_two_connections_same_mission()
    test_remove_connection()
    print("voice_routing tests: ok")


if __name__ == "__main__":
    main()
