"""Speech mode normalization (browser-first vs server-preferred WAV)."""

from __future__ import annotations

from voice.speech_mode import (
    MODE_BROWSER_FIRST,
    MODE_SERVER_PREFERRED,
    normalize_speech_mode,
)


def test_defaults_to_browser_first_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("JARVIS_VOICE_DEFAULT_SPEECH_MODE", raising=False)
    assert normalize_speech_mode(None) == MODE_BROWSER_FIRST


def test_aliases() -> None:
    assert normalize_speech_mode("browser") == MODE_BROWSER_FIRST
    assert normalize_speech_mode("local") == MODE_BROWSER_FIRST
    assert normalize_speech_mode("server") == MODE_SERVER_PREFERRED
    assert normalize_speech_mode("wav") == MODE_SERVER_PREFERRED


def test_unknown_falls_back_to_browser_first() -> None:
    assert normalize_speech_mode("nonsense") == MODE_BROWSER_FIRST


def test_env_default_can_override_none(monkeypatch) -> None:
    monkeypatch.setenv("JARVIS_VOICE_DEFAULT_SPEECH_MODE", "server_preferred")
    assert normalize_speech_mode(None) == MODE_SERVER_PREFERRED


def test_explicit_param_beats_env(monkeypatch) -> None:
    monkeypatch.setenv("JARVIS_VOICE_DEFAULT_SPEECH_MODE", "server_preferred")
    assert normalize_speech_mode("browser_first") == MODE_BROWSER_FIRST
