"""Jarvis reply synthesis — deterministic voice lines from NLU / model output.

Pure string logic; no I/O or LLM calls. ``surface`` is reserved for future surfaces.
"""


def build_jarvis_reply(intent: str, raw: str, surface: str = "voice") -> str:
    """Map classifier intent + raw model text to a single Jarvis-voiced line."""
    _ = surface  # reserved for future use (e.g. command-center vs voice)
    i = (intent or "").strip()
    if i == "open_url":
        return "Opening that for you."
    if i == "unknown":
        return "I didn't catch that. Say it again."
    return (raw or "").strip()
