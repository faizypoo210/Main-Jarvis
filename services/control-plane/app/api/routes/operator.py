"""Operator-facing aggregates (missions, receipts, execution signals)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.auth import require_api_key
from app.schemas.operator import (
    ActivitySummary,
    DailyReceiptCount,
    LaneCount,
    MissionStatusCount,
    OperatorActivityResponse,
    OperatorIntegrationsResponse,
    OperatorUsageResponse,
)
from app.schemas.operator_inbox import (
    OperatorInboxAckResponse,
    OperatorInboxDismissResponse,
    OperatorInboxResponse,
    OperatorInboxSnoozeBody,
)
from app.schemas.cost_events import OperatorCostEventsResponse
from app.schemas.cost_guardrails import OperatorCostGuardrailsResponse
from app.schemas.workers import OperatorWorkersResponse
from app.schemas.governed_action_catalog import GovernedActionCatalogResponse
from app.schemas.operator_evals import OperatorValueEvalsResponse
from app.services.governed_action_catalog import build_governed_action_catalog_response
from app.services.cost_guardrail_service import build_operator_cost_guardrails_response
from app.services.cost_operator_service import fetch_operator_cost_events
from app.services.operator_activity import fetch_activity_items, fetch_activity_summary
from app.services.operator_integrations import build_integrations_report
from app.services.operator_inbox_service import build_operator_inbox_response
from app.services.operator_value_evals import build_operator_value_evals
from app.services.worker_registry_service import list_operator_workers
from app.repositories.operator_inbox_state_repo import OperatorInboxStateRepository

router = APIRouter()


@router.get("/operator/action-catalog", response_model=GovernedActionCatalogResponse)
async def operator_action_catalog() -> GovernedActionCatalogResponse:
    """Launch metadata for governed GitHub/Gmail actions (Command Center + voice). No secrets."""
    return build_governed_action_catalog_response()


def _worker_stale_threshold_minutes() -> float:
    raw = os.environ.get("HEARTBEAT_WORKER_STALE_MINUTES", "").strip()
    if not raw:
        return 15.0
    try:
        return float(raw)
    except ValueError:
        return 15.0


_ACTIVITY_CATEGORIES = frozenset(
    {"mission", "approval", "execution", "attention", "memory", "heartbeat"}
)

def _parse_before_iso(raw: str | None) -> datetime | None:
    if raw is None or not str(raw).strip():
        return None
    s = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid before cursor (ISO-8601 expected)") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    return dt.isoformat().replace("+00:00", "Z")


@router.get("/operator/integrations", response_model=OperatorIntegrationsResponse)
async def operator_integrations(
    session: AsyncSession = Depends(get_db),
) -> OperatorIntegrationsResponse:
    """Honest integration readiness: DB + safe machine probes (no OAuth or secrets)."""
    return await build_integrations_report(session)


@router.get("/operator/workers", response_model=OperatorWorkersResponse)
async def operator_workers(session: AsyncSession = Depends(get_db)) -> OperatorWorkersResponse:
    """Registered workers + last heartbeats (direct DB truth)."""
    return await list_operator_workers(
        session, stale_threshold_minutes=_worker_stale_threshold_minutes()
    )


@router.get("/operator/activity", response_model=OperatorActivityResponse)
async def operator_activity(
    session: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    before: str | None = None,
    mission_id: UUID | None = None,
    category: str | None = None,
) -> OperatorActivityResponse:
    """Unified mission timeline for operators (mission_events + receipt join for execution outcomes)."""
    if category is not None and category not in _ACTIVITY_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=(
                "category must be one of: mission, approval, execution, attention, memory, heartbeat"
            ),
        )
    before_dt = _parse_before_iso(before)
    summary: ActivitySummary = await fetch_activity_summary(session)
    items, next_before = await fetch_activity_items(
        session,
        limit=limit,
        before=before_dt,
        mission_id=mission_id,
        category=category,
    )
    return OperatorActivityResponse(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        summary=summary,
        items=items,
        next_before=next_before,
    )


@router.get("/operator/cost-guardrails", response_model=OperatorCostGuardrailsResponse)
async def operator_cost_guardrails(
    session: AsyncSession = Depends(get_db),
) -> OperatorCostGuardrailsResponse:
    """Env thresholds + rolling cost_events metrics + open `cost_*` heartbeat findings."""
    return await build_operator_cost_guardrails_response(session)


@router.get("/operator/cost-events", response_model=OperatorCostEventsResponse)
async def operator_cost_events(
    session: AsyncSession = Depends(get_db),
    provider: str | None = None,
    cost_status: str | None = None,
    mission_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> OperatorCostEventsResponse:
    """Persisted cost_events — direct / estimated / unknown / not_applicable; not inferred receipt volume."""
    return await fetch_operator_cost_events(
        session,
        provider=provider,
        cost_status=cost_status,
        mission_id=mission_id,
        limit=limit,
        offset=offset,
    )


@router.get("/operator/usage", response_model=OperatorUsageResponse)
async def operator_usage(session: AsyncSession = Depends(get_db)) -> OperatorUsageResponse:
    """Receipt volume, mission counts, and execution signals — not token billing."""
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    r = await session.execute(text("SELECT COUNT(*) FROM missions"))
    missions_total = int(r.scalar_one() or 0)

    r = await session.execute(
        text("SELECT status, COUNT(*)::int AS c FROM missions GROUP BY status ORDER BY status")
    )
    missions_by_status = [
        MissionStatusCount(status=row[0], count=row[1]) for row in r.fetchall()
    ]

    r = await session.execute(
        text("SELECT receipt_type, COUNT(*)::int AS c FROM receipts GROUP BY receipt_type")
    )
    receipt_rows = r.fetchall()
    receipts_by_type: dict[str, int] = {str(row[0]): int(row[1]) for row in receipt_rows}
    receipts_total = sum(receipts_by_type.values())

    r = await session.execute(
        text(
            """
            SELECT
              COUNT(*) FILTER (WHERE receipt_type = 'openclaw_execution')::int AS oc,
              COUNT(*) FILTER (
                WHERE receipt_type = 'openclaw_execution'
                  AND (payload ? 'success')
                  AND (payload->>'success')::boolean = true
              )::int AS ok,
              COUNT(*) FILTER (
                WHERE receipt_type = 'openclaw_execution'
                  AND (payload ? 'success')
                  AND (payload->>'success')::boolean = false
              )::int AS fail,
              COUNT(*) FILTER (
                WHERE receipt_type = 'openclaw_execution'
                  AND NOT (payload ? 'success')
              )::int AS unk
            FROM receipts
            """
        )
    )
    row = r.one()
    openclaw_execution_receipts = int(row[0] or 0)
    openclaw_success = int(row[1] or 0)
    openclaw_failure = int(row[2] or 0)
    openclaw_success_unknown = int(row[3] or 0)

    r = await session.execute(
        text(
            """
            SELECT COALESCE(payload->'execution_meta'->>'lane', 'unknown') AS lane, COUNT(*)::int AS c
            FROM receipts
            WHERE receipt_type = 'openclaw_execution'
            GROUP BY 1
            ORDER BY c DESC
            """
        )
    )
    lane_distribution = [LaneCount(lane=str(row[0]), count=int(row[1])) for row in r.fetchall()]

    r = await session.execute(
        text(
            """
            SELECT
              to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS d,
              COUNT(*)::int AS c
            FROM receipts
            WHERE created_at >= NOW() - INTERVAL '14 days'
            GROUP BY 1
            ORDER BY 1 ASC
            """
        )
    )
    receipts_by_day_utc = [
        DailyReceiptCount(day=str(row[0]), count=int(row[1])) for row in r.fetchall()
    ]

    r = await session.execute(text("SELECT MAX(created_at) FROM mission_events"))
    last_mission_event_at = _iso(r.scalar_one())

    r = await session.execute(text("SELECT MAX(created_at) FROM receipts"))
    last_receipt_at = _iso(r.scalar_one())

    r = await session.execute(
        text(
            "SELECT MAX(created_at) FROM receipts WHERE receipt_type = 'openclaw_execution'"
        )
    )
    last_openclaw_execution_at = _iso(r.scalar_one())

    return OperatorUsageResponse(
        generated_at=now,
        missions_total=missions_total,
        missions_by_status=missions_by_status,
        receipts_total=receipts_total,
        receipts_by_type=receipts_by_type,
        openclaw_execution_receipts=openclaw_execution_receipts,
        openclaw_success=openclaw_success,
        openclaw_failure=openclaw_failure,
        openclaw_success_unknown=openclaw_success_unknown,
        lane_distribution=lane_distribution,
        receipts_by_day_utc=receipts_by_day_utc,
        last_mission_event_at=last_mission_event_at,
        last_receipt_at=last_receipt_at,
        last_openclaw_execution_at=last_openclaw_execution_at,
    )


@router.get("/operator/evals", response_model=OperatorValueEvalsResponse)
async def operator_value_evals(
    session: AsyncSession = Depends(get_db),
    window_hours: int = Query(
        168,
        ge=1,
        le=720,
        description="Rolling UTC window (max 720h). Default 168h (7 days).",
    ),
    group_by: str | None = Query(
        None,
        description="Optional rollup: 'day' for per-UTC-day buckets in timeseries.",
    ),
) -> OperatorValueEvalsResponse:
    """Operator Value Evals v1 — bounded aggregates from mission truth (no subjective AI scoring)."""
    if group_by is not None and group_by != "day":
        raise HTTPException(
            status_code=400,
            detail="group_by must be omitted or 'day'",
        )
    return await build_operator_value_evals(session, window_hours=window_hours, group_by=group_by)


_INBOX_GROUPS = frozenset({"all", "approvals", "system", "cost", "failures"})
_INBOX_STATUS = frozenset({"open", "acknowledged", "snoozed", "dismissed", "all"})
_INBOX_SEVERITY = frozenset({"urgent", "attention", "info"})
_INBOX_SOURCE_KIND = frozenset(
    {"approval", "heartbeat", "integration_failure", "mission_failure"}
)


@router.get("/operator/inbox", response_model=OperatorInboxResponse)
async def operator_inbox(
    session: AsyncSession = Depends(get_db),
    group: str | None = Query(
        None,
        description="Tab filter: all | approvals | system | cost | failures",
    ),
    severity: str | None = Query(None, description="Optional: urgent | attention | info"),
    source_kind: str | None = Query(
        None,
        description="Optional: approval | heartbeat | integration_failure | mission_failure",
    ),
    status: str = Query(
        "open",
        description="Item state: open | acknowledged | snoozed | dismissed | all",
    ),
    limit: int = Query(120, ge=1, le=300),
) -> OperatorInboxResponse:
    g = group or "all"
    if g not in _INBOX_GROUPS:
        raise HTTPException(status_code=400, detail="invalid group")
    if status not in _INBOX_STATUS:
        raise HTTPException(status_code=400, detail="invalid status")
    if severity is not None and severity not in _INBOX_SEVERITY:
        raise HTTPException(status_code=400, detail="invalid severity")
    if source_kind is not None and source_kind not in _INBOX_SOURCE_KIND:
        raise HTTPException(status_code=400, detail="invalid source_kind")
    return await build_operator_inbox_response(
        session,
        group=g if g != "all" else None,
        severity=severity,
        source_kind=source_kind,
        status_filter=status,
        limit=limit,
    )


@router.post(
    "/operator/inbox/{item_key}/acknowledge",
    response_model=OperatorInboxAckResponse,
)
async def operator_inbox_acknowledge(
    item_key: str,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> OperatorInboxAckResponse:
    await OperatorInboxStateRepository.upsert_acknowledge(session, item_key)
    await session.commit()
    return OperatorInboxAckResponse(item_key=item_key)


@router.post(
    "/operator/inbox/{item_key}/snooze",
    response_model=OperatorInboxAckResponse,
)
async def operator_inbox_snooze(
    item_key: str,
    body: OperatorInboxSnoozeBody,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> OperatorInboxAckResponse:
    await OperatorInboxStateRepository.upsert_snooze(session, item_key, minutes=body.minutes)
    await session.commit()
    return OperatorInboxAckResponse(item_key=item_key)


@router.post(
    "/operator/inbox/{item_key}/dismiss",
    response_model=OperatorInboxDismissResponse,
)
async def operator_inbox_dismiss(
    item_key: str,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> OperatorInboxDismissResponse:
    await OperatorInboxStateRepository.upsert_dismiss(session, item_key)
    await session.commit()
    return OperatorInboxDismissResponse(item_key=item_key)
