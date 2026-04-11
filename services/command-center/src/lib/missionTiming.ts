import type { Mission, MissionEvent } from "./types";

/** Derived from mission events + mission row — no extra telemetry. */
export type MissionTimingModel = {
  createdAt: string | null;
  approvalRequestedAt: string | null;
  approvalResolvedAt: string | null;
  firstReceiptAt: string | null;
  /** Last mission_status_changed to a terminal status, if present. */
  terminalStatusEventAt: string | null;
  /** created → approval_requested */
  msToApprovalRequest: number | null;
  /** approval_requested → approval_resolved (operator + runtime) */
  msGovernanceWindow: number | null;
  /** approval_resolved → first receipt, or created → first receipt if no approval path */
  msToFirstExecutionResult: number | null;
};

function parseIsoMs(iso: string): number {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? NaN : t;
}

function msBetween(startIso: string | null, endIso: string | null): number | null {
  if (!startIso?.trim() || !endIso?.trim()) return null;
  const a = parseIsoMs(startIso);
  const b = parseIsoMs(endIso);
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return null;
  return b - a;
}

/**
 * Sort chronologically; tie-break by id for stable ordering.
 */
function sortEventsChronological(events: MissionEvent[]): MissionEvent[] {
  return [...events].sort((a, b) => {
    const t = a.created_at.localeCompare(b.created_at);
    if (t !== 0) return t;
    return a.id.localeCompare(b.id);
  });
}

/**
 * Derive timing anchors from persisted events. Uses `mission.created_at` as fallback for created if no `created` event.
 */
export function deriveMissionTiming(events: MissionEvent[], mission: Mission): MissionTimingModel {
  const sorted = sortEventsChronological(events);

  let createdAt: string | null = mission.created_at;
  let approvalRequestedAt: string | null = null;
  let approvalResolvedAt: string | null = null;
  let firstReceiptAt: string | null = null;
  let terminalStatusEventAt: string | null = null;

  for (const e of sorted) {
    if (e.event_type === "created") {
      createdAt = e.created_at;
    }
    if (e.event_type === "approval_requested") {
      approvalRequestedAt = e.created_at;
    }
    if (e.event_type === "approval_resolved") {
      approvalResolvedAt = e.created_at;
    }
    if (e.event_type === "receipt_recorded" && !firstReceiptAt) {
      firstReceiptAt = e.created_at;
    }
    if (e.event_type === "mission_status_changed") {
      const p = e.payload as { to?: string } | null;
      const to = p?.to;
      if (to === "complete" || to === "failed" || to === "blocked") {
        terminalStatusEventAt = e.created_at;
      }
    }
  }

  const msToApprovalRequest = msBetween(createdAt, approvalRequestedAt);
  const msGovernanceWindow = msBetween(approvalRequestedAt, approvalResolvedAt);

  let msToFirstExecutionResult: number | null = null;
  if (approvalResolvedAt && firstReceiptAt) {
    msToFirstExecutionResult = msBetween(approvalResolvedAt, firstReceiptAt);
  } else if (firstReceiptAt && createdAt && !approvalRequestedAt) {
    msToFirstExecutionResult = msBetween(createdAt, firstReceiptAt);
  } else if (firstReceiptAt && createdAt) {
    msToFirstExecutionResult = msBetween(createdAt, firstReceiptAt);
  }

  return {
    createdAt,
    approvalRequestedAt,
    approvalResolvedAt,
    firstReceiptAt,
    terminalStatusEventAt,
    msToApprovalRequest,
    msGovernanceWindow,
    msToFirstExecutionResult,
  };
}

/** Compact human duration for operator UI (no sub-second noise). */
export function formatDurationHuman(ms: number | null): string {
  if (ms == null || ms < 0) return "—";
  if (ms < 1000) return "<1s";
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const s = sec % 60;
  if (min < 60) return s > 0 ? `${min}m ${s}s` : `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}
