"""Deterministic natural-language interpretation for unified intake (v1).

Later: replace or augment ``interpret`` with a local router model; keep the
:class:`app.schemas.intake.InterpretationResult` contract stable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from app.schemas.intake import InterpretationResult

_JARVIS_ROOT = Path(__file__).resolve().parents[3]
if str(_JARVIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_JARVIS_ROOT))
from shared.routing import decide_route  # noqa: E402

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

# Short conversational — aligned with shared/routing heuristics intent.
_ACK_ONLY = re.compile(
    r"^(ok|okay|k|thanks|thank you|thx|ty|yes|yep|yeah|no|nope|ack|"
    r"got it|understood|cool|nice|hi|hello|hey|bye|goodbye)(\s*[!.]*)?$",
    re.IGNORECASE,
)

_INTERRUPT = re.compile(
    r"^(stop|cancel|abort|interrupt)\b",
    re.IGNORECASE,
)

_STATUS_QUERY = re.compile(
    r"\b(status|what'?s running|list missions|pending missions|how many missions|"
    r"mission list|overview)\b",
    re.IGNORECASE,
)

_APPROVE_VERB = re.compile(
    r"\b(approve|approved|approval yes)\b",
    re.IGNORECASE,
)
_DENY_VERB = re.compile(
    r"\b(deny|denied|deny it|reject|rejected|decline)\b",
    re.IGNORECASE,
)

_INBOX_LINE = re.compile(
    r"^(ack|acknowledge|dismiss|snooze)\s+(\S+)(?:\s+(\d+))?\s*$",
    re.IGNORECASE,
)

_GITHUB_GOVERNED = re.compile(
    r"\b(github|create issue|draft pr|pull request|merge pull request)\b",
    re.IGNORECASE,
)
_GMAIL_GOVERNED = re.compile(
    r"\b(gmail|create draft|send draft|reply draft)\b",
    re.IGNORECASE,
)

_FOLLOWUP_HINT = re.compile(
    r"\b(follow[\s-]?up|followup|continue|update on|same mission|regarding that)\b",
    re.IGNORECASE,
)


def _parse_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value).strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _extract_uuid_from_text(text: str) -> UUID | None:
    m = _UUID_RE.search(text or "")
    if not m:
        return None
    try:
        return UUID(m.group(0))
    except ValueError:
        return None


def _infer_governed_action(text: str) -> str | None:
    low = text.lower()
    if "merge" in low and "pull" in low:
        return "github_merge_pull_request"
    if "pull" in low or "pr" in low or "draft pr" in low:
        return "github_create_pull_request"
    if _GITHUB_GOVERNED.search(text):
        return "github_create_issue"
    if "send" in low and "draft" in low:
        return "gmail_send_draft"
    if "reply" in low and "draft" in low:
        return "gmail_create_reply_draft"
    if _GMAIL_GOVERNED.search(text):
        return "gmail_create_draft"
    return None


def interpret(
    *,
    text: str,
    source_surface: str,
    mission_id: UUID | None,
    context: dict[str, Any] | None,
) -> InterpretationResult:
    """Return structured interpretation using deterministic v1 rules."""
    ctx = dict(context) if context else {}
    raw = (text or "").strip()
    low = raw.lower()

    route = decide_route(text=raw, context=None, risk_class=ctx.get("risk_class"))
    approval_candidate = bool(route.approval_sensitive or route.requires_tools)

    base_kwargs: dict[str, Any] = {
        "source_surface": source_surface,
        "normalized_command": raw,
        "target_mission_id": mission_id,
        "approval_candidate": approval_candidate,
    }

    # --- 1. Interrupt / cancel ---
    if _INTERRUPT.match(raw.strip()):
        tgt = mission_id or _parse_uuid(ctx.get("cancel_mission_id"))
        return InterpretationResult(
            intent_type="interrupt_or_cancel",
            mission_needed=False,
            governed_action_type=None,
            reply_mode="brief",
            confidence=0.9,
            clarification_needed=False,
            clarification_question=None,
            **{**base_kwargs, "target_mission_id": tgt},
        )

    # --- 2. Approval decision (context or UUID + verb) ---
    aid = _parse_uuid(ctx.get("approval_id"))
    if aid is None:
        aid = _extract_uuid_from_text(raw)
    decision = ctx.get("decision")
    if isinstance(decision, str):
        decision = decision.strip().lower()
    wants_approve = bool(_APPROVE_VERB.search(raw)) or decision in ("approved", "approve", "yes")
    wants_deny = bool(_DENY_VERB.search(raw)) or decision in ("denied", "deny", "no", "reject")
    if (wants_approve or wants_deny) and aid is not None:
        return InterpretationResult(
            intent_type="approval_decision",
            mission_needed=False,
            governed_action_type=None,
            reply_mode="brief",
            confidence=0.92,
            clarification_needed=False,
            clarification_question=None,
            **base_kwargs,
        )
    if wants_approve or wants_deny:
        return InterpretationResult(
            intent_type="approval_decision",
            mission_needed=False,
            governed_action_type=None,
            reply_mode="clarify",
            confidence=0.55,
            clarification_needed=True,
            clarification_question=(
                "Which approval should be decided? Pass approval_id in context or include "
                "the approval UUID in the message."
            ),
            **base_kwargs,
        )

    # --- 3. Inbox triage ---
    inbox_key = ctx.get("inbox_item_key")
    inbox_action = (ctx.get("inbox_action") or "").strip().lower() if ctx.get("inbox_action") else None
    if inbox_key and inbox_action in ("acknowledge", "snooze", "dismiss"):
        return InterpretationResult(
            intent_type="inbox_action",
            mission_needed=False,
            governed_action_type=None,
            reply_mode="brief",
            confidence=0.93,
            clarification_needed=False,
            clarification_question=None,
            **base_kwargs,
        )
    m_inbox = _INBOX_LINE.match(raw.strip())
    if m_inbox:
        verb = m_inbox.group(1).lower()
        mapped = "acknowledge" if verb in ("ack", "acknowledge") else verb
        if mapped in ("acknowledge", "snooze", "dismiss"):
            return InterpretationResult(
                intent_type="inbox_action",
                mission_needed=False,
                governed_action_type=None,
                reply_mode="brief",
                confidence=0.88,
                clarification_needed=False,
                clarification_question=None,
                normalized_command=raw,
                source_surface=source_surface,
                target_mission_id=mission_id,
                approval_candidate=approval_candidate,
            )

    # --- 4. Status / list ---
    if _STATUS_QUERY.search(raw) or low in ("status", "missions", "list"):
        return InterpretationResult(
            intent_type="status_query",
            mission_needed=False,
            governed_action_type=None,
            reply_mode="rich",
            confidence=0.85,
            clarification_needed=False,
            clarification_question=None,
            **base_kwargs,
        )

    # --- 5. Governed integration intent (hint only in v1) ---
    gat = _infer_governed_action(raw)
    if gat:
        return InterpretationResult(
            intent_type="governed_action_request",
            mission_needed=False,
            governed_action_type=gat,
            reply_mode="rich",
            confidence=0.7,
            clarification_needed=True,
            clarification_question=(
                "Governed actions use the mission integration routes after a mission exists. "
                "Say what you want in plain language or open the action launcher in Command Center."
            ),
            **base_kwargs,
        )

    # --- 6. Mission follow-up when mission_id set ---
    if mission_id is not None and (
        _FOLLOWUP_HINT.search(raw) or ctx.get("mission_followup") is True
    ):
        return InterpretationResult(
            intent_type="mission_followup",
            mission_needed=True,
            governed_action_type=None,
            reply_mode="brief",
            confidence=0.82,
            clarification_needed=False,
            clarification_question=None,
            normalized_command=raw,
            source_surface=source_surface,
            target_mission_id=mission_id,
            approval_candidate=approval_candidate,
        )

    # --- 7. Pure conversational (short) ---
    if len(raw) <= 80 and _ACK_ONLY.match(raw.strip()):
        return InterpretationResult(
            intent_type="conversational_reply",
            mission_needed=False,
            governed_action_type=None,
            reply_mode="brief",
            confidence=0.8,
            clarification_needed=False,
            clarification_question=None,
            **base_kwargs,
        )

    # --- 8. Default: new mission work ---
    if mission_id is not None:
        # Context implies continuation without explicit follow-up keywords.
        return InterpretationResult(
            intent_type="mission_followup",
            mission_needed=True,
            governed_action_type=None,
            reply_mode="brief",
            confidence=0.72,
            clarification_needed=False,
            clarification_question=None,
            normalized_command=raw,
            source_surface=source_surface,
            target_mission_id=mission_id,
            approval_candidate=approval_candidate,
        )

    return InterpretationResult(
        intent_type="mission_request",
        mission_needed=True,
        governed_action_type=None,
        reply_mode="brief",
        confidence=0.75,
        clarification_needed=False,
        clarification_question=None,
        **base_kwargs,
    )


def map_surface_to_command_source(source_surface: str) -> str:
    """Map intake surface to :class:`app.schemas.commands.CommandCreate` ``source``."""
    if source_surface == "quick_action":
        return "command_center"
    return source_surface


def parse_inbox_triage(
    text: str, context: dict[str, Any] | None
) -> tuple[str, str, int | None] | None:
    """Resolve inbox action, item_key, and optional snooze minutes for execution."""
    ctx = dict(context) if context else {}
    key = ctx.get("inbox_item_key")
    act = ctx.get("inbox_action")
    if key and act:
        a = str(act).strip().lower()
        if a in ("acknowledge", "snooze", "dismiss"):
            mins: int | None = None
            if a == "snooze":
                raw_m = ctx.get("snooze_minutes")
                try:
                    mins = int(raw_m) if raw_m is not None else 60
                except (TypeError, ValueError):
                    mins = 60
            return (a, str(key), mins)

    m = _INBOX_LINE.match((text or "").strip())
    if not m:
        return None
    verb = m.group(1).lower()
    action = "acknowledge" if verb in ("ack", "acknowledge") else verb
    if action not in ("acknowledge", "snooze", "dismiss"):
        return None
    item_key = m.group(2)
    minutes: int | None = int(m.group(3)) if m.group(3) else None
    if action == "snooze" and minutes is None:
        minutes = 60
    return (action, item_key, minutes)


def resolve_approval_target(
    text: str, context: dict[str, Any] | None
) -> tuple[UUID | None, str | None]:
    """Return (approval_id, decision) with decision in approved|denied, or partial Nones."""
    ctx = dict(context) if context else {}
    aid = _parse_uuid(ctx.get("approval_id"))
    if aid is None:
        aid = _extract_uuid_from_text(text)
    raw = (text or "").strip()
    low = raw.lower()
    dctx = ctx.get("decision")
    if isinstance(dctx, str):
        dctx = dctx.strip().lower()
    wants_approve = bool(_APPROVE_VERB.search(raw)) or dctx in ("approved", "approve", "yes")
    wants_deny = bool(_DENY_VERB.search(raw)) or dctx in ("denied", "deny", "no", "reject")
    if wants_approve and not wants_deny:
        return (aid, "approved")
    if wants_deny and not wants_approve:
        return (aid, "denied")
    if wants_approve and wants_deny:
        return (aid, None)
    return (aid, None)
