"""Smoke: voice static client documents hybrid TTS + browser fallback contract."""

from pathlib import Path


def _index_html() -> str:
    return (Path(__file__).resolve().parent / "static" / "index.html").read_text(encoding="utf-8")


def test_error_reason_triggers_browser_fallback_branch() -> None:
    body = _index_html()
    assert "msg.reason" in body
    assert "tts_unavailable" in body
    assert "repeat_no_audio" in body
    assert "startBrowserSpokenFallback" in body


def test_decode_failure_uses_spoken_line_not_full_transcript() -> None:
    """Fallback WAV path should use tts ``msg.text`` (spoken line), not reply display."""
    body = _index_html()
    assert "msg.text" in body
    assert "Could not decode server audio" in body
