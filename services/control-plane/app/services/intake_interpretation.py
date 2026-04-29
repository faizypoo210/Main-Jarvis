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

from app.schemas.intake import BehavioralLane, IntentEnvelope, InterpretationResult

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

# Operator / situational awareness — prefer these over mission_request.
_STATUS_QUERY = re.compile(
    r"(?i)"
    r"\b(?:"
    r"what\s+is\s+going\s+on|what'?s\s+going\s+on|what\s+is\s+happening|what'?s\s+happening|"
    r"what'?s\s+up(?:\s+right\s+now)?|"
    r"what\s+is\s+up|"
    r"any\s+(?:approvals?\s+pending|pending\s+approvals?)|"
    r"what\s+needs\s+my\s+attention|needs\s+my\s+attention|"
    r"status|what'?s\s+running|list\s+missions|pending\s+missions|how\s+many\s+missions|"
    r"mission\s+list|overview|operator\s+overview|state\s+of\s+(?:things|the\s+system)|"
    r"what\s+is\s+the\s+status|what'?s\s+the\s+status"
    r")\b",
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


def _infer_explicit_governed_action(text: str) -> str | None:
    """Match only explicit governed *write* intents (create/open/merge/send drafts).

    Read-only or investigative phrasing (check issues, summarize PRs, list inbox) must not
    match — those stay ``mission_request`` or ``status_query``.
    """
    low = (text or "").lower()
    # GitHub — merge
    if re.search(r"\bmerge\s+(that|the|a)\s+(pull\s+request|pr)\b", low):
        return "github_merge_pull_request"
    # GitHub — open draft PR / PR
    if re.search(
        r"\bopen\s+(a|an)\s+(?:draft\s+)?(?:pull\s+request|pr)\b",
        low,
    ):
        return "github_create_pull_request"
    # GitHub — create issue (explicit product words or “issue for …”)
    if re.search(r"\bcreate\s+(a|an)\s+github\s+issue\b", low):
        return "github_create_issue"
    if re.search(r"\bcreate\s+(a|an)\s+issue\s+for\b", low):
        return "github_create_issue"
    # Gmail — send existing draft
    if re.search(r"\bsend\s+(that|the)\s+draft\b", low):
        return "gmail_send_draft"
    # Gmail — reply draft
    if re.search(r"\bcreate\s+(a|an)\s+reply\s+draft\b", low):
        return "gmail_create_reply_draft"
    # Gmail — new draft (explicit gmail or “email draft”)
    if re.search(r"\bcreate\s+(a|an)\s+gmail\s+draft\b", low):
        return "gmail_create_draft"
    if re.search(r"\bcreate\s+(a|an)\s+(?:new\s+)?email\s+draft\b", low):
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

    # --- 4. Status / operator awareness ---
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

    # --- 5. Governed write intent (explicit only; hint path in v1) ---
    gat = _infer_explicit_governed_action(raw)
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


def derive_activity_label(intent_type: str, raw_text: str) -> str:
    """Derive a short present-tense working label from intent + raw text.
    Max 48 chars. No trailing period. First word capitalised only."""
    if intent_type == "status_query":
        return "Reviewing operator status"
    if intent_type == "approval_decision":
        return "Processing approval decision"
    if intent_type == "inbox_action":
        return "Updating inbox item"
    if intent_type == "interrupt_or_cancel":
        return "Cancelling active task"
    if intent_type == "governed_action_request":
        return "Preparing governed action"
    if intent_type == "mission_followup":
        return "Checking mission status"
    # mission_request or conversational_reply — derive from first meaningful words
    stop = {"please", "can", "you", "i", "the", "a", "an", "my", "me", "could", "would"}
    words = [w for w in raw_text.strip().lower().split() if w not in stop]
    label = " ".join(words[:4]).capitalize()
    return label[:48] if label else "Working on request"


def _derive_envelope_from_interp(
    interp: InterpretationResult,
    raw_text: str,
    source_surface: str,
) -> IntentEnvelope:
    """Build IntentEnvelope deterministically from existing InterpretationResult.

    Used as fallback when Qwen classification fails or times out.
    """
    import uuid

    it = interp.intent_type
    lane_map: dict[str, BehavioralLane] = {
        "conversational_reply": "chat",
        "status_query": "fast_answer",
        "inbox_action": "fast_answer",
        "interrupt_or_cancel": "fast_answer",
        "approval_decision": "approval",
        "governed_action_request": "approval",
        "mission_followup": "fast_answer",
        "mission_request": "mission",
    }
    # Promote to fast_research if text has freshness signals and no identity/action risk
    freshness_hints = re.compile(
        r"\b(today|right now|current|latest|live|now|this week|score|scores|news|price|prices)\b",
        re.IGNORECASE,
    )
    sensitive_hints = re.compile(
        r"\b(send|submit|apply|post|delete|buy|sell|trade|flash|deploy|email)\b",
        re.IGNORECASE,
    )
    suggested: BehavioralLane = lane_map.get(it, "mission")
    if (
        suggested == "mission"
        and freshness_hints.search(raw_text)
        and not sensitive_hints.search(raw_text)
    ):
        suggested = "fast_research"
    return IntentEnvelope(
        input_id=str(uuid.uuid4()),
        surface=source_surface,
        raw_text=raw_text,
        intent_kind=(
            "chat"
            if it == "conversational_reply"
            else (
                "research"
                if suggested in ("fast_research", "deep_research")
                else (
                    "execute"
                    if suggested == "direct_tool"
                    else "approve" if suggested == "approval" else "monitor"
                )
            )
        ),
        freshness="live_current" if suggested == "fast_research" else "none",
        tool_required=suggested not in ("chat", "fast_answer"),
        external_action=it in ("governed_action_request",),
        identity_bearing=it in ("approval_decision", "governed_action_request"),
        destructive=False,
        financial=False,
        hardware_physical=False,
        privacy_sensitive=False,
        duration=(
            "instant"
            if suggested in ("chat", "fast_answer", "fast_research")
            else (
                "long"
                if suggested in ("deep_research", "automation")
                else "short"
            )
        ),
        missing_info=(
            [interp.clarification_question]
            if interp.clarification_needed and interp.clarification_question
            else []
        ),
        suggested_lane=suggested,
        confidence=interp.confidence,
    )


async def classify_intent_envelope(
    raw_text: str,
    source_surface: str,
    interp: InterpretationResult,
) -> IntentEnvelope:
    """Call Qwen to classify request properties into an IntentEnvelope.

    Timeout 6s. Falls back to :func:`_derive_envelope_from_interp` on any failure.
    """
    import json
    import os
    import uuid

    import httpx

    base = os.environ.get("OLLAMA_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("JARVIS_LOCAL_MODEL", "").strip()
    if not base or not model:
        return _derive_envelope_from_interp(interp, raw_text, source_surface)

    safe_request = json.dumps(raw_text, ensure_ascii=False)
    prompt = f"""Classify this operator request and return ONLY a valid JSON object with no extra text or markdown.

Request: {safe_request}

Return exactly these keys (fill values appropriately):
- "intent_kind": one of research, chat, execute, monitor, automate, configure, approve, debug, create, edit
- "freshness": one of none, recent, live_current, continuous
- "tool_required": boolean
- "external_action": boolean
- "identity_bearing": boolean
- "destructive": boolean
- "financial": boolean
- "hardware_physical": boolean
- "privacy_sensitive": boolean
- "duration": one of instant, short, long, ongoing, scheduled
- "missing_info": JSON array of strings (use [] if none)
- "suggested_lane": one of chat, fast_answer, fast_research, direct_tool, mission, approval, deep_research, automation
- "confidence": number between 0 and 1

Rules: Use suggested_lane fast_research for live scores/news/prices/today-style lookups without account actions. Use mission for multi-step work. Use approval when the operator is approving/denying something sensitive or sending/submitting on their behalf. Set identity_bearing true for job applications, banking, email send, or anything needing the operator's identity."""

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.post(
                f"{base}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                },
            )
            r.raise_for_status()
            body = r.json()
            raw_out = (body.get("response") or "").strip()
            s = raw_out
            if s.startswith("```"):
                lines = s.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                s = "\n".join(lines).strip()
            start = s.find("{")
            end = s.rfind("}")
            parsed: dict[str, Any] | None = None
            if start >= 0 and end > start:
                try:
                    cand = json.loads(s[start : end + 1])
                    if isinstance(cand, dict):
                        parsed = cand
                except json.JSONDecodeError as e:
                    _ = e
                    parsed = None
            if not parsed:
                return _derive_envelope_from_interp(interp, raw_text, source_surface)

            lanes: frozenset[str] = frozenset(
                {
                    "chat",
                    "fast_answer",
                    "fast_research",
                    "direct_tool",
                    "mission",
                    "approval",
                    "deep_research",
                    "automation",
                }
            )
            kinds: frozenset[str] = frozenset(
                {
                    "research",
                    "chat",
                    "execute",
                    "monitor",
                    "automate",
                    "configure",
                    "approve",
                    "debug",
                    "create",
                    "edit",
                }
            )
            fresh_vals: frozenset[str] = frozenset(
                {"none", "recent", "live_current", "continuous"}
            )
            dur_vals: frozenset[str] = frozenset(
                {"instant", "short", "long", "ongoing", "scheduled"}
            )

            sl = parsed.get("suggested_lane")
            if not isinstance(sl, str) or sl.strip() not in lanes:
                return _derive_envelope_from_interp(interp, raw_text, source_surface)
            suggested_lane: BehavioralLane = sl.strip()  # type: ignore[assignment]

            ik = parsed.get("intent_kind")
            if not isinstance(ik, str) or ik.strip() not in kinds:
                return _derive_envelope_from_interp(interp, raw_text, source_surface)
            intent_kind = ik.strip()  # type: ignore[assignment]

            fr = parsed.get("freshness")
            if not isinstance(fr, str) or fr.strip() not in fresh_vals:
                fr = "live_current" if suggested_lane == "fast_research" else "none"
            freshness = fr.strip()  # type: ignore[assignment]

            dur = parsed.get("duration")
            if not isinstance(dur, str) or dur.strip() not in dur_vals:
                dur = (
                    "instant"
                    if suggested_lane in ("chat", "fast_answer", "fast_research")
                    else "short"
                )
            duration = dur.strip()  # type: ignore[assignment]

            def _bool(key: str, default: bool = False) -> bool:
                v = parsed.get(key)
                if isinstance(v, bool):
                    return v
                return default

            mi = parsed.get("missing_info")
            missing_info: list[str] = []
            if isinstance(mi, list):
                missing_info = [str(x) for x in mi if x is not None]

            cf = parsed.get("confidence")
            try:
                conf = float(cf) if cf is not None else float(interp.confidence)
            except (TypeError, ValueError) as e:
                _ = e
                conf = float(interp.confidence)
            conf = max(0.0, min(1.0, conf))

            merged: dict[str, Any] = {
                "input_id": str(uuid.uuid4()),
                "surface": source_surface,
                "raw_text": raw_text,
                "intent_kind": intent_kind,
                "freshness": freshness,
                "tool_required": _bool("tool_required"),
                "external_action": _bool("external_action"),
                "identity_bearing": _bool("identity_bearing"),
                "destructive": _bool("destructive"),
                "financial": _bool("financial"),
                "hardware_physical": _bool("hardware_physical"),
                "privacy_sensitive": _bool("privacy_sensitive"),
                "duration": duration,
                "missing_info": missing_info,
                "suggested_lane": suggested_lane,
                "confidence": conf,
            }
            return IntentEnvelope.model_validate(merged)
    except Exception as e:
        _ = e
        return _derive_envelope_from_interp(interp, raw_text, source_surface)


def routing_context_for_decide_route(envelope: IntentEnvelope) -> dict[str, Any]:
    """Return a ``context`` fragment for :func:`shared.routing.decide_route`.

    Merges behavioral lane hints without changing execution lane string values.
    """
    return {"suggested_behavioral_lane": envelope.suggested_lane}
