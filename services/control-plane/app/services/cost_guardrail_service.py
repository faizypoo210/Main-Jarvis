"""Cost guardrails — explicit thresholds on cost_events; heartbeat findings only, no invented budgets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.cost_guardrails import (
    CostGuardrailBreachActive,
    CostGuardrailConfigRead,
    OperatorCostGuardrailsResponse,
)
from app.schemas.heartbeat import HeartbeatFindingRead


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def cost_guardrail_config() -> dict[str, Any]:
    """Env-backed thresholds; 0 disables a check (documented in .env.example)."""
    return {
        "window_hours": _float_env("HEARTBEAT_COST_WINDOW_HOURS", 24.0),
        "direct_usd_threshold": _float_env("HEARTBEAT_COST_DIRECT_USD_THRESHOLD", 100.0),
        "estimated_usd_threshold": _float_env("HEARTBEAT_COST_ESTIMATED_USD_THRESHOLD", 100.0),
        "unknown_count_threshold": float(_int_env("HEARTBEAT_COST_UNKNOWN_COUNT_THRESHOLD", 50)),
        "provider_concentration_pct_threshold": _float_env(
            "HEARTBEAT_COST_PROVIDER_CONCENTRATION_THRESHOLD_PCT", 80.0
        ),
        "min_events_for_concentration": _int_env("HEARTBEAT_COST_MIN_EVENTS_FOR_CONCENTRATION", 5),
    }


def _dec(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


async def compute_window_metrics(
    session: AsyncSession, *, window_start: datetime
) -> dict[str, Any]:
    """Rollups from cost_events for the sliding window (same basis as guardrail checks)."""
    r = await session.execute(
        text(
            """
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
            WHERE created_at >= :start
            """
        ),
        {"start": window_start},
    )
    row = r.one()
    direct_usd = _dec(row[0])
    est_usd = _dec(row[1])
    unknown_n = int(row[2] or 0)
    na_n = int(row[3] or 0)
    total_n = int(row[4] or 0)

    r2 = await session.execute(
        text(
            """
            SELECT COALESCE(provider, 'unset') AS p,
                   COALESCE(SUM(amount) FILTER (
                     WHERE cost_status IN ('direct', 'estimated') AND currency = 'USD'
                   ), 0) AS amt
            FROM cost_events
            WHERE created_at >= :start
            GROUP BY 1
            """
        ),
        {"start": window_start},
    )
    by_prov: dict[str, Decimal] = {}
    for p, amt in r2.fetchall():
        by_prov[str(p)] = _dec(amt)
    total_spend = sum(by_prov.values(), start=Decimal("0"))
    dominant: str | None = None
    dominant_pct: float | None = None
    if total_spend > 0 and by_prov:
        top_p = max(by_prov.items(), key=lambda x: x[1])
        dominant = top_p[0]
        dominant_pct = float((top_p[1] / total_spend) * 100) if total_spend > 0 else None

    return {
        "window_start_utc": window_start.isoformat().replace("+00:00", "Z"),
        "direct_total_usd": direct_usd,
        "estimated_total_usd": est_usd,
        "unknown_count": unknown_n,
        "not_applicable_count": na_n,
        "events_total": total_n,
        "provider_spend_usd": {k: str(v) for k, v in by_prov.items()},
        "dominant_provider": dominant,
        "dominant_provider_spend_pct": dominant_pct,
    }


@dataclass(frozen=True)
class _CostCandidate:
    """Mirror heartbeat _Candidate fields for cost guardrail layer."""

    dedupe_key: str
    finding_type: str
    severity: str
    summary: str
    provenance_note: str


async def collect_cost_guardrail_candidates(
    session: AsyncSession, now: datetime
) -> list[_CostCandidate]:
    """Evaluate cost_events in HEARTBEAT_COST_WINDOW_HOURS; emit at most one finding per guardrail type."""
    cfg = cost_guardrail_config()
    wh = max(1.0, float(cfg["window_hours"]))
    start = now - timedelta(hours=wh)
    metrics = await compute_window_metrics(session, window_start=start)
    direct_usd = Decimal(metrics["direct_total_usd"])
    est_usd = Decimal(metrics["estimated_total_usd"])
    unknown_n = int(metrics["unknown_count"])
    total_n = int(metrics["events_total"])
    dom_pct = metrics["dominant_provider_spend_pct"]
    dom_p = metrics["dominant_provider"]

    out: list[_CostCandidate] = []

    d_thr = float(cfg["direct_usd_threshold"])
    if d_thr > 0 and direct_usd > Decimal(str(d_thr)):
        prov = (
            f"Direct USD sum {direct_usd} in last {wh:.0f}h from cost_events "
            f"(cost_status=direct, currency=USD). Threshold {d_thr} from HEARTBEAT_COST_DIRECT_USD_THRESHOLD."
        )
        out.append(
            _CostCandidate(
                dedupe_key="cost_guardrail:direct_usd",
                finding_type="cost_direct_spend_high",
                severity="medium",
                summary=(
                    f"Direct spend in rolling window exceeds threshold: "
                    f"{direct_usd} USD over {wh:.0f}h (threshold {d_thr})."
                ),
                provenance_note=prov,
            )
        )

    e_thr = float(cfg["estimated_usd_threshold"])
    if e_thr > 0 and est_usd > Decimal(str(e_thr)):
        prov = (
            f"Estimated USD sum {est_usd} in last {wh:.0f}h from cost_events "
            f"(cost_status=estimated, currency=USD). Threshold {e_thr} from HEARTBEAT_COST_ESTIMATED_USD_THRESHOLD."
        )
        out.append(
            _CostCandidate(
                dedupe_key="cost_guardrail:estimated_usd",
                finding_type="cost_estimated_spend_high",
                severity="medium",
                summary=(
                    f"Estimated spend in rolling window exceeds threshold: "
                    f"{est_usd} USD over {wh:.0f}h (threshold {e_thr})."
                ),
                provenance_note=prov,
            )
        )

    u_thr = int(cfg["unknown_count_threshold"])
    if u_thr > 0 and unknown_n >= u_thr:
        prov = (
            f"Unknown-cost event count {unknown_n} in last {wh:.0f}h (cost_status=unknown). "
            f"Threshold {u_thr} from HEARTBEAT_COST_UNKNOWN_COUNT_THRESHOLD. "
            "Unknown means USD was not recorded on the receipt — hygiene signal, not an amount estimate."
        )
        out.append(
            _CostCandidate(
                dedupe_key="cost_guardrail:unknown_count",
                finding_type="cost_unknown_spike",
                severity="low",
                summary=(
                    f"High count of unknown-cost events: {unknown_n} in {wh:.0f}h "
                    f"(threshold {u_thr}). Review execution receipts for missing usage or USD fields."
                ),
                provenance_note=prov,
            )
        )

    pct_thr = float(cfg["provider_concentration_pct_threshold"])
    min_ev = int(cfg["min_events_for_concentration"])
    if (
        pct_thr > 0
        and pct_thr <= 100.0
        and total_n >= min_ev
        and dom_pct is not None
        and dom_pct >= pct_thr
        and dom_p is not None
    ):
        prov = (
            f"Dominant provider «{dom_p}» accounts for {dom_pct:.1f}% of direct+estimated USD in window "
            f"(min {min_ev} cost_events required). Threshold {pct_thr}% from "
            "HEARTBEAT_COST_PROVIDER_CONCENTRATION_THRESHOLD_PCT."
        )
        out.append(
            _CostCandidate(
                dedupe_key="cost_guardrail:provider_concentration",
                finding_type="cost_provider_concentration",
                severity="low",
                summary=(
                    f"Spend concentration: provider «{dom_p}» is about {dom_pct:.1f}% of "
                    f"direct and estimated USD in the last {wh:.0f}h (threshold {pct_thr}% of total)."
                ),
                provenance_note=prov,
            )
        )

    return out


def compute_breach_flags(metrics: dict[str, Any], cfg: dict[str, Any]) -> dict[str, bool]:
    """Same boolean logic as collect_cost_guardrail_candidates (for operator UI)."""
    direct_usd = Decimal(str(metrics["direct_total_usd"]))
    est_usd = Decimal(str(metrics["estimated_total_usd"]))
    unknown_n = int(metrics["unknown_count"])
    total_n = int(metrics["events_total"])
    dom_pct = metrics.get("dominant_provider_spend_pct")
    dom_p = metrics.get("dominant_provider")

    d_thr = float(cfg["direct_usd_threshold"])
    e_thr = float(cfg["estimated_usd_threshold"])
    u_thr = int(cfg["unknown_count_threshold"])
    pct_thr = float(cfg["provider_concentration_pct_threshold"])
    min_ev = int(cfg["min_events_for_concentration"])

    return {
        "direct_spend_high": d_thr > 0 and direct_usd > Decimal(str(d_thr)),
        "estimated_spend_high": e_thr > 0 and est_usd > Decimal(str(e_thr)),
        "unknown_spike": u_thr > 0 and unknown_n >= u_thr,
        "provider_concentration": (
            pct_thr > 0
            and pct_thr <= 100.0
            and total_n >= min_ev
            and dom_pct is not None
            and dom_pct >= pct_thr
            and dom_p is not None
        ),
    }


async def build_operator_cost_guardrails_response(
    session: AsyncSession,
) -> OperatorCostGuardrailsResponse:
    from app.repositories.heartbeat_finding_repo import HeartbeatFindingRepository

    now = datetime.now(UTC)
    cfg = cost_guardrail_config()
    wh = max(1.0, float(cfg["window_hours"]))
    start = now - timedelta(hours=wh)
    metrics = await compute_window_metrics(session, window_start=start)
    breach = compute_breach_flags(metrics, cfg)

    m_json: dict[str, Any] = {
        "window_hours": wh,
        "window_start_utc": metrics["window_start_utc"],
        "direct_total_usd": str(metrics["direct_total_usd"]),
        "estimated_total_usd": str(metrics["estimated_total_usd"]),
        "unknown_count": metrics["unknown_count"],
        "not_applicable_count": metrics["not_applicable_count"],
        "events_total": metrics["events_total"],
        "provider_spend_usd": metrics["provider_spend_usd"],
        "dominant_provider": metrics["dominant_provider"],
        "dominant_provider_spend_pct": metrics["dominant_provider_spend_pct"],
    }

    open_rows = await HeartbeatFindingRepository.list_open(session)
    cost_open = [x for x in open_rows if str(x.finding_type).startswith("cost_")]
    recent = await HeartbeatFindingRepository.list_resolved_cost_findings_recent(
        session, limit=8
    )

    cfg_read = CostGuardrailConfigRead(
        window_hours=float(cfg["window_hours"]),
        direct_usd_threshold=float(cfg["direct_usd_threshold"]),
        estimated_usd_threshold=float(cfg["estimated_usd_threshold"]),
        unknown_count_threshold=float(cfg["unknown_count_threshold"]),
        provider_concentration_pct_threshold=float(cfg["provider_concentration_pct_threshold"]),
        min_events_for_concentration=int(cfg["min_events_for_concentration"]),
    )

    return OperatorCostGuardrailsResponse(
        generated_at=now.isoformat().replace("+00:00", "Z"),
        config=cfg_read,
        metrics=m_json,
        breach_active=CostGuardrailBreachActive(**breach),
        open_cost_findings=[HeartbeatFindingRead.model_validate(x) for x in cost_open],
        recent_resolved_cost_findings=[HeartbeatFindingRead.model_validate(x) for x in recent],
    )
