"""Normal-path executor ACK / durable-write behavior (no Redis, no OpenClaw).

Run:
  python executor/test_executor_normal_path.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock


def _load_executor():
    repo_root = Path(__file__).resolve().parents[1]
    rr = str(repo_root)
    if rr not in sys.path:
        sys.path.insert(0, rr)

    here = Path(__file__).resolve().parent
    mod_path = here / "executor.py"
    name = "jarvis_executor_impl"
    spec = importlib.util.spec_from_file_location(name, mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


async def _test_no_xack_when_receipt_write_fails() -> None:
    m = _load_executor()
    redis = AsyncMock()
    redis.xack = AsyncMock()

    async def fake_openclaw(*_a, **_k):
        return (
            "ok",
            True,
            {
                "attempt_count": 1,
                "error_class": m.ERROR_CLASS_OK,
                "exit_code": 0,
                "stderr_excerpt": "",
                "final_success": True,
            },
        )

    post_calls: list[tuple[str, dict]] = []

    async def fake_post(session, path, payload):
        post_calls.append((path, payload))
        if path == "/api/v1/receipts":
            return False
        return True

    m._call_openclaw = fake_openclaw  # type: ignore[method-assign]
    m._post_control_plane = fake_post  # type: ignore[method-assign]
    m._xadd_updates = AsyncMock()  # type: ignore[method-assign]

    http = AsyncMock()
    mid = "550e8400-e29b-41d4-a716-446655440000"
    raw_fields = {b"data": json.dumps({"mission_id": mid, "text": "hi"}).encode()}

    await m.handle_execution(redis, http, b"1-0", raw_fields)
    assert not redis.xack.called


async def _test_no_xack_when_status_write_fails() -> None:
    m = _load_executor()
    redis = AsyncMock()
    redis.xack = AsyncMock()
    mid = "550e8400-e29b-41d4-a716-446655440000"

    async def fake_openclaw(*_a, **_k):
        return (
            "bad",
            False,
            {
                "attempt_count": 1,
                "error_class": m.ERROR_CLASS_EMPTY_OUTPUT,
                "exit_code": 1,
                "stderr_excerpt": "e",
                "final_success": False,
            },
        )

    async def fake_post(session, path, payload):
        if f"/api/v1/missions/{mid}/status" in path:
            return False
        return True

    m._call_openclaw = fake_openclaw  # type: ignore[method-assign]
    m._post_control_plane = fake_post  # type: ignore[method-assign]
    m._xadd_updates = AsyncMock()  # type: ignore[method-assign]

    http = AsyncMock()
    raw_fields = {b"data": json.dumps({"mission_id": mid, "text": "hi"}).encode()}

    await m.handle_execution(redis, http, b"1-0", raw_fields)
    assert not redis.xack.called


async def _test_xack_after_receipt_and_status_succeed() -> None:
    m = _load_executor()
    redis = AsyncMock()
    redis.xack = AsyncMock()

    async def fake_openclaw(*_a, **_k):
        return (
            "done",
            True,
            {
                "attempt_count": 1,
                "error_class": m.ERROR_CLASS_OK,
                "exit_code": 0,
                "stderr_excerpt": "",
                "final_success": True,
            },
        )

    async def fake_post(session, path, payload):
        return True

    m._call_openclaw = fake_openclaw  # type: ignore[method-assign]
    m._post_control_plane = fake_post  # type: ignore[method-assign]
    m._xadd_updates = AsyncMock()  # type: ignore[method-assign]

    http = AsyncMock()
    mid = "550e8400-e29b-41d4-a716-446655440000"
    raw_fields = {b"data": json.dumps({"mission_id": mid, "text": "hi"}).encode()}

    await m.handle_execution(redis, http, b"1-0", raw_fields)
    assert redis.xack.await_count == 1


async def _test_no_xack_when_execution_started_fails() -> None:
    m = _load_executor()
    redis = AsyncMock()
    redis.xack = AsyncMock()

    async def fake_openclaw(*_a, **_k):
        raise AssertionError("openclaw should not run when execution_started fails")

    async def fake_post(session, path, payload):
        if "/events" in path and payload.get("event_type") == "execution_started":
            return False
        return True

    m._call_openclaw = fake_openclaw  # type: ignore[method-assign]
    m._post_control_plane = fake_post  # type: ignore[method-assign]

    http = AsyncMock()
    mid = "550e8400-e29b-41d4-a716-446655440000"
    raw_fields = {b"data": json.dumps({"mission_id": mid, "text": "hi"}).encode()}

    await m.handle_execution(redis, http, b"1-0", raw_fields)
    assert not redis.xack.called


async def _main() -> None:
    await _test_no_xack_when_receipt_write_fails()
    await _test_no_xack_when_status_write_fails()
    await _test_xack_after_receipt_and_status_succeed()
    await _test_no_xack_when_execution_started_fails()
    print("executor normal-path ack tests: ok")


if __name__ == "__main__":
    asyncio.run(_main())
