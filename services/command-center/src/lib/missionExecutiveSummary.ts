import type { Approval, Mission, MissionEvent, Receipt } from "./types";
import { operatorCopy } from "./operatorCopy";

/** Operator-facing one-screen read on mission state (no extra API). */
export type ExecutiveMissionSummary = {
  status: string;
  lastEventLine: string | null;
  lastEventAt: string | null;
  blockerLine: string | null;
  latestReceiptLine: string | null;
  pendingApprovalLine: string | null;
  /** True when timeline/receipts are empty and mission is still warming up. */
  isSparse: boolean;
};

export type CompactExecutionMeta = {
  lane?: string;
  model?: string;
  resumedFromApproval?: boolean;
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

  const lastReceipt = receipts?.length
    ? [...receipts].sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
    : null;
  let latestReceiptLine: string | null = null;
  if (lastReceipt) {
    const sum = lastReceipt.summary?.trim();
    latestReceiptLine = sum
      ? `${lastReceipt.receipt_type} · ${sum.slice(0, 120)}`
      : `${lastReceipt.receipt_type} · ${
          mission.status === "failed" ? operatorCopy.receiptNoSummaryFailed : operatorCopy.receiptNoSummary
        }`;
  }

  const lastStatusEv = lastStatusChangeEvent(events);
  const blockerLine = blockerFromMission(mission, lastStatusEv);

  const isSparse =
    events.length === 0 &&
    (!receipts || receipts.length === 0) &&
    mission.status !== "awaiting_approval" &&
    mission.status !== "blocked" &&
    mission.status !== "failed";

  return {
    status: mission.status,
    lastEventLine: lastMeaningful ? describeEventOneLine(lastMeaningful) : null,
    lastEventAt: lastMeaningful?.created_at ?? null,
    blockerLine,
    latestReceiptLine,
    pendingApprovalLine,
    isSparse,
  };
}

export function compactExecutionMeta(raw: unknown): CompactExecutionMeta | null {
  if (raw == null || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const lane = typeof o.lane === "string" ? o.lane : undefined;
  const model =
    typeof o.model === "string"
      ? o.model
      : typeof o.model_id === "string"
        ? o.model_id
        : typeof o.model_name === "string"
          ? o.model_name
          : undefined;
  const resumedFromApproval = o.resumed_from_approval === true;
  if (!lane && !model && !resumedFromApproval) return null;
  return { lane, model, resumedFromApproval };
}

export function formatExecutionMetaParts(meta: CompactExecutionMeta): string[] {
  const parts: string[] = [];
  if (meta.lane) parts.push(`Lane ${meta.lane}`);
  if (meta.model) parts.push(meta.model);
  if (meta.resumedFromApproval) parts.push("Resumed after approval");
  return parts;
}

/** Whether `ExecutiveMissionCardLine` will render a line (vs. falling back to description). */
export function hasExecutiveCardLine(summary: ExecutiveMissionSummary): boolean {
  return (
    summary.pendingApprovalLine != null ||
    summary.blockerLine != null ||
    summary.lastEventLine != null ||
    summary.isSparse
  );
}
