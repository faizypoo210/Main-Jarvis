"""Voice reply shaping: display vs spoken (no server, no TTS)."""

from __future__ import annotations

from voice.spoken_render import (
    MAX_SPOKEN_CHARS,
    VoiceReplyShape,
    generic_voice_spoken,
    shape_intake_voice_reply,
    truncate_hard,
)


def test_status_snapshot_preserves_full_display() -> None:
    long_lines = "\n".join(f"- id-{i}: running — title {i}" for i in range(12))
    display = f"Recent missions (newest first):\n{long_lines}"
    extras = {
        "mission_count": 12,
        "preview": [
            {"id": "a", "status": "running", "title": "Fix voice"},
            {"id": "b", "status": "queued", "title": "Docs"},
            {"id": "c", "status": "done", "title": "CI"},
        ],
    }
    s = shape_intake_voice_reply(
        message=display,
        reply_kind="status_snapshot",
        outcome="status_reply",
        extras=extras,
    )
    assert isinstance(s, VoiceReplyShape)
    assert s.display_text == display
    assert len(s.spoken_text) < len(display)
    assert "12" in s.spoken_text
    assert "Fix voice" in s.spoken_text


def test_status_snapshot_spoken_is_concise_without_verbatim_list() -> None:
    display = "Recent missions (newest first):\n- " + "x" * 400
    s = shape_intake_voice_reply(
        message=display,
        reply_kind="status_snapshot",
        outcome="status_reply",
        extras={"mission_count": 3, "preview": [{"title": "Only", "status": "open"}]},
    )
    assert "Recent missions" not in s.spoken_text
    assert len(s.spoken_text) <= MAX_SPOKEN_CHARS


def test_mission_created_stays_short_when_message_short() -> None:
    m = "Mission created, recorded, and dispatched."
    s = shape_intake_voice_reply(
        message=m,
        reply_kind="mission_created",
        outcome="mission_created",
        extras={"mission_status": "queued"},
    )
    assert s.display_text == m
    assert s.spoken_text == m


def test_mission_created_condenses_very_long_message() -> None:
    long = "x" * 500
    s = shape_intake_voice_reply(
        message=long,
        reply_kind="mission_created",
        outcome="mission_created",
        extras=None,
    )
    assert s.display_text == long
    assert len(s.spoken_text) < len(long)
    assert len(s.spoken_text) <= 220


def test_unknown_kind_truncates_long_display() -> None:
    long = "y" * 5000
    s = shape_intake_voice_reply(
        message=long,
        reply_kind="future_kind",
        outcome="noop",
        extras=None,
    )
    assert s.display_text == long
    assert len(s.spoken_text) <= MAX_SPOKEN_CHARS


def test_generic_voice_spoken_caps_plain_handlers() -> None:
    long = "z" * 3000
    out = generic_voice_spoken(long, kind="briefing")
    assert len(out) <= MAX_SPOKEN_CHARS


def test_truncate_hard_ellipsis() -> None:
    assert truncate_hard("abcdef", 4) == "abc…"
