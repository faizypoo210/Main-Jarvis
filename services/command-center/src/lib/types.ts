/** Mirrors control-plane Pydantic schemas (MissionRead, MissionEventRead, ApprovalRead, ReceiptRead, CommandResponse). */

export type UUID = string;

export interface Mission {
  id: UUID;
  title: string;
  description: string | null;
  status: string;
  priority: string;
  created_by: string;
  surface_origin: string | null;
  risk_class: string | null;
  current_stage: string | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface MissionEvent {
  id: UUID;
  mission_id: UUID;
  event_type: string;
  actor_type: string | null;
  actor_id: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface Approval {
  id: UUID;
  mission_id: UUID;
  action_type: string;
  risk_class: string;
  reason: string | null;
  command_text: string | null;
  dashclaw_decision_id: string | null;
  status: string;
  requested_by: string;
  requested_via: string;
  decided_by: string | null;
  decided_via: string | null;
  decision_notes: string | null;
  created_at: string;
  decided_at: string | null;
  expires_at: string | null;
}

/** GET /api/v1/approvals/:id/bundle — Approval Review Packets v1 */
export interface PacketField {
  label: string;
  value: string;
}

export interface ApprovalReviewPacket {
  kind: string;
  action_type: string;
  headline: string;
  subheadline?: string | null;
  action_kind?: string | null;
  operator_effect?: string | null;
  target_summary?: string | null;
  identity_bearing?: boolean | null;
  fields: PacketField[];
  brief_summary: string;
  spoken_summary: string;
  preflight_summary?: string | null;
  preflight_available: boolean;
  parse_ok: boolean;
  parse_note?: string | null;
}

export interface ApprovalContextBlock {
  requested_by: string;
  requested_via: string;
  risk_class: string;
  created_at: string;
  age_seconds: number;
  mission_id: UUID;
  mission_title?: string | null;
  mission_status?: string | null;
  mission_link?: string | null;
  identity_bearing: boolean;
  reason_line?: string | null;
}

export interface MissionEventSnippet {
  id: UUID;
  event_type: string;
  created_at: string;
  summary: string;
}

export interface ReceiptSnippet {
  id: UUID;
  receipt_type: string;
  created_at: string;
  summary?: string | null;
}

export interface BundleDataQuality {
  direct_from_store: string[];
  derived: string[];
  notes: string[];
}

export interface ApprovalBundleResponse {
  generated_at: string;
  approval: Approval;
  mission: Mission | null;
  context: ApprovalContextBlock;
  packet: ApprovalReviewPacket;
  recent_events: MissionEventSnippet[];
  related_receipts: ReceiptSnippet[];
  data_quality: BundleDataQuality;
  notes: string[];
}

export interface Receipt {
  id: UUID;
  mission_id: UUID | null;
  receipt_type: string;
  source: string;
  payload: Record<string, unknown>;
  summary: string | null;
  created_at: string;
}

export interface CommandResponse {
  mission_id: UUID;
  mission_status: string;
  message: string;
}

/** GET /missions/:id/bundle */
export interface MissionBundle {
  mission: Mission;
  events: MissionEvent[];
  approvals: Approval[];
  receipts: Receipt[];
}

/** GET /api/v1/system/health */
export type HealthState = "healthy" | "degraded" | "offline" | "unknown";

export interface ComponentHealth {
  status: HealthState;
  detail: string | null;
}

export interface WorkerRegistrySummary {
  registered_total: number;
  healthy_heartbeat: number;
  stale_or_absent: number;
  threshold_minutes: number;
}

export interface SystemHealthResponse {
  checked_at: string;
  control_plane: ComponentHealth;
  postgres: ComponentHealth;
  redis: ComponentHealth;
  openclaw_gateway: ComponentHealth;
  ollama: ComponentHealth;
  worker_registry: WorkerRegistrySummary;
}

/** GET /api/v1/operator/workers */
export interface WorkerRead {
  id: UUID;
  worker_type: string;
  instance_id: string;
  name: string;
  status: string;
  host: string | null;
  version: string | null;
  last_heartbeat_at: string | null;
  started_at: string | null;
  last_error: string | null;
  updated_at: string;
  meta: Record<string, unknown> | null;
}

export interface OperatorWorkersResponse {
  generated_at: string;
  workers: WorkerRead[];
  stale_threshold_minutes: number;
}

/** GET /api/v1/operator/usage */
export interface MissionStatusCount {
  status: string;
  count: number;
}

export interface LaneCount {
  lane: string;
  count: number;
}

export interface DailyReceiptCount {
  day: string;
  count: number;
}

export interface OperatorUsageResponse {
  generated_at: string;
  missions_total: number;
  missions_by_status: MissionStatusCount[];
  receipts_total: number;
  receipts_by_type: Record<string, number>;
  openclaw_execution_receipts: number;
  openclaw_success: number;
  openclaw_failure: number;
  openclaw_success_unknown: number;
  lane_distribution: LaneCount[];
  receipts_by_day_utc: DailyReceiptCount[];
  last_mission_event_at: string | null;
  last_receipt_at: string | null;
  last_openclaw_execution_at: string | null;
}

/** GET /api/v1/operator/activity */
export type ActivityFeedCategory =
  | "mission"
  | "approval"
  | "execution"
  | "attention"
  | "memory"
  | "heartbeat";

export interface ActivitySummary {
  window_hours: number;
  total_in_window: number;
  approvals_in_window: number;
  execution_in_window: number;
  attention_in_window: number;
  /** Present on control planes that expose memory timeline counts. */
  memory_in_window?: number;
  /** Open heartbeat supervision findings (deduped). */
  heartbeat_open_total?: number;
}

/** GET /api/v1/operator/heartbeat */
export interface HeartbeatFindingRead {
  id: UUID;
  finding_type: string;
  severity: string;
  summary: string;
  dedupe_key: string;
  mission_id: UUID | null;
  approval_id: UUID | null;
  worker_id: UUID | null;
  integration_id: UUID | null;
  service_component: string | null;
  provenance_note: string | null;
  status: string;
  first_seen_at: string;
  last_seen_at: string;
  resolved_at: string | null;
}

export interface HeartbeatOperatorResponse {
  generated_at: string;
  open_count: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  open_findings: HeartbeatFindingRead[];
}

export interface OperatorActivityItem {
  id: string;
  occurred_at: string;
  kind: string;
  category: string;
  title: string;
  summary: string;
  status: string;
  mission_id: string;
  mission_title: string;
  actor_label: string | null;
  risk_class: string | null;
  meta: Record<string, unknown>;
}

export interface OperatorActivityResponse {
  generated_at: string;
  summary: ActivitySummary;
  items: OperatorActivityItem[];
  next_before: string | null;
}

/** GET /api/v1/operator/integrations */
export interface IntegrationHubSummary {
  total: number;
  connected: number;
  needs_auth: number;
  not_configured_or_unknown: number;
}

export interface OperatorIntegrationRow {
  id: string;
  name: string;
  kind: string;
  provider: string;
  status: string;
  connection_source: string;
  last_checked_at: string | null;
  last_activity_at: string | null;
  summary: string;
  next_action: string;
  meta: Record<string, unknown>;
}

export interface OperatorIntegrationsResponse {
  generated_at: string;
  summary: IntegrationHubSummary;
  items: OperatorIntegrationRow[];
  truth_notes: string[];
}

/** GET /api/v1/operator/memory */
export interface MemoryItemRead {
  id: UUID;
  memory_type: string;
  title: string;
  summary: string | null;
  content: string | null;
  status: string;
  importance: number;
  source_kind: string;
  source_mission_id: UUID | null;
  source_receipt_id: UUID | null;
  source_event_id: UUID | null;
  tags: string[];
  dedupe_key: string | null;
  created_at: string;
  updated_at: string;
  last_reviewed_at: string | null;
}

export interface MemoryListResponse {
  items: MemoryItemRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface MemoryCountsResponse {
  by_type: Record<string, number>;
  active: number;
  archived: number;
}

/** GET /api/v1/operator/evals — Operator Value Evals v1 */
export interface EvalLatencyStats {
  sample_count: number;
  median_seconds: number | null;
  p90_seconds: number | null;
  min_seconds: number | null;
  max_seconds: number | null;
}

export interface OperatorValueEvalsSummary {
  window_start_utc: string;
  window_end_utc: string;
  window_hours: number;
  notes: string[];
}

export interface EvalDataQuality {
  direct_from_store: string[];
  derived_aggregates: string[];
  caveats: string[];
}

export interface MissionEvalMetrics {
  missions_created_in_window: number;
  missions_by_status_for_created_cohort: Record<string, number>;
  missions_reached_complete_in_window: number;
  missions_reached_failed_in_window: number;
  time_created_to_first_receipt: EvalLatencyStats;
  time_created_to_first_integration_executed: EvalLatencyStats;
}

export interface ApprovalEvalMetrics {
  approvals_requested_in_window: number;
  approvals_resolved_in_window: number;
  approvals_denied_in_window: number;
  turnaround_seconds: EvalLatencyStats;
  pending_now: number;
  pending_age_under_1h: number;
  pending_age_1h_to_24h: number;
  pending_age_over_24h: number;
}

export interface IntegrationWorkflowCounts {
  github_issue_created: number;
  github_issue_failed: number;
  github_pull_request_created: number;
  github_pull_request_failed: number;
  github_pull_request_merged: number;
  github_pull_request_merge_failed: number;
  gmail_draft_created: number;
  gmail_draft_failed: number;
  gmail_reply_draft_created: number;
  gmail_reply_draft_failed: number;
  gmail_draft_sent: number;
  gmail_draft_send_failed: number;
}

export interface FailureCategoryCounts {
  missing_auth: number;
  provider_http_error: number;
  validation_error: number;
  approval_denied: number;
  timeout: number;
  unknown: number;
}

export interface HeartbeatEvalMetrics {
  findings_first_seen_in_window: number;
  findings_resolved_in_window: number;
  open_findings_by_finding_type: Record<string, number>;
  open_findings_total: number;
}

export interface RoutingEvalMetrics {
  routing_decided_events_in_window: number;
  requested_matches_actual_lane: number;
  requested_differs_actual_lane: number;
  local_fast_to_gateway_fallback: number;
  requested_local_fast: number;
  routing_actual_gateway: number;
}

export interface EvalDayBucket {
  day_utc: string;
  missions_created: number;
  missions_reached_complete: number;
  missions_reached_failed: number;
}

export interface WorkerRegistryEvalMetrics {
  registered_total: number;
  healthy_heartbeat: number;
  stale_or_absent: number;
  threshold_minutes: number;
}

/** GET /api/v1/operator/cost-events */
export interface CostEventRead {
  id: string;
  mission_id: string | null;
  source_kind: string;
  source_receipt_id: string | null;
  provider: string | null;
  operation: string | null;
  amount: string | number | null;
  currency: string | null;
  cost_status: string;
  usage_tokens_input: number | null;
  usage_tokens_output: number | null;
  usage_units: Record<string, unknown> | null;
  notes: string | null;
  created_at: string;
}

export interface CostEventRollup {
  direct_total_usd: string | number;
  estimated_total_usd: string | number;
  unknown_count: number;
  not_applicable_count: number;
  events_total: number;
}

export interface OperatorCostEventsResponse {
  generated_at: string;
  rollup: CostEventRollup;
  provider_breakdown: Record<string, number>;
  events: CostEventRead[];
}

export interface CostEventEvalMetrics {
  events_in_window: number;
  direct_count: number;
  estimated_count: number;
  unknown_count: number;
  not_applicable_count: number;
  direct_total_usd: string | number;
  estimated_total_usd: string | number;
  provider_breakdown: Record<string, number>;
}

export interface CostGuardrailEvalMetrics {
  cost_findings_opened_in_window: number;
  cost_findings_resolved_in_window: number;
  open_cost_findings_now: number;
}

/** GET /api/v1/operator/cost-guardrails */
export interface CostGuardrailConfigRead {
  window_hours: number;
  direct_usd_threshold: number;
  estimated_usd_threshold: number;
  unknown_count_threshold: number;
  provider_concentration_pct_threshold: number;
  min_events_for_concentration: number;
}

export interface CostGuardrailBreachActive {
  direct_spend_high: boolean;
  estimated_spend_high: boolean;
  unknown_spike: boolean;
  provider_concentration: boolean;
}

export interface OperatorCostGuardrailsResponse {
  generated_at: string;
  config: CostGuardrailConfigRead;
  metrics: Record<string, unknown>;
  breach_active: CostGuardrailBreachActive;
  open_cost_findings: HeartbeatFindingRead[];
  recent_resolved_cost_findings: HeartbeatFindingRead[];
}

export interface OperatorValueEvalsResponse {
  generated_at: string;
  window_hours: number;
  group_by: string | null;
  summary: OperatorValueEvalsSummary;
  data_quality: EvalDataQuality;
  mission_metrics: MissionEvalMetrics;
  approval_metrics: ApprovalEvalMetrics;
  integration_metrics: IntegrationWorkflowCounts;
  failure_categories: FailureCategoryCounts;
  heartbeat_metrics: HeartbeatEvalMetrics;
  routing_metrics: RoutingEvalMetrics;
  worker_registry_metrics: WorkerRegistryEvalMetrics;
  cost_event_metrics: CostEventEvalMetrics;
  cost_guardrail_metrics: CostGuardrailEvalMetrics;
  timeseries: EvalDayBucket[];
}
