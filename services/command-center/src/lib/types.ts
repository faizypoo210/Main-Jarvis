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

export interface SystemHealthResponse {
  checked_at: string;
  control_plane: ComponentHealth;
  postgres: ComponentHealth;
  redis: ComponentHealth;
  openclaw_gateway: ComponentHealth;
  ollama: ComponentHealth;
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
