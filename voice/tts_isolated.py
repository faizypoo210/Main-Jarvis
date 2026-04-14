"""Subprocess-isolated TTS so a bad run cannot poison the next synthesis (Windows SAPI/pyttsx3)."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger("jarvis.voice.tts")

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Humane UX: fail faster than multi-minute hangs; subprocess is killed on expiry.
TTS_SYNTHESIS_TIMEOUT_SEC = float(os.environ.get("JARVIS_VOICE_TTS_TIMEOUT_SEC", "45"))

_LAST_FAILURE_MONO: float = 0.0


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        proc.kill()
    except ProcessLookupError:
        return
    except OSError as e:
        log.warning("tts subprocess kill: %s", e)
    try:
        await asyncio.wait_for(proc.wait(), timeout=8.0)
    except asyncio.TimeoutError:
        log.warning("tts subprocess did not exit promptly after kill")


async def synthesize_wav_isolated(text: str) -> bytes:
    """
    Run one fresh ``python -m voice.tts_worker`` process; return WAV bytes.

    Timeouts and failures are contained: the next call gets a new subprocess.
    """
    global _LAST_FAILURE_MONO
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty TTS text")

    t0 = time.perf_counter()
    log.debug("tts subprocess starting text_len=%s", len(stripped))

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "voice.tts_worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(_REPO_ROOT),
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(input=stripped.encode("utf-8")),
            timeout=TTS_SYNTHESIS_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        _LAST_FAILURE_MONO = time.monotonic()
        log.warning(
            "tts subprocess timed out after %.1fs; terminating (text_len=%s)",
            TTS_SYNTHESIS_TIMEOUT_SEC,
            len(stripped),
        )
        await _terminate_process(proc)
        raise
    elapsed = time.perf_counter() - t0
    err_s = (err or b"").decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        _LAST_FAILURE_MONO = time.monotonic()
        log.warning(
            "tts subprocess failed rc=%s elapsed_ms=%.0f stderr=%s",
            proc.returncode,
            elapsed * 1000,
            err_s[:800] if err_s else "(empty)",
        )
        raise RuntimeError(f"tts subprocess exit {proc.returncode}")

    if not out:
        _LAST_FAILURE_MONO = time.monotonic()
        log.warning("tts subprocess returned empty wav (elapsed_ms=%.0f)", elapsed * 1000)
        raise RuntimeError("empty wav from tts subprocess")

    log.info(
        "tts synthesize ok bytes=%s elapsed_ms=%.0f text_len=%s",
        len(out),
        elapsed * 1000,
        len(stripped),
    )
    return out


def last_tts_failure_monotonic() -> float:
    """Test hook: monotonic clock value after last failed/timed-out synthesis."""
    return _LAST_FAILURE_MONO
