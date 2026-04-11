"""Shared human labels for governed approval actions — mirrors governed_action_catalog titles."""

from __future__ import annotations

from app.services.governed_action_catalog import governed_entries_by_approval_action_type

_PREFIX = "Create approval request — "


def compact_title_from_catalog_title(title: str) -> str:
    t = (title or "").strip()
    if t.startswith(_PREFIX):
        return t[len(_PREFIX) :].strip()
    return t or "Action"


def compact_label_for_approval_action_type(action_type: str | None) -> str:
    at = (action_type or "").strip()
    if not at:
        return "Action"
    m = governed_entries_by_approval_action_type()
    entry = m.get(at)
    if entry:
        return compact_title_from_catalog_title(entry.title)
    return at


def humanize_requested_via(v: str | None) -> str:
    s = (v or "").strip().lower()
    if s == "voice":
        return "Voice"
    if s == "command_center":
        return "Command Center"
    if s == "system":
        return "System"
    if s == "sms":
        return "SMS"
    return (v or "").strip() or "unknown"
