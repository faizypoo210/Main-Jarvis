"""Orchestrate unified intake: interpretation plus existing control-plane flows."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.mission_repo import MissionRepository
from app.repositories.operator_inbox_state_repo import OperatorInboxStateRepository
from app.schemas.commands import CommandCreate
from app.schemas.intake import (
    IntakeOutcome,
    IntakeReplyBundle,
    IntakeRequest,
    IntakeResponse,
)
from app.services.approval_service import ApprovalService
from app.services.command_service import CommandService
from app.services.intake_interpretation import (
    interpret,
    map_surface_to_command_source,
    parse_inbox_triage,
    resolve_approval_target,
)


async def _generate_ack(
    raw_text: str,
    intent_type: str,
    activity_label: str,
) -> tuple[str, str]:
    """Call Ollama for a task-aware ack. Returns (display_text, spoken_text).
    Timeout 4s. Any failure returns a safe structured fallback — never raises."""
    import os
    import httpx

    base = os.environ.get("OLLAMA_BASE_URL", "").strip().rstrip("/")
    if not base:
        fallback = f"On it, sir — {activity_label.lower()}."
        return fallback, fallback
    model = os.environ.get("JARVIS_LOCAL_MODEL", "").strip()
    if not model:
        fallback = f"On it, sir — {activity_label.lower()}."
        return fallback, fallback
    prompt = (
        f'You are JARVIS, a governed executive AI assistant. '
        f'The operator said: "{raw_text}". '
        f'Write exactly one acknowledgement sentence, max 12 words, specific to this request. '
        f'Address the operator as "sir". Reply with the sentence only. No quotes.'
    )
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.post(
                f"{base}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "think": False},
            )
            r.raise_for_status()
            display = r.json().get("response", "").strip().strip('"')
            if not display:
                raise ValueError("empty")
            spoken = display.split(".")[0].strip() + "."
            return display, spoken
    except Exception as e:
        fallback = f"On it, sir — {activity_label.lower()}."
        return fallback, fallback


def _decide_lane(
    envelope: "IntentEnvelope",
    interp: "InterpretationResult",
) -> "DecisionEnvelope":
    from app.schemas.intake import DecisionEnvelope

    suggested = envelope.suggested_lane
    notes: list[str] = []

    if envelope.destructive or envelope.financial or envelope.hardware_physical:
        selected = "approval"
        notes.append("Hard override: destructive/financial/hardware requires approval")
    elif envelope.identity_bearing and envelope.external_action:
        selected = "approval"
        notes.append("Hard override: identity-bearing external action requires approval")
    elif interp.intent_type == "interrupt_or_cancel":
        selected = "fast_answer"
        notes.append("Interrupt always fast_answer")
    elif interp.intent_type in ("status_query", "inbox_action"):
        selected = "fast_answer"
        notes.append("Status/inbox always fast_answer")
    elif interp.intent_type == "approval_decision":
        selected = "approval"
        notes.append("Explicit approval decision")
    else:
        selected = suggested

    approval_required = selected == "approval"
    mission_required = selected in ("mission", "deep_research", "automation")

    return DecisionEnvelope(
        input_id=envelope.input_id,
        selected_lane=selected,
        approval_required=approval_required,
        mission_required=mission_required,
        capability_available=True,
        capability_notes=notes,
        allowed_next_step=f"run_{selected}",
        blocked_actions=[],
        risk_class="red" if approval_required else "amber" if mission_required else "green",
        requires_operator_input=interp.clarification_needed,
        missing_info=envelope.missing_info,
        progress_policy=(
            "show_working_indicator_and_update_if_slow" if mission_required else
            "show_working_indicator" if selected == "fast_research" else
            "none"
        ),
    )


def _decided_via_for_surface(source_surface: str) -> str:
    if source_surface == "sms":
        return "sms"
    if source_surface == "voice":
        return "voice"
    if source_surface in ("command_center", "quick_action"):
        return "command_center"
    return "system"


class IntakeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._missions = MissionRepository(session)
        self._commands = CommandService(session)
        self._approvals = ApprovalService(session)

    async def process(self, body: IntakeRequest) -> IntakeResponse:
        ctx = dict(body.context) if body.context else {}
        interp = interpret(
            text=body.text,
            source_surface=body.source_surface,
            mission_id=body.mission_id,
            context=body.context,
        )

        from app.services.intake_interpretation import derive_activity_label

        activity_label = derive_activity_label(interp.intent_type, body.text)
        display_text, spoken_text = await _generate_ack(body.text, interp.intent_type, activity_label)

        from app.services.intake_interpretation import (
            classify_intent_envelope,
            routing_context_for_decide_route,
        )

        intent_envelope = await classify_intent_envelope(body.text, body.source_surface, interp)
        decision_envelope = _decide_lane(intent_envelope, interp)

        show_indicator = interp.intent_type not in (
            "conversational_reply", "status_query", "inbox_action", "interrupt_or_cancel"
        )

        it = interp.intent_type

        if it == "interrupt_or_cancel":
            msg = "Interrupt noted."
            mid = interp.target_mission_id
            if mid:
                msg = f"Interrupt noted for mission context {mid}."
            return IntakeResponse(
                interpretation=interp,
                reply=IntakeReplyBundle(
                    message=msg,
                    kind="interrupt",
                    mission_id=mid,
                    extras={"target_mission_id": str(mid)} if mid else None,
                    display_text=display_text,
                    spoken_text=spoken_text,
                    activity_label=activity_label,
                    show_working_indicator=show_indicator,
                    intent_envelope=intent_envelope,
                    decision_envelope=decision_envelope,
                    terminal=True,
                ),
                outcome="interrupt",
            )

        if it == "approval_decision":
            if interp.clarification_needed:
                return IntakeResponse(
                    interpretation=interp,
                    reply=IntakeReplyBundle(
                        message=interp.clarification_question or "More detail needed.",
                        kind="clarification",
                        extras=None,
                        display_text=display_text,
                        spoken_text=spoken_text,
                        activity_label=activity_label,
                        show_working_indicator=show_indicator,
                        intent_envelope=intent_envelope,
                        decision_envelope=decision_envelope,
                        terminal=True,
                    ),
                    outcome="clarification",
                )
            aid, decision = resolve_approval_target(body.text, body.context)
            if aid is None or decision is None:
                return IntakeResponse(
                    interpretation=interp,
                    reply=IntakeReplyBundle(
                        message=interp.clarification_question
                        or "Could not resolve approval id or decision.",
                        kind="clarification",
                        display_text=display_text,
                        spoken_text=spoken_text,
                        activity_label=activity_label,
                        show_working_indicator=show_indicator,
                        intent_envelope=intent_envelope,
                        decision_envelope=decision_envelope,
                        terminal=True,
                    ),
                    outcome="clarification",
                )
            decided_by = str(ctx.get("decided_by") or "intake")
            decided_via = str(ctx.get("decided_via") or _decided_via_for_surface(body.source_surface))
            try:
                approval = await self._approvals.resolve_approval(
                    approval_id=aid,
                    decision=decision,
                    decided_by=decided_by,
                    decided_via=decided_via,
                    decision_notes=ctx.get("decision_notes"),
                )
            except HTTPException as e:
                return IntakeResponse(
                    interpretation=interp,
                    reply=IntakeReplyBundle(
                        message=str(e.detail),
                        kind="noop",
                        approval_id=aid,
                        extras={"error_status": e.status_code},
                        display_text=display_text,
                        spoken_text=spoken_text,
                        activity_label=activity_label,
                        show_working_indicator=show_indicator,
                        intent_envelope=intent_envelope,
                        decision_envelope=decision_envelope,
                        terminal=True,
                    ),
                    outcome="noop",
                )
            return IntakeResponse(
                interpretation=interp,
                reply=IntakeReplyBundle(
                    message=f"Approval {decision}: {approval.id}.",
                    kind="approval_resolved",
                    approval_id=approval.id,
                    mission_id=approval.mission_id,
                    display_text=display_text,
                    spoken_text=spoken_text,
                    activity_label=activity_label,
                    show_working_indicator=show_indicator,
                    intent_envelope=intent_envelope,
                    decision_envelope=decision_envelope,
                    terminal=True,
                ),
                outcome="approval_resolved",
            )

        if it == "inbox_action":
            parsed = parse_inbox_triage(body.text, body.context)
            if not parsed:
                return IntakeResponse(
                    interpretation=interp,
                    reply=IntakeReplyBundle(
                        message="Specify inbox_item_key and inbox_action in context, or "
                        "say: acknowledge <item_key>, snooze <item_key> [minutes], dismiss <item_key>.",
                        kind="clarification",
                        display_text=display_text,
                        spoken_text=spoken_text,
                        activity_label=activity_label,
                        show_working_indicator=show_indicator,
                        intent_envelope=intent_envelope,
                        decision_envelope=decision_envelope,
                        terminal=True,
                    ),
                    outcome="clarification",
                )
            action, item_key, snooze_minutes = parsed
            if action == "acknowledge":
                await OperatorInboxStateRepository.upsert_acknowledge(self._session, item_key)
            elif action == "snooze":
                await OperatorInboxStateRepository.upsert_snooze(
                    self._session, item_key, minutes=snooze_minutes or 60
                )
            else:
                await OperatorInboxStateRepository.upsert_dismiss(self._session, item_key)
            await self._session.commit()
            return IntakeResponse(
                interpretation=interp,
                reply=IntakeReplyBundle(
                    message=f"Inbox {action} applied for {item_key}.",
                    kind="inbox_updated",
                    extras={"inbox_action": action, "item_key": item_key},
                    display_text=display_text,
                    spoken_text=spoken_text,
                    activity_label=activity_label,
                    show_working_indicator=show_indicator,
                    intent_envelope=intent_envelope,
                    decision_envelope=decision_envelope,
                    terminal=True,
                ),
                outcome="inbox_updated",
            )

        if it == "status_query":
            missions = await self._missions.list_missions(limit=15, offset=0)
            lines = [f"- {m.id}: {m.status} — {m.title[:80]}" for m in missions[:10]]
            summary = "\n".join(lines) if lines else "No missions yet."
            extra: dict[str, Any] = {
                "mission_count": len(missions),
                "preview": [
                    {"id": str(m.id), "status": m.status, "title": m.title} for m in missions[:5]
                ],
            }
            return IntakeResponse(
                interpretation=interp,
                reply=IntakeReplyBundle(
                    message=f"Recent missions (newest first):\n{summary}",
                    kind="status_snapshot",
                    extras=extra,
                    display_text=display_text,
                    spoken_text=spoken_text,
                    activity_label=activity_label,
                    show_working_indicator=show_indicator,
                    intent_envelope=intent_envelope,
                    decision_envelope=decision_envelope,
                    terminal=True,
                ),
                outcome="status_reply",
            )

        if it == "governed_action_request":
            gat = interp.governed_action_type
            return IntakeResponse(
                interpretation=interp,
                reply=IntakeReplyBundle(
                    message=(
                        f"Governed action hint: {gat}. Create a mission first (or use intake with "
                        "a work request), then call the mission-scoped integration route, "
                        "or use GET /api/v1/operator/action-catalog."
                    ),
                    kind="governed_action_hint",
                    extras={
                        "governed_action_type": gat,
                        "catalog": "/api/v1/operator/action-catalog",
                    },
                    display_text=display_text,
                    spoken_text=spoken_text,
                    activity_label=activity_label,
                    show_working_indicator=show_indicator,
                    intent_envelope=intent_envelope,
                    decision_envelope=decision_envelope,
                    terminal=True,
                ),
                outcome="governed_action_hint",
            )

        if it == "conversational_reply":
            return IntakeResponse(
                interpretation=interp,
                reply=IntakeReplyBundle(
                    message="Acknowledged.",
                    kind="conversational",
                    display_text=display_text,
                    spoken_text=spoken_text,
                    activity_label=activity_label,
                    show_working_indicator=show_indicator,
                    intent_envelope=intent_envelope,
                    decision_envelope=decision_envelope,
                    terminal=True,
                ),
                outcome="conversational_reply",
            )

        # mission_request or mission_followup → CommandService
        merged_ctx: dict[str, Any] = dict(ctx)
        merged_ctx.update(routing_context_for_decide_route(intent_envelope))
        if body.surface_session_id is not None:
            merged_ctx.setdefault(
                "intake_surface_session_id",
                str(body.surface_session_id),
            )
        mid_ctx = body.mission_id
        if it == "mission_followup" and mid_ctx is not None:
            merged_ctx.setdefault("related_mission_id", str(mid_ctx))

        cmd = CommandCreate(
            text=interp.normalized_command,
            source=map_surface_to_command_source(body.source_surface),
            surface_session_id=body.surface_session_id,
            context=merged_ctx if merged_ctx else None,
        )
        resp = await self._commands.intake(cmd)

        outcome: IntakeOutcome = "mission_created"
        return IntakeResponse(
            interpretation=interp,
            reply=IntakeReplyBundle(
                message=resp.message,
                kind="mission_created",
                mission_id=resp.mission_id,
                extras={
                    "mission_status": resp.mission_status,
                    "intent_type": it,
                },
                display_text=display_text,
                spoken_text=spoken_text,
                activity_label=activity_label,
                show_working_indicator=show_indicator,
                intent_envelope=intent_envelope,
                decision_envelope=decision_envelope,
                terminal=True,
            ),
            outcome=outcome,
        )
