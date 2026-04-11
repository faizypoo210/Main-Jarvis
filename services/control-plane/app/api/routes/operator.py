"""Operator-facing aggregates (missions, receipts, execution signals)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.operator import (
    ActivitySummary,
    DailyReceiptCount,
    LaneCount,
    MissionStatusCount,
    OperatorActivityResponse,
    OperatorIntegrationsResponse,
    OperatorUsageResponse,
)
from app.services.operator_activity import fetch_activity_items, fetch_activity_summary
from app.services.operator_integrations import build_integrations_report

router = APIRouter()

_ACTIVITY_CATEGORIES = frozenset({"mission", "approval", "execution", "attention", "memory"})

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
            detail="category must be one of: mission, approval, execution, attention, memory",
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
