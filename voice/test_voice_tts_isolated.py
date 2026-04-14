"""Tests for subprocess-isolated TTS wrapper (mocked; no real pyttsx3 in CI)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voice import tts_isolated


def test_synthesize_returns_wav_bytes_on_success() -> None:
    async def run() -> None:
        fake = b"RIFF....WAVE"
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(fake, b""))
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            out = await tts_isolated.synthesize_wav_isolated("hello")
        assert out == fake

    asyncio.run(run())


def test_timeout_kills_process_next_call_can_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A timed-out subprocess must not block the next synthesis."""

    async def run() -> None:
        monkeypatch.setattr(tts_isolated, "TTS_SYNTHESIS_TIMEOUT_SEC", 0.05)

        proc_fail = MagicMock()
        proc_fail.returncode = None

        async def slow_comm(*_a: object, **_k: object) -> tuple[bytes, bytes]:
            await asyncio.sleep(1.0)
            return (b"", b"")

        proc_fail.communicate = slow_comm
        proc_fail.kill = MagicMock()
        proc_fail.wait = AsyncMock(return_value=0)

        proc_ok = MagicMock()
        proc_ok.returncode = 0
        proc_ok.communicate = AsyncMock(return_value=(b"RIFFok", b""))

        calls = [proc_fail, proc_ok]

        async def mock_exec(*_a: object, **_k: object) -> MagicMock:
            return calls.pop(0)

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            with pytest.raises(asyncio.TimeoutError):
                await tts_isolated.synthesize_wav_isolated("first")
            out = await tts_isolated.synthesize_wav_isolated("second")
        assert out == b"RIFFok"
        assert proc_fail.kill.called

    asyncio.run(run())


def test_subprocess_failure_raises_without_poisoning_callback() -> None:
    async def run() -> None:
        proc = MagicMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(return_value=(b"", b"err"))
        before = tts_isolated.last_tts_failure_monotonic()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            with pytest.raises(RuntimeError, match="tts subprocess"):
                await tts_isolated.synthesize_wav_isolated("x")
        assert tts_isolated.last_tts_failure_monotonic() >= before

    asyncio.run(run())


def test_empty_text_raises() -> None:
    async def run() -> None:
        with pytest.raises(ValueError):
            await tts_isolated.synthesize_wav_isolated("   ")

    asyncio.run(run())
