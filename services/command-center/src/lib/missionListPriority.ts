import type { Approval, Mission, MissionEvent, Receipt } from "./types";
import { operatorCopy } from "./operatorCopy";
import { deriveOperatorMissionPhase, type OperatorMissionPhase } from "./missionPhase";
import { deriveMissionTiming, formatDurationHuman } from "./missionTiming";

/**
 * Presentation-only ordering for overview and mission list.
 * Uses the same inputs as `deriveOperatorMissionPhase` — not a backend contract or second source of truth.
 */

const PHASE_LIST_RANK: Record<OperatorMissionPhase, number> = {
  awaiting_approval: 0,
  resumed_waiting_for_execution: 1,
  executing: 2,
  execution_evidence_received: 3,
  blocked: 4,
  failed: 4,
  complete: 5,
};

function isTerminalPhase(p: OperatorMissionPhase): boolean {
  return p === "complete" || p === "failed" || p === "blocked";
}

function safeMsSince(iso: string | null): number {
  if (!iso?.trim()) return 0;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 0;
  const d = Date.now() - t;
  return Number.isNaN(d) ? 0 : Math.max(0, d);
}

/** Latest `receipt_recorded` timestamp from the timeline, if any. */
export function lastReceiptRecordedAt(events: MissionEvent[]): string | null {
  let best: string | null = null;
  for (const e of events) {
    if (e.event_type !== "receipt_recorded") continue;
    if (!best || e.created_at.localeCompare(best) > 0) best = e.created_at;
  }
  return best;
}

/**
 * How "long waiting" a mission is for same-phase ordering (non-terminal: larger = staler = sort first).
 * Terminal phases return 0; use `mission.updated_at` in the comparator instead.
 */
export function getStalenessMsForListing(
  mission: Mission,
  events: MissionEvent[],
  phase: OperatorMissionPhase
): number {
  const timing = deriveMissionTiming(events, mission);
  switch (phase) {
    case "awaiting_approval": {
      const anchor = timing.approvalRequestedAt || timing.createdAt || mission.created_at;
      return safeMsSince(anchor);
    }
    case "resumed_waiting_for_execution":
    case "executing": {
      const anchor = timing.approvalResolvedAt || mission.updated_at || mission.created_at;
      return safeMsSince(anchor);
    }
    case "execution_evidence_received": {
      const last = lastReceiptRecordedAt(events) || timing.firstReceiptAt;
      if (!last) return safeMsSince(mission.updated_at);
      return safeMsSince(last);
    }
    default:
      return 0;
  }
}

/**
 * Compact staleness line for non-terminal operator phases. Calm copy — not a failure diagnosis.
 */
export function deriveMissionStalenessHint(
  mission: Mission,
  events: MissionEvent[],
  phase: OperatorMissionPhase
): string | null {
  if (isTerminalPhase(phase)) return null;

  const timing = deriveMissionTiming(events, mission);

  switch (phase) {
    case "awaiting_approval": {
      const anchor = timing.approvalRequestedAt || timing.createdAt || mission.created_at;
      const ms = safeMsSince(anchor);
      if (ms <= 0) return null;
      return `Waiting ${formatDurationHuman(ms)} for approval`;
    }
    case "resumed_waiting_for_execution":
    case "executing": {
      const anchor = timing.approvalResolvedAt || mission.updated_at || mission.created_at;
      const ms = safeMsSince(anchor);
      if (ms <= 0) return null;
      return `No execution output yet - ${formatDurationHuman(ms)}`;
    }
    case "execution_evidence_received": {
      const last = lastReceiptRecordedAt(events) || timing.firstReceiptAt;
      if (!last?.trim()) return null;
      const ms = safeMsSince(last);
      if (ms <= 0) return null;
      return `Last execution update ${formatDurationHuman(ms)} ago`;
    }
    default:
      return null;
  }
}

/**
 * Sort key for overview / list: phase rank ascending, then within phase staler first (non-terminal)
 * or newest `updated_at` first (terminal).
 */
export function compareMissionsForOperatorListing(
  a: Mission,
  b: Mission,
  eventsByMissionId: Record<string, MissionEvent[]>,
  approvals: Approval[],
  receipts: Receipt[] | null
): number {
  const evA = eventsByMissionId[a.id] ?? [];
  const evB = eventsByMissionId[b.id] ?? [];
  const phaseA = deriveOperatorMissionPhase(a, evA, approvals, receipts).phase;
  const phaseB = deriveOperatorMissionPhase(b, evB, approvals, receipts).phase;
  const rankA = PHASE_LIST_RANK[phaseA];
  const rankB = PHASE_LIST_RANK[phaseB];
  if (rankA !== rankB) return rankA - rankB;

  if (isTerminalPhase(phaseA) && isTerminalPhase(phaseB)) {
    const tb = Date.parse(b.updated_at);
    const ta = Date.parse(a.updated_at);
    const nb = Number.isNaN(tb) ? 0 : tb;
    const na = Number.isNaN(ta) ? 0 : ta;
    if (nb !== na) return nb - na;
    return a.id.localeCompare(b.id);
  }

  const sa = getStalenessMsForListing(a, evA, phaseA);
  const sb = getStalenessMsForListing(b, evB, phaseB);
  if (sa !== sb) return sb - sa;
  return a.id.localeCompare(b.id);
}

export function sortMissionsForOperatorListing(
  missions: Mission[],
  eventsByMissionId: Record<string, MissionEvent[]>,
  approvals: Approval[],
  receipts: Receipt[] | null
): Mission[] {
  return [...missions].sort((a, b) =>
    compareMissionsForOperatorListing(a, b, eventsByMissionId, approvals, receipts)
  );
}

/** Overview triage buckets — presentation only; phases come from `deriveOperatorMissionPhase`. */
export type OverviewGroupedMissions = {
  needs_attention: Mission[];
  running: Mission[];
  recently_updated: Mission[];
  /** Terminal phases (complete / failed / blocked); capped separately for display. */
  settled: Mission[];
};

/** Primary triage buckets (URL `?triage=` and missions list handoff). */
export type OverviewTriageBucketKey = "needs_attention" | "running" | "recently_updated";

export type OverviewTriageOrSettled = OverviewTriageBucketKey | "settled";

/**
 * Map a mission to an overview bucket using the same rules as grouped overview (derived phase only).
 */
export function getMissionOverviewTriageBucket(
  mission: Mission,
  events: MissionEvent[],
  approvals: Approval[],
  receipts: Receipt[] | null
): OverviewTriageOrSettled {
  const phase = deriveOperatorMissionPhase(mission, events, approvals, receipts).phase;
  switch (phase) {
    case "awaiting_approval":
    case "resumed_waiting_for_execution":
      return "needs_attention";
    case "executing":
      return "running";
    case "execution_evidence_received":
      return "recently_updated";
    case "complete":
    case "failed":
    case "blocked":
      return "settled";
  }
}

const TRIAGE_URL_VALUES = ["needs_attention", "running", "recently_updated"] as const;

export type OverviewTriageUrlParam = (typeof TRIAGE_URL_VALUES)[number];

export const OVERVIEW_TRIAGE_SEARCH_PARAM = "triage";

export function parseOverviewTriageSearchParam(value: string | null): OverviewTriageUrlParam | null {
  if (!value?.trim()) return null;
  return TRIAGE_URL_VALUES.includes(value as OverviewTriageUrlParam)
    ? (value as OverviewTriageUrlParam)
    : null;
}

export const overviewTriageHandoffLabels: Record<OverviewTriageUrlParam, string> = {
  needs_attention: "Needs attention",
  running: "Running",
  recently_updated: "Recently updated",
};

const SETTLED_OVERVIEW_CAP = 5;

/**
 * Group missions for the Overview triage surface. Uses the same phase derivation and per-bucket
 * ordering as the mission list (`sortMissionsForOperatorListing`).
 */
export function groupMissionsForOverview(
  missions: Mission[],
  eventsByMissionId: Record<string, MissionEvent[]>,
  approvals: Approval[],
  receipts: Receipt[] | null
): OverviewGroupedMissions {
  const needs: Mission[] = [];
  const running: Mission[] = [];
  const recent: Mission[] = [];
  const settled: Mission[] = [];

  for (const m of missions) {
    const ev = eventsByMissionId[m.id] ?? [];
    const bucket = getMissionOverviewTriageBucket(m, ev, approvals, receipts);
    switch (bucket) {
      case "needs_attention":
        needs.push(m);
        break;
      case "running":
        running.push(m);
        break;
      case "recently_updated":
        recent.push(m);
        break;
      case "settled":
        settled.push(m);
        break;
    }
  }

  return {
    needs_attention: sortMissionsForOperatorListing(needs, eventsByMissionId, approvals, receipts),
    running: sortMissionsForOperatorListing(running, eventsByMissionId, approvals, receipts),
    recently_updated: sortMissionsForOperatorListing(recent, eventsByMissionId, approvals, receipts),
    settled: sortMissionsForOperatorListing(settled, eventsByMissionId, approvals, receipts),
  };
}

export function capSettledForOverview(settled: Mission[]): Mission[] {
  return settled.slice(0, SETTLED_OVERVIEW_CAP);
}

// --- Overview-only presentation: freshness cues + "Recently updated" age cap (not list authority) ---

/** Recent activity window for row cues and section "n new" counts (UI-only). */
export const OVERVIEW_FRESHNESS_WINDOW_MS = 8 * 60 * 1000;

/**
 * Overview "Recently updated" bucket: hide missions whose last execution evidence is older than this.
 * Full list / missions page still show all `execution_evidence_received` missions.
 */
export const OVERVIEW_RECENTLY_UPDATED_MAX_EVIDENCE_AGE_MS = 48 * 60 * 60 * 1000;

export type OverviewFreshnessCueKind = "new" | "just_updated" | "needs_review";

function latestEventOfType(events: MissionEvent[], eventType: string): MissionEvent | null {
  let best: MissionEvent | null = null;
  for (const e of events) {
    if (e.event_type !== eventType) continue;
    if (!best || e.created_at.localeCompare(best.created_at) > 0) best = e;
  }
  return best;
}

function isWithinWindowMs(iso: string | null, windowMs: number): boolean {
  if (!iso?.trim()) return false;
  const ms = safeMsSince(iso);
  return ms > 0 && ms <= windowMs;
}

/**
 * Last execution evidence "activity" time for overview staleness (receipt or mission update fallback).
 */
export function msSinceLastExecutionEvidenceForOverview(mission: Mission, events: MissionEvent[]): number {
  const lastReceipt = lastReceiptRecordedAt(events);
  const timing = deriveMissionTiming(events, mission);
  const anchor = lastReceipt || timing.firstReceiptAt || mission.updated_at;
  return safeMsSince(anchor);
}

/**
 * Drop very old `execution_evidence_received` missions from Overview only; re-sorts the remainder.
 */
export function filterOverviewRecentlyUpdatedBucket(
  missions: Mission[],
  eventsByMissionId: Record<string, MissionEvent[]>,
  approvals: Approval[],
  receipts: Receipt[] | null
): Mission[] {
  const kept = missions.filter((m) => {
    const ev = eventsByMissionId[m.id] ?? [];
    return (
      msSinceLastExecutionEvidenceForOverview(m, ev) <= OVERVIEW_RECENTLY_UPDATED_MAX_EVIDENCE_AGE_MS
    );
  });
  return sortMissionsForOperatorListing(kept, eventsByMissionId, approvals, receipts);
}

/**
 * Single restrained label for overview triage rows (derived from existing timestamps only).
 */
export function deriveOverviewRowFreshnessCue(
  mission: Mission,
  events: MissionEvent[],
  approvals: Approval[],
  receipts: Receipt[] | null,
  bucket: OverviewTriageBucketKey | "settled"
): OverviewFreshnessCueKind | null {
  if (bucket === "running" || bucket === "settled") return null;

  const phase = deriveOperatorMissionPhase(mission, events, approvals, receipts).phase;
  const w = OVERVIEW_FRESHNESS_WINDOW_MS;

  const approvalRequested = latestEventOfType(events, "approval_requested");
  const approvalResolved = latestEventOfType(events, "approval_resolved");

  if (bucket === "needs_attention") {
    if (phase === "awaiting_approval") {
      if (isWithinWindowMs(approvalRequested?.created_at ?? null, w)) return "needs_review";
    }
    if (phase === "resumed_waiting_for_execution") {
      if (isWithinWindowMs(approvalResolved?.created_at ?? null, w)) return "just_updated";
    }
    if (isWithinWindowMs(mission.created_at, w)) return "new";
    return null;
  }

  if (bucket === "recently_updated") {
    const lastReceipt = lastReceiptRecordedAt(events);
    const timing = deriveMissionTiming(events, mission);
    const receiptAnchor = lastReceipt || timing.firstReceiptAt;
    if (isWithinWindowMs(receiptAnchor, w)) return "just_updated";
    if (isWithinWindowMs(mission.updated_at, w)) return "just_updated";
    if (isWithinWindowMs(mission.created_at, w)) return "new";
    return null;
  }

  return null;
}

export function overviewFreshnessCueLabel(kind: OverviewFreshnessCueKind): string {
  const o = operatorCopy.overviewFreshness;
  switch (kind) {
    case "new":
      return o.new;
    case "just_updated":
      return o.justUpdated;
    case "needs_review":
      return o.needsReview;
  }
}
