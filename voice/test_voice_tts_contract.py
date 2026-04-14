"""Lightweight contract checks for voice TTS / WebSocket recovery (no browser)."""

from __future__ import annotations


def test_tts_subprocess_timeout_configured() -> None:
    """Regression: isolated TTS uses a bounded wait (see ``tts_isolated``)."""
    from voice.server import TTS_WAV_TIMEOUT_SEC
    from voice.tts_isolated import TTS_SYNTHESIS_TIMEOUT_SEC

    assert TTS_WAV_TIMEOUT_SEC is TTS_SYNTHESIS_TIMEOUT_SEC
    assert isinstance(TTS_SYNTHESIS_TIMEOUT_SEC, float)
    assert 5.0 <= TTS_SYNTHESIS_TIMEOUT_SEC <= 120.0
