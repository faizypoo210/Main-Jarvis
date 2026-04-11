"""Operator cost event listing + rollups."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_event import CostEvent
from app.schemas.cost_events import (
    CostEventRead,
    CostEventRollup,
    OperatorCostEventsResponse,
)


def _dec(v: object | None) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


async def fetch_operator_cost_events(
    session: AsyncSession,
    *,
    provider: str | None = None,
    cost_status: str | None = None,
    mission_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> OperatorCostEventsResponse:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    clauses: list[str] = ["1=1"]
    params: dict[str, object] = {"lim": limit, "off": offset}

    if provider is not None and str(provider).strip():
        clauses.append("provider = :provider")
        params["provider"] = str(provider).strip()
    if cost_status is not None and str(cost_status).strip():
        clauses.append("cost_status = :cost_status")
        params["cost_status"] = str(cost_status).strip()
    if mission_id is not None:
        clauses.append("mission_id = :mission_id")
        params["mission_id"] = mission_id

    where_sql = " AND ".join(clauses)

    r = await session.execute(
        text(
            f"""
            SELECT
              COALESCE(SUM(amount) FILTER (
                WHERE cost_status = 'direct' AND currency = 'USD'
              ), 0) AS direct_usd,
              COALESCE(SUM(amount) FILTER (
                WHERE cost_status = 'estimated' AND currency = 'USD'
              ), 0) AS est_usd,
              COUNT(*) FILTER (WHERE cost_status = 'unknown')::int AS unknown_n,
              COUNT(*) FILTER (WHERE cost_status = 'not_applicable')::int AS na_n,
              COUNT(*)::int AS total_n
            FROM cost_events
            WHERE {where_sql}
            """
        ),
        params,
    )
    row = r.one()
    rollup = CostEventRollup(
        direct_total_usd=_dec(row[0]),
        estimated_total_usd=_dec(row[1]),
        unknown_count=int(row[2] or 0),
        not_applicable_count=int(row[3] or 0),
        events_total=int(row[4] or 0),
    )

    pb_params = {k: v for k, v in params.items() if k not in ("lim", "off")}
    r2 = await session.execute(
        text(
            f"""
            SELECT COALESCE(provider, 'unset') AS p, COUNT(*)::int AS c
            FROM cost_events
            WHERE {where_sql}
            GROUP BY 1
            ORDER BY c DESC
            """
        ),
        pb_params,
    )
    provider_breakdown = {str(x[0]): int(x[1]) for x in r2.fetchall()}

    r3 = await session.execute(
        text(
            f"""
            SELECT id FROM cost_events
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT :lim OFFSET :off
            """
        ),
        params,
    )
    ids = [row[0] for row in r3.fetchall()]
    events: list[CostEventRead] = []
    if ids:
        stmt = select(CostEvent).where(CostEvent.id.in_(ids))
        ores = await session.execute(stmt)
        objs = list(ores.scalars().all())
        order = {i: n for n, i in enumerate(ids)}
        objs.sort(key=lambda o: order[o.id])
        events = [CostEventRead.model_validate(x) for x in objs]

    return OperatorCostEventsResponse(
        generated_at=now,
        rollup=rollup,
        provider_breakdown=provider_breakdown,
        events=events,
    )
