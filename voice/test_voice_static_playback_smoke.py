"""Smoke checks that the voice client keeps playback ownership guardrails in static HTML."""

from pathlib import Path


def _index_html() -> str:
    p = Path(__file__).resolve().parent / "static" / "index.html"
    return p.read_text(encoding="utf-8")


def test_index_html_has_playback_ownership_and_cleanup():
    text = _index_html()
    assert "ttsPlaybackGen" in text
    assert "stopCurrentTtsPlayback" in text
    assert "clientOwnsSpeakingIdle" in text
    assert "currentTtsPlaybackTimer" in text
    assert "myGen !== ttsPlaybackGen" in text
