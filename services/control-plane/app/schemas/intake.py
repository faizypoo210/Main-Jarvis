"""Unified intake and interpretation contracts.

TRUTH_SOURCE: POST /api/v1/intake request/response; surfaces should prefer this over raw
POST /api/v1/commands when they need governed interpretation + a coherent reply bundle.

Parity: ``source_surface`` aligns with command surfaces where possible; ``quick_action`` maps
to ``command_center`` when delegating to :class:`app.schemas.commands.CommandCreate`.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

IntentType = Literal[
    "conversational_reply",
    "status_query",
    "mission_request",
    "approval_decision",
    "inbox_action",
    "governed_action_request",
    "mission_followup",
    "interrupt_or_cancel",
]

ReplyMode = Literal["silent", "brief", "rich", "clarify"]

IntakeOutcome = Literal[
    "mission_created",
    "approval_resolved",
    "inbox_updated",
    "status_reply",
    "conversational_reply",
    "governed_action_hint",
    "clarification",
    "interrupt",
    "noop",
]

ReplyKind = Literal[
    "mission_created",
    "approval_resolved",
    "inbox_updated",
    "status_snapshot",
    "conversational",
    "governed_action_hint",
    "clarification",
    "interrupt",
    "noop",
]

BehavioralLane = Literal[
    "chat",
    "fast_answer",
    "fast_research",
    "direct_tool",
    "mission",
    "approval",
    "deep_research",
    "automation",
]

ProgressPhase = Literal[
    "acknowledged",
    "routing_decided",
    "capability_check_started",
    "capability_missing",
    "tool_started",
    "source_checked",
    "partial_result",
    "approval_needed",
    "waiting_on_operator",
    "worker_stalled",
    "completed",
    "failed",
]


class IntentEnvelope(BaseModel):
    input_id: str
    surface: str
    raw_text: str
    intent_kind: Literal[
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
    ]
    freshness: Literal["none", "recent", "live_current", "continuous"]
    tool_required: bool
    external_action: bool
    identity_bearing: bool
    destructive: bool
    financial: bool
    hardware_physical: bool
    privacy_sensitive: bool
    duration: Literal["instant", "short", "long", "ongoing", "scheduled"]
    missing_info: list[str]
    suggested_lane: BehavioralLane
    confidence: float = Field(..., ge=0.0, le=1.0)


class DecisionEnvelope(BaseModel):
    input_id: str
    selected_lane: BehavioralLane
    approval_required: bool
    mission_required: bool
    capability_available: bool
    capability_notes: list[str]
    allowed_next_step: str
    blocked_actions: list[str]
    risk_class: Literal["green", "amber", "red"]
    requires_operator_input: bool
    missing_info: list[str]
    progress_policy: str


class ProgressEvent(BaseModel):
    input_id: str
    mission_id: UUID | None
    phase: ProgressPhase
    label: str
    detail: str | None
    timestamp: str


class InterpretationResult(BaseModel):
    """Structured interpretation of natural-language input (v1 deterministic rules)."""

    intent_type: IntentType
    mission_needed: bool = Field(
        ...,
        description="Whether this path should create or extend mission-scoped work.",
    )
    approval_candidate: bool = Field(
        ...,
        description="Heuristic: routed execution may require human approval (text + routing).",
    )
    governed_action_type: str | None = Field(
        None,
        description="When intent is governed_action_request: catalog action_kind if inferred.",
    )
    normalized_command: str = Field(
        ...,
        description="Text normalized for mission/command dispatch when applicable.",
    )
    reply_mode: ReplyMode = Field(
        ...,
        description="How the surface should present the reply bundle.",
    )
    target_mission_id: UUID | None = Field(
        None,
        description="Mission this utterance refers to, when known.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deterministic confidence score for v1 rules (not model entropy).",
    )
    clarification_needed: bool = False
    clarification_question: str | None = None
    source_surface: str = Field(..., description="Echo of the intake surface.")


class IntakeReplyBundle(BaseModel):
    """Single coherent control-plane response for any surface."""

    message: str
    kind: ReplyKind
    mission_id: UUID | None = None
    approval_id: UUID | None = None
    extras: dict[str, Any] | None = Field(
        None,
        description="Narrow structured hints (counts, mission preview, routing hints).",
    )
    display_text: str | None = None
    spoken_text: str | None = None
    activity_label: str | None = None
    show_working_indicator: bool = False
    terminal: bool = True
    intent_envelope: IntentEnvelope | None = None
    decision_envelope: DecisionEnvelope | None = None


class IntakeRequest(BaseModel):
    """Unified intake: raw text plus optional session and mission context."""

    source_surface: str = Field(
        ...,
        pattern="^(voice|command_center|sms|api|quick_action)$",
        description="Calling surface (quick_action: UI shortcuts — maps to command_center for missions).",
    )
    text: str = Field(..., min_length=1, max_length=32000)
    mission_id: UUID | None = Field(
        None,
        description="Optional active mission context (follow-up, status, cancel target).",
    )
    surface_session_id: UUID | None = None
    context: dict[str, Any] | None = None


class IntakeResponse(BaseModel):
    """Interpretation plus one reply bundle and the applied outcome."""

    interpretation: InterpretationResult
    reply: IntakeReplyBundle
    outcome: IntakeOutcome
