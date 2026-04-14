"""Last spoken turn cache for voice WebSocket (text + optional TTS payload for repeat)."""

from __future__ import annotations

from dataclasses import dataclass

# Shown when the user asks for repeat but we only have text (TTS failed or timed out earlier).
NO_AUDIO_REPEAT_HINT = (
    "Audio replay is not available for that reply; the text is shown above."
)


@dataclass(frozen=True)
class LastSpokenTurn:
    """Last reply shown to the user; ``audio_b64`` is set only after successful TTS generation."""

    text: str
    kind: str
    audio_b64: str | None = None


def normalize_last_voice_entry(prev: LastSpokenTurn | str | None) -> LastSpokenTurn | None:
    """Support legacy in-memory entries that stored plain text only."""
    if prev is None:
        return None
    if isinstance(prev, LastSpokenTurn):
        return prev
    if isinstance(prev, str):
        return LastSpokenTurn(text=prev, kind="legacy", audio_b64=None)
    raise TypeError(prev)


def ws_tts_message(turn: LastSpokenTurn, *, kind: str) -> dict | None:
    """Build a ``tts`` WebSocket message from a turn, or ``None`` if no cached audio."""
    if not turn.audio_b64:
        return None
    return {"type": "tts", "kind": kind, "text": turn.text, "audio_b64": turn.audio_b64}
