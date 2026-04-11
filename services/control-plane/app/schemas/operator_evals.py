"""Operator Value Evals v1 — structured aggregates from control-plane mission truth."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvalDataQuality(BaseModel):
    """What is stored truth vs derived; honesty about small samples."""

    direct_from_store: list[str] = Field(
        default_factory=list,
        description="Row counts and filters applied directly to persisted tables.",
    )
    derived_aggregates: list[str] = Field(
        default_factory=list,
        description="Computed from timestamps, percentiles, or category mapping.",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="e.g. low sample size, metrics not measuring model quality.",
    )


class LatencyStats(BaseModel):
    sample_count: int = 0
    median_seconds: float | None = None
    p90_seconds: float | None = None
    min_seconds: float | None = None
    max_seconds: float | None = None


class MissionEvalMetrics(BaseModel):
    missions_created_in_window: int = 0
    missions_by_status_for_created_cohort: dict[str, int] = Field(default_factory=dict)
    missions_reached_complete_in_window: int = 0
    missions_reached_failed_in_window: int = 0
    time_created_to_first_receipt: LatencyStats = Field(default_factory=LatencyStats)
    time_created_to_first_integration_executed: LatencyStats = Field(default_factory=LatencyStats)


class ApprovalEvalMetrics(BaseModel):
    approvals_requested_in_window: int = 0
    approvals_resolved_in_window: int = 0
    approvals_denied_in_window: int = 0
    turnaround_seconds: LatencyStats = Field(default_factory=LatencyStats)
    pending_now: int = 0
    pending_age_under_1h: int = 0
    pending_age_1h_to_24h: int = 0
    pending_age_over_24h: int = 0


class IntegrationWorkflowCounts(BaseModel):
    github_issue_created: int = 0
    github_issue_failed: int = 0
    github_pull_request_created: int = 0
    github_pull_request_failed: int = 0
    github_pull_request_merged: int = 0
    github_pull_request_merge_failed: int = 0
    gmail_draft_created: int = 0
    gmail_draft_failed: int = 0
    gmail_reply_draft_created: int = 0
    gmail_reply_draft_failed: int = 0
    gmail_draft_sent: int = 0
    gmail_draft_send_failed: int = 0


class FailureCategoryCounts(BaseModel):
    """Normalized from receipt payload error_code and approval_denied events."""

    missing_auth: int = 0
    provider_http_error: int = 0
    validation_error: int = 0
    approval_denied: int = 0
    timeout: int = 0
    unknown: int = 0


class HeartbeatEvalMetrics(BaseModel):
    findings_first_seen_in_window: int = 0
    findings_resolved_in_window: int = 0
    open_findings_by_finding_type: dict[str, int] = Field(default_factory=dict)
    open_findings_total: int = 0


class RoutingEvalMetrics(BaseModel):
    routing_decided_events_in_window: int = 0
    requested_matches_actual_lane: int = 0
    requested_differs_actual_lane: int = 0
    local_fast_to_gateway_fallback: int = 0
    requested_local_fast: int = 0
    routing_actual_gateway: int = 0


class EvalDayBucket(BaseModel):
    day_utc: str
    missions_created: int = 0
    missions_reached_complete: int = 0
    missions_reached_failed: int = 0


class OperatorValueEvalsSummary(BaseModel):
    window_start_utc: str
    window_end_utc: str
    window_hours: int
    notes: list[str] = Field(default_factory=list)


class WorkerRegistryEvalMetrics(BaseModel):
    """Snapshot from workers table (same threshold as supervision stale_worker)."""

    registered_total: int = 0
    healthy_heartbeat: int = 0
    stale_or_absent: int = 0
    threshold_minutes: float = 15.0


class OperatorValueEvalsResponse(BaseModel):
    generated_at: str
    window_hours: int
    group_by: str | None = None
    summary: OperatorValueEvalsSummary
    data_quality: EvalDataQuality
    mission_metrics: MissionEvalMetrics
    approval_metrics: ApprovalEvalMetrics
    integration_metrics: IntegrationWorkflowCounts
    failure_categories: FailureCategoryCounts
    heartbeat_metrics: HeartbeatEvalMetrics
    routing_metrics: RoutingEvalMetrics
    worker_registry_metrics: WorkerRegistryEvalMetrics
    timeseries: list[EvalDayBucket] = Field(default_factory=list)
