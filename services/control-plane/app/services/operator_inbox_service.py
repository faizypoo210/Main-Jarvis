"""Build operator inbox from governed truth + merge operator_inbox_state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval_reminder import ApprovalReminder
from app.models.heartbeat_finding import HeartbeatFinding
from app.models.operator_inbox_state import OperatorInboxState
from app.repositories.approval_repo import ApprovalRepository
from app.repositories.heartbeat_finding_repo import HeartbeatFindingRepository
from app.repositories.operator_inbox_state_repo import OperatorInboxStateRepository
from app.services.governed_action_labels import (
    compact_label_for_approval_action_type,
    humanize_requested_via,
)
from app.schemas.operator_inbox import (
    OperatorInboxCounts,
    OperatorInboxItemRead,
    OperatorInboxResponse,
)

_SEVERITY_RANK = {"urgent": 0, "attention": 1, "info": 2}


def _map_hb_severity(sev: str) -> str:
    s = (sev or "").lower()
    if s == "critical":
        return "urgent"
    if s == "high":
        return "attention"
    return "info"


def _approval_severity(*, risk_class: str, escalation_sent: bool) -> str:
    if escalation_sent or str(risk_class).lower() == "red":
        return "urgent"
    if str(risk_class).lower() == "amber":
        return "attention"
    return "info"


def _inbox_group(*, source_kind: str, meta: dict[str, Any]) -> str:
    if source_kind == "approval":
        return "approvals"
    if source_kind == "integration_failure":
        return "failures"
    if source_kind == "mission_failure":
        return "failures"
    if source_kind == "heartbeat":
        ft = str(meta.get("finding_type") or "")
        if ft.startswith("cost_"):
            return "cost"
        if ft in ("stalled_mission", "aging_approval", "approval_escalation_pending"):
            return "failures"
        return "system"
    return "system"


def _heartbeat_href(hf: HeartbeatFinding) -> str:
    ft = hf.finding_type or ""
    if ft.startswith("cost_"):
        return "/cost"
    if ft.startswith("system_degraded") or hf.service_component in ("postgres", "redis", "openclaw_gateway"):
        return "/system"
    if ft == "stale_worker":
        return "/workers"
    if ft == "integration_attention":
        return "/integrations"
    if hf.mission_id:
        return f"/missions/{hf.mission_id}"
    return "/missions"


def _effective_status(
    state: OperatorInboxState | None,
    *,
    now: datetime,
) -> str:
    if state is None:
        return "open"
    if state.dismissed_at is not None:
        return "dismissed"
    if state.snoozed_until is not None and state.snoozed_until > now:
        return "snoozed"
    if state.acknowledged_at is not None:
        return "acknowledged"
    return "open"


@dataclass
class _RawItem:
    item_key: str
    source_kind: str
    severity: str
    headline: str
    summary: str
    action_label: str
    mission_id: UUID | None
    approval_id: UUID | None
    related_href: str
    created_at: datetime
    updated_at: datetime
    meta: dict[str, Any]


async def _escalation_sent_ids(session: AsyncSession, approval_ids: list[UUID]) -> set[UUID]:
    if not approval_ids:
        return set()
    r = await session.execute(
        select(ApprovalReminder.approval_id).where(
            ApprovalReminder.approval_id.in_(approval_ids),
            ApprovalReminder.notification_type == "escalation",
            ApprovalReminder.status == "sent",
        )
    )
    return {row[0] for row in r.all()}


async def _build_raw_items(session: AsyncSession) -> list[_RawItem]:
    out: list[_RawItem] = []

    pending = await ApprovalRepository.get_pending(session, limit=200)
    pending_ids = {a.id for a in pending}
    esc = await _escalation_sent_ids(session, list(pending_ids))

    for a in pending:
        ek = a.id in esc
        sev = _approval_severity(risk_class=a.risk_class, escalation_sent=ek)
        action_label = compact_label_for_approval_action_type(a.action_type)[:80]
        headline = f"Pending approval: {action_label}"
        parts = [f"Risk {a.risk_class}", f"via {humanize_requested_via(a.requested_via)}"]
        if ek:
            parts.append("escalation SMS already sent")
        summary = " · ".join(parts)
        meta: dict[str, Any] = {
            "risk_class": a.risk_class,
            "requested_via": a.requested_via,
            "escalation_sent": ek,
            "inbox_group": "approvals",
        }
        out.append(
            _RawItem(
                item_key=f"approval:{a.id}",
                source_kind="approval",
                severity=sev,
                headline=headline,
                summary=summary,
                action_label="Review approval",
                mission_id=a.mission_id,
                approval_id=a.id,
                related_href=f"/approvals?approval={a.id}",
                created_at=a.created_at,
                updated_at=a.created_at,
                meta=meta,
            )
        )

    # Heartbeat open — dedupe against pending approval noise
    for hf in await HeartbeatFindingRepository.list_open(session):
        if hf.finding_type == "aging_approval" and hf.approval_id and hf.approval_id in pending_ids:
            continue
        if hf.finding_type == "approval_escalation_pending" and hf.approval_id and hf.approval_id in pending_ids:
            continue
        sev = _map_hb_severity(hf.severity)
        meta = {
            "finding_type": hf.finding_type,
            "dedupe_key": hf.dedupe_key,
            "heartbeat_finding_id": str(hf.id),
            "inbox_group": _inbox_group(source_kind="heartbeat", meta={"finding_type": hf.finding_type}),
        }
        out.append(
            _RawItem(
                item_key=f"heartbeat:{hf.id}",
                source_kind="heartbeat",
                severity=sev,
                headline=f"[{hf.finding_type}] Supervision",
                summary=(hf.summary or "")[:500],
                action_label="Open supervision context",
                mission_id=hf.mission_id,
                approval_id=hf.approval_id,
                related_href=_heartbeat_href(hf),
                created_at=hf.first_seen_at,
                updated_at=hf.last_seen_at,
                meta=meta,
            )
        )

    # Latest integration_action_failed per active-ish mission
    r2 = await session.execute(
        text(
            """
            SELECT DISTINCT ON (me.mission_id)
              me.id AS event_id,
              me.mission_id,
              me.created_at,
              me.payload,
              m.title AS mission_title
            FROM mission_events me
            INNER JOIN missions m ON m.id = me.mission_id
            WHERE me.event_type = 'integration_action_failed'
              AND m.status IN ('active', 'pending', 'awaiting_approval')
            ORDER BY me.mission_id, me.created_at DESC
            LIMIT 50
            """
        )
    )
    for row in r2.mappings().all():
        mid = row["mission_id"]
        payload = row["payload"] or {}
        if not isinstance(payload, dict):
            payload = {}
        prov = str(payload.get("provider") or "")
        act = str(payload.get("action") or "")
        err = str(payload.get("error_code") or payload.get("message") or "")[:120]
        headline = f"Integration action failed ({prov or 'integration'})"
        summary = f"{act} · {err}".strip(" · ") if act or err else "Governed integration reported failure on mission timeline."
        meta = {
            "event_id": str(row["event_id"]),
            "provider": prov or None,
            "action": act or None,
            "inbox_group": "failures",
        }
        out.append(
            _RawItem(
                item_key=f"integration_failure:{mid}",
                source_kind="integration_failure",
                severity="urgent",
                headline=headline,
                summary=summary,
                action_label="Open mission",
                mission_id=mid,
                approval_id=None,
                related_href=f"/missions/{mid}",
                created_at=row["created_at"],
                updated_at=row["created_at"],
                meta=meta,
            )
        )

    # Terminal missions (failed / blocked)
    r3 = await session.execute(
        text(
            """
            SELECT id, title, status, updated_at
            FROM missions
            WHERE status IN ('failed', 'blocked')
            ORDER BY updated_at DESC
            LIMIT 25
            """
        )
    )
    for row in r3.mappings().all():
        mid = row["id"]
        title = str(row["title"] or "Mission")[:120]
        st = str(row["status"] or "")
        headline = f"Mission {st}: {title}"
        summary = f"Mission is in terminal state «{st}». Inspect timeline and receipts for remediation."
        meta = {"mission_status": st, "inbox_group": "failures"}
        out.append(
            _RawItem(
                item_key=f"mission_terminal:{mid}",
                source_kind="mission_failure",
                severity="attention",
                headline=headline,
                summary=summary,
                action_label="Open mission",
                mission_id=mid,
                approval_id=None,
                related_href=f"/missions/{mid}",
                created_at=row["updated_at"],
                updated_at=row["updated_at"],
                meta=meta,
            )
        )

    return out


def _passes_filter(
    item: _RawItem,
    *,
    group: str | None,
    severity: str | None,
    source_kind: str | None,
) -> bool:
    if group and group != "all":
        ig = item.meta.get("inbox_group") or _inbox_group(
            source_kind=item.source_kind, meta=item.meta
        )
        if group == "approvals" and ig != "approvals":
            return False
        if group == "system" and ig != "system":
            return False
        if group == "cost" and ig != "cost":
            return False
        if group == "failures" and ig != "failures":
            return False
    if severity and item.severity != severity:
        return False
    if source_kind and item.source_kind != source_kind:
        return False
    return True


def _passes_status_filter(eff: str, status_filter: str) -> bool:
    if status_filter == "all":
        return True
    if status_filter == "open":
        return eff == "open"
    if status_filter == "acknowledged":
        return eff == "acknowledged"
    if status_filter == "snoozed":
        return eff == "snoozed"
    if status_filter == "dismissed":
        return eff == "dismissed"
    return True


async def build_operator_inbox_response(
    session: AsyncSession,
    *,
    group: str | None = None,
    severity: str | None = None,
    source_kind: str | None = None,
    status_filter: str = "open",
    limit: int = 120,
) -> OperatorInboxResponse:
    now = datetime.now(UTC)
    raw = await _build_raw_items(session)
    keys = [r.item_key for r in raw]
    states = await OperatorInboxStateRepository.get_many(session, keys)

    visible: list[tuple[_RawItem, OperatorInboxState | None, str]] = []
    for r in raw:
        if not _passes_filter(r, group=group, severity=severity, source_kind=source_kind):
            continue
        st = states.get(r.item_key)
        eff = _effective_status(st, now=now)
        if not _passes_status_filter(eff, status_filter):
            continue
        visible.append((r, st, eff))

    visible.sort(
        key=lambda t: (
            _SEVERITY_RANK.get(t[0].severity, 9),
            t[0].created_at,
        )
    )
    visible = visible[:limit]

    items: list[OperatorInboxItemRead] = []
    for r, st, eff in visible:
        ig = r.meta.get("inbox_group") or _inbox_group(source_kind=r.source_kind, meta=r.meta)
        items.append(
            OperatorInboxItemRead(
                item_key=r.item_key,
                source_kind=r.source_kind,
                inbox_group=ig,
                severity=r.severity,
                status=eff,
                headline=r.headline,
                summary=r.summary,
                action_label=r.action_label,
                mission_id=r.mission_id,
                approval_id=r.approval_id,
                related_href=r.related_href,
                created_at=r.created_at,
                updated_at=st.updated_at if st else r.updated_at,
                acknowledged_at=st.acknowledged_at if st else None,
                snoozed_until=st.snoozed_until if st else None,
                meta={k: v for k, v in r.meta.items() if k != "inbox_group"},
            )
        )

    # Counts: open items only, respecting group/severity/source_kind filters (not status_filter)
    open_items: list[_RawItem] = []
    for r in raw:
        if not _passes_filter(r, group=group, severity=severity, source_kind=source_kind):
            continue
        st = states.get(r.item_key)
        eff = _effective_status(st, now=now)
        if eff != "open":
            continue
        open_items.append(r)

    c_urgent = sum(1 for x in open_items if x.severity == "urgent")
    c_att = sum(1 for x in open_items if x.severity == "attention")
    c_info = sum(1 for x in open_items if x.severity == "info")
    c_appr = sum(1 for x in open_items if x.source_kind == "approval")
    c_hb = sum(1 for x in open_items if x.source_kind == "heartbeat")
    c_cost = sum(
        1
        for x in open_items
        if x.source_kind == "heartbeat" and str(x.meta.get("finding_type") or "").startswith("cost_")
    )

    counts = OperatorInboxCounts(
        urgent=c_urgent,
        attention=c_att,
        info=c_info,
        approvals_pending=c_appr,
        heartbeat_open=c_hb,
        cost_alerts=c_cost,
        total_visible=len(open_items),
    )

    return OperatorInboxResponse(
        generated_at=now.isoformat().replace("+00:00", "Z"),
        counts=counts,
        items=items,
    )
