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
                ),
                outcome="governed_action_hint",
            )

        if it == "conversational_reply":
            return IntakeResponse(
                interpretation=interp,
                reply=IntakeReplyBundle(
                    message="Acknowledged.",
                    kind="conversational",
                ),
                outcome="conversational_reply",
            )

        # mission_request or mission_followup → CommandService
        merged_ctx: dict[str, Any] = dict(ctx)
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
            ),
            outcome=outcome,
        )
