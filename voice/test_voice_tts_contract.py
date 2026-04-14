"""Lightweight contract checks for voice TTS / WebSocket recovery (no browser)."""

from __future__ import annotations


def test_tts_wav_timeout_configured() -> None:
    """Regression: TTS must not block the receive loop forever (see server _speak_local)."""
    from voice.server import TTS_WAV_TIMEOUT_SEC

    assert isinstance(TTS_WAV_TIMEOUT_SEC, float)
    assert 10.0 <= TTS_WAV_TIMEOUT_SEC <= 600.0
