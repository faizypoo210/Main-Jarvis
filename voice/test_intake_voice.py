"""Unit tests for intake_voice parsing (no network, no FastAPI).

Run from repository root: ``python -m pytest voice/test_intake_voice.py -v``
"""

from __future__ import annotations

# Imports must work when the package is loaded like uvicorn: ``python -m uvicorn voice.server:app``
from voice.intake_voice import friendly_intake_failure, parse_intake_response


def test_parse_mission_created() -> None:
    data = {
        "interpretation": {"intent_type": "mission_request", "source_surface": "voice"},
        "reply": {
            "message": "Mission created, recorded, and dispatched.",
            "kind": "mission_created",
            "mission_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        },
        "outcome": "mission_created",
    }
    r = parse_intake_response(data)
    assert r.ok is True
    assert r.outcome == "mission_created"
    assert r.mission_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert "Mission created" in r.message
    assert r.reply_kind == "mission_created"


def test_parse_status_reply() -> None:
    data = {
        "interpretation": {"intent_type": "status_query"},
        "reply": {
            "message": "Recent missions (newest first):\n- …",
            "kind": "status_snapshot",
            "extras": {"mission_count": 2, "preview": [{"title": "A", "status": "open"}]},
        },
        "outcome": "status_reply",
    }
    r = parse_intake_response(data)
    assert r.outcome == "status_reply"
    assert r.reply_kind == "status_snapshot"
    assert r.mission_id is None
    assert r.extras == {"mission_count": 2, "preview": [{"title": "A", "status": "open"}]}


def test_parse_clarification() -> None:
    data = {
        "interpretation": {"intent_type": "governed_action_request"},
        "reply": {"message": "Governed actions use the mission integration routes…", "kind": "governed_action_hint"},
        "outcome": "governed_action_hint",
    }
    r = parse_intake_response(data)
    assert r.outcome == "governed_action_hint"
    assert r.mission_id is None


def test_parse_missing_reply_defaults() -> None:
    r = parse_intake_response({"outcome": "noop", "reply": {}})
    assert r.ok is True
    assert r.outcome == "noop"


def test_friendly_failure_includes_detail() -> None:
    s = friendly_intake_failure(401, "Unauthorized")
    assert "Unauthorized" in s
    assert "control plane" in s.lower()


def main() -> None:
    test_parse_mission_created()
    test_parse_status_reply()
    test_parse_clarification()
    test_parse_missing_reply_defaults()
    test_friendly_failure_includes_detail()
    print("intake_voice tests: ok")


if __name__ == "__main__":
    main()
