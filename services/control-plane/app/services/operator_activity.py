"""Normalize mission timeline + receipt joins into operator activity feed items."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heartbeat_finding import HeartbeatFinding
from app.models.mission import Mission
from app.repositories.heartbeat_finding_repo import HeartbeatFindingRepository
from app.schemas.operator import ActivitySummary, OperatorActivityItem
from app.services.heartbeat_service import finding_to_activity_meta

_ATTENTION_SQL = """(
  (me.event_type = 'approval_resolved' AND me.payload->>'decision' = 'denied')
  OR (me.event_type = 'mission_status_changed' AND COALESCE(me.payload->>'to', '') IN ('failed', 'blocked'))
  OR (
    me.event_type = 'receipt_recorded'
    AND EXISTS (
      SELECT 1 FROM receipts rx
      WHERE rx.mission_id = me.mission_id
        AND rx.receipt_type = 'openclaw_execution'
        AND (rx.payload ? 'success')
        AND (rx.payload->>'success')::boolean = false
        AND rx.created_at >= me.created_at - interval '3 seconds'
        AND rx.created_at <= me.created_at + interval '3 seconds'
    )
  )
)"""


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    return dt.isoformat().replace("+00:00", "Z")


def _truncate(s: str | None, n: int = 240) -> str | None:
    if s is None:
        return None
    t = s.strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _kind_and_category(event_type: str) -> tuple[str, str]:
    if event_type in ("approval_requested", "approval_resolved"):
        return "approval", "approval"
    if event_type == "receipt_recorded":
        return "receipt", "execution"
    if event_type == "routing_decided":
        # Category "mission" so mission-filtered activity includes routing without a new filter enum.
        return "routing", "mission"
    if event_type in ("memory_saved", "memory_promoted", "memory_archived"):
        return "memory", "memory"
    if event_type in ("created", "mission_status_changed"):
        return "mission_event", "mission"
    return "mission_event", "mission"


def _title_summary_status(
    event_type: str,
    payload: dict[str, Any] | None,
    mission_status: str,
    receipt_payload: dict[str, Any] | None,
) -> tuple[str, str, str]:
    """Return title, summary, status string for UI."""
    p = payload or {}
    if event_type == "created":
        return (
            "Mission created",
            "New mission opened in the control plane.",
            mission_status,
        )
    if event_type == "mission_status_changed":
        to_s = str(p.get("to") or "")
        from_s = str(p.get("from") or "")
        return (
            f"Mission status: {from_s} → {to_s}",
            f"Mission lifecycle update stored as mission_status_changed.",
            to_s or mission_status,
        )
    if event_type == "approval_requested":
        action = str(p.get("action_type") or "Action")
        risk = str(p.get("risk_class") or "")
        title = "Approval requested"
        summary = f"{action}" + (f" · risk {risk}" if risk else "")
        rb = str(p.get("requested_by") or "")
        if rb:
            summary = f"{summary} — requested by {rb}".strip()
        return title, _truncate(summary) or title, "pending"
    if event_type == "approval_resolved":
        dec = str(p.get("decision") or "").lower()
        if dec == "approved":
            title = "Approval approved"
        elif dec == "denied":
            title = "Approval denied"
        else:
            title = "Approval resolved"
        by = str(p.get("decided_by") or "")
        summary = f"Decision: {dec}" + (f" · by {by}" if by else "")
        return title, summary, dec if dec in ("approved", "denied") else "resolved"
    if event_type == "routing_decided":
        req = str(p.get("requested_lane") or "")
        act = str(p.get("actual_lane") or "")
        fb = p.get("fallback_applied") is True
        pending = p.get("pending_approval") is True
        if fb and req == "local_fast" and act == "gateway":
            title = "Routing decided: local-fast, fell back to gateway"
        elif act == "gateway":
            title = "Routing decided: gateway"
        elif act == "local_fast":
            title = "Routing decided: local-fast"
        else:
            title = "Routing decided"
        rs = str(p.get("reason_summary") or "").strip()
        parts: list[str] = []
        if rs:
            parts.append(rs)
        if pending:
            parts.append("Execution deferred pending approval.")
        summary = _truncate(" ".join(parts)) or title
        return title, summary, "pending" if pending else mission_status
    if event_type == "receipt_recorded":
        rt = str(p.get("receipt_type") or "receipt")
        src = str(p.get("source") or "")
        summ = str(p.get("summary") or "").strip()
        if rt == "openclaw_execution":
            title = "Execution receipt recorded"
        else:
            title = "Receipt recorded"
        line = f"{rt}" + (f" · {src}" if src else "")
        if summ:
            line = f"{line} — {_truncate(summ, 160)}"
        # Enrich success from joined receipt row when present
        rp = receipt_payload or {}
        if "success" in rp:
            ok = rp.get("success")
            st = "succeeded" if ok is True else "failed" if ok is False else "unknown"
            line = f"{line} · execution {st}"
            return title, _truncate(line) or title, st
        em = rp.get("execution_meta") if isinstance(rp.get("execution_meta"), dict) else {}
        lane = em.get("lane") if isinstance(em, dict) else None
        if lane:
            line = f"{line} · lane {lane}"
        return title, _truncate(line) or title, "recorded"

    if event_type == "memory_saved":
        title = "Operator memory saved"
        sk = str(p.get("source_kind") or "manual")
        mt = str(p.get("memory_type") or "")
        ti = str(p.get("title") or "").strip()
        summary = f"{ti}" + (f" · type {mt}" if mt else "") + (f" · source {sk}" if sk else "")
        return title, _truncate(summary) or title, "saved"
    if event_type == "memory_promoted":
        title = "Memory promoted"
        sk = str(p.get("source_kind") or "")
        mt = str(p.get("memory_type") or "")
        ti = str(p.get("title") or "").strip()
        summary = f"{ti}" + (f" · {mt}" if mt else "")
        if sk:
            summary = f"{summary} · {sk}".strip()
        return title, _truncate(summary) or title, "promoted"
    if event_type == "memory_archived":
        title = "Memory archived"
        ti = str(p.get("title") or "").strip()
        summary = ti or "Memory item archived."
        return title, _truncate(summary) or title, "archived"

    return (
        event_type.replace("_", " ").title(),
        f"Mission event `{event_type}` recorded.",
        mission_status,
    )


def _actor_label(
    event_type: str,
    actor_type: str | None,
    actor_id: str | None,
    payload: dict[str, Any] | None,
) -> str | None:
    p = payload or {}
    if event_type == "approval_requested":
        return str(p.get("requested_by") or "") or None
    if event_type == "approval_resolved":
        return str(p.get("decided_by") or "") or None
    if actor_id:
        return str(actor_id)
    if actor_type:
        return str(actor_type)
    src = str(p.get("source") or "")
    if src:
        return src
    return None


def _risk_class(event_type: str, payload: dict[str, Any] | None) -> str | None:
    p = payload or {}
    if event_type in ("approval_requested", "approval_resolved"):
        rc = p.get("risk_class")
        if rc:
            return str(rc)
    return None


def _meta(
    event_type: str,
    payload: dict[str, Any] | None,
    receipt_id: uuid.UUID | None,
    receipt_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Small, non-sensitive meta for inspectors."""
    p = payload or {}
    meta: dict[str, Any] = {
        "provenance": "mission_event",
        "event_type": event_type,
    }
    if event_type == "approval_requested" or event_type == "approval_resolved":
        aid = p.get("approval_id")
        if aid:
            meta["approval_id"] = str(aid)
    if event_type == "routing_decided":
        for k in (
            "requested_lane",
            "actual_lane",
            "fallback_applied",
            "reason_code",
            "pending_approval",
        ):
            if k in p:
                meta[k] = p.get(k)
    if event_type in ("memory_saved", "memory_promoted", "memory_archived"):
        for k in ("memory_id", "memory_type", "title", "source_kind", "source_receipt_id"):
            if k in p:
                meta[k] = p.get(k)
    if event_type == "receipt_recorded":
        if p.get("receipt_type"):
            meta["receipt_type"] = str(p.get("receipt_type"))
        if p.get("source"):
            meta["source"] = str(p.get("source"))
        if receipt_id:
            meta["receipt_id"] = str(receipt_id)
        rp = receipt_payload or {}
        if isinstance(rp.get("execution_meta"), dict):
            em = rp["execution_meta"]
            meta["execution_meta"] = {
                k: em.get(k)
                for k in ("lane", "gateway_model", "local_model", "resumed_from_approval", "routing")
                if k in em
            }
        if "success" in rp:
            meta["execution_success"] = rp.get("success")
    return meta


def row_to_item(
    *,
    event_id: uuid.UUID,
    created_at: datetime,
    event_type: str,
    payload: dict[str, Any] | None,
    actor_type: str | None,
    actor_id: str | None,
    mission_id: uuid.UUID,
    mission_title: str,
    mission_status: str,
    receipt_id: uuid.UUID | None,
    receipt_payload: dict[str, Any] | None,
) -> OperatorActivityItem:
    kind, category = _kind_and_category(event_type)
    title, summary, status = _title_summary_status(
        event_type, payload, mission_status, receipt_payload
    )
    return OperatorActivityItem(
        id=str(event_id),
        occurred_at=_iso(created_at),
        kind=kind,
        category=category,
        title=title,
        summary=summary,
        status=status,
        mission_id=str(mission_id),
        mission_title=mission_title,
        actor_label=_actor_label(event_type, actor_type, actor_id, payload),
        risk_class=_risk_class(event_type, payload),
        meta=_meta(event_type, payload, receipt_id, receipt_payload),
    )


_ATTENTION_ME = _ATTENTION_SQL  # uses me. alias

_ATTENTION_COUNT = """(
  (event_type = 'approval_resolved' AND payload->>'decision' = 'denied')
  OR (event_type = 'mission_status_changed' AND COALESCE(payload->>'to', '') IN ('failed', 'blocked'))
  OR (
    event_type = 'receipt_recorded'
    AND EXISTS (
      SELECT 1 FROM receipts rx
      WHERE rx.mission_id = mission_events.mission_id
        AND rx.receipt_type = 'openclaw_execution'
        AND (rx.payload ? 'success')
        AND (rx.payload->>'success')::boolean = false
        AND rx.created_at >= mission_events.created_at - interval '3 seconds'
        AND rx.created_at <= mission_events.created_at + interval '3 seconds'
    )
  )
)"""


def _category_sql_me(category: str | None) -> str:
    if not category:
        return ""
    if category == "mission":
        return (
            "AND me.event_type IN ("
            "'created', 'mission_status_changed', 'routing_decided', "
            "'memory_saved', 'memory_promoted', 'memory_archived'"
            ")"
        )
    if category == "approval":
        return "AND me.event_type IN ('approval_requested', 'approval_resolved')"
    if category == "execution":
        return "AND me.event_type = 'receipt_recorded'"
    if category == "attention":
        return f"AND {_ATTENTION_ME}"
    if category == "memory":
        return (
            "AND me.event_type IN ('memory_saved', 'memory_promoted', 'memory_archived')"
        )
    return ""


ACTIVITY_SELECT = """
SELECT
  me.id,
  me.created_at,
  me.event_type,
  me.payload,
  me.actor_type,
  me.actor_id,
  m.id AS mission_id,
  m.title AS mission_title,
  m.status AS mission_status,
  r.id AS receipt_id,
  r.payload AS receipt_payload
FROM mission_events me
JOIN missions m ON m.id = me.mission_id
LEFT JOIN LATERAL (
  SELECT rx.id, rx.payload
  FROM receipts rx
  WHERE rx.mission_id = me.mission_id
    AND me.event_type = 'receipt_recorded'
    AND rx.receipt_type = 'openclaw_execution'
    AND abs(extract(epoch from (rx.created_at - me.created_at))) < 3
  ORDER BY abs(extract(epoch from (rx.created_at - me.created_at)))
  LIMIT 1
) r ON TRUE
"""


async def fetch_activity_summary(session: AsyncSession, *, window_days: int = 7) -> ActivitySummary:
    win = f"interval '{window_days} days'"
    total = await session.execute(
        text(f"SELECT COUNT(*)::int FROM mission_events WHERE created_at >= NOW() - {win}")
    )
    appr = await session.execute(
        text(
            f"""
            SELECT COUNT(*)::int FROM mission_events
            WHERE created_at >= NOW() - {win}
              AND event_type IN ('approval_requested', 'approval_resolved')
            """
        )
    )
    exe = await session.execute(
        text(
            f"""
            SELECT COUNT(*)::int FROM mission_events
            WHERE created_at >= NOW() - {win}
              AND event_type = 'receipt_recorded'
            """
        )
    )
    att = await session.execute(
        text(
            f"""
            SELECT COUNT(*)::int FROM mission_events
            WHERE created_at >= NOW() - {win}
              AND {_ATTENTION_COUNT}
            """
        )
    )
    mem = await session.execute(
        text(
            f"""
            SELECT COUNT(*)::int FROM mission_events
            WHERE created_at >= NOW() - {win}
              AND event_type IN ('memory_saved', 'memory_promoted', 'memory_archived')
            """
        )
    )
    hb = await session.execute(
        text("SELECT COUNT(*)::int FROM heartbeat_findings WHERE status = 'open'")
    )

    return ActivitySummary(
        window_hours=window_days * 24,
        total_in_window=int(total.scalar_one() or 0),
        approvals_in_window=int(appr.scalar_one() or 0),
        execution_in_window=int(exe.scalar_one() or 0),
        attention_in_window=int(att.scalar_one() or 0),
        memory_in_window=int(mem.scalar_one() or 0),
        heartbeat_open_total=int(hb.scalar_one() or 0),
    )


async def _mission_titles_map(
    session: AsyncSession, ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    result = await session.execute(select(Mission).where(Mission.id.in_(ids)))
    rows = result.scalars().all()
    return {m.id: m.title for m in rows}


async def _heartbeat_rows_to_items(
    session: AsyncSession,
    rows: list[HeartbeatFinding],
) -> list[OperatorActivityItem]:
    mids = {r.mission_id for r in rows if r.mission_id is not None}
    titles = await _mission_titles_map(session, mids)
    out: list[OperatorActivityItem] = []
    for hf in rows:
        mt = titles.get(hf.mission_id, "Mission") if hf.mission_id else "System"
        title = f"[{hf.severity}] {hf.finding_type.replace('_', ' ')}"
        summ = hf.summary.strip() if hf.summary else title
        out.append(
            OperatorActivityItem(
                id=str(hf.id),
                occurred_at=_iso(hf.last_seen_at),
                kind="heartbeat",
                category="heartbeat",
                title=title,
                summary=summ[:2000] if len(summ) > 2000 else summ,
                status="open",
                mission_id=str(hf.mission_id) if hf.mission_id else "",
                mission_title=mt,
                actor_label=None,
                risk_class=None,
                meta=finding_to_activity_meta(hf),
            )
        )
    return out


async def _fetch_heartbeat_activity_page(
    session: AsyncSession,
    *,
    limit: int,
    before: datetime | None,
    mission_id: uuid.UUID | None,
) -> tuple[list[OperatorActivityItem], str | None]:
    rows = await HeartbeatFindingRepository.list_open_recent(
        session, limit=limit * 3, before=before
    )
    if mission_id is not None:
        rows = [r for r in rows if r.mission_id == mission_id]
    rows = rows[:limit]
    items = await _heartbeat_rows_to_items(session, rows)
    next_before: str | None = None
    if items and len(items) >= limit:
        next_before = items[-1].occurred_at
    return items, next_before


async def _fetch_mission_event_activity_page(
    session: AsyncSession,
    *,
    limit: int,
    before: datetime | None,
    mission_id: uuid.UUID | None,
    category: str | None,
) -> tuple[list[OperatorActivityItem], str | None]:
    where_parts = ["1=1"]
    params: dict[str, Any] = {"lim": limit}

    if before is not None:
        where_parts.append("me.created_at < :before_ts")
        params["before_ts"] = before
    if mission_id is not None:
        where_parts.append("me.mission_id = CAST(:mid AS uuid)")
        params["mid"] = str(mission_id)

    cat_sql = _category_sql_me(category)
    where_sql = " AND ".join(where_parts) + (" " + cat_sql if cat_sql else "")

    sql = text(
        f"{ACTIVITY_SELECT.strip()}\nWHERE {where_sql}\nORDER BY me.created_at DESC, me.id DESC\nLIMIT :lim"
    )
    result = await session.execute(sql, params)
    rows = result.mappings().all()
    items: list[OperatorActivityItem] = []
    for row in rows:
        pl = row["payload"]
        if pl is not None and not isinstance(pl, dict):
            pl = dict(pl) if hasattr(pl, "items") else {}
        rp = row["receipt_payload"]
        if rp is not None and not isinstance(rp, dict):
            rp = dict(rp) if hasattr(rp, "items") else {}
        items.append(
            row_to_item(
                event_id=row["id"],
                created_at=row["created_at"],
                event_type=str(row["event_type"]),
                payload=pl,
                actor_type=row["actor_type"],
                actor_id=row["actor_id"],
                mission_id=row["mission_id"],
                mission_title=str(row["mission_title"]),
                mission_status=str(row["mission_status"]),
                receipt_id=row["receipt_id"],
                receipt_payload=rp,
            )
        )

    next_before: str | None = None
    if items and len(items) >= limit:
        next_before = items[-1].occurred_at
    return items, next_before


async def fetch_activity_items(
    session: AsyncSession,
    *,
    limit: int,
    before: datetime | None,
    mission_id: uuid.UUID | None,
    category: str | None,
) -> tuple[list[OperatorActivityItem], str | None]:
    if category == "heartbeat":
        return await _fetch_heartbeat_activity_page(
            session, limit=limit, before=before, mission_id=mission_id
        )

    me_items, me_next = await _fetch_mission_event_activity_page(
        session, limit=limit, before=before, mission_id=mission_id, category=category
    )

    if category not in (None, "all"):
        return me_items, me_next

    hf_items, _hf_next = await _fetch_heartbeat_activity_page(
        session, limit=limit, before=before, mission_id=mission_id
    )

    merged = sorted(
        me_items + hf_items,
        key=lambda it: it.occurred_at,
        reverse=True,
    )[:limit]

    next_before: str | None = None
    if merged and len(merged) >= limit:
        next_before = merged[-1].occurred_at
    return merged, next_before
