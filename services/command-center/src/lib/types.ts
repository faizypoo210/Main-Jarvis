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
