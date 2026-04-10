"""Integration wiring test: control plane health, Redis command, mission visibility.

Run: python test_wiring.py

Prerequisites: control plane :8001, Redis :6379, coordinator consuming jarvis.commands.
"""

from __future__ import annotations

import json
import sys
import time

import httpx
import redis

CONTROL_PLANE_BASE = "http://localhost:8001"
REDIS_URL = "redis://localhost:6379"
EXPECTED_TITLE = "test wiring command"


def main() -> int:
    # coordinator.py uses CONTROL_PLANE_URL default "http://localhost:8001" - matches CONTROL_PLANE_BASE
    all_ok = True

    # Step 1: health
    try:
        resp = httpx.get(f"{CONTROL_PLANE_BASE}/health", timeout=10.0)
        ok = resp.status_code == 200
        detail = f"status={resp.status_code} body={resp.text[:200]!r}"
        if ok:
            print(f"Step 1 (GET /health): PASS - {detail}")
        else:
            print(f"Step 1 (GET /health): FAIL - {detail}")
            all_ok = False
    except Exception as e:
        print(f"Step 1 (GET /health): FAIL - {type(e).__name__}: {e}")
        all_ok = False

    # Step 2: XADD jarvis.commands
    # coordinator.handle_command: _parse_json_field(f, "data") reads JSON from stream field
    # "data" or "payload"; command text from data["text"] or data["command"]; surface from
    # data["surface_origin"] or data["source"] (_control_plane_command_source).
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        data_json = json.dumps(
            {
                "text": "test wiring command",
                "surface_origin": "voice",
            }
        )
        msg_id = r.xadd(
            "jarvis.commands",
            {"data": data_json},
        )
        print(f"Step 2 (XADD jarvis.commands): PASS - id={msg_id!r}")
    except Exception as e:
        print(f"Step 2 (XADD jarvis.commands): FAIL - {type(e).__name__}: {e}")
        all_ok = False

    # Step 3: wait
    print("Step 3 (wait 3s): PASS - sleeping...")
    time.sleep(3)

    # Step 4: GET missions
    missions: list[object] = []
    try:
        resp = httpx.get(
            f"{CONTROL_PLANE_BASE}/api/v1/missions",
            params={"created_by": "voice", "limit": 5},
            timeout=10.0,
        )
        if resp.status_code != 200:
            print(
                f"Step 4 (GET /api/v1/missions): FAIL - status={resp.status_code} body={resp.text[:300]!r}"
            )
            all_ok = False
        else:
            body = resp.json()
            missions = body if isinstance(body, list) else []
            print(
                f"Step 4 (GET /api/v1/missions?created_by=voice&limit=5): PASS - "
                f"received {len(missions)} mission(s)"
            )
            if missions:
                print(f"       sample titles: {[m.get('title') for m in missions[:5] if isinstance(m, dict)]}")
    except Exception as e:
        print(f"Step 4 (GET /api/v1/missions): FAIL - {type(e).__name__}: {e}")
        all_ok = False

    # Step 5: title check
    found = False
    for m in missions:
        if isinstance(m, dict) and m.get("title") == EXPECTED_TITLE:
            found = True
            break
    if found:
        print(
            f"Step 5 (mission title {EXPECTED_TITLE!r}): PASS - found matching mission"
        )
    else:
        print(
            f"Step 5 (mission title {EXPECTED_TITLE!r}): FAIL - no mission with that title "
            f"in the response (check coordinator is running and control plane received POST /api/v1/commands)"
        )
        all_ok = False

    if all_ok:
        print("\nOVERALL: PASS")
        return 0
    print("\nOVERALL: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
