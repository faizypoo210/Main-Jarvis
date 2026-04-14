"""Voice-safe spoken text vs full display text (surface rendering only; control plane remains truth source)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Hard cap for subprocess TTS input — avoids oversized synthesis requests.
MAX_SPOKEN_CHARS = 900


@dataclass(frozen=True)
class VoiceReplyShape:
    """Full transcript for UI vs condensed line(s) for TTS."""

    display_text: str
    spoken_text: str


def truncate_hard(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    if max_chars <= 1:
        return "…"
    return t[: max_chars - 1].rstrip() + "…"


def _truncate_sentences(text: str, max_chars: int) -> str:
    """Prefer whole sentences; then hard truncate."""
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    # First sentence if reasonably short
    parts = re.split(r"(?<=[.!?])\s+", t, maxsplit=1)
    first = parts[0].strip()
    if first and len(first) <= max_chars and len(first) < len(t):
        return first
    return truncate_hard(t, max_chars)


def generic_voice_spoken(display: str, *, kind: str) -> str:
    """Non-intake replies (inbox, briefing, …): cap length; no semantic rewrite."""
    _ = kind
    d = (display or "").strip()
    if not d:
        return ""
    if len(d) <= MAX_SPOKEN_CHARS:
        return d
    return truncate_hard(d, MAX_SPOKEN_CHARS)


def shape_intake_voice_reply(
    *,
    message: str,
    reply_kind: str | None,
    outcome: str | None,
    extras: dict[str, Any] | None,
) -> VoiceReplyShape:
    """
    Derive full ``display_text`` (transcript) and shorter ``spoken_text`` (TTS only).

    ``extras`` mirrors ``reply.extras`` from the control plane (e.g. mission_count, preview).
    """
    _ = outcome
    display = (message or "").strip()
    if not display:
        display = "Done."
    kind = (reply_kind or "").strip() or "conversational"
    ex = extras if isinstance(extras, dict) else {}

    spoken = _spoken_for_intake_kind(kind, display, ex)
    spoken = truncate_hard(spoken, MAX_SPOKEN_CHARS)
    if not spoken.strip():
        spoken = truncate_hard(display, min(240, MAX_SPOKEN_CHARS))
    return VoiceReplyShape(display_text=display, spoken_text=spoken)


def _spoken_for_intake_kind(kind: str, display: str, extras: dict[str, Any]) -> str:
    if kind == "mission_created":
        if len(display) <= 200:
            return display
        return _truncate_sentences(display, 200) or "Mission created and recorded."

    if kind == "status_snapshot":
        return _spoken_status_snapshot(display, extras)

    if kind == "governed_action_hint":
        gat = extras.get("governed_action_type")
        if gat:
            return (
                f"Governed action hint: {gat}. "
                "Create a mission for the work first, then use the operator action catalog."
            )
        return _truncate_sentences(display, 420)

    if kind == "clarification":
        return _truncate_sentences(display, 480)

    if kind in ("conversational", "interrupt", "noop", "approval_resolved", "inbox_updated"):
        if len(display) <= MAX_SPOKEN_CHARS:
            return display
        return truncate_hard(display, MAX_SPOKEN_CHARS)

    # Unknown / future kinds — never send desktop-length strings to TTS
    if len(display) <= MAX_SPOKEN_CHARS:
        return display
    return truncate_hard(display, MAX_SPOKEN_CHARS)


def _spoken_status_snapshot(display: str, extras: dict[str, Any]) -> str:
    n_raw = extras.get("mission_count")
    try:
        n = int(n_raw) if n_raw is not None else 0
    except (TypeError, ValueError):
        n = 0
    preview = extras.get("preview")
    parts: list[str] = []

    if n == 0:
        parts.append("No missions are on file yet.")
    elif n == 1:
        parts.append("You have one recent mission.")
    else:
        parts.append(f"You have {n} recent missions.")

    if isinstance(preview, list) and preview:
        for i, item in enumerate(preview[:3]):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            st = str(item.get("status") or "").strip()
            if not title:
                continue
            title = title[:100]
            if st:
                parts.append(f"Mission {i + 1}: {title}, status {st}.")
            else:
                parts.append(f"Mission {i + 1}: {title}.")

    if len(parts) == 1 and n > 0 and not (isinstance(preview, list) and preview):
        # Count only, no preview titles (unexpected) — still voice-safe
        return parts[0]

    return " ".join(parts)
