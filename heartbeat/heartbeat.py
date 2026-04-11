"""JARVIS Heartbeat worker — periodic POST /api/v1/heartbeat/run (supervision, not chat).

TRUTH_SOURCE: CONTROL_PLANE_URL + CONTROL_PLANE_API_KEY; interval HEARTBEAT_INTERVAL_SEC.
MACHINE_CONFIG_REQUIRED: same API key as coordinator/executor for control plane.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

CONTROL_PLANE_URL = os.environ.get("CONTROL_PLANE_URL", "http://localhost:8001").rstrip("/")
API_KEY = os.environ.get("CONTROL_PLANE_API_KEY", "")
INTERVAL_SEC = float(os.environ.get("HEARTBEAT_INTERVAL_SEC", "120"))

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("jarvis.heartbeat")


async def run_once(client: httpx.AsyncClient) -> None:
    url = f"{CONTROL_PLANE_URL}/api/v1/heartbeat/run"
    try:
        r = await client.post(
            url,
            json={},
            headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
            timeout=120.0,
        )
        r.raise_for_status()
        body = r.json()
        log.info(
            json.dumps(
                {
                    "heartbeat": "ok",
                    "open_count": body.get("open_count"),
                    "resolved_this_run": body.get("resolved_this_run"),
                    "upserted": body.get("upserted"),
                }
            )
        )
    except Exception as e:
        log.warning(json.dumps({"heartbeat": "fail", "detail": str(e)}))


async def main() -> None:
    if not API_KEY.strip():
        log.error("CONTROL_PLANE_API_KEY is required for heartbeat/run")
        sys.exit(1)
    log.info(
        json.dumps(
            {
                "heartbeat": "starting",
                "control_plane": CONTROL_PLANE_URL,
                "interval_sec": INTERVAL_SEC,
            }
        )
    )
    async with httpx.AsyncClient() as client:
        while True:
            t0 = time.monotonic()
            await run_once(client)
            elapsed = time.monotonic() - t0
            sleep_for = max(0.1, INTERVAL_SEC - elapsed)
            await asyncio.sleep(sleep_for)


if __name__ == "__main__":
    asyncio.run(main())
