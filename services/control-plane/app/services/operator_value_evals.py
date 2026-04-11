"""Operator Value Evals v1 — SQL aggregates over missions, events, receipts, approvals, heartbeat."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.operator_evals import (
    ApprovalEvalMetrics,
    EvalDataQuality,
    EvalDayBucket,
    FailureCategoryCounts,
    HeartbeatEvalMetrics,
    IntegrationWorkflowCounts,
    LatencyStats,
    MissionEvalMetrics,
    OperatorValueEvalsResponse,
    OperatorValueEvalsSummary,
    RoutingEvalMetrics,
)

_MAX_WINDOW_H = 720


def _percentile_linear(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * (p / 100.0)
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def _latency_stats(seconds: list[float]) -> LatencyStats:
    if not seconds:
        return LatencyStats()
    s = sorted(seconds)
    return LatencyStats(
        sample_count=len(s),
        median_seconds=_percentile_linear(s, 50),
        p90_seconds=_percentile_linear(s, 90),
        min_seconds=min(s),
        max_seconds=max(s),
    )


def _categorize_error_code(code: str | None) -> str:
    if not code or not str(code).strip():
        return "unknown"
    c = str(code).strip().lower()
    if c in ("missing_token", "missing_gmail_auth", "missing_github_token"):
        return "missing_auth"
    if "missing" in c and "auth" in c:
        return "missing_auth"
    if c.startswith("gmail_http_") or c.startswith("github_http_") or c == "http_error":
        return "provider_http_error"
    if c in (
        "invalid_contract",
        "missing_contract",
        "invalid_draft_id",
        "message_not_found",
        "no_reply_recipient",
        "missing_rfc_message_id",
    ):
        return "validation_error"
    if "timeout" in c or c == "timeout":
        return "timeout"
    return "unknown"


async def build_operator_value_evals(
    session: AsyncSession,
    *,
    window_hours: int,
    group_by: str | None,
) -> OperatorValueEvalsResponse:
    wh = max(1, min(window_hours, _MAX_WINDOW_H))
    end = datetime.now(UTC)
    start = end - timedelta(hours=wh)
    start_s = start.isoformat().replace("+00:00", "Z")
    end_s = end.isoformat().replace("+00:00", "Z")

    notes: list[str] = [
        "Does not measure model or reply quality — only operational signals from stored mission truth.",
        "Latency medians need missions with receipts/events; small samples are labeled in caveats.",
    ]
    caveats: list[str] = []
    direct: list[str] = [
        "Mission/receipt/event/approval/heartbeat row counts filtered by created_at (or decided_at) in the UTC window.",
        "Open heartbeat counts are current snapshots (not window-limited).",
    ]
    derived: list[str] = [
        "Median/p90 seconds from per-mission deltas (mission created_at to first child row).",
        "failure_categories mapped from payload error_code via small heuristic rules.",
        "routing match/mismatch from routing_decided payload fields.",
        "requested_local_fast / routing_actual_gateway: row counts on routing_decided (mission path class vs classifier intent).",
        "OpenClaw model lane (local vs cloud target) is on executor receipts (execution_meta), not duplicated in routing_decided.",
    ]

    bind = {"start": start, "end": end}

    # --- Missions created in window + status cohort (current status of those missions)
    r = await session.execute(
        text(
            """
            SELECT status, COUNT(*)::int AS c
            FROM missions
            WHERE created_at >= :start AND created_at < :end
            GROUP BY status
            """
        ),
        bind,
    )
    cohort_status: dict[str, int] = {str(row[0]): int(row[1]) for row in r.fetchall()}
    missions_created = sum(cohort_status.values())

    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM missions
            WHERE status = 'complete' AND updated_at >= :start AND updated_at < :end
            """
        ),
        bind,
    )
    complete_terminal = int(r.scalar_one() or 0)

    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM missions
            WHERE status = 'failed' AND updated_at >= :start AND updated_at < :end
            """
        ),
        bind,
    )
    failed_terminal = int(r.scalar_one() or 0)

    # Time to first receipt (missions created in window, at least one receipt)
    r = await session.execute(
        text(
            """
            SELECT EXTRACT(EPOCH FROM (MIN(r.created_at) - m.created_at))::float AS dt
            FROM missions m
            INNER JOIN receipts r ON r.mission_id = m.id
            WHERE m.created_at >= :start AND m.created_at < :end
            GROUP BY m.id, m.created_at
            """
        ),
        bind,
    )
    receipt_deltas = [float(row[0]) for row in r.fetchall() if row[0] is not None]
    if len(receipt_deltas) < 5 and missions_created >= 3:
        caveats.append(
            f"Time-to-first-receipt sample_count={len(receipt_deltas)}; interpret medians cautiously."
        )

    # Time to first integration_action_executed
    r = await session.execute(
        text(
            """
            SELECT EXTRACT(EPOCH FROM (MIN(e.created_at) - m.created_at))::float AS dt
            FROM missions m
            INNER JOIN mission_events e ON e.mission_id = m.id AND e.event_type = 'integration_action_executed'
            WHERE m.created_at >= :start AND m.created_at < :end
            GROUP BY m.id, m.created_at
            """
        ),
        bind,
    )
    integ_deltas = [float(row[0]) for row in r.fetchall() if row[0] is not None]

    mission_metrics = MissionEvalMetrics(
        missions_created_in_window=missions_created,
        missions_by_status_for_created_cohort=cohort_status,
        missions_reached_complete_in_window=complete_terminal,
        missions_reached_failed_in_window=failed_terminal,
        time_created_to_first_receipt=_latency_stats(receipt_deltas),
        time_created_to_first_integration_executed=_latency_stats(integ_deltas),
    )

    # --- Approvals
    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM approvals
            WHERE created_at >= :start AND created_at < :end
            """
        ),
        bind,
    )
    appr_req = int(r.scalar_one() or 0)

    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM approvals
            WHERE decided_at IS NOT NULL AND decided_at >= :start AND decided_at < :end
            """
        ),
        bind,
    )
    appr_res = int(r.scalar_one() or 0)

    r = await session.execute(
        text(
            """
            SELECT EXTRACT(EPOCH FROM (decided_at - created_at))::float AS dt
            FROM approvals
            WHERE decided_at IS NOT NULL AND decided_at >= :start AND decided_at < :end
            """
        ),
        bind,
    )
    turn = [float(row[0]) for row in r.fetchall() if row[0] is not None]

    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM mission_events
            WHERE event_type = 'approval_resolved'
              AND payload->>'decision' = 'denied'
              AND created_at >= :start AND created_at < :end
            """
        ),
        bind,
    )
    denied = int(r.scalar_one() or 0)

    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM approvals WHERE status = 'pending'
            """
        )
    )
    pending_now = int(r.scalar_one() or 0)

    r = await session.execute(
        text(
            """
            SELECT
              COUNT(*) FILTER (WHERE NOW() - created_at < INTERVAL '1 hour')::int,
              COUNT(*) FILTER (
                WHERE NOW() - created_at >= INTERVAL '1 hour'
                  AND NOW() - created_at < INTERVAL '24 hours'
              )::int,
              COUNT(*) FILTER (WHERE NOW() - created_at >= INTERVAL '24 hours')::int
            FROM approvals
            WHERE status = 'pending'
            """
        )
    )
    prow = r.one()
    p0, p1, p2 = int(prow[0] or 0), int(prow[1] or 0), int(prow[2] or 0)

    approval_metrics = ApprovalEvalMetrics(
        approvals_requested_in_window=appr_req,
        approvals_resolved_in_window=appr_res,
        approvals_denied_in_window=denied,
        turnaround_seconds=_latency_stats(turn),
        pending_now=pending_now,
        pending_age_under_1h=p0,
        pending_age_1h_to_24h=p1,
        pending_age_over_24h=p2,
    )

    # --- Integration receipt counts (window on receipt created_at)
    integ = IntegrationWorkflowCounts()
    r = await session.execute(
        text(
            """
            SELECT receipt_type, COUNT(*)::int AS c
            FROM receipts
            WHERE created_at >= :start AND created_at < :end
              AND receipt_type IN (
                'github_issue_created', 'github_issue_failed',
                'github_pull_request_created', 'github_pull_request_failed',
                'github_pull_request_merged', 'github_pull_request_merge_failed',
                'gmail_draft_created', 'gmail_draft_failed',
                'gmail_reply_draft_created', 'gmail_reply_draft_failed',
                'gmail_draft_sent', 'gmail_draft_send_failed'
              )
            GROUP BY receipt_type
            """
        ),
        bind,
    )
    rc: dict[str, int] = {str(row[0]): int(row[1]) for row in r.fetchall()}
    integ.github_issue_created = rc.get("github_issue_created", 0)
    integ.github_issue_failed = rc.get("github_issue_failed", 0)
    integ.github_pull_request_created = rc.get("github_pull_request_created", 0)
    integ.github_pull_request_failed = rc.get("github_pull_request_failed", 0)
    integ.github_pull_request_merged = rc.get("github_pull_request_merged", 0)
    integ.github_pull_request_merge_failed = rc.get("github_pull_request_merge_failed", 0)
    integ.gmail_draft_created = rc.get("gmail_draft_created", 0)
    integ.gmail_draft_failed = rc.get("gmail_draft_failed", 0)
    integ.gmail_reply_draft_created = rc.get("gmail_reply_draft_created", 0)
    integ.gmail_reply_draft_failed = rc.get("gmail_reply_draft_failed", 0)
    integ.gmail_draft_sent = rc.get("gmail_draft_sent", 0)
    integ.gmail_draft_send_failed = rc.get("gmail_draft_send_failed", 0)

    # --- Failure categories: integration failure receipts + denied approvals
    fail = FailureCategoryCounts()
    fail.approval_denied = denied

    r = await session.execute(
        text(
            """
            SELECT payload->>'error_code' AS code
            FROM receipts
            WHERE created_at >= :start AND created_at < :end
              AND receipt_type IN (
                'github_issue_failed', 'github_pull_request_failed',
                'github_pull_request_merge_failed',
                'gmail_draft_failed', 'gmail_reply_draft_failed', 'gmail_draft_send_failed'
              )
            """
        ),
        bind,
    )
    for row in r.fetchall():
        cat = _categorize_error_code(row[0])
        if cat == "missing_auth":
            fail.missing_auth += 1
        elif cat == "provider_http_error":
            fail.provider_http_error += 1
        elif cat == "validation_error":
            fail.validation_error += 1
        elif cat == "timeout":
            fail.timeout += 1
        else:
            fail.unknown += 1

    # --- Heartbeat
    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM heartbeat_findings
            WHERE first_seen_at >= :start AND first_seen_at < :end
            """
        ),
        bind,
    )
    hb_first = int(r.scalar_one() or 0)

    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM heartbeat_findings
            WHERE resolved_at IS NOT NULL AND resolved_at >= :start AND resolved_at < :end
            """
        ),
        bind,
    )
    hb_res = int(r.scalar_one() or 0)

    r = await session.execute(
        text(
            """
            SELECT finding_type, COUNT(*)::int AS c
            FROM heartbeat_findings
            WHERE status = 'open'
            GROUP BY finding_type
            ORDER BY c DESC
            """
        )
    )
    hb_open_by: dict[str, int] = {str(row[0]): int(row[1]) for row in r.fetchall()}

    r = await session.execute(
        text("SELECT COUNT(*)::int FROM heartbeat_findings WHERE status = 'open'")
    )
    hb_open_total = int(r.scalar_one() or 0)

    heartbeat_metrics = HeartbeatEvalMetrics(
        findings_first_seen_in_window=hb_first,
        findings_resolved_in_window=hb_res,
        open_findings_by_finding_type=hb_open_by,
        open_findings_total=hb_open_total,
    )

    # --- Routing
    r = await session.execute(
        text(
            """
            SELECT COUNT(*)::int FROM mission_events
            WHERE event_type = 'routing_decided' AND created_at >= :start AND created_at < :end
            """
        ),
        bind,
    )
    rout_n = int(r.scalar_one() or 0)

    r = await session.execute(
        text(
            """
            SELECT
              COUNT(*) FILTER (
                WHERE COALESCE(payload->>'requested_lane','') = COALESCE(payload->>'actual_lane','')
                  AND COALESCE(payload->>'requested_lane','') <> ''
              )::int AS match_n,
              COUNT(*) FILTER (
                WHERE COALESCE(payload->>'requested_lane','') <> COALESCE(payload->>'actual_lane','')
                  AND COALESCE(payload->>'requested_lane','') <> ''
                  AND COALESCE(payload->>'actual_lane','') <> ''
              )::int AS diff_n,
              COUNT(*) FILTER (
                WHERE (payload->>'fallback_applied')::boolean = true
                  AND COALESCE(payload->>'requested_lane','') = 'local_fast'
                  AND COALESCE(payload->>'actual_lane','') = 'gateway'
              )::int AS fb_n,
              COUNT(*) FILTER (
                WHERE COALESCE(payload->>'requested_lane','') = 'local_fast'
              )::int AS req_lf,
              COUNT(*) FILTER (
                WHERE COALESCE(payload->>'actual_lane','') = 'gateway'
              )::int AS act_gw
            FROM mission_events
            WHERE event_type = 'routing_decided' AND created_at >= :start AND created_at < :end
            """
        ),
        bind,
    )
    rw = r.one()
    routing_metrics = RoutingEvalMetrics(
        routing_decided_events_in_window=rout_n,
        requested_matches_actual_lane=int(rw[0] or 0),
        requested_differs_actual_lane=int(rw[1] or 0),
        local_fast_to_gateway_fallback=int(rw[2] or 0),
        requested_local_fast=int(rw[3] or 0),
        routing_actual_gateway=int(rw[4] or 0),
    )

    timeseries: list[EvalDayBucket] = []
    if group_by == "day":
        r = await session.execute(
            text(
                """
                SELECT to_char(date_trunc('day', created_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD') AS d,
                       COUNT(*)::int
                FROM missions
                WHERE created_at >= :start AND created_at < :end
                GROUP BY 1 ORDER BY 1
                """
            ),
            bind,
        )
        created_by_day = {str(row[0]): int(row[1]) for row in r.fetchall()}

        r = await session.execute(
            text(
                """
                SELECT to_char(date_trunc('day', updated_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD') AS d,
                       COUNT(*)::int
                FROM missions
                WHERE status = 'complete' AND updated_at >= :start AND updated_at < :end
                GROUP BY 1 ORDER BY 1
                """
            ),
            bind,
        )
        complete_by_day = {str(row[0]): int(row[1]) for row in r.fetchall()}

        r = await session.execute(
            text(
                """
                SELECT to_char(date_trunc('day', updated_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD') AS d,
                       COUNT(*)::int
                FROM missions
                WHERE status = 'failed' AND updated_at >= :start AND updated_at < :end
                GROUP BY 1 ORDER BY 1
                """
            ),
            bind,
        )
        failed_by_day = {str(row[0]): int(row[1]) for row in r.fetchall()}

        days = sorted(set(created_by_day) | set(complete_by_day) | set(failed_by_day))
        for d in days:
            timeseries.append(
                EvalDayBucket(
                    day_utc=d,
                    missions_created=created_by_day.get(d, 0),
                    missions_reached_complete=complete_by_day.get(d, 0),
                    missions_reached_failed=failed_by_day.get(d, 0),
                )
            )

    if wh >= 168:
        notes.append("Long windows include idle days; prefer shorter windows for active-dev review.")

    return OperatorValueEvalsResponse(
        generated_at=end.isoformat().replace("+00:00", "Z"),
        window_hours=wh,
        group_by=group_by,
        summary=OperatorValueEvalsSummary(
            window_start_utc=start_s,
            window_end_utc=end_s,
            window_hours=wh,
            notes=notes,
        ),
        data_quality=EvalDataQuality(
            direct_from_store=direct,
            derived_aggregates=derived,
            caveats=caveats,
        ),
        mission_metrics=mission_metrics,
        approval_metrics=approval_metrics,
        integration_metrics=integ,
        failure_categories=fail,
        heartbeat_metrics=heartbeat_metrics,
        routing_metrics=routing_metrics,
        timeseries=timeseries,
    )
