"""Smoke: server wires speech mode + browser delivery (string checks, no FastAPI runtime)."""

from pathlib import Path


def test_server_has_browser_first_branch_in_speak_local() -> None:
    from voice import server as voice_server

    body = Path(voice_server.__file__).read_text(encoding="utf-8")
    assert "MODE_BROWSER_FIRST" in body
    assert "speech_mode_for" in body
    assert 'TTS_DELIVERY_BROWSER' in body or '"delivery": TTS_DELIVERY_BROWSER' in body


def test_connect_accepts_speech_mode_query() -> None:
    from voice import server as voice_server

    body = Path(voice_server.__file__).read_text(encoding="utf-8")
    assert "speech_mode" in body and "speech_mode_q" in body
