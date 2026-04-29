"""Explicit lane routing (v1) — deterministic heuristics, no extra models.

TRUTH: Mission execution via ``jarvis.execution`` is always handled by the executor
(OpenClaw). There is no separate local-fast mission worker in this repo; when the
classifier prefers ``local_fast``, ``actual_lane`` remains ``gateway`` and
``fallback_applied`` is true with a stable ``reason_code``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Mirrors ``BehavioralLane`` in control-plane intake schemas (shared stays app-free).
_VALID_BEHAVIORAL_LANES = frozenset(
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

# Prefer gateway when these appear (case-insensitive word boundaries).
_GATEWAY_HINTS = re.compile(
    r"\b("
    r"tool|tools|mcp|search|browse|http|https|curl|api|sql|database|file|files|"
    r"write|edit|deploy|run|execute|script|shell|terminal|code|github|git\b|"
    r"branch|commit|merge|pr\b|pull|research|investigate|analyze|analysis|"
    r"plan|steps|step|multi|workflow|mission|task|approve|approval|"
    r"production|infra|kubernetes|docker|aws|azure|gcp"
    r")\b",
    re.IGNORECASE,
)

# Short conversational / status — still gateway if risky.
_ACK_ONLY = re.compile(
    r"^(ok|okay|k|thanks|thank you|thx|ty|yes|yep|yeah|no|nope|ack|"
    r"got it|understood|cool|nice|hi|hello|hey|bye|goodbye)(\s*[!.]*)?$",
    re.IGNORECASE,
)

_SENSITIVE_HINTS = re.compile(
    r"\b("
    r"delete|remove|drop|wipe|password|secret|credential|token|payment|wire|"
    r"transfer|sudo|root\b|production|prod\b|customer data|pii\b"
    r")\b",
    re.IGNORECASE,
)


def _norm_risk(risk_class: str | None) -> str:
    """Map guard risk to a band; missing → green so unknown risk is not treated as elevated."""
    if not risk_class:
        return "green"
    r = str(risk_class).strip().lower()
    if r in ("green", "amber", "red"):
        return r
    return "green"


@dataclass(frozen=True)
class RoutingDecision:
    requested_lane: str  # "local_fast" | "gateway"
    actual_lane: str  # "local_fast" | "gateway" — mission executor path is always gateway today
    fallback_applied: bool
    reason_code: str
    reason_summary: str
    requires_tools: bool
    requires_long_running_execution: bool
    approval_sensitive: bool

    def to_execution_dict(self) -> dict[str, Any]:
        """Compact JSON-safe dict for Redis execution payload and receipts."""
        return {
            "requested_lane": self.requested_lane,
            "actual_lane": self.actual_lane,
            "fallback_applied": self.fallback_applied,
            "reason_code": self.reason_code,
            "fallback_reason_code": (self.reason_code if self.fallback_applied else None),
            "reason_summary": self.reason_summary,
            "requires_tools": self.requires_tools,
            "requires_long_running_execution": self.requires_long_running_execution,
            "approval_sensitive": self.approval_sensitive,
        }

    def to_mission_event_payload(self, *, pending_approval: bool = False) -> dict[str, Any]:
        """Compact mission truth for ``routing_decided`` events."""
        out: dict[str, Any] = {
            "requested_lane": self.requested_lane,
            "actual_lane": self.actual_lane,
            "fallback_applied": self.fallback_applied,
            "reason_code": self.reason_code,
            "fallback_reason_code": (self.reason_code if self.fallback_applied else None),
            "reason_summary": self.reason_summary,
            "requires_tools": self.requires_tools,
            "requires_long_running_execution": self.requires_long_running_execution,
            "approval_sensitive": self.approval_sensitive,
        }
        if pending_approval:
            out["pending_approval"] = True
        return out


def _text_signals(text: str) -> tuple[bool, bool, bool]:
    """requires_tools, requires_long_running, sensitive_text."""
    t = (text or "").strip()
    low = t.lower()
    requires_tools = bool(_GATEWAY_HINTS.search(t)) or bool(_SENSITIVE_HINTS.search(t))
    requires_long = len(t) > 1200 or "step-by-step" in low or "multi-step" in low
    sensitive = bool(_SENSITIVE_HINTS.search(t))
    return requires_tools, requires_long, sensitive


def decide_route(
    *,
    text: str,
    context: dict[str, Any] | None,
    risk_class: str | None,
) -> RoutingDecision:
    """Classify intended lane and honest actual lane for mission execution."""
    lane_hint: str | None = None
    if context:
        raw_lane = context.get("suggested_behavioral_lane")
        if isinstance(raw_lane, str):
            s = raw_lane.strip()
            if s in _VALID_BEHAVIORAL_LANES:
                lane_hint = s

    rc = _norm_risk(risk_class)
    approval_sensitive = rc in ("red", "amber")

    t0 = (text or "").strip()
    if not t0:
        return RoutingDecision(
            requested_lane="gateway",
            actual_lane="gateway",
            fallback_applied=False,
            reason_code="HEURISTIC_EMPTY_COMMAND",
            reason_summary="Empty command; gateway execution path.",
            requires_tools=False,
            requires_long_running_execution=False,
            approval_sensitive=approval_sensitive,
        )

    requires_tools, requires_long, sensitive_text = _text_signals(text)
    if sensitive_text:
        approval_sensitive = True

    if lane_hint in (
        "fast_research",
        "deep_research",
        "direct_tool",
        "mission",
        "automation",
    ):
        requires_tools = True
    if lane_hint == "approval":
        approval_sensitive = True

    t = t0
    short = len(t) <= 120
    looks_like_ack_only = bool(_ACK_ONLY.match(t.strip())) and len(t) <= 80

    prefer_local = (
        not approval_sensitive
        and not requires_tools
        and not requires_long
        and short
        and (looks_like_ack_only or (len(t) <= 40 and not _GATEWAY_HINTS.search(t)))
    )

    if prefer_local:
        requested = "local_fast"
        reason_code = "HEURISTIC_CONVERSATIONAL_SHORT"
        reason_summary = (
            "Short conversational or status-style text; preferred lane is local-fast."
        )
    else:
        requested = "gateway"
        if requires_long:
            reason_code = "HEURISTIC_LONG_OR_MULTISTEP"
            reason_summary = "Long or multi-step style work; gateway execution path."
        elif requires_tools or _GATEWAY_HINTS.search(t):
            reason_code = "HEURISTIC_TOOLS_OR_ACTION"
            reason_summary = "Tool, research, or action-style command; gateway execution path."
        elif approval_sensitive:
            reason_code = "HEURISTIC_APPROVAL_SENSITIVE"
            reason_summary = "Risk-elevated or sensitive phrasing; gateway execution path."
        else:
            reason_code = "HEURISTIC_DEFAULT_GATEWAY"
            reason_summary = "Default gateway execution path for mission work."

    # Mission executor is OpenClaw-only; honest actual lane for streamed execution.
    actual = "gateway"
    fallback = requested == "local_fast"
    if fallback:
        reason_code = "MISSION_EXECUTOR_GATEWAY_ONLY"
        reason_summary = (
            "Mission execution uses the OpenClaw executor only; local-fast is not wired "
            "for this path, so actual lane is gateway."
        )

    return RoutingDecision(
        requested_lane=requested,
        actual_lane=actual,
        fallback_applied=fallback,
        reason_code=reason_code,
        reason_summary=reason_summary,
        requires_tools=requires_tools,
        requires_long_running_execution=requires_long,
        approval_sensitive=approval_sensitive,
    )
