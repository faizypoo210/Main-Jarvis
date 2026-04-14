"""Web voice surface: how spoken replies are delivered to the browser (local vs server WAV)."""

from __future__ import annotations

import os

# Env default when the client omits ``speech_mode`` (server-side default for WebSocket).
DEFAULT_SPEECH_MODE_ENV = "JARVIS_VOICE_DEFAULT_SPEECH_MODE"

# Client query param / stored mode values.
MODE_BROWSER_FIRST = "browser_first"
MODE_SERVER_PREFERRED = "server_preferred"


def normalize_speech_mode(raw: str | None) -> str:
    """Return ``browser_first`` or ``server_preferred``."""
    default = (os.environ.get(DEFAULT_SPEECH_MODE_ENV) or MODE_BROWSER_FIRST).strip().lower()
    s = (raw or default).strip().lower()
    if s in (MODE_BROWSER_FIRST, "browser", "local"):
        return MODE_BROWSER_FIRST
    if s in (MODE_SERVER_PREFERRED, "server", "wav", "hybrid"):
        return MODE_SERVER_PREFERRED
    return MODE_BROWSER_FIRST


def env_default_speech_mode() -> str:
    return normalize_speech_mode(os.environ.get(DEFAULT_SPEECH_MODE_ENV))
