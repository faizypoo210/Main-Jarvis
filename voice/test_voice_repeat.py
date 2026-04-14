"""Repeat / last-spoken cache contract (no pyttsx3, no WebSocket)."""

from __future__ import annotations

import base64
from pathlib import Path

from voice.last_spoken import (
    NO_AUDIO_REPEAT_HINT,
    LastSpokenTurn,
    normalize_last_voice_entry,
    ws_tts_message,
)


def test_ws_tts_message_none_when_no_cached_audio() -> None:
    turn = LastSpokenTurn(
        display_text="hello",
        spoken_text="hello",
        kind="intake",
        audio_b64=None,
    )
    assert ws_tts_message(turn, kind="repeat") is None


def test_ws_tts_message_returns_payload_when_audio_cached() -> None:
    b64 = base64.b64encode(b"fake wav").decode("ascii")
    turn = LastSpokenTurn(
        display_text="LONG",
        spoken_text="hello",
        kind="intake",
        audio_b64=b64,
    )
    msg = ws_tts_message(turn, kind="repeat")
    assert msg == {
        "type": "tts",
        "kind": "repeat",
        "text": "hello",
        "audio_b64": b64,
    }


def test_normalize_legacy_string_to_turn() -> None:
    t = normalize_last_voice_entry("plain")
    assert isinstance(t, LastSpokenTurn)
    assert t.display_text == "plain"
    assert t.spoken_text == "plain"
    assert t.kind == "legacy"
    assert t.audio_b64 is None


def test_normalize_none() -> None:
    assert normalize_last_voice_entry(None) is None


def test_no_audio_hint_is_explicit() -> None:
    assert "Audio replay" in NO_AUDIO_REPEAT_HINT
    assert len(NO_AUDIO_REPEAT_HINT) < 500


def test_server_repeat_path_resends_cached_tts_without_regenerating() -> None:
    """Regression: repeat must use ``ws_tts_message`` / ``_replay_cached_tts``, not ``_tts_wav_bytes``."""
    from voice import server as voice_server

    body = Path(voice_server.__file__).read_text(encoding="utf-8")
    assert "async def _replay_cached_tts" in body
    assert "ws_tts_message(turn" in body
    assert "if prev.audio_b64:" in body
    assert "await _replay_cached_tts(prev)" in body
