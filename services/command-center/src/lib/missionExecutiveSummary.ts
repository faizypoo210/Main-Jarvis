import type { Approval, Mission, MissionEvent, Receipt } from "./types";
import { operatorCopy } from "./operatorCopy";
import { deriveLatestExecutionResult } from "./missionLatestResult";
import { deriveMissionStalenessHint } from "./missionListPriority";
import { deriveOperatorMissionPhase, type OperatorMissionPhase } from "./missionPhase";

/** Pending rows for a mission from the shared approvals list (same source as thread / right panel). */
export function getPendingApprovalsForMission(missionId: string, approvals: Approval[]): Approval[] {
  return approvals.filter((a) => a.mission_id === missionId && a.status === "pending");
}

/** Operator-facing one-screen read on mission state (no extra API). */
export type ExecutiveMissionSummary = {
  status: string;
  /** Derived presentation phase — same as mission detail header / readout (not a second backend field). */
  phase: OperatorMissionPhase;
  phaseLabel: string;
  lastEventLine: string | null;
  lastEventAt: string | null;
  blockerLine: string | null;
  latestReceiptLine: string | null;
  pendingApprovalLine: string | null;
  /** Optional compact queue timing (derived; same anchors as mission list ordering). */
  stalenessHint: string | null;
  /** True when timeline/receipts are empty and mission is still warming up. */
  isSparse: boolean;
};

export type CompactExecutionMeta = {
  /** @deprecated prefer openclawModelLane — same value; legacy executor field name */
  lane?: string;
  openclawModelLane?: string;
  model?: string;
  resumedFromApproval?: boolean;
  /** Compact routing authority line (from execution_meta.routing). */
  routingLine?: string;
  /** Reconciled block (execution_meta.lane_truth) — one-line summary. */
  laneTruthLine?: string;
};

function eventTitle(type: string): string {
  switch (type) {
    case "created":
      return "Mission created";
    case "mission_status_changed":
      return "Status changed";
    case "approval_requested":
      return "Approval requested";
    case "approval_resolved":
      return "Approval resolved";
    case "receipt_recorded":
      return "Receipt recorded";
    case "routing_decided":
      return "Routing decided";
    case "memory_saved":
      return "Memory saved";
    case "memory_promoted":
      return "Memory promoted";
    case "memory_archived":
      return "Memory archived";
    default:
      return type.replace(/_/g, " ");
  }
}

function describeEventOneLine(ev: MissionEvent): string {
  const p = (ev.payload ?? null) as Record<string, unknown> | null;
  switch (ev.event_type) {
    case "created": {
      const text = p && typeof p.text === "string" ? p.text.trim() : "";
      return text ? text.slice(0, 160) : "Mission created";
    }
    case "mission_status_changed": {
      const from = p && typeof p.from === "string" ? p.from : "?";
      const to = p && typeof p.to === "string" ? p.to : "?";
      return `Status ${from} → ${to}`;
    }
    case "approval_requested": {
      const action = p && typeof p.action_type === "string" ? p.action_type : "Action";
      const reason = p && typeof p.reason === "string" ? p.reason.trim() : "";
      return reason ? `${action} — ${reason.slice(0, 120)}` : `${action} — approval requested`;
    }
    case "approval_resolved": {
      const decision = p && typeof p.decision === "string" ? p.decision : "recorded";
      const by = p && typeof p.decided_by === "string" ? p.decided_by : "";
      return by ? `Decision: ${decision} · ${by}` : `Decision: ${decision}`;
    }
    case "routing_decided": {
      const req = p && typeof p.requested_lane === "string" ? p.requested_lane : "";
      const act = p && typeof p.actual_lane === "string" ? p.actual_lane : "";
      const fb = p && p.fallback_applied === true;
      const pending = p && p.pending_approval === true;
      let line = "Routing decided";
      if (fb && req === "local_fast" && act === "gateway") {
        line = "Routing: local-fast → gateway (fallback)";
      } else if (act === "gateway") {
        line = "Routing: gateway";
      } else if (act === "local_fast") {
        line = "Routing: local-fast";
      }
      if (pending) line = `${line} · pending approval`;
      return line;
    }
    case "memory_saved": {
      const t = p && typeof p.title === "string" ? p.title.trim() : "";
      const sk = p && typeof p.source_kind === "string" ? p.source_kind : "manual";
      return t ? `Memory saved · ${t} (${sk})` : `Operator memory saved (${sk})`;
    }
    case "memory_promoted": {
      const t = p && typeof p.title === "string" ? p.title.trim() : "";
      const sk = p && typeof p.source_kind === "string" ? p.source_kind : "";
      return t ? `Memory promoted · ${t}${sk ? ` · ${sk}` : ""}` : "Memory promoted";
    }
    case "memory_archived": {
      const t = p && typeof p.title === "string" ? p.title.trim() : "";
      return t ? `Memory archived · ${t}` : "Memory archived";
    }
    case "receipt_recorded": {
      const summary = p && typeof p.summary === "string" ? p.summary.trim() : "";
      return summary ? summary.slice(0, 160) : operatorCopy.receiptNoSummary;
    }
    default:
      return eventTitle(ev.event_type);
  }
}

function blockerFromMission(mission: Mission, lastStatusEvent: MissionEvent | null): string | null {
  if (mission.status === "blocked") {
    const hint = mission.summary?.trim();
    if (hint) return hint.slice(0, 200);
    return "Mission is blocked.";
  }
  if (mission.status === "failed") {
    const hint = mission.summary?.trim();
    if (hint) return hint.slice(0, 200);
    return "Mission failed.";
  }
  if (lastStatusEvent?.event_type === "mission_status_changed") {
    const p = lastStatusEvent.payload as Record<string, unknown> | null;
    const to = p && typeof p.to === "string" ? p.to : "";
    if (to === "blocked") {
      const reason = p && typeof p.reason === "string" ? String(p.reason).trim() : "";
      return reason ? reason.slice(0, 200) : "Execution blocked.";
    }
  }
  return null;
}

function lastStatusChangeEvent(events: MissionEvent[]): MissionEvent | null {
  const sorted = [...events].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return sorted.find((e) => e.event_type === "mission_status_changed") ?? null;
}

/**
 * Derive a compact executive summary from mission + related lists.
 * Receipts may be omitted (e.g. mission list cards) — receipt line stays null.
 */
export function deriveExecutiveMissionSummary(
  mission: Mission,
  events: MissionEvent[],
  approvals: Approval[],
  receipts: Receipt[] | null
): ExecutiveMissionSummary {
  const phaseView = deriveOperatorMissionPhase(mission, events, approvals, receipts);

  const sortedEv = [...events].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const lastMeaningful = sortedEv[0] ?? null;

  const pending = approvals.filter((a) => a.mission_id === mission.id && a.status === "pending");
  let pendingApprovalLine: string | null = null;
  if (pending.length > 0) {
    pendingApprovalLine = pending
      .map((a) => {
        const r = a.reason?.trim();
        return r ? `${a.action_type} — ${r.slice(0, 80)}` : a.action_type;
      })
      .join(" · ");
  } else if (mission.status === "awaiting_approval") {
    pendingApprovalLine = "Approval pending";
  }

  const latestExec = deriveLatestExecutionResult(mission, events, receipts);
  const latestReceiptLine = latestExec.hasResult ? latestExec.resultDetailLine : null;

  const lastStatusEv = lastStatusChangeEvent(events);
  const blockerLine = blockerFromMission(mission, lastStatusEv);

  const isSparse =
    events.length === 0 &&
    (!receipts || receipts.length === 0) &&
    mission.status !== "awaiting_approval" &&
    mission.status !== "blocked" &&
    mission.status !== "failed";

  const stalenessHint = deriveMissionStalenessHint(mission, events, phaseView.phase);

  return {
    status: mission.status,
    phase: phaseView.phase,
    phaseLabel: phaseView.label,
    lastEventLine: lastMeaningful ? describeEventOneLine(lastMeaningful) : null,
    lastEventAt: lastMeaningful?.created_at ?? null,
    blockerLine,
    latestReceiptLine,
    pendingApprovalLine,
    stalenessHint,
    isSparse,
  };
}

export function compactExecutionMeta(raw: unknown): CompactExecutionMeta | null {
  if (raw == null || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const openclawModelLane =
    typeof o.openclaw_model_lane === "string"
      ? o.openclaw_model_lane
      : typeof o.lane === "string"
        ? o.lane
        : undefined;
  const lane = openclawModelLane;
  const model =
    typeof o.model === "string"
      ? o.model
      : typeof o.gateway_model === "string"
        ? o.gateway_model
        : typeof o.model_id === "string"
          ? o.model_id
          : typeof o.model_name === "string"
            ? o.model_name
            : undefined;
  const resumedFromApproval = o.resumed_from_approval === true;
  let routingLine: string | undefined;
  const routing = o.routing;
  if (routing && typeof routing === "object") {
    const r = routing as Record<string, unknown>;
    const req = typeof r.requested_lane === "string" ? r.requested_lane : "";
    const act = typeof r.actual_lane === "string" ? r.actual_lane : "";
    const fb = r.fallback_applied === true;
    if (req && act) {
      if (fb && req === "local_fast" && act === "gateway") {
        routingLine = "mission route: local-fast → gateway (no local mission executor)";
      } else {
        routingLine = `mission route: ${req} → ${act}`;
      }
    }
  }
  let laneTruthLine: string | undefined;
  const lt = o.lane_truth;
  if (lt && typeof lt === "object") {
    const t = lt as Record<string, unknown>;
    const oml = typeof t.openclaw_model_lane === "string" ? t.openclaw_model_lane : "";
    const req = typeof t.requested_lane === "string" ? t.requested_lane : "";
    const ral = typeof t.routing_actual_lane === "string" ? t.routing_actual_lane : "";
    if (oml && req && ral) {
      laneTruthLine = `OpenClaw model: ${oml} · mission path: ${req}→${ral}`;
    } else if (oml) {
      laneTruthLine = `OpenClaw model lane: ${oml}`;
    }
  }
  if (!openclawModelLane && !model && !resumedFromApproval && !routingLine && !laneTruthLine) return null;
  return {
    lane,
    openclawModelLane,
    model,
    resumedFromApproval,
    routingLine,
    laneTruthLine,
  };
}

export function formatExecutionMetaParts(meta: CompactExecutionMeta): string[] {
  const parts: string[] = [];
  if (meta.laneTruthLine) parts.push(meta.laneTruthLine);
  else {
    if (meta.openclawModelLane || meta.lane) {
      parts.push(`OpenClaw model lane: ${meta.openclawModelLane ?? meta.lane}`);
    }
    if (meta.routingLine) parts.push(meta.routingLine);
  }
  if (meta.model) parts.push(meta.model);
  if (meta.resumedFromApproval) parts.push("Resumed after approval");
  return parts;
}

/** Whether `ExecutiveMissionCardLine` will render a line (vs. falling back to description). */
export function hasExecutiveCardLine(summary: ExecutiveMissionSummary): boolean {
  return (
    summary.phaseLabel.trim().length > 0 ||
    summary.stalenessHint != null ||
    summary.pendingApprovalLine != null ||
    summary.blockerLine != null ||
    summary.lastEventLine != null ||
    summary.isSparse
  );
}
