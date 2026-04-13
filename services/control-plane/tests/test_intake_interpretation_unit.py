"""Deterministic intake interpretation (no database)."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.services.intake_interpretation import (
    interpret,
    map_surface_to_command_source,
    parse_inbox_triage,
    resolve_approval_target,
)

pytestmark = pytest.mark.unit


def test_interpret_status_query() -> None:
    r = interpret(text="what is the status of missions", source_surface="api", mission_id=None, context=None)
    assert r.intent_type == "status_query"
    assert r.mission_needed is False


def test_interpret_mission_request_default() -> None:
    r = interpret(
        text="Refactor the auth module for clarity and test coverage",
        source_surface="command_center",
        mission_id=None,
        context=None,
    )
    assert r.intent_type == "mission_request"
    assert r.mission_needed is True


def test_interpret_interrupt() -> None:
    r = interpret(text="cancel that", source_surface="voice", mission_id=None, context=None)
    assert r.intent_type == "interrupt_or_cancel"


def test_interpret_conversational_short() -> None:
    r = interpret(text="thanks", source_surface="api", mission_id=None, context=None)
    assert r.intent_type == "conversational_reply"


def test_interpret_followup_with_mission_id() -> None:
    mid = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    r = interpret(
        text="Follow up on the deploy",
        source_surface="api",
        mission_id=mid,
        context=None,
    )
    assert r.intent_type == "mission_followup"
    assert r.target_mission_id == mid


def test_interpret_governed_github_hint() -> None:
    r = interpret(
        text="create a GitHub issue for the bug",
        source_surface="command_center",
        mission_id=None,
        context=None,
    )
    assert r.intent_type == "governed_action_request"
    assert r.governed_action_type == "github_create_issue"


def test_map_quick_action() -> None:
    assert map_surface_to_command_source("quick_action") == "command_center"
    assert map_surface_to_command_source("api") == "api"


def test_parse_inbox_from_context() -> None:
    t = parse_inbox_triage(
        "noise",
        {"inbox_item_key": "approval:abc", "inbox_action": "dismiss"},
    )
    assert t == ("dismiss", "approval:abc", None)


def test_parse_inbox_from_text() -> None:
    t = parse_inbox_triage("acknowledge hello:key", None)
    assert t is not None
    assert t[0] == "acknowledge"
    assert t[1] == "hello:key"


def test_resolve_approval_target() -> None:
    aid = UUID("11111111-2222-3333-4444-555555555555")
    a, d = resolve_approval_target(
        f"approve {aid}",
        None,
    )
    assert a == aid
    assert d == "approved"
