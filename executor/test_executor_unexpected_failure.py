"""Deterministic checks for executor durable-failure / XACK behavior (no Redis required).

Run:
  python executor/test_executor_unexpected_failure.py
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


async def _test_no_xack_when_receipt_not_confirmed() -> None:
    m = _load_executor()
    redis = AsyncMock()
    redis.xack = AsyncMock()

    async def fake_post(_session, path, _payload):
        if "/receipts" in path:
            return False
        return True

    m._post_control_plane = fake_post  # type: ignore[method-assign]
    m._xadd_updates = AsyncMock()  # type: ignore[method-assign]

    http = AsyncMock()
    mid = "550e8400-e29b-41d4-a716-446655440000"
    raw_fields = {b"data": json.dumps({"mission_id": mid}).encode()}

    await m._finish_unexpected_execution_failure(
        http, redis, b"1-0", raw_fields, RuntimeError("simulated")
    )
    assert not redis.xack.called


async def _test_xack_when_durable_writes_succeed() -> None:
    m = _load_executor()
    redis = AsyncMock()
    redis.xack = AsyncMock()

    async def fake_post(_session, _path, _payload):
        return True

    m._post_control_plane = fake_post  # type: ignore[method-assign]
    m._xadd_updates = AsyncMock()  # type: ignore[method-assign]

    http = AsyncMock()
    mid = "550e8400-e29b-41d4-a716-446655440000"
    raw_fields = {b"data": json.dumps({"mission_id": mid}).encode()}

    await m._finish_unexpected_execution_failure(
        http, redis, b"1-0", raw_fields, RuntimeError("simulated")
    )
    assert redis.xack.await_count == 1


async def _test_poison_message_xacks_without_control_plane() -> None:
    m = _load_executor()
    redis = AsyncMock()
    redis.xack = AsyncMock()

    async def fake_post(*_a, **_k):
        raise AssertionError("control plane should not be called without mission_id")

    m._post_control_plane = fake_post  # type: ignore[method-assign]

    http = AsyncMock()
    raw_fields = {b"data": json.dumps({"text": "no mission id"}).encode()}

    await m._finish_unexpected_execution_failure(
        http, redis, b"1-0", raw_fields, RuntimeError("simulated")
    )
    assert redis.xack.await_count == 1


async def _main() -> None:
    await _test_no_xack_when_receipt_not_confirmed()
    await _test_xack_when_durable_writes_succeed()
    await _test_poison_message_xacks_without_control_plane()
    print("executor unexpected-failure tests: ok")


if __name__ == "__main__":
    asyncio.run(_main())
